"""Real Host boundaries and explicit fake API routing; no build, Docker or GPU run."""
import json
from pathlib import Path
import sys

import pytest

from jiuwenswarm.ccv2.ccv2 import Host, load
from jiuwenswarm.factory.store import Store

ROOT = Path(__file__).resolve().parents[2]
CCS = ROOT / 'jiuwenswarm/factory/ccs'
PACKAGES = ('expert_streaming', 'integration_skill')
ALIASES = {
    **{'evidence_' + op: 'evidence.' + op for op in ('query', 'read', 'publish')},
    **{op: 'inspector.' + op for op in ('inspect', 'inspect_strata', 'preflight', 'verify_effective_config')},
    **{'build_' + op: 'builder.' + op for op in ('submit', 'status', 'cancel', 'result')},
    **{'lab_' + op: 'lab.' + op for op in ('submit', 'status', 'cancel', 'result', 'ab_submit', 'ab_status', 'ab_result')},
}


@pytest.fixture
def native(tmp_path, monkeypatch):
    home = tmp_path / 'factory'
    with Store(home) as store:
        store.create_task(dict(task_id='owned', objective='Offline integration package'))
        store.create_task(dict(task_id='private', objective='Other task'))
        store.append_observation('private', dict(obs_id='private-observation', values={'secret': 'private'}))
    monkeypatch.setenv('FACTORY_HOME', str(home))
    monkeypatch.setenv('FACTORY_TASK_ID', 'owned')
    monkeypatch.setenv('FACTORY_READ_TASKS', '')
    monkeypatch.setenv('PYTHONPATH', str(ROOT))
    monkeypatch.delenv('FACTORY_PYTHON', raising=False)
    return home


def host_call(tmp_path, package, capability, inputs, grants=('process.exec',), resources=None):
    host = Host(tmp_path / 'ccstore', session_grants=grants, resources=resources, python=sys.executable)
    return host.call(host.prepare(CCS / package), capability, inputs)


@pytest.mark.parametrize('package', PACKAGES)
def test_self_contained_job_surface(package):
    declaration = load(CCS / package / 'cc.yaml')
    assert set(ALIASES) <= set(declaration['capabilities'])
    assert declaration['version'] == ('2.1.0' if package == 'expert_streaming' else '1.1.0')
    assert declaration['id'] == ('engine.expert_streaming' if package == 'expert_streaming' else 'factory.integration_skill')
    for name in ('integrate', 'repair', 'preflight', 'integration_job'):
        material = declaration['materials'][name]
        assert material['kind'] == 'skill'
        assert (CCS / package / material['path']).is_file()
    for capability in ('lab_submit', 'lab_ab_submit', 'preflight', 'verify_effective_config'):
        assert 'gpu.use' in declaration['capabilities'][capability]['changes']
    assert 'workspace.read' in declaration['capabilities']['inspect']['changes']
    if package == 'expert_streaming':
        assert {'applicability', 'engagement'} <= set(declaration['capabilities'])
        assert sum(material['kind'] == 'component' for material in declaration['materials'].values()) == 8


def test_bundled_integration_materials_match_explicit_source():
    assert (CCS / 'expert_streaming/AB.md').read_bytes() == (CCS / 'methodology_ab/AB.md').read_bytes()
    for filename in ('JOB.md', 'INTEGRATE.md', 'PREFLIGHT.md', 'REPAIR.md'):
        assert (CCS / 'expert_streaming' / filename).read_bytes() == (CCS / 'integration_skill' / filename).read_bytes()


