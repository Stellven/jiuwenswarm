"""Archive/AST checks never execute generated content."""
import hashlib
import io
import unittest
import zipfile
from jiuwenswarm.research.checks.research import CheckError, inspect_bundle


def archive(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        for name, value in files.items():
            z.writestr(name, value)
    return out.getvalue()


class BuilderTests(unittest.TestCase):
    def fixture(self, code=None):
        return {'requirements.txt': '# stdlib', 'poc_patch.py': 'def predict(x): return 2*x\n',
                'run_benchmark.py': code or 'import json\nprint(json.dumps({"metrics":{"mae":0}}))\n'}

    def test_valid_and_exact_members(self):
        files = self.fixture()
        result = inspect_bundle(archive(files), ['mae'], {})
        self.assertTrue(all(x['syntax_result'] in {'pass', 'not_applicable'} for x in result['file_checks']))
        self.assertEqual(result['output_format_check']['result'], 'pass')
        for name in ['../escape', '/absolute.py', 'EXTRA.py', 'extra.py']:
            with self.assertRaises(CheckError):
                inspect_bundle(archive(dict(files, **{name: 'no'})), ['mae'], {})

    def test_forbidden_dynamic_syntax_and_extra_print(self):
        for code in ['import os\n', '__import__("sys")\n', 'eval("1")\n',
                     'import importlib\n', 'def broken(:\n', 'print("side")\nimport json\nprint(json.dumps({"metrics":{"mae":0}}))']:
            with self.assertRaises(CheckError):
                inspect_bundle(archive(self.fixture(code)), ['mae'], {})

    def test_no_generated_execution_and_missing_metric(self):
        files = self.fixture()
        files['poc_patch.py'] = 'raise RuntimeError("never executed")\n'
        inspect_bundle(archive(files), ['mae'], {})
        with self.assertRaises(CheckError):
            inspect_bundle(archive(files), ['not_printed'], {})
