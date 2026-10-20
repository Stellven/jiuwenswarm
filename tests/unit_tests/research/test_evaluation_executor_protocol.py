"""IF016 native receiver controls; controlled IPC, never runtime qualification.

Initial negative population gives a real finite authorization socket a deliberately
unowned field-compatible reply. No fake backend may accept or execute it.
Registered-owner positive controls will use the owning core's actual fixture.
"""
import copy
import json
import os
import time

import pytest

from jiuwenswarm.research.executor import ExecutorBlocked
from jiuwenswarm.research.executor_rpc import ClaimLedger, ExecutionOperations
from jiuwenswarm.research.native_ports import AUTH_PROTOCOL
from jiuwenswarm.research.private_rpc import PrivateRPCClient, PrivateRPCServer
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes


async def owned_execution(tmp_path):
    """Use the real core owner, approved slot and projection, without dispatch."""
    from tests.unit_tests.research.test_evaluation_authority import source_fixture, capture_runtime, product_state
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    authority = provider.resources.bind_runtime(capture_runtime(store, provider, [request]))
    request_ref = authority.accept_request(actor, request, 'E3')
    scope_ref = authority.prepare(request_ref)
    grant_ref = authority.prepare_assignment(scope_ref, 'worker', None)
    grant = store.read_record(grant_ref)
    context=authority.start_assignment(grant_ref, authority.runner._decode_inputs(store.read_record(grant['contract_ref'])))
    await authority.runner._await_start(context)
    return store, authority, grant, prompts, product_state


def kernel_without_effect_resources(tmp_path):
    from jiuwenswarm.research.executor import RestrictedExecutor
    # This is the installed backend itself, with no job factories or kernel
    # resources. A binding test grants no ability to run a scientific job.
    return RestrictedExecutor(workspace_root=tmp_path/'work', cgroup_root=None,
        authorize_job=lambda _: pytest.fail('Binding control launched a kernel job'),
        capture=lambda _: pytest.fail('Binding control captured a kernel effect'))


@pytest.mark.asyncio
async def test_actual_registered_private_owner_binds_unchanged_context_over_unix_ipc(tmp_path):
    store, authority, grant, prompts, product_state = await owned_execution(tmp_path/'source')
    from jiuwenswarm.research.evaluation_executor import EvaluationExecutorAdapter
    ledger = ClaimLedger(tmp_path/'ledger')
    backend = kernel_without_effect_resources(tmp_path)
    adapter = EvaluationExecutorAdapter(store, backend)
    request = {key:grant[key] for key in ('contract_ref','invocation_id','execution_id')}
    seen = []
    def owned_response(payload):
        seen.append(copy.deepcopy(payload))
        return authority.runner.authorize_executor_binding(payload)
    server = PrivateRPCServer(tmp_path/'authorization.sock', protocol=AUTH_PROTOCOL,
        session_id='owned-protocol',capability='owned-protocol-capability',
        handlers={'authorize_executor_binding':owned_response},allowed_uids={os.geteuid()})
    client = PrivateRPCClient(server.path,protocol=AUTH_PROTOCOL,peer_uid=os.geteuid(),
        session_id='owned-protocol',capability='owned-protocol-capability')
    async def authorize(payload):return await client.call('authorize_executor_binding',payload)
    operations = ExecutionOperations(backend=backend,authorize=authorize,
        resolve_inputs=lambda _:pytest.fail('Binding control decoded inputs'),ledger=ledger,
        evaluation_adapter=adapter)
    before = product_state(store)
    try:
        await server.start()
        actual_request, context, bound, _, deadline = await operations._binding(request,set())
        assert actual_request == request and seen == [request]
        assert context == store.read_record(grant['contract_ref'])
        assert context['schema'] == 'ai4r-evaluation-subnode-context:1' and 'schema_version' not in context
        assert bound._binding.contract == context and bound._binding.contract_ref == grant['contract_ref']
        assert bound._binding.execution_id == grant['execution_id'] and bound._binding.invocation_id == grant['invocation_id']
        assert 0 < deadline-time.monotonic() <= grant['limits']['time_s']
        second = await operations._binding(request,set())
        assert second[2] is bound and seen == [request,request]
        assert second[4] == deadline
        assert context['bindings'][0]['effective_authority']['tools']==[]
        for operation in ('provision','hardware_inventory','collect_builder','builder_observation'):
            with pytest.raises(ExecutorBlocked,match='EVALUATION_EXECUTOR_OPERATION_ADAPTER_UNAVAILABLE'):
                await operations.perform(operation,request)
        assert prompts == [] and product_state(store) == before
        assert ledger.db.execute('SELECT COUNT(*) FROM claims').fetchone()[0] == 0
        assert not operations.jobs and not operations.active_tasks
    finally:
        await server.close();ledger.close();store.close()


