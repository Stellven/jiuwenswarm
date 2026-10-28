"""Interface E through the real ``LocalDispatcher``: real runtime tree, real
guarded benchmark program, real parent worker vs Codex's retained round-2
Calculate candidate. Small repetitions; asserts the report and correctness
contract, and only the direction of the latency result (this box is noisy).
"""
import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from jiuwenswarm.research_rsi.records import RecordStore, encoded
from jiuwenswarm.research_rsi.targets import capsule_executor as executor
from jiuwenswarm.research_rsi.targets.capsule_benchmark import (REPORT_SCHEMA, benchmark_config,
    benchmark_job_count, benchmark_protocol)
from jiuwenswarm.research_rsi.targets.capsule_local_dispatcher import LocalDispatcher, dispatcher_for
from jiuwenswarm.research_rsi.targets.capsules import registered_capsule
from tests.unit_tests.research_rsi.test_capsule_dispatch_e2e import loop_grant
from tests.unit_tests.research_rsi.test_capsule_runtime import installed_runtime  # noqa: F401 (fixture)

EVIDENCE = Path(__file__).with_name('codex_evidence')
NAME = 'utility.calculate'
REPS = 3
# Small reps and batches keep this a unit test; the frozen defaults (11 reps,
# 1000/20 batches) are what the loop uses and what Codex measured.
SETTINGS = {'repetitions': REPS, 'bootstrap_resamples': 1000, 'batch_iterations': {'small': 100, 'large': 4}}


def codex_candidate():
    body = (EVIDENCE / 'calculate-native-candidate-r2.py.txt').read_bytes()
    verified = json.loads((EVIDENCE / 'verified-capsule-improvements-r2.json').read_text())
    pinned = next(row for row in verified['targets'] if row['capsule_name'] == NAME)['candidate_sha256']
    assert hashlib.sha256(body).hexdigest() == pinned
    return body


def make(tmp_path, runtime, manifest, *, settings=SETTINGS, budget=None):
    grant = loop_grant(manifest, NAME, timeout_s=120)
    cases = executor.evaluation_fixtures(NAME)
    jobs = benchmark_job_count(NAME, benchmark_config(NAME, settings))
    grant['max_executions'] = budget if budget is not None else executor.loop_execution_budget(
        len(cases), max_iterations=1, trials=1, parent_trials=1, benchmark_jobs=jobs)
    grant['limits']['wall_s'] = 3600
    grant_path = tmp_path / 'grant.json'; grant_path.write_bytes(encoded(grant))
    root = tmp_path / 'evaluator'; root.mkdir()
    captures = RecordStore(tmp_path / 'captures')
    dispatcher = dispatcher_for({'dispatcher': 'local', 'benchmark': settings}, root=root, runtime_root=runtime,
        manifest=manifest, grant_path=grant_path, grant_sha256=executor.digest(grant_path.read_bytes()),
        cgroup_root=None, captures=captures)
    assert type(dispatcher) is LocalDispatcher
    return dispatcher, captures, grant


def binding(dispatcher, grant, ref):
    return {'schema': executor.BINDING_SCHEMA, 'run_id': grant['run_id'], 'capsule_name': NAME,
            'runtime_manifest_sha256': grant['runtime_manifest_sha256'], 'parent_sha256': grant['parent_sha256'],
            'mutable_path': registered_capsule(NAME).carrier_path, 'candidate_ref': ref,
            'grant_sha256': executor.digest(encoded(grant))}


async def evaluate_pair(dispatcher, captures, grant, candidate):
    parent_ref = captures.put_bytes(dispatcher.parent)
    await dispatcher.evaluate('parent', body=dispatcher.parent, candidate_ref=parent_ref, iteration=0)
    ref = captures.put_bytes(candidate)
    await dispatcher.evaluate('candidate', body=candidate, candidate_ref=ref,
                              binding=binding(dispatcher, grant, ref), iteration=1)
    return ref


