"""Cgroup lifecycle mechanics with durable records and a synthetic cgroupfs.

No worker runs and no real cgroup is touched. The fake filesystem models only
cgroupfs rmdir/control semantics; native confinement is verified separately.
"""
import copy
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.targets import cgroup_lifecycle as lifecycle


@pytest.fixture
def fake_cgroupfs(tmp_path, monkeypatch):
    root = tmp_path / 'cgroup'; root.mkdir()
    original_rmdir = os.rmdir
    # Ordinary temp directories are user-owned, unlike protected cgroupfs.
    # Keep path/inode checks real while separating root-custody qualification.
    def identity(path):
        path = Path(path)
        assert path.is_absolute() and not path.is_symlink() and path.is_dir()
        meta = path.stat()
        return {'path': str(path), 'device': meta.st_dev, 'inode': meta.st_ino}
    monkeypatch.setattr(lifecycle, '_identity', identity)
    monkeypatch.setattr(lifecycle, '_boot_id', lambda: '01234567-89ab-cdef-0123-456789abcdef')
    removals = []
    before_remove = []
    def remove(path, *args, **kwargs):
        path = Path(path)
        if path.parent != root:
            return original_rmdir(path, *args, **kwargs)
        for callback in before_remove:
            callback(path)
        assert (path / 'cgroup.events').read_text() == 'populated 0\n'
        assert not (path / 'cgroup.procs').read_text()
        assert not any(p.is_dir() for p in path.iterdir())
        # In real cgroupfs these virtual files disappear with the directory.
        for control in path.iterdir():
            control.unlink()
        original_rmdir(path)
        removals.append(path.name)
    monkeypatch.setattr(lifecycle.os, 'rmdir', remove)
    def controls(path, *, limit='2', visible=0, dying=0, depth='max'):
        (path / 'cgroup.max.descendants').write_text(str(limit))
        (path / 'cgroup.max.depth').write_text(str(depth))
        (path / 'cgroup.stat').write_text(f'nr_descendants {visible}\nnr_dying_descendants {dying}\n')
    controls(root)
    def group(name):
        path = root / name; path.mkdir()
        for key, value in {'cgroup.events': 'populated 0\n', 'cgroup.procs': '',
                           'memory.events': 'oom_kill 0\n', 'pids.events': 'max 0\n',
                           'memory.max': '134217728', 'pids.max': '16'}.items():
            (path / key).write_text(value)
        return path
    return SimpleNamespace(root=root, group=group, controls=controls,
                           removals=removals, before_remove=before_remove)


@pytest.fixture
def completed(fake_cgroupfs, tmp_path):
    fs = fake_cgroupfs
    store = RecordStore(tmp_path / 'evidence')
    group = fs.group('job-1')
    pin = store.put({'contract': 'mechanics'})
    subject = store.put_bytes(b'implementation')
    job = SimpleNamespace(job_id=group.name, invocation_id='invocation-1', contract_ref=pin)
    executor = SimpleNamespace(cgroup_root=fs.root, active={}, owned_groups={job.job_id: {
        'path': group, 'inode': group.stat().st_ino, 'invocation_id': job.invocation_id}})
    start_ref = store.put({'job_id': job.job_id, 'candidate_ref': subject})
    receipt = {'job_id': job.job_id, 'invocation_id': job.invocation_id,
               'contract_ref': pin, 'subject_ref': subject, 'observed_runtime': True,
               'termination_reason': 'completed', 'ended_at': '2026-10-28T00:00:00Z',
               'exit_code': 0, 'stdout_ref': store.put_bytes(b'exact-output'),
               'stderr_ref': store.put_bytes(b''), 'memory_events': 'oom_kill 0\n',
               'pids_events': 'max 0\n', 'observed_limits': {
                   'memory_max': '134217728', 'pids_max': '16',
                   'isolation_probe_ref': store.put_bytes(b'{"ready":true}')}}
    yield SimpleNamespace(fs=fs, store=store, group=group, job=job, executor=executor,
                          start_ref=start_ref, receipt=receipt)
    store.close()


def retire(case):
    return lifecycle.retire_owned_group(case.executor, case.job, receipt=case.receipt,
                                        start_ref=case.start_ref, store=case.store)


@pytest.mark.parametrize('termination,exit_code', [('completed', 0), ('completed', 7),
    ('timeout', -9), ('cancelled', -9), ('resource_limit_exceeded', -9)])