@pytest.mark.asyncio
async def test_private_adapter_rejects_changed_closed_response_before_binding(tmp_path):
    store, authority, grant, prompts, product_state = await owned_execution(tmp_path/'source')
    from jiuwenswarm.research.evaluation_executor import EvaluationExecutorAdapter
    ledger=ClaimLedger(tmp_path/'ledger');backend=kernel_without_effect_resources(tmp_path)
    request={key:grant[key] for key in ('contract_ref','invocation_id','execution_id')}
    before=product_state(store)
    faults=['extra','missing','identity','context','canonical_alias','untyped_context','deadline_bool','deadline_nan',
            'remaining_bool','remaining_infinite','remaining_widened']
    observed=[]
    try:
        for fault in faults:
            response=authority.runner.authorize_executor_binding(request)
            if fault=='extra':response['authorized']=True
            if fault=='missing':response.pop('remaining_time_s')
            if fault=='identity':response['invocation_id']='foreign-invocation'
            if fault=='context':response['contract']['inputs']=[]
            if fault=='canonical_alias':response['contract'].pop('schema');response['contract']['schema_version']='1.0.0'
            if fault=='untyped_context':response['contract']={'run_id':response['contract']['run_id']}
            if fault=='deadline_bool':response['execution_deadline_monotonic_s']=True
            if fault=='deadline_nan':response['execution_deadline_monotonic_s']=float('nan')
            if fault=='remaining_bool':response['remaining_time_s']=True
            if fault=='remaining_infinite':response['remaining_time_s']=float('inf')
            if fault=='remaining_widened':response['remaining_time_s']+=1000
            operations=ExecutionOperations(backend=backend,authorize=lambda _:copy.deepcopy(response),
                resolve_inputs=lambda _:pytest.fail('Invalid reply decoded inputs'),ledger=ledger,
                evaluation_adapter=EvaluationExecutorAdapter(store,backend))
            with pytest.raises(ExecutorBlocked):await operations._binding(request,set())
            assert not operations.bound and not operations.jobs and not operations.active_tasks, fault
            assert ledger.db.execute('SELECT COUNT(*) FROM claims').fetchone()[0]==0, fault
            assert prompts==[] and product_state(store)==before, fault
            observed.append(fault)
        assert observed==faults
    finally:ledger.close();store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['completed','failed'])
