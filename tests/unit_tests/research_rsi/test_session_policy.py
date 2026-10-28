"""Frozen time allocation and durable phases; controlled execution only."""
import asyncio
from copy import deepcopy
import math

import pytest

from jiuwenswarm.research_rsi.session_policy import FinalBudget
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_records.contracts import ContractData


def budget_record(target_ref, *, repeats=1):
    calls=2*20*repeats+2*20*repeats*(1+5+7)
    return {'schema':'ai4r-rsi-final-budget:1','id':'unit:final-budget','target_ref':target_ref,
        'hidden_final_units':20,'mandatory_units':20,'pass_count_repeats':repeats,
        'worker_timeout_s':.005,'invocation_wall_s':.01,'evidence_wall_s':1,
        'final_reserve_s':math.ceil(calls*.01+1)}


def test_final_reserve_covers_both_subjects_checks_repeats_and_all_timing_rounds():
    ref={'id':'target','sha256':'a'*64};value=budget_record(ref,repeats=3)
    budget=FinalBudget.from_record(value,wall_s=60,target_ref=ref,repeats=3)
    assert budget.final_reserve_s==18
    assert budget.search_remaining(deadline=60,now=40)==1
    assert budget.search_remaining(deadline=60,now=43)==0
    assert budget.execution_s==pytest.approx(16.8)
    with pytest.raises(ValueError,match='reserve'):
        FinalBudget.from_record(value|{'final_reserve_s':17},wall_s=60,target_ref=ref,repeats=3)
    with pytest.raises(ValueError,match='wall'):
        FinalBudget.from_record(value,wall_s=18,target_ref=ref,repeats=3)
    with pytest.raises(ValueError):
        FinalBudget.from_record(value,wall_s=60,target_ref=ref,repeats=1)
    with pytest.raises(ValueError):
        FinalBudget.from_record(value|{'hidden_final_units':19},wall_s=60,target_ref=ref,repeats=3)


def test_phase_journal_compare_and_swap_is_durable_and_cannot_reopen_finalizing(tmp_path):
    store=RecordStore(tmp_path);pin=store.put({'unit':'session'})
    def transition(phase,revision,**extra):
        return store.advance_phase('s',pin,phase,expected_revision=revision,
            incumbent_ref=pin,attempts_used=1,queries_used=2,**extra)
    transition('PREFLIGHT',0);transition('BASELINE',1);transition('SEARCH',2)
    with pytest.raises(ValueError,match='revision'):transition('FINALIZING',2)
    transition('FINALIZING',3)
    with pytest.raises(ValueError,match='transition'):transition('SEARCH',4)
    terminal=store.put({'session_ref':pin,'outcome':'NO_IMPROVEMENT'})
    transition('CLOSED',4,terminal_result_ref=terminal)
    with pytest.raises(ValueError):transition('SEARCH',5)
    store.close();store=RecordStore(tmp_path)
    try:
        current=store.latest_phase('s')['record']
        assert current['phase']=='CLOSED' and current['revision']==5
        assert current['terminal_result_ref']==terminal
        assert len(store.phase_refs('s'))==5
    finally:store.close()


def test_job_inspection_uses_protected_phase_index_for_an_opaque_session_ref(tmp_path):
    from jiuwenswarm.research_rsi.ports import JobPort
    store=RecordStore(tmp_path);session={'id':'opaque:session','sha256':'b'*64}
    job={'id':'job_one','sha256':'a'*64};context=store.put({'unit':'history context'})
    class Jobs:
        def resolve(self,ref):return {'session_ref':session}
    try:
        store.claim_job(job);store.bind_job_session(job,session);store.begin_session_history('s',session,context)
        store.advance_phase('s',session,'PREFLIGHT',expected_revision=0)
        value=asyncio.run(JobPort(Jobs(),store,allowed_refs=[job]).inspect(job))
        assert value['progress']==dict(phase='PREFLIGHT',revision=1,incumbent_ref=None,attempts_used=0,queries_used=0)
    finally:store.close()


def test_budget_matches_actual_protected_populations_and_worker_bound(tmp_path):
    store=RecordStore(tmp_path);target=store.put({'unit':'target'})
    plan=budget_record(target);genesis=store.put({'final_budget_ref':store.put(plan)})
    session={'target_profile_ref':target,'chain_root_ref':genesis,'pass_count_repeats':1,'limits':{'wall_s':30}}
    manifest={'partitions':{'hidden_final':[None]*20,'platform':[None]*20}}
    try:
        FinalBudget.for_session(session,store,worker_profile={'timeout_s':.005},manifest=manifest)
        with pytest.raises(ValueError,match='worker'):
            FinalBudget.for_session(session,store,worker_profile={'timeout_s':1},manifest=manifest)
        manifest['partitions']['hidden_final'].append(None)
        with pytest.raises(ValueError,match='populations'):
            FinalBudget.for_session(session,store,worker_profile={'timeout_s':.005},manifest=manifest)
    finally:store.close()


