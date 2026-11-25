"""Operator step: import the prior artifacts a task reuses into its evidence store.

For each entry of the task's resources.prior_artifacts this records one host observation of kind
``prior_artifact`` (values: key, path, made, how, reused: true, size, sha256 of each file up to
FULL_HASH_MAX, the file list of a directory) and, for files up to KEEP_MAX, stores the bytes as an
artifact ``prior-<key>`` the agent can read with factory.evidence.read. Large files (packs) are
named, sized and left in place; their capsule verifiers read them where they are.

Agents cannot write this kind (store.ScopedStore reserves it), so a cited prior_artifact record
always comes from the operator.

    python scripts/factory/import_prior_artifacts.py <task_id>     # FACTORY_HOME set
"""
import hashlib
import json
import os
import sys
from pathlib import Path

from jiuwenswarm.factory.store import Store

FULL_HASH_MAX = 64 << 20
KEEP_MAX = 4 << 20


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def describe(path):
    path = Path(path)
    if path.is_dir():
        files = sorted(p for p in path.iterdir() if p.is_file())
        return dict(kind='directory', bytes=sum(p.stat().st_size for p in files),
                    files=[dict(name=p.name, bytes=p.stat().st_size,
                                sha256=sha256(p) if p.stat().st_size <= FULL_HASH_MAX else None) for p in files])
    size = path.stat().st_size
    return dict(kind='file', bytes=size, sha256=sha256(path) if size <= FULL_HASH_MAX else None)


def main(task_id):
    store = Store(Path(os.environ['FACTORY_HOME']))
    task = store.get_task(task_id)
    prior = (task.get('resources') or {}).get('prior_artifacts') or {}
    done = {json.loads(r[0])['key'] for r in store._db.execute(
        'SELECT "values" FROM observations WHERE task_id=? AND kind=?', (task_id, 'prior_artifact'))}
    for key, entry in prior.items():
        if key in done:
            continue
        values = dict(entry, key=key, reused=True, **describe(entry['path']))
        artifacts = []
        if values['kind'] == 'file' and values['bytes'] <= KEEP_MAX:
            artifact = store.put_artifact(task_id, f'prior-{key}', Path(entry['path']),
                                          'application/json' if entry['path'].endswith('.json') else 'text/plain', None)
            values['artifact_id'] = f'prior-{key}'
            artifacts.append(values['artifact_id'])
        record = store.append_observation(task_id, dict(
            kind='prior_artifact', values=values, source_artifacts=artifacts,
            host_run=dict(by='operator import', script='scripts/factory/import_prior_artifacts.py'),
            limitations='Made before this task by an earlier run (see made and how); reused here, not remade.'))
        print(key, record['obs_id'], values['kind'], values['bytes'], values.get('sha256') or '')


def host_reading(task_id):
    """One operator record of kind host_reading: the machine state now (free disk, memory, what else runs)
    and the memory cap policy every model load must run under. Recorded at each run start."""
    store = Store(Path(os.environ['FACTORY_HOME']))
    reading = json.loads(Path(os.environ['FACTORY_MACHINE_STATE']).read_text(encoding='utf-8'))
    disk = os.statvfs(os.path.expanduser('~'))
    reading['disk_home_free_bytes'] = disk.f_bavail * disk.f_frsize
    for name in ('memory.max', 'memory.swap.max'):
        try:
            slice_ = Path('/proc/self/cgroup').read_text().strip().split('::')[-1]
            reading.setdefault('cgroup_now', {})[name] = (Path('/sys/fs/cgroup') / slice_.lstrip('/') / name).read_text().strip()
        except OSError:
            pass
    reading['memory_cap_policy'] = ('Every model load runs under systemd-run --user -p MemoryMax=96G -p MemorySwapMax=0 '
                                    'with -lm mmap; this run loads no model.')
    record = store.append_observation(task_id, dict(
        kind='host_reading', values=reading,
        host_run=dict(by='operator', script='scripts/factory/import_prior_artifacts.py --host-reading'),
        limitations='A reading at run start; the scheduler brief carries a fresher one (machine).'))
    print('host_reading', record['obs_id'], reading['disk_home_free_bytes'], reading['memory_mib'])


if __name__ == '__main__':
    if sys.argv[1] == '--host-reading':
        host_reading(sys.argv[2])
    else:
        main(sys.argv[1])
