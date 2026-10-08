"""Single process owner for managed login and session-isolated text turns."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from .transport import AppServerTransport, CodexError


class SubscriptionService:
    def __init__(self, root: Path, *, transport=None):
        self.root = root.resolve()
        self.transport = transport or AppServerTransport(self.root)
        self.epoch = uuid.uuid4().hex
        self.account_fingerprint = None
        self.active = {}
        self.login_id = None
        self.login_error = None
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
        if method == "transport/closed":
            self.epoch = uuid.uuid4().hex
        if method == "account/login/completed" and params.get("loginId") == self.login_id:
            self.login_id = None
            self.login_error = None if params.get("success") is True else "LOGIN_FAILED"

    def _save(self):
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.binding_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.bindings), encoding="utf-8")
        tmp.replace(self.binding_path)

    async def _status(self):
        await self.transport.start()
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
        self.account_fingerprint = fingerprint
        return {"enabled": True, "state": "ready" if kind == "chatgpt" else "subscription_required" if kind else "signing_in" if self.login_id else "signed_out", "plan": account.get("planType") if kind == "chatgpt" else None, "error": self.login_error, "login_attempt_id": self.login_id, "active_runs": len(self.active), "milestone": "text_chat"}

    async def status(self):
        async with self._account_lock:
            return await self._status()

    async def login(self):
        async with self._account_lock:
            await self.transport.start()
            if self.active:
                raise CodexError("BUSY")
            if self.login_id:
                raise CodexError("LOGIN_PENDING")
            self.epoch = uuid.uuid4().hex
            result = await self.transport.request("account/login/start", {"type": "chatgpt"})
            url = result.get("authUrl", "")
            parsed = urlparse(url)
            if result.get("type") != "chatgpt" or parsed.scheme != "https" or parsed.hostname not in {"auth.openai.com", "auth0.openai.com", "auth.chatgpt.com"} or not result.get("loginId"):
                await self.transport.close()
                raise CodexError("LOGIN_PROTOCOL_ERROR")
            self.login_id = result["loginId"]
            self.login_error = None
            return {"state": "signing_in", "auth_url": url, "login_attempt_id": self.login_id}

    async def cancel_login(self, attempt_id):
        async with self._account_lock:
            if not self.login_id or not isinstance(attempt_id, str) or attempt_id != self.login_id:
                raise CodexError("STALE_OPERATION")
            if self.login_id:
                await self.transport.request("account/login/cancel", {"loginId": self.login_id})
                self.login_id = None
            return await self._status()

    async def logout(self):
        async with self._account_lock:
            self.epoch = uuid.uuid4().hex
            self.account_fingerprint = None
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

    async def invoke_fresh(self, text, *, role, developer_instructions, timeout_seconds, max_output_bytes, output_schema=None):
        """One protected, bounded text invocation without conversation reuse.

        M1-IF-INTENT@r1. The host records observations; generated output has no
        acceptance authority. Ordinary chat remains on ``stream``.
        """
        if role not in {"compiler", "verifier"} or not isinstance(text, str) or not text:
            raise CodexError("INVALID_INPUT")
        started = time.monotonic()
        ident = uuid.uuid4().hex
        queue = asyncio.Queue(maxsize=4096)
        result = {"conversation_id": f"unavailable:{ident}", "model": None,
                  "status": "environment_blocked", "raw_output": "", "tools": [],
                  "effects": [], "usage": None, "error_code": None}
        run = {"request_id": ident, "queue": queue, "turn": None,
               "cancel": False, "done": asyncio.Event()}
        completed = False
        output_bytes = 0

        def receive(method, params):
            if params.get("threadId") == run.get("thread") or method in {"transport/closed", "account/changed", "server/request/rejected"}:
                if queue.full():
                    while not queue.empty():
                        queue.get_nowait()
                    queue.put_nowait(("observation/overflow", {}))
                else:
                    queue.put_nowait((method, params))

        try:
            async with asyncio.timeout(timeout_seconds):
                async with self._account_lock:
                    status = await self._status()
                    if status["state"] != "ready":
                        raise CodexError("SIGN_IN_REQUIRED")
                    if not self.account_fingerprint:
                        raise CodexError("ACCOUNT_IDENTITY_UNAVAILABLE")
                    if self.active:
                        raise CodexError("BUSY")
                    response = await self.transport.request("thread/start", {
                        "cwd": str(self.root / "chat-workspace"), "sandbox": "read-only",
                        "approvalPolicy": "untrusted", "allowProviderModelFallback": False,
                        "modelProvider": "openai", "developerInstructions": developer_instructions,
                    })
                    run["thread"] = response["thread"]["id"]
                    run["epoch"] = self.epoch
                    result["conversation_id"] = run["thread"]
                    result["model"] = response.get("model") or response["thread"].get("model")
                    self.active[ident] = run
                self.transport.listeners.add(receive)
                response = await self.transport.request("turn/start", {
                    "threadId": run["thread"], "input": [{"type": "text", "text": text}],
                    **({"outputSchema": output_schema} if output_schema is not None else {}),
                })
                run["turn"] = response["turn"]["id"]
                result["status"] = "failed"
                while True:
                    method, params = await queue.get()
                    if method in {"transport/closed", "account/changed", "observation/overflow"}:
                        raise CodexError("RUNTIME_DISCONNECTED")
                    if method == "server/request/rejected":
                        result["tools"].append(str(params.get("method", "unknown")))
                        result["effects"].append("attempted_prohibited_tool")
                        raise CodexError("PROHIBITED_TOOL")
                    if method == "thread/tokenUsage/updated":
                        if params.get("turnId") != run["turn"]:
                            continue
                        usage = (params.get("tokenUsage") or {}).get("total")
                        if isinstance(usage, dict) and all(isinstance(usage.get(k), int) and not isinstance(usage[k], bool) and usage[k] >= 0 for k in ("inputTokens", "outputTokens", "totalTokens")):
                            result["usage"] = {"input_tokens": usage["inputTokens"], "output_tokens": usage["outputTokens"], "total_tokens": usage["totalTokens"]}
                        continue
                    turn_id = params.get("turnId") or (params.get("turn") or {}).get("id")
                    if turn_id != run["turn"]:
                        continue
                    if method == "item/started":
                        kind = (params.get("item") or {}).get("type")
                        if kind not in {"userMessage", "agentMessage", "reasoning"}:
                            result["tools"].append(str(kind or "unknown"))
                            result["effects"].append("attempted_prohibited_tool")
                            raise CodexError("PROHIBITED_TOOL")
                    elif method == "item/agentMessage/delta":
                        delta = params.get("delta")
                        if not isinstance(delta, str):
                            raise CodexError("INVALID_OUTPUT")
                        output_bytes += len(delta.encode("utf-8"))
                        if output_bytes > max_output_bytes:
                            raise CodexError("OUTPUT_LIMIT")
                        result["raw_output"] += delta
                    elif method == "turn/completed":
                        completed = True
                        status = params["turn"].get("status")
                        result["status"] = "completed" if status == "completed" else "cancelled" if status == "interrupted" else "failed"
                        result["error_code"] = None if status == "completed" else "CANCELLED" if status == "interrupted" else "TURN_FAILED"
                        break
        except TimeoutError:
            result.update(status="timeout", error_code="CALL_TIMEOUT")
        except asyncio.CancelledError:
            result.update(status="cancelled", error_code="CANCELLED")
        except CodexError as exc:
            result["error_code"] = str(exc)
            if run.get("turn"):
                result["status"] = "failed"
        except (KeyError, TypeError, ValueError):
            result.update(status="failed", error_code="INVALID_RUNTIME_RESPONSE")
        finally:
            self.transport.listeners.discard(receive)
            self.active.pop(ident, None)
            run["done"].set()
            if run.get("thread") and not completed and run.get("epoch") == self.epoch:
                # No uncertain work survives a bounded invocation or is replayed.
                await self.transport.close()
            result["elapsed_seconds"] = max(0.0, time.monotonic() - started)
        return result

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
                result = await self.transport.request("thread/start", {"cwd": str(self.root / "chat-workspace"), "sandbox": "read-only", "approvalPolicy": "untrusted", "allowProviderModelFallback": False, "modelProvider": "openai", "model": model, "developerInstructions": "Answer ordinary text conversations. Tools are unavailable in this milestone. Do not claim to have executed actions."})
                binding = {"thread": result["thread"]["id"], "epoch": self.epoch, "owner": self.account_fingerprint}
                self.bindings[session_id] = binding
                self._save()
            run["thread"] = binding["thread"]
            run["epoch"] = self.epoch
            self.active[session_id] = run

        def receive(method, params):
            if params.get("threadId") == run["thread"] or method in {"transport/closed", "account/changed"}:
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
                if method in {"transport/closed", "account/changed"}:
                    raise CodexError("RUNTIME_DISCONNECTED")
                turn_id = params.get("turnId") or (params.get("turn") or {}).get("id")
                if turn_id != run["turn"]:
                    continue
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
    root = Path(get_user_workspace_dir()).resolve() / "subscription"
    if root not in _services:
        _services[root] = SubscriptionService(root)
    return _services[root]


async def close_services():
    services = list(_services.values())
    _services.clear()
    for service in services:
        await service.transport.close()
