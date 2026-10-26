"""Local routing through the real bridge/claims; controlled inference only."""
import copy
import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.automatic_routing import AutomaticRouting, LEGACY_POLICY, PRIMARY_POLICY, HYBRID_V3_POLICY, HYBRID_V4_POLICY, POLICY
from jiuwenswarm.research.bridge import BridgeError, GovernedBridge
from jiuwenswarm.research.contracts import ResearchError, validate
from jiuwenswarm.research.local_pool_registry import LocalModelRegistry, local_endpoint_url
from jiuwenswarm.research.model_settings import ModelSettingsOwner
from tests.unit_tests.research.test_budget_ceiling import work_contract


async def setup_local(tmp_path, *, calls=3, legacy=True, hybrid=False, subscription=None, hybrid_policy=None):
    store, runner, ref, contract = await work_contract(tmp_path / 'store', calls=calls)
    config = tmp_path / 'models.json'
    config.write_text(json.dumps({'schema': 'ai4r-local-model-endpoints:1', 'models': [
        {'id': name, 'base_url': f'http://127.0.0.1:{port}/v1', 'served_model': 'ai4r-' + name,
         'context_tokens': 65536, 'output_tokens': 4096, 'enabled': True}
        for name, port in [('e4b', 8011), ('qwen', 8012), ('bolt', 8013)]]}), encoding='utf-8')
    async def probe(entry):
        return True
    owner = ModelSettingsOwner(store, tmp_path / 'private' / 'models.json')
    routing = AutomaticRouting(owner, subscription, local_registry=LocalModelRegistry(config, probe=probe))
    request = {'account_id': 'alice', 'run_id': 'budget-run', 'parent_run_id': None}
    if hybrid:
        if hybrid_policy:
            candidates = [routing._pin_candidate(c) for c in await routing.available('alice')]
            owner.freeze(request, automatic_pool={'routing_policy': copy.deepcopy(hybrid_policy),
                'candidates': candidates, 'selector_id': 'local:qwen', 'verifier_id': 'local:qwen'})
        else:
            await routing.freeze(request)
    elif legacy:
        candidates = [routing._pin_candidate(c) for c in await routing.available('alice')]
        owner.freeze(request, automatic_pool={'routing_policy': dict(LEGACY_POLICY),
            'candidates': candidates, 'selector_id': 'local:e4b', 'verifier_id': 'local:qwen'})
    else:
        candidates = [routing._pin_candidate(c) for c in await routing.available('alice')]
        owner.freeze(request, automatic_pool={'routing_policy': dict(PRIMARY_POLICY),
            'candidates': candidates, 'selector_id': 'local:e4b', 'verifier_id': 'local:qwen'})
    return store, runner, ref, contract, owner, routing


def native_factory(store, observed, *, target='local:e4b', fail_executor=False):
    def factory(config, model):
        assert config['auth_mode'] == 'none' and config['api_key'] == ''
        assert config['max_retries'] == 0
        selection = model['max_tokens'] == 256
        class Client:
            async def _parse_response(self, response):
                return SimpleNamespace(content=response['text'], tool_calls=None)
            async def invoke(self, **kwargs):
                observed.append((model['model_name'], kwargs['messages'][0]['content'], selection))
                assert list(store.iter_records(run_id='budget-run', kinds=('model-call-start',)))
                if fail_executor and not selection:
                    raise ConnectionError('controlled executor failure')
                text = json.dumps({'candidate_id': target, 'reason': 'Small model is sufficient'}) if selection else 'controlled capsule output'
                if selection and kwargs['messages'][0]['content'].startswith('Classify difficulty'):
                    text = json.dumps({'difficulty': 'routine' if target == 'local:qwen' else 'reasoning', 'reason': 'Controlled difficulty'})
                if selection and kwargs['messages'][0]['content'].startswith('Classify task operations'):
                    text = json.dumps({'operations': ['lookup'] if target == 'local:qwen' else ['fit'], 'reason': 'Controlled operations'})
                return await self._parse_response({'text': text, 'model': model['model_name'],
                    'usage': {'prompt_tokens': 20, 'completion_tokens': 5}, 'choices': [{'finish_reason': 'stop'}]})
        return Client()
    return factory


def make_bridge(store, runner, owner, routing):
    return GovernedBridge(persist=store.append_record, authorize=runner.authorize_model_context,
        revalidate=runner.authorize_model_dispatch, subscription_service=object(), manual_models=owner,
        automatic_routing=routing, authorize_routing_selection=runner.authorize_routing_selection,
        read_evidence=store.read_blob, validate_record=validate)


