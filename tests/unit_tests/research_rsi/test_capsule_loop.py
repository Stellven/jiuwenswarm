"""The real improvement loop driven by scripted FakeBackend responses (no models, no network)."""
import asyncio
import hashlib
import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.research_rsi import capsule_loop, capsule_session as session
from jiuwenswarm.research_rsi.model_backends import (AnthropicBackend, FakeBackend, OpenAICompatibleBackend,
    backend_from_configuration, validate_backend_configuration)
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.targets import capsule_objective
from jiuwenswarm.research_rsi.targets.capsules import public_fixtures, registered_capsule

PARENT = b'# original public carrier\n'
HELD_OUT = [{'id': 'held-a'}, {'id': 'held-b'}]
SECRET = 'HELDOUT-EXPECTED-SECRET'


class StubObjective:
    """Minimal Interface B stand-in used only by tests until W3's objective lands."""

    def fixtures(self, name, *, fixture_set):
        return public_fixtures(name) if fixture_set == 'public' else list(HELD_OUT) if fixture_set == 'held_out' else []

    def evaluation_fixtures(self, name):
        return ([dict(row, fixture_set='public') for row in public_fixtures(name)]
                + [dict(row, fixture_set='held_out') for row in HELD_OUT])

    def calibrate_noise(self, parent_trials):
        walls = [row['protected_wall_s'] for row in parent_trials]
        mean = sum(walls) / len(walls)
        return {'trials': len(walls), 'mean_wall_s': mean, 'noise_floor_ratio': (max(walls) - min(walls)) / mean}

    def score(self, parent, candidate, *, noise=None):
        p = parent['passed_count'] / parent['case_count']
        c = candidate['passed_count'] / candidate['case_count']
        both = p == c == 1
        ratio = candidate['protected_wall_s'] / parent['protected_wall_s'] if both else None
        floor = noise['noise_floor_ratio'] if noise else None
        above = ratio is not None and floor is not None and abs(1 - ratio) > floor
        improved = c >= p and (c > p or (above and ratio < 1))
        regressed = c < p or (above and ratio > 1)
        failing = [row['fixture_id'] for row in candidate['rows'] if not row['task_success']]
        return {'correctness': {'parent': p, 'candidate': c}, 'latency_ratio': ratio, 'noise_floor_ratio': floor,
                'above_noise': above, 'improved': improved, 'regressed': regressed,
                'summary': 'correctness %.2f->%.2f latency_ratio %s' % (p, c, ratio),
                'feedback': 'objective failing ids: ' + (', '.join(failing) or 'none')}


def spec(fail=(), wall=0.1, tag='', out=None):
    item = {'fail': list(fail), 'wall': wall, 'tag': tag}
    if out:
        item['out'] = out
    return ('# spec ' + json.dumps(item) + '\n').encode()


def parse(body):
    if body.startswith(b'# spec '):
        return json.loads(body.splitlines()[0][7:])
    return {'fail': [], 'wall': 0.1}


def make_session(tmp_path, name='utility.calculate', *, loop=None, max_executions=None, extra_contracts=0, parent=PARENT):
    store = RecordStore(tmp_path / 'records')
    target = registered_capsule(name)
    parent_ref = store.put_bytes(parent)
    ref = lambda text: store.put({'test': text})
    # Iterative sessions are backed by the iterative (v3) grant; v1 sessions keep v2.
    grant = {'schema': session.LOOP_GRANT_SCHEMA if loop is not None else session.GRANT_SCHEMA,
             'bootstrap_schema': session.BOOTSTRAP_SCHEMA, 'run_id': 'loop-capsule',
             'capsule_name': name, 'roles': ['parent', 'candidate'], 'parent_sha256': parent_ref['sha256'],
             'runtime_manifest_sha256': 'a' * 64}
    if max_executions is not None:
        grant['max_executions'] = max_executions
    elif loop is not None:
        grant['max_executions'] = 10000
    value = {'schema': session.SCHEMA, 'id': grant['run_id'], 'capsule_name': name,
        'grant': grant, 'grant_ref': store.put(grant), 'parent_body_ref': parent_ref,
        'parent_declaration_ref': store.put({'identity': {'name': name, 'version_label': '1.0.0',
            'carrier': {'ref': target.carrier_path.removeprefix('research/'), 'sha256': parent_ref['sha256']},
            'body': [{'path': target.carrier_path.removeprefix('research/'), 'sha256': parent_ref['sha256']}]},
            'evolution': {'rsi': 'none', 'may_change': []}}),
        'visible_context_ref': ref('visible'), 'preparation_ref': ref('preparation'),
        'configuration_ref': ref('configuration'), 'diagnosis_contract_ref': ref('diagnosis'),
        'proposal_contract_ref': ref('proposal'), 'native_scope_ref': ref('scope'),
        'authorized_component': target.carrier_path, 'observed_symptom': 'Public clock observations'}
    if loop is not None:
        loop = dict(loop)
        if extra_contracts:
            loop['contracts'] = [{'diagnosis_contract_ref': ref('diagnosis-%d' % i),
                                  'proposal_contract_ref': ref('proposal-%d' % i)} for i in range(2, 2 + extra_contracts)]
        value['loop'] = loop
    evaluations = []
    jitter = [0.0, 0.01, -0.01]

    async def evaluate(role, *, body, candidate_ref, binding, iteration, trials):
        assert hashlib.sha256(body).hexdigest() == candidate_ref['sha256']
        assert (binding is None) == (role == 'parent')
        evaluations.append({'role': role, 'iteration': iteration, 'trials': trials, 'body': body})
        behaviour = parse(body)
        rows = []
        for fixture_set, fixtures in (('public', public_fixtures(name)), ('held_out', HELD_OUT)):
            for row in fixtures:
                ok = row['id'] not in behaviour['fail']
                # Exact output bytes per case: identical unless the spec changes them.
                stdout = (row['id'] + ':' + behaviour.get('out', {}).get(row['id'], '')).encode()
                item = {'fixture_id': row['id'], 'fixture_set': fixture_set, 'task_success': ok,
                        'protected_wall_s': behaviour['wall'], 'output_bytes': 10,
                        'checks': {'expected': SECRET} if fixture_set == 'held_out' else {'diff': 'want 4 got 5'} if not ok else {},
                        'receipt': {'subject_ref': candidate_ref, 'stdout_ref': store.put_bytes(stdout)},
                        'candidate_ref': candidate_ref}
                rows.append({**item, 'evidence_ref': store.put(item)})
        total = sum(row['protected_wall_s'] for row in rows)
        result = {'schema': capsule_loop.VISIBLE_V2, 'role': role, 'iteration': iteration,
                  'subject_sha256': candidate_ref['sha256'], 'passed_count': sum(r['task_success'] for r in rows),
                  'case_count': len(rows), 'protected_wall_s': total,
                  'trial_wall_s': [total * (1 + jitter[i % 3]) for i in range(trials)] if trials > 1 else [],
                  'rows': rows, 'executions': len(rows) * trials, 'failure': None,
                  'grant_ref': value['grant_ref'], 'security': 'UNQUALIFIED', 'model_calls': 0}
        return {**result, 'result_ref': store.put(result)}

    async def before_model():
        pass
    runtime = SimpleNamespace(store=store, evaluate=evaluate, before_model=before_model, objective=StubObjective())
    return store, value, runtime, evaluations


