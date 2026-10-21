"""Protected hardware observation under the scientific execution profile."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from .contracts import ResearchError
from .executor import InvocationBinding, PreparedEnvironment, _await
from .execution_jobs import _new_root_traversable
from .state import json_bytes


_PROGRAM = r'''
import glob, json, os, platform, re
from datetime import datetime, timezone
from pathlib import Path
devices = glob.glob('/dev/nvidia*') + glob.glob('/dev/dri/render*') + glob.glob('/dev/kfd')
if devices:
    raise RuntimeError('GPU device profiles require separate qualified observation')
cpu = {}
for line in Path('/proc/cpuinfo').read_text().splitlines():
    if ':' in line:
        key, value = line.split(':', 1)
        if value.strip(): cpu.setdefault(key.strip(), value.strip())
model = cpu.get('model name') or cpu.get('Hardware') or cpu.get('Processor') or platform.processor()
if not model: raise RuntimeError('Actual CPU model is unavailable')
memory = re.search(r'^MemTotal:\s+(\d+)\s+kB$', Path('/proc/meminfo').read_text(), re.M)
cores = os.cpu_count()
if not memory or not cores: raise RuntimeError('Actual CPU or RAM observation is unavailable')
driver = None
driver_file = Path('/proc/driver/nvidia/version')
if driver_file.is_file():
    reported = driver_file.read_text()
    match = re.search(r'Kernel Module\s+([0-9.]+)', reported)
    if not match: raise RuntimeError('Detected GPU driver version is not parseable')
    driver = match.group(1)
cuda = None
version_file = Path('/usr/local/cuda/version.json')
if version_file.is_file():
    reported = json.loads(version_file.read_text())
    cuda = reported.get('cuda', {}).get('version')
    if not isinstance(cuda, str) or not cuda: raise RuntimeError('Detected CUDA version is not parseable')
print(json.dumps({'gpu_model': None, 'gpu_count': 0, 'gpu_memory_mb': None,
 'driver_version': driver, 'cuda_version': cuda, 'cpu_model': model, 'cpu_cores': cores,
 'ram_mb': int(memory.group(1)) // 1024, 'os': platform.system() + ' ' + platform.release() + ' ' + platform.machine(),
 'captured_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}, separators=(',', ':'), allow_nan=False))
'''


@dataclass(frozen=True)
class _HardwareJob:
    job_id: str
    contract_ref: Mapping
    invocation_id: str
    cwd: Path
    timeout_s: float
    memory_mb: int
    pids_max: int
    environment: PreparedEnvironment
    readonly_mounts: tuple = field(default_factory=tuple)

    @property
    def argv(self): return ('/usr/local/bin/python3', '-I', '-c', _PROGRAM)

    @property
    def environment_ref(self): return self.environment.ref


class SameSandboxHardwareCapture:
    def __init__(self, store, executor, *, authorize_binding, gpu_required: bool):
        if not callable(authorize_binding) or type(gpu_required) is not bool:
            raise ValueError('Protected binding authorization and explicit device profile are required')
        self.store, self.executor, self.authorize_binding = store, executor, authorize_binding
        self.gpu_required = gpu_required
        self._claimed, self._jobs = set(), []

    @property
    def owned_job_ids(self): return tuple(self._jobs)

    async def __call__(self, binding, *, prepared_environment, timeout_s, memory_mb, pids_max):
        if not isinstance(binding, InvocationBinding) or not isinstance(prepared_environment, PreparedEnvironment):
            raise ResearchError('auth', 'Protected hardware invocation and prepared environment are required')
        authorized = await _await(self.authorize_binding(binding))
        if authorized != binding or os.name != 'posix' or os.geteuid() != 0:
            raise ResearchError('auth', 'Protected hardware binding was not authorized')
        failures = self.executor.prerequisites()
        if failures: raise ResearchError('unavailable', ';'.join(failures))
        if binding.invocation_id in self._claimed:
            raise ResearchError('conflict', 'Hardware observation cannot silently replay')
        for value in [timeout_s, memory_mb, pids_max]:
            if type(value) not in (int, float) or value <= 0:
                raise ResearchError('validation', 'Explicit positive hardware probe limits are required')
        self._claimed.add(binding.invocation_id)
        root = self.executor.workspace_root
        root.mkdir(parents=True, exist_ok=True, mode=0o711)
        key = hashlib.sha256(json_bytes({'contract_ref': binding.contract_ref, 'invocation_id': binding.invocation_id,
                                        'operation': 'hardware_observation'})).hexdigest()
        parent = root / ('hardware-' + key); _new_root_traversable(parent)
        work = parent / 'work'; work.mkdir(mode=0o700)
        _new_root_traversable(work / '.venv', mode=0o555)
        os.chown(work, self.executor.uid, self.executor.gid)
        job = _HardwareJob('hardware-' + uuid.uuid4().hex, binding.contract_ref, binding.invocation_id,
                           work, timeout_s, memory_mb, pids_max, prepared_environment)
        self._jobs.append(job.job_id)
        receipt = await self.executor._run_kernel(job, self.executor._sandbox(job), output_parent=parent)
        if receipt['exit_code'] != 0 or receipt['termination_reason'] != 'completed':
            raise ResearchError('unavailable', 'Actual same-profile hardware observation failed',
                                {'evidence_refs': [receipt['stdout_ref'], receipt['stderr_ref']]})
        inventory = json.loads(self.store.read_blob(receipt['stdout_ref']).decode('utf-8'))
        inventory['hardware_id'] = 'hardware:' + hashlib.sha256(json_bytes(inventory)).hexdigest()
        observation = {'contract_ref': binding.contract_ref, 'invocation_id': binding.invocation_id,
            'run_id': binding.contract['run_id'], 'observed_runtime': True, 'inventory': inventory, 'execution_receipt': receipt}
        ref = self.store.append_record('hardware_observation', observation)
        if self.gpu_required and inventory['gpu_count'] == 0:
            raise ResearchError('unavailable', 'The required GPU is not visible under the qualified scientific profile',
                                {'evidence_refs': [ref]})
        return {'inventory': inventory, 'observation_ref': ref}
