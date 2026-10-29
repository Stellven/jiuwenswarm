"""Exact IF011 consumer; unknown execution is reconciled and never replayed."""
from __future__ import annotations
import base64,hashlib,json
from .records import encoded
from .trial_port import validate_private,validate_parent
from .ports import request

TRIAL_SOCKET='/run/ai4r-rsi-trial/trial.sock'


class TextTrialClient:
    def __init__(self,store,*,allowed_session_refs,transport=None,socket_path=TRIAL_SOCKET,peer_uid=12001,capture=None,timeout=300):
        if socket_path!=TRIAL_SOCKET or peer_uid!=12001 or not 0<timeout<=300:raise ValueError('Unknown protected trial process binding')
        self.store,self.capture=store,capture
        self.sessions=frozenset(encoded(pin) for pin in allowed_session_refs)
        if transport is None:
            async def transport(operation,pin):
                reply=await request(socket_path,peer_uid,operation,pin,timeout=timeout)
                if reply['status']!='ok':raise ValueError('Trial unavailable; inspect existing evidence without replay')
                return reply['result']
        self.transport=transport
    @staticmethod
    def validate_result(binding,trial,result):
        validate_private('result',result)
        for key in ('session_ref','target_ref','parent_declaration_ref','child_declaration_ref'):
            if result[key]!=binding[key]:raise ValueError('Trial result identity differs')
        if result['trial_ref']!=trial or result['accepted'] is not False:raise ValueError('Trial cannot publish acceptance')
        return result
    def _capture(self,reply,binding,trial):
        if set(reply)!={'result_ref','captures'} or not isinstance(reply['captures'],list) or self.capture is None:
            raise ValueError('Exact private result capture is unavailable')
        seen=set()
        for item in reply['captures']:
            if not isinstance(item,dict) or set(item)!={'kind','ref','bytes_base64'}:raise ValueError('Unknown trial capture')
            if item['kind'] not in {'declared-output','isolated-evaluation-result','isolated-evaluation-failure','isolated-reservation-claim','isolated-required-test','trial-measurement','deterministic-check-result','verifier-assessment','invocation-observation','model-call','route-record','model-call-input','model-call-output','model-provider-observation','native-governed-trace','native-governed-trace-event','native-governed-packet','execution-receipt','builder-execution','bound-check-plan','isolated-evaluation-check-plan'}:raise ValueError('Private or unknown trial capture kind')
            raw=base64.b64decode(item['bytes_base64'],validate=True);pin=item['ref']
            if encoded(pin) in seen or hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('Trial capture changed or duplicated')
            self.capture.put_ref(pin,raw);seen.add(encoded(pin))
        result=json.loads(self.capture.read(reply['result_ref']))
        self.validate_result(binding,trial,result)
        required=[r['artifact_ref'] for r in result['outputs']]+result['observation_refs']+result['trace_refs']+result['assessment_refs']
        if result['deterministic_result_ref'] is not None:required.append(result['deterministic_result_ref'])
        if result['failure'] is not None:required+=result['failure']['evidence_refs']
        if any(encoded(pin) not in seen for pin in [reply['result_ref'],*required]):raise ValueError('Required original trial bytes are missing')
        return result,reply['result_ref']
    async def execute(self,binding_ref):
        binding=self.store.get(binding_ref);validate_private('binding',binding)
        if encoded(binding['session_ref']) not in self.sessions:raise ValueError('Trial session is outside custody grant')
        if not self.store.claim_job(binding_ref):raise ValueError('Trial was already started; inspect without replay')
        prepared=await self.transport('trial_prepare',binding_ref)
        if set(prepared)!={'trial_ref'}:raise ValueError('Unknown prepare response')
        self.store.put({'schema':'ai4r-rsi-trial-start:1','binding_ref':binding_ref,'trial_ref':prepared['trial_ref']})
        reply=await self.transport('trial_execute',prepared['trial_ref'])
        result,pin=self._capture(reply,binding,prepared['trial_ref'])
        self.store.finish_job(binding_ref,{'state':'terminal','trial_ref':prepared['trial_ref'],'result_ref':pin})
        return result,pin
    async def inspect(self,binding_ref,trial_ref):
        binding=self.store.get(binding_ref);validate_private('binding',binding)
        if encoded(binding['session_ref']) not in self.sessions:raise ValueError('Trial session is outside custody grant')
        reply=await self.transport('trial_inspect',trial_ref)
        if reply.get('status')=='outcome_unknown':return reply
        return self._capture(reply,binding,trial_ref)


