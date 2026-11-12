"""Offline factory capsules through the real CC host; Docker is always a fake."""
import hashlib
import json
from pathlib import Path
import shlex
import sys

import jsonschema
import pytest
import yaml

from jiuwenswarm.ccv2.ccv2 import Host, load
from jiuwenswarm.ccv2.agent_mcp import Catalog
from jiuwenswarm.factory.store import Store

ROOT = Path(__file__).resolve().parents[2]
CCS = ROOT / 'jiuwenswarm/factory/ccs'
NAMES = ['builder', 'engine_component', 'engine_inspector', 'evidence', 'integration_skill', 'lab_client']


@pytest.mark.parametrize('name', NAMES)
def test_declarations_and_materials(name):
    folder = CCS / name
    declaration = yaml.safe_load((folder / 'cc.yaml').read_text())
    schema = json.loads((ROOT / 'jiuwenswarm/ccv2/schemas/cc.schema.json').read_text())
    jsonschema.validate(declaration, schema)
    assert load(folder / 'cc.yaml')['id'] == 'factory.' + name
    for material in declaration.get('materials', {}).values():
        path = (folder / material['path']).resolve()
        assert path.is_relative_to(folder.resolve()) and path.is_file()


def test_component_schema_and_hashes():
    folder = CCS / 'engine_component'
    component = yaml.safe_load((folder / 'component.yaml').read_text())
    schema = json.loads((ROOT / 'jiuwenswarm/factory/schemas/component.schema.json').read_text())
    jsonschema.validate(component, schema)
    assert hashlib.sha256((folder / component['change']['patch']).read_bytes()).hexdigest() == component['change']['sha256']
    patch = component['base']['pre_integration_patch']
    assert hashlib.sha256((folder / patch['file']).read_bytes()).hexdigest() == patch['sha256']
    assert component['configuration']['env']['LLAMA_EXPERT_PREGATE_K'] == '8'
    assert component['change']['touches'] == ['src/llama-expert-fill.h']
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(dict(component, unsupported=True), schema)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    home = tmp_path / 'factory'
    with Store(home) as store:
        store.create_task({'task_id': 'task', 'objective': 'offline capsule checks'})
    monkeypatch.setenv('FACTORY_HOME', str(home))
    # The host seals the resolved interpreter; expose this checkout to that
    # interpreter just as the controller must for source-based native APIs.
    monkeypatch.setenv('PYTHONPATH', str(ROOT))
    monkeypatch.setenv('FACTORY_TASK_ID', 'task')
    monkeypatch.setenv('FACTORY_READ_TASKS', '')
    fake = tmp_path / 'docker.py'
    fake.write_text('''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['FAKE_LOG'], 'a') as stream:
    stream.write(json.dumps(args) + '\\n')
if args[:2] == ['image', 'inspect']:
    print(json.dumps([{'Id': 'sha256:' + os.environ.get('FAKE_IMAGE_HEX', 'a') * 64,
                      'Architecture': 'arm64', 'Config': {'Labels': {'source': 'offline'}}}]))
elif args[0] == 'run':
    if args[-1] == '--help':
        print('usage: llama-completion -m MODEL -p PROMPT -n TOKENS -ngl N -c CTX --temp N -no-cnv --help')
    elif os.environ.get('FAKE_MODE', 'invalid') == 'invalid':
        print('expert_config: invalid LLAMA_EXPERT_PREGATE_K=99 (range 1..32)', file=sys.stderr)
        sys.exit(134)
    elif os.environ.get('FAKE_MODE') == 'timeout':
        import time
        time.sleep(5)
    elif os.environ.get('FAKE_MODE') == 'missing':
        print('model load failed', file=sys.stderr)
        sys.exit(1)
    else:
        print('expert_config: effective fill=1 random=decode max_tokens=1 threads=16 chunk_kib=2048 pregate=1 k=8 order=after max_inflight=4 lookahead=1 min_tokens=0 diag=0 populate=0 diag_csv=(unset) prefetch=0 prefetch_next=0', file=sys.stderr)
''')
    monkeypatch.setenv('FACTORY_DOCKER', shlex.join([sys.executable, str(fake)]))
    monkeypatch.setenv('FAKE_LOG', str(tmp_path / 'docker.jsonl'))
    # A real group wrapper must never run when the fake seam is installed.
    monkeypatch.setenv('DOCKER_CMD_PREFIX', 'unavailable-group-wrapper -c')
    return home, tmp_path / 'docker.jsonl'


