"""Core decision and deployment authority, without selector implementation.

Source: reference/model-routing-contract.md (exact joins, live dispatch limits),
side-systems/model-catalog.md (qualification/current access), and M1-IF-001/008.
The private implementation records below bind existing obligations to captured
evidence; they add no operator-config or public product-contract fields.
"""
from __future__ import annotations
import copy
from datetime import datetime,timezone
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import threading
import uuid

from .contracts import ResearchError,validate
from .state import json_bytes
from .router_client import CodexRouter,RouterPort,PlatformIntegrityError,decode_frame
from .providers import NativeProviders


def exact_ref(pin):
    validate('Ref',pin)
    return pin


def utc(value):
    parsed=datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    if parsed.strftime('%Y-%m-%dT%H:%M:%SZ')!=value:raise ValueError('Invalid UTC timestamp')
    return parsed


def protected_json(path,max_bytes=4*1024*1024):
    path=Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Unsafe protected record path')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        meta=os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink!=1 or meta.st_mode&0o022 or meta.st_size>max_bytes:raise ValueError('Unsafe protected record custody')
        with os.fdopen(fd,'rb',closefd=False) as stream:return decode_frame(stream.read(max_bytes+1))
    finally:os.close(fd)


def _shared_export_directory(path,group=None):
    """Owner-only writes and shared-group traversal, independent of umask."""
    path=Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('Unsafe routing export directory')
    path.mkdir(mode=0o2750,parents=True,exist_ok=True)
    if os.name=='posix':
        fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            meta=os.fstat(fd)
            if meta.st_uid!=os.geteuid() or meta.st_mode&0o022 or group is not None and meta.st_gid!=group:
                raise ValueError('Unsafe routing export directory custody')
            os.fchmod(fd,0o2750)
            return meta.st_gid
        finally:os.close(fd)
    return None


class PublicRoutingExport:
    """Exact allowlisted public closure; no store tree or credential copy."""
    def __init__(self,store,root):
        self.store,self.root=store,Path(root);self.lock=threading.RLock()
        if not self.root.is_absolute() or any(p.is_symlink() for p in (self.root,*self.root.parents)):raise ValueError('Unsafe routing export root')
        self.group=_shared_export_directory(self.root)
    def publish(self,refs):
        with self.lock:
            path=self.root/'ref-index.json'
            previous=protected_json(path) if path.exists() else {'schema':'ai4r-router-public-index:1','refs':{}}
            if set(previous)!={'schema','refs'} or previous['schema']!='ai4r-router-public-index:1':raise ValueError('Invalid public routing index')
            index=copy.deepcopy(previous['refs'])
            for pin in refs:
                exact_ref(pin);raw=self.store.read_blob(pin)
                if len(raw)>4*1024*1024 or hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('Routing export byte mismatch')
                relative='sha256/'+pin['sha256'];target=self.root/relative
                _shared_export_directory(target.parent,self.group)
                try:
                    with target.open('xb') as stream:
                        if os.name=='posix':os.fchmod(stream.fileno(),0o640)
                        stream.write(raw);stream.flush();os.fsync(stream.fileno())
                except FileExistsError:
                    meta=target.lstat()
                    if (target.is_symlink() or not stat.S_ISREG(meta.st_mode) or meta.st_nlink!=1
                        or os.name=='posix' and (meta.st_uid!=os.geteuid() or meta.st_gid!=self.group or meta.st_mode&0o022)
                        or target.read_bytes()!=raw):raise PlatformIntegrityError('ROUTING_EXPORT_COLLISION')
                entry={'sha256':pin['sha256'],'path':relative}
                if pin['id'] in index and index[pin['id']]!=entry:raise PlatformIntegrityError('ROUTING_REF_IDENTITY_CONFLICT')
                index[pin['id']]=entry
            temporary=self.root/('.index-'+uuid.uuid4().hex)
            try:
                with temporary.open('xb') as stream:
                    if os.name=='posix':os.fchmod(stream.fileno(),0o640)
                    stream.write(json_bytes({'schema':'ai4r-router-public-index:1','refs':index}));stream.flush();os.fsync(stream.fileno())
                os.replace(temporary,path)
                if hasattr(os,'O_DIRECTORY'):
                    fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
                    try:os.fsync(fd)
                    finally:os.close(fd)
            finally:temporary.unlink(missing_ok=True)


