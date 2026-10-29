"""Single process owner for managed login and session-isolated text turns."""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import uuid
from importlib.metadata import version
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .transport import AppServerTransport, CodexError
from .account_telemetry import safe_limits, missing_fields, READ_SCHEMA_SHA256, UPDATE_SCHEMA_SHA256


def governed_tool_config():
    """Packaged 0.163 native declarations disabled for governed text turns.

    Measured on the actual client: the legacy startup [tools] table alone
    leaves request_user_input, view_image, multi-agent and goal tools visible.
    Ordinary chat stream configuration remains separate.
    """
    return {'features.view_image': False, 'features.multi_agent': False,
            'features.goals': False, 'tools.experimental_request_user_input.enabled': False}

_TEXT_ONLY_ITEM_TYPES = frozenset({"userMessage", "agentMessage", "reasoning", "plan"})


def _validate_text_only_event(method, params):
    """Reject native tool activity while allowing text, reasoning and usage events."""
    if method == "turn/completed":
        turn = params.get("turn")
        if not isinstance(turn, dict):
            raise CodexError("INVALID_OUTPUT")
        items = turn.get("items", [])
        if not isinstance(items, list):
            raise CodexError("INVALID_OUTPUT")
        if any(not isinstance(item, dict) or item.get("type") not in _TEXT_ONLY_ITEM_TYPES for item in items):
            raise CodexError("TOOLS_UNAVAILABLE")
        return

    if not method.startswith("item/"):
        return
    parts = method.split("/")
    # Item lifecycle packets are generic; their item type is authoritative.
    if len(parts) == 2 and parts[1] in {"started", "completed"}:
        item = params.get("item")
        if not isinstance(item, dict) or item.get("type") not in _TEXT_ONLY_ITEM_TYPES:
            raise CodexError("TOOLS_UNAVAILABLE")
        return
    # Preserve text/reasoning deltas, reject every other item event family.
    if len(parts) < 3 or parts[1] not in {"userMessage", "agentMessage", "reasoning", "plan"}:
        raise CodexError("TOOLS_UNAVAILABLE")


