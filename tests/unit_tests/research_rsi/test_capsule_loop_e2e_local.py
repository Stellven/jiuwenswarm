"""Model-free end-to-end improvement loop on the real capsules (local dispatcher).

Everything below the model is the production code path, wired exactly as
``deploy/m1/rsi_capsule_run.run`` wires it: the Root ``evaluator`` (dispatcher
selected by ``dispatcher_for({'dispatcher': 'local'})``) and the unprivileged
``controller`` talk over real OS pipes; the controller validates and imports
every Root row/result, and ``capsule_session.run_session`` runs the actual
diagnose -> propose -> evaluate -> score -> keep-best loop. The real
``LocalDispatcher`` executes the frozen runtime tree, the guarded bootstrap
program and the real worker bodies over the real public, public_extended and
held_out fixtures with the independent checker, three trials each; the real
``capsule_objective`` scores. Only the model is scripted (``FakeBackend``).

Assertions avoid timing except where the objective's own noise rule decides
(table_normalize), and there the test asserts the rule, not a speed outcome.
"""
import asyncio
import json
import os
import threading
import time
from types import SimpleNamespace

import pytest

from deploy.m1 import rsi_capsule_run as run
from jiuwenswarm.research_rsi import capsule_session
from jiuwenswarm.research_rsi.model_backends import FakeBackend
from jiuwenswarm.research_rsi.records import RecordStore, encoded
from jiuwenswarm.research_rsi.targets import capsule_executor as executor
from jiuwenswarm.research_rsi.targets.capsule_benchmark import benchmark_config, benchmark_job_count
from jiuwenswarm.research_rsi.targets.capsule_objective import BENCHMARK_REPORT_SCHEMA, evaluation_fixtures
from jiuwenswarm.research_rsi.targets.capsules import public_fixtures, registered_capsule
from tests.unit_tests.research_rsi.test_capsule_dispatch_e2e import loop_grant
from tests.unit_tests.research_rsi.test_capsule_loop import diagnosis_text, proposal_text
from tests.unit_tests.research_rsi.test_capsule_runtime import installed_runtime  # noqa: F401 (fixture)

ITERATIONS, TRIALS = 3, 3


def replaced(body, old, new):
    assert body.count(old) == 1, old
    return body.replace(old, new)


def calculate_script(parent):
    broken = replaced(parent, b"metrics[operation] = len(values)", b"metrics[operation] = len(values) + 1")
    # The documented tie bug: max() keeps the first of equal Decimals
    # ("1.0" vs "1.00"); the checker requires the ordering-stable last one.
    fixed = replaced(parent, b"str(max(values))", b"str(sorted(values)[-1])")
    regressed = replaced(fixed, b"metrics[operation] = str(sum(values, Decimal(0)))",
                         b"metrics[operation] = str(sum(values, Decimal(1)))")
    return [('breaks count', broken), ('fixes the max() tie', fixed), ('regresses sum', regressed)]


def table_normalize_script(parent):
    # Semantics-preserving rewrites only: any improvement can come from
    # latency alone, and only above the objective's calibrated noise floor.
    hoisted = replaced(parent, b"if any(type(value) not in (str, int, float, bool, type(None))",
                       b"if any(type(value) not in _SCALARS")
    hoisted = replaced(hoisted, b"\n\ndef normalize(packet):", b"\n_SCALARS = (str, int, float, bool, type(None))\n\n\ndef normalize(packet):")
    fused = replaced(hoisted, b"        if len(rows) > 10000 or any(len(row) != len(columns) for row in rows):",
                     b"        width = len(columns)\n        if len(rows) > 10000 or any(len(row) != width for row in rows):")
    annotated = hoisted + b"\n# latency-only rewrite: scalar types hoisted to module scope\n"
    return [('hoists scalar types', hoisted), ('fuses width check', fused), ('annotated hoist', annotated)]


def forms(value):
    """Serializations a leaked held-out value could take inside a prompt."""
    out = set()
    for kwargs in ({}, {'sort_keys': True}, {'separators': (',', ':')},
                   {'sort_keys': True, 'separators': (',', ':')}, {'ensure_ascii': False}):
        text = json.dumps(value, **kwargs)
        out |= {text, json.dumps(text)[1:-1]}  # also as an escaped string inside JSON
    return out


