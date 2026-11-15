"""Portable replay reads retained files and never dispatches factory work.

The small fixture is an isolated transport recording, not a product execution.
A separate integration case exports the existing real core recording when it is
available locally or bundled in the checkout.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fastapi import FastAPI
import httpx

from jiuwenswarm.software_factory.api import create_router
from jiuwenswarm.software_factory.engine import FactoryService
from jiuwenswarm.software_factory.recordings import RecordingsStore, export_recording
from jiuwenswarm.software_factory.replay_export import ReplayExportError


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    return path.read_bytes()


@contextmanager
def no_factory_execution():
    """Fail on any accidental construction or child-process dispatch."""
    with ExitStack() as stack:
        for target in ('subprocess.run', 'subprocess.Popen'):
            stack.enter_context(patch(target, side_effect=AssertionError('Replay dispatched a process')))
        stack.enter_context(patch.object(FactoryService, 'create',
                                        side_effect=AssertionError('Replay created a factory run')))
        yield


class PortableRecordingsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.run_dir = self.root / 'original' / ('a' * 32)
        self.run_dir.mkdir(parents=True)
        self.run_id = self.run_dir.name
        self.store_dir = self.root / 'bundles'
        self.store_dir.mkdir()
        self.bundle = self.store_dir / 'transport.zip'
        cpp = self.run_dir / 'stages' / 'n1' / '1' / 'strata_core.cpp'
        cpp.parent.mkdir(parents=True)
        cpp.write_text('void route() {}\n// retained <script>source</script>\n', encoding='utf-8')
        package = cpp.with_name('huawei_native_strata.zip')
        with zipfile.ZipFile(package, 'w') as archive:
            archive.write(cpp, 'src/strata_core.cpp')
        self.artifacts = []
        for identifier, kind, path in [('source', 'construction.cpp', cpp),
                                        ('package', 'construction.package', package)]:
            self.artifacts.append({'id': identifier, 'kind': kind, 'producer': 'n1',
                                   'path': str(path), 'sha256': digest(path.read_bytes()),
                                   'size': path.stat().st_size})
        self.artifact_bytes = {item['id']: Path(item['path']).read_bytes() for item in self.artifacts}
        snapshot = self.run_dir / 'recipe' / 'source' / 'factory' / 'stage.py'
        snapshot.parent.mkdir(parents=True)
        snapshot.write_text('def stage():\n    return 7\n', encoding='utf-8')
        self.catalog = [{'id': 'construct', 'name': 'Construct source', 'workflow_id': 'construction',
                         'subworkflow_id': 'source_generation', 'inputs': [], 'outputs': []}]
        catalog_path = self.run_dir / 'recipe' / 'catalog.json'
        catalog_raw = write_json(catalog_path, self.catalog)
        request = {'goals': ['construction.package'], 'owner_id': 'alice', 'target_backend': 'cpu',
                   'task': {'title': 'Transport fixture', 'acceptance': {'source': True}}}
        request_path = self.run_dir / 'recipe' / 'request.json'
        request_raw = write_json(request_path, request)
        files = [{'relative_path': 'stage.py', 'root': 'factory', 'snapshot_path': str(snapshot),
                  'working_path': str(self.root / 'unavailable-working-source' / 'stage.py'),
                  'sha256': digest(snapshot.read_bytes()), 'size': snapshot.stat().st_size}]
        recipe = {'schema': 'ai4r.executor-recipe:1', 'files': files,
                  'catalog_path': str(catalog_path), 'catalog_sha256': digest(catalog_raw),
                  'request_path': str(request_path), 'request_capture_sha256': digest(request_raw)}
        manifest_path = self.run_dir / 'recipe' / 'manifest.json'
        recipe_raw = write_json(manifest_path, recipe)
        recipe = dict(recipe, manifest_path=str(manifest_path), manifest_sha256=digest(recipe_raw))
        node = {'id': 'n1', 'stage_id': 'construct', 'name': 'Construct source',
                'workflow_id': 'construction', 'subworkflow_id': 'source_generation',
                'status': 'pending', 'attempts': []}
        graph = {'revision': 1, 'time': '2026-11-14T01:00:00+00:00', 'reason': 'Fixture selection',
                 'nodes': [deepcopy(node)], 'edges': []}
        self.events = [
            {'sequence': 1, 'time': '2026-11-14T01:00:00+00:00', 'type': 'graph.updated',
             'node_id': None, 'payload': graph},
            {'sequence': 2, 'time': '2026-11-14T01:00:01+00:00', 'type': 'stage.started',
             'node_id': 'n1', 'payload': {'attempt': 1}},
            {'sequence': 3, 'time': '2026-11-14T01:00:02+00:00', 'type': 'stage.verified',
             'node_id': 'n1', 'payload': {'attempt': 1, 'outputs': self.artifacts}},
            {'sequence': 4, 'time': '2026-11-14T01:00:03+00:00', 'type': 'run.completed',
             'node_id': None, 'payload': {}},
        ]
        self.run = {'id': self.run_id, 'status': 'completed', 'sequence': len(self.events),
                    'request': request, 'recipe': recipe,
                    'recipe_digest': digest(json.dumps([(item['relative_path'], item['sha256'])
                                                       for item in files], sort_keys=True).encode()),
                    'created_at': self.events[0]['time'], 'updated_at': self.events[-1]['time'],
                    'nodes': [dict(node, status='verified')], 'edges': [],
                    'graph_revisions': [graph], 'artifacts': self.artifacts}
        self.run_raw = write_json(self.run_dir / 'run.json', self.run)
        self.event_raw = ''.join(json.dumps(event) + '\n' for event in self.events).encode()
        (self.run_dir / 'events.jsonl').write_bytes(self.event_raw)
        self.raw_evidence = [self.run_raw, self.event_raw, recipe_raw, catalog_raw, request_raw]

    def export(self):
        with no_factory_execution():
            return export_recording(self.run_dir, self.bundle)

    def test_relocated_bundle_preserves_exact_original_metadata_and_bytes(self):
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in self.run_dir.rglob('*') if path.is_file()}
        self.export()
        for path, expected in before.items():
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), expected)
        with zipfile.ZipFile(self.bundle) as archive:
            contents = [archive.read(member) for member in archive.namelist()]
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['schema'], 'ai4r.recording-bundle:1')
            self.assertEqual(manifest['run_id'], self.run_id)
            self.assertEqual(manifest['owner_id'], 'alice')
            self.assertEqual(manifest['original_run_root'], str(self.run_dir))
            for item in self.artifacts:
                entry = manifest['path_map'][item['path']]
                self.assertEqual(entry['blob'], 'blobs/' + item['sha256'])
                self.assertEqual(entry['sha256'], item['sha256'])
                self.assertEqual(entry['size'], item['size'])
                self.assertEqual(archive.read(entry['blob']), self.artifact_bytes[item['id']])
        for raw in self.raw_evidence:
            self.assertIn(raw, contents)
        shutil.rmtree(self.run_dir.parent)
        self.assertFalse(self.run_dir.exists())
        with no_factory_execution():
            store = RecordingsStore(self.store_dir)
            listed = store.list('alice')
            view = store.get(self.run_id, 'alice')
            self.assertEqual([item['id'] for item in listed], [self.run_id])
            self.assertEqual(view['schema'], 'ai4r.recording-view:1')
            self.assertTrue(view['read_only'])
            self.assertEqual(view['run'], self.run)
            self.assertEqual(view['events'], self.events)
            self.assertEqual(view['catalog'], self.catalog)
            self.assertEqual(view['provenance']['run_sha256'], digest(self.run_raw))
            self.assertEqual(view['provenance']['events_sha256'], digest(self.event_raw))
            for item in self.artifacts:
                raw, filename = store.artifact(self.run_id, item['id'], 'alice')
                self.assertEqual(raw, self.artifact_bytes[item['id']])
                self.assertEqual(digest(raw), item['sha256'])
                self.assertEqual(filename, Path(item['path']).name)

    def test_owners_and_unknown_ids_cannot_read_recordings_or_downloads(self):
        self.export()
        with no_factory_execution():
            store = RecordingsStore(self.store_dir)
            self.assertEqual(store.list('bob'), [])
            for run_id, owner in [(self.run_id, 'bob'), ('../' + self.run_id, 'alice')]:
                with self.assertRaises((FileNotFoundError, ValueError)):
                    store.get(run_id, owner)
                with self.assertRaises((FileNotFoundError, ValueError)):
                    store.artifact(run_id, 'source', owner)
            for identifier in ('../source', '/etc/passwd', 'unpublished'):
                with self.assertRaises((FileNotFoundError, ValueError)):
                    store.artifact(self.run_id, identifier, 'alice')

    def test_import_revalidates_and_relocates_without_extraction_or_execution(self):
        self.export()
        destination = self.root / 'fresh-clone' / 'recordings'
        shutil.rmtree(self.run_dir.parent)
        with no_factory_execution():
            store = RecordingsStore(destination)
            store.import_bundle(self.bundle)
            imported = store.get(self.run_id, 'alice')
            self.assertEqual(imported['run'], self.run)
            self.assertEqual(imported['events'], self.events)
            self.assertEqual(store.artifact(self.run_id, 'package', 'alice')[0],
                             self.artifact_bytes['package'])
        self.assertFalse(self.run_dir.exists())

    def test_changed_blob_is_rejected_before_download(self):
        self.export()
        with zipfile.ZipFile(self.bundle) as archive:
            members = [(info, archive.read(info)) for info in archive.infolist()]
        changed = False
        with zipfile.ZipFile(self.bundle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for info, raw in members:
                if raw == self.artifact_bytes['source']:
                    raw = raw + b'changed after publication\n'
                    changed = True
                archive.writestr(info, raw)
        self.assertTrue(changed)
        with no_factory_execution(), self.assertRaises((ReplayExportError, ValueError)):
            store = RecordingsStore(self.store_dir)
            store.artifact(self.run_id, 'source', 'alice')

    def test_archive_traversal_is_rejected_and_does_not_write_outside_store(self):
        self.export()
        with zipfile.ZipFile(self.bundle, 'a') as archive:
            archive.writestr('../escaped.txt', 'untrusted archive member')
        with no_factory_execution(), self.assertRaises((ReplayExportError, ValueError)):
            RecordingsStore(self.root / 'import').import_bundle(self.bundle)
        self.assertFalse((self.root / 'escaped.txt').exists())
        self.assertFalse((self.store_dir.parent / 'escaped.txt').exists())

    def test_only_lifecycle_published_artifacts_are_downloadable(self):
        orphan = self.run_dir / 'stages' / 'n1' / '1' / 'unpublished.txt'
        orphan.write_text('retained bytes never published by a verified stage', encoding='utf-8')
        record = {'id': 'unpublished', 'kind': 'construction.cpp', 'producer': 'n1',
                  'path': str(orphan), 'sha256': digest(orphan.read_bytes()), 'size': orphan.stat().st_size}
        self.run['artifacts'].append(record)
        write_json(self.run_dir / 'run.json', self.run)
        self.export()
        with no_factory_execution():
            store = RecordingsStore(self.store_dir)
            with self.assertRaises((FileNotFoundError, ValueError)):
                store.artifact(self.run_id, 'unpublished', 'alice')

    def test_bundle_owner_cannot_override_recorded_owner(self):
        self.export()
        with zipfile.ZipFile(self.bundle) as archive:
            members = [(info, archive.read(info)) for info in archive.infolist()]
        with zipfile.ZipFile(self.bundle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for info, raw in members:
                if info.filename == 'manifest.json':
                    manifest = json.loads(raw)
                    manifest['owner_id'] = 'bob'
                    raw = json.dumps(manifest).encode()
                archive.writestr(info, raw)
        with no_factory_execution(), self.assertRaises((ReplayExportError, ValueError)):
            RecordingsStore(self.root / 'forged-owner').import_bundle(self.bundle)

    def test_api_replays_and_downloads_with_original_owner_only(self):
        self.export()
        shutil.rmtree(self.run_dir.parent)
        with no_factory_execution():
            service = FactoryService(self.root / 'empty-live-runs', [])
            self.addCleanup(service.pool.shutdown, wait=True)
            app = FastAPI()
            app.include_router(create_router(service, lambda request, scope: request.headers.get('x-user'),
                                             recordings=RecordingsStore(self.store_dir)))
            async def requests():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                             base_url='http://testserver') as client:
                    prefix = '/api/v1/factory/recordings'
                    alice = {'x-user': 'alice'}
                    bob = {'x-user': 'bob'}
                    response = await client.get(prefix, headers=alice)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual([item['id'] for item in response.json()['recordings']], [self.run_id])
                    self.assertEqual((await client.get(prefix, headers=bob)).json()['recordings'], [])
                    view = await client.get(f'{prefix}/{self.run_id}', headers=alice)
                    self.assertEqual(view.status_code, 200)
                    self.assertEqual(view.json()['run'], self.run)
                    self.assertEqual(view.json()['events'], self.events)
                    self.assertEqual((await client.get(f'{prefix}/{self.run_id}', headers=bob)).status_code, 404)
                    for item in self.artifacts:
                        url = f'{prefix}/{self.run_id}/artifacts/{item["id"]}'
                        response = await client.get(url, headers=alice)
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.content, self.artifact_bytes[item['id']])
                        self.assertEqual(response.headers['x-content-type-options'], 'nosniff')
                        self.assertTrue(response.headers['content-disposition'].startswith('attachment;'))
                        self.assertEqual((await client.get(url, headers=bob)).status_code, 404)
                    self.assertEqual((await client.post(f'{prefix}/{self.run_id}', headers=alice, json={})).status_code, 405)
                    self.assertEqual((await client.get(f'{prefix}/{self.run_id}/stream', headers=alice)).status_code, 404)
                    self.assertEqual(list(service.root.glob('*/run.json')), [])
                    with zipfile.ZipFile(self.bundle) as archive:
                        members = [(info, archive.read(info)) for info in archive.infolist()]
                    with zipfile.ZipFile(self.bundle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                        for info, raw in members:
                            if raw == self.artifact_bytes['source']:
                                raw += b'tampered after publication'
                            archive.writestr(info, raw)
                    changed = await client.get(f'{prefix}/{self.run_id}', headers=alice)
                    self.assertEqual(changed.status_code, 409)
                    changed_download = await client.get(f'{prefix}/{self.run_id}/artifacts/source', headers=alice)
                    self.assertEqual(changed_download.status_code, 409)
            asyncio.run(requests())

    def test_unconfigured_api_requires_local_operator_and_local_origin(self):
        self.export()
        with no_factory_execution():
            service = FactoryService(self.root / 'empty-local-runs', [])
            self.addCleanup(service.pool.shutdown, wait=True)
            app = FastAPI()
            app.include_router(create_router(service, recordings=RecordingsStore(self.store_dir)))
            async def requests():
                path = '/api/v1/factory/recordings'
                async with httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=app, client=('192.0.2.1', 4000)),
                        base_url='http://localhost') as remote:
                    self.assertEqual((await remote.get(path)).status_code, 403)
                async with httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=app, client=('127.0.0.1', 4000)),
                        base_url='http://localhost') as local:
                    self.assertEqual((await local.get(path)).status_code, 200)
                    allowed = await local.get(path, headers={'origin': 'http://localhost:5175'})
                    self.assertEqual(allowed.status_code, 200)
                    denied = await local.get(path, headers={'origin': 'https://example.com'})
                    self.assertEqual(denied.status_code, 403)
            asyncio.run(requests())

    def test_original_run_directory_cannot_be_export_destination(self):
        with no_factory_execution(), self.assertRaises((ReplayExportError, ValueError)):
            export_recording(self.run_dir, self.run_dir / 'recording.zip')
        self.assertFalse((self.run_dir / 'recording.zip').exists())


class ActualRecordingPortabilityTests(unittest.TestCase):
    def test_existing_core_recording_exports_and_replays_with_zero_dispatch(self):
        source = Path('/workspace/factory-runs/6db7a2b968c8434eaa9a508a6d16a7cf')
        if not (source / 'run.json').is_file():
            self.skipTest('Original core recording is not present in this checkout')
        run_raw = (source / 'run.json').read_bytes()
        event_raw = (source / 'events.jsonl').read_bytes()
        run = json.loads(run_raw)
        events = [json.loads(line) for line in event_raw.splitlines()]
        owner = run['request']['owner_id']
        original_files = {source / 'run.json': run_raw, source / 'events.jsonl': event_raw}
        package = next(item for item in run['artifacts'] if item['kind'] == 'construction.package')
        package_raw = Path(package['path']).read_bytes()
        read_bytes = Path.read_bytes
        def reject_original_reads(path):
            if path.is_relative_to(source):
                raise AssertionError('Portable replay consulted the original run directory')
            return read_bytes(path)
        with tempfile.TemporaryDirectory() as directory, no_factory_execution():
            root = Path(directory)
            bundle = root / 'core.zip'
            export_recording(source, bundle)
            with patch.object(Path, 'read_bytes', reject_original_reads):
                store = RecordingsStore(root)
                view = store.get(run['id'], owner)
                self.assertEqual(view['run'], run)
                self.assertEqual(view['events'], events)
                self.assertEqual(view['provenance']['run_sha256'], digest(run_raw))
                self.assertEqual(view['provenance']['events_sha256'], digest(event_raw))
                raw, filename = store.artifact(run['id'], package['id'], owner)
                self.assertEqual(raw, package_raw)
                self.assertEqual(filename, 'huawei_native_strata.zip')
        for path, raw in original_files.items():
            self.assertEqual(path.read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
