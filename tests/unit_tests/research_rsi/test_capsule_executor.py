"""Dispatcher budgeting/custody mechanics doubles; no sandbox qualification."""
import asyncio
import copy
import json
import os
from pathlib import Path
import stat
import time
from types import SimpleNamespace

import pytest

from jiuwenswarm.research_rsi.records import RecordStore, encoded
from jiuwenswarm.research_rsi.targets.capsules import public_fixtures, registered_capsule
from jiuwenswarm.research_rsi.targets import capsule_executor as dispatcher
from tests.unit_tests.research_rsi.test_capsule_runtime import installed_runtime
from tests.unit_tests.research_rsi.test_cgroup_lifecycle import fake_cgroupfs


def grant_for(manifest, name, *, paired=True):
    fixtures = public_fixtures(name)
    parent_path = 'source/jiuwenswarm/' + registered_capsule(name).carrier_path
    return {'schema': dispatcher.GRANT_SCHEMA, 'bootstrap_schema': dispatcher.BOOTSTRAP_SCHEMA, 'run_id': 'public-local-dispatcher-double',
        'capsule_name': name, 'runtime_manifest_sha256': dispatcher.digest(encoded(manifest)),
        'parent_sha256': next(row['sha256'] for row in manifest['files'] if row['path'] == parent_path),
        'fixture_sha256': dispatcher.digest(encoded(fixtures)), 'fixture_count': len(fixtures),
        'roles': ['parent', 'candidate'] if paired else ['parent'],
        'max_executions': len(fixtures) * (2 if paired else 1), 'iterations': 1,
        'limits': {'timeout_s': 30, 'memory_mb': 512, 'pids_max': 32, 'wall_s': 600},
        'worker': {name: {'id': 'local:mechanics-test', 'sha256': 'a' * 64}
                   for name in ('contract_ref', 'environment_ref', 'hardware_ref')},
        'expires_unix_s': int(time.time()) + 600, 'scope': 'public_m1_development_only',
        'production_admission': 'UNKNOWN'}


@pytest.mark.parametrize('name,count', [('utility.calculate', 4), ('utility.table_normalize', 5)])
def test_grant_uses_exact_real_fixture_count_and_never_invents_twelve(installed_runtime, name, count):
    _, manifest = installed_runtime
    grant = grant_for(manifest, name)
    assert dispatcher.validate_grant(grant, manifest)['max_executions'] == count * 2
    for key, value in [('bootstrap_schema', 'ai4r-rsi-capsule-bootstrap:1'), ('fixture_count', 12), ('max_executions', 24), ('roles', ['candidate']),
                       ('fixture_sha256', '0' * 64), ('production_admission', 'ADMITTED')]:
        changed = copy.deepcopy(grant); changed[key] = value
        with pytest.raises(ValueError): dispatcher.validate_grant(changed, manifest)


def test_exact_actual_executor_abi_rejects_current_or_arbitrary_base_before_effect():
    from jiuwenswarm.research.executor import RestrictedExecutor, ExecutionJob, ReadonlyMount
    with pytest.raises(ValueError, match='HISTORICAL_V18_EXECUTOR'):
        dispatcher.executor_abi(RestrictedExecutor, ExecutionJob, ReadonlyMount)


def test_parameterized_capture_bounds_both_pipes_and_preserves_separate_probe():
    class Reader:
        def __init__(self, chunks): self.chunks = list(chunks)
        async def read(self, size): return self.chunks.pop(0) if self.chunks else b''
        async def readline(self): return self.chunks.pop(0) if self.chunks else b''
    kills = []
    async def exercise():
        fence = dispatcher.BoundedCapture(lambda: kills.append(True), 16384)
        probe = fence.PREFIX + b'{"test":"mechanics only"}\n'
        stdout = fence.pipe(Reader([probe, b'a' * 12000]), probe=True)
        stderr = fence.pipe(Reader([b'b' * 12000, b'discarded']))
        assert await stdout.readline() == probe
        assert len(await stdout.read()) == 12000
        assert len(await stderr.read()) == 4384
        assert fence.used == fence.limit == 16384 and fence.overflow
    asyncio.run(exercise())
    assert kills == [True]
    with pytest.raises(ValueError): dispatcher.BoundedCapture(lambda: None, 2 * 1024 * 1024 + 1)