def build(tmp_path, runtime_root, manifest, name, iterations=ITERATIONS, benchmark=None):
    target = registered_capsule(name)
    cases = evaluation_fixtures(name)
    store = RecordStore(tmp_path / 'controller-records')
    metadata = {key: {'schema': 'unit-local-worker:1', 'kind': key} for key in ('contract', 'environment', 'hardware')}
    grant = loop_grant(manifest, name)
    loop = {'model_backend': {'kind': 'fake'}, 'max_iterations': iterations,
            # No early no-progress stop: every scripted iteration runs.
            'max_no_progress': iterations + 1, 'trials': TRIALS}
    if benchmark is not None:
        # The slot-materialized sizing (Interface E): the grant carries its
        # wall and its exact per-call jobs for the A/A baseline + each iteration.
        loop['benchmark'] = benchmark['sizing']
        grant['limits'] = dict(grant['limits'], benchmark_wall_s=benchmark['sizing']['wall_s'])
        grant['expires_unix_s'] += benchmark['sizing']['wall_s']
    # The owner's budget function, exactly as the slot and prepare call it.
    grant.update(run_id='local-loop-' + name.replace('.', '-'),
                 max_executions=executor.loop_budget_for(name, loop, case_count=len(cases)),
                 worker={key + '_ref': store.put(record) for key, record in metadata.items()})
    root = tmp_path / 'evaluator'; root.mkdir()
    grant_path = tmp_path / 'grant.json'; grant_path.write_bytes(encoded(grant))
    parent = (runtime_root / 'source/jiuwenswarm' / target.carrier_path).read_bytes()
    parent_ref = store.put_bytes(parent)
    carrier = target.carrier_path.removeprefix('research/')
    ref = lambda text: store.put({'unit': text})
    session = {'schema': capsule_session.SCHEMA, 'id': grant['run_id'], 'capsule_name': name,
        'grant': grant, 'grant_ref': store.put(grant), 'parent_body_ref': parent_ref,
        'parent_declaration_ref': store.put({'identity': {'name': name, 'version_label': '1.0.0',
            'carrier': {'ref': carrier, 'sha256': parent_ref['sha256']},
            'body': [{'path': carrier, 'sha256': parent_ref['sha256']}]}}),
        'visible_context_ref': store.put({'schema': 'ai4r-rsi-whole-capsule-public-context:1', 'capsule_name': name,
            'mutable_path': target.carrier_path, 'fixtures': public_fixtures(name),
            'metrics': list(target.metrics), 'labels': 'PUBLIC'}),
        'preparation_ref': ref('preparation'), 'configuration_ref': ref('configuration'),
        'diagnosis_contract_ref': ref('diagnosis'), 'proposal_contract_ref': ref('proposal'),
        'native_scope_ref': ref('scope'), 'authorized_component': target.carrier_path,
        'observed_symptom': 'Harder public and held-out cases fail or are slow; improve the general behaviour.',
        'loop': loop}
    value = {'session': session, 'composition': {}, 'evaluator': {
        'root': str(root), 'runtime_root': str(runtime_root), 'manifest': manifest, 'metadata': metadata,
        'grant_path': str(grant_path), 'grant_sha256': executor.digest(grant_path.read_bytes()),
        'cgroup_root': None, 'dispatcher': 'local'}}
    if benchmark is not None:
        value['evaluator']['benchmark'] = benchmark['evaluator']
    return store, value, parent, cases


