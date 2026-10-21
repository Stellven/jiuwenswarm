"""Persistent local input storage, independent of research execution authority."""
from __future__ import annotations

import hashlib
import ipaddress
from urllib.parse import urlsplit

from .contracts import ResearchError
from .intake import extract_document
from .uploads import UploadManager

LOCAL_UPLOAD_BYTES = 20 * 1024 * 1024
LOCAL_EXTRACTION_SECONDS = 30


def initialize_local_inputs(store, *, account_id: str, origin: str):
    """Explicit launcher opt-in; no policy, admission or model state is created."""
    try:
        loopback = ipaddress.ip_address(urlsplit(origin).hostname).is_loopback
    except (ValueError, TypeError):
        loopback = False
    if not loopback:
        raise ResearchError('local_workspace_origin', 'Local input workspace requires a loopback origin')
    for kind in ('docs', 'repo', 'datasets'):
        directory = store.input_root / kind / 'local'
        if directory.is_symlink() or directory.parent.is_symlink():
            raise ResearchError('local_workspace_storage', 'Local input storage cannot contain symbolic links')
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    identity = hashlib.sha256(account_id.encode('utf-8')).hexdigest()[:32]
    store.append_record('local-input-workspace', {
        'id': 'local-input-workspace:' + identity,
        'schema': 'local-input-workspace:1', 'account_id': account_id,
        'workspace_id': 'local', 'max_upload_bytes': LOCAL_UPLOAD_BYTES,
        'extraction_timeout_s': LOCAL_EXTRACTION_SECONDS,
        'execution_authority': False,
    })
    return UploadManager(store, store.input_root, extract_document,
                         extraction_timeout_s=LOCAL_EXTRACTION_SECONDS,
                         max_upload_bytes=LOCAL_UPLOAD_BYTES)
