"""Protected native gateway composition, independent of provider ownership."""

from __future__ import annotations

import copy
import inspect
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .accounts import AccountStore,PreferenceService
from .bootstrap_core import compose_core
from .contracts import Principal,ResearchError,validate
from .control import ResearchService
from .intake import extract_document
from .operator_config import ConfigError,OperatorConfiguration
from .native_profile import M1_REFUSAL_REASON
from .runner import Registry
from .shell_auth import SessionAuthority
from .state import SQLiteRunStore
from .uploads import UploadManager
BOOTSTRAP_HANDOFF=Path('/run/ai4r/browser-bootstrap.json')


@dataclass
class NativeResearchAttachment:
    service: ResearchService
    store: SQLiteRunStore
    accounts: AccountStore
    authority: SessionAuthority
    bootstrap_url: str
    composition: object | None
    diagnostics: list[dict]
    runtime_ports: object | None = None

    def close(self):
        self.authority.close();self.accounts.close();self.store.close()


def _protected_file(path: str) -> bytes:
    supplied=Path(path)
    if not supplied.is_absolute() or supplied.is_symlink():raise ResearchError('unavailable','Protected startup record path is invalid')
    metadata=supplied.stat()
    if not stat.S_ISREG(metadata.st_mode) or (os.name=='posix' and metadata.st_mode & 0o022):
        raise ResearchError('unavailable','Protected startup record permits an untrusted writer')
    return supplied.read_bytes()


def compose_evaluation_reader(*,store,operator,principal,bindings):
    """Resolve a protected historical scope without executable resources."""
    settings=operator.snapshot()
    profile_ref=settings['cc']['evaluation_profile_ref']
    if profile_ref is None:return None
    options=bindings.get('protected_options',{})
    runtime_ref=options.get('evaluation_runtime_ref')
    if runtime_ref is None:return None
    from .evaluation_history import EvaluationReader
    reader=EvaluationReader(store,runtime_ref=runtime_ref,operator=operator)
    runtime=reader.runtime
    expected={'profile_ref':profile_ref,'configuration_ref':bindings['configuration_ref'],
        'workspace_id':bindings['workspace_id'],'account_id':principal.account_id,
        'model_selection_profile_ref':bindings['model_selection_profile_ref'],
        'deployment_ref':bindings['deployment_ref'],'policy_ref':settings['cc']['plan_policy_ref']}
    if (any(runtime[key]!=value for key,value in expected.items())
            or runtime['workspace_id'] not in principal.workspace_ids):
        raise ResearchError('auth','Historical runtime differs from protected startup identity')
    for option,key in [('evaluation_assets_ref','assets_ref'),('library_snapshot_ref','library_snapshot_ref')]:
        if options.get(option) is not None and options[option]!=runtime[key]:
            raise ResearchError('auth','Historical runtime differs from its protected capture')
    if store.record_kind(profile_ref)!='evaluation-profile' or store.record_kind(runtime['assets_ref'])!='evaluation-assets':
        raise ResearchError('auth','Historical profile or assets have an unowned capture kind')
    store.read_record(profile_ref,contract_id='evaluation-profile')
    assets=store.read_record(runtime['assets_ref'])
    fields={'schema','id','profile_ref','configuration_ref','account_id','workspace_id','campaign_id','entries','cases'}
    if (not isinstance(assets,dict) or set(assets)!=fields or assets['schema']!='ai4r-evaluation-assets:1'
            or any(assets[key]!=runtime[key] for key in
                ('profile_ref','configuration_ref','account_id','workspace_id','campaign_id'))):
        raise ResearchError('auth','Historical assets differ from the original runtime')
    return reader


