"""Benchmark workloads, frozen protocol, statistics and correctness contract.

Codex's real-machine evidence (copied under ``codex_evidence/``) pins what the
port must reproduce: its frozen manifest (protocol + parent expectations) and
its round-2 paired samples with the comparison they produced.
"""
import base64
import copy
import hashlib
import json
from pathlib import Path

import pytest

from jiuwenswarm.research_rsi.records import encoded
from jiuwenswarm.research_rsi.targets import capsule_benchmark as bench
from jiuwenswarm.research_rsi.targets import capsules
from jiuwenswarm.research_rsi.targets.capsule_benchmark import (
    _drive, all_benchmark_fixtures, benchmark_config, benchmark_fixtures, benchmark_job_count, benchmark_protocol,
    build_cases, compare_paired_samples, compare_protocol_samples, effective_protocol, execution_plan, judge,
    observation, parent_expectations, timing_batches)
from jiuwenswarm.research_rsi.targets.capsule_executor import loop_budget_for, loop_execution_budget
from jiuwenswarm.research_rsi.targets.capsules import _carrier
from tests.unit_tests.research_rsi.test_capsule_runtime import installed_runtime  # noqa: F401 (fixture)

EVIDENCE = Path(__file__).with_name('codex_evidence')
NAMES = ['utility.calculate', 'utility.table_normalize']
STEM = {'utility.calculate': 'calculate', 'utility.table_normalize': 'table_normalize'}


def evidence(name):
    return json.loads((EVIDENCE / name).read_text('utf-8'))


def frozen_target(name):
    return next(row for row in evidence('capsule-benchmark-frozen-manifest-r3.json')['targets']
                if row['capsule_name'] == name)


@pytest.mark.parametrize('name', NAMES)
def test_data_driven_workloads_reproduce_codex_frozen_manifest(name):
    """benchmark.json + the generic generator == Codex's frozen protocol and parent pins."""
    frozen = frozen_target(name)
    protocol = benchmark_protocol(name)
    assert protocol == frozen['protocol']
    verified = next(row for row in evidence('verified-capsule-improvements-r2.json')['targets'] if row['capsule_name'] == name)
    assert hashlib.sha256(encoded(protocol)).hexdigest() == verified['frozen_protocol_sha256']
    for split in ('visible', 'evaluation'):
        cases = benchmark_fixtures(name, split)
        assert hashlib.sha256(encoded(cases)).hexdigest() == frozen['protocol']['splits'][split]['sha256']
        mine = [{k: v for k, v in row.items() if k != 'checker_passed'} for row in parent_expectations(name, split)]
        assert mine == frozen['expectations'][split]
    # 8 timed workloads per capsule (4 visible + 4 withheld), Codex's batch classes.
    timing = timing_batches(name)
    assert len(timing) == 8 and set(timing.values()) == {'small', 'large'}
    assert [ident for ident, batch in timing.items() if batch == 'small'] == [
        ident for ident in timing if ident.startswith('small')]
    # Source pins in the manifest are the installed parent/checker/packet.
    root = Path(capsules.__file__).resolve().parents[2]
    for path, sha in frozen['source_sha256'].items():
        assert hashlib.sha256((root / path).read_bytes()).hexdigest() == sha


