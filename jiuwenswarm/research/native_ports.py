"""Finite protected native process wiring; AgentServer owns model transport."""

from __future__ import annotations

import asyncio
import copy
import inspect
import json
import os
import stat
import hashlib
import importlib.metadata
import re
from dataclasses import dataclass
from pathlib import Path

from .bridge import GovernedBridge,ModelBridgeClient,ModelBridgeServer
from .contracts import ResearchError,validate
from .operator_config import OperatorConfiguration
from .private_rpc import PrivateRPCClient,PrivateRPCServer
from .router_client import RouterPort
from .state import SQLiteRunStore

AUTH_PROTOCOL='ai4r-authorize-v1'
STATUS_PROTOCOL='ai4r-agent-status-v1'
APP_UID=10001
BUILD_MANIFEST=Path('/usr/local/share/ai4r-build-identity.json')


def _verify_component(root,component):
    if not isinstance(component,dict) or set(component)!={'files','links'} or not isinstance(component['files'],list) or not component['files'] or not isinstance(component['links'],list):raise ValueError('component structure')
    root=Path(root).resolve(strict=True);expected=set();expected_links={}
    def contained(relative):
        if not isinstance(relative,str) or not relative or '\\' in relative:raise ValueError('file path')
        item=Path(relative)
        if item.is_absolute() or '..' in item.parts:raise ValueError('file path')
        candidate=root/item
        for ancestor in candidate.parents:
            if ancestor==root:break
            if ancestor.is_symlink():raise ValueError('symlink ancestor')
        if not candidate.resolve(strict=True).is_relative_to(root):raise ValueError('file custody')
        return candidate
    for link in component['links']:
        if not isinstance(link,dict) or set(link)!={'path','target'} or not isinstance(link['target'],str) or not link['target'] or Path(link['target']).is_absolute():raise ValueError('link structure')
        candidate=contained(link['path'])
        if not candidate.is_symlink() or os.readlink(candidate)!=link['target'] or link['path'] in expected_links:raise ValueError('link closure')
        expected_links[link['path']]=link['target']
    for file in component['files']:
        if not isinstance(file,dict) or set(file)!={'path','bytes','sha256'} or type(file['bytes']) is not int or file['bytes']<0:raise ValueError('file inventory')
        candidate=contained(file['path'])
        if file['path'] in expected or candidate.is_symlink():raise ValueError('file path')
        raw=candidate.read_bytes()
        if len(raw)!=file['bytes'] or hashlib.sha256(raw).hexdigest()!=file['sha256']:raise ValueError('installed file differs')
        expected.add(file['path'])
    observed=set();observed_links={}
    for item in root.rglob('*'):
        if item.suffix=='.pyc' or '__pycache__' in item.parts:continue
        logical=item.relative_to(root).as_posix()
        if item.is_symlink():
            contained(logical);target=os.readlink(item)
            if Path(target).is_absolute():raise ValueError('absolute link')
            observed_links[logical]=target
        elif item.is_file():observed.add(logical)
    if observed!=expected or observed_links!=expected_links or expected & set(expected_links):raise ValueError('installed closure differs')


def verify_installed_build(path=BUILD_MANIFEST,*,package_root=None,component_roots=None,allow_legacy_fixture=False):
    """Verify the independent image-build receipt and exact installed closure."""
    try:
        path=Path(path);metadata=path.lstat()
        if (not stat.S_ISREG(metadata.st_mode) or path.is_symlink() or metadata.st_nlink!=1
            or os.name=='posix' and (metadata.st_uid!=0 or metadata.st_mode & 0o022)):
            raise ValueError('manifest custody')
        value=json.loads(path.read_bytes().decode('utf-8'))
        common={'schema','files','links','dependencies','uv_lock_sha256','pyproject_sha256','build_id'}
        legacy=value.get('schema')=='ai4r-installed-build:1'
        if legacy:
            if not allow_legacy_fixture or package_root is None or path==BUILD_MANIFEST or set(value)!=common:raise ValueError('legacy manifests require an explicit isolated fixture')
        elif value.get('schema')!='ai4r-installed-build:2' or set(value)!=common|{'components'} or not isinstance(value['components'],dict) or set(value['components'])!={'jiuwenswarm_tui'}:raise ValueError('manifest structure')
        digest=value['build_id'];body={key:item for key,item in value.items() if key!='build_id'}
        actual=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if not isinstance(digest,str) or re.fullmatch('[a-f0-9]{64}',digest) is None or digest!=actual:raise ValueError('manifest identity')
        root=Path(package_root) if package_root is not None else Path(importlib.metadata.distribution('workswarm').locate_file('jiuwenswarm'))
        _verify_component(root,{'files':value['files'],'links':value['links']})
        if not legacy:
            roots=dict(component_roots or {})
            if set(roots)-{'jiuwenswarm_tui'}:raise ValueError('unknown installed component')
            tui=roots.get('jiuwenswarm_tui')
            if tui is None:tui=Path(importlib.metadata.distribution('workswarm-tui').locate_file('jiuwenswarm_tui'))
            _verify_component(tui,value['components']['jiuwenswarm_tui'])
        for dependency in value['dependencies']:
            if importlib.metadata.version(dependency['name'])!=dependency['version']:raise ValueError('installed dependency differs')
        return digest
    except (OSError,ValueError,KeyError,TypeError,UnicodeError,RuntimeError,importlib.metadata.PackageNotFoundError) as exc:
        raise ResearchError('installed_build_invalid','Independent installed build identity is unavailable or does not verify') from exc