def _validate_selected_capsule(store,context):
    """Existing immutable selected-context checks, without API installation."""
    def record(pin):return json.loads(store.read_blob(exact_ref(pin)))
    request=context['route_request'];validate('route-request',request)
    selected=request['selected_capsule'];bound=selected['bound_context']
    # A missing or swapped selected-Capsule export is a platform integrity
    # failure. Optional routing metadata remains a pre-call router failure.
    try:
        validate('selected-capsule-input',selected)
        declaration=record(selected['declaration_ref']);validate('capsule-declaration',declaration)
        if declaration!=selected['declaration'] or bound['eligibility']!='eligible':raise ValueError('Selected declaration/eligibility changed')
        parent=record(selected['node_contract_ref']);validate('node-execution-contract',parent)
        child=record(selected['subnode_contract_ref']);validate('subnode-execution-contract',child)
        if child['node_contract_ref']!=selected['node_contract_ref'] or len(child['bindings'])!=1:raise ValueError('Selected node/subnode mismatch')
        binding=child['bindings'][0]
        for key in ('run_id','node_id','subnode_id','attempt_id'):
            if child[key]!=bound['runtime'][key] or child[key]!=context[key]:raise ValueError('Selected runtime identity changed')
        if bound['runtime']['invocation_id']!=context['invocation_id']:raise ValueError('Selected invocation changed')
        for key,expected in [('binding_id',binding['id']),('role',binding['role']),('objective',child['objective']),('inputs',child['inputs']),('outputs',child['outputs']),
            ('implementation_refs',binding['implementation_refs']),('dependency_refs',binding['dependency_refs']),('admission_ref',binding['admission_ref']),
            ('effective_authority',binding['effective_authority']),('invocation_limits',binding['limits']),('subnode_limits',child['subnode_limits']),
            ('node_limits',parent['node_limits']),('policy_ref',child['policy_ref']),('configuration_ref',child['configuration_ref'])]:
            if bound[key]!=expected:raise ValueError('Selected protected projection changed')
        if binding['declaration_ref']!=selected['declaration_ref']:raise ValueError('Selected declaration binding changed')
        overlays=[{'id':row['ref'],'sha256':row['sha256']} for row in declaration['identity'].get('overlays',[])]
        if overlays!=bound['overlay_refs']:raise ValueError('Selected overlays changed')
        if request['input_refs']!=child['input_refs'] or request['policy_ref']!=bound['policy_ref']:raise ValueError('Selected request inventory/policy changed')
        for pin in [selected['declaration_ref'],selected['node_contract_ref'],selected['subnode_contract_ref'],bound['admission_ref'],*bound['implementation_refs'],*bound['overlay_refs'],*bound['dependency_refs'],*request['input_refs']]:store.read_blob(pin)
        if not {row['sha256'] for row in declaration['identity']['body']}<={pin['sha256'] for pin in bound['implementation_refs']}:raise ValueError('Selected implementation closure incomplete')
    except Exception as exc:
        if isinstance(exc,PlatformIntegrityError):raise
        raise PlatformIntegrityError('SELECTED_CAPSULE_EXPORT_INVALID') from None
    return request,selected,bound


