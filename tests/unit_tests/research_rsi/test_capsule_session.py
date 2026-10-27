"""Explicit fake governed handles exercise orchestration without model calls."""
import asyncio
import hashlib
import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.research_rsi import capsule_session as session
from jiuwenswarm.research_rsi.records import RecordStore, encoded
from jiuwenswarm.research_rsi.targets.capsules import registered_capsule, public_fixtures


class FakeGoverned:
    def __init__(self, store, role, response=None):
        self.store, self.role, self.response = store, role, response
        self.used = False
        self.last_model_calls = None
        self.last_generating_model = 'explicit-test-double'
        self.last_evidence = []
        self.last_unavailable_reasons = []

    async def __call__(self, prompt):
        assert not self.used
        self.used = True
        self.last_model_calls = 1
        self.last_evidence = [self.store.put({'test_double': self.role})]
        if self.response is not None:
            return self.response
        value = json.loads(prompt)
        if self.role == 'diagnosis':
            return json.dumps({'schema': 'ai4r-rsi-diagnosis:1', 'observed_symptom': 'Public measurement only',
                'supporting_visible_evidence': [value['visible_evidence'][0]['ref']],
                'suspected_mechanism': 'Repeated loop', 'alternative_causes': ['Clock variation'],
                'authorized_component': value['authorized_component'], 'proposed_change_direction': 'Simplify loop',
                'expected_effect': 'Hypothesis only', 'visible_falsification_checks': ['Run complete packets'],
                'uncertainties': ['No improvement measured']})
        return json.dumps({'path': value['visible_context']['authorized_mutable_path'],
                           'body': '# changed public carrier\n', 'rationale': 'Test proposal only'})


def fixture(tmp_path, name):
    store = RecordStore(tmp_path / 'records')
    target = registered_capsule(name)
    parent = b'# original public carrier\n'
    parent_ref = store.put_bytes(parent)
    ref = lambda text: store.put({'test': text})
    grant = {'schema': session.GRANT_SCHEMA, 'bootstrap_schema': session.BOOTSTRAP_SCHEMA, 'run_id': 'test-capsule', 'capsule_name': name, 'roles': ['parent', 'candidate'],
             'parent_sha256': parent_ref['sha256'], 'runtime_manifest_sha256': 'a'*64}
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
    evaluations = []
    async def evaluate(role, *, body, candidate_ref, binding, iteration=0, trials=1):
        assert hashlib.sha256(body).hexdigest() == candidate_ref['sha256']
        evaluations.append((role, binding))
        rows = [{'fixture_id': row['id'], 'candidate_ref': candidate_ref, 'group_empty': True,
            'runtime_manifest_sha256': grant['runtime_manifest_sha256'],
            'receipt': {'subject_ref': candidate_ref}, 'task_success': True,
            'protected_wall_s': 0.1, 'evidence_ref': ref(role+row['id'])} for row in public_fixtures(name)]
        result = {'schema': 'ai4r-rsi-whole-capsule-visible-result:1', 'role': role,
            'executions': len(rows), 'passed_count': len(rows), 'passed': True,
            'grant_ref': value['grant_ref'], 'security': 'UNQUALIFIED', 'model_calls': 0,
            'rows': rows, 'protected_wall_s': sum(row['protected_wall_s'] for row in rows)}
        return {**result, 'result_ref': store.put(result)}
    async def before_model():
        pass
    runtime = SimpleNamespace(store=store, evaluate=evaluate, before_model=before_model, objective=PublicOnlyObjective())
    return store, value, runtime, evaluations


class PublicOnlyObjective:
    """Interface B test stand-in over the historical v1 public-only results."""
    def __init__(self):
        from tests.unit_tests.research_rsi.test_capsule_loop import StubObjective
        self.inner = StubObjective()

    def fixtures(self, name, *, fixture_set):
        return public_fixtures(name) if fixture_set == 'public' else []

    def evaluation_fixtures(self, name):
        return [dict(row, fixture_set='public') for row in public_fixtures(name)]

    def calibrate_noise(self, trials):
        return self.inner.calibrate_noise(trials)

    def score(self, parent, candidate, *, noise=None):
        return self.inner.score(parent, candidate, noise=noise)


@pytest.mark.parametrize('name', ['utility.calculate', 'utility.table_normalize'])
def test_two_governed_handles_actual_scope_and_durable_no_replay(tmp_path, name):
    store, value, runtime, evaluations = fixture(tmp_path, name)
    try:
        handles = [FakeGoverned(store, role) for role in ('diagnosis', 'proposal')]
        result = asyncio.run(session.execute(value, runtime, models=handles))
        assert result['status'] == 'VISIBLE_EVALUATED_UNQUALIFIED', result
        assert result['model_calls'] == 2
        # A v1 session (no ``loop``) is exactly the historical one-shot attempt.
        assert result['loop']['max_iterations'] == result['loop']['completed_iterations'] == 1
        assert result['loop']['model_backend']['kind'] == 'host-codex'
        assert result['loop']['configuration']['source'] == 'legacy-v1-session'
        assert result['security'] == 'UNQUALIFIED' and result['admission_ref'] is None
        assert [row[0] for row in evaluations] == ['parent', 'candidate']
        assert evaluations[1][1]['mutable_path'] == registered_capsule(name).carrier_path
        assert store.read(result['candidate_ref']) == b'# changed public carrier\n'
        with pytest.raises(ValueError, match='ALREADY_CLAIMED'):
            asyncio.run(session.execute(value, runtime, models=[FakeGoverned(store, r) for r in ('diagnosis', 'proposal')]))
    finally:
        store.close()


def test_invalid_proposal_retains_bytes_without_candidate_execution_or_retry(tmp_path):
    store, value, runtime, evaluations = fixture(tmp_path, 'utility.calculate')
    try:
        malformed = json.dumps({'path': '../escape.py', 'body': '# preserved actual bytes', 'rationale': 'Invalid scope'})
        handles = [FakeGoverned(store, 'diagnosis'), FakeGoverned(store, 'proposal', malformed)]
        result = asyncio.run(session.execute(value, runtime, models=handles))
        assert result['status'] == 'ERROR_NO_REPLAY' and result['model_calls'] == 2
        assert store.read(result['proposal_response_ref']).decode() == malformed
        assert store.read(result['proposal_capture']['child_ref']) == b'# preserved actual bytes'
        assert [role for role, _ in evaluations] == ['parent']
        assert result['candidate_visible'] is None
        assert result['loop']['iterations'][0]['outcome'] == 'rejected'
        assert result['loop']['stop_reason'] == 'no_progress'
    finally:
        store.close()
