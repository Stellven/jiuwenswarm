"""Revisable task-scoped work records; execution remains with the controller/jobs.

Patches are immutable observations, so evidence export and replay use the same
durability boundary as decisions. No registry, graph executor or polling loop.
"""
from __future__ import annotations

import json
import time

from .store import NotFound, StaleRevision, encoded, identifier

KIND = 'taskgraph_patch'
KINDS = frozenset('inspect integrate build measure tune investigate decide accept report'.split())
STATES = frozenset('proposed ready running blocked done failed cancelled superseded'.split())
TERMINAL = {'cancelled', 'superseded'}
NODE_FIELDS = {'node_id', 'kind', 'title', 'capability', 'inputs', 'depends_on', 'state',
               'attempt_ids', 'evidence_ids', 'created_by_decision_rev', 'reason',
               'outcome', 'entities', 'requires_evidence', 'resources', 'engine_slice'}


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


def _validate(nodes):
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
        if 'engine_slice' in node:
            from .ontology import validate_slice
            validate_slice(node['engine_slice'])
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
        # Suggestions/readiness precede submission: they cannot name a future attempt.
        if node['kind'] in {'build', 'measure'} and node['state'] in {'running', 'done', 'failed'} and not node['attempt_ids']:
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


def _apply(nodes, patch, decision_rev):
    """Pure patch application. Caller owns the detached node map."""
    _object(patch, {'add', 'update', 'cancel', 'supersede'})
    if not patch or not any(patch.values()):
        raise ValueError('Plan patch must contain an operation')
    for operations in patch.values():
        if not isinstance(operations, list):
            raise ValueError('Plan operations must be lists')
    touched = set()
    for value in patch.get('add', []):
        node = _node(value, decision_rev)
        key = node['node_id']
        if key in nodes:
            raise ValueError('Plan node already exists: ' + key)
        nodes[key] = node
    for operation in ('update', 'cancel', 'supersede'):
        for change in patch.get(operation, []):
            allowed = {'node_id', 'state', 'evidence_ids', 'attempt_ids', 'depends_on', 'reason',
                       'outcome', 'entities', 'requires_evidence', 'resources', 'engine_slice'} if operation == 'update' else {'node_id', 'reason'} | ({'by'} if operation == 'supersede' else set())
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
                for field, value in change.items():
                    if field in {'attempt_ids', 'evidence_ids'}:
                        _ids(value)
                        node[field] = list(dict.fromkeys(node[field] + value))
                    elif field != 'node_id':
                        node[field] = value
            else:
                identifier(change['reason'])
                node.update(state='cancelled' if operation == 'cancel' else 'superseded', reason=change['reason'])
                if operation == 'supersede':
                    by = identifier(change['by'])
                    if by == key or by not in nodes or nodes[by]['state'] in TERMINAL:
                        raise ValueError('Superseding node must exist and be active')
                    node['superseded_by'] = by
    _validate(nodes)


def _view(task_id, rev, nodes, history):
    ready, blocked = [], {}
    for key, node in nodes.items():
        if node['state'] in TERMINAL | {'done'}:
            continue
        reasons = [f"dependency {dep} is {nodes[dep]['state']}" for dep in node['depends_on'] if nodes[dep]['state'] != 'done']
        if node['state'] in {'blocked', 'failed'}:
            reasons.append(node['reason'] or node['state'])
        if reasons:
            blocked[key] = reasons
        elif node['state'] in {'proposed', 'ready'}:
            ready.append(key)
    return dict(schema='factory.taskgraph/1', task_id=task_id, rev=rev,
                nodes=list(nodes.values()), ready_frontier=ready,
                blocked_reasons=blocked, history=history)


def replay(task_id, history, rev=None):
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
        _apply(nodes, entry['patch'], entry['decision_rev'])
        applied.append(entry)
    return _view(task_id, rev, nodes, applied)


def from_records(data, rev=None):
    """Works with Store dumps, read-only story snapshots and exported bundles."""
    task_id = data['tasks'][0]['task_id']
    history = [r['values'] for r in data.get('observations', []) if r['kind'] == KIND]
    return replay(task_id, history, rev)


