"""Local provisioning controls; no real provider, app or operational key use."""
import argparse
import base64
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest


SOURCE = Path(__file__).resolve().parents[3] / 'deploy/m1/rsi_local.py'
spec = importlib.util.spec_from_file_location('rsi_local_under_test', SOURCE)
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)


@pytest.mark.parametrize('path', ['C:/keys', 'D:\\private', '/mnt/c/private', '/mnt/d/private',
                                   '/tmp/../private', '/tmp/private\n', '//host/private', 'relative'])
def test_private_paths_reject_workstation_and_noncanonical_paths(path):
    with pytest.raises(ValueError):
        local.safe_path(path)


def test_alias_to_windows_filesystem_is_not_private_linux_storage(monkeypatch):
    monkeypatch.setattr(local.sys, 'platform', 'linux')
    monkeypatch.setattr(local.os, 'geteuid', lambda: 0, raising=False)
    original = Path.read_text
    def mounts(path, *args, **kwargs):
        if path.as_posix() == '/proc/self/mountinfo':
            return '1 0 0:1 / / rw - 9p drvfs rw\n'
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', mounts)
    with pytest.raises(ValueError, match='native Linux'):
        local.linux_storage(Path('/innocent/private'))


@pytest.mark.parametrize('path', ['/opt/ai4r-local/rsi', '/var/lib/ai4r/rsi', '/root/.codex/rsi'])
def test_provisioning_refuses_live_app_and_existing_account_roots(path):
    with pytest.raises(ValueError, match='live app'):
        local.isolated_root(Path(path))


def template():
    pin = {'id': 'independently-captured', 'sha256': 'a' * 64}
    return {'schema_version': '1.0.0', 'cc': {'plan_source': 'static', 'plan_policy_ref': pin,
        'static_template_ref': pin, 'evaluation_profile_ref': None,
        'router': {'enabled': False, 'deadline_s': 30, 'profile_ref': None}},
        'rsi': {'custodian_key_id': None, 'custodian_public_key': None},
        'codex': {'route_id': 'dedicated-rsi'}, 'role_aliases': {}}


def arguments(tmp_path):
    source = tmp_path / 'operator-template.json'
    source.write_text(json.dumps(template()))
    return argparse.Namespace(root=str(tmp_path / 'protected-rsi'), project='ai4r-rsi-unit', key_id='rsi-dev-unit',
        operator_template=str(source), app_image='app@sha256:' + 'a' * 64,
        image='rsi@sha256:' + 'b' * 64, worker_image='worker@sha256:' + 'c' * 64, cgroup_host=None)


@pytest.mark.parametrize('image_style',['registry','local'])
def test_disposable_provisioning_or_windows_refusal(tmp_path,image_style):
    args = arguments(tmp_path)
    if image_style=='local':
        args.app_image='sha256:'+'a'*64
        args.image='sha256:'+'b'*64
        args.worker_image='sha256:'+'c'*64
    if sys.platform != 'linux' or os.geteuid() != 0:
        with pytest.raises(ValueError):
            local.prepare(args)
        assert not Path(args.root).exists()
        return
    caps = next(row.split()[1] for row in Path('/proc/self/status').read_text().splitlines() if row.startswith('CapEff:'))
    if not int(caps, 16) & 1:  # CAP_CHOWN; broad confinement tests drop it.
        with pytest.raises(PermissionError):
            local.prepare(args)
        assert not (Path(args.root) / 'custodian/signing-key').exists()
        return
    source_bytes = Path(args.operator_template).read_bytes()
    result = local.prepare(args)
    root = Path(args.root)
    assert result['status'] == 'BLOCKED'
    key = root / 'custodian/signing-key'
    assert len(key.read_bytes()) == 32
    assert (key.stat().st_uid, key.stat().st_gid, stat.S_IMODE(key.stat().st_mode)) == (12002, 12002, 0o600)
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    public = Ed25519PrivateKey.from_private_bytes(key.read_bytes()).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    operator = json.loads((root / 'config/operator.json').read_bytes())
    assert operator['rsi'] == {'custodian_key_id': args.key_id,
        'custodian_public_key': base64.urlsafe_b64encode(public).decode().rstrip('=')}
    assert Path(args.operator_template).read_bytes() == source_bytes
    assert not (root / 'config/jobs-service.json').exists()
    assert list((root/'security').iterdir())==[]
    assert ((root/'security').stat().st_uid,(root/'security').stat().st_gid,stat.S_IMODE((root/'security').stat().st_mode))==(0,13000,0o750)
    value = local.load_manifest(str(root / 'local.json'))
    plan = local.inspect(value)
    assert plan['status'] == 'BLOCKED'
    assert any('jobs-service.json' in reason for reason in plan['blockers'])
    assert any('cgroup' in reason for reason in plan['blockers'])
    before = key.read_bytes()
    with pytest.raises(ValueError, match='fresh'):
        local.prepare(args)
    assert key.read_bytes() == before


def manifest():
    return {'schema': local.SCHEMA, 'root': '/var/lib/ai4r-rsi-unit', 'project': 'ai4r-rsi-unit',
        'images': {'app': 'app@sha256:' + 'a' * 64, 'rsi': 'rsi@sha256:' + 'b' * 64,
                   'worker': 'worker@sha256:' + 'c' * 64}, 'key_id': 'rsi-dev',
        'cgroup_host': '/sys/fs/cgroup/rsi-unit'}


def test_plan_absent_authority_prevents_any_start(monkeypatch):
    monkeypatch.setattr(local, 'inspect', lambda _: {'status': 'BLOCKED', 'blockers': ['actual authority absent']})
    monkeypatch.setattr(local.subprocess, 'run', lambda *a, **k: pytest.fail('Docker must not run'))
    assert local.start(manifest())['status'] == 'BLOCKED'