class ControlledSubscription:
    account_fingerprint = 'a' * 64
    def __init__(self): self.calls = []
    async def status(self): return {'state': 'ready'}
    async def invoke_governed(self, prompt, **options):
        self.calls.append((prompt, options))
        assert options['expected_account_fingerprint'] == self.account_fingerprint
        return {'text': 'controlled subscription output', 'observed_runtime': True,
            'identity': {'requested': options['model'], 'effective': options['model'], 'basis': 'controlled'},
            'usage': {'input_tokens': 100, 'output_tokens': 5, 'cost_amount': None, 'currency': None,
                'unavailable_reasons': []}, 'provider_request_id': None}


@pytest.mark.asyncio
@pytest.mark.parametrize('target', ['local:qwen', 'subscription:gpt-6.1-sol'])
async def test_hybrid_router_dispatches_the_exact_selected_access_way(tmp_path, target):
    subscription = ControlledSubscription()
    store, runner, ref, contract, owner, routing = await setup_local(tmp_path, hybrid=True, subscription=subscription, hybrid_policy=HYBRID_V3_POLICY)
    try:
        observed = []
        owner.native_factory = native_factory(store, observed, target=target)
        bridge = make_bridge(store, runner, owner, routing)
        bridge.subscription = subscription
        context = runner._start_context(ref, contract, {})
        await runner._await_start(context)
        result = await bridge.call({'execution_id': context.execution_id, 'call_ordinal': 1}, 'Private worker input')
        assert observed[0][0] == 'ai4r-qwen' and observed[0][2] is True
        assert 'Private worker input' not in observed[0][1]
        decision = next(store.iter_records(kinds=('automatic-route-decision',)))['record']
        assert decision['selected_candidate_id'] == target
        assert decision['eligible_candidate_ids'] == ['local:qwen', 'subscription:gpt-6.1-sol']
        if target.startswith('subscription:'):
            assert len(observed) == 1 and len(subscription.calls) == 1
            assert subscription.calls[0][0] == 'Private worker input'
            assert result['text'] == 'controlled subscription output'
        else:
            assert [c[0] for c in observed] == ['ai4r-qwen', 'ai4r-qwen']
            assert not subscription.calls
        routes = [r['record'] for r in store.iter_records(kinds=('route-record',))]
        assert routes[-1]['schema_version'] == '4.0.0'
        assert routes[-1]['access_way'] == ('chatgpt_subscription' if subscription.calls else 'local')
    finally:
        store.close()


@pytest.mark.asyncio
async def test_hybrid_subscription_cap_excludes_new_invocations(tmp_path):
    subscription = ControlledSubscription()
    store, runner, ref, contract, owner, routing = await setup_local(tmp_path, hybrid=True, subscription=subscription, hybrid_policy=HYBRID_V3_POLICY)
    try:
        for index in range(POLICY['max_subscription_invocations_per_run']):
            store.append_record('automatic-route-decision', {'run_id': 'budget-run',
                'invocation_id': 'reserved-'+str(index), 'access_way': 'chatgpt_subscription'})
        context = runner._start_context(ref, contract, {})
        await runner._await_start(context)
        protected = runner.authorize_model_context({'execution_id': context.execution_id, 'call_ordinal': 1})
        prepared = routing.prepare(protected, 'Worker payload')
        assert [c['id'] for c in prepared['eligible']] == ['local:qwen']
        assert any(r['reason'] == 'SUBSCRIPTION_INVOCATION_CAP' for r in prepared['rejected'])
    finally:
        store.close()


@pytest.mark.asyncio
async def test_trusted_routine_capsule_avoids_assessor_cost(tmp_path):
    subscription = ControlledSubscription()
    store, runner, ref, contract, owner, routing = await setup_local(tmp_path, hybrid=True, subscription=subscription)
    try:
        observed = []
        owner.native_factory = native_factory(store, observed, target='subscription:gpt-6.1-sol')
        context = runner._start_context(ref, contract, {})
        await runner._await_start(context)
        bridge = make_bridge(store, runner, owner, routing); bridge.subscription = subscription
        await bridge.call({'execution_id': context.execution_id, 'call_ordinal': 1}, 'Search input')
        assert observed == [('ai4r-qwen', 'Search input', False)] and not subscription.calls
        decision = next(store.iter_records(kinds=('automatic-route-decision',)))['record']
        assert 'Frozen Capsule difficulty rule' in decision['reason']
    finally:
        store.close()


