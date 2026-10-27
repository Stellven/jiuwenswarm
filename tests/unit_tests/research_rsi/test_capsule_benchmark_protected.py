"""Interface E on the protected ``WholeCapsuleDispatcher`` path (mechanics).

As in ``test_capsule_executor``, Root/isolation gates and the V18 kernel are
replaced ONLY here by a double: it verifies each job's mounts and that its
``worker.py`` is exactly the reproducible guarded benchmark program, then
emulates the child envelope by driving the mounted body in-process. Receipt
walls are synthetic (candidate = 0.8 x parent per batch iteration), so the
statistics and gates are asserted exactly. No security evidence is implied.
"""
import ast
import asyncio
import base64
import hashlib
import json
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research_rsi.records import RecordStore, encoded
from jiuwenswarm.research_rsi.targets import capsule_executor as dispatcher
from jiuwenswarm.research_rsi.targets.capsule_benchmark import benchmark_config, benchmark_job_count
from jiuwenswarm.research_rsi.targets.capsule_benchmark_runtime import BOOTSTRAP_SCHEMA, benchmark_worker_program
from jiuwenswarm.research_rsi.targets.capsule_runtime import TARGET_MODULES
from jiuwenswarm.research_rsi.targets.capsules import registered_capsule
from tests.unit_tests.research_rsi.test_capsule_dispatch_e2e import loop_grant
from tests.unit_tests.research_rsi.test_capsule_runtime import installed_runtime  # noqa: F401 (fixture)

SETTINGS = {'repetitions': 3, 'bootstrap_resamples': 500, 'batch_iterations': {'small': 4, 'large': 2}}


def drive(name, body, packet):
    module = types.ModuleType(TARGET_MODULES[name])
    module.__package__ = TARGET_MODULES[name].rpartition('.')[0]
    exec(compile(body, 'mounted-body.py', 'exec'), module.__dict__)
    invocation = module.execute(None, {'packet': packet})
    try:
        invocation.send(None)
    except StopIteration as done:
        return done.value['result'].data, None
    except Exception as error:  # Mirrors the child's error observation.
        return None, {'type': type(error).__name__, 'code': getattr(error, 'code', None), 'message': str(error)}


