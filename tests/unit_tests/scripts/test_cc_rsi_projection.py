"""Explicit synthetic public UI fixtures; never operational admission/model calls."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import json
import io
import stat
import struct
import sys
import types

import pytest

MODULE = Path(__file__).parents[3] / 'jiuwenswarm/server/rsi/cc_rsi_projection.py'
spec = importlib.util.spec_from_file_location('unit_cc_projection', MODULE)
projection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projection)


def unit_publication():
    body = '# Synthetic UI test fixture\nreturn 1\n'
    digest = hashlib.sha256(body.encode()).hexdigest()
    gate = {'allowed': True, 'blocker': None}
    return {'snapshot': {'schema_version': '1', 'revision': 'synthetic-ui-test', 'generated_at': None,
        'availability': 'TEST_ONLY', 'blocker': None,
        'targets': [{'id': 'unit-target', 'name': 'Synthetic UI target', 'parent_hash': digest, 'active_hash': None, 'run': gate}],
        'runs': [], 'nodes': [{'id': 'unit-parent', 'target_id': 'unit-target', 'run_id': None, 'parent_id': None,
            'hash': digest, 'label': 'Synthetic parent', 'evaluation_status': 'failed', 'admission_status': 'unadmitted',
            'activation_status': 'inactive', 'correctness': None, 'speed': None, 'noise': None,
            'evidence_refs': [], 'operator_receipts': [], 'admit': gate, 'activate': gate}]},
        'candidates': [{'node_id': 'unit-parent', 'candidate_hash': digest, 'path': 'unit.py', 'parent_code': body,
                        'candidate_code': body, 'rationale': None, 'blocker': None}]}


def test_exact_captured_unadmitted_code_remains_reviewable():
    value = projection.validate_publication(unit_publication())
    service = projection.CcRsiProjection()
    service._read = lambda: copy.deepcopy(value)
    node = value['snapshot']['nodes'][0]
    assert service.candidate({'node_id': node['id'], 'candidate_hash': node['hash']})['candidate_code'].startswith('# Synthetic')
    assert service.snapshot({})['nodes'][0]['admission_status'] == 'unadmitted'


@pytest.mark.parametrize('location,field', [('root', 'model_packet'), ('snapshot', 'fixture_labels'), ('node', 'private_ref')])
def test_private_or_unknown_fields_are_rejected(location, field):
    value = unit_publication()
    target = value if location == 'root' else value['snapshot'] if location == 'snapshot' else value['snapshot']['nodes'][0]
    target[field] = 'must not be forwarded'
    with pytest.raises(projection.ProjectionError): projection.validate_publication(value)


def test_changed_captured_bytes_or_identity_fail_closed():
    value = unit_publication()
    value['candidates'][0]['candidate_code'] += '# changed'
    with pytest.raises(projection.ProjectionError): projection.validate_publication(value)
    service = projection.CcRsiProjection(); service._read = unit_publication
    with pytest.raises(projection.ProjectionError): service.candidate({'node_id': 'unit-parent', 'candidate_hash': 'a' * 64})


def test_publication_cannot_grant_root_or_run_authority():
    service = projection.CcRsiProjection(); service._read = unit_publication
    view = service.snapshot({})
    assert view['targets'][0]['run']['allowed'] is False
    assert view['nodes'][0]['admit']['allowed'] is False
    assert view['nodes'][0]['activate']['allowed'] is False
    with pytest.raises(projection.ProjectionError): service.operator_action({'action': 'admit', 'actor': 'root'})
    with pytest.raises(projection.ProjectionError): service.run_start({'target_id': 'unit-target'})


@pytest.mark.parametrize('phase', ['READY', 'PREPARING', 'LAUNCHED'])
def test_published_gate_never_carries_a_root_slot_phase(phase):
    # Slot phases (READY/BLOCKED/CLAIMED/LAUNCHED/PREPARING/FAILED) come only
    # from Root readiness overlaid at request time; a publication is data and
    # can never assert one, whatever revision it carries.
    value = unit_publication()
    value['snapshot']['targets'][0]['run'] = {'allowed': False, 'blocker': 'Root readiness required', 'phase': phase}
    with pytest.raises(projection.ProjectionError):
        projection.validate_publication(value)
    value['snapshot']['targets'][0]['run'] = {'allowed': False, 'blocker': None, 'revision': 'a' * 64, 'phase': phase}
    with pytest.raises(projection.ProjectionError):
        projection.validate_publication(value)


def test_missing_publication_is_explicitly_blocked_without_synthetic_records():
    view = projection.CcRsiProjection().snapshot({})
    assert view['availability'] == 'BLOCKED'
    assert view['nodes'] == view['runs'] == view['targets'] == []


def test_lineage_cycles_rejected():
    value = unit_publication()
    value['snapshot']['nodes'][0]['parent_id'] = 'unit-parent'
    with pytest.raises(projection.ProjectionError): projection.validate_publication(value)


def test_nonfinite_budget_never_becomes_a_measured_zero():
    value = unit_publication()
    value['snapshot']['runs'] = [{'id': 'unit-run', 'target_id': 'unit-target', 'stage': 'unit', 'status': 'TEST_ONLY',
        'blockers': [], 'activity': [], 'budget': {'elapsed_seconds': float('nan'), 'limit_seconds': None,
        'setup_calls': None, 'diagnosis_calls': None, 'proposal_calls': None, 'generation_call_limit': None, 'cost': None, 'currency': None}}]
    with pytest.raises(projection.ProjectionError): projection.validate_publication(value)


def scoped_publication():
    value = unit_publication(); value['workspace_id'] = 'unit-workspace'
    value['snapshot']['nodes'][0]['security_status'] = 'NOT_APPLICABLE'
    return value


def test_exact_workspace_and_deferred_security_preserve_real_visible_metrics():
    value = scoped_publication()
    child = copy.deepcopy(value['snapshot']['nodes'][0])
    child.update(id='unit-child', parent_id='unit-parent', security_status='SECURITY_DEFERRED',
                 evaluation_status='passed', correctness='12/12 visible checks',
                 admit={'allowed': False, 'blocker': 'Security deferred'},
                 activate={'allowed': False, 'blocker': 'Security deferred'})
    value['snapshot']['nodes'].append(child)
    assert projection.validate_publication(value, workspace_id='unit-workspace')['snapshot']['nodes'][1]['correctness'] == '12/12 visible checks'
    with pytest.raises(projection.ProjectionError): projection.validate_publication(value, workspace_id='foreign')
    with pytest.raises(projection.ProjectionError): projection.validate_publication(unit_publication(), workspace_id='unit-workspace')
    for key, claim in [('admission_status', 'admitted'), ('activation_status', 'active'),
                       ('operator_receipts', [{'action': 'admit'}]), ('security_status', 'NOT_APPLICABLE')]:
        changed = copy.deepcopy(value); changed['snapshot']['nodes'][1][key] = claim
        with pytest.raises(projection.ProjectionError): projection.validate_publication(changed, workspace_id='unit-workspace')


def test_explicit_most_specific_readonly_mount_required():
    text = '1 0 0:1 / / rw - overlay overlay rw\n2 1 0:2 / /run/public ro - tmpfs tmpfs rw\n'
    path = '/run/public/publication.json'
    assert projection._readonly_mount(path, text)
    assert not projection._readonly_mount(path, text.replace('/run/public ro', '/run/public rw'))
    assert not projection._readonly_mount(path, text + '3 2 0:3 / /run/public/publication.json rw - tmpfs tmpfs rw\n')
    assert not projection._readonly_mount(path, text + text.splitlines()[1] + '\n')
    assert not projection._readonly_mount(path, '1 0 0:1 / / ro - overlay overlay ro\n')


@pytest.mark.parametrize('mode,owner', [(stat.S_IFLNK | 0o777, 0), (stat.S_IFDIR | 0o777, 0), (stat.S_IFDIR | 0o755, 10001)])
def test_root_nonsymlink_nonwritable_publication_ancestry_required(mode, owner):
    parent = types.SimpleNamespace(lstat=lambda: types.SimpleNamespace(st_mode=mode, st_uid=owner))
    with pytest.raises(projection.ProjectionError):
        projection._root_ancestors(types.SimpleNamespace(parents=[parent]))


@pytest.mark.parametrize('fault', [None, 'workspace', 'mount', 'owner', 'hardlink'])
def test_reader_enforces_actual_workspace_mount_and_leaf_custody(monkeypatch, fault):
    raw = json.dumps(scoped_publication()).encode()
    mountinfo = '1 0 0:1 / / rw - overlay overlay rw\n2 1 0:2 / /run/public ro - tmpfs tmpfs rw\n'
    parent = types.SimpleNamespace(lstat=lambda: types.SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0))
    path = type('SyntheticPath', (), {'__str__': lambda self: '/run/public/publication.json',
                                     'is_absolute': lambda self: True})()
    path.parts = ('/', 'run', 'public', 'publication.json'); path.parents = [parent]
    def paths(name):
        if str(name) == '/proc/self/mountinfo':
            return types.SimpleNamespace(read_text=lambda **kw: mountinfo.replace('/run/public ro', '/run/public rw') if fault == 'mount' else mountinfo)
        return path
    fake_os = types.SimpleNamespace(name='posix', O_RDONLY=0, O_NOFOLLOW=1, O_NONBLOCK=2,
        open=lambda *args: 99, close=lambda fd: None, fdopen=lambda *args, **kw: io.BytesIO(raw),
        fstat=lambda fd: types.SimpleNamespace(st_mode=stat.S_IFREG | 0o440, st_uid=10001 if fault == 'owner' else 0,
                                              st_nlink=2 if fault == 'hardlink' else 1, st_size=len(raw)))
    monkeypatch.setattr(projection, 'Path', paths); monkeypatch.setattr(projection, 'os', fake_os)
    service = projection.CcRsiProjection('/run/public/publication.json', workspace_id='foreign' if fault == 'workspace' else 'unit-workspace')
    assert service.snapshot({})['availability'] == ('TEST_ONLY' if fault is None else 'BLOCKED')


def broker_module():
    package = types.ModuleType('unit_cc_rsi'); package.__path__ = []
    sys.modules['unit_cc_rsi'] = package
    sys.modules['unit_cc_rsi.cc_rsi_projection'] = projection
    spec = importlib.util.spec_from_file_location('unit_cc_rsi.cc_rsi_broker', MODULE.with_name('cc_rsi_broker.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('fault', ['none', 'browser-actor', 'wrong-receipt', 'wrong-peer'])
def test_broker_contract_uses_verified_human_and_exact_receipt_only(monkeypatch, fault):
    broker = broker_module()
    digest = 'a' * 64
    authorization = broker.HumanActionAuthorization('unit:human', 'unit-action', 'synthetic-signed-proof')
    if fault == 'browser-actor':
        with pytest.raises(projection.ProjectionError):
            broker.InstalledHumanOperatorClient().execute('admit', 'unit-node', digest, {'actor': 'root'})
        return
    monkeypatch.setattr(broker.os, 'name', 'posix')
    monkeypatch.setattr(broker.socket, 'SO_PEERCRED', 17, raising=False)
    monkeypatch.setattr(broker.socket, 'AF_UNIX', 1, raising=False)
    monkeypatch.setattr(broker.os, 'lstat', lambda path: types.SimpleNamespace(st_uid=0,
        st_mode=(stat.S_IFSOCK | 0o660) if path.endswith('.sock') else (stat.S_IFDIR | 0o755)))
    sent = []
    class SyntheticSocket:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def settimeout(self, value): assert value == 10
        def connect(self, endpoint): assert endpoint == '/run/ai4r-rsi-ui/operator.sock'
        def getsockopt(self, *args): return struct.pack('3i', 1, 10001 if fault == 'wrong-peer' else 0, 13000)
        def sendall(self, raw): sent.append(json.loads(raw))
        def recv(self, limit):
            return json.dumps({'action': 'admit', 'node_id': 'unit-node', 'candidate_hash': digest,
                'actor': 'unit:other' if fault == 'wrong-receipt' else 'unit:human',
                'receipt_ref': {'id': 'synthetic-receipt', 'sha256': digest}}).encode() + b'\n'
    monkeypatch.setattr(broker.socket, 'socket', lambda *args: SyntheticSocket())
    if fault != 'none':
        with pytest.raises(projection.ProjectionError): broker.InstalledHumanOperatorClient().execute('admit', 'unit-node', digest, authorization)
    else:
        assert broker.InstalledHumanOperatorClient().execute('admit', 'unit-node', digest, authorization)['actor'] == 'unit:human'
        assert set(sent[0]) == {'protocol', 'action', 'node_id', 'candidate_hash', 'authorization'}


# --- Improvement-loop lineage (Interface C ``loop`` -> public run lineage) ---

def _legacy_run():
    return {'id': 'unit-run', 'target_id': 'unit-target', 'stage': 'Complete', 'status': 'ERROR_NO_REPLAY',
            'blockers': ['Retained UnitError; this attempt cannot be replayed.'], 'activity': [],
            'budget': {'elapsed_seconds': None, 'limit_seconds': 3600, 'setup_calls': 0, 'diagnosis_calls': None,
                       'proposal_calls': None, 'generation_call_limit': 2, 'cost': None, 'currency': None}}


def _visible(role, iteration, passed, rows, wall=1.0, failure=None):
    return {'schema': 'ai4r-rsi-whole-capsule-visible-result:2', 'role': role, 'iteration': iteration,
            'subject_sha256': 'c' * 64, 'passed_count': passed, 'case_count': len(rows), 'protected_wall_s': wall,
            'trial_wall_s': [], 'executions': len(rows), 'failure': failure,
            'rows': [{'fixture_id': ident, 'fixture_set': fixture_set, 'task_success': ok, 'protected_wall_s': 0.1,
                      'output_bytes': 1, 'checks': {}, 'receipt': {}} for ident, fixture_set, ok in rows]}


def _score(parent, candidate, ratio, above, improved, feedback):
    return {'correctness': {'parent': parent, 'candidate': candidate}, 'latency_ratio': ratio,
            'noise_floor_ratio': 0.05, 'above_noise': above, 'improved': improved, 'regressed': candidate < parent,
            'summary': f'{candidate:.2f} vs {parent:.2f}', 'feedback': feedback}


def _loop_result(bodies):
    first, second = (hashlib.sha256(body.encode()).hexdigest() for body in bodies)
    cases = [('p1', 'public', True), ('p2', 'public', True), ('h1', 'held_out', True)]
    return {'status': 'COMPLETED_UNQUALIFIED', 'model_calls': 7, 'candidate_ref': {'id': 'second', 'sha256': second},
            'loop': {'schema': 'ai4r-rsi-capsule-loop:1', 'max_iterations': 3, 'completed_iterations': 3,
                     'stop_reason': 'max_iterations',
                     'model_backend': {'kind': 'fake', 'model': 'scripted', 'pinned_sha256': 'd' * 64},
                     'parent_visible': _visible('parent', 0, 3, cases, wall=2.0), 'noise': None,
                     'best': {'iteration': 2, 'candidate_ref': {'id': 'second', 'sha256': second}, 'score': {}},
                     'iterations': [
                         {'iteration': 1, 'diagnosis_ref': 'd1', 'proposal_ref': 'p1', 'candidate_ref': {'id': 'first', 'sha256': first},
                          'candidate_sha256': first, 'rationale': 'Cache parsing', 'kept': False, 'model_calls': 2, 'elapsed_s': 3.5,
                          'visible': _visible('candidate', 1, 2, [cases[0], ('p2', 'public', False), cases[2]]),
                          'score': _score(1.0, 2 / 3, 0.9, True, False, 'p2 failed: expected 4 got 5')},
                         {'iteration': 2, 'diagnosis_ref': 'd2', 'proposal_ref': 'p2', 'candidate_ref': {'id': 'second', 'sha256': second},
                          'candidate_sha256': second, 'rationale': 'Skip copy', 'kept': True, 'model_calls': 2, 'elapsed_s': 3.0,
                          'visible': _visible('candidate', 2, 3, cases, wall=1.2),
                          'score': _score(1.0, 1.0, 0.6, True, True, 'all cases passed')},
                         {'iteration': 3, 'diagnosis_ref': 'd3', 'proposal_ref': 'p3', 'candidate_ref': None,
                          'candidate_sha256': None, 'rationale': None, 'kept': False, 'model_calls': 3, 'elapsed_s': 1.0,
                          'visible': None, 'score': None}]}}


def _loop_publication():
    value = scoped_publication()
    parent = value['snapshot']['nodes'][0]
    bodies = ['# first\nreturn 2\n', '# second\nreturn 1\n']
    result = _loop_result(bodies)
    node_ids = {}
    for index, body in enumerate(bodies):
        digest = hashlib.sha256(body.encode()).hexdigest()
        node = copy.deepcopy(parent)
        node.update(id=f'candidate:unit-run:{digest}', parent_id=parent['id'], run_id='unit-run', hash=digest,
                    label=f'iteration {index + 1}', security_status='SECURITY_DEFERRED',
                    admit={'allowed': False, 'blocker': 'deferred'}, activate={'allowed': False, 'blocker': 'deferred'})
        value['snapshot']['nodes'].append(node)
        value['candidates'].append({'node_id': node['id'], 'candidate_hash': digest, 'path': 'unit.py',
            'parent_code': value['candidates'][0]['candidate_code'], 'candidate_code': body, 'rationale': None, 'blocker': None})
        node_ids[digest] = node['id']
    run = _legacy_run()
    run['lineage'] = projection.project_loop(result, node_ids=node_ids, parent_node_id=parent['id'])
    value['snapshot']['runs'] = [run]
    return value, node_ids


def test_legacy_single_attempt_record_projects_byte_identically():
    value = scoped_publication(); value['snapshot']['runs'] = [_legacy_run()]
    before = json.dumps(value, sort_keys=True)
    assert json.dumps(projection.validate_publication(copy.deepcopy(value), workspace_id='unit-workspace'), sort_keys=True) == before
    service = projection.CcRsiProjection(); service._read = lambda: copy.deepcopy(value)
    run = service.snapshot({})['runs'][0]
    assert run == value['snapshot']['runs'][0] and 'lineage' not in run
    assert projection.project_loop({'status': 'ERROR_NO_REPLAY', 'model_calls': 0}) is None


def test_loop_record_projects_every_iteration_with_best_and_failed_candidates():
    value, node_ids = _loop_publication()
    lineage = projection.validate_publication(value, workspace_id='unit-workspace')['snapshot']['runs'][0]['lineage']
    assert (lineage['max_iterations'], lineage['completed_iterations'], lineage['stop_reason']) == (3, 3, 'max_iterations')
    assert lineage['model_backend'] == {'kind': 'fake', 'model': 'scripted', 'pinned_sha256': 'd' * 64}
    assert lineage['model_calls'] == 7 and lineage['best_iteration'] == 2
    assert lineage['parent'] == {'status': 'passed', 'passed_count': 3, 'case_count': 3, 'protected_wall_s': 2.0, 'failure': None}
    first, second, third = lineage['iterations']
    assert lineage['best_node_id'] == second['node_id'] == node_ids[second['candidate_ref']['sha256']]
    assert [row['best'] for row in lineage['iterations']] == [False, True, False]
    assert first['status'] == 'failed' and first['kept'] is False and first['node_id'] is not None
    assert first['failing_cases'] == [{'id': 'p2', 'fixture_set': 'public'}]
    assert first['feedback'] == 'p2 failed: expected 4 got 5' and first['rationale'] == 'Cache parsing'
    assert (second['correctness_parent'], second['correctness_candidate'], second['latency_ratio']) == (1.0, 1.0, 0.6)
    assert second['above_noise'] is True and second['improved'] is True and second['failing_cases'] == []
    assert third['status'] == 'not_evaluated' and third['candidate_ref'] is None and third['node_id'] is None
    assert third['latency_ratio'] is None and third['improved'] is None and third['model_calls'] == 3
    service = projection.CcRsiProjection(); service._read = lambda: copy.deepcopy(value)
    assert service.snapshot({})['runs'][0]['lineage'] == lineage
    assert service.candidate({'node_id': first['node_id'], 'candidate_hash': first['candidate_ref']['sha256']})['candidate_code'].startswith('# first')


def test_missing_loop_fields_project_as_unknown_never_zero_or_success():
    result = {'loop': {'schema': 'ai4r-rsi-capsule-loop:1', 'stop_reason': 'gave_up', 'model_backend': {'kind': 'mystery'},
                       'iterations': [{'iteration': 1, 'candidate_ref': 'ref-only', 'candidate_sha256': 'e' * 64,
                                       'score': {'correctness': {}, 'latency_ratio': float('nan')},
                                       'visible': {'rows': 'not-rows', 'failure': {'exception_type': 'Boom'}}}]}}
    lineage = projection.project_loop(result)
    assert lineage['max_iterations'] is lineage['completed_iterations'] is lineage['stop_reason'] is None
    assert lineage['model_backend'] == {'kind': None, 'model': None, 'pinned_sha256': None}
    assert lineage['model_calls'] is None and lineage['best_iteration'] is None and lineage['best_node_id'] is None
    assert lineage['parent']['status'] == 'not_evaluated' and lineage['parent']['passed_count'] is None
    row = lineage['iterations'][0]
    assert row['candidate_ref'] == {'id': 'ref-only', 'sha256': 'e' * 64} and row['node_id'] is None
    assert row['status'] == 'evaluation_failed' and row['failure'] == {'exception_type': 'Boom', 'message': None}
    for key in ('kept', 'passed_count', 'case_count', 'correctness_parent', 'correctness_candidate', 'latency_ratio',
                'noise_floor_ratio', 'above_noise', 'improved', 'regressed', 'summary', 'feedback', 'rationale',
                'failing_cases', 'model_calls', 'elapsed_s'):
        assert row[key] is None, key
    assert row['best'] is False
    long = projection.project_loop({'loop': {'schema': 'ai4r-rsi-capsule-loop:1', 'iterations': [
        {'iteration': 1, 'score': {'feedback': 'x' * 10000}}]}})['iterations'][0]['feedback']
    assert len(long) == 4096 and long.endswith('[truncated]')
    with pytest.raises(projection.ProjectionError):
        projection.project_loop({'loop': {'schema': 'other', 'iterations': []}})


@pytest.mark.parametrize('fault', ['two-best', 'foreign-node', 'extra-field', 'missing-parent', 'bad-ratio'])
def test_forged_or_inconsistent_lineage_fails_closed(fault):
    value, _ = _loop_publication()
    lineage = value['snapshot']['runs'][0]['lineage']
    if fault == 'two-best':
        lineage['iterations'][0]['best'] = True
    elif fault == 'foreign-node':
        lineage['iterations'][0]['node_id'] = lineage['iterations'][1]['node_id']
    elif fault == 'extra-field':
        lineage['iterations'][0]['hidden_case_output'] = 'leak'
    elif fault == 'missing-parent':
        lineage['parent_node_id'] = 'not-a-node'
    else:
        lineage['iterations'][0]['latency_ratio'] = float('inf')
    with pytest.raises(projection.ProjectionError):
        projection.validate_publication(value, workspace_id='unit-workspace')


# --- Merge wave: paired batched benchmark as the latency judge (lineage:2) ---

def _report(gain, ratio_ci, met, *, gates=None, jobs=192):
    gates = gates or {key: met for key in projection.BENCHMARK_GATES}
    return {'schema': projection.BENCHMARK_REPORT_SCHEMA, 'report_ref': {'id': 'r.json', 'sha256': 'f' * 64},
            'capsule_name': 'unit-target', 'relative_gain': gain, 'ratio_confidence_interval': ratio_ci,
            'gates': {key: {'threshold': 0.1, 'passed': value} for key, value in gates.items()},
            'objective_met': met, 'protected_jobs': jobs, 'repetitions': 11,
            'workloads': [{'id': 'small-numbers', 'median_ratio': 1 - gain}, {'id': 'large-numbers', 'median_ratio': 0.9}],
            'evidence_refs': [{'id': 'j.json', 'sha256': 'e' * 64}] * jobs}


def _benchmark_loop(*, method='paired_batched_benchmark'):
    result = _loop_result(['# first\nreturn 2\n', '# second\nreturn 1\n'])
    first, second, _ = result['loop']['iterations']
    first['score']['latency_method'] = second['score']['latency_method'] = method
    if method == 'paired_batched_benchmark':
        first['benchmark'] = _report(0.014, [0.9532, 0.9988], False,
                                     gates={'minimum_gain': False, 'ci_upper_bound': False, 'max_workload_regression': True})
        second['benchmark'] = _report(0.1678, [0.8185, 0.8418], True)
        result['loop']['benchmark_baseline'] = dict(_report(0.0, [0.98, 1.02], False), protected_jobs=208)
    return result


def _benchmark_publication():
    value, _ = _loop_publication()
    run = value['snapshot']['runs'][0]
    node_ids = {row['candidate_ref']['sha256']: row['node_id'] for row in run['lineage']['iterations'] if row['node_id']}
    run['lineage'] = projection.project_loop(_benchmark_loop(), node_ids=node_ids,
                                             parent_node_id=value['snapshot']['nodes'][0]['id'])
    return value


def test_benchmark_loop_projects_gain_interval_gates_and_measured_basis():
    lineage = projection.project_loop(_benchmark_loop(), node_ids={}, parent_node_id=None)
    assert lineage['schema'] == projection.LINEAGE_SCHEMA_V2
    assert lineage['benchmark_baseline']['protected_jobs'] == 208 and lineage['benchmark_baseline']['objective_met'] is False
    first, second, third = lineage['iterations']
    assert second['latency_method'] == 'paired_batched_benchmark' and second['improvement_basis'] == 'paired_batched_benchmark'
    assert second['benchmark'] == {'report_ref': {'id': 'r.json', 'sha256': 'f' * 64}, 'relative_gain': 0.1678,
        'ratio_confidence_interval': [0.8185, 0.8418], 'objective_met': True, 'protected_jobs': 192, 'repetitions': 11,
        'gates': {'minimum_gain': True, 'ci_upper_bound': True, 'max_workload_regression': True},
        'workloads': [{'id': 'small-numbers', 'median_ratio': 1 - 0.1678}, {'id': 'large-numbers', 'median_ratio': 0.9}]}
    assert 'evidence_refs' not in json.dumps(lineage)  # Only the report ref is public; job originals stay with Root.
    # The scorer did not call the 1.4% gain an improvement: no claim, failed gates shown.
    assert first['improvement_basis'] is None and first['benchmark']['gates']['minimum_gain'] is False
    assert third['benchmark'] is None and third['latency_method'] is None and third['improvement_basis'] is None
    value = _benchmark_publication()
    served = projection.validate_publication(value, workspace_id='unit-workspace')['snapshot']['runs'][0]['lineage']
    assert served['iterations'][1]['benchmark']['relative_gain'] == 0.1678 and served['best_iteration'] == 2


def test_negative_gain_is_measured_and_never_an_improvement():
    result = _benchmark_loop()
    result['loop']['iterations'][1]['benchmark'] = _report(-0.015, [0.9874, 1.0405], False,
        gates={'minimum_gain': False, 'ci_upper_bound': False, 'max_workload_regression': True})
    row = projection.project_loop(result)['iterations'][1]
    assert row['benchmark']['relative_gain'] == -0.015 and row['improvement_basis'] is None
    assert row['improved'] is True  # The scorer's flag is shown, but no improvement is claimed from it.


def test_single_job_floor_is_labelled_and_never_a_measured_speedup():
    lineage = projection.project_loop(_benchmark_loop(method='single_job_floor'))
    assert lineage['schema'] == projection.LINEAGE_SCHEMA_V2 and lineage['benchmark_baseline'] is None
    second = lineage['iterations'][1]
    assert second['latency_method'] == 'single_job_floor' and second['above_noise'] is True and second['improved'] is True
    assert second['improvement_basis'] is None and second['benchmark'] is None
    gained = _benchmark_loop(method='single_job_floor')
    gained['loop']['iterations'][1]['score']['correctness'] = {'parent': 2 / 3, 'candidate': 1.0}
    assert projection.project_loop(gained)['iterations'][1]['improvement_basis'] == 'correctness'


def test_loop_without_benchmark_data_keeps_lineage_v1_exactly():
    lineage = projection.project_loop(_loop_result(['# first\nreturn 2\n', '# second\nreturn 1\n']))
    assert lineage['schema'] == projection.LINEAGE_SCHEMA and set(lineage) == set(projection.LINEAGE_FIELDS.split())
    assert all(set(row) == set(projection.ITERATION_FIELDS.split()) for row in lineage['iterations'])


@pytest.mark.parametrize('fault', ['basis-without-objective', 'floor-basis', 'correctness-basis-without-gain',
                                   'extra-benchmark-field', 'inverted-ci', 'unknown-method', 'v2-fields-on-v1'])
def test_forged_benchmark_claims_fail_closed(fault):
    value = _benchmark_publication()
    projection.validate_publication(copy.deepcopy(value), workspace_id='unit-workspace')
    run = value['snapshot']['runs'][0]
    first, second = run['lineage']['iterations'][:2]
    if fault == 'basis-without-objective':
        second['benchmark']['objective_met'] = False
    elif fault == 'floor-basis':
        second['latency_method'] = 'single_job_floor'
    elif fault == 'correctness-basis-without-gain':
        second['improvement_basis'] = 'correctness'
    elif fault == 'extra-benchmark-field':
        second['benchmark']['evidence_refs'] = []
    elif fault == 'inverted-ci':
        second['benchmark']['ratio_confidence_interval'] = [0.9, 0.8]
    elif fault == 'unknown-method':
        first['latency_method'] = 'wall_clock_guess'
    else:
        run['lineage']['schema'] = projection.LINEAGE_SCHEMA
    with pytest.raises(projection.ProjectionError):
        projection.validate_publication(value, workspace_id='unit-workspace')
