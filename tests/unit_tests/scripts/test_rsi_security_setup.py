"""Public bootstrap refusal/phase boundaries; never a security case or approval."""
import importlib.util
import json
import os
from pathlib import Path

import pytest


SOURCE = Path(__file__).resolve().parents[3] / 'deploy/m1/rsi_security_setup.py'
spec = importlib.util.spec_from_file_location('security_setup_controls', SOURCE)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def manifest(root):
    return {'schema': setup.local.NATIVE_SCHEMA, 'root': str(root), 'project': 'ai4r-rsi-control',
        'images': {name: 'sha256:' + 'a' * 64 for name in ('app', 'rsi', 'worker')},
        'key_id': 'control-only', 'cgroup_host': str(setup.host.CG / 'jobs'), 'docker_host': setup.host.SOCKET}


def pin(number):
    return {'id': 'controlled-negative:' + str(number), 'sha256': f'{number:064x}'}


def test_draft_never_occupies_final_campaign_or_standard_configuration(tmp_path):
    value = manifest(tmp_path)
    draft = setup.phase_paths(value, 'draft')
    final = setup.phase_paths(value, 'final')
    for name in setup.PHASE_ROOTS:
        assert draft[name] == tmp_path / 'security-phases/draft' / name
        assert final[name] == tmp_path / name
        assert not draft[name].is_relative_to(final[name])
    assert final['broker-config'] == tmp_path / 'config/broker-service.json'
    assert final['custodian-config'] == tmp_path / 'config/validation-custodian.json'
    assert draft['broker-config'] != final['broker-config']
    with pytest.raises(ValueError): setup.phase_paths(value, 'replacement')


@pytest.mark.parametrize('packet', [{}, {'schema': setup.INPUT_SCHEMA, 'runtime': {}, 'additional_profile_refs': [], 'approved': True}])
def test_incomplete_or_approval_shaped_input_is_refused_without_original_reads(tmp_path, monkeypatch, packet):
    monkeypatch.setattr(setup, '_original', lambda *args: pytest.fail('No original may be read for invalid envelope'))
    with pytest.raises(ValueError): setup.runtime_input(packet, tmp_path, {})


def test_case_sessions_must_be_distinct_before_any_public_original_is_read(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, '_original', lambda *args: pytest.fail('Must reject duplicate sessions first'))
    runtime = {'schema': 'ai4r-rsi-security-runtime-config:1',
        'campaign_root': '/var/lib/ai4r-rsi-validation-campaign',
        'custodian_key_id': 'control-only', 'custodian_public_key': 'a' * 43,
        'case_bindings': {case: {'session_ref': pin(1), 'worker_profile_ref': pin(index + 10)}
                          for index, case in enumerate(setup.CASES)},
        'environment_ref': pin(2), 'originals': []}
    with pytest.raises(ValueError):
        setup.runtime_input({'schema': setup.INPUT_SCHEMA, 'runtime': runtime, 'additional_profile_refs': []}, tmp_path, {})


def test_launch_plan_never_starts_owner_or_leaks_ambient_credentials(tmp_path, monkeypatch):
    value = manifest(tmp_path)
    paths = setup.phase_paths(value, 'draft')
    paths['validation-campaign'].mkdir(parents=True)
    monkeypatch.setattr(setup, 'load', lambda _: value)
    monkeypatch.setattr(setup, 'protected_json', lambda _: {'controlled': 'metadata'} )
    monkeypatch.setenv('OPENAI_API_KEY', 'must-never-appear')
    monkeypatch.setenv('DOCKER_CONTEXT', 'must-not-select-context')
    monkeypatch.setattr(setup.host, 'run', lambda *args, **kwargs: pytest.fail('Plan must not invoke Docker'))
    result = setup.launch_plan(manifest='controlled-manifest', phase='draft')
    assert result['command'][:3] == ['/usr/bin/docker', '--host', setup.host.SOCKET]
    assert result['command'][-7:] == ['up', '--detach', '--no-deps', '--no-build', '--pull', 'never', 'rsi-worker-broker']
    assert result['environment']['AI4R_RSI_WORKER_CONFIG'] == str(paths['broker-config'])
    assert 'must-never-appear' not in json.dumps(result) and 'must-not-select-context' not in json.dumps(result)
    assert all(name.startswith('AI4R_') for name in result['environment'])
    assert not any(tmp_path.rglob('approval.json'))