def run_loop(tmp_path, monkeypatch, runtime_root, manifest, name, make_script, *, iterations=ITERATIONS, benchmark=None):
    # ``benchmark``: {'sizing': session loop.benchmark, 'evaluator': Root
    # evaluator benchmark overrides}; Root then serves the real Interface E.
    store, value, parent, cases = build(tmp_path, runtime_root, manifest, name, iterations=iterations,
                                        benchmark=benchmark)
    script = make_script(parent)
    responses = []
    for index, (rationale, body) in enumerate(script, start=1):
        responses += [diagnosis_text, proposal_text(body, 'iteration %d: %s' % (index, rationale))]
    backend = FakeBackend(responses)
    original = capsule_session.run_session

    async def scripted_session(session, runtime, *, models=None):
        assert models is None  # the controller composes no models of its own here
        return await original(session, runtime, models=backend)
    monkeypatch.setattr(capsule_session, 'run_session', scripted_session)

    def write_frame(stream, item):
        stream.write(encoded(item) + b'\n'); stream.flush()

    def exclusive(path, item):
        with open(path, 'xb') as stream:
            stream.write(encoded(item))
    request_read, request_write = os.pipe(); response_read, response_write = os.pipe()
    outcome = {}

    def serve():
        try:
            with os.fdopen(request_read, 'rb') as incoming, os.fdopen(response_write, 'wb') as outgoing:
                asyncio.run(run.evaluator(value, incoming, outgoing, 'c' * 64,
                                          SimpleNamespace(write_frame=write_frame, exclusive=exclusive)))
        except BaseException as error:  # surfaced by the assertions below
            outcome['error'] = error
    thread = threading.Thread(target=serve); thread.start()

    async def compose(composition, evaluate):
        async def before_model():
            pass
        return SimpleNamespace(store=store, evaluate=evaluate, before_model=before_model,
            records=SimpleNamespace(put_ref=store.put_ref, close=lambda: None),
            lease_records=SimpleNamespace(close=lambda: None), core=SimpleNamespace(close=lambda: None),
            subscription=SimpleNamespace(transport=SimpleNamespace()))
    helper = SimpleNamespace(compose=compose, DevelopmentModel=None, write_frame=write_frame)
    try:
        with os.fdopen(response_read, 'rb') as incoming, os.fdopen(request_write, 'wb') as outgoing:
            ready = run.read_frame_deadline(incoming, time.monotonic() + 60)
            assert ready['ready'] is True and ready['plan']['scope'] == 'local_unprotected'
            assert ready['plan']['maximum_executions'] == value['session']['grant']['max_executions']
            assert ready['benchmark']['available'] is (benchmark is not None)
            if benchmark is not None:  # Root announces its exact per-call job count.
                assert ready['benchmark']['jobs'] == benchmark_job_count(name, benchmark_config(name, {
                    **benchmark['evaluator'], 'repetitions': benchmark['sizing']['repetitions'],
                    'warmups': benchmark['sizing']['warmups']}))
            result = asyncio.run(run.controller(value, incoming, outgoing, helper, benchmark_plan=ready['benchmark']))
    finally:
        thread.join(120)
    assert 'error' not in outcome, outcome
    completion = json.loads((tmp_path / 'evaluator' / 'complete.json').read_bytes())
    return store, value, result, backend, cases, completion