def test_difficulty_band_maps_to_the_host_owned_model():
    eligible = [{'id': 'local:qwen'}, {'id': 'subscription:gpt-6.1-sol'}]
    candidate, reason = AutomaticRouting.decode('{"difficulty":"reasoning","reason":"Numerical optimization"}', eligible, policy=HYBRID_V4_POLICY)
    assert candidate['id'] == 'subscription:gpt-6.1-sol'
    with pytest.raises(ValueError):
        AutomaticRouting.decode('{"difficulty":"unknown","reason":"Unbounded"}', eligible, policy=HYBRID_V4_POLICY)


def test_combined_operations_cannot_be_downgraded_by_a_confident_reason():
    eligible = [{'id': 'local:qwen'}, {'id': 'subscription:gpt-6.1-sol'}]
    chosen, _ = AutomaticRouting.decode('{"operations":["count","arithmetic"],"reason":"This is a very simple short task"}', eligible, policy=POLICY)
    assert chosen['id'] == 'subscription:gpt-6.1-sol'
    chosen, _ = AutomaticRouting.decode('{"operations":["extract","format"],"reason":"Direct extraction"}', eligible, policy=POLICY)
    assert chosen['id'] == 'local:qwen'


@pytest.mark.asyncio
@pytest.mark.parametrize('function', ['worker', 'planner'])
async def test_e4b_can_select_itself_with_distinct_governed_calls(tmp_path, function):
    store, runner, ref, contract, owner, routing = await setup_local(tmp_path)
    try:
        observed = []
        owner.native_factory = native_factory(store, observed)
        context = runner._start_context(ref, contract, {}, call_function=function)
        await runner._await_start(context)
        original = copy.deepcopy(contract)
        prompt = 'PRIVATE_INPUT_SENT_ONLY_TO_EXECUTOR'
        result = await make_bridge(store, runner, owner, routing).call(
            {'execution_id': context.execution_id, 'call_ordinal': 1}, prompt)
        assert result['text'] == 'controlled capsule output'
        assert [row[0] for row in observed] == ['ai4r-e4b', 'ai4r-e4b']
        assert prompt not in observed[0][1] and observed[1][1] == prompt
        assert 'Compare an exact index with repeated lookup.' in observed[0][1]
        selector_view = json.loads(observed[0][1].split('\n', 1)[1])
        assert selector_view['remaining_budget']['run_remaining']['model_calls'] == 3
        assert selector_view['remaining_budget']['verifier_reserved']['model_calls'] == 1
        assert selector_view['remaining_budget']['cost_remaining'] is None
        calls = [row['record'] for row in store.iter_records(kinds=('model-call',))]
        assert {c['purpose'] for c in calls} == {'routing_selection', 'task_execution'}
        assert len({c['invocation_id'] for c in calls}) == 2
        worker_call=next(c for c in calls if c['purpose']=='task_execution')
        protected=store.read_record(store.record_ref(worker_call['id']+':claim'))
        prepared=routing.prepare(protected,'Next turn in the same Capsule')
        assert routing.invocation_choice(prepared,protected)[0]['id']=='local:e4b'
        # A later context/access incompatibility must block, never silently
        # switch to another eligible executor in this same invocation.
        narrowed=dict(prepared,eligible=[c for c in prepared['eligible'] if c['id']!='local:e4b'])
        with pytest.raises(ResearchError,match='model switching is forbidden'):
            routing.invocation_choice(narrowed,protected)
        assert routing.invocation_choice(prepared,dict(protected,invocation_id='another-capsule')) is None
        for row in store.iter_records(run_id='budget-run', kinds=('route-record',)):
            validate('route-record', row['record'])
        assert store.read_record(ref) == original
        budget = runner._budget_state(contract, runner._executions[context.execution_id])
        assert budget['verifier_reserved']['model_calls'] == 1
        assert budget['run_remaining']['model_calls'] == 1
        assert contract['subnode_limits']['model_calls'] == 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_verifier_uses_only_fixed_qwen_and_exact_supplied_payload(tmp_path):
    store, runner, ref, contract, owner, routing = await setup_local(tmp_path)
    try:
        observed = []
        owner.native_factory = native_factory(store, observed)
        context = runner._start_context(ref, contract, {}, call_function='verifier')
        await runner._await_start(context)
        payload = '{"declaration":{"task":"check output"},"output":{"answer":4}}'
        await make_bridge(store, runner, owner, routing).call(
            {'execution_id': context.execution_id, 'call_ordinal': 1}, payload)
        assert observed == [('ai4r-qwen', payload, False)]
        assert not any(row['record'].get('purpose') == 'routing_selection'
            for row in store.iter_records(kinds=('model-call',)))
    finally:
        store.close()


