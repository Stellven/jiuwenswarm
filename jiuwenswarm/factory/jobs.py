"""Durable host adapter for jobq. The queue, not the caller, owns processes."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

from .store import FactoryError, NotFound, encoded
from .config import JOBQ_BIN, DOCKER_PREFIX, CANCEL_TIMEOUT

TERMINAL = {'succeeded', 'failed', 'cancelled'}


class KeyConflict(FactoryError):
    code = 'KEY_CONFLICT'


def fingerprint(kind, request, argv, job_class, timeout_s):
    return hashlib.sha256(json.dumps(dict(kind=kind, request=request, argv=list(argv),
        job_class=job_class, timeout_s=timeout_s), sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def metadata(store, attempt, **changes):
    """Host-only metadata update; F02's transition API requires a state change."""
    if 'state' in changes:
        raise ValueError('State changes require transition_attempt')
    with store._transaction():
        current = store._get('attempts', attempt['task_id'], attempt['attempt_id'])
        history_entry = changes.pop('history_entry', None)
        current.update(changes)
        if history_entry:
            current['history'].append(dict(created=time.time(), **history_entry))
            changes['history'] = current['history']
        columns = list(changes)
        if columns:
            store._db.execute('UPDATE attempts SET ' + ','.join(k + '=?' for k in columns)
                + ' WHERE task_id=? AND attempt_id=?',
                tuple(encoded(current[k]) if k in store._json_columns['attempts'] else current[k]
                      for k in columns) + (current['task_id'], current['attempt_id']))
            store._event('attempts', current)
    return current


