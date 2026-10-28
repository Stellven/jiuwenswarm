"""Controller-side references-only proxy; private fixture/key bytes never cross."""
from .ports import request


class CustodianClient:
    def __init__(self,requests,*,socket_path,peer_uid,session_id,timeout=3600):
        if not 0<timeout<=3600:raise ValueError('custodian timeout exceeds session wall ceiling')
        self.requests,self.path,self.uid,self.sid,self.timeout=requests,socket_path,peer_uid,session_id,timeout
    async def _call(self,op,value):
        ref=self.requests.put({'session_id':self.sid,**value})
        reply=await request(self.path,self.uid,op,ref,timeout=self.timeout)
        if reply['status']!='ok':raise ValueError('custodian operation unavailable; exposure may already be charged')
        return reply['result']
    async def score(self,session,action,candidate_ref):
        if session!=self.sid:raise ValueError('cross-session custody denied')
        return await self._call('custodian_evaluate',{'action_id':action,'candidate_ref':candidate_ref})
    async def open_session(self,session,fixture,*,session_cap,lifetime_cap):
        if session!=self.sid:raise ValueError('cross-session custody denied')
        return await self._call('custodian_open',{'fixture_identity':fixture,'session_cap':session_cap,'lifetime_cap':lifetime_cap})
    async def state(self,session):
        if session!=self.sid:raise ValueError('cross-session custody denied')
        return await self._call('custodian_state',{})
    async def halt(self,session):
        if session!=self.sid:raise ValueError('cross-session custody denied')
        return await self._call('custodian_halt',{})
    async def readiness(self,session_ref):
        # Existing immutable session identity is the entire request. A health
        # query does not create a request blob or open a custody session.
        reply=await request(self.path,self.uid,'custodian_readiness',session_ref,timeout=min(self.timeout,30))
        if reply['status']!='ok':raise ValueError('Current read-only custody inspection unavailable')
        return reply['result']
    async def final(self,comparison):
        value=await self._call('custodian_final',{'comparison':comparison})
        if set(value)!={'decision','evidence_ref','evidence'} or self.requests.put(value['evidence'])!=value['evidence_ref']:raise ValueError('Final aggregate transfer differs from its exact Ref')
        return value['decision'],value['evidence_ref']
    async def sign(self,record):return await self._call('custodian_sign_terminal',{'record':record})
