"""Factory persistence. Public methods return detached JSON-compatible records.

Fault callbacks receive a stage string: before_commit (every mutation), and
artifact_temp_fsynced, artifact_renamed, artifact_dir_fsynced (new blobs).
A failed commit never returns an acknowledgement. Unreferenced blobs left by a
process crash are harmless: evidence becomes visible only through SQLite.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import uuid


class FactoryError(Exception):
    code = 'INVALID_INPUT'


class ScopeDenied(FactoryError):
    code = 'SCOPE_DENIED'


class StaleRevision(FactoryError):
    code = 'STALE_REVISION'


class ArtifactConflict(FactoryError):
    code = 'ARTIFACT_CONFLICT'


class NotFound(FactoryError):
    code = 'NOT_FOUND'


class PersistenceFailed(FactoryError):
    code = 'PERSISTENCE_FAILED'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def identifier(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Expected a nonempty identifier')
    return value


# Column declarations also define the JSON serialization boundary.
TABLES = {
    'tasks': ('task_id', 'task_id TEXT PRIMARY KEY, objective TEXT NOT NULL, constraints JSON NOT NULL, allowed_effects JSON NOT NULL, target JSON NOT NULL, budget JSON NOT NULL, revision INTEGER NOT NULL, current_decision_rev INTEGER NOT NULL, evidence_cursor INTEGER NOT NULL, created REAL NOT NULL'),
    'decisions': ('decision_id', 'decision_id TEXT NOT NULL, task_id TEXT NOT NULL REFERENCES tasks(task_id), rev INTEGER NOT NULL, parent_rev INTEGER NOT NULL, evidence_ids JSON NOT NULL, observations JSON NOT NULL, hypothesis TEXT NOT NULL, uncertainty TEXT NOT NULL, action JSON NOT NULL, expected_evidence TEXT NOT NULL, budget JSON NOT NULL, stop_condition TEXT NOT NULL, reason_for_change TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(task_id, decision_id), UNIQUE(task_id, rev)'),
    'artifacts': ('artifact_id', 'artifact_id TEXT NOT NULL, task_id TEXT NOT NULL REFERENCES tasks(task_id), sha256 TEXT NOT NULL, size INTEGER NOT NULL, media_type TEXT NOT NULL, producer_attempt TEXT, location TEXT NOT NULL, complete INTEGER NOT NULL, created REAL NOT NULL, PRIMARY KEY(task_id, artifact_id)'),
    'observations': ('obs_id', 'obs_id TEXT NOT NULL, task_id TEXT NOT NULL REFERENCES tasks(task_id), source_artifacts JSON NOT NULL, kind TEXT NOT NULL, "values" JSON NOT NULL, error JSON NOT NULL, host_run JSON NOT NULL, confidence REAL, limitations TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(task_id, obs_id)'),
    'attempts': ('attempt_id', 'attempt_id TEXT NOT NULL, task_id TEXT NOT NULL REFERENCES tasks(task_id), kind TEXT NOT NULL, idem_key TEXT NOT NULL, fingerprint TEXT NOT NULL, request JSON NOT NULL, state TEXT NOT NULL, jobq_id TEXT, owner JSON NOT NULL, started REAL, ended REAL, resources JSON NOT NULL, result_refs JSON NOT NULL, cleanup_state TEXT NOT NULL, history JSON NOT NULL, PRIMARY KEY(task_id, attempt_id), UNIQUE(task_id, idem_key)'),
    'evaluations': ('eval_id', 'eval_id TEXT NOT NULL, task_id TEXT NOT NULL REFERENCES tasks(task_id), contract_id TEXT NOT NULL, contract_version TEXT NOT NULL, contract JSON NOT NULL, inputs JSON NOT NULL, execution_outcome TEXT NOT NULL, correctness TEXT NOT NULL, evidence_completeness TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(task_id, eval_id)'),
    'uploads': ('upload_id', 'upload_id TEXT NOT NULL, task_id TEXT NOT NULL REFERENCES tasks(task_id), lab_run_id TEXT NOT NULL, sha256 TEXT NOT NULL, ack_state TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(task_id, upload_id)'),
}
TASK_INPUTS = {
    'contract_id': "TEXT NOT NULL DEFAULT ''",
    'initial_run_config': "JSON NOT NULL DEFAULT '{}'",
    'component_cc': "TEXT NOT NULL DEFAULT ''",
    'source': "JSON NOT NULL DEFAULT '{}'",
    'operator_labels': "JSON NOT NULL DEFAULT '{}'",
}
TYPES = {name[:-1] if name != 'observations' else 'observation': name for name in TABLES}
STATES = frozenset({'queued', 'running', 'succeeded', 'failed', 'cancel_requested', 'cancelled', 'unknown'})
TRANSITIONS = {
    'queued': {'running', 'failed', 'cancel_requested', 'cancelled', 'unknown'},
    'running': {'succeeded', 'failed', 'cancel_requested', 'unknown'},
    'cancel_requested': {'cancelled', 'succeeded', 'failed', 'unknown'},
    'unknown': {'queued', 'running', 'succeeded', 'failed', 'cancel_requested', 'cancelled'},
    'succeeded': set(), 'failed': set(), 'cancelled': set(),
}


class Store:
    def __init__(self, home: Path, fault=None):
        self.home = Path(home).expanduser().resolve()
        self.home.mkdir(parents=True, exist_ok=True)
        self.fault = fault
        self._db = sqlite3.connect(self.home / 'factory.sqlite', timeout=30, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute('PRAGMA journal_mode=WAL')
        self._db.execute('PRAGMA synchronous=FULL')
        self._db.execute('PRAGMA foreign_keys=ON')
        # Schema initialization is itself one transaction, without fault injection.
        with self._transaction(inject=False):
            for table, (_, columns) in TABLES.items():
                self._db.execute(f'CREATE TABLE IF NOT EXISTS {table} ({columns})')
            self._db.execute('CREATE TABLE IF NOT EXISTS builder_reuse_keys (task_id TEXT NOT NULL, idem_key TEXT NOT NULL, fingerprint TEXT NOT NULL, attempt_id TEXT NOT NULL, PRIMARY KEY(task_id, idem_key))')
            columns = {r['name'] for r in self._db.execute('PRAGMA table_info(tasks)')}
            for name, declaration in TASK_INPUTS.items():
                if name not in columns:
                    self._db.execute(f'ALTER TABLE tasks ADD COLUMN {name} {declaration}')
            self._db.execute('CREATE TABLE IF NOT EXISTS evidence (cursor INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES tasks(task_id), id TEXT NOT NULL, type TEXT NOT NULL, kind TEXT NOT NULL, summary TEXT NOT NULL, created REAL NOT NULL, record JSON NOT NULL)')
            self._db.execute('CREATE INDEX IF NOT EXISTS evidence_task_cursor ON evidence(task_id, cursor)')
            for table in ('observations', 'artifacts', 'decisions', 'evaluations'):
                for operation in ('UPDATE', 'DELETE'):
                    self._db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable record'); END")
        self._json_columns = {table: {row['name'] for row in self._db.execute(f'PRAGMA table_info({table})') if row['type'] == 'JSON'} for table in TABLES}

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _fault(self, stage):
        if self.fault:
            try:
                self.fault(stage)
            except Exception as exc:
                raise PersistenceFailed(f'Persistence interrupted at {stage}') from exc

    @contextmanager
    def _transaction(self, inject=True):
        self._telemetry_pending = []
        try:
            self._db.execute('BEGIN IMMEDIATE')
            yield
            if inject:
                self._fault('before_commit')
            self._db.commit()
            try:
                from .telemetry import record
                for table, value in self._telemetry_pending:
                    record(self.home, table, value)
            except Exception:
                # Observability must never turn a committed mutation into a failure.
                pass
        except Exception as exc:
            if self._db.in_transaction:
                self._db.rollback()
            if isinstance(exc, (sqlite3.OperationalError, OSError)):
                raise PersistenceFailed('Store persistence failed') from exc
            if isinstance(exc, sqlite3.IntegrityError):
                raise ValueError('Duplicate or invalid record') from exc
            raise

    def _decode(self, table, row):
        result = dict(row)
        for key in self._json_columns[table]:
            result[key] = json.loads(result[key])
        if table == 'artifacts':
            result['complete'] = bool(result['complete'])
        return result

    def _get(self, table, task_id, record_id):
        identifier(task_id)
        identifier(record_id)
        key = TABLES[table][0]
        row = self._db.execute(f'SELECT * FROM {table} WHERE task_id=? AND {key}=?', (task_id, record_id)).fetchone()
        if row is None:
            raise NotFound('Record not found')
        return self._decode(table, row)

    def get_task(self, task_id):
        return self._get('tasks', task_id, task_id)

    def _insert(self, table, record):
        columns = {row['name'] for row in self._db.execute(f'PRAGMA table_info({table})')}
        if set(record) - columns:
            raise ValueError('Unknown record fields: ' + ', '.join(sorted(set(record) - columns)))
        values = {key: encoded(value) if key in self._json_columns[table] else value for key, value in record.items()}
        quoted_columns = ','.join('"' + column + '"' for column in values)
        self._db.execute(f'INSERT INTO {table} ({quoted_columns}) VALUES ({",".join("?" for _ in values)})', tuple(values.values()))
        self._event(table, record)
        return record

    def _event(self, table, record):
        # Snapshot now: later metadata edits must not alter committed telemetry.
        previous = self._db.execute('SELECT record FROM evidence WHERE task_id=? AND id=? ORDER BY cursor DESC LIMIT 1',
                                    (record['task_id'], str(record[TABLES[table][0]]))).fetchone()
        if table != 'attempts' or previous is None or json.loads(previous[0]).get('state') != record.get('state'):
            self._telemetry_pending.append((table, json.loads(encoded(record))))
        type_name = next(k for k, v in TYPES.items() if v == table)
        record_id = str(record[TABLES[table][0]])
        summary = str(record.get('hypothesis', record.get('objective', record.get('values', record.get('sha256', record.get('state', ''))))))[:300]
        cursor = self._db.execute('INSERT INTO evidence(task_id,id,type,kind,summary,created,record) VALUES (?,?,?,?,?,?,?)', (record['task_id'], record_id, type_name, record.get('kind', type_name), summary, time.time(), encoded(record))).lastrowid
        self._db.execute('UPDATE tasks SET evidence_cursor=? WHERE task_id=?', (cursor, record['task_id']))

    def create_task(self, record):
        record = dict(record)
        identifier(record.get('task_id'))
        identifier(record.get('objective'))
        defaults = dict(constraints={}, allowed_effects=[], target={}, budget={}, revision=1, current_decision_rev=0, evidence_cursor=0, created=time.time())
        if any(record.get(key, 0) != 0 for key in ('current_decision_rev', 'evidence_cursor')):
            raise ValueError('New tasks must start at decision revision and cursor zero')
        with self._transaction():
            self._insert('tasks', defaults | record)
            result = self.get_task(record['task_id'])
        return result

    def scoped(self, task_id, readable=frozenset()):
        return ScopedStore(self, identifier(task_id), frozenset(identifier(t) for t in readable))

    def validate_evidence(self, task_id, refs, readable=()):
        if not isinstance(refs, list) or not all(isinstance(ref, str) and ref for ref in refs):
            raise ValueError('evidence_ids must be a list of nonempty ids')
        for ref in refs:
            if not any(self._db.execute('SELECT 1 FROM evidence WHERE task_id=? AND id=?',
                       (target, ref)).fetchone() for target in (task_id, *readable)):
                raise ValueError('Unknown or inaccessible evidence id: ' + ref)

    def advance_decision(self, task_id, expected_rev, record, *, readable=()):
        if type(expected_rev) is not int or expected_rev < 0:
            raise ValueError('expected_rev must be a nonnegative integer')
        record = dict(record)
        if record.get('task_id', task_id) != task_id:
            raise ScopeDenied('Decision belongs to another task')
        protected = {'rev': expected_rev + 1, 'parent_rev': expected_rev, 'task_id': task_id}
        if any(key in record and record[key] != value for key, value in protected.items()):
            raise ValueError('Decision revision and task identity are host-controlled')
        with self._transaction():
            if self.get_task(task_id)['current_decision_rev'] != expected_rev:
                raise StaleRevision('Current decision revision differs from expected_rev')
            self.validate_evidence(task_id, record.get('evidence_ids', []), readable)
            result = self._insert('decisions', dict(decision_id=f'{task_id}:decision:{expected_rev + 1}', evidence_ids=[], observations=[], hypothesis='', uncertainty='', action={}, expected_evidence='', budget={}, stop_condition='', reason_for_change='', created=time.time()) | record | protected)
            self._db.execute('UPDATE tasks SET current_decision_rev=? WHERE task_id=?', (expected_rev + 1, task_id))
        return result

    def _append(self, table, task_id, record, defaults):
        record = dict(record)
        if 'task_id' in record and record['task_id'] != task_id:
            raise ScopeDenied('Record belongs to another task')
        key = TABLES[table][0]
        identifier(record.get(key, defaults.get(key)))
        with self._transaction():
            self.get_task(task_id)
            result = self._insert(table, defaults | record | {'task_id': task_id})
        return result

    def append_observation(self, task_id, record):
        return self._append('observations', task_id, record, dict(obs_id=uuid.uuid4().hex, source_artifacts=[], kind='measurement', values={}, error={}, host_run={}, confidence=None, limitations='', created=time.time()))

    def add_evaluation(self, task_id, record):
        return self._append('evaluations', task_id, record, dict(eval_id=uuid.uuid4().hex, created=time.time()))

    def add_upload(self, task_id, record):
        return self._append('uploads', task_id, record, dict(upload_id=uuid.uuid4().hex, created=time.time()))

    def create_attempt(self, task_id, record):
        if record.get('state', 'queued') != 'queued':
            raise ValueError('New attempts start queued')
        return self._append('attempts', task_id, record, dict(attempt_id=uuid.uuid4().hex, state='queued', jobq_id=None, owner={}, started=None, ended=None, resources={}, result_refs=[], cleanup_state='pending', history=[{'state': 'queued', 'created': time.time()}]))

    def transition_attempt(self, task_id, attempt_id, state, *, expected_state=None, **changes):
        if not isinstance(state, str) or state not in STATES:
            raise ValueError('Unknown attempt state')
        allowed = {'jobq_id', 'owner', 'started', 'ended', 'resources', 'result_refs', 'cleanup_state'}
        if set(changes) - allowed:
            raise ValueError('Attempt identity, request and history are immutable')
        with self._transaction():
            result = self._get('attempts', task_id, attempt_id)
            previous = result['state']
            if expected_state is not None and expected_state != previous:
                raise StaleRevision('Attempt state differs from expected_state')
            if state not in TRANSITIONS[previous]:
                raise ValueError(f'Invalid attempt transition: {previous} -> {state}')
            result.update(changes, state=state)
            now = time.time()
            if state == 'running' and result['started'] is None:
                result['started'] = now
            if state in {'succeeded', 'failed', 'cancelled'}:
                result['ended'] = now
            result['history'].append({'state': state, 'previous': previous, 'created': now})
            columns = ['state', 'history', 'started', 'ended', *sorted(set(changes) - {'started', 'ended'})]
            self._db.execute(f'UPDATE attempts SET {",".join(c + "=?" for c in columns)} WHERE task_id=? AND attempt_id=?', tuple(encoded(result[c]) if c in self._json_columns['attempts'] else result[c] for c in columns) + (task_id, attempt_id))
            self._event('attempts', result)
        return result

    @staticmethod
    def _fsync_dir(path):
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def put_artifact(self, task_id, artifact_id, data, media_type, producer_attempt):
        """data is bytes or a filesystem path; the returned location is store-relative."""
        artifact_id = identifier(artifact_id) if artifact_id is not None else uuid.uuid4().hex
        identifier(media_type)
        if producer_attempt is not None:
            if not isinstance(producer_attempt, (str, int)):
                raise ValueError('producer_attempt must be an identifier or attempt number')
            producer_attempt = str(producer_attempt)
        if not isinstance(data, (bytes, str, os.PathLike)):
            raise ValueError('Artifact data must be bytes or a path')
        installed = None
        temp = None
        try:
            with self._transaction():
                self.get_task(task_id)
                root = self.home / 'artifacts'
                root.mkdir(exist_ok=True)
                self._fsync_dir(self.home)
                fd, name = tempfile.mkstemp(prefix='.pending-', dir=root)
                temp = Path(name)
                digest = hashlib.sha256()
                size = 0
                with os.fdopen(fd, 'wb') as output:
                    if isinstance(data, bytes):
                        output.write(data)
                        digest.update(data)
                        size = len(data)
                    else:
                        with Path(data).open('rb') as source:
                            for block in iter(lambda: source.read(1024 * 1024), b''):
                                output.write(block)
                                digest.update(block)
                                size += len(block)
                    output.flush()
                    os.fsync(output.fileno())
                self._fault('artifact_temp_fsynced')
                sha256 = digest.hexdigest()
                try:
                    existing = self._get('artifacts', task_id, artifact_id)
                except NotFound:
                    existing = None
                if existing is not None:
                    if existing['sha256'] != sha256:
                        raise ArtifactConflict('Artifact id already names different bytes')
                    self.read_artifact(task_id, artifact_id)
                    result = existing
                else:
                    location = Path('artifacts') / sha256[:2] / sha256
                    destination = self.home / location
                    destination.parent.mkdir(exist_ok=True)
                    self._fsync_dir(root)
                    if destination.exists():
                        self._verify_blob(destination, sha256, size)
                    else:
                        os.replace(temp, destination)
                        temp = None
                        installed = destination
                        self._fault('artifact_renamed')
                    self._fsync_dir(destination.parent)
                    self._fault('artifact_dir_fsynced')
                    result = self._insert('artifacts', dict(artifact_id=artifact_id, task_id=task_id, sha256=sha256, size=size, media_type=media_type, producer_attempt=producer_attempt, location=location.as_posix(), complete=True, created=time.time()))
            return result
        except Exception:
            # BEGIN IMMEDIATE prevents another writer from adopting an uncommitted blob.
            # Do not remove a blob if a later writer has already referenced it.
            if installed is not None:
                with self._transaction(inject=False):
                    if not self._db.execute('SELECT 1 FROM artifacts WHERE sha256=?', (installed.name,)).fetchone():
                        installed.unlink(missing_ok=True)
                        self._fsync_dir(installed.parent)
            raise
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)

    @staticmethod
    def _verify_blob(path, sha256, size, preview_limit=0):
        digest = hashlib.sha256()
        preview = bytearray()
        length = 0
        try:
            with path.open('rb') as source:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(block)
                    length += len(block)
                    preview.extend(block[:max(0, preview_limit - len(preview))])
        except OSError as exc:
            raise PersistenceFailed('Artifact bytes unavailable') from exc
        if digest.hexdigest() != sha256 or length != size:
            raise PersistenceFailed('Artifact integrity check failed')
        return bytes(preview)

    def read_artifact(self, task_id, artifact_id):
        record = self._get('artifacts', task_id, artifact_id)
        self._verify_blob(self.home / record['location'], record['sha256'], record['size'])
        return record

    def artifact_bytes(self, task_id, artifact_id):
        record = self._get('artifacts', task_id, artifact_id)
        return self._verify_blob(self.home / record['location'], record['sha256'], record['size'], record['size'])

    def read(self, task_id, record_id):
        """Read a full record; artifacts include a verified, at most 64 KiB preview."""
        for table, (key, _) in TABLES.items():
            row = self._db.execute(f'SELECT * FROM {table} WHERE task_id=? AND {key}=?', (task_id, record_id)).fetchone()
            if row is not None:
                record = self._decode(table, row)
                if table == 'artifacts':
                    preview = self._verify_blob(self.home / record['location'], record['sha256'], record['size'], 65536)
                    # Replacement characters can expand invalid UTF-8. Bound the
                    # encoded preview as well as the source bytes.
                    record['text_preview'] = preview.decode('utf-8', errors='replace').encode('utf-8')[:65536].decode('utf-8', errors='ignore')
                    record['preview_truncated'] = record['size'] > 65536
                return record
        raise NotFound('Record not found')

    def query(self, task_id, *, kinds=None, text=None, since=0, limit=50):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError('limit must be 1..50')
        if type(since) is not int or since < 0:
            raise ValueError('since must be a nonnegative integer')
        if kinds is not None and (not isinstance(kinds, list) or not all(isinstance(k, str) for k in kinds)):
            raise ValueError('kinds must be a list of strings')
        if text is not None and not isinstance(text, str):
            raise ValueError('text must be a string')
        self.get_task(task_id)
        clauses, params = ['task_id=?', 'cursor>?'], [task_id, since]
        if kinds:
            placeholders = ','.join('?' for _ in kinds)
            clauses.append(f'(kind IN ({placeholders}) OR type IN ({placeholders}))')
            params.extend(kinds + kinds)
        if text:
            clauses.append('instr(lower(record),lower(?))>0')
            params.append(text)
        rows = self._db.execute('SELECT cursor,id,type,kind,summary,created FROM evidence WHERE ' + ' AND '.join(clauses) + ' ORDER BY cursor LIMIT ?', (*params, limit)).fetchall()
        # Refuse to answer from a task whose evidence has been tampered with.
        for (artifact_id,) in self._db.execute('SELECT artifact_id FROM artifacts WHERE task_id=?', (task_id,)).fetchall():
            self.read_artifact(task_id, artifact_id)
        return {'items': [{k: row[k] for k in ('id', 'type', 'kind', 'summary', 'created')} for row in rows], 'cursor': rows[-1]['cursor'] if rows else since}

    def dump(self, task_id):
        self.get_task(task_id)
        result = {}
        for table in TABLES:
            records = [self._decode(table, row) for row in self._db.execute(f'SELECT * FROM {table} WHERE task_id=?', (task_id,))]
            if table == 'artifacts':
                for record in records:
                    self._verify_blob(self.home / record['location'], record['sha256'], record['size'])
            result[table] = records
        return result


class ScopedStore:
    """Read grants never grant writes. Every public operation takes an explicit task id."""
    def __init__(self, store, task_id, readable):
        self._store, self.task_id, self.readable = store, task_id, readable

    def _check(self, task_id, write=False):
        if task_id != self.task_id and (write or task_id not in self.readable):
            raise ScopeDenied('Task is outside the authorized scope')

    def get_task(self, task_id):
        self._check(task_id)
        return self._store.get_task(task_id)

    def query(self, task_id, **filters):
        self._check(task_id)
        return self._store.query(task_id, **filters)

    def read(self, task_id, record_id):
        self._check(task_id)
        return self._store.read(task_id, record_id)

    def dump(self, task_id):
        self._check(task_id)
        return self._store.dump(task_id)

    def read_artifact(self, task_id, artifact_id):
        self._check(task_id)
        return self._store.read_artifact(task_id, artifact_id)

    def artifact_bytes(self, task_id, artifact_id):
        self._check(task_id)
        return self._store.artifact_bytes(task_id, artifact_id)

    def create_task(self, record):
        self._check(record.get('task_id'), write=True)
        return self._store.create_task(record)

    def advance_decision(self, task_id, expected_rev, record):
        self._check(task_id, write=True)
        return self._store.advance_decision(task_id, expected_rev, record, readable=self.readable)

    def _agent_id(self, value):
        if value is None:
            return
        identifier(value)
        prefixes = ['admission', *(r[0] for r in self._store._db.execute('SELECT attempt_id FROM attempts'))]
        if ':' in value or any(value.startswith(prefix) for prefix in prefixes):
            raise ScopeDenied('Evidence id is reserved for the host')

    def put_artifact(self, task_id, artifact_id, data, media_type, producer_attempt):
        self._agent_id(artifact_id)
        self._check(task_id, write=True)
        return self._store.put_artifact(task_id, artifact_id, data, media_type, producer_attempt)

    def append_observation(self, task_id, record):
        self._agent_id(record.get('obs_id'))
        if 'host_run' in record or record.get('kind') in {'build_result', 'lab_result', 'evaluation', 'admission', 'operator_intervention'}:
            raise ScopeDenied('Observation fields are reserved for the host')
        self._check(task_id, write=True)
        return self._store.append_observation(task_id, record)

    def create_attempt(self, task_id, record):
        self._check(task_id, write=True)
        return self._store.create_attempt(task_id, record)

    def transition_attempt(self, task_id, attempt_id, state, *, expected_state=None, **changes):
        self._check(task_id, write=True)
        return self._store.transition_attempt(task_id, attempt_id, state, expected_state=expected_state, **changes)

    def add_evaluation(self, task_id, record):
        self._check(task_id, write=True)
        return self._store.add_evaluation(task_id, record)

    def add_upload(self, task_id, record):
        self._check(task_id, write=True)
        return self._store.add_upload(task_id, record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path(os.environ.get('FACTORY_HOME', '~/.jiuwenswarm-factory')).expanduser())
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init-task').add_argument('file', type=Path)
    sub.add_parser('show').add_argument('task_id')
    sub.add_parser('dump').add_argument('task_id')
    args = parser.parse_args()
    with Store(args.home) as store:
        if args.command == 'init-task':
            result = store.create_task(json.loads(args.file.read_text()))
        elif args.command == 'show':
            result = store.get_task(args.task_id)
        else:
            result = store.dump(args.task_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
