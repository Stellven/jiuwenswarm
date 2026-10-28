from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
"""Deterministic controller fault fixtures; no runtime/model qualification claim."""
import asyncio
from copy import deepcopy
import pytest
from jiuwenswarm.research_rsi.controller import Controller
from jiuwenswarm.research_rsi.custody import ExposureLedger
from jiuwenswarm.research_rsi.oracle import LoopOracle
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.signing import Signer
from jiuwenswarm.research_records.contracts import ContractData


def controlled_target(store,unit,parent_body):
    target={'schema_version':'1.0.0','id':'controller_unit_target','parent_ref':parent_body,
        'parent_declaration_ref':unit,'frozen_contract_ref':unit,'required_test_refs':[unit],
        'mutable_paths':['body.py'],'protected_refs':[unit],
        'splits':dict(development='unit:development',hidden_loop='unit:hidden_loop',hidden_final='unit:hidden_final',platform='unit:platform'),
        'scoring':dict(primary='passed_test_count',secondary='paired_time_at_equal_counts',warmup_batches=5,paired_rounds=7,
            min_relative_gain=.1,noise_multiplier=3,batch_iterations=1000,calibrated_relative_noise=.02),
        'calibration_ref':unit,'session_query_limit':30,'lifetime_query_limit':90,
        'limits':dict(time_s=600,model_calls=5,memory_mb=512),'scoring_adapter_ref':unit,'improver_ref':unit,'configuration_ref':unit}
    ContractData().validate('rsi-target-profile',target)
    return store.put(target)


def test_valid_child_no_final_preserves_actual_charged_queries(tmp_path):
    store=RecordStore(tmp_path/'records');ledger=ExposureLedger(tmp_path/'oracle.sqlite')
    ledger.register('visible-unit-fixtures',{s:[s+str(i) for i in range(20)] for s in ('development','hidden_loop','hidden_final','platform')},known_bad=10,known_good=3)
    ref=store.put({'mode':'unit fixture only'});parent_body=store.put_bytes(b'parent body');child_body=store.put_bytes(b'child body');diff=store.put({'format':'ai4r-body-diff-v1','files':[]})
    target_ref=controlled_target(store,ref,parent_body)
    pin={'cc_name':'research.screening','cc_version':'test','declaration_sha256':ref['sha256']}
    session={'schema_version':'1.0.0','id':'session:test','session_id':'session:test','target_profile_ref':target_ref,'parent':pin,'parent_declaration_ref':ref,
        'improver_ref':ref,'scoring_adapter_ref':ref,'configuration_ref':ref,'hash_profile_ref':ref,'chain_root_ref':ref,
        'limits':dict(max_attempts=1,max_no_progress=1,wall_s=30,per_call_s=10,session_query_limit=2,lifetime_query_limit=2),
        'pass_count_repeats':1,'qualification':dict(min_pass_rate_gain=.05,alpha=.05,min_timing_gain=.1,noise_multiplier=3,warmup_batches=5,paired_rounds=7),
        'started_by':'disposable-test-operator','frozen_at':'2026-10-16T00:00:00Z'}
    session['chain_root_ref']=store.put({'schema_version':'1.0.0','id':'genesis:test','session_id':session['session_id'],'target_ref':target_ref,'hash_profile_ref':ref,'interface_revision':'M1-IF-009@r2'})
    class Proposal:
        async def propose(self,context,feedback):return {'path':'body.py','body':'child body','rationale':'unit control'}
    async def evaluate(candidate,split):return {'passed':10 if candidate==parent_body else 11,'total':20}
    async def assess(proposal):return {'child_ref':child_body,'diff_ref':diff,'mandatory_passed':True,'evidence_refs':[ref],
        'child':{**pin,'cc_version':'child'},'child_declaration_ref':ref}
    controller=Controller(qualification=ControlledQualification(),store=store,ledger=ledger,oracle=LoopOracle(ledger,evaluate),proposer=Proposal(),assess=assess,
        signer=Signer.generate('test:custodian'),validate=ContractData().validate)
    result,_=asyncio.run(controller.run(session,opportunity={'decision':'START'},fixture_identity='visible-unit-fixtures',visible_context={},parent_body_ref=parent_body))
    assert result['outcome']=='UNEVALUATED_CANDIDATE' and result['queries_used']==2
    assert result['referee_evidence_ref'] is None and result['statistics'] is None and result['qualified_by']=='none'
    attempt=store.get(result['attempt_refs'][0]);assert attempt['model_calls'] is None and attempt['unavailable_reasons']
    assert attempt['schema_version']=='2.0.0' and attempt['attempt_status']=='proposed'
    assert attempt['rejection_reason'] is None


