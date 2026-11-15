"""Portable, read-only factory recordings with exact historical identities.

Only files consulted by the existing recording validator are retained. Each
original path maps explicitly to a SHA-256 addressed blob; paths are metadata,
never extraction destinations. Importing or opening a bundle cannot execute a
stage or construct a FactoryService.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any
import zipfile

from .replay_export import ReplayExportError, _read, load_recording
from .recorded_paths import historical_basename, historical_root, validate_historical_member


SCHEMA = 'ai4r.recording-bundle:1'
_DIGEST = re.compile(r'^[0-9a-f]{64}$')
_IDENTIFIER = re.compile(r'^[a-zA-Z0-9_-]{1,128}$')
_MAX_BUNDLE = 64 * 1024 * 1024
_MAX_MEMBER = 64 * 1024 * 1024
_MAX_CONTENT = 256 * 1024 * 1024
_MAX_MEMBERS = 8192


def default_recordings_directory() -> Path:
    return (Path(__file__).resolve().parents[2] / 'docs' / 'code' / 'Missions' /
            'software-factory' / 'recordings')


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(raw: bytes, label: str) -> Any:
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise ReplayExportError(f'Invalid {label}') from error


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _encode(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def export_recording(run_dir: str | Path, output: str | Path) -> dict:
    """Export validated real files without changing any original evidence."""
    root = Path(run_dir).resolve(strict=True)
    destination = Path(output).absolute()
    if destination.resolve().is_relative_to(root):
        raise ReplayExportError('Recording output must not modify the original run directory')
    blobs: dict[str, bytes] = {}
    path_map: dict[str, dict] = {}

    def capture(read_root, value, *, sha256=None, size=None):
        raw, original = _read(read_root, value, sha256=sha256, size=size)
        digest = _sha(raw)
        blobs[digest] = raw
        path_map[str(value)] = {'blob': f'blobs/{digest}', 'sha256': digest, 'size': len(raw)}
        return raw, original

    recording = load_recording(root, read_file=capture)
    run = recording['run']
    owner_id = run.get('request', {}).get('owner_id')
    if not _identifier(run['id']) or not isinstance(owner_id, str) or not owner_id:
        raise ReplayExportError('Recording requires an immutable run and owner identity')
    manifest = {'schema': SCHEMA, 'run_id': run['id'], 'owner_id': owner_id,
                'original_run_root': str(root), 'path_map': path_map,
                'provenance': recording['provenance'],
                'exported_at': datetime.now(timezone.utc).isoformat()}
    if any(len(raw) > _MAX_MEMBER for raw in blobs.values()) or sum(map(len, blobs.values())) > _MAX_CONTENT:
        raise ReplayExportError('Recording exceeds portable content limits')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.recording-', suffix='.zip',
                                         dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
            bundle.writestr('manifest.json', _encode(manifest))
            for digest, raw in sorted(blobs.items()):
                bundle.writestr(f'blobs/{digest}', raw)
        # The exported format must pass the same offline importer as a new clone.
        validated = _load_bundle(temporary)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {'output': str(destination), 'size': destination.stat().st_size,
            'sha256': validated['bundle_sha256'], **recording['provenance']}


def _load_bundle(path: Path) -> dict:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_BUNDLE:
            raise ReplayExportError('Invalid recording bundle file or size')
        bundle_raw = path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(bundle_raw)) as bundle:
            members = bundle.infolist()
            names = [member.filename for member in members]
            if (len(members) > _MAX_MEMBERS or len(set(names)) != len(names) or
                    'manifest.json' not in names or
                    sum(member.file_size for member in members) > _MAX_CONTENT):
                raise ReplayExportError('Invalid recording bundle members or size')
            for member in members:
                if (member.file_size > _MAX_MEMBER or member.flag_bits & 1 or
                        stat.S_ISLNK(member.external_attr >> 16) or
                        (member.filename != 'manifest.json' and
                         not re.fullmatch(r'blobs/[0-9a-f]{64}', member.filename))):
                    raise ReplayExportError('Unsafe recording bundle member')
            manifest = _json(bundle.read('manifest.json'), 'recording manifest')
            if (not isinstance(manifest, dict) or manifest.get('schema') != SCHEMA or
                    not _identifier(manifest.get('run_id')) or
                    not isinstance(manifest.get('owner_id'), str) or not manifest['owner_id'] or
                    not isinstance(manifest.get('original_run_root'), str) or
                    not isinstance(manifest.get('path_map'), dict)):
                raise ReplayExportError('Invalid recording manifest identity or path map')
            original_root = historical_root(manifest['original_run_root'])
            paths = manifest['path_map']
            blobs = {}
            expected_names = {'manifest.json'}
            for original, entry in paths.items():
                if (not isinstance(original, str) or not original or '\x00' in original or
                        not isinstance(entry, dict) or
                        not isinstance(entry.get('sha256'), str) or not _DIGEST.fullmatch(entry['sha256']) or
                        type(entry.get('size')) is not int or not 0 <= entry['size'] <= _MAX_MEMBER or
                        entry.get('blob') != f'blobs/{entry["sha256"]}'):
                    raise ReplayExportError('Invalid recording path map entry')
                # Paths retain historical meaning but must remain owned by the
                # original run. They are never resolved against this machine.
                validate_historical_member(original_root, original)
                expected_names.add(entry['blob'])
                if entry['blob'] not in blobs:
                    raw = bundle.read(entry['blob'])
                    if _sha(raw) != entry['sha256']:
                        raise ReplayExportError('Recording blob SHA-256 mismatch')
                    blobs[entry['blob']] = raw
                if len(blobs[entry['blob']]) != entry['size']:
                    raise ReplayExportError('Recording blob size mismatch')
            if set(names) != expected_names:
                raise ReplayExportError('Unindexed recording bundle member')

        consulted = set()

        def read_portable(_root, value, *, sha256=None, size=None):
            key = str(value)
            entry = paths.get(key)
            if entry is None:
                raise ReplayExportError(f'Missing explicitly mapped recorded file: {key}')
            consulted.add(key)
            raw = blobs[entry['blob']]
            if sha256 is not None and _sha(raw) != sha256:
                raise ReplayExportError(f'SHA-256 mismatch: {key}')
            if size is not None and len(raw) != size:
                raise ReplayExportError(f'Recorded size mismatch: {key}')
            return raw, key

        # This module's real directory only anchors the existing validator;
        # read_portable accesses no historical file, working source or process.
        recording = load_recording(Path(__file__).parent, read_file=read_portable)
        run = recording['run']
        if (run['id'] != manifest['run_id'] or
                run.get('request', {}).get('owner_id') != manifest['owner_id'] or
                recording['provenance'] != manifest.get('provenance')):
            raise ReplayExportError('Recording manifest disagrees with original evidence')
        if consulted != set(paths):
            raise ReplayExportError('Recording contains unreferenced paths')
        published = {}
        for event in recording['events']:
            if event['type'] == 'stage.verified':
                for artifact in event['payload'].get('outputs', []):
                    published.setdefault(artifact['id'], event['sequence'])
            elif event['type'] == 'command.finished':
                command = event['payload'].get('command', {})
                for artifact in run.get('artifacts', []):
                    if (artifact.get('kind') in {'process.stdout', 'process.stderr'} and
                            artifact.get('producer') == event.get('node_id') and
                            artifact['path'] in {command.get('stdout_path'), command.get('stderr_path')}):
                        published.setdefault(artifact['id'], event['sequence'])
        return {'recording': recording, 'manifest': manifest, 'blobs': blobs,
                'published': published, 'bundle_sha256': _sha(bundle_raw)}
    except ReplayExportError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError, TypeError, RuntimeError,
            AttributeError, ValueError) as error:
        raise ReplayExportError(f'Cannot read recording bundle: {path.name}') from error


class RecordingsStore:
    """An immutable view of portable bundles, separate from live engine state."""

    def __init__(self, directory: str | Path):
        self.root = Path(directory).expanduser().resolve()

    def _bundles(self):
        seen = set()
        for path in sorted(self.root.glob('*.zip')):
            if path.is_symlink() or not path.resolve().is_relative_to(self.root):
                raise ReplayExportError('Recording bundle escapes store directory')
            item = _load_bundle(path)
            run_id = item['recording']['run']['id']
            if run_id in seen:
                raise ReplayExportError(f'Duplicate recording identity: {run_id}')
            seen.add(run_id)
            yield item

    def _owned(self, run_id: str, owner_id: str) -> dict:
        if not _identifier(run_id):
            raise FileNotFoundError('Unknown factory recording')
        for item in self._bundles():
            if (item['manifest']['run_id'] == run_id and
                    item['manifest']['owner_id'] == owner_id):
                return item
        raise FileNotFoundError('Unknown factory recording')

    @staticmethod
    def _provenance(item):
        return {**item['recording']['provenance'], 'bundle_sha256': item['bundle_sha256'],
                'original_run_root': item['manifest']['original_run_root'],
                'path_map_sha256': _sha(_encode(item['manifest']['path_map']))}

    def list(self, owner_id: str) -> list[dict]:
        result = []
        for item in self._bundles():
            if item['manifest']['owner_id'] != owner_id:
                continue
            run = item['recording']['run']
            result.append({key: deepcopy(run.get(key)) for key in
                           ('id', 'status', 'created_at', 'updated_at', 'request')})
            result[-1].update({key: item['recording']['provenance'][key] for key in
                               ('event_count', 'graph_revision_count', 'artifact_count')})
            result[-1].update(read_only=True, provenance=self._provenance(item))
        return sorted(result, key=lambda run: run['created_at'] or '', reverse=True)

    def get(self, run_id: str, owner_id: str) -> dict:
        item = self._owned(run_id, owner_id)
        optional = {key: deepcopy(item['recording'][key]) for key in ('workflow_catalog',)
                    if key in item['recording']}
        return {'schema': 'ai4r.recording-view:1', 'read_only': True, **optional,
                **{key: deepcopy(item['recording'][key]) for key in ('run', 'events', 'catalog')},
                'provenance': self._provenance(item)}

    def artifact(self, run_id: str, artifact_id: str, owner_id: str) -> tuple[bytes, str]:
        if not _identifier(artifact_id):
            raise FileNotFoundError('Unknown factory recording artifact')
        item = self._owned(run_id, owner_id)
        for artifact in item['recording']['run'].get('artifacts', []):
            if artifact['id'] != artifact_id or artifact_id not in item['published']:
                continue
            entry = item['manifest']['path_map'][artifact['path']]
            raw = item['blobs'][entry['blob']]
            if _sha(raw) != artifact['sha256'] or len(raw) != artifact['size']:
                raise ReplayExportError('Published artifact SHA-256 or size mismatch')
            return raw, historical_basename(artifact['path'])
        raise FileNotFoundError('Unknown factory recording artifact')

    def evidence(self, run_id: str, name: str, owner_id: str) -> bytes:
        if name not in {'run.json', 'events.jsonl', 'recipe-manifest.json',
                        'recorded-catalog.json', 'recorded-request.json', 'workflow-library.json'}:
            raise FileNotFoundError('Unknown recording evidence')
        import base64
        item = self._owned(run_id, owner_id)
        if name not in item['recording']['raw_evidence']:
            raise FileNotFoundError('Unknown recording evidence')
        return base64.b64decode(item['recording']['raw_evidence'][name], validate=True)

    def import_bundle(self, bundle: str | Path) -> dict:
        """Validate and atomically copy a bundle, preserving its recorded owner."""
        source = Path(bundle)
        item = _load_bundle(source)
        run_id = item['manifest']['run_id']
        for existing in self._bundles():
            if existing['manifest']['run_id'] == run_id:
                if existing['bundle_sha256'] != item['bundle_sha256']:
                    raise ReplayExportError('Refusing to replace an existing recording identity')
                return {'id': run_id, 'sha256': item['bundle_sha256'], 'imported': False}
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, prefix='.import-', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(source.read_bytes())
            if _load_bundle(temporary)['bundle_sha256'] != item['bundle_sha256']:
                raise ReplayExportError('Recording changed while importing')
            destination = self.root / f'{run_id}.zip'
            try:
                # An exclusive link prevents concurrent importers from ever
                # replacing a recording that acquired the same identity.
                os.link(temporary, destination)
            except FileExistsError:
                if _load_bundle(destination)['bundle_sha256'] != item['bundle_sha256']:
                    raise ReplayExportError('Refusing to replace an existing recording identity')
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return {'id': run_id, 'sha256': item['bundle_sha256'], 'imported': True}