async def test_native_bridge_packets_join_actual_private_claim_without_second_append(tmp_path,outcome):
    from jiuwenswarm.research.bridge import BridgeError, GovernedBridge
    from jiuwenswarm.research.contracts import validate
    store, authority, grant, prompts, product_state = await owned_execution(tmp_path/'source')
    from jiuwenswarm.research.native_ports import capture_native_record, capture_governed_trace_record
    from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
    from tests.unit_tests.runtime.test_codex_governed_trace import WireTransport
    transport=WireTransport();transport.fail_turn=outcome=='failed'
    subscription=SubscriptionService(tmp_path/'native',transport=transport)
    subscription.set_governed_trace_writer(lambda kind,record:capture_governed_trace_record(store,kind,record),store.put_blob)
    captures=[]
    def capture(kind,record,*,context):
        ref=capture_native_record(store,kind,record,context=context)
        captures.append((kind,copy.deepcopy(record),ref))
        return ref
    bridge=GovernedBridge(persist=lambda *_:pytest.fail('Private packet used unscoped persistence'),
        authorize=authority.runner.authorize_model_context,revalidate=authority.runner.authorize_model_dispatch,
        subscription_service=subscription,validate_record=validate,capture_native=capture,read_evidence=store.read_blob)
    before=product_state(store)
    try:
        if outcome=='failed':
            with pytest.raises(BridgeError,match='provider_error'):
                await bridge.call({'execution_id':grant['execution_id'],'call_ordinal':1},'The source-bound worker body.')
        else:
            result=await bridge.call({'execution_id':grant['execution_id'],'call_ordinal':1},'The source-bound worker body.')
            assert result['text']=='Hello'
        kinds=[kind for kind,_,_ in captures]
        assert kinds[:3]==['route-record','model-call-input','model-call-start']
        assert kinds[-1]=='model-call' and kinds.count('model-call')==1
        expected={'route-record':'route','model-call-input':'prompt','model-call-start':'model_start',
                  'model-call-output':'output','model-call':'model_call'}
        events=[entry['record'] for entry in store.iter_records(kinds=('evaluation-event',))]
        for kind,record,ref in captures:
            assert store.record_kind(ref)==kind and store.read_record(ref)==record
            matches=[event for event in events if event['kind']=='captured' and event['capture_ref']==ref]
            assert len(matches)==1 and matches[0]['capture_kind']==expected[kind]
            assert matches[0]['assignment_grant_ref']==json.loads(authority._assignment(grant['execution_id'])['grant_ref'])
        traces=list(store.iter_records(kinds=('native-governed-trace',)))
        assert len(traces)==1
        summary=traces[0]['record']
        assert summary['status']==('failed' if outcome=='failed' else 'completed')
        assert summary['scope']['contract_ref']==grant['contract_ref']
        assert summary['scope']['execution_id']==grant['execution_id']
        assert summary['event_refs']
        for ref in [traces[0]['ref'],*summary['event_refs']]:
            matches=[event for event in events if event['kind']=='captured' and event['capture_ref']==ref]
            assert len(matches)==1 and matches[0]['capture_kind']=='trace'
        for ref in summary['event_refs']:
            packet=store.read_record(ref)
            assert packet['scope']==summary['scope']
            raw=store.read_blob(packet['raw_ref'])
            assert raw in [row[1] for row in transport.raw]
            assert b'LEAK' not in raw and grant['execution_id'].encode() not in raw
        claim=store.connection.execute('SELECT claim_ref FROM evaluation_calls WHERE execution_id=?',(grant['execution_id'],)).fetchone()
        assert claim is not None
        assert product_state(store)==before and prompts==[]
        assert not list(store.iter_records(kinds=('gate-decision','acceptance-commit','execution-receipt')))
    finally:store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['raw_blob', 'forged_private_kind'], ids=['no-indexed-kind', 'unregistered-private-kind'])
async def test_private_reply_without_registered_custody_cannot_reach_backend_binding(tmp_path, kind):
    """A compatible mapping and an authenticated peer do not mint IF016 authority."""
    store = SQLiteRunStore(tmp_path / 'state')
    ledger = ClaimLedger(tmp_path / 'ledger')
    contract = {'schema':'ai4r-evaluation-subnode-context:1','id':'unit-unowned-context',
                'run_id':'unit-private-run','accepted':False,'invalid_for_product':True}
    contract_ref = (store.put_blob(json_bytes(contract)) if kind == 'raw_blob' else
                    store.append_record('evaluation-subnode-context',contract))
    request = {'contract_ref':contract_ref,'invocation_id':'unit-private-invocation','execution_id':'unit-private-execution'}
    received = []
    def unowned_response(actual):
        received.append(copy.deepcopy(actual))
        assert actual == request
        return {**copy.deepcopy(request),'contract':contract,'execution_deadline_monotonic_s':time.monotonic()+10,
                'remaining_time_s':10.0}
    class NoEffectsBackend:
        def bind_invocation(self, **kwargs):
            pytest.fail('Unowned private mapping reached backend.bind_invocation')
    # This socket is test-owned with its actual UID. Production root-only
    # authorize_executor_binding UID restrictions remain separately required.
    server = PrivateRPCServer(tmp_path/'authorization.sock', protocol=AUTH_PROTOCOL,
        session_id='if016-unit-session',capability='if016-unit-capability',
        handlers={'authorize_executor_binding':unowned_response},allowed_uids={os.geteuid()})
    client = PrivateRPCClient(server.path,protocol=AUTH_PROTOCOL,peer_uid=os.geteuid(),
        session_id='if016-unit-session',capability='if016-unit-capability')
    async def authorize(payload):
        return await client.call('authorize_executor_binding',payload)
    operations = ExecutionOperations(backend=NoEffectsBackend(),authorize=authorize,
        resolve_inputs=lambda _:pytest.fail('Unowned private mapping reached input decoding'),ledger=ledger)
    try:
        await server.start()
        with pytest.raises(ExecutorBlocked):
            await operations.perform('hardware_inventory',request)
        assert received == [request]
        assert not operations.bound and not operations.jobs and not operations.active_tasks
        assert ledger.db.execute('SELECT COUNT(*) FROM claims').fetchone()[0] == 0
        assert not list(store.iter_records(kinds=('model-call-start','model-call','gate-decision','library-admission')))
    finally:
        await server.close()
        ledger.close()
        store.close()