class RoutingAuthority:
    def __init__(self,store,binding,*,clock=lambda:datetime.now(timezone.utc)):
        fields={'schema','router_socket','adapter_revision','catalog_ref','profile_refs','development_profiles_ref','deployment_grants','status_path','export_root','audit_root'}
        if not isinstance(binding,dict) or set(binding)!=fields or binding['schema']!='ai4r-routing-authority:1':raise ValueError('Invalid protected routing binding')
        self.store,self.binding,self.clock=store,copy.deepcopy(binding),clock
        self.export=PublicRoutingExport(store,binding['export_root']);self.audit=Path(binding['audit_root']).resolve()
        self.grants={json_bytes(row['deployment_ref']):copy.deepcopy(row) for row in binding['deployment_grants']}
        if len(self.grants)!=len(binding['deployment_grants']):raise ValueError('Duplicate deployment grant')
        for row in self.grants.values():
            if set(row)!={'deployment_ref','endpoint_ref','qualification_ref'}:raise ValueError('Unknown deployment grant field')
            for pin in row.values():exact_ref(pin)
    def record(self,pin):return json.loads(self.store.read_blob(exact_ref(pin)))
    def audit_record(self,pin):
        exact_ref(pin);relative=Path(pin['id'])
        if relative.is_absolute() or '..' in relative.parts or len(relative.parts)!=2 or relative.parts[0]!='artifacts' or relative.name!=pin['sha256']+'.json':raise ValueError('Unknown router audit reference')
        target=self.audit/relative
        if any(p.is_symlink() for p in (target,*target.parents)):raise ValueError('Router audit symlink')
        raw=target.read_bytes()
        if len(raw)>4*1024*1024 or hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('Router audit bytes changed')
        return decode_frame(raw)
    def current(self,pin):
        value=protected_json(self.binding['status_path'])
        if set(value)!={'schema','entries'} or value['schema']!='ai4r-deployment-status:1':raise ValueError('Current deployment status is unavailable')
        rows=[row for row in value['entries'] if row.get('deployment_ref')==pin]
        if len(rows)!=1 or set(rows[0])!={'deployment_ref','enabled','revoked'} or rows[0]['enabled'] is not True or rows[0]['revoked'] is not False:raise ValueError('Deployment is disabled, revoked or unavailable')
    def resolve_endpoint(self,pin):
        if not any(row['endpoint_ref']==pin for row in self.grants.values()):raise ValueError('Endpoint is outside approved grants')
        value=self.record(pin)
        if not isinstance(value,dict) or value.get('enabled') is not True:raise ValueError('Endpoint is unavailable')
        return value
    def resolve_deployment(self,pin,function,context=None):
        self.current(pin);grant=self.grants.get(json_bytes(pin))
        if grant is None:raise ValueError('Deployment has no approved qualification grant')
        deployment=self.record(pin);qualification=self.record(grant['qualification_ref'])
        fields={'schema','deployment_ref','endpoint_ref','adapter_revision','call_functions','task_categories','declaration_sha256s','profile_refs','checks','model_call_ref','observed_runtime','qualified_at','expires_at'}
        if not isinstance(qualification,dict) or set(qualification)!=fields or qualification['schema']!='ai4r-api-qualification:1':raise ValueError('Exact endpoint qualification is unavailable')
        if qualification['deployment_ref']!=pin or qualification['endpoint_ref']!=grant['endpoint_ref'] or deployment.get('endpoint_ref')!=grant['endpoint_ref'] or deployment.get('adapter_id')!='native-openai-chat-v1' or qualification['adapter_revision']!=deployment.get('revision') or qualification['observed_runtime'] is not True:raise ValueError('Endpoint qualification is stale or unmeasured')
        now=self.clock()
        if not utc(qualification['qualified_at'])<=now<utc(qualification['expires_at']):raise ValueError('Endpoint qualification expired')
        if function not in qualification['call_functions'] or function not in {'worker','planner'}:raise ValueError('Endpoint call scope is not qualified')
        checks=qualification['checks'];required={'callability','identity','adapter_contract','permissions','host','license','usage_capture','capabilities'}
        if not isinstance(checks,list) or len(checks)!=len(required) or {row.get('check_id') for row in checks}!=required:raise ValueError('Endpoint qualification obligations are incomplete')
        for row in checks:
            if set(row)!={'check_id','status','evidence_refs'} or row['status']!='pass' or not row['evidence_refs']:raise ValueError('Endpoint qualification did not pass')
            for evidence in row['evidence_refs']:self.store.read_blob(exact_ref(evidence))
        call=self.record(qualification['model_call_ref']);validate('model-call',call)
        if call['deployment_ref']!=pin or call['outcome']!='completed' or call['observed_runtime'] is not True or not call['identity']['effective'] or not call['evidence_refs']:raise ValueError('Endpoint qualification lacks actual inference evidence')
        for evidence in call['evidence_refs']:self.store.read_blob(evidence)
        if context is not None:
            request=context['route_request'];selected=request['selected_capsule']
            if request['task_category'] not in qualification['task_categories'] or selected['declaration_ref']['sha256'] not in qualification['declaration_sha256s'] or request['model_selection_profile_ref'] not in qualification['profile_refs']:raise ValueError('Endpoint qualification does not cover this invocation')
        self.resolve_endpoint(grant['endpoint_ref'])
        return copy.deepcopy(deployment)
    def prepare_request(self,context):
        request,selected,bound=_validate_selected_capsule(self.store,context)
        refs=[selected['declaration_ref'],selected['node_contract_ref'],selected['subnode_contract_ref'],bound['admission_ref'],bound['policy_ref'],bound['configuration_ref'],
            bound['budget_snapshot']['snapshot_ref'],request['model_selection_profile_ref'],self.binding['catalog_ref'],self.binding['development_profiles_ref']]
        for name in ('implementation_refs','overlay_refs','dependency_refs'):refs.extend(bound[name])
        refs.extend(request['input_refs'])
        profile=self.record(request['model_selection_profile_ref']);refs.append(profile['policy_ref'])
        for grant in self.grants.values():refs.extend((grant['deployment_ref'],grant['endpoint_ref']))
        self.export.publish(refs)
    def validate_decision(self,context,decision):
        validate('model-route',decision);request=context['route_request'];selected=request['selected_capsule'];bound=selected['bound_context']
        profile=self.record(request['model_selection_profile_ref']);validate('model-selection-profile',profile)
        if request['model_selection_profile_ref'] not in self.binding['profile_refs'] or profile['policy_mode']!='development_profile':raise ValueError('Profile is not authorized for API routing')
        if self.audit_record(decision['request_ref'])!=request or self.audit_record(decision['selected_capsule_ref'])!=selected:raise ValueError('Decision request/selected Capsule changed')
        expected={'runtime':bound['runtime'],'execution_id':request['execution_id'],'binding_id':bound['binding_id'],'role':bound['role'],
            'model_selection_profile_ref':request['model_selection_profile_ref'],'registry_snapshot_ref':self.binding['catalog_ref'],'adapter_revision':self.binding['adapter_revision']}
        if any(decision[k]!=v for k,v in expected.items()):raise ValueError('Decision differs from protected invocation')
        eligible=decision['eligible_endpoints'];model=decision['selected_endpoint']
        if len(eligible)!=len(set(eligible)) or model not in eligible or not set(eligible)<=set(profile['approved_model_ids']) or model not in context['approved_model_ids']:raise ValueError('Decision selected an unapproved model')
        if decision['selection_method'] not in {'single_candidate','development_profile_policy','compatible_baseline','router_alternate_model'} or decision['alternate_used']!=(decision['selection_method']=='router_alternate_model') or decision['alternate_used'] and model!=profile['alternate_model_id']:raise ValueError('Decision method/alternate is unauthorized')
        ready,end=utc(decision['ready_at']),utc(decision['valid_until']);now=self.clock()
        if not ready<=now<end or not 0<(end-ready).total_seconds()<=30:raise ValueError('Decision expired or validity widened')
        snapshot=bound['budget_snapshot'];reserves=[snapshot[k] for k in ('verifier_reserved','routing_reserved','other_work_reserved')]
        limits=decision['limits'];caps=[bound['invocation_limits'],bound['subnode_limits'],bound['node_limits'],snapshot['subnode_remaining']]
        for dimension in ('time_s','model_calls','memory_mb'):
            ceiling=min(cap[dimension] for cap in caps)
            ceiling=min(ceiling,snapshot['node_remaining'][dimension]-(sum(row[dimension] for row in reserves) if dimension!='memory_mb' else 0))
            if dimension=='time_s':ceiling=min(ceiling,selected['declaration']['budget']['per_call']['wall_s'])
            if type(limits[dimension]) not in (int,float) or not math.isfinite(limits[dimension]) or not 0<limits[dimension]<=ceiling:raise ValueError('Decision borrowed protected budget')
        derived=self.audit_record(decision['routing_context_ref'])
        checks={'selected_capsule_ref':decision['selected_capsule_ref'],'model_selection_profile_ref':request['model_selection_profile_ref'],
            'adapter_revision':decision['adapter_revision'],'capsule_budget':selected['declaration']['budget'],'effective_limits':limits,'bound_context':bound}
        if any(derived.get(k)!=v for k,v in checks.items()):raise ValueError('Derived routing context lost protected facts')
        deployment=self.resolve_deployment(decision['deployment_ref'],context['call_function'],context)
        if deployment['model_id']!=model or decision['identity']['requested']!=model or decision['identity']['effective'] is not None:raise ValueError('Decision deployment/model identity differs')
        self.current(decision['deployment_ref'])
        return True


