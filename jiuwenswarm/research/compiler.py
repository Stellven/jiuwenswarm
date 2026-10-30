"""Fixed two-work compiler node through committed Research Brief release."""

from __future__ import annotations

from .binding import ContractFactory
from .contracts import ResearchError
from .state import utc_now
from .target_comparisons import BRIEF_CONTRACT, BRIEF_VERSION
import time


def input_port(name,contract,ref):
    if contract == 'research-brief':contract = BRIEF_CONTRACT
    return {'name':name,'contract_id':contract,'version':ContractFactory._version(contract),'required':True,'artifact_refs':[ref]}


class IntentionCompiler:
    def __init__(self,store,runner,factory,*,intent_pin,requirements_pin,default_policy_ref,
                 template_ref,node_limits,policy_ref,authority_ceiling):
        self.store,self.runner,self.factory=store,runner,factory
        self.intent_pin,self.requirements_pin=intent_pin,requirements_pin
        self.default_policy_ref,self.template_ref=default_policy_ref,template_ref
        self.node_limits,self.policy_ref,self.authority_ceiling=node_limits,policy_ref,authority_ceiling
        policy=store.read_record(default_policy_ref,contract_id='default-policy')
        if policy['automatic_retries']!=0 or policy['hardware_profile']!='single_gpu':
            raise ResearchError('default_policy_invalid','M1 fixed compiler requires no retries and the protected conservative hardware default')

    async def _work(self,parent_ref,subnode_id,ports,*,dispatch=None):
        contract_ref,plan_ref,bundle=self.factory.bind_subnode(parent_ref,subnode_id,ports,role='work')
        parent=self.store.read_record(parent_ref)
        assignments=[s for s in parent['subnodes'] if s['role']=='verifier' and s['depends_on']==[subnode_id]]
        # Concrete verifier contracts carry declaration/output only. The exact
        # output does not exist before the work call, so runner binds it below.
        verifier_templates={self.store.read_record(s['template_ref'])['output_port']:s['subnode_id'] for s in assignments}
        return await self.runner.run(contract_ref,plan_ref,bundle_id=bundle,verifier_contract_refs=
            VerifierBindings(self.factory,parent_ref,contract_ref,verifier_templates),dispatch=dispatch)

    async def run(self,run_id,protected):
        run=self.store.get_run(run_id);intake_ref=run['submission']['intake_ref']
        intake=self.store.read_record(intake_ref,contract_id='qualified-intake')
        self.runner.configure_run(run_id,**{key:protected[key] for key in ('model_selection_profile_ref','deployment_ref','router','configuration_ref','run_limits')},routing_context=protected.get('routing_context'))
        inputs=[input_port('request','qualified-intake:field-contract:2',intake_ref),input_port('defaults','default-policy:field-contract:1',self.default_policy_ref)]
        outputs=[{'name':'brief','contract_id':BRIEF_CONTRACT,'version':BRIEF_VERSION,'required':True}]
        work=[{'subnode_id':'intent','cc':self.intent_pin,'depends_on':[]},
              {'subnode_id':'requirements','cc':self.requirements_pin,'depends_on':['intent','intent.verifier']}]
        authority=dict(self.authority_ceiling,resource_reads=[intake_ref,self.default_policy_ref,intake['request_ref'],*intake['source_refs'],*intake['resource_refs']])
        parent_ref=self.factory.prepare_parent(run_id,'intention_compiler',work,inputs=inputs,outputs=outputs,
            objective='Compile qualified user meaning into an accepted Research Brief',requirement_ids=['qualified_intent','research_brief'],
            limits=self.node_limits,policy_ref=self.policy_ref,configuration_ref=protected['configuration_ref'],template_ref=self.template_ref,authority_ceiling=authority)
        self.store.set_node_state(run_id,'intention_compiler','pending',attempt_id='intention_compiler-a1')
        self.runner.prepare_node_check_plan(parent_ref)
        dispatch_scope={'run_id':run_id,'node_id':'intention_compiler','node_contract_ref':parent_ref,'run_plan_ref':None,
            'predecessors':[],'predecessor_commits':[],
            'bound_input_refs':[{'name':p['name'],'ref':ref} for p in inputs for ref in p['artifact_refs']]}
        processing_began=utc_now();processing_clock=time.monotonic()
        try:
            intent=await self._work(parent_ref,'intent',[input_port('request','qualified-intake:field-contract:2',intake_ref)],dispatch=dispatch_scope)
        except BaseException as error:
            timing=self.runner.dispatch_timing(parent_ref)
            self.runner.capture_start_failure(parent_ref,started_at=timing['started_at'] if timing else processing_began,
                elapsed_s=time.monotonic()-(timing['started_monotonic_s'] if timing else processing_clock),
                error=error,phase='pre_plan')
            self.store.set_node_state(run_id,'intention_compiler','failed',attempt_id='intention_compiler-a1',reason=getattr(error,'code',type(error).__name__))
            raise
        timing=self.runner.dispatch_timing(parent_ref)
        if timing is None:raise ResearchError('integrity_fault','Compiler work has no actual start boundary')
        began=timing['started_at'];clock=timing['started_monotonic_s']
        if not intent.accepted:
            decision=await self.runner.finalize_node(parent_ref,[intent],{})
            self.runner.capture_dispatch(parent_ref,decision,[intent],started_at=began,elapsed_s=time.monotonic()-clock,phase='pre_plan')
            return {'accepted':False,'node_decision_ref':decision,'candidate_refs':list(intent.output_refs.values())}
        intent_ref=intent.output_refs['intent']
        # Read only from the actually committed internal acceptance rows.
        if self.store.accepted_outputs(run_id,'intention_compiler',subnode_id='intent').get('intent')!=intent_ref:
            raise ResearchError('unaccepted_input','Requirements cannot consume a candidate Intent')
        try:
            requirements=await self._work(parent_ref,'requirements',[input_port('intent','intent-ir',intent_ref),
                input_port('intake','qualified-intake:field-contract:2',intake_ref),input_port('defaults','default-policy:field-contract:1',self.default_policy_ref)])
        except BaseException as error:
            self.runner.capture_start_failure(parent_ref,started_at=began,elapsed_s=time.monotonic()-clock,error=error,phase='pre_plan')
            self.store.set_node_state(run_id,'intention_compiler','failed',attempt_id='intention_compiler-a1',reason=getattr(error,'code',type(error).__name__))
            raise
        refs={'brief':requirements.output_refs['brief']} if requirements.accepted else {}
        decision=await self.runner.finalize_node(parent_ref,[intent,requirements],refs)
        self.runner.capture_dispatch(parent_ref,decision,[intent,requirements],started_at=began,elapsed_s=time.monotonic()-clock,phase='pre_plan')
        accepted=self.store.read_record(decision)['action']=='advance'
        return {'accepted':accepted,'brief_ref':refs.get('brief'),'node_contract_ref':parent_ref,'node_decision_ref':decision,
                'intent_ref':intent_ref,'results':[intent,requirements]}


