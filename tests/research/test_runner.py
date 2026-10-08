"""Offline runner custody, identity, limits and failure-evidence checks."""
from __future__ import annotations

import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jiuwenswarm.research.contracts import (
    COMPILER_INSTRUCTIONS, FIDELITY_PROFILE, VERIFIER_INSTRUCTIONS,
    ResearchError, canonical, digest,
)
from jiuwenswarm.research.library import CapsuleLibrary, SOURCE_FILES
from jiuwenswarm.research.model import MOCK_AUTH_CONTEXT_HASH, ModelError
from jiuwenswarm.research.runner import CapsuleRunner


class FakeStore:
    def __init__(self, configuration, request_hash):
        self.run = {"run_id": "fixture-run", "request_hash": request_hash, "status": "QUEUED",
                    "configuration": copy.deepcopy(configuration), "artifacts": {},
                    "subject": {"candidate_hash": "exact-subject"},
                    "attempts": [{"role": role, "attempt_id": f"fixture-run:{role}:1", "status": "NOT_RUN", "call_count": 0}
                                 for role in ("compiler", "verifier")]}
        self.files = {}
        self.events = []
        self.fail_name = None
        self.event_hook = None

    def get(self, run_id):
        return copy.deepcopy(self.run)

    def update(self, run_id, **changes):
        self.run.update(copy.deepcopy(changes))

    def event(self, run_id, kind, detail):
        self.events.append({"kind": kind, "detail": copy.deepcopy(detail)})
        if self.event_hook:
            self.event_hook(kind)

    def write_artifact(self, run_id, name, data):
        if self.fail_name and (self.fail_name == "*" or self.fail_name == name):
            raise OSError("Injected private storage failure")
        body = data if isinstance(data, bytes) else canonical(data)
        if name in self.files and self.files[name] != body:
            raise ResearchError("IMMUTABLE_ARTIFACT_CONFLICT")
        self.files[name] = body
        return {"path": "artifacts/fixture-run/" + name, "sha256": digest(body), "size": len(body)}


