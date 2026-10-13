"""Product adapter/facade/history integration; fake provider, actual host code."""
from unittest.mock import AsyncMock

import pytest

from jiuwenswarm.common.schema.agent import AgentRequest
from jiuwenswarm.common.schema.message import ReqMethod
from jiuwenswarm.server.runtime.agent_adapter.interface_codex import CodexSubscriptionAdapter
from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
from tests.unit_tests.runtime.test_codex_subscription import FakeTransport


def test_account_methods_forward_without_local_unknown_method_response():
    from jiuwenswarm.gateway.channel_manager.web.app_web_handlers import (
        _FORWARD_REQ_METHODS, _FORWARD_NO_LOCAL_HANDLER_METHODS,
    )
    from jiuwenswarm.server.runtime.gateway_adapter.codex_adapter import CodexAccountAdapter
    assert CodexAccountAdapter.methods <= _FORWARD_REQ_METHODS
    assert CodexAccountAdapter.methods <= _FORWARD_NO_LOCAL_HANDLER_METHODS


def test_subscription_mode_does_not_schedule_legacy_model_probe(monkeypatch):
    from types import SimpleNamespace
    from jiuwenswarm.server.agent_ws_server import AgentWebSocketServer
    monkeypatch.setenv("JIUWENSWARM_AGENT_SDK", "codex_subscription")
    # No native task field or event loop: returning before touching them is required.
    AgentWebSocketServer.schedule_image_modality_warmup(SimpleNamespace(), reason="test")


@pytest.mark.asyncio
async def test_real_facade_persists_streamed_reply_once(tmp_path, monkeypatch):
    from jiuwenswarm.server.runtime.agent_adapter import interface
    from jiuwenswarm.server.runtime.session import session_history, session_metadata
    monkeypatch.setattr(session_history, "get_agent_sessions_dir", lambda: tmp_path / "sessions")
    monkeypatch.setattr(session_metadata, "get_agent_sessions_dir", lambda: tmp_path / "sessions")
    monkeypatch.setattr(interface, "get_config", lambda: {"preferred_language": "en"})
    monkeypatch.setattr(interface, "get_memory_mode", lambda cfg: "off")
    monkeypatch.setattr(interface, "build_user_prompt", lambda q, **kw: q)
    service = SubscriptionService(tmp_path / "runtime", transport=FakeTransport())
    facade = interface.JiuWenSwarm()
    facade._adapter = CodexSubscriptionAdapter(service)
    facade._sdk_name = "codex_subscription"
    request = AgentRequest(request_id="fixture-r1", channel_id="web", session_id="fixture-session", req_method=ReqMethod.CHAT_SEND, params={"query": "Hi", "mode": "agent.work.normal"})
    chunks = [chunk async for chunk in facade.process_message_stream(request)]
    assert any((chunk.payload or {}).get("event_type") == "chat.delta" for chunk in chunks)
    assert session_history.flush_pending_writes()
    records = session_history.load_history_records("fixture-session")
    assert [r["content"] for r in records if r.get("role") == "user"] == ["Hi"]
    assert [r["content"] for r in records if r.get("event_type") == "chat.final"] == ["Hello"]


@pytest.mark.asyncio
async def test_unsupported_team_does_not_call_provider(tmp_path):
    transport = FakeTransport()
    adapter = CodexSubscriptionAdapter(SubscriptionService(tmp_path, transport=transport))
    request = AgentRequest(request_id="r", channel_id="web", session_id="s", params={"query": "Hi", "mode": "team"})
    chunks = [chunk async for chunk in adapter.process_message_stream_impl(request, {})]
    assert chunks[-1].payload["code"] == "MILESTONE_TEXT_ONLY"
    assert not transport.calls


@pytest.mark.asyncio
async def test_goal_poll_is_empty_and_mutations_do_not_call_provider(tmp_path):
    from jiuwenswarm.server.runtime.agent_adapter.interface import JiuWenSwarm
    transport = FakeTransport()
    adapter = CodexSubscriptionAdapter(SubscriptionService(tmp_path, transport=transport))
    facade = JiuWenSwarm()
    facade._adapter = adapter
    facade._sdk_name = "codex_subscription"
    request = AgentRequest(request_id="goal-poll", channel_id="web", session_id="s",
                           req_method=ReqMethod.COMMAND_GOAL, params={"action": "get"})
    chunks = [chunk async for chunk in facade.process_message_stream(request)]
    assert chunks[-1].payload["event_type"] == "goal.snapshot"
    assert chunks[-1].payload["goal"] is None
    for action in ("set", "resume", "pause", "clear"):
        result = await adapter.handle_goal_command_structured({"action": action}, "s")
        assert result["error_code"] == "MILESTONE_TEXT_ONLY"
        request.params = {"action": action, "query": "Do not execute this goal"}
        chunks = [chunk async for chunk in adapter.process_message_stream_impl(request, {})]
        assert chunks[-1].payload["code"] == "MILESTONE_TEXT_ONLY"
    assert not transport.calls


@pytest.mark.asyncio
async def test_gateway_account_method_dispatch(monkeypatch):
    from jiuwenswarm.server.runtime.gateway_adapter import codex_adapter
    monkeypatch.setenv("JIUWENSWARM_AGENT_SDK", "codex_subscription")
    service = AsyncMock()
    service.status.return_value = {"enabled": True, "state": "signed_out"}
    monkeypatch.setattr(codex_adapter, "get_service", lambda: service)
    response = await codex_adapter.CodexAccountAdapter().handle(AgentRequest(request_id="r", channel_id="web", req_method=ReqMethod.CODEX_AUTH_STATUS))
    assert response.ok and response.payload["state"] == "signed_out"
    service.status.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_mode_cannot_start_subscription_login(monkeypatch):
    from jiuwenswarm.server.runtime.gateway_adapter import codex_adapter
    monkeypatch.setenv("JIUWENSWARM_AGENT_SDK", "harness")
    response = await codex_adapter.CodexAccountAdapter().handle(AgentRequest(request_id="r", channel_id="web", req_method=ReqMethod.CODEX_AUTH_LOGIN))
    assert not response.ok and response.payload["code"] == "SUBSCRIPTION_MODE_DISABLED"


@pytest.mark.asyncio
async def test_facade_stale_cancel_preserves_newer_session_task(tmp_path):
    from jiuwenswarm.server.runtime.agent_adapter.interface import JiuWenSwarm
    facade = JiuWenSwarm()
    facade._sdk_name = "codex_subscription"
    facade._adapter = CodexSubscriptionAdapter(SubscriptionService(tmp_path, transport=FakeTransport()))
    facade._session_manager.cancel_session_task = AsyncMock()
    request = AgentRequest(request_id="cancel-envelope", session_id="s", params={"intent": "cancel", "target_request_id": "stale"})
    response = await facade._process_interrupt(request)
    assert not response.ok
    facade._session_manager.cancel_session_task.assert_not_awaited()
