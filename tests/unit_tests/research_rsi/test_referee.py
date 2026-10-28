"""Independent aggregate construction; fixtures here are labeled unit controls."""
import asyncio
import pytest
from jiuwenswarm.research_rsi.custody import ExposureLedger
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.referee import Referee
from jiuwenswarm.research_rsi.signing import Signer


def setup(tmp_path,status='proposed'):
    store=RecordStore(tmp_path/'records');ledger=ExposureLedger(tmp_path/'counts.sqlite')
    ledger.register('fixture-set',{s:[s+str(i) for i in range(20)] for s in ('development','hidden_loop','hidden_final','platform')},known_bad=10,known_good=3)
    ledger.open_session('s','fixture-set')
    pin=store.put({'unit':'protected-context'})
    target=store.put({'splits':{'hidden_final':'final-pinned'}})
    attempt=store.put({'schema_version':'2.0.0','attempt_status':status,'session_id':'s','target_ref':target,'parent_ref':pin,'child_ref':pin,'configuration_ref':pin})
    async def capture(*_):return {'parent':[[1,0,0]]*20,'child':[[1,1,0]]*10+[[1,0,0]]*10,'independent':True,
        'pairs':[{'parent_passed':999}], 'violations':[], 'parent_times':[2]*7, 'child_times':[1]*7, 'warmups':5}
    async def controlled_prerequisites(**_):
        return {'mandatory_passed':True,'integrity_passed':True}
    referee=Referee(ledger,store,Signer.generate('unit:custodian'),capture,lambda *_:None,
        prerequisite_check=controlled_prerequisites)
    options=dict(attempt_ref=attempt,target_ref=target,parent_ref=pin,child_ref=pin,configuration_ref=pin,repeats=3,
        qualification={'min_pass_rate_gain':.05,'alpha':.05,'min_timing_gain':.1,'noise_multiplier':3},mandatory_passed=True,integrity_passed=True)
    return referee,ledger,store,options


def test_v2_referee_constructs_signed_means_and_directions_not_callback_pairs(tmp_path):
    referee,ledger,store,options=setup(tmp_path)
    decision,pin=asyncio.run(referee.final('s',**options));record=store.get(pin)
    assert record['schema_version']=='2.0.0'
    assert record['pairs']==[{'split':'final-pinned','total':20,'parent_passed':20/3,'child_passed':10,
        'gain_units':10,'loss_units':0,'parent_time_s':[2]*7,'child_time_s':[1]*7}]
    assert decision['statistics']['pass_rate_gain']==1/6
    assert ledger.state('s')['final_sealed']==1


def test_rejected_attempt_cannot_reserve_final_or_be_scored(tmp_path):
    referee,ledger,_,options=setup(tmp_path,status='rejected')
    with pytest.raises(ValueError,match='proposed'):asyncio.run(referee.final('s',**options))
    assert ledger.state('s')['final_sealed']==0


@pytest.mark.parametrize('equal',[False,True])
def test_absent_timing_does_not_erase_correctness_and_final_is_not_reexecuted(tmp_path,equal):
    referee,ledger,store,options=setup(tmp_path)
    calls=[]
    async def missing(*_):
        calls.append('final')
        return {'parent':[[1,0,0]]*20,'child':[[1,0,0]]*20 if equal else [[1,1,0]]*20,
            'independent':True,'violations':[]}
    referee.paired_evaluate=missing
    decision,pin=asyncio.run(referee.final('s',**options))
    assert decision['outcome']==('INCONCLUSIVE' if equal else 'QUALIFIED')
    assert decision['qualified_by']==('none' if equal else 'pass_gain')
    assert decision['limitations'] and decision['statistics']['timing'] is None
    pair=store.get(pin)['pairs'][0]
    assert pair['parent_time_s']==pair['child_time_s']==[]
    assert ledger.state('s')['final_sealed']==1
    assert asyncio.run(referee.final('s',**options))==(decision,pin)
    assert calls==['final']
    ledger.close();store.close()


@pytest.mark.parametrize('prerequisite',['missing','mandatory','integrity','malformed'])
def test_caller_pass_flags_cannot_bypass_independent_final_prerequisites(tmp_path,prerequisite):
    referee,ledger,store,options=setup(tmp_path);calls=[]
    async def forbidden(*_):calls.append('hidden');pytest.fail('Failed prerequisite reached hidden final fixtures')
    async def check(**_):
        return {'mandatory_passed':'yes','integrity_passed':True} if prerequisite=='malformed' else {
            'mandatory_passed':prerequisite!='mandatory','integrity_passed':prerequisite!='integrity'}
    referee.paired_evaluate=forbidden
    referee.prerequisite_check=None if prerequisite=='missing' else check
    try:
        with pytest.raises(ValueError,match='prerequisite'):
            asyncio.run(referee.final('s',**options))
        assert calls==[]
    finally:ledger.close();store.close()


def test_partial_or_unreliable_timing_is_not_published_as_a_comparable_pair(tmp_path):
    referee,ledger,store,options=setup(tmp_path)
    async def partial(*_):return {'parent':[[1,0,0]]*20,'child':[[1,1,0]]*20,
        'independent':True,'parent_times':[2]*7,'child_times':[1]*6,'warmups':5}
    referee.paired_evaluate=partial
    decision,pin=asyncio.run(referee.final('s',**options))
    assert decision['qualified_by']=='pass_gain'
    assert store.get(pin)['pairs'][0]['parent_time_s']==[]
    assert store.get(pin)['pairs'][0]['child_time_s']==[]
    ledger.close();store.close()