@pytest.mark.parametrize('name', ['utility.calculate', 'utility.table_normalize'])
def test_protected_dispatcher_serves_interface_e(installed_runtime, tmp_path, monkeypatch, name):
    import jiuwenswarm.research.executor as kernel
    runtime, manifest = installed_runtime
    root = tmp_path / 'dispatch'; root.mkdir()
    cgroups = tmp_path / 'cgroups'; cgroups.mkdir()
    captures = RecordStore(tmp_path / 'captures')
    grant = loop_grant(manifest, name)
    cases = len(dispatcher.evaluation_fixtures(name))
    jobs_per = benchmark_job_count(name, benchmark_config(name, SETTINGS))
    # One A/A baseline benchmark plus one candidate benchmark.
    grant['max_executions'] = dispatcher.loop_execution_budget(cases, max_iterations=1, trials=1, parent_trials=1,
                                                              benchmark_jobs=jobs_per, max_benchmarks=2)
    grant['limits']['benchmark_wall_s'] = 7200  # Separately bounded benchmark wall.
    grant_path = tmp_path / 'grant.json'; grant_path.write_bytes(encoded(grant))
    seen = []

    class ExecutorDouble:
        def __init__(self, **options): self.options = options
        def prerequisites(self): return []

        async def run(self, job):
            self.options['authorize_job'](job)
            assert job.argv == ('/usr/local/bin/python3', '-I', '-S', '/resources/worker.py')
            mounts = {m.target: m.source for m in job.readonly_mounts}
            for mount in job.readonly_mounts:
                self.options['verify_mount'](mount)
            program = mounts['/resources/worker.py'].read_bytes()
            body = mounts['/resources/body.py'].read_bytes()
            raw_input = mounts['/resources/input.json'].read_bytes()
            packet = json.loads(raw_input)['packet']
            capture = self.options['capture']
            group = cgroups / job.job_id; group.mkdir()
            (group / 'cgroup.events').write_text('populated 0\n'); (group / 'cgroup.procs').write_text('')
            seen.append(job)
            if job.node_id == 'unqualified-whole-capsule-development':  # Ordinary evaluation job.
                output, _ = drive(name, body, packet)
                return {'job_id': job.job_id, 'termination_reason': 'completed', 'exit_code': 0, 'observed_runtime': True,
                        'wall_time_s': .25, 'stdout_ref': capture(output), 'stderr_ref': capture(b''),
                        'observed_limits': {'admin_output_truncated': False}}
            assert job.node_id == 'unqualified-whole-capsule-benchmark'
            config = ast.literal_eval(program.decode().rstrip().rsplit('\n', 1)[1][len('_child_main('):-1])
            warmups = int(program.decode().split('    warmups = ', 1)[1].split('\n', 1)[0])
            # The protected benchmark program is exactly reproducible from its pins.
            assert program == benchmark_worker_program(name, manifest_sha256=grant['runtime_manifest_sha256'],
                candidate_sha256=hashlib.sha256(body).hexdigest(), input_sha256=hashlib.sha256(raw_input).hexdigest(),
                iterations=config['iterations'], warmups=warmups)
            output, error = drive(name, body, packet)
            envelope = {'schema': 'ai4r-rsi-capsule-benchmark-child:1', 'iterations': config['iterations'],
                'warmups': warmups, 'input_unmodified': True,
                'observation': {'error': error} if error else {'output_sha256': hashlib.sha256(output).hexdigest()},
                'output_base64': None if error else base64.b64encode(output).decode()}
            per = 0.010 if job.subject_ref['sha256'] == grant['parent_sha256'] else 0.008
            return {'job_id': job.job_id, 'termination_reason': 'completed', 'exit_code': 0, 'observed_runtime': True,
                    'wall_time_s': per * config['iterations'], 'stdout_ref': capture(encoded(envelope)),
                    'stderr_ref': capture(b''), 'observed_limits': {'admin_output_truncated': False}}

    monkeypatch.setattr(kernel, 'RestrictedExecutor', ExecutorDouble)
    monkeypatch.setattr(kernel, 'ExecutionJob', lambda **kw: SimpleNamespace(**kw))
    monkeypatch.setattr(dispatcher, 'executor_abi', lambda *a: {'test_only': 'no actual ABI proof'})
    monkeypatch.setattr(dispatcher, '_require_root', lambda: None)
    monkeypatch.setattr(dispatcher, '_root_custody', lambda path, **kw: Path(path))
    monkeypatch.setattr(dispatcher.os, 'chown', lambda *a: None, raising=False)
    monkeypatch.setattr(dispatcher, 'ensure_worker_traversal', lambda root, path, **kw: [])
    monkeypatch.setattr(dispatcher, 'require_worker_traversal', lambda paths, **kw: {'mode': 'test-double'})
    value = dispatcher.make_dispatcher('v18-bwrap', root=root, runtime_root=runtime, manifest=manifest,
        grant_path=grant_path, grant_sha256=dispatcher.digest(grant_path.read_bytes()), cgroup_root=cgroups,
        captures=captures, benchmark=SETTINGS)
    assert type(value) is dispatcher.WholeCapsuleDispatcher
    assert value.benchmark_plan()['jobs_per_benchmark'] == jobs_per
    candidate = value.parent + b'\n# latency-neutral rewrite for mechanics\n'
    ref = captures.put_bytes(candidate)
    binding = {'schema': dispatcher.BINDING_SCHEMA, **{key: grant[key] for key in
        ('run_id', 'capsule_name', 'runtime_manifest_sha256', 'parent_sha256')},
        'mutable_path': registered_capsule(name).carrier_path, 'candidate_ref': ref,
        'grant_sha256': dispatcher.digest(encoded(grant))}
    try:
        async def scenario():
            await value.evaluate('parent', body=value.parent, candidate_ref=value.parent_ref, iteration=0)
            baseline = await value.benchmark(value.parent, value.parent, iteration=0)
            await value.evaluate('candidate', body=candidate, candidate_ref=ref, binding=binding, iteration=1)
            return baseline, await value.benchmark(value.parent, candidate, iteration=1)
        baseline, report = asyncio.run(scenario())
        # A/A baseline: parent against itself, ratio exactly 1, objective not met.
        assert baseline['candidate_sha256'] == baseline['parent_sha256'] == grant['parent_sha256']
        assert baseline['correctness_passed'] is True and baseline['median_ratio'] == pytest.approx(1.0)
        assert baseline['objective_met'] is False and baseline['gates']['minimum_gain']['passed'] is False
        assert report['correctness_passed'] is True, report['correctness']['failure']
        assert report['scope'] == dispatcher.PROTECTED_SCOPE
        assert report['protected_jobs'] == jobs_per and value.executions == grant['max_executions']
        assert report['median_ratio'] == pytest.approx(0.8) and report['relative_gain'] == pytest.approx(0.2)
        assert report['ratio_confidence_interval'] == pytest.approx([0.8, 0.8])
        assert report['objective_met'] is True and all(report['gate_results'].values())
        assert all(gate['passed'] is True for gate in report['gates'].values()) and report['repetitions'] == 3
        assert len(report['evidence_refs']) == report['protected_jobs']
        assert all(row['median_ratio'] == pytest.approx(0.8) for row in report['workloads'])
        bench_jobs = [job for job in seen if job.node_id.endswith('benchmark')]
        assert len(bench_jobs) == 2 * jobs_per and all(job.job_id.startswith('capsule-') for job in bench_jobs)
        assert len(list((root / 'claims').glob('capsule-*.json'))) == value.executions
        bench_jobs = bench_jobs[jobs_per:]
        assert len(bench_jobs) == jobs_per and len({job.job_id for job in bench_jobs}) == jobs_per
        stored = captures.get(report['report_ref'])
        assert stored['evidence_refs'] == report['evidence_refs'] and stored['schema'] == report['schema']
        public = captures.get(next(ref for ref in report['evidence_refs'] if _public(captures, ref)))
        assert public['bootstrap_schema'] == BOOTSTRAP_SCHEMA
        start = captures.get(public['start_ref'])
        assert start['benchmark']['paired_candidate_sha256'] == ref['sha256']
        # Budget exhausted exactly: nothing further can be issued.
        with pytest.raises(ValueError):
            asyncio.run(value.benchmark(value.parent, candidate, iteration=2))
    finally:
        value.close(); captures.close()


def _public(captures, ref):
    try:
        captures.get(ref)
        return True
    except FileNotFoundError:
        return False