def diagnosis_text(prompt):
    value = json.loads(prompt)
    return json.dumps({'schema': 'ai4r-rsi-diagnosis:1', 'observed_symptom': 'scripted',
        'supporting_visible_evidence': [value['visible_evidence'][0]['ref']], 'suspected_mechanism': 'scripted',
        'alternative_causes': ['noise'], 'authorized_component': value['authorized_component'],
        'proposed_change_direction': 'scripted', 'expected_effect': 'hypothesis', 'visible_falsification_checks': ['run'],
        'uncertainties': []})


def proposal_text(body, rationale):
    def respond(prompt):
        path = json.loads(prompt)['visible_context']['authorized_mutable_path']
        return json.dumps({'path': path, 'body': body.decode(), 'rationale': rationale})
    return respond


def script(*bodies):
    items = []
    for index, body in enumerate(bodies, start=1):
        items += [diagnosis_text, body if not isinstance(body, bytes) else proposal_text(body, 'rationale %d' % index)]
    return items


LOOP = {'model_backend': {'kind': 'fake'}, 'max_iterations': 4, 'max_no_progress': 3, 'trials': 3}


def run(value, runtime, backend):
    return asyncio.run(session.execute(value, runtime, models=backend))


def test_loop_keeps_best_feeds_back_failures_and_timings(tmp_path):
    store, value, runtime, evaluations = make_session(tmp_path, loop=LOOP)
    case = public_fixtures('utility.calculate')[0]['id']
    try:
        backend = FakeBackend(script(spec(fail=[case], tag='broken'), spec(tag='fixed'),
                                     spec(wall=0.05, tag='faster'), spec(fail=['held-a'], wall=0.04, tag='regressed')))
        result = run(value, runtime, backend)
        loop = result['loop']
        assert result['status'] == 'VISIBLE_EVALUATED_UNQUALIFIED', result
        assert loop['schema'] == 'ai4r-rsi-capsule-loop:1' and loop['stop_reason'] == 'max_iterations'
        assert loop['completed_iterations'] == 4
        assert [row['kept'] for row in loop['iterations']] == [False, False, True, False]
        assert [row['outcome'] for row in loop['iterations']] == ['not_kept', 'not_kept', 'kept', 'not_kept']
        assert loop['iterations'][0]['score']['regressed'] and loop['iterations'][3]['selection']['score']['regressed']
        assert loop['best']['iteration'] == 3
        assert result['selection']['role'] == 'candidate'
        assert result['selection']['iteration'] == 3
        assert result['selection']['body_ref'] == loop['best']['candidate_ref']
        assert store.get(result['selection_ref']) == result['selection']
        # top-level publication fields point at the best kept candidate
        assert result['candidate_ref'] == loop['best']['candidate_ref'] == loop['iterations'][2]['candidate_ref']
        assert store.read(result['candidate_ref']) == spec(wall=0.05, tag='faster')
        assert result['candidate_visible']['result_ref'] == loop['iterations'][2]['visible']['result_ref']
        assert store.get(result['candidate_visible']['result_ref']) == {
            k: v for k, v in result['candidate_visible'].items() if k != 'result_ref'}
        # lineage rows: refs are {id, sha256}; held-out rows are ids/pass/fail/timing only
        for row in loop['iterations']:
            assert set(row['candidate_ref']) == {'id', 'sha256'} and 'candidate_sha256' not in row
            assert set(row['diagnosis_ref']) == set(row['proposal_ref']) == {'id', 'sha256'}
            assert set(row) >= {'model_calls', 'elapsed_s', 'failure'} and row['failure'] is None
            assert all(set(r) <= {'fixture_id', 'fixture_set', 'task_success', 'protected_wall_s', 'evidence_ref'}
                       for r in row['visible']['rows'] if r['fixture_set'] == 'held_out')
        assert SECRET not in json.dumps(loop)
        assert loop['iterations'][3]['held_out_failing_ids'] == ['held-a']
        assert loop['model_calls'] == 8
        assert result['rationale'] == 'rationale 3' and result['selected_iteration'] == 3
        # parent once with >=3 trials, then one evaluation per iteration
        assert [(e['role'], e['iteration'], e['trials']) for e in evaluations] == [
            ('parent', 0, 3), ('candidate', 1, 3), ('candidate', 2, 3), ('candidate', 3, 3), ('candidate', 4, 3)]
        assert loop['noise']['trials'] == 3 and loop['noise']['method'] == 'capsule_objective.calibrate_noise'
        assert len(loop['noise']['parent_wall_s_trials']) == 3 and loop['noise']['floor_ratio'] > 0
        assert loop['noise']['objective']['noise_floor_ratio'] == loop['noise']['floor_ratio']
        # call-count invariant: one diagnosis + one proposal per iteration
        assert result['model_calls'] == 8 == sum(row['model_calls'] for row in loop['iterations'])
        assert all(row['model_calls'] == 2 for row in loop['iterations'])
        assert [(i, role) for i, role, _ in backend.prompts] == [(i, r) for i in range(1, 5) for r in ('diagnosis', 'proposal')]
        # feedback after iteration 1 names the failing case; after 3 the timing deltas
        prompts = {(i, role): prompt for i, role, prompt in backend.prompts}
        assert case in prompts[(2, 'diagnosis')] and case in prompts[(2, 'proposal')]
        feedback = store.get(loop['iterations'][3]['feedback_ref'])
        assert 'Timing deltas vs parent' in feedback['text'] and 'delta -0.05' in feedback['text']
        assert feedback['incumbent']['label'] == 'iteration 3'
        assert any(row['delta_s'] < 0 for row in feedback['last']['timings'])
        # iteration 4 proposes against the kept incumbent, not the parent
        assert json.loads(prompts[(4, 'proposal')])['visible_context']['incumbent']['body'] == spec(wall=0.05, tag='faster').decode()
        # held-out cases: ids and pass/fail only, never their checks
        assert all(SECRET not in prompt for _, _, prompt in backend.prompts)
        last = store.get(loop['iterations'][3]['next_feedback_ref'])
        assert 'held-a (held_out)' in last['text'] and SECRET not in last['text']
        # every iteration's evidence is retained exactly
        for row in loop['iterations']:
            assert store.read(row['candidate_ref']) and store.read(row['proposal_response_ref'])
            assert store.get(row['diagnosis_capture_ref'])['status'] == 'validated'
            assert store.get(row['score_ref']) == row['score']
        assert len(loop['iteration_record_refs']) == 4
        assert loop['model_backend']['kind'] == 'fake' and len(loop['model_backend']['pinned_sha256']) == 64
        assert store.get(result['loop_ref']) == loop
    finally:
        store.close()


