"""Host-only immutable observations for exploratory development campaigns.

This stores evidence and measurements, not product acceptance. Original Harbor
grading remains authoritative for its own scope. No inference occurs here.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import io
import math
import os
from pathlib import Path
import re
import uuid

from .contracts import canonical, read_json, regular, strict_json

IDENT = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}\Z")
SENSITIVE = {'authorization', 'api_key', 'access_token', 'refresh_token', 'id_token',
             'password', 'client_secret', 'account_fingerprint', 'auth_json'}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def public_record(value):
    """Reject credential-shaped fields; never dump environment or auth stores."""
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower().replace('-', '_') in SENSITIVE:
                raise ValueError('credential field is not campaign evidence: ' + str(key))
            public_record(item)
    elif isinstance(value, list):
        for item in value:
            public_record(item)
    elif isinstance(value, str):
        if re.search(r'(?i)(?:bearer\s+[a-z0-9._~-]{12,}|research_bootstrap=\S+|sk-[a-z0-9_-]{20,})', value):
            raise ValueError('credential-shaped text is not campaign evidence')
    canonical(value)  # Reject unsupported types and non-finite measurements.
    return value


def write_once(path, value, *, raw=False):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink evidence path refused')
    data = value if raw else canonical(value)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if os.name != 'nt':
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def csv_bytes(rows, columns):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        cells = {}
        for key in columns:
            value = row.get(key)
            if isinstance(value, (dict, list)):
                value = canonical(value).decode()
            text = '' if value is None else str(value)
            cells[key] = "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r')) else text
        writer.writerow(cells)
    return stream.getvalue().encode('utf-8-sig')


class Dataset:
    """One new file per observation; no shared append stream or mutable scores."""

    def __init__(self, root):
        self.root = Path(root).absolute()
        if any(p.is_symlink() for p in (self.root, *self.root.parents)):
            raise ValueError('symlink dataset refused')
        for name in ('records', 'artifacts', 'claims'):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    def artifact(self, path):
        path = regular(path)
        raw = path.read_bytes()
        return self.json_artifact(raw)

    def json_artifact(self, raw):
        """Retain exact UTF-8 JSON bytes from an explicitly validated export."""
        if not isinstance(raw, bytes) or len(raw) > 16 * 1024 * 1024:
            raise ValueError('bounded original JSON bytes required')
        # Only explicit JSON benchmark exports, never arbitrary logs/auth files.
        public_record(strict_json(raw))
        digest = hashlib.sha256(raw).hexdigest()
        target = self.root / 'artifacts' / (digest + '.json')
        try:
            write_once(target, raw, raw=True)
        except FileExistsError:
            if regular(target).read_bytes() != raw:
                raise ValueError('content-addressed artifact changed') from None
        return {'sha256': digest, 'size': len(raw), 'path': 'artifacts/' + target.name}

    def append(self, kind, value, *, record_id=None):
        if not IDENT.fullmatch(kind):
            raise ValueError('invalid record kind')
        ident = record_id or uuid.uuid4().hex
        if not IDENT.fullmatch(ident):
            raise ValueError('invalid record ID')
        record = {'schema': 'ai4r-value-record:1', 'id': ident, 'kind': kind,
                  'recorded_at': utc_now(), 'value': public_record(value)}
        write_once(self.root / 'records' / (ident + '.json'), record)
        return record

    def records(self):
        records = []
        for path in sorted((self.root / 'records').glob('*.json')):
            row = read_json(regular(path))
            if (row.get('schema') != 'ai4r-value-record:1' or row.get('id') != path.stem
                    or not IDENT.fullmatch(row.get('kind', ''))):
                raise ValueError('invalid dataset record')
            public_record(row)
            self._validate_artifacts(row)
            records.append(row)
        return records

    def _validate_artifacts(self, value):
        if isinstance(value, dict):
            if set(value) == {'path', 'sha256', 'size'} and str(value['path']).startswith('artifacts/'):
                if not re.fullmatch(r'artifacts/[a-f0-9]{64}\.json', value['path']):
                    raise ValueError('invalid retained artifact path')
                raw = regular(self.root / value['path']).read_bytes()
                if len(raw) != value['size'] or hashlib.sha256(raw).hexdigest() != value['sha256']:
                    raise ValueError('retained artifact changed')
            for item in value.values():
                self._validate_artifacts(item)
        elif isinstance(value, list):
            for item in value:
                self._validate_artifacts(item)

    def snapshot(self):
        files = []
        for folder in ('records', 'artifacts', 'claims'):
            for path in sorted((self.root / folder).glob('*.json')):
                raw = regular(path).read_bytes()
                files.append({'path': path.relative_to(self.root).as_posix(),
                              'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)})
        return {'schema': 'ai4r-value-snapshot:1', 'files': files,
                'sha256': hashlib.sha256(canonical(files)).hexdigest()}

    def mirror(self, destination):
        """Copy a stable snapshot without overwriting or deleting either copy."""
        self.records()  # Validate retained source references before copying.
        target = Dataset(destination)
        if target.root.is_relative_to(self.root) or self.root.is_relative_to(target.root):
            raise ValueError('dataset mirror must have a separate root')
        before = self.snapshot()
        for item in before['files']:
            source = regular(self.root / item['path'])
            raw = source.read_bytes()
            if hashlib.sha256(raw).hexdigest() != item['sha256'] or len(raw) != item['size']:
                raise ValueError('source changed during mirror')
            path = target.root / item['path']
            try:
                write_once(path, raw, raw=True)
            except FileExistsError:
                if regular(path).read_bytes() != raw:
                    raise ValueError('mirror contains different retained bytes; never overwrite') from None
        if self.snapshot() != before:
            raise ValueError('source changed during mirror; partial copy retained without a completed snapshot')
        target.records()
        snapshot_path = target.root / ('snapshot-' + before['sha256'] + '.json')
        try:
            write_once(snapshot_path, before)
        except FileExistsError:
            if read_json(snapshot_path) != before:
                raise ValueError('mirror snapshot differs') from None
        return {'snapshot_sha256': before['sha256'], 'files': len(before['files']), 'destination': str(target.root)}
