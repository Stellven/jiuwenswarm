import asyncio

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.runner import ProducedArtifact, Registry
from jiuwenswarm.research.state import SQLiteRunStore


def test_registry_has_no_dynamic_import_fallback():
    registry=Registry()
    with pytest.raises(ResearchError,match='carrier_unregistered'):
        registry.resolve('os.system','1','a'*64)


def test_model_call_claim_is_durable_and_uncertain_start_is_not_resent(tmp_path):
    store=SQLiteRunStore(tmp_path)
    store.create_run('run:one',account_id='alice',workspace_id='project',submission={})
    context={'run_id':'run:one','node_id':'search','attempt_id':'search-a1','invocation_id':'inv:one','call_ordinal':1}
    call,ref=store.claim_model_call(context,invocation_limit=2,node_limit=3,run_limit=5)
    assert store.read_record(ref)['call_id']==call
    with pytest.raises(ResearchError,match='model_call_already_claimed'):
        store.claim_model_call(context,invocation_limit=2,node_limit=3,run_limit=5)
    store.claim_model_call(context|{'call_ordinal':2},invocation_limit=2,node_limit=3,run_limit=5)
    with pytest.raises(ResearchError,match='budget_exhausted'):
        store.claim_model_call(context|{'call_ordinal':3},invocation_limit=2,node_limit=3,run_limit=5)


def test_tool_claim_is_durable_across_queries_and_never_reset_by_reopen(tmp_path):
    store=SQLiteRunStore(tmp_path);store.create_run('run:tools',account_id='alice',workspace_id='project',submission={})
    context={'run_id':'run:tools','node_id':'search','subnode_id':'search','attempt_id':'search-a1','invocation_id':'inv:search','tool_ordinal':1,'operation':'arxiv'}
    first=store.claim_tool_call(context,tool_limit=2)
    assert store.read_record(first)['operation']=='arxiv'
    with pytest.raises(ResearchError,match='tool_call_already_claimed'):store.claim_tool_call(context,tool_limit=2)
    store.close();store=SQLiteRunStore(tmp_path)
    store.claim_tool_call(context|{'tool_ordinal':2,'operation':'local_documents'},tool_limit=2)
    with pytest.raises(ResearchError,match='budget_exhausted'):store.claim_tool_call(context|{'tool_ordinal':3},tool_limit=2)


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['model', 'tool', 'executor'])
async def test_inert_preparation_denies_every_effect_authorizer(tmp_path, operation):
    from tests.unit_tests.research.test_budget_ceiling import work_contract
    store, runner, ref, contract = await work_contract(tmp_path)
    context = runner._start_context(ref, contract, {})
    request = {'contract_ref': ref, 'invocation_id': context.invocation_id,
               'execution_id': context.execution_id}
    with pytest.raises(ResearchError):
        if operation == 'model':
            runner.authorize_model_context({'execution_id': context.execution_id, 'call_ordinal': 1})
        elif operation == 'executor':
            runner.authorize_executor_binding(request)
        else:
            # An unknown tool would be denied even in an active context. Use
            # its actual declared allowance and prove preparation is the reason.
            runner.authorize_tool_call({'execution_id': context.execution_id,
                'tool_ordinal': 1, 'operation': 'arxiv'})
    assert not list(store.iter_records(kinds=('model-call-claim', 'tool-call-claim')))
    preparations = list(store.iter_records(kinds=('invocation-preparation',)))
    assert len(preparations) == 1, 'An actual inert invocation must retain its original preparation'
    assert not list(store.iter_records(kinds=('invocation-observation', 'gate-decision', 'dispatch-start')))
    store.close()


