"""Audience-scoped immutable collection snapshots; no dispatch or deletion."""
from __future__ import annotations

import hashlib
import uuid

from .contracts import ResearchError
from .state import json_bytes, utc_now


def owned_run(service, principal, run_id, audience):
    principal.require('export')
    run = service.store.get_run(run_id, account_id=principal.account_id)
    principal.require('export', run['workspace_id'])
    if audience not in principal.audiences or audience not in {'researcher', 'reviewer'}:
        raise ResearchError('auth')
    return run


def snapshot(service, principal, run_id, audience='researcher'):
    run = owned_run(service, principal, run_id, audience)
    retrieval, _ = service._artifact_bytes(principal, run_id, audience=audience, include_contents=False)
    artifacts = []
    for file in retrieval['files']:
        ref = file['artifact_ref']
        path = service.store.blobs.path_for(ref['sha256'])
        artifacts.append({'artifact_id': hashlib.sha256(json_bytes([file['path'], ref])).hexdigest(),
                          'path': file['path'], 'size': path.stat().st_size, 'sha256': ref['sha256'],
                          'media_type': file['media_type']})
    manifest = {'schema_version': '1.0.0', 'run_id': run_id, 'audience': audience,
                'artifacts': artifacts, 'redactions': retrieval['redactions'],
                'retention': {'policy': 'until_explicit_collection_confirmation', 'expires_at': None,
                              'automatic_deletion': False},
                'execution_terminal': run['state'] not in {'pending', 'running'}}
    digest = hashlib.sha256(json_bytes(manifest)).hexdigest()
    manifest['manifest_sha256'] = digest
    prior = list(service.store.iter_records(run_id=run_id, kinds=('collection-snapshot',)))
    if not any(row['record']['manifest']['manifest_sha256'] == digest for row in prior):
        service.store.append_record('collection-snapshot', {'id': 'collection-snapshot:' + uuid.uuid4().hex,
            'run_id': run_id, 'account_id': principal.account_id, 'workspace_id': run['workspace_id'],
            'manifest': manifest, 'retrieval': retrieval, 'captured_at': utc_now()})
    return manifest


def artifact_path(service, principal, run_id, artifact_id, audience='researcher'):
    owned_run(service, principal, run_id, audience)
    snapshots = service.store.iter_records(run_id=run_id, kinds=('collection-snapshot',))
    for row in snapshots:
        record = row['record']
        if record['manifest']['audience'] != audience: continue
        for item, original in zip(record['manifest']['artifacts'], record['retrieval']['files']):
            if item['artifact_id'] != artifact_id: continue
            ref = original['artifact_ref']
            path = service.store.blobs.path_for(ref['sha256'])
            if path.is_symlink() or not path.is_file(): raise ResearchError('unavailable')
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(64 * 1024), b''): digest.update(chunk)
            if digest.hexdigest() != item['sha256'] or path.stat().st_size != item['size']:
                raise ResearchError('internal')
            return path, item
    raise ResearchError('not_found')


def confirm(service, principal, run_id, value):
    if not isinstance(value, dict) or set(value) != {'manifest_sha256', 'artifacts', 'audience'}:
        raise ResearchError('validation')
    audience = value['audience']
    owned_run(service, principal, run_id, audience)
    rows = list(service.store.iter_records(run_id=run_id, kinds=('collection-snapshot',)))
    matches = [row['record']['manifest'] for row in rows if
               row['record']['manifest']['manifest_sha256'] == value['manifest_sha256'] and
               row['record']['manifest']['audience'] == audience]
    if not matches or matches[0]['artifacts'] != value['artifacts']:
        raise ResearchError('conflict')
    manifest = matches[0]
    # Receipt confirms only these bytes. Active runs can produce later artifacts.
    result = {'schema_version': '1.0.0', 'run_id': run_id, 'manifest_sha256': value['manifest_sha256'],
              'audience': audience, 'status': 'confirmed', 'confirmed_at': utc_now(),
              'retention': {'automatic_deletion': False, 'uncollected_artifacts_retained': True}}
    previous = [row['record'] for row in service.store.iter_records(run_id=run_id, kinds=('collection-confirmation',))
                if row['record']['receipt']['manifest_sha256'] == value['manifest_sha256'] and
                row['record']['receipt']['audience'] == audience]
    if previous: return previous[0]['receipt']
    service.store.append_record('collection-confirmation', {'id': 'collection-confirmation:' + uuid.uuid4().hex,
        'run_id': run_id, 'account_id': principal.account_id, 'receipt': result})
    return result
