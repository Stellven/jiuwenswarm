"""Private IF011 trials. No production Library or acceptance writer is exposed."""
from __future__ import annotations

import asyncio
import copy
import fnmatch
import hashlib
import inspect
import json
import time
import uuid
from importlib.resources import files

from .contracts import ResearchError, validate
from .contracts.rsi import verify_signature
from .gate import SemanticVerifier, assemble_assessment
from .runner import CapsuleArtifacts, InvocationContext, CapsuleRunner
from .state import json_bytes, utc_now


def require(condition,reason):
    if not condition:raise ResearchError('isolated_evaluation',reason)


def private_validate(name,value):
    from jsonschema import Draft202012Validator
    suffix='.v2' if name=='binding' and value.get('schema')=='ai4r-isolated-evaluation-binding:2' else ''
    document=json.loads(files('jiuwenswarm.research_contracts').joinpath('schemas/isolated-evaluation-'+name+suffix+'.schema.json').read_text('utf-8'))
    errors=list(Draft202012Validator(document).iter_errors(value))
    require(not errors,'Invalid closed private '+name+' record')


class SignedTrialReservations:
    """Independently authenticate a projection of the custodian's charged action.

    This once claim is not an oracle budget and never refunds a hidden query.
    The signing key is fixed by protected startup, never by the trial binding.
    """
    def __init__(self,store,public_key,key_id):
        self.store,self.public_key,self.key_id=store,public_key,key_id

    def validate(self,binding):
        value=self.store.read_record(binding['reservation_ref'])
        fields={'schema','id','session_ref','target_ref','child_declaration_ref','phase','repeat_index','inputs_sha256',
                'configuration_ref','action_id','charge_kind','queries_used','queries_left','signer_key_id','signature'}
        version='2' if binding['schema']=='ai4r-isolated-evaluation-binding:2' else '1'
        versions={version,'3'} if version=='2' else {version}
        require(set(value)==fields and value['schema'] in {'ai4r-rsi-trial-reservation:'+v for v in versions},'Unknown or mismatched reservation representation')
        require(self.public_key is not None and self.key_id is not None,'Pinned custodian verification key is unavailable')
        verify_signature(value,self.public_key,self.key_id)
        require(all(value[k]==binding[k] for k in ('session_ref','target_ref','child_declaration_ref','phase','repeat_index','configuration_ref')),
                'Reservation belongs to another session/candidate/phase/repeat/configuration')
        require(value['inputs_sha256']==hashlib.sha256(json_bytes(binding['inputs'])).hexdigest(),'Reservation input closure differs')
        require(isinstance(value['id'],str) and value['id'] and isinstance(value['action_id'],str) and value['action_id'],'Missing charged action identity')
        expected='loop' if binding['phase']=='hidden_loop' else 'final' if binding['phase'] in {'hidden_final','platform'} else 'development'
        require(value['charge_kind']==expected,'Reservation charge kind does not match its source phase')
        session=self.store.read_record(binding['session_ref'],contract_id='rsi-session');cap=session['limits']['session_query_limit']
        require(type(value['queries_used']) is int and type(value['queries_left']) is int and 0<=value['queries_used']<=cap<=30
                and 0<=value['queries_left'] and value['queries_used']+value['queries_left']<=cap,'Invalid source query exposure')
        from .measurement_slots import parse_slot
        parse_slot(value,binding,self.store.read_record(binding['target_ref'],contract_id='rsi-target-profile'),session)
        return binding['reservation_ref']

    def claim(self,trial_ref,binding_ref,binding):
        self.validate(binding)
        reservation=self.store.read_record(binding['reservation_ref'])
        from .measurement_slots import claim_reservation
        return claim_reservation(self.store,binding,reservation,owner='isolated',binding_ref=binding_ref,
            target=self.store.read_record(binding['target_ref'],contract_id='rsi-target-profile'),
            session=self.store.read_record(binding['session_ref'],contract_id='rsi-session'),
            references={'trial_ref':trial_ref},validate_legacy=self.validate)


