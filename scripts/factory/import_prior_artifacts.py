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


if __name__ == '__main__':
    main(sys.argv[1])
