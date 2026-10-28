"""No daemon, mounts, cgroups, credentials, or model calls in these tests."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('restore', Path(__file__).parents[3] /
                                             'deploy/m1/rsi_host_boot_restore.py')
restore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore)


def test_no_restart_policy_and_stopped_state_are_required():
    config = {'State': {'Running': False, 'Restarting': False, 'Pid': 0}}
    restore.stopped_configuration(config, {'RestartPolicy': {'Name': 'no', 'MaximumRetryCount': 0}})
    for name in ('always', 'unless-stopped', 'on-failure', ''):
        with pytest.raises(ValueError, match='AUTOMATIC_CONTAINER_RESTART_REFUSED'):
            restore.stopped_configuration(config, {'RestartPolicy': {'Name': name, 'MaximumRetryCount': 0}})
    for field, value in [('Running', True), ('Restarting', True), ('Pid', 21)]:
        changed = {'State': dict(config['State'], **{field: value})}
        with pytest.raises(ValueError, match='RETAINED_CONTAINER_NOT_STOPPED'):
            restore.stopped_configuration(changed, {'RestartPolicy': {'Name': 'no', 'MaximumRetryCount': 0}})


def test_incarnation_key_changes_when_pid1_changes_on_same_kernel():
    first = {'kernel_boot_id': 'same', 'pid1_start_ticks': '100',
             'pid1_mount_namespace': 'mnt:[1]', 'pid1_pid_namespace': 'pid:[1]'}
    assert restore.host.incarnation_key(first) != restore.host.incarnation_key(dict(first, pid1_start_ticks='200'))
    assert restore.host.incarnation_key(first) != restore.host.incarnation_key(dict(first, pid1_pid_namespace='pid:[2]'))


def test_wrong_approval_or_changed_state_has_no_claim(tmp_path, monkeypatch):
    path = tmp_path / 'plan.json'
    raw = restore.encoded({'previous_boot_id': 'old'})
    path.write_bytes(raw)
    monkeypatch.setattr(restore, 'plan_path', lambda *args: path)
    monkeypatch.setattr(restore.host, 'secure', lambda path: None)
    with pytest.raises(ValueError, match='PLAN_APPROVAL_MISMATCH'):
        restore.apply(path, '0' * 64)
    monkeypatch.setattr(restore, 'observe', lambda old: {'previous_boot_id': 'different'})
    with pytest.raises(ValueError, match='PLAN_STATE_CHANGED'):
        restore.apply(path, restore.sha(raw))
    assert not path.with_suffix('.claim.json').exists()


def test_existing_claim_blocks_effects(tmp_path, monkeypatch):
    path = tmp_path / 'plan.json'
    plan = {'previous_boot_id': 'old', 'current_boot_id': 'new', 'incarnation_key': 'new', 'incarnation': {}}
    raw = restore.encoded(plan)
    path.write_bytes(raw)
    (tmp_path / 'config').mkdir()
    claim = tmp_path / 'config/host-boot-restoration.new.claim.json'
    claim.write_bytes(b'original')
    monkeypatch.setattr(restore, 'ROOT', tmp_path)
    monkeypatch.setattr(restore, 'plan_path', lambda *args: path)
    monkeypatch.setattr(restore.host, 'secure', lambda path: None)
    monkeypatch.setattr(restore, 'observe', lambda old: plan)
    with pytest.raises(FileExistsError):
        restore.apply(path, restore.sha(raw))
    assert claim.read_bytes() == b'original'


def test_private_client_no_shell_interpolation(monkeypatch):
    monkeypatch.setattr(restore.host, 'executable', lambda name: '/opt/verified/' + name)
    command = restore.namespace_command(['/usr/bin/python3', '; touch /bad'], '/opt/verified/compose')
    assert command[:4] == ['/usr/bin/unshare', '--mount', '--propagation', 'private']
    assert command[-1] == '; touch /bad'
    assert command[-4] == '/opt/verified/docker'
    assert command[-3] == '/opt/verified/compose'
    assert 'exec "$@"' in command[6]
    with pytest.raises(ValueError, match='ABSOLUTE_COMMAND_REQUIRED'):
        restore.namespace_command(['python'], '/opt/verified/compose')


def test_wrong_original_client_or_link_target_refused(tmp_path, monkeypatch):
    target = tmp_path / 'docker'
    target.write_bytes(b'ambient-client')
    monkeypatch.setattr(restore, 'CLIENT', target)
    monkeypatch.setattr(restore.host, 'verified', lambda: {})
    with pytest.raises(ValueError, match='ORIGINAL_CLIENT_LINK_REQUIRED'):
        restore.client(['/usr/bin/true'])
    target.unlink()
    target.symlink_to(tmp_path / 'other')
    with pytest.raises(ValueError, match='ORIGINAL_CLIENT_LINK_REQUIRED'):
        restore.client(['/usr/bin/true'])


def test_new_record_never_overwrites(tmp_path):
    path = tmp_path / 'receipt.json'
    restore.new(path, b'first')
    with pytest.raises(FileExistsError):
        restore.new(path, b'second')
    assert path.read_bytes() == b'first'


def test_boot_receipt_chain_accepts_new_inode_preserves_original(tmp_path, monkeypatch):
    host = restore.host
    real_path = Path
    boot = '11111111-1111-1111-1111-111111111111'
    boot_file = tmp_path / 'boot-id'
    boot_file.write_text(boot)
    custody = tmp_path / 'custody'
    identity = {'kernel_boot_id': boot, 'pid1_start_ticks': '1',
                'pid1_mount_namespace': 'mnt:[1]', 'pid1_pid_namespace': 'pid:[1]'}
    key = host.incarnation_key(identity)
    monkeypatch.setattr(host, 'incarnation', lambda: identity)
    plan = custody / key / ('plan.' + restore.sha(b'original-plan') + '.json')
    plan.parent.mkdir(parents=True)
    plan.write_bytes(b'original-plan')
    complete = plan.with_suffix('.complete.json')
    complete.write_bytes(restore.encoded({'cgroup_inode': 99}))
    original = tmp_path / 'started.json'
    original.write_bytes(restore.encoded({'cgroup_inode': 42}))
    successor = tmp_path / ('started.instance.' + key + '.json')
    value = {'schema': 'ai4r-rsi-host-restored-bounds:1', 'boot_id': boot,
             'incarnation': identity,
             'original_started_sha256': restore.sha(original.read_bytes()),
             'plan_path': str(plan), 'plan_sha256': restore.sha(plan.read_bytes()),
             'completion_sha256': restore.sha(complete.read_bytes()), 'cgroup_inode': 99}
    successor.write_bytes(restore.encoded(value))
    def mapped_path(*parts):
        text = str(parts[0])
        if text == '/proc/sys/kernel/random/boot_id':
            return boot_file
        if text == '/var/lib/ai4r-rsi-codex/config/host-boot-restoration':
            return custody
        return real_path(*parts)
    monkeypatch.setattr(host, 'ROOT', tmp_path)
    monkeypatch.setattr(host, 'Path', mapped_path)
    monkeypatch.setattr(host, 'secure', lambda path: None)
    assert host.active_receipt()['cgroup_inode'] == 99
    assert json.loads(original.read_bytes())['cgroup_inode'] == 42
    complete.write_bytes(restore.encoded({'cgroup_inode': 101}))
    with pytest.raises(ValueError, match='HOST_BOOT_RESTORATION_CHAIN_CHANGED'):
        host.active_receipt()
    value['incarnation'] = {'stale': True}
    successor.write_bytes(restore.encoded(value))
    with pytest.raises(ValueError, match='HOST_BOOT_RECEIPT_CHANGED'):
        host.active_receipt()


def test_plan_revision_is_content_addressed_same_incarnation(monkeypatch):
    monkeypatch.setattr(restore, 'ROOT', Path('/root-owned/rsi'))
    first = restore.plan_path('a' * 64, '1' * 64)
    second = restore.plan_path('a' * 64, '2' * 64)
    assert first.parent == second.parent and first != second
    assert first.name == 'plan.' + '1' * 64 + '.json'
    with pytest.raises(ValueError, match='PLAN_HASH_REQUIRED'):
        restore.plan_path('a' * 64, '../escape')