@pytest.mark.parametrize('name,count', [('utility.calculate', 4), ('utility.table_normalize', 5)])
@pytest.mark.parametrize('fail_first', [False, True])
def test_dispatcher_builds_historical_jobs_checks_packets_and_refuses_replay(installed_runtime, tmp_path, monkeypatch, fake_cgroupfs, name, count, fail_first):
    # Root/isolation gates are deliberately replaced ONLY in this local
    # mechanics test. The fake executor does not run candidate code or confer
    # security/runtime evidence; actual sandbox acceptance is a separate job.
    import jiuwenswarm.research.executor as kernel
    runtime, manifest = installed_runtime
    root = tmp_path / 'dispatch'; root.mkdir()
    cgroups = fake_cgroupfs.root
    captures = RecordStore(tmp_path / 'captures')
    grant = grant_for(manifest, name)
    grant_path = tmp_path / 'grant.json'; grant_path.write_bytes(encoded(grant))
    jobs = []
    class ExecutorDouble:
        def __init__(self, **options):
            self.options = options
            self.cgroup_root, self.active, self.owned_groups = cgroups, {}, {}
        def prerequisites(self): return []
        async def run(self, job):
            self.options['authorize_job'](job)
            assert not hasattr(job, 'output_limit_bytes')
            assert job.argv == ('/usr/local/bin/python3', '-I', '-S', '/resources/worker.py')
            for mount in job.readonly_mounts: self.options['verify_mount'](mount)
            original = json.loads(next(m.source for m in job.readonly_mounts if m.target == '/resources/input.json').read_bytes())['packet']
            fixture = next(row for row in public_fixtures(name) if row['packet'] == original)
            output = copy.deepcopy(original)
            output['data']['calculation_result' if name.endswith('calculate') else 'table'] = fixture['expected_task_output']
            group = fake_cgroupfs.group(job.job_id)
            self.owned_groups[job.job_id] = {'path': group, 'inode': group.stat().st_ino, 'invocation_id': job.invocation_id}
            jobs.append(job)
            capture = self.options['capture']
            return {'job_id': job.job_id, 'invocation_id': job.invocation_id,
                'contract_ref': job.contract_ref, 'subject_ref': job.subject_ref,
                'ended_at': '2026-10-28T00:00:00Z', 'memory_events': 'oom_kill 0\n', 'pids_events': 'max 0\n',
                'termination_reason': 'resource_limit_exceeded' if fail_first else 'completed', 'exit_code': 0,
                'observed_runtime': True, 'wall_time_s': .25, 'stdout_ref': capture(encoded(output)),
                'stderr_ref': capture(b''), 'observed_limits': {'admin_output_truncated': False,
                    'memory_max': '134217728', 'pids_max': '16',
                    'isolation_probe_ref': capture(b'{"local":"synthetic mechanics double"}')}}
    monkeypatch.setattr(kernel, 'RestrictedExecutor', ExecutorDouble)
    monkeypatch.setattr(kernel, 'ExecutionJob', lambda **kw: SimpleNamespace(**kw))
    monkeypatch.setattr(dispatcher, 'load_v18_executor', lambda: kernel)
    monkeypatch.setattr(dispatcher, 'executor_abi', lambda *a: {'test_only': 'no actual ABI proof'})
    monkeypatch.setattr(dispatcher, '_require_root', lambda: None)
    monkeypatch.setattr(dispatcher, '_root_custody', lambda path, **kw: Path(path))
    monkeypatch.setattr(dispatcher.os, 'chown', lambda *a: None, raising=False)
    # Worker-identity traversal is proven separately on real directories
    # (test_capsule_dispatch_e2e); pytest's private temp root is not part of it.
    traversed = []
    monkeypatch.setattr(dispatcher, 'ensure_worker_traversal', lambda root, path, **kw: traversed.append(path) or [])
    monkeypatch.setattr(dispatcher, 'require_worker_traversal', lambda paths, **kw: {'mode': 'test-double', 'blocking': None})
    value = dispatcher.WholeCapsuleDispatcher(root=root, runtime_root=runtime, manifest=manifest,
        grant_path=grant_path, grant_sha256=dispatcher.digest(grant_path.read_bytes()), cgroup_root=cgroups, captures=captures)
    assert value.plan()['maximum_executions'] == count * 2
    changed = value.parent + b'\n# public local semantics preservation candidate\n'
    changed_ref = captures.put_bytes(changed)
    binding = {'schema': dispatcher.BINDING_SCHEMA, **{key: grant[key] for key in
        ('run_id', 'capsule_name', 'runtime_manifest_sha256', 'parent_sha256')},
        'mutable_path': registered_capsule(name).carrier_path, 'candidate_ref': changed_ref,
        'grant_sha256': dispatcher.digest(encoded(grant))}
    with pytest.raises(ValueError, match='BASELINE_MUST_COMPLETE_FIRST'):
        asyncio.run(value.evaluate('candidate', body=changed, candidate_ref=changed_ref, binding=binding))
    baseline = asyncio.run(value.evaluate('parent', body=value.parent, candidate_ref=value.parent_ref))
    if fail_first:
        assert baseline['executions'] == 1 and baseline['passed'] is False and len(jobs) == 1
        with pytest.raises(ValueError, match='HALTED_AFTER_FAILED_OR_UNKNOWN'):
            asyncio.run(value.evaluate('candidate', body=changed, candidate_ref=changed_ref, binding=binding))
        assert len(jobs) == 1
        captures.close()
        return
    candidate = asyncio.run(value.evaluate('candidate', body=changed, candidate_ref=changed_ref, binding=binding))
    assert baseline['passed_count'] == candidate['passed_count'] == count
    assert baseline['protected_wall_s'] == candidate['protected_wall_s'] == count * .25
    assert len(jobs) == count * 2 and len({job.job_id for job in jobs}) == count * 2
    assert len(fake_cgroupfs.removals) == len(jobs)
    assert all(owned['retired'] for owned in value.executor.owned_groups.values())
    # Every job's private work directory and its asset files were brought into
    # worker traversal custody before dispatch (general, path-derived).
    assert {job.cwd for job in jobs} <= set(traversed)
    assert all(root / 'assets' / job.job_id / 'worker.py' in traversed for job in jobs)
    upgraded = dispatcher.visible_result_v2(baseline)
    assert upgraded['schema'].endswith(':2') and upgraded['case_count'] == count and upgraded['failure'] is None
    assert all(row['fixture_set'] == 'public' for row in upgraded['rows']) and baseline['schema'].endswith(':1')
    with pytest.raises(ValueError): asyncio.run(value.evaluate('parent', body=value.parent, candidate_ref=value.parent_ref))
    # A fresh owner cannot replay claims retained from the prior owner.
    restarted = dispatcher.WholeCapsuleDispatcher(root=root, runtime_root=runtime, manifest=manifest,
        grant_path=grant_path, grant_sha256=dispatcher.digest(grant_path.read_bytes()), cgroup_root=cgroups, captures=captures)
    with pytest.raises(FileExistsError): asyncio.run(restarted.evaluate('parent', body=restarted.parent, candidate_ref=restarted.parent_ref))
    captures.close()


