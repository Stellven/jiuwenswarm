"""Retire owned, drained cgroups only after immutable execution evidence exists.

This administrative adapter never changes the hash-frozen executor. A failed
capture retains the group; recovery requires the persisted preparation, exact
boot/root/group identity and an already durable terminal execution receipt.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import re
import stat
import time

BOOT_ID = Path('/proc/sys/kernel/random/boot_id')
PREPARED_SCHEMA = 'ai4r-rsi-cgroup-retirement-prepared:1'
RETIRED_SCHEMA = 'ai4r-rsi-cgroup-retired:1'
_COUNTERS = ('cgroup.events', 'cgroup.procs', 'memory.events', 'pids.events',
             'memory.max', 'pids.max')


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _boot_id():
    value = BOOT_ID.read_text().strip()
    _need(bool(re.fullmatch(r'[0-9a-f-]{36}', value)), 'CGROUP_BOOT_ID_UNAVAILABLE')
    return value


def _identity(path):
    path = Path(path)
    meta = path.lstat()
    _need(stat.S_ISDIR(meta.st_mode) and meta.st_uid == 0
          and not stat.S_IMODE(meta.st_mode) & 0o022, 'CGROUP_CUSTODY_INVALID')
    _need(path.is_absolute() and path.resolve(strict=True) == path, 'CGROUP_PATH_ALIAS_DENIED')
    return {'path': str(path), 'device': meta.st_dev, 'inode': meta.st_ino}


def _fields(path):
    rows = [line.split() for line in path.read_text().splitlines()]
    _need(all(len(row) == 2 for row in rows) and len({row[0] for row in rows}) == len(rows),
          'CGROUP_CONTROL_INVALID')
    return dict(rows)


def check_capacity(root, required=1):
    """Check every ancestor's live descendants; retain dying counts as diagnostics.

    This is a preflight, not a reservation. Concurrent external allocations may
    still make mkdir fail, which the frozen executor handles fail-closed.
    """
    _need(type(required) is int and required > 0, 'CGROUP_CAPACITY_REQUEST_INVALID')
    root = Path(root)
    _identity(root)
    facts = []
    for group in (root, *root.parents):
        control = group / 'cgroup.max.descendants'
        if not control.exists():
            break
        _identity(group)
        maximum = control.read_text().strip()
        counts = _fields(group / 'cgroup.stat')
        try:
            visible = int(counts['nr_descendants'])
            dying = int(counts['nr_dying_descendants'])
            limit = None if maximum == 'max' else int(maximum)
        except (KeyError, ValueError):
            raise ValueError('CGROUP_CAPACITY_CONTROL_INVALID') from None
        _need(visible >= 0 and dying >= 0 and (limit is None or limit >= 0),
              'CGROUP_CAPACITY_CONTROL_INVALID')
        # Linux cgroup_check_hierarchy_limits compares nr_descendants only.
        # rmdir decrements that count immediately; nr_dying_descendants tracks
        # asynchronous destruction and does not consume max.descendants slots.
        # See microsoft/WSL2-Linux-Kernel kernel/cgroup/cgroup.c.
        _need(limit is None or visible + required <= limit,
              'CGROUP_CAPACITY_EXHAUSTED')
        depth_path = group / 'cgroup.max.depth'
        if depth_path.exists():
            maximum_depth = depth_path.read_text().strip()
            if maximum_depth != 'max':
                try:
                    depth = int(maximum_depth)
                except ValueError:
                    raise ValueError('CGROUP_CAPACITY_CONTROL_INVALID') from None
                _need(depth >= 0 and len(root.relative_to(group).parts) + 1 <= depth,
                      'CGROUP_DEPTH_EXHAUSTED')
        facts.append({'path': str(group), 'max_descendants': maximum,
                      'visible': visible, 'dying': dying, 'required': required})
    _need(bool(facts), 'OBSERVED_CGROUP_CAPACITY_REQUIRED')
    return facts


def _observe(root, group):
    root_identity, group_identity = _identity(root), _identity(group)
    _need(group.parent == root, 'CGROUP_OWNERSHIP_SCOPE_DENIED')
    counters = {name: (group / name).read_text() for name in _COUNTERS}
    events = _fields(group / 'cgroup.events')
    _need(events.get('populated') == '0' and not counters['cgroup.procs'].strip(),
          'EXECUTION_GROUP_NOT_EMPTY')
    _need(not any(child.is_dir() or child.is_symlink() for child in group.iterdir()),
          'EXECUTION_GROUP_HAS_DESCENDANTS')
    return {'root': root_identity, 'group': group_identity, 'boot_id': _boot_id(),
            'counters': counters}


def _receipt_evidence(store, receipt, start_ref):
    start = store.get(start_ref)
    _need(isinstance(receipt, dict) and start.get('job_id') == receipt.get('job_id'),
          'RETIREMENT_START_RECEIPT_MISMATCH')
    _need(receipt.get('observed_runtime') is True and isinstance(receipt.get('termination_reason'), str)
          and receipt.get('ended_at') and type(receipt.get('exit_code')) is int,
          'RETIREMENT_TERMINAL_RECEIPT_REQUIRED')
    if 'candidate_ref' in start:
        subject = receipt.get('subject_ref')
        candidate = start['candidate_ref']
        _need(isinstance(candidate, dict) and isinstance(subject, dict)
              and isinstance(candidate.get('sha256'), str)
              and re.fullmatch(r'[0-9a-f]{64}', candidate['sha256'])
              and candidate['sha256'] == subject.get('sha256'), 'RETIREMENT_SUBJECT_MISMATCH')
        # Original opaque refs and canonical capture refs can identify the same
        # worker bytes. Verify immutable content rather than equating aliases.
        digest = candidate['sha256']
        store.read({'id': digest + '.json', 'sha256': digest})
    for key in ('input_ref', 'program_ref', 'test_ref'):
        if key in start:
            store.read(start[key])
    for key in ('stdout_ref', 'stderr_ref'):
        store.read(receipt[key])
    limits = receipt['observed_limits']
    store.read(limits['isolation_probe_ref'])
    for key in ('memory_events', 'pids_events'):
        _need(isinstance(receipt.get(key), str), 'RETIREMENT_COUNTER_EVIDENCE_REQUIRED')
    return start


def _remove_prepared(root, prepared_ref, store):
    prepared = store.get(prepared_ref)
    _need(prepared.get('schema') == PREPARED_SCHEMA, 'RETIREMENT_PREPARATION_REQUIRED')
    observation = prepared['observation']
    root = Path(root)
    _need(_identity(root) == observation['root'] and _boot_id() == observation['boot_id'],
          'RETIREMENT_ROOT_OR_BOOT_CHANGED')
    receipt = store.get(prepared['receipt_ref'])
    _receipt_evidence(store, receipt, prepared['start_ref'])
    group = Path(observation['group']['path'])
    _need(group.parent == root and group.name == receipt['job_id'], 'CGROUP_OWNERSHIP_SCOPE_DENIED')
    # lstat distinguishes an absent group from a substituted/dangling symlink.
    try:
        group.lstat()
    except FileNotFoundError:
        # Crash after rmdir but before terminal capture. The durable preparation
        # still identifies exactly what was drained; never recreate the group.
        absent = True
    else:
        current = _observe(root, group)
        _need(current == observation, 'RETIREMENT_GROUP_IDENTITY_OR_COUNTERS_CHANGED')
        # No recursion and no control-file deletion. cgroupfs refuses a group
        # with live tasks/descendants even if it became busy after observation.
        os.rmdir(group)
        absent = False
    terminal = {'schema': RETIRED_SCHEMA, 'prepared_ref': prepared_ref,
                'job_id': receipt['job_id'], 'receipt_ref': prepared['receipt_ref'],
                'start_ref': prepared['start_ref'], 'group': observation['group'],
                'boot_id': observation['boot_id'], 'recovered_absence': absent,
                'recorded_unix_ns': time.time_ns()}
    retired_ref = store.put(terminal)
    return {'prepared_ref': prepared_ref, 'retired_ref': retired_ref,
            'receipt_ref': prepared['receipt_ref']}


def retire_owned_group(executor, job, *, receipt, start_ref, store):
    """Persist receipt and drained-group facts, remove only that owned leaf.

    ``store`` is the protected caller's durable RecordStore (including its
    sealed store for held-out jobs). No receipt, claim or journal is deleted.
    A group whose kernel/capture failed without a receipt is intentionally kept.
    """
    root = Path(executor.cgroup_root)
    _need(job.job_id not in executor.active, 'EXECUTION_GROUP_STILL_ACTIVE')
    owned = executor.owned_groups.get(job.job_id)
    _need(isinstance(owned, dict) and owned.get('invocation_id') == job.invocation_id,
          'OWNED_EXECUTION_GROUP_REQUIRED')
    _need(not owned.get('retired'), 'EXECUTION_GROUP_ALREADY_RETIRED')
    group = root / job.job_id
    _need(Path(owned['path']) == group, 'CGROUP_OWNERSHIP_SCOPE_DENIED')
    observation = _observe(root, group)
    _need(observation['group']['inode'] == owned['inode'], 'OWNED_EXECUTION_GROUP_INODE_CHANGED')
    _need(receipt.get('job_id') == job.job_id and receipt.get('invocation_id') == job.invocation_id
          and receipt.get('contract_ref') == dict(job.contract_ref), 'RETIREMENT_JOB_RECEIPT_MISMATCH')
    result = retire_observed_group(root, observation=observation, receipt=receipt,
                                   start_ref=start_ref, store=store)
    owned.update(retired=True, retirement=result)
    return result


def snapshot_group(root, job_id):
    """Capture a specific drained leaf; does not establish historical ownership."""
    _need(isinstance(job_id, str) and re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}', job_id),
          'JOB_ID_INVALID')
    root = Path(root)
    return _observe(root, root / job_id)


def retire_observed_group(root, *, observation, receipt, start_ref, store):
    """Retire one explicitly authorized leaf after durable evidence capture.

    Recovery callers must first prove the root configuration, durable start and
    terminal receipt belong to the ceased run. A snapshot alone is never proof
    of ownership. Current executors use retire_owned_group instead.
    """
    root = Path(root)
    group = Path(observation['group']['path'])
    _need(group.parent == root and group.name == receipt.get('job_id'), 'CGROUP_OWNERSHIP_SCOPE_DENIED')
    _need(_observe(root, group) == observation, 'RETIREMENT_GROUP_IDENTITY_OR_COUNTERS_CHANGED')
    _receipt_evidence(store, receipt, start_ref)
    _need(receipt['memory_events'] == observation['counters']['memory.events']
          and receipt['pids_events'] == observation['counters']['pids.events']
          and receipt['observed_limits']['memory_max'] == observation['counters']['memory.max'].strip()
          and receipt['observed_limits']['pids_max'] == observation['counters']['pids.max'].strip(),
          'RETIREMENT_RECEIPT_COUNTERS_CHANGED')
    receipt_ref = store.put(copy.deepcopy(receipt))
    prepared_ref = store.put({'schema': PREPARED_SCHEMA, 'job_id': receipt['job_id'],
        'invocation_id': receipt['invocation_id'], 'start_ref': start_ref, 'receipt_ref': receipt_ref,
        'observation': observation, 'recorded_unix_ns': time.time_ns()})
    return _remove_prepared(root, prepared_ref, store)


def recover_retirement(root, *, prepared_ref, store):
    """Finish a specific durable retirement; never discover or sweep groups."""
    return _remove_prepared(Path(root), prepared_ref, store)