def test_existing_approval_or_campaign_prevents_new_launch_plan(tmp_path, monkeypatch):
    value = manifest(tmp_path); paths = setup.phase_paths(value, 'draft')
    paths['validation-control'].mkdir(parents=True)
    paths['validation-campaign'].mkdir(parents=True)
    monkeypatch.setattr(setup, 'load', lambda _: value)
    monkeypatch.setattr(setup, 'protected_json', lambda _: {})
    approval = paths['validation-control'] / 'approval.json'; approval.write_text('{}')
    with pytest.raises(ValueError, match='ORIGINAL_OWNER'): setup.launch_plan(manifest='controlled')
    approval.unlink(); (paths['validation-campaign'] / 'original-state').write_text('retain')
    with pytest.raises(ValueError, match='ORIGINAL_OWNER'): setup.launch_plan(manifest='controlled')


def test_signer_preparation_never_adopts_existing_state_or_an_already_approved_worker(tmp_path, monkeypatch):
    value = manifest(tmp_path); paths = setup.phase_paths(value, 'draft')
    paths['custodian-config'].parent.mkdir(parents=True)
    paths['validation-control'].mkdir(parents=True)
    monkeypatch.setattr(setup, 'load', lambda _: value)
    monkeypatch.setattr(setup, 'protected_json', lambda *args, **kwargs: pytest.fail('No key pin or metadata read before state refusal'))
    monkeypatch.setattr(setup.local, 'write_new', lambda *args, **kwargs: pytest.fail('No config/approval may be written'))
    paths['custodian-config'].write_text('retain original finite signer config')
    with pytest.raises(ValueError, match='ORIGINAL_OWNER'):
        setup.prepare_signer(pin(1), manifest='controlled')
    paths['custodian-config'].unlink()
    (paths['validation-control'] / 'approval.json').write_text('{}')
    with pytest.raises(ValueError, match='APPROVAL_ALREADY_PRESENT'):
        setup.prepare_signer(pin(1), manifest='controlled')


@pytest.mark.skipif(os.name != 'posix', reason='Native Linux absolute observer program paths')
def test_observation_plan_uses_existing_private_namespace_helper_and_only_fixed_entrypoint(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, 'load', lambda _: manifest(tmp_path))
    result = setup.observation_plan('a' * 64, pin(1), manifest='controlled')
    command = result['command']
    assert command[:4] == ['/usr/bin/python3', str(setup.HERE / 'rsi_host.py'), 'observe', '/usr/bin/python3']
    assert 'observe-current' in command and command[-2] == '--scope-ref'
    assert '/usr/bin/python3' in command
    assert command[4:7] == ['-I', '-B', '-c']
    assert 'sys.path[:0]=[str(root),str(deps)]' in command[7]
    assert 'observer_source_digest(root)' in command[7]
    assert 'PYTHONPATH=' not in command[7]
    assert '/opt/ai4r-rsi-host-codex/site-packages' in command[7]
    assert 'docker context' not in ' '.join(command)
    with pytest.raises(ValueError): setup.observation_plan('arbitrary-container-name', pin(1), manifest='controlled')


def test_duplicate_json_and_nonfinite_input_never_become_config():
    for raw in ('{"case":1,"case":2}', '{"value":NaN}'):
        with pytest.raises(ValueError): setup._json(raw)


@pytest.mark.skipif(os.name!='posix' or not hasattr(os,'geteuid') or os.geteuid()!=0,
                    reason='Actual Linux Root mountpoint custody')
def test_nested_readonly_parent_mountpoint_is_created_empty_without_state_changes(tmp_path):
    control=tmp_path/'validation-control';control.mkdir(mode=0o750)
    original=control/'runtime.json';original.write_bytes(b'original protected metadata')
    target=setup.prepare_validation_mountpoint(control)
    assert target==control/'public' and list(target.iterdir())==[]
    assert target.stat().st_uid==target.stat().st_gid==0
    assert target.stat().st_mode & 0o777==0o755
    assert original.read_bytes()==b'original protected metadata'
    assert setup.prepare_validation_mountpoint(control)==target


@pytest.mark.skipif(os.name!='posix' or not hasattr(os,'geteuid') or os.geteuid()!=0,
                    reason='Actual Linux Root mountpoint custody')
@pytest.mark.parametrize('fault',['symlink','file','populated','writable','parent-writable'])
def test_mountpoint_never_adopts_substituted_or_writable_state(tmp_path,fault):
    control=tmp_path/'validation-control';control.mkdir(mode=0o750)
    target=control/'public'
    if fault=='symlink':target.symlink_to(tmp_path,target_is_directory=True)
    elif fault=='file':target.write_bytes(b'retain')
    else:
        target.mkdir(mode=0o755)
        if fault=='populated':(target/'retain').write_bytes(b'original')
        elif fault=='writable':target.chmod(0o777)
        else:control.chmod(0o777)
    with pytest.raises(ValueError):setup.prepare_validation_mountpoint(control)
