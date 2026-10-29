"""Core-only resource composition for an independently owned isolated caller.

The caller injects its own native credential service, store, executor, actor and
exact captured bindings. This module has no RSI/controller/oracle dependency,
does not load factories from configuration and never performs installation.
"""
from __future__ import annotations

import copy
import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping
from .bootstrap_core import compose_core
from .bridge import GovernedBridge
from .contracts import ResearchError,validate


TRACE_KINDS=frozenset({'model-call','route-record','invocation-observation'})


def owned_model_evidence(store, call_ref):
    """Finite exact call evidence only; no account journal or arbitrary Ref walk."""
    if store.record_kind(call_ref) != 'model-call':
        raise ResearchError('capture_identity', 'Expected protected model call')
    call = store.read_record(call_ref)
    found = []; seen = set()
    def add(kind, ref):
        key = (ref['id'], ref['sha256'])
        if key not in seen:
            seen.add(key); found.append({'kind': kind, 'ref': ref, 'bytes': store.read_blob(ref)})
    for ref in call['evidence_refs']:
        kind = store.record_kind(ref)
        if kind in {'model-call-input', 'model-call-output', 'model-provider-observation'}:
            value = store.read_record(ref)
            if value.get('invocation_id') != call['invocation_id'] or value.get('call_id') not in (None, call['id']):
                raise ResearchError('capture_identity', 'Foreign model evidence')
            add(kind, ref); continue
        if kind != 'native-governed-trace':
            raise ResearchError('capture_identity', 'Unknown or private model evidence')
        summary = store.read_record(ref); scope = summary.get('scope', {})
        required = {'run_id','node_id','subnode_id','attempt_id','execution_id','invocation_id','call_id','contract_ref','model_call_start_ref'}
        if (set(summary) != {'schema','scope','status','event_refs'} or set(scope) != required
                or summary['schema'] != 'ai4r-native-governed-trace:1'
                or summary['status'] not in {'completed','failed','interrupted'}
                or not isinstance(summary['event_refs'], list)
                or scope['call_id'] != call['id']
                or any(scope[k] != call[k] for k in ('execution_id','invocation_id'))):
            raise ResearchError('capture_identity', 'Native summary differs from exact call')
        start = store.read_record(scope['model_call_start_ref'])
        if (store.record_kind(scope['model_call_start_ref']) != 'model-call-start'
                or any(start[k] != scope[k] for k in ('run_id','execution_id','invocation_id','call_id','contract_ref'))):
            raise ResearchError('capture_identity', 'Native trace start differs')
        contract = store.read_record(start['contract_ref'])
        if (store.record_kind(start['contract_ref']) not in {'subnode-execution-contract','isolated-evaluation-contract','isolated-evaluation-verifier-contract'}
                or any(contract[k] != scope[k] for k in ('run_id','node_id','subnode_id','attempt_id'))):
            raise ResearchError('capture_identity', 'Native trace contract differs')
        add(kind, ref)
        for sequence, event_ref in enumerate(summary['event_refs']):
            event = store.read_record(event_ref)
            if (store.record_kind(event_ref) != 'native-governed-trace-event'
                    or set(event) != {'schema','scope','sequence','direction','method','raw_ref'}
                    or event['schema'] != 'ai4r-native-governed-trace-event:1' or event['scope'] != scope
                    or type(event['sequence']) is not int or event['sequence'] != sequence
                    or event['direction'] not in {'in','out'} or not isinstance(event['method'], str)
                    or event['method'].startswith(('account/','login/','auth/'))):
                raise ResearchError('capture_identity', 'Native event is not call-owned')
            packet = json.loads(store.read_blob(event['raw_ref']))
            if not isinstance(packet, dict) or str(packet.get('method','')).startswith(('account/','login/','auth/')):
                raise ResearchError('capture_identity', 'Private native packet')
            add('native-governed-trace-event', event_ref)
            add('native-governed-packet', event['raw_ref'])
    return found