def test_no_progress_stop_and_duplicates_are_not_reevaluated(tmp_path):
    store, value, runtime, evaluations = make_session(tmp_path, loop={**LOOP, 'max_iterations': 5, 'max_no_progress': 2})
    try:
        backend = FakeBackend(script(spec(tag='same-speed'), spec(tag='same-speed')))
        result = run(value, runtime, backend)
        loop = result['loop']
        assert loop['stop_reason'] == 'no_progress' and loop['completed_iterations'] == 2
        assert [row['outcome'] for row in loop['iterations']] == ['not_kept', 'duplicate']
        assert [e['role'] for e in evaluations] == ['parent', 'candidate']
        assert loop['best'] is None and result['candidate_ref'] == loop['iterations'][0]['candidate_ref']
        assert result['selection'] == {'schema': 'ai4r-rsi-capsule-selection:1',
            'role': 'parent', 'body_ref': value['parent_body_ref'], 'iteration': 0, 'reason': 'no_child_improved'}
        assert store.get(result['selection_ref']) == result['selection']
        assert store.read(result['selection']['body_ref']) == PARENT
        assert result['status'] == 'VISIBLE_EVALUATED_UNQUALIFIED' and result['model_calls'] == 4
    finally:
        store.close()


def test_model_call_and_execution_budgets_stop_before_effects(tmp_path):
    store, value, runtime, evaluations = make_session(tmp_path, loop={**LOOP, 'max_model_calls': 4})
    try:
        result = run(value, runtime, FakeBackend(script(spec(wall=0.09), spec(wall=0.08))))
        assert result['loop']['stop_reason'] == 'budget' and result['loop']['completed_iterations'] == 2
        assert result['model_calls'] == 4
    finally:
        store.close()
    cases = len(public_fixtures('utility.calculate')) + len(HELD_OUT)
    store, value, runtime, evaluations = make_session(tmp_path / 'b', loop=LOOP, max_executions=cases * 7)
    try:
        backend = FakeBackend(script(spec(wall=0.05), spec(wall=0.04), spec(wall=0.03)))
        result = run(value, runtime, backend)
        loop = result['loop']
        assert loop['trials'] == {'requested': 3, 'parent': 3, 'candidate': 3, 'estimated_cases': cases}
        assert loop['stop_reason'] == 'budget' and loop['completed_iterations'] == 1
        assert len(backend.prompts) == 2
    finally:
        store.close()


def test_small_execution_budget_degrades_trials_and_records_limitation(tmp_path):
    cases = len(public_fixtures('utility.calculate')) + len(HELD_OUT)
    store, value, runtime, evaluations = make_session(tmp_path, loop=LOOP, max_executions=cases * 2)
    try:
        result = run(value, runtime, FakeBackend(script(spec(wall=0.05))))
        assert [(e['role'], e['trials']) for e in evaluations] == [('parent', 1), ('candidate', 1)]
        assert result['loop']['noise'] is None and result['loop']['stop_reason'] == 'budget'
        assert any('noise not calibrated' in item for item in result['limitations'])
    finally:
        store.close()


def test_deadline_stop_uses_observed_iteration_duration(tmp_path):
    store, value, runtime, evaluations = make_session(tmp_path, loop={**LOOP, 'wall_s': 60, 'per_call_s': 10})
    ticks = iter(range(0, 10000, 7))
    runtime.clock = lambda: next(ticks)
    try:
        result = run(value, runtime, FakeBackend(script(*[spec(wall=0.1 - i / 100) for i in range(1, 5)])))
        assert result['loop']['stop_reason'] == 'deadline'
        assert 0 < result['loop']['completed_iterations'] < 4
    finally:
        store.close()


def test_malformed_response_rejects_iteration_unknown_effect_stops_loop(tmp_path):
    store, value, runtime, evaluations = make_session(tmp_path, loop=LOOP)
    try:
        malformed = 'not json at all'
        backend = FakeBackend([diagnosis_text, malformed, *script(spec(wall=0.05)),
                               diagnosis_text, TimeoutError('transport lost')])
        result = run(value, runtime, backend)
        loop = result['loop']
        assert [row['outcome'] for row in loop['iterations']] == ['rejected', 'kept', 'error']
        assert loop['iterations'][2]['failure'] == {'exception_type': 'TimeoutError', 'message': 'transport lost'}
        assert store.read(loop['iterations'][0]['proposal_response_ref']).decode() == malformed
        assert loop['iterations'][0]['visible'] is None
        assert loop['stop_reason'] == 'error' and result['exception_type'] == 'TimeoutError'
        assert result['status'] == 'VISIBLE_EVALUATED_UNQUALIFIED' and result['loop']['best']['iteration'] == 2
        assert result['model_calls'] == 6 and len(backend.prompts) == 6
        assert store.get(result['failure_ref'])['stop_reason'] == 'error'
        # iteration 2 was told why iteration 1 was rejected
        assert 'PROPOSAL_REJECTED' in json.loads(backend.prompts[2][2])['observed_symptom']
    finally:
        store.close()


