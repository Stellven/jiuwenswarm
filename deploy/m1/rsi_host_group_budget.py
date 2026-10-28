"""Reviewed finite descendant allowance for the dedicated RSI host.

Changes only cgroup.max.descendants, while every dedicated container is stopped
and every retained job group is empty. Never removes groups or changes resource
limits. An interrupted claim blocks replay; original host receipts stay intact.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('group_budget_restore', HERE / 'rsi_host_boot_restore.py')
restore = importlib.util.module_from_spec(spec); spec.loader.exec_module(restore)
host = restore.host
ROOT = Path('/var/lib/ai4r-rsi-codex/config/host-group-budget')
LIMIT = 4096


def need(value, reason):
    if not value: raise ValueError(reason)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def sha(raw): return hashlib.sha256(raw).hexdigest()


def demand(value, retained):
    need(set(value) == {'schema', 'jobs', 'container_reserve', 'max_descendants'}
         and value['schema'] == 'ai4r-rsi-host-group-demand:1', 'CLOSED_GROUP_DEMAND_REQUIRED')
    jobs = value['jobs']
    bounds = {'timing_calibration': 2196, 'visible_opportunity': 312, 'security': 64, 'final_qualification_and_candidate': 1024}
    need(set(jobs) == set(bounds) and all(type(jobs[k]) is int and 0 <= jobs[k] <= bounds[k] for k in bounds), 'FINITE_JOB_COUNTS_REQUIRED')
    need(type(value['container_reserve']) is int and 2 <= value['container_reserve'] <= 128
         and type(value['max_descendants']) is int and value['max_descendants'] == LIMIT, 'FINITE_DESCENDANT_ALLOWANCE_REQUIRED')
    total = retained + sum(jobs.values()) + value['container_reserve']
    need(total <= LIMIT, 'PLANNED_GROUP_DEMAND_EXCEEDS_ALLOWANCE')
    return total


def empty_job_groups(root):
    """Observe all descendants, including nested groups, without writing them."""
    host.safe(root)
    need(root.is_dir(), 'OWNED_JOBS_BRANCH_REQUIRED')
    rows = []
    for path in [root, *sorted(p for p in root.rglob('*') if p.is_dir())]:
        host.secure(path)
        events = dict(line.split() for line in (path / 'cgroup.events').read_text().splitlines())
        need(events.get('populated') == '0' and not (path / 'cgroup.procs').read_text().strip(), 'OWNED_JOB_GROUP_NOT_EMPTY')
        rows.append({'path': str(path.relative_to(root)), 'inode': path.stat().st_ino})
    return rows


def containers():
    command = ['/usr/bin/docker', '--host', host.SOCKET]
    ids = restore.client(command + ['ps', '-aq', '--no-trunc']).decode().split()
    need(len(ids) <= 128 and len(set(ids)) == len(ids) and all(re.fullmatch('[a-f0-9]{64}', i) for i in ids), 'BOUNDED_CONTAINER_SET_REQUIRED')
    rows = json.loads(restore.client(command + ['inspect', *ids])) if ids else []
    need(sorted(row['Id'] for row in rows) == sorted(ids), 'CONTAINER_SET_CHANGED')
    for row in rows:
        restore.stopped_configuration(row, row['HostConfig'])
        mounts = row.get('Mounts', [])
        need(isinstance(mounts, list) and len({m['Destination'] for m in mounts}) == len(mounts), 'UNIQUE_MOUNT_DESTINATIONS_REQUIRED')
        row['Mounts'] = sorted(mounts, key=encoded)
    return [{'id': row['Id'], 'inspection_sha256': sha(encoded(row))} for row in sorted(rows, key=lambda r: r['Id'])]


def observe(request, *, expected_limit=None):
    host.verified()
    receipt = host.active_receipt()
    host.secure(host.CG)
    bounds = {key: (host.CG / name).read_text().strip() for key, name in
              (('memory_max', 'memory.max'), ('pids_max', 'pids.max'), ('cpu_max', 'cpu.max'))}
    need(host.CG.stat().st_ino == receipt['cgroup_inode'] and all(bounds[k] == receipt[k] for k in bounds), 'HOST_IDENTITY_OR_RESOURCE_LIMIT_CHANGED')
    current = (host.CG / 'cgroup.max.descendants').read_text().strip()
    need(current.isdecimal() and int(current) > 0, 'EXISTING_FINITE_DESCENDANT_LIMIT_REQUIRED')
    need(int(current) == expected_limit if expected_limit is not None else int(current) < LIMIT, 'DESCENDANT_LIMIT_CHANGED_OR_ALREADY_ISSUED')
    groups = empty_job_groups(host.CG / 'jobs')
    visible = len([p for p in host.CG.rglob('*') if p.is_dir()])
    cgroup_stat = dict(line.split() for line in (host.CG / 'cgroup.stat').read_text().splitlines())
    need(all(cgroup_stat.get(k, '').isdecimal() for k in ('nr_descendants', 'nr_dying_descendants'))
         and int(cgroup_stat['nr_descendants']) == visible, 'DESCENDANT_COUNT_CHANGED')
    # Removed-but-dying kernel groups are conservatively charged as well.
    dying = int(cgroup_stat['nr_dying_descendants'])
    retained = visible + dying
    total = demand(request, retained)
    stopped = containers()
    need(empty_job_groups(host.CG / 'jobs') == groups, 'OWNED_JOB_SET_CHANGED')
    return {'schema': 'ai4r-rsi-host-group-budget-plan:1', 'incarnation': host.incarnation(),
            'cgroup_inode': host.CG.stat().st_ino, 'active_receipt_sha256': sha(encoded(receipt)),
            'original_started_sha256': host.digest(host.ROOT / 'started.json'), 'bounds': bounds,
            'swap_max': (host.CG / 'memory.swap.max').read_text().strip(),
            'max_depth': (host.CG / 'cgroup.max.depth').read_text().strip(),
            'prior_max_descendants': int(current), 'request': request, 'retained_descendants': retained,
            'visible_descendants': visible, 'dying_descendants': dying,
            'planned_total_descendants': total, 'job_groups': groups, 'containers': stopped,
            'admin_source_sha256': {name: host.digest(HERE / name) for name in
                ('rsi_host_group_budget.py', 'rsi_host.py', 'rsi_host_boot_restore.py')}}


def location(): return ROOT / host.incarnation_key()


def compatible(expected, actual, *, after_write=False):
    """Only asynchronous reclamation of already-dying groups may progress."""
    if set(expected) != set(actual): return False
    before, after = expected['dying_descendants'], actual['dying_descendants']
    if not (type(before) is int and type(after) is int and 0 <= after <= before): return False
    reclaimed = before - after
    if (actual['retained_descendants'] != expected['retained_descendants'] - reclaimed
            or actual['planned_total_descendants'] != demand(expected['request'], actual['retained_descendants'])): return False
    normalized = dict(actual, dying_descendants=before,
                      retained_descendants=expected['retained_descendants'],
                      planned_total_descendants=expected['planned_total_descendants'])
    if after_write:
        if actual['prior_max_descendants'] != LIMIT: return False
        normalized['prior_max_descendants'] = expected['prior_max_descendants']
    return normalized == expected


def new(path, raw):
    host.secure(path.parent)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_DIRECTORY | os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


@contextmanager
def lock():
    host.secure(ROOT.parent)
    fd = os.open(ROOT.parent / 'host-group-budget.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        meta = os.fstat(fd)
        need(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1 and meta.st_uid == 0 and not meta.st_mode & 0o077, 'ROOT_LOCK_REQUIRED')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally: os.close(fd)


def plan(input_path):
    host.secure(input_path)
    request = json.loads(input_path.read_bytes())
    result = observe(request)
    need(sum(request['jobs'].values()) > 0, 'NONEMPTY_PLANNED_WORK_REQUIRED')
    path = location()
    need(not path.exists(), 'EXISTING_GROUP_BUDGET_ISSUANCE_BLOCKS_REPLAY')
    if not ROOT.exists(): ROOT.mkdir(mode=0o700)
    host.secure(ROOT); path.mkdir(mode=0o700)
    new(path / 'plan.json', encoded(result))
    return {'plan_path': str(path / 'plan.json'), 'plan_sha256': sha(encoded(result)), 'plan': result}


def apply(approval):
    path = location(); host.secure(path / 'plan.json')
    raw = (path / 'plan.json').read_bytes(); result = json.loads(raw)
    need(sha(raw) == approval, 'EXACT_GROUP_BUDGET_PLAN_APPROVAL_REQUIRED')
    need(not (path / 'claim.json').exists() and not (path / 'complete.json').exists(), 'GROUP_BUDGET_CLAIM_BLOCKS_REPLAY')
    before = observe(result['request'])
    need(compatible(result, before), 'GROUP_BUDGET_PLAN_CHANGED')
    new(path / 'claim.json', encoded({'plan_sha256': approval, 'incarnation': result['incarnation']}))
    (host.CG / 'cgroup.max.descendants').write_text(str(LIMIT))
    after = observe(result['request'], expected_limit=LIMIT)
    need(compatible(before, after, after_write=True), 'GROUP_BUDGET_POSTCONDITION_CHANGED')
    completion = {'schema': 'ai4r-rsi-host-group-budget-complete:1', 'plan_sha256': approval,
                  'claim_sha256': host.digest(path / 'claim.json'), 'max_descendants': LIMIT,
                  'original_receipts_and_job_groups_preserved': True}
    new(path / 'complete.json', encoded(completion))
    return completion


def doctor(input_path):
    path = location()
    for name in ('plan.json', 'claim.json', 'complete.json'): host.secure(path / name)
    result = json.loads((path / 'plan.json').read_bytes()); complete = json.loads((path / 'complete.json').read_bytes())
    pin = host.digest(path / 'plan.json')
    need(json.loads((path / 'claim.json').read_bytes()) == {'plan_sha256': pin, 'incarnation': result['incarnation']}
         and complete == {'schema': 'ai4r-rsi-host-group-budget-complete:1', 'plan_sha256': pin,
             'claim_sha256': host.digest(path / 'claim.json'), 'max_descendants': LIMIT,
             'original_receipts_and_job_groups_preserved': True}, 'GROUP_BUDGET_COMPLETION_CHAIN_CHANGED')
    need(complete['max_descendants'] == LIMIT and (host.CG / 'cgroup.max.descendants').read_text().strip() == str(LIMIT), 'DESCENDANT_ALLOWANCE_CHANGED')
    # Root supplies remaining demand explicitly; never assume original captures
    # have been consumed, or count them twice after retaining their groups.
    host.secure(input_path)
    current = observe(json.loads(input_path.read_bytes()), expected_limit=LIMIT)
    need(all(current[k] == result[k] for k in ('incarnation', 'cgroup_inode', 'bounds', 'swap_max', 'max_depth',
         'original_started_sha256', 'active_receipt_sha256', 'admin_source_sha256'))
         and all(row in current['job_groups'] for row in result['job_groups']), 'GROUP_BUDGET_HOST_CHANGED')
    return {'status': 'FINITE_GROUP_BUDGET_IDLE_VERIFIED', 'max_descendants': LIMIT,
            'remaining_descendants': LIMIT - current['retained_descendants'],
            'planned_total_descendants': current['planned_total_descendants']}


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('operation', choices=('plan', 'apply', 'doctor')); parser.add_argument('--input', type=Path)
    parser.add_argument('--review-sha256'); args = parser.parse_args()
    need(os.geteuid() == os.getegid() == 0, 'ROOT_REQUIRED')
    with lock():
        result = plan(args.input) if args.operation == 'plan' else apply(args.review_sha256) if args.operation == 'apply' else doctor(args.input)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
