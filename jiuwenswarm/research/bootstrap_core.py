"""Protected core composition; explicit installation is distinct from startup."""

from __future__ import annotations

import asyncio
import json
import base64
import copy
from dataclasses import dataclass,field
from importlib.resources import files

from .binding import Binder,ContractFactory
from .checks import CheckRegistry
from .compiler import IntentionCompiler,register_compiler_capsules
from .control import ResearchService
from .contracts import ResearchError
from .library import LibraryService
from .planning import PlanningCoordinator
from .runner import CapsuleRunner,Registry
from .scheduler import Scheduler
from .run_evidence import RunEvidence


@dataclass
class CoreComposition:
    service: ResearchService
    runner: CapsuleRunner
    library: LibraryService
    registry: Registry
    checks: CheckRegistry
    compiler: IntentionCompiler | None = None
    planner: PlanningCoordinator | None = None
    scheduler: Scheduler | None = None
    installed: dict = field(default_factory=dict)
    diagnostics: list[dict] = field(default_factory=list)
    static_template_ref: dict | None = None
    evidence: object | None = None
    calibration_authority: object | None = None
    calibration_diagnostics: list[dict] = field(default_factory=list)
    rsi_diagnostics: list[dict] = field(default_factory=list)
    evidence_aware_pilot_catalog_ref: dict | None = None


