"""Counts-only loop oracle. Reserved unknown outcomes are never replayed."""
import json
import uuid
import hashlib
from .custody import ExposureError
from .statistics import mean_score_total


class LoopOracle:
    def __init__(self,ledger,evaluate,*,repeats=1):
        if type(repeats) is not int or repeats not in (1,3):raise ValueError('frozen one/three repeats required')
        self.ledger,self.evaluate,self.repeats=ledger,evaluate,repeats
    async def score(self,session,action,candidate_ref):
        fingerprint=hashlib.sha256(json.dumps(candidate_ref,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        reservation=self.ledger.reserve(session,action,'loop',fingerprint=fingerprint)
        if reservation['state']=='complete':
            result=json.loads(reservation['result'])
            return result['feedback']
        else:
            # A duplicate reserved action means the prior process may have scored.
            # The caller must reconcile; this flag is persisted before evaluation.
            if not reservation['fresh']:raise ExposureError('unknown evaluation outcome; automatic replay forbidden')
            self.ledger.db.execute('UPDATE actions SET state=? WHERE session=? AND id=?',('evaluating',session,action))
            result=await self.evaluate(candidate_ref,'hidden_loop')
            try:
                if not isinstance(result,dict) or set(result)!={'passed','total'}:raise ValueError('mean-score fields differ')
                mean_score_total(result['passed'],result['total'],self.repeats)
            except (ValueError,TypeError,KeyError):raise ExposureError('malformed mean totals; exposure retained') from None
            feedback={'schema_version':'2.0.0','id':'feedback:'+hashlib.sha256((session+'\0'+action).encode()).hexdigest()[:32],
                'passed':result['passed'],'total':result['total'],'queries_left':reservation['queries_left']}
            self.ledger.complete(session,action,{'feedback':feedback})
            return feedback
