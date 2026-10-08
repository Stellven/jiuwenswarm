"""Real host/store/gate connections with independently specified endpoint fixtures."""
import asyncio
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from jiuwenswarm.ai4research.intent.models import FrozenPolicy, InvocationEvidence, sha256_text
from jiuwenswarm.ai4research.intent.prompts import compiler_prompt, verifier_prompt
from jiuwenswarm.ai4research.intent.service import IntentService
from jiuwenswarm.ai4research.intent.store import IntentStore, StoreError

TEXT = "Compare the supplied baseline with method B on dataset D. Do not use network. Prefer lower latency."


def faithful_candidate(text, run_id):
    def claim(value):
        return {"text": value, "source_quote": value}
    return {"schema_version": "1", "run_id": run_id, "input_sha256": sha256_text(text),
            "lane": "scientific_research", "objective": claim(text.split(". ")[0] + "."),
            "in_scope": [claim("dataset D")], "out_of_scope": [],
            "mandatory_requirements": [claim("Do not use network.")], "preferences": [claim("Prefer lower latency.")],
            "constraints": [claim("Do not use network.")], "targets": [], "evidence_obligations": [],
            "ambiguities": [], "defaults": {"lane": "scientific_research", "scope": "unspecified", "resources": "unspecified"}}


class FixtureBridge:
    def __init__(self, *, mutate=None, semantic_status="PASS", delay=0, warnings=None, error=False, tools=None):
        self.calls = []
        self.candidate = None
        self.mutate = mutate
        self.semantic_status = semantic_status
        self.delay = delay
        self.warnings = warnings or []
        self.error = error
        self.tools = tools or []
        self.on_call = None
        self.verifier_release = None

    async def invoke(self, role, prompt, run_id, policy):
        self.calls.append(role)
        if self.on_call:
            self.on_call(role, run_id)
        if role == "verifier" and self.verifier_release is not None:
            await self.verifier_release.wait()
        if self.error:
            raise RuntimeError("private credential-looking exception must not reach product")
        if self.delay:
            await asyncio.sleep(self.delay)
        if role == "compiler":
            candidate = faithful_candidate(TEXT, run_id)
            if self.mutate:
                self.mutate(candidate)
            raw = json.dumps(candidate, ensure_ascii=False)
            self.candidate = raw
        else:
            # Independent expected output for the fixed fixture: exact fidelity,
            # scope, prohibition and optional preference all survive.
            raw = json.dumps({"schema_version": "1", "run_id": run_id, "input_sha256": sha256_text(TEXT),
                              "candidate_sha256": sha256_text(self.candidate),
                              "checks": [{"obligation_id": key, "status": self.semantic_status,
                                          "reason": "The supplied baseline, data, network prohibition and preference are preserved.",
                                          "evidence": [{"source": "input", "quote": TEXT},
                                                       {"source": "candidate", "quote": self.candidate}]}
                                         for key in ("fidelity", "omissions", "additions", "constraints", "scope", "ambiguity")],
                              "limitations": self.warnings}, ensure_ascii=False)
        return InvocationEvidence(invocation_id=uuid.uuid4().hex, role=role, run_id=run_id,
                                  conversation_id=uuid.uuid4().hex, prompt_sha256=sha256_text(prompt),
                                  status="completed", elapsed_seconds=0.0, raw_output=raw, tools=self.tools,
                                  effects=[], usage=None)


class IntentServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = IntentStore(Path(self.directory.name))

    def service(self, bridge=None, policy=None):
        return IntentService(self.store, bridge or FixtureBridge(), policy)

    async def execute(self, service):
        return await service.execute(TEXT, "owner", "profile", "workspace")

    async def test_connected_acceptance_exact_evidence_and_restart(self):
        bridge = FixtureBridge()
        service = self.service(bridge)
        captured = []
        bridge.on_call = lambda role, run_id: captured.append((role, self.store.read(run_id, "owner")["state"]))
        result = await self.execute(service)
        self.assertEqual(result["state"], "ACCEPTED")
        self.assertEqual(bridge.calls, ["compiler", "verifier"])
        self.assertEqual(captured, [("compiler", "COMPILING"), ("verifier", "VERIFYING")])
        path = self.store.artifact_root / result["run_id"]
        self.assertEqual((path / "original.txt").read_text(), TEXT)
        self.assertEqual((path / "candidate.raw.json").read_text(), bridge.candidate)
        self.assertTrue((path / "assessment.raw.json").exists())
        self.assertTrue((path / "decision.json").exists())
        reopened = IntentService(IntentStore(Path(self.directory.name)), FixtureBridge())
        self.assertEqual(reopened.get(result["run_id"], "owner")["accepted_reference"], result["accepted_reference"])
        with self.assertRaises(StoreError):
            reopened.get(result["run_id"], "other-owner")

    async def test_invalid_schema_skips_semantic_verifier(self):
        bridge = FixtureBridge(mutate=lambda candidate: candidate.update(extra="producer claims pass"))
        result = await self.execute(self.service(bridge))
        self.assertEqual(result["state"], "HALTED")
        self.assertIsNone(result["accepted_reference"])
        self.assertEqual(bridge.calls, ["compiler"])

    async def test_semantic_deficiency_cannot_advance(self):
        for status in ("FAIL", "INCONCLUSIVE"):
            result = await self.execute(self.service(FixtureBridge(semantic_status=status)))
            self.assertEqual(result["verdict"], status)
            self.assertIsNone(result["accepted_reference"])

    async def test_material_ambiguity_blocks_without_dialogue(self):
        bridge = FixtureBridge(mutate=lambda candidate: candidate.update(ambiguities=["Which supplied dataset is authorized?"]))
        result = await self.execute(self.service(bridge))
        self.assertEqual(result["verdict"], "INCONCLUSIVE")
        self.assertEqual(bridge.calls, ["compiler"])

    async def test_nonblocking_warning_preserved_after_mandatory_pass(self):
        result = await self.execute(self.service(FixtureBridge(warnings=["Optional latency preference lacks a numeric target."])))
        self.assertEqual(result["verdict"], "PASS_WITH_KNOWN_LIMITATIONS")
        self.assertIsNotNone(result["accepted_reference"])
        self.assertEqual(len(result["warnings"]), 1)

    async def test_no_reference_while_independent_decision_pending(self):
        bridge = FixtureBridge()
        started = asyncio.Event()
        bridge.verifier_release = asyncio.Event()
        bridge.on_call = lambda role, run_id: started.set() if role == "verifier" else None
        service = self.service(bridge)
        run_id = await service.submit(TEXT, "owner", "profile", "workspace")
        task = service.tasks[run_id]
        await asyncio.wait_for(started.wait(), 2)
        pending = service.get(run_id, "owner")
        self.assertEqual(pending["state"], "VERIFYING")
        self.assertIsNone(pending["accepted_reference"])
        bridge.verifier_release.set()
        await task
        self.assertEqual(service.get(run_id, "owner")["state"], "ACCEPTED")

    async def test_timeout_is_durable_and_never_retried(self):
        bridge = FixtureBridge(delay=0.05)
        result = await self.execute(self.service(bridge, FrozenPolicy(per_call_seconds=0.01)))
        self.assertEqual(result["state"], "HALTED")
        self.assertIn("TIME_BUDGET_EXCEEDED", result["reasons"])
        self.assertEqual(bridge.calls, ["compiler"])
        self.assertTrue(result["durable"])

    async def test_call_limit_and_unavailable_token_meter_block(self):
        for policy in (FrozenPolicy(max_calls=1), FrozenPolicy(max_tokens=100)):
            bridge = FixtureBridge()
            result = await self.execute(self.service(bridge, policy))
            self.assertEqual(result["state"], "HALTED")
            self.assertEqual(bridge.calls, ["compiler"])
            self.assertIsNone(result["accepted_reference"])

    async def test_cancel_before_and_during_call_preserves_halt(self):
        for start_call in (False, True):
            service = self.service(FixtureBridge(delay=1))
            run_id = await service.submit(TEXT, "owner", "profile", "workspace")
            if start_call:
                await asyncio.sleep(0.01)
            result = await service.cancel(run_id, "owner")
            self.assertEqual(result["state"], "HALTED")
            self.assertIn("CANCELLED", result["reasons"])
            self.assertIsNone(result["accepted_reference"])

    async def test_storage_failure_never_exposes_model_pass(self):
        service = self.service()
        with patch.object(self.store, "complete", side_effect=OSError("fixture storage failure")):
            result = await self.execute(service)
        self.assertFalse(result["durable"])
        self.assertIsNone(result["accepted_reference"])
        self.assertEqual(result["verdict"], "ENVIRONMENT_BLOCKED")

    async def test_changed_or_missing_required_evidence_revokes_reference_visibility(self):
        for delete in (False, True):
            service = self.service()
            result = await self.execute(service)
            original = self.store.artifact_root / result["run_id"] / "original.txt"
            if delete:
                original.unlink()
            else:
                original.write_text("swapped input")
            observed = service.get(result["run_id"], "owner")
            self.assertIsNone(observed["accepted_reference"])
            self.assertIn("EVIDENCE_INTEGRITY_FAILED", observed["reasons"])

    async def test_environment_failure_durable_and_sensitive_error_suppressed(self):
        result = await self.execute(self.service(FixtureBridge(error=True)))
        self.assertEqual(result["verdict"], "ENVIRONMENT_BLOCKED")
        self.assertTrue(result["durable"])
        self.assertNotIn("private credential", json.dumps(result))

    async def test_prohibited_effect_stops_before_verifier(self):
        bridge = FixtureBridge(tools=["shell"])
        result = await self.execute(self.service(bridge))
        self.assertEqual(result["state"], "HALTED")
        self.assertEqual(bridge.calls, ["compiler"])

    async def test_restart_pauses_uncertain_work_and_correction_is_new_run(self):
        service = self.service()
        run_id = service._capture(TEXT, "owner", "profile", "workspace", None)
        # Simulate restart recovery under exclusive process ownership.
        lock = self.store.claim_runtime()
        self.store.recover_interrupted()
        lock.close()
        restarted = self.service()
        self.assertEqual(restarted.get(run_id, "owner")["state"], "PAUSED")
        corrected = await restarted.execute(TEXT, "owner", "profile", "workspace", run_id)
        self.assertNotEqual(corrected["run_id"], run_id)
        self.assertEqual(corrected["corrects_run_id"], run_id)
        self.assertEqual(restarted.get(run_id, "owner")["state"], "PAUSED")

    async def test_empty_and_overlarge_rejected_before_call(self):
        bridge = FixtureBridge()
        service = self.service(bridge)
        for text in ("  ", "é" * 32769):
            with self.assertRaises(ValueError):
                await service.execute(text, "owner", "profile", "workspace")
        self.assertEqual(bridge.calls, [])

    async def test_another_service_cannot_pause_active_owner(self):
        service = self.service(FixtureBridge(delay=1))
        run_id = await service.submit(TEXT, "owner", "profile", "workspace")
        await asyncio.sleep(0)
        second = self.service()
        with self.assertRaisesRegex(StoreError, "RUNTIME_BUSY"):
            await second.submit(TEXT, "owner", "profile", "workspace")
        self.assertNotEqual(service.get(run_id, "owner")["state"], "PAUSED")
        await service.cancel(run_id, "owner")

    async def test_policy_is_frozen_before_task_entry(self):
        service = self.service()
        run_id = await service.submit(TEXT, "owner", "profile", "workspace")
        task = service.tasks[run_id]
        service.policy = FrozenPolicy(max_calls=1)
        await task
        self.assertEqual(service.get(run_id, "owner")["state"], "ACCEPTED")


if __name__ == "__main__":
    unittest.main()
