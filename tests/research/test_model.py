"""Model-boundary fixtures: no real process, account, network, or credentials."""
from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jiuwenswarm.research.model import (
    CodexModel,
    MockModel,
    MOCK_AUTH_CONTEXT_HASH,
    ModelError,
    _ResearchTransport,
)
from jiuwenswarm.server.runtime.codex_subscription.transport import AppServerTransport, CodexError


class FakeTransport:
    def __init__(self):
        self.listeners = set()
        self.calls = []
        self.starts = 0
        self.closed = 0
        self.thread_count = 0
        self.account = {"type": "chatgpt", "email": "not-for-evidence@example.invalid", "token": "secret"}
        self.hang_at = None
        self.error = None
        self.thread_provider = "openai"
        self.thread_model = "fixture-model"
        self.reuse_thread = False
        self.turn_status = "completed"
        self.scenario = None
        self.turn_started = asyncio.Event()
        self.on_request = None

    async def start(self):
        self.starts += 1
        if self.hang_at == "start":
            await asyncio.Future()

    async def close(self):
        self.closed += 1
        self.emit("transport/closed", {})

    def emit(self, method, params):
        for listener in tuple(self.listeners):
            listener(method, params)

    async def request(self, method, params=None):
        self.calls.append((method, params))
        if self.on_request:
            self.on_request(method, params)
        if self.hang_at == method:
            await asyncio.Future()
        if self.error and method == "turn/start":
            raise self.error
        if method == "account/read":
            return {"account": self.account}
        if method == "thread/start":
            self.thread_count += 1
            thread = "thread-1" if self.reuse_thread else f"thread-{self.thread_count}"
            return {"thread": {"id": thread, "turns": []},
                    "modelProvider": self.thread_provider, "model": self.thread_model}
        if method == "turn/start":
            thread = params["threadId"]
            turn = f"turn-{self.thread_count}"
            self.turn_started.set()
            if self.scenario:
                self.scenario(thread, turn)
            elif self.hang_at != "completion":
                self.emit("item/agentMessage/delta", {"threadId": "foreign", "turnId": turn, "delta": "LEAK"})
                self.emit("item/agentMessage/delta", {"threadId": thread, "turnId": "foreign-turn", "delta": "LEAK"})
                self.emit("item/started", {"threadId": thread, "turnId": turn, "item": {"id": "user", "type": "userMessage"}})
                self.emit("item/completed", {"threadId": thread, "turnId": turn,
                                             "item": {"id": "reasoning", "type": "reasoning", "summary": ["private reasoning"]}})
                self.emit("item/reasoning/summaryTextDelta", {"threadId": thread, "turnId": turn, "delta": "private reasoning"})
                self.emit("item/agentMessage/delta", {"threadId": thread, "turnId": turn, "delta": '{"okay":true}'})
                final = {"id": "answer", "type": "agentMessage", "text": '{"okay":true}'}
                self.emit("item/completed", {"threadId": thread, "turnId": turn, "item": final})
                self.emit("thread/tokenUsage/updated", {"threadId": thread, "turnId": turn,
                                                       "tokenUsage": {"total": {"inputTokens": 5, "outputTokens": 3, "email": "secret"}, "token": "secret"}})
                self.emit("turn/completed", {"threadId": thread, "turn": {
                    "id": turn, "status": self.turn_status, "items": [final],
                }})
            return {"turn": {"id": turn}}
        if method == "turn/interrupt":
            return {}
        raise AssertionError("Unexpected fixture call")


class CodexModelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "research-model"
        self.transport = FakeTransport()
        self.model = CodexModel(self.root, transport=self.transport)

    async def asyncTearDown(self):
        await self.model.close()
        self.tmp.cleanup()

    async def complete(self, *, role="compiler", timeout=1.0, **overrides):
        options = {"role": role, "instructions": "Protected fixture contract.",
                   "payload": {"request": "Study attribution."}, "model": "fixture-model",
                   "timeout_seconds": timeout}
        options.update(overrides)
        return await self.model.complete(**options)

    async def assert_code(self, code, **options):
        with self.assertRaises(ModelError) as caught:
            await self.complete(**options)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), code)

    async def test_readiness_has_no_account_identity_or_credentials(self):
        result = await self.model.readiness()
        context_hash = result.pop("auth_context_hash")
        self.assertRegex(context_hash, r"^[a-f0-9]{64}$")
        self.assertEqual(context_hash, self.model.auth_context_hash)
        self.assertEqual(result, {"ready": True, "code": "READY", "provider": "openai",
                                  "model_control": "configured", "security": True})
        self.assertEqual(self.transport.calls, [("account/read", {"refreshToken": False})])
        self.assertNotIn("secret", json.dumps(result))

    async def test_signed_out_rejected_before_thread_or_model_call(self):
        self.transport.account = None
        await self.assert_code("SIGN_IN_REQUIRED")
        self.assertFalse(any(method == "thread/start" for method, _ in self.transport.calls))

    async def test_api_key_account_has_no_fallback(self):
        self.transport.account = {"type": "apiKey", "apiKey": "secret"}
        result = await self.model.readiness()
        self.assertFalse(result["ready"])
        self.assertEqual(result["code"], "SUBSCRIPTION_REQUIRED")
        await self.assert_code("SUBSCRIPTION_REQUIRED")

    async def test_every_role_gets_new_thread_and_isolated_instructions(self):
        compiler = await self.complete(role="compiler", instructions="Compiler-only contract.")
        verifier = await self.complete(role="verifier", instructions="Verifier-only protected rubric.")
        self.assertNotEqual(compiler["thread_id"], verifier["thread_id"])
        starts = [params for method, params in self.transport.calls if method == "thread/start"]
        self.assertEqual(len(starts), 2)
        self.assertIn("Compiler-only contract", starts[0]["developerInstructions"])
        self.assertNotIn("Compiler-only contract", starts[1]["developerInstructions"])
        self.assertIn("Verifier-only protected rubric", starts[1]["developerInstructions"])
        for params in starts:
            self.assertEqual(params["cwd"], str(self.root.resolve() / "research-workspace"))
            self.assertEqual(params["sandbox"], "read-only")
            self.assertFalse(params["allowProviderModelFallback"])
            self.assertEqual(params["modelProvider"], "openai")
            self.assertEqual(params["config"]["web_search"], "disabled")
            self.assertFalse(params["config"]["features.shell_tool"])
            self.assertFalse(params["config"]["features.apps"])
        self.assertFalse(any("resume" in method for method, _ in self.transport.calls))
        self.assertFalse((self.root / "bindings.json").exists())

    async def test_early_events_foreign_threads_usage_and_agent_final(self):
        result = await self.complete()
        self.assertEqual(result["text"], '{"okay":true}')
        self.assertEqual(result["provider"], "openai")
        self.assertEqual(result["model"], "fixture-model")
        self.assertEqual(result["tool_calls"], [])
        self.assertEqual(result["usage"], {"total": {"inputTokens": 5, "outputTokens": 3}})
        self.assertGreaterEqual(result["duration_ms"], 0)
        self.assertNotIn("private reasoning", json.dumps(result))
        self.assertNotIn("secret", json.dumps(result))
        self.assertEqual(self.transport.listeners, {self.model._observe_account})

    async def test_reused_thread_is_blocked(self):
        self.transport.reuse_thread = True
        await self.complete()
        await self.assert_code("MODEL_THREAD_REUSED")
        self.assertEqual(sum(method == "turn/start" for method, _ in self.transport.calls), 1)

    async def test_configuration_mismatch_blocks_instead_of_fallback(self):
        for attribute, value in (("thread_provider", "other-provider"), ("thread_model", "other-model")):
            with self.subTest(attribute=attribute):
                self.transport.thread_provider = "openai"
                self.transport.thread_model = "fixture-model"
                setattr(self.transport, attribute, value)
                await self.assert_code("MODEL_CONFIGURATION_MISMATCH")
        self.assertFalse(any(method == "turn/start" for method, _ in self.transport.calls))

    async def test_tool_and_unknown_items_are_blocked(self):
        for kind in ("commandExecution", "mcpToolCall", "dynamicToolCall", "webSearch",
                     "fileChange", "imageView", "unexpectedNewItemType"):
            with self.subTest(kind=kind):
                def events(thread, turn):
                    self.transport.emit("item/started", {"threadId": thread, "turnId": turn,
                                                         "item": {"id": "tool", "type": kind}})
                self.transport.scenario = events
                await self.assert_code("MODEL_TOOLS_FORBIDDEN")
        interrupts = [params for method, params in self.transport.calls if method == "turn/interrupt"]
        self.assertEqual(len(interrupts), 7)
        self.assertEqual(self.transport.listeners, {self.model._observe_account})

    async def test_terminal_embedded_tool_is_rejected(self):
        def events(thread, turn):
            self.transport.emit("item/agentMessage/delta", {"threadId": thread, "turnId": turn, "delta": "valid text"})
            self.transport.emit("turn/completed", {"threadId": thread, "turn": {
                "id": turn, "status": "completed", "items": [{"id": "tool", "type": "commandExecution"}],
            }})
        self.transport.scenario = events
        await self.assert_code("MODEL_TOOLS_FORBIDDEN")

    async def test_non_agent_tool_delta_is_rejected(self):
        self.transport.scenario = lambda thread, turn: self.transport.emit("item/commandExecution/outputDelta", {
            "threadId": thread, "turnId": turn, "delta": "tool output",
        })
        await self.assert_code("MODEL_TOOLS_FORBIDDEN")

    async def test_server_request_refusal_blocks_acceptance(self):
        self.transport.scenario = lambda thread, turn: self.transport.emit("research/server-request-rejected", {})
        await self.assert_code("MODEL_TOOLS_FORBIDDEN")

    async def test_completed_text_is_preferred_without_duplicating_deltas(self):
        def events(thread, turn):
            self.transport.emit("item/agentMessage/delta", {"threadId": thread, "turnId": turn, "delta": "partial"})
            self.transport.emit("item/completed", {"threadId": thread, "turnId": turn,
                                                  "item": {"id": "answer", "type": "agentMessage", "text": "complete"}})
            self.transport.emit("turn/completed", {"threadId": thread, "turn": {"id": turn, "status": "completed"}})
        self.transport.scenario = events
        self.assertEqual((await self.complete())["text"], "complete")

    async def test_multiple_agent_outputs_are_not_silently_discarded(self):
        def events(thread, turn):
            for ident in ("one", "two"):
                self.transport.emit("item/completed", {"threadId": thread, "turnId": turn,
                                                      "item": {"id": ident, "type": "agentMessage", "text": ident}})
        self.transport.scenario = events
        await self.assert_code("MODEL_MULTIPLE_OUTPUTS")

    async def test_empty_or_failed_output_cannot_succeed(self):
        for status, code in (("completed", "MODEL_EMPTY_OUTPUT"), ("failed", "MODEL_TURN_FAILED"),
                             ("interrupted", "MODEL_CANCELLED")):
            with self.subTest(status=status):
                self.transport.scenario = lambda thread, turn: self.transport.emit("turn/completed", {
                    "threadId": thread, "turn": {"id": turn, "status": status},
                })
                await self.assert_code(code)

    async def test_output_and_event_queue_are_bounded(self):
        self.transport.scenario = lambda thread, turn: self.transport.emit("item/agentMessage/delta", {
            "threadId": thread, "turnId": turn, "delta": "123456789",
        })
        with patch("jiuwenswarm.research.model.MAX_OUTPUT_BYTES", 8):
            await self.assert_code("MODEL_OUTPUT_LIMIT")
        self.transport.scenario = None
        with patch("jiuwenswarm.research.model.MAX_EVENTS", 2):
            await self.assert_code("MODEL_EVENT_LIMIT")

    async def test_event_payload_size_is_bounded(self):
        self.transport.scenario = lambda thread, turn: self.transport.emit("item/agentMessage/delta", {
            "threadId": thread, "turnId": turn, "delta": "x" * 100,
        })
        with patch("jiuwenswarm.research.model.MAX_EVENT_BYTES", 20):
            await self.assert_code("MODEL_EVENT_LIMIT")

    async def test_total_timeout_covers_start_account_thread_and_turn(self):
        for stage in ("start", "account/read", "thread/start", "turn/start", "completion"):
            with self.subTest(stage=stage):
                self.transport.hang_at = stage
                previous = self.transport.closed
                await self.assert_code("MODEL_TIMEOUT", timeout=0.01)
                self.assertGreater(self.transport.closed, previous)
                self.assertEqual(self.transport.listeners, {self.model._observe_account})
        self.assertEqual(sum(method == "turn/interrupt" for method, _ in self.transport.calls), 1)

    async def test_cancellation_interrupts_turn_and_closes_owned_transport(self):
        self.transport.hang_at = "completion"
        task = asyncio.create_task(self.complete(timeout=10))
        await self.transport.turn_started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(any(method == "turn/interrupt" for method, _ in self.transport.calls))
        self.assertEqual(self.transport.closed, 1)
        self.assertEqual(self.transport.listeners, {self.model._observe_account})

    async def test_busy_call_does_not_start_second_invocation(self):
        self.transport.hang_at = "completion"
        task = asyncio.create_task(self.complete(timeout=10))
        await self.transport.turn_started.wait()
        await self.assert_code("MODEL_BUSY")
        self.assertEqual((await self.model.readiness())["code"], "MODEL_BUSY")
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.transport.thread_count, 1)

    async def test_unknown_provider_errors_are_stable_and_never_retried(self):
        self.transport.error = RuntimeError("credential=do-not-expose-this")
        await self.assert_code("MODEL_UNAVAILABLE")
        self.assertEqual(sum(method == "turn/start" for method, _ in self.transport.calls), 1)
        self.transport.error = CodexError("RUNTIME_DISCONNECTED")
        await self.assert_code("RUNTIME_DISCONNECTED")

    async def test_account_change_blocks_current_output(self):
        self.transport.scenario = lambda thread, turn: self.transport.emit("account/updated", {"email": "secret"})
        await self.assert_code("MODEL_ACCOUNT_CHANGED")

    async def test_identity_is_required_without_exposing_raw_account_fields(self):
        self.transport.account = {"type": "chatgpt", "token": "do-not-expose"}
        ready = await self.model.readiness()
        self.assertFalse(ready["ready"])
        self.assertEqual(ready["code"], "ACCOUNT_IDENTITY_UNAVAILABLE")
        self.assertNotIn("auth_context_hash", ready)
        await self.assert_code("ACCOUNT_IDENTITY_UNAVAILABLE")
        self.assertFalse(any(method == "thread/start" for method, _ in self.transport.calls))
        self.assertNotIn("do-not-expose", json.dumps(ready))

    async def test_silent_identity_change_after_readiness_never_dispatches_or_rebinds(self):
        ready = await self.model.readiness()
        original_hash = ready["auth_context_hash"]
        self.transport.account["email"] = "different-account@example.invalid"
        await self.assert_code("MODEL_ACCOUNT_CHANGED")
        self.assertFalse(any(method == "thread/start" for method, _ in self.transport.calls))
        self.assertEqual(self.model.auth_context_hash, original_hash)
        self.transport.account["email"] = "not-for-evidence@example.invalid"
        ready = await self.model.readiness()
        self.assertFalse(ready["ready"])
        self.assertEqual(ready["code"], "MODEL_ACCOUNT_CHANGED")
        self.assertNotIn("auth_context_hash", ready)

    async def test_identity_change_between_compiler_and_verifier_is_not_silent(self):
        compiler = await self.complete()
        self.transport.account["email"] = "other-account@example.invalid"
        await self.assert_code("MODEL_ACCOUNT_CHANGED", role="verifier")
        self.assertEqual(sum(method == "turn/start" for method, _ in self.transport.calls), 1)
        self.assertEqual(self.model.auth_context_hash, compiler["auth_context_hash"])

    async def test_lifetime_observer_covers_idle_gap_and_thread_start(self):
        await self.model.readiness()
        self.transport.emit("account/updated", {"email": "never-save-this"})
        await self.assert_code("MODEL_ACCOUNT_CHANGED")
        self.assertFalse(any(method == "thread/start" for method, _ in self.transport.calls))
        replacement = CodexModel(self.root, transport=FakeTransport())
        try:
            await replacement.readiness()
            replacement.transport.on_request = lambda method, params: replacement.transport.emit("account/updated", {}) if method == "thread/start" else None
            with self.assertRaises(ModelError) as caught:
                await replacement.complete(role="compiler", instructions="Fixture", payload={"request": "Scoped"}, model="fixture-model", timeout_seconds=1)
            self.assertEqual(caught.exception.code, "MODEL_ACCOUNT_CHANGED")
            self.assertFalse(any(method == "turn/start" for method, _ in replacement.transport.calls))
        finally:
            await replacement.close()
        self.assertFalse(replacement.transport.listeners)

    async def test_post_call_account_read_rejects_silent_identity_change(self):
        def events(thread, turn):
            self.transport.emit("item/agentMessage/delta", {"threadId": thread, "turnId": turn, "delta": "Candidate"})
            self.transport.account["email"] = "changed-during-call@example.invalid"
            self.transport.emit("turn/completed", {"threadId": thread, "turn": {"id": turn, "status": "completed"}})
        self.transport.scenario = events
        await self.assert_code("MODEL_ACCOUNT_CHANGED")
        self.assertEqual(sum(method == "account/read" for method, _ in self.transport.calls), 2)

    async def test_identity_hash_is_salted_per_instance_and_stable_per_call(self):
        ready = await self.model.readiness()
        result = await self.complete()
        self.assertEqual(ready["auth_context_hash"], result["auth_context_hash"])
        self.assertNotIn("not-for-evidence", json.dumps(result))
        replacement = CodexModel(self.root, transport=FakeTransport())
        try:
            self.assertNotEqual((await replacement.readiness())["auth_context_hash"], ready["auth_context_hash"])
        finally:
            await replacement.close()

    async def test_stable_account_id_takes_precedence_over_email_metadata(self):
        self.transport.account["id"] = "stable-account-id"
        ready = await self.model.readiness()
        self.transport.account["email"] = "changed-email-metadata@example.invalid"
        result = await self.complete()
        self.assertEqual(result["auth_context_hash"], ready["auth_context_hash"])
        self.assertNotIn("stable-account-id", json.dumps(result))
        self.assertNotIn("changed-email", json.dumps(result))

    async def test_account_notification_during_initial_account_read_is_uncertain(self):
        self.transport.on_request = lambda method, params: self.transport.emit("account/updated", {}) if method == "account/read" else None
        ready = await self.model.readiness()
        self.assertFalse(ready["ready"])
        self.assertEqual(ready["code"], "MODEL_ACCOUNT_CHANGED")
        self.assertNotIn("auth_context_hash", ready)

    async def test_readiness_timeout_is_reported_and_cleanup_is_bounded(self):
        self.transport.hang_at = "start"
        with patch("jiuwenswarm.research.model.READINESS_TIMEOUT_SECONDS", 0.01):
            result = await self.model.readiness()
        self.assertFalse(result["ready"])
        self.assertEqual(result["code"], "MODEL_TIMEOUT")
        self.assertEqual(self.transport.closed, 1)

    async def test_invalid_inputs_do_not_start_any_process(self):
        invalid = ({"role": "planner"}, {"role": []}, {"instructions": ""}, {"payload": []},
                   {"payload": {"bad": float("nan")}}, {"model": "secret\nmodel"},
                   {"timeout_seconds": 0}, {"timeout_seconds": float("inf")}, {"timeout_seconds": True})
        for options in invalid:
            with self.subTest(options=options):
                await self.assert_code("MODEL_INVALID_INPUT", **options)
        self.assertEqual(self.transport.starts, 0)

    async def test_explicit_close_disables_future_calls(self):
        await self.model.close()
        await self.assert_code("MODEL_CLOSED")
        self.assertEqual((await self.model.readiness())["code"], "MODEL_CLOSED")

    async def test_real_transport_ownership_is_dedicated_without_starting_it(self):
        dedicated = CodexModel(self.root)
        self.assertIsInstance(dedicated.transport, AppServerTransport)
        self.assertEqual(dedicated.transport.root, self.root.resolve())
        self.assertEqual(dedicated.transport.home, self.root.resolve() / "codex-home")
        self.assertEqual(dedicated.transport.cwd, self.root.resolve() / "research-workspace")
        chat = AppServerTransport(Path(self.tmp.name) / "chat")
        with self.assertRaisesRegex(ModelError, "MODEL_PROFILE_MISMATCH"):
            CodexModel(self.root, transport=chat)
        await dedicated.close()
        self.assertFalse(self.root.exists())