class IsolatedEvaluation:
    def __init__(self,resources,*,reservation_authority=None,required_tests=None):
        self.resources=resources;self.store=resources.store;self.library=resources.composition.library
        operator=resources.operator.snapshot()['rsi']
        import base64
        public=operator.get('custodian_public_key')
        key=base64.urlsafe_b64decode(public+'='*(-len(public)%4)) if public else None
        self.reservations=reservation_authority or SignedTrialReservations(self.store,key,operator.get('custodian_key_id'))
        self.required_tests=required_tests;self._active={}

    def _validate(self,binding):
        private_validate('binding',binding)
        store=self.store
        parent=store.read_record(binding['parent_declaration_ref'],contract_id='capsule-declaration')
        child=store.read_record(binding['child_declaration_ref'],contract_id='capsule-declaration')
        target=store.read_record(binding['target_ref'],contract_id='rsi-target-profile')
        session=store.read_record(binding['session_ref'],contract_id='rsi-session')
        require(parent['identity']['name']=='research.screening' and parent['evolution']['rsi']=='propose','Only the installed conditional Screening trial is supported')
        row=self.library.get(parent['identity']['name'],parent['identity']['version_label'])
        require(row['declaration_ref']==binding['parent_declaration_ref'] and row['admission_ref']==binding['parent_admission_ref'],'Parent is not the exact admitted version')
        admission=store.read_record(binding['parent_admission_ref'],contract_id='library-admission')
        require(admission['status']=='admitted' and admission['candidate_ref']==binding['parent_declaration_ref'],'Missing exact parent admission')
        association=self.library.eligible_association(binding['parent_declaration_ref'])
        require(association['bundle_ref']==binding['check_bundle_ref'] and association['profile_ref']==binding['checking_profile_ref'],'Child cannot select or weaken checking assets')
        contract=store.read_record(binding['parent_contract_ref'],contract_id='subnode-execution-contract')
        pbind=contract['bindings'][0];enclosing=store.read_record(contract['node_contract_ref'],contract_id='node-execution-contract')
        require(len(contract['bindings'])==1 and pbind['declaration_ref']==binding['parent_declaration_ref'] and pbind['admission_ref']==binding['parent_admission_ref'],'Parent runtime contract is not the admitted parent binding')
        require(contract['configuration_ref']==binding['configuration_ref']==session['configuration_ref']==target['configuration_ref'],'Frozen parent/session/target configuration differs')
        require(session['target_profile_ref']==binding['target_ref'] and session['parent_declaration_ref']==binding['parent_declaration_ref']
                and target['parent_declaration_ref']==binding['parent_declaration_ref'],'Session target or admitted parent changed')
        require(session['pass_count_repeats'] in (1,3) and binding['repeat_index']<session['pass_count_repeats'],'Repeat index differs from frozen session policy')
        store.read_blob(target['frozen_contract_ref'])
        expected=self.resources.exact_binding_refs
        require(all(binding[k]==expected[k] for k in ('configuration_ref','model_selection_profile_ref','deployment_ref')),'Trial cannot select another model/deployment configuration')
        profile=store.read_record(binding['model_selection_profile_ref'],contract_id='model-selection-profile')
        require(profile['policy_mode']=='fixed_baseline','Private advanced routing export is unavailable; settings cannot be silently changed')
        limits=binding['limits']
        require(all(limits[k]<=min(target['limits'][k],enclosing['node_limits'][k]) for k in limits),'Trial widened parent or target limits')
        require(binding['dependency_refs']==pbind['dependency_refs'],'Child changed inherited dependency closure')
        for ref in binding['dependency_refs']:store.read_blob(ref)
        stripped=[]
        for declaration in (parent,child):
            value=copy.deepcopy(declaration)
            for key in ('version_label','carrier','body','lineage'):value['identity'].pop(key,None)
            stripped.append(value)
        require(stripped[0]==stripped[1],'Child changed protected ports/effects/authority/requirements')
        from .library import version_matches
        require(child['identity']['version_label']!=parent['identity']['version_label'] and version_matches(child['identity']['version_label'],parent['identity']['version_label']+'.x'),'Child version is outside the parent family')
        before={v['path']:v['sha256'] for v in parent['identity']['body']};after={v['path']:v['sha256'] for v in child['identity']['body']}
        touched={p for p in before.keys()|after.keys() if before.get(p)!=after.get(p)}
        globs=[p[6:] for p in parent['evolution']['may_change'] if p.startswith('files:')]
        require(touched and touched<=set(target['mutable_paths']) and all(any(fnmatch.fnmatchcase(p,g) for g in globs) for p in touched),'Mutation escapes frozen target/parent paths')
        # Target1's mutable helper is evaluated by its external pure-function
        # worker. This installed Target2 carrier never imports candidate code.
        require(touched<= {'screening_prompt.txt','screening_rubric.json'},'Mutable helper requires its external Target1 worker')
        v2=binding['schema']=='ai4r-isolated-evaluation-binding:2'
        require(v2 or 'screening_rubric.json' not in touched,'Changed child rubric requires the version2 subject-owned input binding')
        require(set(binding['child_body_refs'])==set(after),'Incomplete or additional child body paths')
        for path,digest in after.items():
            require(binding['child_body_refs'][path]['sha256']==digest,'Child body does not match declaration')
            store.read_blob(binding['child_body_refs'][path])
        from .checks.admission import rubric_checks
        require(all(r['outcome']=='PASS' for r in rubric_checks(store.read_blob(binding['child_body_refs']['screening_rubric.json']))),'Child rubric violates source admission invariants')
        require(child['identity']['carrier']==parent['identity']['carrier'],'Installed carrier cannot be replaced by a trial')
        require(child['identity'].get('lineage',{}).get('parent')==binding['parent_declaration_ref'],'Child lineage does not name its parent')
        declared={p['name']:p for p in parent['ports']['inputs']};names=[p['name'] for p in binding['inputs']]
        require((names==['brief','candidate_set']) if v2 else (len(names)==len(set(names)) and set(names)==set(declared)),'Trial external input inventory differs from its explicit version')
        ports=copy.deepcopy(binding['inputs'])
        if v2:ports.append({'name':'screening_rubric','contract_id':declared['screening_rubric']['schema_ref'],
            'artifact_refs':[binding['child_body_refs']['screening_rubric.json']]})
        inputs=[]
        for port in ports:
            require(port['contract_id']==declared[port['name']]['schema_ref'] and (port['artifact_refs'] or not declared[port['name']]['required']),'Input type or required binding differs')
            for ref in port['artifact_refs']:
                raw=store.read_blob(ref)
                if port['contract_id']!='opaque-bytes':
                    try:value=json.loads(raw.decode('utf-8'))
                    except (ValueError,UnicodeError) as error:raise ResearchError('isolated_evaluation','Input is not its exact declared JSON contract') from error
                    validate(port['contract_id'],value)
            version=next(p['version'] for p in contract['inputs'] if p['name']==port['name'])
            inputs.append(dict(port,version=version,required=declared[port['name']]['required']))
        rubric=next(p for p in inputs if p['name']=='screening_rubric')['artifact_refs']
        require(rubric==[binding['child_body_refs']['screening_rubric.json']],'Actual named work rubric must match the child body')
        self.reservations.validate(binding)
        return parent,child,target,contract,enclosing,inputs

    def prepare_isolated_evaluation(self,binding_ref):
        binding=self.store.read_record(binding_ref);self._validate(binding)
        self.library._require_rsi_security('trial',binding['session_ref'],binding['child_declaration_ref'])
        identity='trial:'+hashlib.sha256(json_bytes(binding_ref)).hexdigest()
        revision='r3' if self.store.read_record(binding['reservation_ref'])['schema'].endswith(':3') else 'r2' if binding['schema']=='ai4r-isolated-evaluation-binding:2' else 'r1'
        return self.store.append_record('isolated-evaluation-trial',{'id':identity,'interface_revision':'M1-IF-011@'+revision,
            'binding_ref':binding_ref,'session_ref':binding['session_ref'],'target_ref':binding['target_ref'],
            'child_declaration_ref':binding['child_declaration_ref'],'accepted':False})

    async def execute_isolated_evaluation(self,trial_ref):
        trial=self.store.read_record(trial_ref)
        require(self.store.record_kind(trial_ref)=='isolated-evaluation-trial' and trial['interface_revision'] in {'M1-IF-011@r1','M1-IF-011@r2','M1-IF-011@r3'},'Unknown private trial')
        binding=self.store.read_record(trial['binding_ref']);validated=self._validate(binding)
        revision='r3' if self.store.read_record(binding['reservation_ref'])['schema'].endswith(':3') else 'r2' if binding['schema']=='ai4r-isolated-evaluation-binding:2' else 'r1'
        require(trial['interface_revision']=='M1-IF-011@'+revision,'Trial owning revision differs from its actual binding')
        existing=[r for r in self.store.iter_records(kinds=('isolated-evaluation-result',)) if r['record']['trial_ref']==trial_ref]
        if existing:
            require(len(existing)==1,'Ambiguous terminal trial result');return existing[0]['ref']
        self.library._require_rsi_security('trial',binding['session_ref'],binding['child_declaration_ref'])
        require(self.required_tests is not None,'Actual confined mandatory-test owner is unavailable')
        claim=self.reservations.claim(trial_ref,trial['binding_ref'],binding)
        parent,child,target,parent_contract,enclosing,inputs=validated
        context=None
        status='failed';failure=None;measurement=None;tests=[];tests_passed=False;failure_refs=[]
        try:
            context=TrialContext(self,trial_ref,binding,validated)
            self._active[trial_ref['id']]=context
            async with asyncio.timeout_at(context.deadline_monotonic_s):
                pending=self.required_tests.run(trial['binding_ref'],target['required_test_refs'])
                require(inspect.isawaitable(pending),'Mandatory test owner must provide bounded asynchronous execution')
                tests=await pending
                self._verify_tests(tests,binding,target)
                tests_passed=True
                context.test_refs=list(tests)
                from .measurement import measure_trial
                from .capsules.screening import ScreeningCarrier
                from .capsules.ranking import rank_opportunities
                handler=ScreeningCarrier(rank_opportunities,binding['child_body_refs']['ranking_parent.txt'],binding['child_body_refs']['screening_prompt.txt'])
                measurement=await measure_trial(context,handler,context.inputs,context.contract['outputs'],context.check_plan_ref,
                    context.bundle_id,context.review)
                status=measurement.status if measurement.status in {'completed','rejected','failed','interrupted'} else 'failed'
                failure=measurement.failure
        except asyncio.CancelledError:
            status='interrupted';failure='cancelled'
            if context is not None:await context.contain('cancelled')
        except Exception as error:
            failure=getattr(error,'code',type(error).__name__)
            failure_refs.append(self.store.append_record('isolated-evaluation-failure',{'id':'trial-failure:'+uuid.uuid4().hex,
                'trial_ref':trial_ref,'code':failure,'detail':error.message if isinstance(error,ResearchError) and error.code=='isolated_evaluation' else None}))
            if isinstance(error,TimeoutError) and context is not None:await context.contain('deadline')
        finally:
            if context is not None:context.closed=True
            self._active.pop(trial_ref['id'],None)
        outputs=[] if measurement is None else [{'name':name,'artifact_ref':ref,'contract_id':next(p['contract_id'] for p in context.contract['outputs'] if p['name']==name)} for name,ref in measurement.output_refs.items()]
        result={'schema':'ai4r-isolated-evaluation-result:1','id':'trial-result:'+uuid.uuid4().hex,'trial_ref':trial_ref,
            **{k:binding[k] for k in ('session_ref','target_ref','parent_declaration_ref','child_declaration_ref')},'status':status,
            'outputs':outputs,'mandatory_tests_passed':tests_passed,
            'deterministic_result_ref':getattr(measurement,'deterministic_ref',None),'assessment_refs':list(getattr(measurement,'assessment_refs',())),
            'observation_refs':([measurement.observation_ref] if measurement else [])+list(getattr(measurement,'observation_refs',())),
            'trace_refs':list(getattr(measurement,'trace_refs',()))+[claim,*tests],
            'failure':{'code':failure,'evidence_refs':[claim,*tests,*failure_refs,*([measurement.measurement_ref] if measurement else [])]} if failure else None,'accepted':False}
        private_validate('result',result)
        return self.store.append_record('isolated-evaluation-result',result)

    def _verify_tests(self,refs,binding,target):
        require(isinstance(refs,(list,tuple)) and len(refs)==len(target['required_test_refs']),'Every parent test needs actual evidence')
        seen=[]
        for ref in refs:
            value=self.store.read_record(ref)
            require(self.store.record_kind(ref)=='isolated-required-test','Required test evidence is not a protected owner capture')
            require(value['child_declaration_ref']==binding['child_declaration_ref'] and value['configuration_ref']==binding['configuration_ref']
                    and value['outcome']=='PASS','Parent test failed or names another child/configuration')
            measured=False
            if value.get('execution_receipt_ref') is not None:
                observed=self.store.read_record(value['execution_receipt_ref'])
                require(observed.get('observed_runtime') is True and observed.get('exit_code')==0 and observed.get('termination_reason')=='completed','No actual successful confined external test execution')
                measured=True
            if value.get('deterministic_result_ref') is not None:
                checked=self.store.read_record(value['deterministic_result_ref'],contract_id='deterministic-check-result')
                plan=self.store.read_record(checked['check_plan_ref'])
                subjects=[binding['child_declaration_ref'],*binding['child_body_refs'].values()]
                ids=[r['check_id'] for r in checked['results']]
                require(checked['subject_ref'] in subjects and value['test_ref'] in plan['runner_refs']
                    and ids and len(ids)==len(set(ids)) and set(plan['mandatory_deterministic'])<=set(ids)
                    and all(r['outcome']=='PASS' for r in checked['results'] if r['check_id'] in plan['mandatory_deterministic']),
                    'Declared deterministic parent test lacks complete exact child-bound measurements')
                measured=True
            require(measured,'A candidate test PASS boolean is not actual test evidence')
            for artifact in value['evidence_refs']:self.store.read_blob(artifact)
            seen.append(value['test_ref'])
        require(len({json.dumps(r,sort_keys=True) for r in seen})==len(seen) and sorted(seen,key=lambda r:r['sha256'])==sorted(target['required_test_refs'],key=lambda r:r['sha256']),'Required tests were substituted or duplicated')