class ParentMeasurementClient(TextTrialClient):
    """Exact admitted-original-parent consumer; no child relabeling path."""
    @staticmethod
    def validate_result(binding,grant,result,*,binding_ref):
        validate_parent('result',result)
        if (result['grant_ref']!=grant or result['binding_ref']!=binding_ref or result['accepted'] is not False
                or any(result[k]!=binding[k] for k in ('session_ref','target_ref','parent_declaration_ref'))):
            raise ValueError('Original-parent measurement identity differs')
        return result
    def _capture_parent(self,reply,binding,grant,binding_ref):
        if set(reply)!={'result_ref','captures'} or not isinstance(reply['captures'],list) or self.capture is None:
            raise ValueError('Exact original-parent capture is unavailable')
        allowed={'declared-output','admitted-parent-result','trial-measurement','deterministic-check-result','verifier-assessment',
            'invocation-observation','model-call','route-record','model-call-input','model-call-output','model-provider-observation','native-governed-trace','native-governed-trace-event','native-governed-packet',
            'execution-receipt','builder-execution','bound-check-plan','isolated-evaluation-check-plan'}
        seen=set()
        for item in reply['captures']:
            if not isinstance(item,dict) or set(item)!={'kind','ref','bytes_base64'} or item['kind'] not in allowed:
                raise ValueError('Private or unknown original-parent capture')
            raw=base64.b64decode(item['bytes_base64'],validate=True);pin=item['ref']
            if encoded(pin) in seen or hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('Parent capture changed or duplicated')
            self.capture.put_ref(pin,raw);seen.add(encoded(pin))
        result=json.loads(self.capture.read(reply['result_ref']));self.validate_result(binding,grant,result,binding_ref=binding_ref)
        measured=json.loads(self.capture.read(result['measurement_ref']))
        if measured['contract_ref']!=result['contract_ref'] or measured['accepted'] is not False:
            raise ValueError('Returned measurement changed canonical admitted subject')
        refs=[reply['result_ref'],result['measurement_ref'],measured['deterministic_ref'],measured['observation_ref'],
            *measured['output_refs'].values(),*measured['assessment_refs'],*measured['verifier_check_refs'],*measured['observation_refs'],*measured['trace_refs']]
        if any(encoded(pin) not in seen for pin in refs):raise ValueError('Original parent measurement closure is incomplete')
        return result,reply['result_ref']
    async def execute(self,binding_ref):
        binding=self.store.get(binding_ref);validate_parent('binding',binding)
        if encoded(binding['session_ref']) not in self.sessions:raise ValueError('Parent session is outside custody grant')
        if not self.store.claim_job(binding_ref):raise ValueError('Parent measurement already started; inspect without replay')
        prepared=await self.transport('parent_prepare',binding_ref)
        if set(prepared)!={'grant_ref'}:raise ValueError('Unknown original-parent prepare response')
        self.store.put({'schema':'ai4r-rsi-parent-start:1','binding_ref':binding_ref,'grant_ref':prepared['grant_ref']})
        reply=await self.transport('parent_execute',prepared['grant_ref'])
        result,pin=self._capture_parent(reply,binding,prepared['grant_ref'],binding_ref)
        self.store.finish_job(binding_ref,{'state':'terminal','grant_ref':prepared['grant_ref'],'result_ref':pin})
        return result,pin
    async def inspect(self,binding_ref,grant_ref):
        binding=self.store.get(binding_ref);validate_parent('binding',binding)
        if encoded(binding['session_ref']) not in self.sessions:raise ValueError('Parent session is outside custody grant')
        reply=await self.transport('parent_inspect',grant_ref)
        if reply.get('status')=='outcome_unknown':return reply
        return self._capture_parent(reply,binding,grant_ref,binding_ref)