def test_failed_parent_control_makes_no_model_call(tmp_path):
    store, value, runtime, evaluations = make_session(tmp_path, loop=LOOP)
    original = runtime.evaluate

    async def broken(role, **kwargs):
        result = await original(role, **kwargs)
        rows = [dict(result['rows'][0], task_success=False)] + result['rows'][1:]
        changed = {**{k: v for k, v in result.items() if k != 'result_ref'}, 'rows': rows,
                   'passed_count': result['passed_count'] - 1}
        return {**changed, 'result_ref': store.put(changed)}
    runtime.evaluate = broken
    try:
        backend = FakeBackend([])
        result = run(value, runtime, backend)
        assert result['status'] == 'ERROR_NO_REPLAY' and result['model_calls'] == 0
        assert result['loop']['stop_reason'] == 'error' and backend.prompts == []
        assert 'PARENT_CONTROL_FAILED_NO_MODEL_CALL' in store.get(result['failure_ref'])['message']
    finally:
        store.close()


def test_configuration_requires_explicit_matching_backend(tmp_path):
    store, value, runtime, _ = make_session(tmp_path, loop={'max_iterations': 2})
    try:
        with pytest.raises(ValueError, match='EXPLICIT_MODEL_BACKEND_REQUIRED'):
            session.validate_session(value)
        value['loop'] = {'model_backend': {'kind': 'host-codex'}, 'max_iterations': 0}
        with pytest.raises(ValueError, match='FINITE_LOOP_MAX_ITERATIONS_REQUIRED'):
            session.validate_session(value)
        value['loop'] = {'model_backend': {'kind': 'host-codex'}}
        with pytest.raises(ValueError, match='MODEL_BACKEND_DIFFERS_FROM_CONFIGURATION'):
            run(value, runtime, FakeBackend([]))
        value['loop'] = {'model_backend': {'kind': 'fake'}}
        with pytest.raises(ValueError, match='FAKE_BACKEND_REQUIRES_EXPLICIT_SCRIPT'):
            asyncio.run(session.execute(value, runtime))
        config = capsule_loop.loop_configuration(value)
        assert {k: config[k] for k in ('max_iterations', 'max_no_progress', 'trials')} == {
            'max_iterations': 5, 'max_no_progress': 3, 'trials': 3}
        # nothing was claimed by refused configurations
        assert store.db.execute("SELECT name FROM sqlite_master WHERE name='capsule_session_claims'").fetchone() is None
    finally:
        store.close()


def test_host_codex_backend_uses_one_prepared_contract_pair_per_iteration(tmp_path):
    loop = {'model_backend': {'kind': 'host-codex'}, 'max_iterations': 4, 'max_no_progress': 4, 'trials': 3}
    store, value, runtime, _ = make_session(tmp_path, loop=loop, extra_contracts=1)
    bodies = iter([spec(wall=0.05), spec(wall=0.04)])
    issued = []

    class Handle:
        def __init__(self, contract_ref):
            self.contract_ref, self.used = contract_ref, False
            self.last_model_calls, self.last_evidence, self.last_generating_model = None, [], 'host'

        async def __call__(self, prompt):
            assert not self.used
            self.used, self.last_model_calls = True, 1
            self.last_evidence = [store.put({'call': self.contract_ref})]
            if 'visible_evidence' in json.loads(prompt):
                return diagnosis_text(prompt)
            return proposal_text(next(bodies), 'host')(prompt)

    def factory(resources, lease, contract_ref, run_id):
        issued.append(contract_ref)
        return Handle(contract_ref)
    runtime.development_model_factory = factory
    runtime.resources = runtime.lease = None
    try:
        result = asyncio.run(session.execute(value, runtime))
        assert result['loop']['stop_reason'] == 'budget' and result['loop']['completed_iterations'] == 2
        assert issued == [value['diagnosis_contract_ref'], value['proposal_contract_ref'],
                          value['loop']['contracts'][0]['diagnosis_contract_ref'],
                          value['loop']['contracts'][0]['proposal_contract_ref']]
        assert result['loop']['model_backend']['kind'] == 'host-codex'
        assert capsule_loop.loop_run_context_ids(value) == {
            'rsi-development:loop-capsule:diagnosis', 'rsi-development:loop-capsule:proposal',
            'rsi-development:loop-capsule:diagnosis:2', 'rsi-development:loop-capsule:proposal:2'}
    finally:
        store.close()


def test_backend_configuration_is_closed_and_never_defaulted():
    with pytest.raises(ValueError, match='EXPLICIT_MODEL_BACKEND_REQUIRED'):
        validate_backend_configuration({})
    with pytest.raises(ValueError, match='CLOSED_MODEL_BACKEND_CONFIGURATION_REQUIRED'):
        validate_backend_configuration({'kind': 'anthropic', 'model': 'm'})
    with pytest.raises(ValueError, match='EXACT_BACKEND_BASE_URL_REQUIRED'):
        validate_backend_configuration({'kind': 'openai-compatible', 'base_url': 'file:///x', 'model': 'm', 'api_key_env': 'K'})
    assert backend_from_configuration({'kind': 'anthropic', 'model': 'claude-x', 'api_key_env': 'K'}).kind == 'anthropic'


