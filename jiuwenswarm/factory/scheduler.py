"""Scheduler: which planned nodes can run now, with what, and within which limits.

It reads the task graph (from the planner) and the node contracts (from the contract)
and works out the next work. It is deterministic and starts nothing: the agent works
the node, ``jobq`` orders the jobs it submits, and the host enforces what this module
decides:

* a node runs only when every predecessor is done (``taskgraph.dispatch_precondition``);
* a job that names a node is admitted only within the node's ``authority_ceiling`` and
  ``node_limits`` (``admitted``), atomically per node, and a retry with the same
  idempotency key is never charged twice;
* only the contracted deliver node may compose the lab package;
* a node is done only when every required output passed its check (``node_check``).

``next_work`` is what the agent sees at the start of every turn and through
``factory.evidence.plan_next``: for each node that can run, its objective, its inputs
resolved to the passing checks of the nodes that produced them, the outputs it owes with
their criteria and verifiers, the capsules that help, and what is left of its limits.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
import time

LIMIT_KINDS = {'build_attempts': ('build',), 'gpu_launches': ('lab',)}
# API capabilities that may name a node: (capsule, capsule capability, attempt kind charged).
NODE_CAPABILITIES = {'builder.submit': ('builder', 'submit', 'build'),
                     'lab.submit': ('lab_client', 'submit', 'lab'),
                     'lab.ab_submit': ('lab_client', 'ab_submit', 'lab'),
                     'lab_manager.compose': ('lab_manager', 'compose', None)}
WORKSPACE_EFFECTS = {'none': set(), 'read': {'workspace.read'}, 'write': {'workspace.read', 'workspace.write'}}


FINAL_KIND, REFUSAL_KIND = 'node_contract_final', 'node_contract_refusal'


def _contracts(host, task):
    from .node_contract import for_task
    if not task.get('contract_id'):
        return None
    try:
        return for_task(task)
    except (OSError, ValueError):
        return None


def _graph(host, task_id):
    from .taskgraph import plan_get
    return plan_get(host, task_id)


def _attempts(host, task_id, node_id):
    rows = host._db.execute('SELECT kind, request FROM attempts WHERE task_id=?', (task_id,))
    return [kind for kind, request in rows if json.loads(request or '{}').get('node_id') == node_id]


def _passed_output(host, task_id, node_id, output):
    from .node_check import checks_for
    checks = checks_for(host, task_id, node_id, output)
    if checks and checks[-1].get('state') == 'finished' and checks[-1].get('passed'):
        latest = checks[-1]
        return dict(node_id=node_id, check=latest['obs_id'], artifacts=latest['source_artifacts'],
                    **{k: latest[k] for k in ('found', 'diff_sha256', 'head') if latest.get(k)})
    return None


def _contract_input(task, name):
    from .contract import load
    try:
        declared = (load(task['contract_id']).get('inputs') or {}).get(name)
    except (OSError, ValueError):
        declared = None
    label = f'input {name} of contract {task["contract_id"]}'
    return dict(declared, input=label) if isinstance(declared, dict) else label


def _resolve(host, task, contract_node, graph_nodes):
    """Inputs of a node, with producers named by node contract mapped to the planner's graph nodes."""
    by_contract = {}
    for node in graph_nodes:
        if node.get('node_contract') and node['state'] not in {'cancelled', 'superseded'}:
            by_contract.setdefault(node['node_contract'], []).append(node)
    resolved = {}
    for item in contract_node.get('inputs', []):
        source = item['from']
        if source.startswith('task:'):
            resolved[item['name']] = {'from': source, 'value': task.get(source[5:])}
        elif source.startswith('contract:'):
            # The pinned declaration itself (digest, size, path), not just its name.
            resolved[item['name']] = {'from': source, 'value': _contract_input(task, source[9:])}
        else:
            producer, _, output = source.partition('.')
            producers = sorted(by_contract.get(producer, []), key=lambda n: n['state'] != 'done')
            value = next((v for v in (_passed_output(host, task['task_id'], n['node_id'], output) for n in producers) if v), None)
            resolved[item['name']] = {'from': source, 'value': value}
    return resolved


def remaining_limits(host, task_id, node_id, limits):
    kinds = _attempts(host, task_id, node_id)
    left = {}
    for limit, used_by in LIMIT_KINDS.items():
        if limit in limits:
            left[limit] = limits[limit] - sum(kind in used_by for kind in kinds)
    for limit in ('time_s', 'turns'):
        if limit in limits:
            left[limit] = limits[limit]  # advisory: the controller budget enforces wall clock and turns
    return left


