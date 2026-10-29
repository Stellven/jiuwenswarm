"""Prototype protections against R001 counterexamples; no live model calls."""
import asyncio
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from openjiuwen.harness_protocol import ToolApprovalRequest, ToolApprovalDecision, HarnessContext
from guard_prototype import (ApprovalBroker, GuardError, GuardedIOAdapter, Scope,
                             child_environment, guarded_start, launch_signed_out_probe)
from test_boundaries import OfflineHarness, answer

SCOPE = Scope("s1", "e1", "thread1", "turn1", 1)
KEYS = set(asdict(SCOPE)) | {"request_id", "call_id", "ticket"}


class ApprovalTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.broker = ApprovalBroker(SCOPE)
        self.harness = OfflineHarness()
        self.adapter = GuardedIOAdapter(self.harness, self.broker)
        self.tasks = []

    async def asyncTearDown(self):
        self.broker.close()
        if self.tasks:
            await asyncio.wait_for(asyncio.gather(*self.tasks, return_exceptions=True), 2)

    async def begin(self, request_id="r1"):
        request = ToolApprovalRequest(request_id, "call1", "fixture_write",
                                      provider_session_id="thread1", turn_id="turn1")
        task = asyncio.create_task(self.adapter.handle(request))
        self.tasks.append(task)
        notice = await asyncio.wait_for(self.broker.events.get(), 2)
        payload = {k: notice[k] for k in KEYS}
        return task, notice, payload

    async def test_explicit_allow_and_deny_only_resolve_permission(self):
        for decision in (False, True):
            task, _, payload = await self.begin(str(decision))
            result = self.broker.decide({**payload, "approved": decision})
            self.assertEqual(result, {"accepted": True, "ticket": payload["ticket"]})
            self.assertEqual((await task).decision,
                             ToolApprovalDecision.ALLOW if decision else ToolApprovalDecision.DENY)
        self.assertEqual(self.harness.sent, [])

    async def test_malformed_values_never_approve_or_forward(self):
        task, _, payload = await self.begin()
        variants = [{}, payload, None, [], *[{**payload, "approved": v} for v in (None, 1, 0, "true", {}, [])],
                    {**payload, "approved": True, "extra": "ignored?"},
                    {**payload, "approved": True, "generation": True}]
        for bad in variants:
            with self.subTest(payload_type=type(bad).__name__):
                with self.assertRaisesRegex(GuardError, "INVALID_DECISION"):
                    self.broker.decide(bad)
        self.assertFalse(task.done())
        self.assertEqual(self.harness.sent, [])

    async def test_each_wrong_identity_rejected(self):
        task, _, payload = await self.begin()
        for key in KEYS:
            with self.subTest(field=key):
                wrong = 2 if key == "generation" else "wrong"
                with self.assertRaisesRegex(GuardError, "STALE_OPERATION"):
                    self.broker.decide({**payload, key: wrong, "approved": True})
        self.assertFalse(task.done())
        self.assertEqual(self.harness.sent, [])

    async def test_duplicate_decision_race_has_one_winner(self):
        task, _, payload = await self.begin()
        async def resolve():
            try:
                return self.broker.decide({**payload, "approved": True})["accepted"]
            except GuardError:
                return False
        self.assertEqual(sum(await asyncio.gather(resolve(), resolve())), 1)
        self.assertEqual((await task).decision, ToolApprovalDecision.ALLOW)

    async def test_old_ticket_cannot_answer_reused_request_id(self):
        first, _, old = await self.begin()
        self.broker.cancel("r1")
        self.assertEqual((await first).decision, ToolApprovalDecision.DENY)
        second, _, new = await self.begin()
        self.assertNotEqual(old["ticket"], new["ticket"])
        with self.assertRaisesRegex(GuardError, "STALE_OPERATION"):
            self.broker.decide({**old, "approved": True})
        self.assertFalse(second.done())

    async def test_close_denies_pending_and_rejects_late_decisions(self):
        task, _, payload = await self.begin()
        self.broker.close()
        self.assertEqual((await task).decision, ToolApprovalDecision.DENY)
        with self.assertRaisesRegex(GuardError, "CLOSED"):
            self.broker.decide({**payload, "approved": True})

    async def test_interactive_input_cannot_enter_chat_channel(self):
        for identity in ("r1", "stale"):
            with self.assertRaisesRegex(GuardError, "CONTROL_CHANNEL_REQUIRED"):
                await self.adapter.send(answer(identity, {"approved": True}))
        self.assertEqual(self.harness.sent, [])
        await self.adapter.send("ordinary text")
        self.assertEqual(len(self.harness.sent), 1)

    async def test_context_routes_to_guard_and_mismatched_provider_rejected(self):
        ctx = self.adapter.prepare_context(HarnessContext("fixture", "agent", "s1", ""))
        self.assertIs(ctx.interactions, self.adapter)
        with self.assertRaisesRegex(GuardError, "STALE_OPERATION"):
            await self.adapter.handle(ToolApprovalRequest("r", "c", "fixture",
                                      provider_session_id="wrong", turn_id="turn1"))
        self.assertTrue(self.broker.events.empty())

    async def test_foreign_interaction_handler_cannot_bypass_guard(self):
        ctx = HarnessContext("fixture", "agent", "s1", "", interactions=object())
        with self.assertRaisesRegex(GuardError, "UNTRUSTED_INTERACTION_HANDLER"):
            self.adapter.prepare_context(ctx)

    async def test_adapter_cancellation_and_stop_release_permission_waiters(self):
        task, _, _ = await self.begin()
        await self.adapter.cancel("r1")
        self.assertEqual((await task).decision, ToolApprovalDecision.DENY)
        task, _, _ = await self.begin("r2")
        await self.adapter.stop()
        self.assertEqual((await task).decision, ToolApprovalDecision.DENY)
        with self.assertRaisesRegex(GuardError, "CLOSED"):
            await self.adapter.send("late text")

    async def test_real_frontend_serialization_resolves_backend_permission(self):
        node = Path(os.environ["LOCALAPPDATA"]) / "ai4r-tools/node-v22.23.3-win-x64/node.exe"
        for decision in (False, True):
            task, notice, _ = await self.begin(str(decision))
            fixture = Path(__file__).with_name("frontend_wire_fixture.mjs")
            result = await asyncio.to_thread(subprocess.run, [str(node), str(fixture)],
                input=json.dumps({"scope": asdict(SCOPE), "notice": notice, "approved": decision}),
                capture_output=True, text=True, check=True, timeout=10)
            self.broker.decide(json.loads(result.stdout))
            self.assertEqual((await task).decision,
                             ToolApprovalDecision.ALLOW if decision else ToolApprovalDecision.DENY)
        self.assertEqual(self.harness.sent, [])