def _host(store, task_id, write=False):
    if hasattr(store, '_check'):
        store._check(task_id, write=write)
        return store._store
    return store


def plan_get(store, task_id, rev=None):
    host = _host(store, task_id)
    host.get_task(task_id)
    rows = host._db.execute('SELECT "values" FROM observations WHERE task_id=? AND kind=? ORDER BY created', (task_id, KIND))
    return replay(task_id, [json.loads(r[0]) for r in rows], rev)


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
    unfinished = [f"{dep} is {nodes[dep]['state']}" for dep in node['depends_on'] if nodes[dep]['state'] != 'done']
    if unfinished:
        raise ValueError('Dispatch dependencies not done: ' + ', '.join(unfinished))


def _apply_patch(host, task_id, patch, expected_graph_rev, decision_rev, *, readable=(), seed=False):
    """Inside an existing Store transaction (also used by decision publication)."""
    _revision(expected_graph_rev)
    _revision(decision_rev)
    graph = plan_get(host, task_id)
    if graph['rev'] != expected_graph_rev:
        raise StaleRevision('Current plan revision differs from expected_graph_rev')
    if not seed:
        if decision_rev == 0 or not host._db.execute('SELECT 1 FROM decisions WHERE task_id=? AND rev=?', (task_id, decision_rev)).fetchone():
            raise ValueError('Plan patch must cite an existing decision revision in this task')
    elif decision_rev != 0 or graph['rev'] != 0:
        raise ValueError('Only the host initial suggestion may cite decision zero')
    patch = json.loads(encoded(patch))
    nodes = {n['node_id']: n for n in graph['nodes']}
    _apply(nodes, patch, decision_rev)
    for node in nodes.values():
        host.validate_evidence(task_id, node['evidence_ids'], readable)
        for aid in node['attempt_ids']:
            host._get('attempts', task_id, aid)
    rev = expected_graph_rev + 1
    record = dict(task_id=task_id, rev=rev, parent_rev=expected_graph_rev,
                  decision_rev=decision_rev, patch=patch, origin='seed' if seed else 'decision', created=time.time())
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


def apply_decision_patch(store, task_id, decision, readable=()):
    patch = decision.get('plan_patch')
    expected = decision.get('expected_graph_rev')
    if patch is None and expected is None:
        return
    if patch is None or expected is None:
        raise ValueError('Decision plan_patch requires expected_graph_rev and vice versa')
    _apply_patch(store, task_id, patch, expected, decision['rev'], readable=readable)


def initial_plan(task):
    """Pure suggested work, with no invented attempt/evidence or execution claim."""
    component = task.get('component_cc')
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
    slice_id = constraints.get('engine_slice') if isinstance(constraints, dict) else None
    target = {}
    if slice_id is not None:
        from .ontology import validate_slice
        validate_slice(slice_id)
        target = {'engine_slice': slice_id}
    nodes = []
    for key, kind, title, capability in specs:
        nodes.append(_node(dict(node_id=key, kind=kind, title=title, capability=capability,
                     inputs=[task['task_id']] + (["contract:" + task['contract_id']] if target else []),
                     **target, depends_on=[nodes[-1]['node_id']] if nodes else [],
                     reason='Host suggestion; agent may cancel, replace or reorder from evidence.'), 0))
    return {'add': nodes}


def seed_plan(store, task):
    host = _host(store, task['task_id'], write=True)
    with host._transaction():
        return _apply_patch(host, task['task_id'], initial_plan(task), 0, 0, seed=True)


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
        if node['state'] in TERMINAL:
            continue
        deps_done = all(nodes[d]['state'] == 'done' for d in node['depends_on'])
        if not node['attempt_ids']:
            if node['state'] in {'ready', 'running', 'done'} and not deps_done:
                reason = 'Dependencies no longer done after job reconciliation'
                updates.append(dict(node_id=key, state='blocked', reason=reason))
                node.update(state='blocked', reason=reason)
            continue
        aid = node['attempt_ids'][-1]
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
