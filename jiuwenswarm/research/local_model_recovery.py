"""Offline operator acknowledgement of historical unknowns; never retries a call.

This is a private operator capability, intentionally absent from the relay RPC.
The acknowledgement authorizes distinct new work and makes no provider-terminal
claim. Local process containment must be investigated before invoking this CLI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from .contracts.types import ResearchError
from . import local_model_relay

SCHEMA = 'ai4r-unknown-acknowledgement:1'
MAX_EVIDENCE = 1024 * 1024
MAX_SNAPSHOT = 64 * 1024 * 1024
FIELDS = {'schema', 'request_id', 'payload_sha256', 'result_sha256',
          'ledger_snapshot_sha256', 'ledger_file_sha256', 'evidence_sha256',
          'operator_note', 'recorded_at', 'local_processes_contained',
          'provider_status', 'authorization'}


def private_path(path, **options):
    return local_model_relay.private_path(path, **options)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class RuntimeLock:
    """One relay or offline operator per private runtime, including across processes."""
    def __init__(self, runtime):
        self.fd = None
        target = Path(runtime) / 'relay.lock'
        private_path(runtime, directory=True)
        fd = os.open(target, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            private_path(target)
            if os.name == 'posix':
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                # Fixture support on Windows; production custody requires Linux.
                import msvcrt
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b'\0')
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            self.fd = fd
        except Exception:
            os.close(fd)
            raise ResearchError('ENVIRONMENT_BLOCKED') from None

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()


def read_private(path, limit):
    private_path(path)
    if path.stat().st_size > limit:
        raise ResearchError('ENVIRONMENT_BLOCKED')
    raw = path.read_bytes()
    if len(raw) > limit:
        raise ResearchError('ENVIRONMENT_BLOCKED')
    return raw


def paths(runtime, request_id):
    directory = Path(runtime) / 'unknown-acknowledgements'
    stem = sha(request_id.encode('utf-8'))
    return directory, directory / (stem + '.json'), directory / (stem + '.snapshot'), directory / (stem + '.evidence')


def decode(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('duplicate field')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))


def acknowledged_unknown(runtime, row):
    """Fail closed on missing, stale, corrupted, or differently bound acknowledgements."""
    try:
        request_id, digest, result = row
        if result is None or decode(result).get('outcome') != 'outcome_unknown':
            return False
        directory, acknowledgement, snapshot, evidence = paths(runtime, request_id)
        if not directory.exists():
            return False
        private_path(directory, directory=True)
        value = decode(read_private(acknowledgement, 16384))
        if (not isinstance(value, dict) or set(value) != FIELDS
                or value['schema'] != SCHEMA or value['request_id'] != request_id
                or value['payload_sha256'] != digest
                or value['result_sha256'] != sha(result.encode('utf-8'))
                or value['local_processes_contained'] is not True
                or value['provider_status'] != 'unknown'
                or value['authorization'] != 'distinct-new-work-only'
                or not isinstance(value['operator_note'], str)
                or not 1 <= len(value['operator_note'].strip()) <= 2048
                or not isinstance(value['recorded_at'], str)):
            return False
        for key in ('payload_sha256', 'result_sha256', 'ledger_snapshot_sha256',
                    'ledger_file_sha256', 'evidence_sha256'):
            if not isinstance(value[key], str) or not re.fullmatch('[0-9a-f]{64}', value[key]):
                return False
        datetime.fromisoformat(value['recorded_at'])
        snapshot_raw = read_private(snapshot, MAX_SNAPSHOT)
        evidence_raw = read_private(evidence, MAX_EVIDENCE)
        if (sha(snapshot_raw) != value['ledger_snapshot_sha256']
                or sha(evidence_raw) != value['evidence_sha256'] or not evidence_raw):
            return False
        frozen = decode(snapshot_raw)
        return (isinstance(frozen, dict) and set(frozen) == {'schema', 'ledger_file_sha256', 'requests'}
                and frozen['schema'] == 'ai4r-request-ledger-snapshot:1'
                and frozen['ledger_file_sha256'] == value['ledger_file_sha256']
                and isinstance(frozen['requests'], list)
                and [request_id, digest, result] in frozen['requests'])
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ResearchError):
        return False


def acknowledge(runtime, request_id, payload_sha256, evidence_file, operator_note, *,
                authorize_new_work=False, confirm_local_process_containment=False,
                acknowledge_provider_status_unknown=False):
    if (not authorize_new_work or not confirm_local_process_containment
            or not acknowledge_provider_status_unknown
            or not isinstance(request_id, str) or not 1 <= len(request_id) <= 128
            or not re.fullmatch('[0-9a-f]{64}', payload_sha256)
            or not isinstance(operator_note, str) or not 1 <= len(operator_note.strip()) <= 2048):
        raise ResearchError('invalid_request')
    runtime = Path(runtime)
    with RuntimeLock(runtime):
        ledger = runtime / 'requests.sqlite3'
        ledger_raw = read_private(ledger, MAX_SNAPSHOT)
        # Existing only: do not create/migrate the ledger or change any result.
        with closing(sqlite3.connect(ledger.as_uri() + '?mode=ro', uri=True)) as db:
            rows = db.execute('SELECT id,digest,result FROM requests ORDER BY id').fetchall()
        row = next((row for row in rows if row[0] == request_id), None)
        if (row is None or row[1] != payload_sha256 or row[2] is None
                or decode(row[2]).get('outcome') != 'outcome_unknown'):
            raise ResearchError('invalid_request')
        evidence = read_private(Path(evidence_file), MAX_EVIDENCE)
        if not evidence:
            raise ResearchError('invalid_request')
        directory, target, snapshot_path, evidence_path = paths(runtime, request_id)
        directory.mkdir(mode=0o700, exist_ok=True)
        private_path(directory, directory=True)
        if any(path.exists() or path.is_symlink() for path in (target, snapshot_path, evidence_path)):
            raise ResearchError('ENVIRONMENT_BLOCKED')
        snapshot = canonical({'schema': 'ai4r-request-ledger-snapshot:1',
                              'ledger_file_sha256': sha(ledger_raw), 'requests': rows})
        if len(snapshot) > MAX_SNAPSHOT:
            raise ResearchError('ENVIRONMENT_BLOCKED')
        value = dict(schema=SCHEMA, request_id=request_id, payload_sha256=payload_sha256,
                     result_sha256=sha(row[2].encode('utf-8')),
                     ledger_snapshot_sha256=sha(snapshot), ledger_file_sha256=sha(ledger_raw),
                     evidence_sha256=sha(evidence), operator_note=operator_note.strip(),
                     recorded_at=datetime.now(timezone.utc).isoformat(),
                     local_processes_contained=True, provider_status='unknown',
                     authorization='distinct-new-work-only')
        # Publish authority last. A crash before it leaves no accepted acknowledgement.
        local_model_relay.LocalModelRelay._write_once(snapshot_path, snapshot)
        local_model_relay.LocalModelRelay._write_once(evidence_path, evidence)
        local_model_relay.LocalModelRelay._write_once(target, canonical(value))
        if not acknowledged_unknown(runtime, row):
            raise ResearchError('ENVIRONMENT_BLOCKED')
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--request-id', required=True)
    parser.add_argument('--payload-sha256', required=True)
    parser.add_argument('--evidence-file', required=True, help='Private mode-0600 containment observations')
    parser.add_argument('--operator-note', required=True)
    parser.add_argument('--authorize-new-work', action='store_true')
    parser.add_argument('--confirm-local-process-containment', action='store_true')
    parser.add_argument('--acknowledge-provider-status-unknown', action='store_true')
    args = vars(parser.parse_args())
    value = acknowledge(**{key.replace('-', '_'): item for key, item in args.items()})
    print(json.dumps(value, sort_keys=True))


if __name__ == '__main__':
    main()