class MeasurementCallAuthority:
    """Shared finite call claims for installed non-accepting measurement owners.

    An owner supplies exact validated metadata and implements require_checks().
    This class cannot resolve a client-selected factory or publish acceptance.
    """
    def _context(self,contract,ref,declaration,function,seconds):
        execution_id='trial-execution:'+uuid.uuid4().hex;began=time.monotonic()
        self._executions[execution_id]={'contract_ref':ref,'contract':contract,'declaration':declaration,
            'invocation_id':'invocation:'+uuid.uuid4().hex,'started':began,'deadline':min(self.deadline_monotonic_s,began+seconds),
            'calls':[],'closed':False,'call_function':function}
        return InvocationContext(self,contract,execution_id,self.inputs if function=='worker' else {})


    def _active(self,execution_id):
        execution=self._executions.get(execution_id)
        require(execution is not None and not execution['closed'] and not self.closed,'No active private trial invocation')
        require(not self.store.cancellation_requested(self.run_id),'Cancelled private trial cannot dispatch')
        require(time.monotonic()<min(execution['deadline'],self.deadline_monotonic_s),'Private trial deadline expired')
        self.require_checks()
        return execution


    def authorize_model_context(self,context):
        require(isinstance(context,dict) and set(context)=={'execution_id','call_ordinal'},'Unknown private model authorization fields')
        execution=self._active(context['execution_id']);contract=execution['contract'];binding=contract['bindings'][0]
        selection=self.store.read_record(self.binding['model_selection_profile_ref'],contract_id='model-selection-profile')
        settings=self.service.resources.operator.snapshot()['cc']
        value={**{k:contract[k] for k in ('run_id','node_id','subnode_id','attempt_id')},'invocation_id':execution['invocation_id'],
            **context,'call_function':execution['call_function'],'cc_name':execution['declaration']['identity']['name'],
            'cc_version':execution['declaration']['identity']['version_label'],'contract_ref':execution['contract_ref'],
            'input_refs':contract['input_refs'],'limits':dict(binding['limits'],time_s=min(execution['deadline'],self.deadline_monotonic_s)-time.monotonic()),
            'execution_deadline_monotonic_s':min(execution['deadline'],self.deadline_monotonic_s),'router':settings['router'],
            **{k:self.binding[k] for k in ('configuration_ref','model_selection_profile_ref','deployment_ref')},
            'model_selection_profile':selection,'approved_model_ids':selection['approved_model_ids']}
        reserve=self.reviews_remaining if execution['call_function']=='worker' else max(0,self.reviews_remaining-1)
        call_id,claim=self.store.claim_model_call(value,invocation_limit=binding['limits']['model_calls'],
            node_limit=self.binding['limits']['model_calls'],run_limit=self.binding['limits']['model_calls'],
            reserved_node_calls=reserve,reserved_run_calls=reserve)
        return dict(value,call_id=call_id,call_claim_ref=claim)


    def authorize_model_dispatch(self,payload):
        fields={'execution_id','invocation_id','call_id','call_claim_ref','contract_ref'}
        require(isinstance(payload,dict) and set(payload)==fields,'Unknown private dispatch fields')
        execution=self._active(payload['execution_id']);claim=self.store.read_record(payload['call_claim_ref'])
        require(all(claim.get(k)==payload[k] for k in fields-{'call_claim_ref'}) and claim['invocation_id']==execution['invocation_id']
            and claim['contract_ref']==execution['contract_ref'],'Private dispatch differs from its durable claim')
        with self.store._lock:
            row=self.store.connection.execute('SELECT claim_ref FROM model_calls WHERE run_id=? AND call_id=?',(self.run_id,payload['call_id'])).fetchone()
        require(row is not None and json.loads(row['claim_ref'])==payload['call_claim_ref'],'Unknown durable private call')
        deadline=min(execution['deadline'],self.deadline_monotonic_s)
        return {**claim,'call_claim_ref':payload['call_claim_ref'],'limits':dict(claim['limits'],time_s=deadline-time.monotonic()),'execution_deadline_monotonic_s':deadline}




