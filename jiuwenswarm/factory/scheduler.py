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

LIMIT_KINDS = {'build_attempts': ('build',), 'gpu_launches': ('lab',)}
# API capabilities that may name a node: (capsule, capsule capability, attempt kind charged).
NODE_CAPABILITIES = {'builder.submit': ('builder', 'submit', 'build'),
                     'lab.submit': ('lab_client', 'submit', 'lab'),
                     'lab.ab_submit': ('lab_client', 'ab_submit', 'lab'),
                     'lab_manager.compose': ('lab_manager', 'compose', None)}
WORKSPACE_EFFECTS = {'none': set(), 'read': {'workspace.read'}, 'write': {'workspace.read', 'workspace.write'}}


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
            resolved[item['name']] = {'from': source, 'value': f'input {source[9:]} of contract {task["contract_id"]}'}
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
    from .node_contract import node as contract_node_of
    task = host.get_task(task_id)
    graph_node = next((n for n in _graph(host, task_id)['nodes'] if n['node_id'] == node_id), None)
    if not graph_node or not graph_node.get('node_contract'):
        return
    contract_node = contract_node_of(_contracts(host, task), graph_node['node_contract']) or {}
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
    from .node_contract import node as contract_node_of
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
        contract_node = contract_node_of(contracts, graph_node.get('node_contract')) if contracts else None
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
    from .node_contract import node as contract_node_of
    task = host.get_task(task_id)
    graph = _graph(host, task_id)
    contracts = _contracts(host, task)
    nodes = {n['node_id']: n for n in graph['nodes']}
    runnable, waiting, done = [], {}, []
    for node in graph['nodes']:  # planner order
        key = node['node_id']
        if node['state'] == 'done':
            done.append(key)
            continue
        if node['state'] in {'cancelled', 'superseded'}:
            continue
        unfinished = [d for d in node['depends_on'] if nodes[d]['state'] != 'done']
        if unfinished:
            waiting[key] = 'waiting for ' + ', '.join(unfinished)
            continue
        contract_node = contract_node_of(contracts, node.get('node_contract')) if node.get('node_contract') else None
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
                runnable=runnable, waiting=waiting, done=done, delivered=delivered)


def brief(work):
    """A compact form for the agent's turn message."""
    return dict(graph_rev=work['graph_rev'], done=work['done'], waiting=work['waiting'],
                runnable=[{k: item[k] for k in ('node_id', 'kind', 'objective', 'outputs', 'done_blocked_by', 'helpful_ccs',
                                                 'inputs', 'limits_left', 'hands_to') if k in item}
                          for item in work['runnable']])
