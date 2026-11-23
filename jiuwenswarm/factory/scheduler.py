"""Scheduler: which planned nodes can run now, with what, and within which limits.

It reads the task graph (from the planner) and the node contracts (from the contract)
and works out the next work. It is deterministic and starts nothing: the agent works
the node, ``jobq`` orders the jobs it submits, and the host enforces what this module
decides:

* a node runs only when every predecessor is done (``taskgraph.dispatch_precondition``);
* jobs that name a node are charged against its ``node_limits`` (``charge``);
* a node is done only when every required output passed its check (``node_check``).

``next_work`` is what the agent sees at the start of every turn and through
``factory.evidence.plan_next``: for each node that can run, its objective, its inputs
resolved to the passing checks of the nodes that produced them, the outputs it owes with
their criteria and verifiers, the capsules that help, and what is left of its limits.
"""
from __future__ import annotations

import json

LIMIT_KINDS = {'build_attempts': ('build',), 'gpu_launches': ('lab', 'ab', 'benchmark', 'runtime')}


def _attempts(host, task_id, node_id):
    rows = host._db.execute('SELECT kind, request FROM attempts WHERE task_id=?', (task_id,))
    return [kind for kind, request in rows if json.loads(request or '{}').get('node_id') == node_id]


def _passed_output(host, task_id, node_id, output):
    from .node_check import checks_for
    checks = checks_for(host, task_id, node_id, output)
    if checks and checks[-1].get('passed'):
        latest = checks[-1]
        return dict(check=latest['obs_id'], artifacts=latest['source_artifacts'],
                    **{k: latest[k] for k in ('found', 'diff_sha256', 'head') if latest.get(k)})
    return None


def _resolve(host, task, contract_node):
    resolved = {}
    for item in contract_node.get('inputs', []):
        source = item['from']
        if source.startswith('task:'):
            field = source[5:]
            resolved[item['name']] = {'from': source, 'value': task.get(field) if field != 'source' else (task.get('source') or None)}
        elif source.startswith('contract:'):
            resolved[item['name']] = {'from': source, 'value': f'input {source[9:]} of contract {task["contract_id"]}'}
        else:
            producer, _, output = source.partition('.')
            resolved[item['name']] = {'from': source, 'value': _passed_output(host, task['task_id'], producer, output)}
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


def charge(host, task_id, node_id, kind):
    """Refuse a job for a node that has used up its contract limit for that kind of job."""
    from .node_contract import for_task, node as contract_node_of
    task = host.get_task(task_id)
    graph_node = next((n for n in _graph(host, task_id)['nodes'] if n['node_id'] == node_id), None)
    if not graph_node or not graph_node.get('node_contract'):
        return
    contract_node = contract_node_of(for_task(task), graph_node['node_contract']) or {}
    limits = contract_node.get('node_limits', {})
    for limit, used_by in LIMIT_KINDS.items():
        if kind in used_by and limit in limits and remaining_limits(host, task_id, node_id, limits)[limit] <= 0:
            raise ValueError(f'Node {node_id} has used its {limit} ({limits[limit]}) from its node contract')


def _graph(host, task_id):
    from .taskgraph import plan_get
    return plan_get(host, task_id)


def next_work(host, task_id):
    """The nodes that can run now and why the others cannot. Pure read."""
    from .node_check import effective_spec, outputs_of, pending
    from .node_contract import for_task, node as contract_node_of
    task = host.get_task(task_id)
    graph = _graph(host, task_id)
    try:
        contracts = for_task(task)
    except (OSError, ValueError):
        contracts = None
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
                        inputs=_resolve(host, task, contract_node),
                        limits_left=remaining_limits(host, task_id, key, contract_node.get('node_limits', {})),
                        authority_ceiling=contract_node.get('authority_ceiling', {}),
                        hands_to=contract_node['hands_to'])
        if node['state'] == 'failed':
            waiting[key] = 'failed: ' + (node['reason'] or 'revise or supersede it')
            continue
        runnable.append(item)
    return dict(schema='factory.next-work/1', task_id=task_id, graph_rev=graph['rev'],
                planner=next((h.get('planner') for h in graph['history'] if h.get('origin') == 'seed'), None),
                runnable=runnable, waiting=waiting, done=done,
                delivered=bool(nodes) and all(n['state'] in {'done', 'cancelled', 'superseded'} for n in nodes.values()))


def brief(work):
    """A compact form for the agent's turn message."""
    return dict(graph_rev=work['graph_rev'], done=work['done'], waiting=work['waiting'],
                runnable=[{k: item[k] for k in ('node_id', 'kind', 'objective', 'outputs', 'done_blocked_by', 'helpful_ccs',
                                                 'inputs', 'limits_left', 'hands_to') if k in item}
                          for item in work['runnable']])
