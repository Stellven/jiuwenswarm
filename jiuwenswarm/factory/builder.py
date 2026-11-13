"""Validated Builder submissions; compilation runs entirely under jobq."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from .jobs import Jobs, KeyConflict, fingerprint
from .store import encoded

from .config import ENGINE, RECIPE, JOBQ_BIN, BUILD_TIMEOUT
# Explicit environment inputs affecting compilation. Credentials never enter receipts.
ENV_KEYS = {'PATH', 'LD_LIBRARY_PATH', 'BUILD_JOBS', 'CC', 'CXX', 'CUDAHOSTCXX',
            'CUDACXX', 'CUDA_HOME', 'CUDA_PATH', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS',
            'CCACHE_DIR', 'CCACHE_BASEDIR', 'CCACHE_COMPILERCHECK', 'CCACHE_NOHASHDIR',
            'FACTORY_BUILD_ENGINE', 'BASE_RUNTIME'}


class Builder:
    def __init__(self, store, jobq_bin=JOBQ_BIN, jobq_dir=None):
        self.store = store
        self.jobs = Jobs(store, jobq_bin, jobq_dir)

    def _request(self, request):
        if not isinstance(request, dict) or request.get('target') != 'jetson-orin':
            raise ValueError('target must be jetson-orin')
        if set(request) - {'target', 'source', 'patch', 'tag', 'deadline_s', 'env'}:
            raise ValueError('Unknown build request fields')
        source = request['source']
        path = Path(source['path']).expanduser().resolve()
        def git(*args):
            return subprocess.run(['git', '-C', str(path), *args], check=True,
                stdin=subprocess.DEVNULL, capture_output=True, text=True).stdout.strip()
        try:
            commit = git('rev-parse', 'HEAD')
            if commit != source['commit'] or git('status', '--porcelain', '--untracked-files=all'):
                raise ValueError('Source must be clean and HEAD must equal commit')
            tree = git('rev-parse', 'HEAD^{tree}')
        except subprocess.CalledProcessError as exc:
            raise ValueError('Source must be a git repository') from exc
        if not isinstance(request.get('tag'), str) or not re.fullmatch(r'factory/llamacpp:[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}', request['tag']):
            raise ValueError('tag must use factory/llamacpp namespace')
        deadline = request.get('deadline_s') or BUILD_TIMEOUT
        if isinstance(deadline, bool) or not isinstance(deadline, (int, float)) or not math.isfinite(deadline) or deadline <= 0:
            raise ValueError('deadline_s must be positive and finite')
        extra = request.get('env', {})
        if not isinstance(extra, dict) or set(extra) - ENV_KEYS or not all(isinstance(v, str) for v in extra.values()):
            raise ValueError('Invalid build environment')
        env = {key: os.environ[key] for key in ENV_KEYS if key in os.environ}
        operator_path = env.get('PATH', os.defpath)
        env.update(extra)
        # Normalize the actual environment jobq will capture. A requested PATH goes first but
        # cannot drop the operator's toolchain directories (cmake/ninja may live outside /usr/bin).
        parts = env.get('PATH', operator_path).split(os.pathsep) + operator_path.split(os.pathsep)
        env['PATH'] = os.pathsep.join(dict.fromkeys(p for p in parts if p))
        engine = Path(env.get('FACTORY_BUILD_ENGINE', ENGINE)).resolve()
        normalized = dict(target='jetson-orin', source=dict(path=str(path), commit=commit, tree=tree),
            tag=request['tag'], deadline_s=deadline, env=env,
            engine_sha256=hashlib.sha256(engine.read_bytes()).hexdigest(),
            recipe_sha256=hashlib.sha256(RECIPE.read_bytes()).hexdigest())
        if request.get('patch'):
            patch = Path(request['patch']).expanduser().resolve()
            normalized.update(patch=str(patch), patch_sha256=hashlib.sha256(patch.read_bytes()).hexdigest())
        return normalized

    def submit(self, task_id, request, idem_key, node_id=None):
        self.store.get_task(task_id)
        if not isinstance(idem_key, str) or not idem_key.strip():
            raise ValueError('idem_key must be nonempty')
        request = self._request(request)
        if node_id is not None:
            request['node_id'] = node_id
        # Stable request path and argv keep attempt identity out of its fingerprint.
        digest = hashlib.sha256(encoded(request).encode()).hexdigest()
        root = self.store.home / 'requests'
        root.mkdir(exist_ok=True)
        request_path = root / (digest + '.json')
        if not request_path.exists():
            fd, name = tempfile.mkstemp(dir=root)
            with os.fdopen(fd, 'w') as stream:
                json.dump(request, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, request_path)
        argv = [sys.executable, '-m', 'jiuwenswarm.factory.build_job', '--task', task_id,
                '--attempt', '{attempt_id}', '--request', str(request_path)]
        fp = fingerprint('build', request, argv, 'build', request['deadline_s'])
        # Reconcile matching jobs before deciding whether completed output can
        # be reused. No caller needs to have polled their success previously.
        candidates = self.store._db.execute("SELECT attempt_id FROM attempts WHERE task_id=? AND kind='build' AND fingerprint=?", (task_id, fp)).fetchall()
        for candidate in candidates:
            self.jobs.status(candidate['attempt_id'])
        # Reuse is task-local and limited to observed successful output.
        with self.jobs.locked():
            alias = self.store._db.execute('SELECT * FROM builder_reuse_keys WHERE task_id=? AND idem_key=?', (task_id, idem_key)).fetchone()
            if alias:
                if alias['fingerprint'] != fp:
                    raise KeyConflict('Idempotency key names different inputs')
                return self.jobs._get(alias['attempt_id'])
            keyed = self.store._db.execute('SELECT fingerprint FROM attempts WHERE task_id=? AND idem_key=?', (task_id, idem_key)).fetchone()
            if keyed and keyed['fingerprint'] != fp:
                raise KeyConflict('Idempotency key names different inputs')
            if not keyed:
                rows = self.store._db.execute("SELECT * FROM attempts WHERE task_id=? AND kind='build' AND fingerprint=? AND state='succeeded'", (task_id, fp)).fetchall()
                if rows:
                    result = self.store._decode('attempts', rows[0])
                    with self.store._transaction():
                        self.store._db.execute('INSERT INTO builder_reuse_keys VALUES (?,?,?,?)',
                            (task_id, idem_key, fp, result['attempt_id']))
                    return result
        env = dict(request['env'], FACTORY_HOME=str(self.store.home))
        return self.jobs.submit(task_id, 'build', request, idem_key, 'build', argv, request['deadline_s'], env)

    def status(self, attempt_id):
        return self.jobs.status(attempt_id)

    def cancel(self, attempt_id):
        return self.jobs.cancel(attempt_id)

    def result(self, attempt_id):
        return self.jobs.result(attempt_id)