def test_start_only_own_infrastructure_and_honestly_reports_doctor_block(monkeypatch):
    monkeypatch.setattr(local, 'inspect', lambda _: {'status': 'CONFIGURED', 'blockers': []})
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 2 if 'exec' in command else 0,
            stdout=b'{"status":"BLOCKED"}', stderr=b'PRIVATE DIAGNOSTIC MUST NOT ESCAPE')
    monkeypatch.setattr(local.subprocess, 'run', run)
    value = local.start(manifest())
    assert value['status'] == 'BLOCKED'
    assert value['daemons_requested'] is True and value['session_started'] is False
    assert len(calls) == 3
    assert calls[0][-2:] == ['config', '--quiet']
    assert calls[1][-3:] == ['rsi-worker-broker', 'rsi-custodian', 'rsi-workbench']
    assert '--no-build' in calls[1] and calls[1][calls[1].index('--pull') + 1] == 'never'
    assert calls[2][-2:] == ['doctor','--live']
    assert 'PRIVATE DIAGNOSTIC' not in json.dumps(value)
    assert all('compose.rsi-inbox.yaml' not in ' '.join(call) and 'session' not in call for call in calls)


def test_static_configured_result_is_not_operational_ready(monkeypatch):
    monkeypatch.setattr(local, 'inspect', lambda _: {'status': 'CONFIGURED', 'blockers': []})
    monkeypatch.setattr(local.subprocess, 'run', lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, stdout=b'{"status":"CONFIGURED"}'))
    assert local.start(manifest())['status'] == 'BLOCKED'


def test_ambient_app_root_and_inbox_env_cannot_substitute(monkeypatch):
    monkeypatch.setenv('AI4R_RSI_SIGNING_KEY', '/mnt/c/main-app-key')
    monkeypatch.setenv('AI4R_RSI_CONTROLLER_ROOT', '/opt/ai4r-local')
    monkeypatch.setenv('COMPOSE_FILE', '/opt/live-compose.yaml')
    monkeypatch.setenv('COMPOSE_PROJECT_NAME', 'live-app')
    monkeypatch.setenv('AI4R_RSI_SECURITY_ROOT','/foreign/qualification')
    env = local.environment(manifest())
    assert env['AI4R_RSI_SIGNING_KEY'] == str(Path('/var/lib/ai4r-rsi-unit/custodian/signing-key'))
    assert env['AI4R_RSI_CONTROLLER_ROOT'] == str(Path('/var/lib/ai4r-rsi-unit/controller'))
    assert env['AI4R_RSI_SECURITY_ROOT']==str(Path('/var/lib/ai4r-rsi-unit/security'))
    assert not any(k.startswith('COMPOSE_') for k in env)
    command = local.compose(manifest())
    assert command[command.index('--project-name') + 1] == 'ai4r-rsi-unit'
    assert '--env-file' in command and '/dev/null' in command
    assert str(SOURCE.parent/'compose.rsi.security.yaml') in command


def test_local_image_wrapper_copies_neutral_contracts_in_both_precedence_locations():
    source = (SOURCE.parent / 'Dockerfile.rsi-local').read_text()
    for target in ('production', 'worker-broker'):
        assert ' AS ' + target in source
    assert source.count('COPY jiuwenswarm/research_contracts/') == 4
    assert '/opt/ai4r/jiuwenswarm/research_contracts/' in source
    assert '/opt/venv/lib/python3.12/site-packages/jiuwenswarm/research_contracts/' in source
    ignores = (SOURCE.parent / 'Dockerfile.rsi-local.dockerignore').read_text()
    assert ignores.startswith('**\n') and '**/*.key' in ignores and '**/protected/**' in ignores


def test_explicit_validation_signer_start_preserves_the_producer_and_checks_public_pin(tmp_path,monkeypatch):
    if sys.platform!='linux' or os.geteuid()!=0:return
    caps=next(row.split()[1] for row in Path('/proc/self/status').read_text().splitlines() if row.startswith('CapEff:'))
    if not int(caps,16)&1:return
    args=arguments(tmp_path);local.prepare(args);root=Path(args.root)
    public=json.loads((root/'config/custodian-public.json').read_bytes());pin={'id':'unit:plan','sha256':'a'*64}
    config={'schema':'ai4r-rsi-validation-custody:1','plan_ref':pin,'scope_ref':pin,'attack_pins_ref':pin,
        **public,'rpc_session_id':'unit:signer','rpc_capability':'A'*43}
    local.write_new(root/'config/validation-custodian.json',local.encoded(config),gid=13000,mode=0o640)
    calls=[]
    def command(argv,**kwargs):
        calls.append(argv);return subprocess.CompletedProcess(argv,0,stdout=b'',stderr=b'')
    monkeypatch.setattr(local.subprocess,'run',command)
    result=local.start_validation_custodian(local.load_manifest(root/'local.json'))
    assert result['status']=='STARTED_NOT_QUALIFIED' and result['producer_restarted'] is False
    assert len(calls)==1 and calls[0][-1]=='rsi-validation-custodian' and '--no-deps' in calls[0]
    assert not any(role in calls[0] for role in ('rsi-worker-broker','rsi-workbench','rsi-custodian'))
    config['custodian_public_key']='B'*43
    (root/'config/validation-custodian.json').write_bytes(local.encoded(config))
    with pytest.raises(ValueError,match='pin differs'):local.start_validation_custodian(local.load_manifest(root/'local.json'))
    assert len(calls)==1
