"""Pre-call persistence, authority, fixed-route and no-replay expectations."""
import copy
import hashlib
import json
from time import monotonic

import pytest

from jiuwenswarm.research.bridge import BridgeError, GovernedBridge
from jiuwenswarm.research.router_client import PlatformIntegrityError


def authorized_context():
    ref = {"id": "pin", "sha256": "a" * 64}
    return {"run_id": "run", "node_id": "node", "subnode_id": "worker", "attempt_id": "attempt",
            "invocation_id": "invocation", "execution_id": "execution", "call_ordinal": 1,
            "call_id": "call:fixture", "call_claim_ref": ref, "contract_ref": ref,
            "call_function": "worker", "model_selection_profile_ref": ref, "deployment_ref": ref,
            "limits": {"time_s": 1, "model_calls": 1, "memory_mb": 64},
            "execution_deadline_monotonic_s": monotonic() + 1,
            "router": {"enabled": False, "deadline_s": 30, "profile_ref": None}}


class Ledger:
    def __init__(self):
        self.records = []
        self.fail_kind = None

    def append(self, kind, record):
        if kind == self.fail_kind:
            raise OSError("protected persistence failure")
        self.records.append((kind, copy.deepcopy(record)))
        return {"id": record.get("id", record.get("route_id")), "sha256": hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()}

    def read(self,ref):
        for _,record in self.records:
            raw=json.dumps(record,sort_keys=True).encode()
            if record.get('id',record.get('route_id'))==ref['id'] and hashlib.sha256(raw).hexdigest()==ref['sha256']:return raw
        raise ValueError('unknown immutable evidence')


class Provider:
    def __init__(self, ledger):
        self.ledger = ledger
        self.calls = 0
        self.fail = False

    async def invoke_governed(self, prompt, **kwargs):
        assert any(k == "route-record" for k, _ in self.ledger.records)
        assert any(k == "model-call-start" for k, _ in self.ledger.records)
        self.calls += 1
        if self.fail:
            raise ConnectionResetError("private-provider-error")
        return {"text": "answer", "identity": {"effective": "observed", "basis": "provider"},
                "usage": {"input_tokens": 7, "output_tokens": 2}, "observed_runtime": True}


def make_bridge(ledger, provider, authorize=None):
    return GovernedBridge(persist=ledger.append, authorize=authorize or (lambda _: authorized_context()),
                          revalidate=lambda _: authorized_context(), subscription_service=provider)


@pytest.mark.asyncio
async def test_failed_native_capture_blocks_spend_and_latches_result_rejection():
    ledger = Ledger()
    provider = Provider(ledger)
    healthy = False
    claims = []
    bridge = GovernedBridge(persist=ledger.append, subscription_service=provider,
        authorize=lambda _: claims.append(True) or authorized_context(), revalidate=lambda _: authorized_context(), health_check=lambda: healthy)
    with pytest.raises(BridgeError, match="AUDIT_UNAVAILABLE"):
        await bridge.call({}, "prompt")
    assert not claims and provider.calls == 0
    healthy = True
    class CaptureFailure(Provider):
        async def invoke_governed(self, *args, **kwargs):
            nonlocal healthy
            result = await super().invoke_governed(*args, **kwargs)
            healthy = False
            return result
    provider = CaptureFailure(ledger)
    bridge.subscription = provider
    with pytest.raises(BridgeError):
        await bridge.call({}, "prompt")
    assert provider.calls == 1
    assert not any(k == "model-call-output" for k, _ in ledger.records)
    assert next(r for k, r in ledger.records if k == "model-call")["outcome"] != "completed"
    with pytest.raises(BridgeError, match="AUDIT_UNAVAILABLE"):
        await bridge.call({}, "prompt")
    assert provider.calls == 1 and len(claims) == 1


@pytest.mark.asyncio
async def test_route_and_start_persist_before_one_actual_adapter_invocation():
    ledger = Ledger()
    provider = Provider(ledger)
    result = await make_bridge(ledger, provider).call({}, "governed prompt")
    assert result["text"] == "answer"
    assert provider.calls == 1
    final = next(r for k, r in ledger.records if k == "model-call")
    route = next(r for k, r in ledger.records if k == "route-record")
    assert final["identity"]["requested"] == route["model_id"] == "codex-cli-default"
    assert final["usage"]["cost_amount"] is None
    assert final["route_decision_ref"] is None
    assert final["model_selection_profile_ref"] is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["route-record", "model-call-start"])