@pytest.mark.asyncio
async def test_inert_preparation_is_exact_once_and_preserves_original_deadline(tmp_path):
    import copy
    import time
    from jiuwenswarm.research.contracts import validate
    from tests.unit_tests.research.test_budget_ceiling import work_contract
    store, runner, ref, contract = await work_contract(tmp_path)
    context = runner._start_context(ref, contract, {})
    preparations = list(store.iter_records(kinds=('invocation-preparation',)))
    assert len(preparations) == 1, 'Construction must prepare rather than start'
    original = preparations[0]
    validate('urn:ai4r:private:invocation-preparation:1', original['record'])
    binding = {'contract_ref': ref, 'invocation_id': context.invocation_id,
               'execution_id': context.execution_id}
    first = runner.authorize_executor_preparation(binding)
    assert set(first) == {'contract_ref', 'invocation_id', 'execution_id', 'contract',
        'preparation_ref', 'execution_deadline_monotonic_s', 'remaining_time_s'}
    assert first['preparation_ref'] == original['ref'] and first['contract'] == contract
    assert first['execution_deadline_monotonic_s'] > time.monotonic()
    assert 0 < first['remaining_time_s'] <= contract['subnode_limits']['time_s']
    second = runner.authorize_executor_preparation(binding)
    assert second['execution_deadline_monotonic_s'] == first['execution_deadline_monotonic_s']
    assert second['remaining_time_s'] <= first['remaining_time_s']
    before = copy.deepcopy(original['record'])
    await runner._await_start(context)
    assert store.read_record(original['ref']) == before
    with pytest.raises(ResearchError):
        runner.authorize_executor_preparation(binding)
    with pytest.raises(ResearchError):
        runner._start_context(ref, contract, {})
    active = runner.authorize_model_context({'execution_id': context.execution_id, 'call_ordinal': 1})
    assert active['execution_deadline_monotonic_s'] <= first['execution_deadline_monotonic_s']
    assert len(list(store.iter_records(kinds=('model-call-claim',)))) == 1
    store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('stop', ['cancel', 'deadline'])
async def test_stopped_inert_preparation_never_starts_or_refunds_once(tmp_path, monkeypatch, stop):
    from tests.unit_tests.research.test_budget_ceiling import work_contract
    store, runner, ref, contract = await work_contract(tmp_path)
    context = runner._start_context(ref, contract, {})
    preparations = list(store.iter_records(kinds=('invocation-preparation',)))
    assert len(preparations) == 1, 'Original preparation must precede stop'
    if stop == 'cancel':
        store.request_cancellation(contract['run_id'], 'alice', 'cancel:prepared')
    else:
        import jiuwenswarm.research.runner as module
        observed = module.time.monotonic
        deadline = runner._executions[context.execution_id]['deadline']
        monkeypatch.setattr(module.time, 'monotonic', lambda: deadline + 1)
    with pytest.raises(ResearchError):
        await runner._await_start(context)
    with pytest.raises(ResearchError):
        runner._start_context(ref, contract, {})
    assert len(list(store.iter_records(kinds=('invocation-preparation',)))) == 1
    assert not list(store.iter_records(kinds=('model-call-claim', 'tool-call-claim',
        'invocation-observation', 'gate-decision', 'dispatch-start')))
    if stop == 'deadline':
        monkeypatch.setattr(module.time, 'monotonic', observed)
    store.close()


@pytest.mark.asyncio
async def test_inert_preparation_record_cannot_register_a_reconstructed_runner(tmp_path):
    from jiuwenswarm.research.runner import CapsuleRunner
    from tests.unit_tests.research.test_budget_ceiling import work_contract
    store, runner, ref, contract = await work_contract(tmp_path)
    context = runner._start_context(ref, contract, {})
    assert len(list(store.iter_records(kinds=('invocation-preparation',)))) == 1, \
        'Actual preparation original is required before reconstruction'
    replacement = CapsuleRunner(store, runner.registry, runner.check_registry,
        model=runner.model, check_assets=runner.check_assets)
    binding = {'contract_ref': ref, 'invocation_id': context.invocation_id,
               'execution_id': context.execution_id}
    with pytest.raises(ResearchError):
        replacement.authorize_executor_preparation(binding)
    assert runner.authorize_executor_preparation(binding)['contract_ref'] == ref
    assert not list(store.iter_records(kinds=('model-call-claim', 'invocation-observation')))
    store.close()
