"""Offline characterization of pinned dependencies, NOT product acceptance tests.

Run directly with the project's Python. No account, model or tool is invoked.
Counterexample tests deliberately establish existing unsafe defaults so a future
product adapter has explicit requirements; their success is not a safety pass.
"""
import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from openai_codex.client import CodexClient, CodexConfig
from openjiuwen.agent_teams.agent.agent_configurator import AgentConfigurator
from openjiuwen.core.session.interaction.interactive_input import InteractiveInput
from openjiuwen.harness_protocol import (
    DeliveryMode, DynamicToolCallRequest, HarnessState, HarnessStateError,
    InteractionResponseStatus, OutputEvent, OutputKind, OutputOperation,
    SendReceipt, ToolApprovalDecision, ToolApprovalRequest,
    UnsupportedHarnessCapabilityError,
)
from openjiuwen.harness_providers.codex.config import CodexHarnessConfig
from openjiuwen.harness_providers.codex.harness import CodexHarness, _install_approval_handler
from openjiuwen.harness_providers.codex.options import build_process_env
from openjiuwen.harness_providers.io_adapter import HarnessIOAdapter


class OfflineHarness:
    """Only the provider transport is faked; adapter methods are real."""
    card = CodexHarness.card
    state = HarnessState.RUNNING
    provider_session_id = "offline-session"

    def __init__(self):
        self.sent = []
        self.aborted = []

    async def send(self, content, *, mode):
        self.sent.append((content, mode))
        return SendReceipt("offline-message", "offline-turn", mode)

    async def abort(self, *, mode):
        self.aborted.append(mode)


def request(identity="permission-1"):
    return ToolApprovalRequest(identity, "call-1", "fixture_write", {"path": "unused.txt"})


def answer(identity, value):
    reply = InteractiveInput()
    reply.update(identity, value)
    return reply


class AdapterBoundaries(unittest.IsolatedAsyncioTestCase):
    async def pending(self, adapter, identity="permission-1"):
        task = asyncio.create_task(adapter.handle(request(identity)))
        self.addAsyncCleanup(self.release, adapter, task, identity)
        chunk = await asyncio.wait_for(anext(adapter.outputs()), 2)
        self.assertEqual(chunk.type, "__interaction__")
        return task

    async def release(self, adapter, task, identity):
        await adapter.cancel(identity)
        await asyncio.wait_for(task, 2)

    async def test_counterexample_default_auto_approval(self):
        adapter = HarnessIOAdapter(OfflineHarness())
        result = await adapter.handle(request())
        self.assertEqual(result.decision, ToolApprovalDecision.ALLOW)
        self.assertFalse(adapter.has_pending_interrupt())

    async def test_explicit_denial_does_not_reach_provider(self):
        harness = OfflineHarness()
        adapter = HarnessIOAdapter(harness, auto_approve_tools=False)
        pending = await self.pending(adapter)
        self.assertFalse(pending.done())
        self.assertIsNone(await adapter.send(answer("permission-1", {"approved": False})))
        self.assertEqual((await pending).decision, ToolApprovalDecision.DENY)
        self.assertEqual(harness.sent, [])

    async def test_counterexample_empty_approval_object_allows(self):
        adapter = HarnessIOAdapter(OfflineHarness(), auto_approve_tools=False)
        pending = await self.pending(adapter)
        await adapter.send(answer("permission-1", {}))
        self.assertEqual((await pending).decision, ToolApprovalDecision.ALLOW)

    async def test_counterexample_stale_answer_becomes_provider_input(self):
        harness = OfflineHarness()
        adapter = HarnessIOAdapter(harness, auto_approve_tools=False)
        pending = await self.pending(adapter)
        await adapter.send(answer("old-request", {"approved": True}))
        self.assertFalse(pending.done())
        self.assertEqual(len(harness.sent), 1)
        self.assertEqual(harness.sent[0][1], DeliveryMode.FOLLOW_UP)

    async def test_duplicate_pending_id_rejected(self):
        adapter = HarnessIOAdapter(OfflineHarness(), auto_approve_tools=False)
        await self.pending(adapter)
        with self.assertRaises(HarnessStateError):
            await adapter.handle(request())

    async def test_separate_adapters_do_not_resolve_each_others_requests(self):
        first = HarnessIOAdapter(OfflineHarness(), auto_approve_tools=False)
        second = HarnessIOAdapter(OfflineHarness(), auto_approve_tools=False)
        a = await self.pending(first)
        b = await self.pending(second)
        await first.send(answer("permission-1", {"approved": False}))
        self.assertEqual((await a).decision, ToolApprovalDecision.DENY)
        self.assertFalse(b.done())
        self.assertEqual(second.pending_interrupt_ids, ("permission-1",))

    async def test_cancel_pending_approval_denies(self):
        adapter = HarnessIOAdapter(OfflineHarness(), auto_approve_tools=False)
        pending = await self.pending(adapter)
        await adapter.cancel("permission-1")
        self.assertEqual((await pending).decision, ToolApprovalDecision.DENY)

    async def test_pause_is_unsupported_for_running_codex(self):
        adapter = HarnessIOAdapter(OfflineHarness(), auto_approve_tools=False)
        with self.assertRaises(UnsupportedHarnessCapabilityError):
            await adapter.pause()

    async def test_dynamic_tool_requests_are_not_routed_by_adapter(self):
        adapter = HarnessIOAdapter(OfflineHarness(), auto_approve_tools=False)
        result = await adapter.handle(DynamicToolCallRequest("r", "c", "fixture"))
        self.assertEqual(result.status, InteractionResponseStatus.DECLINED)
        self.assertTrue(result.is_error)

    async def test_final_snapshot_does_not_duplicate_streamed_text(self):
        adapter = HarnessIOAdapter(OfflineHarness(), auto_approve_tools=False)
        chunks = [adapter._project_output(OutputEvent("o", OutputKind.TEXT, text, op))
                  for text, op in [("rea", OutputOperation.DELTA),
                                   ("dy", OutputOperation.DELTA),
                                   ("ready", OutputOperation.FINAL)]]
        self.assertEqual("".join(c.payload["content"] for c in chunks if c), "ready")
        self.assertIsNone(chunks[-1])


