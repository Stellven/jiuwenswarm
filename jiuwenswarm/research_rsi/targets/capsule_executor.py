"""Root-only finite whole-capsule dispatch through the exact historical kernel.

The immutable V18 executor is reused with private bounded pipe adapters. No
generated code executes in this owner, and no model, admission or activation
authority is provided. Root separately approves a public development grant.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import re
import stat
import time
import types

from ..records import encoded
from .capsules import public_fixtures, registered_capsule
from .capsule_runtime import (BOOTSTRAP_SCHEMA, MAX_OUTPUT_BYTES, capsule_job_assets,
    check_capsule_output, verify_runtime)

V18_EXECUTOR_SHA256 = '25c77a8c6830e32e83a6b77334d82e12350912fe33b312df8d5b1aad26bc4715'
GRANT_SCHEMA = 'ai4r-rsi-whole-capsule-development-grant:2'
BINDING_SCHEMA = 'ai4r-rsi-whole-capsule-candidate-binding:1'


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(value):
    need(isinstance(value, dict) and set(value) == {'id', 'sha256'}
        and isinstance(value['id'], str) and 0 < len(value['id']) <= 512
        and isinstance(value['sha256'], str) and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'EXACT_REF_REQUIRED')
    return value


def validate_grant(grant, manifest):
    fields = {'schema', 'bootstrap_schema', 'run_id', 'capsule_name', 'runtime_manifest_sha256', 'parent_sha256',
        'fixture_sha256', 'fixture_count', 'roles', 'max_executions', 'iterations', 'limits',
        'worker', 'expires_unix_s', 'scope', 'production_admission'}
    need(isinstance(grant, dict) and set(grant) == fields and grant['schema'] == GRANT_SCHEMA,
         'CLOSED_ROOT_DEVELOPMENT_GRANT_REQUIRED')
    need(grant['bootstrap_schema'] == BOOTSTRAP_SCHEMA, 'EXACT_VERSIONED_CAPSULE_BOOTSTRAP_REQUIRED')
    target = registered_capsule(grant['capsule_name'])
    need(target.public_evaluation_available and grant['scope'] == 'public_m1_development_only'
         and grant['production_admission'] == 'UNKNOWN', 'FINITE_PUBLIC_DEVELOPMENT_SCOPE_REQUIRED')
    need(isinstance(grant['run_id'], str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', grant['run_id']),
         'BOUNDED_DEVELOPMENT_RUN_ID_REQUIRED')
    fixtures = public_fixtures(grant['capsule_name'])
    need(grant['fixture_sha256'] == digest(encoded(fixtures)) and type(grant['fixture_count']) is int
         and grant['fixture_count'] == len(fixtures), 'EXACT_PUBLIC_FIXTURE_INVENTORY_REQUIRED')
    need(grant['roles'] in (['parent'], ['parent', 'candidate'])
         and type(grant['max_executions']) is int
         and grant['max_executions'] == len(fixtures) * len(grant['roles']), 'EXACT_ROLE_EXECUTION_BUDGET_REQUIRED')
    need(type(grant['iterations']) is int and 1 <= grant['iterations'] <= 10000, 'FROZEN_BOUNDED_ITERATIONS_REQUIRED')
    need(grant['runtime_manifest_sha256'] == digest(encoded(manifest)), 'EXACT_REVIEWED_RUNTIME_REQUIRED')
    carrier = 'source/jiuwenswarm/' + target.carrier_path
    need(grant['parent_sha256'] == next((row['sha256'] for row in manifest['files'] if row['path'] == carrier), None),
         'EXACT_ORIGINAL_CAPSULE_PARENT_REQUIRED')
    limits = grant['limits']
    need(isinstance(limits, dict) and set(limits) == {'timeout_s', 'memory_mb', 'pids_max', 'wall_s'}, 'CLOSED_JOB_LIMITS_REQUIRED')
    for name, ceiling in {'timeout_s': 300, 'memory_mb': 65536, 'pids_max': 256, 'wall_s': 3600}.items():
        need(type(limits[name]) is int and 0 < limits[name] <= ceiling, 'FINITE_JOB_LIMIT_REQUIRED')
    need(limits['timeout_s'] <= limits['wall_s'] and type(grant['expires_unix_s']) is int,
         'FINITE_DEVELOPMENT_DEADLINE_REQUIRED')
    need(isinstance(grant['worker'], dict) and set(grant['worker']) == {'contract_ref', 'environment_ref', 'hardware_ref'},
         'EXACT_ROOT_WORKER_BINDINGS_REQUIRED')
    for value in grant['worker'].values():
        pin(value)
    return grant


def validate_candidate_binding(binding, grant, candidate_ref):
    fields = {'schema', 'run_id', 'capsule_name', 'runtime_manifest_sha256', 'parent_sha256',
              'mutable_path', 'candidate_ref', 'grant_sha256'}
    need(isinstance(binding, dict) and set(binding) == fields and binding['schema'] == BINDING_SCHEMA,
         'EXACT_ROOT_CANDIDATE_BINDING_REQUIRED')
    for name in ('run_id', 'capsule_name', 'runtime_manifest_sha256', 'parent_sha256'):
        need(binding[name] == grant[name], 'CANDIDATE_DEVELOPMENT_SCOPE_DIFFERS')
    need(binding['grant_sha256'] == digest(encoded(grant))
         and binding['mutable_path'] == registered_capsule(grant['capsule_name']).carrier_path
         and binding['candidate_ref'] == pin(candidate_ref)
         and candidate_ref['sha256'] != grant['parent_sha256'], 'ONLY_CHANGED_ACTUAL_WORKER_SOURCE_ALLOWED')
    return binding


def executor_abi(base, job_type, mount_type):
    source = Path(inspect.getsourcefile(base))
    need(digest(source.read_bytes()) == V18_EXECUTOR_SHA256, 'EXACT_HISTORICAL_V18_EXECUTOR_REQUIRED')
    expected = set(('job_id invocation_id contract_ref run_id node_id attempt_id sequence role repeat_index seed argv cwd '
        'timeout_s memory_mb pids_max baseline_ref validation_ref environment_ref subject_ref hardware_ref readonly_mounts environment').split())
    need(set(inspect.signature(job_type).parameters) == expected, 'HISTORICAL_EXECUTION_JOB_ABI_DIFFERS')
    need(set(inspect.signature(mount_type).parameters) == {'source', 'target', 'ref'}, 'HISTORICAL_READONLY_MOUNT_ABI_DIFFERS')
    need(set(inspect.signature(base._run_kernel).parameters) == {'self', 'job', 'command', 'output_parent',
        'stdin_bytes', 'stdout_line_observer', 'stdout_line_limit'}, 'HISTORICAL_KERNEL_ABI_DIFFERS')
    return {'executor_source_sha256': V18_EXECUTOR_SHA256,
        'adapter_sha256': digest(Path(__file__).read_bytes()), 'combined_stdout_stderr_limit_bytes': MAX_OUTPUT_BYTES,
        'separate_probe_limit_bytes': 4096}


class BoundedCapture:
    """Parameterize the already proven pipe fence without touching its owner."""
    PREFIX = b'AI4R_EXECUTOR_PROBE_V1 '

    def __init__(self, kill, limit):
        need(type(limit) is int and 0 < limit <= MAX_OUTPUT_BYTES, 'ROOT_OUTPUT_BOUND_REQUIRED')
        self.kill, self.limit, self.used, self.overflow = kill, limit, 0, False

    async def take(self, reader, chunk):
        remaining = self.limit - self.used
        kept = chunk[:remaining]; self.used += len(kept)
        if len(chunk) > remaining:
            if not self.overflow:
                self.overflow = True; self.kill()
            while await reader.read(65536):
                pass
        return kept

    def pipe(self, reader, *, probe=False):
        fence = self
        class Pipe:
            async def readline(self):
                frame = await reader.readline()
                if probe and frame.startswith(fence.PREFIX) and len(frame) <= 4096 + len(fence.PREFIX) + 1:
                    return frame
                return await fence.take(reader, frame)
            async def read(self, size=65536):
                need(type(size) is int and 0 < size <= 65536, 'FINITE_CAPTURE_READ_REQUIRED')
                return await fence.take(reader, await reader.read(size))
        return Pipe()


def bounded_executor(base, *, output_limit=MAX_OUTPUT_BYTES):
    """Reuse canonical kernel code with private globals and bounded pipe readers.

    The operational dispatcher verifies the exact base ABI first. This helper
    does not mutate the installed module, asyncio or completed helper evidence.
    """
    need(type(output_limit) is int and 0 < output_limit <= MAX_OUTPUT_BYTES, 'ROOT_OUTPUT_BOUND_REQUIRED')
    class Executor(base):
        async def _run_kernel(self, job, command, **kwargs):
            canonical = base._run_kernel
            original_asyncio = canonical.__globals__['asyncio']
            def kill():
                active = self.active.get(job.job_id)
                need(active is not None, 'OWNED_OUTPUT_LIMIT_GROUP_UNAVAILABLE')
                (active[1] / 'cgroup.kill').write_text('1')
            fence = BoundedCapture(kill, output_limit)
            class Process:
                def __init__(self, process):
                    self.process = process
                    self.stdout = fence.pipe(process.stdout, probe=True)
                    self.stderr = fence.pipe(process.stderr)
                def __getattr__(self, name):
                    return getattr(self.process, name)
            class Asyncio:
                def __getattr__(self, name):
                    return getattr(original_asyncio, name)
                async def create_subprocess_exec(self, *args, **kw):
                    return Process(await original_asyncio.create_subprocess_exec(*args, **kw))
            scoped = types.FunctionType(canonical.__code__, dict(canonical.__globals__, asyncio=Asyncio()),
                canonical.__name__, canonical.__defaults__, canonical.__closure__)
            scoped.__kwdefaults__ = canonical.__kwdefaults__
            receipt = await scoped(self, job, command, **kwargs)
            receipt['observed_limits'] = {**receipt.get('observed_limits', {}),
                'admin_output_limit_bytes': fence.limit, 'admin_output_captured_bytes': fence.used,
                'admin_output_truncated': fence.overflow,
                'admin_kernel_source_sha256': digest(Path(inspect.getsourcefile(base)).read_bytes()),
                'admin_output_adapter_sha256': digest(Path(__file__).read_bytes())}
            if fence.overflow and receipt['termination_reason'] == 'completed':
                receipt['termination_reason'] = 'output_limit_exceeded'
            return receipt
    return Executor


def _root_custody(path, *, directory=False):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)), 'ROOT_REAL_PATH_REQUIRED')
    for parent in (path, *path.parents):
        meta = parent.stat()
        need(meta.st_uid == 0 and not meta.st_mode & 0o022, 'ROOT_IMMUTABLE_PATH_REQUIRED')
    meta = path.stat()
    need(stat.S_ISDIR(meta.st_mode) if directory else stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1,
         'ROOT_PATH_TYPE_REQUIRED')
    return path


def _require_root():
    need(os.name == 'posix' and os.geteuid() == 0, 'ROOT_CAPSULE_DISPATCHER_REQUIRED')


class WholeCapsuleDispatcher:
    """Exactly granted baseline/candidate public jobs, with durable no-replay claims."""
    def __init__(self, *, root, runtime_root, manifest, grant_path, grant_sha256, cgroup_root, captures):
        _require_root()
        from jiuwenswarm.research.executor import RestrictedExecutor, ExecutionJob, ReadonlyMount
        from jiuwenswarm.research_rsi.records import RecordStore
        self.abi = executor_abi(RestrictedExecutor, ExecutionJob, ReadonlyMount)
        grant_path = _root_custody(grant_path)
        need(grant_path.stat().st_size <= 65536, 'BOUNDED_ROOT_GRANT_REQUIRED')
        grant_raw = grant_path.read_bytes()
        need(len(grant_raw) <= 65536 and digest(grant_raw) == grant_sha256, 'ROOT_REVIEWED_GRANT_BYTES_REQUIRED')
        self.grant = validate_grant(json.loads(grant_raw), manifest)
        need(grant_raw == encoded(self.grant), 'CANONICAL_ROOT_GRANT_REQUIRED')
        need(time.time() < self.grant['expires_unix_s'], 'ROOT_DEVELOPMENT_GRANT_EXPIRED')
        self.runtime_root = _root_custody(runtime_root, directory=True)
        self.manifest = verify_runtime(self.runtime_root, manifest)
        for path in self.runtime_root.rglob('*'):
            _root_custody(path, directory=path.is_dir())
            need(path.stat().st_mode & (0o001 if path.is_dir() else 0o004), 'WORKER_READABLE_RUNTIME_REQUIRED')
        self.root = _root_custody(root, directory=True)
        need(type(captures) is RecordStore, 'ROOT_CAPTURE_RECORD_STORE_REQUIRED')
        _root_custody(captures.root, directory=True)
        self.captures, self.cgroup_root = captures, _root_custody(cgroup_root, directory=True)
        self.grant_ref = captures.put(self.grant)
        self.runtime_manifest_ref = captures.put(self.manifest)
        self.job_type, self.mount_type = ExecutionJob, ReadonlyMount
        self.fixtures = public_fixtures(self.grant['capsule_name'])
        self.parent = (self.runtime_root / 'source/jiuwenswarm' / registered_capsule(self.grant['capsule_name']).carrier_path).read_bytes()
        need(digest(self.parent) == self.grant['parent_sha256'], 'FROZEN_PARENT_BYTES_DIFFER')
        self.parent_ref = captures.put_bytes(self.parent)
        self.issued = {}; self.completed = {}; self.executions = 0; self.halted = False
        self.deadline = time.monotonic() + self.grant['limits']['wall_s']
        for name in ('assets', 'work', 'claims'):
            (self.root / name).mkdir(mode=0o711, exist_ok=True)
            _root_custody(self.root / name, directory=True)
            if name in ('assets', 'work'):
                # Setup may precreate these Root-owned public job parents as
                # 0700. The dropped sandbox owner must traverse them; captures
                # and individual private job directories retain their modes.
                (self.root / name).chmod(0o711)
        def authorize(job):
            need(self.issued.get(job.job_id) == job, 'UNISSUED_WHOLE_CAPSULE_JOB'); return job
        def verify(mount):
            if mount.target == '/resources/capsule-runtime':
                need(mount.source == self.runtime_root and mount.ref['sha256'] == digest(encoded(self.manifest)),
                     'EXACT_RUNTIME_DIRECTORY_MOUNT_REQUIRED')
                verify_runtime(self.runtime_root, self.manifest)
            else:
                need(mount.source.is_file() and digest(mount.source.read_bytes()) == mount.ref['sha256'],
                     'EXACT_CAPSULE_JOB_ASSET_REQUIRED')
        self.executor = bounded_executor(RestrictedExecutor)(workspace_root=self.root / 'work',
            cgroup_root=self.cgroup_root, authorize_job=authorize,
            capture=lambda raw, **_: captures.put_bytes(raw), executor_uid=12003, executor_gid=12003,
            allowed_asset_roots=[self.root / 'assets', self.runtime_root], verify_mount=verify)
        need(not self.executor.prerequisites(), 'ACTUAL_KERNEL_CONFINEMENT_PREREQUISITES_UNAVAILABLE')

    def plan(self):
        return {'schema': 'ai4r-rsi-whole-capsule-dispatch-plan:1', 'grant_sha256': digest(encoded(self.grant)),
            'bootstrap_schema': BOOTSTRAP_SCHEMA,
            'capsule_name': self.grant['capsule_name'], 'fixture_count': len(self.fixtures),
            'maximum_executions': self.grant['max_executions'], 'roles': self.grant['roles'],
            'runtime_manifest_sha256': digest(encoded(self.manifest)), 'executor_abi': self.abi,
            'model_calls': 0, 'scope': 'public_m1_development_only', 'operational_qualification': False}

    async def evaluate(self, role, *, body, candidate_ref, binding=None):
        need(not self.halted, 'DISPATCHER_HALTED_AFTER_FAILED_OR_UNKNOWN_EXECUTION')
        need(role in self.grant['roles'] and role not in self.completed, 'ROLE_NOT_GRANTED_OR_ALREADY_COMPLETED')
        need(isinstance(body, bytes) and 0 < len(body) <= 256 * 1024 and digest(body) == pin(candidate_ref)['sha256'],
             'EXACT_BOUNDED_CANDIDATE_BYTES_REQUIRED')
        if role == 'parent':
            need(body == self.parent and binding is None, 'EXACT_BASELINE_PARENT_REQUIRED')
        else:
            need('parent' in self.completed, 'BASELINE_MUST_COMPLETE_FIRST')
            validate_candidate_binding(binding, self.grant, candidate_ref)
        need(time.time() < self.grant['expires_unix_s'] and time.monotonic() < self.deadline, 'DEVELOPMENT_DEADLINE_EXPIRED')
        self.captures.put_ref(candidate_ref, body)
        binding_ref = self.captures.put(binding) if binding is not None else None
        role_claim = self.root / 'claims' / (digest(encoded([self.grant['run_id'], role])) + '.json')
        with role_claim.open('xb') as stream:
            stream.write(encoded({'grant_ref': self.grant_ref, 'role': role, 'candidate_ref': candidate_ref, 'binding_ref': binding_ref}))
            stream.flush(); os.fsync(stream.fileno())
        rows = []
        for index, fixture in enumerate(self.fixtures):
            need(time.monotonic() < self.deadline and time.time() < self.grant['expires_unix_s'], 'DEVELOPMENT_DEADLINE_EXPIRED')
            need(self.executions < self.grant['max_executions'], 'ROOT_EXECUTION_BUDGET_EXHAUSTED')
            assets = capsule_job_assets(self.grant['capsule_name'], runtime_root=self.runtime_root,
                manifest=self.manifest, candidate=body, inputs={'packet': fixture['packet']}, iterations=self.grant['iterations'])
            ident = 'capsule-' + digest(encoded([self.grant['run_id'], role, fixture['id']]))[:48]
            asset_root = self.root / 'assets' / ident; asset_root.mkdir(mode=0o755)
            work = self.root / 'work' / ident; work.mkdir(mode=0o700); os.chown(work, 12003, 12003)
            mounts = [self.mount_type(self.runtime_root, '/resources/capsule-runtime',
                {'id': 'capsule-runtime:' + assets['runtime_manifest_sha256'], 'sha256': assets['runtime_manifest_sha256']})]
            for name, raw in assets['files'].items():
                path = asset_root / name; path.write_bytes(raw); path.chmod(0o444)
                mounts.append(self.mount_type(path, '/resources/' + name, {'id': name, 'sha256': digest(raw)}))
            input_ref = self.captures.put_bytes(assets['files']['input.json'])
            program_ref = self.captures.put_bytes(assets['files']['worker.py'])
            test_ref = self.captures.put(fixture)
            worker, limits = self.grant['worker'], self.grant['limits']
            job = self.job_type(job_id=ident, invocation_id=ident, contract_ref=worker['contract_ref'],
                run_id=self.grant['run_id'], node_id='unqualified-whole-capsule-development', attempt_id=role,
                sequence=1, role='treatment', repeat_index=index, seed=0, argv=assets['argv'], cwd=work,
                timeout_s=limits['timeout_s'], memory_mb=limits['memory_mb'], pids_max=limits['pids_max'],
                baseline_ref=self.parent_ref, validation_ref=test_ref, environment_ref=worker['environment_ref'],
                subject_ref=candidate_ref, hardware_ref=worker['hardware_ref'], readonly_mounts=tuple(mounts))
            start = {'schema': 'ai4r-rsi-whole-capsule-execution-start:1', 'job_id': ident,
                'grant_ref': self.grant_ref, 'binding_ref': binding_ref, 'runtime_manifest_ref': self.runtime_manifest_ref,
                'grant_sha256': digest(encoded(self.grant)), 'runtime_manifest_sha256': assets['runtime_manifest_sha256'],
                'bootstrap_schema': BOOTSTRAP_SCHEMA,
                'candidate_ref': candidate_ref, 'input_ref': input_ref, 'program_ref': program_ref,
                'test_ref': test_ref, 'fixture_id': fixture['id'], 'role': role, 'recorded_unix_ns': time.time_ns()}
            claim = self.root / 'claims' / (ident + '.json')
            with claim.open('xb') as stream:
                stream.write(encoded(start)); stream.flush(); os.fsync(stream.fileno())
            start_ref = self.captures.put(start)
            self.executions += 1; self.issued[ident] = job
            self.halted = True  # Unknown/in-flight effects cannot authorize another job.
            try:
                receipt = await self.executor.run(job)
            except BaseException:
                self.halted = True
                raise
            group = self.cgroup_root / ident
            events = dict(line.split() for line in (group / 'cgroup.events').read_text().splitlines())
            need(events.get('populated') == '0' and not (group / 'cgroup.procs').read_text().strip(), 'EXECUTION_GROUP_NOT_EMPTY')
            wall = receipt.get('wall_time_s')
            need(type(wall) in (float, int) and math.isfinite(wall) and wall >= 0, 'PROTECTED_RECEIPT_CLOCK_REQUIRED')
            stdout = self.captures.read(receipt['stdout_ref'])
            successful = (receipt['termination_reason'] == 'completed' and receipt['exit_code'] == 0
                and receipt['observed_runtime'] is True and not receipt['observed_limits']['admin_output_truncated'])
            checked = None
            if successful:
                try:
                    checked = check_capsule_output(self.grant['capsule_name'], inputs={'packet': fixture['packet']},
                        output=stdout, expected_checks_sha256=assets['checks_sha256'])
                except (ValueError, TypeError, KeyError, UnicodeError):
                    successful = False
                else:
                    successful = checked['task_success']
            evidence = {'schema': 'ai4r-rsi-whole-capsule-visible-check:1', 'start_ref': start_ref,
                'receipt': receipt, 'independent_check': checked, 'fixture_id': fixture['id'],
                'task_success': successful, 'group_empty': True, 'output_bytes': len(stdout),
                'protected_wall_s': wall, 'batch_iterations': self.grant['iterations'],
                'bootstrap_schema': BOOTSTRAP_SCHEMA,
                'candidate_ref': candidate_ref, 'input_ref': input_ref, 'program_ref': program_ref,
                'runtime_manifest_sha256': assets['runtime_manifest_sha256'], 'checks_sha256': assets['checks_sha256']}
            evidence_ref = self.captures.put(evidence)
            rows.append({**evidence, 'evidence_ref': evidence_ref})
            if not successful:
                break
            self.halted = False
        result = {'schema': 'ai4r-rsi-whole-capsule-visible-result:1', 'capsule_name': self.grant['capsule_name'],
            'grant_ref': self.grant_ref, 'binding_ref': binding_ref, 'runtime_manifest_ref': self.runtime_manifest_ref,
            'role': role, 'executions': len(rows), 'passed_count': sum(row['task_success'] for row in rows),
            'passed': all(row['task_success'] for row in rows), 'protected_wall_s': sum(row['protected_wall_s'] for row in rows),
            'rows': rows, 'model_calls': 0, 'security': 'UNQUALIFIED', 'hidden_evaluation': 'NOT_RUN',
            'admission_ref': None, 'activation_ref': None, 'scope': 'public_m1_development_only'}
        result_ref = self.captures.put(result)
        self.completed[role] = result_ref
        return {**result, 'result_ref': result_ref}