def _existing_attempt(host, task_id, idem_key):
    return idem_key and host._db.execute('SELECT 1 FROM attempts WHERE task_id=? AND idem_key=?', (task_id, idem_key)).fetchone()


def charge(host, task_id, node_id, kind, idem_key=None):
    """Refuse a new job for a node that has used up its contract limit for that kind of job."""
    if _existing_attempt(host, task_id, idem_key):
        return  # an idempotent retry of a job already admitted
    task = host.get_task(task_id)
    graph_node = next((n for n in _graph(host, task_id)['nodes'] if n['node_id'] == node_id), None)
    if not graph_node or not graph_node.get('node_contract'):
        return
    contract_node = effective_contract(host, task_id, graph_node, _contracts(host, task))[0] or {}
    limits = contract_node.get('node_limits', {})
    for limit, used_by in LIMIT_KINDS.items():
        if kind in used_by and limit in limits and remaining_limits(host, task_id, node_id, limits)[limit] <= 0:
            raise ValueError(f'Node {node_id} has used its {limit} ({limits[limit]}) from its node contract')


def _capsule_effects(capsule, capability):
    import yaml
    from pathlib import Path
    declaration = yaml.safe_load((Path(__file__).with_name('ccs') / capsule / 'cc.yaml').read_text(encoding='utf-8'))
    return set(declaration['capabilities'][capability].get('changes', []))


def check_ceiling(contract_node, capsule, capability):
    """The node contract's authority ceiling must allow what the capability does."""
    ceiling = contract_node.get('authority_ceiling') or {}
    effects = _capsule_effects(capsule, capability)
    if 'effects' in ceiling and not effects <= set(ceiling['effects']):
        raise ValueError(f'{capsule}.{capability} needs {sorted(effects - set(ceiling["effects"]))}, '
                         f'beyond node {contract_node["node_id"]}\'s authority ceiling')
    workspace = ceiling.get('workspace')
    if workspace is not None and effects & {'workspace.read', 'workspace.write'} - WORKSPACE_EFFECTS[workspace]:
        raise ValueError(f'{capsule}.{capability} uses the workspace; node {contract_node["node_id"]} allows workspace {workspace}')


@contextmanager
def _node_lock(home, task_id, node_id):
    import fcntl
    import hashlib
    directory = home / 'locks'
    directory.mkdir(exist_ok=True)
    path = directory / ('node-' + hashlib.sha256(f'{task_id}\0{node_id}'.encode()).hexdigest()[:24] + '.lock')
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@contextmanager
def admitted(store, task_id, capability, inputs):
    """Admit a job that names a node; held while the job is submitted so limits cannot be raced."""
    if capability not in NODE_CAPABILITIES:
        yield
        return
    from .taskgraph import dispatch_precondition
    host = getattr(store, '_store', store)
    task = host.get_task(task_id)
    contracts = _contracts(host, task)
    capsule, cap, kind = NODE_CAPABILITIES[capability]
    node_id = inputs.get('node_id')
    if contracts is not None and capability == 'lab_manager.compose' and not node_id:
        raise ValueError('This task has node contracts: compose the lab package from its deliver node (node_id)')
    if not node_id:
        yield
        return
    with _node_lock(host.home, task_id, node_id):
        graph_node = next((n for n in _graph(host, task_id)['nodes'] if n['node_id'] == node_id), {})
        contract_node, needs_final = effective_contract(host, task_id, graph_node, contracts)
        if needs_final:
            raise ValueError(f'Node {node_id} has a preliminary node contract; the scheduler finalizes it before work starts')
        if contracts is not None and capability == 'lab_manager.compose' and (
                not contract_node or contract_node['kind'] != 'deliver' or graph_node.get('kind') != 'deliver'):
            raise ValueError(f'Node {node_id} is not the contracted deliver node; only it hands the engine to the lab manager')
        dispatch_precondition(store, task_id, node_id)
        if contract_node:
            check_ceiling(contract_node, capsule, cap)
        if kind:
            charge(host, task_id, node_id, kind, inputs.get('idem_key'))
        yield