async def compose_core(*,store,operator,model,executor,readiness,upload_manager,principal,
                       configuration_ref,model_selection_profile_ref,deployment_ref,
                       workspace_id,operator_actor=None,initialize=False,protected_options=None,connectors=None,profiles=None,rsi_scope_observer=None):
    """Compose only approved refs and installed pins. Missing refs remain blocked.

    protected_options is server initialization data, not operator-config schema
    or a client payload. No callable or graph arrives through submit.
    """
    options=dict(protected_options or {});actor=operator_actor or principal
    from .utility_rsi_scope import require_scope
    if require_scope(store, operator.snapshot(), options) is not None:
        raise ResearchError('utility_rsi_scope', 'Utility-only RSI bindings cannot initialize a research product composition')
    from .releases import STAGES as RELEASE_STAGES, implicit_release, pinned_extras, require_release
    selections={stage:require_release(stage,options.get(stage+'_version',implicit_release(stage)),'configuration_override') for stage in RELEASE_STAGES}
    intent_version,requirements_version,screening_version,delivery_version=(selections[k] for k in ('intent','requirements','screening','delivery'))
    configuration=store.read_record(configuration_ref)
    if configuration.get('operator',configuration)!=operator.snapshot():
        raise ResearchError('configuration_override','Captured configuration differs from validated operator settings')
    await asyncio.to_thread(store.warm_product_material_index)
    registry=Registry();checks=CheckRegistry()
    catalog=json.loads(files('jiuwenswarm.research_assets').joinpath('catalog.json').read_text('utf-8'))
    from .capsules.assets import load_research_catalog
    research_catalog=load_research_catalog()
    from .compiler import prepare_compiler_assets
    compiler_assets=await prepare_compiler_assets(store,requirements_version=requirements_version,intent_version=intent_version)
    from .capsules.assets import build_research_assets
    research_assets=build_research_assets(store,screening_version=screening_version,delivery_version=delivery_version)
    evidence_aware_review=options.get('evidence_aware_review') is True
    if evidence_aware_review and options.get('finite_e1_binding_ref') is not None:
        raise ResearchError('evidence_pilot_assets','Evidence-aware pilot releases are unavailable to the finite E1 shortcut')
    bootstrap_pins=tuple(v['declaration_sha256'] for v in catalog['capsules'].values())+tuple(v['declaration_ref']['sha256'] for v in research_catalog['stages'].values())
    bootstrap_pins+=pinned_extras(selections,compiler_assets,research_assets)
    paper_assets={}
    integrated = options.get('integrated_workflows') is True
    if options.get('paper_summary_workflow') is True or integrated:
        from .summary_planning import is_document_summary_policy
        from .unified_planning import is_integrated_policy
        from .capability_planning import is_capability_policy
        policy=store.read_record(operator.snapshot()['cc']['plan_policy_ref'],contract_id='plan-policy')
        permitted = (is_integrated_policy(policy) or is_capability_policy(policy)) if integrated else is_document_summary_policy(policy)
        if not permitted or operator.snapshot()['cc']['evaluation_profile_ref'] is not None:
            raise ResearchError('paper_policy_binding','Paper workflow requires its exact protected document policy')
        from .capsules.paper_assets import build_paper_assets
        paper_assets=build_paper_assets(store)
        if integrated:
            paper_assets.pop('paper_planner', None)
        bootstrap_pins+=tuple(v['declaration_ref']['sha256'] for v in paper_assets.values())
    evidence_pilot_assets=None
    evidence_verifier_asset=None
    if evidence_aware_review:
        if not paper_assets:
            from .capsules.paper_assets import build_paper_assets
            paper_assets=build_paper_assets(store)
            paper_assets.pop('paper_planner', None)
            bootstrap_pins+=tuple(v['declaration_ref']['sha256'] for v in paper_assets.values())
        from .pilot_catalog import prepare_evidence_aware_pilot_assets
        evidence_pilot_assets=prepare_evidence_aware_pilot_assets(store,compiler_assets=compiler_assets,
            research_assets=research_assets,paper_assets=paper_assets)
        evidence_verifier_asset=evidence_pilot_assets['compiler_assets']['verifier']
        compiler_assets=copy.deepcopy(compiler_assets)
        compiler_assets['verifier']=[compiler_assets['verifier'],evidence_verifier_asset]
        bootstrap_pins+=tuple(asset['declaration_ref']['sha256'] for asset in [
            evidence_verifier_asset,*evidence_pilot_assets['research_assets'].values(),
            *evidence_pilot_assets['paper_assets'].values()])
    public=operator.snapshot()['rsi']['custodian_public_key']
    public_bytes=base64.urlsafe_b64decode(public+'='*(-len(public)%4)) if public is not None else None
    rsi_guard=None;rsi_diagnostics=[]
    if options.get('rsi_security_qualification_ref') is not None:
        try:
            from .contracts.rsi_security import RSIQualification
            rsi_guard=RSIQualification.from_store(store,options['rsi_security_qualification_ref'],scope_observer=rsi_scope_observer)
        except (ResearchError,OSError,ValueError,KeyError,TypeError) as error:
            rsi_diagnostics.append({'status':'blocked','code':getattr(error,'code','rsi_security_unavailable'),
                'detail':'Protected RSI security qualification or actual producer scope is unavailable'})
    library=LibraryService(store,executor=executor,bootstrap_pins=bootstrap_pins,rsi_public_key=public_bytes,
        rsi_key_id=operator.snapshot()['rsi']['custodian_key_id'],rsi_inbox=options.get('rsi_inbox'),rsi_custodian_uid=options.get('rsi_custodian_uid'),
        rsi_security_guard=rsi_guard)
    admission_profile=options.get('admission_execution_profile_ref')
    if admission_profile is not None and callable(getattr(executor,'run_admission_self_test',None)):
        from .admission_executor import AdmissionTestProvider
        library.self_test_provider=AdmissionTestProvider(store,configuration_ref=configuration_ref,
            execution_profile_ref=admission_profile,rpc=executor)
    evidence=RunEvidence(store,library)
    runner=CapsuleRunner(store,registry,checks,model=model,executor=executor,connectors=connectors,check_assets=library.check_assets,evidence=evidence)
    service=ResearchService(store,registry=registry,model=model,executor=executor,readiness=readiness,upload_manager=upload_manager,profiles=profiles,evidence=evidence)
    result=CoreComposition(service,runner,library,registry,checks)
    result.evidence=evidence
    result.rsi_diagnostics=rsi_diagnostics
    if options.get('calibration_runtime_ref') is not None:
        try:
            from .calibration_authority import CalibrationAuthority
            result.calibration_authority=CalibrationAuthority(store,options['calibration_runtime_ref'],
                configuration_ref=configuration_ref,model_selection_profile_ref=model_selection_profile_ref,deployment_ref=deployment_ref,
                policy_ref=operator.snapshot()['cc']['plan_policy_ref'],model=model)
        except (ResearchError,OSError,ValueError,KeyError,TypeError) as error:
            result.calibration_diagnostics.append({'status':'blocked','code':getattr(error,'code','calibration_runtime_unavailable'),
                'detail':'Optional protected calibration runtime is unresolved or invalid'})
    finite=None
    if options.get('finite_e1_binding_ref') is not None:
        try:
            from .finite_evaluation import FiniteE1
            finite=FiniteE1(store,operator,binding_ref=options['finite_e1_binding_ref'],configuration_ref=configuration_ref,library=library)
        except (ResearchError,OSError,ValueError,KeyError,TypeError) as exc:
            result.diagnostics.append({'status':'blocked','code':getattr(exc,'code','finite_e1_binding'),
                'detail':'Protected finite binding is unresolved or invalid'})
            return result
    try:
        if profiles is None and operator.snapshot()['cc']['evaluation_profile_ref'] is not None:
            from .profiles import EvaluationProfiles
            profiles=EvaluationProfiles(store,operator,fault_plan_ref=options.get('fault_plan_ref'),fixture_index_ref=options.get('fixture_index_ref'))
        service.profiles=profiles
        runner.faults=profiles
        policy=store.read_record(operator.snapshot()['cc']['plan_policy_ref'],contract_id='plan-policy')
        memory_ceiling=policy['aggregate_limits']['memory_mb']
        from .capsules.assets import register_research_capsules
        assets=research_assets
        assets.update(paper_assets)
        install_assets=dict(assets)
        if evidence_pilot_assets is not None:
            install_assets.update(evidence_pilot_assets['research_assets'])
            install_assets.update(evidence_pilot_assets['paper_assets'])
        if options.get('development_builtin_catalog') is True:
            import os
            if finite is not None or os.environ.get('JIUWENSWARM_M1_LOCAL_RESEARCH')!='1':
                raise ResearchError('development_builtin_binding','Development built-ins require explicit local research startup')
            selected_compiler_assets=[asset for value in compiler_assets.values()
                                      for asset in (value if isinstance(value,list) else [value])]
            selected_assets={**research_assets,**paper_assets}
            if evidence_pilot_assets is not None:
                selected_assets.update(evidence_pilot_assets['research_assets'])
                selected_assets.update(evidence_pilot_assets['paper_assets'])
            library.select_development_builtins([*selected_compiler_assets,*selected_assets.values()],memory_mb=memory_ceiling)
        if finite is None:
            result.installed=await register_compiler_capsules(registry,checks,library,store,actor,
                activate=initialize,initialize=initialize,memory_mb=memory_ceiling,prepared_assets=compiler_assets,requirements_version=requirements_version,intent_version=intent_version)
        else:
            # Pure immutable body preparation does not require Compiler work/resources.
            asset=compiler_assets['verifier']
            declaration=asset['declaration'];identity=declaration['identity']
            existing=None
            try:existing=library.get(identity['name'],identity['version_label'])
            except ResearchError as exc:
                if exc.code!='library_membership':raise
            if initialize and existing is None:
                library.associate_checks(asset['declaration_ref'],asset['bundle_ref'],asset['profile_ref'],actor)
                admission_ref=await library.admit(asset['declaration_ref'],asset['body_refs'],actor,memory_mb=memory_ceiling)
            elif existing is not None:
                association=library.association(asset['declaration_ref'])
                if (existing['declaration_ref']!=asset['declaration_ref'] or existing['body_refs']!=asset['body_refs']
                    or association['bundle_ref']!=asset['bundle_ref'] or association['profile_ref']!=asset['profile_ref']
                    or existing['effect_scope']!='live_plans' or existing['standing'] not in ({'inactive','active'} if initialize else {'active'})):
                    raise ResearchError('installed_catalog_conflict','Finite startup cannot change/revive an installed verifier')
                admission_ref=existing['admission_ref']
            else:raise ResearchError('installed_catalog_unadmitted','Finite shared verifier is not installed')
            admission=store.read_record(admission_ref,contract_id='library-admission')
            if admission['status']!='admitted':raise ResearchError('catalog_admission_blocked','Finite verifier eligibility did not pass',{'admission_ref':admission_ref})
            if initialize and (existing is None or existing['standing']=='inactive'):
                library.set_standing(identity['name'],identity['version_label'],'active',actor,reason='Explicit installation of the exact finite shared verifier')
            if asset['declaration_ref']!=finite._profile['verifier_cc_ref']:
                raise ResearchError('verifier_binding','Finite profile differs from the installed shared verifier')
            result.installed={'verifier':dict(asset,admission_ref=admission_ref,pin=admission['cc'])}
            library.configure_verifier(admission['cc'])
            names=[name.removeprefix('research.') for name in finite._qualification['stages']]
            assets={name:assets[name] for name in names}
            install_assets=dict(assets)

        for stage,asset in install_assets.items():
            declaration=store.read_record(asset['declaration_ref']);identity=declaration['identity']
            if initialize:
                memory=options.get('research_memory_mb',{}).get(stage.removesuffix('_evidence'),memory_ceiling)
                if type(memory) is not int or not 0<memory<=memory_ceiling:raise ResearchError('memory_binding_invalid','Installed admission memory must narrow the approved policy ceiling')
                existing=None
                try:existing=library.get(identity['name'],identity['version_label'])
                except ResearchError as exc:
                    if exc.code!='library_membership':raise
                if existing is None:
                    library.associate_checks(asset['declaration_ref'],asset['bundle_ref'],asset['profile_ref'],actor)
                    admission_ref=await library.admit(asset['declaration_ref'],asset['body_refs'],actor,memory_mb=memory)
                else:
                    association=library.association(asset['declaration_ref'])
                    if (existing['declaration_ref']!=asset['declaration_ref'] or existing['body_refs']!=asset['body_refs']
                        or association['bundle_ref']!=asset['bundle_ref'] or association['profile_ref']!=asset['profile_ref']
                        or existing['standing'] not in {'inactive','active'} or existing['effect_scope']!='live_plans'):
                        raise ResearchError('installed_catalog_conflict','Init cannot overwrite or automatically reactivate an existing version')
                    admission_ref=existing['admission_ref']
                admission=store.read_record(admission_ref)
                if admission['status']!='admitted':raise ResearchError('catalog_admission_blocked','Installed research CC eligibility did not pass',{'admission_ref':admission_ref})
                if existing is None or existing['standing']=='inactive':
                    library.set_standing(identity['name'],identity['version_label'],'active',actor,reason='Explicit operator installation of the bounded M1 research catalog')
            else:
                entry=library.get(identity['name'],identity['version_label'])
                if entry['declaration_ref']!=asset['declaration_ref'] or entry['standing']!='active':raise ResearchError('installed_catalog_unadmitted','Ordinary startup cannot admit or activate a changed version')
            current=library.get(identity['name'],identity['version_label'])
            asset['admission_ref']=current['admission_ref']
            asset['pin']=store.read_record(current['admission_ref'],contract_id='library-admission')['cc']
        register_research_capsules(registry,checks,library,store,connectors=connectors,executor=executor,
                                  assets={key:value for key,value in assets.items() if key not in paper_assets})
        if paper_assets:
            from .capsules.paper_assets import register_paper_capsules
            register_paper_capsules(registry,checks,library,store,assets=paper_assets)
        result.installed.update(assets)
        if evidence_pilot_assets is not None:
            evidence_research=evidence_pilot_assets['research_assets']
            evidence_paper=evidence_pilot_assets['paper_assets']
            register_research_capsules(registry,checks,library,store,connectors=connectors,executor=executor,
                assets={'evaluation':evidence_research['evaluation_evidence'],
                        'delivery':evidence_research['delivery_evidence']})
            from .capsules.paper_assets import register_paper_capsules
            register_paper_capsules(registry,checks,library,store,assets={
                'paper_summary':evidence_paper['paper_summary_evidence'],
                'paper_delivery':evidence_paper['paper_delivery_evidence']})
            result.installed.update(evidence_research)
            result.installed.update(evidence_paper)
            from .pilot_catalog import capture_evidence_aware_pilot_catalog
            result.evidence_aware_pilot_catalog_ref=capture_evidence_aware_pilot_catalog(store,library,
                evidence_assets=evidence_pilot_assets,original_assets=assets)
        from .capsule_extensions.catalog import register_active
        result.installed.update(register_active(registry, checks, library, store))
        if finite is None:
            from .screening_static_capture import capture_static_template
            result.static_template_ref=capture_static_template(store,library,
                screening_version=screening_version,delivery_version=delivery_version,expected_ref=operator.snapshot()['cc']['static_template_ref'])
            if result.static_template_ref!=operator.snapshot()['cc']['static_template_ref']:
                raise ResearchError('static_template_pin','Approved configuration must explicitly capture the current authored static release')
        else:result.static_template_ref=finite._binding['template_ref']
    except (ResearchError,OSError,ValueError) as exc:
        refs=[exc.details['admission_ref']] if isinstance(exc,ResearchError) and exc.details.get('admission_ref') else []
        result.diagnostics.append({'status':'blocked','code':getattr(exc,'code','installed_assets_unavailable'),'detail':getattr(exc,'message','Installed assets or exact admissions are unavailable'),'evidence_refs':refs})
    required=('profile_ref','workspace_ref','input_directory_ref','finalization_profile_ref','authority_ceiling','resource_inventory_ref')
    if finite is None:required+=('default_policy_ref','compiler_template_ref','compiler_limits','planner_template_ref','planner_limits')
    for name in required:
        if name not in options:result.diagnostics.append({'status':'blocked','code':'protected_source_unavailable','detail':'Missing protected bootstrap binding: '+name})
    if result.diagnostics:return result
    refs={'finalization_profile_ref':'node-finalization-profile','resource_inventory_ref':'resource-inventory'}
    if finite is None:refs['default_policy_ref']='default-policy'
    try:
        for key,contract in refs.items():store.read_record(options[key],contract_id=contract)
        for key in ('profile_ref','workspace_ref','input_directory_ref')+(() if finite is not None else ('compiler_template_ref','planner_template_ref')):store.read_blob(options[key])
        run_authority=copy.deepcopy(options['authority_ceiling'])
        host_records=copy.deepcopy(options.get('host_records',{}))
        if finite is None:
            # These fixed host inputs come from the exact admitted release and
            # captured operator record, never from a request or proposed graph.
            screening=result.installed['screening']
            declaration=store.read_record(screening['declaration_ref'],contract_id='capsule-declaration')
            selected=library.get(declaration['identity']['name'],declaration['identity']['version_label'])
            rubric=screening['body_refs']['screening_rubric.json']
            if (selected['declaration_ref']!=screening['declaration_ref']
                    or selected['body_refs'].get('screening_rubric.json')!=rubric
                    or host_records.get('screening_rubric',rubric)!=rubric):
                raise ResearchError('host_record_binding','Prepared Screening rubric differs from the exact admitted body')
            store.read_record(rubric,contract_id='screening-rubric')
            host_records['screening_rubric']=rubric
            for ref in (rubric,configuration_ref):
                if ref not in run_authority['resource_reads']:run_authority['resource_reads'].append(ref)
        factory=ContractFactory(store,library,verifier_pin=result.installed['verifier']['pin'],finalization_profile_ref=options['finalization_profile_ref'])
        compiler=planner=None
        if finite is None:
            compiler=IntentionCompiler(store,runner,factory,intent_pin=result.installed['intent']['pin'],requirements_pin=result.installed['requirements']['pin'],
                default_policy_ref=options['default_policy_ref'],template_ref=options['compiler_template_ref'],node_limits=options['compiler_limits'],
                policy_ref=operator.snapshot()['cc']['plan_policy_ref'],authority_ceiling=run_authority)
            planner_stage='paper_planner' if paper_assets and not integrated and 'paper_planner' in result.installed else 'planner'
            planner=PlanningCoordinator(store,runner,factory,planner_pin=result.installed[planner_stage]['pin'],template_ref=options['planner_template_ref'],
                node_limits=options['planner_limits'],authority_ceiling=run_authority)
        binder=Binder(store,library,checks,search_bounds_ref=options.get('search_bounds_ref'),finite_e1=finite)
        scheduler=Scheduler(store,runner,factory,binder,library=library,planning=planner,progress_sink=options.get('progress_sink'),evidence=evidence)
        service.finite_e1=finite
        service.compiler=compiler;service.binder=binder;service.scheduler=scheduler
        settings=operator.snapshot()['cc']
        policy=store.read_record(settings['plan_policy_ref'],contract_id='plan-policy')
        run_context={'configuration_ref':configuration_ref,'model_selection_profile_ref':model_selection_profile_ref,'deployment_ref':deployment_ref,
            'router':settings['router'],'run_limits':policy['aggregate_limits'],'profile_ref':options['profile_ref'],'workspace_ref':options['workspace_ref'],
            'input_directory_ref':options['input_directory_ref'],'profile_id':options.get('profile_id'),'resource_inventory_ref':options['resource_inventory_ref'],
            'run_inputs':options.get('run_inputs',{}),'host_records':host_records,'authority_ceiling':run_authority,
            'routing_context':options.get('routing_context'),
            'verifier_cc_ref':result.installed['verifier']['declaration_ref'],
            'candidate_pins':profiles._profile['candidate_pins'] if profiles is not None and profiles.profile_id is not None else options.get('candidate_pins',[])}
        if profiles is not None:
            if run_context['profile_id'] not in (None,profiles.profile_id):raise ResearchError('evaluation_profile','Protected binding differs from the approved evaluation profile')
            run_context['profile_id']=profiles.profile_id
        if finite is not None:run_context['finite_e1_binding_ref']=finite.binding_ref
        service.configure_workspace(principal.account_id,workspace_id,**run_context)
        result.compiler,result.planner,result.scheduler=compiler,planner,scheduler
    except (ResearchError,OSError,ValueError) as exc:
        result.diagnostics.append({'status':'blocked','code':getattr(exc,'code','protected_source_unavailable'),'detail':getattr(exc,'message','Protected source binding is unavailable')})
    return result
