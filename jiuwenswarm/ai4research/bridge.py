"""M0-IF-001@r2: one-shot native Codex through protected local IPC.

The POSIX application container is the supported real execution boundary.
Other hosts fail closed; an adapter TCP listener is never substituted.
"""
from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import math
import os
import secrets
import stat
import time
from pathlib import Path

from .common import GovernanceError, canonical_json, hash_json, utc_now

MAX_FRAME = 262144
MAX_EVENTS = 8192
PACKAGE = Path(__file__).parent
PROMPTS = {"compiler": PACKAGE / "intent/compiler.prompt.md",
           "verifier": PACKAGE / "intent/verifier.prompt.md"}


def _safe_path(path):
    """Inspect original custody components before any operation resolves them."""
    path = Path(path).absolute()
    if ".." in path.parts:
        raise GovernanceError("security_unavailable", "Custody traversal is prohibited.")
    for component in reversed((path, *path.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise GovernanceError("security_unavailable", "Custody symlinks and reparse points are prohibited.")
    return path


def _validate_request(request):
    if not isinstance(request, dict) or set(request) != {"role", "model", "input_data", "identities", "timeout_seconds"}:
        raise GovernanceError("invalid_input", "Unsupported model invocation fields.")
    identities = request["identities"]
    timeout = request["timeout_seconds"]
    if (not isinstance(request["role"], str) or request["role"] not in PROMPTS or not isinstance(request["model"], str) or
            not request["model"] or len(request["model"]) > 256 or
            not isinstance(identities, dict) or
            any(not isinstance(identities.get(key), str) or not identities[key] or len(identities[key]) > 256
                for key in ("run_id", "node_id", "attempt_id", "invocation_id", "role")) or
            identities["role"] != request["role"] or
            isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or
            not math.isfinite(timeout) or timeout <= 0 or timeout > 300):
        raise GovernanceError("invalid_input", "Invalid bounded model invocation.")
    identity_keys = {"run_id", "node_id", "attempt_id", "invocation_id", "role", "runtime_identity"}
    if set(identities) - identity_keys:
        raise GovernanceError("policy_denied", "Invocation identities cannot replace runtime observations or add unsupported fields.")
    if "runtime_identity" in identities:
        runtime_identity = identities["runtime_identity"]
        runtime_keys = {"account_fingerprint", "account_epoch", "runtime_version"}
        if (not isinstance(runtime_identity, dict) or set(runtime_identity) != runtime_keys or
                any(not isinstance(runtime_identity[key], str) or not runtime_identity[key] or
                    len(runtime_identity[key]) > 256 for key in runtime_keys)):
            raise GovernanceError("invalid_input", "Frozen runtime identity must contain only its three bounded generation fields.")
    try:
        if len(canonical_json(request)) > MAX_FRAME // 2:
            raise GovernanceError("invalid_input", "Model input exceeded the bounded frame.")
    except (TypeError, ValueError):
        raise GovernanceError("invalid_input", "Model input is not a finite JSON value.") from None


class NativeCompletionBackend:
    """Reuse the application-owned transport, never an ordinary chat thread."""
    is_mock = False

    def __init__(self, service):
        self.service = service
        self._lock = asyncio.Lock()
        self._admitted_account = None

    def bind_account(self, readiness):
        identity = (readiness.get("account_fingerprint"), readiness.get("account_epoch"))
        if not readiness.get("ready") or any(not isinstance(part, str) or not part for part in identity):
            raise GovernanceError("environment_unavailable", "Authenticated account generation is unavailable.")
        if self._lock.locked():
            raise GovernanceError("model_busy", "Account admission cannot change during an invocation.")
        self._admitted_account = identity

    def _check_account(self, initial):
        current = (self.service.account_fingerprint, self.service.epoch)
        if current != initial or (self._admitted_account is not None and current != self._admitted_account):
            raise GovernanceError("account_changed", "Model account generation changed; this invocation cannot be replayed.")

    async def readiness(self):
        try:
            status = await self.service.status()
            if status.get("state") != "ready":
                return {"ready": False, "authentication": status.get("state", "unavailable"),
                        "models": [], "runtime": "Codex App Server 0.144.4"}
            models = (await self.service.models())["models"]
            from importlib.metadata import version
            runtime = version("openai-codex-cli-bin")
            identified = bool(self.service.account_fingerprint and self.service.epoch)
            return {"ready": bool(models) and identified and runtime == "0.144.4",
                    "authentication": "ready" if identified else "identity_unavailable", "models": models,
                    "runtime": "Codex App Server " + runtime, "runtime_version": runtime,
                    "account_fingerprint": self.service.account_fingerprint, "account_epoch": self.service.epoch,
                    "is_mock": False}
        except Exception as exc:
            if isinstance(exc, asyncio.CancelledError):
                raise
            return {"ready": False, "authentication": "unavailable", "models": [],
                    "error": "environment_unavailable", "runtime": "unavailable"}

    async def complete(self, *, role, model, input_data, identities, timeout_seconds):
        from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError
        _validate_request(dict(role=role, model=model, input_data=input_data, identities=identities, timeout_seconds=timeout_seconds))
        transport = self.service.transport
        started = time.monotonic()
        deadline = started + timeout_seconds
        # A second call never queues behind an owned turn and cannot time out
        # by closing that other turn's process. Fresh user work may be submitted
        # after the explicit busy halt; this invocation is never retried.
        if self._lock.locked():
            raise GovernanceError("model_busy", "The application-owned native model already has an active invocation.")
        async with self._lock:
            try:
                readiness = await asyncio.wait_for(self.readiness(), max(0, deadline - time.monotonic()))
            except TimeoutError:
                await transport.close()
                raise GovernanceError("timeout", "Native invocation exceeded the frozen wall-time limit during readiness.") from None
            except asyncio.CancelledError:
                await transport.close()
                raise
            if not readiness["ready"] or model not in {m["id"] for m in readiness["models"]}:
                raise GovernanceError("environment_unavailable", "The frozen native model is not authenticated and available.")
            queue = asyncio.Queue(maxsize=2048)
            thread_id = None
            turn_id = None
            done = False
            overflow = False
            native_failure = None
            parts = []
            output_bytes = 0
            initial_account = (self.service.account_fingerprint, self.service.epoch)
            self._check_account(initial_account)
            runtime_identity = {"account_fingerprint": initial_account[0], "account_epoch": initial_account[1],
                                "runtime_version": readiness["runtime_version"]}
            if "runtime_identity" in identities and identities["runtime_identity"] != runtime_identity:
                raise GovernanceError("account_changed", "Frozen runtime account generation does not match native readiness.")
            for key, value in zip(("account_fingerprint", "account_epoch"), initial_account):
                if key in identities and identities[key] != value:
                    raise GovernanceError("account_changed", "Frozen run model account does not match the current generation.")
            events = 0

            def receive(method, params):
                nonlocal overflow, events, native_failure
                if method in {"transport/closed", "account/changed"} or (thread_id is not None and params.get("threadId") == thread_id):
                    if method in {"model/rerouted", "error"} and (turn_id is None or params.get("turnId") == turn_id):
                        # A queued completion cannot conceal an already observed
                        # refusal, including one delivered during turn/start.
                        native_failure = method
                    events += 1
                    if queue.full() or events > MAX_EVENTS:
                        overflow = True
                    else:
                        queue.put_nowait((method, params))

            def check_native_failure():
                if native_failure == "model/rerouted":
                    raise GovernanceError("policy_denied", "Native model rerouting is prohibited by the frozen route.")
                if native_failure == "error":
                    raise GovernanceError("execution_failed", "Native turn reported an error; automatic replay is forbidden.")

            transport.listeners.add(receive)
            try:
                async with asyncio.timeout(max(0, deadline - time.monotonic())):
                    if time.monotonic() >= deadline:
                        raise GovernanceError("timeout", "Native invocation budget expired before dispatch.")
                    result = await transport.request("thread/start", {
                        "cwd": str(transport.cwd), "sandbox": "read-only",
                        "approvalPolicy": "untrusted",
                        "modelProvider": "openai", "model": model,
                        "developerInstructions": PROMPTS[role].read_text(encoding="utf-8")})
                    # The standard 0.144.4 reply confirms thread configuration.
                    # allowProviderModelFallback is experimental; this transport
                    # has not negotiated experimental fields and never relies on it.
                    thread = result.get("thread") if isinstance(result, dict) else None
                    if not isinstance(thread, dict):
                        raise GovernanceError("delivery_unknown", "Native runtime returned no attributable thread configuration.")
                    thread_id = thread.get("id")
                    if not isinstance(thread_id, str) or not thread_id:
                        raise GovernanceError("delivery_unknown", "Native runtime returned no attributable thread.")
                    configured_model = result.get("model")
                    configured_provider = result.get("modelProvider")
                    runtime_version = thread.get("cliVersion")
                    if not all(isinstance(value, str) and value for value in
                               (configured_model, configured_provider, runtime_version, thread.get("modelProvider"))):
                        raise GovernanceError("delivery_unknown", "Native thread configuration identity is unavailable.")
                    if configured_model != model or configured_provider != "openai" or thread["modelProvider"] != configured_provider:
                        raise GovernanceError("policy_denied", "Native thread configuration changed the frozen model route.")
                    if runtime_version != readiness["runtime_version"] or runtime_version != "0.144.4":
                        raise GovernanceError("environment_unavailable", "Native thread CLI version differs from the admitted runtime.")
                    self._check_account(initial_account)
                    if time.monotonic() >= deadline:
                        raise GovernanceError("timeout", "Native invocation budget expired before turn dispatch.")
                    result = await transport.request("turn/start", {
                        "threadId": thread_id, "model": model,
                        "input": [{"type": "text", "text": canonical_json(input_data).decode("utf-8")} ]})
                    turn = result.get("turn") if isinstance(result, dict) else None
                    turn_id = turn.get("id") if isinstance(turn, dict) else None
                    if not isinstance(turn_id, str) or not turn_id:
                        raise GovernanceError("delivery_unknown", "Native runtime returned no attributable turn.")
                    while True:
                        self._check_account(initial_account)
                        check_native_failure()
                        if overflow:
                            raise GovernanceError("evidence_overflow", "Native event capture exceeded its bound.")
                        method, params = await queue.get()
                        if method == "transport/closed":
                            raise GovernanceError("delivery_unknown", "Native transport ended without a confirmed completion.")
                        if method == "account/changed":
                            raise GovernanceError("account_changed", "Native account changed during the invocation.")
                        if (params.get("turnId") or (params.get("turn") or {}).get("id")) != turn_id:
                            continue
                        if method == "model/rerouted":
                            raise GovernanceError("policy_denied", "Native model rerouting is prohibited by the frozen route.")
                        if method == "error":
                            # Even a native willRetry notification is a halt. The
                            # owned process is interrupted and closed, never replayed.
                            raise GovernanceError("execution_failed", "Native turn reported an error; automatic replay is forbidden.")
                        if method == "item/started":
                            item_type = (params.get("item") or {}).get("type")
                            if item_type not in {"userMessage", "agentMessage", "reasoning"}:
                                raise GovernanceError("prohibited_effect", "Native model attempted an effect outside text assessment.")
                        elif method == "item/agentMessage/delta":
                            delta = params.get("delta")
                            if not isinstance(delta, str):
                                raise GovernanceError("malformed_output", "Invalid text delta.")
                            parts.append(delta)
                            output_bytes += len(delta.encode("utf-8"))
                            if output_bytes > MAX_FRAME // 2:
                                raise GovernanceError("output_limit", "Native output exceeded its finite bound.")
                        elif method == "turn/completed":
                            if params["turn"].get("status") == "interrupted":
                                raise GovernanceError("cancelled", "Native turn was interrupted; automatic replay is forbidden.")
                            if params["turn"].get("status") != "completed":
                                raise GovernanceError("execution_failed", "Native completion did not succeed.")
                            break
                    status = await self.service.status()
                    self._check_account(initial_account)
                    check_native_failure()
                    if status.get("state") != "ready":
                        raise GovernanceError("account_changed", "Model account changed during the frozen invocation.")
                    done = True
                return {"text": "".join(parts), "thread_id": thread_id, "turn_id": turn_id,
                        "model": configured_model, "provider": "openai_codex_subscription",
                        "requested_model": model, "configured_model": configured_model,
                        "configured_model_provider": configured_provider,
                        "model_identity_basis": "native_thread_start_configuration",
                        "served_model": None,
                        "served_model_unavailable_reason": "Codex 0.144.4 turn replies do not independently identify the model that served the completion.",
                        "runtime_version": runtime_version, "elapsed_seconds": time.monotonic() - started,
                        "model_calls": 1, "usage": None, "usage_unavailable_reason": "Reliable per-call usage mapping is not exposed by this boundary.",
                        "cost": None, "cost_unavailable_reason": "Subscription allowance is not per-call billing.",
                        "seed": None, "seed_unavailable_reason": "Native turn API has no seed control.",
                        **identities, "account_fingerprint": initial_account[0], "account_epoch": initial_account[1],
                        "effects": [], "is_mock": False}
            except TimeoutError as exc:
                raise GovernanceError("timeout", "Native invocation exceeded the frozen wall-time limit.") from exc
            except CodexError as exc:
                raise GovernanceError("delivery_unknown", "Native invocation failed without permission to replay.") from exc
            finally:
                transport.listeners.discard(receive)
                if not done:
                    if thread_id and turn_id:
                        with contextlib.suppress(Exception):
                            await asyncio.wait_for(transport.request("turn/interrupt", {"threadId": thread_id, "turnId": turn_id}), 1)
                    # Ownership is explicit; no other account/IDE process is touched.
                    await transport.close()


class LocalModelBridge:
    """A same-user private UDS plus one-use host-granted request identities."""
    is_mock = False

    def __init__(self, directory: Path, backend):
        self.directory = _safe_path(directory)
        self.socket_path = self.directory / "model.sock"
        self.backend = backend
        self.token = secrets.token_hex(32)
        self.server = None
        self.grants = {}
        self.used = set()
        self.active = {}
        self.handlers = {}
        self._socket_identity = None

    async def start(self):
        if os.name != "posix":
            raise GovernanceError("environment_unavailable", "Protected real model IPC requires the supported POSIX container; Windows is not silently downgraded.")
        _safe_path(self.directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = self.directory.lstat()
        if self.directory.is_symlink() or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise GovernanceError("security_unavailable", "Model IPC directory must be owned and private (0700).")
        if self.socket_path.exists() or self.socket_path.is_symlink():
            raise GovernanceError("security_unavailable", "Refuse an existing model IPC endpoint.")
        self.server = await asyncio.start_unix_server(self._serve, path=str(self.socket_path), limit=MAX_FRAME)
        os.chmod(self.socket_path, 0o600)
        self._socket_identity = self.socket_path.stat().st_ino

    async def close(self):
        try:
            if self.server:
                self.server.close()
                await self.server.wait_closed()
                self.server = None
                # Never unlink an endpoint substituted by a different owner.
                if self.socket_path.exists() and self.socket_path.lstat().st_ino == self._socket_identity:
                    self.socket_path.unlink()
        finally:
            try:
                tasks = list(self.handlers.values()) + [task for ident, task in self.active.items() if ident not in self.handlers]
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                self.active.clear()
                self.handlers.clear()
                self.token = secrets.token_hex(32)
                self.grants.clear()
                await self.backend.service.transport.close()

    async def readiness(self):
        secure = self.server is not None and os.name == "posix"
        if secure:
            try:
                _safe_path(self.directory)
                info = self.directory.lstat()
                socket = self.socket_path.lstat()
                secure = (info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700 and
                          stat.S_ISSOCK(socket.st_mode) and socket.st_uid == os.getuid() and
                          stat.S_IMODE(socket.st_mode) == 0o600 and socket.st_ino == self._socket_identity)
            except (OSError, GovernanceError):
                secure = False
        if not secure:
            return {"ready": False, "security_ready": False, "authentication": "not_checked",
                    "models": [], "runtime": "not_checked", "ipc": "unavailable", "is_mock": False}
        native = await self.backend.readiness()
        return {**native, "security_ready": secure, "ready": secure and native.get("ready", False),
                "ipc": "private_posix_uds" if secure else "unavailable", "is_mock": False}

    async def complete(self, **request):
        _validate_request(request)
        if not self.server:
            raise GovernanceError("environment_unavailable", "Protected model IPC is not ready.")
        ident = request["identities"]["invocation_id"]
        if ident in self.used or ident in self.grants:
            raise GovernanceError("replay_denied", "An invocation cannot be replayed.")
        self.grants[ident] = hash_json(request)
        try:
            reader, writer = await asyncio.open_unix_connection(str(self.socket_path), limit=MAX_FRAME)
            try:
                writer.write(canonical_json({"token": self.token, "request": request}) + b"\n")
                await writer.drain()
                line = await asyncio.wait_for(reader.readline(), request["timeout_seconds"] + 40)
                if not line or len(line) > MAX_FRAME:
                    raise GovernanceError("delivery_unknown", "Model IPC response is incomplete; replay is forbidden.")
                reply = json.loads(line)
                if "error" in reply:
                    raise GovernanceError(reply["error"]["code"], reply["error"]["message"])
                return reply["result"]
            finally:
                writer.close()
                with contextlib.suppress(OSError, ConnectionError):
                    await writer.wait_closed()
        finally:
            self.grants.pop(ident, None)
            handler = self.handlers.get(ident)
            task = self.active.get(ident)
            # Cancelling the handler propagates exactly one cancellation to its
            # awaited backend. A second cancellation can interrupt process cleanup.
            owned = [handler] if handler and not handler.done() else [task] if task and not task.done() else []
            for item in owned:
                item.cancel()
            if owned:
                await asyncio.gather(*owned, return_exceptions=True)

    async def _serve(self, reader, writer):
        try:
            line = await asyncio.wait_for(reader.readline(), 5)
            if not line or len(line) > MAX_FRAME:
                raise GovernanceError("invalid_input", "Invalid bounded model frame.")
            value = json.loads(line)
            if not hmac.compare_digest(str(value.get("token", "")), self.token):
                raise GovernanceError("policy_denied", "Model IPC authentication failed.")
            request = value["request"]
            _validate_request(request)
            ident = request["identities"]["invocation_id"]
            if request.get("role") not in PROMPTS or self.grants.get(ident) != hash_json(request) or ident in self.used:
                raise GovernanceError("policy_denied", "Request lacks an exact one-use protected grant.")
            self.used.add(ident)
            self.grants.pop(ident, None)
            self.handlers[ident] = asyncio.current_task()
            task = asyncio.create_task(self.backend.complete(**request))
            self.active[ident] = task
            try:
                reply = {"result": await task}
            finally:
                self.active.pop(ident, None)
                self.handlers.pop(ident, None)
        except asyncio.CancelledError:
            writer.close()
            raise
        except GovernanceError as exc:
            reply = {"error": {"code": exc.code, "message": str(exc)}}
        except (ValueError, KeyError, TypeError, OSError, asyncio.TimeoutError):
            reply = {"error": {"code": "invalid_input", "message": "Invalid model IPC request."}}
        except Exception:
            reply = {"error": {"code": "execution_failed", "message": "Owned model invocation failed."}}
        try:
            frame = canonical_json(reply) + b"\n"
            if len(frame) > MAX_FRAME:
                frame = canonical_json({"error": {"code": "output_limit", "message": "Model IPC response exceeded its bound."}}) + b"\n"
            writer.write(frame)
            await writer.drain()
        finally:
            writer.close()
            with contextlib.suppress(OSError, ConnectionError):
                await writer.wait_closed()
