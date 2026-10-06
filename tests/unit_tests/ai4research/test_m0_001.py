"""Fresh native protocol contexts and fail-closed IPC; provider is a fixture."""
import asyncio
from pathlib import Path

import pytest

from jiuwenswarm.ai4research.bridge import LocalModelBridge, NativeCompletionBackend
from jiuwenswarm.ai4research.common import GovernanceError
from jiuwenswarm.server.runtime.codex_subscription.transport import child_environment
from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError


class FixtureTransport:
    def __init__(self, root, behavior="success"):
        self.cwd = root
        self.listeners = set()
        self.requests = []
        self.threads = 0
        self.behavior = behavior
        self.closed = False

    async def request(self, method, params):
        self.requests.append((method, params))
        if method == "thread/start":
            self.threads += 1
            return {"approvalPolicy": "untrusted", "approvalsReviewer": "user", "cwd": str(self.cwd),
                    "model": params["model"], "modelProvider": "openai", "instructionSources": [],
                    "sandbox": {"type": "readOnly", "networkAccess": False},
                    "thread": {"id": f"fixture-thread-{self.threads}", "cliVersion": "0.144.4",
                               "modelProvider": "openai", "cwd": str(self.cwd), "createdAt": 0,
                               "updatedAt": 0, "ephemeral": False, "preview": "", "sessionId": "fixture-session",
                               "source": "appServer", "status": {"type": "idle"}, "turns": []}}
        if method == "turn/start":
            thread = params["threadId"]
            events = [] if self.behavior == "timeout" else [
                ("item/agentMessage/delta", {"threadId": thread, "turnId": "fixture-turn", "delta": "{}"}),
                ("turn/completed", {"threadId": thread, "turn": {"id": "fixture-turn", "items": [], "status": "completed"}})]
            if self.behavior == "tool":
                events.insert(0, ("item/started", {"threadId": thread, "turnId": "fixture-turn", "item": {"type": "commandExecution"}}))
            for method_name, payload in events:
                for listener in tuple(self.listeners):
                    listener(method_name, payload)
            return {"turn": {"id": "fixture-turn", "items": [], "status": "inProgress"}}
        return {}

    async def close(self):
        self.closed = True


class FixtureService:
    def __init__(self, root, behavior="success"):
        self.transport = FixtureTransport(root, behavior)
        self.account_fingerprint = "fixture-account"
        self.epoch = "fixture-epoch"
        self.active = {}

    async def status(self):
        return {"state": "ready"}

    async def models(self):
        return {"models": [{"id": "fixture-model", "default": True}]}


def invocation(role="compiler", ident="call-1"):
    return {"role": role, "model": "fixture-model", "input_data": {"original_text": "Compare batteries."},
            "identities": {"run_id": "run-1", "node_id": "intent", "attempt_id": ident,
                           "invocation_id": ident, "role": role}, "timeout_seconds": 1}


@pytest.mark.asyncio
async def test_m0_001_b01_b03_fresh_context_each_role_and_no_chat_history(tmp_path):
    service = FixtureService(tmp_path)
    backend = NativeCompletionBackend(service)
    first = await backend.complete(**invocation())
    second = await backend.complete(**invocation("verifier", "call-2"))
    assert first["thread_id"] != second["thread_id"]
    threads = [p for m, p in service.transport.requests if m == "thread/start"]
    assert len(threads) == 2
    assert all("allowProviderModelFallback" not in p for p in threads)
    assert all(p["model"] == "fixture-model" and p["modelProvider"] == "openai" for p in threads)
    assert "Intent compiler" in threads[0]["developerInstructions"]
    assert "semantic assessment" in threads[1]["developerInstructions"]
    assert not any(m == "thread/resume" for m, _ in service.transport.requests)


@pytest.mark.asyncio
async def test_m0_001_b04_usage_unavailable_never_inferred_as_zero(tmp_path):
    outcome = await NativeCompletionBackend(FixtureService(tmp_path)).complete(**invocation())
    assert outcome["model_calls"] == 1
    assert outcome["usage"] is None and outcome["cost"] is None and outcome["seed"] is None
    assert outcome["usage_unavailable_reason"]
    assert outcome["model"] == outcome["configured_model"] == outcome["requested_model"] == "fixture-model"
    assert outcome["configured_model_provider"] == "openai" and outcome["runtime_version"] == "0.144.4"
    assert outcome["model_identity_basis"] == "native_thread_start_configuration"
    assert outcome["served_model"] is None and outcome["served_model_unavailable_reason"]


@pytest.mark.asyncio
async def test_m0_001_b05_bounded_tool_effect_denial_closes_owned_process(tmp_path):
    service = FixtureService(tmp_path, "tool")
    with pytest.raises(GovernanceError, match="effect outside"):
        await NativeCompletionBackend(service).complete(**invocation())
    assert service.transport.closed
    assert len([1 for m, _ in service.transport.requests if m == "turn/start"]) == 1


@pytest.mark.asyncio
async def test_m0_001_b06_timeout_no_replay(tmp_path):
    service = FixtureService(tmp_path, "timeout")
    request = invocation()
    request["timeout_seconds"] = 0.02
    with pytest.raises(GovernanceError, match="wall-time"):
        await NativeCompletionBackend(service).complete(**request)
    assert service.transport.closed
    assert len([1 for m, _ in service.transport.requests if m == "turn/start"]) == 1


