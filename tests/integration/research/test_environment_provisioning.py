"""Real offline package installation in the job-owned Linux executor profile.

The tiny wheel is a controlled mechanics fixture, not scientific evidence or a
production environment approval. Candidate package code never runs in the parent.
"""
import base64
import builtins
import csv
import hashlib
import io
import os
import platform
import sys
import zipfile
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest

from tests.integration.research.test_executor import actual_executor
from jiuwenswarm.research.contracts import validate
from jiuwenswarm.research.execution_jobs import ApprovedEnvironment, ScienceExecutionAdapter, ScienceProfile
from jiuwenswarm.research.executor import ExecutorBlocked, InvocationBinding
from jiuwenswarm.research.hardware import SameSandboxHardwareCapture
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore


def fixture_wheel():
    entries = {
        'unit_science/__init__.py': b'raise RuntimeError("Fixture package must never be imported by the parent")\n',
        'unit_science_probe.pth': b'import builtins; builtins.AI4R_CANDIDATE_IMPORT_WAS_EXECUTED = True\n',
        'unit_science-1.0.0.dist-info/METADATA': b'Metadata-Version: 2.1\nName: unit-science\nVersion: 1.0.0\n',
        'unit_science-1.0.0.dist-info/WHEEL': b'Wheel-Version: 1.0\nGenerator: source-bound-mechanics-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
    }
    rows = []
    for name, data in entries.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
        rows.append([name, 'sha256=' + digest, str(len(data))])
    rows.append(['unit_science-1.0.0.dist-info/RECORD', '', ''])
    record = io.StringIO(newline=''); csv.writer(record, lineterminator='\n').writerows(rows)
    entries['unit_science-1.0.0.dist-info/RECORD'] = record.getvalue().encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        for name, data in entries.items(): archive.writestr(name, data)
    return output.getvalue()


