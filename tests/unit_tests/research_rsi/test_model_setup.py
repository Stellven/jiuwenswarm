"""Isolated model setup contracts; never authenticate, start Docker, or invoke a model."""
import asyncio
from contextlib import nullcontext
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest


BASE = Path(__file__).resolve().parents[3] / 'deploy/m1'


def load(name):
    spec = importlib.util.spec_from_file_location('test_' + name, BASE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load('rsi_model')
client = load('rsi_model_client')
FRESH_IMAGE = 'sha256:' + 'f' * 64


@pytest.mark.parametrize('path', ['C:/model', '/mnt/c/model', '/tmp/../model', '//server/model',
    '/var/lib/ai4r/accounts/new', '/var/lib/ai4r-rsi/controller/accounts', '/root/fresh',
    '/home/person/fresh', '/opt/ai4r-local/model', '/tmp/.codex/new', '/tmp/model,readonly',
    '/tmp/model\n'])
def test_root_rejects_workstation_live_accounts_and_mount_injection(path):
    with pytest.raises(ValueError):
        host.model_root(path)


def test_linux_storage_rejects_disguised_drvfs_and_git(monkeypatch, tmp_path):
    # Native-root Linux tests exercise Git directly; no private files are made.
    if sys.platform != 'linux':
        pytest.skip('Linux mountinfo semantics')
    original = Path.read_text
    def mounts(path, *args, **kwargs):
        if str(path) == '/proc/self/mountinfo':
            return '1 0 0:1 / / rw - 9p drvfs rw\n'
        return original(path, *args, **kwargs)
    with monkeypatch.context() as change:
        change.setattr(Path, 'read_text', mounts)
        with pytest.raises(ValueError, match='native Linux'):
            host._paths.linux_storage(tmp_path / 'new')
    (tmp_path / '.git').mkdir()
    with pytest.raises(ValueError, match='Git'):
        host._paths.linux_storage(tmp_path / 'new')


def test_prepare_empty_exact_custody_and_refuses_reuse(tmp_path, monkeypatch):
    root = tmp_path / 'fresh-model'
    if sys.platform != 'linux' or os.geteuid() != 0:
        with pytest.raises(ValueError):
            host.prepare(str(root), image=FRESH_IMAGE)
        assert not root.exists()
        return
    # Deliberately put a sentinel in an ambient credential home. Preparing the
    # isolated model root must neither open nor copy any of these bytes.
    ambient = tmp_path / 'ambient-home'
    (ambient / '.codex').mkdir(parents=True)
    sentinel = ambient / '.codex/auth.json'
    sentinel.write_text('DO-NOT-COPY-EXISTING-CREDENTIALS')
    monkeypatch.setenv('HOME', str(ambient))
    monkeypatch.setenv('CODEX_HOME', str(ambient / '.codex'))
    result = host.prepare(str(root), image=FRESH_IMAGE)
    assert result['state'] == 'prepared'
    assert list((root / 'profile').iterdir()) == []
    assert sorted(p.name for p in root.iterdir()) == ['model.json', 'profile']
    for path, uid, mode in ((root, 0, 0o700), (root / 'profile', 12001, 0o700), (root / 'model.json', 0, 0o600)):
        meta = path.stat()
        assert (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) == (uid, uid, mode)
    assert host.load_manifest(str(root)) == host.manifest_for(root, image=FRESH_IMAGE, docker_host=host._paths.DEFAULT_DOCKER_HOST)
    before = (root / 'model.json').read_bytes()
    with pytest.raises(ValueError, match='fresh'):
        host.prepare(str(root), image=FRESH_IMAGE)
    assert (root / 'model.json').read_bytes() == before
    assert sentinel.read_text() == 'DO-NOT-COPY-EXISTING-CREDENTIALS'
    altered = json.loads(before)
    altered['account_root'] = '/root/.codex'
    (root / 'model.json').write_text(json.dumps(altered))
    with pytest.raises(ValueError, match='finite'):
        host.load_manifest(str(root))


def test_docker_command_is_bounded_fixed_image_and_exact_two_binds():
    value = host.manifest_for(Path(host.DEFAULT_ROOT))
    command = host.docker_command(value, 'login')
    assert command[:4] == ['docker', '--host', 'unix:///var/run/docker.sock', 'run']
    assert command[command.index('--pull') + 1] == 'never'
    assert '-it' in command and '--read-only' in command and '--rm' in command
    assert command[command.index('--cap-drop') + 1] == 'ALL'
    assert command[command.index('--user') + 1] == '12001:12001'
    assert command[command.index('--pids-limit') + 1] == '64'
    assert command[command.index('--memory') + 1] == '512m'
    assert command[command.index('--cpus') + 1] == '1'
    assert 'size=64m,uid=12001,gid=12001,mode=700' in command[command.index('--tmpfs') + 1]
    mounts = [command[i + 1] for i, item in enumerate(command) if item == '--mount']
    assert len(mounts) == 2
    assert mounts[0] == f"type=bind,src={value['profile']},dst={host.ACCOUNT_ROOT}"
    assert mounts[1].endswith(f',dst={host.HELPER},readonly')
    assert command[-3:] == [host.IMAGE, host.HELPER, 'login']
    assert '--privileged' not in command and '--volume' not in command
    status = host.docker_command(value, 'status')
    assert '-it' not in status and status[-1] == 'status'
    with pytest.raises(ValueError):
        host.docker_command(value, 'logout')
    altered = dict(value, image='latest')
    with pytest.raises(ValueError):
        host.docker_command(altered, 'login')


def test_environment_cannot_inherit_model_credentials_or_docker_endpoint():
    source = {'HOME': '/root', 'PATH': '/usr/bin', 'TERM': 'xterm',
              'OPENAI_API_KEY': 'secret', 'CODEX_HOME': '/root/.codex', 'AI4R_MODEL_ROOT': '/live',
              'COMPOSE_FILE': '/live/compose.yml', 'DOCKER_HOST': 'tcp://untrusted',
              'DOCKER_CONTEXT': 'live-context', 'DOCKER_CONFIG': '/foreign/config', 'XDG_RUNTIME_DIR': '/foreign/runtime',
              'PYTHONPATH': '/unreviewed', 'HTTP_PROXY': 'secret'}
    assert host.environment(source) == {'HOME': '/root', 'PATH': '/usr/bin', 'TERM': 'xterm'}


@pytest.mark.parametrize('native', [False, True])
def test_new_model_manifest_pins_reviewed_image_and_only_fixed_endpoint(native):
    endpoint = host._paths.NATIVE_DOCKER_HOST if native else host._paths.DEFAULT_DOCKER_HOST
    root = Path(host.DEFAULT_ROOT)
    value = host.manifest_for(root, image=FRESH_IMAGE, docker_host=endpoint)
    assert value['schema'] == host.SCHEMA_V2
    assert host.validate_manifest(value, root) == value
    command = host.docker_command(value, 'status')
    assert command[:4] == ['docker', '--host', endpoint, 'run']
    assert command[-3:] == [FRESH_IMAGE, host.HELPER, 'status']
    assert ('--network' in command) == native
    if native:
        assert command[command.index('--network') + 1] == 'host'
    for altered in (dict(value, docker_host='tcp://remote:2375'), dict(value, image='latest'), dict(value, extra=True)):
        with pytest.raises(ValueError):
            host.docker_command(altered, 'status')


def test_legacy_model_manifest_remains_exact_and_is_not_migrated():
    root = Path(host.DEFAULT_ROOT)
    original = host.manifest_for(root)
    before = json.dumps(original, sort_keys=True)
    assert original['schema'] == host.SCHEMA and original['image'] == host.IMAGE
    assert host.validate_manifest(original, root) is original
    assert host.docker_command(original, 'status')[-3:] == [host.IMAGE, host.HELPER, 'status']
    assert json.dumps(original, sort_keys=True) == before
    assert 'docker_host' not in original


def test_native_prepare_checks_actual_host_before_creating_any_profile(tmp_path, monkeypatch):
    root = tmp_path / 'fresh-native-model'
    monkeypatch.setattr(host._paths, 'require_root', lambda: None)
    monkeypatch.setattr(host, 'model_root', lambda value: root)
    monkeypatch.setattr(host._paths, 'native_host_status', lambda: {'status': 'unavailable'})
    with pytest.raises(ValueError, match='native Docker'):
        host.prepare(root, image=FRESH_IMAGE, native_host=True)
    assert not root.exists()


def test_fresh_cli_requires_explicit_image_and_later_commands_refuse_overrides(monkeypatch):
    monkeypatch.setattr(host, 'prepare', lambda *args, **kwargs: pytest.fail('No implicit prepare'))
    with pytest.raises(SystemExit) as error:
        host.main(['prepare'])
    assert error.value.code == 2
    for operation in ('login', 'status', 'summary'):
        with pytest.raises(SystemExit) as error:
            host.main([operation, '--image', FRESH_IMAGE])
        assert error.value.code == 2


def test_host_login_requires_terminal_before_any_process(monkeypatch):
    monkeypatch.setattr(host, 'load_manifest', lambda root: host.manifest_for(Path(host.DEFAULT_ROOT)))
    monkeypatch.setattr(host.sys, 'stdin', SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(host.subprocess, 'run', lambda *a, **k: pytest.fail('Must not start login'))
    with pytest.raises(ValueError, match='human terminal'):
        host.operate('login')


def test_host_status_discards_process_outputs_and_reads_only_sanitized_summary(monkeypatch):
    value = host.manifest_for(Path(host.DEFAULT_ROOT))
    expected = client.sanitized({'state': 'signed_out'}, None, {'models': []})
    monkeypatch.setattr(host, 'load_manifest', lambda root: value)
    monkeypatch.setattr(host, 'safe_summary', lambda root: expected)
    seen = []
    def run(command, **options):
        seen.append((command, options))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(host.subprocess, 'run', run)
    assert host.operate('status') == expected
    command, options = seen[0]
    assert command[-1] == 'status' and '-it' not in command
    assert options['stdout'] == subprocess.DEVNULL and options['stderr'] == subprocess.DEVNULL
    assert options['timeout'] == 120


def test_sanitization_excludes_every_private_field_and_rejects_forged_summaries():
    status = {'state': 'ready', 'plan': 'pro', 'email': 'person@example.com', 'auth_url': 'secret-url',
              'user_code': 'secret-code', 'tokens': {'access_token': 'secret-token'}}
    models = {'models': [{'id': 'gpt-5.4', 'name': 'secret-name'}, {'id': 'bad@email'}, {'id': 'bad\ncode'}, {'id': 'gpt-5.4'}]}
    summary = client.sanitized(status, 'a' * 64, models)
    assert summary == {'schema': client.SCHEMA, 'state': 'ready', 'plan': 'pro',
                       'account_fingerprint': 'a' * 64, 'models': ['gpt-5.4']}
    assert client.valid_summary(summary)
    assert 'secret' not in json.dumps(summary) and '@' not in json.dumps(summary)
    assert not client.valid_summary(dict(summary, email='person@example.com'))
    assert not client.valid_summary(dict(summary, state=['ready']))
    assert not client.valid_summary(dict(summary, models=['bad@email']))
    assert client.sanitized({'state': 'signed_out', 'plan': 'secret'}, 'person@example.com', models)['models'] == []


@pytest.mark.parametrize('state', ['ready', 'signed_out'])
def test_existing_status_uses_actual_service_api_without_login_turns_or_subprocess(monkeypatch, state):
    calls = []
    class Service:
        account_fingerprint = 'b' * 64
        def __init__(self, root):
            assert root == client.ACCOUNT_ROOT
            self.transport = SimpleNamespace(close=self.close)
        async def close(self): calls.append('close')
        async def status(self):
            calls.append('status')
            return {'state': state, 'plan': 'plus', 'email': 'private@example.com'}
        async def models(self):
            calls.append('models')
            return {'models': [{'id': 'public-model'}]}
    monkeypatch.setitem(sys.modules, 'jiuwenswarm.server.runtime.codex_subscription.service', SimpleNamespace(SubscriptionService=Service))
    monkeypatch.setattr(client.subprocess, 'run', lambda *a, **kw: pytest.fail('status cannot invoke login subprocess'))
    result = asyncio.run(client.existing_status())
    assert calls == (['status', 'models', 'close'] if state == 'ready' else ['status', 'close'])
    assert result['models'] == (['public-model'] if state == 'ready' else [])
    assert result['account_fingerprint'] == 'b' * 64


def test_config_is_generated_by_packaged_transport_start_and_close(monkeypatch):
    calls = []
    class Transport:
        def __init__(self, root): assert root == client.ACCOUNT_ROOT
        async def start(self): calls.append('start')
        async def close(self): calls.append('close')
    monkeypatch.setitem(sys.modules, 'jiuwenswarm.server.runtime.codex_subscription.transport', SimpleNamespace(AppServerTransport=Transport))
    asyncio.run(client.initialize_owned_config())
    assert calls == ['start', 'close']


def test_client_login_reuses_transport_then_packaged_cli_with_terminal_inherited(monkeypatch):
    calls = []
    async def initialize(): calls.append('owned-config')
    def sanitized_env(home):
        assert home == client.ACCOUNT_ROOT / 'codex-home'
        return {'CODEX_HOME': str(home)}
    def run(command, **options):
        calls.append('login')
        assert command == [str(Path('/packaged/codex')), 'login', '--device-auth']
        assert 'stdout' not in options and 'stderr' not in options and 'stdin' not in options
        assert options['env'] == {'CODEX_HOME': str(client.ACCOUNT_ROOT / 'codex-home')}
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(client, 'initialize_owned_config', initialize)
    monkeypatch.setattr(client, 'login_profile_lock', nullcontext)
    monkeypatch.setitem(sys.modules, 'codex_cli_bin', SimpleNamespace(bundled_codex_path=lambda: Path('/packaged/codex')))
    monkeypatch.setitem(sys.modules, 'jiuwenswarm.server.runtime.codex_subscription.transport', SimpleNamespace(child_environment=sanitized_env))
    for name in ('stdin', 'stdout', 'stderr'):
        monkeypatch.setattr(client.sys, name, SimpleNamespace(isatty=lambda: True))
    monkeypatch.setenv('JIUWENSWARM_M1_PROFILE', '1')
    monkeypatch.setattr(client.subprocess, 'run', run)
    client.login()
    assert calls == ['owned-config', 'login']


def test_overlay_exposes_profile_only_to_workbench():
    text = (BASE / 'compose.rsi.model.yaml').read_text()
    assert '  rsi-workbench:' in text
    assert 'rsi-custodian:' not in text and 'rsi-worker:' not in text
    assert 'target: /var/lib/ai4r-rsi/controller/accounts' in text
    assert 'create_host_path: false' in text
