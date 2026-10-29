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
from .capsules import public_fixtures, registered_capsule, fixture_inputs
from .cgroup_lifecycle import check_capacity, retire_owned_group
from .capsule_runtime import (BOOTSTRAP_SCHEMA, MAX_OUTPUT_BYTES, capsule_job_assets,
    check_capsule_output, require_runtime_closure, verify_runtime)
from ..capsule_doctor import (WORKER_GID, WORKER_UID, _searchable, require_worker_traversal,
    static_traversal, traversal_components, worker_traversal)

V18_EXECUTOR_SHA256 = '25c77a8c6830e32e83a6b77334d82e12350912fe33b312df8d5b1aad26bc4715'

V18_KERNEL_DIRECTORY = Path('/opt/ai4r-rsi-frozen-v18-03ed3199/jiuwenswarm/research')
V18_KERNEL_FILES = {'executor.py': V18_EXECUTOR_SHA256,
    '_executor_probe.py': '96067b0fe8c65abbd3eef1a9e90bc42e6ef7b01d199f42aaf6b718566bd560da'}


def v18_kernel_sources():
    """The exact read-only closure needed by the protected capsule run path."""
    paths = []
    for filename, expected in V18_KERNEL_FILES.items():
        path = _root_custody(V18_KERNEL_DIRECTORY / filename)
        need(digest(path.read_bytes()) == expected, 'EXACT_HISTORICAL_V18_KERNEL_CLOSURE_REQUIRED')
        paths.append(path)
    return tuple(paths)


def load_v18_executor():
    """Load the immutable kernel privately; never replace the product executor."""
    import importlib.util
    import sys
    paths = v18_kernel_sources()
    name = '_ai4r_capsule_v18_executor_25c77a8c'
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, paths[0])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    need(Path(module.__file__) == paths[0], 'FROZEN_V18_MODULE_IDENTITY_DIFFERS')
    executor_abi(module.RestrictedExecutor, module.ExecutionJob, module.ReadonlyMount)
    return module


GRANT_SCHEMA = 'ai4r-rsi-whole-capsule-development-grant:2'
LOOP_GRANT_SCHEMA = 'ai4r-rsi-whole-capsule-development-grant:3'
MAX_LOOP_EXECUTIONS = 100000
MAX_BENCHMARK_WALL_S = 14 * 24 * 3600
VISIBLE_RESULT_V1 = 'ai4r-rsi-whole-capsule-visible-result:1'
VISIBLE_RESULT_V2 = 'ai4r-rsi-whole-capsule-visible-result:2'
PROTECTED_SCOPE = 'public_m1_development_only'
LOCAL_SCOPE = 'local_unprotected'
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


def evaluation_fixtures(name):
    """The ordered case list a loop grant pins; parent and candidate share it.

    The objective owner supplies it (``capsules.evaluation_fixtures`` or
    ``capsule_objective.evaluation_fixtures``: public, public_extended and
    held_out cases with their ``fixture_set``/``fixture_group`` labels, which
    are carried through unchanged). Without an objective owner the public
    cases alone are evaluated. Fixture data is read by Root/evaluator code
    only; it is never part of the sandbox runtime package.
    """
    from . import capsules
    source = getattr(capsules, 'evaluation_fixtures', None)
    if source is None:
        try:
            from . import capsule_objective
        except ImportError:
            capsule_objective = None
        source = getattr(capsule_objective, 'evaluation_fixtures', None)
    if source is None:
        return [dict(row, fixture_set='public', fixture_group='public') for row in public_fixtures(name)]
    rows = [dict(row) for row in source(name)]
    need(rows and all(isinstance(row, dict) and {'id', 'packet', 'expected_task_output', 'fixture_set'} <= set(row)
                      and row['fixture_set'] in ('public', 'held_out') for row in rows)
         and len({row['id'] for row in rows}) == len(rows), 'EXACT_LABELED_EVALUATION_FIXTURES_REQUIRED')
    for row in rows:
        row.setdefault('fixture_group', row['fixture_set'])
    return rows


def loop_execution_budget(case_count, *, max_iterations, trials, parent_trials=None, benchmark_jobs=0,
                          max_benchmarks=None, benchmark=None, capsule_name=None):
    """Executions a loop needs: parent trials (>= 3 for noise calibration)
    plus ``trials`` candidate trials for each of ``max_iterations`` iterations,
    plus ``benchmark_jobs`` (one ``benchmark()`` call: paired parent+candidate
    jobs x workloads x repetitions, and semantic-edge jobs) for each
    benchmarked candidate: at most one per iteration, or ``max_benchmarks``.

    ``benchmark`` is the slot's sizing dict ``{workloads, repetitions,
    warmups, per_job_s, wall_s}``: then ``benchmark_jobs`` is derived from it
    (``benchmark_jobs_for_sizing``) and ``max_benchmarks`` defaults to
    ``max_iterations + 1`` (an A/A baseline plus one per iteration)."""
    if benchmark is not None:
        need(benchmark_jobs == 0, 'ONE_BENCHMARK_SIZING_REQUIRED')
        benchmark_jobs = benchmark_jobs_for_sizing(benchmark, capsule_name=capsule_name)
        if max_benchmarks is None:
            max_benchmarks = max_iterations + 1
    need(all(type(x) is int and x > 0 for x in (case_count, max_iterations, trials)), 'FINITE_LOOP_BUDGET_INPUTS_REQUIRED')
    need(type(benchmark_jobs) is int and benchmark_jobs >= 0 and (max_benchmarks is None or (
        type(max_benchmarks) is int and 0 <= max_benchmarks <= max_iterations + 1)), 'FINITE_BENCHMARK_BUDGET_INPUTS_REQUIRED')
    parent = max(3, trials) if parent_trials is None else parent_trials
    benchmarks = max_iterations if max_benchmarks is None else max_benchmarks
    return case_count * (parent + trials * max_iterations) + benchmark_jobs * benchmarks


