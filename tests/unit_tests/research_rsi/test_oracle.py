import asyncio
import pytest
from jiuwenswarm.research_rsi.custody import ExposureLedger,ExposureError
from jiuwenswarm.research_rsi.oracle import LoopOracle


def test_five_fields_duplicate_feedback_identical_and_unknown_not_replayed(tmp_path):
    ledger=ExposureLedger(tmp_path/'oracle.sqlite')
    ledger.register('actual-content-identity',{s:[s+str(i) for i in range(20)] for s in ('development','hidden_loop','hidden_final','platform')},known_bad=10,known_good=3)
    ledger.open_session('s','actual-content-identity')
    calls=[]
    async def score(ref,split):calls.append(ref);return {'passed':15,'total':20}
    oracle=LoopOracle(ledger,score)
    async def run():
        a=await oracle.score('s','baseline',{'id':'parent'})
        b=await oracle.score('s','baseline',{'id':'parent'})
        assert a==b and set(a)=={'schema_version','id','passed','total','queries_left'}
        ledger.reserve('s','unknown','loop')
        with pytest.raises(ExposureError):await oracle.score('s','unknown',{'id':'child'})
    asyncio.run(run());assert len(calls)==1 and ledger.state('s')['used']==2
