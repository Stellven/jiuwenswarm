"""Native package integration with real SQLite/Host; no GPU or model execution."""
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory import prefill_workbench
from jiuwenswarm.factory.store import Store
from test_strata_prefill import v2

PACKAGE = Path(__file__).resolve().parents[2] / 'jiuwenswarm/factory/ccs/strata_prefill_workbench'


@pytest.fixture
def job(tmp_path, monkeypatch):
    home = tmp_path / 'factory'
    host = Host(home / 'ccstore', session_grants=['process.exec', 'gpu.use'], python=sys.executable)
    release = host.prepare(PACKAGE)
    base = v2()
    base.update(workspace_root=str(tmp_path), assets={})
    contract = prefill_workbench.design(base, [42] * 512,
        {f'tokenizer/{name}': 'a' * 64 for name in ('vocab.json', 'token_type.json', 'tokenizer.json')})
    template = tmp_path / 'screen.json'
    template.write_text(json.dumps(contract))
    policy = dict(id='configuration', release=release, capabilities=['apply', 'verify_profile'],
        required_units=['profile-single-change'], allowed_effects=['process.exec'])
    with Store(home) as store:
        store.create_task(dict(task_id='prefill-job', objective='Scoped prefill improvement',
            contract_id=str(template), allowed_effects=['process.exec', 'gpu.use'], constraints={
                'cc_qualification': {'policies': [policy]},
                'factory_loop': dict(max_cycles=2, max_experiments=2, wall_clock_s=300,
                    templates=[dict(id='screen', path=str(template),
                        sha256=hashlib.sha256(template.read_bytes()).hexdigest(),
                        allowed_hypothesis_ids=['measure_io_readiness'])])}))
        store.create_task(dict(task_id='private', objective='Other task'))
        store.append_observation('private', dict(obs_id='secret', values={'status': 'success'}))
    monkeypatch.setenv('FACTORY_HOME', str(home))
    monkeypatch.setenv('FACTORY_TASK_ID', 'prefill-job')
    monkeypatch.setenv('FACTORY_READ_TASKS', '')
    monkeypatch.setenv('PYTHONPATH', str(Path.cwd()))
    monkeypatch.delenv('FACTORY_BRIDGE_DIR', raising=False)
    def call(capability, **inputs):
        receipt = host.call(release, capability, inputs)
        assert receipt['state'] == 'succeeded', receipt
        return receipt['outputs']
    return host, release, home, contract, call


def test_actual_host_prefill_job_evidence_method_component_qualification_chain(job):
    host, release, home, contract, call = job
    declaration = host.describe(release)
    assert declaration['version'] == '1.1.1'
    from jiuwenswarm.ccv2.roles import read_roles
    roles = read_roles(declaration, PACKAGE)
    assert roles['materials']['component'] == 'component'
    assert roles['materials']['integration'] == 'skill'
    assert call('inspect')['result']['execution_performed'] is False
    published = call('publish', type='observation', record=dict(obs_id='seed', kind='report',
        values={'status': 'success'}))
    assert published['record']['obs_id'] == 'seed'
    assert any(item['id'] == 'seed' for item in call('query')['items'])
    assert call('read', id='seed')['record']['obs_id'] == 'seed'
    analysis = call('diagnose', evidence_ids=['seed'])['analysis']
    assert analysis['evidence_sources'] == [{'task_id': 'prefill-job', 'evidence_id': 'seed'}]
    assert call('ablation', evidence_ids=['seed'])['analysis']['scoring_ready'] is False
    assert call('followup', evidence_ids=['seed'])['analysis']['requires_operator_admission'] is True
    scope = call('test_scope', claim='subsystem_performance', layer='prefill')['analysis']
    assert scope['promotion_authorized'] is False
    candidate = call('apply', base_profile=contract['arms']['A'], chunk_tokens=512)['result']['profile']
    assert candidate == contract['arms']['B']
    assert call('verify_profile', profile=candidate, chunk_tokens=512)['result']['runtime_engagement'] == 'not_measured'
    qualified = call('qualify_profile', policy_id='configuration',
        base_profile=contract['arms']['A'], chunk_tokens=512)['result']
    assert qualified['profile'] == candidate
    assert qualified['verification']['verification']['verdict'] == 'passed'
    assert qualified['admission']['eligibility']['verdict'] == 'eligible'
    assert qualified['execution_authorized'] is qualified['promotion_authorized'] is False
    assert call('read', id=qualified['profile_evidence_id'])['record']['values']['candidate_profile'] == candidate
    with Store(home) as store:
        rows = store.query('prefill-job', kinds=['cc_admission_assessment'])['items']
        assert rows
        assert store._db.execute('SELECT count(*) FROM attempts').fetchone()[0] == 0
    denied = host.call(release, 'read', {'id': 'secret'})
    assert denied['state'] == 'failed'
    forged = host.call(release, 'publish', {'type': 'observation',
        'record': {'kind': 'scoped_prefill_result', 'values': {'verdict': 'scoped_improvement'}}})
    assert forged['state'] == 'failed'