@pytest.mark.parametrize('package', PACKAGES)
def test_real_host_evidence_and_scope(native, tmp_path, package):
    published = host_call(tmp_path, package, 'evidence_publish', {'type': 'observation',
        'record': {'obs_id': 'integration-observation', 'values': {'kind': 'fixture'}}})
    assert published['state'] == 'succeeded', published
    assert published['outputs']['record']['obs_id'] == 'integration-observation'
    read = host_call(tmp_path, package, 'evidence_read', {'id': 'integration-observation'})
    assert read['outputs']['record']['values'] == {'kind': 'fixture'}
    query = host_call(tmp_path, package, 'evidence_query', {})
    assert query['state'] == 'succeeded' and isinstance(query['outputs']['items'], list)
    denied = host_call(tmp_path, package, 'evidence_read', {'id': 'private-observation', 'task_id': 'private'})
    assert denied['state'] == 'failed' and denied['reason'] in {'NOT_FOUND', 'SCOPE_DENIED'}, denied


@pytest.mark.parametrize('package', PACKAGES)
@pytest.mark.parametrize('capability,inputs,grants', [
    ('evidence_query', {}, ()),
    ('lab_submit', {'image': {'tag': 'fake:only', 'id': 'sha256:' + 'a' * 64},
        'build_attempt_id': 'fake-build', 'contract_id': 'fake-contract', 'run_config': {}, 'idem_key': 'fake'}, ('process.exec',)),
    ('verify_effective_config', {'image': {'tag': 'fake:only'}, 'env': {}}, ('process.exec',)),
])
def test_host_denies_before_api_execution(native, tmp_path, monkeypatch, package, capability, inputs, grants):
    fake = tmp_path / 'forbidden-api'
    marker = tmp_path / 'executed'
    fake.write_text('#!' + sys.executable + '\nfrom pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n')
    fake.chmod(0o755)
    monkeypatch.setenv('FACTORY_PYTHON', str(fake))
    receipt = host_call(tmp_path, package, capability, inputs, grants)
    assert receipt['state'] in {'blocked', 'failed'} and receipt['reason'] == 'DENIED', receipt
    assert not marker.exists()


@pytest.mark.parametrize('package', PACKAGES)
def test_host_preserves_workspace_containment(native, tmp_path, package):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    receipt = host_call(tmp_path, package, 'inspect', {'source': 'workspace', 'subpath': '..'},
        ('process.exec', 'workspace.read'), {'workspace': {'kind': 'workspace', 'path': str(workspace)}})
    assert receipt['state'] == 'failed' and receipt['reason'] == 'INVALID_INPUT', receipt
    assert receipt['outputs']['evidence']['observation_id']


@pytest.fixture
def fake_api(native, tmp_path, monkeypatch):
    """Fake only the existing API process, making every routing assertion observable."""
    program = tmp_path / 'fake-api'
    log = tmp_path / 'api.jsonl'
    response = tmp_path / 'response.json'
    program.write_text('#!' + sys.executable + '''
import json, os, sys
from pathlib import Path
packet = json.load(sys.stdin)
with open(os.environ['INTEGRATION_TEST_LOG'], 'a') as stream:
    stream.write(json.dumps({'argv': sys.argv[1:], 'packet': packet}) + '\\n')
print(Path(os.environ['INTEGRATION_TEST_RESPONSE']).read_text())
''')
    program.chmod(0o755)
    monkeypatch.setenv('FACTORY_PYTHON', str(program))
    monkeypatch.setenv('INTEGRATION_TEST_LOG', str(log))
    monkeypatch.setenv('INTEGRATION_TEST_RESPONSE', str(response))
    return log, response


def attempt(state='queued'):
    return dict(attempt_id='fake-attempt', task_id='owned', kind='build', idem_key='fake-key',
        fingerprint='fake-fingerprint', request={}, state=state, jobq_id='fake-job', owner={},
        started=None, ended=None, resources={}, result_refs=[], cleanup_state='pending', history=[])


