"""M1-INTENT/V03 protected fresh-call protocol checks; no external model."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from jiuwenswarm.ai4research.intent.bridge import CodexBridge, provider_output_schema
from jiuwenswarm.ai4research.intent.models import FIXED_DEFAULTS, FrozenPolicy
from jiuwenswarm.ai4research.intent.service import IntentService
from jiuwenswarm.ai4research.intent.store import IntentStore
from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService


class ProtocolFixture:
    def __init__(self):
        self.listeners = set()
        self.calls = []
        self.account = {"type": "chatgpt", "email": "fixture@example.invalid"}
        self.counter = 0
        self.hold = False
        self.tool = False
        self.output = '  {"answer":"研究"}\n'
        self.usage = {"inputTokens": 20, "outputTokens": 10, "totalTokens": 30}
        self.closed = 0

    async def start(self):
        pass

    async def close(self):
        self.closed += 1
        self.emit("transport/closed", {})

    def emit(self, method, params):
        for listener in tuple(self.listeners):
            listener(method, params)

    async def request(self, method, params=None):
        self.calls.append((method, params))
        if method == "account/read":
            return {"account": self.account}
        if method == "thread/start":
            self.counter += 1
            return {"thread": {"id": f"thread-{self.counter}"}, "model": "configured-fixture-model"}
        if method == "turn/start":
            thread = params["threadId"]
            turn = f"turn-{self.counter}"
            base = {"threadId": thread, "turnId": turn}
            self.emit("item/started", {**base, "item": {"type": "userMessage"}})
            self.emit("item/agentMessage/delta", {**base, "delta": self.output})
            self.emit("thread/tokenUsage/updated", {**base, "tokenUsage": {"total": self.usage}})
            if self.tool:
                self.emit("item/started", {**base, "item": {"type": "commandExecution"}})
            elif not self.hold:
                self.emit("turn/completed", {"threadId": thread, "turn": {"id": turn, "status": "completed"}})
            return {"turn": {"id": turn}}
        return {}


class IntentBridgeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.protocol = ProtocolFixture()
        self.service = SubscriptionService(Path(self.tmp.name), transport=self.protocol)
        self.bridge = CodexBridge(self.service)

    def tearDown(self):
        self.tmp.cleanup()

    async def invoke(self, role="compiler", policy=None):
        return await self.bridge.invoke(role, "Frozen prompt", "run-fixture", policy or FrozenPolicy())

    async def test_separate_fresh_threads_exact_raw_usage_and_configured_model(self):
        first = await self.invoke()
        second = await self.invoke("verifier")
        self.assertNotEqual(first.conversation_id, second.conversation_id)
        self.assertEqual(first.raw_output, self.protocol.output)
        self.assertEqual(first.usage["total_tokens"], 30)
        self.assertEqual(first.model, "configured-fixture-model")
        self.assertEqual(first.status, "completed")
        for method, params in self.protocol.calls:
            if method == "thread/start":
                self.assertEqual(params["sandbox"], "read-only")
                self.assertFalse(params["allowProviderModelFallback"])
        self.assertFalse(self.service.bindings)

    async def test_role_output_schemas_reach_only_intent_turns(self):
        await self.invoke("compiler")
        await self.invoke("verifier")
        turns = [params for method, params in self.protocol.calls if method == "turn/start"]
        self.assertEqual(turns[0]["outputSchema"], provider_output_schema("compiler"))
        self.assertEqual(turns[1]["outputSchema"], provider_output_schema("verifier"))
        defaults = turns[0]["outputSchema"]["properties"]["defaults"]
        self.assertFalse(defaults["additionalProperties"])
        self.assertEqual(set(defaults["required"]), set(FIXED_DEFAULTS))
        self.assertEqual({key: value["const"] for key, value in defaults["properties"].items()}, FIXED_DEFAULTS)
        self.assertEqual(turns[1]["outputSchema"]["properties"]["checks"]["minItems"], 6)
        self.assertEqual(turns[1]["outputSchema"]["properties"]["checks"]["maxItems"], 6)
        events = [event async for event in self.service.stream("ordinary", "request", "Ordinary chat")]
        self.assertTrue(events)
        last_turn = [params for method, params in self.protocol.calls if method == "turn/start"][-1]
        self.assertNotIn("outputSchema", last_turn)
        self.assertEqual(last_turn["input"][0]["text"], "Ordinary chat")

    async def test_tool_attempt_is_observed_failed_contained_and_not_retried(self):
        self.protocol.tool = True
        observed = await self.invoke()
        self.assertEqual(observed.status, "failed")
        self.assertEqual(observed.error_code, "PROHIBITED_TOOL")
        self.assertEqual(observed.tools, ["commandExecution"])
        self.assertTrue(observed.effects)
        self.assertEqual(self.protocol.closed, 1)
        self.assertEqual(sum(m == "turn/start" for m, _ in self.protocol.calls), 1)

    async def test_timeout_contains_and_keeps_partial_output(self):
        self.protocol.hold = True
        observed = await self.invoke(policy=FrozenPolicy(per_call_seconds=0.02))
        self.assertEqual(observed.status, "timeout")
        self.assertEqual(observed.raw_output, self.protocol.output)
        self.assertEqual(self.protocol.closed, 1)

    async def test_output_byte_bound_halts_without_retry(self):
        observed = await self.invoke(policy=FrozenPolicy(max_output_bytes=4))
        self.assertEqual(observed.error_code, "OUTPUT_LIMIT")
        self.assertEqual(self.protocol.closed, 1)

    async def test_signed_out_is_environment_blocked_without_turn(self):
        self.protocol.account = None
        observed = await self.invoke()
        self.assertEqual(observed.status, "environment_blocked")
        self.assertEqual(observed.error_code, "SIGN_IN_REQUIRED")
        self.assertFalse(any(m == "turn/start" for m, _ in self.protocol.calls))

    async def test_malformed_usage_stays_unavailable(self):
        self.protocol.usage["totalTokens"] = "30"
        self.assertIsNone((await self.invoke()).usage)

    async def test_cancellation_contains_inflight_call(self):
        self.protocol.hold = True
        task = asyncio.create_task(self.invoke())
        while not self.service.active:
            await asyncio.sleep(0)
        task.cancel()
        self.assertEqual((await task).status, "cancelled")
        self.assertEqual(self.protocol.closed, 1)

    async def test_connected_cancellation_retains_available_partial_invocation(self):
        self.protocol.hold = True
        store = IntentStore(Path(self.tmp.name) / "intent-state")
        orchestrator = IntentService(store, self.bridge)
        run_id = await orchestrator.submit("Compare baseline A and B on supplied data.", "owner", "profile", "workspace")
        while not self.service.active:
            await asyncio.sleep(0)
        result = await orchestrator.cancel(run_id, "owner")
        self.assertEqual(result["state"], "HALTED")
        self.assertIn("CANCELLED", result["reasons"])
        self.assertIsNone(result["accepted_reference"])
        artifacts = {artifact["name"] for artifact in result["evidence"]["artifacts"]}
        self.assertIn("compiler.json", artifacts)
        self.assertIn("candidate.raw.json", artifacts)
        directory = store.artifact_root / run_id
        observation = json.loads((directory / "compiler.json").read_text(encoding="utf-8"))
        self.assertEqual(observation["status"], "cancelled")
        self.assertEqual(observation["raw_output"], self.protocol.output)
        self.assertEqual(observation["usage"]["total_tokens"], 30)
        self.assertEqual((directory / "candidate.raw.json").read_text(encoding="utf-8"), self.protocol.output)
        self.assertNotIn("verifier.json", artifacts)
        self.assertEqual(sum(method == "turn/start" for method, _ in self.protocol.calls), 1)


if __name__ == "__main__":
    unittest.main()