async def test_failed_persistence_prevents_provider_effect(kind):
    ledger = Ledger()
    ledger.fail_kind = kind
    provider = Provider(ledger)
    with pytest.raises(BridgeError):
        await make_bridge(ledger, provider).call({}, "prompt")
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_invalid_authority_never_uses_codex_fallback():
    ledger = Ledger()
    provider = Provider(ledger)
    def reject(_):
        raise PlatformIntegrityError("forged")
    with pytest.raises(PlatformIntegrityError):
        await make_bridge(ledger, provider, reject).call({}, "prompt")
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_network_failure_retains_one_attempt_and_no_provider_error_text():
    ledger = Ledger()
    provider = Provider(ledger)
    provider.fail = True
    with pytest.raises(BridgeError, match="network_error"):
        await make_bridge(ledger, provider).call({}, "prompt")
    assert provider.calls == 1
    assert "private-provider-error" not in json.dumps(ledger.records)
    final = next(r for k, r in ledger.records if k == "model-call")
    assert final["outcome"] == "outcome_unknown"
    assert final["provider_error_code"] is None
    assert final["usage"]["input_tokens"] is None


@pytest.mark.asyncio
async def test_authorizer_must_return_durable_call_claim():
    ledger = Ledger()
    provider = Provider(ledger)
    data = authorized_context()
    data.pop("call_claim_ref")
    with pytest.raises(PlatformIntegrityError):
        await make_bridge(ledger, provider, lambda _: data).call({}, "prompt")
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_router_elapsed_time_and_live_dispatch_allowance_narrow_provider(monkeypatch):
    from jiuwenswarm.research import bridge as module
    from jiuwenswarm.research.router_client import RouteChoice
    clock = [monotonic()]
    monkeypatch.setattr(module, 'monotonic', lambda: clock[0])
    protected = authorized_context()
    protected['execution_deadline_monotonic_s'] = clock[0] + 1
    dispatches = []
    class Router:
        async def select(self, context):
            clock[0] += .4
            return RouteChoice('codex-cli-default')
    class TimedProvider(Provider):
        async def invoke_governed(self, *args, **kwargs):
            assert 0 < kwargs['timeout_s'] <= .3
            return await super().invoke_governed(*args, **kwargs)
    def revalidate(payload):
        dispatches.append(payload)
        return dict(protected, limits=dict(protected['limits'], time_s=.3),
                    execution_deadline_monotonic_s=clock[0]+.3)
    ledger=Ledger();provider=TimedProvider(ledger)
    bridge=GovernedBridge(persist=ledger.append,authorize=lambda _:protected,
        revalidate=revalidate,subscription_service=provider,router_port=Router())
    await bridge.call({}, 'controlled deadline fixture')
    assert len(dispatches)==1 and set(dispatches[0])=={'execution_id','invocation_id','call_id','call_claim_ref','contract_ref'}
    assert provider.calls==1


@pytest.mark.asyncio
async def test_recheck_denial_after_route_retains_attempt_without_provider_effect():
    ledger=Ledger();provider=Provider(ledger)
    def reject(_):raise PlatformIntegrityError('stopped_before_dispatch')
    bridge=GovernedBridge(persist=ledger.append,authorize=lambda _:authorized_context(),
        revalidate=reject,subscription_service=provider)
    with pytest.raises(BridgeError):await bridge.call({}, 'controlled denial')
    assert provider.calls==0
    assert not any(k in {'model-call-start','model-call'} for k,_ in ledger.records)
    refusal=next(r for k,r in ledger.records if k=='model-call-refused')
    assert refusal['reason_code']=='dispatch_authorization_denied' and refusal['call_claim_ref']