def next_work(host, task_id):
    """The nodes that can run now and why the others cannot. Pure read."""
    from .node_check import effective_spec, outputs_of, pending
    task = host.get_task(task_id)
    graph = _graph(host, task_id)
    contracts = _contracts(host, task)
    nodes = {n['node_id']: n for n in graph['nodes']}
    runnable, waiting, done, to_finalize = [], {}, [], []
    for node in graph['nodes']:  # planner order
        key = node['node_id']
        if node['state'] == 'done':
            done.append(key)
            continue
        if node['state'] in {'cancelled', 'superseded'}:
            continue
        if node.get('hold'):
            waiting[key] = 'held by operator: ' + node['hold']
            continue
        unfinished = [d for d in node['depends_on'] if nodes[d]['state'] != 'done']
        if unfinished:
            waiting[key] = 'waiting for ' + ', '.join(unfinished)
            continue
        contract_node, needs_final = effective_contract(host, task_id, node, contracts)
        if needs_final and node['state'] != 'failed':
            waiting[key] = 'waiting for the scheduler to finalize its node contract'
            to_finalize.append(dict(node_id=key, node_contract=node['node_contract'], objective=contract_node['objective'],
                                    slots=[s['id'] for s in contract_node.get('slots', [])]))
            continue
        spec = effective_spec(task, node)
        item = dict(node_id=key, kind=node['kind'], state=node['state'], title=node['title'],
                    objective=(contract_node or {}).get('objective', node['title']),
                    outputs=[dict(name=o['name'], kind=o['kind'], required=o.get('required', True),
                                  **{k: o[k] for k in ('verifier', 'stage', 'review', 'criteria') if o.get(k)})
                             for o in outputs_of(spec)] if spec else [],
                    done_blocked_by=pending(host, task, node))
        if contract_node:
            item.update(node_contract=node['node_contract'],
                        requirement_ids=contract_node.get('requirement_ids', []),
                        helpful_ccs=(contract_node.get('work') or {}).get('helpful_ccs', []),
                        **({'bound_ccs': contract_node['work']['bound_ccs'], 'final_contract': node['final_contract']}
                           if (contract_node.get('work') or {}).get('bound_ccs') else {}),
                        inputs=_resolve(host, task, contract_node, graph['nodes']),
                        limits_left=remaining_limits(host, task_id, key, contract_node.get('node_limits', {})),
                        authority_ceiling=contract_node.get('authority_ceiling', {}),
                        hands_to=contract_node['hands_to'])
        if node['state'] == 'failed':
            waiting[key] = 'failed: ' + (node['reason'] or 'revise or supersede it')
            continue
        runnable.append(item)
    if contracts is not None:  # delivered = every node contract is done by some graph node
        done_contracts = {n.get('node_contract') for n in graph['nodes'] if n['state'] == 'done'}
        delivered = all(c['node_id'] in done_contracts for c in contracts['nodes'])
    else:
        delivered = bool(nodes) and all(n['state'] in {'done', 'cancelled', 'superseded'} for n in nodes.values())
    return dict(schema='factory.next-work/1', task_id=task_id, graph_rev=graph['rev'],
                planner=next((h.get('planner') for h in graph['history'] if h.get('origin') == 'seed'), None),
                runnable=runnable, waiting=waiting, done=done, delivered=delivered, to_finalize=to_finalize,
                held=[n['node_id'] for n in graph['nodes'] if n.get('hold')])


def brief(work):
    """A compact form for the agent's turn message."""
    return dict(graph_rev=work['graph_rev'], done=work['done'], waiting=work['waiting'],
                runnable=[{k: item[k] for k in ('node_id', 'kind', 'objective', 'outputs', 'done_blocked_by', 'bound_ccs',
                                                 'helpful_ccs', 'inputs', 'limits_left', 'hands_to') if k in item}
                          for item in work['runnable']],
                **({'to_finalize': [i['node_id'] for i in work['to_finalize']]} if work.get('to_finalize') else {}))


# -- preliminary -> final node contracts ------------------------------------------------------------

def recorded_finals(host, task_id):
    """Every admitted final node contract of the task, oldest first."""
    rows = host._db.execute('SELECT "values" FROM observations WHERE task_id=? AND kind=? ORDER BY created, rowid',
                            (task_id, FINAL_KIND))
    return [json.loads(r[0]) for r in rows]


def effective_contract(host, task_id, graph_node, contracts):
    """(the node contract work runs under, whether it still needs finalizing).

    A contract without ``stage: preliminary`` runs as written. A preliminary one runs under the final
    contract the scheduler admitted for this graph node, and until then nothing runs.
    """
    from .node_contract import node as contract_node_of
    from .node_finalize import is_preliminary
    name = (graph_node or {}).get('node_contract')
    contract = contract_node_of(contracts, name) if contracts and name else None
    if not is_preliminary(contract):
        return contract, False
    digest = graph_node.get('final_contract')
    if digest:
        for record in recorded_finals(host, task_id):
            if record['digest'] == digest and record['node_id'] == graph_node['node_id']:
                return record['final'], False
    return contract, True


