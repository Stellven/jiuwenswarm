"""Actual E2 cleanup entry; controlled review fault is not automatic cleanup.

The original canonical producer runs once. A test-only wrapper enters the real
registered cleanup operation after the real selected review call fails and
before measurement capture. No terminal/result/marker is fabricated.
"""
import copy
import json

import pytest

from jiuwenswarm.research.bridge import BridgeError
from jiuwenswarm.research.contracts import validate
from jiuwenswarm.research.evaluation_authority import EvaluationMeasurementContext
from jiuwenswarm.research.evaluation_history import EvaluationReader
from jiuwenswarm.research.evaluation_provider import EvaluationProvider, InstalledEvaluationResources
from jiuwenswarm.research.measurement import ordered_replay_outputs
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes
from tests.unit_tests.research.evaluation_runtime_fixture import bind_request_runtime
from tests.unit_tests.research.test_evaluation_authority import product_state, source_fixture
from tests.unit_tests.research.test_evaluation_replay import replay_fixture
from tests.unit_tests.research.test_evaluation_resource_loss import private_snapshot


async def actual_replay_source(root, mode):
    if mode == 'single':
        store, provider, actor, request, prompts, original = await replay_fixture(
            root, bad_span=False, record_gate=True)
        return store, provider, actor, request, prompts, original

    store, producer, actor, _, prompts = await source_fixture(
        root, allowed_entry_points=['E2', 'E3'],
        opportunity_statement='The frozen mechanism avoids repeated lookup work.')
    try:
        admitted = producer.resources.admitted
        source_ref = producer.assets['cases'][0]['binding_ref']
        source = store.read_record(source_ref, contract_id='subnode-execution-contract')
        check_ref = next(row['ref'] for row in store.iter_records(kinds=('bound-check-plan',))
                         if row['record']['contract_ref'] == source_ref)
        original = await admitted.execute(admitted.prepare(source_ref, check_ref, semantic_review=False))
        assert original.failure is None and len(original.output_refs) == 2 and len(prompts) == 1
        observed = store.read_record(original.observation_ref, contract_id='invocation-observation')
        output_map = ordered_replay_outputs(original.output_refs, observed['output_refs'])
        # The second actually observed port is deliberately selected. JSON object
        # sorting is not an authority for the source observation's Ref[] order.
        selected = list(output_map)[1]
        assert selected == 'opportunity_card'
        verifier = admitted.resources.composition.installed['verifier']['pin']
        verifier_id = verifier['cc_name'] + '@' + verifier['cc_version']
        declaration = source['bindings'][0]['declaration_ref']
        binding = store.append_record('evaluation-case-binding', {
            'schema': 'ai4r-node-replay-binding:2', 'id': 'binding:e2-cleanup-multi',
            'contract_ref': source_ref, 'check_plan_ref': check_ref,
            'output_refs': copy.deepcopy(output_map), 'original_observation_ref': original.observation_ref,
            'verifier_cc_id': verifier_id, 'host_records': [], 'selected_output_port': selected})
        assets = store.append_record('evaluation-assets', {
            'schema': 'ai4r-evaluation-assets:1', 'id': 'assets:e2-cleanup-multi',
            **{key: producer.assets[key] for key in
               ('profile_ref', 'configuration_ref', 'account_id', 'workspace_id', 'campaign_id')},
            'entries': [{'path': name, 'sha256': ref['sha256'], 'artifact_ref': ref, 'role': role}
                        for name, ref, role in [('declaration.json', declaration, 'declaration'),
                                               ('selected.json', output_map[selected], 'output')]],
            'cases': [{'case_id': 'e2-cleanup-multi', 'entry_point': 'E2',
                       'binding_ref': binding, 'record_gate': True}]})
        resources = InstalledEvaluationResources(admitted, profile_ref=producer.profile_ref,
            assets_ref=assets, library_snapshot_ref=producer.resources.snapshot_ref)
        provider = EvaluationProvider(store, admitted.resources.operator, assets_ref=assets,
            resources=resources, library=admitted.library)
        request = {'request_id': 'e2-cleanup:multi', 'campaign_id': producer.assets['campaign_id'],
            'case_id': 'e2-cleanup-multi', 'evaluation_profile_id': producer.profile['profile_id'],
            'verifier_cc_id': verifier_id, 'node_id': source['node_id'],
            'declaration': {'path': 'declaration.json', 'sha256': declaration['sha256']},
            'output': {'path': 'selected.json', 'sha256': output_map[selected]['sha256']},
            'host_records': []}
        return store, provider, actor, request, prompts, original
    except BaseException:
        store.close()
        raise


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['single', 'multi'])
async def test_actual_e2_failed_review_cleanup_preserves_ordered_source_and_history(tmp_path, monkeypatch, mode):
    store, provider, actor, request, prompts, original = await actual_replay_source(tmp_path, mode)
    try:
        owner = bind_request_runtime(store, provider, request, 'E2')
        before_product = product_state(store)
        source_originals = [(ref, store.read_blob(ref))
                            for ref in [original.observation_ref, *original.output_refs.values()]]
        calls_before = len(prompts)
        assert calls_before == 1  # The actual canonical source has already run.
        cleanup = []
        actual_review = EvaluationMeasurementContext.review

        async def enter_actual_cleanup(ctx, *args, **kwargs):
            try:
                return await actual_review(ctx, *args, **kwargs)
            except Exception as error:
                if getattr(error, 'code', None) != 'provider_error':
                    raise
                assert ctx.owner is owner and ctx.grant is None
                receipt = await ctx.contain('provider_error')
                cleanup.append((ctx.scope_ref, receipt))
                raise

        class FailedSelectedReviewer:
            async def invoke_governed(self, prompt, *, model, timeout_s):
                payload = json.loads(prompt.split('<subject_payload>\n', 1)[1].split('\n</subject_payload>', 1)[0])
                assert set(payload) == {'subject_declaration', 'subject_output'}
                prompts.append(prompt)
                raise BridgeError('provider_error')

        # Explicit component trigger only. The unwrapped generic provider-error
        # path does not currently request this extra cleanup; that remains a
        # separate producer gap, not behavior supplied by the validator fix.
        monkeypatch.setattr(EvaluationMeasurementContext, 'review', enter_actual_cleanup)
        owner.runner.model.subscription = FailedSelectedReviewer()
        result = await provider.node_replay(actor, request)
        assert result['tier1_verdict'] == 'PASS' and result['tier2_verdict'] == 'NOT_RUN'
        assert result['reason'] == 'provider_error' and result['advanced'] is False
        assert result['gate_decision']['action'] == 'halt' and result['downstream_action'] == 'halted'
        assert result['invalid_for_product'] is True and len(prompts) == calls_before + 1
        assert len(result['model_calls']) == 1 and result['model_calls'][0]['role'] == 'verifier'
        assert result['model_calls'][0]['outcome'] == 'failed'
        assert len(cleanup) == 1
        row = store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
        request_ref, scope_ref = json.loads(row['request_ref']), json.loads(row['scope_ref'])
        scope = store.read_record(scope_ref)
        validate('urn:ai4r:private:evaluation-scope:1', scope)
        assert isinstance(scope['source_output_refs'], list)
        binding = store.read_record(scope['source_binding_ref'])
        observation = store.read_record(scope['source_observation_ref'], contract_id='invocation-observation')
        expected = ordered_replay_outputs(binding['output_refs'], observation['output_refs'])
        assert scope['source_output_refs'] == list(expected.values()) == observation['output_refs']
        assert expected == original.output_refs and scope['selected_output_port'] in expected
        if mode == 'multi':
            assert scope['selected_output_port'] == list(expected)[1]
            assert list(binding['output_refs']) != list(expected)  # Canonical JSON sorted its map keys.
        terminal_ref = json.loads(row['terminal_ref'])
        terminal = owner.inspect(request_ref)
        assert row['state'] == terminal['state'] == 'failed'
        assert terminal['containment_ref'] == cleanup[0][1]['containment_ref'] and row['cancel_id']
        assert cleanup[0][0] == scope_ref and len(terminal['measurement_refs']) == 1
        measured = store.read_record(terminal['measurement_refs'][0])
        assert measured['output_refs'] == expected and measured['observation_ref'] == original.observation_ref
        assert measured['status'] == 'failed' and measured['failure'] == 'provider_error'
        publication = store.read_record(json.loads(row['head_ref']))
        assert publication['kind'] == 'terminal' and publication['capture_ref'] == terminal_ref
        assert publication['previous_event_ref'] == terminal['through_event_ref']
        assert product_state(store) == before_product
        assert all(store.read_blob(ref) == raw for ref, raw in source_originals)
        assert store.record_kind(original.observation_ref) == 'invocation-observation'
        store.require_product_material(list(original.output_refs.values()))
        before_private = private_snapshot(store)
        provider.resources = None
        owner.runner._evaluation_owners.clear()
        owner.runner.model = owner.runner.executor = None
        reader = EvaluationReader(store, runtime_ref=owner.runtime_ref)
        assert provider.get(actor, request['request_id'])['result'] == result
        assert await provider.node_replay(actor, request) == result
        assert reader.get(actor, request['request_id'])['result'] == result
        assert len(prompts) == calls_before + 1 and private_snapshot(store) == before_private
        root = store.root
        store.close()
        store = SQLiteRunStore(root, recover=False)
        assert EvaluationReader(store, runtime_ref=owner.runtime_ref).get(actor, request['request_id'])['result'] == result
        assert len(prompts) == calls_before + 1
        assert all(store.read_blob(ref) == raw for ref, raw in source_originals)
    finally:
        store.close()
