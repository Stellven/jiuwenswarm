"""Read-only Strata streaming inspection; no inference/GPU/engine mutation."""
import copy
import json
import struct

import pytest

from jiuwenswarm.factory import contract as contracts
from jiuwenswarm.factory.engine_adapters import sha
from jiuwenswarm.factory.expert_streaming import dispatch, parse_strata_engagement, strata_applicability
from jiuwenswarm.factory.jobs import metadata


@pytest.fixture
def strata_contract(tmp_path):
    files = []
    for name in ('experts-1.gguf', 'experts-2.gguf', 'engram.gguf', 'draft.gguf'):
        path = tmp_path / name
        path.write_bytes(('synthetic-' + name).encode())
        stat = path.stat()
        files.append(dict(path=str(path), sha256=sha(path), st_size=stat.st_size,
                          st_mtime_ns=stat.st_mtime_ns, st_ctime_ns=stat.st_ctime_ns))
    inventory = tmp_path / 'assets.json'
    inventory.write_text(json.dumps(dict(files=files, pack_files={})))
    return dict(adapter='strata-v1', contract_id='strata-stream-test-v1', version=1, target='spark-gb10',
        tolerance='canonical-token-ids-and-finish', scope='Synthetic protocol fixture',
        assets=dict(identity_path=str(inventory), identity_sha256=sha(inventory)),
        limits=dict(cpus=8, memory_bytes=104*2**30, extra_swap_bytes=0, guard_gib=8, timeout_s=900),
        workload=dict(argv=['--pack', str(tmp_path), '--experts', '6', '--mmap-experts', 'on', '--dspark', 'none'],
                      environment={'STRATA_DS4_REUSE': '0'}, requests=[dict(ids=[1, 2, 3], max_new_tokens=2)]*2))


def stdout():
    return ('READY 8192 stop\nT 42\nT 43\nDONE 2 3 100 20 length 0 0 0 0 0\n'
            'T 42\nT 43\nDONE 2 3 50 10 length 0 0 0 0 0\n')


def stderr():
    return 'ds4: experts per word: 6 (full quality)\n'


def task_contract(store, tmp_path, value):
    path = tmp_path / 'approved.json'
    path.write_text(json.dumps(value))
    store._db.execute('UPDATE tasks SET contract_id=? WHERE task_id=?', (str(path), 't'))
    return path


def lab_attempt(store, value, out=None, err=None, suffix='cell/'):
    attempt = store.create_attempt('t', dict(kind='lab', idem_key='strata', fingerprint='strata',
                                           request=dict(adapter='strata-v1', contract=value)))
    refs = []
    for name, content in [('stdout.log', stdout() if out is None else out), ('stderr.log', stderr() if err is None else err)]:
        ref = attempt['attempt_id'] + ':' + suffix + name
        store.put_artifact('t', ref, content.encode(), 'text/plain', attempt['attempt_id'])
        refs.append(ref)
    metadata(store, attempt, result_refs=refs)
    return attempt, refs


def test_applicability_reads_complete_sealed_inventory_not_llama_cpu_flags(strata_contract):
    result = strata_applicability(strata_contract)
    assert result['verdict'] == 'unknown'
    assert result['expert_bytes'] is result['other_bytes'] is result['experts_cpu_side'] is None
    assert result['mmap'] is True
    candidate = result['candidates'][0]
    assert candidate['status'] == 'configured_not_measured'
    assert candidate['configuration']['experts'] == 6
    assert len(candidate['assets']['files']) == 4
    assert candidate['assets']['total_bytes'] == sum(row['bytes'] for row in candidate['assets']['files'])
    assert candidate['expected_performance_benefit'] == 'unknown'
    assert any('2x-memory heuristic' in reason for reason in result['reasons'])


def test_applicability_approved_strata_contract_and_observation(store, tmp_path, strata_contract):
    task_contract(store, tmp_path, strata_contract)
    result = dispatch(store.scoped('t'), 't', 'applicability', {})
    assert result['candidates'][0]['backend'] == 'strata-v1'
    assert store.read('t', result['evidence']['observation_id'])['values']['verdict'] == 'unknown'
    altered = [*strata_contract['workload']['argv'], '--no-expert-cache']
    with pytest.raises(ValueError, match='approved contract argv'):
        dispatch(store.scoped('t'), 't', 'applicability', {'argv': altered})


def test_applicability_inventory_changes_fail_not_false_applicable(strata_contract):
    inventory = json.loads(open(strata_contract['assets']['identity_path']).read())
    from pathlib import Path
    Path(inventory['files'][1]['path']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='metadata changed'):
        strata_applicability(strata_contract)


def test_explicit_llama_path_and_argv_still_work_without_contract(store, tmp_path, monkeypatch):
    # A tiny valid GGUF header with no tensors is enough to prove no contract
    # lookup occurs. The observation accurately says no MoE tensors are present.
    model = tmp_path/'tiny.gguf'
    model.write_bytes(b'GGUF' + struct.pack('<IQQ', 3, 0, 0))
    monkeypatch.setattr(contracts, 'load', lambda _: (_ for _ in ()).throw(AssertionError('contract must not load')))
    result = dispatch(store.scoped('t'), 't', 'applicability', {'model_path': str(model), 'argv': ['-cmoe', '-lm', 'mmap']})
    assert result['verdict'] == 'not_applicable'
    assert result['expert_bytes'] == 0