@pytest.mark.asyncio
@pytest.mark.parametrize('terminal',['completed','budget_exceeded','timeout'])
async def test_builder_terminal_receipt_is_joined_before_success_or_failure(terminal):
    ledger=Ledger();provider=Provider(ledger);protected=authorized_context();protected['cc_name']='research.builder'
    evidence=[]
    class Builder:
        async def invoke(self,context,prompt,*,timeout_s):
            assert context['model_call_start_ref'] and context['input_ref'] and context['route_ref']
            receipt={key:context[key] for key in ('contract_ref','run_id','invocation_id','execution_id','call_id','route_ref','model_call_start_ref','input_ref')}
            ref=ledger.append('builder_execution',dict(receipt,id='builder:receipt',event_refs=[],output_refs=[],
                terminal_reason=terminal,credential_removed=True,observed_runtime=True))
            evidence.append(ref)
            return {'text':'builder answer' if terminal=='completed' else None,'identity':{},'usage':{},
                'outcome':'completed' if terminal=='completed' else 'outcome_unknown' if terminal=='timeout' else 'failed',
                'error_code':None if terminal=='completed' else terminal,'terminal_reason':terminal,'evidence_refs':[ref]}
    bridge=GovernedBridge(persist=ledger.append,authorize=lambda _:protected,revalidate=lambda _:protected,
        subscription_service=provider,builder_launcher=Builder(),read_evidence=ledger.read)
    if terminal=='completed':assert (await bridge.call({},'captured builder prompt'))['text']=='builder answer'
    else:
        with pytest.raises(BridgeError,match=terminal):await bridge.call({},'captured builder prompt')
    final=next(row for kind,row in ledger.records if kind=='model-call')
    assert evidence[0] in final['evidence_refs'] and provider.calls==0
    if terminal=='budget_exceeded':assert final['provider_error_code']=='invalid_request'


@pytest.mark.asyncio
async def test_builder_timeout_waits_for_already_issued_cleanup_and_retains_its_receipt():
    import asyncio
    ledger=Ledger();protected=authorized_context();protected['cc_name']='research.builder'
    protected['limits']['time_s']=.02;protected['execution_deadline_monotonic_s']=monotonic()+.02
    receipt_refs=[]
    class Builder:
        async def invoke(self,context,prompt,*,timeout_s):
            # Broker's effect deadline is independent; this models only its
            # terminal containment/capture delivery after that deadline.
            await asyncio.sleep(.04)
            receipt={key:context[key] for key in ('contract_ref','run_id','invocation_id','execution_id','call_id','route_ref','model_call_start_ref','input_ref')}
            ref=ledger.append('builder_execution',dict(receipt,id='builder:late-receipt',event_refs=[],output_refs=[],
                terminal_reason='timeout',credential_removed=True,observed_runtime=True));receipt_refs.append(ref)
            return {'text':None,'outcome':'outcome_unknown','error_code':'timeout','terminal_reason':'timeout','evidence_refs':[ref]}
    bridge=GovernedBridge(persist=ledger.append,authorize=lambda _:protected,revalidate=lambda _:protected,
        subscription_service=Provider(ledger),builder_launcher=Builder(),read_evidence=ledger.read)
    with pytest.raises(BridgeError,match='timeout'):await bridge.call({},'captured prompt')
    assert receipt_refs[0] in next(row for kind,row in ledger.records if kind=='model-call')['evidence_refs']


@pytest.mark.asyncio
@pytest.mark.parametrize('wrapped_timeout',[False,True])
async def test_failure_retains_observed_provider_telemetry_even_through_timeout_cause(wrapped_timeout):
    import asyncio
    ledger=Ledger()
    class FailedProvider:
        async def invoke_governed(self,*args,**kwargs):
            original=asyncio.CancelledError() if wrapped_timeout else BridgeError('invalid_output')
            original.observation={'identity':{'effective':'actually-observed-model','basis':'actual structured response'},
                'usage':{'input_tokens':17,'output_tokens':4},'provider_request_id':'actually-observed-request','observed_runtime':True}
            if wrapped_timeout:raise TimeoutError() from original
            raise original
    with pytest.raises(BridgeError):await make_bridge(ledger,FailedProvider()).call({},'controlled input')
    final=next(row for kind,row in ledger.records if kind=='model-call')
    captured=next(row for kind,row in ledger.records if kind=='model-provider-observation')
    assert final['identity']['effective']=='actually-observed-model'
    assert final['usage']['input_tokens']==17 and final['usage']['output_tokens']==4
    assert final['usage']['cost_amount'] is None
    assert final['provider_request_id']=='actually-observed-request'
    assert captured['observation']['usage']==final['usage']
    assert any(ref['id']==captured['id'] for ref in final['evidence_refs'])