@pytest.mark.asyncio
async def test_actual_nonempty_lock_install_and_original_receipt_without_parent_execution(actual_executor):
    executor, make, captured, work = actual_executor
    prepared_root = work.parent / 'prepared'; prepared_root.mkdir(mode=0o711)
    groups = []
    captures = []
    try:
        with closing(SQLiteRunStore(work.parent / 'private-store')) as store:
            approval = store.put_blob(b'Controlled offline install mechanics fixture, not a production approval.\n')
            wheel_ref = store.put_blob(fixture_wheel())
            lock = {'schema_version': '1.0.0', 'id': 'unit_environment', 'platform': 'controlled-linux-profile',
                    'requirements_ref': store.put_blob(b'unit-science==1.0.0\n'), 'package_refs': [wheel_ref], 'approval_ref': approval}
            lock_ref = store.put_record('environment-lock', lock)
            contract = {'run_id': 'controlled-run', 'node_id': 'controlled-benchmark', 'attempt_id': 'controlled-attempt',
                'inputs': [{'name': 'environment_lock', 'artifact_refs': [lock_ref]},
                           {'name': 'poc_manifest', 'artifact_refs': [store.put_blob(b'controlled-poc-manifest')]}],
                'subnode_limits': {'time_s': 30, 'memory_mb': 256}, 'bindings': [{'limits': {'time_s': 30, 'memory_mb': 256}}]}
            binding = InvocationBinding(store.put_blob(b'controlled-frozen-contract'), 'controlled-provision-invocation', contract)
            profile = ScienceProfile(work.parent / 'assets', prepared_root, 256, 32, 10, 20,
                (), (), Path('/usr/local/bin/uv'), Path(sys._base_executable))
            approval_entry = ApprovedEnvironment(lock_ref, approval, (platform.system(), platform.machine(), platform.python_version()),
                {wheel_ref['sha256']: 'unit_science-1.0.0-py3-none-any.whl'})
            executor.preparation_roots = (prepared_root,)
            executor.authorize_provisioning = lambda job, *, binding: job
            executor.capture = store.put_blob

            async def launch(job, *, binding):
                with pytest.raises(ExecutorBlocked, match='PROVISIONING_CAPTURE_IDENTITY_INVALID'):
                    await executor.run_provisioning(replace(job, requirements_ref={'id': 'changed', 'sha256': '0' * 64}), binding=binding)
                alias = prepared_root / 'alias'; alias.symlink_to(job.environment.parent, target_is_directory=True)
                try:
                    with pytest.raises(ExecutorBlocked, match='PROVISIONING_PATH_ALIAS_DENIED'):
                        await executor.run_provisioning(replace(job, environment=alias / 'venv'), binding=binding)
                finally: alias.unlink()
                wheel = next(job.wheelhouse.iterdir()); wheel.chmod(0o644)
                try:
                    with pytest.raises(ExecutorBlocked, match='PROVISIONING_WHEEL_BYTES_CHANGED'):
                        await executor.run_provisioning(job, binding=binding)
                finally: wheel.chmod(0o444)
                groups.append(job.job_id)
                result = await executor.run_provisioning(job, binding=binding)
                assert result['exit_code'] == 0, store.read_blob(result['stderr_ref']).decode()
                proof = store.read_record(result['observed_limits']['isolation_probe_ref'])
                assert proof['ready'] and proof['executor_uid'] == 10002 and proof['executor_gid'] == 10002
                assert proof['network'] == 'none' and all(proof['denied_paths'].values())
                assert int(proof['cap_effective'], 16) == 0 and proof['no_new_privileges'] == '1'
                assert result['observed_limits']['memory_max'] == str(256 * 1024 * 1024)
                assert result['observed_limits']['pids_max'] == '32'
                with pytest.raises(ExecutorBlocked, match='PROVISIONING_JOB_REPLAY_DENIED'):
                    await executor.run_provisioning(job, binding=binding)
                with pytest.raises(ExecutorBlocked, match='PROTECTED_PROVISIONING_BINDING_REQUIRED'):
                    await executor.run_provisioning(replace(job, invocation_id='foreign'), binding=binding)
                return result

            adapter = ScienceExecutionAdapter(store, profile, approved_environments=[approval_entry],
                workspace_allocator=None, hardware_capture=None, provision_runner=launch)
            receipt = await adapter.provisioner(contract, {'environment_lock': lock}, {'unit-science': '1.0.0'}, binding=binding)
            validate('provisioning-receipt', receipt)
            assert receipt['status'] == 'succeeded'
            assert receipt['packages'] == [{'name': 'unit-science', 'locked_version': '1.0.0',
                                            'installed_version': '1.0.0', 'hash_verified': True}]
            assert receipt['venv_path'] == '/workspace/poc/.venv'
            assert [effect['op'] for effect in receipt['effects']] == ['create_venv', 'install_package']
            assert not getattr(builtins, 'AI4R_CANDIDATE_IMPORT_WAS_EXECUTED', False)
            assert executor.active == {}
            adapter.environment_verifier(adapter._prepared[binding.invocation_id][0])
            executor.environment_verifier = adapter.environment_verifier
            capture = SameSandboxHardwareCapture(store, executor, authorize_binding=lambda binding: binding, gpu_required=False)
            captures.append(capture)
            adapter.hardware_capture = capture
            hardware = await adapter.hardware_probe(contract, binding=binding)
            assert hardware['gpu_count'] == 0 and hardware['gpu_model'] is None and hardware['gpu_memory_mb'] is None
            assert hardware['cpu_model'] and hardware['cpu_cores'] >= 1 and hardware['ram_mb'] >= 1
            assert 'Linux' in hardware['os'] and hardware['hardware_id'].startswith('hardware:')
            # Reuse the captured inventory without repeating the hardware process.
            assert await adapter.hardware_probe(contract, binding=binding) == hardware
            assert len(capture.owned_job_ids) == 1
            gpu_capture = SameSandboxHardwareCapture(store, executor, authorize_binding=lambda binding: binding, gpu_required=True)
            captures.append(gpu_capture)
            with pytest.raises(ResearchError, match='required GPU'):
                await gpu_capture(InvocationBinding(binding.contract_ref, 'controlled-gpu-required', contract),
                    prepared_environment=adapter._prepared[binding.invocation_id][0], timeout_s=5, memory_mb=256, pids_max=32)
    finally:
        for capture in captures: groups.extend(capture.owned_job_ids)
        for identifier in groups:
            group = Path(executor.cgroup_root) / identifier
            if group.exists():
                assert group.resolve().parent == Path(executor.cgroup_root).resolve()
                assert not (group / 'cgroup.procs').read_text().strip()
                group.rmdir()
