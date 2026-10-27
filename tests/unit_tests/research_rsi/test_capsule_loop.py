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


def spec(fail=(), wall=0.1, tag=''):
    return ('# spec ' + json.dumps({'fail': list(fail), 'wall': wall, 'tag': tag}) + '\n').encode()


def parse(body):
    if body.startswith(b'# spec '):
        return json.loads(body.splitlines()[0][7:])
    return {'fail': [], 'wall': 0.1}


def make_session(tmp_path, name='utility.calculate', *, loop=None, max_executions=None, extra_contracts=0):
    store = RecordStore(tmp_path / 'records')
    target = registered_capsule(name)
    parent_ref = store.put_bytes(PARENT)
    ref = lambda text: store.put({'test': text})
    grant = {'schema': session.GRANT_SCHEMA, 'bootstrap_schema': session.BOOTSTRAP_SCHEMA, 'run_id': 'loop-capsule',
             'capsule_name': name, 'roles': ['parent', 'candidate'], 'parent_sha256': parent_ref['sha256'],
             'runtime_manifest_sha256': 'a' * 64}
    if max_executions is not None:
        grant['max_executions'] = max_executions
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
                item = {'fixture_id': row['id'], 'fixture_set': fixture_set, 'task_success': ok,
                        'protected_wall_s': behaviour['wall'], 'output_bytes': 10,
                        'checks': {'expected': SECRET} if fixture_set == 'held_out' else {'diff': 'want 4 got 5'} if not ok else {},
                        'receipt': {'subject_ref': candidate_ref}, 'candidate_ref': candidate_ref}
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