def test_rejected_attempt_absence_and_failure_are_counted_and_chained(tmp_path):
    store=RecordStore(tmp_path/'records');ledger=ExposureLedger(tmp_path/'oracle.sqlite')
    ledger.register('set',{s:[s+str(i) for i in range(20)] for s in ('development','hidden_loop','hidden_final','platform')},known_bad=10,known_good=3)
    ref=store.put({'fixture':'public unit only'});parent=store.put_bytes(b'parent')
    target_ref=controlled_target(store,ref,parent)
    pin={'cc_name':'research.screening','cc_version':'test','declaration_sha256':ref['sha256']}
    session={'schema_version':'1.0.0','id':'s','session_id':'s','target_profile_ref':target_ref,'parent':pin,'parent_declaration_ref':ref,
        'improver_ref':ref,'scoring_adapter_ref':ref,'configuration_ref':ref,'hash_profile_ref':ref,'chain_root_ref':ref,
        'limits':dict(max_attempts=2,max_no_progress=2,wall_s=30,per_call_s=10,session_query_limit=2,lifetime_query_limit=2),
        'pass_count_repeats':1,'qualification':dict(min_pass_rate_gain=.05,alpha=.05,min_timing_gain=.1,noise_multiplier=3,warmup_batches=5,paired_rounds=7),
        'started_by':'unit-actor','frozen_at':'2026-10-16T00:00:00Z'}
    session['chain_root_ref']=store.put({'session_id':'s','target_ref':target_ref,'hash_profile_ref':ref,'interface_revision':'M1-IF-009@r2'})
    calls={'proposal':0,'assessment':0}
    class Malformed:
        async def propose(self,*_):
            calls['proposal']+=1
            raise ValueError('no decodable proposal')
    async def evaluate(*_):return {'passed':10,'total':20}
    async def forbidden(*_):
        calls['assessment']+=1
        raise AssertionError('rejected proposal must never execute')
    controller=Controller(qualification=ControlledQualification(),store=store,ledger=ledger,oracle=LoopOracle(ledger,evaluate),proposer=Malformed(),assess=forbidden,
        signer=Signer.generate('unit:custodian'),validate=ContractData().validate)
    result,_=asyncio.run(controller.run(session,opportunity={'decision':'START'},fixture_identity='set',visible_context={},parent_body_ref=parent))
    assert result['attempts_used']==2 and result['queries_used']==1 and result['final_attempt_ref'] is None
    assert calls=={'proposal':2,'assessment':0}
    for number,pin in enumerate(result['attempt_refs']):
        attempt=store.get(pin)
        assert attempt['schema_version']=='2.0.0' and attempt['attempt_status']=='rejected'
        assert attempt['rejection_reason']=='ValueError: proposal or visible assessment failed'
        assert attempt['child_ref'] is None and attempt['diff_ref'] is None and attempt['rationale'] is None
        assert attempt['rejection_reason'] and attempt['failure_evidence_refs']
        assert attempt['previous_ref']==(result['attempt_refs'][number-1] if number else None)
    store.close();ledger.close()


