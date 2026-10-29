"""Protected native wire capture mechanics; controlled protocol, no model claim."""
import asyncio
import json
from pathlib import Path

import pytest

from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError
from tests.unit_tests.runtime.test_codex_subscription import FakeTransport


class WireTransport(FakeTransport):
    """Explicit wire observer transport double with exact owned packet bytes."""
    def __init__(self):
        super().__init__();self.wire_listeners=set();self.wire_sequence=0;self.raw=[];self.closed=0
    def emit(self,method,params):
        value={'method':method,'params':params}
        raw=('  '+json.dumps(value,separators=(', ', ': '))+' \n').encode()
        self.raw.append(('in',raw,value))
        for observe in tuple(self.wire_listeners):observe('in',raw,value)
        super().emit(method,params)
    async def request(self,method,params=None,*,wire_observer=None):
        self.wire_sequence+=1;ident=self.wire_sequence
        value={'id':ident,'method':method,'params':params or {}}
        raw=(json.dumps(value)+'\n').encode();self.raw.append(('out',raw,value))
        if wire_observer:wire_observer('out',raw,value)
        try:result=await super().request(method,params)
        except BaseException:
            error={'id':ident,'error':{'code':-1,'message':'Controlled protocol failure'}}
            raw=(json.dumps(error)+'\n').encode();self.raw.append(('in',raw,error))
            if wire_observer:wire_observer('in',raw,error)
            raise
        response={'id':ident,'result':result}
        raw=(' '+json.dumps(response)+'\n').encode();self.raw.append(('in',raw,response))
        if wire_observer:wire_observer('in',raw,response)
        return result
    async def close(self):
        self.closed+=1
        await super().close()


@pytest.fixture
def traced(tmp_path):
    store=SQLiteRunStore(tmp_path/'records');transport=WireTransport()
    service=SubscriptionService(tmp_path/'native',transport=transport)
    pin=store.put_blob(b'actual controlled protected start')
    scope={'run_id':'run:trace','node_id':'intent','subnode_id':'intent','attempt_id':'attempt:trace',
        'execution_id':'execution:trace','invocation_id':'invocation:trace','call_id':'PRIVATE-CALL-FINGERPRINT',
        'contract_ref':pin,'model_call_start_ref':pin}
    try:yield store,service,transport,scope
    finally:store.close()


@pytest.mark.asyncio
async def test_traced_call_requires_protected_writer_before_any_native_effect(traced):
    _,service,transport,scope=traced
    with pytest.raises(CodexError,match='AUDIT_UNAVAILABLE'):
        await service.invoke_governed_traced(scope,'controlled prompt',timeout_s=2)
    assert transport.calls==[]


@pytest.mark.asyncio
async def test_exact_owned_packets_are_retained_without_local_scope_on_provider_wire(traced):
    store,service,transport,scope=traced
    service.set_governed_trace_writer(store.append_record,store.put_blob)
    result=await service.invoke_governed_traced(scope,'controlled prompt',timeout_s=2)
    summary=store.read_record(result['native_trace_ref'])
    assert summary['scope']==scope and summary['status']=='completed'
    events=[store.read_record(ref) for ref in summary['event_refs']]
    assert [e['sequence'] for e in events]==list(range(len(events)))
    raw=[store.read_blob(e['raw_ref']) for e in events]
    assert any(packet.startswith(b'  ') and packet.endswith(b' \n') for packet in raw)
    assert not any(b'LEAK' in packet or b'fixture@example.invalid' in packet for packet in raw)
    assert all(b'PRIVATE-CALL-FINGERPRINT' not in packet for packet in raw)
    assert {e['method'] for e in events}=={'thread/start','turn/start','item/agentMessage/delta','turn/completed'}
    assert all(e['scope']==scope and e['direction'] in {'in','out'} for e in events)
    assert result['text']=='Hello' and not service.active and not transport.wire_listeners


@pytest.mark.asyncio
async def test_trace_write_failure_before_thread_request_prevents_dispatch(traced):
    store,service,transport,scope=traced
    def fail(*_args,**_kwargs):raise OSError('controlled storage failure')
    service.set_governed_trace_writer(fail,store.put_blob)
    with pytest.raises(CodexError,match='AUDIT_UNAVAILABLE'):
        await service.invoke_governed_traced(scope,'controlled prompt',timeout_s=2)
    assert not any(method in {'thread/start','turn/start'} for method,_ in transport.calls)
    assert not service.active and not transport.wire_listeners