@pytest.mark.asyncio
async def test_invalid_selection_falls_back_before_dispatch_and_provider_failure_never_replays(tmp_path):
    store, runner, ref, contract, owner, routing = await setup_local(tmp_path)
    try:
        observed = []
        owner.native_factory = native_factory(store, observed, target='unapproved-cloud-model', fail_executor=True)
        context = runner._start_context(ref, contract, {})
        await runner._await_start(context)
        with pytest.raises(BridgeError):
            await make_bridge(store, runner, owner, routing).call(
                {'execution_id': context.execution_id, 'call_ordinal': 1}, 'Capsule input')
        assert [row[0] for row in observed] == ['ai4r-e4b', 'ai4r-qwen']
        decision = next(store.iter_records(run_id='budget-run', kinds=('automatic-route-decision',)))['record']
        assert decision['selection_method'] == 'compatible_baseline'
        assert decision['selector_failure'] == 'INVALID_SELECTOR_REPLY'
        with pytest.raises(ResearchError):
            runner.authorize_model_context({'execution_id': context.execution_id, 'call_ordinal': 1})
        assert len(observed) == 2
    finally:
        store.close()


@pytest.mark.asyncio
async def test_selection_cannot_borrow_verifier_run_reservation(tmp_path):
    store, runner, ref, contract, owner, routing = await setup_local(tmp_path, calls=2)
    try:
        observed = []
        owner.native_factory = native_factory(store, observed)
        context = runner._start_context(ref, contract, {})
        await runner._await_start(context)
        await make_bridge(store, runner, owner, routing).call(
            {'execution_id': context.execution_id, 'call_ordinal': 1}, 'Capsule input')
        assert observed == [('ai4r-qwen', 'Capsule input', False)]
        assert runner._budget_state(contract, runner._executions[context.execution_id])['run_remaining']['model_calls'] == 1
    finally:
        store.close()


def test_local_plaintext_destinations_are_operator_scoped():
    for value in ['http://127.0.0.1:8011/v1', 'http://ai4r-model-e4b:8000/v1', 'http://100.105.127.48:8011/v1']:
        assert local_endpoint_url(value)
    for value in ['http://example.com/v1', 'http://169.254.169.254/v1', 'http://localhost:bad/v1',
                  'http://user:secret@localhost:8011/v1', 'http://localhost:8011/v1?url=other']:
        assert not local_endpoint_url(value)


@pytest.mark.asyncio
@pytest.mark.parametrize('function', ['worker', 'planner', 'verifier'])
async def test_new_policy_requires_qwen_without_selector_call(tmp_path, function):
    store, runner, ref, contract, owner, routing = await setup_local(tmp_path, legacy=False)
    try:
        observed = []
        owner.native_factory = native_factory(store, observed, target='local:e4b')
        context = runner._start_context(ref, contract, {}, call_function=function)
        await runner._await_start(context)
        await make_bridge(store, runner, owner, routing).call(
            {'execution_id': context.execution_id, 'call_ordinal': 1}, 'Exact Capsule payload')
        assert observed == [('ai4r-qwen', 'Exact Capsule payload', False)]
        snapshot = next(store.iter_records(kinds=('run-model-selection',)))['record']
        assert snapshot['routing_policy'] == PRIMARY_POLICY
        decision = next(store.iter_records(kinds=('automatic-route-decision',)))['record']
        assert decision['selected_candidate_id'] == 'local:qwen'
        assert decision['selection_call_ref'] is None
        if function != 'verifier':
            assert decision['eligible_candidate_ids'] == ['local:qwen']
            assert 'Protected Qwen-primary policy' in decision['reason']
        assert not any(r['record']['purpose'] == 'routing_selection'
            for r in store.iter_records(kinds=('model-call',)))
    finally:
        store.close()


@pytest.mark.asyncio
async def test_qwen_access_loss_blocks_without_e4b_or_bolt_downgrade(tmp_path):
    store, runner, ref, contract, owner, routing = await setup_local(tmp_path, legacy=False)
    try:
        observed = []
        owner.native_factory = native_factory(store, observed)
        original = owner.preflight
        def unavailable(candidate):
            if candidate['id'] == 'local:qwen':
                raise ConnectionError('Qwen unavailable')
            original(candidate)
        owner.preflight = unavailable
        context = runner._start_context(ref, contract, {})
        await runner._await_start(context)
        with pytest.raises(BridgeError, match='ENVIRONMENT_BLOCKED'):
            await make_bridge(store, runner, owner, routing).call(
                {'execution_id': context.execution_id, 'call_ordinal': 1}, 'Capsule input')
        assert observed == []
    finally:
        store.close()