def controller_fixture(tmp_path,with_budget=True):
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
    from jiuwenswarm.research_rsi.fixed_resources import CombinedRecords
    from jiuwenswarm.research_rsi.controller import Controller
    from jiuwenswarm.research_rsi.custody import ExposureLedger
    from jiuwenswarm.research_rsi.oracle import LoopOracle
    f=make_unit_package(tmp_path/'source');records=RecordStore(tmp_path/'records')
    store=CombinedRecords(records,core=f['store']);session=deepcopy(f['session'])
    session['pass_count_repeats']=1
    session['limits']=dict(max_attempts=2,max_no_progress=2,wall_s=30,
        per_call_s=30,session_query_limit=3,lifetime_query_limit=3)
    genesis=store.get(session['chain_root_ref'])
    if with_budget:genesis['final_budget_ref']=store.put(budget_record(session['target_profile_ref']))
    session['chain_root_ref']=store.put(genesis)
    ledger=ExposureLedger(tmp_path/'oracle.sqlite');ledger.register('unit:set',
        {name:[name+str(i) for i in range(20)] for name in ('development','hidden_loop','hidden_final','platform')},
        known_bad=10,known_good=3)
    clock=[0];calls=[];budget=FinalBudget.from_record(budget_record(session['target_profile_ref']),
        wall_s=30,target_ref=session['target_profile_ref'],repeats=1)
    class Proposer:
        count=0
        contexts=[]
        async def propose(self,context,*_):
            self.contexts.append(context)
            self.count+=1;calls.append('proposal')
            clock[0]=budget.search_remaining(deadline=30,now=0)-(1 if self.count==1 else 0)
            if self.count>1:raise asyncio.TimeoutError
            return {'rationale':'controlled proposal'}
    async def evaluate(candidate,*_):
        calls.append('query');return {'passed':10 if candidate==f['attempt']['parent_ref'] else 11,'total':20}
    async def assess(*_):
        return {'child_ref':f['attempt']['child_ref'],'diff_ref':f['attempt']['diff_ref'],
            'mandatory_passed':True,'evidence_refs':[],
            'child':f['result']['child'],'child_declaration_ref':f['result']['child_declaration_ref']}
    async def final(best):
        calls.append('final');assert clock[0]==budget.search_remaining(deadline=30,now=0)
        clock[0]+=1
        return {'outcome':'NO_IMPROVEMENT','qualified_by':'none','statistics':None,
            'reason':'controlled comparison'},store.put({'unit':'referee control only'})
    controller=Controller(qualification=ControlledQualification(),store=store,ledger=ledger,
        oracle=LoopOracle(ledger,evaluate),proposer=Proposer(),assess=assess,
        signer=f['signer'],validate=ContractData().validate,clock=lambda:clock[0])
    controller.controlled_clock=clock
    return f,records,ledger,controller,session,final,calls


def test_search_cannot_spend_final_reserve_and_phase_precedes_final_effect(tmp_path,monkeypatch):
    f,records,ledger,controller,session,final,calls=controller_fixture(tmp_path)
    timeouts=[];original=asyncio.wait_for
    async def observed(awaitable,timeout):
        timeouts.append(timeout);return await original(awaitable,timeout)
    monkeypatch.setattr(asyncio,'wait_for',observed)
    async def observed_final(best):
        assert records.latest_phase(session['session_id'])['record']['phase']=='FINALIZING'
        return await final(best)
    try:
        result,_=asyncio.run(controller.run(session,opportunity={'decision':'START'},fixture_identity='unit:set',
            visible_context={},parent_body_ref=f['attempt']['parent_ref'],finalize=observed_final))
        assert result['outcome']=='NO_IMPROVEMENT' and result['attempts_used']==2 and result['queries_used']==2
        assert timeouts==[22,22,1,1,1,7]
        assert calls==['query','proposal','query','proposal','final']
        contexts=controller.proposer.contexts
        assert contexts[0]['incumbent']['body']==f['store'].read_blob(f['attempt']['parent_ref']).decode()
        assert contexts[1]['incumbent']['body']==f['store'].read_blob(f['attempt']['child_ref']).decode()
        assert contexts[1]['attempt_history']==[{'sequence':1,'rationale':'controlled proposal','status':'proposed'}]
        phase=records.latest_phase(session['session_id'])['record']
        assert phase['phase']=='CLOSED' and phase['attempts_used']==2 and phase['queries_used']==2
    finally:records.close();ledger.close();f['store'].close()


@pytest.mark.parametrize('delay_phase',['SEARCH','FINALIZING'])
def test_persistence_cannot_shorten_final_bound_or_start_an_underbudget_final(tmp_path,monkeypatch,delay_phase):
    f,records,ledger,controller,session,_,calls=controller_fixture(tmp_path)
    original=records.advance_phase
    def delayed(sid,session_ref,phase,**kwargs):
        pin=original(sid,session_ref,phase,**kwargs)
        if phase==delay_phase and kwargs['attempts_used']==2:controller.controlled_clock[0]=24
        return pin
    monkeypatch.setattr(records,'advance_phase',delayed)
    async def forbidden(*_):pytest.fail('Incomplete reserved budget reached final execution')
    try:
        result,_=asyncio.run(controller.run(session,opportunity={'decision':'START'},fixture_identity='unit:set',
            visible_context={},parent_body_ref=f['attempt']['parent_ref'],finalize=forbidden))
        assert result['outcome']=='UNEVALUATED_CANDIDATE' and result['final_attempt_ref'] is None
        assert ledger.state(session['session_id'])['final_sealed']==0
    finally:records.close();ledger.close();f['store'].close()