@pytest.mark.parametrize('kind', ['openai-compatible', 'anthropic'])
def test_http_backends_capture_evidence_without_network(tmp_path, monkeypatch, kind):
    store = RecordStore(tmp_path / 'records')
    sent = []
    if kind == 'anthropic':
        reply = {'model': 'claude-effective', 'content': [{'type': 'text', 'text': 'hello'}],
                 'usage': {'input_tokens': 3, 'output_tokens': 1}}
    else:
        reply = {'model': 'oa-effective', 'choices': [{'message': {'content': 'hello'}}],
                 'usage': {'prompt_tokens': 3, 'completion_tokens': 1}}

    def transport(url, headers, body, timeout):
        sent.append((url, headers, json.loads(body)))
        return 200, json.dumps(reply).encode()
    backend = (AnthropicBackend('claude-x', 'TEST_MODEL_KEY', transport=transport) if kind == 'anthropic' else
               OpenAICompatibleBackend('http://127.0.0.1:9/v1', 'oa-x', 'TEST_MODEL_KEY', transport=transport))
    backend.bind(runtime=SimpleNamespace(store=store), session={})
    try:
        monkeypatch.delenv('TEST_MODEL_KEY', raising=False)
        first, second = backend.handles(1)
        with pytest.raises(ValueError, match='KEY_UNAVAILABLE_NO_CALL'):
            asyncio.run(first('prompt'))
        assert first.last_model_calls == 0 and sent == []
        monkeypatch.setenv('TEST_MODEL_KEY', 'secret-key')
        assert asyncio.run(second('prompt')) == 'hello'
        assert second.last_model_calls == 1 and second.last_generating_model == reply['model']
        url, headers, body = sent[0]
        assert url.endswith('/v1/messages' if kind == 'anthropic' else '/chat/completions')
        assert body['messages'] == [{'role': 'user', 'content': 'prompt'}]
        start, call = (store.get(ref) for ref in second.last_evidence)
        assert start['kind'] == kind and 'secret-key' not in json.dumps(start)
        assert call['outcome'] == 'completed' and store.read(call['response_ref']) == json.dumps(reply).encode()
        with pytest.raises(ValueError, match='ALREADY_USED'):
            asyncio.run(second('again'))
        third, _ = backend.handles(2)
        backend.transport = lambda *a: (500, b'{"error":"x"}')
        with pytest.raises(ValueError, match='HTTP_STATUS_500'):
            asyncio.run(third('prompt'))
        assert third.last_model_calls == 1 and store.get(third.last_evidence[-1])['outcome'] == 'failed'
    finally:
        store.close()


# ------------------------------------------------- Interface E (benchmark) policy

BENCH_LOOP = {**LOOP, 'max_no_progress': 5}
DEPENDENCY_EXCERPT = 'def output_packet(packet, **changes):  # validates and deep-copies the envelope again'


class BenchObjective(StubObjective):
    """Stub inventory, but the real Interface B rule: correctness contract and
    benchmark-judged latency come from ``capsule_objective.score`` itself."""

    def calibrate_noise(self, parent_trials):
        return capsule_objective.calibrate_noise(parent_trials)

    def score(self, parent, candidate, *, noise=None, benchmark=None):
        return capsule_objective.score(parent, candidate, noise=noise, benchmark=benchmark)


AA = (1.0, (0.98, 1.02), None)   # the parent A/A baseline (iteration 0)
UNMEASURED = 'unmeasured'         # the benchmark's own correctness gate failed


def bench_report(parent, candidate, *, ratio, ci, workloads=None, jobs=40):
    """W-M1's report shape (Interface E, Codex's paired batched protocol):
    gates ``{name: {threshold, passed}}`` from gain >= 10%, CI upper <= 0.90,
    no workload > 5% slower; ``withheld`` workloads; None ratios when the
    benchmark's parent-relative correctness fails (``ratio is None``)."""
    workloads = workloads or {'w-small': ratio, 'w-large': ratio}
    measured = ratio is not None
    rows = [{'id': ident, 'split': 'evaluation' if ident.startswith('withheld') else 'visible',
             'withheld': ident.startswith('withheld'), 'median_ratio': value,
             'relative_gain': None if value is None else 1 - value, 'regression': measured and value > 1}
            for ident, value in workloads.items()]
    gates = {'minimum_gain': {'threshold': 0.10, 'passed': measured and 1 - ratio >= 0.10},
             'ci_upper_bound': {'threshold': 0.90, 'passed': measured and ci[1] <= 0.90},
             'max_workload_regression': {'threshold': 0.05, 'passed': measured and max(workloads.values()) <= 1.05}}
    return {'schema': capsule_objective.BENCHMARK_REPORT_SCHEMA, 'scope': 'local_unprotected',
            'parent_sha256': hashlib.sha256(parent).hexdigest(), 'candidate_sha256': hashlib.sha256(candidate).hexdigest(),
            'median_ratio': ratio, 'relative_gain': None if not measured else 1 - ratio,
            'ratio_confidence_interval': list(ci) if measured else None, 'repetitions': 11,
            'gates': gates, 'objective_met': all(gate['passed'] for gate in gates.values()), 'correctness_passed': measured,
            'correctness': {'passed': measured, 'cases': [{'id': 'c1', 'improved': False}],
                            'failure': None if measured else {'kind': 'semantic_edge', 'fixture_id': 'withheld-edge-3',
                                                              'role': 'candidate', 'rule': 'parent_bytes_exact'}},
            'workloads': rows, 'samples': {ident: [[0.002, 0.002 * value]] * 3 for ident, value in workloads.items()}
            if measured else {}, 'protected_jobs': jobs, 'evidence_refs': []}


class FakeBenchmark:
    """Scripted ``runtime.benchmark`` (Interface E): one (ratio, ci, workloads) per call."""

    def __init__(self, reports, jobs=40):
        self.reports, self.jobs, self.calls = list(reports), jobs, []

    async def __call__(self, parent_body, candidate_body, *, iteration):
        self.calls.append((iteration, hashlib.sha256(parent_body).hexdigest(), hashlib.sha256(candidate_body).hexdigest()))
        item = self.reports.pop(0)
        if isinstance(item, BaseException):
            raise item
        if item == UNMEASURED:
            return bench_report(parent_body, candidate_body, ratio=None, ci=None,
                                workloads={'w-small': None, 'w-large': None}, jobs=self.jobs)
        ratio, ci, workloads = item
        return bench_report(parent_body, candidate_body, ratio=ratio, ci=ci, workloads=workloads, jobs=self.jobs)