@pytest.mark.asyncio
@pytest.mark.parametrize('fail_turn', [False, True])
async def test_actual_bridge_joins_native_trace_on_success_and_failure(traced, fail_turn):
    from jiuwenswarm.research.bridge import GovernedBridge, BridgeError
    from tests.unit_tests.research.test_bridge import authorized_context
    store,service,transport,_=traced;transport.fail_turn=fail_turn
    context=authorized_context();context['contract_ref']=store.put_blob(b'controlled contract')
    service.set_governed_trace_writer(store.append_record,store.put_blob)
    bridge=GovernedBridge(persist=store.append_record,authorize=lambda _:context,revalidate=lambda _:context,
        subscription_service=service,read_evidence=store.read_blob)
    if fail_turn:
        with pytest.raises(BridgeError):await bridge.call({},'controlled prompt')
    else:
        assert (await bridge.call({},'controlled prompt'))['text']=='Hello'
    calls=list(store.iter_records(kinds={'model-call'}));assert len(calls)==1
    call=store.read_record(calls[0]['ref'])
    traces=list(store.iter_records(kinds={'native-governed-trace'}));assert len(traces)==1
    assert traces[0]['ref'] in call['evidence_refs']
    summary=store.read_record(traces[0]['ref'])
    assert summary['scope']['call_id']==call['id'] and summary['scope']['contract_ref']==context['contract_ref']
    assert summary['status']==('failed' if fail_turn else 'completed')


class PacketProcess:
    def __init__(self):
        self.stdout=asyncio.StreamReader();self.stdin=self;self.writes=[];self.returncode=None
    def write(self,raw):self.writes.append(raw)
    async def drain(self):pass
    def terminate(self):self.returncode=0


@pytest.mark.asyncio
async def test_real_transport_observer_precedes_write_and_retains_original_response(tmp_path):
    from jiuwenswarm.server.runtime.codex_subscription.transport import AppServerTransport
    transport=AppServerTransport(tmp_path);process=PacketProcess();transport.process=process
    observed=[]
    def observe(direction,raw,envelope):
        if direction=='out':assert not process.writes
        observed.append((direction,raw,envelope))
    request=asyncio.create_task(transport.request('thread/start',{'ephemeral':True},wire_observer=observe))
    while not process.writes:await asyncio.sleep(0)
    original=b'  { "id": 1, "result": {"thread": {"id": "actual-thread"}} }  \n'
    process.stdout.feed_data(original);process.stdout.feed_eof()
    await transport._read(process)
    assert (await request)['thread']['id']=='actual-thread'
    assert observed[1][1]==original and observed[0][1]==process.writes[0]
    assert not transport.pending and not transport._wire_observers


@pytest.mark.asyncio
async def test_real_transport_audit_failure_never_reports_success(tmp_path):
    from jiuwenswarm.server.runtime.codex_subscription.transport import AppServerTransport
    transport=AppServerTransport(tmp_path);process=PacketProcess();transport.process=process
    def observe(direction,*_):
        if direction=='in':raise CodexError('AUDIT_UNAVAILABLE')
    request=asyncio.create_task(transport.request('turn/start',{},wire_observer=observe))
    while not process.writes:await asyncio.sleep(0)
    process.stdout.feed_data(b'{"id":1,"result":{"turn":{"id":"owned"}}}\n')
    await transport._read(process)
    with pytest.raises(CodexError,match='AUDIT_UNAVAILABLE'):await request
    assert process.returncode==0 and not transport.pending and not transport._wire_observers


@pytest.mark.asyncio
async def test_rejected_server_request_is_reported_as_unsupported_tool_activity(tmp_path):
    from jiuwenswarm.server.runtime.codex_subscription.transport import AppServerTransport
    transport=AppServerTransport(tmp_path);process=PacketProcess();transport.process=process
    observed=[];transport.listeners.add(lambda method,params: observed.append((method,params)))
    process.stdout.feed_data(b'{"id":7,"method":"item/commandExecution/requestApproval","params":{"threadId":"owned"}}\n')
    process.stdout.feed_eof()
    await transport._read(process)
    # EOF closes the reader after the request, so the owned-turn observer also
    # receives the transport terminal event.
    assert observed==[("transport/unsupported-request",{}),("transport/closed",{})]
    assert json.loads(process.writes[0])['error']['code']==-32601


