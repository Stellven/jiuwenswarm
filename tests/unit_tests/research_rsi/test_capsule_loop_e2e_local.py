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
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import pytest

from deploy.m1 import rsi_capsule_run as run
from jiuwenswarm.research_rsi import capsule_session
from jiuwenswarm.research_rsi.model_backends import FakeBackend
from jiuwenswarm.research_rsi.records import RecordStore, encoded
from jiuwenswarm.research_rsi.targets import capsule_executor as executor
from jiuwenswarm.research_rsi.targets.capsule_benchmark import benchmark_config, benchmark_job_count, all_benchmark_fixtures, timing_batches
from jiuwenswarm.research_rsi.targets.capsule_objective import BENCHMARK_REPORT_SCHEMA, evaluation_fixtures
from jiuwenswarm.research_rsi.targets.capsule_semantic_edges import semantic_edge_fixtures
from jiuwenswarm.research_rsi.targets.capsules import public_fixtures, registered_capsule, release_binding, _SourceStore
from tests.unit_tests.research_rsi.test_capsule_dispatch_e2e import loop_grant
from tests.unit_tests.research_rsi.test_capsule_loop import diagnosis_text, proposal_text
from tests.unit_tests.research_rsi.test_capsule_runtime import implementation_body, installed_runtime  # noqa: F401 (fixture)

ITERATIONS, TRIALS = 3, 3


def replaced(body, old, new):
    assert body.count(old) == 1, old
    return body.replace(old, new)


def calculate_script(parent):
    current = implementation_body('utility.calculate')
    broken = replaced(current, b"metrics[operation] = len(values)", b"metrics[operation] = len(values) + 1")
    # The partner checker now requires first-in-row tie spelling. The formerly
    # proposed last-sorted fix is a regression for the current selected release.
    regressed = replaced(current, b"str(max(values))", b"str(sorted(values)[-1])")
    return [('breaks count', broken), ('inlines current declared dependency', current),
            ('regresses current tie contract', regressed)]