def common_assertions(store, value, result, backend, cases, completion):
    loop = result['loop']
    held = [case for case in cases if case['fixture_set'] == 'held_out']
    held_ids = {case['id'] for case in held}
    assert held and len(held) < len(cases)
    assert result['status'] == 'VISIBLE_EVALUATED_UNQUALIFIED', store.get(result['failure_ref'])
    assert result['security'] == 'UNQUALIFIED' and result['admission_ref'] is None and result['activation_ref'] is None
    assert loop['stop_reason'] == 'max_iterations' and loop['completed_iterations'] == ITERATIONS
    assert loop['model_calls'] == result['model_calls'] == 2 * ITERATIONS
    assert [row['model_calls'] for row in loop['iterations']] == [2] * ITERATIONS
    assert [(i, role) for i, role, _ in backend.prompts] == [(i, r) for i in range(1, ITERATIONS + 1)
                                                            for r in ('diagnosis', 'proposal')]
    # Root served parent once (3 trials for noise) then one evaluation per iteration.
    assert completion['stop'] == 'CONTROLLER_CLOSED' and completion['halted'] is False
    assert [(e['role'], e['iteration'], e['trials']) for e in completion['evaluations']] == (
        [('parent', 0, TRIALS)] + [('candidate', i, TRIALS) for i in range(1, ITERATIONS + 1)])
    assert completion['executions'] == len(cases) * TRIALS * (ITERATIONS + 1) <= value['session']['grant']['max_executions']
    assert loop['noise']['trials'] == TRIALS and len(loop['noise']['parent_wall_s_trials']) == TRIALS
    assert 0 < loop['noise']['floor_ratio'] < 1
    # Visible rows: v2, the whole tagged inventory, local scope, outputs on public rows only.
    raws = [result['parent_visible']] + [store.get(row['visible']['result_ref']) for row in loop['iterations']]
    for raw in raws:
        assert raw['schema'] == 'ai4r-rsi-whole-capsule-visible-result:2' and raw['scope'] == 'local_unprotected'
        assert [r['fixture_id'] for r in raw['rows']] == [c['id'] for c in cases]
        assert [(r['fixture_set'], r['fixture_group']) for r in raw['rows']] == [(c['fixture_set'], c['fixture_group']) for c in cases]
        assert len(raw['trial_wall_s']) == TRIALS and len(raw['trial_rows']) == TRIALS - 1
        for row in raw['rows'] + [r for trial in raw['trial_rows'] for r in trial]:
            assert row['receipt']['scope'] == 'local_unprotected'
            if row['fixture_set'] == 'held_out':
                assert 'actual_task_output' not in row and 'error' not in row
                assert all(set(check) == {'check_id', 'outcome'} for check in row['checks'])
            else:
                assert set(row['actual_task_output']) == {'value', 'truncated', 'bytes'}
    for row in loop['iterations']:
        for item in row['visible']['rows']:
            if item['fixture_set'] == 'held_out':
                assert set(item) <= set(('fixture_id', 'fixture_set', 'fixture_group', 'task_success',
                                         'protected_wall_s', 'evidence_ref'))
            else:
                assert 'actual_task_output' in item
    # The parent control passed on the historical public baseline.
    assert all(r['task_success'] for r in result['parent_visible']['rows'] if r['fixture_group'] == 'public')
    # Held-out cases reach the model as opaque ids with pass/fail only.
    prompts = [prompt for _, _, prompt in backend.prompts]
    def secrets(case):
        items = [case['expected_task_output'], case['packet'], case['packet']['data'], *case['packet'].get('files', [])]
        return set().union(*(forms(item) for item in items))
    # A held-out value that coincides with a public one (shared defaults) is not a leak.
    shown = set().union(*(secrets(case) for case in cases if case['fixture_set'] == 'public'))
    for case in held:
        leaked = secrets(case) - shown
        assert leaked
        found = sorted(text for text in leaked if any(text in prompt for prompt in prompts))
        assert not found, (case['id'], [text[:200] for text in found])
    failing_held = set(loop['iterations'][0]['held_out_failing_ids'])
    if failing_held:
        later = prompts[2] + prompts[3]
        assert all(ident in later for ident in failing_held)
    exported = json.dumps(loop)
    for case in held:
        assert not any(text in exported for text in forms(case['expected_task_output']))
    return loop, held_ids


def test_calculate_loop_keeps_the_real_tie_fix_and_rejects_breakage_and_regression(
        installed_runtime, tmp_path, monkeypatch):
    runtime_root, manifest = installed_runtime
    store, value, result, backend, cases, completion = run_loop(
        tmp_path, monkeypatch, runtime_root, manifest, 'utility.calculate', calculate_script)
    try:
        loop, held_ids = common_assertions(store, value, result, backend, cases, completion)
        first, fixed, regressed = loop['iterations']
        parent_failing = [r['fixture_id'] for r in result['parent_visible']['rows'] if not r['task_success']]
        assert parent_failing  # the headroom the loop exists to close
        # 1: a broken candidate is a scored outcome (not a loop stop), regressed, not kept.
        assert first['outcome'] == 'not_kept' and first['failure'] is None
        assert first['score']['regressed'] and not first['score']['improved'] and first['score']['newly_failed']
        assert first['visible']['failure'] is not None
        # 2: the real fix passes every case, including held-out ties.
        assert fixed['outcome'] == 'kept' and fixed['kept'] is True
        assert fixed['score']['improved'] is True and not fixed['score']['regressed']
        assert fixed['score']['correctness']['candidate'] == 1.0 > fixed['score']['correctness']['parent']
        assert set(fixed['score']['newly_passed']) == set(parent_failing)
        assert set(parent_failing) & held_ids and fixed['held_out_failing_ids'] == []
        # 3: proposed against the kept incumbent, regressed vs it, not kept.
        assert regressed['base']['sha256'] == fixed['candidate_ref']['sha256']
        assert json.loads(backend.prompts[5][2])['visible_context']['incumbent']['body'] == store.read(fixed['candidate_ref']).decode()
        assert regressed['outcome'] == 'not_kept' and regressed['selection']['score']['regressed']
        # Best is the fixing iteration; publication fields point at it.
        assert loop['best']['iteration'] == 2 and loop['best']['score']['improved'] is True
        assert result['selected_iteration'] == 2 and result['candidate_ref'] == fixed['candidate_ref']
        assert result['candidate_visible']['result_ref'] == fixed['visible']['result_ref']
        assert result['candidate_visible']['passed_count'] == result['candidate_visible']['case_count'] == len(cases)
        # Feedback after the break carries a public expected-vs-actual diff.
        feedback = store.get(first['next_feedback_ref'])['text']
        assert 'REGRESSIONS' in feedback and 'expected' in feedback and '.count' in feedback
        # Machine-selected read-only dependency excerpts (targets.capsule_context)
        # of the worker's imports reach diagnosis and proposal: packet.py first.
        header = '# read-only dependency: jiuwenswarm/research/capsule_extensions/packet.py'
        assert all(header in prompt for _, _, prompt in backend.prompts)
        assert 'def output_packet' in prompts_of(backend, 1, 'proposal')
        context = store.get(first['dependency_context_ref'])
        assert context['sources'][0]['path'] == 'jiuwenswarm/research/capsule_extensions/packet.py'
        assert 'unavailable' not in context and context['worker_sha256'] == value['session']['parent_body_ref']['sha256']
        assert not any('Dependency context unavailable' in item for item in loop['limitations'])
    finally:
        store.close()


