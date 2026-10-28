"""Negative delivery regressions; run with python -m unittest discover -s reference/tests."""
import json
import hashlib
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from package_checks import delivery_issues, source_issues


class DeliveryBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name) / 'design-package'
        shutil.copytree(Path(__file__).resolve().parents[2], cls.root,
                        ignore=shutil.ignore_patterns('__pycache__'))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def assert_rejected(self, relative, text, expected):
        path = self.root / relative
        original = path.read_bytes() if path.exists() else None
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(text, encoding='utf-8')
            self.assertTrue(any(expected in error for error in delivery_issues(self.root)))
        finally:
            if original is None:
                path.unlink()
                # Remove the temporary source collection so tests cannot mask failures.
                if relative.startswith('sources/'):
                    shutil.rmtree(self.root / 'sources')
            else:
                path.write_bytes(original)

    def test_clean_package(self):
        self.assertEqual(delivery_issues(self.root), [])

    def test_source_copy_rejected(self):
        self.assert_rejected('sources/received/draft.md', '# Draft', 'Received source collection')

    def test_removed_link_in_markdown_text(self):
        self.assert_rejected('dependency.txt', '[draft](../sources/model-routing/README.md)', 'Removed source reference')

    def test_archive_link_rejected(self):
        self.assert_rejected('dependency.md', '[draft](../source-archive/received/draft.md)', 'Archived input reference')

    def test_renamed_prd_body_rejected(self):
        self.assert_rejected('notes.txt', '\n'.join('## 1.%s Clause' % i for i in range(101)), 'Bundled PRD body')

    def test_missing_reuse_coverage(self):
        path = 'reference/native-reuse-evidence.json'
        data = json.loads((self.root / path).read_text(encoding='utf-8'))
        data['jiuwenswarm_files'] = []
        self.assert_rejected(path, json.dumps(data), 'reuse coverage')

    def test_false_runtime_claim(self):
        path = 'reference/native-reuse-evidence.json'
        data = json.loads((self.root / path).read_text(encoding='utf-8'))
        data['runtime_compatibility'] = 'PASS'
        self.assert_rejected(path, json.dumps(data), 'cannot claim runtime')

    def test_product_identity_drift(self):
        self.assert_rejected('reference/product-input.md', '# Wrong identity', 'External PRD identity differs')

    def test_missing_acceptance_case(self):
        path = 'side-systems/routing-acceptance.md'
        text = (self.root / path).read_text(encoding='utf-8')
        self.assert_rejected(path, text.replace('| A40 |', '| A39 |'), 'acceptance identities')

    def test_duplicate_catalog_entry(self):
        path = 'side-systems/model-catalog.md'
        text = (self.root / path).read_text(encoding='utf-8')
        self.assert_rejected(path, text.replace('`qwen.multimodal4b` |', '`openai.economy` |'), 'routing inventory')

    def test_text_link_cannot_escape_package(self):
        path = self.root / 'escape.txt'
        outside = self.root.parent / 'outside.md'
        outside.write_text('# Outside', encoding='utf-8')
        try:
            path.write_text('[external checkout](../outside.md)', encoding='utf-8')
            result = subprocess.run([sys.executable, str(self.root / 'reference/validate.py'), str(self.root)],
                                    capture_output=True, text=True, encoding='utf-8')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Nonportable required link:', result.stdout)
        finally:
            path.unlink()
            outside.unlink()

    def test_stale_source_hash_and_symbol(self):
        path = self.root / 'reference/native-reuse-evidence.json'
        original = path.read_bytes()
        commit = '0' * 40
        pin = '1' * 40
        code = b'class Worker:\n    pass\n'
        manifest = ('openjiuwen @ git+https://example.invalid/agent-core.git@' + pin).encode()
        fixture = {'jiuwenswarm_files': [
            {'area': 'agent_execution', 'path': 'worker.py', 'commit': commit,
             'sha256': hashlib.sha256(code).hexdigest(), 'symbols': [{'name': 'Worker', 'line': 1}]},
            {'area': 'dependency_pin', 'path': 'pyproject.toml', 'commit': commit,
             'sha256': hashlib.sha256(manifest).hexdigest()}],
            'openjiuwen_files': [], 'openjiuwen_dependency_commit': pin}
        def read_blob(repo, revision, name):
            return code if name == 'worker.py' else manifest
        try:
            path.write_text(json.dumps(fixture), encoding='utf-8')
            self.assertEqual(source_issues(self.root, read_blob), [])
            fixture['jiuwenswarm_files'][0]['sha256'] = '0' * 64
            fixture['jiuwenswarm_files'][0]['symbols'][0]['line'] = 2
            path.write_text(json.dumps(fixture), encoding='utf-8')
            errors = source_issues(self.root, read_blob)
            self.assertTrue(any('source hash differs' in e for e in errors))
            self.assertTrue(any('source symbol differs' in e for e in errors))
        finally:
            path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
