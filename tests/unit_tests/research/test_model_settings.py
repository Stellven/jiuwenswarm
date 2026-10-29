"""Manual API selection stays in the governed bridge and keeps secrets private."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.bridge import BridgeError, GovernedBridge
from jiuwenswarm.research.contracts import validate
from jiuwenswarm.research.model_settings import ModelSettingsOwner
from jiuwenswarm.research.run_contracts import contract_export_files
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research_records.contracts import ContractData
from tests.unit_tests.research.test_bridge import authorized_context


@pytest.fixture
def owned(tmp_path):
    store = SQLiteRunStore(tmp_path / 'store')
    owner = ModelSettingsOwner(store, tmp_path / 'private' / 'keys.json')
    yield store, owner
    store.close()


def select_api(store, owner):
    owner.settings({'account_id': 'account:user', 'action': 'save', 'values': {
        'preset_id': 'deepseek-pro', 'api_key': 'test-secret-never-export'}})
    store.allocate_run('account:user', 'request:api', 'a' * 64, 'run:api', 'local', {}, [])
    owner.freeze({'account_id': 'account:user', 'run_id': 'run:api', 'parent_run_id': None})


def test_selection_is_frozen_and_exports_never_contain_the_key(owned):
    store, owner = owned
    select_api(store, owner)
    assert all(item['configured'] for item in owner.status('account:user')['choices'])
    owner.settings({'account_id': 'account:user', 'action': 'save', 'values': {
        'preset_id': 'grok', 'api_key': ''}})
    store.allocate_run('account:user', 'request:other', 'b' * 64, 'run:other', 'local', {}, [])
    owner.freeze({'account_id': 'account:user', 'run_id': 'run:other', 'parent_run_id': None})
    other = owner.for_call({'run_id': 'run:other'})
    owner.preflight(other)
    assert store.read_record(other['deployment_ref'])['provider_model_name'] == 'x-ai/grok-4.7'
    owner.settings({'account_id': 'account:user', 'action': 'select', 'values': {'preset_id': 'codex'}})
    assert owner.for_call({'run_id': 'run:api'})['mode'] == 'api'
    files = contract_export_files(store, store.get_run('run:api'),
        list(store.iter_records(run_id='run:api')), 'researcher', {})
    assert any('run-model-selection-' in row['path'] for row in files)
    for row in files:
        assert b'test-secret-never-export' not in store.read_blob(row['artifact_ref'])
    assert 'test-secret-never-export' not in json.dumps(owner.status('account:user'))


@pytest.mark.parametrize('function', ['worker', 'verifier'])
def test_api_calls_use_real_bridge_checks_and_native_provider_adapter(owned, function):
    store, owner = owned
    select_api(store, owner)
    observed = []
    class NativeClient:
        async def _parse_response(self, response):
            return SimpleNamespace(content='controlled answer', tool_calls=None)
        async def invoke(self, **kwargs):
            assert any(row['kind'] == 'model-call-start' for row in store.iter_records(run_id='run:api'))
            observed.append(kwargs)
            return await self._parse_response({'model': 'deepseek-v4-pro',
                'usage': {'prompt_tokens': 10, 'completion_tokens': 2}})
    def factory(config, model):
        assert config['api_key'] == 'test-secret-never-export'
        assert config['max_retries'] == 0
        return NativeClient()
    owner.native_factory = factory
    context = authorized_context()
    context.update(run_id='run:api', call_function=function)
    bridge = GovernedBridge(persist=store.append_record, authorize=lambda _: context,
        revalidate=lambda _: context, subscription_service=object(), manual_models=owner,
        read_evidence=store.read_blob, validate_record=validate)
    result = asyncio.run(bridge.call({}, 'Only the supplied declaration and output.'))
    assert result['text'] == 'controlled answer' and len(observed) == 1
    routes = list(store.iter_records(run_id='run:api', kinds=('route-record',)))
    assert routes[0]['record']['decision_source'] == 'user_api'
    assert routes[0]['record']['router_enabled'] is False
    ContractData().validate('route-record', routes[0]['record'])
    assert observed[0]['messages'] == [{'role': 'user', 'content': 'Only the supplied declaration and output.'}]


def test_revoked_api_credential_blocks_without_falling_back_to_codex(owned):
    store, owner = owned
    select_api(store, owner)
    owner.settings({'account_id': 'account:user', 'action': 'remove', 'values': {'preset_id': 'deepseek-pro'}})
    context = authorized_context()
    context['run_id'] = 'run:api'
    bridge = GovernedBridge(persist=store.append_record, authorize=lambda _: context,
        revalidate=lambda _: context, subscription_service=object(), manual_models=owner,
        read_evidence=store.read_blob, validate_record=validate)
    with pytest.raises(BridgeError, match='auth_failed'):
        asyncio.run(bridge.call({}, 'Bounded request'))
    assert not list(store.iter_records(run_id='run:api', kinds=('model-call-start',)))


@pytest.mark.parametrize('function', ['worker', 'planner', 'verifier'])
def test_chatgpt_model_selection_is_frozen_and_reaches_subscription(owned, function):
    store, owner = owned
    catalog = {'gpt-6-sol', 'gpt-6.1-sol'}
    def select(model):
        return owner.settings({'account_id': 'account:user', 'action': 'select', 'values': {
            'preset_id': 'codex', 'chatgpt_model': model}}, chatgpt_models=catalog)
    select('gpt-6-sol')
    store.allocate_run('account:user', 'request:chatgpt', 'c' * 64, 'run:chatgpt', 'local', {}, [])
    owner.freeze({'account_id': 'account:user', 'run_id': 'run:chatgpt', 'parent_run_id': None})
    select('gpt-6.1-sol')
    observed = []
    class Subscription:
        async def invoke_governed(self, prompt, *, model, timeout_s):
            observed.append(model)
            return {'text': 'controlled answer', 'identity': {
                'requested': model, 'effective': model, 'basis': 'controlled subscription'}}
    context = authorized_context()
    context.update(run_id='run:chatgpt', call_function=function, requested_model='gpt-6.1-sol')
    bridge = GovernedBridge(persist=store.append_record, authorize=lambda _: context,
        revalidate=lambda _: context, subscription_service=Subscription(), manual_models=owner,
        read_evidence=store.read_blob, validate_record=validate)
    result = asyncio.run(bridge.call({}, 'Declaration and output only.'))
    assert result['text'] == 'controlled answer' and observed == ['gpt-6-sol']
    call = store.read_record(result['call_ref'])
    assert call['identity']['requested'] == 'gpt-6-sol'
    assert store.read_record(call['deployment_ref'])['provider_model_name'] == 'gpt-6-sol'
