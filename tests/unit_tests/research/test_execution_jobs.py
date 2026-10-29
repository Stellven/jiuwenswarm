"""Protected host preparation tests; no generated trial or model is invoked."""
import asyncio
import io
import os
import platform
import stat
import sys
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path

from jiuwenswarm.research.contracts import ResearchError, validate
from jiuwenswarm.research.execution_jobs import ApprovedEnvironment, ScienceExecutionAdapter, ScienceProfile, allocate_science_workspace
from jiuwenswarm.research.executor import InvocationBinding
from jiuwenswarm.research.state import SQLiteRunStore


class ExecutionJobsTests(unittest.TestCase):
    def fixture(self, directory, store, platform_fact=None):
        approval = store.put_blob(b'Unit-test approved stdlib-only environment; not scientific evidence.\n')
        lock = {'schema_version': '1.0.0', 'id': 'unit_stdlib', 'platform': 'unit-explicit-platform',
                'requirements_ref': store.put_blob(b'# stdlib only\n'), 'package_refs': [], 'approval_ref': approval}
        lock_ref = store.put_record('environment-lock', lock)
        manifest_ref = store.put_blob(b'fixture manifest identity')
        contract = {'run_id': 'run:unit', 'node_id': 'benchmark', 'attempt_id': 'attempt:unit',
                    'inputs': [{'name': 'environment_lock', 'artifact_refs': [lock_ref]},
                               {'name': 'poc_manifest', 'artifact_refs': [manifest_ref]}],
                    'subnode_limits': {'time_s': 30, 'memory_mb': 256}, 'bindings': [{'limits': {'time_s': 30, 'memory_mb': 256}}]}
        binding = InvocationBinding(store.put_blob(b'fixture frozen contract identity'), 'invocation:unit', contract)
        profile = ScienceProfile(Path(directory) / 'assets', Path(directory) / 'environments', 256, 16, 5, 15,
                                 ('--seed', '{seed}'), ('--seed', '{seed}'), Path('/usr/local/bin/uv'), Path(sys._base_executable))
        approved = ApprovedEnvironment(lock_ref, approval, platform_fact or (platform.system(), platform.machine(), platform.python_version()), {})
        adapter = ScienceExecutionAdapter(store, profile, approved_environments=[approved],
                                          workspace_allocator=None, hardware_capture=None)
        return adapter, contract, binding, lock

    def test_wrong_platform_and_unbound_call_publish_no_environment(self):
        with tempfile.TemporaryDirectory() as directory, closing(SQLiteRunStore(Path(directory) / 'store')) as store:
            adapter, contract, binding, lock = self.fixture(directory, store, ('unsupported', 'unsupported', 'unsupported'))
            with self.assertRaises(ResearchError):
                asyncio.run(adapter.provisioner(contract, {'environment_lock': lock}, {}, binding=binding))
            self.assertFalse(adapter.profile.environment_root.exists())
            with self.assertRaises(ResearchError):
                asyncio.run(adapter.hardware_probe(contract, binding=None))

    @unittest.skipUnless(os.name == 'posix' and hasattr(os, 'geteuid') and os.geteuid() == 0, 'actual Linux root broker required')
    def test_exact_empty_lock_provisions_without_package_install_and_detects_tamper(self):
        with tempfile.TemporaryDirectory() as directory, closing(SQLiteRunStore(Path(directory) / 'store')) as store:
            adapter, contract, binding, lock = self.fixture(directory, store)
            receipt = asyncio.run(adapter.provisioner(contract, {'environment_lock': lock}, {}, binding=binding))
            self.assertEqual(receipt['status'], 'succeeded')
            self.assertEqual(receipt['packages'], [])
            self.assertEqual([event['op'] for event in receipt['effects']], ['create_venv'])
            prepared = adapter._prepared[binding.invocation_id][0]
            adapter.environment_verifier(prepared)
            # Restore controlled test-directory writability for this mutation.
            prepared.source.chmod(0o755)
            (prepared.source / 'unexpected.txt').write_bytes(b'not in prepared inventory')
            with self.assertRaises(ResearchError): adapter.environment_verifier(prepared)
            with self.assertRaises(ResearchError):
                asyncio.run(adapter.hardware_probe(contract, binding=binding))

    @unittest.skipUnless(os.name == 'posix' and hasattr(os, 'geteuid') and os.geteuid() == 0, 'actual Linux root broker required')
    def test_actual_allocator_ownership_and_no_replay(self):
        with tempfile.TemporaryDirectory() as directory, closing(SQLiteRunStore(Path(directory) / 'store')) as store:
            adapter, contract, binding, lock = self.fixture(directory, store)
            root = Path(directory) / 'poc'
            work = allocate_science_workspace(root, binding, 1, 'baseline')
            try:
                self.assertEqual(work.stat().st_uid, 10002)
                self.assertEqual(work.stat().st_gid, 10002)
                self.assertEqual(stat.S_IMODE(work.stat().st_mode), 0o700)
                self.assertEqual(work.parent.stat().st_uid, 0)
                self.assertEqual(stat.S_IMODE(work.parent.stat().st_mode), 0o711)
                with self.assertRaises(FileExistsError): allocate_science_workspace(root, binding, 1, 'baseline')
            finally:
                # Restore only this test allocation for TemporaryDirectory's
                # cleanup; CHOWN is sufficient, no DAC_OVERRIDE/FOWNER needed.
                os.chown(work, 0, 0)

    @unittest.skipUnless(os.name == 'posix' and hasattr(os, 'geteuid') and os.geteuid() == 0, 'actual Linux root broker required')
    def test_nonempty_receipt_uses_source_package_and_effect_fields(self):
        """Installer is a controlled double; this tests receipt projection only."""
        with tempfile.TemporaryDirectory() as directory, closing(SQLiteRunStore(Path(directory) / 'store')) as store:
            adapter, contract, binding, lock = self.fixture(directory, store)
            wheel = io.BytesIO()
            with zipfile.ZipFile(wheel, 'w') as archive:
                archive.writestr('unit_pkg-1.0.dist-info/METADATA', 'Metadata-Version: 2.1\nName: unit-pkg\nVersion: 1.0\n')
                archive.writestr('unit_pkg-1.0.dist-info/WHEEL', 'Wheel-Version: 1.0\nGenerator: unit-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
            package_ref = store.put_blob(wheel.getvalue())
            lock = dict(lock, requirements_ref=store.put_blob(b'unit-pkg==1.0\n'), package_refs=[package_ref])
            lock_ref = store.put_record('environment-lock', lock)
            contract['inputs'][0]['artifact_refs'] = [lock_ref]
            approved = ApprovedEnvironment(lock_ref, lock['approval_ref'], (platform.system(), platform.machine(), platform.python_version()),
                                           {package_ref['sha256']: 'unit_pkg-1.0-py3-none-any.whl'})
            adapter.approved = {lock_ref['sha256']: approved}

            async def controlled_installer(job, *, binding):
                argv = job.argv
                self.assertIn('--offline', argv); self.assertIn('--no-index', argv); self.assertIn('--require-hashes', argv)
                environment = job.environment
                site = next((environment / 'lib').glob('python*/site-packages'))
                metadata = site / 'unit_pkg-1.0.dist-info'; metadata.mkdir()
                (metadata / 'METADATA').write_text('Metadata-Version: 2.1\nName: unit-pkg\nVersion: 1.0\n', encoding='utf-8')
                (site / 'untrusted.pth').write_text('raise RuntimeError("candidate code must not execute in parent")\n', encoding='utf-8')
                return []

            adapter._command = controlled_installer
            receipt = asyncio.run(adapter.provisioner(contract, {'environment_lock': lock}, {'unit-pkg': '1.0'}, binding=binding))
            validate('provisioning-receipt', receipt)
            self.assertEqual(receipt['packages'], [{'name': 'unit-pkg', 'locked_version': '1.0',
                                                   'installed_version': '1.0', 'hash_verified': True}])
            self.assertEqual(receipt['effects'], [
                {'op': 'create_venv', 'target': '/workspace/poc/.venv', 'outcome': 'ok'},
                {'op': 'install_package', 'target': 'unit-pkg==1.0', 'outcome': 'ok'}])
