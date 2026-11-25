"""Planner seam: where the task graph comes from.

The planner is another component's job. The factory takes its plan, checks it against
the contract's node contracts and seeds the task graph from it. Until a real planner is
connected, the stand-in below orders the node contracts as they are.

A plan (``factory.plan/1``)::

    {"format": "factory.plan/1", "planner": "<who made it>",
     "nodes": [{"node_id": "integrate_cache", "node_contract": "integrate_cache",
                "depends_on": ["inspect_engine"], "title": "optional"}]}

Where the plan comes from, first match wins:

1. ``plan`` in the task file: a planner wrote it before ``jiuwenswarm-factory init``.
2. ``FACTORY_PLANNER=module:function``: called as ``function(task, contract, node_contracts)``
   and returns a plan.
3. The stand-in ``contract_plan``: one graph node per node contract, in contract order.
4. No node contracts in the contract: the older fixed suggestion ``taskgraph.initial_plan``.

Every plan is checked the same way: each node contract is covered exactly once, no
uncontracted node is added, and each node depends on at least its contract's
predecessors (a planner may add ordering-only edges). The graph node takes its kind,
title, capability and ``check`` (one verifier per output) from its node contract, so the
planner chooses order, not obligations. The agent can still revise the graph afterwards,
but a node's check never changes.
"""
from __future__ import annotations

import importlib
import os

FORMAT = 'factory.plan/1'
NODE_FIELDS = {'node_id', 'node_contract', 'depends_on', 'title'}


class PlanError(ValueError):
    pass


def contract_plan(task, contract, node_contracts):
    """The stand-in planner: every node contract, in contract order, with its predecessors."""
    from .node_contract import order
    nodes = {n['node_id']: n for n in node_contracts['nodes']}
    return dict(format=FORMAT, planner='factory.planner.contract_plan',
                nodes=[dict(node_id=key, node_contract=key, depends_on=list(nodes[key].get('predecessors', [])))
                       for key in order(node_contracts['nodes'])])


def _external():
    spec = os.environ.get('FACTORY_PLANNER')
    if not spec:
        return None
    module, _, name = spec.partition(':')
    if not module or not name:
        raise PlanError('FACTORY_PLANNER must be module:function')
    return getattr(importlib.import_module(module), name)


def check_plan(plan, node_contracts):
    """Problems of a plan against the node contracts; empty when it can seed the graph."""
    if not isinstance(plan, dict) or plan.get('format') != FORMAT or not isinstance(plan.get('nodes'), list) or not plan['nodes']:
        return [f'a plan is {{"format": "{FORMAT}", "nodes": [...]}} with at least one node']
    found = []
    contracts = {n['node_id']: n for n in node_contracts['nodes']}
    seen, covered = set(), {}
    for item in plan['nodes']:
        if not isinstance(item, dict) or set(item) - NODE_FIELDS or not isinstance(item.get('node_id'), str):
            found.append(f'plan node {item!r}: fields are {sorted(NODE_FIELDS)}, node_id required')
            continue
        key = item['node_id']
        if key in seen:
            found.append(f'{key}: planned twice')
        seen.add(key)
        name = item.get('node_contract', key)
        if name not in contracts:
            found.append(f'{key}: no node contract {name}; a plan cannot add work the contract does not define')
            continue
        if name in covered:
            found.append(f'{key}: node contract {name} is already planned as {covered[name]}')
        covered[name] = key
    for name in contracts:
        if name not in covered:
            found.append(f'node contract {name} is not in the plan')
    if found:
        return found
    for item in plan['nodes']:
        depends = item.get('depends_on', [])
        if not isinstance(depends, list) or any(d not in seen for d in depends):
            found.append(f'{item["node_id"]}/depends_on: every entry must be a planned node')
            continue
        needed = {covered[p] for p in contracts[item.get('node_contract', item['node_id'])].get('predecessors', [])}
        missing = needed - set(depends)
        if missing:
            found.append(f'{item["node_id"]}/depends_on: missing contract predecessors {sorted(missing)}')
    return found


