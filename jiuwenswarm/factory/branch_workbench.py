"""Agent-chosen alternatives in the existing durable task graph; never an executor.

Resource allocations are conservative bookkeeping reservations across *all*
branches, including pruned ones. They grant no execution effects. Comparisons
report evidence claims, never scientific acceptance or projected speedup.
"""
from __future__ import annotations

import hashlib
import math
import time

from .store import NotFound, encoded, identifier
from .taskgraph import _apply_patch, _host, plan_get

KIND = 'branch_workbench_operation'
RESOURCES = ('cpu_seconds', 'gpu_seconds')
METRICS = ('throughput_tps', 'peak_memory_bytes', 'quality_score')
STAGES = {'hypothesis', 'measured', 'inconclusive', 'pruned'}
DEFAULT_LIMITS = {'max_branches': 8, 'cpu_seconds': 60, 'gpu_seconds': 0}


def _fields(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError('Invalid or missing branch fields')


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _resources(value):
    _fields(value, RESOURCES, RESOURCES)
    if any(not _number(v) for v in value.values()):
        raise ValueError('Branch resource seconds must be finite and nonnegative')


def validate_branch(branch):
    _fields(branch, {'parent_id', 'hypothesis', 'allocation', 'stage', 'measurement_evidence_id', 'capabilities'},
            {'parent_id', 'hypothesis', 'allocation', 'stage'})
    identifier(branch['hypothesis'])
    if branch['parent_id'] is not None:
        identifier(branch['parent_id'])
    _resources(branch['allocation'])
    caps = branch.get('capabilities', [])
    if not isinstance(caps, list) or any(not isinstance(c, str) or '.' not in c or any(not part for part in c.split('.')) for c in caps) or len(set(caps)) != len(caps):
        raise ValueError('Branch capabilities must be unique CC id.capability references')
    if branch['stage'] not in STAGES:
        raise ValueError('Unknown branch stage')
    if 'measurement_evidence_id' in branch:
        identifier(branch['measurement_evidence_id'])
    if branch['stage'] == 'measured' and 'measurement_evidence_id' not in branch:
        raise ValueError('Measured branch requires a measurement evidence id')


def _limits(task):
    limits = dict(DEFAULT_LIMITS)
    constraints = task.get('constraints', {})
    if not isinstance(constraints, dict):
        raise ValueError('Branch workbench requires object task constraints')
    config = constraints.get('branch_workbench', {})
    _fields(config, DEFAULT_LIMITS)
    limits.update(config)
    if type(limits['max_branches']) is not int or limits['max_branches'] < 1:
        raise ValueError('max_branches must be a positive integer')
    _resources({key: limits[key] for key in RESOURCES})
    return limits


def measurement(host, task_id, evidence_id):
    """Only current-task observations with explicit measurement scope are read.

    The evidence can be agent-published. Its claims remain reported measurements,
    and this interface deliberately cannot turn them into accepted engine gains.
    """
    record = host._get('observations', task_id, evidence_id)
    value = record['values'].get('branch_measurement')
    _fields(value, {'comparison_key', 'scope', 'metrics', 'cost'}, {'comparison_key', 'scope', 'metrics', 'cost'})
    identifier(value['comparison_key'])
    if value['scope'] not in {'configuration', 'offline_replay', 'subsystem', 'end_to_end'}:
        raise ValueError('Measurement scope must be explicit')
    _fields(value['metrics'], METRICS)
    if any(v is not None and not _number(v) for v in value['metrics'].values()):
        raise ValueError('Reported metrics must be nonnegative finite numbers or null')
    _resources(value['cost'])
    return dict(value, metrics={key: value['metrics'].get(key) for key in METRICS})


def validate_graph(host, task_id, nodes):
    branches = {key: n for key, n in nodes.items() if 'branch' in n}
    limits = _limits(host.get_task(task_id))
    if len(branches) > limits['max_branches']:
        raise ValueError('Task branch count budget exhausted')
    for resource in RESOURCES:
        if sum(n['branch']['allocation'][resource] for n in branches.values()) > limits[resource]:
            raise ValueError('Task branch allocation budget exhausted: ' + resource)
    for key, node in branches.items():
        branch = node['branch']
        parent = branch['parent_id']
        if parent is not None and (parent == key or parent not in branches):
            raise ValueError('Branch parent must be another branch in this task')
        seen, cursor = {key}, parent
        while cursor is not None:
            if cursor in seen:
                raise ValueError('Branch lineage cycle')
            if cursor not in branches:
                raise ValueError('Branch parent must be another branch in this task')
            seen.add(cursor)
            cursor = branches[cursor]['branch']['parent_id']
        evidence_id = branch.get('measurement_evidence_id')
        if evidence_id:
            if evidence_id not in node['evidence_ids']:
                raise ValueError('Branch measurement must be linked in node evidence')
            result = measurement(host, task_id, evidence_id)
            if any(result['cost'][r] > branch['allocation'][r] for r in RESOURCES):
                raise ValueError('Measured cost exceeds branch resource allocation')


def status(store, task_id, graph=None):
    host = _host(store, task_id)
    graph = graph or plan_get(host, task_id)
    limits = _limits(host.get_task(task_id))
    branches = []
    for node in graph['nodes']:
        if 'branch' not in node:
            continue
        row = dict(node_id=node['node_id'], state=node['state'], evidence_ids=node['evidence_ids'],
                   depends_on=node['depends_on'], outcome=node.get('outcome'), reason=node['reason'], **node['branch'])
        if row['state'] == 'cancelled':
            row['stage'] = 'pruned'
        row['measurement'] = (measurement(host, task_id, row['measurement_evidence_id'])
                              if row.get('measurement_evidence_id') else None)
        branches.append(row)
    allocated = {r: sum(b['allocation'][r] for b in branches) for r in RESOURCES}
    return dict(schema='factory.branch-workbench/1', task_id=task_id, graph_rev=graph['rev'], branches=branches,
                ready=[n for n in graph['ready_frontier'] if any(b['node_id'] == n for b in branches)],
                blocked_reasons={key: reasons for key, reasons in graph['blocked_reasons'].items() if any(b['node_id'] == key for b in branches)},
                limits=limits, allocated=allocated,
                remaining={r: limits[r] - allocated[r] for r in RESOURCES},
                execution_authorized=False, acceptance_authorized=False,
                limitations=['Allocations are bookkeeping; existing CC grants and job admission remain required.',
                             'Metrics are reported evidence claims; missing metrics remain unknown.'])


def compare(store, task_id):
    result = status(store, task_id)
    groups, unknown = {}, []
    for branch in result['branches']:
        measured = branch['measurement']
        if measured is None or any(measured['metrics'][k] is None for k in METRICS):
            unknown.append(branch['node_id'])
            continue
        groups.setdefault((measured['comparison_key'], measured['scope']), []).append(branch)
    comparisons = []
    for (key, scope), branches in groups.items():
        def dominates(a, b):
            x, y = a['measurement']['metrics'], b['measurement']['metrics']
            comparisons = [x['throughput_tps'] >= y['throughput_tps'], x['peak_memory_bytes'] <= y['peak_memory_bytes'],
                           x['quality_score'] >= y['quality_score']]
            return all(comparisons) and x != y
        comparisons.append(dict(comparison_key=key, scope=scope,
            pareto_frontier=[b['node_id'] for b in branches if not any(dominates(a, b) for a in branches)],
            members=[b['node_id'] for b in branches]))
    return dict(groups=comparisons, unknown=unknown, acceptance_authorized=False,
                limitations=['Pareto ordering requires all three reported metrics and an identical comparison key and scope.',
                             'The caller must freeze workload, units, decoding, quality rule and hardware in comparison_key.',
                             'Ordering does not establish repeatability, correctness, causal gains or promotion authority.'])


def mutate(store, task_id, operation, inputs):
    host = _host(store, task_id, write=True)
    common = {'expected_graph_rev', 'decision_rev', 'idem_key'}
    shapes = {
        'create': ({'node_id', 'hypothesis', 'allocation', 'capabilities'}, {'node_id', 'hypothesis', 'allocation'}),
        'fork': ({'node_id', 'parent_id', 'hypothesis', 'allocation', 'continuation', 'capabilities'}, {'node_id', 'parent_id', 'hypothesis', 'allocation'}),
        'refine': ({'node_id', 'parent_id', 'hypothesis', 'allocation', 'capabilities'}, {'node_id', 'parent_id', 'hypothesis', 'allocation'}),
        'record': ({'node_id', 'evidence_id'}, {'node_id', 'evidence_id'}),
        'attach': ({'node_id', 'evidence_ids', 'outcome'}, {'node_id', 'evidence_ids', 'outcome'}),
        'prune': ({'node_id', 'reason'}, {'node_id', 'reason'}),
    }
    allowed, required = shapes[operation]
    _fields(inputs, common | allowed, common | required)
    identifier(inputs['idem_key'])
    fingerprint = hashlib.sha256(encoded(dict(operation=operation, inputs=inputs)).encode()).hexdigest()
    obs_id = task_id + ':branch-op:' + hashlib.sha256(inputs['idem_key'].encode()).hexdigest()
    with host._transaction():
        try:
            prior = host._get('observations', task_id, obs_id)['values']
        except NotFound:
            prior = None
        if prior is not None:
            if prior['fingerprint'] != fingerprint:
                raise ValueError('Branch idempotency key reused with different inputs')
            return status(host, task_id, plan_get(host, task_id, prior['graph_rev']))
        graph = plan_get(host, task_id)
        nodes = {n['node_id']: n for n in graph['nodes']}
        key = identifier(inputs['node_id'])
        if operation in {'create', 'fork', 'refine'}:
            parent = inputs.get('parent_id')
            continuation = operation == 'refine' or inputs.get('continuation', False)
            if type(continuation) is not bool:
                raise ValueError('continuation must be boolean')
            if parent is not None and (parent not in nodes or 'branch' not in nodes[parent]):
                raise ValueError('Unknown parent branch in current task')
            branch = dict(parent_id=parent, hypothesis=inputs['hypothesis'], allocation=inputs['allocation'], stage='hypothesis', capabilities=inputs.get('capabilities', []))
            patch = {'add': [dict(node_id=key, kind='investigate', title=inputs['hypothesis'], branch=branch,
                                  depends_on=[parent] if continuation else [], resources={'class': 'cpu'})]}
        else:
            if key not in nodes or 'branch' not in nodes[key]:
                raise ValueError('Unknown branch in current task')
            branch = dict(nodes[key]['branch'])
            if operation == 'prune':
                patch = {'cancel': [dict(node_id=key, reason=inputs['reason'])]}
            elif operation == 'attach':
                from .taskgraph import _ids
                _ids(inputs['evidence_ids'])
                if not inputs['evidence_ids']:
                    raise ValueError('Attach requires current-task evidence')
                host.validate_evidence(task_id, inputs['evidence_ids'])
                identifier(inputs['outcome'])
                if branch.get('measurement_evidence_id'):
                    raise ValueError('Branch already measured; fork to refine')
                branch['stage'] = 'inconclusive'
                patch = {'update': [dict(node_id=key, state='done', branch=branch, evidence_ids=inputs['evidence_ids'], outcome=inputs['outcome'])]}
            else:
                evidence_id = identifier(inputs['evidence_id'])
                measurement(host, task_id, evidence_id)
                if branch.get('measurement_evidence_id'):
                    raise ValueError('Branch already measured; fork to record a new experiment')
                branch.update(stage='measured', measurement_evidence_id=evidence_id)
                patch = {'update': [dict(node_id=key, state='done', branch=branch, evidence_ids=[evidence_id])]}
        updated = _apply_patch(host, task_id, patch, inputs['expected_graph_rev'], inputs['decision_rev'])
        host._insert('observations', dict(obs_id=obs_id, task_id=task_id, kind=KIND,
            values=dict(operation=operation, fingerprint=fingerprint, graph_rev=updated['rev']),
            source_artifacts=[], error={}, host_run={}, confidence=None, limitations='Agent work record only.', created=time.time()))
        return status(host, task_id, updated)


def dispatch(store, task_id, operation, inputs):
    if operation in {'status', 'ready', 'compare'}:
        _fields(inputs, {})
        return {'analysis': compare(store, task_id) if operation == 'compare' else status(store, task_id)}
    if operation not in {'create', 'fork', 'refine', 'record', 'attach', 'prune'}:
        raise ValueError('Unknown branch workbench capability')
    return {'analysis': mutate(store, task_id, operation, inputs)}