def benchmark_jobs_for_sizing(sizing, *, capsule_name=None):
    """Jobs one ``benchmark()`` call uses under a slot sizing dict.

    With ``capsule_name`` the count is exact for that capsule's data. Without
    it, the largest exact count of any registered benchmarked capsule with
    ``sizing['workloads']`` timed workloads (an upper bound; never a guess
    below what Root will need).
    """
    from .capsule_benchmark import benchmark_job_count, timing_batches
    from .capsules import benchmark_spec, capsule_catalog
    need(isinstance(sizing, dict) and {'workloads', 'repetitions'} <= set(sizing)
         and set(sizing) <= {'workloads', 'repetitions', 'warmups', 'per_job_s', 'wall_s'}, 'CLOSED_BENCHMARK_SIZING_REQUIRED')
    overrides = {'repetitions': sizing['repetitions']}
    if 'warmups' in sizing:
        overrides['warmups'] = min(sizing['warmups'], 10)
    names = [capsule_name] if capsule_name is not None else [
        row['capsule_name'] for row in capsule_catalog() if benchmark_spec(row['capsule_name']) is not None]
    counts = [benchmark_job_count(name, overrides) for name in names
              if len(timing_batches(name)) == sizing['workloads']]
    need(counts, 'NO_BENCHMARK_MATCHES_SIZING_WORKLOADS')
    return max(counts)


def loop_budget_for(name, loop, *, case_count=None):
    """``loop_execution_budget`` from a session ``loop`` configuration.

    ``loop['benchmark']`` (absent/None/False: no benchmark) is the benchmark
    configuration (``capsule_benchmark.benchmark_config`` overrides, including
    ``max_benchmarks``); ``True`` means the capsule's spec defaults.
    """
    from .capsule_benchmark import benchmark_config, benchmark_job_count
    need(isinstance(loop, dict), 'LOOP_CONFIGURATION_REQUIRED')
    settings = loop.get('benchmark')
    jobs, cap = 0, None
    if isinstance(settings, dict) and 'workloads' in settings:  # Slot sizing dict.
        cases = len(evaluation_fixtures(name)) if case_count is None else case_count
        return loop_execution_budget(cases, max_iterations=loop['max_iterations'], trials=loop.get('trials', 1),
                                     parent_trials=loop.get('parent_trials'), benchmark=settings, capsule_name=name)
    if settings:
        config = benchmark_config(name, None if settings is True else settings)
        jobs, cap = benchmark_job_count(name, config), config['max_benchmarks']
    cases = len(evaluation_fixtures(name)) if case_count is None else case_count
    return loop_execution_budget(cases, max_iterations=loop['max_iterations'], trials=loop.get('trials', 1),
                                 parent_trials=loop.get('parent_trials'), benchmark_jobs=jobs, max_benchmarks=cap)


def evaluator_benchmark_settings(session, configured=None):
    """Root benchmark configuration for one run, from the session's sizing.

    The session's ``loop.benchmark`` sizing (materialized by the slot, pinned
    by the grant's ``limits.benchmark_wall_s`` and ``max_executions``) decides
    whether Interface E is served and its ``repetitions``/``warmups``; the
    evaluator configuration's optional ``benchmark`` block may add the other
    ``benchmark_config`` overrides (batch sizes, gates, bootstrap) but never
    contradict the sizing. Returns None when no benchmark is served. The
    returned settings run exactly ``benchmark_jobs_for_sizing(sizing)`` jobs
    per call, so Root never executes more than the grant was sized for.
    """
    from .capsule_benchmark import benchmark_config, benchmark_job_count
    loop = session.get('loop') if isinstance(session, dict) else None
    sizing = loop.get('benchmark') if isinstance(loop, dict) else None
    if sizing is None:
        need(configured is None, 'EVALUATOR_BENCHMARK_WITHOUT_SESSION_SIZING')
        return None
    grant, name = session['grant'], session['capsule_name']
    need(grant['schema'] == LOOP_GRANT_SCHEMA and grant['limits'].get('benchmark_wall_s') == sizing.get('wall_s'),
         'GRANT_BENCHMARK_WALL_DIFFERS_FROM_SESSION_SIZING')
    configured = dict(configured or {})
    need(not {'max_benchmarks'} & set(configured), 'BENCHMARK_COUNT_IS_SIZED_BY_THE_SLOT')
    settings = dict(configured, repetitions=sizing['repetitions'], warmups=min(sizing['warmups'], 10))
    need(all(configured.get(key, settings[key]) == settings[key] for key in ('repetitions', 'warmups')),
         'EVALUATOR_BENCHMARK_CONTRADICTS_SESSION_SIZING')
    config = benchmark_config(name, settings)
    need(benchmark_job_count(name, config) == benchmark_jobs_for_sizing(sizing, capsule_name=name),
         'BENCHMARK_JOBS_DIFFER_FROM_SIZING')
    return settings


def grant_fixtures(grant):
    """The exact case inventory a grant pins (v2: public only, v3: evaluation)."""
    if grant['schema'] == LOOP_GRANT_SCHEMA:
        return evaluation_fixtures(grant['capsule_name'])
    return [dict(row, fixture_set='public') for row in public_fixtures(grant['capsule_name'])]


def _fixture_digest(grant, fixtures):
    if grant['schema'] == LOOP_GRANT_SCHEMA:
        return digest(encoded(fixtures))
    # v2 grants pin the historical public inventory bytes exactly.
    return digest(encoded([{k: v for k, v in row.items() if k != 'fixture_set'} for row in fixtures]))