class RoutingInstallationFailure(str,Enum):
    BINDING_MISSING='binding_missing'
    CONFIGURATION_INVALID='configuration_invalid'
    RESOURCES_UNAVAILABLE='resources_unavailable'


class UnavailableRoutingPort(RouterPort):
    """Typed local unavailability, with no selector/provider capability.

    The existing selected-Capsule checks remain call-time integrity checks.
    This object creates no socket request, API decision, credential environment
    or provider. The bridge still owns audited fixed Codex dispatch.
    """
    def __init__(self,*,store,route_id,reason):
        if type(reason) is not RoutingInstallationFailure:
            raise ValueError('Unknown optional routing installation reason')
        super().__init__('/run/ai4r-router/router.sock',peer_uid=10011,route_id=route_id)
        self._store=store;self.installation_failure=reason

    async def select(self,context):
        # Preserve the exact existing fixed/verifier/export-error policy, with
        # no attempt to consult the absent optional subsystem.
        if context.get('call_function')=='verifier':
            return await super().select(context)
        settings=self.validate_settings(context)
        if (not settings['enabled'] or context.get('model_selection_profile',{}).get('policy_mode')=='fixed_baseline'
                or settings.get('profile_ref') is None or context.get('routing_export_error') is not None):
            return await super().select(context)
        _validate_selected_capsule(self._store,context)
        return self.fallback('no_route','PROFILE_UNAVAILABLE')


