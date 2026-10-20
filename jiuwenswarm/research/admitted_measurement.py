"""Measure an actual admitted carrier without publishing gate acceptance.

Normal canonical contracts, capability contexts, budgets, model-call claims and
independent verifier bindings are reused. The adapter never creates a child
identity or calls CapsuleRunner.run/ProtectedGate/commit_acceptance.
"""
from __future__ import annotations
import asyncio,copy,hashlib,json,time,uuid
from dataclasses import dataclass
from .contracts import ResearchError
from .binding import ContractFactory
from .measurement import TrialMeasurement,measure_trial,ordered_replay_outputs
from .state import json_bytes,utc_now


def require(condition,message):
    if not condition:raise ResearchError('admitted_measurement',message)


@dataclass(frozen=True)
class AdmittedResourceContext:
    """Existing protected runtime handles, with no second composition/bridge.

    This context makes no isolation or qualification claim. The admitted owner
    validates every canonical subject against these actual protected handles.
    """
    store: object
    operator: object
    composition: object
    principal: object
    exact_binding_refs: dict
    executor: object

    @property
    def runner(self):return self.composition.runner

    @property
    def registry(self):return self.composition.registry


class AdmittedMeasurementResources:
    def __init__(self,resources):
        self.resources=resources;self.store=resources.store;self.runner=resources.runner
        self.library=resources.composition.library
    def _host_records(self,records):
        """Finite canonical host-evidence views; unsupported formats block.

        The four source record classes project captured invocation-observation3
        bytes into actual deterministic host checks. They are never model input.
        """
        require(isinstance(records,list) and len(records)<=4,'Invalid replay host-record inventory')
        seen=set()
        for item in records:
            require(isinstance(item,dict) and set(item)=={'record_type','ref'}
                and item['record_type'] in {'runtime_observation','identity_record','budget_record','tool_observation'}
                and item['record_type'] not in seen,'Unsupported or duplicate replay host-record class')
            seen.add(item['record_type'])
            require(self.store.record_kind(item['ref'])=='invocation-observation','Unsupported host-record format: canonical observation capture required')
            self.store.read_record(item['ref'],contract_id='invocation-observation')
        return copy.deepcopy(records)
    def _validate(self,contract_ref,check_plan_ref,*,replay=False):
        store=self.store;contract=store.read_record(contract_ref,contract_id='subnode-execution-contract')
        require(store.record_kind(contract_ref)=='subnode-execution-contract','Canonical protected subject capture is required')
        require(len(contract['bindings'])==1 and contract['bindings'][0]['role']=='work','One actual admitted work binding is required')
        plan=store.read_record(check_plan_ref,contract_id='bound-check-plan')
        require(store.record_kind(check_plan_ref)=='bound-check-plan' and plan['contract_ref']==contract_ref
            and plan['node_contract_ref']==contract['node_contract_ref'] and plan['subnode_id']==contract['subnode_id'],'Checking plan differs from subject')
        parent=store.read_record(contract['node_contract_ref'],contract_id='node-execution-contract')
        self.runner._require_child_authority(contract_ref,contract)
        selected=contract['bindings'][0];declaration=store.read_record(selected['declaration_ref'],contract_id='capsule-declaration')
        row=self.library.get(declaration['identity']['name'],declaration['identity']['version_label'])
        admission=store.read_record(selected['admission_ref'],contract_id='library-admission')
        require(row['declaration_ref']==selected['declaration_ref'] and row['admission_ref']==selected['admission_ref']
            and admission['status']=='admitted' and admission['candidate_ref']==selected['declaration_ref'],'Subject is not the exact admitted immutable version')
        require(selected['implementation_refs']==[row['body_refs'][p['path']] for p in declaration['identity']['body']], 'Admitted implementation closure differs')
        for pin in [*selected['implementation_refs'],*selected['dependency_refs']]:store.read_blob(pin)
        expected=self.resources.exact_binding_refs
        require(contract['configuration_ref']==expected['configuration_ref']==parent['configuration_ref'],'Measurement configuration differs from protected resources')
        require(all(contract[k]==parent[k] for k in ('run_id','node_id','attempt_id','revision')),'Subject belongs to another frozen node attempt')
        run=store.get_run(contract['run_id'],account_id=self.resources.principal.account_id)
        require(run['workspace_id']==expected['workspace_id'],'Measurement workspace differs from protected resources')
        per=declaration['budget']['per_call'];calls=per['invocations'] if any(i['service_key']=='audited_model_bridge' for i in declaration['needs']['injects']) else 0
        ceilings={'time_s':per['wall_s'],'model_calls':calls,'memory_mb':admission['memory_mb']}
        require(all(selected['limits'][k]<=min(parent['node_limits'][k],ceilings[k]) and contract['subnode_limits'][k]<=min(parent['node_limits'][k],ceilings[k]) for k in selected['limits']),'Subject widened its frozen declaration/node limit')
        from .contracts import contract_schema
        for direction in ('inputs','outputs'):
            expected_ports={p['name']:p for p in declaration['ports'][direction]};actual=contract[direction]
            require(len(actual)==len({p['name'] for p in actual}) and {p['name'] for p in actual}==set(expected_ports),'Subject port inventory differs from admitted declaration')
            require(all(p['required']==expected_ports[p['name']]['required'] and (p['contract_id']==expected_ports[p['name']]['schema_ref'] or contract_schema(p['contract_id'])==contract_schema(expected_ports[p['name']]['schema_ref'])) for p in actual),'Subject port type/requiredness changed')
        dependencies=[row['body_refs'][pin['ref']] for dependency in declaration['needs']['external'] for key in ('pin','lockfile') if (pin:=dependency.get(key))]
        require(selected['dependency_refs']==dependencies,'Inherited dependency closure changed')
        authority=selected['effective_authority'];ceiling=parent['authority_ceiling'];network=declaration['needs']['network']
        require(all(v in ceiling[k] for k in ('network_allowlist','resource_reads','write_roots','tools') for v in authority[k])
            and (authority['network']=='none' or ceiling['network']=='allowlist' and network['mode']=='allowlist' and all(v in network['allowlist'] for v in authority['network_allowlist'])), 'Effective authority exceeds the exact parent/declaration')
        self.runner._require_check_assets(contract)
        template=store.read_record(contract['template_ref']);bundle=store.read_record(template['check_bundle_ref'],contract_id='check-bundle')
        require(plan['profile_ref']==contract['checking_profile_ref'] and template['check_bundle_ref'] in plan['runner_refs'],'Measurement checking assets differ')
        required={c['check_id'] for c in bundle['checks'] if c['blocking']}|{'host_contract','host_identity','host_limits','host_authority'}
        require(required<=set(plan['mandatory_deterministic']) and len(plan['mandatory_deterministic'])==len(set(plan['mandatory_deterministic'])),'Mandatory source checks were omitted or duplicated')
        profile=store.read_record(plan['profile_ref'],contract_id='checking-profile')
        require(set(plan['mandatory_semantic'])=={c['criterion_id'] for c in profile['criteria'] if c['blocking']} and len(plan['mandatory_semantic'])==len(set(plan['mandatory_semantic'])),'Mandatory semantic criteria changed')
        settings=self.resources.operator.snapshot()['cc']
        policy=store.read_record(settings['plan_policy_ref'],contract_id='plan-policy')
        require(contract['policy_ref']==parent['policy_ref']==plan['policy_ref']==settings['plan_policy_ref'],'Subject policy differs from the immutable approved operator policy')
        require(all(parent['node_limits'][key]<=policy['aggregate_limits'][key] for key in policy['aggregate_limits']),'Captured node exceeds the immutable global policy ceiling')
        selection=store.read_record(expected['model_selection_profile_ref'],contract_id='model-selection-profile')
        require(selection['policy_mode']=='fixed_baseline' and settings['router']['enabled'] is False,'Protected advanced routing resources are unavailable')
        inputs=self.runner._decode_inputs(contract)
        handler=None
        if not replay:
            handler,pinned=self.resources.registry.resolve(declaration['identity']['name'],declaration['identity']['version_label'],selected['declaration_ref']['sha256'])
            require(not pinned or tuple(selected['implementation_refs'])==pinned,'Installed carrier closure differs from canonical binding')
        return contract,plan,parent,inputs,bundle,handler
    def _prepare(self,contract_ref,check_plan_ref,*,replay_outputs=None,observation_ref=None,semantic_review=True,host_records=None,review_ports=None):
        require(type(semantic_review) is bool,'Protected review mode must be explicit')
        replay=replay_outputs is not None;require(not replay or semantic_review,'Frozen replay retains independent semantic review')
        host_records=self._host_records(host_records if host_records is not None else [])
        require(replay or not host_records,'Host-only replay records cannot enter a producing invocation')
        contract,plan,parent,_,_,_=self._validate(contract_ref,check_plan_ref,replay=replay)
        if replay:
            specs={p['name']:p for p in contract['outputs']}
            require(isinstance(replay_outputs,dict) and set(replay_outputs)<=set(specs)
                and all(not p['required'] or name in replay_outputs for name,p in specs.items()),'Frozen replay outputs differ from declared ports')
            for pin in replay_outputs.values():self.store.read_blob(pin)
            if observation_ref is None:
                rows=[r for r in self.store.iter_records(kinds=('invocation-observation',)) if r['record']['contract_ref']==contract_ref
                    and r['record']['output_refs']==list(replay_outputs.values())]
                require(len(rows)==1,'Replay needs one exact original protected observation');observation_ref=rows[0]['ref']
            observed=self.store.read_record(observation_ref,contract_id='invocation-observation')
            require(observed['contract_ref']==contract_ref,'Replay changed original observation identity')
            ordered_replay_outputs(replay_outputs,observed['output_refs'])
        require(review_ports is None or replay and isinstance(review_ports,list) and bool(review_ports)
            and len(review_ports)==len(set(review_ports)) and set(review_ports)<=set(replay_outputs),'Invalid protected replay review selection')
        value={'schema':'ai4r-admitted-measurement:2','contract_ref':contract_ref,'check_plan_ref':check_plan_ref,
            'configuration_ref':contract['configuration_ref'],'mode':'replay' if replay else 'execute',
            'replay_output_refs':replay_outputs,'original_observation_ref':observation_ref,'semantic_review':semantic_review,
            'replay_host_records':host_records,'review_ports':copy.deepcopy(review_ports),'accepted':False}
        value['id']='admitted-measurement:'+hashlib.sha256(json_bytes(value)).hexdigest()
        return self.store.append_record('admitted-measurement-grant',value)
    def prepare(self,contract_ref,check_plan_ref,*,semantic_review=True):return self._prepare(contract_ref,check_plan_ref,semantic_review=semantic_review)
    def metadata(self,grant_ref):
        """Protected adapter metadata only; constructs no worker context/effect."""
        from types import SimpleNamespace
        grant=self.store.read_record(grant_ref)
        require(self.store.record_kind(grant_ref)=='admitted-measurement-grant','Unknown protected measurement grant')
        contract=self._validate(grant['contract_ref'],grant['check_plan_ref'],replay=grant['mode']=='replay')[0]
        return SimpleNamespace(store=self.store,contract_ref=grant['contract_ref'],contract=copy.deepcopy(contract),
            check_plan_ref=grant['check_plan_ref'],replay_output_refs=copy.deepcopy(grant['replay_output_refs']),semantic_review=grant['semantic_review'],measurement_grant_ref=copy.deepcopy(grant_ref))
    def prepare_replay(self,contract_ref,check_plan_ref,output_refs,*,observation_ref=None,host_records=None,review_ports=None):
        return self._prepare(contract_ref,check_plan_ref,replay_outputs=copy.deepcopy(output_refs),observation_ref=observation_ref,host_records=host_records,review_ports=review_ports)
    async def execute(self,grant_ref):
        grant=self.store.read_record(grant_ref)
        require(self.store.record_kind(grant_ref)=='admitted-measurement-grant' and grant['schema'] in {'ai4r-admitted-measurement:1','ai4r-admitted-measurement:2'},'Unknown measurement grant')
        self._host_records(grant.get('replay_host_records',[]))
        replay=grant['mode']=='replay';validated=self._validate(grant['contract_ref'],grant['check_plan_ref'],replay=replay)
        existing=[r for r in self.store.iter_records(kinds=('admitted-measurement-result',)) if r['record']['grant_ref']==grant_ref]
        if existing:
            require(len(existing)==1,'Ambiguous completed measurement')
            return TrialMeasurement(**self.store.read_record(existing[0]['record']['measurement_ref']))
        key='admitted-measurement-start:'+hashlib.sha256(json_bytes(grant_ref)).hexdigest()
        with self.store.transaction() as db:
            require(db.execute('SELECT 1 FROM metadata WHERE key=?',(key,)).fetchone() is None,'Started measurement has no terminal proof; reconcile without replay')
            db.execute('INSERT INTO metadata VALUES(?,?)',(key,json_bytes(grant_ref).decode()))
        contract=validated[0]
        context=None
        try:
            context=AdmittedContext(self,grant_ref,grant,validated)
            if not replay:await self.runner._await_start(context.worker_context)
            measured=await measure_trial(context,validated[-1],context.inputs,context.contract['outputs'],context.check_plan_ref,context.bundle_id,context.review if grant['semantic_review'] else None)
            # Dataclass-only decoding data is independent of the source raw record.
            from dataclasses import asdict
            data=asdict(measured);value=self.store.put_blob(json_bytes(data),media_type='application/json')
            self.store.append_record('admitted-measurement-result',{'id':key+':result','grant_ref':grant_ref,'measurement_ref':value,'raw_measurement_ref':measured.measurement_ref,'accepted':False})
            return measured
        finally:
            if context is not None:context.closed=True
            if (not replay and context is not None and context.worker_context is not None
                    and self.runner._executions[context.worker_context.execution_id].get('phase')=='active'):
                self.store.finish_attempt(contract,'observed')
    async def execute_replay(self,grant_ref):
        require(self.store.read_record(grant_ref)['mode']=='replay','Expected a frozen replay grant')
        return await self.execute(grant_ref)


