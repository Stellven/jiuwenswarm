"""Launcher boundary tests use the actual checked-in historical recordings."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PureWindowsPath
import tempfile
import unittest
from unittest.mock import patch

import httpx

from jiuwenswarm.software_factory.demo import (
    REPOSITORY, check_frontend, create_app, frontend_fingerprint, preflight, record_frontend_build,
)


RECORDINGS = REPOSITORY / 'docs/code/Missions/software-factory/recordings'


def host_fixture(root):
    frontend = root / 'frontend'
    (frontend / 'src').mkdir(parents=True)
    (frontend / 'src/App.tsx').write_text('export const host = true;\n')
    (frontend / 'dist').mkdir()
    index = frontend / 'dist/index.html'
    index.write_text('<!doctype html><title>Isolated host static transport test</title>')
    (frontend / 'dist/assets').mkdir()
    (frontend / 'dist/assets/host.js').write_text('/* isolated static transport fixture */')
    record_frontend_build(frontend)
    return frontend


class DemoTests(unittest.IsolatedAsyncioTestCase):
    def test_seal_is_unchanged_under_windows_native_path_ordering(self):
        with tempfile.TemporaryDirectory() as directory:
            frontend = host_fixture(Path(directory))
            for name in ('Banana.tsx', 'apple/file.tsx', 'apple.tsx', 'banana.css'):
                path = frontend / 'src' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name)
            record_frontend_build(frontend)
            expected = frontend_fingerprint(frontend)
            with patch.object(Path, '__lt__', lambda left, right:
                              PureWindowsPath(str(left)) < PureWindowsPath(str(right))):
                self.assertEqual(frontend_fingerprint(frontend), expected)
                self.assertEqual(check_frontend(frontend)['source_sha256'], expected)

    def test_preflight_reads_real_bundles_without_constructing_an_executor(self):
        with tempfile.TemporaryDirectory() as directory:
            frontend = host_fixture(Path(directory))
            with patch('jiuwenswarm.software_factory.engine.FactoryService',
                       side_effect=AssertionError('Preflight must never create an executor')):
                report = preflight(RECORDINGS, frontend)
            self.assertFalse(report['execution_dispatched'])
            self.assertEqual(report['mode'], 'existing-host-ui')
            self.assertGreaterEqual(len(report['recordings']), 2)

    def test_changed_host_source_and_missing_build_cannot_be_presented_as_current(self):
        with tempfile.TemporaryDirectory() as directory:
            frontend = host_fixture(Path(directory))
            check_frontend(frontend)
            (frontend / 'src/App.tsx').write_text('export const changed = true;\n')
            with self.assertRaisesRegex(RuntimeError, 'stale'):
                check_frontend(frontend)

    def test_modified_or_missing_compiled_asset_fails_presentation_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            frontend = host_fixture(Path(directory))
            asset = frontend / 'dist/assets/host.js'
            asset.write_text('/* changed build artifact */')
            with self.assertRaisesRegex(RuntimeError, 'assets changed'):
                check_frontend(frontend)
            asset.unlink()
            with self.assertRaisesRegex(RuntimeError, 'assets changed'):
                check_frontend(frontend)
            (frontend / 'dist/.factory-build.json').unlink()
            with self.assertRaisesRegex(RuntimeError, '--build'):
                check_frontend(frontend)

    async def test_one_app_serves_host_and_real_recorded_cpp_without_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frontend = host_fixture(root)
            app = create_app(root=root / 'new-runtime', recordings_directory=RECORDINGS,
                             frontend=frontend)
            transport = httpx.ASGITransport(app=app, client=('127.0.0.1', 56100))
            with patch.object(app.state.factory_service, 'create',
                              side_effect=AssertionError('Playback must never construct a run')):
                async with httpx.AsyncClient(transport=transport, base_url='http://localhost:5175') as client:
                    page = await client.get('/?view=workflow')
                    self.assertEqual(page.content, (frontend / 'dist/index.html').read_bytes())
                    summaries = (await client.get('/api/v1/factory/recordings')).json()
                    records = summaries.get('recordings', summaries) if isinstance(summaries, dict) else summaries
                    self.assertGreaterEqual(len(records), 2)
                    identifier = next(item['id'] for item in records
                                      if item['request']['target_backend'] == 'cpu')
                    result = await client.get('/api/v1/factory/recordings/' + identifier)
                    self.assertEqual(result.status_code, 200)
                    recording = result.json()
                    self.assertTrue(recording['read_only'])
                    self.assertEqual(recording['run']['request']['target_backend'], 'cpu')
                    artifact = next(item for item in recording['run']['artifacts']
                                    if item['kind'] == 'construction.cpp')
                    source = await client.get('/api/v1/factory/recordings/' + identifier +
                                              '/artifacts/' + artifact['id'])
                    self.assertEqual(source.status_code, 200)
                    self.assertEqual(hashlib.sha256(source.content).hexdigest(), artifact['sha256'])
                    self.assertIn(b'namespace strata_core', source.content)
            self.assertEqual(list((root / 'new-runtime').glob('*/run.json')), [])
