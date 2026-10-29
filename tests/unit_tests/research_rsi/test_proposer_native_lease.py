from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
"""Native ownership controls with an explicitly labeled model transport double."""
import asyncio
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research_records.original_bytes import OriginalBytes
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.fixed_resources import CoreProposer,CombinedRecords
from jiuwenswarm.research_rsi.native_lease import NativeEffectLease,ProfileInUse


def test_proposer_releases_only_known_calls_and_never_publishes_account_frames(tmp_path):
    core=SQLiteRunStore(tmp_path/'core');records=RecordStore(tmp_path/'records')
    public=OriginalBytes(tmp_path/'public',writable=True);combined=CombinedRecords(records,core,publisher=public)
    scope=records.put({'unit':'native profile binding'});lease=NativeEffectLease(records,scope)
    contract=core.put_blob(b'controlled contract identity')
    sentinel=core.append_record('native-account-frame',{'secret_sentinel':'must remain private'})
    class ModelDouble:
        store=core
        outcome='completed'
        async def propose_once(self,pin,prompt):
            invocation='controlled-invocation';call='controlled-call'
            core.append_record('model-call-start',{'id':call+':start','contract_ref':pin,'invocation_id':invocation,'call_id':call})
            raw=core.append_record('model-provider-observation',{'id':'provider','invocation_id':invocation,'call_id':call,'identity':{'effective':'double'},'usage':None})
            call_ref=core.append_record('model-call',{'id':call,'invocation_id':invocation,'outcome':self.outcome,'evidence_refs':[raw]})
            core.append_record('invocation-observation',{'id':'observation','contract_ref':pin,'model_calls':1,'output_refs':[],'trace_refs':[call_ref]})
            return 'controlled proposal response'
    model=ModelDouble();proposer=CoreProposer(model,[contract],combined,native_lease=lease,session_id='unit',qualification=ControlledQualification())
    assert asyncio.run(proposer('public proposer input'))=='controlled proposal response'
    lease.assert_available()
    assert sentinel['id'] not in public.index()
    assert not any(b'must remain private' in p.read_bytes() for p in public.root.glob('*.bytes'))
    records.close();core.close()


def test_unknown_model_call_persists_profile_in_use_without_retry(tmp_path):
    core=SQLiteRunStore(tmp_path/'core');records=RecordStore(tmp_path/'records');scope=records.put({'unit':'scope'})
    lease=NativeEffectLease(records,scope);contract=core.put_blob(b'controlled contract')
    class UnknownDouble:
        store=core
        async def propose_once(self,pin,prompt):
            core.append_record('model-call-start',{'id':'unknown:start','contract_ref':pin,'invocation_id':'i','call_id':'unknown'})
            core.append_record('model-call',{'id':'unknown','invocation_id':'i','outcome':'outcome_unknown','evidence_refs':[]})
            core.append_record('invocation-observation',{'id':'o','contract_ref':pin,'model_calls':1,'output_refs':[]})
            raise TimeoutError('controlled uncertain transport')
    proposer=CoreProposer(UnknownDouble(),[contract],CombinedRecords(records,core),native_lease=lease,session_id='unit',qualification=ControlledQualification())
    with pytest.raises(ProfileInUse):asyncio.run(proposer('public input'))
    with pytest.raises(ProfileInUse):NativeEffectLease(records,scope).assert_available()
    assert proposer.last_model_calls==1
    records.close();core.close()