def test_table_normalize_latency_only_loop_never_claims_correctness_and_obeys_noise(
        installed_runtime, tmp_path, monkeypatch):
    runtime_root, manifest = installed_runtime
    store, value, result, backend, cases, completion = run_loop(
        tmp_path, monkeypatch, runtime_root, manifest, 'utility.table_normalize', table_normalize_script)
    try:
        loop, _ = common_assertions(store, value, result, backend, cases, completion)
        parent_outcomes = [r['task_success'] for r in result['parent_visible']['rows']]
        for row in loop['iterations']:
            score, selection = row['score'], row['selection']['score']
            raw = store.get(row['visible']['result_ref'])
            # Semantics-preserving rewrites: identical per-case outcomes.
            assert [r['task_success'] for r in raw['rows']] == parent_outcomes
            assert not score['regressed'] and not score['newly_failed'] and not score['newly_passed']
            assert score['correctness']['candidate'] == score['correctness']['parent']
            # Improvement only from latency strictly above the calibrated noise floor.
            assert score['improved'] is score['above_noise']
            assert score['above_noise'] is (score['latency_ratio'] < score['noise_floor_ratio'])
            assert row['kept'] is (selection['improved'] and not selection['regressed'])
        kept = [row['iteration'] for row in loop['iterations'] if row['kept']]
        assert (loop['best'] is None) is (not kept)
        if loop['best'] is not None:
            assert loop['best']['iteration'] == kept[-1] and loop['best']['score']['above_noise']
        assert result['candidate_ref'] == (loop['iterations'][-1] if loop['best'] is None else
                                           loop['iterations'][loop['best']['iteration'] - 1])['candidate_ref']
    finally:
        store.close()


# Codex's round-2 native Calculate candidate (evidence
# verified-capsule-improvements-r2.json: 16.78% batched gain, CI upper 0.8418),
# rebuilt from the shared parent (sha256 22e37d0e...) as an exact byte transform.
CODEX_R2_CALCULATE_SHA256 = '0fb940f090431ba01ef940ad7e3dc54b2a14e1749e0f9a2e62d2cccd9522bb70'
CODEX_R2_COMPARISON = {'median_ratio': 0.8321761733497889, 'ratio_confidence_interval': [0.8185217253623219, 0.8417550863553439],
    'rows': {'small-numbers': 0.8066675710112525, 'large-numbers': 0.8543369331894676, 'wide-numbers': 0.820449711090694,
             'large-decimals': 0.8413980631717547, 'small-decimals': 0.8201475089392516,
             'large-mixed-sign': 0.8403496413949503, 'wide-reordered': 0.8215735498075524,
             'decimal-exponents': 0.8537810754011907}}


