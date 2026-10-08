"""Offline authentication-custody integration fixtures, never a real provider.

The fixture labels its protocol replies openai only to exercise the codex route
checks. It starts no native bridge, uses no credentials and proves no connected
model trial or semantic model reliability.
"""
from __future__ import annotations

import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jiuwenswarm.research.contracts import CHECK_IDS, ResearchError, digest
from jiuwenswarm.research.service import ResearchService


SESSION = "offline-auth-session"
AUTH_A = "a" * 64
AUTH_B = "b" * 64
REQUEST = "Study faithful extraction without external actions."


class FakeCodexProvider:
    """Scripted native-protocol shape, with no native process or network access."""

    def __init__(self, *, missing_hash=False, change_before_execute=False,
                 change_after_compiler=False):
        self.missing_hash = missing_hash
        self.change_before_execute = change_before_execute
        self.change_after_compiler = change_after_compiler
        self.current_hash = AUTH_A
        self.readiness_calls = 0
        self.calls = []
        self.closed = False

    async def readiness(self):
        self.readiness_calls += 1
        if self.change_before_execute and self.readiness_calls >= 2:
            self.current_hash = AUTH_B
        result = {"ready": True, "security": True, "code": "READY",
                  "provider": "openai", "model_control": "configured"}
        if not self.missing_hash:
            result["auth_context_hash"] = self.current_hash
        return result

    async def complete(self, *, role, instructions, payload, model, timeout_seconds):
        self.calls.append({"role": role, "payload": copy.deepcopy(payload)})
        context_hash = self.current_hash
        request = payload["request"]
        if role == "compiler":
            output = {"schema_version": "intent.v1", "request_hash": payload["request_hash"],
                      "objective": [{"text": request, "quote": request, "start": 0, "end": len(request)}],
                      "desired_outcome": [], "scope": [], "constraints": [],
                      "omissions": ["desired_outcome", "scope", "constraints"], "conflicts": []}
            if self.change_after_compiler:
                self.current_hash = AUTH_B
        else:
            output = {"schema_version": "intent-assessment.v1", "subject": copy.deepcopy(payload["subject"]),
                      "checks": [{"id": ident, "status": "PASS", "reason": "Scripted offline custody fixture",
                                  "evidence": [{"source": "request", "quote": request}]} for ident in CHECK_IDS]}
        return {"text": json.dumps(output), "provider": "openai", "model": model,
                "duration_ms": 0, "usage": None, "tool_calls": [],
                "thread_id": "offline-fixture-" + role, "auth_context_hash": context_hash}

    async def close(self):
        self.closed = True


class AuthContextIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="offline-auth-integration-")
        self.root = Path(self.temporary.name)
        self.services = []
        self.serial = 0

    async def asyncTearDown(self):
        for service in self.services:
            await service.close()
        self.temporary.cleanup()

    def service(self, model):
        self.serial += 1
        # Guard the default profile path as well as explicitly selecting a
        # temporary product identity. Tests must not read a personal profile.
        with patch.object(ResearchService, "_identity", side_effect=AssertionError("Personal identity access is forbidden")):
            service = ResearchService(self.root / ("case-" + str(self.serial)), model=model,
                                      profile="codex", timeout_seconds=5.0,
                                      product_user_id="offline-auth-user-" + str(self.serial),
                                      workspace_id="offline-auth-workspace-" + str(self.serial))
        self.services.append(service)
        return service

    async def run_to_terminal(self, service, request_id):
        created = await service.submit(REQUEST, request_id, SESSION, mode="headless")
        task = service.tasks.get(created["run_id"])
        if task is not None:
            await asyncio.wait_for(asyncio.shield(task), 10)
        run = service.get(created["run_id"], SESSION)
        self.assertIn(run["status"], {"ACCEPTED", "HALTED", "PAUSED", "CANCELLED"})
        return run

    def assert_environment_blocked(self, run, code):
        self.assertEqual(run["status"], "HALTED")
        self.assertEqual(run["verdict"], "ENVIRONMENT_BLOCKED")
        self.assertEqual(run["reason"], code)
        self.assertIsNone(run["accepted_ref"])
        self.assertIsNone(run["accepted_intent"])
        self.assertFalse(run["decision"]["mandatory_obligations_passed"])

    @staticmethod
    def execution(service, run, role):
        return json.loads(service.store.read_artifact(run["artifacts"][role + "_execution"]))

    async def test_ready_codex_reply_without_identity_hash_is_blocked_before_any_call(self):
        model = FakeCodexProvider(missing_hash=True)
        service = self.service(model)
        run = await self.run_to_terminal(service, "missing-auth-hash")
        self.assert_environment_blocked(run, "ACCOUNT_IDENTITY_UNAVAILABLE")
        self.assertEqual(model.calls, [])
        self.assertEqual(model.readiness_calls, 1)
        self.assertIsNone(run["configuration"]["auth_context_hash"])
        self.assertFalse(run["configuration"]["model_readiness_at_start"]["ready"])
        self.assertTrue(all(attempt["status"] == "NOT_RUN" for attempt in run["attempts"]))

    async def test_auth_change_after_freeze_and_before_execute_prevents_compiler_call(self):
        model = FakeCodexProvider(change_before_execute=True)
        service = self.service(model)
        run = await self.run_to_terminal(service, "change-before-compiler")
        self.assert_environment_blocked(run, "MODEL_ACCOUNT_CHANGED")
        self.assertEqual(model.calls, [])
        self.assertEqual(model.readiness_calls, 2)
        self.assertEqual(run["configuration"]["auth_context_hash"], AUTH_A)
        self.assertTrue(run["configuration"]["model_readiness_at_start"]["ready"])
        self.assertEqual(run["contract"]["configuration_hash"], digest(run["configuration"]))

    async def test_auth_change_between_compiler_and_verifier_cannot_release(self):
        model = FakeCodexProvider(change_after_compiler=True)
        service = self.service(model)
        run = await self.run_to_terminal(service, "change-before-verifier")
        self.assert_environment_blocked(run, "MODEL_ACCOUNT_CHANGED")
        self.assertEqual([call["role"] for call in model.calls], ["compiler", "verifier"])
        self.assertEqual(run["configuration"]["auth_context_hash"], AUTH_A)
        compiler = self.execution(service, run, "compiler")
        verifier = self.execution(service, run, "verifier")
        self.assertTrue(compiler["completed"])
        self.assertTrue(compiler["auth_context_verified"])
        self.assertEqual(compiler["auth_context_hash"], AUTH_A)
        self.assertFalse(verifier["completed"])
        self.assertFalse(verifier["auth_context_verified"])
        self.assertEqual(verifier["auth_context_hash"], AUTH_B)
        self.assertEqual(verifier["auth_context_expected_hash"], AUTH_A)
        self.assertEqual(verifier["error_code"], "MODEL_ACCOUNT_CHANGED")
        self.assertNotIn("assessment", run["artifacts"])
        self.assertIn("verifier_raw", run["artifacts"])

    async def test_same_auth_hash_releases_only_with_matching_persisted_execution_proofs(self):
        model = FakeCodexProvider()
        service = self.service(model)
        run = await self.run_to_terminal(service, "same-auth-context")
        self.assertEqual(run["status"], "ACCEPTED")
        self.assertEqual(run["verdict"], "PASS")
        self.assertIsNotNone(run["accepted_ref"])
        self.assertEqual(run["accepted_intent"]["objective"][0]["quote"], REQUEST)
        self.assertEqual(run["subject"]["auth_context_hash"], AUTH_A)
        self.assertEqual(run["configuration"]["auth_context_hash"], AUTH_A)
        for role in ("compiler", "verifier"):
            execution = self.execution(service, run, role)
            self.assertTrue(execution["completed"])
            self.assertTrue(execution["auth_context_verified"])
            self.assertEqual(execution["auth_context_hash"], AUTH_A)
            self.assertEqual(execution["auth_context_expected_hash"], AUTH_A)
            self.assertEqual(execution["auth_context_control"], "codex_subscription")
        self.assertEqual([call["role"] for call in model.calls], ["compiler", "verifier"])
        persisted_decision = json.loads(service.store.read_artifact(run["decision_ref"]))
        service.store.verify_release(service.store.get(run["run_id"]), persisted_decision, run["accepted_ref"])

    async def test_release_rejects_false_verified_flag_or_expected_identity_mismatch(self):
        service = self.service(FakeCodexProvider())
        accepted = await self.run_to_terminal(service, "proof-auth-guard")
        self.assertEqual(accepted["status"], "ACCEPTED")
        original_execution = self.execution(service, accepted, "compiler")
        for index, alteration in enumerate(({"auth_context_verified": False},
                                           {"auth_context_expected_hash": AUTH_B}), 1):
            with self.subTest(alteration=alteration):
                # Use new, correctly hashed immutable evidence, so this probes
                # the authentication proof instead of a byte-integrity failure.
                probe = service.store.get(accepted["run_id"])
                evidence = dict(original_execution, **alteration)
                replacement = service.store.write_artifact(accepted["run_id"],
                                                           f"probe-compiler-auth-{index}.json", evidence)
                probe["artifacts"]["compiler_execution"] = replacement
                next(attempt for attempt in probe["attempts"] if attempt["role"] == "compiler")["evidence_ref"] = replacement
                with self.assertRaises(ResearchError) as caught:
                    service.store.verify_release(probe, accepted["decision"], accepted["accepted_ref"])
                self.assertEqual(caught.exception.code, "GATE_EXECUTION_INVALID")
        self.assertEqual(service.get(accepted["run_id"], SESSION)["status"], "ACCEPTED")

    async def test_non_string_and_malformed_parent_run_ids_have_stable_intake_error(self):
        model = FakeCodexProvider()
        service = self.service(model)
        malformed = ([], {}, ["a" * 32], {"run_id": "a" * 32}, 123, True,
                     float("nan"), "", "a" * 31, "A" * 32, "../outside")
        for index, parent in enumerate(malformed):
            with self.subTest(index=index):
                with self.assertRaises(ResearchError) as caught:
                    await service.submit(REQUEST, "invalid-parent-" + str(index), SESSION,
                                         mode="headless", options={"parent_run_id": parent})
                self.assertEqual(caught.exception.code, "INVALID_PARENT_RUN")
        self.assertEqual(model.readiness_calls, 0)
        self.assertEqual(model.calls, [])
        self.assertEqual(service.store.list_runs(SESSION), [])


if __name__ == "__main__":
    unittest.main()
