from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
"""Finite broker policy controls; these tests do not qualify kernel isolation."""
import pytest
from jiuwenswarm.research_rsi.worker import validate_request,validate_profile


REF={'id':'pin','sha256':'a'*64}


def test_worker_wire_cannot_select_command_path_import_or_actor():
    value=dict(profile_ref=REF,session_ref=REF,candidate_ref=REF,input_ref=REF,reservation_ref=REF,phase='hidden_loop',repeat_index=0)
    assert validate_request(value)==value
    for key in ('argv','module','factory','actor','fixture_path'):
        with pytest.raises(ValueError):validate_request({**value,key:'untrusted'})
    with pytest.raises(ValueError):validate_request({**value,'phase':'arbitrary'})


def test_worker_profile_requires_bound_pins_and_narrow_limits():
    value=dict(schema='ai4r-rsi-worker-profile:1',target_kind='ranking-v1',session_ref=REF,target_ref=REF,parent_ref=REF,
        contract_ref=REF,environment_ref=REF,hardware_ref=REF,memory_mb=128,pids_max=16,timeout_s=10)
    assert validate_profile(value)==value
    with pytest.raises(ValueError):validate_profile({**value,'target_kind':'module:chosen'})
    with pytest.raises(ValueError):validate_profile({**value,'timeout_s':301})


def test_cancel_refuses_ungranted_session_and_is_durable(tmp_path):
    import asyncio
    from types import SimpleNamespace
    from jiuwenswarm.research_rsi.worker import WorkerBroker
    from jiuwenswarm.research_rsi.records import encoded
    broker=object.__new__(WorkerBroker);broker.root=tmp_path;broker.profiles={b'profile':{'session_ref':REF}}
    broker.tasks={};broker.job_sessions={};broker.cancelled=set();broker.executor=SimpleNamespace(active={})
    wrong={'id':'other','sha256':'b'*64}
    with pytest.raises(ValueError):asyncio.run(broker.cancel({'session_ref':wrong}))
    assert asyncio.run(broker.cancel({'session_ref':REF}))['contained'] is True
    assert encoded(REF) in broker.cancelled and len(list(tmp_path.glob('cancelled-*')))==1


@pytest.mark.asyncio
@pytest.mark.parametrize('phase',['hidden_final','platform','hidden_loop','development'])
@pytest.mark.parametrize('hidden',[True,False])
async def test_actual_worker_client_scopes_timing_to_custodian_final_phases(tmp_path,phase,hidden):
    from types import SimpleNamespace
    from jiuwenswarm.research_rsi.records import RecordStore
    from jiuwenswarm.research_rsi.worker import WorkerClient
    store=RecordStore(tmp_path/'requests');client=object.__new__(WorkerClient)
    client.requests=store;client.profile_ref=REF;client.session_ref=REF;client.hidden=hidden;calls=[]
    async def rpc(operation,value,**kwargs):calls.append((operation,value));return {'captures':[]}
    client.rpc=SimpleNamespace(call=rpc)
    allowed=hidden and phase in {'hidden_final','platform'}
    if allowed:
        await client.run(REF,{'scores':[]},phase=phase,reservation_ref=REF,timing=True)
        assert len(calls)==1 and calls[0][0]=='run_timing_batch' and calls[0][1]['phase']==phase
    else:
        with pytest.raises(ValueError):await client.run(REF,{'scores':[]},phase=phase,reservation_ref=REF,timing=True)
        assert not calls
    store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('phase',['hidden_final','platform','hidden_loop','development'])
@pytest.mark.parametrize('hidden',[True,False])
async def test_actual_private_broker_phase_gate_precedes_any_candidate_effect(tmp_path,phase,hidden):
    import asyncio
    from types import SimpleNamespace
    from jiuwenswarm.research_rsi.records import encoded
    from jiuwenswarm.research_rsi.worker import WorkerBroker
    broker=object.__new__(WorkerBroker);broker.qualification=ControlledQualification();broker.root=tmp_path;broker.hidden=hidden
    broker.profiles={encoded(REF):{'session_ref':REF,'target_ref':REF}};broker.cancelled=set();broker.claims=set();broker.lock=asyncio.Lock()
    reservation={'session_ref':REF,'candidate_ref':REF,'phase':phase,'operation':'timing:0:parent'}
    broker.inputs=SimpleNamespace(get=lambda ref:reservation)
    reached=[]
    class EffectProbe(Exception):pass
    def before_effect(ref):reached.append(ref);raise EffectProbe('Actual executor is deliberately absent from this scope-only control')
    broker.public=SimpleNamespace(get=lambda ref:{'scoring':{'batch_iterations':2}},read=before_effect)
    value=dict(profile_ref=REF,session_ref=REF,candidate_ref=REF,input_ref=REF,reservation_ref=REF,phase=phase,repeat_index=0)
    if hidden and phase in {'hidden_final','platform'}:
        with pytest.raises(EffectProbe):await broker.run(value,timing=True)
        assert reached==[REF]
        with pytest.raises(ValueError,match='already issued'):await broker.run(value,timing=True)
    else:
        with pytest.raises(ValueError):await broker.run(value,timing=True)
        assert not reached and not list(tmp_path.glob('claim-*'))