# --- Bounded coalesced-frame reader on the kernel's child pipes ---------------

class ChunkReader:
    """Arbitrary read boundaries, as a real pipe delivers them."""
    def __init__(self, data, sizes):
        self.data, self.sizes = bytes(data), list(sizes)
    async def read(self, size=65536):
        if not self.data:
            return b''
        step = min(size, self.sizes.pop(0) if self.sizes else size)
        chunk, self.data = self.data[:step], self.data[step:]
        return chunk
    async def readline(self):
        raise AssertionError('StreamReader.readline (64 KiB limit) must not be used')


def drain_like_kernel(pipe):
    async def run():
        first = await pipe.readline()
        rest = []
        while chunk := await pipe.read(65536):
            rest.append(chunk)
        return first, b''.join(rest)
    return asyncio.run(run())


@pytest.mark.parametrize('sizes', [[1] * 64 + [7, 3, 65536], [65536], [5, 4096, 13, 9]])
def test_probe_frame_coalesced_with_output_and_split_across_reads(sizes):
    probe = dispatcher.BoundedCapture.PREFIX + b'{"probe":1}\n'
    body = b'{"frame":2}\n{"frame":3}\n' + b'z' * 70000  # >64 KiB without newline
    fence = dispatcher.BoundedCapture(lambda: None, 1024 * 1024)
    first, rest = drain_like_kernel(fence.pipe(ChunkReader(probe + body, sizes), probe=True))
    assert first == probe and rest == body
    assert fence.used == len(body) and not fence.overflow  # probe never counted


def test_long_first_line_and_partial_eof_are_plain_output_counted_once():
    fence = dispatcher.BoundedCapture(lambda: None, 1024 * 1024)
    data = b'q' * 200000  # no newline at all, then EOF
    first, rest = drain_like_kernel(fence.pipe(ChunkReader(data, [3000] * 100), probe=True))
    assert first + rest == data and fence.used == len(data)
    fence = dispatcher.BoundedCapture(lambda: None, 1024)
    first, rest = drain_like_kernel(fence.pipe(ChunkReader(b'partial-no-newline', [4, 4]), probe=True))
    assert first + rest == b'partial-no-newline'
    empty = dispatcher.BoundedCapture(lambda: None, 1024)
    assert drain_like_kernel(empty.pipe(ChunkReader(b'', []), probe=True)) == (b'', b'')
    # A forged oversize "probe" is ordinary output, never a bypass.
    forged = dispatcher.BoundedCapture.PREFIX + b'x' * 5000 + b'\n'
    fence = dispatcher.BoundedCapture(lambda: None, 1024 * 1024)
    first, rest = drain_like_kernel(fence.pipe(ChunkReader(forged, [65536]), probe=True))
    assert first + rest == forged and fence.used == len(forged)