def catalog():
    """Capsule id -> version, folder, purpose and capabilities, from the factory capsule folders."""
    import yaml
    from pathlib import Path
    found = {}
    for path in sorted(Path(__file__).with_name('ccs').glob('*/cc.yaml')):
        try:
            declaration = yaml.safe_load(path.read_text(encoding='utf-8'))
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(declaration, dict) and declaration.get('id'):
            purpose = declaration.get('purpose') or declaration.get('does') or declaration.get('summary') or ''
            found[declaration['id']] = dict(version=str(declaration.get('version', '')), folder=path.parent.name,
                                            purpose=str(purpose)[:300],
                                            capabilities=sorted((declaration.get('capabilities') or {}).keys()))
    return found


def _failures(host, task_id, graph, name):
    """What went wrong before for this node contract: failed or reopened nodes, and earlier finals."""
    finals = [r for r in recorded_finals(host, task_id) if r['node_contract'] == name]
    history = []
    for node in graph['nodes']:
        if node.get('node_contract') != name:
            continue
        if node['state'] in {'failed', 'superseded', 'cancelled'} or node.get('retry_from'):
            history.append(dict(node_id=node['node_id'], state=node['state'], reason=node.get('reason', ''),
                                attempts=len(node['attempt_ids']), outcome=node.get('outcome')))
    return history, [dict(node_id=r['node_id'], digest=r['digest'], diff=r['diff'], rationale=r['rationale'])
                     for r in finals]


def finalize_brief(store, task_id, node_id):
    """What the scheduler agent reads before it finalizes one node. Pure read."""
    from .node_contract import node as contract_node_of
    from .node_finalize import draft_final, is_preliminary
    host = getattr(store, '_store', store)
    if hasattr(store, '_check'):
        store._check(task_id)
    task = host.get_task(task_id)
    graph = _graph(host, task_id)
    node = next((n for n in graph['nodes'] if n['node_id'] == node_id), None)
    if node is None:
        raise ValueError('Unknown plan node: ' + node_id)
    contracts = _contracts(host, task)
    prelim = contract_node_of(contracts, node.get('node_contract')) if contracts and node.get('node_contract') else None
    if not is_preliminary(prelim):
        raise ValueError(f'Node {node_id} has no preliminary node contract')
    failures, earlier_finals = _failures(host, task_id, graph, node['node_contract'])
    upstream = {}
    for item in graph['nodes']:
        if item['state'] == 'done' and item.get('node_contract'):
            final, _ = effective_contract(host, task_id, item, contracts)
            upstream[item['node_id']] = dict(node_contract=item['node_contract'], evidence_ids=item['evidence_ids'],
                                             outcome=item.get('outcome'), final_contract=item.get('final_contract'),
                                             bound_ccs=((final or {}).get('work') or {}).get('bound_ccs'))
    known = catalog()
    eligible = (prelim.get('work') or {}).get('eligible_ccs')
    machine = None
    state_file = os.environ.get('FACTORY_MACHINE_STATE')
    if state_file:
        try:
            with open(state_file, encoding='utf-8') as handle:
                machine = json.load(handle)
        except (OSError, ValueError) as exc:
            machine = {'unavailable': str(exc)}
    refusals = [json.loads(r[0]) for r in host._db.execute(
        'SELECT "values" FROM observations WHERE task_id=? AND kind=? ORDER BY created, rowid', (task_id, REFUSAL_KIND))]
    refusals = [dict(problems=r['problems'], rationale=r['rationale'], by=r.get('by', 'scheduler-agent'))
                for r in refusals if r['node_id'] == node_id]
    return dict(schema='factory.finalize-brief/1', task_id=task_id, node_id=node_id, state=node['state'],
                refusals=refusals,
                preliminary=prelim, draft_final=draft_final(prelim),
                inputs=_resolve(host, task, prelim, graph['nodes']), upstream=upstream,
                failures=failures, earlier_finals=earlier_finals,
                capsules={k: v for k, v in known.items() if not eligible or k in eligible},
                machine=machine,
                # Operator inputs only (never producer prose): constraints and resources such as prior
                # artifacts and results the operator lists for this task.
                constraints=task.get('constraints'), resources=task.get('resources') or {},
                rule='The final contract may be more concrete or stricter than the preliminary one, never weaker. '
                     'Fill every slot, keep every criterion word for word, keep limits at or under the ceiling, '
                     'bind capsules in work.bound_ccs. If the preliminary contract cannot be met as written, do not '
                     'propose; report it as a spec gap.')