def test_terminal_jobs_retire_only_after_durable_full_evidence(completed, termination, exit_code):
    c = completed
    c.receipt.update(termination_reason=termination, exit_code=exit_code)
    original = copy.deepcopy(c.receipt)
    def before_remove(group):
        records = [__import__('json').loads(p.read_bytes()) for p in c.store.root.glob('*.json')
                   if p.read_bytes().startswith(b'{')]
        prepared = next(r for r in records if r.get('schema') == lifecycle.PREPARED_SCHEMA)
        # Reopen an independent store: neither an in-memory receipt nor a
        # pending transaction suffices to permit group removal.
        reopened = RecordStore(c.store.root)
        try:
            assert reopened.get(prepared['receipt_ref']) == original
            assert reopened.get(prepared['start_ref'])['job_id'] == c.job.job_id
            assert reopened.read(original['stdout_ref']) == b'exact-output'
            assert reopened.read(original['stderr_ref']) == b''
            assert reopened.read(original['observed_limits']['isolation_probe_ref']) == b'{"ready":true}'
        finally:
            reopened.close()
    c.fs.before_remove.append(before_remove)
    result = retire(c)
    assert not c.group.exists() and c.fs.removals == ['job-1']
    assert c.store.get(result['receipt_ref']) == original
    assert c.store.get(result['retired_ref'])['prepared_ref'] == result['prepared_ref']
    assert c.receipt == original
    assert c.executor.owned_groups['job-1']['retired'] is True
    with pytest.raises(ValueError, match='ALREADY_RETIRED'):
        retire(c)


@pytest.mark.parametrize('failure', ['capture', 'prepared'])
def test_capture_failure_preserves_group_and_evidence(completed, monkeypatch, failure):
    c = completed
    put = c.store.put
    def fail(value):
        if (failure == 'capture' and value.get('observed_runtime') is True
                or failure == 'prepared' and value.get('schema') == lifecycle.PREPARED_SCHEMA):
            raise OSError('simulated durable capture failure')
        return put(value)
    monkeypatch.setattr(c.store, 'put', fail)
    with pytest.raises(OSError, match='durable capture failure'):
        retire(c)
    assert c.group.exists() and not c.fs.removals
    assert c.store.read(c.receipt['stdout_ref']) == b'exact-output'
    assert not c.executor.owned_groups['job-1'].get('retired')


@pytest.mark.parametrize('change,reason', [
    ('active', 'STILL_ACTIVE'), ('foreign', 'OWNED_EXECUTION_GROUP_REQUIRED'),
    ('invocation', 'OWNED_EXECUTION_GROUP_REQUIRED'), ('inode', 'INODE_CHANGED'),
    ('populated', 'NOT_EMPTY'), ('process', 'NOT_EMPTY'), ('descendant', 'HAS_DESCENDANTS'),
    ('receipt', 'JOB_RECEIPT_MISMATCH'), ('subject', 'SUBJECT_MISMATCH'),
    ('counter', 'COUNTERS_CHANGED'), ('no_terminal', 'TERMINAL_RECEIPT_REQUIRED')])
def test_unproven_or_busy_groups_never_retired(completed, change, reason):
    c = completed
    owned = c.executor.owned_groups['job-1']
    if change == 'active': c.executor.active['job-1'] = object()
    elif change == 'foreign': c.executor.owned_groups.clear()
    elif change == 'invocation': owned['invocation_id'] = 'other'
    elif change == 'inode': owned['inode'] += 1
    elif change == 'populated': (c.group / 'cgroup.events').write_text('populated 1\n')
    elif change == 'process': (c.group / 'cgroup.procs').write_text('123\n')
    elif change == 'descendant': (c.group / 'child').mkdir()
    elif change == 'receipt': c.receipt['invocation_id'] = 'other'
    elif change == 'subject': c.receipt['subject_ref'] = c.store.put_bytes(b'other')
    elif change == 'counter': (c.group / 'memory.events').write_text('oom_kill 1\n')
    elif change == 'no_terminal': c.receipt.pop('ended_at')
    with pytest.raises(ValueError, match=reason): retire(c)
    assert c.group.exists() and not c.fs.removals


def test_missing_captured_output_cannot_authorize_retirement(completed):
    c = completed
    (c.store.root / c.receipt['stdout_ref']['id']).unlink()
    with pytest.raises(FileNotFoundError): retire(c)
    assert c.group.exists() and not c.fs.removals


@pytest.mark.parametrize('crash_after_remove', [False, True])
def test_recovery_from_durable_preparation_without_reexecuting_job(completed, monkeypatch, crash_after_remove):
    c = completed
    put = c.store.put
    prepared_refs = []
    def crash(value):
        if value.get('schema') == lifecycle.RETIRED_SCHEMA:
            raise OSError('crashed after removal')
        ref = put(value)
        if value.get('schema') == lifecycle.PREPARED_SCHEMA:
            prepared_refs.append(ref)
            if not crash_after_remove:
                raise OSError('crashed after preparation')
        return ref
    monkeypatch.setattr(c.store, 'put', crash)
    with pytest.raises(OSError, match='crashed'): retire(c)
    assert c.group.exists() is not crash_after_remove
    monkeypatch.setattr(c.store, 'put', put)
    result = lifecycle.recover_retirement(c.fs.root, prepared_ref=prepared_refs[0], store=c.store)
    assert not c.group.exists() and c.fs.removals == ['job-1']
    assert c.store.get(result['retired_ref'])['recovered_absence'] is crash_after_remove
    assert c.store.get(result['receipt_ref']) == c.receipt


