"""Fixed optional in-container selector process; no selector implementation import.

D44 requires independently killable local selection. Its absence or failure
leaves the core's audited fixed route available. This launcher supplies no
provider credential, application store, account directory or hidden fixture.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys

from .contracts import validate

ROUTER_UID = 10011
ROUTING_GID = 13100
EXPORT_ROOT = '/run/ai4r-routing/public'
AUDIT_ROOT = '/var/lib/ai4r-router'
SOCKET_PATH = '/run/ai4r-router/router.sock'


class RouterStartupError(RuntimeError):
    pass


def validate_router_config(value):
    fields = {'socket_path', 'audit_root', 'allowed_peer_uids', 'data_roots', 'catalog_ref',
              'profile_refs', 'development_profiles_ref', 'adapter_revision', 'ref_index_path'}
    if not isinstance(value, dict) or set(value) != fields:
        raise RouterStartupError('ROUTER_CONFIGURATION_INVALID')
    if (value['socket_path'] != SOCKET_PATH or value['audit_root'] != AUDIT_ROOT
            or value['data_roots'] != [EXPORT_ROOT] or value['allowed_peer_uids'] != [10001]
            or value['ref_index_path'] != EXPORT_ROOT + '/ref-index.json'
            or not isinstance(value['adapter_revision'], str) or not value['adapter_revision']
            or not isinstance(value['profile_refs'], list) or not value['profile_refs']):
        raise RouterStartupError('ROUTER_AUTHORITY_INVALID')
    for pin in [value['catalog_ref'], value['development_profiles_ref'], *value['profile_refs']]:
        try: validate('Ref', pin)
        except Exception: raise RouterStartupError('ROUTER_REFERENCE_INVALID') from None
    return value


def router_environment(environ):
    allowed = {'PATH', 'LANG', 'LC_ALL', 'TZ', 'PYTHONUTF8'}
    return {**{key: value for key, value in environ.items() if key in allowed},
            'PYTHONUNBUFFERED': '1', 'PYTHONDONTWRITEBYTECODE': '1'}


def _root_config(path):
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise RouterStartupError('ROUTER_CONFIGURATION_CUSTODY_INVALID')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_nlink != 1
                or metadata.st_mode & 0o022 or metadata.st_size > 65536):
            raise RouterStartupError('ROUTER_CONFIGURATION_CUSTODY_INVALID')
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            return validate_router_config(json.load(stream))
    finally: os.close(descriptor)


def _identity():
    os.setgroups([])
    os.setgid(ROUTING_GID)
    os.setuid(ROUTER_UID)


class OptionalRouter:
    def __init__(self, process, log):
        self.process, self.log = process, log

    @classmethod
    def start(cls, environ):
        config_path = environ.get('JIUWENSWARM_M1_ROUTER_CONFIG')
        if not config_path: return None
        if os.geteuid() != 0: raise RouterStartupError('ROUTER_LAUNCHER_IDENTITY_INVALID')
        _root_config(config_path)
        from .bootstrap import _directory, clear_stale_socket
        _directory('/run/ai4r-routing', uid=0, gid=0, mode=0o711)
        _directory(EXPORT_ROOT, uid=10001, gid=ROUTING_GID, mode=0o2750)
        _directory(AUDIT_ROOT, uid=ROUTER_UID, gid=ROUTING_GID, mode=0o2750)
        _directory(Path(SOCKET_PATH).parent, uid=ROUTER_UID, gid=ROUTING_GID, mode=0o2750)
        clear_stale_socket(SOCKET_PATH, uid=ROUTER_UID, mode=0o660)
        # Only fixed command and allowlisted environment cross the identity
        # boundary. The selector itself scrubs its environment again.
        log_path = Path(AUDIT_ROOT) / 'process.log'
        descriptor = os.open(log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o640)
        try:
            meta = os.fstat(descriptor)
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
                raise RouterStartupError('ROUTER_LOG_CUSTODY_INVALID')
            os.fchown(descriptor, ROUTER_UID, ROUTING_GID); os.fchmod(descriptor, 0o640)
            log = os.fdopen(descriptor, 'ab', buffering=0); descriptor = None
            try:
                process = subprocess.Popen([sys.executable, '-m', 'jiuwenswarm.research_router',
                    'serve', '--config', str(config_path)], env=router_environment(environ),
                    cwd=AUDIT_ROOT, preexec_fn=_identity, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=log, close_fds=True)
                return cls(process, log)
            except BaseException:
                log.close(); raise
        finally:
            if descriptor is not None: os.close(descriptor)

    def close(self):
        try:
            if self.process.poll() is None:
                self.process.terminate()
                try: self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait(timeout=2)
        finally:
            if self.log is not None: self.log.close()