def compose_evaluation_provider(*,store,operator,composition,principal,bindings):
    """Bind only captured evaluation assets to the existing actual core.

    No snapshot, admission, credential, contract or case is manufactured here.
    The launcher must already have captured the exact approved identities.
    """
    profile_ref=operator.snapshot()['cc']['evaluation_profile_ref']
    if profile_ref is None:return None
    options=bindings.get('protected_options',{})
    assets_ref=options.get('evaluation_assets_ref');snapshot_ref=options.get('library_snapshot_ref')
    runtime_ref=options.get('evaluation_runtime_ref')
    if assets_ref is None or snapshot_ref is None or runtime_ref is None or composition is None or principal is None:
        raise ResearchError('unavailable','Exact captured evaluation runtime, assets, snapshot or core resources are unavailable')
    reader=compose_evaluation_reader(store=store,operator=operator,principal=principal,bindings=bindings)
    if reader is None or reader.runtime['assets_ref']!=assets_ref:
        raise ResearchError('auth','Execution assets differ from protected historical scope')
    from .admitted_measurement import AdmittedResourceContext,AdmittedMeasurementResources
    from .evaluation_provider import EvaluationProvider,InstalledEvaluationResources
    exact={key:copy.deepcopy(bindings[key]) for key in
        ('configuration_ref','model_selection_profile_ref','deployment_ref','workspace_id','protected_options')}
    context=AdmittedResourceContext(store,operator,composition,principal,exact,composition.runner.executor)
    admitted=AdmittedMeasurementResources(context)
    resources=InstalledEvaluationResources(admitted,profile_ref=profile_ref,assets_ref=assets_ref,library_snapshot_ref=snapshot_ref)
    provider=EvaluationProvider(store,operator,assets_ref=assets_ref,resources=resources,library=composition.library)
    assets=provider.assets
    if (assets['configuration_ref']!=bindings['configuration_ref'] or assets['account_id']!=principal.account_id
            or assets['workspace_id']!=bindings['workspace_id']):
        raise ResearchError('auth','Evaluation assets differ from protected startup identity')
    resources.bind_runtime(runtime_ref)
    return provider