@pytest.mark.asyncio
@pytest.mark.parametrize('wrapper',['cause','context','asyncio_timeout'])
async def test_failed_native_trace_survives_wrapped_cancellation(wrapper):
    """Real bridge retention and trace validator, no provider/model effect."""
    import asyncio
    ledger=Ledger();blobs={};trace_refs=[];calls=[]
    def store(value):
        raw=json.dumps(value,sort_keys=True).encode()
        digest=hashlib.sha256(raw).hexdigest()
        ref={'id':'blob:'+digest,'sha256':digest};blobs[ref['id']]=raw
        return ref
    class InterruptedProvider:
        async def invoke_governed_traced(self,scope,prompt,**kwargs):
            calls.append(prompt)
            raw_ref=store({'method':'item/agentMessage/delta','params':{'delta':'{"partial":'}})
            event_ref=store({'schema':'ai4r-native-governed-trace-event:1','scope':scope,
                'sequence':0,'direction':'in','method':'item/agentMessage/delta','raw_ref':raw_ref})
            trace=store({'schema':'ai4r-native-governed-trace:1','scope':scope,
                'status':'interrupted','event_refs':[event_ref]});trace_refs.append(trace)
            if wrapper=='asyncio_timeout':
                async with asyncio.timeout(.001):
                    try:await asyncio.sleep(1)
                    except asyncio.CancelledError as error:
                        error.native_trace_ref=trace
                        raise
            original=asyncio.CancelledError();original.native_trace_ref=trace
            if wrapper=='cause':raise TimeoutError() from original
            try:raise original
            except asyncio.CancelledError:raise TimeoutError()
    bridge=GovernedBridge(persist=ledger.append,authorize=lambda _:authorized_context(),
        revalidate=lambda _:authorized_context(),subscription_service=InterruptedProvider(),
        read_evidence=lambda ref:blobs[ref['id']])
    with pytest.raises(BridgeError,match='timeout'):await bridge.call({},'controlled prompt')
    final=next(row for kind,row in ledger.records if kind=='model-call')
    assert len(calls)==1 and trace_refs[0] in final['evidence_refs']
    assert final['evidence_refs'].count(trace_refs[0])==1
    assert final['outcome']=='outcome_unknown' and final['usage']['input_tokens'] is None
    assert not any(kind=='model-call-output' for kind,_ in ledger.records)


def test_failure_native_trace_walk_deduplicates_and_stops_on_cycles():
    from jiuwenswarm.research.bridge import failure_native_trace_refs
    import asyncio
    ref={'id':'blob:original','sha256':'a'*64}
    outer=TimeoutError();inner=asyncio.CancelledError()
    outer.native_trace_ref=inner.native_trace_ref=ref
    outer.__cause__=inner;inner.__context__=outer
    assert failure_native_trace_refs(outer)==[ref]


@pytest.mark.asyncio
async def test_wrapped_trace_still_requires_exact_call_scope():
    import asyncio
    ledger=Ledger();trace_ref={'id':'blob:wrong-scope','sha256':'b'*64}
    class FailedProvider:
        async def invoke_governed_traced(self,scope,prompt,**kwargs):
            error=asyncio.CancelledError();error.native_trace_ref=trace_ref
            raise TimeoutError() from error
    wrong={'schema':'ai4r-native-governed-trace:1','scope':{'call_id':'other-call'},
           'status':'interrupted','event_refs':[]}
    bridge=GovernedBridge(persist=ledger.append,authorize=lambda _:authorized_context(),
        revalidate=lambda _:authorized_context(),subscription_service=FailedProvider(),
        read_evidence=lambda _:json.dumps(wrong).encode())
    with pytest.raises(BridgeError,match='AUDIT_UNAVAILABLE'):await bridge.call({},'controlled prompt')
    final=next(row for kind,row in ledger.records if kind=='model-call')
    assert trace_ref not in final['evidence_refs'] and final['outcome']!='completed'
