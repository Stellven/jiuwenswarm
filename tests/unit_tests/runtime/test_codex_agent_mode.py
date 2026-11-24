"""Opt-in Codex agent mode: workspace-write threads, MCP config and tool events.

The default text-only profile is covered by test_codex_subscription.py; these
tests only prove the agent mode is off unless asked and maps tool items.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService, _tool_event
from jiuwenswarm.server.runtime.codex_subscription.transport import AGENT_MARKER, agent_mode_config

from tests.unit_tests.runtime.test_codex_subscription import FakeTransport

TOOL_ITEM = {"type": "mcpToolCall", "id": "call-1", "server": "cc", "tool": "cc_list",
             "status": "completed", "arguments": {}, "result": {"content": [{"type": "text", "text": "[]"}]}}
SHELL_ITEM = {"type": "commandExecution", "id": "call-2", "command": "echo hi", "cwd": "w",
              "status": "completed", "exitCode": 0, "aggregatedOutput": "hi\n"}


class ToolFakeTransport(FakeTransport):
    async def request(self, method, params=None):
        if method != "turn/start":
            return await super().request(method, params)
        self.calls.append((method, params))
        tid, turn = params["threadId"], f"turn-{len(self.calls)}"
        for item in (TOOL_ITEM, SHELL_ITEM):
            self.emit("item/started", {"threadId": tid, "turnId": turn, "item": dict(item, status="inProgress")})
            self.emit("item/completed", {"threadId": tid, "turnId": turn, "item": item})
        self.emit("item/agentMessage/delta", {"threadId": tid, "turnId": turn, "delta": "done"})
        self.emit("turn/completed", {"threadId": tid, "turn": {"id": turn, "status": "completed", "items": []}})
        return {"turn": {"id": turn}}


class AgentModeTests(unittest.IsolatedAsyncioTestCase):
    def test_off_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIUWENSWARM_CODEX_AGENT", None)
            self.assertIsNone(agent_mode_config())

    def test_config_has_workspace_write_and_operator_mcp_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            mcp = Path(tmp) / "mcp.toml"
            mcp.write_text('[mcp_servers.cc]\ncommand = "python"\n', encoding="utf-8")
            with mock.patch.dict(os.environ, {"JIUWENSWARM_CODEX_AGENT": "1", "JIUWENSWARM_CODEX_AGENT_MCP": str(mcp)}):
                config = agent_mode_config()
        self.assertTrue(config.startswith(AGENT_MARKER))
        self.assertIn('sandbox_mode = "workspace-write"', config)
        self.assertIn('approval_policy = "never"', config)
        self.assertIn("network_access = false", config)
        self.assertIn("[mcp_servers.cc]", config)
        self.assertIn('forced_login_method = "chatgpt"', config)

    def test_tool_item_mapping(self):
        started = _tool_event("item/started", {"item": TOOL_ITEM}, "s")
        self.assertEqual(started["event_type"], "chat.tool_call")
        self.assertEqual(started["tool_call"], {"tool_call_id": "call-1", "name": "cc.cc_list", "arguments": {}})
        done = _tool_event("item/completed", {"item": SHELL_ITEM}, "s")
        self.assertEqual((done["event_type"], done["tool_call_id"], done["tool_name"]), ("chat.tool_result", "call-2", "shell"))
        self.assertIsNone(_tool_event("item/completed", {"item": {"type": "agentMessage", "id": "m"}}, "s"))

    async def test_agent_mode_streams_tool_events_and_uses_workspace_write(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {
                "JIUWENSWARM_CODEX_AGENT": "1", "JIUWENSWARM_CODEX_AGENT_CWD": str(Path(tmp) / "work")}):
            transport = ToolFakeTransport()
            service = SubscriptionService(Path(tmp) / "sub", transport=transport)
            events = [e async for e in service.stream("one", "r1", "go")]
        kinds = [e["event_type"] for e in events]
        self.assertEqual(kinds.count("chat.tool_call"), 2)
        self.assertEqual(kinds.count("chat.tool_result"), 2)
        self.assertEqual(kinds[-1], "chat.final")
        start = next(p for m, p in transport.calls if m == "thread/start")
        self.assertEqual(start["sandbox"], "workspace-write")
        self.assertEqual(start["approvalPolicy"], "never")
        self.assertIn("cc_list", start["developerInstructions"])

    async def test_default_mode_still_rejects_tool_activity(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIUWENSWARM_CODEX_AGENT", None)
            service = SubscriptionService(Path(tmp), transport=ToolFakeTransport())
            with self.assertRaises(Exception) as caught:
                [e async for e in service.stream("one", "r1", "go")]
        self.assertIn("TOOLS_UNAVAILABLE", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