class AdmittedContext:
    def __init__(self,owner,grant_ref,grant,validated):
        self.owner=owner;self.store=owner.store;self.runner=owner.runner;self.grant=grant;self.grant_ref=grant_ref;self.closed=False
        self.contract,self.check_plan,parent,self.inputs,bundle,_=validated
        self.contract_ref=grant['contract_ref'];self.check_plan_ref=grant['check_plan_ref'];self.bundle_id=bundle['bundle_id'];self.check_registry=self.runner.check_registry
        self.run_id=self.contract['run_id'];self.replay_output_refs=grant['replay_output_refs'];self.original_observation_ref=grant['original_observation_ref']
        self.replay_output_order=self.store.read_record(self.original_observation_ref)['output_refs'] if self.original_observation_ref else None
        self.review_ports=copy.deepcopy(grant.get('review_ports'))
        expected=owner.resources.exact_binding_refs;settings=owner.resources.operator.snapshot()['cc']
        policy=self.store.read_record(settings['plan_policy_ref'],contract_id='plan-policy')
        run_ceiling=copy.deepcopy(policy['aggregate_limits'])
        reservation=expected.get('protected_options',{}).get('run_limits')
        if reservation is not None:
            from .contracts import validate
            validate('Limits',reservation)
            require(all(reservation[key]<=run_ceiling[key] for key in run_ceiling),'Protected reservation cannot enlarge the global ceiling')
            run_ceiling={key:min(run_ceiling[key],reservation[key]) for key in run_ceiling}
        require(all(parent['node_limits'][key]<=run_ceiling[key] for key in run_ceiling),'Captured node does not fit its protected run reservation')
        if self.run_id not in self.runner._run_contexts:
            self.runner.configure_run(self.run_id,model_selection_profile_ref=expected['model_selection_profile_ref'],deployment_ref=expected['deployment_ref'],
                router=settings['router'],configuration_ref=expected['configuration_ref'],run_limits=run_ceiling)
        frozen=self.runner._run_contexts[self.run_id]
        require(all(frozen[k]==expected[k] for k in ('configuration_ref','model_selection_profile_ref','deployment_ref')),'Existing run context differs from protected measurement resources')
        require(all(frozen['run_limits'][key]<=run_ceiling[key] and parent['node_limits'][key]<=frozen['run_limits'][key] for key in run_ceiling),'Existing run context widens policy or cannot contain this node')
        self.runner._budget_state(self.contract)
        self.deadline_monotonic_s=min(self.runner._run_started[self.run_id]+frozen['run_limits']['time_s'],
            self.runner._node_started[(self.run_id,self.contract['node_id'])]+parent['node_limits']['time_s'])
        self.worker_context=None
        self.review_observation_refs=[]
        if grant['mode']=='execute':
            self.worker_context=self.runner._start_context(self.contract_ref,self.contract,self.inputs)
            self.deadline_monotonic_s=min(self.deadline_monotonic_s,self.runner._executions[self.worker_context.execution_id]['started']+parent['node_limits']['time_s'])
    def require_checks(self):
        require(not self.closed,'Measurement is closed')
        self.owner._validate(self.contract_ref,self.check_plan_ref,replay=self.grant['mode']=='replay')
        require(not self.store.cancellation_requested(self.run_id),'Measurement was cancelled')
    def capture_observation(self,*,output_refs,started_at,elapsed_s,outcome,failure):
        if self.grant['mode']=='replay':return self.original_observation_ref
        execution=self.runner._executions[self.worker_context.execution_id];execution['closed']=True
        observed=self.runner._observation(execution,self.contract_ref,started_at,output_refs,outcome,failure)
        pin=self.store.put_record('invocation-observation',observed,scope=self.contract)
        execution['observation_ref']=pin;execution['failure']=failure
        return pin
    def host_results(self,*,observation_ref,output_refs,outputs):
        observed=self.store.read_record(observation_ref,contract_id='invocation-observation')
        rows=self.runner._host_checks(self.contract_ref,self.contract,observed,observation_ref)
        if observed['contract_ref']!=self.contract_ref or observed['output_refs']!=list(output_refs.values()):
            next(r for r in rows if r['check_id']=='host_contract')['outcome']='FAIL'
        projections={'runtime_observation':{r['check_id'] for r in rows},'identity_record':{'host_identity'},
            'budget_record':{'host_limits'},'tool_observation':{'host_authority'}}
        for item in self.owner._host_records(self.grant.get('replay_host_records',[])):
            supplied=self.store.read_record(item['ref'],contract_id='invocation-observation')
            measured=self.runner._host_checks(self.contract_ref,self.contract,supplied,item['ref'])
            joined=(supplied['contract_ref']==self.contract_ref and supplied['id']==observed['id']
                and supplied['output_refs']==list(output_refs.values()))
            for result in measured:
                if result['check_id'] not in projections[item['record_type']]:continue
                base=next(row for row in rows if row['check_id']==result['check_id'])
                if not joined or result['outcome']!='PASS':base['outcome']='FAIL'
                # Effects are literal observed operation names in this finite
                # adapter; an unknown effect cannot prove scoped tool use.
                if result['check_id']=='host_authority' and any(effect not in self.contract['bindings'][0]['effective_authority']['tools'] for effect in supplied['effects']):
                    base['outcome']='FAIL'
                base['evidence_refs'].append(item['ref'])
                base['reason']+='; evaluated captured '+item['record_type']+' projection'
        return rows
    async def review(self,port,output_ref,deterministic_ref,observation_ref):
        parent=self.store.read_record(self.contract['node_contract_ref']);matches=[]
        for assignment in parent['subnodes']:
            if assignment['role']!='verifier':continue
            template=self.store.read_record(assignment['template_ref'])
            if template.get('subject_subnode_id')==self.contract['subnode_id'] and template.get('output_port')==port:matches.append(assignment)
        require(len(matches)==1,'Exact independent verifier assignment is unavailable')
        factory=ContractFactory(self.store,self.owner.library,verifier_pin=self.owner.resources.composition.installed['verifier']['pin'],finalization_profile_ref=parent['checking_profile_ref'])
        from .compiler import input_port
        verifier_ref,_,_=factory.bind_subnode(self.contract['node_contract_ref'],matches[0]['subnode_id'],[
            input_port('subject_declaration','capsule-declaration',self.contract['bindings'][0]['declaration_ref']),input_port('subject_output','opaque-bytes',output_ref)],role='verifier')
        contract=self.store.read_record(verifier_ref,contract_id='subnode-execution-contract')
        context=self.runner._start_context(verifier_ref,contract,{},call_function='verifier')
        await self.runner._await_start(context)
        started=utc_now();assessment=None;failure=None
        try:
            review=self.store.put_record('review-context',{'schema_version':'2.0.0','id':'measurement-review:'+uuid.uuid4().hex,'subject_ref':output_ref,
                'contract_ref':self.contract_ref,'check_plan_ref':self.check_plan_ref,'input_refs':self.contract['input_refs'],'deterministic_result_ref':deterministic_ref,
                'criteria':self.check_plan['mandatory_semantic'],'observations':[observation_ref],'evidence_classes':['captured_input_and_output','invocation_observation'],
                'node_contract_ref':self.contract['node_contract_ref'],'subnode_id':self.contract['subnode_id']})
            assessment=await self.runner.verifier.review(self.contract['bindings'][0]['declaration_ref'],output_ref,self.check_plan['profile_ref'],review,port,context.model,
                zip_output=next(p for p in self.contract['outputs'] if p['name']==port)['contract_id']=='poc-artifact-bundle')
        except BaseException as error:failure=getattr(error,'code',type(error).__name__);raise
        finally:
            execution=self.runner._executions[context.execution_id];execution['closed']=True
            observed=self.runner._observation(execution,verifier_ref,started,{'verifier_assessment':assessment} if assessment else {},'failed' if failure else 'success',failure)
            observed_ref=self.store.put_record('invocation-observation',observed,scope=contract);execution['observation_ref']=observed_ref
            self.review_observation_refs.append(observed_ref)
            self.store.finish_attempt(contract,'observed')
        checked=self.runner._check_verifier(verifier_ref,contract,observed,observed_ref,assessment,self.contract,self.check_plan,port,output_ref)
        return {'assessment_ref':assessment,'verifier_check_ref':checked,'observation_refs':[observed_ref],'trace_refs':observed['trace_refs']}
    async def contain(self,reason):
        request='measurement-cancel:'+uuid.uuid4().hex
        self.store.request_cancellation(self.run_id,self.owner.resources.principal.account_id,request)
        acknowledgments=[]
        for name,owner in [('model',self.runner.model),('executor',self.runner.executor)]:
            active=any(v['contract']['run_id']==self.run_id for v in self.runner._executions.values())
            if owner is None:
                require(not active or name=='executor' and all(not v['contract']['bindings'][0]['effective_authority']['tools'] for v in self.runner._executions.values() if v['contract']['run_id']==self.run_id),'Effect containment owner is unavailable')
                continue
            method=getattr(owner,'contain_run',None);require(method is not None,'Actual containment method is unavailable')
            from .bridge import GovernedBridge
            result=(method({'authorized':True,'run_id':self.run_id,'request_id':request,'invocation_ids':[v['invocation_id'] for v in self.runner._executions.values() if v['contract']['run_id']==self.run_id]})
                if isinstance(owner,GovernedBridge) else method(self.run_id,request))
            if hasattr(result,'__await__'):result=await asyncio.wait_for(result,35)
            require(isinstance(result,dict) and result.get('contained') is True,'Effect containment remains uncertain');acknowledgments.append(result)
        return {'contained':True,'owner_receipts':acknowledgments}
