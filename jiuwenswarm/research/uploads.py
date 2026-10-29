"""Controlled upload validation; core owns publication, active use and deletion."""
from __future__ import annotations

import asyncio
import hashlib
import io
import re
import secrets
import stat
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath

from jiuwenswarm.research.contracts.types import Principal, ResearchError


class UploadManager:
    def __init__(self, store, root: str | Path, extractor, *, extraction_timeout_s: float,
                 max_upload_bytes: int | None = None):
        if extraction_timeout_s <= 0:
            raise ValueError('a positive protected extraction deadline is required')
        self.store = store
        self.root = Path(root).resolve()
        self.extractor = extractor
        self.timeout = extraction_timeout_s
        self.max_bytes = max_upload_bytes

    @staticmethod
    def _archive(data: bytes) -> None:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set()
                for entry in archive.infolist():
                    name = entry.filename
                    normalized = name.replace('\\', '/')
                    p = PurePosixPath(normalized)
                    if (not name or p.is_absolute() or PureWindowsPath(name).drive or '..' in p.parts
                            or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1
                            or normalized in names or '\x00' in name):
                        raise ResearchError('validation', 'Archive contains an unsafe member')
                    names.add(normalized)
        except (zipfile.BadZipFile, RuntimeError) as exc:
            raise ResearchError('validation', 'Repository upload must be a readable ZIP') from exc

    async def upload(self, principal: Principal, kind: str, scope_id: str, filename: str, data: bytes) -> dict:
        principal.require('upload')
        if (kind not in {'docs', 'repo', 'datasets'} or not isinstance(filename, str)
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', filename)
                or not isinstance(scope_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,63}', scope_id)
                or filename in {'.', '..'} or scope_id in {'.', '..'} or not isinstance(data, bytes)):
            raise ResearchError('validation', 'Invalid upload kind, scope or filename')
        if self.max_bytes is not None and len(data) > self.max_bytes:
            raise ResearchError('validation', 'Upload exceeds its protected size limit')
        extracted = None
        if kind == 'repo':
            if Path(filename).suffix.lower() != '.zip':
                raise ResearchError('validation', 'Repository upload requires a ZIP')
            self._archive(data)
        elif kind == 'docs':
            if Path(filename).suffix.lower() not in {'.txt', '.md', '.markdown', '.json', '.pdf'}:
                raise ResearchError('validation', 'Document type is unsupported')
            try:
                # The sole decoder is M1-003's canonical intake extractor.
                extracted = await asyncio.wait_for(self.extractor(filename, data, timeout_s=self.timeout), self.timeout)
                if not isinstance(extracted, bytes):
                    raise ValueError('extractor must return exact UTF8 bytes')
                extracted.decode('utf-8', errors='strict')
            except (TimeoutError, UnicodeError, ValueError) as exc:
                raise ResearchError('validation', 'Document extraction failed or exceeded its deadline') from exc
        destination = self.root / kind / scope_id / filename
        if not destination.is_relative_to(self.root) or any(p.is_symlink() for p in [destination, *destination.parents] if p.is_relative_to(self.root)):
            raise ResearchError('validation', 'Upload path is not permitted')
        record = {'schema_version': '1.0.0', 'id': 'upload:' + secrets.token_hex(16),
                  'user_id': principal.account_id, 'scope_id': scope_id, 'kind': kind,
                  'resource_type': {'docs': 'reference_document', 'repo': 'project_asset', 'datasets': 'validation_data'}[kind],
                  'filename': filename, 'size_bytes': len(data),
                  'stored_path': '/'.join(('workspace', 'input', kind, scope_id, filename)),
                  'content_sha256': hashlib.sha256(data).hexdigest(),
                  'text_sha256': hashlib.sha256(extracted).hexdigest() if extracted is not None else None,
                  'status': 'uploaded', 'uploaded_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                  'deleted_at': None}
        # No bytes are published before every validator/extractor succeeds.
        return self.store.publish_upload(record, data, extracted)

    def list(self, principal: Principal, scope_id: str) -> list[dict]:
        principal.require('list_uploads')
        return self.store.list_uploads(principal.account_id, scope_id)

    def delete(self, principal: Principal, upload_id: str) -> dict:
        principal.require('delete_upload')
        return self.store.delete_upload(upload_id, principal.account_id)
