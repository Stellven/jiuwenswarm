from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
"""Deterministic controller fault fixtures; no runtime/model qualification claim."""
import asyncio
from dataclasses import asdict
from jiuwenswarm.research_rsi.controller import Controller
from jiuwenswarm.research_rsi.custody import ExposureLedger
from jiuwenswarm.research_rsi.oracle import LoopOracle
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.signing import Signer
from jiuwenswarm.research_records.contracts import ContractData


def test_valid_child_no_final_preserves_actual_charged_queries(tmp_path):
    store=RecordStore(tmp_path/'records');ledger=ExposureLedger(tmp_path/'oracle.sqlite')
    ledger.register('visible-unit-fixtures',{s:[s+str(i) for i in range(20)] for s in ('development','hidden_loop','hidden_final','platform')},known_bad=10,known_good=3)
    ref=store.put({'mode':'unit fixture only'});parent_body=store.put_bytes(b'parent body');child_body=store.put_bytes(b'child body');diff=store.put({'format':'ai4r-body-diff-v1','files':[]})
    pin={'cc_name':'research.screening','cc_version':'test','declaration_sha256':ref['sha256']}
    session={'schema_version':'1.0.0','id':'session:test','session_id':'session:test','target_profile_ref':ref,'parent':pin,'parent_declaration_ref':ref,
        'improver_ref':ref,'scoring_adapter_ref':ref,'configuration_ref':ref,'hash_profile_ref':ref,'chain_root_ref':ref,
        'limits':dict(max_attempts=1,max_no_progress=1,wall_s=30,per_call_s=10,session_query_limit=2,lifetime_query_limit=2),
        'pass_count_repeats':1,'qualification':dict(min_pass_rate_gain=.05,alpha=.05,min_timing_gain=.1,noise_multiplier=3,warmup_batches=5,paired_rounds=7),
        'started_by':'disposable-test-operator','frozen_at':'2026-10-16T00:00:00Z'}
    session['chain_root_ref']=store.put({'schema_version':'1.0.0','id':'genesis:test','session_id':session['session_id'],'target_ref':ref,'hash_profile_ref':ref,'interface_revision':'M1-IF-009@r2'})
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
    pin={'cc_name':'research.screening','cc_version':'test','declaration_sha256':ref['sha256']}
    session={'schema_version':'1.0.0','id':'s','session_id':'s','target_profile_ref':ref,'parent':pin,'parent_declaration_ref':ref,
        'improver_ref':ref,'scoring_adapter_ref':ref,'configuration_ref':ref,'hash_profile_ref':ref,'chain_root_ref':ref,
        'limits':dict(max_attempts=2,max_no_progress=2,wall_s=30,per_call_s=10,session_query_limit=2,lifetime_query_limit=2),
        'pass_count_repeats':1,'qualification':dict(min_pass_rate_gain=.05,alpha=.05,min_timing_gain=.1,noise_multiplier=3,warmup_batches=5,paired_rounds=7),
        'started_by':'unit-actor','frozen_at':'2026-10-16T00:00:00Z'}
    session['chain_root_ref']=store.put({'session_id':'s','target_ref':ref,'hash_profile_ref':ref,'interface_revision':'M1-IF-009@r2'})
    class Malformed:
        async def propose(self,*_):raise ValueError('no decodable proposal')
    async def evaluate(*_):return {'passed':10,'total':20}
    async def forbidden(*_):raise AssertionError('rejected proposal must never execute')
    controller=Controller(qualification=ControlledQualification(),store=store,ledger=ledger,oracle=LoopOracle(ledger,evaluate),proposer=Malformed(),assess=forbidden,
        signer=Signer.generate('unit:custodian'),validate=ContractData().validate)
    result,_=asyncio.run(controller.run(session,opportunity={'decision':'START'},fixture_identity='set',visible_context={},parent_body_ref=parent))
    assert result['attempts_used']==2 and result['queries_used']==1 and result['final_attempt_ref'] is None
    for number,pin in enumerate(result['attempt_refs']):
        attempt=store.get(pin)
        assert attempt['schema_version']=='2.0.0' and attempt['attempt_status']=='rejected'
        assert attempt['child_ref'] is None and attempt['diff_ref'] is None and attempt['rationale'] is None
        assert attempt['rejection_reason'] and attempt['failure_evidence_refs']
        assert attempt['previous_ref']==(result['attempt_refs'][number-1] if number else None)
    # A durable start without a canonical completion models process loss.
    # Recovery closes evidence only; it must not submit another model/query.
    session['limits']['max_attempts']=3
    store.record_proposer_start('s',{'record_kind':'rsi-proposer-start:1','session_id':'s','sequence':3,
        'previous_ref':result['attempt_refs'][-1],'recorded_at':'2026-10-16T00:00:00Z',
        'configuration_ref':ref,'improver_ref':ref})
    before=ledger.state('s')['used']
    recovered,_=asyncio.run(controller.recover_terminal(session,parent_body_ref=parent))
    assert recovered['outcome']=='ERROR' and recovered['attempts_used']==3 and recovered['queries_used']==before
    last=store.get(recovered['attempt_refs'][-1])
    assert last['attempt_status']=='rejected' and last['child_ref'] is None and last['diff_ref'] is None
    assert last['rejection_reason'] and last['failure_evidence_refs'] and last['model_calls'] is None
    assert ledger.state('s')['used']==before and recovered['final_attempt_ref'] is None