@pytest.mark.parametrize('name', NAMES)
def test_statistics_reproduce_codex_round2_comparison(name):
    """Codex's 16.78% / 20.74%: same samples -> identical ratio, gain, CI and rows."""
    stem = STEM[name]
    paired = evidence(f'{stem}-paired-report-r2.json')
    readable = evidence(f'{stem}-readable-benchmark-r2.json')
    assert hashlib.sha256((EVIDENCE / f'{stem}-paired-report-r2.json').read_bytes()).hexdigest() == readable['original_report_sha256']
    expected = readable['frozen_comparison']
    protocol = benchmark_protocol(name)
    assert paired['protocol_sha256'] == hashlib.sha256(encoded(protocol)).hexdigest()
    assert compare_protocol_samples(protocol, paired['samples'], correctness_passed=True) == expected
    # The Interface E statistics with default gates give the same numbers.
    config = benchmark_config(name)
    ids = [i for split in protocol['splits'].values() for i in split['timing_case_ids']]
    value = compare_paired_samples(paired['samples'], workload_ids=ids, gates=config['gates'],
        resamples=config['bootstrap_resamples'], seed=config['bootstrap_seed'], confidence=config['confidence'])
    assert value['relative_gain'] == expected['relative_gain'] and value['median_ratio'] == expected['median_ratio']
    assert value['ratio_confidence_interval'] == expected['ratio_confidence_interval']
    assert value['rows'] == expected['rows'] and value['objective_met'] is True
    verified = next(row for row in evidence('verified-capsule-improvements-r2.json')['targets'] if row['capsule_name'] == name)
    assert 100 * value['relative_gain'] == verified['time_reduction_percent']
    # Per-workload medians agree with the readable report's per-workload table.
    for row in readable['supplementary_per_workload_uncertainty']:
        pairs = paired['samples'][row['workload']]
        assert len(pairs) == row['pairs'] == 11
        assert next(r for r in value['rows'] if r['id'] == row['workload'])['median_ratio'] == row['median_candidate_parent_ratio']


def samples(ids, ratio, reps=11):
    return {ident: [[100 + i, (100 + i) * ratio] for i in range(reps)] for ident in ids}


def test_gates_reject_noise_trade_offs_and_incorrect_candidates():
    protocol = benchmark_protocol('utility.calculate')
    ids = [i for split in protocol['splits'].values() for i in split['timing_case_ids']]
    compare = lambda values, **kw: compare_paired_samples(values, workload_ids=ids, resamples=500, **kw)
    assert compare(samples(ids, .85))['objective_met']
    assert not compare(samples(ids, .95))['objective_met']
    assert not compare(samples(ids, .85), correctness_passed=False)['objective_met']
    traded = samples(ids, .75)
    traded[ids[0]] = [[100, 106]] * 11  # one workload 6% slower
    result = compare(traded)
    assert not result['objective_met'] and not result['gate_results']['max_workload_regression']
    assert result['gate_results']['minimum_gain'] and result['gate_results']['ci_upper_bound']
    # Gates are configuration: a looser regression limit accepts the trade.
    assert compare(traded, gates={'max_workload_regression': 0.10})['objective_met']
    with pytest.raises(ValueError):
        compare_paired_samples({}, workload_ids=ids)
    with pytest.raises(ValueError):
        compare_protocol_samples(protocol, {ident: rows[:3] for ident, rows in samples(ids, .8).items()},
                                 correctness_passed=True)


def test_config_defaults_overrides_and_effective_protocol():
    config = benchmark_config('utility.calculate')
    assert config['gates'] == {'minimum_gain': 0.10, 'ci_upper_bound': 0.90, 'max_workload_regression': 0.05}
    assert config['repetitions'] == 11 and config['warmups'] == 2
    assert config['batch_iterations'] == {'small': 1000, 'large': 20} and config['semantic_edges'] is True
    assert effective_protocol('utility.calculate', config) == benchmark_protocol('utility.calculate')
    small = benchmark_config('utility.calculate', {'repetitions': 3, 'batch_iterations': {'large': 5},
                                                   'gates': {'ci_upper_bound': 0.95}})
    assert small['batch_iterations'] == {'small': 1000, 'large': 5} and small['gates']['minimum_gain'] == 0.10
    changed = effective_protocol('utility.calculate', small)
    assert changed['repetitions'] == 3 and changed['ci_upper_bound'] == 0.95 and changed != benchmark_protocol('utility.calculate')
    assert benchmark_config('utility.calculate', small) == small  # idempotent
    for bad in ({'repetitions': 0}, {'gates': {'unknown': 1}}, {'batch_iterations': {'huge': 5}},
                {'unreviewed': True}, {'bootstrap_resamples': 10}):
        with pytest.raises(ValueError):
            benchmark_config('utility.calculate', bad)


