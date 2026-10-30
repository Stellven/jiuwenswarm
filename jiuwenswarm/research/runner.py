"""Exactly pinned carrier dispatch with protected call claims and checking."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
import logging
import time
import uuid
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Mapping

from .checks import CheckContext
from .contracts import Ref, ResearchError, validate
from .gate import ADVANCING
from .evidence_review import (EvidenceAwareGate, EvidenceAwareSemanticVerifier,
                              build_review_evidence)
from .checks.verifier import verifier_predicates,contract_is
from .state import json_bytes, utc_now
from .router_client import PlatformIntegrityError
from .automatic_routing import POLICY as AUTOMATIC_ROUTING_POLICY, routing_policy, node_routing_allowance
from .checks.records import body_files_sha256,complete_observation
from .checks.assets import CheckAssetAdmissions


async def _capture_off_loop(callback, *args, **kwargs):
    """Finish finite durable custody without blocking or abandoning its writes."""
    pending = asyncio.create_task(asyncio.to_thread(callback, *args, **kwargs))
    cancellation = None
    while not pending.done():
        try:
            await asyncio.shield(pending)
        except asyncio.CancelledError as error:
            cancellation = cancellation or error
        except BaseException:
            break
    if cancellation is not None:
        # Drain even repeated cancellation; the original cancellation wins over
        # a later custody failure, and no worker continues after this returns.
        try:
            pending.result()
        except BaseException:
            pass
        raise cancellation
    return pending.result()


@dataclass(frozen=True)
class ProducedArtifact:
    data: bytes | dict | str
    contract_id: str | None = None
    media_type: str = 'application/json'
    name: str | None = None
    ref: Ref | None = None


@dataclass(frozen=True)
class RunResult:
    accepted: bool
    output_refs: Mapping[str,Ref]
    decision_refs: tuple[Ref,...]
    deterministic_ref: Ref
    observation_ref: Ref
    assessment_refs: tuple[Ref,...]
    outcome: str
    protected_stop_ref: Ref | None = None


class Registry:
    def __init__(self):self._handlers={}

    def register(self,cc_id: str,version: str,handler,*,declaration_sha256: str,implementation_refs=()):
        key=(cc_id,version,declaration_sha256)
        if key in self._handlers:raise ResearchError('carrier_duplicate','Exact carrier already registered')
        if not callable(handler) and not callable(getattr(handler,'execute',None)):
            raise ResearchError('carrier_invalid','Carrier must be an explicitly installed callable')
        self._handlers[key]=(handler,tuple(implementation_refs))

    def resolve(self,cc_id,version,declaration_sha256):
        try:return self._handlers[(cc_id,version,declaration_sha256)]
        except KeyError as exc:raise ResearchError('carrier_unregistered','No installed carrier for this exact declaration') from exc


def refs_in(value):
    if isinstance(value,dict):
        if set(value)=={'id','sha256'}:yield value
        else:
            for child in value.values():yield from refs_in(child)
    elif isinstance(value,(list,tuple)):
        for child in value:yield from refs_in(child)


class CapsuleArtifacts:
    """Artifact capability only; no authoritative database/release operations."""
    __slots__=('__store','__allowed','__scope')
    def __init__(self,store,allowed,*,scope):
        self.__store=store;self.__allowed={(r['id'],r['sha256']) for r in allowed};self.__scope=dict(scope)
    def _grant(self,value):
        self.__allowed.update((r['id'],r['sha256']) for r in refs_in(value))
        return value
    def read_blob(self,ref):
        if (ref['id'],ref['sha256']) not in self.__allowed:raise ResearchError('artifact_scope','Artifact is outside this invocation read capability')
        return self.__store.read_blob(ref)
    def read_record(self,ref,*,contract_id=None):
        raw=self.read_blob(ref)
        try:value=json.loads(raw.decode('utf-8'))
        except (ValueError,UnicodeError) as exc:raise ResearchError('integrity_fault','Artifact is not a JSON record') from exc
        if contract_id:validate(contract_id,value)
        return value
    def put_blob(self,data,**metadata):
        ref=self.__store.put_blob(data,**metadata)
        self.__store.mark_evaluation_material(self.__scope['run_id'],ref)
        return self._grant(ref)
    def put_record(self,contract_id,record,**metadata):
        if contract_id not in {'build-receipt', 'urn:ai4r:prediction-build-receipt:2.0.0', 'urn:ai4r:prediction-build-receipt:3.0.0', 'urn:ai4r:prediction-build-receipt:4.0.0'}:
            raise ResearchError('authority_boundary','Capsules may publish candidate bytes, never host authority records')
        return self._grant(self.__store.put_record(contract_id,record,scope=self.__scope))
    def append_record(self,kind,record):
        if kind not in {'build_failure','scientific_execution','benchmark_attempt','planner_attempt','builder_attempt'}:raise ResearchError('authority_boundary','Capsule event kind is not permitted')
        if kind == 'builder_attempt':
            if (set(record) != {'ordinal','candidate_ref','diagnostics_ref','advisory','repair_requested'}
                    or type(record['ordinal']) is not int or record['ordinal'] not in (1,2,3)
                    or record['advisory'] is not True or type(record['repair_requested']) is not bool):
                raise ResearchError('authority_boundary', 'Invalid advisory Builder event')
            for key in ('candidate_ref','diagnostics_ref'):
                self.read_blob(record[key])
        if kind == 'planner_attempt':
            if (self.__scope['node_id'] != 'planner' or self.__scope['subnode_id'] != 'planner'
                    or set(record) != {'ordinal','candidate_ref','diagnostics_ref','advisory','repair_requested'}
                    or type(record['ordinal']) is not int or record['ordinal'] not in (1, 2)
                    or record['advisory'] is not True or type(record['repair_requested']) is not bool):
                raise ResearchError('authority_boundary', 'Invalid advisory Planner attempt event')
            for key in ('candidate_ref','diagnostics_ref'):
                self.read_blob(record[key])
        safe=dict(record,**self.__scope,id='capsule-event:'+uuid.uuid4().hex)
        return self._grant(self.__store.append_record(kind,safe))


class BoundExecutorAccess:
    def __init__(self,facade,artifacts,before_tool=None):self.__facade,self.__artifacts,self.__before_tool=facade,artifacts,before_tool
    def __getattr__(self,name):
        if name not in {'measure_job','provision','hardware_inventory','collect_builder','run','builder_test','builder_action'}:raise AttributeError(name)
        method=getattr(self.__facade,name)
        async def invoke(*args,**kwargs):
            if name == 'builder_action' and self.__before_tool is not None:
                value=self.__before_tool('builder_action')
                if inspect.isawaitable(value):await value
            value=method(*args,**kwargs)
            if inspect.isawaitable(value):value=await value
            self.__artifacts._grant(value)
            return value
        return invoke


class BoundConnectorsAccess:
    def __init__(self,facade,artifacts):self.__facade,self.__artifacts=facade,artifacts
    async def retrieve(self,scope,queries):
        value=await self.__facade.retrieve(scope,queries)
        self.__artifacts._grant(value)
        return value


class InvocationContext:
    def __init__(self,runner,contract,execution_id,inputs):
        self._runner=runner;self.contract=copy.deepcopy(contract);self.execution_id=execution_id
        self._tool_ordinal=0
        execution=runner._executions[execution_id]
        allowed=list(contract['input_refs'])+list(refs_in(inputs))+list(contract['bindings'][0]['implementation_refs'])+list(contract['bindings'][0]['dependency_refs'])
        self.store=CapsuleArtifacts(runner.store,allowed,scope={k:contract[k] for k in ('run_id','node_id','subnode_id','attempt_id')})
        self.connectors=None
        self.executor=None
        self.inputs=inputs;self._ordinal=0;self._retried=False

    def _bind_active_capabilities(self):
        runner=self._runner;contract=self.contract;execution_id=self.execution_id
        if runner._executions[execution_id].get('phase') not in {'prepared','active'}:
            raise ResearchError('invocation_not_active','Closed work has no effect capabilities')
        # Trusted facade construction is inert. Every operation still passes
        # the active-only authorizers, including during the final start CAS.
        if runner.connectors is not None and 'deepsearch' in contract['bindings'][0]['effective_authority']['tools']:
            bind=getattr(runner.connectors,'bind_invocation',None)
            if bind is not None:self.connectors=BoundConnectorsAccess(bind(contract_ref=self.contract_ref,invocation_id=self.invocation_id,contract=copy.deepcopy(contract),before_tool=self._before_tool),self.store)
        if runner.executor is not None:
            bind=getattr(runner.executor,'bind_invocation',None)
            if bind is not None:self.executor=BoundExecutorAccess(bind(contract_ref=self.contract_ref,invocation_id=self.invocation_id,contract=copy.deepcopy(contract),execution_id=execution_id),self.store,self._before_tool)

    def input_refs(self,port):
        matches=[p for p in self.contract['inputs'] if p['name']==port]
        if len(matches)!=1:raise ResearchError('input_binding','Missing or duplicate named input')
        return tuple(matches[0]['artifact_refs'])

    def input_ref(self,port):
        refs=self.input_refs(port)
        if len(refs)!=1:raise ResearchError('input_binding','Input is not a single artifact')
        return refs[0]

    def read_blob(self,ref):return self.store.read_blob(ref)
    def read_json(self,ref):return self.store.read_record(ref)

    def _before_tool(self,operation):
        self._tool_ordinal+=1
        return self._runner.authorize_tool_call({'execution_id':self.execution_id,'tool_ordinal':self._tool_ordinal,'operation':operation})

    @property
    def configuration_ref(self):
        execution=self._runner._executions[self.execution_id]
        if execution.get('evaluation_owner') is not None:
            grant,context,_=execution['evaluation_owner']._execution(self.execution_id)
            return copy.deepcopy(context['configuration_ref'])
        return copy.deepcopy(self._runner._run_contexts[self.contract['run_id']]['configuration_ref'])

    @property
    def contract_ref(self):return copy.deepcopy(self._runner._executions[self.execution_id]['contract_ref'])

    @property
    def invocation_id(self):return self._runner._executions[self.execution_id]['invocation_id']

    def record_host(self,key: str,ref: Ref)->None:
        from .binding import HOST_KEYS
        if key not in HOST_KEYS|{'planner_infeasible'}:raise ResearchError('host_record_invalid','Unknown protected host-record key')
        self.store.read_blob(ref)
        self._runner.store.append_record('host-record-proposal',{'id':'host-record:'+uuid.uuid4().hex,
            **{k:self.contract[k] for k in ('run_id','node_id','subnode_id','attempt_id')},
            'invocation_id':self._runner._executions[self.execution_id]['invocation_id'],'key':key,'ref':ref})

    async def model(self,prompt: str,system: str | None=None)->str:
        self._ordinal+=1
        if not isinstance(prompt,str) or (system is not None and not isinstance(system,str)):
            raise ResearchError('model_input','Text-only governed calls required')
        bridge=self._runner.model
        if bridge is None:raise ResearchError('model_unavailable','Governed model bridge is unavailable')
        context={'execution_id':self.execution_id,'call_ordinal':self._ordinal}
        # The transport has one text field. Fixed instructions and payload remain
        # separate labelled material; the verifier payload has exactly two members.
        text=prompt if system is None else system+'\n\n<subject_payload>\n'+prompt+'\n</subject_payload>'
        evidence=getattr(self._runner,'evidence',None)
        if evidence is not None:
            try:evidence.capture_prompt(self.contract,self._ordinal,text)
            except Exception as error:evidence.missing(self.contract['run_id'],'prompt-before:'+self.execution_id+':'+str(self._ordinal),'Optional original prompt file copy failed: '+type(error).__name__)
        try:result=await bridge.call(context,text)
        except Exception as error:
            ref=getattr(error,'call_ref',None)
            if ref is not None:
                captured=self._runner.store.read_record(ref,contract_id='model-call')
                if captured['execution_id']!=self.execution_id or captured['invocation_id']!=self.invocation_id:
                    raise ResearchError('integrity_fault','Failed governed call belongs to another invocation') from error
                self._runner._executions[self.execution_id]['calls'].append(dict(captured,call_ref=ref,route_ref=getattr(error,'route_ref',None)))
                # Stopgap: one retry of a call that definitely failed (never an
                # unknown outcome) with a transient provider code. The failed
                # call keeps its claim, record and ordinal.
                # Product path only: evaluation/replay owners keep their exact
                # measured one-call budgets.
                if (captured.get('outcome')=='failed' and captured.get('provider_error_code') in TRANSIENT_PROVIDER_CODES
                        and not self._retried and self._runner.resolve_evaluation_owner(execution_id=self.execution_id) is None):
                    self._retried=True
                    self._runner.store.append_record('model-call-retry',{'id':'model-call-retry:'+uuid.uuid4().hex,
                        **{k:self.contract[k] for k in ('run_id','node_id','subnode_id','attempt_id')},
                        'invocation_id':self.invocation_id,'failed_call_id':captured.get('id'),
                        'failed_call_ordinal':self._ordinal,'reason_code':captured['provider_error_code'],'recorded_at':utc_now()})
                    from .builder_mode import builder_mode
                    try:agent_builder=builder_mode(self._runner._executions[self.execution_id]['declaration'])=='agent'
                    except Exception:agent_builder=False
                    if agent_builder:
                        # The Builder runtime keeps its own model ordinal; it
                        # re-asks through this context so both advance together.
                        error.retryable=True
                    else:
                        return await self.model(prompt,system)
            raise
        self._runner._executions[self.execution_id]['calls'].append(result)
        from .reply_repair import carrier_reply_schema,reply_problems,repair_prompt
        carrier,schema=carrier_reply_schema(system)
        if carrier and not self._retried and self._runner.resolve_evaluation_owner(execution_id=self.execution_id) is None:
            # Stopgap: one re-ask of a reply that fails its own reply schema,
            # sharing this invocation's single retry allowance.
            problems=reply_problems(result['text'],schema)
            if problems:
                self._retried=True
                self._runner.store.append_record('model-call-retry',{'id':'model-call-retry:'+uuid.uuid4().hex,
                    **{k:self.contract[k] for k in ('run_id','node_id','subnode_id','attempt_id')},
                    'invocation_id':self.invocation_id,'failed_call_id':result.get('id'),
                    'failed_call_ordinal':self._ordinal,'reason_code':'reply_invalid','recorded_at':utc_now()})
                return await self.model(repair_prompt(prompt,result['text'],problems),system)
        return result['text']


TRACE_REF_LIMIT=64  # invocation-observation trace_refs maxItems
TRANSIENT_PROVIDER_CODES=frozenset({'provider_error','rate_limited','timeout','network_error'})


def transient_retries(store,run_id,*,node_id=None,invocation_id=None,subnode_id=None,attempt_id=None):
    """Granted one-shot retries of failed transient model calls (model-call-retry records).

    Each is a stopgap allowance on top of the frozen invocation, node and run
    call limits; reviewer reservations are never used for them."""
    return sum(1 for row in store.iter_records(run_id=run_id,kinds=('model-call-retry',))
               if (node_id is None or row['record'].get('node_id')==node_id)
               and (invocation_id is None or row['record'].get('invocation_id')==invocation_id)
               and (subnode_id is None or row['record'].get('subnode_id')==subnode_id)
               and (attempt_id is None or row['record'].get('attempt_id')==attempt_id))


class CapsuleRunner:
    def __init__(self,store,registry,check_registry,*,model,executor=None,connectors=None,check_assets=None,evidence=None,faults=None):
        self.store,self.registry,self.check_registry=store,registry,check_registry
        self.model,self.executor,self.connectors=model,executor,connectors
        self.gate=EvidenceAwareGate(store);self.verifier=EvidenceAwareSemanticVerifier(store)
        self._executions={};self._run_contexts={}
        self._preparations={}
        self._node_check_plans={}
        self._native_start_port=None
        self._native_start_identity=None
        self._run_started={};self._node_started={}
        self.check_assets=CheckAssetAdmissions(store) if check_assets is None else check_assets
        self.evidence=evidence
        self.faults=faults
        self._evaluation_owners=[]

    def register_evaluation_owner(self,owner):
        from .evaluation_authority import EvaluationAuthority
        if type(owner) is not EvaluationAuthority or owner.store is not self.store or owner.runner is not self:
            raise ResearchError('evaluation_authority','Only an exact installed private owner can register')
        owner._current_runtime()
        if any(other.runtime_ref==owner.runtime_ref and other is not owner for other in self._evaluation_owners):
            raise ResearchError('evaluation_authority','Runtime already has a registered owner')
        if owner not in self._evaluation_owners:self._evaluation_owners.append(owner)

    def resolve_evaluation_owner(self,*,execution_id=None,run_id=None):
        if (execution_id is None)==(run_id is None):raise ResearchError('evaluation_authority','One exact identity required')
        matches=[owner for owner in self._evaluation_owners if (owner.owns_execution(execution_id) if execution_id is not None else owner.owns_run(run_id))]
        if len(matches)>1:raise ResearchError('evaluation_authority','Ambiguous private execution owner')
        return matches[0] if matches else None

    def capture_record(self,kind,record):
        """Native persistence sink with exact registered private attribution."""
        execution_id=record.get('execution_id')
        if execution_id is None and record.get('invocation_id'):
            matches=[key for key,value in self._executions.items() if value['invocation_id']==record['invocation_id']]
            if len(matches)==1:execution_id=matches[0]
        owner=self.resolve_evaluation_owner(execution_id=execution_id) if execution_id else None
        if owner is not None:return owner.capture_native(kind,record,execution_id=execution_id)
        return self.store.append_record(kind,record)

    def configure_run(self,run_id,*,model_selection_profile_ref,deployment_ref,router,configuration_ref,run_limits,routing_context=None):
        for ref in (model_selection_profile_ref,deployment_ref,configuration_ref):self.store.read_blob(ref)
        prior=self._run_contexts.get(run_id)
        value={'model_selection_profile_ref':copy.deepcopy(model_selection_profile_ref),'deployment_ref':copy.deepcopy(deployment_ref),
               'router':copy.deepcopy(router),'configuration_ref':copy.deepcopy(configuration_ref),'run_limits':copy.deepcopy(run_limits),
               'routing_context':copy.deepcopy(routing_context)}
        # The model name is protected deployment data, never a prompt parameter.
        # Historical opaque deployment captures retain their original behavior.
        try: deployment=json.loads(self.store.read_blob(deployment_ref))
        except (ValueError,UnicodeError):deployment=None
        from .fixed_subscription import FIXED_DEPLOYMENT_SCHEMAS, deployment_model, deployment_backend
        if isinstance(deployment,dict) and deployment.get('schema') in FIXED_DEPLOYMENT_SCHEMAS:
            requested = deployment_model(deployment)
            deployment_backend(deployment)  # Validate the explicit protected backend too.
            if requested not in {'gpt-6.1-sol','gpt-6-luna'}:
                raise ResearchError('deployment_binding','Unsupported fixed subscription deployment')
            value['requested_model']=requested
        if prior is not None and prior!=value:raise ResearchError('frozen_context','Run authorization cannot change')
        self._run_contexts[run_id]=value
        # Configuration freezes authority; the run clock begins on its first actual reservation.

    def _budget_state(self,contract,execution=None,*,reserve=True):
        """Reconstruct unspent frozen sibling/reviewer reservations before effects."""
        run_id,node_id=contract['run_id'],contract['node_id']
        frozen=self._run_contexts.get(run_id)
        if frozen is None:raise ResearchError('budget_unavailable','No protected run ceiling was frozen')
        run=self.store.get_run(run_id)
        if run['state'] not in {'pending','running'} or self.store.cancellation_requested(run_id):
            raise ResearchError('run_not_dispatchable','Stopped work cannot consume a reservation')
        parent=self.store.read_record(contract['node_contract_ref'],contract_id='node-execution-contract')
        now=time.monotonic();key=(run_id,node_id)
        run_started=self._run_started.get(run_id,now)
        node_started=self._node_started.get(key,now)
        if reserve:
            self._run_started.setdefault(run_id,now)
        if reserve and key not in self._node_started:
            self._node_started[key]=now
            self.store.append_record('node-budget-start',{'id':'node-budget:'+uuid.uuid4().hex,'run_id':run_id,'node_id':node_id,
                'node_contract_ref':contract['node_contract_ref'],'interface_revision':'M1-IF-002@r2','started_monotonic_s':now,'recorded_at':utc_now()})
        completed={entry['record']['subnode_id'] for entry in self.store.iter_records(run_id=run_id,kinds=('invocation-observation',))
                   if entry['record'].get('node_contract_ref')==contract['node_contract_ref']}
        reserved={kind:{'time_s':0,'model_calls':0,'memory_mb':parent['node_limits']['memory_mb']}
                  for kind in ('verifier_reserved','other_work_reserved','routing_reserved')}
        for assignment in parent['subnodes']:
            if not assignment['required'] or assignment['subnode_id']==contract['subnode_id'] or assignment['subnode_id'] in completed:continue
            template=self.store.read_record(assignment['template_ref'])
            declaration=self.store.read_record(template['capsule_ref'],contract_id='capsule-declaration')
            per=declaration['budget']['per_call']
            seconds=per['wall_s'];calls=per['invocations'] if any(i['service_key']=='audited_model_bridge' for i in declaration['needs']['injects']) else 0
            kind='verifier_reserved' if assignment['role']=='verifier' else 'other_work_reserved'
            if assignment['role']=='verifier':
                profile=self.store.read_record(template['checking_profile_ref'],contract_id='checking-profile')
                if calls!=1 or profile['model_call_limit']!=1:raise ResearchError('verifier_binding','Frozen reviewer must retain its independent one-call budget')
                seconds=min(seconds,profile['time_s'])
            reserved[kind]['time_s']+=seconds;reserved[kind]['model_calls']+=calls
        with self.store._lock:
            node_used=self.store.connection.execute('SELECT COUNT(*) FROM model_calls WHERE run_id=? AND node_id=?',(run_id,node_id)).fetchone()[0]
            run_used=self.store.connection.execute('SELECT COUNT(*) FROM model_calls WHERE run_id=?',(run_id,)).fetchone()[0]
            used=0 if execution is None else self.store.connection.execute('SELECT COUNT(*) FROM model_calls WHERE run_id=? AND invocation_id=?',(run_id,execution['invocation_id'])).fetchone()[0]
        # Product automatic routing has its own versioned per-worker selection
        # capacity. Worker/reviewer invocation ceilings and the run total stay
        # unchanged. Selection claims are included in node and run usage.
        retries_run=transient_retries(self.store,run_id)
        retries_node=transient_retries(self.store,run_id,node_id=node_id)
        retries_own=0 if execution is None else transient_retries(self.store,run_id,invocation_id=execution['invocation_id'])
        node_call_ceiling = parent['node_limits']['model_calls'] + node_routing_allowance(self.store, parent) + retries_node
        node_remaining={'time_s':max(0,parent['node_limits']['time_s']-(now-node_started)),
                        'model_calls':max(0,node_call_ceiling-node_used),'memory_mb':parent['node_limits']['memory_mb']}
        run_remaining={'time_s':max(0,frozen['run_limits']['time_s']-(now-run_started)),
                       'model_calls':max(0,frozen['run_limits']['model_calls']+retries_run-run_used),'memory_mb':frozen['run_limits']['memory_mb']}
        elapsed=0 if execution is None else now-execution['started']
        own=contract['bindings'][0]['limits']
        subremaining={'time_s':max(0,min(own['time_s'],contract['subnode_limits']['time_s'])-elapsed),
                      'model_calls':max(0,min(own['model_calls'],contract['subnode_limits']['model_calls'])+retries_own-used),
                      'memory_mb':min(own['memory_mb'],contract['subnode_limits']['memory_mb'])}
        reserved_calls=sum(r['model_calls'] for r in reserved.values());reserved_time=sum(r['time_s'] for r in reserved.values())
        spendable={'time_s':min(subremaining['time_s'],node_remaining['time_s']-reserved_time,run_remaining['time_s']-reserved_time),
                   'model_calls':min(subremaining['model_calls'],node_remaining['model_calls']-reserved_calls,run_remaining['model_calls']-reserved_calls),
                   'memory_mb':min(subremaining['memory_mb'],node_remaining['memory_mb'],run_remaining['memory_mb'])}
        if spendable['time_s']<=0 or spendable['model_calls']<0:
            raise ResearchError('budget_exhausted','Frozen independent reviewer/sibling reservations do not fit the remaining node/run ceiling')
        return {'node_remaining':node_remaining,'run_remaining':run_remaining,'subnode_remaining':subremaining,
                **reserved,'spendable':spendable,'reserved_calls':reserved_calls,'observed_monotonic_s':now,
                'node_call_ceiling': node_call_ceiling}

    def authorize_model_context(self,context: Mapping)->dict:
        owner=self.resolve_evaluation_owner(execution_id=context.get('execution_id'))
        if owner is not None:return owner.authorize_model_context(context)
        execution=self._executions.get(context.get('execution_id'))
        if execution is None or execution['closed'] or execution.get('phase')!='active':raise ResearchError('model_call_authorization','No active protected execution')
        contract=execution['contract'];binding=contract['bindings'][0]
        frozen=self._run_contexts.get(contract['run_id'])
        if frozen is None:raise ResearchError('model_call_authorization','No frozen protected call authorization')
        if self.store.cancellation_requested(contract['run_id']):raise ResearchError('cancelled','Run is being contained')
        parent=self.store.read_record(contract['node_contract_ref'],contract_id='node-execution-contract')
        selection_profile=self.store.read_record(frozen['model_selection_profile_ref'],contract_id='model-selection-profile')
        if selection_profile['policy_mode'] not in {'fixed_baseline','development_profile'}:
            raise ResearchError('model_call_authorization','Unsupported selection policy cannot authorize an M1 call')
        elapsed=time.monotonic()-execution['started']
        budget=self._budget_state(contract,execution)
        deadline=min(execution['deadline'],budget['observed_monotonic_s']+budget['spendable']['time_s'])
        remaining=deadline-time.monotonic()
        if remaining<=0 or budget['spendable']['model_calls']<1:raise ResearchError('budget_exhausted','Invocation cannot consume protected reviewer/sibling capacity')
        protected={**{k:contract[k] for k in ('run_id','node_id','subnode_id','attempt_id')},
                   'invocation_id':execution['invocation_id'],'execution_id':context['execution_id'],
                   'call_ordinal':context.get('call_ordinal'),'call_function':execution['call_function'],
                   'cc_name':execution['declaration']['identity']['name'],'cc_version':execution['declaration']['identity']['version_label'],
                   'declaration':copy.deepcopy(execution['declaration']),
                   'contract_ref':execution['contract_ref'],'input_refs':contract['input_refs'],
                   'limits':dict(binding['limits'],time_s=remaining),
                   'execution_deadline_monotonic_s':deadline,
                   **{k:copy.deepcopy(v) for k,v in frozen.items() if k not in {'run_limits','routing_context'}},
                   'model_selection_profile':selection_profile,'approved_model_ids':selection_profile['approved_model_ids']}
        if routing_policy(self.store, contract['run_id']) is not None:
            protected['routing_budget'] = {
                'schema': 'ai4r-routing-budget-view:1',
                'basis': 'remaining_before_current_executor_claim',
                **{key: copy.deepcopy(budget[key]) for key in (
                    'node_remaining', 'run_remaining', 'subnode_remaining',
                    'verifier_reserved', 'other_work_reserved', 'spendable')},
                'tokens_remaining': None, 'cost_remaining': None,
                'unavailable_reason': 'Local token and compute-cost balances are not measured',
            }
        if frozen['router']['enabled'] and selection_profile['policy_mode']!='fixed_baseline' and execution['call_function']!='verifier':
            try:
                selected,request=self._route_export(execution,context['execution_id'],parent,frozen,selection_profile)
                protected.update(selected_capsule=selected,route_request=request)
            except ResearchError as exc:
                if exc.code in {'TASK_MISMATCH','BUDGET_UNVERIFIABLE','PROFILE_UNAVAILABLE'}:protected['routing_export_error']=exc.code
                else:raise
        call_id,claim_ref=self.store.claim_model_call(protected,invocation_limit=min(contract['subnode_limits']['model_calls'],binding['limits']['model_calls'])
            +transient_retries(self.store,contract['run_id'],invocation_id=execution['invocation_id']),
            node_limit=budget['node_call_ceiling'],run_limit=frozen['run_limits']['model_calls']+transient_retries(self.store,contract['run_id']),
            reserved_node_calls=budget['reserved_calls'],reserved_run_calls=budget['reserved_calls'])
        return dict(protected,call_id=call_id,call_claim_ref=claim_ref)

    def authorize_routing_selection(self, payload):
        """Private bridge-only allowance for one nonrecursive selection call."""
        fields = {'execution_id', 'invocation_id', 'call_id', 'call_claim_ref', 'contract_ref'}
        if (not isinstance(payload, Mapping) or set(payload) != fields | {'prompt_sha256'}
                or not isinstance(payload['prompt_sha256'], str)
                or len(payload['prompt_sha256']) != 64
                or any(c not in '0123456789abcdef' for c in payload['prompt_sha256'])):
            raise ResearchError('invalid_request', 'Invalid routing selection binding')
        subject = self.authorize_model_dispatch({key: payload[key] for key in fields})
        if subject['call_function'] not in {'worker', 'planner'} or subject.get('purpose') == 'routing_selection':
            raise ResearchError('invalid_request', 'This call cannot request another selector')
        snapshot = routing_policy(self.store, subject['run_id'])
        if snapshot is None:
            raise ResearchError('invalid_request', 'No frozen automatic routing policy')
        if snapshot['routing_policy']['selection_calls_per_capsule_invocation'] == 0:
            raise ResearchError('invalid_request', 'The frozen primary-executor policy forbids model selection calls')
        candidate = next((c for c in snapshot['candidates'] if c['id'] == snapshot['selector_id']), None)
        if candidate is None:
            raise ResearchError('invalid_request', 'No pinned selection model')
        execution = self._executions[subject['execution_id']]
        contract = execution['contract']
        budget = self._budget_state(contract, execution)
        deadline = min(subject['execution_deadline_monotonic_s'],
            time.monotonic() + snapshot['routing_policy']['selection_time_s'])
        if deadline <= time.monotonic():
            raise ResearchError('budget_exhausted', 'No time remains for routing selection')
        selection = {key: copy.deepcopy(value) for key, value in subject.items()
            if key not in {'call_id', 'call_claim_ref', 'selected_capsule', 'route_request'}}
        selection.update(
            purpose='routing_selection', call_function='routing_selection',
            subject_call_id=subject['call_id'], subject_invocation_id=subject['invocation_id'],
            invocation_id=subject['invocation_id'] + ':routing', call_ordinal=1,
            expected_prompt_sha256=payload['prompt_sha256'], routing_selection_candidate=copy.deepcopy(candidate),
            deployment_ref=candidate['deployment_ref'],
            limits=dict(subject['limits'], time_s=deadline-time.monotonic(), model_calls=1),
            execution_deadline_monotonic_s=deadline)
        frozen = self._run_contexts[subject['run_id']]
        call_id, claim_ref = self.store.claim_model_call(selection, invocation_limit=1,
            node_limit=budget['node_call_ceiling'], run_limit=frozen['run_limits']['model_calls'],
            reserved_node_calls=budget['reserved_calls'], reserved_run_calls=budget['reserved_calls'])
        return dict(selection, call_id=call_id, call_claim_ref=claim_ref)

    def authorize_model_dispatch(self,payload: Mapping)->dict:
        """Recheck the existing durable claim immediately before its effect."""
        owner=self.resolve_evaluation_owner(execution_id=payload.get('execution_id'))
        if owner is not None:return owner.authorize_model_dispatch(payload)
        fields={'execution_id','invocation_id','call_id','call_claim_ref','contract_ref'}
        if not isinstance(payload,Mapping) or set(payload)!=fields:
            raise ResearchError('model_dispatch_authorization','Malformed finite dispatch recheck')
        execution=self._executions.get(payload['execution_id'])
        if (execution is None or execution['closed'] or execution.get('phase')!='active' or payload['contract_ref']!=execution['contract_ref']):
            raise ResearchError('model_dispatch_authorization','No matching active invocation')
        contract=execution['contract']
        with self.store._lock:
            row=self.store.connection.execute('SELECT claim_ref FROM model_calls WHERE run_id=? AND invocation_id=? AND call_id=?',
                (contract['run_id'],payload['invocation_id'],payload['call_id'])).fetchone()
        if row is None or json.loads(row['claim_ref'])!=payload['call_claim_ref']:
            raise ResearchError('model_dispatch_authorization','Dispatch does not match an exact durable call claim')
        claim=self.store.read_record(payload['call_claim_ref'])
        if any(claim.get(key)!=payload[key] for key in fields-{'call_claim_ref'}):
            raise ResearchError('model_dispatch_authorization','Claim and protected execution differ')
        if claim.get('purpose') == 'routing_selection':
            snapshot = routing_policy(self.store, contract['run_id'])
            selector = next((c for c in snapshot['candidates'] if c['id'] == snapshot['selector_id']), None) if snapshot else None
            if (claim.get('subject_invocation_id') != execution['invocation_id'] or selector is None
                    or claim.get('routing_selection_candidate') != selector
                    or claim['invocation_id'] != execution['invocation_id'] + ':routing'
                    or self.store.read_record(self.store.record_ref(claim['subject_call_id'] + ':claim'))['invocation_id'] != execution['invocation_id']):
                raise ResearchError('model_dispatch_authorization', 'Routing selection scope differs')
        elif payload['invocation_id'] != execution['invocation_id']:
            raise ResearchError('model_dispatch_authorization', 'Dispatch invocation differs')
        budget=self._budget_state(contract,execution)
        deadline=min(execution['deadline'],claim['execution_deadline_monotonic_s'],
                     budget['observed_monotonic_s']+budget['spendable']['time_s'])
        remaining=deadline-time.monotonic()
        if remaining<=0:raise ResearchError('budget_exhausted','Call expired before provider dispatch')
        return {**copy.deepcopy(claim),'call_claim_ref':copy.deepcopy(payload['call_claim_ref']),
                'limits':dict(claim['limits'],time_s=remaining),'execution_deadline_monotonic_s':deadline}

    def _route_export(self,execution,execution_id,parent,frozen,profile):
        if execution.get('route_request') is not None:return execution['selected_capsule'],execution['route_request']
        envelope=frozen.get('routing_context');contract=execution['contract'];binding=contract['bindings'][0]
        categories={'ml_methods_and_inference','retrieval_and_knowledge_systems','algorithms_optimization_and_formal','software_systems_and_performance','databases_and_data_processing','networking_and_distributed_algorithms','security_and_reliability','experimental_evaluation_and_technical_data'}
        if not isinstance(envelope,dict) or any(not isinstance(envelope.get(k),str) or not envelope[k] for k in ('workflow_id','task_id','task_category')) or envelope['task_category'] not in categories:
            raise ResearchError('TASK_MISMATCH','Protected routing correlation/category is unavailable')
        if frozen['router']['profile_ref']!=frozen['model_selection_profile_ref']:
            raise ResearchError('PROFILE_UNAVAILABLE','API route profile differs from the protected selected profile')
        budget=self._budget_state(contract,execution)
        remaining=budget['node_remaining'];subremaining=budget['spendable']
        reserved={key:budget[key] for key in ('verifier_reserved','other_work_reserved','routing_reserved')}
        if any(profile['selection_allowance'][k] for k in ('model_calls','time_s','output_tokens')) or profile['selection_allowance']['enabled']:
            raise ResearchError('BUDGET_UNVERIFIABLE','M1 development routing requires zero selection-call spend')
        if remaining['model_calls']<sum(v['model_calls'] for v in reserved.values())+subremaining['model_calls']:
            raise ResearchError('BUDGET_UNVERIFIABLE','Mandatory sibling/verifier call reservations cannot be protected')
        ledger={'id':'routing-budget:'+uuid.uuid4().hex,'run_id':contract['run_id'],'node_id':contract['node_id'],'subnode_id':contract['subnode_id'],
                'node_remaining':remaining,'subnode_remaining':subremaining,**reserved,'tokens_remaining':None,'cost_remaining':None,'cost_currency':None,
                'unavailable_reasons':['No attributable token or monetary ledger is configured; unknown balances remain unavailable']}
        snapshot_ref=self.store.append_record('routing-budget-snapshot',ledger)
        bound={'runtime':{**{k:contract[k] for k in ('run_id','node_id','subnode_id','attempt_id')},'invocation_id':execution['invocation_id']},
               'binding_id':binding['id'],'role':binding['role'],'objective':contract['objective'],'inputs':contract['inputs'],'outputs':contract['outputs'],
               'implementation_refs':binding['implementation_refs'],
               'overlay_refs':[{'id':item['ref'],'sha256':item['sha256']} for item in execution['declaration']['identity'].get('overlays',[])],
               'dependency_refs':binding['dependency_refs'],'admission_ref':binding['admission_ref'],
               'eligibility':'eligible','prerequisite_results':[],'effective_authority':binding['effective_authority'],'invocation_limits':binding['limits'],
               'subnode_limits':contract['subnode_limits'],'node_limits':parent['node_limits'],'budget_snapshot':dict({k:v for k,v in ledger.items() if k not in {'id','run_id','node_id','subnode_id'}},snapshot_ref=snapshot_ref),
               'policy_ref':contract['policy_ref'],'configuration_ref':contract['configuration_ref']}
        selected={'schema_version':'1.0.0','declaration':execution['declaration'],'declaration_ref':binding['declaration_ref'],
                  'node_contract_ref':contract['node_contract_ref'],'subnode_contract_ref':execution['contract_ref'],'bound_context':bound}
        validate('selected-capsule-input',selected)
        run=self.store.get_run(contract['run_id'])
        request={'schema_version':'1.0.0','request_id':'route-request:'+uuid.uuid4().hex,'workflow_id':envelope['workflow_id'],'task_id':envelope['task_id'],
                 'execution_id':execution_id,'user_id':run['account_id'],'domain':'cs_ml','task_category':envelope['task_category'],'workflow_stage':contract['node_id'],
                 'call_function':execution['call_function'],'task_summary':contract['objective'],'input_refs':contract['input_refs'],'selected_capsule':selected,
                 'model_selection_profile_ref':frozen['model_selection_profile_ref'],'requirements':envelope.get('requirements',{}),'policy_ref':contract['policy_ref'],'preferences':envelope.get('preferences',{})}
        validate('route-request',request)
        execution['selected_capsule']=selected;execution['route_request']=request
        self.store.append_record('protected-route-export',{'id':'route-export:'+uuid.uuid4().hex,'run_id':contract['run_id'],
            'invocation_id':execution['invocation_id'],'selected_capsule_ref':self.store.put_record('selected-capsule-input',selected),'request_ref':self.store.put_record('route-request',request)})
        return selected,request

    def authorize_executor_binding(self,payload: Mapping)->dict:
        owner=self.resolve_evaluation_owner(execution_id=payload.get('execution_id'))
        if owner is not None:return owner.authorize_executor_binding(payload)
        if not isinstance(payload,Mapping) or set(payload)!={'contract_ref','invocation_id','execution_id'}:
            raise ResearchError('executor_authorization','Executor binding request has unknown or missing fields')
        execution=self._executions.get(payload['execution_id'])
        if execution is None or execution['closed'] or execution.get('phase')!='active' or execution['contract_ref']!=payload['contract_ref'] or execution['invocation_id']!=payload['invocation_id']:
            raise ResearchError('executor_authorization','No matching active registered invocation')
        contract=execution['contract'];run=self.store.get_run(contract['run_id'])
        if run['state'] not in {'pending','running'} or self.store.cancellation_requested(contract['run_id']):
            raise ResearchError('run_not_dispatchable','Stopped run cannot authorize an executor effect')
        budget=self._budget_state(contract,execution)
        deadline=min(execution['deadline'],budget['observed_monotonic_s']+budget['spendable']['time_s'])
        remaining=deadline-time.monotonic()
        if remaining<=0:
            raise ResearchError('budget_exhausted','Executor invocation wall-clock allowance exhausted')
        self.store.read_blob(execution['contract_ref'])
        return {'contract_ref':copy.deepcopy(execution['contract_ref']),'invocation_id':execution['invocation_id'],
                'execution_id':payload['execution_id'],'contract':copy.deepcopy(contract),
                'execution_deadline_monotonic_s':deadline,'remaining_time_s':remaining}

    def authorize_containment(self,payload: Mapping)->dict:
        owner=self.resolve_evaluation_owner(run_id=payload.get('run_id'))
        if owner is not None:return owner.authorize_containment(payload)
        if not isinstance(payload,Mapping) or set(payload)!={'run_id','request_id'} or any(not isinstance(v,str) or not v for v in payload.values()):
            raise ResearchError('containment_authorization','Malformed finite containment request')
        self.store.get_cancellation(payload['run_id'],payload['request_id'])
        invocations={value['invocation_id'] for value in self._executions.values() if value['contract']['run_id']==payload['run_id']}
        for entry in self.store.iter_records(run_id=payload['run_id'],kinds=('invocation-observation','model-call-claim','tool-call-claim','invocation-budget-reservation')):
            if isinstance(entry['record'].get('invocation_id'),str):invocations.add(entry['record']['invocation_id'])
        return {'authorized':True,'run_id':payload['run_id'],'request_id':payload['request_id'],'invocation_ids':sorted(invocations)}

    def authorize_tool_call(self,payload: Mapping)->Ref:
        owner=self.resolve_evaluation_owner(execution_id=payload.get('execution_id'))
        if owner is not None:return owner.authorize_tool_call(payload)
        if not isinstance(payload,Mapping) or set(payload)!={'execution_id','tool_ordinal','operation'}:raise ResearchError('tool_authorization','Malformed protected tool request')
        execution=self._executions.get(payload['execution_id'])
        if execution is None or execution['closed'] or execution.get('phase')!='active':raise ResearchError('tool_authorization','No active invocation can authorize this lookup')
        contract=execution['contract'];binding=contract['bindings'][0]
        if payload['operation'] not in binding['effective_authority']['tools']:raise ResearchError('tool_authorization','Tool is outside the exact effective binding')
        budget=self._budget_state(contract,execution)
        if time.monotonic()>=execution['deadline'] or budget['spendable']['time_s']<=0:raise ResearchError('budget_exhausted','Tool lookup deadline exhausted')
        context={**{key:contract[key] for key in ('run_id','node_id','subnode_id','attempt_id')},'contract_ref':execution['contract_ref'],
                 'invocation_id':execution['invocation_id'],'execution_id':payload['execution_id'],'tool_ordinal':payload['tool_ordinal'],'operation':payload['operation']}
        return self.store.claim_tool_call(context,tool_limit=execution['declaration']['budget']['per_call']['tool_calls'])

    def _require_child_authority(self,contract_ref,contract):
        """Reopen the original ordinary parent before any invocation authority."""
        from .binding import ContractFactory, validate_child_authority
        if (self.store.record_kind(contract_ref)!='subnode-execution-contract'
            or self.store.read_record(contract_ref,contract_id='subnode-execution-contract')!=contract
            or self.store.record_kind(contract['node_contract_ref'])!='node-execution-contract'):
            raise ResearchError('input_authority','Invocation is not an original canonical child and parent')
        parent=self.store.read_record(contract['node_contract_ref'],contract_id='node-execution-contract')
        assignments=[row for row in parent['subnodes'] if row['subnode_id']==contract['subnode_id']]
        if (len(assignments)!=1 or len(contract['bindings'])!=1
            or any(contract[key]!=parent[key] for key in ('run_id','node_id','attempt_id','revision','policy_ref','configuration_ref'))):
            raise ResearchError('input_authority','Child identity differs from its original parent assignment')
        assignment=assignments[0];binding=contract['bindings'][0]
        if (contract['template_ref']!=assignment['template_ref'] or binding['role']!=assignment['role']
            or binding['declaration_ref']!=assignment['capsule_ref']
            or contract['input_refs']!=[ref for port in contract['inputs'] for ref in port['artifact_refs']]):
            raise ResearchError('input_authority','Child binding or flat reads differ from the assigned concrete inputs')
        template=self.store.read_record(assignment['template_ref'])
        declared=self.store.read_record(assignment['capsule_ref'],contract_id='capsule-declaration')
        if binding['admission_ref']!=template['admission_ref'] or self.store.record_kind(binding['admission_ref'])!='library-admission':
            raise ResearchError('input_authority','Child admission differs from the original frozen template')
        admitted=self.store.read_record(binding['admission_ref'],contract_id='library-admission')
        identity=declared['identity']
        pin={'cc_name':identity['name'],'cc_version':identity['version_label'],'declaration_sha256':assignment['capsule_ref']['sha256']}
        if (admitted['status']!='admitted' or admitted['candidate_ref']!=assignment['capsule_ref']
            or admitted['cc']!=pin or template['cc']!=pin or template['ports']!=declared['ports']):
            raise ResearchError('input_authority','Original admitted declaration/template identity differs')
        implementations=[template['body_refs'][row['path']] for row in declared['identity']['body']]
        dependency_pins=[item for row in declared['needs']['external']
            for key in ('pin','lockfile') if (item:=row.get(key))]
        dependencies=[template['body_refs'][item['ref']] for item in dependency_pins]
        if binding['implementation_refs']!=implementations or binding['dependency_refs']!=dependencies:
            raise ResearchError('input_authority','Child implementation/dependency inventory differs from original template')
        for body,ref in zip(declared['identity']['body'],implementations):
            if ref['sha256']!=body['sha256']:raise ResearchError('input_authority','Original body pin differs from declaration')
        for dependency,ref in zip(dependency_pins,dependencies):
            if ref['sha256']!=dependency['sha256']:
                raise ResearchError('input_authority','Original dependency pin differs from declaration')
        for ref in [*implementations,*dependencies]:self.store.read_blob(ref)
        outputs=[{'name':port['name'],'contract_id':port['schema_ref'],
            'version':ContractFactory._version(port['schema_ref']),'required':port['required']}
            for port in declared['ports']['outputs']]
        if (contract['outputs']!=outputs
            or contract['required_outputs']!=[port['name'] for port in outputs if port['required']]):
            raise ResearchError('input_authority','Child output inventory differs from the original declaration')
        per=declared['budget']['per_call']
        calls=per['invocations'] if any(item['service_key']=='audited_model_bridge' for item in declared['needs']['injects']) else 0
        caps={'time_s':min(per['wall_s'],parent['node_limits']['time_s']),
            'model_calls':min(calls,parent['node_limits']['model_calls']),
            'memory_mb':min(admitted['memory_mb'],parent['node_limits']['memory_mb'])}
        if assignment['role']=='verifier':
            profile=self.store.read_record(template['checking_profile_ref'],contract_id='checking-profile')
            caps['time_s']=min(caps['time_s'],profile['time_s']);caps['model_calls']=min(caps['model_calls'],profile['model_call_limit'],1)
        if (binding['limits']!=contract['subnode_limits']
            or any(contract['subnode_limits'][key]>caps[key] for key in caps)):
            raise ResearchError('input_authority','Child invocation/subnode limits exceed original declaration/admission/template caps')
        validate_child_authority(self.store,contract['node_contract_ref'],contract['subnode_id'],contract['inputs'],
            effective_authority=binding['effective_authority'])

    def _start_context(self,contract_ref,contract,inputs,*,call_function='worker'):
        self._require_child_authority(contract_ref,contract)
        self._require_check_assets(contract)
        binding=contract['bindings'][0];declaration=self.store.read_record(binding['declaration_ref'],contract_id='capsule-declaration')
        for ref in [*binding['implementation_refs'],*binding['dependency_refs'],binding['admission_ref']]:self.store.read_blob(ref)
        if len(contract['bindings'])!=1:raise ResearchError('binding_invalid','Each subnode binds exactly one CC')
        budget=self._budget_state(contract)
        if min(contract['subnode_limits']['model_calls'],binding['limits']['model_calls'])>0 and budget['spendable']['model_calls']<1:
            raise ResearchError('budget_exhausted','Required independent review capacity cannot be borrowed to start work')
        if not self.store.claim_attempt(contract_ref,contract):
            raise ResearchError('attempt_already_claimed','Prepared work is never replayed after an uncertain claim')
        execution_id='execution:'+uuid.uuid4().hex
        began=time.monotonic()
        self._executions[execution_id]={'contract_ref':contract_ref,'contract':copy.deepcopy(contract),'declaration':declaration,
            'invocation_id':'invocation:'+uuid.uuid4().hex,'started':began,'deadline':began+budget['spendable']['time_s'],
            'calls':[],'closed':False,'call_function':call_function}
        self.store.append_record('invocation-budget-reservation',{'id':'invocation-budget:'+uuid.uuid4().hex,
            'run_id':contract['run_id'],'node_id':contract['node_id'],'subnode_id':contract['subnode_id'],
            'contract_ref':contract_ref,'invocation_id':self._executions[execution_id]['invocation_id'],
            'execution_id':execution_id,'interface_revision':'M1-IF-002@r2','budget':budget,'recorded_at':utc_now()})
        from .invocation_start import prepare
        return prepare(self,InvocationContext(self,contract,execution_id,inputs))

    def authorize_executor_preparation(self,payload):
        from .invocation_start import authorize
        return authorize(self,payload)

    def _register_native_start_port(self,ports):
        """Bind the installed protected composition, never a caller permit."""
        from .native_ports import NativePorts
        from .executor_rpc import ExecutorClient,PROTOCOL
        from .private_rpc import PrivateRPCClient
        if type(ports) is not NativePorts or ports.runner is not self or ports.executor is not self.executor:
            raise ResearchError('executor_preparation_authorization','Native start composition does not own this Runner')
        client=ports.executor
        if (type(client) is not ExecutorClient or type(client.rpc) is not PrivateRPCClient
                or client.rpc.path!=Path('/run/ai4r-executor/executor.sock')
                or client.rpc.protocol!=PROTOCOL or client.rpc.peer_uid!=0 or client.rpc.socket_mode!=0o660
                or client.rpc.session_id!=ports.session['session_id'] or client.rpc.capability!=ports.session['capability']):
            raise ResearchError('executor_preparation_authorization','An installed exact root-peer native start carrier is required')
        if self._native_start_port is not None and self._native_start_port is not ports:
            raise ResearchError('identity_conflict','Native start owner cannot be replaced')
        self._native_start_port=ports
        self._native_start_identity=(client,client.rpc,client.rpc.path,client.rpc.protocol,
            client.rpc.peer_uid,client.rpc.socket_mode,client.rpc.session_id,client.rpc.capability)

    def _require_native_start_port(self):
        ports=self._native_start_port;expected=self._native_start_identity
        if ports is None or expected is None or ports.runner is not self or ports.executor is not self.executor:
            raise ResearchError('SCIENCE_RUNTIME_BINDINGS_UNAVAILABLE','No actual installed native start owner')
        client=ports.executor;rpc=getattr(client,'rpc',None)
        if (client,rpc,getattr(rpc,'path',None),getattr(rpc,'protocol',None),getattr(rpc,'peer_uid',None),
                getattr(rpc,'socket_mode',None),getattr(rpc,'session_id',None),getattr(rpc,'capability',None))!=expected:
            raise ResearchError('executor_preparation_authorization','Original protected native start carrier changed')
        if rpc.session_id!=ports.session['session_id'] or rpc.capability!=ports.session['capability']:
            raise ResearchError('executor_preparation_authorization','Original protected native session changed')
        return client

    async def _await_start(self,context,*,dispatch=None):
        from .invocation_start import start
        return await start(self,context,dispatch=dispatch)

    def _require_check_assets(self,contract):
        template=self.store.read_record(contract['template_ref'])
        if (template.get('capsule_ref')!=contract['bindings'][0]['declaration_ref']
            or template.get('checking_profile_ref')!=contract['checking_profile_ref']
            or 'check_bundle_ref' not in template):
            raise ResearchError('check_binding','Exact prepared checking assets differ from the frozen subnode')
        if contract['bindings'][0]['role']!='verifier':
            self.check_assets.require(template['check_bundle_ref'],contract['checking_profile_ref'])
            return
        # The verifier's own mechanical bundle/profile is a different admitted
        # pair from the subject profile that supplies its semantic criteria.
        own_profile=template.get('capsule_checking_profile_ref')
        subject_bundle=template.get('subject_check_bundle_ref')
        if own_profile is None or subject_bundle is None:
            raise ResearchError('check_binding','Verifier template omits its own or subject checking pair')
        validate('Ref',own_profile);validate('Ref',subject_bundle)
        parent=self.store.read_record(contract['node_contract_ref'],contract_id='node-execution-contract')
        subjects=[item for item in parent['subnodes'] if item['role']=='work'
            and item['subnode_id']==template.get('subject_subnode_id')]
        if (len(subjects)!=1 or template.get('role')!='verifier'
                or template.get('depends_on')!=[subjects[0]['subnode_id']]):
            raise ResearchError('check_binding','Verifier checking pair has no exact original work predecessor')
        subject=self.store.read_record(subjects[0]['template_ref'])
        if (subject.get('capsule_ref')!=subjects[0]['capsule_ref']
                or subject.get('role')!='work'
                or subject.get('check_bundle_ref')!=subject_bundle
                or subject.get('checking_profile_ref')!=contract['checking_profile_ref']):
            raise ResearchError('check_binding','Verifier subject checking pair differs from its frozen work predecessor')
        for selected,bundle_ref,profile_ref in ((template,template['check_bundle_ref'],own_profile),
                (subject,subject_bundle,contract['checking_profile_ref'])):
            admission=self.store.read_record(selected['admission_ref'],contract_id='library-admission')
            bundle=self.store.read_record(bundle_ref,contract_id='check-bundle')
            profile=self.store.read_record(profile_ref,contract_id='checking-profile')
            pins={'check_bundle_id':bundle['bundle_id'],'check_bundle_version':bundle['version'],
                'check_bundle_sha256':bundle_ref['sha256'],'checking_profile_id':profile['profile_id'],
                'checking_profile_version':profile['version'],'checking_profile_sha256':profile_ref['sha256']}
            if (self.store.record_kind(selected['admission_ref'])!='library-admission'
                    or admission['status']!='admitted' or admission['candidate_ref']!=selected['capsule_ref']
                    or admission['check_pins']!=pins):
                raise ResearchError('check_binding','Verifier checking pair differs from its exact original Capsule admission')
            self.check_assets.require(bundle_ref,profile_ref)

    def _decode_inputs(self,contract):
        values={}
        for port in contract['inputs']:
            decoded=[]
            for ref in port['artifact_refs']:
                raw=self.store.read_blob(ref)
                if port['contract_id'] in {'opaque-bytes','text/plain','poc-artifact-bundle','poc-artifact-bundle:field-contract:1','research-report','research-report:field-contract:1'}:value=raw
                else:
                    try:value=json.loads(raw.decode('utf-8'))
                    except (UnicodeError,ValueError) as exc:raise ResearchError('input_invalid','Input is not its declared JSON contract') from exc
                    validate(port['contract_id'],value)
                decoded.append(value)
            if port['required'] and not decoded:raise ResearchError('input_binding','Required input is unbound')
            values[port['name']]=decoded[0] if len(decoded)==1 else decoded
        if [r for p in contract['inputs'] for r in p['artifact_refs']]!=contract['input_refs']:
            raise ResearchError('input_binding','Input inventory differs from named exact bindings')
        return values

    async def run(self,contract_ref,check_plan_ref,*,bundle_id,verifier_contract_refs=None,dispatch=None)->RunResult:
        existing=set(self._executions);stop=None
        try:
            return await self._run(contract_ref,check_plan_ref,bundle_id=bundle_id,verifier_contract_refs=verifier_contract_refs,dispatch=dispatch)
        except BaseException as exc:
            stop=exc;raise
        finally:
            for execution_id in set(self._executions)-existing:
                execution=self._executions[execution_id]
                if execution.get('phase')!='active':
                    if stop is not None and execution.get('phase')=='prepared':
                        execution.update(closed=True,phase='start_failed')
                        self.store.finish_attempt(execution['contract'],'interrupted')
                    continue
                if execution.get('observation_ref') is None and stop is not None:
                    execution['closed']=True
                    reason='cancelled' if isinstance(stop,asyncio.CancelledError) else getattr(stop,'code',type(stop).__name__)
                    observed=await _capture_off_loop(self._observation,execution,execution['contract_ref'],execution.get('started_at',utc_now()),{},
                        'interrupted' if isinstance(stop,asyncio.CancelledError) else 'failed',reason)
                    execution['observation_ref']=self.store.put_record('invocation-observation',observed,scope=execution['contract'])
                if execution.get('observation_ref') is not None:
                    try:await _capture_off_loop(self._complete_execution,execution,stop)
                    except Exception as exc:
                        # Completed lines and derived hooks never grant release.
                        # Their failure is retained as missing optional evidence.
                        logging.getLogger(__name__).warning('Capsule record publication unavailable: %s',type(exc).__name__)
                        try:self.store.append_record('capture-hook-failure',{'id':'capture-failure:'+uuid.uuid4().hex,
                            'run_id':execution['contract']['run_id'],'node_id':execution['contract']['node_id'],
                            'observation_ref':execution['observation_ref'],'item':'capsule_run_record','reason':type(exc).__name__})
                        except Exception:pass

    async def _run(self,contract_ref,check_plan_ref,*,bundle_id,verifier_contract_refs=None,dispatch=None)->RunResult:
        contract=self.store.read_record(contract_ref,contract_id='subnode-execution-contract')
        plan=self.store.read_record(check_plan_ref,contract_id='bound-check-plan')
        if plan['contract_ref']!=contract_ref or plan['node_contract_ref']!=contract['node_contract_ref'] or plan['subnode_id']!=contract['subnode_id']:
            raise ResearchError('check_binding','Bound checks do not govern this exact subnode')
        self._require_check_assets(contract)
        self._require_child_authority(contract_ref,contract)
        inputs=self._decode_inputs(contract)
        if dispatch is not None:self.store.prepare_dispatch(contract,dispatch)
        ctx=self._start_context(contract_ref,contract,inputs)
        execution=self._executions[ctx.execution_id];declaration=execution['declaration'];identity=declaration['identity']
        handler,pinned=self.registry.resolve(identity['name'],identity['version_label'],contract['bindings'][0]['declaration_ref']['sha256'])
        if pinned and tuple(contract['bindings'][0]['implementation_refs'])!=pinned:raise ResearchError('carrier_pin_mismatch','Installed code closure differs from binding')
        await self._await_start(ctx,dispatch=dispatch)
        outputs={};output_refs={};outcome='success';failure=None;started=utc_now();execution['started_at']=started
        try:
            call=handler.execute if hasattr(handler,'execute') else handler
            pending=call(ctx,inputs)
            produced=await asyncio.wait_for(pending,max(0,execution['deadline']-time.monotonic())) if inspect.isawaitable(pending) else pending
            if not isinstance(produced,dict):raise ResearchError('output_invalid','Carrier must return named produced artifacts')
            allowed={p['name']:p for p in contract['outputs']}
            if set(produced)-set(allowed) or any(p['required'] and p['name'] not in produced for p in allowed.values()):raise ResearchError('output_invalid','Output ports differ from the frozen contract')
            for port,item in produced.items():
                if not isinstance(item,ProducedArtifact):raise ResearchError('output_invalid','Carrier returned an uncaptured output representation')
                raw=item.data if isinstance(item.data,bytes) else (item.data.encode('utf-8') if isinstance(item.data,str) else json_bytes(item.data))
                ref=self.store.put_blob(raw,media_type=item.media_type)
                self.store.mark_evaluation_material(contract['run_id'],ref)
                if item.ref is not None and (item.ref!=ref or self.store.read_blob(item.ref)!=raw):raise ResearchError('integrity_fault','Produced Ref differs from captured exact bytes')
                output_refs[port]=ref
                self.store.append_record('captured-output',{'id':'captured-output:'+uuid.uuid4().hex,
                    **{key:contract[key] for key in ('run_id','node_id','subnode_id','attempt_id')},
                    'invocation_id':execution['invocation_id'],'output_port':port,'artifact_ref':ref,
                    'media_type':item.media_type,'contract_id':allowed[port]['contract_id']})
                # Raw bundle/report contracts are checked via deterministic pinned
                # projections in the scientific bundle; bytes are never rewritten.
                if item.media_type in {'application/zip','text/markdown'}:outputs[port]=raw
                else:
                    try:value=json.loads(raw.decode('utf-8'))
                    except (UnicodeError,ValueError) as exc:raise ResearchError('output_invalid','Output is not declared JSON') from exc
                    validate(allowed[port]['contract_id'],value);outputs[port]=value
        except asyncio.TimeoutError:
            outcome='budget_exhausted';failure='wall_clock_exhausted'
        except ResearchError as exc:
            outcome='budget_exhausted' if exc.code=='budget_exhausted' else 'failed';failure=exc.code
        except Exception as exc:
            failure='integrity_fault' if isinstance(exc,PlatformIntegrityError) else getattr(exc,'code',type(exc).__name__)
            outcome='budget_exhausted' if failure in {'budget_exceeded','budget_exhausted'} else 'interrupted' if failure=='cancelled' else 'failed'
        finally:
            execution['closed']=True
        # Only actual canonical returned work enters checking. Preparation and
        # the separately owned private measurement path confer no node state.
        if execution.get('evaluation_owner') is None:
            self.store.mark_node_evaluating(contract_ref,contract,execution['preparation_ref'],
                invocation_id=execution['invocation_id'],execution_id=ctx.execution_id)
        original_output_refs=copy.deepcopy(output_refs)
        if self.faults is not None and not failure:
            selected=await self.faults.after_capture({'run_id':contract['run_id'],'contract_ref':contract_ref,'output_refs':copy.deepcopy(output_refs)})
            if not isinstance(selected,dict) or set(selected)!={'output_refs'} or set(selected['output_refs'])!=set(output_refs):
                raise ResearchError('fault_integrity','Protected fault hook returned an invalid output inventory')
            output_refs=copy.deepcopy(selected['output_refs'])
            for ref in output_refs.values():self.store.read_blob(ref)
        observation=await _capture_off_loop(self._observation,execution,contract_ref,started,original_output_refs,outcome,failure)
        observation_ref=self.store.put_record('invocation-observation',observation,scope=contract)
        execution['observation_ref']=observation_ref;execution['failure']=failure
        if failure:
            subjects=list(output_refs.values()) or [observation_ref]
            results=[{'check_id':key,'outcome':'FAIL','reason':failure,'evidence_refs':[observation_ref]} for key in plan['mandatory_deterministic']]
        else:
            self._require_check_assets(contract)
            subjects=list(output_refs.values())
            host_results=self._host_checks(contract_ref,contract,observation,observation_ref,effective_output_refs=output_refs)
            if output_refs!=original_output_refs:
                # The real foreign bytes are the check subject; the original raw
                # observation remains truthful. Identity fails before review.
                outputs=self._decode_outputs(contract,output_refs)
            checkctx=CheckContext(contract,self.store,inputs,outputs,output_refs,observation,tuple(host_results))
            results=await self.check_registry.run(plan,checkctx,bundle_id=bundle_id)
        result={'schema_version':'1.0.0','subject_ref':subjects[0],'check_plan_ref':check_plan_ref,'results':results}
        if len(subjects)>1:result['subject_refs']=subjects
        deterministic_ref=self.store.put_record('deterministic-check-result',result,record_id='checks:'+uuid.uuid4().hex,scope=contract)
        eligible=not failure and all(r['outcome']=='PASS' for r in results if r['check_id'] in plan['mandatory_deterministic'])
        # Producer readiness is advisory data. Its explicit blocking uncertainty
        # halts; it never grants release by itself.
        for value in outputs.values():
            if isinstance(value,dict) and (value.get('readiness',{}).get('status')=='needs_clarification' or any(x.get('blocking') for x in value.get('uncertainties',[])) or any(x.get('blocking') for x in value.get('unresolved_items',[]))):
                eligible=False;failure='blocking_uncertainty'
        assessments=[];decisions=[]
        if eligible:
            for port,ref in output_refs.items():
                assessment_ref=None;vctx=None;vobsref=None;verifier_check_ref=None;verifier_failure=None
                manifest={'schema_version':'2.0.0','id':'review:'+uuid.uuid4().hex,'subject_ref':ref,'contract_ref':contract_ref,
                    'check_plan_ref':check_plan_ref,'input_refs':contract['input_refs'],'deterministic_result_ref':deterministic_ref,
                    'criteria':plan['mandatory_semantic'],'observations':[observation_ref],'evidence_classes':['captured_input_and_output','invocation_observation'],
                    'node_contract_ref':contract['node_contract_ref'],'subnode_id':contract['subnode_id']}
                checking_profile=self.store.read_record(plan['profile_ref'],contract_id='checking-profile')
                review_evidence_ref=None
                if checking_profile.get('review_mode')=='task_sources_tier1_v1':
                    evidence=build_review_evidence(self.store,manifest,checking_profile)
                    review_evidence_ref=self.store.put_blob(json_bytes(evidence),media_type='application/json')
                    manifest['review_evidence_ref']=review_evidence_ref
                manifest_ref=self.store.put_record('review-context',manifest)
                if hasattr(verifier_contract_refs,'bind'):
                    verifier_ref=verifier_contract_refs.bind(port,ref,review_evidence_ref=review_evidence_ref)
                else:
                    verifier_ref=(verifier_contract_refs or {}).get(port)
                try:
                    if verifier_ref is None:raise ResearchError('verifier_unavailable','No separately budgeted verifier binding')
                    vcontract=self.store.read_record(verifier_ref,contract_id='subnode-execution-contract')
                    if vcontract['node_contract_ref']!=contract['node_contract_ref']:raise ResearchError('verifier_binding','Verifier belongs to another node')
                    if review_evidence_ref is not None and review_evidence_ref not in vcontract['input_refs']:
                        raise ResearchError('review_evidence_binding','Evidence projection is outside the separately budgeted verifier inputs')
                    self._require_child_authority(verifier_ref,vcontract)
                    vctx=self._start_context(verifier_ref,vcontract,{},call_function='verifier')
                    await self._await_start(vctx)
                    verifier_started=utc_now()
                    assessment_ref=await self.verifier.review(contract['bindings'][0]['declaration_ref'],ref,plan['profile_ref'],manifest_ref,port,vctx.model,
                        zip_output=contract_is(next(p for p in contract['outputs'] if p['name']==port)['contract_id'],'poc-artifact-bundle'),
                        review_evidence_ref=review_evidence_ref)
                    assessments.append(assessment_ref)
                except BaseException as exc:
                    verifier_failure='integrity_fault' if isinstance(exc,PlatformIntegrityError) else getattr(exc,'code',type(exc).__name__);failure=verifier_failure
                    if not isinstance(exc,Exception):raise
                finally:
                    if vctx is not None and self._executions[vctx.execution_id].get('phase')=='active':
                        self._executions[vctx.execution_id]['closed']=True
                        vobs=await _capture_off_loop(self._observation,self._executions[vctx.execution_id],verifier_ref,verifier_started,{'verifier_assessment':assessment_ref} if assessment_ref else {},'failed' if verifier_failure else 'success',verifier_failure)
                        vobsref=self.store.put_record('invocation-observation',vobs,scope=vcontract)
                        self._executions[vctx.execution_id]['observation_ref']=vobsref
                        self._executions[vctx.execution_id]['failure']=verifier_failure
                        verifier_check_ref=self._check_verifier(verifier_ref,vcontract,vobs,vobsref,assessment_ref,contract,plan,port,ref)
                        if any(row['outcome']!='PASS' for row in self.store.read_record(verifier_check_ref)['results']):failure='verifier_check_failed'
                        self.store.finish_attempt(vcontract,'rejected' if failure else 'accepted')
                if vobsref is None:
                    raise ResearchError(verifier_failure or 'verifier_unavailable','Independent reviewer never started')
                invocations=[observation_ref]+([vobsref] if vobsref is not None else [])
                decisions.append(self.gate.decide(contract_ref,check_plan_ref,deterministic_ref,assessment_ref,[ref],invocations,output_port=port,halt_reason=failure,verifier_check_ref=verifier_check_ref))
        else:
            decisions.append(self.gate.decide(contract_ref,check_plan_ref,deterministic_ref,None,list(output_refs.values()),[observation_ref],halt_reason=failure or 'deterministic_check_failed'))
        accepted=bool(decisions) and all(self.store.read_record(ref)['action']=='advance' for ref in decisions)
        if accepted:
            self._require_check_assets(contract)
            self.store.commit_acceptance(contract['run_id'],contract['node_id'],contract['attempt_id'],output_refs,decisions,subnode_id=contract['subnode_id'])
        self.store.finish_attempt(contract,'accepted' if accepted else 'rejected')
        stop_ref=self._capture_protected_stop(contract_ref,contract,observation_ref,failure) if not accepted else None
        return RunResult(accepted,output_refs,tuple(decisions),deterministic_ref,observation_ref,tuple(assessments),'accepted' if accepted else outcome if outcome in {'failed','budget_exhausted'} else 'rejected',stop_ref)

    def _capture_protected_stop(self,contract_ref,contract,observation_ref,failure):
        """Keep actual protected stops outside the source CC stop-reason field.

        That source field is deliberately null when any output was captured.
        A partial output therefore cannot be used as the scheduler stop signal.
        """
        signals=[(failure,observation_ref)]
        for execution in self._executions.values():
            if (execution['contract']['node_contract_ref']==contract['node_contract_ref']
                    and execution.get('observation_ref') is not None):
                signals.append((execution.get('failure'),execution['observation_ref']))
        protected={'integrity_fault','security_fault','AUDIT_UNAVAILABLE','CONTAINMENT_UNCERTAIN'}
        reason,failed_ref=next(((why,ref) for why,ref in signals if why in protected),(None,None))
        if reason is None and any(why in {'budget_exhausted','budget_exceeded','wall_clock_exhausted'} for why,_ in signals):
            frozen=self._run_contexts.get(contract['run_id'])
            if frozen is not None:
                with self.store._lock:
                    used=self.store.connection.execute('SELECT COUNT(*) FROM model_calls WHERE run_id=?',(contract['run_id'],)).fetchone()[0]
                started = self._run_started.get(contract['run_id'])
                if ((started is not None and time.monotonic()-started>=frozen['run_limits']['time_s'])
                        or used>=frozen['run_limits']['model_calls']):
                    reason,failed_ref='run_budget_exhausted',observation_ref
        if reason is None:return None
        # The executor masks its own fault from the RPC reply. Its protected
        # fault record is the only place the real cause survives, so carry it
        # into the stop receipt instead of leaving a bare integrity_fault.
        fault=None
        if reason=='integrity_fault':
            rows=[row['record'] for row in self.store.iter_records(run_id=contract['run_id'],kinds=('executor-rpc-fault',))
                  if row['record'].get('node_id')==contract['node_id'] and row['record'].get('attempt_id')==contract['attempt_id']]
            if rows:
                last=rows[-1]
                fault={key:last.get(key) for key in ('operation','exception_class','code','frame')}
                if isinstance(last.get('cause_chain'),list) and last['cause_chain']:fault['cause_chain']=last['cause_chain']
        return self.store.append_record('protected-invocation-stop',{'schema':'ai4r-protected-invocation-stop:1',
            'id':'protected-stop:'+uuid.uuid4().hex,**{key:contract[key] for key in ('run_id','node_id','attempt_id')},
            'contract_ref':contract_ref,'worker_observation_ref':observation_ref,'failure_observation_ref':failed_ref,
            'reason_code':reason,'executor_fault':fault,'recorded_at':utc_now()})

    def _complete_execution(self,execution,stop=None):
        raw_ref=execution['observation_ref'];raw=self.store.read_record(raw_ref,contract_id='invocation-observation')
        if self.evidence is not None:
            try:self.evidence.capture_invocation_end(raw_ref)
            except Exception as error:self.evidence.missing(raw['run_id'],'invocation-end:'+raw['id'],'Optional original-byte file copy failed: '+type(error).__name__)
        all_rows=list(self.store.iter_records(run_id=raw['run_id'],
            kinds=('gate-decision','bound-check-plan','deterministic-check-result')))
        chosen=[row for row in all_rows if row['kind']=='gate-decision' and raw_ref in row['record']['invocation_refs'] and row['record']['scope_kind']=='subnode']
        decision_refs=[row['ref'] for row in chosen];decisions=[row['record'] for row in chosen]
        plans=[row for row in all_rows if row['kind']=='bound-check-plan' and row['record']['contract_ref']==raw['contract_ref']]
        plan_refs=[row['ref'] for row in plans]
        results=[row for row in all_rows if row['kind']=='deterministic-check-result' and row['record']['check_plan_ref'] in plan_refs]
        assessment_refs=[]
        if execution['call_function']!='verifier':
            for decision in decisions:
                ref=decision['assessment_ref']
                if ref is not None and ref not in assessment_refs:assessment_refs.append(ref)
        assessment_ref=None
        if len(assessment_refs)==1:assessment_ref=assessment_refs[0]
        elif assessment_refs:
            # The singular field points to all actual raw review outputs for
            # a multi-output invocation; no new combined verdict is invented.
            assessment_ref=self.store.put_blob(b'\n'.join(self.store.read_blob(ref) for ref in assessment_refs)+b'\n',media_type='application/x-ndjson')
        failed_inputs=set();input_names={port['name'] for port in execution['contract']['inputs']}
        for plan in plans:
            template=self.store.read_record(execution['contract']['template_ref'])
            bundle=self.store.read_record(template['check_bundle_ref'],contract_id='check-bundle')
            failed_inputs.update(check['check_id'] for check in bundle['checks'] if check.get('target_port') in input_names)
        input_invalid=any(item['check_id'] in failed_inputs and item['outcome']!='PASS' for row in results for item in row['record']['results'])
        negative=False
        if raw['cc_name']=='research.evaluation' and decisions and all(item['action']=='advance' for item in decisions):
            for ref in raw['output_refs']:
                value=self.store.read_record(ref)
                if 'classification' in value and value['classification']!='PASS':negative=True
        reason=execution.get('failure') or (getattr(stop,'code',type(stop).__name__) if stop is not None else None)
        platform=reason in {'provider_error','auth_failed','rate_limited','network_error','model_unavailable','DELIVERY_UNKNOWN','RUNTIME_DISCONNECTED','integrity_fault','AUDIT_UNAVAILABLE','CONTAINMENT_UNCERTAIN'}
        platform=platform or bool(reason and reason.startswith(('EXECUTOR_','PRIVATE_RPC_','ENVIRONMENT_','BUILDER_RUNTIME_','BUILDER_ACTUAL_')))
        completed=complete_observation(raw,decisions=decisions,check_refs=[row['ref'] for row in results],assessment_ref=assessment_ref,
            platform_error=platform,input_invalid=input_invalid,scientific_negative=negative,error_text=reason)
        return self.store.publish_capsule_record(raw_ref,completed,decision_refs=decision_refs,assessment_refs=assessment_refs)

    def capture_dispatch(self,parent_ref,decision_ref,results,*,started_at,elapsed_s,phase,run_plan_ref=None,cc=None,check_pins=None):
        parent=self.store.read_record(parent_ref,contract_id='node-execution-contract');decision=self.store.read_record(decision_ref,contract_id='gate-decision')
        refs=list(dict((ref['id'],ref) for result in results for decision in result.decision_refs for ref in self.store.read_record(decision)['invocation_refs']).values()) if results else []
        observations=[self.store.read_record(ref,contract_id='invocation-observation') for ref in refs]
        failures={result.outcome for result in results};accepted=decision['action']=='advance'
        outcome='accepted' if accepted else 'budget_exhausted' if 'budget_exhausted' in failures else 'failed' if 'failed' in failures else 'rejected'
        if any(result.protected_stop_ref is not None for result in results) or any(v['failure_reason_code'] in {'integrity_fault','security_fault','AUDIT_UNAVAILABLE'} for v in observations):outcome='halted'
        gate=decision_ref if outcome not in {'failed','budget_exhausted','interrupted'} else None
        counts=[v['model_calls'] for v in observations]
        record={'schema_version':'2.0.0','id':'dispatch_'+uuid.uuid4().hex,'run_id':parent['run_id'],'attempt_id':parent['attempt_id'],
            'phase':phase,'run_plan_ref':run_plan_ref,'node_id':parent['node_id'],'cc':cc,'node_contract_ref':parent_ref,
            'bound_input_refs':[{'name':p['name'],'ref':ref} for p in parent['inputs'] for ref in p['artifact_refs']],
            'check_pins':check_pins,'check_plan_ref':decision['check_plan_ref'],'attempt':1,'started_at':started_at,'ended_at':utc_now(),
            'outcome':outcome,'gate_decision_ref':gate,'output_gate_decision_refs':decision['internal_decision_refs'] if gate else [],
            'output_refs':decision['accepted_refs'] if accepted else [],'elapsed_s':elapsed_s,
            'model_calls_used':sum(counts) if counts and all(v is not None for v in counts) else None}
        self.store.put_record('dispatch-record',record,scope=record)
        return record

    def dispatch_timing(self,parent_ref):
        executions=[value for value in self._executions.values()
            if value['contract']['node_contract_ref']==parent_ref and value.get('actual_started_at') is not None]
        if not executions:return None
        first=min(executions,key=lambda value:value['actual_started_monotonic_s'])
        return {'started_at':first['actual_started_at'],'started_monotonic_s':first['actual_started_monotonic_s']}

    def prepare_node_check_plan(self,parent_ref):
        """Capture the real node plan once, before execution or finalization."""
        key=(parent_ref['id'],parent_ref['sha256'])
        parent=self.store.read_record(parent_ref,contract_id='node-execution-contract')
        if key in self._node_check_plans:
            ref=self._node_check_plans[key]
            plan=self.store.read_record(ref,contract_id='bound-check-plan')
            if (plan['contract_ref']!=parent_ref or plan['node_contract_ref']!=parent_ref
                    or plan['input_refs']!=parent['input_refs'] or plan['profile_ref']!=parent['checking_profile_ref']
                    or plan['policy_ref']!=parent['policy_ref'] or plan['subnode_id'] is not None):
                raise ResearchError('check_binding','Original node finalization plan changed')
            return ref
        profile=self.store.read_record(parent['checking_profile_ref'],contract_id='node-finalization-profile')
        if profile['mandatory_deterministic']!=['internal_acceptance','external_output','aggregate_limits']:
            raise ResearchError('check_binding','Original node finalization coverage differs')
        for assignment in parent['subnodes']:
            template=self.store.read_record(assignment['template_ref'])
            self.store.read_blob(template['check_bundle_ref']);self.store.read_blob(template['checking_profile_ref'])
        plan={'schema_version':'2.0.0','id':'node_checks:'+uuid.uuid4().hex,'contract_ref':parent_ref,'node_contract_ref':parent_ref,
            'input_refs':parent['input_refs'],'profile_ref':parent['checking_profile_ref'],'policy_ref':parent['policy_ref'],
            'mandatory_deterministic':profile['mandatory_deterministic'],'mandatory_semantic':[],
            'runner_refs':[self.store.put_blob(Path(__file__).read_bytes(),media_type='text/x-python')],'subnode_id':None}
        ref=self.store.put_record('bound-check-plan',plan,scope=parent)
        self._node_check_plans[key]=ref
        return ref

    def capture_start_failure(self,parent_ref,*,started_at,elapsed_s,error,phase,run_plan_ref=None,cc=None,check_pins=None):
        """A failed Scheduler interval is not a fabricated worker invocation."""
        parent=self.store.read_record(parent_ref,contract_id='node-execution-contract')
        check_plan_ref=self.prepare_node_check_plan(parent_ref)
        outcome='interrupted' if isinstance(error,asyncio.CancelledError) else 'budget_exhausted' if getattr(error,'code',None)=='budget_exhausted' else 'failed'
        record={'schema_version':'2.0.0','id':'dispatch_'+uuid.uuid4().hex,'run_id':parent['run_id'],
            'attempt_id':parent['attempt_id'],'phase':phase,'run_plan_ref':run_plan_ref,'node_id':parent['node_id'],
            'cc':cc,'node_contract_ref':parent_ref,
            'bound_input_refs':[{'name':port['name'],'ref':ref} for port in parent['inputs'] for ref in port['artifact_refs']],
            'check_pins':check_pins,'check_plan_ref':check_plan_ref,'attempt':1,'started_at':started_at,
            'ended_at':None if outcome=='interrupted' else utc_now(),'outcome':outcome,
            'gate_decision_ref':None,'output_gate_decision_refs':[],'output_refs':[],
            'elapsed_s':elapsed_s,'model_calls_used':None}
        dispatch_ref=self.store.put_record('dispatch-record',record,scope=record)
        # The closed dispatch record has no cause field. Keep class, code and a
        # constant reason identifier (e.g. ExecutorBlocked WHOLE_ATTEMPT_RESOURCE_HELD_OR_UNKNOWN),
        # never a message, so a refused start says why.
        code=getattr(error,'code',None);reason=getattr(error,'reason',None)
        if outcome!='interrupted':self.store.append_record('start-failure-cause',{'id':'start-failure-cause:'+uuid.uuid4().hex,
            'run_id':parent['run_id'],'node_id':parent['node_id'],'attempt_id':parent['attempt_id'],'dispatch_ref':dispatch_ref,
            'exception_class':type(error).__name__,
            'code':code if isinstance(code,str) and code.replace('_','').isalnum() and len(code)<=64 else None,
            'reason':reason if isinstance(reason,str) and reason.replace('_','').isalnum() and len(reason)<=64 else None,
            'recorded_at':utc_now()})
        return dispatch_ref

    def _check_verifier(self,verifier_ref,vcontract,observation,observation_ref,assessment_ref,subject_contract,subject_plan,port,output_ref):
        plans=[e for e in self.store.iter_records(run_id=vcontract['run_id'],kinds=('bound-check-plan',)) if e['record']['contract_ref']==verifier_ref]
        if len(plans)!=1:raise ResearchError('verifier_check_binding','Verifier needs one exact protected check plan')
        check_plan_ref=plans[0]['ref'];vplan=plans[0]['record']
        profile=self.store.read_record(subject_contract['checking_profile_ref'],contract_id='checking-profile')
        criteria=[c for c in profile['criteria'] if c['target_port'] in (None,port)]
        predicates=verifier_predicates(self.store,vcontract,assessment_ref,criteria,
            subject_contract['bindings'][0]['declaration_ref'],output_ref)
        rows=self._host_checks(verifier_ref,vcontract,observation,observation_ref)
        known={row['check_id']:row for row in rows}
        for key in vplan['mandatory_deterministic']:
            if key not in known:known[key]={'check_id':key,'outcome':'PASS' if predicates.get(key) is True else 'FAIL',
                'reason':'Independent verifier mechanical predicate '+key,'evidence_refs':[observation_ref,*([assessment_ref] if assessment_ref else [])]}
        record={'schema_version':'1.0.0','subject_ref':assessment_ref or observation_ref,'check_plan_ref':check_plan_ref,
                'results':[known[key] for key in vplan['mandatory_deterministic']]}
        return self.store.put_record('deterministic-check-result',record,scope=vcontract)

    def _decode_outputs(self,contract,refs):
        values={}
        for port,ref in refs.items():
            raw=self.store.read_blob(ref)
            kind=next(p['contract_id'] for p in contract['outputs'] if p['name']==port)
            if contract_is(kind,'poc-artifact-bundle') or contract_is(kind,'research-report'):values[port]=raw
            else:
                try:values[port]=json.loads(raw.decode('utf-8'))
                except (ValueError,UnicodeError):values[port]=raw
        return values

    def _host_checks(self,contract_ref,contract,observation,observation_ref,*,effective_output_refs=None,validated_parent=None):
        binding=contract['bindings'][0]
        if validated_parent is not None:
            owner=self.resolve_evaluation_owner(run_id=contract['run_id'])
            if owner is None:raise ResearchError('evaluation_authority','Private host checks require a registered owner')
            parent=copy.deepcopy(validated_parent)
            if parent!=self.store.read_record(contract['node_contract_ref']):raise ResearchError('evaluation_authority','Private parent changed')
        else:parent=self.store.read_record(contract['node_contract_ref'],contract_id='node-execution-contract')
        admission=self.store.read_record(binding['admission_ref'],contract_id='library-admission')
        declared=self.store.read_record(binding['declaration_ref'],contract_id='capsule-declaration')
        authority=binding['effective_authority'];ceiling=parent['authority_ceiling']
        read_ceiling=list(ceiling['resource_reads'])
        # A parent owns its accepted internal outputs. Reading those through an
        # explicit dependency transfers data, never another CC's permissions.
        for assignment in (parent['subnodes'] if validated_parent is None else []):
            read_ceiling.extend(self.store.accepted_outputs(contract['run_id'],contract['node_id'],subnode_id=assignment['subnode_id']).values())
        if binding['role']=='verifier' and validated_parent is None:
            assignment=next(s for s in parent['subnodes'] if s['subnode_id']==contract['subnode_id'])
            subjects=set(assignment['depends_on'])
            read_ceiling.extend(s['capsule_ref'] for s in parent['subnodes'] if s['subnode_id'] in subjects and s['role']=='work')
            for envelope in self.store.iter_records(run_id=contract['run_id'],kinds=('invocation-observation',)):
                observed=envelope['record']
                if observed['node_contract_ref']==contract['node_contract_ref'] and observed['subnode_id'] in subjects:
                    read_ceiling.extend(observed['output_refs'])
            # Binding admitted review_evidence only as the exact host projection of
            # the subject's original inputs and passing Tier 1 (validate_child_authority).
            read_ceiling.extend(ref for port in contract['inputs'] if port['name']=='review_evidence' for ref in port['artifact_refs'])
        elif binding['role']=='verifier' and validated_parent is not None:
            # The exact registered projection grants only the original subject
            # declaration and selected original output. No source/global scan
            # can provide an additional private reviewer read capability.
            rows=[r for r in owner.captures(contract['request_ref'],'actual_contract') if r['capture_ref']==contract_ref]
            if len(rows)!=1:raise ResearchError('evaluation_authority','Private reviewer context is not request-owned')
            grant,child,_=owner.projection.load_execution(rows[0]['assignment_grant_ref'])
            if child!=contract or grant['contract_ref']!=contract_ref:raise ResearchError('evaluation_authority','Private reviewer projection differs')
            read_ceiling.extend(child['input_refs'])
        scoped=all(value in (read_ceiling if key=='resource_reads' else ceiling[key]) for key in ('network_allowlist','resource_reads','write_roots','tools') for value in authority[key])
        scoped=scoped and (ceiling['network']=='allowlist' or authority['network']=='none')
        scoped=scoped and (declared['needs']['network']['mode']=='allowlist' or authority['network']=='none')
        limited=observation['duration_s'] is not None and observation['duration_s']<=min(contract['subnode_limits']['time_s'],binding['limits']['time_s'])
        # A granted transient retry is an explicit extra call for this invocation.
        retried=transient_retries(self.store,contract['run_id'],subnode_id=contract['subnode_id'],attempt_id=contract['attempt_id'])
        limited=limited and observation['model_calls'] is not None and observation['model_calls']<=min(contract['subnode_limits']['model_calls'],binding['limits']['model_calls'])+retried
        identified=admission['status']=='admitted' and admission['candidate_ref']==binding['declaration_ref'] and admission['cc']['declaration_sha256']==binding['declaration_ref']['sha256']
        identity=declared['identity']
        expected_identity={**{key:contract[key] for key in ('run_id','node_id','subnode_id','attempt_id','node_contract_ref','input_refs')},
            'contract_ref':contract_ref,'binding_id':binding['id'],'cc_name':identity['name'],'cc_version':identity['version_label'],
            'declaration_sha256':binding['declaration_ref']['sha256'],'body_files_sha256':body_files_sha256(identity['body'])}
        identified=identified and all(observation.get(key)==value for key,value in expected_identity.items())
        identified=identified and admission['cc']['cc_name']==identity['name'] and admission['cc']['cc_version']==identity['version_label']
        if effective_output_refs is not None:
            captured=[r['record'] for r in self.store.iter_records(run_id=contract['run_id'],kinds=('captured-output',))
                if r['record'].get('invocation_id')==self._executions[next(k for k,v in self._executions.items() if v.get('observation_ref')==observation_ref)]['invocation_id']]
            identified=identified and list(effective_output_refs.values())==observation['output_refs'] and all(
                len([r for r in captured if r['output_port']==port and r['artifact_ref']==ref])==1 for port,ref in effective_output_refs.items())
        return [{'check_id':key,'outcome':'PASS' if okay else 'FAIL','reason':description,'evidence_refs':[contract_ref,observation_ref]}
                for key,okay,description in [('host_contract',True,'Exact critical contract and input/output inventory validated before execution'),
                    ('host_identity',identified,'Pinned admission/declaration/implementation identity matches protected capture'),
                    ('host_limits',limited,'Observed work stays inside independently frozen invocation/subnode limits'),
                    ('host_authority',scoped,'Effective authority is a subset of the node and selected declaration, without pooling')]]

    async def finalize_node(self,parent_ref,results,output_refs):
        parent=self.store.read_record(parent_ref,contract_id='node-execution-contract')
        internal=[ref for result in results for ref in result.decision_refs]
        observations=[observation for decision in internal for observation in self.store.read_record(decision)['invocation_refs']]
        observations=list({(r['id'],r['sha256']):r for r in observations}.values())
        values=[self.store.read_record(ref,contract_id='invocation-observation') for ref in observations]
        coverage=set(output_refs)==set(parent['required_outputs'])
        required={s['subnode_id'] for s in parent['subnodes'] if s['required']}
        observed={v['subnode_id'] for v in values}
        valid=bool(results) and all(result.accepted for result in results) and required.issubset(observed)
        duration=sum(v['duration_s'] for v in values if v['duration_s'] is not None)
        counts=[v['model_calls'] for v in values]
        limits=parent['node_limits']
        routing_starts = [row for row in self.store.iter_records(run_id=parent['run_id'], kinds=('model-call-start',))
            if row['record'].get('contract_ref') and self.store.read_record(row['record']['contract_ref']).get('node_contract_ref') == parent_ref
            and self.store.read_record(row['record']['call_claim_ref']).get('purpose') == 'routing_selection']
        allowance = node_routing_allowance(self.store, parent)
        retried = transient_retries(self.store, parent['run_id'], node_id=parent['node_id'])
        within=(all(c is not None for c in counts) and sum(counts)<=limits['model_calls']+retried
            and len(routing_starts)<=allowance and sum(counts)+len(routing_starts)<=limits['model_calls']+allowance+retried
            and duration<=limits['time_s'])
        if allowance:
            self.store.append_record('node-routing-budget', {'id':'node-routing-budget:'+uuid.uuid4().hex,
                'run_id':parent['run_id'], 'node_id':parent['node_id'], 'node_contract_ref':parent_ref,
                'routing_policy':dict(routing_policy(self.store, parent['run_id'])['routing_policy']), 'worker_and_verifier_ceiling':limits['model_calls'],
                'routing_call_ceiling':allowance, 'aggregate_call_ceiling':limits['model_calls']+allowance,
                'routing_calls_started':len(routing_starts), 'recorded_at':utc_now()})
        planref=self.prepare_node_check_plan(parent_ref)
        checkrows=[{'check_id':key,'outcome':'PASS' if okay else 'FAIL','reason':reason,'evidence_refs':observations+internal}
                   for key,okay,reason in [('internal_acceptance',valid,'Every required work output independently advanced'),
                       ('external_output',coverage,'External output inventory equals the frozen parent'),('aggregate_limits',within,'Observed aggregate time and call ceilings include checking')]]
        refs=list(output_refs.values())
        subject=refs[0] if refs else (observations[0] if observations else parent_ref)
        checked={'schema_version':'1.0.0','subject_ref':subject,'check_plan_ref':planref,'results':checkrows}
        if len(refs)>1:checked['subject_refs']=refs
        checkedref=self.store.put_record('deterministic-check-result',checked,scope=parent)
        assessment=None
        for decisionref in internal:
            decision=self.store.read_record(decisionref)
            if refs and refs[0] in decision['output_refs']:assessment=decision['assessment_ref'];break
        decision=self.gate.decide(parent_ref,planref,checkedref,assessment,refs,observations,
            scope_kind='node',internal_decision_refs=internal,halt_reason=None if valid and coverage and within else 'node_obligation_failed',persist=False)
        if decision['action']=='advance':
            deadline=min(self._run_started[parent['run_id']]+self._run_contexts[parent['run_id']]['run_limits']['time_s'],
                self._node_started[(parent['run_id'],parent['node_id'])]+parent['node_limits']['time_s'])
            if self.faults is not None:
                await self.faults.before_advance({'run_id':parent['run_id'],'node_id':parent['node_id'],'contract_ref':parent_ref,
                    'decision_id':decision['id'],'deadline_monotonic_s':deadline})
            if self.store.cancellation_requested(parent['run_id']):raise ResearchError('cancelled','Cancelled node cannot persist an advancing verdict')
            if time.monotonic()>=deadline:raise ResearchError('budget_exhausted','Node expired before durable advancement')
            for result in results:
                observed=self.store.read_record(result.observation_ref)
                self._require_check_assets(self.store.read_record(observed['contract_ref']))
            decision['recorded_at']=utc_now()
        decisionref=self.store.put_record('gate-decision',decision)
        if self.evidence is not None:
            try:self.evidence.capture_node_gate(decisionref)
            except Exception as error:self.evidence.missing(parent['run_id'],'node-gate:'+decision['id'],'Optional original node-gate copy failed: '+type(error).__name__)
        if decision['action']=='advance':
            self.store.commit_acceptance(parent['run_id'],parent['node_id'],parent['attempt_id'],output_refs,[decisionref])
        else:self.store.set_node_state(parent['run_id'],parent['node_id'],'failed',attempt_id=parent['attempt_id'],reason='node_gate_halted')
        return decisionref

    def _observation(self,execution,contract_ref,started,outputs,outcome,failure):
        execution['observed_duration_s']=time.monotonic()-execution['actual_started_monotonic_s']
        c=execution['contract'];b=c['bindings'][0];identity=execution['declaration']['identity'];calls=execution['calls']
        if execution.get('evaluation_owner') is not None:
            owner=execution['evaluation_owner'];grant=owner.projection.load_execution(execution['evaluation_grant_ref'])[0]
            starts=[{'ref':e['capture_ref'],'record':self.store.read_record(e['capture_ref'])} for e in owner.captures(grant['request_ref'],'model_start')
                    if e['assignment_grant_ref']==execution['evaluation_grant_ref']]
        else:starts=[r for r in self.store.iter_records(run_id=c['run_id'],kinds=('model-call-start',)) if r['record'].get('invocation_id')==execution['invocation_id']]
        usage={'input_tokens':None,'output_tokens':None,'cost_amount':None,'currency':None,'unavailable_reasons':[]}
        for key in ('input_tokens','output_tokens'):
            observed=[r.get('usage',{}).get(key) for r in calls]
            if observed and all(v is not None for v in observed) and len(calls)==len(starts):usage[key]=sum(observed)
            else:usage['unavailable_reasons'].append(key+': complete aggregate not observed')
        amounts=[r.get('usage',{}).get('cost_amount') for r in calls];currencies={r.get('usage',{}).get('currency') for r in calls}
        if amounts and all(v is not None for v in amounts) and len(calls)==len(starts) and len(currencies)==1 and None not in currencies:
            usage.update(cost_amount=sum(amounts),currency=next(iter(currencies)))
        else:usage['unavailable_reasons'].extend(['cost_amount: complete comparable aggregate not observed','currency: complete comparable aggregate not observed'])
        model_identity=calls[-1].get('identity') if calls else None
        if not isinstance(model_identity,dict) or not {'requested','effective','basis'}.issubset(model_identity):model_identity={'requested':'not_observed','effective':None,'basis':'No provider-reported model identity'}
        traces=[r[key] for r in calls for key in ('call_ref','route_ref') if r.get(key)]
        evidence=getattr(self,'evidence',None)
        if evidence is not None and execution.get('evaluation_owner') is None:
            try:evidence.capture_invocation_traces(c,execution['invocation_id'])
            except Exception as error:evidence.missing(c['run_id'],'native-trace:'+execution['invocation_id'],'Original native trace file capture failed: '+type(error).__name__)
            # The observation schema bounds trace_refs at 64. Call and route refs
            # always stay (checks join on them); static capsule declaration/body
            # copies go last. Every file remains a run-evidence-file record.
            for ref in sorted(evidence.invocation_trace_refs(c),key=lambda r:'/capsule/' in r['id']):
                if ref not in traces and len(traces)<TRACE_REF_LIMIT:traces.append(ref)
        route_id=None;decision_source=None
        if starts:
            route_ref=starts[-1]['record'].get('route_ref')
            if route_ref:
                route=self.store.read_record(route_ref);route_id=route.get('route_id');decision_source=route.get('decision_source')
        model_injected=any(i['service_key']=='audited_model_bridge' for i in execution['declaration']['needs']['injects'])
        calls_observed=len(starts) if starts else len(calls) if calls and all(r.get('observed_runtime') is True for r in calls) else (None if model_injected else 0)
        return {'schema_version':'4.0.0' if decision_source=='user_api' else '3.0.0','id':'observation:'+uuid.uuid4().hex,**{k:c[k] for k in ('run_id','node_id','subnode_id','attempt_id')},
            'cc_name':identity['name'],'cc_version':identity['version_label'],'declaration_sha256':b['declaration_ref']['sha256'],
            'route_id':route_id,'measurement_status':'observed' if calls_observed is not None else 'unavailable','contract_ref':contract_ref,'binding_id':b['id'],'input_refs':c['input_refs'],
            'output_refs':list(outputs.values()),'model_identity':model_identity,'started_at':started,'ended_at':utc_now(),'outcome':outcome,
            'effects':[],'duration_s':execution['observed_duration_s'],'model_calls':calls_observed,'trace_refs':traces,
            'unavailable_reasons':['model_calls: bridge observation unavailable'] if calls_observed is None else [],'observed_runtime':True,'usage':usage,
            'node_contract_ref':c['node_contract_ref'],'body_files_sha256':body_files_sha256(identity['body']),
            'decision_source':decision_source,'failure_class':None,'failure_reason_code':failure if not outputs else None,
            'error_fingerprint':None,'check_result_refs':[],
            'verifier_assessment_ref':None,'human_answer_ref':None}