class VerifierBindings:
    """Host-only lazy binding after captured output, never a worker callback."""
    def __init__(self,factory,parent_ref,work_ref,assignments):
        self.factory,self.parent_ref,self.work_ref,self.assignments=factory,parent_ref,work_ref,assignments

    def bind(self,port,output_ref,review_evidence_ref=None):
        work=self.factory.store.read_record(self.work_ref)
        declaration_ref=work['bindings'][0]['declaration_ref']
        inputs=[input_port('subject_declaration','capsule-declaration',declaration_ref),
                input_port('subject_output','opaque-bytes',output_ref)]
        if review_evidence_ref is not None:
            # The verifier declares review_evidence as an optional port.
            inputs.append(dict(input_port('review_evidence','opaque-bytes',review_evidence_ref),required=False))
        ref,_,_=self.factory.bind_subnode(self.parent_ref,self.assignments[port],inputs,role='verifier')
        return ref


async def prepare_compiler_assets(store,*,requirements_version='m1-8',intent_version='m1-6'):
    """Verify and capture installed data without eligibility or model effects."""
    return await register_compiler_capsules(None,None,None,store,None,prepare_only=True,requirements_version=requirements_version,intent_version=intent_version)


async def register_compiler_capsules(registry,check_registry,library,store,actor,*,activate=False,bootstrap=False,initialize=True,memory_mb=256,prepare_only=False,prepared_assets=None,requirements_version='m1-8',intent_version='m1-6'):
    """Trusted installation from the bounded byte-pinned packaged catalog.

    The caller supplies an authenticated operator identity. Asset ownership and
    standing operations stay separate; this is never reachable from submit.
    """
    import hashlib
    if not isinstance(intent_version,str) or intent_version not in {'m1-6','m1-7','m1-8'}:
        raise ResearchError('prepared_catalog_invalid','Unknown explicit Intent release')
    if not isinstance(requirements_version,str) or requirements_version not in {'m1-8','m1-9'}:
        raise ResearchError('prepared_catalog_invalid','Unknown explicit Requirements release')
    import json
    from importlib.resources import files
    from .capsules import intent,requirements,planner
    from .checks.compiler import compiler_checks
    from .planning import planner_checks
    from .state import json_bytes
    package=files('jiuwenswarm');assets=package.joinpath('research_assets')
    catalog=json.loads(assets.joinpath('catalog.json').read_text('utf-8'))
    base_instructions=assets.joinpath('compiler','verifier.txt').read_bytes()
    from .checks.schema_context import frozen_output_instructions
    generic=[('declared_output_conformance','Does this exact output conform to the declared type, fields and shape?'),
             ('internal_consistency','Do output fields and local ID references agree internally?'),
             ('limitations_consistency','Are stated uncertainties and limitations coherent with the output?')]
    extra={'intent':[('uncertainty_consistency','Does readiness agree with blocking uncertainties?')],
           'requirements':[('requirement_link_completeness','Does every mandatory requirement have acceptance and evidence links?')],
           'planner':[('graph_self_consistent','Is the declared predecessor/future graph internally acyclic and resolved?'),
                      ('output_ports_named','Does every future output name a compatible listed producer port?'),
                      ('coverage_tags_present','Does every node have a requirement or deliverable tag?'),
                      ('coverage_map_consistent','For requirement and deliverable entries, is coverage the exact inverse of the corresponding node tags? For evidence_obligation entries, do node_ids name existing nodes without requiring a matching node tag?'),
                      ('no_authority_claims','Do notes, objectives and suggested checks avoid commands or authority claims?')],
           'verifier':[]}
    checks={'intent':['intent_schema','source_spans','exact_identity'],
            'requirements':['brief_schema','source_identity','requirement_coverage'],
            'verifier':['declaration_pin_matches','output_hash_matches','assessment_schema','verifier_assessment_schema','criterion_coverage_exact','verdict_follows_findings'],
            'planner':['plan_proposal_schema','brief_coverage','library_membership','port_type_compatibility','dependency_closure','acyclicity','delivery_leaf_coverage','mandatory_check_bundle_present','effects_within_policy','resource_feasibility','budget_ceilings','suggested_checks_known']}
    handlers={'intent':intent.execute,'requirements':requirements.execute,'planner':planner.execute}
    installed={};prepared={}
    for stage,entry in catalog['capsules'].items():
        if prepared_assets is not None:
            continue
        raw=assets.joinpath(entry['declaration_path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=entry['declaration_sha256']:raise ResearchError('asset_integrity','Installed declaration changed after catalog pin')
        declaration_ref=store.put_blob(raw,media_type='application/json');declaration=store.read_record(declaration_ref,contract_id='capsule-declaration')
        stage_instructions=base_instructions
        if stage=='planner':
            # CoverageEntry.item_kind explicitly excludes evidence obligations
            # from the inverse-tag rule. This is fixed contract interpretation,
            # independent of any request, Brief, fixture or observed output.
            stage_instructions+=b'\nPlanner coverage contract: coverage entries with item_kind requirement must exactly invert nodes.requirement_ids; entries with item_kind deliverable must exactly invert nodes.deliverable_ids. An evidence_obligation coverage entry names the existing nodes intended to produce that evidence. Nodes carry no evidence-obligation tag, so such entries are outside the inverse-tag rule and are not inconsistent merely because no requirement_ids or deliverable_ids contains their item_id. Check these entries for internally resolved node_ids only; whether the item or evidence assignment agrees with the hidden Brief belongs to deterministic host checks and cannot be established from this pair. Apply this distinction to both internal_consistency and coverage_map_consistent.\n'
        instructions_ref=store.put_blob(frozen_output_instructions(stage_instructions,declaration),media_type='text/plain')
        body_refs={}
        for body in entry['body']:
            data=package.joinpath(body['path']).read_bytes()
            if hashlib.sha256(data).hexdigest()!=body['sha256']:raise ResearchError('asset_integrity','Installed carrier/prompt changed after catalog pin')
            body_refs[body['path']]=store.put_blob(data)
        code_path='research/checks/compiler.py' if stage in {'intent','requirements'} else 'research/checks/verifier.py' if stage=='verifier' else 'research/planning.py'
        runner_bytes=package.joinpath(code_path).read_bytes()
        if stage in {'intent','requirements'}:
            runner_bytes=json_bytes({'implementation':code_path,'files':{code_path:store.put_blob(runner_bytes),
                'research/target_comparisons.py':store.put_blob(package.joinpath('research/target_comparisons.py').read_bytes())}})
        runner_ref=store.put_blob(runner_bytes)
        if stage == 'planner':
            paths = ['research/planning.py', 'research/binding.py', 'research/unified_planning.py',
                     'research/summary_planning.py', 'research/capability_planning.py', 'research/planner_catalog.py']
            closure = {path: store.put_blob(package.joinpath(path).read_bytes()) for path in paths}
            runner_ref = store.put_blob(json_bytes({'implementation': 'research.planning.planner_checks', 'files': closure}))

        port=declaration['ports']['outputs'][0]['name'];cc=declaration['identity']['name']
        asset_release=declaration['identity']['version_label']
        # Verifier remains the exact installed release. Changed work releases
        # get distinct immutable artifact IDs, preserving prior captures.
        asset_suffix=asset_release
        bundle={'schema_version':'1.0.0','id':cc+'.checks.'+asset_suffix,'bundle_id':cc+'.checks','version':'1.0.0','target_cc_name':cc,'target_cc_version_range':asset_release,
            'checks':[{'check_id':key,'target_port':port,'rule_summary':'Enforce the source-defined '+key+' invariant on exact bound artifacts and observed records',
                'runner_ref':runner_ref,'reads':['output'] if key.endswith('_schema') else ['output','inputs','runtime_records'],'blocking':key!='suggested_checks_known'} for key in checks[stage]],'owner_role':'verifier_owner'}
        profile_suffix='.coverage_scope_3' if stage=='planner' else '.schema_context_2'
        profile_version='1.2.0' if stage=='planner' else '1.1.0'
        profile={'schema_version':'1.0.0','id':cc+'.profile.'+asset_suffix+profile_suffix,'profile_id':cc+'.profile','version':profile_version,'target_cc_name':cc,'target_cc_version_range':asset_release,
            'criteria':[{'criterion_id':key,'question':question,'blocking':True,'answerable_from':'declaration_and_output','target_port':None} for key,question in [*generic,*extra[stage]]],
            'instruction_ref':instructions_ref,'model_call_limit':1,'time_s':60,'owner_role':'verifier_owner'}
        bundle_ref=store.put_record('check-bundle',bundle);profile_ref=store.put_record('checking-profile',profile)
        prepared[stage]={'declaration_ref':declaration_ref,'declaration':declaration,'body_refs':body_refs,
            'bundle_ref':bundle_ref,'profile_ref':profile_ref,'bundle':bundle,'runner_ref':runner_ref,'cc':cc}
    if prepared_assets is None and intent_version=='m1-7':
        from .intent_release import prepare_intent_release
        prepared['intent']=await prepare_intent_release(store,base=prepared['intent'])
    if prepared_assets is None and intent_version=='m1-8':
        from .intent_release import prepare_intent_m1_8_release
        prepared['intent']=await prepare_intent_m1_8_release(store,base=prepared['intent'])
    if prepared_assets is None and requirements_version=='m1-9':
        from .requirements_release import prepare_requirements_release
        prepared['requirements']=await prepare_requirements_release(store,base=prepared['requirements'])
    if prepared_assets is not None:
        if not isinstance(prepared_assets, dict) or set(prepared_assets) != set(catalog['capsules']):
            raise ResearchError('prepared_catalog_invalid', 'Prepared catalog must explicitly cover every packaged compiler stage')
        for stage, supplied in prepared_assets.items():
            if stage=='intent' and intent_version=='m1-7':
                from .intent_release import prepare_intent_release
                expected=await prepare_intent_release(store)
                if supplied!=expected:
                    raise ResearchError('prepared_catalog_invalid','Intent m1-7 candidate differs from exact explicit release')
                prepared[stage]=expected
                continue
            if stage=='intent' and intent_version=='m1-8':
                from .intent_release import prepare_intent_m1_8_release
                expected=await prepare_intent_m1_8_release(store)
                if supplied!=expected:
                    raise ResearchError('prepared_catalog_invalid','Intent m1-8 candidate differs from exact explicit release')
                prepared[stage]=expected
                continue
            if stage=='requirements' and requirements_version=='m1-9':
                from .requirements_release import prepare_requirements_release
                expected=await prepare_requirements_release(store)
                if supplied!=expected:
                    raise ResearchError('prepared_catalog_invalid','Requirements m1-9 candidate differs from exact explicit release')
                prepared[stage]=expected
                continue
            required = {'declaration_ref', 'bundle_ref', 'profile_ref', 'body_refs', 'runner_ref', 'cc'}
            candidates = supplied if isinstance(supplied, list) else [supplied]
            if not candidates or (stage != 'verifier' and len(candidates) != 1):
                raise ResearchError('prepared_catalog_invalid', 'Only the verifier stage may have multiple explicit releases')
            packaged = candidates[0]
            entry = catalog['capsules'][stage]
            raw_declaration = assets.joinpath(entry['declaration_path']).read_bytes()
            if hashlib.sha256(raw_declaration).hexdigest() != entry['declaration_sha256']:
                raise ResearchError('asset_integrity', 'Installed declaration changed after catalog pin')
            original = json.loads(raw_declaration.decode('utf-8'))
            original_body = {row['path']: row['sha256'] for row in entry['body']}
            base_decl = store.read_record(packaged.get('declaration_ref'), contract_id='capsule-declaration')
            if (base_decl != original or packaged.get('declaration_ref', {}).get('sha256') != entry['declaration_sha256']
                    or packaged.get('cc') != original['identity']['name']
                    or set(packaged.get('body_refs', {})) != set(original_body)
                    or any(packaged['body_refs'][path].get('sha256') != digest for path, digest in original_body.items())):
                raise ResearchError('prepared_catalog_invalid', 'Prepared baseline does not match the exact packaged compiler release')
            validated_candidates = []
            for candidate in candidates:
                if not isinstance(candidate, dict) or not required.issubset(candidate):
                    raise ResearchError('prepared_catalog_invalid', 'Prepared compiler release is incomplete')
                declaration = store.read_record(candidate['declaration_ref'], contract_id='capsule-declaration')
                bundle = store.read_record(candidate['bundle_ref'], contract_id='check-bundle')
                profile = store.read_record(candidate['profile_ref'], contract_id='checking-profile')
                body_refs = candidate['body_refs']
                body_paths = {item['path'] for item in declaration['identity']['body']}
                packaged_body_paths = set(packaged['body_refs'])
                packaged_decl_paths = {item['path'] for item in packaged['declaration']['identity']['body']}
                expected_body_paths = packaged_body_paths | (body_paths - packaged_decl_paths)
                problems = []
                if candidate.get('declaration', declaration) != declaration:
                    problems.append('declaration')
                if candidate.get('bundle', bundle) != bundle:
                    problems.append('bundle')
                if candidate.get('profile', profile) != profile:
                    problems.append('profile')
                if candidate['cc'] != declaration['identity']['name'] or candidate['cc'] != packaged['cc']:
                    problems.append('cc')
                if candidate['runner_ref'] != packaged['runner_ref']:
                    problems.append('runner')
                if stage != 'verifier' and any(candidate[key] != packaged[key] for key in
                        ('declaration_ref', 'bundle_ref', 'profile_ref', 'body_refs')):
                    problems.append('non-verifier-override')
                if set(body_refs) != expected_body_paths or not body_paths.issubset(body_refs):
                    problems.append('body-paths')
                if stage == 'verifier' and (not packaged_body_paths.issubset(body_refs)
                        or any(body_refs.get(path) != packaged['body_refs'][path] for path in packaged_body_paths)):
                    problems.append('packaged-body-pins')
                if body_paths.issubset(body_refs) and any(body_refs[item['path']].get('sha256') != item['sha256']
                        for item in declaration['identity']['body']):
                    problems.append('body-hashes')
                expected_implementation_refs = tuple(body_refs[item['path']] for item in declaration['identity']['body'])
                if tuple(candidate.get('implementation_refs', expected_implementation_refs)) != expected_implementation_refs:
                    problems.append('implementation-refs')
                if problems:
                    raise ResearchError('prepared_catalog_invalid',
                                        'Prepared release metadata or implementation pins are stale: ' + ', '.join(problems),
                                        {'stage': stage, 'problems': problems,
                                         'body_paths': sorted(body_refs), 'declared_body_paths': sorted(body_paths)})
                for item in declaration['identity']['body']:
                    store.read_blob(body_refs[item['path']])
                validated_candidates.append({**candidate, 'declaration': declaration, 'bundle': bundle, 'profile': profile})
            prepared[stage] = validated_candidates if len(validated_candidates) > 1 else validated_candidates[0]
    if prepare_only:return prepared
    # Immutable preparation has no model/calibration dependency. Eligibility is
    # evaluated only after the complete bounded compiler catalog is captured.
    for stage,releases in prepared.items():
      for value in (releases if isinstance(releases, list) else [releases]):
        declaration_ref=value['declaration_ref'];declaration=value['declaration'];body_refs=value['body_refs']
        bundle_ref=value['bundle_ref'];profile_ref=value['profile_ref'];bundle=value['bundle'];runner_ref=value['runner_ref'];cc=value['cc']
        existing=None
        try:existing=library.get(cc,declaration['identity']['version_label'])
        except ResearchError as exc:
            if exc.code!='library_membership':raise
        if initialize:
            if existing is None:
                library.associate_checks(declaration_ref,bundle_ref,profile_ref,actor)
                admission_ref=await (library.bootstrap if bootstrap else library.admit)(declaration_ref,body_refs,actor,memory_mb=memory_mb)
            else:
                association=library.association(declaration_ref)
                if (existing['declaration_ref']!=declaration_ref or existing['body_refs']!=body_refs or association['bundle_ref']!=bundle_ref
                    or association['profile_ref']!=profile_ref or existing['standing'] not in {'inactive','active'} or existing['effect_scope']!='live_plans'):
                    raise ResearchError('installed_catalog_conflict','Explicit init cannot overwrite or reactivate a changed/suspended/revoked installed version')
                admission_ref=existing['admission_ref']
        else:
            existing=library.get(cc,declaration['identity']['version_label']);association=library.association(declaration_ref)
            if existing['declaration_ref']!=declaration_ref or existing['body_refs']!=body_refs or association['bundle_ref']!=bundle_ref or association['profile_ref']!=profile_ref or existing['standing']!='active':
                raise ResearchError('installed_catalog_unadmitted','Ordinary startup cannot adopt a new, changed or inactive version')
            admission_ref=existing['admission_ref']
        admission=store.read_record(admission_ref)
        if admission['status']!='admitted':raise ResearchError('bootstrap_blocked','Fixed installed CC failed governed eligibility',{'admission_ref':admission_ref})
        if initialize and activate and not bootstrap and (existing is None or existing['standing']=='inactive'):
            library.set_standing(cc,declaration['identity']['version_label'],'active',actor,reason='Explicit operator installation of the bounded M1 catalog')
        if stage in handlers:
            handler=handlers[stage]
            if stage=='intent' and intent_version=='m1-8':
                from .capsules.intent_m1_8 import execute as handler
            if stage=='requirements' and requirements_version=='m1-9':
                from .capsules.requirements_m1_9 import execute as handler
            registry.register(cc,declaration['identity']['version_label'],handler,declaration_sha256=declaration_ref['sha256'],
                implementation_refs=tuple(body_refs[body['path']] for body in declaration['identity']['body']))
            check_registry.register_bundle(bundle['bundle_id'],checks[stage],compiler_checks if stage in {'intent','requirements'} else planner_checks,
                implementation_ref=runner_ref,profile_ref=profile_ref)
        installed[stage]={'pin':admission['cc'],'admission_ref':admission_ref,'declaration_ref':declaration_ref,'bundle_ref':bundle_ref,'profile_ref':profile_ref,'body_refs':body_refs}
    library.configure_verifier(installed['verifier']['pin'])
    return installed