class SubscriptionService:
    def __init__(self, root: Path, *, transport=None):
        self.root = root.resolve()
        self.transport = transport or AppServerTransport(self.root)
        self.epoch = uuid.uuid4().hex
        self.account_fingerprint = None
        self.active = {}
        self.login_id = None
        self.login_url = None
        self.login_user_code = None
        self.login_error = None
        self._account_observer = None
        self._governed_trace_writer = None
        self._observation_generation = 0
        self._observation_identity_verified = False
        self.last_account_observation = None
        self.account_observation_state = {'status':'unavailable','reason':'observation_writer_not_bound'}
        self._account_lock = asyncio.Lock()
        self.transport.listeners.add(self._account_event)
        self.binding_path = self.root / "bindings.json"
        try:
            self.bindings = json.loads(self.binding_path.read_text(encoding="utf-8"))
            if not isinstance(self.bindings, dict):
                raise ValueError()
        except FileNotFoundError:
            self.bindings = {}
        except (OSError, ValueError):
            raise CodexError("PROFILE_STATE_INVALID") from None

    def _account_event(self, method, params):
        if method in {'transport/closed','account/updated','account/login/completed'}:
            self._observation_generation += 1
            self._observation_identity_verified = False
            self.last_account_observation = None
        if method == "transport/closed":
            self.epoch = uuid.uuid4().hex
            self.login_id = self.login_url = self.login_user_code = None
        if method == "account/login/completed" and params.get("loginId") == self.login_id:
            self.login_id = None
            self.login_url = self.login_user_code = None
            self.login_error = None if params.get("success") is True else "LOGIN_FAILED"
        if method == 'account/rateLimits/updated' and self._account_observer:
            if not self._observation_identity_verified or not self.account_fingerprint:
                self._publish_account_observation(None,method,reason='account_identity_not_verified',sparse=True)
            else:
                try:values=safe_limits(params,notification=True)
                except (ValueError,TypeError,OverflowError):
                    self._publish_account_observation(None,method,reason='invalid_account_limits_protocol',sparse=True)
                else:self._publish_account_observation(values,method,sparse=True)

    def set_account_observer(self, writer):
        """Bind the protected native owner's durable writer, never caller identity."""
        if not callable(writer):raise ValueError('Protected account observation writer required')
        self._account_observer=writer

    def set_governed_trace_writer(self, append_record, put_blob):
        if not callable(append_record) or not callable(put_blob):
            raise ValueError('Protected trace writers required')
        self._governed_trace_writer = (append_record, put_blob)

    async def invoke_governed_traced(self, scope, prompt, **options):
        from .governed_trace import GovernedTrace
        if self._governed_trace_writer is None or not hasattr(self.transport, 'wire_listeners'):
            raise CodexError('AUDIT_UNAVAILABLE')
        trace = GovernedTrace(scope, *self._governed_trace_writer)
        try:
            result = await self.invoke_governed(prompt, _trace=trace, **options)
        except BaseException as error:
            try:
                error.native_trace_ref = trace.finish('interrupted' if isinstance(error, asyncio.CancelledError) else 'failed')
            except CodexError:
                if isinstance(error, asyncio.CancelledError):
                    error.native_trace_failure = 'AUDIT_UNAVAILABLE'
                    raise error
                raise
            raise
        result['native_trace_ref'] = trace.finish('completed')
        return result

    def _publish_account_observation(self, values, method, *, reason=None, sparse=False):
        if self._account_observer is None:return
        missing=missing_fields(values) if values is not None else {}
        record={'schema':'ai4r-subscription-account-observation:1','id':'account-observation:'+uuid.uuid4().hex,
            'observed_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
            'account_fingerprint':self.account_fingerprint if self._observation_identity_verified else None,
            'profile_id':hashlib.sha256(str(self.root).encode()).hexdigest(),'epoch':self.epoch,
            'source':{'method':method,'runtime_version':version('openai-codex-cli-bin'),'schema_sha256':
                UPDATE_SCHEMA_SHA256 if sparse else READ_SCHEMA_SHA256},
            'informational_only':True,'sparse_update':sparse,
            'status':'unavailable' if values is None else 'partial' if missing else 'observed',
            'values':values,'unavailable_fields':missing,'unavailable_reason':reason}
        try:self._account_observer('subscription-account-observation',record)
        except Exception:
            self.account_observation_state={'status':'unavailable','reason':'observation_persistence_failed'}
            self.last_account_observation=None
            return
        self.account_observation_state={'status':record['status'],'reason':reason}
        # Sparse nullable metadata never clears a previously observed snapshot.
        # A status request always refetches a full response instead of guessing.
        if not sparse:self.last_account_observation=record if values is not None else None

    async def _observe_account_limits(self):
        if not self._observation_identity_verified or not self.account_fingerprint:
            self._publish_account_observation(None,'account/rateLimits/read',reason='account_identity_not_verified')
            return
        identity=(self.account_fingerprint,self.epoch,self._observation_generation)
        try:
            async with asyncio.timeout(5):
                result=await self.transport.request('account/rateLimits/read',{})
            if identity!=(self.account_fingerprint,self.epoch,self._observation_generation):
                self._publish_account_observation(None,'account/rateLimits/read',reason='account_identity_changed_during_read')
                return
            values=safe_limits(result)
        except asyncio.CancelledError:raise
        except (ValueError,TypeError,OverflowError):
            self._publish_account_observation(None,'account/rateLimits/read',reason='invalid_account_limits_protocol')
        except Exception:
            self._publish_account_observation(None,'account/rateLimits/read',reason='account_limits_read_failed')
        else:self._publish_account_observation(values,'account/rateLimits/read')

    def _save(self):
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.binding_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.bindings), encoding="utf-8")
        tmp.replace(self.binding_path)

    async def _status(self):
        await self.transport.start()
        generation = self._observation_generation
        result = await self.transport.request("account/read", {"refreshToken": False})
        account = result.get("account") or {}
        kind = account.get("type")
        fingerprint = hashlib.sha256(str(account.get("email")).encode()).hexdigest() if kind == "chatgpt" and account.get("email") else None
        if self.account_fingerprint is not None and fingerprint != self.account_fingerprint:
            self.epoch = uuid.uuid4().hex
            # A changed/unknown identity is not permission to reuse old threads.
            for run in self.active.values():
                queue = run["queue"]
                if queue.full():
                    queue.get_nowait()
                queue.put_nowait(("account/changed", {}))
        if fingerprint != self.account_fingerprint:self.last_account_observation=None
        self.account_fingerprint = fingerprint
        self._observation_identity_verified = bool(fingerprint) and generation == self._observation_generation
        return {"enabled": True, "state": "ready" if kind == "chatgpt" else "subscription_required" if kind else "signing_in" if self.login_id else "signed_out", "plan": account.get("planType") if kind == "chatgpt" else None, "error": self.login_error, "login_attempt_id": self.login_id, "auth_url": self.login_url if self.login_id else None, "user_code": self.login_user_code if self.login_id else None, "active_runs": len(self.active), "milestone": "text_chat"}

    async def status(self):
        async with self._account_lock:
            try:status=await self._status()
            except Exception:
                self._observation_identity_verified=False
                self._publish_account_observation(None,'account/rateLimits/read',reason='account_status_unavailable')
                raise
            if self._account_observer:await self._observe_account_limits()
            return status

    async def login(self):
        async with self._account_lock:
            await self.transport.start()
            if self.active:
                raise CodexError("BUSY")
            if self.login_id:
                raise CodexError("LOGIN_PENDING")
            self.epoch = uuid.uuid4().hex
            login_type = 'chatgptDeviceCode' if os.environ.get('JIUWENSWARM_M1_PROFILE') == '1' else 'chatgpt'
            result = await self.transport.request("account/login/start", {"type": login_type})
            url = result.get('verificationUrl' if login_type == 'chatgptDeviceCode' else 'authUrl', '')
            parsed = urlparse(url)
            code = result.get('userCode') if login_type == 'chatgptDeviceCode' else None
            if (result.get("type") != login_type or parsed.scheme != "https" or parsed.hostname not in {"auth.openai.com", "auth0.openai.com", "auth.chatgpt.com"} or not result.get("loginId")
                    or login_type == 'chatgptDeviceCode' and (not isinstance(code, str) or not 1 <= len(code) <= 64 or not code.isascii() or not code.isprintable())):
                await self.transport.close()
                raise CodexError("LOGIN_PROTOCOL_ERROR")
            self.login_id = result["loginId"]
            self.login_url, self.login_user_code = url, code
            self.login_error = None
            return {"state": "signing_in", "auth_url": url, "login_attempt_id": self.login_id, "user_code": code}

    async def cancel_login(self, attempt_id):
        async with self._account_lock:
            if not self.login_id or not isinstance(attempt_id, str) or attempt_id != self.login_id:
                raise CodexError("STALE_OPERATION")
            if self.login_id:
                await self.transport.request("account/login/cancel", {"loginId": self.login_id})
                self.login_id = None
                self.login_url = self.login_user_code = None
            return await self._status()

    async def logout(self):
        async with self._account_lock:
            self.epoch = uuid.uuid4().hex
            self.account_fingerprint = None
            self._observation_identity_verified = False
            self.last_account_observation = None
            # Close all active streams before revoking credentials. Admission is
            # serialized behind this lock; accepted work is never replayed.
            await self.transport.close()
            self.login_id = None
            await self.transport.start()
            await self.transport.request("account/logout", {})
            self.login_error = None
            return await self._status()

    async def models(self):
        async with self._account_lock:
            status = await self._status()
            if status["state"] != "ready":
                raise CodexError("SIGN_IN_REQUIRED")
            result = await self.transport.request("model/list", {"limit": 100})
            return {"models": [{"id": m["model"], "name": m.get("displayName", m["model"]), "default": m.get("isDefault", False)} for m in result.get("data", []) if isinstance(m.get("model"), str)]}

    async def interrupt(self, session_id, request_id):
        run = self.active.get(session_id)
        if not run or run["request_id"] != request_id:
            raise CodexError("STALE_OPERATION")
        run["cancel"] = True
        if run.get("turn"):
            await self.transport.request("turn/interrupt", {"threadId": run["thread"], "turnId": run["turn"]})
        try:
            await asyncio.wait_for(run["done"].wait(), 10)
        except asyncio.TimeoutError:
            await self.transport.close()
            raise CodexError("RUNTIME_TIMEOUT") from None
        return {"success": True, "interrupted": True, "session_id": session_id, "request_id": request_id}

    async def invoke_governed(self, prompt: str, *, model=None, timeout_s: float = 120,
                              system: str | None = None, _trace=None, local_conversation=False,
                              reasoning_effort: str | None = None, expected_account_fingerprint=None):
        """One fresh, tool-free research turn through the existing owner.

        Governed calls use a private provider alias: current Codex reserves
        built-in provider IDs, while a custom OpenAI-authenticated provider
        can enforce zero HTTP/stream retries without changing normal chat.
        No chat binding is read or written. The deadline covers account
        admission, context creation, submission and every streamed notification.
        An optional medium-effort pin must resolve at thread/start before any
        turn is submitted. The environment pin applies only to governed research,
        while local conversation retains its existing behavior unless explicit.
        """
        if not isinstance(prompt, str) or not prompt.strip() or not 0 < timeout_s <= 600:
            raise CodexError("INVALID_INPUT")
        requested_effort = reasoning_effort
        if requested_effort is None and not local_conversation:
            requested_effort = os.environ.get("JIUWENSWARM_GOVERNED_REASONING_EFFORT") or None
        if requested_effort is not None and requested_effort != "medium":
            raise CodexError("INVALID_REASONING_EFFORT")
        thread_config = {} if local_conversation else {
            "model_providers.ai4r_governed.name": "AI4Research governed subscription",
            "model_providers.ai4r_governed.wire_api": "responses",
            "model_providers.ai4r_governed.requires_openai_auth": True,
            "model_providers.ai4r_governed.request_max_retries": 0,
            "model_providers.ai4r_governed.stream_max_retries": 0,
        }
        if requested_effort is not None:
            thread_config["model_reasoning_effort"] = requested_effort
        key = ("governed", uuid.uuid4().hex)
        queue = asyncio.Queue(maxsize=4096)
        run = {"request_id": key[1], "queue": queue, "turn": None,
               "thread": None, "cancel": False, "done": asyncio.Event()}
        completed = False
        effective_model = None
        usage = {"input_tokens": None, "output_tokens": None,
                 "cost_amount": None, "currency": None, "unavailable_reasons": []}
        parts = {}
        failure = None
        pilot_budget = None
        if os.environ.get('AI4R_PILOT_BUDGET_DIRECTORY'):
            from jiuwenswarm.research.pilot_budget import PilotBudget, PilotLimitReached
            try:
                pilot_budget = PilotBudget(os.environ['AI4R_PILOT_BUDGET_DIRECTORY'])
                timeout_s = min(timeout_s, pilot_budget.claim(key[1], model))
            except PilotLimitReached:
                pilot_budget.close()
                raise CodexError('PILOT_BUDGET_EXHAUSTED') from None
            except Exception:
                if pilot_budget is not None:
                    pilot_budget.close()
                raise CodexError('PILOT_BUDGET_UNAVAILABLE') from None

        async def native_request(method, params):
            if _trace is None:
                return await self.transport.request(method, params)
            return await self.transport.request(method, params, wire_observer=_trace.request_observer(method))

        def observed_failure():
            if not run['turn'] and not effective_model and not any(usage[key] is not None for key in ('input_tokens','output_tokens')):
                return None
            observed_usage=dict(usage)
            observed_usage['unavailable_reasons']=[f'{field}: not reported by packaged Codex'
                for field in ('input_tokens','output_tokens','cost_amount','currency') if usage[field] is None]
            return {'identity':{'requested':model or 'codex-default','effective':effective_model,
                    'basis':'packaged app-server thread/start resolved model' if effective_model else 'effective model not reported'},
                'usage':observed_usage,'provider_request_id':None,'observed_runtime':True}

        def receive(method, params):
            if params.get("threadId") == run["thread"] or method in {"transport/closed", "account/changed", "transport/unsupported-request"}:
                if queue.full():
                    while not queue.empty():
                        queue.get_nowait()
                    queue.put_nowait(("transport/closed", {}))
                else:
                    queue.put_nowait((method, params))

        try:
            async with asyncio.timeout(timeout_s):
                async with self._account_lock:
                    status = await self._status()
                    if status["state"] != "ready":
                        raise CodexError("SUBSCRIPTION_REQUIRED" if status["state"] == "subscription_required" else "SIGN_IN_REQUIRED")
                    if not self.account_fingerprint:
                        raise CodexError("ACCOUNT_IDENTITY_UNAVAILABLE")
                    if expected_account_fingerprint is not None and self.account_fingerprint != expected_account_fingerprint:
                        raise CodexError('ACCOUNT_IDENTITY_MISMATCH')
                    self.active[key] = run
                    run["epoch"] = self.epoch
                    # Per-thread config prevents CLI network retries for governed
                    # work while preserving the existing chat profile unchanged.
                    if _trace is not None:
                        self.transport.wire_listeners.add(_trace.notification)
                    result = await native_request("thread/start", {
                        "cwd": str(self.root / "chat-workspace"),
                        "sandbox": "read-only", "approvalPolicy": "never",
                        "modelProvider": "openai" if local_conversation else "ai4r_governed",
                        "model": model, "ephemeral": True,
                        "developerInstructions": system or "Execute the supplied governed instruction. Tools are unavailable.",
                        **({"config": thread_config} if thread_config else {}),
                    })
                    run["thread"] = result["thread"]["id"]
                    if _trace is not None:
                        _trace.bind_thread(run['thread'])
                    effective_model = result.get("model")
                    if model and effective_model != model:
                        raise CodexError('MODEL_IDENTITY_MISMATCH')
                    # Match the pinned host helper's canonical app-server
                    # ThreadStartResponse field, never infer a default effort.
                    if requested_effort is not None and result.get("reasoningEffort") != requested_effort:
                        raise CodexError("REASONING_EFFORT_MISMATCH")
                    self.transport.listeners.add(receive)
                result = await native_request("turn/start", {
                    "threadId": run["thread"], "input": [{"type": "text", "text": prompt}],
                    "model": model, "approvalPolicy": "never",
                    **({"effort": requested_effort} if requested_effort is not None else {}),
                })
                run["turn"] = result["turn"]["id"]
                while True:
                    method, params = await queue.get()
                    if method == "transport/unsupported-request":
                        raise CodexError("TOOLS_UNAVAILABLE")
                    if method in {"transport/closed", "account/changed"}:
                        raise CodexError("RUNTIME_DISCONNECTED")
                    turn_id = params.get("turnId") or (params.get("turn") or {}).get("id")
                    if turn_id != run["turn"]:
                        continue
                    _validate_text_only_event(method, params)
                    if method == "model/rerouted":
                        # Preserve the fact in the exception's stable reason;
                        # never accept an unexpected server-side model change.
                        raise CodexError("MODEL_REROUTED")
                    if method == "item/agentMessage/delta":
                        delta = params.get("delta")
                        if not isinstance(delta, str):
                            raise CodexError("INVALID_OUTPUT")
                        ident = params.get("itemId", "message")
                        parts[ident] = parts.get(ident, "") + delta
                    elif method == "thread/tokenUsage/updated":
                        last = (params.get("tokenUsage") or {}).get("last") or {}
                        for source, target in (("inputTokens", "input_tokens"), ("outputTokens", "output_tokens")):
                            value = last.get(source)
                            if type(value) is int and value >= 0:
                                usage[target] = value
                    elif method == "turn/completed":
                        turn = params["turn"]
                        completed = True
                        if turn.get("status") != "completed":
                            raise CodexError("TURN_FAILED")
                        messages = [item["text"] for item in turn.get("items", [])
                                    if item.get("type") == "agentMessage" and isinstance(item.get("text"), str)]
                        text = "\n".join(messages) if messages else "".join(parts.values())
                        if not text:
                            raise CodexError("INVALID_OUTPUT")
                        usage["unavailable_reasons"] = [f"{field}: not reported by packaged Codex"
                                                         for field in ("input_tokens", "output_tokens", "cost_amount", "currency")
                                                         if usage[field] is None]
                        return {"text": text, "thread_id": run["thread"], "turn_id": run["turn"],
                                "provider_request_id": None, "usage": usage,
                                "identity": {"requested": model or "codex-default",
                                             "effective": effective_model,
                                             "basis": "packaged app-server thread/start resolved model" if effective_model else "effective model not reported"},
                                "observed_runtime": True}
        except TimeoutError:
            failure=CodexError('RUNTIME_TIMEOUT')
            raise failure from None
        except BaseException as error:
            failure=error
            raise
        finally:
            try:
                if not completed and run["thread"] and run["turn"]:
                    try:
                        async with asyncio.timeout(3):
                            await native_request("turn/interrupt", {
                                "threadId": run["thread"], "turnId": run["turn"]})
                            # An interrupt request reply is not terminal proof.
                            while True:
                                method, params = await queue.get()
                                turn_id = params.get("turnId") or (params.get("turn") or {}).get("id")
                                if method=='thread/tokenUsage/updated' and turn_id==run['turn']:
                                    last=(params.get('tokenUsage') or {}).get('last') or {}
                                    for source,target in (('inputTokens','input_tokens'),('outputTokens','output_tokens')):
                                        if type(last.get(source)) is int and last[source]>=0:usage[target]=last[source]
                                if method == "turn/completed" and turn_id == run["turn"]:
                                    break
                                if method in {"transport/closed", "account/changed"}:
                                    raise CodexError("RUNTIME_DISCONNECTED")
                    except (Exception, asyncio.CancelledError):
                        # Await the owned subprocess exit when no matching
                        # terminal turn can be established. Never replay it.
                        await self.transport.close()
                elif not completed and run.get("epoch") == self.epoch:
                    await self.transport.close()
            except (Exception, asyncio.CancelledError):
                failure=CodexError('CONTAINMENT_UNCERTAIN')
                raise failure from None
            finally:
                if failure is not None:
                    observation=observed_failure()
                    if observation is not None:failure.observation=observation
                self.transport.listeners.discard(receive)
                if _trace is not None:
                    self.transport.wire_listeners.discard(_trace.notification)
                self.active.pop(key, None)
                run["done"].set()
                if pilot_budget is not None:
                    try:
                        pilot_budget.finish(key[1], 'completed' if completed and failure is None else type(failure).__name__, effective_model)
                    finally:
                        pilot_budget.close()

    async def stream(self, session_id, request_id, text, model=None):
        if not session_id or not request_id or not isinstance(text, str) or not text.strip():
            raise CodexError("INVALID_INPUT")
        queue = asyncio.Queue(maxsize=4096)
        run = {"request_id": request_id, "queue": queue, "turn": None, "cancel": False, "done": asyncio.Event()}
        async with self._account_lock:
            status = await self._status()
            if status["state"] != "ready":
                raise CodexError("SUBSCRIPTION_REQUIRED" if status["state"] == "subscription_required" else "SIGN_IN_REQUIRED")
            if session_id in self.active:
                raise CodexError("BUSY")
            binding = self.bindings.get(session_id)
            if binding and (binding.get("epoch") != self.epoch or binding.get("owner") != self.account_fingerprint):
                raise CodexError("NEW_SESSION_REQUIRED")
            if not self.account_fingerprint:
                raise CodexError("ACCOUNT_IDENTITY_UNAVAILABLE")
            if not binding:
                result = await self.transport.request("thread/start", {"cwd": str(self.root / "chat-workspace"), "sandbox": "read-only", "approvalPolicy": "never", "allowProviderModelFallback": False, "modelProvider": "openai", "model": model, "developerInstructions": "Answer ordinary text conversations. Tools are unavailable in this milestone. Do not claim to have executed actions."})
                binding = {"thread": result["thread"]["id"], "epoch": self.epoch, "owner": self.account_fingerprint}
                self.bindings[session_id] = binding
                self._save()
            run["thread"] = binding["thread"]
            run["epoch"] = self.epoch
            self.active[session_id] = run

        def receive(method, params):
            if params.get("threadId") == run["thread"] or method in {"transport/closed", "account/changed", "transport/unsupported-request"}:
                if queue.full():
                    # Stop admission/stream on overflow rather than silently losing
                    # a terminal notification and leaving the UI running forever.
                    while not queue.empty():
                        queue.get_nowait()
                    queue.put_nowait(("transport/closed", {}))
                else:
                    queue.put_nowait((method, params))

        self.transport.listeners.add(receive)
        parts = []
        completed = False
        try:
            result = await self.transport.request("turn/start", {"threadId": run["thread"], "input": [{"type": "text", "text": text}], "model": model})
            run["turn"] = result["turn"]["id"]
            if run["cancel"]:
                await self.transport.request("turn/interrupt", {"threadId": run["thread"], "turnId": run["turn"]})
            while True:
                try:
                    method, params = await asyncio.wait_for(queue.get(), 180)
                except asyncio.TimeoutError:
                    raise CodexError("RUNTIME_TIMEOUT") from None
                if method == "transport/unsupported-request":
                    raise CodexError("TOOLS_UNAVAILABLE")
                if method in {"transport/closed", "account/changed"}:
                    raise CodexError("RUNTIME_DISCONNECTED")
                turn_id = params.get("turnId") or (params.get("turn") or {}).get("id")
                if turn_id != run["turn"]:
                    continue
                _validate_text_only_event(method, params)
                if method == "item/agentMessage/delta":
                    delta = params.get("delta", "")
                    if isinstance(delta, str):
                        parts.append(delta)
                        yield {"event_type": "chat.delta", "content": delta, "session_id": session_id}
                elif method == "turn/completed":
                    completed = True
                    status = params["turn"].get("status")
                    if status not in {"completed", "interrupted"}:
                        raise CodexError("TURN_FAILED")
                    yield {"event_type": "chat.final", "content": "".join(parts), "session_id": session_id, "final_mode": "replace_turn", "cancelled": status == "interrupted"}
                    return
        finally:
            run["done"].set()
            self.transport.listeners.discard(receive)
            self.active.pop(session_id, None)
            if not completed:
                # May include unknown delivery; never reuse/replay that thread.
                binding["epoch"] = "interrupted"
                self._save()
                # Logout/transport failure may already have created a new owner
                # generation. Do not close its replacement process from an old turn.
                if run["epoch"] == self.epoch:
                    await self.transport.close()


_services = {}


def get_service():
    from jiuwenswarm.common.utils import get_user_workspace_dir
    if os.environ.get("JIUWENSWARM_M1_PROFILE") == "1":
        accounts = os.environ.get("JIUWENSWARM_M1_ACCOUNTS")
        if not accounts or not Path(accounts).is_absolute():
            raise CodexError("ACCOUNT_STORAGE_UNAVAILABLE")
        root = Path(accounts).resolve() / "subscription"
    else:
        root = Path(get_user_workspace_dir()).resolve() / "subscription"
    if root not in _services:
        _services[root] = SubscriptionService(root)
    return _services[root]


async def close_services():
    services = list(_services.values())
    _services.clear()
    for service in services:
        await service.transport.close()