@pytest.mark.parametrize('name,paired', [('utility.calculate', 192), ('utility.table_normalize', 188)])
def test_execution_plan_is_paired_alternating_and_matches_codex_job_counts(name, paired):
    config = benchmark_config(name)
    plan = execution_plan(name, config)
    assert len(plan) == paired  # Codex's protected job counts (192 / 188)
    assert benchmark_job_count(name) == paired + 2 * 9
    assert benchmark_job_count(name, {'semantic_edges': False}) == paired
    timed = [job for job in plan if job['timed']]
    for job in timed:
        expected = ('parent', 'candidate') if job['repeat'] % 2 == 0 else ('candidate', 'parent')
        assert job['role'] in expected and job['warmups'] == 2
        assert job['batch_iterations'] == config['batch_iterations'][timing_batches(name)[job['fixture']['id']]]
    pairs = [(a['role'], b['role']) for a, b in zip(plan[::2], plan[1::2])]
    assert all(set(pair) == {'parent', 'candidate'} for pair in pairs)
    assert [pair for pair, job in zip(pairs, plan[::2]) if job['timed'] and job['repeat'] == 1][0] == ('candidate', 'parent')
    assert all(job['batch_iterations'] == 1 and job['warmups'] == 0 for job in plan if not job['timed'])


def test_workloads_come_only_from_data_with_one_generic_generator(monkeypatch):
    """No capsule-name branches: changing the data changes the workloads; any capsule can ship a spec."""
    source = Path(bench.__file__).read_text()
    assert 'utility.' not in source and 'calculate' not in source.replace('calculation', '')
    spec = capsules.benchmark_spec('utility.calculate')
    changed = copy.deepcopy(spec)
    changed['splits']['visible'][1]['table']['height'] = 7
    bench._fixtures_text.cache_clear(); bench._timing_text.cache_clear()
    monkeypatch.setattr(bench, 'benchmark_spec', lambda name: copy.deepcopy(changed))
    try:
        large = next(case for case in benchmark_fixtures('utility.calculate') if case['id'] == 'large-numbers')
        assert len(large['packet']['data']['table']['rows']) == 7
        assert benchmark_protocol('utility.calculate') != frozen_target('utility.calculate')['protocol']
    finally:
        bench._fixtures_text.cache_clear(); bench._timing_text.cache_clear()
    # Every case kind of the generic builder on a capsule-neutral spec.
    rows = [{'id': 'grid', 'timed': True, 'batch': 'b', 'vars': {'tag': 'x'},
             'table': {'height': 3, 'width': 2, 'column_name': 'c{k}', 'format': '.1f',
                       'cell': {'row_coef': 2, 'col_coef': 1, 'mod': 5, 'offset': -1, 'divisor': 2},
                       'patches': [{'rows': {'step': 2}, 'column': -1, 'value': 'p'}],
                       'encoding': {'kind': 'csv', 'delimiter': ';', 'lineterminator': '\n'}}},
            {'id': 'derived', 'derive': 'grid', 'malformed': True, 'set': [{'path': ['data', 'tag'], 'value': 'y'}]},
            {'id': 'literal', 'data': {'tag': {'$var': 'tag'}, 'cut': {'$slice': {'of': [1, 2, 3], 'step': -1}}},
             'files': [['a.txt', 'A']], 'vars': {'tag': 'z'}}]
    cases = build_cases(rows, split='s', workload_packet={'data': {'tag': {'$var': 'tag'}, 'cols': {'$var': 'columns'}},
                                                          'files': [['t.csv', {'$var': 'table'}]]})
    assert [c['id'] for c in cases] == ['grid', 'derived', 'literal'] and cases[1]['malformed'] is True
    assert cases[0]['packet']['files'][0]['text'] == 'c0;c1\n-0.5;p\n0.5;1.0\n1.5;p\n'
    assert cases[0]['packet']['data'] == {'tag': 'x', 'cols': ['c0', 'c1']} and cases[1]['packet']['data']['tag'] == 'y'
    assert cases[2]['packet']['data'] == {'tag': 'z', 'cut': [3, 2, 1]}
    with pytest.raises(ValueError):
        build_cases([{'id': 'x', 'derive': 'missing'}], split='s')
    with pytest.raises(ValueError):
        build_cases([{'id': 'x', 'data': {}, 'table': {}}], split='s')