def bench_session(tmp_path, monkeypatch, reports, *, loop=BENCH_LOOP, parent=PARENT, max_executions=None, jobs=40,
                  context_bytes=None):
    store, value, runtime, evaluations = make_session(tmp_path, loop=loop, parent=parent, max_executions=max_executions)
    runtime.objective = BenchObjective()
    runtime.benchmark = FakeBenchmark(reports, jobs=jobs)

    def compile_context(name, body, *, max_total_bytes):
        # Stand-in for W-M1's targets.capsule_context.dependency_context.
        assert name == 'utility.calculate' and isinstance(body, bytes)
        assert max_total_bytes == capsule_loop.DEFAULTS['context_bytes']
        text = DEPENDENCY_EXCERPT + '\n' if context_bytes is None else 'x' * (max_total_bytes + 1)
        return {'schema': 'ai4r-rsi-capsule-dependency-context:1', 'capsule_name': name, 'truncated': False,
                'omitted': [], 'context_sha256': 'c' * 64,
                'sources': [{'module': 'jiuwenswarm.research.capsule_extensions.packet',
                             'path': 'jiuwenswarm/research/capsule_extensions/packet.py', 'selection': 'whole_file',
                             'first_line': 1, 'last_line': 1, 'text': text, 'source_sha256': 'a' * 64,
                             'excerpt_sha256': 'b' * 64, 'truncated': False, 'mutable': False}]}

    def render(context):
        return '\n\n'.join('# read-only dependency: %s\n%s' % (row['path'], row['text']) for row in context['sources'])
    monkeypatch.setattr(capsule_loop, 'load_dependency_context', lambda: (compile_context, render))
    return store, value, runtime, evaluations


def test_benchmark_gates_decide_latency_keeps_and_feedback_names_failed_gates(tmp_path, monkeypatch):
    parent_sha = hashlib.sha256(PARENT).hexdigest()
    bodies = [spec(tag='one'), spec(tag='two'), spec(tag='three'), spec(tag='four'), spec(tag='five')]
    shas = [hashlib.sha256(body).hexdigest() for body in bodies]
    reports = [(0.83, (0.82, 0.84), {'w-small': 0.81, 'w-large': 0.85, 'withheld-w9': 0.84}),  # 1: gates pass
               (0.88, (0.80, 0.95), {'w-small': 0.87, 'w-large': 0.89}),                       # 2: CI gate fails
               (0.85, (0.83, 0.87), {'w-small': 0.70, 'w-large': 1.08}),                       # 3: workload regression
               (0.84, (0.83, 0.85), None),                                 # 4: met, but not faster than best
               (0.76, (0.74, 0.78), None)]                                 # 5: met and beats best (0.78 < 0.83)
    store, value, runtime, evaluations = bench_session(tmp_path, monkeypatch, [AA] + reports,
                                                       loop={**BENCH_LOOP, 'max_iterations': 5})
    try:
        backend = FakeBackend(script(*bodies))
        result = run(value, runtime, backend)
        loop = result['loop']
        rows = loop['iterations']
        assert loop['stop_reason'] == 'max_iterations' and loop['completed_iterations'] == 5
        assert [row['kept'] for row in rows] == [True, False, False, False, True]
        # Interface E calls: the parent A/A baseline (iteration 0) first, then parent vs candidate per iteration.
        assert runtime.benchmark.calls == [(0, parent_sha, parent_sha)] + [(i + 1, parent_sha, shas[i]) for i in range(5)]
        for row, (ratio, ci, _) in zip(rows, reports):
            # The row carries the exact Interface E report (what W-M3 projects and publishes).
            assert row['benchmark']['schema'] == capsule_objective.BENCHMARK_REPORT_SCHEMA
            assert row['benchmark']['parent_sha256'] == parent_sha
            assert row['benchmark']['candidate_sha256'] == row['candidate_ref']['sha256']
            assert row['benchmark']['median_ratio'] == ratio and row['benchmark']['protected_jobs'] == 40
            score = row['score']
            assert score['latency_method'] == 'paired_batched_benchmark' and score['latency_ratio'] == ratio
            assert score['above_noise'] is row['benchmark']['objective_met']
            assert not score['regressed'] and score['contract']['changed_bytes'] == []
            decision = row['benchmark_decision']
            assert decision['status'] == 'ran' and decision['against'] == 'parent'
            assert store.get(decision['record_ref']) == row['benchmark']
        assert rows[0]['score']['improved'] is True
        assert rows[0]['score']['correctness']['candidate'] == rows[0]['score']['correctness']['parent']
        assert rows[1]['benchmark_decision']['failed_gates'] == ['ci_upper_bound']
        assert rows[2]['benchmark_decision']['failed_gates'] == ['max_workload_regression']
        # Later iterations compare against the current best as well as the parent.
        assert rows[0]['benchmark_decision']['vs_best'] is None
        fourth = rows[3]['benchmark_decision']
        assert fourth['objective_met'] is True and fourth['beats_best'] is False
        assert fourth['vs_best']['best_median_ratio'] == 0.83 and abs(fourth['vs_best']['ratio_vs_best'] - 0.84 / 0.83) < 1e-12
        assert rows[3]['score']['improved'] is True and rows[3]['kept'] is False  # better than parent, not than best
        assert 'does not beat the current best' in rows[3]['reason']
        assert rows[4]['benchmark_decision']['beats_best'] is True
        assert rows[4]['selection']['against'] == 'iteration 1'
        # The A/A baseline: the exact report, recorded once, before any model call.
        baseline = loop['benchmark_baseline']
        assert baseline['parent_sha256'] == baseline['candidate_sha256'] == parent_sha and baseline['median_ratio'] == 1.0
        status = loop['benchmark_baseline_status']
        assert status['status'] == 'measured' and status['kind'] == 'parent_a_a'
        assert store.get(status['record_ref']) == baseline
        assert loop['best']['iteration'] == 5 and result['selected_iteration'] == 5
        # Budget accounting: every benchmark job counted, baseline included.
        assert loop['benchmark_accounting'] == {'available': True, 'latency_method': 'paired_batched_benchmark',
                                                'calls': 6, 'protected_jobs': 240, 'jobs_per_call_estimate': 40}
        # Machine-generated feedback: CI, failed gate, per-workload ratios, timing deltas.
        second = store.get(rows[1]['next_feedback_ref'])
        assert 'Failed gates: ci_upper_bound.' in second['text'] and '95% CI [0.8000, 0.9500]' in second['text']
        assert 'w-small 0.870' in second['text']
        assert 'timing w-small: parent 2.000 ms -> candidate 1.740 ms' in second['text']
        assert second['last']['benchmark']['failed_gates'] == ['ci_upper_bound']
        third = store.get(rows[2]['next_feedback_ref'])
        assert 'gate max_workload_regression: FAIL' in third['text'] and 'w-large 1.080 (+8.0%, REGRESSION)' in third['text']
        assert 'does not beat the best' in store.get(rows[3]['next_feedback_ref'])['text']
        first = store.get(rows[0]['next_feedback_ref'])
        assert 'Withheld workloads: 1' in first['text']
        # Where time goes: parent profile before iteration 1, benchmark-derived after.
        prompts = {(i, role): prompt for i, role, prompt in backend.prompts}
        assert 'Single-job protected walls of parent' in prompts[(1, 'diagnosis')]
        assert 'Paired benchmark self-noise (parent A/A): ratio CI [0.9800, 1.0200].' in prompts[(1, 'diagnosis')]
        assert 'Amortized per-invocation medians' in prompts[(2, 'diagnosis')]
        assert 'withheld-w9' not in ''.join(prompts.values())
        # Machine-selected dependency excerpts (W-M1 compiler + renderer) reach diagnosis and proposal.
        assert DEPENDENCY_EXCERPT in prompts[(1, 'proposal')] and DEPENDENCY_EXCERPT in prompts[(1, 'diagnosis')]
        assert '# read-only dependency: jiuwenswarm/research/capsule_extensions/packet.py' in prompts[(1, 'proposal')]
        context = store.get(rows[0]['dependency_context_ref'])
        assert [row['path'] for row in context['sources']] == ['jiuwenswarm/research/capsule_extensions/packet.py']
        assert context['context_sha256'] == 'c' * 64 and 'unavailable' not in context
        assert all(store.get(row['time_profile_ref'])['schema'] == capsule_loop.TIME_PROFILE_SCHEMA for row in rows)
        assert SECRET not in json.dumps(loop) and all(SECRET not in prompt for prompt in prompts.values())
    finally:
        store.close()


