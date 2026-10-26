"""Protected model-call owner: authorize, persist, dispatch once, retain outcome.

M1-IF-001@r1. The injected authorizer reconstructs frozen facts and atomically
claims a model-call ordinal in the protected store. A producer never supplies
its own model authority, route or budget. Side selection is IPC-only.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import math
import os
import re
import secrets
import stat
import uuid
import json
import weakref
from datetime import datetime, timezone
from time import monotonic
from typing import Mapping
from pathlib import Path

from .router_client import (CodexRouter, RouteChoice, PlatformIntegrityError, MAX_IPC_FRAME_BYTES,
                            close_writer, encode_frame, peer_credentials, read_frame)
from .contracts import ResearchError


class BridgeError(RuntimeError):
    def __init__(self, code, *, call_ref=None, route_ref=None):
        super().__init__(code)
        self.code, self.call_ref, self.route_ref = code, call_ref, route_ref


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _resolved(value):
    return await value if inspect.isawaitable(value) else value


def _is_ref(value):
    return (isinstance(value, dict) and set(value) == {"id", "sha256"}
            and isinstance(value["id"], str) and bool(value["id"])
            and isinstance(value["sha256"], str) and re.fullmatch(r"[a-f0-9]{64}", value["sha256"]))


def observed_usage(value=None):
    value = value if isinstance(value, Mapping) else {}
    result = {}
    for field in ("input_tokens", "output_tokens"):
        number = value.get(field)
        result[field] = number if type(number) is int and number >= 0 else None
    amount = value.get("cost_amount")
    result["cost_amount"] = amount if type(amount) in (int, float) and math.isfinite(amount) and amount >= 0 else None
    currency = value.get("currency")
    result["currency"] = currency if isinstance(currency, str) and currency else None
    reported = value.get("unavailable_reasons", [])
    result["unavailable_reasons"] = [reason for reason in reported if isinstance(reason, str)] if isinstance(reported, list) else []
    for field in ("input_tokens", "output_tokens", "cost_amount", "currency"):
        if result[field] is None and not any(reason.startswith(field + ":") for reason in result["unavailable_reasons"]):
            result["unavailable_reasons"].append(field + ": not observed")
    return result


def failure_observation(error,requested_model):
    """Keep typed exposed telemetry, including cancellation timeout causes."""
    pending=[error];seen=set()
    while pending and len(seen)<8:
        current=pending.pop(0)
        if current is None or id(current) in seen:continue
        seen.add(id(current));value=getattr(current,'observation',None)
        if isinstance(value,Mapping) and value.get('observed_runtime') is True:
            identity=value.get('identity') if isinstance(value.get('identity'),Mapping) else {}
            effective=identity.get('effective');basis=identity.get('basis')
            request=value.get('provider_request_id')
            return {'identity':{'requested':requested_model,'effective':effective if isinstance(effective,str) and effective else None,
                    'basis':basis if isinstance(basis,str) and basis else 'effective model not observed'},
                    'usage':observed_usage(value.get('usage')),'provider_request_id':request if isinstance(request,str) and request else None,
                    'observed_runtime':True}
        pending.extend((getattr(current,'__cause__',None),getattr(current,'__context__',None)))
    return None


class GovernedBridge:
    def __init__(self, *, persist, authorize, subscription_service, router_port=None,
                 providers=None, fixed_route_id="codex-cli-default", validate_record=None,
                 builder_launcher=None, health_check=None, revalidate=None, read_evidence=None,
                 capture_native=None, manual_models=None, automatic_routing=None,
                 authorize_routing_selection=None):
        self.persist, self.authorize = persist, authorize
        self.subscription = subscription_service
        self.router = router_port or CodexRouter(fixed_route_id)
        self.providers = providers
        self.fixed_route_id = fixed_route_id
        self.validate_record = validate_record
        self.builder_launcher = builder_launcher
        self.health_check = health_check
        self.revalidate = revalidate
        self.read_evidence = read_evidence
        self.capture_native = capture_native
        self.manual_models = manual_models
        self.automatic_routing = automatic_routing
        self.authorize_routing_selection = authorize_routing_selection
        self._active_calls={};self._contained_runs=set();self._uncertain_runs=set()
        self._routing_locks=weakref.WeakValueDictionary()

    async def _require_capture(self):
        if self.health_check is not None and await _resolved(self.health_check()) is not True:
            raise BridgeError("AUDIT_UNAVAILABLE")

    async def _capture(self, kind, record, *, context=None):
        if self.validate_record and kind in {"route-record", "model-call"}:
            self.validate_record(kind, record)
        if context is not None and self.capture_native is not None:
            ref = await _resolved(self.capture_native(kind, record, context=context))
        else:
            ref = await _resolved(self.persist(kind, record))
        if not _is_ref(ref):
            raise BridgeError("AUDIT_UNAVAILABLE")
        return ref

    @staticmethod
    def _check_context(context):
        required = ("run_id", "node_id", "subnode_id", "attempt_id", "invocation_id", "execution_id", "call_id")
        if not isinstance(context, Mapping) or any(not isinstance(context.get(k), str) or not context[k] for k in required):
            raise PlatformIntegrityError("PROTECTED_CALL_CONTEXT_INVALID")
        if context.get("call_function") not in {"worker", "verifier", "planner", "routing_selection"}:
            raise PlatformIntegrityError("CALL_FUNCTION_INVALID")
        for field in ("model_selection_profile_ref", "deployment_ref", "call_claim_ref", "contract_ref"):
            if not _is_ref(context.get(field)):
                raise PlatformIntegrityError("PROTECTED_CALL_REFERENCE_INVALID")
        limit = context.get("limits", {}).get("time_s")
        if type(limit) not in (float, int) or not math.isfinite(limit) or not 0 < limit <= 600:
            raise PlatformIntegrityError("CALL_DEADLINE_INVALID")
        deadline=context.get('execution_deadline_monotonic_s')
        if type(deadline) not in (float,int) or not math.isfinite(deadline):
            raise PlatformIntegrityError('CALL_ABSOLUTE_DEADLINE_INVALID')
        if 'expected_prompt_sha256' in context:
            digest=context['expected_prompt_sha256']
            if not isinstance(digest,str) or re.fullmatch(r'[a-f0-9]{64}',digest) is None:
                raise PlatformIntegrityError('PROTECTED_PROMPT_HASH_INVALID')

    async def call(self, context: Mapping, prompt: str) -> dict:
        if not isinstance(prompt, str) or not prompt.strip():
            raise PlatformIntegrityError("GOVERNED_PROMPT_INVALID")
        began=monotonic()
        await self._require_capture()
        # Authorizer claims a unique call ordinal before returning frozen facts;
        # a duplicate/unknown prior effect cannot obtain another claim.
        protected = await _resolved(self.authorize(context))
        self._check_context(protected)
        if ('expected_prompt_sha256' in protected
                and hashlib.sha256(prompt.encode('utf-8')).hexdigest()!=protected['expected_prompt_sha256']):
            raise PlatformIntegrityError('PROTECTED_PROMPT_MISMATCH')
        deadline=min(protected['execution_deadline_monotonic_s'],began+protected['limits']['time_s'])
        run_id=protected['run_id'];task=asyncio.current_task()
        if run_id in self._contained_runs:raise BridgeError('cancelled')
        if run_id in self._uncertain_runs:raise BridgeError('CONTAINMENT_UNCERTAIN')
        self._active_calls.setdefault(run_id,set()).add(task)
        try:
            return await self._call_protected(protected,prompt,deadline)
        except BridgeError as exc:
            if exc.code=='CONTAINMENT_UNCERTAIN':self._uncertain_runs.add(run_id)
            raise
        except ResearchError as exc:
            if exc.code in {'invalid_request', 'integrity_fault'}:
                raise PlatformIntegrityError('AUTOMATIC_ROUTING_CONTEXT_INVALID') from None
            raise BridgeError(exc.code) from None
        finally:
            self._active_calls[run_id].discard(task)

    async def contain_run(self,grant):
        if not isinstance(grant,Mapping) or grant.get('authorized') is not True or not all(isinstance(grant.get(k),str) and grant[k] for k in ('run_id','request_id')):
            raise PlatformIntegrityError('CONTAINMENT_AUTHORIZATION_INVALID')
        run_id=grant['run_id'];self._contained_runs.add(run_id)
        tasks=tuple(self._active_calls.get(run_id,()))
        for task in tasks:
            if task is asyncio.current_task():raise PlatformIntegrityError('CONTAINMENT_OWNER_INVALID')
            task.cancel()
        try:
            results=await asyncio.wait_for(asyncio.gather(*tasks,return_exceptions=True),25) if tasks else []
        except TimeoutError:
            self._uncertain_runs.add(run_id);raise BridgeError('CONTAINMENT_UNCERTAIN') from None
        if run_id in self._uncertain_runs or any(isinstance(result,BaseException) and not isinstance(result,asyncio.CancelledError) for result in results):
            raise BridgeError('CONTAINMENT_UNCERTAIN')
        await self._capture('model-run-contained',{'id':'model-contained:'+uuid.uuid4().hex,'run_id':run_id,'request_id':grant['request_id'],
            'contained':True,'invocation_ids':grant.get('invocation_ids',[]),'recorded_at':utc_now()})
        return {'contained':True,'run_id':run_id,'request_id':grant['request_id']}

    async def _join_builder_evidence(self,result,context,call_record):
        refs=result.get('evidence_refs') if isinstance(result,Mapping) else None
        if self.read_evidence is None or not isinstance(refs,list) or not refs:
            raise BridgeError('AUDIT_UNAVAILABLE')
        for ref in refs:
            if not _is_ref(ref):raise BridgeError('AUDIT_UNAVAILABLE')
            try:
                raw=await _resolved(self.read_evidence(ref))
                receipt=json.loads(raw)
                keys=('contract_ref','run_id','invocation_id','execution_id','call_id','route_ref','model_call_start_ref','input_ref')
                if any(receipt.get(key)!=context[key] for key in keys):raise ValueError('Builder receipt join')
                if type(receipt.get('credential_removed')) is not bool or receipt.get('observed_runtime') is not True:
                    raise ValueError('Builder receipt observation')
                for child in receipt.get('event_refs',[])+receipt.get('output_refs',[]):
                    if not _is_ref(child):raise ValueError('Builder raw reference')
                    await _resolved(self.read_evidence(child))
            except Exception:raise BridgeError('AUDIT_UNAVAILABLE') from None
            if ref not in call_record['evidence_refs']:call_record['evidence_refs'].append(ref)

    async def _invoke_builder(self,context,prompt,timeout_s,call_record):
        # Execution is bounded by the broker's independent absolute deadline.
        # A timeout here still waits for the issued effect's containment and
        # immutable receipt delivery; it never submits another operation.
        pending=asyncio.create_task(self.builder_launcher.invoke(context,prompt,timeout_s=timeout_s))
        try:
            result=await asyncio.shield(pending)
        except asyncio.CancelledError as cancellation:
            try:
                result=await asyncio.wait_for(asyncio.shield(pending),20)
                await self._join_builder_evidence(result,context,call_record)
                cancellation.observation={key:result.get(key) for key in ('identity','usage','provider_request_id','observed_runtime')}
            except BaseException:
                pending.cancel()
                await asyncio.gather(pending,return_exceptions=True)
                raise BridgeError('CONTAINMENT_UNCERTAIN') from None
            raise
        await self._join_builder_evidence(result,context,call_record)
        if result.get('outcome') in {'failed','outcome_unknown'}:
            error=BridgeError(result.get('error_code') or 'provider_error')
            error.outcome_unknown=result['outcome']=='outcome_unknown'
            error.observation={key:result.get(key) for key in ('identity','usage','provider_request_id','observed_runtime')}
            raise error
        if result.get('outcome','completed')!='completed':raise BridgeError('invalid_output')
        return result

    async def _join_native_trace(self, ref, scope, call_record):
        try:
            if not _is_ref(ref) or self.read_evidence is None:raise ValueError('Trace unavailable')
            summary=json.loads(await _resolved(self.read_evidence(ref)))
            if (not isinstance(summary,dict) or set(summary)!={'schema','scope','status','event_refs'}
                    or summary.get('schema')!='ai4r-native-governed-trace:1' or summary.get('scope')!=scope
                    or summary.get('status') not in {'completed','failed','interrupted'}
                    or not isinstance(summary.get('event_refs'),list)):raise ValueError('Trace join')
            for index,event_ref in enumerate(summary['event_refs']):
                if not _is_ref(event_ref):raise ValueError('Trace reference')
                event=json.loads(await _resolved(self.read_evidence(event_ref)))
                if (not isinstance(event,dict) or set(event)!={'schema','scope','sequence','direction','method','raw_ref'}
                        or event.get('schema')!='ai4r-native-governed-trace-event:1' or event.get('scope')!=scope
                        or type(event.get('sequence')) is not int or event.get('sequence')!=index
                        or event.get('direction') not in {'in','out'} or not isinstance(event.get('method'),str)
                        or not event['method']
                        or not _is_ref(event.get('raw_ref'))):raise ValueError('Trace event join')
                await _resolved(self.read_evidence(event['raw_ref']))
        except Exception:raise BridgeError('AUDIT_UNAVAILABLE') from None
        call_record['evidence_refs'].append(ref)

    async def _automatic_choice(self, protected, prompt, deadline):
        # Serialize choice reservation per run: concurrent DAG nodes cannot
        # overbook the frozen subscription-invocation cap.
        key=(protected['run_id'],)
        lock=self._routing_locks.setdefault(key,asyncio.Lock())
        async with lock:
            return await self._automatic_choice_locked(protected,prompt,deadline)

    async def _automatic_choice_locked(self, protected, prompt, deadline):
        owner = self.automatic_routing
        prepared = owner.prepare(protected, prompt)
        if prepared is None:
            return None
        selected = prepared['baseline']
        reason = 'Fixed compatible baseline'
        method, failure, selection_call_ref = 'compatible_baseline', None, None
        prior=owner.invocation_choice(prepared,protected)
        if protected['call_function'] == 'verifier':
            method, reason = 'fixed_verifier', 'Independent verifier uses the frozen compatible baseline'
        elif prior is not None:
            selected, origin = prior
            method, reason = 'pinned_invocation', 'Retain the executor selected for this exact Capsule invocation'
            selection_call_ref=origin['record'].get('selection_call_ref')
        elif len(prepared['eligible']) == 1:
            method, reason = 'single_candidate', prepared.get('policy_reason') or 'Only one authorized compatible executor'
        elif prepared['selector'] is None:
            failure = 'LIGHTWEIGHT_SELECTOR_UNAVAILABLE'
        else:
            try:
                if self.authorize_routing_selection is None:
                    raise BridgeError('invalid_request')
                selection_context = await _resolved(self.authorize_routing_selection({
                    **{key: protected[key] for key in ('execution_id', 'invocation_id', 'call_id', 'call_claim_ref', 'contract_ref')},
                    'prompt_sha256': hashlib.sha256(prepared['prompt'].encode()).hexdigest(),
                }))
                self._check_context(selection_context)
                selection_deadline = min(deadline, selection_context['execution_deadline_monotonic_s'])
                result = await self._call_protected(selection_context, prepared['prompt'], selection_deadline)
                selection_call_ref = result['call_ref']
                selected, reason = owner.decode(result['text'], prepared['eligible'],
                    policy=prepared['snapshot']['routing_policy'])
                method = 'bounded_llm_selection'
            except asyncio.CancelledError:
                raise
            except Exception as error:
                code = getattr(error, 'code', None)
                if isinstance(error, ResearchError) and code in {'invalid_request', 'integrity_fault'}:
                    raise PlatformIntegrityError('ROUTING_SELECTION_CONTEXT_INVALID') from None
                if isinstance(error, PlatformIntegrityError) or code in {'AUDIT_UNAVAILABLE', 'CONTAINMENT_UNCERTAIN', 'cancelled'}:
                    raise
                selection_call_ref = getattr(error, 'call_ref', None) or selection_call_ref
                failure = 'INVALID_SELECTOR_REPLY' if isinstance(error, ValueError) else code or 'SELECTOR_UNAVAILABLE'
                reason = 'Compatible baseline selected before executor dispatch; selector could not return a valid choice'
        decision = {
            'schema': 'ai4r-automatic-route:1', 'id': 'automatic-route:' + uuid.uuid4().hex,
            **{key: protected[key] for key in ('run_id', 'node_id', 'subnode_id', 'invocation_id', 'execution_id')},
            'subject_call_id': protected['call_id'], 'contract_ref': protected['contract_ref'],
            'run_model_selection_id': prepared['snapshot']['id'],
            'eligible_candidate_ids': [c['id'] for c in prepared['eligible']], 'exclusions': prepared['rejected'],
            'selected_candidate_id': selected['id'], 'selected_model_id': selected['model_id'],
            'access_way': selected['access_way'], 'deployment_ref': selected['deployment_ref'],
            'selection_method': method, 'reason': reason, 'selector_failure': failure,
            'selection_call_ref': selection_call_ref, 'recorded_at': utc_now(),
            'invocation_decision_ref': prior[1]['ref'] if prior is not None else None,
        }
        ref = await self._capture('automatic-route-decision', decision, context=protected)
        return prepared, selected, ref, method

    async def _call_protected(self,protected,prompt,deadline):
        # Keep this host-derived scalar independently of the route adapter's
        # view. Caller-supplied identity/ordinal never supplies payload authority.
        expected_prompt_sha256=protected.get('expected_prompt_sha256')
        if expected_prompt_sha256 is not None and hashlib.sha256(prompt.encode('utf-8')).hexdigest() != expected_prompt_sha256:
            raise PlatformIntegrityError('MODEL_PROMPT_BINDING_INVALID')
        # These immutable Builder releases are tool-free text generators. Their trusted
        # carrier packages returned file bytes; only the original tool-using
        # release enters the dedicated, credential-isolated Builder launcher.
        is_builder = (protected.get("cc_name") == "research.builder"
                      and protected.get("cc_version") not in {"m1-2", "m1-3", "m1-4", "m1-5", "m1-6", "m1-7", "m1-8", "m1-9", "m1-10", "m1-11", "m1-12", "m1-13", "m1-14", "m1-15", "m1-16", "m1-17", "m1-18"})
        if is_builder and self.builder_launcher is None:
            raise BridgeError("ENVIRONMENT_BLOCKED")
        remaining=deadline-monotonic()
        if remaining<=0:raise BridgeError('timeout')
        manual = self.manual_models.for_call(protected) if self.manual_models is not None else None
        chatgpt = self.manual_models.chatgpt_for_call(protected) if self.manual_models is not None else None
        automatic = None
        pinned_selector = protected.get('routing_selection_candidate')
        if pinned_selector is not None:
            if (protected.get('purpose') != 'routing_selection' or protected['call_function'] != 'routing_selection'
                    or self.automatic_routing is None):
                raise PlatformIntegrityError('INVALID_ROUTING_SELECTION_CONTEXT')
            manual, chatgpt = self.automatic_routing.transport(pinned_selector)
        elif self.automatic_routing is not None:
            automatic = await self._automatic_choice(protected, prompt, deadline)
            if automatic is not None:
                manual, chatgpt = self.automatic_routing.transport(automatic[1])
        try:
            async with asyncio.timeout(min(30,remaining)):
                if automatic is not None or pinned_selector is not None:
                    selected = automatic[1] if automatic is not None else pinned_selector
                    if is_builder:
                        raise BridgeError('invalid_request')
                    choice = RouteChoice(selected['model_id'], 'router', None,
                        route_decision_ref=automatic[2] if automatic is not None else None)
                elif chatgpt is not None:
                    if is_builder:
                        raise BridgeError('invalid_request')
                    choice = RouteChoice(chatgpt['chatgpt_model'], 'codex_router_disabled', None)
                elif manual is not None:
                    if is_builder:
                        raise BridgeError('invalid_request')
                    deployment = self.read_evidence(manual['deployment_ref'])
                    deployment = json.loads(await _resolved(deployment))
                    choice = RouteChoice(deployment['model_id'], 'user_api', None)
                else:
                    choice = await self.router.select(protected)
        except TimeoutError:
            choice=RouteChoice(self.fixed_route_id,'codex_router_failed','timeout')
        route_id = "route-" + uuid.uuid4().hex
        auto_route = automatic is not None or pinned_selector is not None
        hybrid_route = auto_route and ((automatic[0]['snapshot']['routing_policy'].get('executor_ids') is not None)
            if automatic else False)
        route = {"schema_version": "4.0.0" if hybrid_route else "3.0.0" if auto_route else "2.0.0" if manual is not None else "1.0.0", "route_id": route_id,
                 **{k: protected[k] for k in ("run_id", "node_id", "subnode_id", "invocation_id")},
                 "router_enabled": choice.decision_source not in {"codex_router_disabled", "user_api"},
                 "decision_source": choice.decision_source, "router_failure": choice.router_failure,
                 "router_halt_code": choice.router_halt_code, "model_id": choice.model_id,
                 "route_decision_ref": choice.route_decision_ref, "recorded_at": utc_now()}
        if auto_route:
            route.update(access_way=(automatic[1] if automatic else pinned_selector)['access_way'],
                selection_method=automatic[3] if automatic else 'pinned_selector')
        # Host capture IDs are separate from public RouteRecord fields.
        try:
            route_ref = await self._capture("route-record", route, context=protected)
            evidence_ref = await self._capture("model-call-input", {
                "id": "input:" + uuid.uuid4().hex, "run_id": protected["run_id"],
                "invocation_id": protected["invocation_id"], "call_id": protected["call_id"], "prompt": prompt}, context=protected)
        except PlatformIntegrityError:
            raise
        except Exception:
            raise BridgeError("AUDIT_UNAVAILABLE") from None
        # The durable claim is already consumed. Staging must not turn an
        # expired/revoked frozen API choice into another route or provider call.
        # Source124 terminates this attempt; no public ModelCall is invented
        # when final authorization refuses it before call-start.
        try:
            if self.revalidate is None:
                raise PlatformIntegrityError('DISPATCH_AUTHORIZATION_UNAVAILABLE')
            async with asyncio.timeout_at(deadline):
                if manual is not None:
                    self.manual_models.preflight(manual)
                if choice.decision_source=='router' and not auto_route:
                    if not isinstance(choice.decision,dict):
                        raise PlatformIntegrityError('FROZEN_ROUTE_INVALID')
                    if self.providers is None:
                        raise BridgeError('auth_failed')
                    if is_builder and getattr(self.providers,'invoke_tool_loop',None) is None:
                        raise BridgeError('invalid_request')
                    preflight=getattr(self.providers,'preflight',None)
                    if preflight is None:
                        raise BridgeError('invalid_request')
                    preflight_timeout=min(deadline-monotonic(),protected['limits']['time_s'])
                    if preflight_timeout<=0:raise TimeoutError()
                    await _resolved(preflight(choice.decision['deployment_ref'],
                        timeout_s=preflight_timeout,
                        call_function=protected['call_function']))
                live=await _resolved(self.revalidate({key:protected[key] for key in
                    ('execution_id','invocation_id','call_id','call_claim_ref','contract_ref')}))
                self._check_context(live)
                if manual is not None and not auto_route and self.manual_models.for_call(live) != manual:
                    raise PlatformIntegrityError('DISPATCH_CONTEXT_CHANGED')
                if chatgpt is not None and not auto_route and self.manual_models.chatgpt_for_call(live) != chatgpt:
                    raise PlatformIntegrityError('DISPATCH_CONTEXT_CHANGED')
                if (live.get('expected_prompt_sha256')!=expected_prompt_sha256
                        or protected.get('expected_prompt_sha256')!=expected_prompt_sha256):
                    raise PlatformIntegrityError('DISPATCH_CONTEXT_CHANGED')
                for key in ('run_id','node_id','subnode_id','attempt_id','execution_id','invocation_id','call_id',
                            'call_claim_ref','contract_ref','model_selection_profile_ref','deployment_ref','call_function'):
                    if live[key]!=protected[key]:raise PlatformIntegrityError('DISPATCH_CONTEXT_CHANGED')
                if automatic is not None:
                    await _resolved(self.automatic_routing.revalidate(automatic[0], automatic[1], live, automatic[2]))
                if pinned_selector is not None and live.get('routing_selection_candidate') != pinned_selector:
                    raise PlatformIntegrityError('DISPATCH_CONTEXT_CHANGED')
                deadline=min(deadline,live['execution_deadline_monotonic_s'],monotonic()+live['limits']['time_s'])
                # A supported asynchronous audit-health callback can consume
                # ready validity, so it must finish before the final decision
                # freshness/authorization check, never after that check.
                await self._require_capture()
                if choice.decision is not None:
                    if self.read_evidence is None:
                        raise PlatformIntegrityError('FROZEN_ROUTE_CAPTURE_UNAVAILABLE')
                    captured=json.loads(await _resolved(self.read_evidence(choice.route_decision_ref)))
                    if captured!=choice.decision:
                        raise PlatformIntegrityError('FROZEN_ROUTE_CAPTURE_CHANGED')
                    recheck=getattr(self.router,'revalidate_frozen',None)
                    if recheck is None:
                        raise PlatformIntegrityError('FROZEN_ROUTE_RECHECK_UNAVAILABLE')
                    await _resolved(recheck(protected,choice))
                    allowance=choice.decision['limits']['time_s']
                    if type(allowance) not in (int,float) or not math.isfinite(allowance) or allowance<=0:
                        raise PlatformIntegrityError('ROUTE_DEADLINE_INVALID')
                    deadline=min(deadline,monotonic()+allowance)
            timeout_s=min(deadline-monotonic(),live['limits']['time_s'],protected['limits']['time_s'],
                          choice.decision['limits']['time_s'] if choice.decision is not None else protected['limits']['time_s'])
            if timeout_s<=0:raise TimeoutError()
        except (Exception,asyncio.CancelledError) as error:
            code=getattr(error,'code',None)
            reason=code if code in {'cancelled','budget_exhausted','auth_failed','invalid_request','AUDIT_UNAVAILABLE',
                                    'model_dispatch_authorization','model_call_authorization','run_not_dispatchable'} else 'dispatch_authorization_denied'
            if isinstance(error,TimeoutError):reason='timeout'
            elif isinstance(error,asyncio.CancelledError):reason='cancelled'
            elif isinstance(error,PlatformIntegrityError) and str(error) in {
                    'DISPATCH_AUTHORIZATION_UNAVAILABLE','DISPATCH_CONTEXT_CHANGED','FROZEN_ROUTE_CAPTURE_UNAVAILABLE',
                    'FROZEN_ROUTE_CAPTURE_CHANGED','FROZEN_ROUTE_RECHECK_UNAVAILABLE','FROZEN_ROUTE_INVALID',
                    'FROZEN_ROUTE_INVALIDATED','ROUTE_DEADLINE_INVALID'}:
                reason=str(error)
            try:
                await self._capture('model-call-refused',{
                    'id':protected['call_id']+':refused',
                    **{key:protected[key] for key in ('run_id','node_id','subnode_id','attempt_id','invocation_id',
                                                      'execution_id','call_id','call_claim_ref','contract_ref')},
                    'route_ref':route_ref,'input_ref':evidence_ref,'route_decision_ref':choice.route_decision_ref,
                    'reason_code':reason,'recorded_at':utc_now()}, context=protected)
            except Exception:
                raise BridgeError('AUDIT_UNAVAILABLE',route_ref=route_ref) from None
            if isinstance(error,asyncio.CancelledError):raise
            raise BridgeError(reason if reason in {'timeout','cancelled','budget_exhausted','auth_failed','AUDIT_UNAVAILABLE'}
                              else 'invalid_request',route_ref=route_ref) from None
        started_at = utc_now()
        try:
            start_ref = await self._capture("model-call-start", {
                "id": protected["call_id"] + ":start", "run_id": protected["run_id"],
                "invocation_id": protected["invocation_id"], "execution_id": protected["execution_id"],
                "call_id": protected["call_id"], "call_claim_ref": protected["call_claim_ref"],
                "contract_ref": protected["contract_ref"],
                "route_id": route_id, "route_ref": route_ref, "input_ref": evidence_ref, "started_at": started_at}, context=protected)
        except Exception:
            raise BridgeError('AUDIT_UNAVAILABLE',route_ref=route_ref) from None
        deployment_ref = chatgpt['deployment_ref'] if chatgpt is not None else manual['deployment_ref'] if manual is not None else choice.decision["deployment_ref"] if choice.decision else protected["deployment_ref"]
        call_record = {"schema_version": "1.0.0", "id": protected["call_id"],
                       "route_attempt_id": "attempt:" + uuid.uuid4().hex,
                       "route_decision_ref": choice.route_decision_ref,
                       "execution_id": protected["execution_id"], "invocation_id": protected["invocation_id"],
                       "purpose": protected.get('purpose', 'task_execution'), "call_function": protected["call_function"],
                       "deployment_ref": deployment_ref, "model_selection_profile_ref": protected["model_selection_profile_ref"],
                       "provider_request_id": None, "identity": {"requested": choice.model_id, "effective": None,
                                                                    "basis": "effective model not observed"},
                       "started_at": started_at, "ended_at": None, "outcome": "outcome_unknown",
                       "provider_error_code": None, "usage": observed_usage(),
                       "evidence_refs": [evidence_ref], "observed_runtime": True}
        result = None
        failure = None
        failure_code = None
        native_scope={key:protected[key] for key in ('run_id','node_id','subnode_id','attempt_id',
            'execution_id','invocation_id','call_id','contract_ref')}
        native_scope['model_call_start_ref']=start_ref
        native_trace_expected=False
        try:
            # Start persistence itself consumes the protected absolute budget.
            timeout_s=min(timeout_s,deadline-monotonic())
            if timeout_s<=0:raise TimeoutError()
            dispatch_context={**protected,'limits':dict(live['limits'],time_s=timeout_s),
                'execution_deadline_monotonic_s':deadline,'route_ref':route_ref,'route_decision_ref':choice.route_decision_ref,
                'selected_deployment_ref':deployment_ref,'model_call_start_ref':start_ref,'input_ref':evidence_ref}
            async with asyncio.timeout_at(deadline):
                if manual is not None:
                    options = {'context':dispatch_context} if manual.get('platform_id')=='operator-local' else {}
                    result = await self.manual_models.invoke(manual, prompt, timeout_s=timeout_s,
                        call_function=protected['call_function'],**options)
                elif chatgpt is not None or choice.model_id == self.fixed_route_id:
                    if is_builder:
                        result = await self._invoke_builder(dispatch_context,prompt,timeout_s,call_record)
                    else:
                        traced=getattr(self.subscription,'invoke_governed_traced',None)
                        native_trace_expected=traced is not None
                        subscription_options = ({'reasoning_effort': chatgpt['reasoning_effort'],
                            'expected_account_fingerprint': chatgpt['account_fingerprint']}
                            if chatgpt is not None and chatgpt.get('access_way') == 'chatgpt_subscription' else {})
                        if traced is not None:
                            result=await traced(native_scope,prompt,model=chatgpt['chatgpt_model'] if chatgpt else protected.get('requested_model'),timeout_s=timeout_s,**subscription_options)
                        else:
                            result = await self.subscription.invoke_governed(prompt, model=chatgpt['chatgpt_model'] if chatgpt else protected.get("requested_model"), timeout_s=timeout_s,**subscription_options)
                else:
                    if self.providers is None:
                        raise BridgeError("auth_failed")
                    if is_builder:
                        invoke_loop = getattr(self.providers, "invoke_tool_loop", None)
                        if invoke_loop is None:
                            raise BridgeError("invalid_request")
                        result = await invoke_loop(deployment_ref, dispatch_context, prompt, timeout_s=timeout_s)
                    else:
                        result = await self.providers.invoke(deployment_ref, prompt, timeout_s=timeout_s,
                                                             call_function=protected["call_function"])
            await self._require_capture()
            if not isinstance(result, Mapping) or not isinstance(result.get("text"), str) or not result["text"]:
                raise BridgeError("invalid_output")
            if native_trace_expected or manual is not None and manual.get('platform_id')=='operator-local':
                await self._join_native_trace(result.get('native_trace_ref'),native_scope,call_record)
            identity = result.get("identity", {})
            call_record["identity"] = {"requested": choice.model_id, "effective": identity.get("effective"),
                                       "basis": identity.get("basis") or "effective model not observed"}
            call_record["usage"] = observed_usage(result.get("usage"))
            call_record["provider_request_id"] = result.get("provider_request_id")
            output_ref = await self._capture("model-call-output", {
                "id": "output:" + uuid.uuid4().hex, "run_id": protected["run_id"],
                "invocation_id": protected["invocation_id"], "call_id": protected["call_id"], "text": result["text"]}, context=protected)
            call_record["evidence_refs"].append(output_ref)
            call_record["outcome"] = "completed"
        except (asyncio.CancelledError, ConnectionError, TimeoutError) as error:
            failure = error
            failure_code = "timeout" if isinstance(error, TimeoutError) else "cancelled" if isinstance(error, asyncio.CancelledError) else "network_error"
            # Submission may have happened. Unknown outcomes carry no invented
            # provider error code and are never replay eligible.
        except Exception as error:
            failure = error
            known = getattr(error, "code", None) or (str(error) if type(error).__name__ == "CodexError" else None)
            mapped = {"SIGN_IN_REQUIRED": "auth_failed", "SUBSCRIPTION_REQUIRED": "auth_failed",
                      "RUNTIME_TIMEOUT": "timeout", "INVALID_OUTPUT": "invalid_output", "TURN_FAILED": "provider_error"}
            failure_code = mapped.get(known, known if known in {"auth_failed", "rate_limited", "timeout", "provider_error", "invalid_request", "network_error", "invalid_output"} else "provider_error")
            if known in {'CONTAINMENT_UNCERTAIN','AUDIT_UNAVAILABLE','budget_exceeded','cancelled'}:failure_code=known
            if known in {"DELIVERY_UNKNOWN", "RUNTIME_DISCONNECTED", "CONTAINMENT_UNCERTAIN"} or getattr(error, "outcome_unknown", False):
                call_record["outcome"] = "outcome_unknown"
            else:
                call_record["outcome"] = "failed"
                call_record["provider_error_code"] = 'invalid_request' if failure_code=='budget_exceeded' else failure_code if failure_code in {'auth_failed','rate_limited','timeout','provider_error','invalid_request','network_error','invalid_output'} else 'provider_error'
        finally:
            if call_record['outcome'] == 'outcome_unknown':
                # A bounded local selector is read-only inference with no task
                # execution/acceptance authority. Its HTTP timeout/disconnect
                # permits the frozen pre-dispatch baseline policy, including
                # the subsequent independent verifier. Keep its original
                # unknown call and budget debit, but do not poison executor
                # containment. Unknown worker/verifier effects and explicit
                # containment faults remain terminal and cannot be replayed.
                selector_transport_unknown = (
                    pinned_selector is not None and not is_builder
                    and protected.get('purpose') == 'routing_selection'
                    and protected['call_function'] == 'routing_selection'
                    and pinned_selector.get('access_way') == 'local'
                    and failure_code in {'timeout', 'network_error'})
                if not selector_transport_unknown:
                    self._uncertain_runs.add(protected['run_id'])
            call_record["ended_at"] = None if call_record["outcome"] == "outcome_unknown" else utc_now()
        if failure is not None:
            trace_ref=getattr(failure,'native_trace_ref',None)
            if trace_ref is not None:
                try:await self._join_native_trace(trace_ref,native_scope,call_record)
                except BridgeError:
                    failure_code='AUDIT_UNAVAILABLE'
                    if call_record['outcome']!='outcome_unknown':
                        call_record['outcome']='failed'
                        call_record['ended_at']=utc_now()
            observation=failure_observation(failure,choice.model_id)
            if observation is not None:
                call_record.update({key:observation[key] for key in ('identity','usage','provider_request_id')})
                provider_ref=await self._capture('model-provider-observation',{
                    'id':'provider-observation:'+uuid.uuid4().hex,'run_id':protected['run_id'],
                    'invocation_id':protected['invocation_id'],'call_id':protected['call_id'],'observation':observation}, context=protected)
                call_record['evidence_refs'].append(provider_ref)
        try:
            call_ref = await self._capture("model-call", call_record, context=protected)
        except Exception:
            # A provider effect with an uncommitted result can never be accepted.
            raise BridgeError("AUDIT_UNAVAILABLE", route_ref=route_ref) from None
        if failure:
            if isinstance(failure, asyncio.CancelledError):
                raise failure
            raise BridgeError(failure_code, call_ref=call_ref, route_ref=route_ref) from None
        return {"text": result["text"], "call_ref": call_ref, "route_ref": route_ref,
                "identity": call_record["identity"], "usage": call_record["usage"],
                "provider_request_id": call_record["provider_request_id"], "observed_runtime": True}


MODEL_IPC_PROTOCOL = "ai4r-model-ipc:1"


class ModelBridgeServer:
    """One boot/session capability and Linux peer identity protect model IPC."""
    def __init__(self, bridge: GovernedBridge, socket_path: str | Path, *, allowed_peer_uids,
                 capability: str | None = None, session_id: str | None = None, authorize_containment=None):
        self.bridge, self.path = bridge, Path(socket_path)
        self.allowed_peer_uids = frozenset(allowed_peer_uids)
        if not self.allowed_peer_uids:
            raise ValueError("MODEL_PEER_ALLOWLIST_EMPTY")
        self.capability = capability or secrets.token_urlsafe(32)
        self.session_id = session_id or uuid.uuid4().hex
        self.server = None
        self._socket_inode = None
        self._closed = False
        self.authorize_containment=authorize_containment

    async def _handle(self, reader, writer):
        try:
            _, uid, _ = peer_credentials(writer.get_extra_info("socket"))
            if self._closed or uid not in self.allowed_peer_uids:
                raise PermissionError("MODEL_PEER_DENIED")
            async with asyncio.timeout(30):
                envelope = await read_frame(reader)
            common={"protocol", "op", "session_id", "capability"}
            operation=envelope.get('op')
            fields={'context','prompt'} if operation=='invoke' else {'request'} if operation=='contain' else set()
            if (not fields or set(envelope) != common|fields
                    or envelope.get("protocol") != MODEL_IPC_PROTOCOL
                    or envelope.get("session_id") != self.session_id
                    or not isinstance(envelope.get("capability"), str)
                    or not secrets.compare_digest(envelope["capability"], self.capability)):
                raise PermissionError("MODEL_SESSION_DENIED")
            if operation=='invoke':result = await self.bridge.call(envelope["context"], envelope["prompt"])
            else:
                request=envelope['request']
                if (self.authorize_containment is None or not isinstance(request,dict) or set(request)!={'run_id','request_id'}):
                    raise PermissionError('MODEL_CONTAINMENT_DENIED')
                grant=await _resolved(self.authorize_containment(request))
                if any(grant.get(k)!=request[k] for k in request):raise PermissionError('MODEL_CONTAINMENT_DENIED')
                result=await self.bridge.contain_run(grant)
            response = {"protocol": MODEL_IPC_PROTOCOL, "result": result}
        except asyncio.CancelledError:
            await close_writer(writer)
            raise
        except PlatformIntegrityError:
            response = {"protocol": MODEL_IPC_PROTOCOL, "error": "PLATFORM_INTEGRITY_FAULT"}
        except BridgeError as error:
            response = {"protocol": MODEL_IPC_PROTOCOL, "error": error.code,
                        "call_ref": error.call_ref, "route_ref": error.route_ref}
        except (PermissionError, ValueError, asyncio.TimeoutError, asyncio.IncompleteReadError,
                ConnectionError, RuntimeError):
            # Authentication/framing failures get no response or reflected input.
            await close_writer(writer)
            return
        try:
            writer.write(encode_frame(response))
            await writer.drain()
        except (ValueError, ConnectionError):
            pass
        finally:
            await close_writer(writer)

    async def start(self):
        if os.name != "posix":
            raise RuntimeError("LINUX_MODEL_IPC_REQUIRED")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        metadata = self.path.parent.stat()
        if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise PermissionError("MODEL_SOCKET_DIRECTORY_CUSTODY_INVALID")
        if self.path.exists() or self.path.is_symlink():
            raise RuntimeError("MODEL_SOCKET_ALREADY_EXISTS")
        self.server = await asyncio.start_unix_server(self._handle, path=str(self.path), limit=MAX_IPC_FRAME_BYTES + 4)
        self.path.chmod(0o600)
        self._socket_inode = self.path.stat().st_ino
        return self

    async def serve_forever(self):
        if self.server is None:
            await self.start()
        async with self.server:
            await self.server.serve_forever()

    async def close(self):
        self._closed = True
        self.capability = secrets.token_urlsafe(32)
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
        if self.path.exists() and self.path.lstat().st_ino == self._socket_inode:
            self.path.unlink()


class ModelBridgeClient:
    """One submission over owned IPC. Any delivery uncertainty is terminal."""
    def __init__(self, socket_path: str | Path, *, peer_uid: int, capability: str, session_id: str):
        self.path, self.peer_uid = Path(socket_path), peer_uid
        self.capability, self.session_id = capability, session_id

    async def call(self, context: Mapping, prompt: str):
        deadline = context.get("limits", {}).get("time_s", 600)
        if type(deadline) not in (int, float) or not 0 < deadline <= 600:
            raise PlatformIntegrityError("CALL_DEADLINE_INVALID")
        return await self._exchange('invoke',{'context':dict(context),'prompt':prompt},deadline)

    async def contain_run(self,run_id,request_id):
        return await self._exchange('contain',{'request':{'run_id':run_id,'request_id':request_id}},30)

    async def _exchange(self,operation,payload,deadline):
        writer = None
        try:
            async with asyncio.timeout(deadline):
                metadata = self.path.lstat()
                if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != self.peer_uid or stat.S_IMODE(metadata.st_mode) != 0o600:
                    raise PlatformIntegrityError("MODEL_SOCKET_CUSTODY_INVALID")
                reader, writer = await asyncio.open_unix_connection(str(self.path), limit=MAX_IPC_FRAME_BYTES + 4)
                _, uid, _ = peer_credentials(writer.get_extra_info("socket"))
                if uid != self.peer_uid:
                    raise PlatformIntegrityError("MODEL_PEER_INVALID")
                writer.write(encode_frame({"protocol": MODEL_IPC_PROTOCOL, "op": operation,
                    "session_id": self.session_id, "capability": self.capability,
                    **payload}))
                await writer.drain()
                reply = await read_frame(reader)
                if reply.get("protocol") != MODEL_IPC_PROTOCOL:
                    raise PlatformIntegrityError("MODEL_PROTOCOL_INVALID")
                if reply.get("error") == "PLATFORM_INTEGRITY_FAULT":
                    raise PlatformIntegrityError("MODEL_CONTEXT_REJECTED")
                if reply.get("error"):
                    raise BridgeError(reply["error"], call_ref=reply.get("call_ref"), route_ref=reply.get("route_ref"))
                if not isinstance(reply.get("result"), dict):
                    raise PlatformIntegrityError("MODEL_REPLY_INVALID")
                return reply["result"]
        except (TimeoutError, OSError, asyncio.IncompleteReadError):
            raise BridgeError("DELIVERY_UNKNOWN") from None
        finally:
            if writer is not None:
                await close_writer(writer)