def test_native_phase_units_and_unknown_readiness_are_separate(strata_contract):
    required = ['decode.ms_per_token', 'prompt.ms_per_token', 'readiness.ready_bytes_predicted']
    result = parse_strata_engagement(stdout(), stderr(), strata_contract, required)
    assert result['status'] == 'measured'
    assert result['config']['effective_experts'] == 6
    assert result['quantities']['decode.ms_per_token'] == 7.5
    assert result['quantities']['prompt.ms_per_token'] == 25
    assert result['timings']['decode']['unit'] == 'ms/token'
    assert result['draft'] == dict(status='measured', accepted=0, offered=0)
    assert result['derived']['decode_tokens'] == 4
    assert result['derived']['demand_wait_ms_per_token'] is None
    assert result['derived']['decode_bytes_read_per_token'] is None
    assert result['readiness'] == {'status': 'not_measured'}
    assert result['missing_required'] == ['readiness.ready_bytes_predicted']


def test_actual_drafting_counters_have_native_units(strata_contract):
    value = copy.deepcopy(strata_contract)
    value['workload']['argv'][-1] = 'on'
    result = parse_strata_engagement(stdout().replace('length 0 0', 'length 1 2'), stderr(), value)
    assert result['draft'] == dict(status='measured', accepted=2, offered=4)
    assert result['derived']['recall_at_k'] is None
    assert result['pregate'] == {'status': 'not_measured'}


@pytest.mark.parametrize('out,err', [
    ('READY 8192 stop\nT 42\n', 'experts per word: 6'),
    (stdout(), 'experts per word: 5'),
    (stdout(), 'no effective expert log'),
    (stdout().replace('100 20', '100 nan'), stderr()),
    (stdout(), stderr() + 'terminate called\n'),
])
def test_partial_failed_or_reduced_protocol_is_invalid_not_zero(strata_contract, out, err):
    required = ['decode.ms_per_token', 'readiness.ready_bytes_predicted']
    result = parse_strata_engagement(out, err, strata_contract, required)
    assert result['status'] == 'invalid'
    assert result['quantities'] == {}
    assert result['timings'] == {}
    assert result['missing_required'] == required
    assert all(value is None for value in result['derived'].values())


def test_strata_attempt_and_eval_use_snapshot_with_paired_raw_artifacts(store, tmp_path, strata_contract):
    attempt, refs = lab_attempt(store, strata_contract)
    # The current task has no Strata contract; the actual attempt/evaluation
    # snapshot must govern inspection instead of loading a different workload.
    required = ['decode.ms_per_token', 'readiness.ready_bytes_predicted']
    result = dispatch(store.scoped('t'), 't', 'engagement', dict(attempt_id=attempt['attempt_id'], requires_evidence=required))
    assert result['status'] == 'measured'
    assert result['runs'][0]['backend'] == 'strata-v1'
    assert result['missing_required'] == ['readiness.ready_bytes_predicted']
    observation = store.read('t', result['evidence']['observation_id'])
    assert observation['source_artifacts'] == refs
    evaluation = store.add_evaluation('t', dict(eval_id='strata-eval', contract_id=strata_contract['contract_id'],
        contract_version='1', contract=strata_contract, inputs={'source_artifacts': refs},
        execution_outcome='ok', correctness='not_evaluated', evidence_completeness='complete'))
    other = dispatch(store.scoped('t'), 't', 'engagement', dict(evaluation_id=evaluation['eval_id'], requires_evidence=required))
    assert other['runs'] == result['runs']


def test_missing_paired_stderr_is_not_measured(store, strata_contract):
    attempt, refs = lab_attempt(store, strata_contract)
    metadata(store, attempt, result_refs=refs[:1])
    result = dispatch(store.scoped('t'), 't', 'engagement', dict(attempt_id=attempt['attempt_id'], requires_evidence=['decode.ms_per_token']))
    assert result['status'] == 'not_measured'
    assert result['missing_required'] == ['decode.ms_per_token']
    assert result['runs'][0]['status'] == 'not_measured'


def test_strata_log_cannot_borrow_llama_units_or_other_arm_evidence(store, strata_contract):
    attempt, refs = lab_attempt(store, strata_contract)
    # A second arm with only partial protocol cannot borrow complete timing
    # evidence from the first arm, or a llama stderr counter in its own stream.
    for name, text in [('stdout.log', 'READY 8192 stop\nT 42\n'), ('stderr.log', stderr() + 'expert_readiness: stats decode_ready_bytes_predicted=999\n')]:
        ref = attempt['attempt_id'] + ':ab/002-candidate/' + name
        store.put_artifact('t', ref, text.encode(), 'text/plain', attempt['attempt_id'])
        refs.append(ref)
    metadata(store, attempt, result_refs=refs)
    result = dispatch(store.scoped('t'), 't', 'engagement', dict(attempt_id=attempt['attempt_id'], requires_evidence=['decode.ms_per_token', 'readiness.ready_bytes_predicted']))
    assert result['status'] == 'invalid'
    assert result['missing_required'] == ['decode.ms_per_token', 'readiness.ready_bytes_predicted']
    assert result['runs'][1]['quantities'] == {}