def validate_grant(grant, manifest):
    fields = {'schema', 'bootstrap_schema', 'run_id', 'capsule_name', 'runtime_manifest_sha256', 'parent_sha256',
        'fixture_sha256', 'fixture_count', 'roles', 'max_executions', 'iterations', 'limits',
        'worker', 'expires_unix_s', 'scope', 'production_admission'}
    need(isinstance(grant, dict) and set(grant) == fields and grant['schema'] in (GRANT_SCHEMA, LOOP_GRANT_SCHEMA),
         'CLOSED_ROOT_DEVELOPMENT_GRANT_REQUIRED')
    need(grant['bootstrap_schema'] == BOOTSTRAP_SCHEMA, 'EXACT_VERSIONED_CAPSULE_BOOTSTRAP_REQUIRED')
    target = registered_capsule(grant['capsule_name'])
    need(target.public_evaluation_available and grant['scope'] == 'public_m1_development_only'
         and grant['production_admission'] == 'UNKNOWN', 'FINITE_PUBLIC_DEVELOPMENT_SCOPE_REQUIRED')
    need(isinstance(grant['run_id'], str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', grant['run_id']),
         'BOUNDED_DEVELOPMENT_RUN_ID_REQUIRED')
    fixtures = grant_fixtures(grant)
    need(grant['fixture_sha256'] == _fixture_digest(grant, fixtures) and type(grant['fixture_count']) is int
         and grant['fixture_count'] == len(fixtures), 'EXACT_PUBLIC_FIXTURE_INVENTORY_REQUIRED')
    if grant['schema'] == LOOP_GRANT_SCHEMA:
        # Iterative loop grant: any number of parent/candidate evaluations,
        # bounded only by a finite execution budget of at least one pair.
        need(grant['roles'] == ['parent', 'candidate'] and type(grant['max_executions']) is int
             and len(fixtures) * 2 <= grant['max_executions'] <= MAX_LOOP_EXECUTIONS,
             'FINITE_LOOP_EXECUTION_BUDGET_REQUIRED')
    else:
        need(grant['roles'] in (['parent'], ['parent', 'candidate'])
             and type(grant['max_executions']) is int
             and grant['max_executions'] == len(fixtures) * len(grant['roles']), 'EXACT_ROLE_EXECUTION_BUDGET_REQUIRED')
    need(type(grant['iterations']) is int and 1 <= grant['iterations'] <= 10000, 'FROZEN_BOUNDED_ITERATIONS_REQUIRED')
    need(grant['runtime_manifest_sha256'] == digest(encoded(manifest)), 'EXACT_REVIEWED_RUNTIME_REQUIRED')
    carrier = 'source/jiuwenswarm/' + target.carrier_path
    need(grant['parent_sha256'] == next((row['sha256'] for row in manifest['files'] if row['path'] == carrier), None),
         'EXACT_ORIGINAL_CAPSULE_PARENT_REQUIRED')
    limits = grant['limits']
    base = {'timeout_s', 'memory_mb', 'pids_max', 'wall_s'}
    # Loop grants may add ``benchmark_wall_s``: the paired benchmark's own wall,
    # bounded separately from the session's ``wall_s``.
    need(isinstance(limits, dict) and (set(limits) == base or (
        grant['schema'] == LOOP_GRANT_SCHEMA and set(limits) == base | {'benchmark_wall_s'})), 'CLOSED_JOB_LIMITS_REQUIRED')
    for name, ceiling in {'timeout_s': 300, 'memory_mb': 65536, 'pids_max': 256, 'wall_s': 3600,
                          'benchmark_wall_s': MAX_BENCHMARK_WALL_S}.items():
        need(name not in limits or type(limits[name]) is int and 0 < limits[name] <= ceiling, 'FINITE_JOB_LIMIT_REQUIRED')
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

    PROBE_FRAME_LIMIT = 4096

    def pipe(self, reader, *, probe=False):
        """Bounded frame reader over one child pipe.

        Reads are chunked (never ``StreamReader.readline``, whose 64 KiB
        limit raises on a long first line). ``readline`` returns the first
        newline-terminated frame, retaining any coalesced subsequent bytes for
        later reads; a frame that grows past the probe bound without a newline,
        or a partial frame at EOF, is returned as ordinary output bytes. Only
        a complete, bounded probe frame bypasses the output fence; every other
        byte is counted exactly once against the shared limit.
        """
        fence = self
        maximum = self.PROBE_FRAME_LIMIT + len(self.PREFIX) + 1
        class Pipe:
            def __init__(self):
                self.pending = bytearray(); self.eof = False
            async def _fill(self):
                if self.eof:
                    return False
                chunk = await reader.read(65536)
                if not chunk:
                    self.eof = True
                    return False
                self.pending.extend(chunk)
                return True
            async def readline(self):
                while True:
                    boundary = self.pending.find(b'\n')
                    if 0 <= boundary < maximum:
                        frame = bytes(self.pending[:boundary + 1]); del self.pending[:boundary + 1]
                        break
                    if boundary >= maximum or len(self.pending) >= maximum or not await self._fill():
                        # Not a bounded frame (or EOF): plain output bytes.
                        frame = bytes(self.pending); self.pending.clear()
                        return await fence.take(reader, frame) if frame else b''
                if probe and frame.startswith(fence.PREFIX):
                    return frame
                return await fence.take(reader, frame)
            async def read(self, size=65536):
                need(type(size) is int and 0 < size <= 65536, 'FINITE_CAPTURE_READ_REQUIRED')
                if self.pending:
                    chunk = bytes(self.pending[:size]); del self.pending[:size]
                    return await fence.take(reader, chunk)
                if self.eof:
                    return b''
                return await fence.take(reader, await reader.read(size))
        return Pipe()


def bounded_executor(base, *, output_limit=MAX_OUTPUT_BYTES):
    """Reuse canonical kernel code with private globals and bounded pipe readers.

    The operational dispatcher verifies the exact base ABI first. This helper
    does not mutate the installed module, asyncio or completed helper evidence.
    """
    need(type(output_limit) is int and 0 < output_limit <= MAX_OUTPUT_BYTES, 'ROOT_OUTPUT_BOUND_REQUIRED')
    class Executor(base):
        def _cgroup(self, job):
            # Check every finite ancestor immediately before allocating. The
            # frozen kernel still owns creation, limits and confinement.
            check_capacity(self.cgroup_root)
            return super()._cgroup(job)

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


def ensure_worker_traversal(evidence_root, target, *, uid=WORKER_UID, gid=WORKER_GID, owner=0):
    """Make every Root-owned directory from the evidence root to ``target``'s
    parent searchable (at least 0711) for the worker; verify the rest.

    Only directories inside the evidence root and owned by ``owner`` are ever
    changed; group/other read and write bits are never added. Ancestors above
    the evidence root and foreign-owned directories are verified only, and the
    first blocking one is reported. Derived from configured paths, for any
    layout (no special-cased directory names).
    """
    evidence_root, target = Path(evidence_root), Path(target)
    need(target == evidence_root or target.is_relative_to(evidence_root), 'TRAVERSAL_TARGET_OUTSIDE_EVIDENCE_ROOT')
    gids = {gid}
    changed = []
    leaf = target.lstat()
    need(not stat.S_ISLNK(leaf.st_mode), 'REAL_TRAVERSAL_TARGET_REQUIRED')
    components = traversal_components(target)
    if not stat.S_ISDIR(leaf.st_mode):
        components = components[:-1]
        # A job asset file must be readable by the worker (0444 assets).
        readable = (0o400 if leaf.st_uid == uid else 0o040 if leaf.st_gid in gids else 0o004)
        need(stat.S_ISREG(leaf.st_mode) and leaf.st_mode & readable, 'WORKER_READABLE_JOB_FILE_REQUIRED: ' + str(target))
    for component in components:
        meta = component.lstat()
        need(stat.S_ISDIR(meta.st_mode) and not stat.S_ISLNK(meta.st_mode), 'REAL_TRAVERSAL_DIRECTORY_REQUIRED')
        if _searchable(meta, uid, gids):
            continue
        need(component == evidence_root or component.is_relative_to(evidence_root),
             'WORKER_TRAVERSAL_BLOCKED_ABOVE_EVIDENCE_ROOT: ' + str(component))
        need(meta.st_uid == owner, 'WORKER_TRAVERSAL_BLOCKED_BY_FOREIGN_OWNER: ' + str(component))
        component.chmod(stat.S_IMODE(meta.st_mode) | 0o111)
        changed.append(str(component))
    blocking = static_traversal([target], uid=uid, gid=gid)
    need(blocking is None, 'WORKER_TRAVERSAL_BLOCKED: ' + json.dumps(blocking, sort_keys=True))
    return changed


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


_FAILURE_LINE = re.compile(rb'^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Exit|Interrupt|Warning)):?\s?(.*)$')


def failure_summary(stderr, receipt):
    """Closed failure facts for a captured failed job (never re-raised)."""
    exception_type, message = None, ''
    for line in reversed(stderr.strip().splitlines()[-64:]):
        match = _FAILURE_LINE.match(line.strip())
        if match:
            exception_type = match.group(1).decode('ascii', 'replace').rpartition('.')[2]
            message = match.group(2).decode('utf8', 'replace')
            break
    if exception_type is None:
        exception_type = {'output_limit_exceeded': 'OutputLimitExceeded', 'timeout': 'TimeoutError',
                          'resource_limit_exceeded': 'ResourceLimitExceeded'}.get(
            receipt.get('termination_reason'), 'CapsuleJobFailed')
        message = 'termination_reason=%s exit_code=%s' % (receipt.get('termination_reason'), receipt.get('exit_code'))
    return {'exception_type': exception_type[:128], 'message': message[:4096]}


TASK_OUTPUT_CAP_BYTES = 16 * 1024


def task_output_key(name, packet, output):
    """The packet data key the capsule writes, from its registration when
    declared, else derived as the single data key the output adds/changes."""
    declared = getattr(registered_capsule(name), 'task_output_key', None)
    if declared:
        return declared
    before, after = packet.get('data', {}), output.get('data', {})
    changed = [key for key in after if key not in before or after[key] != before[key]]
    return changed[0] if len(changed) == 1 else None


def bounded_task_output(name, packet, stdout, *, cap=TASK_OUTPUT_CAP_BYTES):
    """``{'value', 'truncated', 'bytes'}``: parsed task output when its
    canonical JSON fits ``cap``, else the first ``cap`` bytes of that JSON text;
    ``value`` is None when the job produced no parseable packet."""
    try:
        output = json.loads(stdout)
        key = task_output_key(name, packet, output)
        value = output['data'][key] if key is not None else None
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        return {'value': None, 'truncated': False, 'bytes': 0}
    raw = encoded(value)
    if len(raw) <= cap:
        return {'value': value, 'truncated': False, 'bytes': len(raw)}
    return {'value': raw[:cap].decode('utf8', 'ignore'), 'truncated': True, 'bytes': len(raw)}


def sealed_check(checked):
    """Held-out check facts reduced to pass/fail per check id (no details)."""
    if checked is None:
        return None
    return {**{key: checked[key] for key in ('capsule_name', 'task_success', 'checks_sha256', 'output_bytes', 'scope')
               if key in checked},
            'checks': [{'check_id': row.get('check_id'), 'outcome': row.get('outcome')} for row in checked.get('checks', [])]}


def visible_row_v2(row, *, fixture_set, fixture_group=None):
    """Interface A row: the v1 evidence row plus the v2 summary fields."""
    checked = row.get('independent_check') or {}
    return {**row, 'fixture_set': fixture_set, 'fixture_group': fixture_group or fixture_set,
            'checks': checked.get('checks', [])}


def visible_result_v2(result):
    """Read a v1 or v2 visible result as Interface A v2 (v1 is never rewritten)."""
    need(isinstance(result, dict) and result.get('schema') in (VISIBLE_RESULT_V1, VISIBLE_RESULT_V2),
         'KNOWN_VISIBLE_RESULT_SCHEMA_REQUIRED')
    if result['schema'] == VISIBLE_RESULT_V2:
        return result
    rows = [visible_row_v2(row, fixture_set='public') for row in result['rows']]
    subject = rows[0]['candidate_ref']['sha256'] if rows else None
    failed = next((row for row in rows if not row['task_success']), None)
    return {**result, 'schema': VISIBLE_RESULT_V2, 'iteration': 0, 'subject_sha256': subject,
            'case_count': len(public_fixtures(result['capsule_name'])), 'held_out_case_count': 0,
            'trial_wall_s': [result['protected_wall_s']], 'rows': rows, 'trial_rows': [],
            'failure': None if failed is None else {'exception_type': 'CapsuleJobFailed',
                'message': 'fixture %s failed (historical v1 result)' % failed['fixture_id']},
            'upgraded_from': VISIBLE_RESULT_V1}


class _EvaluationLedger:
    """Grant-bounded parent/candidate evaluation bookkeeping shared by dispatchers.

    Grant v2 keeps its historical single parent+candidate semantics and v1
    result bytes. Grant v3 (``LOOP_GRANT_SCHEMA``) and the local dispatcher
    serve any number of iteration-keyed evaluations bounded only by
    ``max_executions`` and return Interface A v2 results.
    """
    scope = PROTECTED_SCOPE
    result_schema_v1 = True
    task_output_cap = TASK_OUTPUT_CAP_BYTES

    def _load_grant(self, grant_path, grant_sha256, manifest):
        grant_raw = Path(grant_path).read_bytes()
        need(len(grant_raw) <= 65536 and digest(grant_raw) == grant_sha256, 'ROOT_REVIEWED_GRANT_BYTES_REQUIRED')
        self.grant = validate_grant(json.loads(grant_raw), manifest)
        need(grant_raw == encoded(self.grant), 'CANONICAL_ROOT_GRANT_REQUIRED')
        need(time.time() < self.grant['expires_unix_s'], 'ROOT_DEVELOPMENT_GRANT_EXPIRED')
        self.loop = self.grant['schema'] == LOOP_GRANT_SCHEMA or not self.result_schema_v1
        self.fixtures = grant_fixtures(self.grant) if self.loop else public_fixtures(self.grant['capsule_name'])
        self.issued = {}; self.completed = {}; self.evaluations = []; self.executions = 0; self.halted = False
        self.benchmarkable = {}; self.benchmarks = []
        # Session wall plus the grant's separately bounded benchmark wall.
        self.deadline = time.monotonic() + self.grant['limits']['wall_s'] + self.grant['limits'].get('benchmark_wall_s', 0)

    benchmark_settings = None

    def _set_benchmark(self, settings):
        """Benchmark configuration (Interface E); validated before any job.

        ``None`` means this dispatcher serves no benchmark (configuration, never
        inferred); ``{}`` means the capsule's frozen spec defaults.
        """
        self.benchmark_settings = settings
        if settings is not None:
            from .capsule_benchmark import benchmark_config
            need(self.loop, 'BENCHMARK_REQUIRES_ITERATIVE_GRANT')
            benchmark_config(self.grant['capsule_name'], settings)

    @property
    def benchmark_available(self):
        """True only when the evaluator configuration enables Interface E."""
        return self.benchmark_settings is not None

    def benchmark_plan(self):
        """What one ``benchmark()`` call will execute under this grant."""
        from .capsule_benchmark import benchmark_config, benchmark_job_count
        config = benchmark_config(self.grant['capsule_name'], self.benchmark_settings)
        return {'schema': 'ai4r-rsi-capsule-benchmark-plan:1', 'capsule_name': self.grant['capsule_name'],
                'config': config, 'jobs_per_benchmark': benchmark_job_count(self.grant['capsule_name'], config),
                'maximum_executions': self.grant['max_executions'], 'executions': self.executions, 'scope': self.scope}

    async def benchmark(self, parent_body, candidate_body, *, iteration):
        """Interface E: paired batched benchmark of an already evaluated candidate."""
        from .capsule_benchmark_executor import run_benchmark
        need(self.benchmark_available, 'ROOT_BENCHMARK_NOT_CONFIGURED')
        return await run_benchmark(self, parent_body, candidate_body, iteration=iteration)

    async def semantic_edges(self, candidate_body, *, iteration):
        """The supplementary semantic-edge correctness gate on its own."""
        from .capsule_benchmark_executor import run_semantic_edges
        return await run_semantic_edges(self, candidate_body, iteration=iteration)

    def plan(self):
        return {'schema': 'ai4r-rsi-whole-capsule-dispatch-plan:1', 'grant_sha256': digest(encoded(self.grant)),
            'bootstrap_schema': BOOTSTRAP_SCHEMA,
            'capsule_name': self.grant['capsule_name'], 'fixture_count': len(self.fixtures),
            'maximum_executions': self.grant['max_executions'], 'roles': self.grant['roles'],
            'runtime_manifest_sha256': digest(encoded(self.manifest)), 'executor_abi': self.abi,
            'model_calls': 0, 'scope': self.scope, 'operational_qualification': False}

    def _live(self):
        need(time.time() < self.grant['expires_unix_s'] and time.monotonic() < self.deadline, 'DEVELOPMENT_DEADLINE_EXPIRED')

    sealing = False  # True while a held-out job's bytes are being captured.

    def _sealed_store(self):
        """Root-only store for held-out inputs, fixtures and job output.

        Rows and start records keep exact ``{id, sha256}`` pins to these bytes,
        but the public capture store (whose closure is transferred to the
        model-side controller) cannot resolve them, so held-out packets,
        expected outputs and actual outputs never leave the evaluator.
        """
        store = getattr(self, '_sealed', None)
        if store is None:
            from jiuwenswarm.research_rsi.records import RecordStore
            path = self.root / 'sealed-captures'
            path.mkdir(mode=0o700, exist_ok=True)
            store = self._sealed = RecordStore(path)
        return store

    def _store_for(self, fixture):
        return self._sealed_store() if fixture.get('fixture_set') == 'held_out' else self.captures

    def _read(self, ref):
        try:
            return self.captures.read(ref)
        except FileNotFoundError:
            return self._sealed_store().read(ref)

    def _capture(self, raw):
        return (self._sealed_store() if self.sealing else self.captures).put_bytes(raw)

    def close(self):
        store = getattr(self, '_sealed', None)
        if store is not None:
            store.close(); self._sealed = None

    def _authorize_subject(self, role, body, candidate_ref, binding):
        need(isinstance(body, bytes) and 0 < len(body) <= 256 * 1024 and digest(body) == pin(candidate_ref)['sha256'],
             'EXACT_BOUNDED_CANDIDATE_BYTES_REQUIRED')
        if role == 'parent':
            need(body == self.parent and binding is None, 'EXACT_BASELINE_PARENT_REQUIRED')
        else:
            need('parent' in self.completed, 'BASELINE_MUST_COMPLETE_FIRST')
            validate_candidate_binding(binding, self.grant, candidate_ref)

    def _claim(self, name, value):
        with (self.root / 'claims' / name).open('xb') as stream:
            stream.write(encoded(value)); stream.flush(); os.fsync(stream.fileno())

    async def evaluate(self, role, *, body, candidate_ref, binding=None, iteration=None, trials=1):
        if not self.loop:
            # The historical single attempt is parent = iteration 0, the one
            # candidate = iteration 1 (as the legacy loop numbers them).
            need(iteration in (None, 0 if role == 'parent' else 1) and trials == 1,
                 'ITERATIVE_EVALUATION_REQUIRES_LOOP_GRANT')
            return await self._evaluate_v1(role, body=body, candidate_ref=candidate_ref, binding=binding)
        return await self._evaluate_loop(role, body=body, candidate_ref=candidate_ref, binding=binding,
                                         iteration=0 if iteration is None else iteration, trials=trials)

    async def _evaluate_v1(self, role, *, body, candidate_ref, binding):
        need(not self.halted, 'DISPATCHER_HALTED_AFTER_FAILED_OR_UNKNOWN_EXECUTION')
        need(role in self.grant['roles'] and role not in self.completed, 'ROLE_NOT_GRANTED_OR_ALREADY_COMPLETED')
        self._authorize_subject(role, body, candidate_ref, binding)
        self._live()
        self.captures.put_ref(candidate_ref, body)
        binding_ref = self.captures.put(binding) if binding is not None else None
        self._claim(digest(encoded([self.grant['run_id'], role])) + '.json',
            {'grant_ref': self.grant_ref, 'role': role, 'candidate_ref': candidate_ref, 'binding_ref': binding_ref})
        rows = []
        for index, fixture in enumerate(self.fixtures):
            self._live()
            need(self.executions < self.grant['max_executions'], 'ROOT_EXECUTION_BUDGET_EXHAUSTED')
            ident = 'capsule-' + digest(encoded([self.grant['run_id'], role, fixture['id']]))[:48]
            self.halted = True  # Unknown/in-flight effects cannot authorize another job.
            row = await self._run_case(role=role, fixture=fixture, body=body, candidate_ref=candidate_ref,
                binding_ref=binding_ref, ident=ident, index=index)
            rows.append(row)
            if not row['task_success']:
                break
            self.halted = False
        result = {'schema': VISIBLE_RESULT_V1, 'capsule_name': self.grant['capsule_name'],
            'grant_ref': self.grant_ref, 'binding_ref': binding_ref, 'runtime_manifest_ref': self.runtime_manifest_ref,
            'role': role, 'executions': len(rows), 'passed_count': sum(row['task_success'] for row in rows),
            'passed': all(row['task_success'] for row in rows), 'protected_wall_s': sum(row['protected_wall_s'] for row in rows),
            'rows': rows, 'model_calls': 0, 'security': 'UNQUALIFIED', 'hidden_evaluation': 'NOT_RUN',
            'admission_ref': None, 'activation_ref': None, 'scope': self.scope}
        result_ref = self.captures.put(result)
        self.completed[role] = result_ref
        return {**result, 'result_ref': result_ref}

    async def _evaluate_loop(self, role, *, body, candidate_ref, binding, iteration, trials):
        need(not self.halted, 'DISPATCHER_HALTED_AFTER_UNKNOWN_EXECUTION')
        need(role in self.grant['roles'], 'ROLE_NOT_GRANTED')
        need(type(iteration) is int and 0 <= iteration <= 100000 and type(trials) is int and 1 <= trials <= 32,
             'FINITE_ITERATION_AND_TRIALS_REQUIRED')
        self._authorize_subject(role, body, candidate_ref, binding)
        self._live()
        planned = len(self.fixtures) * trials
        need(self.executions + planned <= self.grant['max_executions'], 'ROOT_EXECUTION_BUDGET_EXHAUSTED')
        self.captures.put_ref(candidate_ref, body)
        binding_ref = self.captures.put(binding) if binding is not None else None
        if role == 'candidate':
            # Root-authorized (bound) candidate: benchmark() may time it later.
            self.benchmarkable.setdefault(candidate_ref['sha256'], {
                'candidate_ref': candidate_ref, 'binding_ref': binding_ref, 'iteration': iteration})
        key = [self.grant['run_id'], role, iteration, candidate_ref['sha256']]
        self._claim(digest(encoded(key)) + '.json', {'grant_ref': self.grant_ref, 'role': role, 'iteration': iteration,
            'trials': trials, 'candidate_ref': candidate_ref, 'binding_ref': binding_ref})
        trial_rows = []
        for trial in range(trials):
            if trial and any(row['receipt'].get('termination_reason') == 'timeout' for row in trial_rows[0]):
                # Repeated trials only refine latency, which a candidate that hit
                # the job timeout can never win; it must not cost trials x cases
                # x timeout. The shorter trial list is reported, never invented.
                break
            rows = []
            for index, fixture in enumerate(self.fixtures):
                self._live()
                ident = 'capsule-' + digest(encoded([*key, trial, fixture['id']]))[:48]
                self.halted = True  # Only an observed terminal outcome re-authorizes.
                row = await self._run_case(role=role, fixture=fixture, body=body, candidate_ref=candidate_ref,
                    binding_ref=binding_ref, ident=ident, index=index)
                self.halted = False
                extra = {'role': role, 'iteration': iteration, 'trial': trial, 'check_ref': row.pop('evidence_ref')}
                if fixture['fixture_set'] != 'held_out':
                    # Public cases only: bounded actual task output for diffs.
                    # Held-out rows never carry it.
                    extra['actual_task_output'] = bounded_task_output(self.grant['capsule_name'], fixture['packet'],
                        self._read(row['receipt']['stdout_ref']), cap=self.task_output_cap)
                    receipt = row['receipt']
                    if not (receipt['termination_reason'] == 'completed' and receipt['exit_code'] == 0):
                        # The objective's public failure detail ({exception_type, message}).
                        extra['error'] = failure_summary(
                            self._read(receipt['stderr_ref']) if receipt.get('stderr_ref') else b'', receipt)
                if fixture['fixture_set'] == 'held_out':
                    row['independent_check'] = sealed_check(row['independent_check'])
                visible = visible_row_v2({**row, **extra}, fixture_set=fixture['fixture_set'],
                                         fixture_group=fixture.get('fixture_group'))
                # The Interface A row itself is the persisted evidence record.
                rows.append({**visible, 'evidence_ref': self.captures.put(visible)})
            trial_rows.append(rows)
        rows = trial_rows[0]
        failed = next((row for row in rows if not row['task_success']), None)
        failure = None
        if failed is not None:
            receipt = failed['receipt']
            if failed['fixture_set'] == 'held_out' and receipt['termination_reason'] == 'completed' and receipt['exit_code'] == 0:
                failure = {'exception_type': 'IndependentCheckFailed', 'message': 'held-out case failed'}
            elif receipt['termination_reason'] == 'completed' and receipt['exit_code'] == 0:
                # The candidate ran to completion; the independent checker
                # (outside the candidate interpreter) rejected its packet.
                rejected = [row for row in failed['checks'] if row.get('outcome') != 'PASS']
                failure = {'exception_type': 'IndependentCheckFailed', 'message': json.dumps(
                    [{key: row.get(key) for key in ('check_id', 'outcome', 'detail', 'message') if key in row}
                     for row in rejected] or 'output packet rejected', sort_keys=True, default=str)[:4096]}
            else:
                if failed['fixture_set'] == 'held_out':
                    # Held-out error text may echo the hidden case: type only.
                    failure = {'exception_type': failure_summary(self._read(receipt['stderr_ref']), receipt)['exception_type'],
                               'message': 'held-out case failed'}
                else:
                    stderr = self._read(receipt['stderr_ref']) if receipt.get('stderr_ref') else b''
                    failure = failure_summary(stderr, receipt)
            # Closed Interface A shape {exception_type, message}; the case id
            # (an opaque label for held-out cases) is part of the message.
            failure['message'] = ('[%s] ' % failed['fixture_id'] + failure['message'])[:4096]
        passed = sum(row['task_success'] for row in rows)
        result = {'schema': VISIBLE_RESULT_V2, 'capsule_name': self.grant['capsule_name'],
            'grant_ref': self.grant_ref, 'binding_ref': binding_ref, 'runtime_manifest_ref': self.runtime_manifest_ref,
            'role': role, 'iteration': iteration, 'subject_sha256': candidate_ref['sha256'],
            'executions': sum(len(item) for item in trial_rows), 'passed_count': passed, 'case_count': len(rows),
            'held_out_case_count': sum(row['fixture_set'] == 'held_out' for row in rows),
            'passed': passed == len(rows), 'protected_wall_s': sum(row['protected_wall_s'] for row in rows),
            'trial_wall_s': [sum(row['protected_wall_s'] for row in item) for item in trial_rows],
            'rows': rows, 'trial_rows': trial_rows[1:], 'failure': failure,
            'model_calls': 0, 'security': 'UNQUALIFIED', 'hidden_evaluation': 'NOT_RUN',
            'admission_ref': None, 'activation_ref': None, 'scope': self.scope}
        result_ref = self.captures.put(result)
        self.completed.setdefault(role, result_ref)
        self.evaluations.append(result_ref)
        return {**result, 'result_ref': result_ref}

    def _finish_case(self, *, role, fixture, assets, receipt, stdout, start_ref, candidate_ref, input_ref, program_ref):
        """Independent check of captured output; returns the persisted evidence row."""
        wall = receipt.get('wall_time_s')
        need(type(wall) in (float, int) and math.isfinite(wall) and wall >= 0, 'PROTECTED_RECEIPT_CLOCK_REQUIRED')
        successful = (receipt['termination_reason'] == 'completed' and receipt['exit_code'] == 0
            and receipt['observed_runtime'] is True and not receipt['observed_limits']['admin_output_truncated'])
        checked = None
        if successful:
            try:
                checked = check_capsule_output(self.grant['capsule_name'], inputs=fixture_inputs(self.grant['capsule_name'], fixture),
                    output=stdout, expected_checks_sha256=assets['checks_sha256'],
                    binding=self.manifest.get('target_bindings', {}).get(self.grant['capsule_name']))
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
        evidence_ref = self._store_for(fixture).put(evidence)  # Held-out: sealed.
        return {**evidence, 'evidence_ref': evidence_ref}

    def _start_record(self, *, ident, role, fixture, binding_ref, candidate_ref, assets, input_ref, program_ref, test_ref,
                      extra=None):
        start = {'schema': 'ai4r-rsi-whole-capsule-execution-start:1', 'job_id': ident,
            'grant_ref': self.grant_ref, 'binding_ref': binding_ref, 'runtime_manifest_ref': self.runtime_manifest_ref,
            'grant_sha256': digest(encoded(self.grant)), 'runtime_manifest_sha256': assets['runtime_manifest_sha256'],
            'bootstrap_schema': assets.get('bootstrap_schema', BOOTSTRAP_SCHEMA),
            'candidate_ref': candidate_ref, 'input_ref': input_ref, 'program_ref': program_ref,
            'test_ref': test_ref, 'fixture_id': fixture['id'], 'role': role, 'recorded_unix_ns': time.time_ns()}
        if self.scope != PROTECTED_SCOPE:
            start['scope'] = self.scope
        if extra:
            start.update(extra)
        self._claim(ident + '.json', start)
        return self.captures.put(start)


class WholeCapsuleDispatcher(_EvaluationLedger):
    """Exactly granted baseline/candidate public jobs, with durable no-replay claims."""
    def __init__(self, *, root, runtime_root, manifest, grant_path, grant_sha256, cgroup_root, captures, benchmark=None):
        _require_root()
        kernel = load_v18_executor()
        RestrictedExecutor, ExecutionJob, ReadonlyMount = kernel.RestrictedExecutor, kernel.ExecutionJob, kernel.ReadonlyMount
        from jiuwenswarm.research_rsi.records import RecordStore
        self.abi = executor_abi(RestrictedExecutor, ExecutionJob, ReadonlyMount)
        grant_path = _root_custody(grant_path)
        need(grant_path.stat().st_size <= 65536, 'BOUNDED_ROOT_GRANT_REQUIRED')
        self._load_grant(grant_path, grant_sha256, manifest)
        self.runtime_root = _root_custody(runtime_root, directory=True)
        self.manifest = verify_runtime(self.runtime_root, manifest)
        self.runtime_closure = require_runtime_closure(self.runtime_root, self.manifest)
        for path in (self.runtime_root, *self.runtime_root.rglob('*')):
            _root_custody(path, directory=path.is_dir())
            # The worker inventories the whole runtime: directories must be
            # listable (r+x), not merely searchable, or files silently vanish.
            need(path.stat().st_mode & 0o005 == 0o005 if path.is_dir() else path.stat().st_mode & 0o004,
                 'WORKER_READABLE_RUNTIME_REQUIRED: ' + str(path))
        self.root = _root_custody(root, directory=True)
        need(type(captures) is RecordStore, 'ROOT_CAPTURE_RECORD_STORE_REQUIRED')
        _root_custody(captures.root, directory=True)
        self.captures, self.cgroup_root = captures, _root_custody(cgroup_root, directory=True)
        self.grant_ref = captures.put(self.grant)
        self.runtime_manifest_ref = captures.put(self.manifest)
        self.job_type, self.mount_type = ExecutionJob, ReadonlyMount
        self.parent = (self.runtime_root / 'source/jiuwenswarm' / registered_capsule(self.grant['capsule_name']).carrier_path).read_bytes()
        need(digest(self.parent) == self.grant['parent_sha256'], 'FROZEN_PARENT_BYTES_DIFFER')
        self.parent_ref = captures.put_bytes(self.parent)
        for name in ('assets', 'work', 'claims'):
            (self.root / name).mkdir(mode=0o711, exist_ok=True)
            _root_custody(self.root / name, directory=True)
        # Every Root-owned directory from the evidence root down to the public
        # job parents becomes worker-searchable (precreated 0700 included);
        # ancestors above the evidence root are verified, never changed.
        # The actual worker identity then resolves each bind source path.
        for name in ('assets', 'work'):
            ensure_worker_traversal(self.root, self.root / name)
        self.traversal = require_worker_traversal([self.root / 'assets', self.root / 'work'], trees=[self.runtime_root])
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
            capture=lambda raw, **_: self._capture(raw), executor_uid=WORKER_UID, executor_gid=WORKER_GID,
            allowed_asset_roots=[self.root / 'assets', self.runtime_root], verify_mount=verify)
        need(not self.executor.prerequisites(), 'ACTUAL_KERNEL_CONFINEMENT_PREREQUISITES_UNAVAILABLE')
        self._set_benchmark(benchmark)

    async def _run_case(self, *, role, fixture, body, candidate_ref, binding_ref, ident, index):
        job = await self._run_job(role=role, fixture=fixture, candidate_ref=candidate_ref, binding_ref=binding_ref,
            ident=ident, index=index, make_assets=lambda profile: capsule_job_assets(self.grant['capsule_name'],
                runtime_root=self.runtime_root, manifest=self.manifest, candidate=body,
                inputs=fixture_inputs(self.grant['capsule_name'], fixture), iterations=self.grant['iterations'], **profile))
        return self._finish_case(role=role, fixture=fixture, assets=job['assets'], receipt=job['receipt'],
            stdout=job['stdout'], start_ref=job['start_ref'], candidate_ref=candidate_ref,
            input_ref=job['input_ref'], program_ref=job['program_ref'])

    async def _run_job(self, *, role, fixture, candidate_ref, binding_ref, ident, index, make_assets,
                       node_id='unqualified-whole-capsule-development', start_extra=None):
        """One protected V18 job; ``make_assets(profile_kwargs)`` builds its program."""
        need(self.executions < self.grant['max_executions'], 'ROOT_EXECUTION_BUDGET_EXHAUSTED')
        # Fail before consuming a claim or preparing a worker when the shared
        # host hierarchy has no room. Creation repeats this check for races.
        check_capacity(self.cgroup_root)
        assets = make_assets({})
        asset_root = self.root / 'assets' / ident; asset_root.mkdir(mode=0o755)
        work = self.root / 'work' / ident; work.mkdir(mode=0o700); os.chown(work, WORKER_UID, WORKER_GID)
        mounts = [self.mount_type(self.runtime_root, '/resources/capsule-runtime',
            {'id': 'capsule-runtime:' + assets['runtime_manifest_sha256'], 'sha256': assets['runtime_manifest_sha256']})]
        for name, raw in assets['files'].items():
            path = asset_root / name; path.write_bytes(raw); path.chmod(0o444)
            mounts.append(self.mount_type(path, '/resources/' + name, {'id': name, 'sha256': digest(raw)}))
        for path in (asset_root / 'worker.py', work):
            ensure_worker_traversal(self.root, path)
        store = self._store_for(fixture)
        input_ref = store.put_bytes(assets['files']['input.json'])
        program_ref = self.captures.put_bytes(assets['files']['worker.py'])
        test_ref = store.put({k: v for k, v in fixture.items() if k != 'fixture_set'}
                             if not self.loop else fixture)
        worker, limits = self.grant['worker'], self.grant['limits']
        job = self.job_type(job_id=ident, invocation_id=ident, contract_ref=worker['contract_ref'],
            run_id=self.grant['run_id'], node_id=node_id, attempt_id=role,
            sequence=1, role='treatment', repeat_index=index, seed=0, argv=assets['argv'], cwd=work,
            timeout_s=limits['timeout_s'], memory_mb=limits['memory_mb'], pids_max=limits['pids_max'],
            baseline_ref=self.parent_ref, validation_ref=test_ref, environment_ref=worker['environment_ref'],
            subject_ref=candidate_ref, hardware_ref=worker['hardware_ref'], readonly_mounts=tuple(mounts))
        start_ref = self._start_record(ident=ident, role=role, fixture=fixture, binding_ref=binding_ref,
            candidate_ref=candidate_ref, assets=assets, input_ref=input_ref, program_ref=program_ref, test_ref=test_ref,
            extra=start_extra)
        self.executions += 1; self.issued[ident] = job
        self.sealing = store is not self.captures
        try:
            receipt = await self.executor.run(job)
        finally:
            self.sealing = False
        # Retain the complete kernel receipt and verify its captured bytes
        # before retiring only this executor's empty group. Sealed job evidence
        # remains in the sealed store; copying public bindings into it never
        # makes withheld output visible to the controller.
        if store is not self.captures:
            for ref in (start_ref, program_ref, candidate_ref):
                store.put_ref(ref, self.captures.read(ref))
        retirement = retire_owned_group(self.executor, job, receipt=receipt,
            start_ref=start_ref, store=store)
        stdout = store.read(receipt['stdout_ref'])
        return {'assets': assets, 'receipt': receipt, 'stdout': stdout, 'start_ref': start_ref,
                'input_ref': input_ref, 'program_ref': program_ref, 'cgroup_retirement': retirement}


def make_dispatcher(kind, **options):
    """Explicitly configured dispatcher; never autodetected.

    ``kind`` must be ``"v18-bwrap"`` (protected production path) or
    ``"local"`` (plain subprocess, results tagged ``local_unprotected``).
    """
    need(kind in ('v18-bwrap', 'local'), 'EXPLICIT_DISPATCHER_KIND_REQUIRED')
    if kind == 'v18-bwrap':
        return WholeCapsuleDispatcher(**options)
    from .capsule_local_dispatcher import LocalDispatcher
    return LocalDispatcher(**options)