def graph_nodes(task, plan, node_contracts):
    """Task graph nodes (for the seed patch) from a checked plan."""
    from .node_contract import check_spec
    contracts = {n['node_id']: n for n in node_contracts['nodes']}
    nodes = []
    for item in plan['nodes']:
        name = item.get('node_contract', item['node_id'])
        contract = contracts[name]
        node = dict(node_id=item['node_id'], kind=contract['kind'], title=item.get('title') or contract['objective'],
                    capability=(contract.get('work') or {}).get('capability'),
                    inputs=[task['task_id'], f'contract:{task["contract_id"]}'],
                    depends_on=list(item.get('depends_on', [])), node_contract=name, check=check_spec(contract),
                    reason=f'Planned by {plan.get("planner", "an unnamed planner")} from node contract {name}.')
        if contract['kind'] == 'build':
            node['resources'] = {'class': 'build'}
        nodes.append(node)
    return nodes


def plan_for_task(task, plan=None):
    """(planner name, seed patch nodes) for a new task, or (None, None) to use the fixed suggestion."""
    from .node_contract import for_task
    from .contract import load
    if not task.get('contract_id'):
        if plan is not None:
            raise PlanError('A plan needs a task contract with node contracts')
        return None, None
    try:
        node_contracts = for_task(task)
    except FileNotFoundError:
        if plan is not None:
            raise
        return None, None  # an unknown contract file is reported by whoever loads the contract
    if node_contracts is None:
        if plan is not None:
            raise PlanError(f'Contract {task["contract_id"]} has no node contracts to check the plan against')
        return None, None
    if plan is None:
        external = _external()
        plan = external(task, load(task['contract_id']), node_contracts) if external else contract_plan(task, None, node_contracts)
    found = check_plan(plan, node_contracts)
    if found:
        raise PlanError('The plan does not fit the node contracts: ' + '; '.join(found[:8]))
    return plan.get('planner', 'unnamed planner'), graph_nodes(task, plan, node_contracts)


def contract_gate(host, task_id, after):
    """Every revision of a planned graph keeps the contracted work: called on each plan patch.

    The agent may add its own nodes and reorder, retry or supersede work, but every node
    contract stays covered by an active node that carries that contract's kind and checks
    and depends on nodes covering the contract's predecessors; only a contracted deliver
    node may be a deliver node.
    """
    from .node_contract import check_spec, for_task
    task = host.get_task(task_id)
    contracts = None
    if task.get('contract_id'):
        try:
            contracts = for_task(task)
        except FileNotFoundError:
            return
    if contracts is None:
        if any(n.get('node_contract') for n in after.values()):
            raise ValueError('node_contract needs a task contract with node contracts')
        return
    by_id = {c['node_id']: c for c in contracts['nodes']}
    from .scheduler import recorded_finals
    final_checks = {}  # a finalized node carries the checks of its admitted final node contract
    for record in recorded_finals(host, task_id):
        final_checks.setdefault(record['node_contract'], []).append(check_spec(record['final']))
    active = [n for n in after.values() if n['state'] not in {'cancelled', 'superseded'}]
    covering = {}
    for node in active:
        name = node.get('node_contract')
        if name is None:
            if node['kind'] == 'deliver':
                raise ValueError(f'Node {node["node_id"]}: only the contracted deliver node may be a deliver node')
            continue
        if name not in by_id:
            raise ValueError(f'Node {node["node_id"]}: no node contract {name}')
        contract = by_id[name]
        if node['kind'] != contract['kind'] or (node.get('check') != check_spec(contract)
                                                and node.get('check') not in final_checks.get(name, [])):
            raise ValueError(f'Node {node["node_id"]} must keep the kind and checks of node contract {name}')
        covering.setdefault(name, []).append(node)
    missing = [name for name in by_id if name not in covering]
    if missing:
        raise ValueError('Every node contract stays covered by an active node; supersede with a node of the same '
                         'node_contract instead of cancelling. Uncovered: ' + ', '.join(missing))
    for name, nodes in covering.items():
        for node in nodes:
            for predecessor in by_id[name].get('predecessors', []):
                if not any(dep in after and after[dep].get('node_contract') == predecessor for dep in node['depends_on']):
                    raise ValueError(f'Node {node["node_id"]} must depend on a node covering its contract predecessor {predecessor}')