def test_final_budget_missing_blocks_before_any_exposure_or_proposal(tmp_path):
    f,records,ledger,controller,session,final,calls=controller_fixture(tmp_path,with_budget=False)
    try:
        with pytest.raises(ValueError,match='final budget'):
            asyncio.run(controller.run(session,opportunity={'decision':'START'},fixture_identity='unit:set',
                visible_context={},parent_body_ref=f['attempt']['parent_ref'],finalize=final))
        assert calls==[] and ledger.db.execute('SELECT count(*) FROM sessions').fetchone()[0]==0
    finally:records.close();ledger.close();f['store'].close()


def canonical_opportunity(session,decision):
    return dict(schema_version='1.0.0',id='unit:opportunity',target_profile_ref=session['target_profile_ref'],
        parent=session['parent'],trigger='operator_selected',selected_by=session['started_by'],evidence_refs=[session['target_profile_ref']],
        attribution='implementation',symptom_reproduced=True,parent_mandatory_passed=True,headroom=.2,
        headroom_minimum=.1,diagnosis_ref=None,decision=decision,reason='controlled visible decision',
        decided_at='2026-10-25T00:00:00Z')


@pytest.mark.parametrize('decision,readiness,outcome',[
    ('NO_ATTEMPT','BLOCKED','BLOCKED'),('NO_ATTEMPT','READY','NO_IMPROVEMENT'),
    ('NEEDS_REVIEW','READY','INCONCLUSIVE')])
def test_preflight_nonstart_closes_without_exposure_proposal_or_replayed_diagnosis(tmp_path,decision,readiness,outcome):
    from jiuwenswarm.research_rsi.custody import ExposureError
    f,records,ledger,controller,session,final,calls=controller_fixture(tmp_path)
    invoked=[]
    async def qualify():
        invoked.append('diagnosis')
        assert records.latest_phase(session['session_id'])['record']['phase']=='PREFLIGHT'
        return dict(record=canonical_opportunity(session,decision),readiness=readiness,parent_visible_time_s=1)
    kwargs=dict(opportunity=None,fixture_identity='unit:set',visible_context={},
        parent_body_ref=f['attempt']['parent_ref'],finalize=final,qualify=qualify)
    try:
        result,_=asyncio.run(controller.run(session,**kwargs))
        assert result['outcome']==outcome and result['queries_used']==result['attempts_used']==0
        assert calls==[] and invoked==['diagnosis']
        assert records.latest_phase(session['session_id'])['record']['phase']=='CLOSED'
        with pytest.raises(ExposureError,match='preflight'):
            asyncio.run(controller.run(session,**kwargs))
        assert invoked==['diagnosis']
    finally:records.close();ledger.close();f['store'].close()


@pytest.mark.parametrize('fault',['native','security'])
def test_preflight_effect_fault_never_becomes_an_ordinary_blocked_decision(tmp_path,fault):
    from jiuwenswarm.research_rsi.native_lease import ProfileInUse
    from jiuwenswarm.research_rsi.mutation import SecurityViolation
    f,records,ledger,controller,session,final,calls=controller_fixture(tmp_path)
    async def qualify():
        raise ProfileInUse('controlled unknown native outcome') if fault=='native' else SecurityViolation('controlled scope violation')
    try:
        result,_=asyncio.run(controller.run(session,opportunity=None,fixture_identity='unit:set',visible_context={},
            parent_body_ref=f['attempt']['parent_ref'],finalize=final,qualify=qualify))
        assert result['outcome']==('ERROR' if fault=='native' else 'SECURITY_HALTED')
        assert result['queries_used']==result['attempts_used']==0 and not calls
        assert ledger.state(session['session_id'])['halted']
        assert controller.containment_uncertain==(fault=='native')
    finally:records.close();ledger.close();f['store'].close()


def test_cancellation_during_diagnosis_prevents_baseline_and_proposal(tmp_path):
    f,records,ledger,controller,session,final,calls=controller_fixture(tmp_path)
    async def qualify():
        record=canonical_opportunity(session,'START')
        record['diagnosis_ref']=controller.store.put({'controlled':'diagnosis only'})
        controller.cancel()
        return dict(record=record,readiness='READY',parent_visible_time_s=1)
    async def contained(sid):return dict(contained=True,session_id=sid)
    controller.recovery_containment=contained
    try:
        result,_=asyncio.run(controller.run(session,opportunity=None,fixture_identity='unit:set',visible_context={},
            parent_body_ref=f['attempt']['parent_ref'],finalize=final,qualify=qualify))
        assert result['outcome']=='CANCELLED' and result['queries_used']==result['attempts_used']==0
        assert not calls and not controller.containment_uncertain
    finally:records.close();ledger.close();f['store'].close()
