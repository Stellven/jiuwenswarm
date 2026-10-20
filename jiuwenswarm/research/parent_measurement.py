"""Private IF012 original-parent measurements; no child or release authority."""
from __future__ import annotations
import asyncio
import base64
import copy
import hashlib
import json
from importlib.resources import files
from .contracts import ResearchError,validate,contract_schema
from .contracts.rsi import verify_signature
from .state import json_bytes
from .binding import ContractFactory


def require(value,reason):
    if not value:raise ResearchError('parent_measurement',reason)


def private_validate(kind,value):
    from jsonschema import Draft202012Validator
    suffix='.v2' if kind=='binding' and value.get('schema')=='ai4r-admitted-measurement-binding:2' else ''
    schema=json.loads(files('jiuwenswarm.research_contracts').joinpath('schemas/admitted-measurement-'+kind+suffix+'.schema.json').read_text('utf-8'))
    require(not list(Draft202012Validator(schema).iter_errors(value)),'Invalid closed IF012 '+kind)


class ParentMeasurement:
    def __init__(self,resources,*,admitted=None):
        from .admitted_measurement import AdmittedMeasurementResources
        self.resources=resources;self.store=resources.store;self.library=resources.composition.library
        self.admitted=admitted or AdmittedMeasurementResources(resources)

    def _reservation(self,binding):
        value=self.store.read_record(binding['reservation_ref']);operator=self.resources.operator.snapshot()['rsi']
        fields={'schema','id','session_ref','target_ref','parent_declaration_ref','phase','repeat_index','inputs_sha256',
            'configuration_ref','action_id','charge_kind','queries_used','queries_left','signer_key_id','signature'}
        version='2' if binding['schema']=='ai4r-admitted-measurement-binding:2' else '1'
        versions={version,'3'} if version=='2' else {version}
        require(set(value)==fields and value['schema'] in {'ai4r-rsi-parent-reservation:'+v for v in versions},'Unknown or mismatched parent reservation representation')
        public=operator.get('custodian_public_key');require(public and operator.get('custodian_key_id'),'Pinned parent reservation key is unavailable')
        verify_signature(value,base64.urlsafe_b64decode(public+'='*(-len(public)%4)),operator['custodian_key_id'])
        require(all(value[k]==binding[k] for k in ('session_ref','target_ref','parent_declaration_ref','phase','repeat_index','configuration_ref')),'Reservation belongs to another original parent context')
        require(value['inputs_sha256']==hashlib.sha256(json_bytes(binding['inputs'])).hexdigest(),'Parent reservation input hash differs')
        require(isinstance(value['id'],str) and value['id'] and isinstance(value['action_id'],str) and value['action_id'],'Charged comparison action identity is missing')
        expected='loop' if binding['phase']=='hidden_loop' else 'final' if binding['phase'] in {'hidden_final','platform'} else 'development'
        require(value['charge_kind']==expected,'Parent reservation phase differs from its charged action')
        session=self.store.read_record(binding['session_ref'],contract_id='rsi-session');cap=session['limits']['session_query_limit']
        require(type(value['queries_used']) is int and type(value['queries_left']) is int and 0<=value['queries_used']<=cap<=30
            and 0<=value['queries_left'] and value['queries_used']+value['queries_left']<=cap,'Parent query exposure exceeds the frozen source cap')
        if expected=='loop':require(value['queries_used']>=1,'A hidden-loop parent measurement must already be charged')
        from .measurement_slots import parse_slot
        parse_slot(value,binding,self.store.read_record(binding['target_ref'],contract_id='rsi-target-profile'),session)
        return value

    def _validate(self,binding):
        private_validate('binding',binding)
        contract,plan,parent,_,_,_=self.admitted._validate(binding['parent_contract_ref'],binding['parent_check_plan_ref'])
        selected=contract['bindings'][0];declaration=self.store.read_record(binding['parent_declaration_ref'],contract_id='capsule-declaration')
        require(selected['declaration_ref']==binding['parent_declaration_ref'] and selected['admission_ref']==binding['parent_admission_ref'],'Canonical subject is not the exact admitted original parent')
        session=self.store.read_record(binding['session_ref'],contract_id='rsi-session');target=self.store.read_record(binding['target_ref'],contract_id='rsi-target-profile')
        require(session['target_profile_ref']==binding['target_ref'] and session['parent_declaration_ref']==target['parent_declaration_ref']==binding['parent_declaration_ref'],'Session or target names another parent')
        require(session['parent']=={'cc_name':declaration['identity']['name'],'cc_version':declaration['identity']['version_label'],'declaration_sha256':binding['parent_declaration_ref']['sha256']},'Frozen session parent pin differs')
        require(session['configuration_ref']==target['configuration_ref']==binding['configuration_ref']==contract['configuration_ref'],'Frozen comparison configuration differs')
        expected=self.resources.exact_binding_refs
        require(all(binding[k]==expected[k] for k in ('configuration_ref','model_selection_profile_ref','deployment_ref')),'Parent cannot select different protected model resources')
        repeats=session['pass_count_repeats'];require(type(repeats) is int and repeats in (1,3) and binding['repeat_index']<repeats,'Parent repeat is outside frozen source policy')
        require(all(binding['limits'][k]<=min(target['limits'][k],parent['node_limits'][k]) for k in binding['limits']),'Parent measurement widens target or original limits')
        require(binding['limits']['time_s']<=session['limits']['per_call_s'],'Parent measurement exceeds the frozen per-call ceiling')
        self.store.read_blob(target['frozen_contract_ref'])
        declared={p['name']:p for p in declaration['ports']['inputs']};original={p['name']:p for p in contract['inputs']}
        v2=binding['schema']=='ai4r-admitted-measurement-binding:2';names=[p['name'] for p in binding['inputs']]
        require((names==['brief','candidate_set']) if v2 else (len(names)==len(declared) and set(names)==set(declared)),'Original-parent external input inventory differs from its explicit version')
        ports=copy.deepcopy(binding['inputs'])
        row=self.library.get(declaration['identity']['name'],declaration['identity']['version_label'])
        rubric=row['body_refs']['screening_rubric.json']
        require(rubric in selected['implementation_refs'],'Original-parent rubric is outside its exact admitted implementation')
        from .checks.admission import rubric_checks
        require(all(r['outcome']=='PASS' for r in rubric_checks(self.store.read_blob(rubric))),'Original-parent rubric violates source admission invariants')
        if v2:ports.append({'name':'screening_rubric','contract_id':original['screening_rubric']['contract_id'],'artifact_refs':[rubric]})
        inputs=[]
        for port in ports:
            spec=declared[port['name']]
            require(port['contract_id']==original[port['name']]['contract_id'] or contract_schema(port['contract_id'])==contract_schema(original[port['name']]['contract_id']),'Original-parent input contract changed')
            require(port['artifact_refs'] or not spec['required'],'Required original-parent input is absent')
            self.store.require_product_material(port['artifact_refs'])
            for ref in port['artifact_refs']:
                require((v2 and port['name']=='screening_rubric' and ref==rubric) or ref in parent['authority_ceiling']['resource_reads'],'Signed input is outside the original protected resource grant')
                raw=self.store.read_blob(ref)
                if port['contract_id']!='opaque-bytes':validate(port['contract_id'],json.loads(raw.decode('utf-8')))
            inputs.append({**copy.deepcopy(original[port['name']]),'artifact_refs':copy.deepcopy(port['artifact_refs'])})
        require(next(p for p in inputs if p['name']=='screening_rubric')['artifact_refs']==[rubric],'Original-parent work rubric differs from its actual admitted body')
        self._reservation(binding)
        return contract,parent,inputs

    def prepare_admitted_measurement(self,binding_ref):
        binding=self.store.read_record(binding_ref);contract,parent,inputs=self._validate(binding)
        identity='parent-grant:'+hashlib.sha256(json_bytes(binding_ref)).hexdigest()
        existing=[r for r in self.store.iter_records(kinds=('admitted-parent-grant',)) if r['record']['binding_ref']==binding_ref]
        if existing:require(len(existing)==1,'Ambiguous original-parent grant');return existing[0]['ref']
        self.library._require_rsi_security('trial',binding['session_ref'],binding['parent_declaration_ref'])
        verifiers={tuple(sorted(self.store.read_record(a['capsule_ref'],contract_id='capsule-declaration')['identity'][k] for k in ('name','version_label'))) for a in parent['subnodes'] if a['role']=='verifier'}
        require(len(verifiers)==1,'Original-parent reviewer identity is missing or ambiguous')
        assignment=next(a for a in parent['subnodes'] if a['role']=='verifier')
        vd=self.store.read_record(assignment['capsule_ref'],contract_id='capsule-declaration')['identity']
        verifier_pin={'cc_name':vd['name'],'cc_version':vd['version_label'],'declaration_sha256':assignment['capsule_ref']['sha256']}
        factory=ContractFactory(self.store,self.library,verifier_pin=verifier_pin,finalization_profile_ref=parent['checking_profile_ref'])
        run_id='parent-measure:'+hashlib.sha256(json_bytes(binding_ref)).hexdigest()[:32]
        try:self.store.get_run(run_id,account_id=self.resources.principal.account_id)
        except ResearchError as error:
            if error.code!='not_found':raise
            self.store.create_run(run_id,account_id=self.resources.principal.account_id,workspace_id=self.resources.exact_binding_refs['workspace_id'],submission={})
        selected=contract['bindings'][0];decl=self.store.read_record(selected['declaration_ref'])['identity']
        pin={'cc_name':decl['name'],'cc_version':decl['version_label'],'declaration_sha256':selected['declaration_ref']['sha256']}
        enclosing=factory.prepare_parent(run_id,parent['node_id'],[{'subnode_id':contract['subnode_id'],'cc':pin,'depends_on':[]}],
            inputs=inputs,outputs=copy.deepcopy(contract['outputs']),objective=parent['objective'],requirement_ids=parent['requirement_ids'],limits=copy.deepcopy(binding['limits']),
            policy_ref=parent['policy_ref'],configuration_ref=parent['configuration_ref'],template_ref=parent['template_ref'],authority_ceiling=copy.deepcopy(parent['authority_ceiling']))
        subject,checks,_=factory.bind_subnode(enclosing,contract['subnode_id'],inputs)
        inner=self.admitted.prepare(subject,checks,semantic_review=True)
        value={'schema':'ai4r-admitted-measurement-grant:1','id':identity,'binding_ref':binding_ref,'contract_ref':subject,'check_plan_ref':checks,
            'session_ref':binding['session_ref'],'target_ref':binding['target_ref'],'parent_declaration_ref':binding['parent_declaration_ref'],'accepted':False}
        private_validate('grant',value);grant=self.store.append_record('admitted-parent-grant',value)
        self.store.append_record('admitted-parent-adapter-binding',{'id':identity+':adapter','grant_ref':grant,'measurement_grant_ref':inner})
        return grant

    async def execute_admitted_measurement(self,grant_ref):
        grant=self.store.read_record(grant_ref);private_validate('grant',grant)
        require(self.store.record_kind(grant_ref)=='admitted-parent-grant','No protected original-parent grant')
        binding=self.store.read_record(grant['binding_ref']);self._validate(binding)
        require(all(grant[k]==binding[k] for k in ('session_ref','target_ref','parent_declaration_ref')),'Parent grant provenance differs')
        prior=[r for r in self.store.iter_records(kinds=('admitted-parent-result',)) if r['record']['grant_ref']==grant_ref]
        if prior:require(len(prior)==1,'Ambiguous original-parent terminal result');return prior[0]['ref']
        self.library._require_rsi_security('trial',binding['session_ref'],binding['parent_declaration_ref'])
        reservation=self._reservation(binding)
        from .measurement_slots import claim_reservation
        claim=claim_reservation(self.store,binding,reservation,owner='parent',binding_ref=grant['binding_ref'],
            target=self.store.read_record(binding['target_ref'],contract_id='rsi-target-profile'),
            session=self.store.read_record(binding['session_ref'],contract_id='rsi-session'),
            references={'grant_ref':grant_ref},validate_legacy=self._reservation)
        key=claim['id']
        adapters=[r['record'] for r in self.store.iter_records(kinds=('admitted-parent-adapter-binding',)) if r['record']['grant_ref']==grant_ref]
        require(len(adapters)==1,'Missing exact installed parent adapter binding')
        try:
            measured=await self.admitted.execute(adapters[0]['measurement_grant_ref']);measurement_ref=measured.measurement_ref
        except asyncio.CancelledError:
            measured=[r for r in self.store.iter_records(kinds=('trial-measurement',)) if r['record']['contract_ref']==grant['contract_ref']]
            require(len(measured)==1,'Cancelled original-parent work lacks a terminal measurement; reconcile without replay')
            measurement_ref=measured[0]['ref']
        raw=self.store.read_record(measurement_ref);require(self.store.record_kind(measurement_ref)=='trial-measurement' and raw['contract_ref']==grant['contract_ref'] and raw['accepted'] is False,'Parent adapter returned another measurement')
        value={'schema':'ai4r-admitted-measurement-result:1','id':key+':result','grant_ref':grant_ref,'binding_ref':grant['binding_ref'],
            **{k:grant[k] for k in ('session_ref','target_ref','parent_declaration_ref','contract_ref','check_plan_ref')},
            'status':raw['status'],'measurement_ref':measurement_ref,'accepted':False}
        private_validate('result',value)
        return self.store.append_record('admitted-parent-result',value)
