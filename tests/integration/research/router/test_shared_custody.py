"""Actual app/router UID byte transfer under the production restrictive umask."""
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import tempfile

import pytest


def _as_identity(channel, uid, gid, groups, operation, root, pin=None):
    try:
        os.setgroups(groups); os.setgid(gid); os.setuid(uid); os.umask(0o077)
        root = Path(root)
        if operation == 'publish':
            from jiuwenswarm.research.state import SQLiteRunStore
            from jiuwenswarm.research.routing_authority import PublicRoutingExport
            store = SQLiteRunStore(root / 'state')
            pin = store.put_blob(b'{"actual_shared_capture":true}', record_id='opaque:shared')
            PublicRoutingExport(store, root / 'public').publish([pin])
            store.close(); channel.send(pin)
        elif operation == 'route':
            from jiuwenswarm.research_router.request_validation import ProtectedData
            from jiuwenswarm.research_router.engine import DecisionEngine
            data = ProtectedData([root / 'public'], ref_index_path=root / 'public/ref-index.json')
            assert data.read_json(pin) == {'actual_shared_capture': True}
            engine = DecisionEngine(data=data, validate=lambda *_: None,
                audit_root=root / 'audit', catalog_ref=pin, profile_refs=[],
                development_profiles_ref=pin, adapter_revision='custody-test:1')
            channel.send(engine.capture({'exact_request_ref': pin}))
        elif operation == 'read_audit':
            from jiuwenswarm.research.routing_authority import RoutingAuthority
            authority = RoutingAuthority.__new__(RoutingAuthority); authority.audit = root / 'audit'
            channel.send(authority.audit_record(pin))
        elif operation == 'forbidden_read':
            try: (root / 'public/ref-index.json').read_bytes()
            except PermissionError: channel.send('denied')
            else: raise AssertionError('unrelated UID read the protected publication')
    except BaseException as exc:
        channel.send({'error': type(exc).__name__, 'message': str(exc)})
    finally:
        channel.close()


def _invoke(uid, gid, groups, operation, root, pin=None):
    parent, child = multiprocessing.Pipe(duplex=False)
    process = multiprocessing.Process(target=_as_identity,
        args=(child, uid, gid, groups, operation, str(root), pin))
    process.start(); child.close()
    try:
        assert parent.poll(15), 'identity process did not complete'
        value = parent.recv()
        assert not (isinstance(value, dict) and 'error' in value), value
        process.join(5); assert process.exitcode == 0
        return value
    finally:
        if process.is_alive(): process.kill(); process.join(5)
        parent.close()


def test_app_and_router_exchange_exact_bytes_without_other_uid_read_access():
    if not hasattr(os, 'setuid') or os.geteuid() != 0:
        pytest.fail('BLOCKED: Linux root test driver with SETUID/SETGID/CHOWN required')
    root = Path(tempfile.mkdtemp(prefix='ai4r-router-custody-'))
    os.chmod(root, 0o711)
    try:
        for name, uid, gid, mode in [('state', 10001, 10001, 0o700),
                ('public', 10001, 13100, 0o2750), ('audit', 10011, 13100, 0o2750)]:
            path = root / name; path.mkdir(); os.chown(path, uid, gid); os.chmod(path, mode)
        source = _invoke(10001, 10001, [13100], 'publish', root)
        audit = _invoke(10011, 13100, [], 'route', root, source)
        assert _invoke(10001, 10001, [13100], 'read_audit', root, audit) == {'exact_request_ref': source}
        assert _invoke(10002, 10002, [], 'forbidden_read', root) == 'denied'
        for path in (root / 'public/sha256', root / 'audit/artifacts'):
            assert path.stat().st_gid == 13100
            assert path.stat().st_mode & 0o7777 == 0o2750
    finally:
        shutil.rmtree(root)