class Jobs:
    def __init__(self, store, jobq_bin=JOBQ_BIN, jobq_dir=None):
        self.store = store
        self.jobq_bin = Path(jobq_bin).resolve()
        # Default = the host's shared supervisor queue (jobq's own default, <repo>/lab/jobq), so
        # factory gpu/build jobs are serialized with every other GPU/build job on the host and
        # served by the running worker. A private queue would have no worker and no exclusivity.
        self.jobq_dir = Path(jobq_dir or os.environ.get('JOBQ_DIR')
                             or self.jobq_bin.parents[1] / 'lab' / 'jobq').resolve()

    @contextmanager
    def locked(self):
        with (self.store.home / 'jobs.lock').open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def _qdir(self, attempt):
        # Reconcile an attempt against the queue it was submitted to (recorded before launch),
        # not whatever queue this Jobs instance defaults to now.
        return Path((attempt.get('resources') or {}).get('jobq_dir') or self.jobq_dir)

    def _call(self, *args, env_extra=None, qdir=None):
        env = dict(os.environ, **(env_extra or {}))
        env.update(JOBQ_DIR=str(qdir or self.jobq_dir),
                   PATH='/usr/local/cuda/bin:' + env.get('PATH', os.defpath),
                   DOCKER_CMD_PREFIX=DOCKER_PREFIX)
        return subprocess.run([sys.executable, str(self.jobq_bin), *map(str, args)],
            env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True)

    def _get(self, attempt_id):
        row = self.store._db.execute('SELECT * FROM attempts WHERE attempt_id=?', (attempt_id,)).fetchone()
        if row is None:
            raise NotFound('Attempt not found')
        return self.store._decode('attempts', row)

    def _recover(self, attempt):
        if attempt['jobq_id']:
            return attempt
        # The unique name is persisted before launch. Recover the acknowledgement
        # after a submitter crash; jobq has no idempotency key of its own.
        for path in self._qdir(attempt).glob('job-*.json'):
            job = json.loads(path.read_text())
            if job['name'] == 'factory:' + attempt['attempt_id']:
                return metadata(self.store, attempt, jobq_id=job['id'])
        return attempt

    def submit(self, task_id, kind, request: dict, idem_key: str, job_class, argv,
               timeout_s, env_extra):
        if not isinstance(idem_key, str) or not idem_key.strip():
            raise ValueError('idem_key must be nonempty')
        if job_class not in {'build', 'gpu', 'cpu'} or not argv:
            raise ValueError('Invalid job class or argv')
        if not math.isfinite(timeout_s) or timeout_s < 0:
            raise ValueError('Invalid timeout')
        argv = list(map(str, argv))
        fp = fingerprint(kind, request, argv, job_class, timeout_s)
        with self.locked():
            row = self.store._db.execute('SELECT * FROM attempts WHERE task_id=? AND idem_key=?',
                                        (task_id, idem_key)).fetchone()
            if row:
                attempt = self.store._decode('attempts', row)
                if attempt['fingerprint'] != fp:
                    raise KeyConflict('Idempotency key names different inputs')
                return self._recover(attempt)
            attempt = self.store.create_attempt(task_id, dict(kind=kind, request=request,
                idem_key=idem_key, fingerprint=fp, resources=dict(argv=argv,
                job_class=job_class, timeout_s=timeout_s, jobq_dir=str(self.jobq_dir))))
            actual = [arg.replace('{attempt_id}', attempt['attempt_id']) for arg in argv]
            try:
                jid = self._call('submit', '--class', job_class, '--name',
                    'factory:' + attempt['attempt_id'], '--timeout', timeout_s, '--', *actual,
                    env_extra=env_extra).stdout.strip()
            except subprocess.CalledProcessError as exc:
                reason = (exc.stderr or '')[-2000:]
                return self.store.transition_attempt(task_id, attempt['attempt_id'], 'failed',
                    resources=dict(attempt['resources'], submit_error=reason, error=reason))
            except (OSError, subprocess.TimeoutExpired):
                # Submission may have reached jobq even if its acknowledgement
                # was lost. Preserve identity and reconcile, never blindly retry.
                attempt = self._recover(attempt)
                if attempt['jobq_id']:
                    return attempt
                return self.store.transition_attempt(task_id, attempt['attempt_id'], 'unknown')
            return metadata(self.store, attempt, jobq_id=jid)

    def status(self, attempt_id):
        with self.locked():
            attempt = self._recover(self._get(attempt_id))
            if not attempt['jobq_id']:
                job = None
            else:
                try:
                    job = json.loads(self._call('show', attempt['jobq_id'], qdir=self._qdir(attempt)).stdout)
                except subprocess.CalledProcessError:
                    if (self._qdir(attempt) / (attempt['jobq_id'] + '.json')).exists():
                        raise
                    job = None
            if job is None:
                return attempt
            state = job['state']
            detail = state
            if state in {'timeout', 'skipped_dep_failed'}:
                state = 'failed'
            if state not in TERMINAL | {'queued', 'running'}:
                state = 'unknown'
            if job and job.get('stop_reason') == 'cancelled' and state == 'running':
                state = 'cancel_requested'
            if attempt['state'] == 'cancel_requested' and state in {'queued', 'running'}:
                state = 'cancel_requested'
            changes = {}
            if job:
                changes['owner'] = {key: job.get(key) for key in ('pid', 'pgid', 'wrapper_pgid', 'runner_pid')}
                changes['resources'] = dict(attempt['resources'], jobq_state=detail, rc=job.get('rc'),
                                            error=job.get('error'))
                if state in TERMINAL:
                    changes['cleanup_state'] = self._cleanup(job)
            # A fast command may finish between polls. F02 requires observing
            # the intervening running state before queued -> succeeded.
            if attempt['state'] == 'queued' and state == 'succeeded':
                attempt = self.store.transition_attempt(attempt['task_id'], attempt_id, 'running')
            if attempt['state'] == 'running' and state == 'cancelled':
                attempt = self.store.transition_attempt(attempt['task_id'], attempt_id, 'cancel_requested')
            if attempt['state'] != state and attempt['state'] not in TERMINAL:
                attempt = self.store.transition_attempt(attempt['task_id'], attempt_id, state, **changes)
            elif changes and any(attempt[k] != v for k, v in changes.items()):
                attempt = metadata(self.store, attempt, **changes)
            if detail in {'timeout', 'skipped_dep_failed'} and not any(h.get('detail') == detail for h in attempt['history']):
                attempt = metadata(self.store, attempt, history_entry={'detail': detail})
            return attempt

    @staticmethod
    def _cleanup(job):
        groups = {job.get('pgid'), job.get('wrapper_pgid')} - {None}
        for path in Path('/proc').glob('[0-9]*/stat'):
            try:
                stat = path.read_text().rsplit(')', 1)[1].split()
                if int(stat[2]) in groups:
                    return 'process_group_remaining'
            except (OSError, ValueError, IndexError):
                continue
        # jobq reaps command process groups; it does not prove Docker daemon
        # cleanup. Never run its global container reaper against unrelated jobs.
        return 'process_groups_reaped;containers_unverified'

    def cancel(self, attempt_id, timeout_s=CANCEL_TIMEOUT):
        attempt = self.status(attempt_id)
        if attempt['state'] in TERMINAL:
            return attempt
        if attempt['state'] != 'cancel_requested':
            attempt = self.store.transition_attempt(attempt['task_id'], attempt_id, 'cancel_requested')
        if not attempt['jobq_id']:
            return self.status(attempt_id)
        self._call('cancel', attempt['jobq_id'], qdir=self._qdir(attempt))
        deadline = time.monotonic() + timeout_s
        while True:
            attempt = self.status(attempt_id)
            if attempt['state'] in TERMINAL | {'unknown'} or time.monotonic() >= deadline:
                return attempt
            time.sleep(.05)

    def retry(self, attempt_id, new_idem_key):
        attempt = self.status(attempt_id)
        if attempt['state'] not in TERMINAL:
            raise ValueError('Retry requires an observed terminal attempt')
        if new_idem_key == attempt['idem_key']:
            raise KeyConflict('Retry requires a new idempotency key')
        r = attempt['resources']
        env = {}
        job_path = self._qdir(attempt) / (attempt['jobq_id'] + '.json')
        if job_path.exists():
            job = json.loads(job_path.read_text())
            if job.get('env_file'):
                env = json.loads(Path(job['env_file']).read_text())
        if attempt['kind'] == 'build':
            env.update(attempt['request'].get('env', {}), FACTORY_HOME=str(self.store.home))
        result = self.submit(attempt['task_id'], attempt['kind'], attempt['request'], new_idem_key,
                             r['job_class'], r['argv'], r['timeout_s'], env)
        if not any(h.get('retry_of') == attempt_id for h in result['history']):
            result = metadata(self.store, result, history_entry={'retry_of': attempt_id})
        return result

    def result(self, attempt_id):
        attempt = self.status(attempt_id)
        return dict(attempt_id=attempt_id, state=attempt['state'],
                    result_refs=attempt['result_refs'] if attempt['state'] == 'succeeded' else [])