def test_actual_host_prefill_job_loop_with_fake_runtime_only(job, tmp_path, monkeypatch):
    """Only runtime submit/result are fake; no fabricated timing or scientific result."""
    host, release, home, contract, call = job
    seam = tmp_path / 'runtime-seam'
    seam.mkdir()
    (seam / 'sitecustomize.py').write_text('''
from jiuwenswarm.factory import prefill_workbench
class FakeRuntime:
    def __init__(self, store): self.store = store
    def submit(self, task_id, contract_id, idem_key):
        rows = self.store._db.execute('SELECT attempt_id FROM attempts WHERE task_id=? AND idem_key=?', (task_id, idem_key)).fetchall()
        if rows: return self.store.read(task_id, rows[0]['attempt_id'])
        return self.store.create_attempt(task_id, dict(kind='lab', idem_key=idem_key, fingerprint='offline-runtime-seam', request={'contract_id': contract_id}))
    def result(self, task_id, attempt_id):
        self.store.read(task_id, attempt_id)
        return dict(attempt_id=attempt_id, state='failed', analysis=dict(status='failed', verdict='inconclusive', error='Offline runtime seam; no GPU execution'))
prefill_workbench.Workbench = FakeRuntime
''')
    monkeypatch.setenv('PYTHONPATH', str(seam) + os.pathsep + str(Path.cwd()))
    call('publish', type='observation', record=dict(obs_id='seed', kind='report', values={'status': 'success'}))
    call('qualify_profile', policy_id='configuration', base_profile=contract['arms']['A'], chunk_tokens=512)
    assert call('loop_status')['result']['cycles'] == []
    selected = call('select', cycle_id='one', evidence_ids=['seed'],
        hypothesis_id='measure_io_readiness', template_id='screen', expected_rev=0)['result']
    assert selected['state'] == 'selected'
    sent = call('execute', cycle_id='one')['result']
    assert call('execute', cycle_id='one')['result']['attempt_id'] == sent['attempt_id']
    collected = call('collect', cycle_id='one')['result']
    assert collected['state'] == 'collected'
    assert collected['result']['analysis']['verdict'] == 'inconclusive'
    assert call('read', id=collected['evidence_id'])['record']
    assert call('followup', evidence_ids=[collected['evidence_id']])['analysis']['requires_operator_admission'] is True
    call('stop', reason='Offline seam demonstrated lifecycle; no measurement claim')
    assert call('loop_status')['result']['stopped'] == 'Offline seam demonstrated lifecycle; no measurement claim'
    with Store(home) as store:
        assert store._db.execute('SELECT count(*) FROM attempts').fetchone()[0] == 1
        assert store.get_task('prefill-job')['contract_id'].endswith('screen.json')