def test_local_benchmark_real_selected_worker_vs_equivalent_candidate(installed_runtime, tmp_path):
    runtime, manifest = installed_runtime
    candidate = (Path(__file__).resolve().parents[3] / 'jiuwenswarm' / registered_capsule(NAME).carrier_path).read_bytes() + b'\n# equivalent benchmark candidate\n'
    dispatcher, captures, grant = make(tmp_path, runtime, manifest)

    async def scenario():
        await evaluate_pair(dispatcher, captures, grant, candidate)
        before = dispatcher.executions
        report = await dispatcher.benchmark(dispatcher.parent, candidate, iteration=1)
        return before, report
    before, report = asyncio.run(scenario())
    try:
        protocol = benchmark_protocol(NAME)
        ids = [i for split in protocol['splits'].values() for i in split['timing_case_ids']]
        assert report['schema'] == REPORT_SCHEMA and report['scope'] == 'local_unprotected'
        assert report['candidate_sha256'] == hashlib.sha256(candidate).hexdigest()
        assert report['parent_sha256'] == grant['parent_sha256']
        assert report['correctness_passed'] is True, report['correctness']['failure']
        assert report['correctness']['failure'] is None
        assert report['semantic_edges']['enabled'] and report['semantic_edges']['passed'] is True
        # 8 timed workloads x REPS x 2, 8 untimed cases x 2, 9 semantic edges x 2.
        assert report['protected_jobs'] == report['planned_jobs'] == benchmark_job_count(NAME, SETTINGS)
        assert dispatcher.executions - before == report['protected_jobs'] <= grant['max_executions']
        assert len(report['evidence_refs']) == report['protected_jobs']
        assert [row['id'] for row in report['workloads']] == ids and set(report['samples']) == set(ids)
        assert all(len(pairs) == REPS for pairs in report['samples'].values())
        assert {row['split'] for row in report['workloads'] if row['withheld']} == {'evaluation'}
        assert {k: g['threshold'] for k, g in report['gates'].items()} == {
            'minimum_gain': 0.10, 'ci_upper_bound': 0.90, 'max_workload_regression': 0.05}
        assert all(g['passed'] is report['gate_results'][k] for k, g in report['gates'].items())
        assert report['repetitions'] == REPS
        assert set(report['gate_results']) == {'correctness', 'minimum_gain', 'ci_upper_bound', 'max_workload_regression'}
        assert report['frozen_protocol'] is False and report['protocol']['repetitions'] == REPS
        low, high = report['ratio_confidence_interval']
        assert 0 < low <= report['median_ratio'] <= high
        assert report['relative_gain'] == 1 - report['median_ratio']
        assert report['objective_met'] == all(report['gate_results'].values())
        # The direction Codex measured (16.78% on its box); never the exact size here.
        assert report['median_ratio'] > 0, report['summary']
        # Persisted exactly; every job original is in Root captures with a
        # ``capsule-*`` start claim; withheld inputs/outputs stay sealed.
        stored = captures.get(report['report_ref'])
        assert stored == {key: value for key, value in report.items() if key != 'report_ref'}
        starts = {path.stem for path in (dispatcher.root / 'claims').glob('capsule-*.json')}
        withheld = 0
        for ref in report['evidence_refs']:
            evidence = captures.get(ref)
            assert evidence['receipt']['scope'] == 'local_unprotected'
            assert evidence['receipt']['job_id'] in starts
            assert evidence['amortized_wall_s'] == evidence['wall_s'] / evidence['batch_iterations']
            if evidence['split'] == 'evaluation':
                withheld += 1
                with pytest.raises(FileNotFoundError):
                    captures.read(evidence['input_ref'])
        assert withheld and len(starts) == dispatcher.executions
        rules = {row['rule'] for row in report['correctness']['cases']}
        assert {'exact_parent_bytes', 'error_identity'} <= rules
        # The same candidate/iteration cannot be benchmarked twice (no replay).
        with pytest.raises(FileExistsError):
            asyncio.run(dispatcher.benchmark(dispatcher.parent, candidate, iteration=1))
    finally:
        dispatcher.close(); captures.close()


def test_benchmark_refuses_unevaluated_candidates_and_budget_before_any_job(installed_runtime, tmp_path):
    runtime, manifest = installed_runtime
    candidate = (Path(__file__).resolve().parents[3] / 'jiuwenswarm' / registered_capsule(NAME).carrier_path).read_bytes() + b'\n# equivalent benchmark candidate\n'
    cases = len(executor.evaluation_fixtures(NAME))
    dispatcher, captures, grant = make(tmp_path, runtime, manifest, budget=cases * 2 + 10)
    try:
        async def scenario():
            with pytest.raises(ValueError, match='EVALUATED_FIRST'):
                await dispatcher.benchmark(dispatcher.parent, candidate, iteration=1)
            await evaluate_pair(dispatcher, captures, grant, candidate)
            with pytest.raises(ValueError, match='EXACT_BASELINE_PARENT'):
                await dispatcher.benchmark(candidate, candidate, iteration=1)
            executions = dispatcher.executions
            with pytest.raises(ValueError, match='BUDGET_EXHAUSTED'):
                await dispatcher.benchmark(dispatcher.parent, candidate, iteration=1)
            assert dispatcher.executions == executions and dispatcher.halted is False
        asyncio.run(scenario())
    finally:
        dispatcher.close(); captures.close()


def _replaced(body, old, new):
    assert body.count(old) == 1, old
    return body.replace(old, new)


@pytest.mark.parametrize('label,edit,passed', [
    # Parent passes the checker on every edge but signed-zero ties; there the
    # checker is authoritative, so the documented max() tie fix is accepted.
    ('breaks the first-row max() tie', (b'str(max(values))', b'str(sorted(values)[-1])'), False),
    # Wrong count: differs from the parent where the parent passes the checker.
    ('breaks count', (b'metrics[operation] = len(values)', b'metrics[operation] = len(values) + 1'), False),
])
def test_semantic_edge_gate_applies_the_parent_relative_contract(installed_runtime, tmp_path, label, edit, passed):
    runtime, manifest = installed_runtime
    dispatcher, captures, grant = make(tmp_path, runtime, manifest)
    import importlib
    selected = importlib.import_module(registered_capsule(NAME).selected_worker_module)
    implementation = Path(__import__('inspect').getsourcefile(selected._execute)).read_bytes()
    candidate = _replaced(implementation, *edit)
    try:
        async def scenario():
            await evaluate_pair(dispatcher, captures, grant, candidate)
            return await dispatcher.semantic_edges(candidate, iteration=1)
        report = asyncio.run(scenario())
        assert report["passed"] is passed, (label, report["failure"], report["cases"])
        assert 'signed-zero-ties' not in report['parent_checker_discrepancies']
        rules = {row['id']: row['rule'] for row in report['cases']}
        if 'signed-zero-ties' in rules:
            assert rules['signed-zero-ties'] == 'exact_parent_bytes'
        if passed:
            assert report['failure'] is None and len(report['cases']) == report['case_count'] == 9
            assert rules['leading-zero-representations'] == 'exact_parent_bytes'
            assert rules['empty-mean-error'] == 'error_identity'
            assert report['protected_jobs'] == 18
        else:
            assert report['failure']['role'] == 'candidate' and report['failure']['kind'] == 'semantic'
            assert report['protected_jobs'] < 18 and dispatcher.halted is False
    finally:
        dispatcher.close(); captures.close()