def codex_r2_calculate(parent):
    body = b'import copy\n' + parent
    body = replaced(body, b'from ..packet import output_packet, produced, validate_packet',
                    b'from ..packet import produced, validate_packet')
    body = replaced(body, b"    return {'result': produced(output_packet(packet, data=dict(packet['data'], "
                          b"calculation_result=calculate(packet))))}\n", (
        b"    # Preserve the original data lookup before calculate's packet validation.\n"
        b"    data = packet['data']\n"
        b"    calculation_result = calculate(packet)\n"
        b"    # Construct replacement data at the same point as the original expression.\n"
        b"    data = dict(data, calculation_result=calculation_result)\n"
        b"    # calculate has fully validated the input. Copy its envelope and data once.\n"
        b"    result = copy.deepcopy(dict(packet, data=data))\n"
        b"    result['limitations'] = list(dict.fromkeys(result['limitations']))\n"
        b"    # Keep the frozen final validation, canonical serialization and artifact type.\n"
        b"    return {'result': produced(result)}\n"))
    assert executor.digest(body) == CODEX_R2_CALCULATE_SHA256
    return [('drops the redundant output_packet validation and copies', body)]


def prompts_of(backend, iteration, role):
    return next(prompt for i, r, prompt in backend.prompts if (i, r) == (iteration, role))


# Interface E for the model-free e2e: the real paired batched protocol on the
# real LocalDispatcher with small repetitions and batches (configuration), so
# the whole loop runs in minutes. 8 timed workloads x 3 AB/BA pairs x 2 sides,
# + 8 untimed cases x 2 + 9 semantic edges x 2 = 82 jobs per call.
BENCH_REPS, BENCH_WARMUPS, BENCH_PER_JOB_S = 3, 2, 10
# Keep-decision gates, set explicitly here (gates are configuration; the
# production spec keeps Codex's frozen gain >= 10%, CI upper <= 0.90, no
# workload > 5% slower, at 11 pairs and 1000/20 batches). With 3 pairs and
# 100/4 batches on a shared 2-CPU box one run cleared the frozen gates and
# the next measured gain 12.9%, CI [0.829, 0.913] (CI gate failed) with a
# parent A/A CI of [0.969, 1.055]. The e2e therefore judges with gain
# >= 5%, CI upper <= 0.95, no workload > 10% slower: still a paired,
# CI-gated measurement clear of the A/A self-noise, never a single-job wall.
E2E_GATES = {'minimum_gain': 0.05, 'ci_upper_bound': 0.95, 'max_workload_regression': 0.10}


def e2e_benchmark(name, iterations):
    sizing = {'workloads': 8, 'repetitions': BENCH_REPS, 'warmups': BENCH_WARMUPS, 'per_job_s': BENCH_PER_JOB_S}
    jobs = executor.benchmark_jobs_for_sizing(sizing, capsule_name=name)
    sizing['wall_s'] = (iterations + 1) * jobs * BENCH_PER_JOB_S  # The slot's default wall rule.
    return {'sizing': sizing, 'evaluator': {'batch_iterations': {'small': 100, 'large': 4},
                                            'bootstrap_resamples': 1000, 'gates': dict(E2E_GATES)}}


