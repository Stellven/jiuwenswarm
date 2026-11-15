"""Portable readers do not interpret historical paths using their host OS."""
from __future__ import annotations

import base64
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

from jiuwenswarm.software_factory.recordings import RecordingsStore, default_recordings_directory
from jiuwenswarm.software_factory.replay_export import load_recording

import test_recordings as fixtures


class RecordingPlatformTests(unittest.TestCase):
    def test_windows_recorded_paths_license_and_download_on_posix_host(self):
        fixture = fixtures.PortableRecordingsTests(methodName='runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        original = str(fixture.run_dir)
        windows_root = 'C:\\factory-runs\\' + fixture.run_id

        def relocate(value):
            if isinstance(value, dict):
                return {key: relocate(item) for key, item in value.items()}
            if isinstance(value, list):
                return [relocate(item) for item in value]
            if isinstance(value, str) and value.startswith(original):
                return windows_root + value[len(original):].replace('/', '\\')
            return value

        run = relocate(deepcopy(fixture.run))
        events = relocate(deepcopy(fixture.events))
        files = {}
        recipe = {key: value for key, value in run['recipe'].items()
                  if key not in {'manifest_path', 'manifest_sha256'}}
        for old, new in zip(fixture.run['recipe']['files'], recipe['files']):
            files[new['snapshot_path']] = Path(old['snapshot_path']).read_bytes()
        files[recipe['catalog_path']] = Path(fixture.run['recipe']['catalog_path']).read_bytes()
        files[recipe['request_path']] = Path(fixture.run['recipe']['request_path']).read_bytes()
        for old, new in zip(fixture.run['artifacts'], run['artifacts']):
            files[new['path']] = Path(old['path']).read_bytes()

        source_dir = windows_root + '\\source\\strata'
        checkout_path = windows_root + '\\source.json'
        checkout_raw = json.dumps({'source_dir': source_dir, 'commit_sha': 'a' * 40,
                                   'repository_url': 'https://example.test/transport-fixture'}).encode()
        checkout = {'id': 'checkout', 'kind': 'source.checkout', 'producer': 'n1',
                    'path': checkout_path, 'sha256': fixtures.digest(checkout_raw), 'size': len(checkout_raw)}
        run['artifacts'].append(checkout)
        events[2]['payload']['outputs'].append(deepcopy(checkout))
        files[checkout_path] = checkout_raw
        license_path = source_dir + '\\LICENSE'
        files[license_path] = b'Transport fixture license\n'
        manifest_path = run['recipe']['manifest_path']
        manifest_raw = json.dumps(recipe).encode()
        files[manifest_path] = manifest_raw
        run['recipe'] = {**recipe, 'manifest_path': manifest_path,
                         'manifest_sha256': fixtures.digest(manifest_raw)}
        files['run.json'] = json.dumps(run).encode()
        files['events.jsonl'] = b''.join(json.dumps(event).encode() + b'\n' for event in events)

        def read_retained(_root, value, *, sha256=None, size=None):
            raw = files[str(value)]
            if sha256 is not None:
                self.assertEqual(fixtures.digest(raw), sha256)
            if size is not None:
                self.assertEqual(len(raw), size)
            return raw, str(value)

        with fixtures.no_factory_execution():
            recording = load_recording(fixture.root, read_file=read_retained)
            self.assertEqual(recording['licenses'][0]['path'], license_path)
            path_map = {name: {'blob': 'blobs/' + fixtures.digest(raw),
                               'sha256': fixtures.digest(raw), 'size': len(raw)}
                        for name, raw in files.items()}
            manifest = {'schema': 'ai4r.recording-bundle:1', 'run_id': run['id'], 'owner_id': 'alice',
                        'original_run_root': windows_root, 'path_map': path_map,
                        'provenance': recording['provenance']}
            with zipfile.ZipFile(fixture.bundle, 'w') as archive:
                archive.writestr('manifest.json', json.dumps(manifest))
                for digest, raw in {fixtures.digest(raw): raw for raw in files.values()}.items():
                    archive.writestr('blobs/' + digest, raw)

            def native_path(value):
                if str(value).startswith(windows_root):
                    raise AssertionError('Historical Windows paths reached the native filesystem API')
                return Path(value)

            with patch('jiuwenswarm.software_factory.recordings.Path', side_effect=native_path), \
                    patch('jiuwenswarm.software_factory.replay_export.Path', side_effect=native_path):
                store = RecordingsStore(fixture.store_dir)
                self.assertEqual(store.get(run['id'], 'alice')['run'], run)
                raw, filename = store.artifact(run['id'], 'source', 'alice')
                self.assertEqual(raw, fixture.artifact_bytes['source'])
                self.assertEqual(filename, 'strata_core.cpp')
                self.assertEqual(store.evidence(run['id'], 'run.json', 'alice'), files['run.json'])
        self.assertEqual(base64.b64decode(recording['raw_evidence']['run.json']), files['run.json'])

    def test_real_linux_bundle_never_uses_native_paths_for_historical_metadata(self):
        store = RecordingsStore(default_recordings_directory())
        run_id = '11a6ce02166b4618baea6db59aaf44ec'
        if not (store.root / 'ascend-inner-stages.zip').is_file():
            self.skipTest('Corrected production recording is not present')

        def native_path(value):
            if str(value).startswith(('/workspace/factory-runs/', '/workspace/factory-monday-')):
                raise AssertionError('Historical Linux paths reached the native filesystem API')
            return Path(value)

        with fixtures.no_factory_execution(), \
                patch('jiuwenswarm.software_factory.recordings.Path', side_effect=native_path), \
                patch('jiuwenswarm.software_factory.replay_export.Path', side_effect=native_path):
            view = store.get(run_id, 'local-operator')
            self.assertEqual(view['run']['id'], run_id)
            self.assertEqual(len(view['events']), 132)
            artifact = next(value for value in view['run']['artifacts']
                            if value['kind'] == 'construction.native_sources')
            raw, filename = store.artifact(run_id, artifact['id'], 'local-operator')
            self.assertEqual(fixtures.digest(raw), artifact['sha256'])
            self.assertEqual(filename, artifact['path'].rsplit('/', 1)[-1])


if __name__ == '__main__':
    unittest.main()