def test_oversize_output_kills_once_and_bounds_every_frame():
    kills = []
    fence = dispatcher.BoundedCapture(lambda: kills.append(1), 10000)
    data = b''.join(b'%06d\n' % i for i in range(5000))
    first, rest = drain_like_kernel(fence.pipe(ChunkReader(data, [777] * 100), probe=True))
    assert len(first + rest) == 10000 == fence.used and fence.overflow and kills == [1]
    assert (first + rest) == data[:10000]


def test_real_linux_pipe_many_frames_through_bounded_reader():
    import os, subprocess, sys
    code = ("import sys,os;w=sys.stdout.buffer;w.write(b'AI4R_EXECUTOR_PROBE_V1 {}\\n'+b''.join(b'{\"f\":%d}\\n'%i for i in range(5000))+b'y'*100000);w.flush()")
    async def run():
        process = await asyncio.create_subprocess_exec(sys.executable, '-c', code, stdout=asyncio.subprocess.PIPE)
        fence = dispatcher.BoundedCapture(lambda: process.kill(), 2 * 1024 * 1024)
        pipe = fence.pipe(process.stdout, probe=True)
        first = await pipe.readline(); parts = []
        while chunk := await pipe.read(65536):
            parts.append(chunk)
        await process.wait()
        return first, b''.join(parts), fence
    first, rest, fence = asyncio.run(run())
    assert first == b'AI4R_EXECUTOR_PROBE_V1 {}\n'
    assert rest.count(b'\n') == 5000 and rest.endswith(b'y' * 100000) and fence.used == len(rest)


# --- Evaluator traversal correction for any configured layout ----------------

@pytest.mark.skipif(not hasattr(os, 'geteuid') or os.geteuid() != 0,
                    reason='traversal correction is a Root evaluator duty (chmod/chown of Root-owned dirs)')
def test_precreated_private_parents_are_corrected_inside_evidence_root_only():
    import shutil, tempfile
    base = Path(tempfile.mkdtemp(prefix='evaluator-layout-'))
    try:
        base.chmod(0o711)
        evidence = base / 'any/configured/evidence'; evidence.mkdir(parents=True)
        for path in (base / 'any', base / 'any/configured'):
            path.chmod(0o711)
        evidence.chmod(0o700)
        job = evidence / 'deep/work/job'; job.mkdir(parents=True)
        for path in (evidence / 'deep', evidence / 'deep/work'):
            path.chmod(0o700)
        os.chown(job, 12003, 12003); job.chmod(0o700)
        assert dispatcher.worker_traversal([job])['blocking']['path'] == str(evidence)
        changed = dispatcher.ensure_worker_traversal(evidence, job)
        assert changed == [str(evidence), str(evidence / 'deep'), str(evidence / 'deep/work')]
        assert all(stat.S_IMODE(Path(p).stat().st_mode) == 0o711 for p in changed)
        assert stat.S_IMODE(job.stat().st_mode) == 0o700  # worker-owned job dir untouched
        assert dispatcher.worker_traversal([job]) == {'mode': 'simulated', 'uid': 12003, 'gid': 12003, 'blocking': None}
        asset = evidence / 'deep/assets/job/worker.py'; asset.parent.mkdir(parents=True); asset.write_text('x')
        asset.chmod(0o600)
        with pytest.raises(ValueError, match='WORKER_READABLE_JOB_FILE_REQUIRED'):
            dispatcher.ensure_worker_traversal(evidence, asset)
        asset.chmod(0o444); asset.parent.chmod(0o700)
        assert dispatcher.ensure_worker_traversal(evidence, asset) == [str(asset.parent)]
        # Ancestors above the evidence root are never changed, only reported.
        (base / 'any/configured').chmod(0o700)
        with pytest.raises(ValueError, match='BLOCKED_ABOVE_EVIDENCE_ROOT: ' + str(base / 'any/configured')):
            dispatcher.ensure_worker_traversal(evidence, job)
        assert stat.S_IMODE((base / 'any/configured').stat().st_mode) == 0o700
    finally:
        shutil.rmtree(base)