def call(tmp_path, name, capability, inputs, grants):
    host = Host(tmp_path / ('host-' + name), session_grants=grants)
    return host.call(host.prepare(CCS / name), capability, inputs)


def test_evidence_host_roundtrip(setup, tmp_path):
    result = call(tmp_path, 'evidence', 'query', {}, ['process.exec'])
    assert result['state'] == 'succeeded', result
    assert result['outputs']['items'][0]['type'] == 'task'
    published = call(tmp_path, 'evidence', 'publish', {'type': 'observation', 'record': {'obs_id': 'obs', 'values': {'count': 1}}}, ['process.exec'])
    assert published['state'] == 'succeeded', published
    read = call(tmp_path, 'evidence', 'read', {'id': 'obs'}, ['process.exec'])
    assert read['outputs']['record']['values'] == {'count': 1}


def test_rejected_config_is_failed_receipt_with_evidence(setup, tmp_path):
    result = call(tmp_path, 'engine_inspector', 'verify_effective_config',
                  {'image': {'tag': 'test:mutable'}, 'env': {'LLAMA_EXPERT_PREGATE_K': '99'}}, ['process.exec', 'gpu.use'])
    assert result['state'] == 'failed', result
    assert result['reason'] == 'CONFIG_REJECTED'
    output = result['outputs']
    assert output['invalid_line'] == 'expert_config: invalid LLAMA_EXPERT_PREGATE_K=99 (range 1..32)'
    assert output['exit_status'] == 134 and output['aborted']
    home, log = setup
    with Store(home) as store:
        observation = store.read('task', output['evidence']['observation_id'])
        assert observation['error']['code'] == 'CONFIG_REJECTED'
        artifact = store.artifact_bytes('task', output['evidence']['artifact_id']).decode()
        assert output['invalid_line'] in artifact
    calls = [json.loads(row) for row in log.read_text().splitlines()]
    run = next(c for c in calls if c[0] == 'run')
    assert '--runtime' in run and 'nvidia' in run and 'factory=1' in run
    assert run[run.index('--entrypoint') + 2] == 'sha256:' + 'a' * 64
    assert run[-13:] == ['-m', '/probe/granite-3.1-1b-a400m-instruct-Q8_0.gguf', '-p', 'x', '-n', '1', '-ngl', '0', '-c', '256', '--temp', '0', '-no-cnv']
    name = run[run.index('--name') + 1]
    assert calls[-1] == ['rm', '-f', name]


@pytest.mark.parametrize('requested,code', [('8', None), ('10', 'CONFIG_MISMATCH')])
def test_effective_values(setup, tmp_path, monkeypatch, requested, code):
    monkeypatch.setenv('FAKE_MODE', 'effective')
    result = call(tmp_path, 'engine_inspector', 'verify_effective_config',
                  {'image': {'id': 'sha256:' + 'a' * 64}, 'env': {'LLAMA_EXPERT_PREGATE_K': requested}}, ['process.exec', 'gpu.use'])
    assert result['state'] == ('failed' if code else 'succeeded'), result
    assert result['outputs']['effective']['k'] == '8'
    if code:
        assert result['reason'] == code
        assert result['outputs']['mismatches']['LLAMA_EXPERT_PREGATE_K']['requested'] == requested


def test_missing_config_is_failed(setup, tmp_path, monkeypatch):
    monkeypatch.setenv('FAKE_MODE', 'missing')
    result = call(tmp_path, 'engine_inspector', 'verify_effective_config', {'image': {'tag': 'test:mutable'}, 'env': {}}, ['process.exec', 'gpu.use'])
    assert result['reason'] == 'CONFIG_MISSING' and result['state'] == 'failed'
    assert result['outputs']['evidence']['artifact_id']


@pytest.mark.parametrize('name,cap,inputs,grants', [
    ('evidence', 'query', {}, []),
    ('engine_inspector', 'verify_effective_config', {'image': {'tag': 'test:mutable'}, 'env': {}}, ['process.exec']),
])
def test_missing_grant_denied(setup, tmp_path, name, cap, inputs, grants):
    result = call(tmp_path, name, cap, inputs, grants)
    assert result['state'] in {'blocked', 'failed'} and result['reason'] == 'DENIED', result
    assert not setup[1].exists()


