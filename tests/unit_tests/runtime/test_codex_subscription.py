"""M1 behavioral fixtures: no account or network required."""
import asyncio
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError, child_environment


class FakeTransport:
    def __init__(self):
        self.listeners = set()
        self.calls = []
        self.account = {"type": "chatgpt", "email": "fixture@example.invalid", "planType": "plus"}
        self.counter = 0
        self.fail_turn = False
        self.hold_turn = False

    async def start(self):
        pass

    async def close(self):
        self.emit("transport/closed", {})

    def emit(self, method, params):
        for listener in tuple(self.listeners):
            listener(method, params)

    async def request(self, method, params=None):
        self.calls.append((method, params))
        if method == "account/read":
            return {"account": self.account}
        if method == "account/logout":
            self.account = None
            return {}
        if method == "account/login/start":
            return {"type": "chatgpt", "loginId": "fixture-login", "authUrl": "https://auth.openai.com/authorize?fixture=1"}
        if method == "model/list":
            return {"data": [{"id": "fixture", "model": "fixture", "displayName": "Fixture", "isDefault": True}], "nextCursor": None}
        if method == "thread/start":
            self.counter += 1
            return {"thread": {"id": f"thread-{self.counter}"}}
        if method == "thread/resume":
            return {"thread": {"id": params["threadId"]}}
        if method == "turn/start":
            if self.fail_turn:
                raise CodexError("RUNTIME_ERROR")
            tid = params["threadId"]
            turn = f"turn-{len(self.calls)}"
            # Events may precede the start response. Also send foreign-session data.
            self.emit("item/agentMessage/delta", {"threadId": "foreign", "turnId": turn, "delta": "LEAK"})
            self.emit("item/agentMessage/delta", {"threadId": tid, "turnId": turn, "delta": "Hello"})
            if not self.hold_turn:
                self.emit("turn/completed", {"threadId": tid, "turn": {"id": turn, "status": "completed"}})
            return {"turn": {"id": turn}}
        if method == "turn/interrupt":
            self.emit("turn/completed", {"threadId": params["threadId"], "turn": {"id": params["turnId"], "status": "interrupted"}})
            return {}
        return {}


class SubscriptionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.transport = FakeTransport()
        self.service = SubscriptionService(Path(self.tmp.name), transport=self.transport)

    def tearDown(self):
        self.tmp.cleanup()

    async def collect(self, sid="one", rid="r1"):
        return [event async for event in self.service.stream(sid, rid, "Hi")]

    async def test_signed_out_never_starts_model_or_key_fallback(self):
        self.transport.account = None
        with self.assertRaisesRegex(CodexError, "SIGN_IN_REQUIRED"):
            await self.collect()
        self.assertFalse(any(m == "turn/start" for m, _ in self.transport.calls))

    async def test_api_account_rejected(self):
        self.transport.account = {"type": "apiKey"}
        with self.assertRaisesRegex(CodexError, "SUBSCRIPTION_REQUIRED"):
            await self.collect()

    async def test_early_notifications_and_foreign_session_isolation(self):
        events = await self.collect()
        self.assertEqual([e["content"] for e in events if e["event_type"] == "chat.delta"], ["Hello"])
        self.assertEqual(events[-1]["event_type"], "chat.final")
        self.assertEqual(events[-1]["content"], "Hello")
        self.assertEqual(events[-1]["session_id"], "one")

    async def test_sessions_get_distinct_threads_and_same_session_reuses(self):
        await self.collect("one", "r1")
        await self.collect("two", "r2")
        await self.collect("one", "r3")
        starts = [p["threadId"] for m, p in self.transport.calls if m == "turn/start"]
        self.assertEqual(starts, ["thread-1", "thread-2", "thread-1"])

    async def test_restart_preserves_binding_but_blocks_unproven_account_resume(self):
        await self.collect()
        restarted = SubscriptionService(Path(self.tmp.name), transport=self.transport)
        with self.assertRaisesRegex(CodexError, "NEW_SESSION_REQUIRED"):
            _ = [e async for e in restarted.stream("one", "r2", "Again")]
        self.assertTrue((Path(self.tmp.name) / "bindings.json").exists())

    async def test_logout_invalidates_old_threads(self):
        await self.collect()
        await self.service.logout()
        self.transport.account = {"type": "chatgpt", "email": "fixture@example.invalid", "planType": "plus"}
        with self.assertRaisesRegex(CodexError, "NEW_SESSION_REQUIRED"):
            await self.collect()

    async def test_provider_failure_is_not_retried(self):
        self.transport.fail_turn = True
        with self.assertRaises(CodexError):
            await self.collect()
        self.assertEqual(sum(m == "turn/start" for m, _ in self.transport.calls), 1)
        self.assertFalse(self.service.active)

    async def test_stale_interrupt_does_not_control_other_request(self):
        with self.assertRaisesRegex(CodexError, "STALE_OPERATION"):
            await self.service.interrupt("one", "unknown")
        self.assertFalse(any(m == "turn/interrupt" for m, _ in self.transport.calls))

    async def test_login_cancel_ignores_late_completion(self):
        self.transport.account = None
        result = await self.service.login()
        self.assertEqual(result["state"], "signing_in")
        await self.service.cancel_login("fixture-login")
        self.transport.emit("account/login/completed", {"loginId": "fixture-login", "success": True})
        self.assertEqual((await self.service.status())["state"], "signed_out")
        self.assertIsNone(self.service.login_id)

    async def test_stale_login_cancel_leaves_current_attempt_running(self):
        await self.service.login()
        with self.assertRaisesRegex(CodexError, "STALE_OPERATION"):
            await self.service.cancel_login("old-login")
        self.assertEqual(self.service.login_id, "fixture-login")
        self.assertFalse(any(m == "account/login/cancel" for m, _ in self.transport.calls))

    async def test_duplicate_login_has_no_second_side_effect(self):
        await self.service.login()
        with self.assertRaisesRegex(CodexError, "LOGIN_PENDING"):
            await self.service.login()
        self.assertEqual(sum(m == "account/login/start" for m, _ in self.transport.calls), 1)

    async def test_logout_stops_active_stream_without_closing_replacement(self):
        self.transport.hold_turn = True
        stream = self.service.stream("one", "r1", "Hi")
        self.assertEqual((await anext(stream))["content"], "Hello")
        await self.service.logout()
        with self.assertRaisesRegex(CodexError, "RUNTIME_DISCONNECTED"):
            await anext(stream)
        self.assertFalse(self.service.active)

    async def test_cancel_waits_for_terminal_preserves_partial_and_allows_next_turn(self):
        self.transport.hold_turn = True
        task = asyncio.create_task(self.collect())
        while not self.service.active.get("one", {}).get("turn"):
            await asyncio.sleep(0)
        result = await self.service.interrupt("one", "r1")
        events = await task
        self.assertTrue(result["success"])
        self.assertTrue(events[-1]["cancelled"])
        self.assertEqual(events[-1]["content"], "Hello")
        self.transport.hold_turn = False
        self.assertEqual((await self.collect("one", "r2"))[-1]["content"], "Hello")

    async def test_cancel_before_start_ack_waits_for_correlated_terminal(self):
        self.transport.hold_turn = True
        entered, release = asyncio.Event(), asyncio.Event()
        original = self.transport.request

        async def delayed(method, params=None):
            if method == "turn/start":
                entered.set()
                await release.wait()
            return await original(method, params)

        self.transport.request = delayed
        task = asyncio.create_task(self.collect())
        await entered.wait()
        cancel = asyncio.create_task(self.service.interrupt("one", "r1"))
        await asyncio.sleep(0)
        self.assertFalse(cancel.done())
        release.set()
        self.assertTrue((await cancel)["success"])
        self.assertTrue((await task)[-1]["cancelled"])

    async def test_same_session_rejects_concurrent_admission(self):
        self.transport.hold_turn = True
        stream = self.service.stream("one", "r1", "Hi")
        await anext(stream)
        with self.assertRaisesRegex(CodexError, "BUSY"):
            await self.collect("one", "r2")
        await stream.aclose()

    def test_child_environment_does_not_inherit_credentials_or_providers(self):
        env = child_environment(Path(self.tmp.name), {"PATH": "safe", "SystemRoot": "Windows", "OPENAI_API_KEY": "fake", "CODEX_HOME": "foreign", "OPENAI_BASE_URL": "foreign", "ANTHROPIC_API_KEY": "fake"})
        self.assertEqual(env["CODEX_HOME"], self.tmp.name)
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("OPENAI_BASE_URL", env)
        self.assertNotIn("ANTHROPIC_API_KEY", env)

    def test_launcher_seeds_incrementally_without_interactive_init(self):
        from jiuwenswarm.codex_start import main
        profile = Path(self.tmp.name)
        with patch("sys.argv", ["codex_start", "all"]), \
             patch("jiuwenswarm.codex_start.configure_profile", return_value=profile), \
             patch("jiuwenswarm.common.utils.prepare_workspace") as prepare, \
             patch("jiuwenswarm.start_services._run", return_value=0) as run, \
             patch("builtins.input", side_effect=AssertionError("No terminal prompt")):
            with self.assertRaises(SystemExit) as exited:
                main()
            self.assertEqual(exited.exception.code, 0)
            prepare.assert_called_once_with(overwrite=False, workspace_dir=profile)
            run.assert_called_once_with("all")

    def test_profile_selection_preserves_old_data_and_rejects_foreign_directory(self):
        from jiuwenswarm.codex_start import configure_profile
        home = Path(self.tmp.name)
        old = home / ".jiuwenswarm"
        old.mkdir()
        (old / "sentinel").write_text("keep")
        with patch("pathlib.Path.home", return_value=home), patch.dict("os.environ", {}, clear=False):
            fresh = configure_profile()
            self.assertEqual(fresh.name, ".jiuwenswarm-ai4r")
            self.assertEqual((old / "sentinel").read_text(), "keep")
            self.assertEqual(configure_profile(), fresh)
            (fresh / ".ai4r-subscription-profile").unlink()
            (fresh / "foreign-data").write_text("keep")
            with self.assertRaisesRegex(RuntimeError, "not empty"):
                configure_profile()


if __name__ == "__main__":
    unittest.main()
