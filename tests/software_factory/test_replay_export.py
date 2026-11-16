"""Offline export tests use isolated recording files, never execute a factory."""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from jiuwenswarm.software_factory.replay_export import (
    ReplayExportError, export_replay, load_recording,
)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False))
    return path.read_bytes()


class ReplayExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.run_dir = self.root / 'run'
        self.run_dir.mkdir()
        code = 'void route() {}\n// </script><script>window.injected=1</script> & \u2028\u2029\n'
        cpp = self.run_dir / 'stages' / 'n1' / '1' / 'strata_core.cpp'
        cpp.parent.mkdir(parents=True)
        cpp.write_text(code)
        self.artifact = {'id': 'a1', 'kind': 'construction.cpp', 'producer': 'n1',
                         'path': str(cpp), 'sha256': digest(cpp.read_bytes()), 'size': cpp.stat().st_size}
        snapshot = self.run_dir / 'recipe' / 'source' / 'factory' / 'stage.py'
        snapshot.parent.mkdir(parents=True)
        snapshot.write_text('def stage():\n    return 7\n')
        catalog_path = self.run_dir / 'recipe' / 'catalog.json'
        catalog = [{'id': 'construct', 'name': 'Construct source', 'workflow_id': 'construction',
                    'subworkflow_id': 'source_generation', 'inputs': [], 'outputs': []}]
        catalog_raw = write_json(catalog_path, catalog)
        request_path = self.run_dir / 'recipe' / 'request.json'
        request_raw = write_json(request_path, {'goals': ['construction.cpp']})
        files = [{'relative_path': 'stage.py', 'root': 'factory', 'snapshot_path': str(snapshot),
                  'working_path': str(self.root / 'not-consulted' / 'stage.py'),
                  'sha256': digest(snapshot.read_bytes()), 'size': snapshot.stat().st_size}]
        manifest = {'schema': 'ai4r.executor-recipe:1', 'files': files,
                    'catalog_path': str(catalog_path), 'catalog_sha256': digest(catalog_raw),
                    'request_path': str(request_path), 'request_capture_sha256': digest(request_raw)}
        manifest_path = self.run_dir / 'recipe' / 'manifest.json'
        manifest_raw = write_json(manifest_path, manifest)
        recipe = dict(manifest, manifest_path=str(manifest_path), manifest_sha256=digest(manifest_raw))
        node = {'id': 'n1', 'stage_id': 'construct', 'name': 'Construct source',
                'workflow_id': 'construction', 'subworkflow_id': 'source_generation',
                'status': 'pending', 'attempts': []}
        graph = {'revision': 1, 'time': '2026-11-14T01:00:00+00:00', 'reason': 'Recorded selection',
                 'nodes': [deepcopy(node)], 'edges': []}
        self.events = [
            {'sequence': 1, 'time': '2026-11-14T01:00:00+00:00', 'type': 'graph.updated', 'node_id': None, 'payload': graph},
            {'sequence': 2, 'time': '2026-11-14T01:00:01+00:00', 'type': 'stage.started', 'node_id': 'n1', 'payload': {'attempt': 1}},
            {'sequence': 3, 'time': '2026-11-14T01:00:02+00:00', 'type': 'stage.verified', 'node_id': 'n1',
             'payload': {'attempt': 1, 'outputs': [self.artifact]}},
            {'sequence': 4, 'time': '2026-11-14T01:00:03+00:00', 'type': 'run.completed', 'node_id': None, 'payload': {}},
        ]
        self.run = {'id': 'recorded-test-run', 'status': 'completed', 'sequence': 4,
                    'request': {'goals': ['construction.cpp']}, 'recipe': recipe,
                    'recipe_digest': digest(json.dumps([(item['relative_path'], item['sha256']) for item in files], sort_keys=True).encode()),
                    'created_at': '2026-11-14T01:00:00+00:00', 'updated_at': '2026-11-14T01:00:03+00:00',
                    'nodes': [dict(node, status='verified')], 'edges': [], 'graph_revisions': [graph], 'artifacts': [self.artifact]}
        self.save()

    def save(self):
        write_json(self.run_dir / 'run.json', self.run)
        (self.run_dir / 'events.jsonl').write_text(''.join(json.dumps(event) + '\n' for event in self.events))

    def test_exports_exact_evidence_and_preserves_original_recording(self):
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.run_dir.rglob('*') if path.is_file()}
        output = self.root / 'export' / 'replay.html'
        with patch('subprocess.run', side_effect=AssertionError('Replay must never execute a process')), \
                patch('subprocess.Popen', side_effect=AssertionError('Replay must never execute a process')):
            report = export_replay(self.run_dir, output)
        self.assertEqual(report['event_count'], 4)
        self.assertEqual(report['graph_revision_count'], 1)
        recording = load_recording(self.run_dir)
        self.assertEqual(recording['attachments']['a1']['sequence'], 3)
        self.assertEqual(base64.b64decode(recording['raw_evidence']['run.json']), (self.run_dir / 'run.json').read_bytes())
        self.assertEqual(base64.b64decode(recording['raw_evidence']['events.jsonl']), (self.run_dir / 'events.jsonl').read_bytes())
        for path, value in before.items():
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), value)
        self.assertTrue(output.is_file())

    def test_source_script_closing_tags_are_safe_and_viewer_is_network_free(self):
        output = self.root / 'replay.html'
        export_replay(self.run_dir, output)
        document = output.read_text()
        self.assertEqual(len(re.findall('</script>', document, re.I)), 1)
        self.assertNotIn('</script><script>window.injected', document)
        self.assertIn('\\u003c/script\\u003e', document)
        self.assertIn('\\u0026', document)
        self.assertIn('\\u2028', document)
        self.assertIn("connect-src 'none'", document)
        self.assertIn('requestAnimationFrame', document)
        self.assertNotRegex(document, r'\b(?:setTimeout|setInterval|fetch|EventSource)\s*\(')
        self.assertIn('--color-action-primary:#2563eb;', document)
        self.assertIn('var(--color-feedback-success)', document)
        script = document.split('<script type="module">', 1)[1].rsplit('</script>', 1)[0]
        expected_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        self.assertIn(f"script-src 'sha256-{expected_hash}'", document)

    def test_changed_artifact_is_rejected(self):
        Path(self.artifact['path']).write_text('changed')
        with self.assertRaisesRegex(ReplayExportError, 'SHA-256 mismatch'):
            load_recording(self.run_dir)

    def test_outside_artifact_and_symlink_escape_are_rejected(self):
        outside = self.root / 'outside.cpp'
        outside.write_text(Path(self.artifact['path']).read_text())
        Path(self.artifact['path']).unlink()
        Path(self.artifact['path']).symlink_to(outside)
        with self.assertRaisesRegex(ReplayExportError, 'escapes run directory'):
            load_recording(self.run_dir)

    def test_noncontiguous_events_and_rewritten_graph_are_rejected(self):
        self.events[1]['sequence'] = 3
        self.save()
        with self.assertRaisesRegex(ReplayExportError, 'noncontiguous'):
            load_recording(self.run_dir)
        self.events[1]['sequence'] = 2
        self.run['graph_revisions'] = [dict(self.events[0]['payload'], reason='invented')]
        self.save()
        with self.assertRaisesRegex(ReplayExportError, 'Graph revisions differ'):
            load_recording(self.run_dir)

    def test_tampered_recipe_source_is_rejected_without_working_source_dependency(self):
        recording = load_recording(self.run_dir)
        self.assertEqual(recording['provenance']['recipe_digest'], self.run['recipe_digest'])
        Path(self.run['recipe']['files'][0]['snapshot_path']).write_text('changed recipe')
        with self.assertRaisesRegex(ReplayExportError, 'SHA-256 mismatch'):
            load_recording(self.run_dir)

    def test_original_run_cannot_be_export_destination(self):
        with self.assertRaisesRegex(ReplayExportError, 'must not modify'):
            export_replay(self.run_dir, self.run_dir / 'replay.html')
        self.assertFalse((self.run_dir / 'replay.html').exists())

    def test_lifecycle_cannot_publish_different_or_unrecorded_artifacts(self):
        self.events[2]['payload']['outputs'] = [dict(self.artifact, sha256='0' * 64)]
        self.save()
        with self.assertRaisesRegex(ReplayExportError, 'Published artifact differs'):
            load_recording(self.run_dir)


if __name__ == '__main__':
    unittest.main()