def test_correctness_contract_both_branches_and_benchmark_only_after_correctness(tmp_path, monkeypatch):
    public = public_fixtures('utility.calculate')[0]['id']
    parent = spec(fail=['held-b'], tag='parent')   # passes the public baseline, fails one held-out case
    changed = spec(fail=['held-b'], out={public: 'reformatted'})
    fixed = spec(out={'held-b': 'now-correct'})
    edge_broken = spec(out={'held-b': 'now-correct'}, tag='edge-broken')
    store, value, runtime, evaluations = bench_session(
        tmp_path, monkeypatch, [AA, (1.01, (0.99, 1.03), None), UNMEASURED], parent=parent,
        loop={**BENCH_LOOP, 'max_iterations': 3})
    try:
        result = run(value, runtime, FakeBackend(script(changed, fixed, edge_broken)))
        first, second, third = result['loop']['iterations']
        # Parent passes, checker accepts, bytes differ -> regression; never benchmarked.
        assert first['visible']['passed_count'] == result['parent_visible']['passed_count']
        assert first['score']['regressed'] is True and first['score']['improved'] is False
        assert first['score']['contract']['changed_bytes'] == [public] and not first['score']['newly_failed']
        assert first['benchmark'] is None
        assert first['benchmark_decision'] == {'schema': capsule_loop.BENCHMARK_RECORD_SCHEMA, 'status': 'not_run',
                                               'reason': 'CORRECTNESS_REGRESSED'}
        assert first['kept'] is False
        feedback = store.get(first['next_feedback_ref'])
        assert 'CONTRACT REGRESSIONS' in feedback['text'] and feedback['last']['contract_changed_bytes'] == [public]
        assert 'Paired batched benchmark not run: CORRECTNESS_REGRESSED.' in feedback['text']
        # Parent fails the checker, candidate passes (new bytes there) -> improvement,
        # kept on the correctness gain although its benchmark gates fail.
        assert second['score']['newly_passed'] == ['held-b'] and second['score']['contract']['changed_bytes'] == []
        assert second['score']['contract']['checker_fixed'] == ['held-b']
        assert second['benchmark_decision']['status'] == 'ran' and second['benchmark']['objective_met'] is False
        assert second['score']['improved'] is True and second['kept'] is True
        assert second['score']['latency_method'] == 'paired_batched_benchmark'
        # The benchmark's own parent-relative correctness gate failing (no ratio
        # measured) is a regression, never a latency claim.
        assert third['benchmark']['correctness_passed'] is False and third['benchmark']['median_ratio'] is None
        assert third['score']['regressed'] is True and third['score']['latency_ratio'] is None
        assert third['score']['contract']['benchmark_correctness_passed'] is False
        assert third['benchmark_decision']['beats_best'] is False and third['kept'] is False
        stopped = store.get(third['next_feedback_ref'])['text']
        assert 'stopped on a correctness failure' in stopped and 'semantic_edge' in stopped
        assert 'withheld-edge-3' not in stopped
        # A/A first; the regressed iteration-1 candidate is never benchmarked.
        assert [call[0] for call in runtime.benchmark.calls] == [0, 2, 3]
        assert result['loop']['best']['iteration'] == 2
    finally:
        store.close()