def test_m0_001_b05_provider_environment_excludes_host_credentials(tmp_path):
    env = child_environment(tmp_path, {"PATH": "safe-path", "OPENAI_API_KEY": "fixture-canary",
                                       "CODEX_HOME": "foreign-profile", "PRIVATE_TOKEN": "fixture-secret"})
    assert env == {"PATH": "safe-path", "CODEX_HOME": str(tmp_path.resolve())}


@pytest.mark.asyncio
async def test_m0_001_b06_unknown_model_is_not_substituted(tmp_path):
    service = FixtureService(tmp_path)
    request = invocation()
    request["model"] = "unapproved-model"
    with pytest.raises(GovernanceError, match="frozen native model"):
        await NativeCompletionBackend(service).complete(**request)
    assert not service.transport.requests


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value,code", [
    ("model", "another-model", "policy_denied"),
    ("modelProvider", "another-provider", "policy_denied"),
    ("thread.modelProvider", "another-provider", "policy_denied"),
    ("thread.cliVersion", "0.144.5", "environment_unavailable"),
    ("model", None, "delivery_unknown"),
    ("modelProvider", None, "delivery_unknown"),
    ("thread.cliVersion", None, "delivery_unknown"),
    ("thread.modelProvider", None, "delivery_unknown"),
])
async def test_m0_001_b03_b06_native_configuration_denial_precedes_turn_dispatch(tmp_path, field, value, code):
    service = FixtureService(tmp_path)
    original = service.transport.request
    async def changed(method, params):
        result = await original(method, params)
        if method == "thread/start":
            owner, key = (result["thread"], field.split(".")[1]) if field.startswith("thread.") else (result, field)
            if value is None:
                owner.pop(key)
            else:
                owner[key] = value
        return result
    service.transport.request = changed
    with pytest.raises(GovernanceError) as halted:
        await NativeCompletionBackend(service).complete(**invocation())
    assert halted.value.code == code
    assert service.transport.closed
    assert [method for method, _ in service.transport.requests] == ["thread/start"]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,will_retry,after_completion", [
    ("model/rerouted", False, False),
    ("model/rerouted", False, True),
    ("error", False, False),
    ("error", True, False),
])
async def test_m0_001_b03_b06_native_route_or_error_refusal_never_releases_or_replays(tmp_path, method, will_retry, after_completion):
    service = FixtureService(tmp_path)
    original = service.transport.request
    def notify(thread):
        params = {"threadId": thread, "turnId": "fixture-turn"}
        params.update({"fromModel": "fixture-model", "toModel": "another-model", "reason": "highRiskCyberActivity"}
                      if method == "model/rerouted" else {"error": {"message": "fixture failure"}, "willRetry": will_retry})
        for listener in tuple(service.transport.listeners):
            listener(method, params)
    async def changed(name, params):
        if name == "turn/start" and not after_completion:
            notify(params["threadId"])
        result = await original(name, params)
        if name == "turn/start" and after_completion:
            notify(params["threadId"])
        return result
    service.transport.request = changed
    with pytest.raises(GovernanceError) as halted:
        await NativeCompletionBackend(service).complete(**invocation())
    assert halted.value.code == ("policy_denied" if method == "model/rerouted" else "execution_failed")
    assert service.transport.closed
    assert [name for name, _ in service.transport.requests] == ["thread/start", "turn/start", "turn/interrupt"]


@pytest.mark.asyncio
@pytest.mark.parametrize("dispatch", ["thread/start", "turn/start"])
async def test_m0_001_b06_native_request_failure_never_retries(tmp_path, dispatch):
    service = FixtureService(tmp_path)
    original = service.transport.request
    async def fail(method, params):
        if method == dispatch:
            service.transport.requests.append((method, params))
            raise CodexError("RUNTIME_ERROR")
        return await original(method, params)
    service.transport.request = fail
    with pytest.raises(GovernanceError) as halted:
        await NativeCompletionBackend(service).complete(**invocation())
    assert halted.value.code == "delivery_unknown" and service.transport.closed
    assert [method for method, _ in service.transport.requests] == (
        ["thread/start"] if dispatch == "thread/start" else ["thread/start", "turn/start"])


@pytest.mark.asyncio
async def test_m0_001_b06_native_interruption_is_cancellation_without_replay(tmp_path):
    service = FixtureService(tmp_path, "timeout")
    original = service.transport.request
    async def interrupted(method, params):
        result = await original(method, params)
        if method == "turn/start":
            for listener in tuple(service.transport.listeners):
                listener("turn/completed", {"threadId": params["threadId"],
                    "turn": {"id": "fixture-turn", "items": [], "status": "interrupted"}})
        return result
    service.transport.request = interrupted
    with pytest.raises(GovernanceError) as halted:
        await NativeCompletionBackend(service).complete(**invocation())
    assert halted.value.code == "cancelled" and service.transport.closed
    assert [method for method, _ in service.transport.requests] == ["thread/start", "turn/start", "turn/interrupt"]
