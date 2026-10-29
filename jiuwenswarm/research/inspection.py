"""Immutable, audience-scoped export construction; no experiment dispatch."""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import PurePosixPath, PureWindowsPath

from .contracts.types import ResearchError
from .state import json_bytes
from .contracts import validate


def safe_named_path(path: str) -> bool:
    if (not isinstance(path, str) or not path or '\\' in path
            or re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*', path) is None):
        return False
    p = PurePosixPath(path)
    return (not p.is_absolute() and not PureWindowsPath(path).drive and all(
        part not in {'.', '..'} and re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', part) for part in p.parts))


def build_retrieval(store, principal, run_id: str, run_account_id: str, audience: str, files, *, allowed_refs,
                    redactor=None, include_contents=True):
    principal.require('export')
    if run_account_id != principal.account_id:
        raise ResearchError('not_found', 'Run is unavailable')
    if audience not in {'researcher', 'reviewer'} or audience not in principal.audiences:
        raise ResearchError('auth', 'Audience is outside the grant', {'http_status': 403})
    # The protected caller derives allowed_refs from the owned run's evidence;
    # possession of an arbitrary Ref does not create retrieval authority.
    allowed = {(r['id'], r['sha256']) for r in allowed_refs}
    returned, contents, redactions, paths = [], {}, [], set()
    for file in files:
        path = file.get('path')
        if not safe_named_path(path) or path in paths:
            raise ResearchError('validation', 'Unsafe or duplicate export path')
        paths.add(path)
        if file.get('audience') != audience:
            redactions.append('An artifact is withheld for this audience.')
            continue
        ref = file['artifact_ref']
        if (ref['id'], ref['sha256']) not in allowed:
            redactions.append('An artifact is outside the owned run evidence scope.')
            continue
        raw = store.read_blob(ref)
        if hashlib.sha256(raw).hexdigest() != ref['sha256']:
            raise ResearchError('internal', 'Stored artifact identity mismatch')
        item = {key: file[key] for key in ['path', 'artifact_ref', 'media_type', 'audience']}
        if redactor is not None:
            replacement, reason = redactor(path, raw)
            if replacement is None:
                redactions.append(reason or 'An artifact is withheld by disclosure policy.')
                continue
            if replacement != raw:
                if not isinstance(replacement, bytes):
                    raise ResearchError('internal', 'Invalid disclosure transformation')
                item['artifact_ref'] = store.put_blob(replacement, media_type=file['media_type'],
                                                    provenance={'redacted_from': ref, 'reason': reason})
                redactions.append(reason or 'An artifact has an explicitly redacted identity.')
                raw = replacement
        returned.append(item)
        if include_contents: contents[path] = raw
    refs, seen_refs = [], set()
    for item in returned:
        key = (item['artifact_ref']['id'], item['artifact_ref']['sha256'])
        if key not in seen_refs:
            seen_refs.add(key)
            refs.append(item['artifact_ref'])
    manifest = {'schema_version': '1.0.0', 'run_id': run_id, 'artifact_refs': refs,
                'audience': audience, 'files': returned, 'redactions': redactions}
    manifest['id'] = 'retrieval:' + hashlib.sha256(json_bytes(manifest)).hexdigest()
    return manifest, contents


def encode_export_zip(manifest: dict, contents: dict[str, bytes]) -> bytes:
    """M1-I011 representation of the existing authorized export operation."""
    validate('client-retrieval', manifest)
    files = manifest['files']
    paths = [f['path'] for f in files]
    if (len(paths) != len(set(paths)) or set(paths) != set(contents) or 'client_retrieval.json' in paths
            or any(not safe_named_path(path) for path in paths)):
        raise ResearchError('validation', 'Export path inventory is invalid')
    allowed = {(ref['id'], ref['sha256']) for ref in manifest['artifact_refs']}
    for file in files:
        raw = contents[file['path']]
        if (not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != file['artifact_ref']['sha256']
                or file['audience'] != manifest['audience']
                or (file['artifact_ref']['id'], file['artifact_ref']['sha256']) not in allowed):
            raise ResearchError('internal', 'Export byte identity or audience differs from its manifest')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path, raw in [('client_retrieval.json', json_bytes(manifest)), *sorted(contents.items())]:
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16; info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    return output.getvalue()
