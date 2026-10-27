"""Local, unprotected whole-capsule dispatcher for any Linux box.

``LocalDispatcher`` has the constructor and ``evaluate`` interface of
``WholeCapsuleDispatcher`` but runs the captured runtime worker program in a
plain subprocess: no bwrap, no UID switch, no seccomp policy, no cgroup. It is
selected only by explicit configuration (``make_dispatcher('local', ...)``),
never autodetected, and every result, row, start record and receipt carries
``scope: "local_unprotected"`` so publication (which requires the protected
``public_m1_development_only`` scope) can never present it as protected.

What is still enforced: the exact grant, frozen runtime inventory and derived
source closure, the pinned bootstrap with its trusted input-mutation guard,
Python ABI identity, a combined stdout/stderr output bound, wall/CPU/memory/
file-size limits, process-session cleanup, no-replay claims, the execution
budget and the independent output checker outside the candidate interpreter.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import signal
import sys
import time

from .capsule_executor import (LOCAL_SCOPE, BoundedCapture, _EvaluationLedger, digest, need)
from .capsule_runtime import (MAX_OUTPUT_BYTES, capsule_job_assets, require_runtime_closure, verify_runtime)
from .capsules import registered_capsule
from ..records import encoded

RECEIPT_SCHEMA = 'ai4r-rsi-local-capsule-receipt:1'


def _limits(memory_mb, timeout_s):
    def apply():
        import resource
        memory = memory_mb * 1024 * 1024
        for name, value in (('RLIMIT_AS', memory), ('RLIMIT_CPU', timeout_s + 1),
                            ('RLIMIT_CORE', 0), ('RLIMIT_FSIZE', 64 * 1024 * 1024)):
            limit = getattr(resource, name, None)
            if limit is not None:
                resource.setrlimit(limit, (value, value))
    return apply


class LocalDispatcher(_EvaluationLedger):
    """Grant-bounded parent/candidate evaluation in plain subprocesses."""
    scope = LOCAL_SCOPE
    result_schema_v1 = False  # Always Interface A v2, iteration-keyed.

    def __init__(self, *, root, runtime_root, manifest, grant_path, grant_sha256, cgroup_root=None, captures,
                 python=None, benchmark=None):
        from jiuwenswarm.research_rsi.records import RecordStore
        need(sys.platform.startswith('linux') or os.name == 'posix', 'POSIX_LOCAL_DISPATCHER_REQUIRED')
        self._load_grant(grant_path, grant_sha256, manifest)
        self.runtime_root = Path(runtime_root).resolve(strict=True)
        self.manifest = verify_runtime(self.runtime_root, manifest)
        self.runtime_closure = require_runtime_closure(self.runtime_root, self.manifest)
        need(type(captures) is RecordStore, 'CAPTURE_RECORD_STORE_REQUIRED')
        self.root = Path(root).resolve(strict=True)
        need(self.root.is_dir(), 'LOCAL_EVALUATION_ROOT_REQUIRED')
        self.captures = captures
        self.python = str(Path(python or sys.executable).resolve(strict=True))
        self.abi = {'dispatcher': 'local', 'isolation': 'none', 'scope': LOCAL_SCOPE,
                    'python': self.python, 'adapter_sha256': digest(Path(__file__).read_bytes()),
                    'combined_stdout_stderr_limit_bytes': MAX_OUTPUT_BYTES}
        self.grant_ref = captures.put(self.grant)
        self.runtime_manifest_ref = captures.put(self.manifest)
        self.parent = (self.runtime_root / 'source/jiuwenswarm'
                       / registered_capsule(self.grant['capsule_name']).carrier_path).read_bytes()
        need(digest(self.parent) == self.grant['parent_sha256'], 'FROZEN_PARENT_BYTES_DIFFER')
        self.parent_ref = captures.put_bytes(self.parent)
        for name in ('claims', 'local-jobs'):
            (self.root / name).mkdir(mode=0o700, exist_ok=True)
        self._set_benchmark(benchmark)

    async def _run_case(self, *, role, fixture, body, candidate_ref, binding_ref, ident, index):
        job = await self._run_job(role=role, fixture=fixture, candidate_ref=candidate_ref, binding_ref=binding_ref,
            ident=ident, index=index, make_assets=lambda profile: capsule_job_assets(self.grant['capsule_name'],
                runtime_root=self.runtime_root, manifest=self.manifest, candidate=body,
                inputs={'packet': fixture['packet']}, iterations=self.grant['iterations'], **profile))
        return self._finish_case(role=role, fixture=fixture, assets=job['assets'], receipt=job['receipt'],
            stdout=job['stdout'], start_ref=job['start_ref'], candidate_ref=candidate_ref,
            input_ref=job['input_ref'], program_ref=job['program_ref'])

    async def _run_job(self, *, role, fixture, candidate_ref, binding_ref, ident, index, make_assets,
                       node_id=None, start_extra=None):
        """One local subprocess job; ``make_assets(profile_kwargs)`` builds its program."""
        need(self.executions < self.grant['max_executions'], 'ROOT_EXECUTION_BUDGET_EXHAUSTED')
        job_root = self.root / 'local-jobs' / ident
        job_root.mkdir(mode=0o700)
        resources, work = job_root / 'resources', job_root / 'work'
        resources.mkdir(mode=0o700); work.mkdir(mode=0o700)
        assets = make_assets({'execution_profile': 'local_unprotected', 'resource_root': resources})
        for name, raw in assets['files'].items():
            path = resources / name; path.write_bytes(raw); path.chmod(0o444)
        store = self._store_for(fixture)
        input_ref = store.put_bytes(assets['files']['input.json'])
        program_ref = self.captures.put_bytes(assets['files']['worker.py'])
        test_ref = store.put(fixture)
        start_ref = self._start_record(ident=ident, role=role, fixture=fixture, binding_ref=binding_ref,
            candidate_ref=candidate_ref, assets=assets, input_ref=input_ref, program_ref=program_ref, test_ref=test_ref,
            extra=start_extra)
        self.executions += 1
        receipt, stdout = await self._spawn(ident, assets['argv'], work, candidate_ref, store)
        return {'assets': assets, 'receipt': receipt, 'stdout': stdout, 'start_ref': start_ref,
                'input_ref': input_ref, 'program_ref': program_ref}

    async def _spawn(self, ident, argv, work, candidate_ref, store):
        limits = self.grant['limits']
        started = time.perf_counter()
        process = await asyncio.create_subprocess_exec(self.python, *argv, cwd=str(work),
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'},
            preexec_fn=_limits(limits['memory_mb'], limits['timeout_s']), start_new_session=True, close_fds=True)
        def kill():
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        fence = BoundedCapture(kill, MAX_OUTPUT_BYTES)
        async def drain(pipe):
            parts = []
            while chunk := await pipe.read(65536):
                parts.append(chunk)
            return b''.join(parts)
        readers = [asyncio.ensure_future(drain(fence.pipe(process.stdout))),
                   asyncio.ensure_future(drain(fence.pipe(process.stderr)))]
        termination = 'completed'
        try:
            await asyncio.wait_for(process.wait(), timeout=limits['timeout_s'])
        except asyncio.TimeoutError:
            termination = 'timeout'
            kill()
            await process.wait()
        wall = time.perf_counter() - started
        done, pending = await asyncio.wait(readers, timeout=5)
        if pending:  # A session member still holds a pipe: kill and stop reading.
            kill()
            done, pending = await asyncio.wait(readers, timeout=5)
            for task in pending:
                task.cancel()
        stdout, stderr = (task.result() if task in done and not task.cancelled() else b'' for task in readers)
        # Session cleanup: nothing the candidate started may outlive its job.
        lingering = True
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            lingering = False
        if lingering:
            kill()
        if fence.overflow:
            termination = 'output_limit_exceeded'
        elif termination == 'completed' and process.returncode < 0:
            termination = 'signal_' + signal.Signals(-process.returncode).name.lower()
        receipt = {'schema': RECEIPT_SCHEMA, 'job_id': ident, 'termination_reason': termination,
            'exit_code': process.returncode, 'wall_time_s': wall,
            'stdout_ref': store.put_bytes(stdout), 'stderr_ref': store.put_bytes(stderr),
            'observed_runtime': True, 'subject_ref': candidate_ref, 'isolation': 'none', 'scope': LOCAL_SCOPE,
            'session_lingering_killed': lingering,
            'observed_limits': {'admin_output_limit_bytes': fence.limit, 'admin_output_captured_bytes': fence.used,
                'admin_output_truncated': fence.overflow, 'timeout_s': limits['timeout_s'],
                'memory_mb': limits['memory_mb'], 'pids_max_enforced': False,
                'admin_output_adapter_sha256': digest(Path(__file__).read_bytes())}}
        return receipt, stdout


def dispatcher_for(evaluator, **options):
    """Select by the configured ``evaluator['dispatcher']`` ("local" | "v18-bwrap").

    A configuration without the key keeps the historical protected path; the
    choice is never inferred from the host (bwrap/UID availability).
    """
    from .capsule_executor import make_dispatcher
    kind = evaluator.get('dispatcher', 'v18-bwrap')
    if evaluator.get('benchmark') is not None:
        # The evaluator configuration's benchmark block (Interface E settings).
        options.setdefault('benchmark', evaluator['benchmark'])
    return make_dispatcher(kind, **options)