class LaunchTests(unittest.TestCase):
    def test_missing_hook_blocks_start(self):
        start = Mock()
        for client in (SimpleNamespace(), SimpleNamespace(_client=SimpleNamespace(_sync=object()))):
            with self.assertRaisesRegex(GuardError, "APPROVAL_HOOK_UNAVAILABLE"):
                guarded_start(client, lambda *args: {}, start)
        start.assert_not_called()

    def test_handler_installed_before_start(self):
        handler = lambda *args: {"decision": "decline"}
        low = SimpleNamespace(_approval_handler=lambda *args: {"decision": "accept"})
        client = SimpleNamespace(_client=SimpleNamespace(_sync=low))
        self.assertTrue(guarded_start(client, handler, lambda: low._approval_handler is handler))

    def test_actual_child_does_not_inherit_provider_or_python_overrides(self):
        with tempfile.TemporaryDirectory(prefix="ai4r-env-") as root:
            parent = {**os.environ, "OPENAI_API_KEY": "fake", "ANTHROPIC_API_KEY": "fake",
                      "OPENAI_BASE_URL": "https://example.invalid", "PYTHONPATH": "untrusted",
                      "CODEX_HOME": "old-home", "CODEX_CONFIG_OVERRIDES": "fake"}
            env = child_environment(parent, Path(root) / "home", Path(root))
            script = 'import os,json; print(json.dumps([k in os.environ for k in ["OPENAI_API_KEY","ANTHROPIC_API_KEY","OPENAI_BASE_URL","PYTHONPATH","CODEX_CONFIG_OVERRIDES"]]))'
            result = subprocess.run([sys.executable, "-c", script], env=env,
                                    capture_output=True, text=True, check=True, timeout=10)
            self.assertEqual(json.loads(result.stdout), [False] * 5)
            self.assertEqual(env["CODEX_HOME"], str(Path(root) / "home"))

    def test_codex_launch_boundary_receives_curated_environment(self):
        with tempfile.TemporaryDirectory(prefix="ai4r-launch-") as root:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "fake", "CODEX_CONFIG_OVERRIDES": "fake"}), \
                 patch("guard_prototype.subprocess.Popen") as launch:
                launch_signed_out_probe(Path(sys.executable), Path(root) / "home", Path(root))
            env = launch.call_args.kwargs["env"]
            self.assertNotIn("OPENAI_API_KEY", env)
            self.assertNotIn("CODEX_CONFIG_OVERRIDES", env)
            self.assertIn('forced_login_method="chatgpt"', launch.call_args.args[0])

    def test_relative_profile_rejected(self):
        with self.assertRaisesRegex(GuardError, "ABSOLUTE_PATH_REQUIRED"):
            child_environment({}, Path("relative"), Path.cwd())


if __name__ == "__main__":
    unittest.main(verbosity=2)
