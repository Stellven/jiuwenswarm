"""Uninstalled Root composition for the existing permanent-UID Library child.

All paths and mappings are installation inputs. No browser field selects a
module, executable, environment, command, package path or callback.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

from .cc_rsi_operator import RootOperatorEngine, validate_operator_policy
from .cc_rsi_projection import ProjectionError, _fields, _hash, _ref


def _root_path(value, *, directory=False, leaf_uid=0):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise ProjectionError('Literal absolute installed operator path required')
    for entry in (path, *path.parents):
        info = entry.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != (leaf_uid if entry == path else 0) or info.st_mode & 0o022:
            raise ProjectionError('Installed operator path custody differs')
        if entry != path and not stat.S_ISDIR(info.st_mode):
            raise ProjectionError('Installed operator ancestry differs')
    info = path.stat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ProjectionError('Installed operator path type differs')
    return str(path)


class ProtectedLibraryComposition:
    """Finite subprocess adapter; instantiate only in a separate Linux Root broker.

    The interpreter must contain the installed Root-owned jiuwenswarm package.
    Isolated Python ignores user site/PYTHONPATH and imports that installation.
    Each invocation enters library_operator.operator_identity then permanently
    drops all real/effective/saved identities to UID/GID10001 before store access.
    """
    def __init__(self, policy, *, python, bindings_path, config_path, state_root, timeout=3600, python_sha256=None):
        if os.name != 'posix' or os.geteuid() != 0:
            raise ProjectionError('Separate installed Linux OS Root composition required')
        if type(timeout) is not int or not 1 <= timeout <= 3600:
            raise ProjectionError('Finite Library child timeout required')
        self.policy = copy.deepcopy(validate_operator_policy(policy))
        self.workspace_id = self.policy.get('workspace_id')
        self.python = _root_path(python)
        if python_sha256 is not None:
            _hash(python_sha256)
            if hashlib.sha256(Path(self.python).read_bytes()).hexdigest()!=python_sha256:
                raise ProjectionError('Installed Library interpreter bytes differ')
        self.environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'JIUWENSWARM_M1_PROFILE': '1',
            'JIUWENSWARM_M1_BOOTSTRAP_BINDINGS': _root_path(bindings_path),
            'JIUWENSWARM_M1_CONFIG': _root_path(config_path),
            'JIUWENSWARM_M1_STATE': _root_path(state_root, directory=True, leaf_uid=10001),
            'JIUWENSWARM_M1_RSI_INBOX': '/var/lib/ai4r-rsi-inbox'}
        # SQLiteRunStore uses this fixed native input root after UID10001 drop.
        # An absent directory cannot be created on the broker's read-only rootfs.
        _root_path('/workspace/input', directory=True, leaf_uid=10001)
        self.timeout = timeout
        self.mapping = {}
        for digest, candidate in self.policy['candidates'].items():
            for action, command in (('admit', 'admit-rsi'), ('activate', 'standing')):
                ref = candidate[action + '_request_ref']
                if ref is None: continue
                key = (command, json.dumps(ref, sort_keys=True, separators=(',', ':')))
                if key in self.mapping:
                    raise ProjectionError('Each installed Library request must name one exact candidate action')
                self.mapping[key] = (digest, candidate['node_id'])

    def _invoke(self, command, request_ref, *, preflight):
        _ref(request_ref)
        raw_ref = json.dumps(request_ref, sort_keys=True, separators=(',', ':'))
        subject = self.mapping.get((command, raw_ref))
        if subject is None:
            raise ProjectionError('Library action is outside the installed exact candidate mapping')
        digest, node_id = subject
        arguments = [self.python, '-I', '-m', 'jiuwenswarm.research.library_operator', command,
                     '--request-ref', raw_ref, '--cc-candidate-hash', digest, '--cc-node-id', node_id]
        if preflight: arguments.append('--preflight-only')
        if self.workspace_id is not None: arguments.extend(['--cc-workspace-id',self.workspace_id])
        # No shell, inherited descriptors, app environment or app working tree.
        # Timeout/abnormal exit is uncertain delivery; Root's prior durable claim
        # remains unresolved and cannot be replayed.
        with tempfile.TemporaryFile() as output:
            child = subprocess.Popen(arguments, cwd='/', env=self.environment, stdin=subprocess.DEVNULL,
                                     stdout=output, stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True)
            try:
                code = child.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()
                raise ProjectionError('Library child timed out; reconcile without replay') from None
            output.seek(0); raw = output.read(65537)
        if code != 0 or len(raw) > 65536:
            raise ProjectionError('Protected Library terminal acknowledgement unavailable')
        try:
            result = json.loads(raw)
            _fields(result, 'status request_ref candidate_hash' if preflight else
                    'status request_ref candidate_hash operator_receipt_ref')
            _hash(result['candidate_hash'])
            if result['candidate_hash'] != digest or result['request_ref'] != request_ref:
                raise ProjectionError('Library terminal subject differs')
            expected = 'eligible' if preflight else 'admitted_inactive' if command == 'admit-rsi' else 'activated'
            if result['status'] != expected:
                raise ProjectionError('Library terminal state differs')
            if not preflight: _ref(result['operator_receipt_ref'])
            return result
        except (ValueError, KeyError, TypeError):
            raise ProjectionError('Protected Library terminal acknowledgement invalid') from None

    def preflight(self, action, digest, request_ref):
        command = {'admit': 'admit-rsi', 'activate': 'standing'}.get(action)
        subject = self.mapping.get((command, json.dumps(request_ref, sort_keys=True, separators=(',', ':'))))
        if subject is None or subject[0] != digest:
            raise ProjectionError('Preflight differs from installed candidate mapping')
        self._invoke(command, request_ref, preflight=True)
        return True

    def execute(self, command, request_ref):
        return self._invoke(command, request_ref, preflight=False)

    def engine(self, gateway_public_key, journal):
        return RootOperatorEngine(copy.deepcopy(self.policy), gateway_public_key, journal, self.preflight, self.execute)