def test_recovery_closes_an_unmatched_start_from_original_frozen_bytes(tmp_path):
    """Model an interrupted open session, never extend a completed session."""
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    fixture=make_unit_package(tmp_path/'source')
    store=RecordStore(tmp_path/'records');ledger=ExposureLedger(tmp_path/'oracle.sqlite')
    validate=ContractData().validate
    try:
        ref=store.put({'fixture':'schema-complete recovery control, not operational qualification'})
        original=fixture['store'];package=fixture['package']
        declaration=original.read_record(package['parent_declaration_ref'])
        declaration_ref=store.put(declaration)
        target=deepcopy(original.read_record(package['target_profile_ref']))
        parent=store.put_bytes(original.read_blob(target['parent_ref']))
        target.update(parent_ref=parent,parent_declaration_ref=declaration_ref,
            required_test_refs=[ref],protected_refs=[ref],calibration_ref=ref,
            configuration_ref=ref,improver_ref=ref,scoring_adapter_ref=ref)
        validate('rsi-target-profile',target);target_ref=store.put(target)
        session=deepcopy(fixture['session'])
        session.update(session_id='interrupted',target_profile_ref=target_ref,
            parent_declaration_ref=declaration_ref,
            parent={**session['parent'],'declaration_sha256':declaration_ref['sha256']},
            configuration_ref=ref,improver_ref=ref,scoring_adapter_ref=ref,hash_profile_ref=ref)
        session['chain_root_ref']=store.put({'session_id':session['session_id'],
            'target_ref':target_ref,'hash_profile_ref':ref,'interface_revision':'M1-IF-009@r2'})
        validate('rsi-session',session);session_ref=store.put(session)
        ledger.register('recovery-control',{s:[s+str(i) for i in range(20)]
            for s in ('development','hidden_loop','hidden_final','platform')},known_bad=10,known_good=3)
        ledger.open_session(session['session_id'],'recovery-control')
        calls=[]
        async def baseline(*_):calls.append('baseline');return {'passed':10,'total':20}
        asyncio.run(LoopOracle(ledger,baseline).score(session['session_id'],'baseline',parent))
        async def forbidden(*_):pytest.fail('Recovery must not propose, assess or evaluate')
        async def contained(sid):return {'contained':True,'session_id':sid}
        controller=Controller(qualification=ControlledQualification(),store=store,ledger=ledger,
            oracle=None,proposer=None,assess=forbidden,signer=fixture['signer'],validate=validate,
            recovery_containment=contained)
        context_ref=controller._history_context(session,session_ref,parent)
        store.begin_session_history(session['session_id'],session_ref,context_ref)
        store.record_proposer_start(session['session_id'],{'record_kind':'rsi-proposer-start:1',
            'session_id':session['session_id'],'sequence':1,'previous_ref':None,
            'recorded_at':session['frozen_at'],'configuration_ref':ref,'improver_ref':ref})
        # Reopen the durable state as a new process would after a hard loss.
        store.close();ledger.close()
        store=RecordStore(tmp_path/'records');ledger=ExposureLedger(tmp_path/'oracle.sqlite')
        controller.store=store;controller.ledger=ledger
        changed=deepcopy(session);changed['limits']['max_attempts']=19
        with pytest.raises(ValueError,match='bytes differ'):
            asyncio.run(controller.recover_terminal(changed,parent_body_ref=parent,session_ref=session_ref))
        before=ledger.state(session['session_id'])['used']
        recovered,pin=asyncio.run(controller.recover_terminal(session,parent_body_ref=parent,session_ref=session_ref))
        assert recovered['outcome']=='ERROR' and recovered['attempts_used']==1 and recovered['queries_used']==before==1
        assert store.get(pin)==recovered and calls==['baseline']
        assert ledger.state(session['session_id'])['halted']
        last=store.get(recovered['attempt_refs'][-1])
        assert last['attempt_status']=='rejected' and last['child_ref'] is None and last['diff_ref'] is None
        assert last['rejection_reason'] and last['failure_evidence_refs'] and last['model_calls'] is None
        assert ledger.state(session['session_id'])['used']==before and recovered['final_attempt_ref'] is None
    finally:
        store.close();ledger.close();fixture['store'].close()
