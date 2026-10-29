"""Fresh private E2 replay, source host checks and actual selected review."""
import copy
import hashlib

import pytest

from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_evaluation_replay import replay_fixture
from tests.unit_tests.research.test_evaluation_authority import product_state


def replay_runtime(store, provider, requests):
    resources = provider.resources
    refs = resources.admitted.resources.exact_binding_refs
    case = provider.assets['cases'][0]
    subject, _, _ = resources._subject(case)
    contract = store.read_record(subject)
    parent = store.read_record(contract['node_contract_ref'])
    slots = [{'slot_id': 'replay-slot-' + str(i), 'request_id': request['request_id'],
        'entry_point': 'E2', 'case_id': request['case_id'], 'config_id': 'controlled', 'repeat_index': i,
        'request_sha256': hashlib.sha256(json_bytes(['E2', dict(request, host_records=request.get('host_records', []))])).hexdigest(),
        'limits': copy.deepcopy(parent['node_limits'])} for i, request in enumerate(requests)]
    return store.append_record('evaluation-runtime', {'schema': 'ai4r-evaluation-runtime:1', 'id': 'runtime:replay',
        **{k: provider.assets[k] for k in ('account_id', 'workspace_id', 'campaign_id', 'configuration_ref')},
        **{k: refs[k] for k in ('model_selection_profile_ref', 'deployment_ref')},
        'profile_ref': provider.profile_ref, 'assets_ref': provider.assets_ref,
        'policy_ref': contract['policy_ref'], 'library_snapshot_ref': resources.snapshot_ref,
        'schedule_ref': store.put_blob(json_bytes(slots)), 'slots': slots,
        'accepted': False, 'invalid_for_product': True})


@pytest.mark.asyncio
@pytest.mark.parametrize('bad_span', [True, False])
async def test_private_replay_preserves_original_worker_and_only_selected_fresh_review(tmp_path, bad_span, monkeypatch):
    from jiuwenswarm.research.evaluation_authority import EvaluationMeasurementContext
    import traceback
    actual_review=EvaluationMeasurementContext.review
    async def audited_review(self,*args,**kwargs):
        try:return await actual_review(self,*args,**kwargs)
        except BaseException:
            traceback.print_exc()
            raise
    monkeypatch.setattr(EvaluationMeasurementContext,'review',audited_review)
    store, provider, actor, request, prompts, original = await replay_fixture(tmp_path,
        bad_span=bad_span, record_gate=True, host_duration=.01)
    try:
        second = request | {'request_id': request['request_id'] + ':second'}
        owner = provider.resources.bind_runtime(replay_runtime(store, provider, [request, second]))
        owner.runner.model.persist = owner.runner.capture_record
        before = product_state(store)
        original_observations = [x['ref'] for x in store.iter_records(kinds=('invocation-observation',))]
        first = await provider.node_replay(actor, request)
        duplicate = await provider.node_replay(actor, request)
        other = await provider.node_replay(actor, second)
        assert duplicate == first and first['tier1_verdict'] == ('FAIL' if bad_span else 'PASS')
        assert first['tier2_verdict'] == ('NOT_RUN' if bad_span else 'PASS'), first.get('reason')
        assert first['advanced'] is (not bad_span)
        assert first['downstream_action'] == ('halted' if bad_span else 'started')
        assert len(prompts) == (1 if bad_span else 3)
        assert product_state(store) == before
        assert [x['ref'] for x in store.iter_records(kinds=('invocation-observation',))] == original_observations
        assignments = store.connection.execute('SELECT role FROM evaluation_assignments').fetchall()
        assert [x['role'] for x in assignments] == ([] if bad_span else ['verifier', 'verifier'])
        assert len(first['model_calls']) == (0 if bad_span else 1)
        assert len(other['model_calls']) == (0 if bad_span else 1)
        if not bad_span:
            assert first['model_calls'][0]['call_ref'] != other['model_calls'][0]['call_ref']
            assert all('HOST_RECORD_SENTINEL' not in p for p in prompts[1:])
            claims = list(store.iter_records(kinds=('evaluation-call-claim',)))
            assert len(claims) == 2 and all(x['record']['expected_prompt_sha256'] for x in claims)
        measurements = list(store.iter_records(kinds=('evaluation-trial-measurement',)))
        assert len(measurements) == 2
        assert all(x['record']['observation_ref'] == original.observation_ref
            and x['record']['output_refs'] == original.output_refs for x in measurements)
    finally:
        store.close()