def create_routing_runtime(*,store,operator,environ,credential_environment=None):
    """Install optional API routing without making it a Codex startup gate.

    Mandatory operator/session/Store composition and protected call-time
    validation are deliberately outside this optional installation boundary.
    """
    route_id=operator.codex_route_id
    settings=RouterPort.validate_settings({'router':operator.snapshot()['cc']['router']})
    if not settings['enabled']:
        return CodexRouter(route_id),None,None
    path=environ.get('JIUWENSWARM_M1_ROUTING_BINDINGS')
    if not path:
        return UnavailableRoutingPort(store=store,route_id=route_id,
            reason=RoutingInstallationFailure.BINDING_MISSING),None,None
    try:
        locator=protected_json(path)
        if type(locator) is not dict or set(locator)!={'binding_ref'}:
            raise ValueError('Routing locator must name one exact captured binding')
        binding=store.read_record(locator['binding_ref'])
        expected={'router_socket':'/run/ai4r-router/router.sock','export_root':'/run/ai4r-routing/public','audit_root':'/var/lib/ai4r-router'}
        if type(binding) is not dict or any(binding.get(key)!=value for key,value in expected.items()):
            raise ValueError('Routing authority differs from the fixed native process paths')
        authority=RoutingAuthority(store,binding)
        port=RouterPort(binding['router_socket'],peer_uid=10011,route_id=route_id,
            validate_decision=authority.validate_decision,persist_decision=store.append_record,prepare_request=authority.prepare_request)
        if credential_environment is None:
            from .native_profile import M1_PROFILE,startup_credential_environment
            credential_environment=startup_credential_environment() if M1_PROFILE else environ
        providers=NativeProviders(resolve_deployment=authority.resolve_deployment,resolve_endpoint=authority.resolve_endpoint,
            credential_environment=credential_environment)
        return port,providers,authority
    except OSError:
        reason=RoutingInstallationFailure.RESOURCES_UNAVAILABLE
    except (ResearchError,ValueError,TypeError,KeyError,RecursionError):
        reason=RoutingInstallationFailure.CONFIGURATION_INVALID
    return UnavailableRoutingPort(store=store,route_id=route_id,reason=reason),None,None