def test_benchmark_jobs_count_against_the_execution_budget(tmp_path, monkeypatch):
    cases = len(public_fixtures('utility.calculate')) + len(HELD_OUT)
    passing = (0.8, (0.78, 0.82), None)
    # Room for the parent (3 trials), the A/A baseline, one candidate (3
    # trials) and its benchmark -- not for a second iteration.
    store, value, runtime, evaluations = bench_session(tmp_path, monkeypatch, [AA, passing, passing],
                                                       max_executions=cases * 6 + 100, jobs=50)
    runtime.benchmark_jobs = 50
    try:
        result = run(value, runtime, FakeBackend(script(spec(tag='a'), spec(tag='b'))))
        loop = result['loop']
        assert loop['stop_reason'] == 'budget' and loop['completed_iterations'] == 1
        assert loop['benchmark_accounting']['protected_jobs'] == 100 and loop['benchmark_accounting']['calls'] == 2
        assert loop['iterations'][0]['kept'] is True and [c[0] for c in runtime.benchmark.calls] == [0, 1]
        assert loop['benchmark_baseline_status']['status'] == 'measured'
    finally:
        store.close()
    # One job short of a candidate plus its benchmark after the A/A: no model call is made.
    store, value, runtime, evaluations = bench_session(tmp_path / 'b', monkeypatch, [AA],
                                                       max_executions=cases * 6 + 99, jobs=50)
    runtime.benchmark_jobs = 50
    try:
        backend = FakeBackend([])
        result = run(value, runtime, backend)
        assert result['loop']['stop_reason'] == 'budget' and result['loop']['completed_iterations'] == 0
        assert backend.prompts == [] and [c[0] for c in runtime.benchmark.calls] == [0]
    finally:
        store.close()
    # A refused A/A baseline is an unknown effect before any model call: the run stops.
    store, value, runtime, evaluations = bench_session(tmp_path / 'd', monkeypatch, [ValueError('ROOT_REFUSED')])
    try:
        backend = FakeBackend([])
        result = run(value, runtime, backend)
        assert result['loop']['stop_reason'] == 'error' and result['model_calls'] == 0 and backend.prompts == []
        assert 'ROOT_REFUSED' in result['loop']['stop_detail']
    finally:
        store.close()
    # A refused candidate benchmark is an unknown effect: the iteration errors and the loop stops.
    # (Its oversized dependency context is refused as unbounded: a recorded limitation, never a prompt.)
    store, value, runtime, evaluations = bench_session(tmp_path / 'c', monkeypatch, [AA, ValueError('ROOT_REFUSED')],
                                                       context_bytes='oversized')
    try:
        backend = FakeBackend(script(spec(tag='a')))
        result = run(value, runtime, backend)
        assert any('BOUNDED_DEPENDENCY_CONTEXT_REQUIRED' in item for item in result['limitations'])
        assert 'read-only dependency' not in backend.prompts[1][2]
        row = result['loop']['iterations'][0]
        assert row['outcome'] == 'error' and row['reason'].startswith('CANDIDATE_BENCHMARK_FAILED')
        assert result['loop']['stop_reason'] == 'error' and row['kept'] is False
    finally:
        store.close()


def test_slot_benchmark_sizing_is_closed_and_extends_the_run_deadline(tmp_path):
    sizing = {'workloads': 8, 'repetitions': 11, 'warmups': 2, 'per_job_s': 6, 'wall_s': 2000}
    store, value, runtime, _ = make_session(tmp_path, loop={**LOOP, 'wall_s': 600, 'per_call_s': 60, 'benchmark': sizing})
    try:
        # The sizing is served only under a grant carrying the same benchmark wall.
        with pytest.raises(ValueError, match='BENCHMARK_WALL_DIFFERS_FROM_GRANT'):
            session.validate_session(value)
        value['grant']['limits'] = {**value['grant'].get('limits', {}), 'benchmark_wall_s': 2000}
        value['grant_ref'] = store.put(value['grant'])
        config = capsule_loop.loop_configuration(session.validate_session(value))
        assert config['benchmark'] == sizing and capsule_loop.benchmark_wall_s(config) == 2000
        # wall_s + benchmark.wall_s + 2*per_call_s + 60 (W-M3's run-deadline formula)
        assert session.session_timeout_s(value) == 600 + 2000 + 2 * 60 + 60
        del value['grant']['limits']['benchmark_wall_s']
        value['grant_ref'] = store.put(value['grant'])
        value['loop'] = {**LOOP, 'wall_s': 600, 'per_call_s': 60}
        assert session.session_timeout_s(value) == 600 + 2 * 60 + 60
        for bad in ({**sizing, 'extra': 1}, {k: v for k, v in sizing.items() if k != 'wall_s'},
                    {**sizing, 'repetitions': 0}, {**sizing, 'wall_s': 1.5}):
            value['loop'] = {**LOOP, 'benchmark': bad}
            with pytest.raises(ValueError, match='BENCHMARK'):
                session.validate_session(value)
        # W-M1's grant limits.benchmark_wall_s alone extends the deadline; with
        # the slot sizing both must agree.
        value['grant']['limits'] = {'wall_s': 3600, 'benchmark_wall_s': 900}
        value['loop'] = {**LOOP, 'wall_s': 600, 'per_call_s': 60}
        assert capsule_loop.benchmark_wall_s(capsule_loop.loop_configuration(value)) == 900
        value['loop']['benchmark'] = sizing
        with pytest.raises(ValueError, match='BENCHMARK_WALL_DIFFERS_FROM_GRANT'):
            capsule_loop.loop_configuration(value)
    finally:
        store.close()


def test_score_without_benchmark_is_flagged_and_reports_must_match_subjects(tmp_path):
    store, value, runtime, _ = make_session(tmp_path, loop=LOOP)
    try:
        parent = asyncio.run(runtime.evaluate('parent', body=PARENT, candidate_ref=value['parent_body_ref'],
                                              binding=None, iteration=0, trials=1))
        body = spec(tag='x')
        ref = store.put_bytes(body)
        candidate = asyncio.run(runtime.evaluate('candidate', body=body, candidate_ref=ref, binding={},
                                                 iteration=1, trials=1))
        plain = capsule_objective.score(parent, candidate)
        assert plain['latency_method'] == 'single_job_floor' and plain['benchmark'] is None
        assert plain['contract']['byte_compared'] == len(parent['rows'])
        good = bench_report(PARENT, body, ratio=0.8, ci=(0.78, 0.82))
        judged = capsule_objective.score(parent, candidate, benchmark=good)
        assert judged['latency_method'] == 'paired_batched_benchmark' and judged['improved'] is True
        assert judged['benchmark']['failed_gates'] == [] and judged['latency_ratio'] == 0.8
        with pytest.raises(ValueError, match='BENCHMARK_SUBJECT_DIFFERS'):
            capsule_objective.score(parent, candidate,
                                    benchmark=bench_report(PARENT, b'other', ratio=0.8, ci=(0.78, 0.82)))
        with pytest.raises(ValueError, match='BENCHMARK_OBJECTIVE_CONTRADICTS_GATES'):
            capsule_objective.score(parent, candidate, benchmark={**good, 'gates': {'ci_upper_bound': False}})
    finally:
        store.close()
