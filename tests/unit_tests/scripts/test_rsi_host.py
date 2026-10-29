"""Host prep safety boundaries; no package, daemon, mount or cgroup mutations."""
import importlib.util
import io
from pathlib import Path
import tarfile

import pytest


spec = importlib.util.spec_from_file_location('rsi_host', Path(__file__).parents[3] / 'deploy/m1/rsi_host.py')
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


def payload(entries):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w') as archive:
        for name, kind, value in entries:
            member = tarfile.TarInfo(name)
            if kind == 'file':
                member.size = len(value)
                member.mode = 0o6755
                archive.addfile(member, io.BytesIO(value))
            else:
                member.type = tarfile.SYMTYPE
                member.linkname = value
                archive.addfile(member)
    return out.getvalue()


@pytest.mark.parametrize('name', ['../../escape', '/etc/shadow', './usr/../../escape', 'usr\\escape'])
def test_archive_traversal_refused(tmp_path, name):
    with pytest.raises(ValueError, match='UNSAFE_DEB_ARCHIVE_PATH'):
        host.extract_payload(payload([(name, 'file', b'bad')]), tmp_path)


@pytest.mark.parametrize('target', ['/etc/shadow', '../../../escape'])
def test_archive_link_escape_refused(tmp_path, target):
    with pytest.raises(ValueError, match='DEB_LINK_ESCAPE'):
        host.extract_payload(payload([('usr/bin/link', 'link', target)]), tmp_path)


def test_archive_file_mode_and_payload_collision(tmp_path):
    host.extract_payload(payload([('usr/bin/tool', 'file', b'one')]), tmp_path)
    assert (tmp_path / 'usr/bin/tool').read_bytes() == b'one'
    assert (tmp_path / 'usr/bin/tool').stat().st_mode & 0o7777 == 0o755
    with pytest.raises(ValueError, match='DEB_PAYLOAD_COLLISION'):
        host.extract_payload(payload([('usr/bin/tool', 'file', b'two')]), tmp_path)


def test_symlink_parent_refused(tmp_path):
    (tmp_path / 'usr').mkdir()
    (tmp_path / 'usr/real').mkdir()
    with pytest.raises(ValueError, match='DEB_SYMLINK_PARENT'):
        host.extract_payload(payload([('usr/link', 'link', 'real'), ('usr/link/escape', 'file', b'bad')]), tmp_path)


def test_service_and_docker_arguments_are_private(monkeypatch):
    monkeypatch.setattr(host, 'executable', lambda name: '/opt/ai4r-rsi-host/payload/usr/bin/' + name)
    command = host.docker_command()
    assert '--host=unix:///run/ai4r-rsi-docker/docker.sock' in command
    assert '--bridge=none' in command
    assert '--iptables=false' in command
    assert '--data-root=/var/lib/ai4r-rsi-docker/docker' in command
    assert '--config-file=/opt/ai4r-rsi-host/daemon.json' in command
    service = host.service_command('docker', command, 2048, 256)
    assert '--unit=ai4r-rsi-docker' in service
    assert '--property=MemoryMax=2147483648' in service
    assert '--property=TasksMax=256' in service
    assert all('DOCKER_HOST' not in value for value in service)


@pytest.mark.parametrize('memory,pids', [(0, 256), (65537, 256), (2048, 0), (2048, 32769)])
def test_unbounded_limits_refused(memory, pids):
    with pytest.raises(ValueError, match='FINITE_EXPLICIT_HOST_LIMITS_REQUIRED'):
        host.bounds(memory, pids)


def test_observer_is_private_and_arguments_are_not_shell_interpolated():
    command = host.observer_command(['/usr/bin/python3', '/opt/observe.py', '; touch /bad'])
    assert command[:4] == ['/usr/bin/unshare', '--mount', '--propagation', 'private']
    assert 'exec "$@"' in command[6]
    assert command[-1] == '; touch /bad'
    with pytest.raises(ValueError, match='ABSOLUTE_TRUSTED_OBSERVER_REQUIRED'):
        host.observer_command(['python3'])


def test_apt_authentication_cannot_be_disabled():
    options = host.apt_options()
    assert 'APT::Get::AllowUnauthenticated=false' in options
    assert 'Acquire::AllowInsecureRepositories=false' in options
    assert 'Dir::Etc::sourceparts=-' in options


@pytest.mark.parametrize('seconds', [0, -1, 7201, None])
def test_hold_requires_finite_explicit_lifetime(seconds):
    with pytest.raises(ValueError, match='FINITE_HOST_HOLD_SECONDS_REQUIRED'):
        host.hold(seconds)
