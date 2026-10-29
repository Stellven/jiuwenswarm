"""Saved provider selection; no infrastructure, account reads, or network calls."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import argparse
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).parents[3] / 'deploy/m1/rsi_local.py'
spec = importlib.util.spec_from_file_location('rsi_model_binding_test', SOURCE)
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)


def manifest(backend='spark'):
    return {'schema': local.MODEL_SCHEMA, 'root': '/var/lib/ai4r-rsi-unit',
            'project': 'ai4r-rsi-unit', 'images': {key: 'sha256:' + char * 64
                for key, char in [('app', 'a'), ('rsi', 'b'), ('worker', 'c')]},
            'key_id': 'rsi-unit', 'cgroup_host': '/sys/fs/cgroup/ai4r-rsi-host/jobs',
            'docker_host': local.NATIVE_DOCKER_HOST, 'model_backend': backend,
            'model_account_root': local.MODEL_BACKENDS[backend]['account_root']}


@pytest.mark.parametrize('backend', ['codex', 'spark', 'host-codex'])
def test_saved_choice_roundtrips_and_selects_one_final_overlay(tmp_path, monkeypatch, backend):
    value = manifest(backend)
    value['root'] = str(tmp_path)
    path = tmp_path / 'local.json'
    path.write_text(json.dumps(value))
    monkeypatch.setattr(local, 'require_root', lambda: None)
    monkeypatch.setattr(local, 'safe_path', Path)
    monkeypatch.setattr(local, 'linux_storage', lambda _: None)
    monkeypatch.setattr(local, 'protected_file', lambda path: path)
    monkeypatch.setattr(local, 'isolated_root', lambda _: None)
    monkeypatch.setattr(local, 'protected_ancestry', lambda _: None)
    saved = local.load_manifest(path)
    assert saved == value
    command = local.compose(saved)
    assert command[:3] == ['docker', '--host', local.NATIVE_DOCKER_HOST]
    overlays = [Path(argument).name for argument in command if argument.endswith('.yaml')]
    assert overlays[-2:] == ['compose.rsi.native-host.yaml', local.MODEL_BACKENDS[backend]['overlay']]
    assert len(set(overlays) & {'compose.rsi.model.yaml', 'compose.rsi.spark.yaml', 'compose.rsi.host-codex.yaml'}) == 1


@pytest.mark.parametrize('backend', ['codex', 'spark', 'host-codex'])
def test_ambient_profile_cannot_mix_with_saved_choice(monkeypatch, backend):
    for variable in ('AI4R_RSI_MODEL_ACCOUNT_ROOT', 'AI4R_RSI_SPARK_ACCOUNT_ROOT', 'AI4R_RSI_HOST_CODEX_ACCOUNT_ROOT'):
        monkeypatch.setenv(variable, '/foreign/main-app-account')
    value = manifest(backend)
    env = local.environment(value)
    binding = local.MODEL_BACKENDS[backend]
    assert env[binding['environment']] == binding['account_root']
    assert all(item['environment'] not in env for name, item in local.MODEL_BACKENDS.items() if name != backend)


@pytest.mark.parametrize('change', [
    {'model_backend': 'foreign'}, {'model_account_root': '/root/.codex'},
    {'model_account_root': '/var/lib/ai4r-rsi-model/profile'}, {'extra': True},
    {'docker_host': local.DEFAULT_DOCKER_HOST}, {'model_backend': ['spark']},
])
def test_closed_model_configuration_refuses_substitution(change):
    value = manifest()
    value.update(change)
    with pytest.raises(ValueError):
        local.compose(value)
    with pytest.raises(ValueError):
        local.environment(value)


@pytest.mark.parametrize('schema', [local.SCHEMA, local.NATIVE_SCHEMA])
def test_legacy_manifest_preserves_no_model_overlay_and_no_account_env(monkeypatch, schema):
    value = manifest()
    value['schema'] = schema
    value.pop('model_backend')
    value.pop('model_account_root')
    if schema == local.SCHEMA:
        value.pop('docker_host')
    monkeypatch.setenv('AI4R_RSI_MODEL_ACCOUNT_ROOT', '/foreign')
    monkeypatch.setenv('AI4R_RSI_SPARK_ACCOUNT_ROOT', '/foreign')
    assert not any(Path(item).name in {'compose.rsi.model.yaml', 'compose.rsi.spark.yaml', 'compose.rsi.host-codex.yaml'}
                   for item in local.compose(value))
    env = local.environment(value)
    assert 'AI4R_RSI_MODEL_ACCOUNT_ROOT' not in env
    assert 'AI4R_RSI_SPARK_ACCOUNT_ROOT' not in env


def test_cloud_checks_fixed_protected_manifest_without_status_or_credentials(monkeypatch):
    calls = []
    helper = SimpleNamespace(load_manifest=lambda root: calls.append(root) or
                             {'profile': local.MODEL_BACKENDS['codex']['account_root']})
    monkeypatch.setattr(local, 'require_root', lambda: None)
    monkeypatch.setattr(local, 'model_helper', lambda name: helper if name == 'codex' else pytest.fail('mixed backend'))
    local.validate_model_backend(manifest('codex'))
    assert calls == ['/var/lib/ai4r-rsi-model']


def test_host_checks_dedicated_root_metadata_without_native_account_reads(monkeypatch):
    calls = []
    helper = SimpleNamespace(load=lambda: calls.append('protected-profile') or {'catalog': {'models': [
        {'model_name': 'gpt-6.1-sol', 'reasoning_effort': 'medium'}]}})
    monkeypatch.setattr(local, 'require_root', lambda: None)
    monkeypatch.setattr(local, 'model_helper', lambda backend: helper if backend == 'host-codex' else pytest.fail('mixed backend'))
    monkeypatch.setattr(local, 'safe_path', Path)
    monkeypatch.setattr(local, 'linux_storage', lambda _: None)
    monkeypatch.setattr(local, 'protected_ancestry', lambda _: None)
    monkeypatch.setattr(Path, 'lstat', lambda _: SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=12001, st_gid=12001))
    monkeypatch.setattr(os.path, 'lexists', lambda _: False)
    local.validate_model_backend(manifest('host-codex'))
    assert calls == ['protected-profile']


@pytest.mark.parametrize('has_auth', [False, True])
def test_spark_checks_custody_and_auth_filename_without_reading_auth(monkeypatch, has_auth):
    calls = []
    helper = SimpleNamespace(load_profile=lambda: calls.append('profile') or {'model': 'Qwen3.8-27B-NVFP4'})
    monkeypatch.setattr(local, 'require_root', lambda: None)
    monkeypatch.setattr(local, 'model_helper', lambda name: helper if name == 'spark' else pytest.fail('mixed backend'))
    monkeypatch.setattr(local, 'safe_path', Path)
    monkeypatch.setattr(local, 'linux_storage', lambda _: None)
    monkeypatch.setattr(local, 'protected_ancestry', lambda _: None)
    monkeypatch.setattr(Path, 'lstat', lambda _: SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=12001, st_gid=12001))
    monkeypatch.setattr(local.os.path, 'lexists', lambda path: has_auth)
    monkeypatch.setattr(Path, 'read_bytes', lambda _: pytest.fail('profile credential contents must not be read'))
    if has_auth:
        with pytest.raises(ValueError, match='authentication'):
            local.validate_model_backend(manifest())
    else:
        local.validate_model_backend(manifest())
    assert calls == ['profile']


def test_dead_selected_model_prevents_role_inspection_and_start(monkeypatch):
    monkeypatch.setattr(local, 'validate_backend', lambda _: None)
    def unavailable(_):
        raise ValueError('selected protected model is unavailable')
    monkeypatch.setattr(local, 'validate_model_backend', unavailable)
    monkeypatch.setattr(local.subprocess, 'run', lambda *a, **k: pytest.fail('no compose start'))
    with pytest.raises(ValueError, match='selected protected model'):
        local.start(manifest())


@pytest.mark.parametrize('backend', ['codex', 'spark', 'host-codex'])
def test_prepare_publishes_explicit_choice_last_after_preflight(tmp_path, monkeypatch, backend):
    pin = {'id': 'unit:captured', 'sha256': 'a' * 64}
    template = {'schema_version': '1.0.0', 'cc': {'plan_source': 'static', 'plan_policy_ref': pin,
        'static_template_ref': pin, 'evaluation_profile_ref': None,
        'router': {'enabled': False, 'deadline_s': 30, 'profile_ref': None}},
        'rsi': {'custodian_key_id': None, 'custodian_public_key': None},
        'codex': {'route_id': 'dedicated-rsi'}, 'role_aliases': {}}
    source = tmp_path / 'operator.json'
    source.write_text(json.dumps(template))
    root = tmp_path / 'deployment'
    value = manifest(backend)
    args = argparse.Namespace(root=str(root), project=value['project'], key_id=value['key_id'],
        app_image=value['images']['app'], image=value['images']['rsi'], worker_image=value['images']['worker'],
        cgroup_host=None, native_host=True, model_backend=backend, operator_template=str(source))
    monkeypatch.setattr(local, 'safe_path', Path)
    for name in ('require_root',):
        monkeypatch.setattr(local, name, lambda: None)
    for name in ('linux_storage', 'protected_ancestry', 'isolated_root', 'validate_backend'):
        monkeypatch.setattr(local, name, lambda _: None)
    monkeypatch.setattr(local.os, 'chown', lambda *args: None, raising=False)
    monkeypatch.setattr(local, 'native_host_status', lambda: {'cgroup_root': value['cgroup_host']})
    calls = []
    def preflight(selected):
        assert not root.exists()
        calls.append(selected)
    monkeypatch.setattr(local, 'validate_model_backend', preflight)
    writes = []
    def write(path, data, **kwargs):
        writes.append(path.name)
        path.write_bytes(data)
    monkeypatch.setattr(local, 'write_new', write)
    local.prepare(args)
    saved = json.loads((root / 'local.json').read_bytes())
    assert saved['schema'] == local.MODEL_SCHEMA
    assert saved['model_backend'] == backend
    assert saved['model_account_root'] == local.MODEL_BACKENDS[backend]['account_root']
    assert calls == [saved]
    assert writes[-1] == 'local.json'
