from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import subprocess

from jiuwenswarm.ccv2.ccv2 import CCError, Host
from .product_fixture import fixture
from jiuwenswarm.ccv2.source_build import materialize


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.host = Host(self.root/'store')
        self.template, self.change = fixture(self.root/'input', self.host)

    def tearDown(self): self.temp.cleanup()

    def build(self, change=None, **options):
        return materialize(self.host, self.template, change or self.change, self.root/'output', **options)

    def test_exact_change_build_and_provenance(self):
        built = self.build(trusted_build=True)
        record = json.loads(self.host.artifact_path(built['build_record']).read_bytes())
        self.assertEqual(record['observed_tree'], self.change['tree'])
        self.assertIn(b'FACTOR = 2', (self.root/'output/payload/server.py').read_bytes())
        call = self.host.call(built['release'], 'inspect', {})
        self.assertEqual(call['state'], 'succeeded')
        self.assertEqual(call['provenance']['build_record'], built['build_record'])

    def test_build_authority_not_implicit(self):
        with self.assertRaises(CCError) as error: self.build()
        self.assertEqual(error.exception.code, 'BUILD_AUTHORIZATION_REQUIRED')

    def test_wrong_tree_rejected(self):
        change = deepcopy(self.change); change['tree'] = '0'*40
        with self.assertRaises(CCError) as error: self.build(change, trusted_build=True)
        self.assertEqual(error.exception.code, 'TREE_MISMATCH')
        self.assertFalse((self.root/'output').exists())

    def test_mutable_base_rejected(self):
        change = deepcopy(self.change); change['base'] = 'main'
        with self.assertRaises(CCError) as error: self.build(change, trusted_build=True)
        self.assertEqual(error.exception.code, 'MUTABLE_SOURCE')

    def test_missing_lock_rejected(self):
        change = deepcopy(self.change); change['build']['lock'] = 'missing.lock'
        with self.assertRaises(CCError) as error: self.build(change, trusted_build=True)
        self.assertEqual(error.exception.code, 'MISSING_DEPENDENCY_LOCK')

    def test_staged_source_mutation_rejected(self):
        change = deepcopy(self.change)
        change['build']['command'] = ['{python}', '-c', "from pathlib import Path; import subprocess; Path('server.py').write_text('changed'); subprocess.run(['git','add','server.py'],check=True)"]
        with self.assertRaises(CCError) as error: self.build(change, trusted_build=True)
        self.assertEqual(error.exception.code, 'BUILD_MUTATED_SOURCE')

    def test_no_overwrite(self):
        (self.root/'output').mkdir()
        with self.assertRaises(CCError) as error: self.build(trusted_build=True)
        self.assertEqual(error.exception.code, 'OUTPUT_EXISTS')

    def test_failure_retains_stdout_stderr_and_exit(self):
        change = deepcopy(self.change)
        change['build']['command'] = ['{python}', '-c', "import sys; print('build observation'); print('build failure',file=sys.stderr); sys.exit(3)"]
        with self.assertRaises(CCError) as error: self.build(change, trusted_build=True)
        record = json.loads(Path(error.exception.path).read_bytes())
        self.assertEqual(record['state'], 'failed')
        self.assertEqual(record['steps'][-1]['exit_code'], 3)
        self.assertIn('build observation', record['steps'][-1]['stdout'])
        self.assertIn('build failure', record['steps'][-1]['stderr'])

    def test_timeout_is_durable_unknown(self):
        change = deepcopy(self.change)
        change['build']['command'] = ['{python}', '-c', "import time; print('started',flush=True); time.sleep(5)"]
        with self.assertRaises(CCError) as error: self.build(change, trusted_build=True, timeout=.5)
        self.assertEqual(error.exception.code, 'BUILD_TIMEOUT')
        record = json.loads(Path(error.exception.path).read_bytes())
        self.assertEqual(record['state'], 'unknown')
        self.assertIn('started', record['steps'][-1]['stdout'])

    def test_empty_patch_rebuilds_exact_base(self):
        repository = self.root/'input/repository'
        tree = subprocess.check_output(['git', 'rev-parse', self.change['base']+'^{tree}'], cwd=repository).decode().strip()
        patch = self.root/'empty.patch'; patch.write_bytes(b'')
        change = deepcopy(self.change); change.update(tree=tree, patch=self.host.put_artifact(patch))
        built = self.build(change, trusted_build=True)
        self.assertEqual(built['source_tree'], tree)

    def test_unresolved_lfs_pointer_rejected(self):
        repository = self.root/'input/repository'
        (repository/'weights.bin').write_text('version https://git-lfs.github.com/spec/v1\noid sha256:'+'a'*64+'\nsize 999\n', encoding='utf-8')
        def git(*args): return subprocess.check_output(['git', *args], cwd=repository, stderr=subprocess.PIPE).decode().strip()
        git('add', 'weights.bin')
        git('-c', 'user.name=CC fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'LFS pointer fixture')
        patch = self.root/'empty.patch'; patch.write_bytes(b'')
        change = deepcopy(self.change); change.update(base=git('rev-parse', 'HEAD'), tree=git('rev-parse', 'HEAD^{tree}'), patch=self.host.put_artifact(patch))
        with self.assertRaises(CCError) as error: self.build(change, trusted_build=True)
        self.assertEqual(error.exception.code, 'UNSUPPORTED_SOURCE_MATERIAL')


if __name__ == '__main__': unittest.main()