def _session(root,uid):
    root=Path(root);path=root/'session.json'
    if os.name!='posix' or root.is_symlink() or path.is_symlink():raise ResearchError('unavailable','Linux private process session is unavailable')
    parent=root.stat();metadata=path.stat()
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid!=uid or stat.S_IMODE(parent.st_mode)!=0o700
        or not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=uid or stat.S_IMODE(metadata.st_mode)!=0o600 or metadata.st_nlink!=1):
        raise ResearchError('unavailable','Private process session custody is invalid')
    value=json.loads(path.read_bytes().decode('utf-8'))
    if not isinstance(value,dict) or set(value)!={'session_id','capability'} or any(not isinstance(v,str) or not v for v in value.values()):
        raise ResearchError('unavailable','Private process session is invalid')
    return value


class NativePorts:
    async def model_settings(self, principal, action, values=None):
        principal.require('settings')
        return await self.status_client.call('model_settings', {
            'account_id': principal.account_id, 'action': action, 'values': values or {}}, timeout_s=30)

    async def freeze_model_selection(self, principal, run_id, *, parent_run_id=None):
        principal.require('submit')
        return await self.status_client.call('freeze_model_selection', {
            'account_id': principal.account_id, 'run_id': run_id, 'parent_run_id': parent_run_id}, timeout_s=30)

    def __init__(self,*,executor=None,connectors=None,ipc_root='/run/ai4r',app_uid=APP_UID,build_manifest=BUILD_MANIFEST,installed_package_root=None,installed_component_roots=None):
        self.root=Path(ipc_root);self.uid=app_uid;self.session=_session(self.root,self.uid)
        if executor is None:
            from .executor_rpc import ExecutorClient,PROTOCOL
            executor=ExecutorClient(PrivateRPCClient('/run/ai4r-executor/executor.sock',protocol=PROTOCOL,
                peer_uid=0,socket_mode=0o660,**self.session))
        self.executor,self.connectors=executor,connectors
        self.model_bridge=ModelBridgeClient(self.root/'model.sock',peer_uid=self.uid,**self.session)
        self.status_client=PrivateRPCClient(self.root/'agent-status.sock',protocol=STATUS_PROTOCOL,peer_uid=self.uid,**self.session)
        self.authorization_server=None;self.composition=None;self.bindings=None;self.operator=None
        self.build_manifest,self.installed_package_root=build_manifest,installed_package_root
        self.installed_component_roots=installed_component_roots
        self.inspection_store=None;self.inspection_library=None;self.inspection_diagnostics=[]
        self.evaluation_provider=None
        self.admission_tests=None
        self.calibration_authority=None
        self.runner=None

    async def bind_inspection(self,store,operator,diagnostics):
        from .library import LibraryService
        from .connectors import AcademicConnectors
        self.inspection_store=store;self.operator=operator
        if self.connectors is None:
            self.connectors=AcademicConnectors(store,approved={'local_documents'},timeout_s=30)
        elif type(self.connectors) is AcademicConnectors and self.connectors.store is not store:
            raise ResearchError('identity_conflict','Installed Search operator belongs to another actual Store')
        self.inspection_library=LibraryService(store)
        self.inspection_diagnostics=copy.deepcopy(diagnostics)

    async def bind_composition(self,composition,bindings,operator):
        self.composition=composition;self.bindings=copy.deepcopy(bindings);self.operator=operator
        self.admission_tests=getattr(composition.library,'self_test_provider',None)
        self.calibration_authority=getattr(composition,'calibration_authority',None)

    def _calibration(self):
        if self.calibration_authority is None:raise ResearchError('ENVIRONMENT_BLOCKED','Protected calibration runtime is unavailable')
        return self.calibration_authority

    def authorize_model_context(self,payload):
        if isinstance(payload,dict) and str(payload.get('execution_id','')).startswith('calibration-execution:'):
            return self._calibration().authorize_model_context(payload)
        return self.runner.authorize_model_context(payload)

    def authorize_model_dispatch(self,payload):
        if isinstance(payload,dict) and str(payload.get('execution_id','')).startswith('calibration-execution:'):
            return self._calibration().authorize_model_dispatch(payload)
        return self.runner.authorize_model_dispatch(payload)

    def authorize_containment(self,payload):
        if isinstance(payload,dict) and str(payload.get('run_id','')).startswith('calibration-run:'):
            return self._calibration().authorize_containment(payload)
        return self.runner.authorize_containment(payload)

    def authorize_executor_preparation(self,payload):
        if self.runner is None or not callable(getattr(self.runner,'authorize_executor_preparation',None)):
            raise ResearchError('ENVIRONMENT_BLOCKED','Installed live prepared owner is unavailable')
        return self.runner.authorize_executor_preparation(payload)

    def publish_scientific_start_receipt(self,payload):
        if type(payload) is not dict or set(payload)!={'kind','record','preparation_ref'}:
            raise ResearchError('invalid_request','Only a finite original scientific start receipt is accepted')
        if self.runner is None or self.composition is None or self.composition.library.store is not self.runner.store:
            raise ResearchError('scientific_receipt_custody','Actual installed Runner/Store composition is unavailable')
        from .scientific_custody import publish_scientific_start_receipt
        return publish_scientific_start_receipt(self.runner,payload['kind'],payload['record'],payload['preparation_ref'])

    def inspect_scientific_attempt(self,payload):
        if self.runner is None:
            raise ResearchError('ENVIRONMENT_BLOCKED','Installed immutable attempt inspection is unavailable')
        from .attempt_inspection import inspect_node_attempt
        return inspect_node_attempt(self.runner.store,payload)

    def inspect_scientific_evaluation(self,payload):
        if self.runner is None:
            raise ResearchError('ENVIRONMENT_BLOCKED','Installed immutable evaluation inspection is unavailable')
        from .evaluation_authority import inspect_evaluation_executor_binding
        return inspect_evaluation_executor_binding(self.runner.store,payload)

    def prepare_calibration_case(self,payload):return self._calibration().prepare_calibration_case(payload)
    def inspect_calibration(self,payload):return self._calibration().inspect_calibration(payload)
    async def cancel_calibration(self,payload):return await self._calibration().cancel_calibration(payload)

    def authorize_admission_self_test(self,payload):
        if not isinstance(payload,dict) or set(payload)!={'job_ref'}:
            raise ResearchError('invalid_request','Admission authorization accepts only the exact issued job Ref')
        validate('Ref',payload['job_ref'])
        if self.admission_tests is None:
            raise ResearchError('ENVIRONMENT_BLOCKED','Protected admission execution profile/provider is unavailable')
        return self.admission_tests.authorize(payload['job_ref'])

    def bind_evaluation(self,provider):
        self.evaluation_provider=provider

    async def bind_runner(self,runner):
        if self.authorization_server is not None:raise ResearchError('identity_conflict','Authorization owner is already bound for this boot')
        self.runner=runner
        register_start=getattr(runner,'_register_native_start_port',None)
        if callable(register_start):register_start(self)
        self.authorization_server=PrivateRPCServer(self.root/'authorization.sock',protocol=AUTH_PROTOCOL,**self.session,
            handlers={'authorize_model_context':self.authorize_model_context,'authorize_model_dispatch':self.authorize_model_dispatch,
                      'authorize_routing_selection':runner.authorize_routing_selection,
                      'authorize_executor_binding':runner.authorize_executor_binding,
                      'authorize_executor_preparation':self.authorize_executor_preparation,
                      'publish_scientific_start_receipt':self.publish_scientific_start_receipt,
                      'inspect_scientific_attempt':self.inspect_scientific_attempt,
                      'inspect_scientific_evaluation':self.inspect_scientific_evaluation,
                      'authorize_containment':self.authorize_containment,
                      'authorize_admission_self_test':self.authorize_admission_self_test,
                      'prepare_calibration_case':self.prepare_calibration_case,'inspect_calibration':self.inspect_calibration,
                      'cancel_calibration':self.cancel_calibration},allowed_uids={self.uid,0},
            operation_uids={'authorize_model_context':{self.uid},'authorize_model_dispatch':{self.uid,0},
                            'authorize_routing_selection':{self.uid},
                            'authorize_executor_binding':{0},'authorize_containment':{self.uid,0},
                            'authorize_executor_preparation':{0},'publish_scientific_start_receipt':{0},
                            'inspect_scientific_attempt':{0},'inspect_scientific_evaluation':{0},
                            'authorize_admission_self_test':{0},'prepare_calibration_case':{self.uid},
                            'inspect_calibration':{self.uid},'cancel_calibration':{self.uid}})
        await self.authorization_server.start()

    async def readiness(self,principal):
        principal.require('readiness')
        if self.operator is None:raise ResearchError('unavailable','Mandatory approved operator configuration is unavailable')
        bindings=self.bindings or {};options=bindings.get('protected_options',{})
        build=bindings.get('build_id');instance=bindings.get('instance_id')
        # Exact installed-file checks include filesystem reads and hashing.
        # Keep that work off the Gateway event loop so config and chat packets
        # remain responsive while readiness is being established.
        installed=await asyncio.to_thread(verify_installed_build,self.build_manifest,
            package_root=self.installed_package_root,component_roots=self.installed_component_roots)
        library_service=self.composition.library if self.composition is not None else self.inspection_library
        if library_service is None:raise ResearchError('unavailable','Protected library observation is unavailable')
        local_development=(options.get('development_builtin_catalog') is True
            and getattr(library_service,'development_mode',False) is True
            and os.environ.get('JIUWENSWARM_M1_LOCAL_RESEARCH')=='1')
        observed_build=local_development and build is None
        observed_instance=local_development and instance is None
        # A reusable local-development configuration predates this image/boot.
        # Bind only absent identities to independently observed protected state;
        # an explicit conflicting or malformed capture must still refuse.
        if observed_build:build=installed
        if observed_instance:instance=self.session['session_id']
        identity_bound=(isinstance(build,str) and bool(build)
            and isinstance(instance,str) and bool(instance))
        if not isinstance(instance,str) or not instance:instance=self.session['session_id']
        inspection=getattr(library_service,'inspection_pins',None)
        library=(inspection or library_service.current_pins)(candidate_pins=options.get('candidate_pins',()))
        if library.get('unavailable_reason'):
            raise ResearchError('unavailable','No canonical selectable library snapshot is available; internal empty eligibility diagnostics cannot form RunPins')
        settings=self.operator.snapshot()['cc'];prerequisites=[]
        prerequisites.append({'name':'build_identity','status':'ready' if build is None or build==installed else 'unavailable',
            'reason':'Explicit local-development build identity is the independently verified installed closure' if observed_build else 'Independent installed build closure verified; no approved bootstrap comparison is available' if build is None else 'Captured build matches the verified installed closure' if build==installed else 'Captured bootstrap build differs from the independently verified installed build'})
        prerequisites.append({'name':'storage','status':'ready','reason':'Protected store and current exact library/check pins were read successfully'})
        prerequisites.append({'name':'auth','status':'ready','reason':'Authenticated local product account grant was checked'})
        store=self.composition.library.store if self.composition is not None and hasattr(self.composition.library,'store') else self.inspection_store
        policy_resolved=False
        if store is not None:
            try:store.read_record(settings['plan_policy_ref'],contract_id='plan-policy');policy_resolved=True
            except ResearchError:pass
        if not policy_resolved:
            raise ResearchError('unavailable','The declared approved plan-policy Ref does not resolve to its exact original bytes; RunPins are unavailable')
        prerequisites.append({'name':'plan_policy','status':'ready' if policy_resolved else 'unavailable',
            'reason':'Declared approved policy Ref resolves to its exact adopted bytes' if policy_resolved else 'Approved operator declares this exact policy Ref; its original bytes are unavailable'})
        if not bindings:prerequisites.append({'name':'bootstrap','status':'unavailable','reason':'Protected captured bootstrap bindings are missing; only authenticated inspection is available'})
        elif not identity_bound:
            prerequisites.append({'name':'bootstrap_identity','status':'unavailable','reason':'Captured bootstrap build or instance binding is unavailable; the verified current build and actual boot identity are reported'})
        elif observed_build or observed_instance:
            prerequisites.append({'name':'bootstrap_identity','status':'ready','reason':'Explicit local development binds absent capture identities to the verified installed build and protected current boot session'})
        if library.get('unavailable_reason'):
            prerequisites.append({'name':'library','status':'unavailable','reason':'No work is eligible while its exact protected library/check binding is unresolved: '+library['unavailable_reason']})
        try:
            selected=await self.status_client.call('model_settings', {
                'account_id':principal.account_id,'action':'get','values':{},
                'include_chatgpt_models':False},timeout_s=30)
            automatic=selected.get('selected_id') in {'auto', 'chatgpt_ai4r'}
            api_selected=selected.get('selected_id') not in {'auto', 'codex', 'chatgpt_ai4r'}
            # Local/API execution must not wait for subscription discovery,
            # authentication or the comparison CLI to become available.
            status=await self.status_client.call('subscription_status',
                {'include_subscription':False} if automatic or api_selected else {},timeout_s=30)
            ready=selected.get('local_ready') is True if automatic else selected.get('api_ready') is True if api_selected else status.get('state')=='ready'
            if selected.get('selected_id') == 'chatgpt_ai4r':
                ready = ready and status.get('state') == 'ready'
            if api_selected or automatic:
                status=dict(status,state='ready' if ready else 'unavailable',enabled=ready)
            prerequisites.append({'name':'model','status':'ready' if ready else 'unavailable',
                'reason':('Local routing, execution and independent verifier services are ready; signed-in ChatGPT may serve difficult tasks' if ready else 'Required local routing, executor or verifier service is unavailable') if automatic
                    else 'Selected API model has a configured private credential; provider authentication is checked at dispatch' if api_selected and ready else 'Managed subscription is ready' if ready else 'Selected model authentication or transport is unavailable'})
        except Exception:
            status={}
            prerequisites.append({'name':'model','status':'unavailable','reason':'AgentServer model status could not be established'})
        from .execution_readiness import assess_execution_scope
        core_available, finite_scope, core_reason = assess_execution_scope(
            self.composition, bindings, self.operator, library_pins=library, principal=principal, model_port=self.model_bridge)
        integrated_scope = finite_scope is not None and finite_scope.get('kind') == 'integrated_submission'
        if finite_scope is None:
            prerequisites.append({'name':'builder','status':'ready' if status.get('builder_qualified') is True else 'unavailable',
                'reason':('Exact admitted Builder; generated jobs run as ordinary non-root processes in the app container'
                    if status.get('execution_mode') == 'm1_app_process' else
                    'Exact admitted tool-free Builder release; generated code executes only in the scientific sandbox'
                    if status.get('builder_mode') in {'tool_free', 'bounded_tests', 'native_agent'} else 'Dedicated Builder runtime, credential separation and confinement were qualified')
                    if status.get('builder_qualified') is True else 'Required Builder release or isolated runtime qualification is unavailable'})
        elif integrated_scope:
            prerequisites.append({'name':'workflow_scope','status':'ready',
                'reason':'Admitted Compiler, Planner and read-only paper workflow are available; scientific plans still require their selected resources and protected execution qualification'})
        else:
            prerequisites.append({'name':'finite_scope','status':'ready',
                'reason':'Only the exact approved finite stages and shared verifier are selected; full workflow readiness is not claimed'})
        from .trajectory import capture_healthy
        healthy=status.get('capture_healthy') is True and capture_healthy() is True
        prerequisites.append({'name':'trajectory','status':'ready' if healthy else 'unavailable',
            'reason':'Both native process raw trajectory journals are healthy' if healthy else 'Required lossless trajectory capture is unavailable or faulted'})
        if self.executor is None:prerequisites.append({'name':'isolation','status':'unavailable','reason':'Protected restricted executor RPC is unavailable'})
        else:
            try:
                state=(self.executor.read_only_prerequisites() if integrated_scope
                    else self.executor.prerequisites())
                if inspect.isawaitable(state):state=await state
                isolated=state is True or isinstance(state,dict) and state.get('ready') is True or isinstance(state,list) and not state
                reason=('Protected executor broker is reachable for the read-only submission scope; scientific effects remain guarded'
                    if integrated_scope else 'Actual restricted executor prerequisites passed')
                prerequisites.append({'name':'isolation','status':'ready' if isolated else 'unavailable','reason':reason if isolated else 'Actual restricted executor prerequisites did not pass'})
            except Exception:prerequisites.append({'name':'isolation','status':'unavailable','reason':'Restricted executor prerequisite report is unavailable'})
        if not core_available:
            diagnostics=self.inspection_diagnostics+([] if self.composition is None else self.composition.diagnostics)
            reasons=list(dict.fromkeys(item.get('detail',item.get('code','Protected binding is unavailable')) for item in diagnostics))
            prerequisites.append({'name':'core_bindings','status':'unavailable','reason':'; '.join(reasons) or core_reason})
        ready=all(p['status']=='ready' for p in prerequisites)
        pins={'app_build':installed,'client_contract_version':'1.0.0','library_snapshot_sha256':library['library_snapshot_sha256'],
              'plan_policy_ref':settings['plan_policy_ref'],'check_bundle_set_sha256':library['check_bundle_set_sha256'],
              'router_enabled':settings['router']['enabled'],'router_version':bindings.get('router_version') if settings['router']['enabled'] else None}
        report={'schema_version':'1.0.0','id':'readiness:'+__import__('uuid').uuid4().hex,'client_contract_version':'1.0.0',
                'instance_id':instance,'build_id':installed,'operations':(['submit'] if ready else [])+['status','reconcile','export','cancel','readiness'],
                'prerequisites':prerequisites,'ready':ready,'evaluation_profile':finite_scope['profile_id'] if finite_scope is not None else options.get('profile_id'),
                'fault_injection':False,'pins':pins}
        provider=self.evaluation_provider
        if provider is not None:
            report['evaluation_profile']=provider.profile['profile_id']
            # Availability includes actual canonical/check qualification; the
            # native readiness probes additionally qualify current effects.
            if ready:
                report['operations']+=['node_replay' if p=='E2' else 'single_cc'
                    for p in provider.available_entry_points]
            elif await self._independent_single_cc_ready(prerequisites, identity_bound=identity_bound):
                report['operations'].append('single_cc')
        validate('client-readiness',report);return report

    async def _independent_single_cc_ready(self, prerequisites, *, identity_bound):
        """Observe the actual tool-free E3 owner independently of E1 science.

        Ordinary submit readiness is unchanged. This grants no assignment: the
        provider still validates the separate credential, frozen slot, exact
        subject and current authority at the existing protected E3 boundary.
        """
        from .admitted_measurement import AdmittedResourceContext
        from .evaluation_provider import EvaluationProvider, InstalledEvaluationResources
        try:
            provider = self.evaluation_provider
            if type(provider) is not EvaluationProvider or not identity_bound or not self.bindings:
                return False
            required = {'build_identity', 'storage', 'auth', 'plan_policy', 'model', 'trajectory'}
            shared = [p for p in prerequisites if p['name'] in required]
            if {p['name'] for p in shared} != required or any(p['status'] != 'ready' for p in shared):
                return False
            # An explicit unavailable bootstrap condition cannot be masked by
            # a library owner captured under some earlier composition.
            if any(p['status'] != 'ready' for p in prerequisites if p['name'].startswith('bootstrap')):
                return False
            installed = provider.resources
            if type(installed) is not InstalledEvaluationResources:
                return False
            actual = installed.admitted.resources
            if (type(actual) is not AdmittedResourceContext or actual.composition is not self.composition
                    or actual.operator is not self.operator or provider.store is not self.composition.runner.store
                    or self.model_bridge is None or self.composition.runner.model is not self.model_bridge
                    or actual.executor is not self.executor or self.composition.runner.executor is not self.executor
                    or self.executor is None):
                return False
            options = self.bindings['protected_options']
            if (any(actual.exact_binding_refs[key] != self.bindings[key] for key in
                    ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref', 'workspace_id'))
                    or options.get('evaluation_runtime_ref') != installed.authority.runtime_ref
                    or options.get('evaluation_assets_ref') != provider.assets_ref
                    or options.get('library_snapshot_ref') != installed.snapshot_ref
                    or 'E3' not in provider.available_entry_points):
                return False
            cases = [case for case in provider.assets['cases'] if case['entry_point'] == 'E3']
            if not cases:
                return False
            for case in cases:
                source, checks, _ = installed._subject(case)
                contract = installed.admitted._validate(source, checks)[0]
                declaration = provider.store.read_record(contract['bindings'][0]['declaration_ref'],
                                                         contract_id='capsule-declaration')
                authority = contract['bindings'][0]['effective_authority']
                if (declaration['needs']['network']['mode'] != 'none'
                        or declaration['budget']['per_call']['tool_calls'] != 0
                        or authority['network'] != 'none' or authority['network_allowlist']
                        or authority['tools'] or authority['write_roots']):
                    return False
                from .attempt_resources import attempt_resource_disposition
                disposition = attempt_resource_disposition(provider.store, contract['node_contract_ref'])
                if disposition.requires_broker:
                    return False
            probe = self.executor.read_only_prerequisites()
            if inspect.isawaitable(probe):
                probe = await probe
            return (probe is True or isinstance(probe, dict) and probe.get('ready') is True
                    or isinstance(probe, list) and not probe)
        except (ResearchError, AttributeError, KeyError, TypeError, ValueError, OSError):
            return False

    async def close(self):
        if self.authorization_server is not None:await self.authorization_server.close()


async def create_gateway_ports(*,executor=None,connectors=None):
    return NativePorts(executor=executor,connectors=connectors)


def capture_native_record(store, kind, record, *, context):
    """Persist once under the exact durable call owner, including late packets.

    This is a capture sink, not a dispatch authorization. Only the bridge's
    already protected context reaches it; original packet fields stay intact.
    """
    fields = ('execution_id', 'invocation_id', 'call_id', 'call_claim_ref', 'contract_ref')
    if not isinstance(context, dict) or any(key not in context for key in fields):
        raise ResearchError('audit_unavailable', 'Native capture has no protected call context')
    protected = {key: copy.deepcopy(context[key]) for key in fields}
    claim_kind = store.record_kind(protected['call_claim_ref'])
    if claim_kind == 'evaluation-call-claim':
        from .evaluation_authority import capture_evaluation_native
        return capture_evaluation_native(store, kind, record, context=protected)
    if claim_kind not in {'model-call-claim', 'calibration-call-claim'}:
        raise ResearchError('audit_unavailable', 'Native capture has no recognized call owner')
    return store.append_record(kind, record)


def capture_governed_trace_record(store, kind, record):
    """Attribute raw native packets through their original captured call start."""
    if (kind not in {'native-governed-trace', 'native-governed-trace-event', 'host-codex-native-original'}
            or not isinstance(record, dict) or not isinstance(record.get('scope'), dict)):
        raise ResearchError('audit_unavailable', 'Malformed native governed trace capture')
    if kind == 'host-codex-native-original':
        # The host adapter captures its validated original before individual
        # frames. This is call-owned native evidence, never caller metadata.
        if (set(record) != {'schema', 'scope', 'policy_sha256', 'raw_ref'}
                or record['schema'] != 'ai4r-host-codex-original:1'
                or not isinstance(record['policy_sha256'], str)
                or re.fullmatch('[0-9a-f]{64}', record['policy_sha256']) is None):
            raise ResearchError('audit_unavailable', 'Malformed host native original capture')
        validate('Ref', record['raw_ref'])
        raw = store.read_blob(record['raw_ref'])
        if len(raw) > 1024 * 1024:
            raise ResearchError('audit_unavailable', 'Host native original exceeds evidence bound')
        from .local_model_codex import unpack_bundle
        from .local_models import CODEX_BUNDLE_FIELDS
        from ..research_rsi.host_codex_backend import MODEL, EFFORT, NATIVE_SHA256
        try:
            original = unpack_bundle(json.loads(raw))
            early_failure = (isinstance(original, dict) and original.get('outcome') == 'failed'
                and original.get('wire_frames') == []
                and all(original.get(key) is None for key in ('thread_start', 'turn_start', 'turn_completed'))
                and original.get('error_code') not in (None, 'CONTAINMENT_UNCERTAIN'))
            valid = (isinstance(original, dict) and set(original) == CODEX_BUNDLE_FIELDS
                     and original.get('schema') == 'ai4r-host-codex-response:1'
                     and original.get('requested_model') == MODEL
                     and original.get('reasoning_effort') == EFFORT
                     and (original.get('binary_sha256') == NATIVE_SHA256
                          or early_failure and original.get('binary_sha256') is None))
        except (ValueError, TypeError, KeyError):
            valid = False
        if not valid:
            raise ResearchError('audit_unavailable', 'Host native original policy differs')
    scope = record['scope']; start_ref = scope.get('model_call_start_ref')
    validate('Ref', start_ref)
    if store.record_kind(start_ref) != 'model-call-start':
        raise ResearchError('audit_unavailable', 'Native trace has no original call start')
    start = store.read_record(start_ref)
    if any(start.get(key) != scope.get(key) for key in
            ('run_id', 'execution_id', 'invocation_id', 'call_id', 'contract_ref')):
        raise ResearchError('audit_unavailable', 'Native trace scope differs from original call start')
    context = {key: start[key] for key in
        ('execution_id', 'invocation_id', 'call_id', 'call_claim_ref', 'contract_ref')}
    return capture_native_record(store, kind, record, context=context)


@dataclass
class AgentPorts:
    model_server: ModelBridgeServer
    status_server: PrivateRPCServer
    store: SQLiteRunStore
    routing_authority: object = None

    async def close(self):
        await self.model_server.close();await self.status_server.close();self.store.close()


async def start_agent_ports():
    """Called by the existing AgentServer after its owned service is available."""
    from jiuwenswarm.server.runtime.codex_subscription.service import get_service
    from .trajectory import capture_healthy
    root=Path('/run/ai4r');session=_session(root,APP_UID)
    store=SQLiteRunStore(os.environ.get('JIUWENSWARM_M1_STATE','/var/lib/ai4r'),recover=False,input_root='/workspace/input')
    operator=OperatorConfiguration.load(os.environ.get('JIUWENSWARM_M1_CONFIG','/etc/ai4r/config.yaml'),resolve_profile=lambda ref:store.read_record(ref))
    authorization=PrivateRPCClient(root/'authorization.sock',protocol=AUTH_PROTOCOL,peer_uid=APP_UID,**session)
    async def authorize(payload):return await authorization.call('authorize_model_context',dict(payload),timeout_s=30)
    async def revalidate(payload):return await authorization.call('authorize_model_dispatch',dict(payload),timeout_s=30)
    async def authorize_routing_selection(payload):return await authorization.call('authorize_routing_selection',dict(payload),timeout_s=30)
    async def authorize_containment(payload):return await authorization.call('authorize_containment',dict(payload),timeout_s=30)
    from .executor_rpc import ExecutorClient,PROTOCOL
    executor=ExecutorClient(PrivateRPCClient('/run/ai4r-executor/executor.sock',protocol=PROTOCOL,
        peer_uid=0,socket_mode=0o660,**session))
    class BrokerBuilderPort:
        async def invoke(self,protected,prompt,*,timeout_s):
            return await executor.invoke_builder(protected,prompt,timeout_s=timeout_s)
    subscription=get_service()
    subscription.set_account_observer(store.append_record)
    subscription.set_governed_trace_writer(lambda kind,record:capture_governed_trace_record(store,kind,record),store.put_blob)
    from .routing_authority import create_routing_runtime,UnavailableRoutingPort
    router,providers,routing_authority=create_routing_runtime(store=store,operator=operator,environ=os.environ)
    from .model_settings import ModelSettingsOwner
    from .local_models import LocalModelCatalog
    manual_models=ModelSettingsOwner(store,local_catalog=LocalModelCatalog(os.environ.get('AI4R_LOCAL_MODEL_CATALOG')))
    from .automatic_routing import AutomaticRouting
    automatic_routing=AutomaticRouting(manual_models, subscription)
    if type(router) is UnavailableRoutingPort:
        print(json.dumps({'event':'optional-routing-unavailable','reason':router.installation_failure.value}),flush=True)
    bridge=GovernedBridge(persist=store.append_record,authorize=authorize,subscription_service=subscription,
                         router_port=router,providers=providers,fixed_route_id=operator.codex_route_id,validate_record=validate,health_check=capture_healthy,
                          revalidate=revalidate,builder_launcher=BrokerBuilderPort(),read_evidence=store.read_blob,
                          capture_native=lambda kind,record,*,context:capture_native_record(store,kind,record,context=context),
                          manual_models=manual_models, automatic_routing=automatic_routing,
                          authorize_routing_selection=authorize_routing_selection)
    model_server=ModelBridgeServer(bridge,root/'model.sock',allowed_peer_uids={APP_UID},authorize_containment=authorize_containment,**session)
    from .unified_planning import is_integrated_policy
    try:integrated_policy=is_integrated_policy(store.read_record(operator.snapshot()['cc']['plan_policy_ref'],contract_id='plan-policy'))
    except ResearchError:integrated_policy=False
    async def subscription_status(payload):
        if not isinstance(payload,dict) or (payload and
                (set(payload)!={'include_subscription'} or payload['include_subscription'] is not False)):
            raise ResearchError('invalid_request','Status accepts no supplied identity or credential')
        status=await subscription.status() if not payload else {}
        # Managed-model availability must remain observable without scientific
        # datasets or Builder qualification in the integrated read-only scope.
        try:execution_status={} if integrated_policy else await executor.prerequisites()
        except Exception:execution_status={}
        return {'state':status.get('state'),'enabled':status.get('enabled') is True,
                'builder_qualified':isinstance(execution_status,dict) and execution_status.get('builder_qualified') is True,
                'builder_mode':execution_status.get('builder_mode') if isinstance(execution_status,dict) else None,
                'execution_mode':execution_status.get('execution_mode') if isinstance(execution_status,dict) else None,
                'capture_healthy':capture_healthy() is True}
    async def model_settings(payload):
        payload=dict(payload)
        include_catalog=payload.pop('include_chatgpt_models',True)
        if type(include_catalog) is not bool:
            raise ResearchError('invalid_request','Invalid model catalog request')
        catalog=[]
        if include_catalog:
            try:
                async with asyncio.timeout(5):
                    catalog=(await subscription.models())['models']
            except Exception:
                pass  # The comparison catalog never blocks local model settings.
        result=manual_models.settings(payload,chatgpt_models={m['id'] for m in catalog})
        return dict(result,chatgpt_models=catalog,**(await automatic_routing.status()))
    from .subscription_baseline import SubscriptionBaseline
    baseline = SubscriptionBaseline(store, subscription)
    from .hybrid_benchmark import HybridBenchmark
    hybrid_benchmark = HybridBenchmark(store.root/'hybrid-benchmark', subscription)
    status_server=PrivateRPCServer(root/'agent-status.sock',protocol=STATUS_PROTOCOL,**session,
        handlers={'subscription_status':subscription_status,'model_settings':model_settings,
                  'freeze_model_selection':automatic_routing.freeze,
                  'benchmark_chatgpt_baseline':baseline.invoke,
                  'benchmark_hybrid_route':hybrid_benchmark.invoke},allowed_uids={APP_UID})
    try:
        await model_server.start();await status_server.start()
    except BaseException:
        await model_server.close();await status_server.close();store.close();raise
    return AgentPorts(model_server,status_server,store,routing_authority)
