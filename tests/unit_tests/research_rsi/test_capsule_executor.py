"""Dispatcher budgeting/custody mechanics doubles; no sandbox qualification."""
import asyncio
import copy
import json
from pathlib import Path
import time
from types import SimpleNamespace

import pytest

from jiuwenswarm.research_rsi.records import RecordStore, encoded
from jiuwenswarm.research_rsi.targets.capsules import public_fixtures, registered_capsule
from jiuwenswarm.research_rsi.targets import capsule_executor as dispatcher
from tests.unit_tests.research_rsi.test_capsule_runtime import installed_runtime


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
def test_dispatcher_builds_historical_jobs_checks_packets_and_refuses_replay(installed_runtime, tmp_path, monkeypatch, name, count, fail_first):
    # Root/isolation gates are deliberately replaced ONLY in this local
    # mechanics test. The fake executor does not run candidate code or confer
    # security/runtime evidence; actual sandbox acceptance is a separate job.
    import jiuwenswarm.research.executor as kernel
    runtime, manifest = installed_runtime
    root = tmp_path / 'dispatch'; root.mkdir()
    cgroups = tmp_path / 'cgroups'; cgroups.mkdir()
    captures = RecordStore(tmp_path / 'captures')
    grant = grant_for(manifest, name)
    grant_path = tmp_path / 'grant.json'; grant_path.write_bytes(encoded(grant))
    jobs = []
    class ExecutorDouble:
        def __init__(self, **options): self.options = options
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
            group = cgroups / job.job_id; group.mkdir()
            (group / 'cgroup.events').write_text('populated 0\n'); (group / 'cgroup.procs').write_text('')
            jobs.append(job)
            capture = self.options['capture']
            return {'job_id': job.job_id, 'termination_reason': 'resource_limit_exceeded' if fail_first else 'completed', 'exit_code': 0,
                'observed_runtime': True, 'wall_time_s': .25, 'stdout_ref': capture(encoded(output)),
                'stderr_ref': capture(b''), 'observed_limits': {'admin_output_truncated': False,
                    'isolation_probe_ref': capture(b'{"local":"synthetic mechanics double"}')}}
    monkeypatch.setattr(kernel, 'RestrictedExecutor', ExecutorDouble)
    monkeypatch.setattr(kernel, 'ExecutionJob', lambda **kw: SimpleNamespace(**kw))
    monkeypatch.setattr(dispatcher, 'executor_abi', lambda *a: {'test_only': 'no actual ABI proof'})
    monkeypatch.setattr(dispatcher, '_require_root', lambda: None)
    monkeypatch.setattr(dispatcher, '_root_custody', lambda path, **kw: Path(path))
    monkeypatch.setattr(dispatcher.os, 'chown', lambda *a: None, raising=False)
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
    with pytest.raises(ValueError): asyncio.run(value.evaluate('parent', body=value.parent, candidate_ref=value.parent_ref))
    # A fresh owner cannot replay claims retained from the prior owner.
    restarted = dispatcher.WholeCapsuleDispatcher(root=root, runtime_root=runtime, manifest=manifest,
        grant_path=grant_path, grant_sha256=dispatcher.digest(grant_path.read_bytes()), cgroup_root=cgroups, captures=captures)
    with pytest.raises(FileExistsError): asyncio.run(restarted.evaluate('parent', body=restarted.parent, candidate_ref=restarted.parent_ref))
    captures.close()
