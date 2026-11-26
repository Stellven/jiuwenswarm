"""Revisable task-scoped work records; execution remains with the controller/jobs.

Patches are immutable observations, so evidence export and replay use the same
durability boundary as decisions. No registry, graph executor or polling loop.
"""
from __future__ import annotations

import json
import time

from .store import NotFound, StaleRevision, encoded, identifier

KIND = 'taskgraph_patch'
KINDS = frozenset('inspect integrate build measure tune investigate decide accept report deliver'.split())
STATES = frozenset('proposed ready running blocked done failed cancelled superseded'.split())
TERMINAL = {'cancelled', 'superseded'}
NODE_FIELDS = {'node_id', 'kind', 'title', 'capability', 'inputs', 'depends_on', 'state',
               'attempt_ids', 'evidence_ids', 'created_by_decision_rev', 'reason',
               'outcome', 'entities', 'requires_evidence', 'resources', 'engine_slice', 'branch', 'check',
               'node_contract', 'hold', 'retry_from', 'checks_after', 'final_contract'}
OPERATOR_OPS = ('hold', 'release', 'reopen', 'retire')  # host-recorded operator patches; agents cannot issue them
SCHEDULER_OPS = ('finalize',)  # host-recorded after scheduler.finalize admits a final node contract


def initialize(db):
    """Add optional decision fields before Store discovers its JSON columns."""
    columns = {r['name'] for r in db.execute('PRAGMA table_info(decisions)')}
    for name, declaration in {'plan_patch': 'JSON', 'expected_graph_rev': 'INTEGER'}.items():
        if name not in columns:
            db.execute(f'ALTER TABLE decisions ADD COLUMN {name} {declaration}')


