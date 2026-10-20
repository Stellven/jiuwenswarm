import pytest
import asyncio
from jiuwenswarm.research_rsi.custody import ExposureLedger, ExposureError
from jiuwenswarm.research_rsi.oracle import LoopOracle


def test_charge_before_feedback_idempotency_and_final_once(tmp_path):
    db=ExposureLedger(tmp_path/'oracle.sqlite')
    db.register('actual-fixtures', {s:[s+str(i) for i in range(20)] for s in ('development','hidden_loop','hidden_final','platform')}, known_bad=10,known_good=3)
    db.open_session('s','actual-fixtures',session_cap=2,lifetime_cap=3)
    assert db.reserve('s','baseline','loop')['queries_used']==1
    assert db.reserve('s','baseline','loop')['state']=='reserved'
    db.complete('s','baseline',{'passed':10,'total':20})
    assert db.reserve('s','baseline','loop')['state']=='complete'
    db.reserve('s','child','loop')
    with pytest.raises(ExposureError):db.reserve('s','other','loop')
    db.reserve('s','final','final')
    with pytest.raises(ExposureError):db.reserve('s','another-final','final')
    db.open_session('s2','actual-fixtures',session_cap=2,lifetime_cap=3)
    db.reserve('s2','baseline','loop')
    with pytest.raises(ExposureError):db.reserve('s2','child','loop')
    db.close()


def test_v2_feedback_preserves_fractional_passed_sum_and_rejects_bad_means(tmp_path):
    db=ExposureLedger(tmp_path/'oracle.sqlite')
    db.register('set',{s:[s+str(i) for i in range(20)] for s in ('development','hidden_loop','hidden_final','platform')},known_bad=10,known_good=3)
    db.open_session('s','set',session_cap=3,lifetime_cap=3)
    async def evaluate(ref,split):return {'passed':20/3,'total':20}
    oracle=LoopOracle(db,evaluate,repeats=3)
    feedback=asyncio.run(oracle.score('s','baseline',{'id':'body','sha256':'a'*64}))
    assert feedback['schema_version']=='2.0.0' and feedback['passed']==20/3
    assert set(feedback)=={'schema_version','id','passed','total','queries_left'}
    assert asyncio.run(oracle.score('s','baseline',{'id':'body','sha256':'a'*64}))==feedback
    async def bad(ref,split):return {'passed':float('nan'),'total':20}
    with pytest.raises(ExposureError):asyncio.run(LoopOracle(db,bad,repeats=3).score('s','bad',{'id':'child','sha256':'b'*64}))
    assert db.state('s')['used']==2
    db.close()