class ServerRequestRefusalTests(unittest.IsolatedAsyncioTestCase):
    async def test_inherited_protocol_rejects_requests_without_exposing_arguments(self):
        class Writer:
            def __init__(self):
                self.sent = []

            def write(self, data):
                self.sent.append(json.loads(data))

            async def drain(self):
                pass

        class Process:
            def __init__(self):
                self.returncode = None
                self.stdin = Writer()
                self.stdout = asyncio.StreamReader()

            def terminate(self):
                self.returncode = 0

        with tempfile.TemporaryDirectory() as temporary:
            transport = _ResearchTransport(Path(temporary))
            process = Process()
            transport.process = process
            events = []
            transport.listeners.add(lambda method, params: events.append((method, params)))
            process.stdout.feed_data(json.dumps({"id": 55, "method": "item/commandExecution/requestApproval",
                                                "params": {"secret": "do-not-echo", "command": "unsafe"}}).encode() + b"\n")
            process.stdout.feed_eof()
            await transport._read(process)
            self.assertEqual(process.stdin.sent[0]["id"], 55)
            self.assertEqual(process.stdin.sent[0]["error"]["code"], -32601)
            self.assertNotIn("do-not-echo", json.dumps(process.stdin.sent))
            self.assertIn(("research/server-request-rejected", {}), events)
            self.assertNotIn("unsafe", json.dumps(events))


class MockModelTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_mock_identity_and_attributed_compiler_output(self):
        mock = MockModel()
        ready = await mock.readiness()
        self.assertEqual(ready["provider"], "mock")
        self.assertEqual(ready["profile"], "wiring-only")
        self.assertTrue(ready["mock"])
        self.assertEqual(ready["auth_context_hash"], MOCK_AUTH_CONTEXT_HASH)
        request = "研究原样提取，保留 attribution。"
        result = await mock.complete(role="compiler", instructions="Fixture", payload={
            "request": request, "request_hash": "fixture-hash",
        }, model=None, timeout_seconds=1)
        output = json.loads(result["text"])
        self.assertEqual(output["schema_version"], "intent.v1")
        self.assertEqual(output["request_hash"], "fixture-hash")
        self.assertEqual(output["objective"], [{"text": request, "quote": request, "start": 0, "end": len(request)}])
        self.assertEqual(output["omissions"], ["desired_outcome", "scope", "constraints"])
        self.assertEqual(result["tool_calls"], [])

    async def test_mock_verifier_preserves_exact_subject_and_five_explicit_checks(self):
        mock = MockModel()
        subject = {"candidate_hash": "exact", "request_hash": "original", "attempt_id": "one"}
        request = "A scoped request."
        result = await mock.complete(role="verifier", instructions="Protected fixture", payload={
            "request": request, "subject": subject, "candidate": {"objective": []},
        }, model=None, timeout_seconds=1)
        output = json.loads(result["text"])
        self.assertEqual(output["schema_version"], "intent-assessment.v1")
        self.assertEqual(output["subject"], subject)
        self.assertEqual([check["id"] for check in output["checks"]], ["omission", "addition", "scope", "ambiguity", "instruction"])
        for check in output["checks"]:
            self.assertEqual(check["status"], "PASS")
            self.assertEqual(check["reason"], "Mock wiring only")
            self.assertEqual(check["evidence"], [{"source": "request", "quote": request}])
        await mock.close()
        self.assertFalse((await mock.readiness())["ready"])


if __name__ == "__main__":
    unittest.main()