class IntegrationBoundaries(unittest.TestCase):
    def test_counterexample_sdk_reinherits_parent_environment(self):
        # This fabricated value never goes to a real subprocess.
        sentinel = "not-a-real-key-offline-fixture"
        with patch.dict(os.environ, {"OPENAI_API_KEY": sentinel}):
            curated = build_process_env(CodexHarnessConfig(inherit_process_env=False), {})
            self.assertNotIn("OPENAI_API_KEY", curated)
            client = CodexClient(CodexConfig(launch_args_override=("never-executed",), env=curated))
            with patch("openai_codex.client.subprocess.Popen", side_effect=RuntimeError("intercepted")) as launch:
                with self.assertRaisesRegex(RuntimeError, "intercepted"):
                    client.start()
            self.assertEqual(launch.call_args.kwargs["env"]["OPENAI_API_KEY"], sentinel)

    def test_counterexample_missing_approval_hook_does_not_fail_startup(self):
        client = SimpleNamespace()
        with patch("openjiuwen.harness_providers.codex.harness.logger") as log:
            self.assertIsNone(_install_approval_handler(client, lambda *args: {"decision": "decline"}))
            log.warning.assert_called_once()

    def test_external_leader_seam_adopts_runtime_but_skips_native_construction(self):
        # A seam fixture only: workspace/coordination collaborators are mocked.
        # This does not exercise real team creation, tools, memory or budgets.
        configurator = AgentConfigurator(SimpleNamespace())
        runtime, spec = object(), SimpleNamespace()
        context = SimpleNamespace(role="leader", member_name="leader")
        with patch.object(configurator, "_prepare_external_cli_workspace") as workspace, \
             patch.object(configurator, "_attach_workspace_cache") as cache, \
             patch.object(configurator, "resolve_agent_spec") as native:
            result = configurator.setup_agent(spec, context, member_runtime=runtime)
        self.assertIs(result, runtime)
        self.assertIs(configurator.harness, runtime)
        self.assertIsNone(configurator.memory_manager)
        workspace.assert_called_once_with(spec, context)
        cache.assert_called_once()
        native.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