@pytest.mark.parametrize('package', PACKAGES)
def test_fake_two_phase_build_and_lab_route_through_host(fake_api, tmp_path, package):
    log, response = fake_api
    submit = {'attempt_id': 'fake-attempt', 'state': 'queued', 'jobq_id': 'fake-job'}
    cases = [
        ('build_submit', {'request': {'source': {'path': '/fake/owned', 'commit': 'a' * 40}}, 'idem_key': 'fake-build'}, submit),
        ('build_status', {'attempt_id': 'fake-attempt'}, attempt()),
        ('build_result', {'attempt_id': 'fake-attempt'}, {'attempt_id': 'fake-attempt', 'state': 'queued', 'result_refs': []}),
        ('build_cancel', {'attempt_id': 'fake-attempt'}, attempt('cancelled')),
        ('lab_submit', {'image': {'tag': 'fake:only', 'id': 'sha256:' + 'a' * 64}, 'build_attempt_id': 'fake-build',
            'contract_id': 'fake-contract', 'run_config': {}, 'idem_key': 'fake-lab'}, dict(submit, admission={'admission_id': 'fake-admission'})),
        ('lab_status', {'attempt_id': 'fake-attempt'}, dict(attempt(), kind='lab')),
        ('lab_result', {'attempt_id': 'fake-attempt'}, dict(attempt_id='fake-attempt', state='queued', result_refs=[], execution_outcome='not_run', evaluation={}, evidence_refs=[])),
        ('lab_cancel', {'attempt_id': 'fake-attempt'}, dict(attempt('cancelled'), kind='lab')),
        ('lab_ab_submit', {'base_image': {}, 'candidate_image': {}, 'base_env': {}, 'candidate_env': {},
            'rounds': 1, 'component': 'expert_fill', 'idem_key': 'fake-ab'}, dict(attempt(), kind='lab')),
        ('lab_ab_status', {'attempt_id': 'fake-attempt'}, dict(attempt(), kind='lab')),
        ('lab_ab_result', {'attempt_id': 'fake-attempt'}, dict(attempt_id='fake-attempt', state='queued', result_refs=[], execution_outcome='not_run', evaluation={}, evidence_refs=[], ab_result={})),
    ]
    for capability, inputs, outputs in cases:
        response.write_text(json.dumps({'outcome': 'ok', 'outputs': outputs}))
        receipt = host_call(tmp_path, package, capability, inputs, ('process.exec', 'gpu.use'))
        assert receipt['state'] == 'succeeded', json.dumps(receipt)
        assert receipt['outputs'] == outputs
        if capability.endswith('submit'):
            assert receipt['outputs']['state'] == 'queued'
            assert 'evaluation' not in receipt['outputs']
        call = json.loads(log.read_text().splitlines()[-1])
        assert call['argv'] == ['-m', 'jiuwenswarm.factory.api', ALIASES[capability]]
        assert call['packet']['capability'] == ALIASES[capability]
        assert call['packet']['inputs'] == inputs


@pytest.mark.parametrize('package', PACKAGES)
def test_real_host_attempt_kind_and_task_boundaries(native, tmp_path, package):
    with Store(native) as store:
        lab = store.create_attempt('owned', dict(kind='lab', idem_key='lab', fingerprint='lab', request={}))
        build = store.create_attempt('owned', dict(kind='build', idem_key='build', fingerprint='build', request={}))
        foreign = store.create_attempt('private', dict(kind='build', idem_key='foreign', fingerprint='foreign', request={}))
    for capability, identifier in [
        ('build_status', lab['attempt_id']), ('build_cancel', lab['attempt_id']), ('build_result', lab['attempt_id']),
        ('lab_status', build['attempt_id']), ('lab_cancel', build['attempt_id']), ('lab_result', build['attempt_id']),
        ('build_status', foreign['attempt_id']), ('build_cancel', foreign['attempt_id']), ('build_result', foreign['attempt_id']),
    ]:
        receipt = host_call(tmp_path, package, capability, {'attempt_id': identifier})
        assert receipt['state'] == 'failed' and receipt['reason'] == 'SCOPE_DENIED', receipt
    with Store(native) as store:
        assert store._get('attempts', 'owned', lab['attempt_id'])['state'] == 'queued'
        assert store._get('attempts', 'private', foreign['attempt_id'])['state'] == 'queued'