def test_exact_native_thread_trace_is_published_but_account_packets_never_are(tmp_path):
    from jiuwenswarm.server.runtime.codex_subscription.governed_trace import GovernedTrace
    from jiuwenswarm.research.isolated_resources import owned_model_evidence
    core=SQLiteRunStore(tmp_path/'core');records=RecordStore(tmp_path/'records')
    public=OriginalBytes(tmp_path/'public',writable=True);combined=CombinedRecords(records,core,publisher=public)
    contract=core.append_record('subnode-execution-contract',{'run_id':'run','node_id':'node','subnode_id':'work','attempt_id':'attempt'});scope_ref=records.put({'unit':'separate profile'})
    lease=NativeEffectLease(records,scope_ref);private=core.append_record('native-account-frame',{'token':'private sentinel'})
    class ModelDouble:
        store=core
        async def propose_once(self,pin,prompt):
            fields={'run_id':'run','node_id':'node','subnode_id':'work','attempt_id':'attempt','execution_id':'execution','invocation_id':'invocation','call_id':'call','contract_ref':pin}
            start=core.append_record('model-call-start',{k:fields[k] for k in ('run_id','execution_id','invocation_id','call_id','contract_ref')})
            trace=GovernedTrace({**fields,'model_call_start_ref':start},core.append_record,core.put_blob)
            trace.bind_thread('owned-thread')
            trace.notification('in',b'{"method":"account/login","params":{"secret":"private sentinel"}}',{'method':'account/login','params':{}})
            trace.notification('in',b'{"method":"turn/completed","params":{"threadId":"owned-thread"}}',{'method':'turn/completed','params':{'threadId':'owned-thread'}})
            summary=trace.finish('completed')
            call=core.append_record('model-call',{'id':'call',**{k:fields[k] for k in ('execution_id','invocation_id')},'outcome':'completed','evidence_refs':[summary]})
            core.append_record('invocation-observation',{'id':'o','contract_ref':pin,'model_calls':1,'output_refs':[],'trace_refs':[call]})
            return 'public response'
    proposer=CoreProposer(ModelDouble(),[contract],combined,native_lease=lease,session_id='unit',qualification=ControlledQualification())
    assert asyncio.run(proposer('public input'))=='public response'
    calls=list(core.iter_records(kinds=('model-call',)));closure=owned_model_evidence(core,calls[0]['ref'])
    assert {row['kind'] for row in closure}=={'native-governed-trace','native-governed-trace-event','native-governed-packet'}
    assert all(public.read(row['ref'])==row['bytes'] for row in closure)
    assert private['id'] not in public.index()
    assert not any(b'private sentinel' in p.read_bytes() for p in public.root.glob('*.bytes'))
    core.close();records.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('failed',[False,True])
async def test_actual_bridge_subscription_source_shaped_trace_closure_and_scope_tamper(tmp_path,failed):
    import copy
    from jiuwenswarm.research.bridge import GovernedBridge,BridgeError
    from jiuwenswarm.research.isolated_resources import owned_model_evidence
    from jiuwenswarm.research.contracts import ResearchError
    from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
    from tests.unit_tests.runtime.test_codex_governed_trace import WireTransport
    from tests.unit_tests.research.test_bridge import authorized_context
    from tests.unit_tests.research.test_admitted_measurement import adapter_fixture
    core,_,contract_ref,_,_=await adapter_fixture(tmp_path/'actual-core')
    contract=core.read_record(contract_ref);context=authorized_context()
    context.update({k:contract[k] for k in ('run_id','node_id','subnode_id','attempt_id')});context['contract_ref']=contract_ref
    transport=WireTransport();transport.fail_turn=failed;service=SubscriptionService(tmp_path/'own-native',transport=transport)
    service.set_governed_trace_writer(core.append_record,core.put_blob)
    bridge=GovernedBridge(persist=core.append_record,authorize=lambda _:context,revalidate=lambda _:context,subscription_service=service,read_evidence=core.read_blob)
    if failed:
        with pytest.raises(BridgeError):await bridge.call({},'controlled public proposer input')
    else:assert (await bridge.call({},'controlled public proposer input'))['text']=='Hello'
    call_ref=next(core.iter_records(kinds=('model-call',)))['ref'];call=core.read_record(call_ref)
    assert 'run_id' not in call and 'node_id' not in call and 'attempt_id' not in call
    closure=owned_model_evidence(core,call_ref)
    assert {'native-governed-trace','native-governed-trace-event','native-governed-packet'}<={r['kind'] for r in closure}
    summary_ref=next(r['ref'] for r in closure if r['kind']=='native-governed-trace')
    for field in ('run_id','node_id','subnode_id','attempt_id','execution_id','invocation_id'):
        bad=copy.deepcopy(core.read_record(summary_ref));bad['scope'][field]='wrong-scope'
        changed=core.append_record('native-governed-trace',bad)
        altered=copy.deepcopy(call);altered['evidence_refs']=[changed if r==summary_ref else r for r in call['evidence_refs']]
        with pytest.raises(ResearchError):owned_model_evidence(core,core.append_record('model-call',altered))
    assert not any(b'fixture@example.invalid' in row['bytes'] or b'LEAK' in row['bytes'] for row in closure)
    core.close()