async def attach_native_research(web_channel,runtime_ports=None):
    """Attach before WebChannel.start; no dynamic factories or provider facade.

    JIUWENSWARM_M1_BOOTSTRAP_BINDINGS names a protected JSON file containing
    exactly {"binding_ref": Ref}. That immutable Ref resolves in the core store.
    Explicit initialization belongs to the init command, never normal startup.
    Missing bindings retain authenticated inspection and deny new execution.
    """
    state_root=Path(os.environ.get('JIUWENSWARM_M1_STATE','/var/lib/ai4r'))
    account_root=Path(os.environ.get('JIUWENSWARM_M1_ACCOUNTS','/var/lib/ai4r-accounts'))
    if not state_root.is_absolute() or not account_root.is_absolute():raise ResearchError('unavailable','Private storage roots must be absolute')
    store=SQLiteRunStore(state_root,recover=True,input_root='/workspace/input');accounts=AccountStore(account_root)
    origin=os.environ.get('JIUWENSWARM_M1_ORIGIN')
    if not origin:raise ResearchError('unavailable','Protected native origin is missing')
    authority=SessionAuthority(account_root/'sessions',origin,
        reusable_bootstrap=os.environ.get('JIUWENSWARM_M1_REUSABLE_BOOTSTRAP')=='1')
    diagnostics=[];bindings=None;operator=None;composition=None
    config_path=os.environ.get('JIUWENSWARM_M1_CONFIG','/etc/ai4r/config.yaml')
    try:
        if M1_REFUSAL_REASON:
            raise ResearchError('unavailable','Operator configuration was unavailable at boot')
        _protected_file(config_path)
        operator=OperatorConfiguration.load(config_path,resolve_profile=lambda ref:store.read_record(ref))
    except (ConfigError,ResearchError,OSError,ValueError):
        diagnostics.append({'status':'blocked','code':'operator_configuration_unavailable',
                            'detail':'Mandatory operator configuration is invalid or unavailable; execution is disabled'})
    binding_path=os.environ.get('JIUWENSWARM_M1_BOOTSTRAP_BINDINGS')
    try:
        if not binding_path:raise ResearchError('unavailable','Protected bootstrap bindings are missing')
        envelope=json.loads(_protected_file(binding_path).decode('utf-8'))
        if not isinstance(envelope,dict) or set(envelope)!={'binding_ref'}:raise ResearchError('unavailable','Protected binding locator is invalid')
        validate('Ref',envelope['binding_ref']);bindings=store.read_record(envelope['binding_ref'])
        required={'workspace_id','host_id','configuration_ref','model_selection_profile_ref','deployment_ref','protected_options'}
        if not required.issubset(bindings) or any(not isinstance(bindings[key],str) or not bindings[key] for key in ('workspace_id','host_id')):
            raise ResearchError('unavailable','Protected binding record is incomplete')
        if operator is None:raise ResearchError('unavailable','Mandatory operator configuration is missing')
        captured=store.read_record(bindings['configuration_ref'])
        if captured.get('operator',captured)!=operator.snapshot():raise ResearchError('unavailable','Captured configuration differs from the single approved operator file')
    except (ResearchError,ValueError,OSError,UnicodeError) as exc:
        diagnostics.append({'status':'blocked','code':getattr(exc,'code','bootstrap_unavailable'),'detail':'Protected configuration or captured bootstrap bindings are unavailable'})
        bindings=None
    workspace=bindings['workspace_id'] if bindings else 'local'
    principal=Principal(accounts.primary()['account_id'],frozenset({workspace}),frozenset({'status','readiness','submit','reconcile','cancel','export','upload','list_uploads','delete_upload','settings'}),frozenset({'researcher','reviewer'}))
    service=ResearchService(store,registry=Registry(),model=None)
    if bindings is None and os.environ.get('JIUWENSWARM_M1_LOCAL_WORKSPACE')=='1':
        from .local_workspace import initialize_local_inputs
        service.upload_manager=initialize_local_inputs(store,account_id=principal.account_id,origin=origin)
    bind_inspection=getattr(runtime_ports,'bind_inspection',None)
    if bind_inspection is not None:
        observed=bind_inspection(store,operator,diagnostics)
        if inspect.isawaitable(observed):await observed
    async def readiness(actor):
        port=getattr(runtime_ports,'readiness',None) if runtime_ports is not None else None
        if port is None:raise ResearchError('unavailable','Protected readiness probes or immutable runtime pins are unavailable')
        report=port(actor) if callable(port) else port.report(actor)
        if inspect.isawaitable(report):report=await report
        report=copy.deepcopy(report);validate('client-readiness',report)
        from .execution_readiness import assess_execution_scope
        core_available, _, _ = assess_execution_scope(composition, bindings, operator, library_pins=report['pins'], principal=actor, model_port=getattr(runtime_ports,'model_bridge',None))
        if diagnostics or not core_available:
            report['ready']=False
            report['prerequisites']=[*report['prerequisites'],{'name':'protected_core','status':'unavailable','reason':'Exact installed catalog or protected bootstrap bindings are unavailable'}]
        return report
    if bindings is not None:
        ports_present=runtime_ports is not None and all(getattr(runtime_ports,key,None) is not None for key in ('executor','model_bridge','readiness'))
        if not ports_present:diagnostics.append({'status':'blocked','code':'runtime_ports_unavailable','detail':'Protected executor, model bridge and readiness ports are required'})
        options=copy.deepcopy(bindings['protected_options'])
        inbox=os.environ.get('JIUWENSWARM_M1_RSI_INBOX')
        if inbox is not None:
            if inbox!='/var/lib/ai4r-rsi-inbox':
                raise ResearchError('rsi_custody','Optional RSI inbox must use the fixed protected mount')
            options['rsi_inbox']=inbox;options['rsi_custodian_uid']=12002
        upload_manager=None
        timeout=options.get('document_extraction_timeout_s')
        if type(timeout) in (int,float) and timeout>0:
            upload_manager=UploadManager(store,store.input_root,extract_document,extraction_timeout_s=timeout,max_upload_bytes=options.get('max_upload_bytes'))
        else:diagnostics.append({'status':'blocked','code':'upload_deadline_unavailable','detail':'Protected document extraction deadline is missing'})
        composition=await compose_core(store=store,operator=operator,model=getattr(runtime_ports,'model_bridge',None),
            executor=getattr(runtime_ports,'executor',None),readiness=readiness,upload_manager=upload_manager,principal=principal,
            configuration_ref=bindings['configuration_ref'],model_selection_profile_ref=bindings['model_selection_profile_ref'],deployment_ref=bindings['deployment_ref'],
            workspace_id=workspace,initialize=False,protected_options=options,connectors=getattr(runtime_ports,'connectors',None),profiles=getattr(runtime_ports,'profiles',None))
        diagnostics.extend(composition.diagnostics);service=composition.service
        bind_composition=getattr(runtime_ports,'bind_composition',None)
        if bind_composition is not None:
            bound=bind_composition(composition,bindings,operator)
            if inspect.isawaitable(bound):await bound
        bind=getattr(runtime_ports,'bind_runner',None)
        if bind is not None:
            bound=bind(composition.runner)
            if inspect.isawaitable(bound):await bound
    service._readiness=readiness
    if runtime_ports is not None:
        service.model_settings=getattr(runtime_ports,'model_settings',None)
        service.freeze_model_selection=getattr(runtime_ports,'freeze_model_selection',None)
    service.evaluation_provider=None
    service.evaluation_reader=None
    service.evaluation_diagnostics=[]
    if operator is not None and bindings is not None:
        try:
            service.evaluation_reader=compose_evaluation_reader(store=store,operator=operator,
                principal=principal,bindings=bindings)
        except (ResearchError,ValueError,OSError,KeyError,TypeError):
            service.evaluation_diagnostics.append({'status':'blocked','code':'evaluation_history_unavailable',
                'detail':'The exact protected historical evaluation scope is unavailable'})
        try:
            service.evaluation_provider=compose_evaluation_provider(store=store,operator=operator,
                composition=composition,principal=principal,bindings=bindings)
        except (ResearchError,ValueError,OSError,KeyError,TypeError):
            # Optional measurement resources cannot grant fallback authority or
            # disable otherwise independent product startup/inspection.
            service.evaluation_diagnostics.append({'status':'blocked','code':'evaluation_resources_unavailable',
                'detail':'Exact approved evaluation assets or admitted measurement resources are unavailable'})
    bind_evaluation=getattr(runtime_ports,'bind_evaluation',None)
    if bind_evaluation is not None:
        observed=bind_evaluation(service.evaluation_provider)
        if inspect.isawaitable(observed):await observed
    preferences=PreferenceService(accounts,host_id=bindings['host_id'] if bindings else 'local',project_id=workspace,root=state_root)
    bootstrap_url=authority.initialize(principal)
    profile_ref=operator.snapshot()['cc']['evaluation_profile_ref'] if operator is not None else None
    if profile_ref is not None and bindings is not None and (service.evaluation_reader is not None or service.profiles is not None):
        profile=store.read_record(profile_ref,contract_id='evaluation-profile')
        campaign_id=None
        history_pins={}
        if service.evaluation_reader is not None:
            runtime=service.evaluation_reader.runtime
            campaign_id=runtime['campaign_id']
            history_pins={'runtime_ref':service.evaluation_reader.runtime_ref,'assets_ref':runtime['assets_ref']}
        fault_plan_ref=bindings['protected_options'].get('fault_plan_ref')
        if fault_plan_ref is not None:
            if store.record_kind(fault_plan_ref)!='evaluation-fault-plan':
                raise ResearchError('auth','Protected campaign definition has the wrong capture kind')
            fault_plan=store.read_record(fault_plan_ref)
            if fault_plan.get('profile_ref')!=profile_ref:
                raise ResearchError('auth','Protected campaign differs from the startup profile')
            fault_campaign=fault_plan.get('campaign_id')
            if campaign_id is not None and campaign_id!=fault_campaign:
                raise ResearchError('auth','Protected fault and measurement campaigns differ')
            campaign_id=fault_campaign
        if campaign_id is not None or not ({'E2','E3'}&set(profile['allowed_entry_points'])):
            authority.configure_evaluation({'account_id':principal.account_id,'workspace_id':workspace,
                'configuration_ref':bindings['configuration_ref'],'profile_ref':profile_ref,'profile_id':profile['profile_id']},
                run_lookup=lambda run_id:store.get_run(run_id),
                run_reconcile=lambda account_id,request_id:store.list_runs(account_id=account_id,request_id=request_id),
                campaign_id=campaign_id,**history_pins)
    service.local_chat_ready=os.environ.get('JIUWENSWARM_M1_LOCAL_CHAT')=='1'
    if bindings is not None and bindings['protected_options'].get('integrated_workflows') is True:
        from .unified_planning import is_integrated_policy
        if operator is not None and is_integrated_policy(store.read_record(
                operator.snapshot()['cc']['plan_policy_ref'], contract_id='plan-policy')):
            # The integrated product always sends the existing chat composer
            # through Compiler/Planner, including stale direct-chat choices.
            service.local_chat_ready=False
    service.local_example_ref=bindings.get('protected_options',{}).get('local_example_ref') if bindings is not None else None
    service.captured_plan_source=operator.snapshot()['cc']['plan_source'] if operator is not None else None
    defaults_path=authority.token_path.parent/'client-defaults.json'
    # Same protected custody as the bearer token, without copying the token.
    temporary=defaults_path.parent/('.client-defaults-'+__import__('secrets').token_hex(12))
    descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(descriptor,'wb') as handle:
            handle.write(json.dumps(service.client_defaults(principal),sort_keys=True,allow_nan=False).encode('utf-8'));handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,defaults_path);os.chmod(defaults_path,0o600)
    finally:temporary.unlink(missing_ok=True)
    os.environ['JIUWENSWARM_M1_CLIENT_CONFIG']=str(defaults_path)
    os.environ['JIUWENSWARM_M1_TOKEN_FILE']=str(authority.token_path)
    os.environ['JIUWENSWARM_M1_ORIGIN']=authority.origin
    handoff=BOOTSTRAP_HANDOFF;parent=handoff.parent.lstat()
    if handoff.parent.is_symlink() or not stat.S_ISDIR(parent.st_mode) or os.name=='posix' and (parent.st_uid!=os.geteuid() or stat.S_IMODE(parent.st_mode)!=0o700):
        raise ResearchError('unavailable','Private browser bootstrap handoff custody is invalid')
    pending=handoff.parent/('.browser-bootstrap-'+__import__('secrets').token_hex(12))
    descriptor=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(descriptor,'wb') as handle:
            handle.write(json.dumps({'url':bootstrap_url}).encode('utf-8'));handle.flush();os.fsync(handle.fileno())
        os.replace(pending,handoff);os.chmod(handoff,0o600)
    finally:pending.unlink(missing_ok=True)
    attachment=NativeResearchAttachment(service,store,accounts,authority,bootstrap_url,composition,diagnostics,runtime_ports)
    web_channel.research_profile=True;web_channel.research_service=service;web_channel.research_authority=authority
    web_channel.research_cc_workspace=workspace
    web_channel.research_refusal_reason='operator_configuration_unavailable' if operator is None else None
    web_channel.research_preferences=preferences;web_channel.research_composition=attachment
    # A fixed Root-sealed installation is the only operator opt-in. Missing or
    # invalid authority preserves authenticated inspection with actions denied.
    try:
        from .cc_ui_runtime import attach_native_operator
        attach_native_operator(web_channel,authority)
    except (ResearchError,OSError,ValueError,TypeError,KeyError):
        web_channel.research_cc_operator=None
        diagnostics.append({'status':'blocked','code':'cc_operator_installation_unavailable',
            'detail':'Protected human CC operator installation is unavailable; inspection remains enabled'})
    try:
        from .cc_ui_runtime import attach_native_development
        attach_native_development(web_channel,authority,workspace)
    except (ResearchError,OSError,ValueError,TypeError,KeyError):
        web_channel.research_cc_development=None
        diagnostics.append({'status':'blocked','code':'cc_development_installation_unavailable',
            'detail':'Fixed development run installation is unavailable; inspection remains enabled'})
    return attachment