def table_normalize_script(parent):
    parent = implementation_body('utility.table_normalize')
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
    import importlib
    source_store = _SourceStore()
    asset = importlib.import_module('jiuwenswarm.research.capsule_extensions.' + target.release_module + '.release').prepare(source_store)
    declaration = source_store.read_record(asset['declaration_ref'])
    ref = lambda text: store.put({'unit': text})
    session = {'schema': capsule_session.SCHEMA, 'id': grant['run_id'], 'capsule_name': name,
        'grant': grant, 'grant_ref': store.put(grant), 'parent_body_ref': parent_ref,
        'parent_declaration_ref': store.put(declaration),
        'release_binding': release_binding(name),
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


def test_calculate_loop_preserves_current_release_and_rejects_old_tie_semantics(
        installed_runtime, tmp_path, monkeypatch):
    runtime_root, manifest = installed_runtime
    store, value, result, backend, cases, completion = run_loop(
        tmp_path, monkeypatch, runtime_root, manifest, 'utility.calculate', calculate_script)
    try:
        loop, _ = common_assertions(store, value, result, backend, cases, completion)
        broken, correct, regressed = loop['iterations']
        assert all(row['task_success'] for row in result['parent_visible']['rows'])
        assert broken['outcome'] == 'not_kept' and broken['score']['regressed']
        assert broken['score']['newly_failed'] and broken['visible']['failure'] is not None
        assert correct['score']['correctness'] == {'parent': 1.0, 'candidate': 1.0}
        assert not correct['score']['newly_passed'] and not correct['score']['newly_failed']
        assert correct['score']['contract']['changed_bytes'] == []
        assert correct['kept'] is (correct['selection']['score']['improved']
                                  and not correct['selection']['score']['regressed'])
        assert regressed['outcome'] == 'not_kept' and regressed['score']['regressed']
        assert regressed['held_out_failing_ids']
        selected = result['selection']
        if correct['kept']:
            assert loop['best']['iteration'] == selected['iteration'] == 2
            assert selected['body_ref'] == correct['candidate_ref']
        else:
            assert loop['best'] is None and selected['role'] == 'parent'
            assert selected['body_ref'] == value['session']['parent_body_ref']
        feedback = store.get(broken['next_feedback_ref'])['text']
        assert 'REGRESSIONS' in feedback and 'expected' in feedback and '.count' in feedback
        header = '# read-only dependency: jiuwenswarm/research/capsule_extensions/packet.py'
        assert all(header in prompt for _, _, prompt in backend.prompts)
        assert 'def output_packet' in prompts_of(backend, 1, 'proposal')
        context = store.get(broken['dependency_context_ref'])
        assert any(row['path'].endswith('/calculate_v3/worker.py') for row in context['sources'])
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


def test_historical_codex_candidate_bytes_remain_pinned():
    source = Path(__file__).resolve().parents[3] / 'jiuwenswarm/research/capsule_extensions/calculate/worker.py'
    assert executor.digest(codex_r2_calculate(source.read_bytes())[0][1]) == CODEX_R2_CALCULATE_SHA256


def current_calculate_optimization(parent):
    body = b'import copy\n' + implementation_body('utility.calculate')
    body = replaced(body, b'from ..packet import output_packet, produced, validate_packet',
                    b'from ..packet import produced, validate_packet')
    body = replaced(body, b"    return {'result': produced(output_packet(packet, data=dict(packet['data'], "
                          b"calculation_result=calculate(packet))))}\n",
        b"    data = dict(packet['data'], calculation_result=calculate(packet))\n"
        b"    result = copy.deepcopy(dict(packet, data=data))\n"
        b"    result['limitations'] = list(dict.fromkeys(result['limitations']))\n"
        b"    return {'result': produced(result)}\n")
    return [('retains selected release semantics while removing redundant copying', body)]


def prompts_of(backend, iteration, role):
    return next(prompt for i, r, prompt in backend.prompts if (i, r) == (iteration, role))


# Interface E for the model-free e2e: the real paired batched protocol on the
# real LocalDispatcher with small repetitions and batches (configuration), so
# the whole loop runs in minutes. 8 timed workloads x 3 AB/BA pairs x 2 sides,
# + 8 untimed cases x 2 + 9 semantic edges x 2 = 82 jobs per call.
BENCH_REPS, BENCH_WARMUPS, BENCH_PER_JOB_S = 3, 2, 10
# Current release is measured with the production acceptance thresholds.
# Sample/batch counts are reduced for model-free integration testing; a child
# is retained only when its actual report clears every gate.
E2E_GATES = {'minimum_gain': 0.10, 'ci_upper_bound': 0.90, 'max_workload_regression': 0.05}


def e2e_benchmark(name, iterations):
    sizing = {'workloads': 8, 'repetitions': BENCH_REPS, 'warmups': BENCH_WARMUPS, 'per_job_s': BENCH_PER_JOB_S}
    jobs = executor.benchmark_jobs_for_sizing(sizing, capsule_name=name)
    sizing['wall_s'] = (iterations + 1) * jobs * BENCH_PER_JOB_S  # The slot's default wall rule.
    return {'sizing': sizing, 'evaluator': {'batch_iterations': {'small': 100, 'large': 4},
                                            'bootstrap_resamples': 1000, 'gates': dict(E2E_GATES)}}


def test_current_calculate_candidate_selection_follows_real_paired_benchmark(installed_runtime, tmp_path, monkeypatch):
    runtime_root, manifest = installed_runtime
    name = 'utility.calculate'
    bench = e2e_benchmark(name, 1)
    store, value, result, backend, cases, completion = run_loop(
        tmp_path, monkeypatch, runtime_root, manifest, name, current_calculate_optimization, iterations=1, benchmark=bench)
    try:
        loop = result['loop']
        assert result['status'] == 'VISIBLE_EVALUATED_UNQUALIFIED', store.get(result['failure_ref'])
        assert loop['stop_reason'] == 'max_iterations' and loop['completed_iterations'] == 1
        (row,) = loop['iterations']
        parent_sha = value['session']['parent_body_ref']['sha256']
        child_sha = row['candidate_ref']['sha256']
        assert child_sha == executor.digest(current_calculate_optimization(b'')[0][1])
        score = row['score']
        # Correctness contract on real bytes: every case the parent passes is
        # byte-identical; the selected partner parent passes all current cases.
        assert not score['regressed'] and score['newly_failed'] == [] and score['newly_passed'] == []
        assert score['contract']['changed_bytes'] == [] and score['contract']['unverified'] == []
        assert score['contract']['byte_compared'] == score['contract']['parent_passed'] > 0
        assert score['correctness']['candidate'] == score['correctness']['parent'] == 1.0
        # The real Root report (parent -> candidate) over the pipes.
        report = row['benchmark']
        jobs = benchmark_job_count(name, benchmark_config(name, {**bench['evaluator'], 'repetitions': BENCH_REPS,
                                                                 'warmups': BENCH_WARMUPS}))
        assert jobs == 8 * BENCH_REPS * 2 + 2 * sum(case['id'] not in timing_batches(name) for case in all_benchmark_fixtures(name)) + 2 * len(semantic_edge_fixtures(name))
        assert report['schema'] == BENCHMARK_REPORT_SCHEMA and report['scope'] == 'local_unprotected'
        assert report['candidate_sha256'] == child_sha and report['parent_sha256'] == parent_sha
        assert report['correctness_passed'] is True, report['correctness']['failure']
        assert report['semantic_edges']['passed'] is True
        assert report['protected_jobs'] == jobs == len(report['evidence_refs']) and report['repetitions'] == BENCH_REPS
        assert {key: gate['threshold'] for key, gate in report['gates'].items()} == E2E_GATES
        # The same eight data-driven workloads Codex measured, in its order.
        assert [w['id'] for w in report['workloads']] == list(CODEX_R2_COMPARISON['rows'])
        low, high = report['ratio_confidence_interval']
        assert 0 < low <= report['median_ratio'] <= high
        # Current-release performance is measured, not inherited from a historical
        # candidate on another machine. Keep requires the unchanged explicit gates.
        expected_keep = report['objective_met'] and not score['regressed']
        assert score['latency_method'] == 'paired_batched_benchmark'
        assert score['latency_ratio'] == report['median_ratio']
        assert score['above_noise'] is report['objective_met']
        assert row['kept'] is expected_keep
        assert row['outcome'] == ('kept' if expected_keep else 'not_kept')
        assert row['benchmark_decision']['status'] == 'ran'
        assert row['benchmark_decision']['beats_best'] is report['objective_met']
        # A/A baseline: parent against itself, ratio near 1, objective never met.
        baseline = loop['benchmark_baseline']
        assert baseline['candidate_sha256'] == baseline['parent_sha256'] == parent_sha
        assert baseline['correctness_passed'] is True and baseline['protected_jobs'] == jobs
        assert baseline['objective_met'] is False
        assert baseline['median_ratio'] > 0
        assert loop['benchmark_baseline_status'] == {**loop['benchmark_baseline_status'], 'kind': 'parent_a_a',
                                                     'status': 'measured', 'median_ratio': baseline['median_ratio']}
        # Root ledger: the A/A baseline then the iteration, every job a real
        # ``capsule-*`` start claim, all inside the grant's budget.
        assert completion['benchmarks'] == [
            {'iteration': 0, 'parent_sha256': parent_sha, 'candidate_sha256': parent_sha, 'protected_jobs': jobs,
             'objective_met': False, 'report_ref': baseline['report_ref']},
            {'iteration': 1, 'parent_sha256': parent_sha, 'candidate_sha256': child_sha,
             'protected_jobs': jobs, 'objective_met': report['objective_met'], 'report_ref': report['report_ref']}]
        assert [(e['role'], e['iteration']) for e in completion['evaluations']] == [('parent', 0), ('candidate', 1)]
        evaluated = sum(e['executions'] for e in completion['evaluations'])
        claims = list((tmp_path / 'evaluator' / 'claims').glob('capsule-*.json'))
        assert completion['executions'] == evaluated + 2 * jobs == len(claims) <= value['session']['grant']['max_executions']
        assert value['session']['grant']['max_executions'] == executor.loop_budget_for(name, value['session']['loop'])
        assert loop['benchmark_accounting']['calls'] == 2 and loop['benchmark_accounting']['available'] is True
        assert loop['benchmark_accounting']['protected_jobs'] == 2 * jobs
        assert (loop['best'] is not None) is expected_keep
        assert result['selection']['body_ref'] == (row['candidate_ref'] if expected_keep else value['session']['parent_body_ref'])
        feedback = store.get(row['next_feedback_ref'])['text']
        first = report['workloads'][0]
        assert ('objective_met ' + ('yes' if report['objective_met'] else 'no')) in feedback and '%s %.3f' % (first['id'], first['median_ratio']) in feedback
        assert 'Single-job protected walls of parent' in backend.prompts[0][2]
        assert 'Paired benchmark self-noise (parent A/A)' in backend.prompts[0][2]
    finally:
        store.close()