def _object(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError('Invalid or missing plan fields')


def _revision(value):
    if type(value) is not int or value < 0:
        raise ValueError('Plan revision must be a nonnegative integer')


def _ids(value):
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise ValueError('Plan references must be lists of nonempty identifiers')
    if len(set(value)) != len(value):
        raise ValueError('Duplicate plan reference')


def _node(value, decision_rev):
    _object(value, NODE_FIELDS, {'node_id', 'kind', 'title'})
    identifier(value['node_id'])
    identifier(value['title'])
    if value.get('created_by_decision_rev', decision_rev) != decision_rev:
        raise ValueError('Node creation decision is host-controlled')
    return dict(capability=None, inputs=[], depends_on=[], state='proposed',
                attempt_ids=[], evidence_ids=[], reason='') | value | {
                    'created_by_decision_rev': decision_rev}


def _validate(nodes, component_cc=None):
    for node in nodes.values():
        if node['kind'] not in KINDS or node['state'] not in STATES:
            raise ValueError('Unknown plan kind or state')
        cap = node['capability']
        if cap is not None and (not isinstance(cap, str) or '.' not in cap or any(not p for p in cap.split('.'))):
            raise ValueError('capability must be CC id.capability or null')
        for field in ('inputs', 'depends_on', 'attempt_ids', 'evidence_ids'):
            _ids(node[field])
        if not isinstance(node['reason'], str):
            raise ValueError('Plan reason must be text')
        if 'outcome' in node and (not isinstance(node['outcome'], str) or not node['outcome'].strip()):
            raise ValueError('Plan outcome must be nonempty text')
        if 'branch' in node:
            from .branch_workbench import validate_branch
            validate_branch(node['branch'])
        if 'engine_slice' in node:
            from .ontology import validate_slice
            validate_slice(node['engine_slice'], component_cc)
        if 'check' in node:
            from .node_check import validate_spec
            validate_spec(node['check'])
        if 'node_contract' in node and (not isinstance(node['node_contract'], str) or not node['node_contract']):
            raise ValueError('node_contract names a node contract of the task contract')
        if 'hold' in node and (not isinstance(node['hold'], str) or not node['hold'].strip()):
            raise ValueError('A node hold carries a nonempty reason')
        if 'retry_from' in node and (type(node['retry_from']) is not int or not 0 <= node['retry_from'] <= len(node['attempt_ids'])):
            raise ValueError('retry_from must index the node attempt list')
        if 'entities' in node:
            _ids(node['entities'])
        if 'requires_evidence' in node:
            from .ontology import validate_quantities
            _ids(node['requires_evidence'])
            validate_quantities(node['requires_evidence'])
        if 'resources' in node:
            _object(node['resources'], {'class'}, {'class'})
            if node['resources']['class'] not in {'gpu', 'build', 'cpu'}:
                raise ValueError('Plan resource class must be gpu, build or cpu')
        if any(dep not in nodes for dep in node['depends_on']):
            raise ValueError('Plan dependency does not exist')
        if node['state'] == 'done' and not node['evidence_ids']:
            raise ValueError('A done node requires evidence_ids')
        # Suggestions/readiness precede submission: they cannot name a future attempt. A node planned
        # from a node contract is evidenced by its output checks instead (a lab may do the build).
        if (node['kind'] in {'build', 'measure'} and node['state'] in {'running', 'done', 'failed'}
                and not node['attempt_ids'] and not node.get('node_contract')):
            raise ValueError('Executing build/measure nodes require attempt_ids')
        if node['state'] in {'ready', 'running', 'done'} and any(nodes[d]['state'] != 'done' for d in node['depends_on']):
            raise ValueError('Node is not ready: dependencies must all be done')
    # Iterative Kahn walk avoids Python recursion limits on long task histories.
    degree = {key: len(n['depends_on']) for key, n in nodes.items()}
    children = {key: [] for key in nodes}
    for key, node in nodes.items():
        for dep in node['depends_on']:
            children[dep].append(key)
    frontier = [key for key, n in degree.items() if n == 0]
    visited = 0
    while frontier:
        key = frontier.pop()
        visited += 1
        for child in children[key]:
            degree[child] -= 1
            if not degree[child]:
                frontier.append(child)
    if visited != len(nodes):
        raise ValueError('Plan dependency cycle')


def _descendants(nodes, key):
    out, frontier = [], [key]
    while frontier:
        parent = frontier.pop()
        for child, node in nodes.items():
            if parent in node['depends_on'] and child not in out:
                out.append(child)
                frontier.append(child)
    return out


def _restart(node, reason, since=None):
    """Back to proposed for a fresh attempt/check; earlier attempts and node checks stay recorded but no
    longer count (node checks recorded before the ``since`` plan record are ignored by the done gate)."""
    node.update(state='proposed', reason=reason, evidence_ids=[], retry_from=len(node['attempt_ids']))
    node.pop('final_contract', None)  # a fresh attempt gets a fresh final node contract from the scheduler
    if since:
        node['checks_after'] = since


def _apply_operator(nodes, patch, component_cc=None):
    """Operator pause/resume. hold stops a node from starting or closing, release lifts it, and reopen
    sends a failed (or finished) node and its descendants back to proposed. Upstream done nodes, their
    outputs and passed checks are untouched, so a run continues from the node instead of restarting."""
    _object(patch, set(OPERATOR_OPS))
    if not patch or not any(patch.values()):
        raise ValueError('Operator patch must contain an operation')
    for op, changes in patch.items():
        if not isinstance(changes, list):
            raise ValueError('Plan operations must be lists')
        for change in changes:
            _object(change, {'node_id', 'reason', 'since'}, {'node_id', 'reason'})
            key = identifier(change['node_id'])
            reason = change['reason']
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError('Operator patches need a reason')
            if key not in nodes:
                raise ValueError('Unknown plan node: ' + key)
            node = nodes[key]
            if node['state'] in TERMINAL:
                raise ValueError('Cancelled/superseded nodes are terminal')
            if op == 'hold':
                if node['state'] == 'done':
                    raise ValueError(f'Node {key} is done; reopen it to run it again')
                node['hold'] = reason
            elif op == 'release':
                if 'hold' not in node:
                    raise ValueError(f'Node {key} is not held')
                del node['hold']
            elif op == 'retire':
                # A contract revision removed this node's work (checked by operator_patch): cancel the node and
                # drop it from the dependencies of the nodes after it. Its records stay.
                if node['state'] == 'running':
                    raise ValueError(f'Node {key} is running; cancel its attempts first')
                node.update(state='cancelled', reason='retired by operator: ' + reason)
                node.pop('hold', None)
                for other in nodes.values():
                    if key in other.get('depends_on', []):
                        other['depends_on'] = [d for d in other['depends_on'] if d != key]
            else:
                affected = [key] + _descendants(nodes, key)
                running = [k for k in affected if nodes[k]['state'] == 'running']
                if running:
                    raise ValueError('Cancel the running attempts first: ' + ', '.join(running))
                since = change.get('since')
                _restart(node, 'reopened by operator: ' + reason, since)
                for child in affected[1:]:
                    if nodes[child]['state'] not in TERMINAL | {'proposed'}:
                        _restart(nodes[child], f'upstream {key} reopened by operator', since)
    _validate(nodes, component_cc)


def _apply_scheduler(nodes, patch, component_cc=None):
    """Record an admitted final node contract on its graph node: its digest and the checks it implies."""
    _object(patch, set(SCHEDULER_OPS), set(SCHEDULER_OPS))
    for change in patch['finalize']:
        _object(change, {'node_id', 'digest', 'check'}, {'node_id', 'digest', 'check'})
        key = identifier(change['node_id'])
        if key not in nodes:
            raise ValueError('Unknown plan node: ' + key)
        node = nodes[key]
        if node['state'] not in {'proposed', 'ready'}:
            raise ValueError(f"Node {key} is {node['state']}; only a node about to run is finalized")
        if node.get('final_contract'):
            raise ValueError(f'Node {key} already has a final node contract')
        node.update(final_contract=change['digest'], check=change['check'])
    _validate(nodes, component_cc)


def _apply(nodes, patch, decision_rev, component_cc=None, operator=False, scheduler=False):
    """Pure patch application. Caller owns the detached node map."""
    if operator:
        return _apply_operator(nodes, patch, component_cc)
    if scheduler:
        return _apply_scheduler(nodes, patch, component_cc)
    _object(patch, {'add', 'update', 'cancel', 'supersede'})
    if not patch or not any(patch.values()):
        raise ValueError('Plan patch must contain an operation')
    for operations in patch.values():
        if not isinstance(operations, list):
            raise ValueError('Plan operations must be lists')
    touched = set()
    for value in patch.get('add', []):
        if 'final_contract' in value:
            raise ValueError('Only the scheduler finalizes a node contract')
        node = _node(value, decision_rev)
        key = node['node_id']
        if key in nodes:
            raise ValueError('Plan node already exists: ' + key)
        nodes[key] = node
    for operation in ('update', 'cancel', 'supersede'):
        for change in patch.get(operation, []):
            allowed = {'node_id', 'state', 'evidence_ids', 'attempt_ids', 'depends_on', 'reason',
                       'outcome', 'entities', 'requires_evidence', 'resources', 'engine_slice', 'branch'} if operation == 'update' else {'node_id', 'reason'} | ({'by'} if operation == 'supersede' else set())
            required = {'node_id'} if operation == 'update' else allowed
            _object(change, allowed, required)
            key = identifier(change['node_id'])
            if key not in nodes:
                raise ValueError('Unknown plan node: ' + key)
            if key in touched:
                raise ValueError('Multiple mutations of one node in a patch')
            touched.add(key)
            node = nodes[key]
            if node['state'] in TERMINAL:
                raise ValueError('Cancelled/superseded nodes are terminal')
            if operation == 'update':
                if change.get('state') in TERMINAL:
                    raise ValueError('Use cancel/supersede operations with a reason')
                if node.get('hold') and change.get('state') in {'ready', 'running', 'done'}:
                    raise ValueError(f"Node {key} is held by the operator: {node['hold']}")
                for field, value in change.items():
                    if field in {'attempt_ids', 'evidence_ids'}:
                        _ids(value)
                        node[field] = list(dict.fromkeys(node[field] + value))
                    elif field != 'node_id':
                        if field == 'branch' and 'branch' in node:
                            from .branch_workbench import validate_branch
                            validate_branch(value)
                            for fixed in ('parent_id', 'hypothesis', 'allocation', 'capabilities'):
                                if value.get(fixed) != node['branch'].get(fixed):
                                    raise ValueError('Branch lineage, hypothesis, allocation and capabilities are immutable; fork to refine')
                        node[field] = value
            else:
                identifier(change['reason'])
                node.update(state='cancelled' if operation == 'cancel' else 'superseded', reason=change['reason'])
                if operation == 'supersede':
                    by = identifier(change['by'])
                    if by == key or by not in nodes or nodes[by]['state'] in TERMINAL:
                        raise ValueError('Superseding node must exist and be active')
                    node['superseded_by'] = by
    _validate(nodes, component_cc)


def _view(task_id, rev, nodes, history):
    ready, blocked = [], {}
    for key, node in nodes.items():
        if node['state'] in TERMINAL | {'done'}:
            continue
        reasons = [f"dependency {dep} is {nodes[dep]['state']}" for dep in node['depends_on'] if nodes[dep]['state'] != 'done']
        if node.get('hold'):
            reasons.append('held by operator: ' + node['hold'])
        if node['state'] in {'blocked', 'failed'}:
            reasons.append(node['reason'] or node['state'])
        if reasons:
            blocked[key] = reasons
        elif node['state'] in {'proposed', 'ready'}:
            ready.append(key)
    return dict(schema='factory.taskgraph/1', task_id=task_id, rev=rev,
                nodes=list(nodes.values()), ready_frontier=ready,
                blocked_reasons=blocked, history=history)


def replay(task_id, history, rev=None, *, component_cc=None):
    """Reconstruct a graph solely from committed patch records."""
    history = sorted(json.loads(encoded(history)), key=lambda h: h['rev'])
    if rev is None:
        rev = history[-1]['rev'] if history else 0
    _revision(rev)
    if rev > (history[-1]['rev'] if history else 0):
        raise NotFound('Plan revision not found')
    nodes, applied = {}, []
    for entry in history:
        if entry['rev'] > rev:
            break
        if entry['parent_rev'] != len(applied) or entry['rev'] != len(applied) + 1:
            raise ValueError('Noncontiguous plan history')
        _apply(nodes, entry['patch'], entry['decision_rev'], component_cc, operator=entry.get('origin') == 'operator',
               scheduler=entry.get('origin') == 'scheduler')
        applied.append(entry)
    return _view(task_id, rev, nodes, applied)


def from_records(data, rev=None):
    """Works with Store dumps, read-only story snapshots and exported bundles."""
    task = data['tasks'][0]
    # Curated bundles may hold rows from several tasks; the plan belongs to the primary task.
    history = [r['values'] for r in data.get('observations', [])
               if r['kind'] == KIND and r.get('task_id', task['task_id']) == task['task_id']]
    return replay(task['task_id'], history, rev, component_cc=task.get('component_cc'))


def _host(store, task_id, write=False):
    if hasattr(store, '_check'):
        store._check(task_id, write=write)
        return store._store
    return store


def plan_get(store, task_id, rev=None):
    host = _host(store, task_id)
    task = host.get_task(task_id)
    rows = host._db.execute('SELECT "values" FROM observations WHERE task_id=? AND kind=? ORDER BY created', (task_id, KIND))
    return replay(task_id, [json.loads(r[0]) for r in rows], rev, component_cc=task.get('component_cc'))


def dispatch_precondition(store, task_id, node_id):
    """Check an explicitly linked submission; the graph never schedules work."""
    if not isinstance(node_id, str) or not node_id.strip():
        raise ValueError('Dispatch node_id must be nonempty text')
    nodes = {n['node_id']: n for n in plan_get(store, task_id)['nodes']}
    if node_id not in nodes:
        raise ValueError('Dispatch node does not exist: ' + node_id)
    node = nodes[node_id]
    if node['state'] in {'superseded', 'cancelled', 'done', 'failed'}:
        raise ValueError(f"Dispatch node {node_id} is {node['state']}")
    if node.get('hold'):
        raise ValueError(f"Dispatch node {node_id} is held by the operator: {node['hold']}")
    unfinished = [f"{dep} is {nodes[dep]['state']}" for dep in node['depends_on'] if nodes[dep]['state'] != 'done']
    if unfinished:
        raise ValueError('Dispatch dependencies not done: ' + ', '.join(unfinished))


def _apply_patch(host, task_id, patch, expected_graph_rev, decision_rev, *, readable=(), seed=False, planner=None, operator=False,
                 scheduler=False):
    """Inside an existing Store transaction (also used by decision publication)."""
    _revision(expected_graph_rev)
    _revision(decision_rev)
    graph = plan_get(host, task_id)
    if graph['rev'] != expected_graph_rev:
        raise StaleRevision('Current plan revision differs from expected_graph_rev')
    if operator or scheduler:
        if seed or decision_rev != 0 or (operator and scheduler):
            raise ValueError('Operator and scheduler patches cite no decision')
    elif not seed:
        if decision_rev == 0 or not host._db.execute('SELECT 1 FROM decisions WHERE task_id=? AND rev=?', (task_id, decision_rev)).fetchone():
            raise ValueError('Plan patch must cite an existing decision revision in this task')
    elif decision_rev != 0 or graph['rev'] != 0:
        raise ValueError('Only the host initial suggestion may cite decision zero')
    patch = json.loads(encoded(patch))
    nodes = {n['node_id']: n for n in graph['nodes']}
    before = {key: dict(node) for key, node in nodes.items()}
    _apply(nodes, patch, decision_rev, host.get_task(task_id).get('component_cc'), operator=operator, scheduler=scheduler)
    from .planner import contract_gate
    contract_gate(host, task_id, nodes)  # contracted work stays covered, with its checks
    if not seed and not operator and not scheduler:  # a checked node is done only with its latest passing node check
        from .node_check import gate
        gate(host, task_id, before, nodes)
    if any('branch' in n for n in nodes.values()):
        from .branch_workbench import validate_graph
        validate_graph(host, task_id, nodes)
    for node in nodes.values():
        host.validate_evidence(task_id, node['evidence_ids'], readable)
        for aid in node['attempt_ids']:
            host._get('attempts', task_id, aid)
    rev = expected_graph_rev + 1
    record = dict(task_id=task_id, rev=rev, parent_rev=expected_graph_rev,
                  decision_rev=decision_rev, patch=patch,
                  origin='seed' if seed else 'operator' if operator else 'scheduler' if scheduler else 'decision', created=time.time())
    if planner:
        record['planner'] = planner
    host._insert('observations', dict(obs_id=f'{task_id}:plan:{rev}', task_id=task_id,
                 source_artifacts=[], kind=KIND, values=record, error={}, host_run={},
                 confidence=None, limitations='Work record; does not authorize execution or acceptance.', created=record['created']))
    host._telemetry_pending.append(('plan_patches', record))
    return _view(task_id, rev, nodes, graph['history'] + [record])


def plan_patch(store, task_id, patch, expected_graph_rev, decision_rev):
    host = _host(store, task_id, write=True)
    with host._transaction():
        return _apply_patch(host, task_id, patch, expected_graph_rev, decision_rev,
                            readable=getattr(store, 'readable', ()))


def operator_patch(store, task_id, op, node_id, reason, expected_graph_rev=None):
    """Record one operator hold, release or reopen (see _apply_operator) as a new graph revision."""
    if op not in OPERATOR_OPS:
        raise ValueError('Operator operation must be one of ' + ', '.join(OPERATOR_OPS))
    host = _host(store, task_id, write=True)
    with host._transaction():
        rev = plan_get(host, task_id)['rev'] if expected_graph_rev is None else expected_graph_rev
        change = dict(node_id=node_id, reason=reason)
        if op == 'reopen':  # this patch's own record: node checks before it no longer count
            change['since'] = f'{task_id}:plan:{rev + 1}'
        if op == 'retire':
            node = next((n for n in plan_get(host, task_id)['nodes'] if n['node_id'] == node_id), None)
            from .node_contract import for_task
            contracts = for_task(host.get_task(task_id)) or {'nodes': []}
            if node and node.get('node_contract') in {c['node_id'] for c in contracts['nodes']}:
                raise ValueError(f'Node {node_id}: its node contract {node["node_contract"]} is still in the task contract; '
                                 'retire only work a contract revision removed')
        return _apply_patch(host, task_id, {op: [change]}, rev, 0,
                            readable=getattr(store, 'readable', ()), operator=True)


def apply_decision_patch(store, task_id, decision, readable=()):
    patch = decision.get('plan_patch')
    expected = decision.get('expected_graph_rev')
    if patch is None and expected is None:
        return
    if patch is None or expected is None:
        raise ValueError('Decision plan_patch requires expected_graph_rev and vice versa')
    _apply_patch(store, task_id, patch, expected, decision['rev'], readable=readable)


def _format_two(task):
    try:
        from .contract import load
        return load(task['contract_id']).get('schema') == 'factory.contract/2'
    except (KeyError, OSError, ValueError):
        return False


def initial_plan(task):
    """Pure suggested work, with no invented attempt/evidence or execution claim."""
    component = task.get('component_cc')
    constraints = task.get('constraints', {})
    if isinstance(constraints, dict) and constraints.get('methodology_driven'):
        specs = [
            ('inspect', 'inspect', 'Inspect fixed contract and available evidence', 'factory.engine_inspector.inspect_strata'),
            ('diagnose', 'decide', 'Choose one uncertainty using methodology CCs', 'factory.methodology_diagnosis.diagnose'),
            ('experiment', 'measure', 'Submit a justified bounded experiment or stop with evidence', 'factory.lab_client.submit'),
            ('review', 'decide', 'Review outcomes and retained failures', 'factory.methodology_followup.followup'),
            ('report', 'report', 'Report findings and propose next input', None),
        ]
    else:
        specs = [
            ('inspect', 'inspect', 'Inspect task source and constraints', 'factory.engine_inspector.inspect'),
            ('applicability', 'decide', 'Assess component applicability', None),
            ('baseline-build', 'build', 'Build baseline', 'factory.builder.submit'),
            ('baseline-measure', 'measure', 'Measure baseline', 'factory.lab_client.submit'),
            ('integrate', 'integrate', f'Integrate {component or "selected component"}', None),
            ('candidate-build', 'build', 'Build candidate', 'factory.builder.submit'),
            ('candidate-measure', 'measure', 'Measure candidate against baseline', 'factory.lab_client.ab_submit'),
            ('accept', 'accept', 'Decide from comparable evidence', None),
            ('report', 'report', 'Report result and limitations', None),
        ]
    constraints = task.get('constraints', {})
    if _format_two(task):  # format-2 contracts are measured by a lab through the lab manager
        specs = [(key, kind, title, {'factory.lab_client.submit': 'factory.lab_manager.compose',
                                     'factory.lab_client.ab_submit': 'factory.lab_manager.compose'}.get(capability, capability))
                 for key, kind, title, capability in specs]
    if isinstance(constraints, dict) and constraints.get('external_model_execution_only'):
        specs = [(key, kind, ('Await imported capped model evidence' if kind == 'measure' else title),
                  None if kind == 'measure' else capability)
                 for key, kind, title, capability in specs]
    slice_id = constraints.get('engine_slice') if isinstance(constraints, dict) else None
    target = {}
    if slice_id is not None:
        from .ontology import validate_slice
        validate_slice(slice_id, component)
        target = {'engine_slice': slice_id}
    nodes = []
    for key, kind, title, capability in specs:
        nodes.append(_node(dict(node_id=key, kind=kind, title=title, capability=capability,
                     inputs=[task['task_id']] + (["contract:" + task['contract_id']] if target else []),
                     **target, depends_on=[nodes[-1]['node_id']] if nodes else [],
                     reason='Host suggestion; agent may cancel, replace or reorder from evidence.'), 0))
    return {'add': nodes}


def seed_plan(store, task, plan=None):
    """Revision 1 of the graph: the planner's plan, checked against the node contracts.

    Without node contracts (older contracts) the host's fixed suggestion is used. See planner.py.
    """
    from .planner import plan_for_task
    planner, nodes = plan_for_task(task, plan)
    patch = {'add': [_node(n, 0) for n in nodes]} if nodes else initial_plan(task)
    host = _host(store, task['task_id'], write=True)
    with host._transaction():
        return _apply_patch(host, task['task_id'], patch, 0, 0, seed=True, planner=planner or 'factory.taskgraph.initial_plan')


def reconcile_patch(graph, attempts):
    """Pure one-shot projection of durable attempt snapshots, not job submission.

    Latest linked attempt wins on retries. Success needs result evidence before
    becoming done; a successful job alone is not a scientific acceptance.
    """
    updates = []
    nodes = {n['node_id']: dict(n) for n in graph['nodes']}
    pending, ordered = set(nodes), []
    while pending:
        ready = [key for key in nodes if key in pending and all(d not in pending for d in nodes[key]['depends_on'])]
        if not ready:
            raise ValueError('Plan dependency cycle')
        ordered.extend(ready)
        pending.difference_update(ready)
    for key in ordered:
        node = nodes[key]
        if node['state'] in TERMINAL or node.get('hold'):
            continue  # a held node changes only by operator release
        deps_done = all(nodes[d]['state'] == 'done' for d in node['depends_on'])
        current = node['attempt_ids'][node.get('retry_from', 0):]  # attempts before a reopen no longer count
        if not current:
            if node['state'] in {'ready', 'running', 'done'} and not deps_done:
                reason = 'Dependencies no longer done after job reconciliation'
                updates.append(dict(node_id=key, state='blocked', reason=reason))
                node.update(state='blocked', reason=reason)
            continue
        aid = current[-1]
        attempt = attempts.get(aid, {})
        status = attempt.get('state', 'unknown')
        result_refs = attempt.get('result_refs', [])
        evidence = list(dict.fromkeys(node['evidence_ids'] + result_refs))
        if status == 'succeeded':
            state = 'done' if result_refs and deps_done else 'blocked'
            reason = 'Attempt succeeded' if state == 'done' else 'Attempt succeeded; result evidence or completed dependencies pending'
        elif status == 'failed':
            state, reason = 'failed', 'Linked attempt failed'
        elif status == 'running' and deps_done:
            state, reason = 'running', 'Linked attempt running'
        elif status == 'queued' and deps_done:
            state, reason = 'ready', 'Linked attempt queued'
        else:
            state, reason = 'blocked', f'Linked attempt {status}; requires agent review'
        if state != node['state'] or evidence != node['evidence_ids'] or reason != node['reason']:
            updates.append(dict(node_id=node['node_id'], state=state, evidence_ids=evidence, reason=reason))
            node.update(state=state, evidence_ids=evidence, reason=reason)
    return {'update': updates} if updates else {}


def reconcile(store, task_id, expected_graph_rev, decision_rev):
    """Reconcile stored job evidence once, using the same CAS and decision link."""
    host = _host(store, task_id, write=True)
    _revision(expected_graph_rev)
    _revision(decision_rev)
    with host._transaction():
        graph = plan_get(host, task_id)
        if graph['rev'] != expected_graph_rev:
            raise StaleRevision('Current plan revision differs from expected_graph_rev')
        attempts = {r['attempt_id']: host._decode('attempts', r) for r in host._db.execute('SELECT * FROM attempts WHERE task_id=?', (task_id,))}
        patch = reconcile_patch(graph, attempts)
        from .node_check import pending
        task, nodes = host.get_task(task_id), {n['node_id']: n for n in graph['nodes']}
        for update in patch.get('update', []):
            if update['state'] == 'done':
                reason = pending(host, task, dict(nodes[update['node_id']], evidence_ids=update['evidence_ids']))
                if reason:
                    update.update(state='blocked', reason='Attempt succeeded; ' + reason)
        if not patch:
            return graph
        return _apply_patch(host, task_id, patch, expected_graph_rev, decision_rev,
                            readable=getattr(store, 'readable', ()))


def to_json(graph):
    """Detached JSON-compatible object shared by native CCs and the monitor."""
    return json.loads(encoded(graph))


def render_text(graph):
    lines = [f"Plan {graph['task_id']} · graph rev {graph['rev']}"]
    depths = {}
    pending = list(graph['nodes'])
    while pending:
        remaining = []
        for node in pending:
            if any(dep not in depths for dep in node['depends_on']):
                remaining.append(node)
                continue
            depth = max((depths[d] + 1 for d in node['depends_on']), default=0)
            depths[node['node_id']] = depth
            lines.append('  ' * depth + f"[{node['state']}] {node['node_id']}: {node['title']}" +
                         (f" ({node['capability']})" if node['capability'] else ''))
            for reason in graph['blocked_reasons'].get(node['node_id'], []):
                lines.append('  ' * (depth + 1) + reason)
        pending = remaining
    lines.append('Ready frontier: ' + (', '.join(graph['ready_frontier']) or '(empty)'))
    lines.append('Revision history:')
    for entry in graph['history']:
        changes = '; '.join(f"{op}: " + ', '.join(n['node_id'] for n in values) for op, values in entry['patch'].items() if values)
        lines.append(f"  graph {entry['rev']} ← decision {entry['decision_rev']} ({entry['origin']}): {changes}")
    return '\n'.join(lines)


def to_dot(graph):
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    lines = ['digraph factory_plan {']
    for node in graph['nodes']:
        label = f"{node['node_id']} [{node['state']}]\n{node['title']}"
        lines.append(f'  {quote(node["node_id"])} [label={quote(label)}];')
        for dep in node['depends_on']:
            lines.append(f'  {quote(dep)} -> {quote(node["node_id"])};')
        if node.get('superseded_by'):
            lines.append(f'  {quote(node["node_id"])} -> {quote(node["superseded_by"])} [style=dashed,label="superseded"];')
    for entry in graph['history']:
        changes = ', '.join(f'{op} ' + '/'.join(n['node_id'] for n in values) for op, values in entry['patch'].items() if values)
        lines.append('  // ' + quote(f"graph {entry['rev']} decision {entry['decision_rev']}: {changes}"))
    return '\n'.join(lines + ['}'])
