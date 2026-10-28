"""Finite backend binding; no real RSI provisioning or container starts."""
import importlib.util
import json
import os
from pathlib import Path

import pytest

SOURCE = Path(__file__).parents[3] / 'deploy/m1/rsi_local.py'
spec = importlib.util.spec_from_file_location('rsi_native_binding_test', SOURCE)
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)


def manifest(native=True):
    value = {'schema': local.SCHEMA, 'root': '/var/lib/ai4r-rsi-unit', 'project': 'ai4r-rsi-unit',
        'images': {'app': 'sha256:' + 'a' * 64, 'rsi': 'sha256:' + 'b' * 64, 'worker': 'sha256:' + 'c' * 64},
        'key_id': 'rsi-unit', 'cgroup_host': '/sys/fs/cgroup/ai4r-rsi-host/jobs'}
    if native:
        value.update(schema=local.NATIVE_SCHEMA, docker_host=local.NATIVE_DOCKER_HOST)
    return value


@pytest.mark.parametrize('native', [True, False])
def test_endpoint_is_explicit_and_native_overlay_is_opt_in(native):
    command = local.compose(manifest(native))
    assert command[:4] == ['docker', '--host', local.NATIVE_DOCKER_HOST if native else local.DEFAULT_DOCKER_HOST, 'compose']
    assert (str(SOURCE.parent / 'compose.rsi.native-host.yaml') in command) == native


def test_unknown_endpoint_cannot_be_selected():
    value = manifest()
    value['docker_host'] = 'tcp://remote:2375'
    with pytest.raises(ValueError, match='endpoint'):
        local.compose(value)


def test_ambient_docker_context_and_host_are_removed(monkeypatch):
    for key in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'):
        monkeypatch.setenv(key, 'foreign')
    assert not any(key.startswith('DOCKER_') for key in local.environment(manifest()))


def test_native_backend_checks_actual_root_status_and_matching_delegation(monkeypatch):
    monkeypatch.setattr(local, 'require_root', lambda: None)
    calls = []
    def status():
        calls.append(True)
        return {'status': 'OBSERVED_NOT_QUALIFIED', 'socket': local.NATIVE_DOCKER_HOST,
                'cgroup_root': '/sys/fs/cgroup/ai4r-rsi-host/jobs'}
    monkeypatch.setattr(local, 'native_host_status', status)
    local.validate_backend(manifest())
    assert calls == [True]
    value = manifest()
    value['cgroup_host'] = '/sys/fs/cgroup/foreign'
    with pytest.raises(ValueError, match='delegation'):
        local.validate_backend(value)
    local.validate_backend(manifest(False))
    assert len(calls) == 2


@pytest.mark.parametrize('changes', [{'docker_host': 'unix:///foreign'}, {'extra': True}, {'schema': local.SCHEMA}])
def test_native_manifest_has_closed_versioned_fields(tmp_path, monkeypatch, changes):
    value = manifest()
    value.update(changes)
    path = tmp_path / 'local.json'
    path.write_text(json.dumps(value))
    monkeypatch.setattr(local, 'require_root', lambda: None)
    monkeypatch.setattr(local, 'safe_path', Path)
    monkeypatch.setattr(local, 'linux_storage', lambda path: None)
    monkeypatch.setattr(local, 'protected_file', lambda path: path)
    with pytest.raises(ValueError, match='finite local'):
        local.load_manifest(path)


@pytest.mark.parametrize('native', [True, False])
def test_both_finite_manifest_versions_load(tmp_path, monkeypatch, native):
    value = manifest(native)
    value['root'] = str(tmp_path)
    path = tmp_path / 'local.json'
    path.write_text(json.dumps(value))
    monkeypatch.setattr(local, 'require_root', lambda: None)
    monkeypatch.setattr(local, 'safe_path', Path)
    monkeypatch.setattr(local, 'linux_storage', lambda path: None)
    monkeypatch.setattr(local, 'protected_file', lambda path: path)
    monkeypatch.setattr(local, 'isolated_root', lambda path: None)
    monkeypatch.setattr(local, 'protected_ancestry', lambda path: None)
    assert local.load_manifest(path) == value


def test_native_inspection_refuses_dead_backend_before_role_or_compose_access(monkeypatch):
    def unavailable():
        raise ValueError('actual native host unavailable')
    monkeypatch.setattr(local, 'require_root', lambda: None)
    monkeypatch.setattr(local, 'native_host_status', unavailable)
    with pytest.raises(ValueError, match='native host unavailable'):
        local.inspect(manifest())
    with pytest.raises(ValueError, match='native host unavailable'):
        local.start(manifest())


def test_native_overlay_only_replaces_controller_network():
    text = (SOURCE.parent / 'compose.rsi.native-host.yaml').read_text()
    assert 'network_mode: host' in text
    assert 'networks: !reset []' in text
    assert 'networks: !reset {}' in text
    assert 'ports:' not in text and 'volumes:' not in text
    assert 'rsi-worker-broker:' not in text and 'rsi-custodian:' not in text