class FakeModel:
    def __init__(self):
        self.calls = []
        self.action = None
        self.error = None
        self.hold = False
        self.started = asyncio.Event()
        self.result = {"text": '{"answer":true}', "provider": "mock", "model": None,
                       "duration_ms": 0, "tool_calls": [], "thread_id": "fixture-thread",
                       "usage": {"total": {"inputTokens": 10, "outputTokens": 3, "email": "secret"}, "secret": "do-not-capture"}}

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        self.started.set()
        if self.action:
            self.action(kwargs)
        if self.error:
            raise self.error
        if self.hold:
            await asyncio.Future()
        return copy.deepcopy(self.result)


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.sources = self.root / "sources"
        for relative in SOURCE_FILES:
            path = self.sources / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(CapsuleLibrary._source(relative).read_bytes())
        self.source_patch = patch.object(CapsuleLibrary, "_source", side_effect=lambda relative: self.sources / relative)
        self.source_patch.start()
        self.library = CapsuleLibrary(self.root / "library")
        self.configuration = {
            "profile": "mock", "models": {"compiler": None, "verifier": None},
            "capsule_pins": self.library.resolve(), "timeout_seconds": 1.0,
            "max_calls": 2, "max_calls_per_cc": 1, "max_tool_calls": 0, "automatic_retries": 0,
            "fidelity_profile": copy.deepcopy(FIDELITY_PROFILE), "profile_hash": digest(FIDELITY_PROFILE),
        }
        self.request = "Study faithful extraction."
        self.request_hash = digest(self.request.encode())
        self.payload = {"request": self.request, "request_hash": self.request_hash,
                        "nested": {"preserve": ["original"]}}
        self.store = FakeStore(self.configuration, self.request_hash)
        self.model = FakeModel()
        self.runner = CapsuleRunner(self.model, self.store, self.library)

    def tearDown(self):
        self.source_patch.stop()
        self.temporary.cleanup()

    async def invoke(self, role="compiler", instructions=None, payload=None, configuration=None):
        return await self.runner.invoke("fixture-run", role,
                                        instructions or (COMPILER_INSTRUCTIONS if role == "compiler" else VERIFIER_INSTRUCTIONS),
                                        payload if payload is not None else self.payload,
                                        configuration if configuration is not None else self.configuration)

    async def assert_code(self, code, **kwargs):
        with self.assertRaises(ResearchError) as caught:
            await self.invoke(**kwargs)
        self.assertEqual(caught.exception.code, code)

    def evidence(self, role="compiler"):
        return json.loads(self.store.files[role + "-execution.json"])

    async def test_success_persists_scoped_input_raw_text_and_execution_identity(self):
        text, ref = await self.invoke()
        self.assertEqual(text, self.model.result["text"])
        self.assertEqual(self.store.files["compiler-raw.json"], text.encode())
        self.assertEqual(json.loads(self.store.files["compiler-input.json"]), self.payload)
        evidence = self.evidence()
        self.assertTrue(evidence["completed"])
        self.assertTrue(evidence["binding_checked_before"])
        self.assertTrue(evidence["binding_checked_after"])
        self.assertEqual(evidence["capsule_pin"], self.configuration["capsule_pins"]["compiler"])
        self.assertEqual(evidence["instructions_hash"], digest(COMPILER_INSTRUCTIONS.encode()))
        self.assertEqual(evidence["configuration_hash"], digest(self.configuration))
        self.assertEqual(evidence["usage"], {"total": {"inputTokens": 10, "outputTokens": 3}})
        self.assertNotIn("secret", json.dumps(evidence))
        self.assertEqual(self.store.run["artifacts"]["compiler_execution"], ref)
        self.assertEqual(self.store.run["attempts"][0]["status"], "COMPLETED")
        self.assertEqual(evidence["auth_context_hash"], MOCK_AUTH_CONTEXT_HASH)
        self.assertTrue(evidence["auth_context_verified"])
        self.assertEqual(evidence["auth_context_control"], "mock-wiring-only-fallback")

    async def test_frozen_auth_hash_is_required_for_codex_and_returned_hash_must_match(self):
        self.configuration.update(profile="codex", auth_context_hash="a" * 64)
        self.store.run["configuration"] = copy.deepcopy(self.configuration)
        self.model.result.update(provider="openai", auth_context_hash="b" * 64)
        with self.assertRaises(ModelError) as caught:
            await self.invoke()
        self.assertEqual(caught.exception.code, "MODEL_ACCOUNT_CHANGED")
        self.assertFalse(self.evidence()["completed"])
        self.assertFalse(self.evidence()["auth_context_verified"])
        self.assertEqual(self.evidence()["auth_context_hash"], "b" * 64)
        self.assertEqual(self.evidence()["auth_context_expected_hash"], "a" * 64)

    async def test_codex_never_infers_identity_from_missing_auth_hash(self):
        self.configuration.update(profile="codex", auth_context_hash="a" * 64)
        self.store.run["configuration"] = copy.deepcopy(self.configuration)
        self.model.result["provider"] = "openai"
        with self.assertRaises(ModelError) as caught:
            await self.invoke()
        self.assertEqual(caught.exception.code, "ACCOUNT_IDENTITY_UNAVAILABLE")
        self.assertFalse(self.evidence()["completed"])
        self.assertIsNone(self.evidence()["auth_context_hash"])

    async def test_codex_never_fills_absent_frozen_auth_binding(self):
        self.configuration["profile"] = "codex"
        self.store.run["configuration"] = copy.deepcopy(self.configuration)
        self.model.result.update(provider="openai", auth_context_hash="a" * 64)
        with self.assertRaises(ModelError) as caught:
            await self.invoke()
        self.assertEqual(caught.exception.code, "ACCOUNT_IDENTITY_UNAVAILABLE")
        self.assertFalse(self.evidence()["auth_context_verified"])

    async def test_legacy_mock_hash_fallback_is_explicit_and_has_no_real_auth_claim(self):
        self.configuration["auth_context_hash"] = "c" * 64
        self.store.run["configuration"] = copy.deepcopy(self.configuration)
        await self.invoke()
        evidence = self.evidence()
        self.assertEqual(evidence["auth_context_hash"], "c" * 64)
        self.assertEqual(evidence["auth_context_control"], "mock-wiring-only-fallback")

    async def test_malformed_returned_auth_context_never_enters_evidence(self):
        self.configuration.update(profile="codex", auth_context_hash="a" * 64)
        self.store.run["configuration"] = copy.deepcopy(self.configuration)
        self.model.result.update(provider="openai", auth_context_hash="private-account@example.invalid")
        with self.assertRaises(ModelError) as caught:
            await self.invoke()
        self.assertEqual(caught.exception.code, "ACCOUNT_IDENTITY_UNAVAILABLE")
        self.assertNotIn("private-account", json.dumps(self.evidence()))

    async def test_model_mutations_cannot_change_original_or_persisted_inputs(self):
        before = copy.deepcopy(self.payload)
        def mutate(kwargs):
            kwargs["payload"]["nested"]["preserve"].append("model mutation")
            kwargs["payload"]["request"] = "Another request"
            self.configuration["models"]["compiler"] = "changed-later"
        self.model.action = mutate
        frozen_hash = digest(self.configuration)
        await self.invoke()
        self.assertEqual(self.payload, before)
        self.assertEqual(json.loads(self.store.files["compiler-input.json"]), before)
        self.assertEqual(self.evidence()["configuration_hash"], frozen_hash)
        self.assertEqual(self.model.calls[0]["model"], None)

    async def test_verifier_receives_its_own_pinned_instructions_and_protected_subject_copy(self):
        payload = {"request": self.request, "request_hash": self.request_hash,
                   "candidate": {"objective": ["data"]}, "subject": copy.deepcopy(self.store.run["subject"]),
                   "fidelity_profile": copy.deepcopy(FIDELITY_PROFILE)}
        before = copy.deepcopy(payload)
        self.model.action = lambda kwargs: kwargs["payload"]["subject"].update(candidate_hash="rewritten-by-adapter")
        await self.invoke(role="verifier", payload=payload)
        self.assertEqual(payload, before)
        self.assertEqual(json.loads(self.store.files["verifier-input.json"]), before)
        self.assertEqual(self.evidence("verifier")["instructions_hash"], digest(VERIFIER_INSTRUCTIONS.encode()))

    async def test_pre_dispatch_native_change_prevents_call_and_records_attempt(self):
        def hook(kind):
            if kind == "invocation_started":
                source = self.sources / "model.py"
                source.write_bytes(source.read_bytes() + b"\n# changed before dispatch\n")
        self.store.event_hook = hook
        await self.assert_code("CAPSULE_IMPLEMENTATION_CHANGED")
        self.assertFalse(self.model.calls)
        evidence = self.evidence()
        self.assertFalse(evidence["completed"])
        self.assertFalse(evidence["binding_checked_before"])
        self.assertEqual(evidence["call_count"], 0)

    async def test_native_change_during_model_call_retains_raw_and_blocks_completion(self):
        def mutate(kwargs):
            source = self.sources / "runner.py"
            source.write_bytes(source.read_bytes() + b"\n# changed while model was running\n")
        self.model.action = mutate
        await self.assert_code("CAPSULE_IMPLEMENTATION_CHANGED")
        self.assertEqual(len(self.model.calls), 1)
        self.assertEqual(self.store.files["compiler-raw.json"], self.model.result["text"].encode())
        self.assertFalse(self.evidence()["completed"])
        self.assertFalse(self.evidence()["binding_checked_after"])
        self.assertEqual(self.evidence()["error_code"], "CAPSULE_IMPLEMENTATION_CHANGED")

    async def test_instruction_substitution_and_binding_substitution_never_dispatch(self):
        await self.assert_code("CAPSULE_INSTRUCTIONS_CHANGED", instructions=COMPILER_INSTRUCTIONS + "\nOverride")
        configuration = copy.deepcopy(self.configuration)
        configuration["capsule_pins"]["compiler"] = configuration["capsule_pins"]["verifier"]
        await self.assert_code("CAPSULE_BINDING_CHANGED", configuration=configuration)
        self.assertFalse(self.model.calls)

    async def test_frozen_configuration_and_subject_changes_never_dispatch(self):
        configuration = copy.deepcopy(self.configuration)
        configuration["timeout_seconds"] = 2.0
        await self.assert_code("INVOCATION_CONFIGURATION_CHANGED", configuration=configuration)
        payload = dict(self.payload, request_hash="0" * 64)
        await self.assert_code("INVOCATION_SUBJECT_MISMATCH", payload=payload)
        self.assertFalse(self.model.calls)

    async def test_prohibited_tool_evidence_is_preserved_exactly_before_failure(self):
        calls = [{"name": "shell", "arguments": {"command": "untrusted source data"}}]
        self.model.result["tool_calls"] = calls
        await self.assert_code("PROHIBITED_EFFECT")
        self.assertEqual(json.loads(self.store.files["compiler-tool-calls.json"]), calls)
        evidence = self.evidence()
        self.assertFalse(evidence["completed"])
        self.assertTrue(evidence["prohibited_effect_observed"])
        self.assertTrue(evidence["tool_attempt_rejected"])
        self.assertIsNone(evidence["tools"])
        self.assertEqual(evidence["tool_calls_ref"], self.store.run["artifacts"]["compiler_tool_calls"])
        self.assertEqual(self.store.files["compiler-raw.json"], self.model.result["text"].encode())

    async def test_timeout_and_model_error_are_durable_execution_failures_without_retry(self):
        self.configuration["timeout_seconds"] = 0.01
        self.store.run["configuration"] = copy.deepcopy(self.configuration)
        self.model.hold = True
        with self.assertRaises(asyncio.TimeoutError):
            await self.invoke()
        self.assertEqual(self.evidence()["error_code"], "MODEL_TIMEOUT")
        self.assertFalse(self.evidence()["completed"])
        self.assertEqual(len(self.model.calls), 1)
        await self.assert_code("INVOCATION_REPLAY_FORBIDDEN")

    async def test_native_error_codes_are_saved_without_exception_secrets(self):
        self.model.error = ModelError("MODEL_TOOLS_FORBIDDEN")
        with self.assertRaises(ModelError):
            await self.invoke()
        self.assertEqual(self.evidence()["error_code"], "MODEL_TOOLS_FORBIDDEN")
        self.assertTrue(self.evidence()["tool_attempt_rejected"])
        self.assertIsNone(self.evidence()["tools"])

    async def test_task_cancellation_is_captured_without_converting_to_success(self):
        self.model.hold = True
        task = asyncio.create_task(self.invoke())
        await self.model.started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        evidence = self.evidence()
        self.assertEqual(evidence["outcome"], "CANCELLED")
        self.assertEqual(evidence["error_code"], "INVOCATION_CANCELLED")
        self.assertFalse(evidence["completed"])

    async def test_storage_errors_are_not_swallowed_behind_model_errors(self):
        self.model.error = RuntimeError("private-provider-credential")
        self.store.fail_name = "compiler-execution.json"
        with self.assertRaises(OSError):
            await self.invoke()
        self.assertNotIn("compiler_execution", self.store.run["artifacts"])
        self.assertNotIn("private-provider-credential", json.dumps(self.store.events))

    async def test_raw_storage_failure_blocks_and_cannot_report_completed(self):
        self.store.fail_name = "compiler-raw.json"
        with self.assertRaises(OSError):
            await self.invoke()
        self.assertFalse(self.evidence()["completed"])
        self.assertEqual(self.evidence()["error_code"], "PERSISTENCE_FAILED")

    async def test_profile_or_model_route_drift_is_refused(self):
        self.model.result["provider"] = "openai"
        await self.assert_code("MODEL_ROUTE_MISMATCH")
        self.assertFalse(self.evidence()["completed"])

    async def test_raw_capture_is_bounded_and_original_hash_remains_visible(self):
        self.model.result["text"] = "text exceeding output boundary"
        original = self.model.result["text"].encode()
        with patch("jiuwenswarm.research.runner.MAX_RAW_BYTES", 8):
            await self.assert_code("OUTPUT_LIMIT_EXCEEDED")
        self.assertEqual(self.store.files["compiler-raw.json"], original[:8])
        self.assertTrue(self.evidence()["raw_truncated"])
        self.assertEqual(self.evidence()["raw_original_size"], len(original))
        self.assertEqual(self.evidence()["raw_original_hash"], digest(original))

    async def test_elapsed_budget_includes_after_call_binding_validation(self):
        # A zero-cost scripted response cannot bypass time spent verifying the
        # implementation and persisting its returned output.
        clock_values = iter((0.0, 0.5, 1.5))
        clock = SimpleNamespace(monotonic=lambda: next(clock_values))
        with patch("jiuwenswarm.research.runner.time", clock):
            await self.assert_code("TIME_BUDGET_EXCEEDED")
        self.assertFalse(self.evidence()["completed"])
        self.assertEqual(self.evidence()["error_code"], "TIME_BUDGET_EXCEEDED")

    async def test_replay_and_unsupported_limits_cannot_increase_call_count(self):
        await self.invoke()
        await self.assert_code("INVOCATION_REPLAY_FORBIDDEN")
        self.assertEqual(len(self.model.calls), 1)
        for key, value in (("max_calls", 999), ("max_calls_per_cc", 2), ("max_tool_calls", 1), ("automatic_retries", 1)):
            with self.subTest(key=key):
                configuration = copy.deepcopy(self.configuration)
                configuration[key] = value
                await self.assert_code("INVOCATION_LIMIT_INVALID", configuration=configuration)

    async def test_unsupported_or_nonfinite_configuration_blocks_without_call(self):
        for value in (float("nan"), float("inf"), True, 0, 601):
            with self.subTest(value=value):
                configuration = copy.deepcopy(self.configuration)
                configuration["timeout_seconds"] = value
                code = "INVOCATION_INPUT_INVALID" if isinstance(value, float) and not value < float("inf") else "INVOCATION_CONFIGURATION_INVALID"
                await self.assert_code(code, configuration=configuration)
        self.assertFalse(self.model.calls)


if __name__ == "__main__":
    unittest.main()
