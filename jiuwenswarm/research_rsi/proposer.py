"""One bounded proposal via the existing separately configured governed bridge."""
import asyncio
import json
from .profiles import Limits


class GuardedProposer:
    def __init__(self,model,*,configuration_ref,improver_ref,limits=None,store=None):
        self.model,self.configuration_ref,self.improver_ref=model,configuration_ref,improver_ref
        self.limits=limits or Limits()
        self.store=store;self.last_evidence=[];self.last_model_calls=None;self.last_capture={};self.last_response_ref=None
    async def propose(self,visible_context,feedback):
        self.last_evidence=[];self.last_model_calls=None;self.last_capture={};self.last_response_ref=None
        if feedback is not None and set(feedback)!={'schema_version','id','passed','total','queries_left'}:raise ValueError('feedback envelope leaks protected information')
        # model is the bound core ctx.model adapter, never an independent SDK.
        prompt=json.dumps({'instruction':'Return one proposed replacement body and a short rationale. Preserve the frozen interface and mandatory tests.',
            'visible_context':visible_context,'feedback':feedback},ensure_ascii=False,allow_nan=False)
        try:result=await asyncio.wait_for(self.model(prompt),timeout=self.limits.per_call_s)
        finally:
            self.last_evidence=list(getattr(self.model,'last_evidence',[]))
            self.last_model_calls=getattr(self.model,'last_model_calls',None)
        if not isinstance(result,str):raise ValueError('proposal text unavailable')
        if self.store:self.last_response_ref=self.store.put_bytes(result.encode('utf8'))
        if len(result.encode('utf8'))>4*1024*1024:raise ValueError('proposal response exceeds protected transport policy')
        def pairs(items):
            value={}
            for key,item in items:
                if key in value:raise ValueError('duplicate proposal field')
                value[key]=item
            return value
        try:value=json.loads(result,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite proposal')))
        except ValueError:raise ValueError('malformed proposal; no implicit retry') from None
        if isinstance(value,dict):
            # Preserve actual bytes even when another proposal field is invalid.
            # Missing bytes remain absent; no placeholder child is manufactured.
            if self.store and isinstance(value.get('body'),str):self.last_capture['child_ref']=self.store.put_bytes(value['body'].encode('utf8'))
            if isinstance(value.get('rationale'),str) and 0<len(value['rationale'])<=2000:self.last_capture['rationale']=value['rationale']
        if not isinstance(value,dict) or set(value)!={'path','body','rationale'} or not all(isinstance(value[k],str) for k in value) or not value['path'] or not 0<len(value['rationale'])<=2000:raise ValueError('proposal contract mismatch')
        return value


class BridgeProposalModel:
    """Bind an existing governed IPC client to one protected proposer context."""
    def __init__(self,client,context):self.client,self.context=client,context;self.last_evidence=[];self.last_model_calls=None
    async def __call__(self,prompt):
        self.last_evidence=[];self.last_model_calls=None
        result=await self.client.call(self.context,prompt)
        self.last_evidence=[result[k] for k in ('call_ref','route_ref') if result.get(k)]
        if result.get('call_ref'):self.last_model_calls=1
        return result['text']