def finalize(store, task_id, node_id, final, rationale, by='scheduler-agent'):
    """Admit or refuse a proposed final node contract. Control code: it never edits the proposal.

    Admitted: the final contract is recorded (with its digest and its change from the preliminary
    one) and the graph node is marked finalized with the checks it implies. Refused: the reasons are
    recorded and returned; nothing else changes. An exact repeat of an earlier final for the same
    node contract (same contract, inputs and capsule versions) is refused: something must change.
    """
    from .contract import load
    from .node_contract import check_spec, node as contract_node_of, problems as document_problems
    from .node_finalize import check_final, diff, digest, is_preliminary
    from .taskgraph import _apply_patch
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError('A final node contract needs a rationale')
    if hasattr(store, '_check'):
        store._check(task_id, write=True)
    host = getattr(store, '_store', store)
    with host._transaction():
        task = host.get_task(task_id)
        graph = _graph(host, task_id)
        nodes = {n['node_id']: n for n in graph['nodes']}
        node = nodes.get(node_id)
        if node is None:
            raise ValueError('Unknown plan node: ' + node_id)
        contracts = _contracts(host, task)
        prelim = contract_node_of(contracts, node.get('node_contract')) if contracts and node.get('node_contract') else None
        if not is_preliminary(prelim):
            raise ValueError(f'Node {node_id} has no preliminary node contract')
        if node.get('final_contract'):
            raise ValueError(f'Node {node_id} already has a final node contract')
        if node.get('hold'):
            raise ValueError(f'Node {node_id} is held by the operator: {node["hold"]}')
        if node['state'] not in {'proposed', 'ready'}:
            raise ValueError(f'Node {node_id} is {node["state"]}; only a node about to run is finalized')
        unfinished = [d for d in node['depends_on'] if nodes[d]['state'] != 'done']
        if unfinished:
            raise ValueError('Finalize a node when it can run; waiting for ' + ', '.join(unfinished))
        known = catalog()
        found = check_final(prelim, final, known_ccs=set(known))
        if not found:
            document = dict(contracts, nodes=[final if n['node_id'] == prelim['node_id'] else n for n in contracts['nodes']])
            found = document_problems(document, load(task['contract_id']))
        inputs = _resolve(host, task, prelim, graph['nodes'])
        bound = ((final.get('work') or {}).get('bound_ccs') or []) if isinstance(final, dict) else []
        versions = {cc: known.get(cc, {}).get('version') for cc in bound if isinstance(cc, str)}
        final_digest = digest(final) if isinstance(final, dict) else None
        repeat_key = digest(dict(final=final_digest, inputs=inputs, ccs=versions, source=task.get('source')))
        earlier = [r for r in recorded_finals(host, task_id) if r['node_contract'] == node['node_contract']]
        if not found and any(r['repeat_key'] == repeat_key for r in earlier):
            found = ['an identical final contract (same contract, inputs and capsule versions) already ran for '
                     f'{node["node_contract"]} without completing; something must change']
        now = time.time()
        if found:
            refusals = host._db.execute('SELECT COUNT(*) FROM observations WHERE task_id=? AND kind=?',
                                        (task_id, REFUSAL_KIND)).fetchone()[0]
            host._insert('observations', dict(
                obs_id=f'{task_id}:final-refused:{node_id}:{refusals + 1}', task_id=task_id, source_artifacts=[],
                kind=REFUSAL_KIND, values=dict(node_id=node_id, node_contract=node['node_contract'], by=by,
                                               problems=found, proposal_digest=final_digest, rationale=rationale,
                                               created=now),
                error={}, host_run={}, confidence=None,
                limitations='A refused final node contract proposal; nothing ran.', created=now))
            return dict(admitted=False, node_id=node_id, problems=found)
        changes = diff(prelim, final)
        record = dict(node_id=node_id, node_contract=node['node_contract'], digest=final_digest,
                      preliminary_digest=digest(prelim), final=final, diff=changes, rationale=rationale, by=by,
                      inputs=inputs, cc_versions=versions, repeat_key=repeat_key, created=now)
        host._insert('observations', dict(
            obs_id=f'{task_id}:final:{node_id}:{len(earlier) + 1}:{final_digest[:12]}', task_id=task_id,
            source_artifacts=[], kind=FINAL_KIND, values=record, error={}, host_run={}, confidence=None,
            limitations='Admitted final node contract; it starts no work and accepts no output.', created=now))
        view = _apply_patch(host, task_id, {'finalize': [dict(node_id=node_id, digest=final_digest,
                                                                check=check_spec(final))]},
                            graph['rev'], 0, scheduler=True)
    return dict(admitted=True, node_id=node_id, digest=final_digest, diff=changes, graph_rev=view['rev'],
                bound_ccs=bound)
