"""Recorder protocol/boundary and durable-journal tests, without real Docker."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from jiuwenswarm.factory import lab_recorder as recorder


IMAGE = 'sha256:'+'a'*64


def validate(**kw):
    values = dict(argv=['/engine'], image=IMAGE, mounts=[], environment={}, protocol=b'GEN 1 0\nQUIT\n',
                  timeout_s=10, interval_ms=100, guard_gib=8, memory_bytes=104*2**30, cpus=8)
    values.update(kw)
    return recorder.validate_spec(**values)


@pytest.mark.parametrize('change', [dict(timeout_s=float('nan')), dict(cpus=9), dict(memory_bytes=105*2**30),
    dict(image='mutable:tag'), dict(protocol=b'QUIT'), dict(protocol=b'GEN 1 0\n'),
    dict(protocol=b'RESET\nQUIT\n'), dict(environment={'LD_PRELOAD':'/x'}), dict(environment={'HOME':'/host'})])
def test_invalid_spec_rejected(change):
    with pytest.raises(ValueError): validate(**change)


def test_readonly_mount_restrictions(tmp_path):
    validate(mounts=[(tmp_path, '/model')])
    for target in ('/', '/proc/x', '/sys/x', '/var/run/docker.sock'):
        with pytest.raises(ValueError): validate(mounts=[(tmp_path, target)])


def test_journal_checkpoint_covers_fsynced_bytes(tmp_path):
    journal = recorder.Journal(tmp_path)
    journal.chunk('stdout', b'READY\n')
    journal.chunk('stdin', b'GEN 1 0\n')
    journal.chunk('stdout', b'T 42\nDONE 1\n')
    journal.sample(dict(available_bytes=123))
    journal.close()
    checkpoint = json.loads((tmp_path/'checkpoint.json').read_text())
    events = [json.loads(line) for line in (tmp_path/'pipe-events.jsonl').read_text().splitlines()]
    assert checkpoint['sequence'] == 3
    assert [event['sequence'] for event in events] == [0, 1, 2]
    assert checkpoint['offsets']['stdout'] == (tmp_path/'stdout.log').stat().st_size
    assert checkpoint['offsets']['stdin'] == (tmp_path/'stdin-wire.log').stat().st_size
    assert checkpoint['fsync_interval_s'] == 1
    assert checkpoint['max_observed_sync_gap_s'] >= 0


def test_create_args_bind_ownership_and_no_swap(tmp_path):
    intent = dict(container_name='factory-lab-'+'a'*32, nonce='b'*32, image=IMAGE)
    args = recorder.create_argv(['/engine'], intent, mounts=[(tmp_path, '/model')], gpu=False,
                                environment={'DS4_AHEAD':'0'}, memory_bytes=64*2**20, cpus=1)
    assert args[args.index('--memory')+1] == args[args.index('--memory-swap')+1] == str(64*2**20)
    assert 'factory.lab.nonce='+intent['nonce'] in args
    assert '--device' not in args
    assert f'type=bind,src={tmp_path},dst=/model,readonly' in args


def test_manifest_hashes_retained_bytes(tmp_path):
    (tmp_path/'stdout.log').write_bytes(b'partial')
    manifest = recorder.seal_manifest(tmp_path, 'partial')
    assert manifest['state'] == 'partial'
    assert manifest['files']['stdout.log'] == hashlib.sha256(b'partial').hexdigest()
    assert 'manifest.json' not in manifest['files']


def test_exited_cgroup_enodev_keeps_host_sample(tmp_path, monkeypatch):
    import errno
    original = Path.read_text
    def read(path, *args, **kwargs):
        if path.is_relative_to(tmp_path):
            raise OSError(errno.ENODEV, 'cgroup device is gone')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    sample = recorder.memory_sample(tmp_path)
    assert sample['available_bytes'] > 0
    assert sample['cgroup_current'] is None


def test_exiting_process_io_permission_denial_is_unknown_not_zero(monkeypatch):
    original=Path.read_text
    def read(path,*args,**kwargs):
        if str(path)=='/proc/999999/io':raise PermissionError(13,'process is no longer dumpable')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',read)
    sample=recorder.memory_sample(pid=999999)
    assert sample['available_bytes']>0
    assert 'process_io' not in sample
    assert sample['process_io_status']=={'status':'not_measured','errno':13}


def test_kernel_peak_and_process_status_units(tmp_path, monkeypatch):
    (tmp_path/'memory.current').write_text('1234')
    (tmp_path/'memory.peak').write_text('5678')
    original=Path.read_text
    def read(path,*args,**kwargs):
        if str(path)=='/proc/999999/status':
            return 'Name:\ttest\nVmRSS:\t11 kB\nVmHWM:\t17 kB\nVmSize:\t22 kB\n'
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',read)
    sample=recorder.memory_sample(tmp_path,999999)
    assert sample['cgroup_current']==1234
    assert sample['cgroup_peak']==5678
    assert sample['process_memory_bytes']==dict(VmRSS=11*1024,VmHWM=17*1024,VmSize=22*1024)
    (tmp_path/'memory.peak').unlink()
    assert recorder.memory_sample(tmp_path)['cgroup_peak'] is None