def test_correctness_contract_parent_relative_and_checker_authoritative():
    name = 'utility.calculate'
    execute, _, key = _carrier(name)
    fixtures = {case['id']: case for case in all_benchmark_fixtures(name)}
    valid = fixtures['small-numbers']
    raw = _drive(execute, copy.deepcopy(valid['packet']))
    parent = observation(completed=True, input_unmodified=True, output=raw)
    same = judge(name, valid, parent, observation(completed=True, input_unmodified=True, output=raw))
    assert same == {'passed': True, 'rule': 'exact_parent_bytes', 'reason': None}
    respaced = json.dumps(json.loads(raw)).encode()  # checker-equivalent, different bytes
    assert not judge(name, valid, parent, observation(completed=True, input_unmodified=True, output=respaced))['passed']
    assert not judge(name, valid, parent, observation(completed=True, input_unmodified=False, output=raw))['passed']
    assert not judge(name, valid, parent, observation(completed=False, detail='timeout'))['passed']
    bad = fixtures['bad-bool']
    error = parent_expectations(name, None, fixtures=[bad])[0]['error']
    parent_error = observation(completed=True, input_unmodified=True, error=error)
    assert judge(name, bad, parent_error, observation(completed=True, input_unmodified=True, error=dict(error)))['passed']
    assert judge(name, bad, parent_error, observation(completed=True, input_unmodified=True,
                                                      error={**error, 'message': 'changed'}))['rule'] == 'error_identity'
    assert not judge(name, bad, parent_error, observation(completed=True, input_unmodified=True,
                                                          error={**error, 'message': 'changed'}))['passed']
    # Where the parent fails the checker: a checker pass is accepted (improvement),
    # the exact parent behaviour is accepted (no regression), anything else fails.
    from jiuwenswarm.research_rsi.targets.capsule_semantic_edges import semantic_edge_fixtures
    tie = next(case for case in semantic_edge_fixtures(name) if case['id'] == 'signed-zero-ties')
    tie_raw = _drive(execute, copy.deepcopy(tie['packet']))
    tie_parent = observation(completed=True, input_unmodified=True, output=tie_raw)
    fixed = json.loads(tie_raw)
    fixed['data'][key]['columns']['v']['max'] = '0.00'
    fixed_raw = json.dumps(fixed, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert bench.checker_passes(name, tie['packet'], fixed_raw) and not bench.checker_passes(name, tie['packet'], tie_raw)
    improved = judge(name, tie, tie_parent, observation(completed=True, input_unmodified=True, output=fixed_raw))
    assert improved['passed'] and improved['rule'] == 'checker' and improved['improved'] is True
    kept = judge(name, tie, tie_parent, observation(completed=True, input_unmodified=True, output=tie_raw))
    assert kept['passed'] and kept['improved'] is False
    other = json.loads(tie_raw); other['data'][key]['columns']['v']['count'] = 3
    assert not judge(name, tie, tie_parent, observation(completed=True, input_unmodified=True,
                                                        output=json.dumps(other).encode()))['passed']


def test_benchmark_program_reuses_guarded_bootstrap_and_has_no_child_clock():
    from jiuwenswarm.research_rsi.targets.capsule_benchmark_runtime import benchmark_worker_program, decode_benchmark_output
    raw = benchmark_worker_program('utility.calculate', manifest_sha256='a' * 64, candidate_sha256='b' * 64,
                                   input_sha256='c' * 64, iterations=20, warmups=2)
    compile(raw, 'protected-benchmark-test.py', 'exec')
    assert b'perf_counter' not in raw and b'monotonic' not in raw
    assert b'def require_original' in raw and b'require_original()' in raw and b'warmups = 2' in raw
    local = benchmark_worker_program('utility.calculate', manifest_sha256='a' * 64, candidate_sha256='b' * 64,
        input_sha256='c' * 64, iterations=5, warmups=0, execution_profile='local_unprotected',
        resource_root='/tmp/r', runtime_root='/tmp/t')
    compile(local, 'local-benchmark-test.py', 'exec')
    assert b"'execution_profile': 'local_unprotected'" in local
    with pytest.raises(ValueError):
        benchmark_worker_program('utility.calculate', manifest_sha256='a' * 64, candidate_sha256='b' * 64,
                                 input_sha256='c' * 64, iterations=0, warmups=2)
    output = b'{"result":"baseline test double"}'
    envelope = {'schema': 'ai4r-rsi-capsule-benchmark-child:1', 'iterations': 20, 'warmups': 2,
        'input_unmodified': True, 'observation': {'output_sha256': hashlib.sha256(output).hexdigest()},
        'output_base64': base64.b64encode(output).decode()}
    assert decode_benchmark_output(encoded(envelope))[1] == output
    for forged in ({**envelope, 'forged_time': 1}, {**envelope, 'observation': {'output_sha256': 'd' * 64}},
                   {**envelope, 'input_unmodified': False}):
        with pytest.raises(ValueError):
            decode_benchmark_output(encoded(forged))
    with pytest.raises(ValueError):
        decode_benchmark_output(b'{"schema":1,"schema":2}')


def test_grant_carries_a_separate_benchmark_wall(installed_runtime):
    from jiuwenswarm.research_rsi.targets import capsule_executor as executor
    from tests.unit_tests.research_rsi.test_capsule_dispatch_e2e import loop_grant
    from tests.unit_tests.research_rsi.test_capsule_executor import grant_for
    _, manifest = installed_runtime
    grant = loop_grant(manifest, 'utility.calculate')
    grant['limits']['benchmark_wall_s'] = 2 * 3600  # beyond the 3600 s session cap
    assert executor.validate_grant(grant, manifest) is grant
    for value in (0, executor.MAX_BENCHMARK_WALL_S + 1, 1.5):
        with pytest.raises(ValueError):
            executor.validate_grant({**grant, 'limits': {**grant['limits'], 'benchmark_wall_s': value}}, manifest)
    legacy = grant_for(manifest, 'utility.calculate')  # v2 grants keep their exact closed limits
    legacy['limits']['benchmark_wall_s'] = 60
    with pytest.raises(ValueError):
        executor.validate_grant(legacy, manifest)


def test_loop_budget_covers_benchmark_jobs():
    assert loop_execution_budget(20, max_iterations=3, trials=2) == 20 * (3 + 2 * 3)  # unchanged
    assert loop_execution_budget(20, max_iterations=3, trials=2, benchmark_jobs=210) == 20 * 9 + 3 * 210
    assert loop_execution_budget(20, max_iterations=3, trials=2, benchmark_jobs=210, max_benchmarks=1) == 20 * 9 + 210
    with pytest.raises(ValueError):
        loop_execution_budget(20, max_iterations=3, trials=2, benchmark_jobs=10, max_benchmarks=5)  # > baseline + 3
    name = 'utility.calculate'
    from jiuwenswarm.research_rsi.targets.capsule_executor import evaluation_fixtures
    cases = len(evaluation_fixtures(name))
    loop = {'max_iterations': 5, 'trials': 1}
    assert loop_budget_for(name, loop) == loop_execution_budget(cases, max_iterations=5, trials=1)
    assert loop_budget_for(name, {**loop, 'benchmark': True}) == loop_execution_budget(
        cases, max_iterations=5, trials=1, benchmark_jobs=192 + 18)
    # The slot's sizing dict (M3): exact with the capsule name; without it the
    # largest exact count of benchmarked capsules of that workload count.
    sizing = {'workloads': 8, 'repetitions': 11, 'warmups': 2, 'per_job_s': 6, 'wall_s': 9000}
    exact = loop_execution_budget(cases, max_iterations=5, trials=1, benchmark=sizing, capsule_name=name)
    assert exact == loop_execution_budget(cases, max_iterations=5, trials=1, benchmark_jobs=210, max_benchmarks=6)
    assert loop_execution_budget(cases, max_iterations=5, trials=1, benchmark=sizing) == exact  # 210 >= 206
    assert loop_budget_for(name, {**loop, 'benchmark': sizing}) == exact
    with pytest.raises(ValueError):
        loop_execution_budget(cases, max_iterations=5, trials=1, benchmark={**sizing, 'workloads': 3})
    settings = {'repetitions': 5, 'semantic_edges': False, 'max_benchmarks': 2}
    assert loop_budget_for(name, {**loop, 'benchmark': settings}) == loop_execution_budget(
        cases, max_iterations=5, trials=1, benchmark_jobs=8 * 5 * 2 + 8 * 2, max_benchmarks=2)


def test_root_benchmark_settings_come_from_the_session_sizing_and_its_grant():
    """M4 integration: Interface E is served exactly when the session carries
    the slot sizing; the grant pins its wall; the evaluator may only add
    batch/gate/bootstrap overrides that keep the sized job count."""
    from jiuwenswarm.research_rsi.targets.capsule_executor import LOOP_GRANT_SCHEMA, evaluator_benchmark_settings
    name = 'utility.calculate'
    sizing = {'workloads': 8, 'repetitions': 3, 'warmups': 1, 'per_job_s': 5, 'wall_s': 900}
    session = {'capsule_name': name, 'grant': {'schema': LOOP_GRANT_SCHEMA, 'limits': {'wall_s': 600, 'benchmark_wall_s': 900}},
               'loop': {'max_iterations': 2, 'trials': 1, 'benchmark': sizing}}
    assert evaluator_benchmark_settings(session) == {'repetitions': 3, 'warmups': 1}
    extra = {'batch_iterations': {'small': 50}, 'gates': {'minimum_gain': 0.05}}
    settings = evaluator_benchmark_settings(session, extra)
    assert settings == {**extra, 'repetitions': 3, 'warmups': 1}
    assert benchmark_job_count(name, benchmark_config(name, settings)) == 8 * 3 * 2 + 8 * 2 + 9 * 2
    # No sizing: nothing served, and an evaluator block alone is refused.
    plain = {**session, 'loop': {'max_iterations': 2}}
    assert evaluator_benchmark_settings(plain) is None
    with pytest.raises(ValueError, match='EVALUATOR_BENCHMARK_WITHOUT_SESSION_SIZING'):
        evaluator_benchmark_settings(plain, extra)
    with pytest.raises(ValueError, match='CONTRADICTS_SESSION_SIZING'):
        evaluator_benchmark_settings(session, {'repetitions': 11})
    with pytest.raises(ValueError, match='SIZED_BY_THE_SLOT'):
        evaluator_benchmark_settings(session, {'max_benchmarks': 9})
    with pytest.raises(ValueError, match='GRANT_BENCHMARK_WALL_DIFFERS'):
        evaluator_benchmark_settings({**session, 'grant': {'schema': LOOP_GRANT_SCHEMA, 'limits': {'wall_s': 600}}})
    with pytest.raises(ValueError, match='BENCHMARK_JOBS_DIFFER_FROM_SIZING'):
        evaluator_benchmark_settings(session, {'semantic_edges': False})