class TrialContext(MeasurementCallAuthority):
    """Installed authorizer and capability-only carrier context for one trial."""
    def __init__(self,service,trial_ref,binding,validated):
        from .bridge import GovernedBridge
        self.service=service;self.store=service.store;self.binding=copy.deepcopy(binding)
        self.trial_ref=trial_ref;self.closed=False;self.test_refs=[];self._executions={};self.connectors=None;self.executor=None
        parent,child,target,pcontract,enclosing,inputs=validated
        self.declaration=child;self.check_registry=service.resources.composition.checks
        self.deadline_monotonic_s=time.monotonic()+binding['limits']['time_s']
        self.run_id='trial-run:'+trial_ref['sha256'][:32]
        self.store.create_run(self.run_id,account_id=service.resources.principal.account_id,
            workspace_id=service.resources.exact_binding_refs['workspace_id'],submission={'private_trial_ref':trial_ref})
        self._run_contexts={self.run_id:{'configuration_ref':binding['configuration_ref']}}
        self.contract=copy.deepcopy(pcontract)
        self.contract.pop('schema_version',None)
        self.contract.update(schema='ai4r-isolated-evaluation-contract:1',id=trial_ref['id']+':contract',run_id=self.run_id,
            attempt_id='trial-a1',subnode_id='screening',inputs=inputs,input_refs=[r for p in inputs for r in p['artifact_refs']],
            subnode_limits=copy.deepcopy(binding['limits']),template_ref=trial_ref)
        cb=self.contract['bindings'][0];cb.pop('admission_ref',None)
        cb.update(parent_admission_ref=binding['parent_admission_ref'],declaration_ref=binding['child_declaration_ref'],
            implementation_refs=[binding['child_body_refs'][p['path']] for p in child['identity']['body']],
            dependency_refs=copy.deepcopy(binding['dependency_refs']))
        cb['limits']={key:min(cb['limits'][key],binding['limits'][key]) for key in binding['limits']}
        cb['effective_authority']['resource_reads']=self.contract['input_refs']
        self.contract_ref=self.store.append_record('isolated-evaluation-contract',self.contract)
        bundle=self.store.read_record(binding['check_bundle_ref'],contract_id='check-bundle');self.bundle_id=bundle['bundle_id']
        self.profile=self.store.read_record(binding['checking_profile_ref'],contract_id='checking-profile')
        self.check_plan={'id':'trial-checks:'+uuid.uuid4().hex,'schema':'ai4r-isolated-evaluation-check-plan:1',
            'contract_ref':self.contract_ref,'node_contract_ref':pcontract['node_contract_ref'],'subnode_id':'screening',
            'input_refs':self.contract['input_refs'],'profile_ref':binding['checking_profile_ref'],'policy_ref':pcontract['policy_ref'],
            'mandatory_deterministic':list(dict.fromkeys([*[c['check_id'] for c in bundle['checks'] if c['blocking']],
                'host_contract','host_identity','host_limits','host_authority','parent_tests'])),
            'mandatory_semantic':[c['criterion_id'] for c in self.profile['criteria'] if c['blocking']],
            'runner_refs':list({r['sha256']:r for r in [binding['check_bundle_ref'],*[c['runner_ref'] for c in bundle['checks']]]}.values())}
        self.check_plan_ref=self.store.append_record('isolated-evaluation-check-plan',self.check_plan)
        self.inputs=CapsuleRunner._decode_inputs(self,self.contract)
        base=service.resources.bridge
        self.model=GovernedBridge(persist=self.store.append_record,authorize=self.authorize_model_context,
            subscription_service=base.subscription,router_port=base.router,providers=base.providers,
            fixed_route_id=base.fixed_route_id,validate_record=validate,health_check=base.health_check,
            revalidate=self.authorize_model_dispatch)
        self.reviews_remaining=len(self.contract['outputs'])
        verifier_pin=service.resources.composition.installed['verifier']['pin']
        verifier=service.library.get(verifier_pin['cc_name'],verifier_pin['cc_version'])
        verifier_declaration=self.store.read_record(verifier['declaration_ref'],contract_id='capsule-declaration')
        reserved_s=self.reviews_remaining*min(self.profile['time_s'],verifier_declaration['budget']['per_call']['wall_s'])
        require(binding['limits']['model_calls']>=cb['limits']['model_calls']+self.reviews_remaining,
            'Trial cannot borrow independent reviewer capacity for worker calls')
        require(self.deadline_monotonic_s-time.monotonic()>reserved_s,'Trial lacks independently reserved review time')
        self.worker_context=self._context(self.contract,self.contract_ref,child,'worker',
            min(cb['limits']['time_s'],self.deadline_monotonic_s-time.monotonic()-reserved_s))



    def require_checks(self):
        self.service._validate(self.binding)
        self.service.library.check_assets.require(self.binding['check_bundle_ref'],self.binding['checking_profile_ref'])



    def capture_observation(self,*,output_refs,started_at,elapsed_s,outcome,failure):
        execution=self._executions[self.worker_context.execution_id];execution['closed']=True
        value=CapsuleRunner._observation(self,execution,self.contract_ref,started_at,output_refs,outcome,failure)
        self.observation_ref=self.store.put_record('invocation-observation',value,scope=self.contract)
        return self.observation_ref

    def host_results(self,*,observation_ref,output_refs,outputs):
        self.require_checks();observation=self.store.read_record(observation_ref,contract_id='invocation-observation')
        okay=observation['contract_ref']==self.contract_ref and observation['output_refs']==list(output_refs.values())
        limited=observation['duration_s'] is not None and observation['duration_s']<=self.contract['bindings'][0]['limits']['time_s']
        limited=limited and observation['model_calls'] is not None and observation['model_calls']<=self.contract['bindings'][0]['limits']['model_calls']
        return [{'check_id':key,'outcome':'PASS' if valid else 'FAIL','reason':reason,'evidence_refs':[self.contract_ref,observation_ref,*self.test_refs]}
            for key,valid,reason in [('host_contract',okay,'Actual private trial output inventory matches its capture'),
                ('host_identity',okay,'Actual child identity and inherited admitted parent were independently validated'),
                ('host_limits',limited,'Actual worker measurement remains within its frozen reservation'),
                ('host_authority',True,'Exact inherited authority was independently revalidated'),
                ('parent_tests',bool(self.test_refs),'Every required parent test has attributable measured evidence')]]

    async def review(self,port,output_ref,deterministic_ref,observation_ref):
        installed=self.service.resources.composition.installed['verifier'];row=self.service.library.get(installed['pin']['cc_name'],installed['pin']['cc_version'])
        association=self.service.library.eligible_association(row['declaration_ref'])
        declaration=self.store.read_record(row['declaration_ref'],contract_id='capsule-declaration')
        contract=copy.deepcopy(self.contract);contract['id']='trial-review:'+uuid.uuid4().hex;contract['subnode_id']='review.'+port
        contract['inputs']=[{'name':'subject_declaration','contract_id':'capsule-declaration','version':'1.0.0','required':True,'artifact_refs':[self.binding['child_declaration_ref']]},
            {'name':'subject_output','contract_id':'opaque-bytes','version':'1.0.0','required':True,'artifact_refs':[output_ref]}]
        contract['input_refs']=[self.binding['child_declaration_ref'],output_ref]
        limits={'time_s':min(self.profile['time_s'],declaration['budget']['per_call']['wall_s']),
            'model_calls':1,'memory_mb':min(self.binding['limits']['memory_mb'],self.store.read_record(row['admission_ref'])['memory_mb'])}
        contract['bindings']=[{'id':'review.binding','role':'verifier','declaration_ref':row['declaration_ref'],
            'admission_ref':row['admission_ref'],'implementation_refs':[row['body_refs'][b['path']] for b in declaration['identity']['body']],
            'dependency_refs':[],'limits':limits,'effective_authority':{'network':'none','network_allowlist':[],
                'resource_reads':contract['input_refs'],'write_roots':[],'tools':[]}}]
        contract_ref=self.store.append_record('isolated-evaluation-verifier-contract',contract)
        context=self._context(contract,contract_ref,declaration,'verifier',limits['time_s']);execution=self._executions[context.execution_id]
        review={'schema_version':'2.0.0','id':'trial-review-context:'+uuid.uuid4().hex,'subject_ref':output_ref,
            'contract_ref':self.contract_ref,'check_plan_ref':self.check_plan_ref,'input_refs':self.contract['input_refs'],
            'deterministic_result_ref':deterministic_ref,'criteria':self.check_plan['mandatory_semantic'],
            'observations':[observation_ref],'evidence_classes':['captured_input_and_output','invocation_observation'],
            'node_contract_ref':self.contract['node_contract_ref'],'subnode_id':self.contract['subnode_id']}
        review_ref=self.store.put_record('review-context',review);started=utc_now();assessment_ref=None;failure=None
        try:
            assessment_ref=await SemanticVerifier(self.store).review(self.binding['child_declaration_ref'],output_ref,
                self.binding['checking_profile_ref'],review_ref,port,context.model)
        except BaseException as error:
            failure=getattr(error,'code',type(error).__name__);raise
        finally:
            execution['closed']=True
            observed=CapsuleRunner._observation(self,execution,contract_ref,started,{'assessment':assessment_ref} if assessment_ref else {},'failed' if failure else 'success',failure)
            vobs=self.store.put_record('invocation-observation',observed,scope=contract)
            self.reviews_remaining-=1
        assessment=self.store.read_record(assessment_ref,contract_id='verifier-assessment')
        criteria=[c for c in self.profile['criteria'] if c['target_port'] in (None,port)]
        body={k:assessment[k] for k in ('uncertainties','limitations','required_correction')}
        body['findings']=[{k:v[k] for k in ('criterion_id','outcome','reason')} for v in assessment['findings']]
        reconstructed=assemble_assessment(body,criteria,self.binding['child_declaration_ref'],output_ref,review_ref)
        require(reconstructed==assessment,'Independent private assessment does not recompute')
        check_ids=['declaration_pin_matches','output_hash_matches','assessment_schema','verifier_assessment_schema','criterion_coverage_exact','verdict_follows_findings','host_identity','host_limits']
        plan={**self.check_plan,'id':'trial-review-checks:'+uuid.uuid4().hex,'contract_ref':contract_ref,'subnode_id':contract['subnode_id'],
            'mandatory_deterministic':check_ids,'mandatory_semantic':[],'runner_refs':[association['bundle_ref']]}
        plan_ref=self.store.append_record('isolated-evaluation-check-plan',plan)
        valid=observed['model_calls']==1 and observed['duration_s']<=limits['time_s']
        checked={'schema_version':'1.0.0','subject_ref':assessment_ref,'check_plan_ref':plan_ref,'results':[
            {'check_id':key,'outcome':'PASS' if valid else 'FAIL','reason':'Captured independent verifier identities/schema/criteria and actual limits checked','evidence_refs':[contract_ref,vobs,assessment_ref]}
            for key in check_ids]}
        checked_ref=self.store.put_record('deterministic-check-result',checked,scope=contract)
        return {'assessment_ref':assessment_ref,'verifier_check_ref':checked_ref,'observation_refs':[vobs],'trace_refs':observed['trace_refs']}

    async def contain(self,reason):
        request='trial-cancel:'+uuid.uuid4().hex
        self.store.request_cancellation(self.run_id,self.service.resources.principal.account_id,request)
        grant={'authorized':True,'run_id':self.run_id,'request_id':request,'invocation_ids':[v['invocation_id'] for v in self._executions.values()]}
        ack=await self.model.contain_run(grant)
        require(ack.get('contained') is True,'Private model containment remains uncertain')
        owner=self.service.required_tests
        if hasattr(owner,'contain'):
            value=owner.contain(self.trial_ref)
            if inspect.isawaitable(value):value=await value
            require(isinstance(value,dict) and value.get('contained') is True,'Parent-test containment remains uncertain')
        else:raise ResearchError('CONTAINMENT_UNCERTAIN','Parent-test owner has no actual containment acknowledgment')
