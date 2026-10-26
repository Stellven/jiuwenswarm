from copy import deepcopy

from jiuwenswarm.research.process_evidence import validate_process_evidence


class Store:
    def __init__(self, records):
        self.records = records

    def read_record(self, ref):
        return deepcopy(self.records[ref['id']])

    def record_kind(self, ref):
        return 'science-runtime' if ref['id'] == 'runtime' else 'record'

    def iter_records(self, *, run_id=None, kinds=None):
        return [{'record': deepcopy(item)} for item in self.attestations
                if item.get('run_id') == run_id and item.get('kind') in kinds]


def evidence():
    config, policy, decl = ({'id': 'config'}, {'id': 'policy'}, {'id': 'decl'})
    impl, deps, admission = [{'id': 'impl'}], [{'id': 'dep'}], {'id': 'admission'}
    child_ref, parent_ref, runtime_ref, proof_ref = (
        {'id': 'child'}, {'id': 'parent'}, {'id': 'runtime'}, {'id': 'proof'})
    selected = {'declaration_ref': decl, 'implementation_refs': impl,
                'dependency_refs': deps, 'admission_ref': admission}
    records = {
        'runtime': {'schema': 'ai4r-science-runtime:5', 'execution_mode': 'm1_app_process',
                    'execution_bindings': [{'configuration_ref': config, 'policy_ref': policy,
                        'declaration_ref': decl, 'implementation_refs': impl,
                        'dependency_refs': deps, 'admission_ref': admission}]},
        'child': {'run_id': 'run', 'node_contract_ref': parent_ref, 'bindings': [selected]},
        'parent': {'configuration_ref': config, 'policy_ref': policy},
        'proof': {'schema': 'ai4r-m1-process:1', 'execution_mode': 'm1_app_process',
                  'runtime_ref': runtime_ref, 'job_id': 'job', 'contract_ref': child_ref,
                  'invocation_id': 'invoke', 'ready': True, 'executor_uid': 10002,
                  'executor_gid': 10002, 'no_new_privileges': '1', 'cap_effective': '0',
                  'cpu_affinity': [0], 'cwd': '/tmp/job', 'mode': 'm1_app_process'},
    }
    raw = {'execution_mode': 'm1_app_process', 'runtime_ref': runtime_ref,
           'contract_ref': child_ref, 'invocation_id': 'invoke', 'job_id': 'job',
           'observed_runtime': True, 'observed_limits': {'execution_mode': 'm1_app_process',
               'process_observation_ref': proof_ref, 'network': 'inherited',
               'memory_max': None, 'pids_max': None}}
    store = Store(records)
    store.attestations = [{'kind': 'm1_process_execution', 'run_id': 'run', 'job_id': 'job',
        'contract_ref': child_ref, 'invocation_id': 'invoke', 'runtime_ref': runtime_ref,
        'receipt': deepcopy(raw)}]
    return store, raw


def test_accepts_m1_only_when_original_schema5_mapping_and_process_proof_join():
    store, raw = evidence()
    assert validate_process_evidence(store, raw, expected_uid=10002, expected_gid=10002,
        contract_ref=raw['contract_ref'], invocation_id='invoke', job_id='job')


def test_legacy_evidence_returns_false_for_existing_strict_checker_path():
    store, raw = evidence()
    raw.pop('execution_mode')
    assert not validate_process_evidence(store, raw, expected_uid=10002, expected_gid=10002)


def test_runtime5_requires_explicit_mode_and_preserves_historical_decoder():
    import pytest
    from jiuwenswarm.research.executor import ExecutorBlocked
    from jiuwenswarm.research.science_runtime import decode_science_runtime_record
    from tests.unit_tests.research.test_executor_rpc import _i032_runtime_data
    old = _i032_runtime_data()
    assert decode_science_runtime_record(old).record == old
    current = dict(old, schema='ai4r-science-runtime:5', execution_mode='m1_app_process', scoring_profile=None)
    assert decode_science_runtime_record(current).record == current
    for broken in [dict(current, execution_mode='restricted'), {k:v for k,v in current.items() if k!='execution_mode'}]:
        with pytest.raises(ExecutorBlocked):
            decode_science_runtime_record(broken)


def test_scoring_may_append_only_its_protected_reference_to_original_process_receipt():
    store, raw = evidence()
    raw['trusted_scoring_ref'] = {'id':'root-score'}
    assert validate_process_evidence(store, raw, expected_uid=10002, expected_gid=10002)
    raw['wall_time_s'] = 0.001
    assert not validate_process_evidence(store, raw, expected_uid=10002, expected_gid=10002)


def test_rejects_missing_root_mode_wrong_runtime_and_claimed_isolation():
    store, raw = evidence()
    store.records['runtime'].pop('execution_mode')
    assert not validate_process_evidence(store, raw, expected_uid=10002, expected_gid=10002)
    store, raw = evidence()
    raw['runtime_ref'] = {'id': 'other'}
    assert not validate_process_evidence(store, raw, expected_uid=10002, expected_gid=10002)
    store, raw = evidence()
    raw['observed_limits']['network'] = 'none'
    assert not validate_process_evidence(store, raw, expected_uid=10002, expected_gid=10002)
    store, raw = evidence()
    raw['observed_limits']['isolation_probe_ref'] = {'id': 'fake'}
    assert not validate_process_evidence(store, raw, expected_uid=10002, expected_gid=10002)