@pytest.mark.asyncio
async def test_large_payload_is_original_evidence_beyond_display_truncation(traced):
    store,service,transport,scope=traced
    original_emit=transport.emit;large='original controlled text '*16000
    def emit(method,params):
        if method=='item/agentMessage/delta' and params['threadId']!='foreign':params=dict(params,delta=large)
        original_emit(method,params)
    transport.emit=emit;service.set_governed_trace_writer(store.append_record,store.put_blob)
    result=await service.invoke_governed_traced(scope,'controlled prompt',timeout_s=5)
    assert result['text']==large
    events=[store.read_record(ref) for ref in store.read_record(result['native_trace_ref'])['event_refs']]
    packets=[store.read_blob(event['raw_ref']) for event in events if event['method']=='item/agentMessage/delta']
    assert len(packets)==1 and len(packets[0])>300000
    assert json.loads(packets[0])['params']['delta']==large


@pytest.mark.asyncio
async def test_late_storage_failure_retains_partial_trace_and_refuses_success(traced):
    store,service,transport,scope=traced
    def append(kind,record):
        if kind=='native-governed-trace-event' and record['method']=='item/agentMessage/delta':
            raise OSError('Controlled late storage failure')
        return store.append_record(kind,record)
    service.set_governed_trace_writer(append,store.put_blob)
    with pytest.raises(CodexError,match='AUDIT_UNAVAILABLE') as error:
        await service.invoke_governed_traced(scope,'controlled prompt',timeout_s=5)
    summary=store.read_record(error.value.native_trace_ref)
    assert summary['status']=='failed' and summary['event_refs']
    assert sum(method=='turn/start' for method,_ in transport.calls)==1
    assert not service.active and not transport.wire_listeners


@pytest.mark.asyncio
async def test_timeout_retains_interrupt_terminal_without_replay(traced):
    store,service,transport,scope=traced;transport.hold_turn=True
    service.set_governed_trace_writer(store.append_record,store.put_blob)
    with pytest.raises(CodexError,match='RUNTIME_TIMEOUT') as error:
        await service.invoke_governed_traced(scope,'controlled prompt',timeout_s=1)
    summary=store.read_record(error.value.native_trace_ref)
    assert summary['status']=='failed'
    assert any(store.read_record(ref)['method']=='turn/interrupt' for ref in summary['event_refs'])
    assert sum(method=='turn/start' for method,_ in transport.calls)==1


def test_thread_notification_before_start_reply_preserves_original_order(traced):
    from jiuwenswarm.server.runtime.codex_subscription.governed_trace import GovernedTrace
    store,_,_,scope=traced;trace=GovernedTrace(scope,store.append_record,store.put_blob)
    observe=trace.request_observer('thread/start')
    observe('out',b'{"id":1,"method":"thread/start"}\n',{'id':1,'method':'thread/start'})
    packet={'method':'thread/started','params':{'thread':{'id':'owned'}}}
    trace.notification('in',b' {"method":"thread/started","params":{"thread":{"id":"owned"}}}\n',packet)
    observe('in',b'{"id":1,"result":{"thread":{"id":"owned"}}}\n',{'id':1,'result':{'thread':{'id':'owned'}}})
    assert [store.read_record(ref)['method'] for ref in trace.event_refs]==['thread/start','thread/started','thread/start']


@pytest.mark.asyncio
async def test_failed_turn_retains_original_scope_and_terminal_failure_trace(traced):
    store,service,transport,scope=traced;transport.fail_turn=True
    service.set_governed_trace_writer(store.append_record,store.put_blob)
    with pytest.raises(CodexError) as error:
        await service.invoke_governed_traced(scope,'controlled prompt',timeout_s=2)
    summary=store.read_record(error.value.native_trace_ref)
    assert summary['status']=='failed' and summary['scope']==scope
    assert any(b'Controlled protocol failure' in store.read_blob(store.read_record(ref)['raw_ref']) for ref in summary['event_refs'])
    assert sum(method=='turn/start' for method,_ in transport.calls)==1
    assert not service.active and not transport.wire_listeners


@pytest.mark.asyncio
async def test_cancellation_awaits_native_terminal_and_preserves_interrupt_packets(traced):
    store,service,transport,scope=traced;transport.hold_turn=True
    service.set_governed_trace_writer(store.append_record,store.put_blob)
    task=asyncio.create_task(service.invoke_governed_traced(scope,'controlled prompt',timeout_s=5))
    async with asyncio.timeout(5):
        while not any(method=='turn/start' for method,_ in transport.calls):
            if task.done():await task
            await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError) as error:await task
    summary=store.read_record(error.value.native_trace_ref)
    assert summary['status']=='interrupted'
    events=[store.read_record(ref) for ref in summary['event_refs']]
    assert any(e['method']=='turn/interrupt' and e['direction']=='out' for e in events)
    assert any(b'interrupted' in store.read_blob(e['raw_ref']) for e in events)
    assert not service.active and not transport.wire_listeners