@pytest.mark.parametrize('change', ['boot', 'replacement', 'busy'])
def test_recovery_refuses_changed_boot_replaced_or_busy_group(completed, monkeypatch, change):
    c = completed
    original = lifecycle._remove_prepared
    prepared = []
    def stop(root, ref, store):
        prepared.append(ref)
        raise OSError('interrupted')
    monkeypatch.setattr(lifecycle, '_remove_prepared', stop)
    with pytest.raises(OSError): retire(c)
    monkeypatch.setattr(lifecycle, '_remove_prepared', original)
    if change == 'boot': monkeypatch.setattr(lifecycle, '_boot_id', lambda: 'other-boot')
    elif change == 'replacement':
        c.group.rename(c.fs.root / 'original-job')
        c.fs.group(c.job.job_id)
    else: (c.group / 'cgroup.events').write_text('populated 1\n')
    with pytest.raises(ValueError):
        lifecycle.recover_retirement(c.fs.root, prepared_ref=prepared[0], store=c.store)
    assert c.group.exists() and not c.fs.removals


def test_capacity_dying_descendants_do_not_consume_live_quota(fake_cgroupfs):
    fs = fake_cgroupfs
    # Regression from native run: all directories had been retired, but two
    # dying groups remained in kernel diagnostics after their quota was freed.
    fs.controls(fs.root, limit=2, visible=0, dying=2)
    facts = lifecycle.check_capacity(fs.root)
    assert facts[0]['visible'] == 0 and facts[0]['dying'] == 2
    fs.controls(fs.root, limit=2, visible=1, dying=2)
    assert lifecycle.check_capacity(fs.root)[0]['visible'] == 1
    with pytest.raises(ValueError, match='CAPACITY_EXHAUSTED'):
        lifecycle.check_capacity(fs.root, required=2)
    fs.controls(fs.root, limit=2, visible=2, dying=0)
    with pytest.raises(ValueError, match='CAPACITY_EXHAUSTED'):
        lifecycle.check_capacity(fs.root)


def test_capacity_counts_live_siblings_at_every_ancestor(fake_cgroupfs):
    fs = fake_cgroupfs
    child = fs.root / 'delegation'; child.mkdir(); fs.controls(child, limit=20)
    fs.controls(fs.root, limit=2, visible=2, dying=0)
    with pytest.raises(ValueError, match='CAPACITY_EXHAUSTED'):
        lifecycle.check_capacity(child)


def test_capacity_respects_ancestor_depth_and_requires_observed_controls(fake_cgroupfs):
    fs = fake_cgroupfs
    child = fs.root / 'delegation'; child.mkdir(); fs.controls(child, limit=20)
    fs.controls(fs.root, limit=20, depth=1)
    with pytest.raises(ValueError, match='DEPTH_EXHAUSTED'): lifecycle.check_capacity(child)
    empty = fs.root.parent / 'unqualified'; empty.mkdir()
    with pytest.raises(ValueError, match='OBSERVED_CGROUP_CAPACITY_REQUIRED'): lifecycle.check_capacity(empty)


def test_repeated_jobs_do_not_accumulate_live_groups(completed):
    c = completed
    for number in range(20):
        if number:
            c.group = c.fs.group(f'job-{number + 1}')
            c.job.job_id = c.group.name
            c.receipt['job_id'] = c.group.name
            c.start_ref = c.store.put({'job_id': c.group.name, 'candidate_ref': c.receipt['subject_ref']})
            c.executor.owned_groups[c.group.name] = {'path': c.group, 'inode': c.group.stat().st_ino,
                                                    'invocation_id': c.job.invocation_id}
        # One visible job consumes the entire small delegation limit.
        c.fs.controls(c.fs.root, limit=1, visible=1)
        with pytest.raises(ValueError, match='CAPACITY_EXHAUSTED'): lifecycle.check_capacity(c.fs.root)
        result = retire(c)
        c.fs.controls(c.fs.root, limit=1, visible=0)
        lifecycle.check_capacity(c.fs.root)
        assert c.store.get(result['receipt_ref'])['job_id'] == c.job.job_id
        assert not any(path.is_dir() for path in c.fs.root.iterdir())
    assert len(c.fs.removals) == 20


def test_equivalent_opaque_subject_alias_is_verified_by_exact_body(completed):
    c = completed
    c.receipt['subject_ref'] = {**c.receipt['subject_ref'], 'id': 'blob:original-worker'}
    result = retire(c)
    assert c.store.get(result['receipt_ref'])['subject_ref']['id'] == 'blob:original-worker'


@pytest.mark.parametrize('key', ['input_ref', 'program_ref', 'test_ref'])
def test_missing_start_dependency_prevents_retirement(completed, key):
    c = completed
    dependency = c.store.put_bytes(('dependency-' + key).encode())
    start = c.store.get(c.start_ref)
    start[key] = dependency
    c.start_ref = c.store.put(start)
    (c.store.root / dependency['id']).unlink()
    with pytest.raises(FileNotFoundError): retire(c)
    assert c.group.exists() and not c.fs.removals
