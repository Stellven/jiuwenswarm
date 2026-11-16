"""Mechanical source-custody tests; no device or engineering-run claims."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

from jiuwenswarm.software_factory.contracts import Stage, StageFailure
from jiuwenswarm.software_factory.provenance import capture_recipe, command_recipe, verify_recipe


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.executor = self.root / 'external_executor.py'
        self.executor.write_text('def produce(ctx, inputs):\n    return {"result": ctx.write_json("value.json", {"value": 7})}\n')
        self.module_name = 'provenance_test_' + uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(self.module_name, self.executor)
        self.module = importlib.util.module_from_spec(spec)
        sys.modules[self.module_name] = self.module
        spec.loader.exec_module(self.module)
        self.stage = Stage('external.produce', 'Produce', 'source', 'file', {}, {'result': 'result'}, self.module.produce)
        self.request = {'goals': ['result'], 'target_backend': 'cpu', 'api_token': 'not-for-capture',
                        'options': {'env': {'SECRET': 'never-retained'}},
                        'repository_url': 'https://private-user:private-password@example.test/source?token=private-token'}

    def tearDown(self):
        sys.modules.pop(self.module_name, None)
        self.temp.cleanup()

    def capture(self):
        return capture_recipe(self.root / 'run', [self.stage], self.request)

    def external_record(self, recipe):
        return next(record for record in recipe['files'] if record['working_path'] == str(self.executor))

    def test_capture_retains_actual_factory_and_external_source_bytes_without_credentials(self):
        recipe = self.capture()
        verify_recipe(recipe)
        self.assertTrue(any(row['relative_path'] == 'engine.py' and row['root'] == 'factory' for row in recipe['files']))
        self.assertTrue(any(row['relative_path'] == 'provenance.py' for row in recipe['files']))
        self.assertTrue(any(row['relative_path'] == 'core_codegen.py' for row in recipe['files']))
        record = self.external_record(recipe)
        self.assertEqual(Path(record['snapshot_path']).read_bytes(), self.executor.read_bytes())
        self.assertEqual(record['sha256'], hashlib.sha256(self.executor.read_bytes()).hexdigest())
        self.assertIn('git_head', recipe['host'])
        self.assertTrue(recipe['packages'])
        retained = Path(recipe['request_path']).read_text() + Path(recipe['manifest_path']).read_text()
        for secret in ('not-for-capture', 'never-retained', 'private-user', 'private-password', 'private-token'):
            self.assertNotIn(secret, retained)
        self.assertTrue(recipe['request_redacted'])
        self.assertEqual(json.loads(Path(recipe['catalog_path']).read_text())[0]['id'], self.stage.id)

    def test_real_working_source_edit_rejects_execution_and_preserves_captured_bytes(self):
        recipe = self.capture()
        record = self.external_record(recipe)
        captured = Path(record['snapshot_path']).read_bytes()
        self.executor.write_text('def produce(ctx, inputs):\n    raise RuntimeError("changed implementation")\n')
        with self.assertRaises(StageFailure) as raised:
            verify_recipe(recipe)
        self.assertEqual(raised.exception.code, 'executor_source_changed')
        self.assertEqual(Path(record['snapshot_path']).read_bytes(), captured)
        with self.assertRaises(StageFailure) as command:
            command_recipe([sys.executable, str(self.executor)], recipe)
        self.assertEqual(command.exception.code, 'executor_source_changed')

    def test_source_deletion_fails_closed(self):
        recipe = self.capture()
        self.executor.unlink()
        with self.assertRaises(StageFailure) as raised:
            verify_recipe(recipe)
        self.assertEqual(raised.exception.code, 'executor_source_changed')

    def test_captured_source_and_catalog_tampering_each_fail_closed(self):
        recipe = self.capture()
        captured = Path(self.external_record(recipe)['snapshot_path'])
        original = captured.read_bytes()
        captured.chmod(0o644)
        captured.write_bytes(b'# forged retained source\n')
        with self.assertRaises(StageFailure) as raised:
            verify_recipe(recipe)
        self.assertEqual(raised.exception.code, 'executor_source_changed')
        captured.write_bytes(original)
        verify_recipe(recipe)
        catalog = Path(recipe['catalog_path'])
        catalog.chmod(0o644)
        catalog.write_text('[]')
        with self.assertRaises(StageFailure) as raised:
            verify_recipe(recipe)
        self.assertEqual(raised.exception.code, 'executor_source_changed')

    def test_capture_is_write_once_and_manifest_tamper_cannot_replace_recipe(self):
        recipe = self.capture()
        with self.assertRaises(StageFailure) as raised:
            self.capture()
        self.assertEqual(raised.exception.code, 'executor_recipe_exists')
        manifest = Path(recipe['manifest_path'])
        manifest.chmod(0o644)
        manifest.write_text('{}')
        with self.assertRaises(StageFailure) as raised:
            verify_recipe(recipe)
        self.assertEqual(raised.exception.code, 'executor_source_changed')

    def test_command_identifies_executable_code_file_and_generated_code_without_argv_secrets(self):
        recipe = self.capture()
        command = command_recipe([sys.executable, str(self.executor), '--token', 'command-secret'], recipe)
        self.assertEqual(command['executable']['resolved_path'], str(Path(sys.executable).resolve()))
        self.assertEqual(command['executable']['sha256'], hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest())
        self.assertTrue(command['code_inputs'][0]['captured_executor_source'])
        self.assertNotIn('command-secret', json.dumps(command))
        generated = self.root / 'generated.py'
        generated.write_text('print("actual generated program")\n')
        result = command_recipe([sys.executable, str(generated)], recipe)
        self.assertFalse(result['code_inputs'][0]['captured_executor_source'])
        self.assertEqual(result['code_inputs'][0]['sha256'], hashlib.sha256(generated.read_bytes()).hexdigest())
        inline = command_recipe([sys.executable, '-c', 'print("inline")' + ' ' * 500], recipe)
        self.assertEqual(inline['inline_code'][0]['argument_index'], 2)
        self.assertNotIn('print(', json.dumps(inline))


if __name__ == '__main__':
    unittest.main()
