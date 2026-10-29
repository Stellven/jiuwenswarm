"""Literal preregistered calibration measurements without release authority.

Expected labels remain in CheckAssetAdmissions. Installed check handlers see
captured case material; semantic calls see only declaration/output/instructions.
Protected composition supplies any necessary frozen host context and a bound
governed model port, never a candidate PASS boolean or configurable factory.
"""
from __future__ import annotations
import asyncio
import copy
import hashlib
import inspect
import json
from pathlib import Path
from .engine import CheckContext
from ..contracts import ResearchError
from ..gate import SemanticVerifier
from ..state import json_bytes
from .verifier import contract_is


def require(value,reason):
    if not value:raise ResearchError('calibration_runner',reason)


class CalibrationMeasurements:
    def __init__(self,admissions,checks,*,case_contexts=None,model_ports=None,private_request_ref=None):
        self.admissions=admissions;self.store=admissions.store;self.checks=checks
        self.contexts=dict(case_contexts or {});self.models=dict(model_ports or {})
        self.private_request_ref=private_request_ref

    def _produced(self,ref):
        if self.private_request_ref is not None:
            self.store.read_blob(ref)
            identity=hashlib.sha256(json_bytes(ref)).hexdigest()
            self.store.append_record('calibration-material',{'id':'calibration-material:'+identity,'artifact_ref':ref,'calibration_only':True})
        return ref

    def install(self,profile_ref,actor):
        profile,_=self.admissions._profile(profile_ref)
        implementation=profile['measurement_runner_ref']
        require(self.store.read_blob(implementation)==Path(__file__).read_bytes(),'Calibration profile does not pin this exact installed measurement adapter')
        installed=self.admissions._runners.get(implementation['sha256'])
        if installed is None:self.admissions.register_runner(implementation,self.evaluate)
        else:require(installed==(implementation,self.evaluate),'Installed calibration adapter is ambiguous')
        return self.admissions.register_profile(profile_ref,actor)

    def _context(self,case,closure,profile_ref):
        declaration=self.store.read_record(case['declaration_ref'],contract_id='capsule-declaration')
        key=(profile_ref['sha256'],case['case_id']);bound=self.contexts.get(key)
        if bound is None:
            # Output-only challenges need no producing worker or invented
            # runtime observation. Input-dependent handlers fail closed unless
            # their actual protected frozen context is supplied separately.
            contract={'schema':'ai4r-calibration-subject:1','id':'calibration-subject:'+profile_ref['sha256']+':'+case['case_id'],
                'declaration_ref':case['declaration_ref'],'inputs':[],'input_refs':[],
                'outputs':[{'name':p['name'],'contract_id':p['schema_ref'],'required':p['required']} for p in declaration['ports']['outputs']]}
            contract_ref=self.store.append_record('calibration-subject',contract);observation={};output_refs={case['output_port']:case['subject_ref']};inputs={};host=()
        else:
            require(set(bound)=={'contract_ref','observation_ref','output_refs'},'Unknown protected calibration context fields')
            contract_ref=bound['contract_ref'];contract=self.store.read_record(contract_ref)
            fixture=contract.get('schema')=='ai4r-calibration-fixture:2'
            private=contract.get('schema')=='ai4r-calibration-subject:1' or fixture
            observation=self.store.read_record(bound['observation_ref'],contract_id='invocation-observation') if bound['observation_ref'] is not None else None
            require(observation is not None and observation.get('contract_ref')==contract_ref
                or private and observation is None and (fixture or not contract.get('inputs') and not contract.get('input_refs')),
                'Calibration observation belongs to another subject or is unavailable')
            if fixture:
                require(self.store.record_kind(contract_ref)=='calibration-fixture' and contract.get('invalid_for_product') is True
                    and contract.get('accepted') is False and bound['observation_ref'] is None,
                    'Static fixture cannot supply a product invocation observation')
            require((contract.get('declaration_ref') if private else contract['bindings'][0]['declaration_ref'])==case['declaration_ref'],'Calibration context names another declaration')
            output_refs=copy.deepcopy(bound['output_refs']);require(not observation or observation['output_refs']==list(output_refs.values()),'Calibration output capture was swapped')
            def decode(ref):
                raw=self.store.read_blob(ref)
                try:return json.loads(raw.decode('utf-8'))
                except (ValueError,UnicodeError):return raw
            inputs={p['name']:[decode(r) for r in p['artifact_refs']] for p in contract['inputs']}
            inputs={name:values[0] if len(values)==1 else values for name,values in inputs.items()};host=()
        require(output_refs.get(case['output_port'])==case['subject_ref'],'Calibration case is not the exact captured output')
        outputs={}
        for name,ref in output_refs.items():
            raw=self.store.read_blob(ref)
            try:outputs[name]=json.loads(raw.decode('utf-8'))
            except (ValueError,UnicodeError):outputs[name]=raw
        bundle=self.store.read_record(closure['bundle_ref'],contract_id='check-bundle')
        profile=self.store.read_record(closure['profile_ref'],contract_id='checking-profile')
        identity='calibration:'+hashlib.sha256(json_bytes([profile_ref,case['case_id']])).hexdigest()[:32]
        plan={'schema_version':'2.0.0','id':identity+':checks',
            'contract_ref':contract_ref,'node_contract_ref':contract.get('node_contract_ref',contract_ref),
            'input_refs':contract.get('input_refs',[]),'profile_ref':closure['profile_ref'],'policy_ref':profile_ref,
            'mandatory_deterministic':[c['check_id'] for c in bundle['checks'] if c['blocking']],
            'mandatory_semantic':[c['criterion_id'] for c in profile['criteria'] if c['blocking']],
            'runner_refs':[closure['bundle_ref'],*closure['runner_refs']],'subnode_id':contract.get('subnode_id')}
        kind='bound-check-plan'
        if self.private_request_ref is not None:
            plan.pop('schema_version');plan.update(schema='ai4r-calibration-check-plan:1',request_ref=self.private_request_ref,
                calibration_profile_ref=profile_ref,case_id=case['case_id']);kind='calibration-check-plan'
        plan_ref=self.store.append_record(kind,plan) if self.private_request_ref is not None else self.store.put_record(kind,plan,record_id=plan['id'])
        self._produced(plan_ref)
        return contract_ref,plan_ref,plan,CheckContext(contract,self.store,inputs,outputs,output_refs,observation,host),bundle,profile

    async def evaluate(self,case,closure,profile_ref):
        profile,registered,_=self.admissions._registered(profile_ref)
        require(registered==closure and case in profile['cases'],'Calibration case/closure differs from preregistration')
        claim='calibration-adapter:'+profile_ref['sha256']+':'+case['case_id']
        with self.store.transaction() as db:
            issued=db.execute('SELECT state FROM calibration_attempts WHERE profile_sha=? AND case_id=?',(profile_ref['sha256'],case['case_id'])).fetchone()
            require(issued is not None and issued['state']=='issued','No protected issued calibration action')
            require(db.execute('SELECT 1 FROM metadata WHERE key=?',(claim,)).fetchone() is None,'Calibration adapter already started; reconcile without replay')
            db.execute('INSERT INTO metadata VALUES(?,?)',(claim,json_bytes({'profile_ref':profile_ref,'case_id':case['case_id']}).decode()))
        contract_ref,plan_ref,plan,context,bundle,checking=self._context(case,closure,profile_ref)
        if case['asset_kind']=='bundle':
            results=await self.checks.run(plan,context,bundle_id=bundle['bundle_id'])
            value={'schema_version':'1.0.0','subject_ref':case['subject_ref'],'check_plan_ref':plan_ref,'results':results}
            return {'result_ref':self._produced(self.store.put_record('deterministic-check-result',value)),'model_call_refs':[]}
        port=self.models.get((profile_ref['sha256'],case['case_id']))
        if port is None:raise ResearchError('calibration_model_unavailable','No exact protected governed model port for this registered case')
        try:results=await self.checks.run(plan,context,bundle_id=bundle['bundle_id'])
        except (ResearchError,KeyError,TypeError,ValueError,OSError) as error:
            if self.private_request_ref is None:raise
            # Criteria and deterministic assets have separate challenge cases.
            # Missing host context cannot qualify the bundle or prevent the
            # separately authorized declaration/output-only criteria measure.
            results=[{'check_id':c['check_id'],'outcome':'ENVIRONMENT_BLOCKED',
                'reason':'Actual registered host predicate context unavailable: '+type(error).__name__,
                'evidence_refs':list(context.output_refs.values())} for c in bundle['checks']]
        checked=self._produced(self.store.put_record('deterministic-check-result',{'schema_version':'1.0.0','subject_ref':case['subject_ref'],'check_plan_ref':plan_ref,'results':results}))
        call_refs=[]
        async def invoke(prompt,*,system):
            require(not call_refs,'Calibration review makes only one actual model call')
            try:
                async with asyncio.timeout(checking['time_s']):
                    value=port.invoke(prompt,system=system)
                    if inspect.isawaitable(value):value=await value
            except (asyncio.CancelledError,TimeoutError):
                ack=port.contain()
                if inspect.isawaitable(ack):ack=await ack
                if not isinstance(ack,dict) or ack.get('contained') is not True:raise ResearchError('calibration_containment_uncertain','Actual calibration model containment is unconfirmed')
                raise
            require(isinstance(value,dict) and isinstance(value.get('text'),str) and value.get('call_ref'),'Calibration model lacks actual captured text/call identity')
            call_refs.append(value['call_ref'])
            capture=getattr(port,'capture_returned_evidence',None)
            if capture is not None:
                # This is awaited before assessment publication. It remains
                # under the whole-request deadline, while allowing concurrent
                # IPC returns/deadline callbacks to run on this event loop.
                captured=capture()
                if inspect.isawaitable(captured):await captured
            return value['text']
        review={'schema_version':'2.0.0','id':plan['id'].replace(':checks',':review'),
            'subject_ref':case['subject_ref'],'contract_ref':contract_ref,'check_plan_ref':plan_ref,'input_refs':context.contract.get('input_refs',[]),
            'deterministic_result_ref':checked,'criteria':plan['mandatory_semantic'],'observations':[],
            'evidence_classes':['captured_input_and_output'],'node_contract_ref':plan['node_contract_ref'],'subnode_id':plan['subnode_id']}
        # This calibration manifest records supplied challenges; it cannot be
        # consumed by a product advancing gate, and no worker is invoked here.
        review_ref=self._produced(self.store.put_record('review-context',review))
        declared=self.store.read_record(case['declaration_ref'])
        schema=next(p['schema_ref'] for p in declared['ports']['outputs'] if p['name']==case['output_port'])
        result=await SemanticVerifier(self.store).review(case['declaration_ref'],case['subject_ref'],closure['profile_ref'],review_ref,
            case['output_port'],invoke,zip_output=contract_is(schema,'poc-artifact-bundle'))
        return {'result_ref':self._produced(result),'model_call_refs':call_refs}
