"""CPU-only native package workflows; measurements below are synthetic fixtures."""
import copy
from pathlib import Path
import sys

import pytest

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.store import Store

PACKAGE = Path('jiuwenswarm/factory/ccs/inference_lab')


def baseline_profile():
    return dict(args=['--pack', '/pack', '--experts', '6', '--mmap-experts', 'on',
        '--cpu-threads', '8', '--reserve-mib', '16384', '--vram-experts', '1.0',
        '--dspark', 'none', '--dspark-conf', '0.65', '--no-expert-cache',
        '--prefill-chunk', '256'], environment={'STRATA_DS4_REUSE': '0',
        'DS4_UMA_HEADROOM_GIB': '16', 'DS4_COPY_ALL': '0', 'DS4_STORE_GB': '0'},
        image='sha256:' + 'a' * 64, limits={'cpus': 8, 'memory_bytes': 104 * 2**30})


@pytest.fixture
def lab_package(tmp_path, monkeypatch):
    home = tmp_path / 'factory'
    with Store(home) as store:
        store.create_task(dict(task_id='lab', objective='Investigate retained inference evidence'))
        store.create_task(dict(task_id='private', objective='Unrelated work'))
        request = dict(prompt='same', ids=[1, 2], finish_reason='length',
            generated_tokens=2, decode_ms=1000, prompt_tokens=4, prompt_ms=100,
            draft_offered=0, draft_accepted=0)
        store.append_observation('lab', dict(obs_id='retained-report', kind='report',
            values={'status': 'success', 'container_removed': True,
                    'requests': [request, copy.deepcopy(request)]}))
        store.append_observation('private', dict(obs_id='private-report', kind='report',
            values={'status': 'success'}))
    monkeypatch.setenv('FACTORY_HOME', str(home))
    monkeypatch.setenv('FACTORY_TASK_ID', 'lab')
    monkeypatch.setenv('PYTHONPATH', str(Path.cwd()))
    monkeypatch.delenv('FACTORY_READ_TASKS', raising=False)
    host = Host(tmp_path / 'ccstore', session_grants=['process.exec'], python=sys.executable)
    return home, host, host.prepare(PACKAGE)


def call(package, capability, inputs, key=None):
    _, host, release = package
    receipt = host.call(release, capability, inputs, key=key or capability)
    assert receipt['state'] == 'succeeded', receipt
    return receipt['outputs']


@pytest.mark.parametrize('capability,setting,value,inputs', [
    ('apply_prefill', '--prefill-chunk', '512', {'chunk_tokens': 512}),
    ('apply_drafting', '--dspark', 'on', {'enabled': True}),
])
def test_inquire_analyze_transform_and_save_next_input(lab_package, capability, setting, value, inputs):
    items = call(lab_package, 'query', {'kinds': ['report']})['items']
    assert [row['id'] for row in items] == ['retained-report']
    record = call(lab_package, 'read', {'id': items[0]['id']})['record']
    assert record['values']['requests'][0]['generated_tokens'] == 2
    analysis = call(lab_package, 'diagnose', {'evidence_ids': [record['obs_id']]})['analysis']
    assert analysis['decode_tps']['median'] == 2
    assert analysis['semantic_accuracy'] == 'not_established'
    scope = call(lab_package, 'test_scope',
        {'claim': 'subsystem_performance', 'layer': 'prefill' if capability == 'apply_prefill' else 'drafting'})['analysis']
    assert scope['smallest_useful_scope'] == 'subsystem'
    assert scope['execution_authorized'] is False
    baseline = baseline_profile()
    candidate = call(lab_package, capability, {'base_profile': baseline, **inputs})
    index = baseline['args'].index(setting) + 1
    assert candidate['profile']['args'][index] == value
    changed = copy.deepcopy(baseline)
    changed['args'][index] = value
    assert candidate['profile'] == changed
    assert candidate['change']['maximum_changed_variables'] == 1
    assert candidate['change']['performance_benefit'] == 'unknown'
    followup = call(lab_package, 'followup', {'evidence_ids': [record['obs_id']]})['analysis']
    assert followup['status'] == 'proposal_only'
    saved = call(lab_package, 'publish', {'type': 'observation', 'record': {
        'obs_id': 'saved-next-input', 'kind': 'methodology_proposal',
        'values': {'followup': followup, 'candidate': candidate,
                   'claim_scope': scope, 'evidence_ids': [record['obs_id']]}}})['record']
    reread = call(lab_package, 'read', {'id': saved['obs_id']}, key='read-next')['record']
    assert reread['values']['candidate'] == candidate
    assert reread['values']['followup']['requires_operator_admission'] is True
    with Store(lab_package[0]) as store:
        assert store.get_task('lab')['contract_id'] == ''
        assert store._db.execute('SELECT count(*) FROM attempts').fetchone()[0] == 0
        assert store.read('lab', 'retained-report') == record


def test_analysis_cannot_read_private_evidence_or_publish_host_verdict(lab_package):
    _, host, release = lab_package
    for capability, inputs in [
        ('read', {'id': 'private-report', 'task_id': 'private'}),
        ('diagnose', {'evidence_ids': ['private-report']}),
        ('publish', {'type': 'observation', 'record': {'kind': 'scoped_prefill_result',
            'values': {'verdict': 'scoped_improvement'}}}),
        ('apply_prefill', {'base_profile': baseline_profile(), 'chunk_tokens': 0}),
    ]:
        receipt = host.call(release, capability, inputs, key='deny-' + capability)
        assert receipt['state'] != 'succeeded', receipt
    with Store(lab_package[0]) as store:
        assert not store.query('lab', kinds=['scoped_prefill_result'])['items']
        assert store._db.execute('SELECT count(*) FROM attempts').fetchone()[0] == 0


def test_execution_requires_explicit_effect_even_in_analysis_package(lab_package):
    _, host, release = lab_package
    for capability, inputs in [('execute', {'cycle_id': 'unadmitted'}),
        ('lab_submit', {'image': {'tag': 'test', 'id': 'sha256:' + 'a'*64},
         'build_attempt_id': 'missing', 'contract_id': 'missing', 'run_config': {}, 'idem_key': 'no-run'})]:
        receipt = host.call(release, capability, inputs, key='no-grant-' + capability)
        assert receipt['state'] != 'succeeded', receipt
    with Store(lab_package[0]) as store:
        assert store._db.execute('SELECT count(*) FROM attempts').fetchone()[0] == 0
