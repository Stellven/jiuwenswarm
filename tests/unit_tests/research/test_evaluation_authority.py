"""IF016 source-directed controls. Controlled transport is not runtime qualification."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from jiuwenswarm.research.contracts import ResearchError, validate
from jiuwenswarm.research.state import json_bytes

PRIVATE_TYPES = (
    'evaluation-runtime', 'evaluation-request', 'evaluation-node-context',
    'evaluation-subnode-context', 'evaluation-checking-basis', 'evaluation-scope',
    'evaluation-assignment-grant', 'evaluation-call-claim', 'evaluation-tool-claim',
    'evaluation-event', 'evaluation-terminal', 'evaluation-export',
)
PRODUCT_TABLES = ('runs', 'requests', 'nodes', 'attempts', 'acceptance', 'cancellation', 'model_calls', 'tool_calls')


def product_state(store):
    return {name: [tuple(row) for row in store.connection.execute('SELECT * FROM ' + name)] for name in PRODUCT_TABLES}


@pytest.mark.asyncio
async def test_private_assignment_construction_is_inert_until_explicit_start(tmp_path):
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    owner = provider.resources.bind_runtime(capture_runtime(store, provider, [request]))
    before_product = product_state(store)
    request_ref = owner.accept_request(actor, request, 'E3')
    scope_ref = owner.prepare(request_ref)
    grant_ref = owner.prepare_assignment(scope_ref, 'worker', None)
    grant, child, _ = owner.projection.load_execution(grant_ref)
    context = owner.start_assignment(grant_ref, owner.runner._decode_inputs(child))
    assert owner._assignment(grant['execution_id'])['state'] == 'prepared', \
        'Construction cannot publish assignment_started before an awaited start'
    def starts():
        return [row['record'] for row in store.iter_records(kinds=('evaluation-event',))
            if row['record']['request_ref'] == request_ref and row['record']['kind'] == 'assignment_started']
    assert starts() == []
    binding = {'contract_ref': grant['contract_ref'], 'invocation_id': grant['invocation_id'],
        'execution_id': grant['execution_id']}
    preparation = owner.runner.authorize_executor_preparation(binding)
    captured = store.read_record(preparation['preparation_ref'])
    assert captured['assignment_grant_ref'] == grant_ref
    assert captured['deadline_unix_ns'] <= grant['deadline_unix_ns']
    with pytest.raises(ResearchError):
        owner.authorize_model_context({'execution_id': grant['execution_id'], 'call_ordinal': 1})
    with pytest.raises(ResearchError):
        owner.authorize_executor_binding(binding)
    assert product_state(store) == before_product and prompts == []
    await owner.runner._await_start(context)
    assert owner._assignment(grant['execution_id'])['state'] == 'started'
    assert len(starts()) == 1
    with pytest.raises(ResearchError):
        await owner.runner._await_start(context)
    assert product_state(store) == before_product and prompts == []
    store.close()


async def source_fixture(root, *, allowed_entry_points=None, opportunity_statement='The frozen mechanism avoids repeated lookup work.'):
    from tests.unit_tests.research.test_evaluation_provider import installed_provider
    from jiuwenswarm.research.bridge import GovernedBridge
    from jiuwenswarm.research.capsules.assets import register_research_capsules
    from jiuwenswarm.research.runner import Registry
    store, provider, actor, request = await installed_provider(root, allowed_entry_points=allowed_entry_points)
    resources = provider.resources
    owner, prompts = resources.admitted, []
    runner = owner.runner

    class ControlledSubscription:
        async def invoke_governed(self, prompt, *, model, timeout_s):
            prompts.append(prompt)
            if 'Criteria for this output:\n' in prompt:
                criteria = json.loads(prompt.split('Criteria for this output:\n', 1)[1].split('\n\n<subject_payload>', 1)[0])
                response = {'findings': [{'criterion_id': c['criterion_id'], 'outcome': 'PASS',
                    'reason': 'Controlled finding for source-shaped protocol mechanics only'} for c in criteria],
                    'uncertainties': [], 'limitations': [], 'required_correction': None}
            else:
                response = {'scores': json.loads(Path('tests/fixtures/research/pipeline/source-valid/screening_result.json').read_bytes())['scores'],
                    'opportunity_statement': opportunity_statement}
            return {'text': json.dumps(response), 'identity': {'effective': None, 'basis': 'controlled protocol fixture'},
                'usage': {}, 'provider_request_id': None, 'observed_runtime': True}

    registry = Registry(); runner.registry = registry; owner.resources.registry = registry
    register_research_capsules(registry, runner.check_registry, owner.library, store,
        assets={'screening': owner.resources.composition.installed['screening']})
    runner.model = GovernedBridge(persist=runner.capture_record, authorize=runner.authorize_model_context,
        revalidate=runner.authorize_model_dispatch, subscription_service=ControlledSubscription(), validate_record=validate)
    return store, provider, actor, request, prompts


def capture_runtime(store, provider, requests, *, seconds=None):
    resources = provider.resources; expected = resources.admitted.resources.exact_binding_refs
    contract = store.read_record(provider.assets['cases'][0]['binding_ref'])
    parent = store.read_record(contract['node_contract_ref'])
    limits = copy.deepcopy(parent['node_limits'])
    if seconds is not None: limits['time_s'] = seconds
    slots = [{'slot_id': 'slot' + str(i), 'request_id': request['request_id'], 'entry_point': 'E3',
        'case_id': request['case_id'], 'config_id': 'controlled', 'repeat_index': i,
        'request_sha256': hashlib.sha256(json_bytes(['E3', request])).hexdigest(), 'limits': limits}
        for i, request in enumerate(requests)]
    schedule = store.put_blob(json_bytes(slots), media_type='application/json')
    return store.append_record('evaluation-runtime', {'schema': 'ai4r-evaluation-runtime:1', 'id': 'evaluation-runtime:controlled',
        **{key: provider.assets[key] for key in ('account_id', 'workspace_id', 'campaign_id', 'configuration_ref')},
        'profile_ref': provider.profile_ref, 'assets_ref': provider.assets_ref,
        'model_selection_profile_ref': expected['model_selection_profile_ref'], 'deployment_ref': expected['deployment_ref'],
        'policy_ref': contract['policy_ref'], 'library_snapshot_ref': resources.snapshot_ref,
        'schedule_ref': schedule, 'slots': slots, 'accepted': False, 'invalid_for_product': True})


@pytest.mark.asyncio
async def test_public_fresh_request_cannot_reuse_a_legacy_deterministic_grant(tmp_path):
    """Baseline reproduced one worker result/identity reused for two request IDs."""
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        try:
            first = await provider.single_cc(actor, request)
            second = await provider.single_cc(actor, request | {'request_id': 'actual-single-2'})
        except ResearchError as error:
            assert error.code == 'entry_point_unavailable' and prompts == []
        else:
            assert first['invocation_id'] != second['invocation_id'], 'Two scheduled requests reused one actual assignment'
            assert len(prompts) == 2, 'Fresh requests must perform distinct actual work, or fail closed before work'
    finally:
        store.close()


@pytest.mark.parametrize('kind', PRIVATE_TYPES)
def test_twelve_private_schemas_are_closed_and_tainted(kind):
    from jiuwenswarm.research.evaluation_projection import private_schema
    schema = private_schema(kind)
    assert schema['additionalProperties'] is False
    # The optional frozen account selection extends existing runtime records;
    # legacy fixed-subscription captures remain valid without this field.
    optional = {'account_model_selection_ref'} if kind == 'evaluation-runtime' else set()
    assert set(schema['required']) == set(schema['properties']) - optional
    assert schema['properties']['accepted'] == {'const': False}
    assert schema['properties']['invalid_for_product'] == {'const': True}
    assert schema['properties']['schema']['const'] == 'ai4r-' + kind + ':1'
    assert schema['x-owning-interface'] == 'M1-IF-016@r1'


@pytest.mark.asyncio
async def test_two_approved_slots_create_private_actual_work_without_product_rows(tmp_path):
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        second = request | {'request_id': 'actual-single-2'}
        runtime = capture_runtime(store, provider, [request, second])
        authority = provider.resources.bind_runtime(runtime)
        before = product_state(store)
        first_result = await provider.single_cc(actor, request)
        second_result = await provider.single_cc(actor, second)
        if first_result['status']!='completed':
            print('FIRST_PRIVATE_RESULT',json.dumps(first_result,sort_keys=True))
        assert first_result['status'] == 'completed', first_result
        assert second_result['status'] == 'completed', second_result
        assert first_result['invocation_id'] != second_result['invocation_id']
        assert len(prompts) == 2 and len(first_result['model_calls']) == len(second_result['model_calls']) == 1
        assert product_state(store) == before
        grants = list(store.iter_records(kinds=('evaluation-assignment-grant',)))
        assert len(grants) == 2 and len({r['record']['execution_id'] for r in grants}) == 2
        for row in grants:
            grant = row['record']
            assert store.record_kind(grant['contract_ref']) == 'evaluation-subnode-context'
            assert store.record_kind(grant['check_plan_ref']) == 'evaluation-checking-basis'
            assert store.read_record(grant['contract_ref'])['schema'] == 'ai4r-evaluation-subnode-context:1'
        assert len(list(store.iter_records(kinds=('evaluation-invocation-observation',)))) == 2
        assert len(list(store.iter_records(kinds=('evaluation-trial-measurement',)))) == 2
        assert not list(store.iter_records(kinds=('gate-decision', 'acceptance-commit', 'invocation-observation')))
        assert await provider.single_cc(actor, request) == first_result and len(prompts) == 2
        with pytest.raises(ResearchError): await provider.single_cc(actor, request | {'request_id': 'unscheduled'})
        assert len(prompts) == 2
        for result in (first_result, second_result):
            with pytest.raises(ResearchError, match='Evaluation|evaluation'): store.require_product_material(list(result['output_refs'].values()))
        assert authority is not None
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['kind', 'hash', 'template', 'input', 'extra', 'canonical_schema', 'grant_target'])
async def test_private_context_forgery_never_reaches_model(tmp_path, fault):
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        authority = provider.resources.bind_runtime(capture_runtime(store, provider, [request]))
        request_ref = authority.accept_request(actor, request, 'E3')
        scope_ref = authority.prepare(request_ref)
        grant_ref = authority.prepare_assignment(scope_ref, 'worker', None)
        grant = store.read_record(grant_ref); context = store.read_record(grant['contract_ref'])
        if fault == 'hash':
            changed = dict(grant_ref, sha256='0' * 64)
        elif fault == 'grant_target':
            grant['contract_ref'] = grant['check_plan_ref']; grant['id'] += ':forged'
            changed = store.append_record('evaluation-assignment-grant', grant)
        else:
            if fault == 'template': context['source_template_ref'] = grant['check_plan_ref']
            if fault == 'input': context['input_refs'] = []
            if fault == 'extra': context['unapproved'] = True
            if fault == 'canonical_schema': context['schema_version'] = '1.0.0'
            context['id'] += ':forged'
            ref = store.append_record('subnode-execution-contract' if fault == 'kind' else 'evaluation-subnode-context', context)
            grant.update(id=grant['id'] + ':forged', contract_ref=ref)
            changed = store.append_record('evaluation-assignment-grant', grant)
        with pytest.raises(ResearchError): authority.projection.load_execution(changed)
        assert prompts == [] and not list(store.iter_records(kinds=('model-call-start',)))
    finally:
        store.close()