def test_preflight_flags_and_id_cache(setup, tmp_path, monkeypatch):
    inputs = {'image': {'tag': 'test:mutable'}, 'tool': 'llama-completion', 'argv': ['-m', 'model', '--cache-ram=4']}
    result = call(tmp_path, 'engine_inspector', 'preflight', inputs, ['process.exec', 'gpu.use'])
    assert result['state'] == 'failed' and result['reason'] == 'UNSUPPORTED_FLAG', result
    assert result['outputs']['unsupported_flags'] == ['--cache-ram']
    inputs['argv'] = ['-n', '1', '--temp=0']
    assert call(tmp_path, 'engine_inspector', 'preflight', inputs, ['process.exec', 'gpu.use'])['state'] == 'succeeded'
    log = setup[1]
    assert sum(json.loads(row)[0] == 'run' for row in log.read_text().splitlines()) == 1
    monkeypatch.setenv('FAKE_IMAGE_HEX', 'b')
    assert call(tmp_path, 'engine_inspector', 'preflight', inputs, ['process.exec', 'gpu.use'])['state'] == 'succeeded'
    assert sum(json.loads(row)[0] == 'run' for row in log.read_text().splitlines()) == 2
    assert len(list((setup[0] / 'preflight').glob('*.txt'))) == 2


def test_catalog_factory_capsules(tmp_path):
    catalog = Catalog([CCS, CCS / 'expert_streaming/components'], tmp_path / 'catalog')
    rows = catalog.scan()
    assert len(rows) == 15 and not catalog.errors
    by_id = {row['cc']: row for row in rows}
    assert set(by_id) == {'engine.expert_streaming'} | {'factory.' + name for name in NAMES + ['methodology_ab'] + ['components.' + n for n in ['mmap_advice', 'router_prefetch', 'expert_fill', 'expert_pregate', 'thread_names', 'expert_readiness', 'inflight_join']]}
    assert set(by_id['factory.engine_inspector']['capabilities']) == {'inspect', 'preflight', 'verify_effective_config'}
    assert set(by_id['factory.builder']['capabilities']) == {'submit', 'status', 'cancel', 'result'}
    assert set(by_id['factory.lab_client']['capabilities']) == {'submit', 'status', 'cancel', 'result', 'ab_submit', 'ab_status', 'ab_result'}
    assert set(by_id['factory.evidence']['capabilities']) == {'query', 'read', 'publish', 'plan_get', 'plan_patch'}
    assert by_id['factory.engine_component']['capabilities'] == {}
    assert by_id['factory.integration_skill']['capabilities'] == {}


def test_lab_unknown_attempt_is_not_found(setup, tmp_path):
    result = call(tmp_path, 'lab_client', 'status', {'attempt_id': 'not-yet'}, ['process.exec'])
    assert result['state'] == 'failed' and result['reason'] == 'NOT_FOUND', result


def test_inspect_checkout_and_source_containment(setup, tmp_path):
    from jiuwenswarm.factory.inspector import dispatch
    home, _ = setup
    with Store(home) as store:
        result = dispatch(store.scoped('task'), 'task', 'inspector.inspect', {
            'inputs': {'source': 'workspace', 'subpath': '.'},
            'resources': {'workspace': {'kind': 'workspace', 'path': str(ROOT)}}})
        assert result['outcome'] == 'ok', result
        assert len(result['outputs']['source']['commit']) == 40
        assert isinstance(result['outputs']['source']['dirty'], bool)
        assert isinstance(result['outputs']['source']['applied_patches'], list)
        assert result['outputs']['host']['docker'] is True
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    host = Host(tmp_path / 'inspect-host', resources={'workspace': {'kind': 'workspace', 'path': str(workspace)}},
                session_grants=['workspace.read', 'process.exec'])
    result = host.call(host.prepare(CCS / 'engine_inspector'), 'inspect', {'source': 'workspace', 'subpath': '..'})
    assert result['state'] == 'failed' and result['reason'] == 'INVALID_INPUT'
    assert result['outputs']['evidence']['observation_id']


def test_probe_timeout_removes_only_owned_container(setup, monkeypatch, tmp_path):
    from jiuwenswarm.factory.inspector import Inspector, InspectionError
    monkeypatch.setenv('FAKE_MODE', 'timeout')
    inspector = Inspector(tmp_path)
    with pytest.raises(InspectionError) as error:
        inspector.container('sha256:' + 'a' * 64, 'llama-completion', ['-n', '1'], timeout=.2)
    assert error.value.code == 'TIMEOUT'
    calls = [json.loads(row) for row in setup[1].read_text().splitlines()]
    run = calls[0]
    name = run[run.index('--name') + 1]
    assert name.startswith('factory-inspector-')
    assert calls[-1] == ['rm', '-f', name]
