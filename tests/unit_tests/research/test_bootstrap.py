"""Protected startup and actual instance-scoped native process ownership."""
import os
import uuid
from pathlib import Path

import pytest

from jiuwenswarm.research.bootstrap import (
    InstanceLease, NativeSessions, StartupBlocked, _directory, _private_json, _read_json, private_origin)


@pytest.mark.parametrize("origin,bind", [
    ("http://127.0.0.1:5173", "127.0.0.1"),
    ("http://192.168.1.4:5173", "192.168.1.4"),
    ("https://[fd00::1]:5173", "fd00::1")])
def test_only_private_published_origin(origin, bind):
    assert private_origin(origin, bind) == origin


@pytest.mark.parametrize("origin,bind", [
    ("http://127.0.0.1:5173", "0.0.0.0"),
    ("http://8.8.8.8:5173", "127.0.0.1"),
    ("http://127.0.0.1:5173/#secret", "127.0.0.1"),
    ("http://user:password@127.0.0.1:5173", "127.0.0.1"),
    ("http://127.0.0.1:5173/other", "127.0.0.1")])
def test_public_binding_or_origin_credential_is_refused(origin, bind):
    with pytest.raises(StartupBlocked):
        private_origin(origin, bind)


def test_exclusive_lease_does_not_replace_existing_owner(tmp_path):
    with InstanceLease(tmp_path / "lease"):
        with pytest.raises(StartupBlocked, match="INSTANCE_ALREADY_OWNED"):
            with InstanceLease(tmp_path / "lease"):
                pytest.fail("second launcher obtained ownership")
    with InstanceLease(tmp_path / "lease"):
        pass


def test_protected_record_refuses_links_and_broad_permissions(tmp_path):
    path = tmp_path / "private"
    _private_json(path, {"test": "value"}, uid=os.geteuid(), gid=os.getegid())
    assert _read_json(path, uid=os.geteuid()) == {"test": "value"}
    path.chmod(0o644)
    with pytest.raises(StartupBlocked):
        _read_json(path, uid=os.geteuid())
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(OSError):
        _read_json(link, uid=os.geteuid())
    with pytest.raises(StartupBlocked):
        _directory(link, uid=os.geteuid(), gid=os.getegid())


def test_native_roles_cannot_turn_into_arbitrary_commands(tmp_path):
    with pytest.raises(StartupBlocked):
        NativeSessions(tmp_path, "../../arbitrary", {})
    from jiuwenswarm.research.native_entry import main
    with pytest.raises(SystemExit, match="fixed native role"):
        main(["sh", "-c", "echo unsafe"])


def test_native_start_profile_import_does_not_load_legacy_initializer():
    import subprocess
    import sys
    result = subprocess.run([sys.executable, "-c", "import sys; import jiuwenswarm.start_services; assert 'jiuwenswarm.instance_manager' not in sys.modules"],
        env={**os.environ, "JIUWENSWARM_M1_PROFILE": "1"}, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr.decode()


@pytest.mark.parametrize('inbox,expected', [(None, [13100]), ('/var/lib/ai4r-rsi-inbox', [13100, 13000])])
def test_product_identity_gets_inbox_group_only_with_explicit_public_mount(monkeypatch, inbox, expected):
    from jiuwenswarm.research.bootstrap import _drop_identity
    changes = []
    monkeypatch.setattr(os, 'geteuid', lambda: 0)
    monkeypatch.setattr(os, 'setgroups', lambda value: changes.append(('groups', value)))
    monkeypatch.setattr(os, 'setgid', lambda value: changes.append(('gid', value)))
    monkeypatch.setattr(os, 'setuid', lambda value: changes.append(('uid', value)))
    if inbox is None: monkeypatch.delenv('JIUWENSWARM_M1_RSI_INBOX', raising=False)
    else: monkeypatch.setenv('JIUWENSWARM_M1_RSI_INBOX', inbox)
    _drop_identity()
    assert changes == [('groups', expected), ('gid', 10001), ('uid', 10001)]


def test_unavailable_or_untrusted_operator_file_never_validates_for_execution(tmp_path):
    import yaml
    from jiuwenswarm.research.bootstrap import _configuration_is_valid
    from tests.unit_tests.research.test_operator_config import valid_config
    path = tmp_path / 'operator.yaml'
    assert not _configuration_is_valid(path, lambda _: None)
    path.write_text(yaml.safe_dump(valid_config()), encoding='utf-8')
    path.chmod(0o644)
    assert _configuration_is_valid(path, lambda _: None)
    path.chmod(0o666)
    assert not _configuration_is_valid(path, lambda _: None)
    path.chmod(0o644)
    link = tmp_path / 'operator-link.yaml'; link.symlink_to(path)
    assert not _configuration_is_valid(link, lambda _: None)
    path.write_text('credential-canary: [malformed', encoding='utf-8')
    assert not _configuration_is_valid(path, lambda _: None)
