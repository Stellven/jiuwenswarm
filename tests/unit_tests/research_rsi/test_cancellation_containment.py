from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
"""Cancellation ordering with explicit controlled effect owners, not kernel proof."""
import asyncio
import pytest
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.controller import Controller
from jiuwenswarm.research_rsi.custody import ExposureLedger
from jiuwenswarm.research_rsi.oracle import LoopOracle
from jiuwenswarm.research_rsi.signing import Signer
from jiuwenswarm.research_records.contracts import ContractData


@pytest.mark.parametrize('contained',[True,False])
def test_cancelled_history_waits_for_actual_owner_ack_and_marks_uncertainty(tmp_path,contained):
    store=RecordStore(tmp_path/'records');ledger=ExposureLedger(tmp_path/'ledger')
    ledger.register('fixture',{n:[n+str(i) for i in range(20)] for n in ['development','hidden_loop','hidden_final','platform']},known_bad=10,known_good=3)
    ref=store.put({'control':'no model or hidden data'});body=store.put_bytes(b'parent')
    session={'schema_version':'1.0.0','id':'s','session_id':'s','target_profile_ref':ref,
        'parent':{'cc_name':'research.screening','cc_version':'m1-1','declaration_sha256':ref['sha256']},'parent_declaration_ref':ref,
        **{k:ref for k in ['improver_ref','scoring_adapter_ref','configuration_ref','hash_profile_ref','chain_root_ref']},
        'limits':{'max_attempts':1,'max_no_progress':1,'wall_s':30,'per_call_s':10,'session_query_limit':2,'lifetime_query_limit':2},
        'pass_count_repeats':1,'qualification':{'min_pass_rate_gain':.05,'alpha':.05,'min_timing_gain':.1,'noise_multiplier':3,'warmup_batches':5,'paired_rounds':7},
        'started_by':'explicit-test-actor','frozen_at':'2026-10-16T00:00:00Z'}
    session['chain_root_ref']=store.put({'session_id':'s','target_ref':ref,'hash_profile_ref':ref,'interface_revision':'M1-IF-009@r2'})
    class Cancelled:
        async def propose(self,*_):raise asyncio.CancelledError
    calls=[]
    async def contain(sid):calls.append(sid);return {'contained':contained,'session_id':sid}
    async def evaluate(*_):return {'passed':10,'total':20}
    async def no_candidate(*_):pytest.fail('Cancelled proposal must not execute a child')
    controller=Controller(qualification=ControlledQualification(),store=store,ledger=ledger,oracle=LoopOracle(ledger,evaluate),proposer=Cancelled(),assess=no_candidate,
        signer=Signer.generate('test-key'),validate=ContractData().validate,recovery_containment=contain)
    result,_=asyncio.run(controller.run(session,opportunity={'decision':'START'},fixture_identity='fixture',visible_context={},parent_body_ref=body))
    assert calls==['s'] and result['queries_used']==1 and result['attempts_used']==1
    assert result['outcome']==('CANCELLED' if contained else 'ERROR')
    assert controller.containment_uncertain is (not contained)
    if not contained:assert any('containment' in value for value in result['limitations'])
    store.close();ledger.close()
