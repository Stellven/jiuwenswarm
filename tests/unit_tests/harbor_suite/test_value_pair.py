import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from benchmarks.harbor_suite import value_pair as subject
from benchmarks.harbor_suite.contracts import canonical
from jiuwenswarm.research.unified_planning import integrated_plan_policy


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


class PairCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bank, self.product, self.native, self.broker = [self.root / name for name in ("bank", "product", "native", "broker")]
        self.case_id = "test-paper"
        self.pdf, self.text = b"%PDF-original-fixture", "canonical source"
        pdf_path = self.bank / self.case_id / "test-paper.pdf"
        pdf_path.parent.mkdir(parents=True)
        pdf_path.write_bytes(self.pdf)
        self.case = {"task_sha256": "a" * 64, "task": {"id": self.case_id,
            "response_schema": {"type": "object"},
            "documents": [{"path": "test-paper.pdf", "text": self.text, "canonical_text_filename": "canonical.txt"}]}}
        policy = integrated_plan_policy()
        plan = {"policy_ref": {"id": "blob:policy", "sha256": hashlib.sha256(canonical(policy)).hexdigest()},
                "limits": {"model_calls": 4, "time_s": 480}}
        self.original = canonical({"answer": "actual produced answer"})
        ref = {"id": "blob:actual", "sha256": hashlib.sha256(self.original).hexdigest()}
        self.archive = self.product / "artifacts/originals.zip"
        self.archive.parent.mkdir(parents=True)
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr("artifacts/actual-output", self.original)
            archive.writestr("paper_summary.json", canonical({"answer": "unlinked fixture must not be selected"}))
            archive.writestr("contracts/run-plan-" + "0" * 64 + ".json", canonical(plan))
            archive.writestr("sources/document_001.txt", self.text.encode())
        self.record = {"task": "same public request", "app_run_id": "run:actual", "execution_state": "completed",
            "limits": {"deadline_s": 600}, "inputs": [{"path": "test-paper.pdf", "sha256": hashlib.sha256(self.pdf).hexdigest(),
                "upload_record": {"text_sha256": hashlib.sha256(self.text.encode()).hexdigest()}}]}
        put(self.product / "run_record.json", self.record)
        put(self.native / "assignment.json", {"task": "same public request", "variant": "native-skills", "max_model_calls": 80, "wall_time_s": 600})
        put(self.native / "result.json", {"status": "completed", "model_calls": 1, "variant": "native-skills"})
        put(self.native / "skill-inventory.json", {"selected": ["ordinary-skill"]})
        (self.native / "project").mkdir()
        put(self.native / "project/task.json", self.case["task"])
        put(self.native / "project/output-schema.json", self.case["task"]["response_schema"])
        (self.native / "project/test-paper.pdf").write_bytes(self.pdf)
        (self.native / "project/canonical.txt").write_text(self.text, encoding="utf-8")
        (self.native / "project/paper_summary.json").write_bytes(self.original)
        ident = "f" * 32
        packet = {"messages": [{"role": "user", "content": "same public request"}], "tools": []}
        response = {"request_id": ident, "status": "completed", "identity": {"effective": "gpt-6.1-sol"},
                    "reasoning_effort": "medium", "usage": {"input_tokens": 10, "output_tokens": 2}}
        put(self.native / "evidence/completion-001-request.json", packet)
        put(self.native / "evidence/completion-001-response.json", response)
        put(self.broker / (ident + ".request.json"), {"request_id": ident, "model": "gpt-6.1-sol", "reasoning_effort": "medium",
            "prompt": "wire instructions\n" + json.dumps(packet)})
        put(self.broker / (ident + ".response.json"), response)
        self.audit = {"all_model_calls_joined": True, "missing_output_refs": [], "archive_sha256": "e" * 64,
            "model_calls": 2, "call_functions": {"worker": 1, "verifier": 1},
            "usage": {"input_tokens": {"total": 20}, "output_tokens": {"total": 4}},
            "original_model_calls": [{"id": "call:worker"}, {"id": "call:verifier"}],
            "invocations": [{"cc_name": "research.paper_summary", "outcome": "success",
                "output_refs": [{"ref": ref, "archive_paths": ["artifacts/actual-output"]}]}]}
        self.projection = {"comparison_eligible": True, "expected_call_ids": ["call:worker", "call:verifier"]}

    def tearDown(self):
        self.temp.cleanup()

    def collect(self):
        with patch.object(subject, "load_pdf_cases", return_value=[self.case]), \
                patch.object(subject, "request_text", return_value="same public request"), \
                patch.object(subject, "audit_archive", return_value=self.audit), \
                patch.object(subject, "product_identity", return_value=self.projection), \
                patch.object(subject, "grade", side_effect=lambda case, answer: {"content_correct": answer["answer"] == "actual produced answer"}):
            return subject.collect_pair(self.root / "dataset", self.bank, self.case_id,
                                        self.product, self.native, self.broker, "frozen-image")

    def test_collects_producing_invocation_bytes_full_pipeline_cost_and_equal_caps(self):
        record = self.collect()
        value = record["value"]
        self.assertEqual(record["kind"], "native_cc_pair")
        self.assertTrue(value["comparison_eligible"])
        self.assertTrue(value["arms"]["cc"]["correct"])
        self.assertEqual(value["arms"]["cc"]["model_calls"], 2)
        self.assertEqual(value["arms"]["native-skills"]["model_calls"], 1)
        self.assertEqual(value["content_delta_cc_minus_native"], 0)
        self.assertEqual(value["caps"]["model_calls_per_arm"], 80)
        self.assertIsNone(value["arms"]["native-skills"]["controller_elapsed_s"])
        self.assertIsNone(value["arms"]["cc"]["cost_usd"])

    def test_luna_evidence_requires_explicit_same_model_pin(self):
        ident = "f" * 32
        submitted_path = self.broker / (ident + ".request.json")
        submitted = json.loads(submitted_path.read_text())
        put(submitted_path, {**submitted, "model": "gpt-6-luna"})
        for path in (self.broker / (ident + ".response.json"), self.native / "evidence/completion-001-response.json"):
            value = json.loads(path.read_text())
            put(path, {**value, "identity": {"effective": "gpt-6-luna"}})
        with self.assertRaises(ValueError):
            subject.native_evidence(self.native, self.broker)
        evidence, _ = subject.native_evidence(self.native, self.broker, expected_model="gpt-6-luna")
        self.assertTrue(evidence["model_and_effort_verified"])
        self.assertEqual(evidence["model_calls"], 1)

    def test_mismatched_request_and_canonical_sources_are_rejected(self):
        path = self.native / "assignment.json"
        original = json.loads(path.read_text())
        put(path, {**original, "task": "different public request"})
        with self.assertRaisesRegex(ValueError, "request differs"):
            self.collect()
        put(path, original)
        (self.native / "project/canonical.txt").write_text("altered", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "byte identity"):
            self.collect()

    def test_native_broker_tamper_and_unmatched_caps_are_rejected(self):
        path = self.broker / ("f" * 32 + ".response.json")
        original = json.loads(path.read_text())
        put(path, {**original, "reasoning_effort": "high"})
        with self.assertRaisesRegex(ValueError, "join exactly"):
            self.collect()
        put(path, original)
        assignment = self.native / "assignment.json"
        put(assignment, {**json.loads(assignment.read_text()), "max_model_calls": 12})
        with self.assertRaisesRegex(ValueError, "caps do not match"):
            self.collect()


if __name__ == "__main__":
    unittest.main()