@dataclass(frozen=True)
class IsolatedResources:
    store: object
    operator: object
    composition: object
    bridge: GovernedBridge
    executor: object
    principal: object
    exact_binding_refs: Mapping

    @property
    def ready(self):return not self.composition.diagnostics
    @property
    def runner(self):return self.composition.runner
    @property
    def registry(self):return self.composition.registry
    @property
    def checks(self):return self.composition.checks
    def public_reader(self,ref):return self.store.read_blob(ref)
    def trace_reader(self,ref):
        matches=[e for e in self.store.iter_records(kinds=TRACE_KINDS) if e['ref']==ref]
        if len(matches)==1:
            return {'kind':matches[0]['kind'],'bytes':self.store.read_blob(ref)}
        for entry in self.store.iter_records(kinds=('model-call',)):
            for nested in owned_model_evidence(self.store,entry['ref']):
                if nested['ref']==ref:return {'kind':nested['kind'],'bytes':nested['bytes']}
        return None

    async def propose_once(self,contract_ref,prompt):
        """One normal claimed model invocation, without publishing acceptance.

        The caller supplies an already captured protected contract, not a model
        context or provider settings. Its run and frozen budget must exist in
        this isolated store. Unknown starts are never replayed.
        """
        from .state import utc_now
        contract=self.store.read_record(contract_ref,contract_id='subnode-execution-contract')
        if not isinstance(prompt,str):raise ResearchError('model_input','Text prompt required')
        context=None;failure=None;output={};started=utc_now()
        try:
            inputs=self.runner._decode_inputs(contract)
            context=self.runner._start_context(contract_ref,contract,inputs)
            await self.runner._await_start(context)
            started=utc_now()
            text=await asyncio.wait_for(context.model(prompt),max(0,self.runner._executions[context.execution_id]['deadline']-time.monotonic()))
            output['proposal_text']=self.store.put_blob(text.encode('utf8'),media_type='text/plain')
            return text
        except BaseException as exc:
            failure=getattr(exc,'code',type(exc).__name__)
            raise
        finally:
            if context is not None and self.runner._executions[context.execution_id].get('phase')=='active':
                execution=self.runner._executions[context.execution_id];execution['closed']=True
                observation=self.runner._observation(execution,contract_ref,started,output,'failed' if failure else 'success',failure)
                self.store.put_record('invocation-observation',observation,scope=contract)
                self.store.finish_attempt(contract,'interrupted' if failure else 'observed')


async def build_isolated_resources(*,store,operator,own_subscription_service,
        own_executor,principal,exact_binding_refs,isolation_root,forbidden_roots,
        readiness,upload_manager=None,connectors=None,profiles=None,router_port=None,
        providers=None,builder_launcher=None):
    root=Path(isolation_root).resolve(strict=True)
    denied=tuple(Path(p).resolve() for p in forbidden_roots)
    if not denied:raise ResearchError('isolation','Explicit forbidden live/account roots are required')
    paths=[store.root,store.blobs.root,store.db_path,store.input_root,
           own_subscription_service.root,own_executor.workspace_root]
    transport=getattr(own_subscription_service,'transport',None)
    if transport is not None and hasattr(transport,'root'):paths.append(transport.root)
    for value in paths:
        path=Path(value).resolve()
        if not path.is_relative_to(root) or any(path==p or path.is_relative_to(p) or p.is_relative_to(path) for p in denied):
            raise ResearchError('isolation','Isolated state, credential and work roots must be separate from live/account roots')
    bindings=copy.deepcopy(dict(exact_binding_refs))
    required={'configuration_ref','model_selection_profile_ref','deployment_ref','workspace_id','protected_options'}
    if set(bindings)!=required or not isinstance(bindings['protected_options'],dict):raise ResearchError('isolation','Exact protected binding set is incomplete')
    for key in ('configuration_ref','model_selection_profile_ref','deployment_ref'):store.read_blob(bindings[key])
    def not_composed(_):raise ResearchError('model_context_invalid','Isolated protected runner is not yet composed')
    trace_writer=getattr(own_subscription_service,'set_governed_trace_writer',None)
    if trace_writer is not None:trace_writer(store.append_record,store.put_blob)
    bridge=GovernedBridge(persist=store.append_record,authorize=not_composed,
        subscription_service=own_subscription_service,router_port=router_port,providers=providers,
        fixed_route_id=operator.codex_route_id,validate_record=validate,builder_launcher=builder_launcher,
        read_evidence=store.read_blob)
    composition=await compose_core(store=store,operator=operator,model=bridge,executor=own_executor,
        readiness=readiness,upload_manager=upload_manager,principal=principal,
        configuration_ref=bindings['configuration_ref'],model_selection_profile_ref=bindings['model_selection_profile_ref'],
        deployment_ref=bindings['deployment_ref'],workspace_id=bindings['workspace_id'],initialize=False,
        protected_options=bindings['protected_options'],connectors=connectors,profiles=profiles)
    bridge.authorize=composition.runner.authorize_model_context
    bridge.revalidate=composition.runner.authorize_model_dispatch
    return IsolatedResources(store,operator,composition,bridge,own_executor,principal,bindings)
