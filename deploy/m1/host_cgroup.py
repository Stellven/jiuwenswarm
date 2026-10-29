"""Host-only preparation/cleanup of one explicit bounded executor delegation.

Run on the approved Linux Docker host. Never mounted in an untrusted job, and
never changes the root cgroup or an unrelated project's resource controls.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path


def owned_path(job_id):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", job_id):
        raise ValueError("INVALID_DELEGATION_ID")
    root = Path('/sys/fs/cgroup')
    target = root / ('ai4r-m1.' + job_id)
    if target.is_symlink() or target.resolve().parent != root:
        raise ValueError("DELEGATION_SCOPE_INVALID")
    return target


def prepare(job_id, memory_mb, pids_max, manifest):
    target = owned_path(job_id)
    if memory_mb <= 0 or pids_max < 4:
        raise ValueError("EXPLICIT_POSITIVE_HOST_LIMITS_REQUIRED")
    target.mkdir(mode=0o700)  # an existing delegation is never adopted
    try:
        controls = (target / 'cgroup.controllers').read_text().split()
        if not {'memory', 'pids'} <= set(controls):
            raise RuntimeError('HOST_CONTROLLERS_NOT_DELEGATED')
        (target / 'memory.max').write_text(str(memory_mb * 1024 * 1024))
        (target / 'pids.max').write_text(str(pids_max))
        (target / 'cgroup.subtree_control').write_text('+memory +pids')
        for filename, value in [('cgroup.max.depth', '8'), ('cgroup.max.descendants', '32')]:
            if (target / filename).exists(): (target / filename).write_text(value)
        receipt = {'schema': 'ai4r-host-delegation:1', 'job_id': job_id, 'path': str(target),
                   'inode': target.stat().st_ino, 'memory_max': (target / 'memory.max').read_text().strip(),
                   'pids_max': (target / 'pids.max').read_text().strip(), 'jobs': []}
        with Path(manifest).open('x', encoding='utf-8') as stream:
            json.dump(receipt, stream, indent=2)
            stream.write('\n')
        return receipt
    except Exception:
        if not (target / 'cgroup.procs').read_text().strip():
            target.rmdir()
        raise


def cleanup(manifest):
    receipt = json.loads(Path(manifest).read_text(encoding='utf-8'))
    target = owned_path(receipt['job_id'])
    if receipt['path'] != str(target) or target.stat().st_ino != receipt['inode']:
        raise ValueError('DELEGATION_IDENTITY_CHANGED')
    children = [p for p in target.iterdir() if p.is_dir()]
    for child in children:
        if child.is_symlink() or child.resolve().parent != target or child.name not in receipt['jobs']:
            raise ValueError('UNRECORDED_CHILD_DELEGATION')
        if (child / 'cgroup.procs').read_text().strip() or any(p.is_dir() for p in child.iterdir()):
            raise ValueError('DELEGATION_STILL_POPULATED')
    if (target / 'cgroup.procs').read_text().strip():
        raise ValueError('DELEGATION_STILL_POPULATED')
    for child in children: child.rmdir()
    target.rmdir()
    return {'schema': 'ai4r-host-cleanup:1', 'job_id': receipt['job_id'], 'removed': str(target)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['prepare', 'cleanup'])
    parser.add_argument('--job-id')
    parser.add_argument('--memory-mb', type=int)
    parser.add_argument('--pids-max', type=int)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--hold', action='store_true', help='Keep the approved host job alive until stop/EOF, then clean its empty delegation')
    args = parser.parse_args()
    if os.name != 'posix' or os.geteuid() != 0:
        raise SystemExit('APPROVED_LINUX_HOST_ROOT_REQUIRED')
    if args.operation == 'prepare':
        if args.job_id is None or args.memory_mb is None or args.pids_max is None:
            parser.error('prepare needs explicit job-id, memory-mb and pids-max')
        result = prepare(args.job_id, args.memory_mb, args.pids_max, args.manifest)
    else:
        result = cleanup(args.manifest)
    print(json.dumps(result), flush=True)
    if args.hold:
        if args.operation != 'prepare':
            raise ValueError('HOLD_REQUIRES_PREPARE')
        for line in sys.stdin:
            if line.strip() == 'stop': break
        print(json.dumps(cleanup(args.manifest)), flush=True)


if __name__ == '__main__':
    main()