def test_codex_r2_calculate_candidate_is_kept_on_the_paired_benchmark(installed_runtime, tmp_path, monkeypatch):
    runtime_root, manifest = installed_runtime
    name = 'utility.calculate'
    bench = e2e_benchmark(name, 1)
    store, value, result, backend, cases, completion = run_loop(
        tmp_path, monkeypatch, runtime_root, manifest, name, codex_r2_calculate, iterations=1, benchmark=bench)
    try:
        loop = result['loop']
        assert result['status'] == 'VISIBLE_EVALUATED_UNQUALIFIED', store.get(result['failure_ref'])
        assert loop['stop_reason'] == 'max_iterations' and loop['completed_iterations'] == 1
        (row,) = loop['iterations']
        parent_sha = value['session']['parent_body_ref']['sha256']
        assert row['candidate_ref']['sha256'] == CODEX_R2_CALCULATE_SHA256
        score = row['score']
        # Correctness contract on real bytes: every case the parent passes is
        # byte-identical; the parent's failing (tie) cases stay failing.
        assert not score['regressed'] and score['newly_failed'] == [] and score['newly_passed'] == []
        assert score['contract']['changed_bytes'] == [] and score['contract']['unverified'] == []
        assert score['contract']['byte_compared'] == score['contract']['parent_passed'] > 0
        assert score['correctness']['candidate'] == score['correctness']['parent'] < 1.0
        # The real Root report (parent -> candidate) over the pipes.
        report = row['benchmark']
        jobs = benchmark_job_count(name, benchmark_config(name, {**bench['evaluator'], 'repetitions': BENCH_REPS,
                                                                 'warmups': BENCH_WARMUPS}))
        assert jobs == 8 * BENCH_REPS * 2 + 8 * 2 + 9 * 2
        assert report['schema'] == BENCHMARK_REPORT_SCHEMA and report['scope'] == 'local_unprotected'
        assert report['candidate_sha256'] == CODEX_R2_CALCULATE_SHA256 and report['parent_sha256'] == parent_sha
        assert report['correctness_passed'] is True, report['correctness']['failure']
        assert report['semantic_edges']['passed'] is True
        assert report['protected_jobs'] == jobs == len(report['evidence_refs']) and report['repetitions'] == BENCH_REPS
        assert {key: gate['threshold'] for key, gate in report['gates'].items()} == E2E_GATES
        # The same eight data-driven workloads Codex measured, in its order.
        assert [w['id'] for w in report['workloads']] == list(CODEX_R2_COMPARISON['rows'])
        low, high = report['ratio_confidence_interval']
        assert 0 < low <= report['median_ratio'] <= high
        # Codex's direction (16.78% on its box), measured here for real.
        assert report['median_ratio'] < 1, report.get('summary')
        assert report['objective_met'] is True, (report['median_ratio'], report['ratio_confidence_interval'],
                                                  report['gate_results'], [(w['id'], w['median_ratio'])
                                                                           for w in report['workloads']])
        # Latency judged by the paired benchmark; kept on the explicit gates.
        assert score['latency_method'] == 'paired_batched_benchmark'
        assert score['latency_ratio'] == report['median_ratio'] and score['above_noise'] is True
        assert score['improved'] is True and row['kept'] is True and row['outcome'] == 'kept'
        assert row['benchmark_decision']['status'] == 'ran' and row['benchmark_decision']['beats_best'] is True
        # A/A baseline: parent against itself, ratio near 1, objective never met.
        baseline = loop['benchmark_baseline']
        assert baseline['candidate_sha256'] == baseline['parent_sha256'] == parent_sha
        assert baseline['correctness_passed'] is True and baseline['protected_jobs'] == jobs
        assert baseline['objective_met'] is False and 0.85 < baseline['median_ratio'] < 1.15, baseline['median_ratio']
        assert loop['benchmark_baseline_status'] == {**loop['benchmark_baseline_status'], 'kind': 'parent_a_a',
                                                     'status': 'measured', 'median_ratio': baseline['median_ratio']}
        # Root ledger: the A/A baseline then the iteration, every job a real
        # ``capsule-*`` start claim, all inside the grant's budget.
        assert completion['benchmarks'] == [
            {'iteration': 0, 'parent_sha256': parent_sha, 'candidate_sha256': parent_sha, 'protected_jobs': jobs,
             'objective_met': False, 'report_ref': baseline['report_ref']},
            {'iteration': 1, 'parent_sha256': parent_sha, 'candidate_sha256': CODEX_R2_CALCULATE_SHA256,
             'protected_jobs': jobs, 'objective_met': True, 'report_ref': report['report_ref']}]
        assert [(e['role'], e['iteration']) for e in completion['evaluations']] == [('parent', 0), ('candidate', 1)]
        evaluated = sum(e['executions'] for e in completion['evaluations'])
        claims = list((tmp_path / 'evaluator' / 'claims').glob('capsule-*.json'))
        assert completion['executions'] == evaluated + 2 * jobs == len(claims) <= value['session']['grant']['max_executions']
        assert value['session']['grant']['max_executions'] == executor.loop_budget_for(name, value['session']['loop'])
        assert loop['benchmark_accounting']['calls'] == 2 and loop['benchmark_accounting']['available'] is True
        assert loop['benchmark_accounting']['protected_jobs'] == 2 * jobs
        assert loop['best']['iteration'] == 1 and result['candidate_ref'] == row['candidate_ref']
        feedback = store.get(row['next_feedback_ref'])['text']
        first = report['workloads'][0]
        assert 'objective_met yes' in feedback and '%s %.3f' % (first['id'], first['median_ratio']) in feedback
        assert 'Single-job protected walls of parent' in backend.prompts[0][2]
        assert 'Paired benchmark self-noise (parent A/A)' in backend.prompts[0][2]
    finally:
        store.close()
