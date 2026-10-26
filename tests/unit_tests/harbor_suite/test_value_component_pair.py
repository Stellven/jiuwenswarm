import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmarks.harbor_suite import value_component_pair as subject
from benchmarks.harbor_suite.contracts import canonical


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


class ComponentPairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bank, self.cc, self.native = [self.root / name for name in ("bank", "cc", "native")]
        self.cases = [{"id": "one", "task_sha256": hashlib.sha256(canonical({"id": "one"})).hexdigest(), "oracle": {"expected_verdict": "safe"}},
                      {"id": "two", "task_sha256": hashlib.sha256(canonical({"id": "two"})).hexdigest(), "oracle": {"expected_verdict": "unsafe"}}]
        self.responses = [{"id": "one", "verdict": "safe", "reason": "Checked original source"},
                          {"id": "two", "verdict": "unsafe", "reason": "Exact scalar types differ"}]
        put(self.bank / "manifest.json", {"cases": self.cases})
        batch = {"cases": [{"id": row["id"]} for row in self.cases]}
        put(self.bank / "public/batch.json", batch)
        put(self.native / "project/batch.json", batch)
        put(self.native / "project/response.json", {"results": self.responses})
        put(self.native / "result.json", {"status": "completed", "model_calls": 8})
        rows = []
        for case, response in zip(self.cases, self.responses):
            row = {"id": case["id"], "task_sha256": case["task_sha256"], "status": "observed", "model_calls": 0,
                   "checks": [{"check_id": "integrity", "outcome": "PASS"}], "response": response}
            put(self.cc / (case["id"] + ".json"), row)
            rows.append(row)
        put(self.cc / "summary.json", {"model_calls": 0, "rows": rows})

    def tearDown(self):
        self.temp.cleanup()

    def collect(self, helper=None):
        with patch("benchmarks.harbor_suite.value_verification_cases.load", return_value=self.cases), \
                patch.object(subject, "native_evidence", return_value=({"model_calls": 8,
                    "usage": {"input_tokens": 20, "output_tokens": 4}, "model_and_effort_verified": True}, [])):
            return subject.collect_verification(self.root / "dataset", self.bank, self.cc,
                self.native, self.root / "broker", "frozen-image", helper_receipt=helper)["value"]

    def test_batch_cost_is_not_divided_into_independent_case_trials(self):
        value = self.collect()
        self.assertEqual(value["correct_decisions"], {"cc": 2, "native": 2})
        self.assertEqual(value["batch_cost"]["native_model_calls"], 8)
        self.assertEqual(value["population"]["independent_native_trials"], 1)
        self.assertEqual(value["population"]["artifact_decisions"], 2)
        self.assertTrue(all(row["per_case_call_allocation"] is None for row in value["rows"]))
        self.assertIsNone(value["ordinary_helper_control"]["correct"])

    def test_missing_duplicate_and_unexpected_ids_remain_unavailable_not_fake_failures(self):
        put(self.native / "project/response.json", {"results": [self.responses[0], self.responses[0],
            {"id": "unexpected", "verdict": "safe", "reason": "unrelated"}]})
        value = self.collect()
        self.assertEqual(value["alignment"]["missing_ids"], ["two"])
        self.assertEqual(value["alignment"]["duplicate_ids"], ["one"])
        self.assertEqual(value["alignment"]["unexpected_ids"], ["unexpected"])
        self.assertTrue(all(row["native"]["correct"] is None and not row["native"]["available"] for row in value["rows"]))

    def test_altered_batch_is_rejected_before_grading(self):
        put(self.native / "project/batch.json", {"cases": []})
        with self.assertRaisesRegex(ValueError, "batch differs"):
            self.collect()

    def test_original_helper_receipt_is_regraded_and_hash_matched(self):
        helper_path = self.bank / "public/native_skill/verify_helper.py"
        helper_path.parent.mkdir(parents=True)
        helper_path.write_text("# ordinary source", encoding="utf-8")
        receipt = self.root / "helper.json"
        put(receipt, {"schema": "ai4r-value-ordinary-helper-receipt:1", "model_calls": 0, "returncode": 0,
            "batch_sha256": hashlib.sha256((self.bank / "public/batch.json").read_bytes()).hexdigest(),
            "helper_sha256": hashlib.sha256(helper_path.read_bytes()).hexdigest(),
            "correct": 2, "decisions": 2, "stdout": json.dumps({"results": self.responses})})
        value = self.collect(receipt)
        self.assertEqual(value["ordinary_helper_control"]["correct"], 2)
        self.assertEqual(value["ordinary_helper_control"]["model_calls"], 0)

    def test_planning_preserves_json_boolean_type_and_full_original_check_rows(self):
        ident = "planning-01"
        packet = {"source": "public planning fixture"}
        put(self.bank / "public" / ident / "candidate.json", packet)
        put(self.native / "project" / ident / "candidate.json", packet)
        put(self.bank / "private/manifest.json", {"cases": [{"case_id": ident,
            "public_sha256": hashlib.sha256(canonical(packet)).hexdigest()}]})
        expected = {"reject": False, "failed_checks": []}
        checks = [{"check_id": "acyclicity", "outcome": "PASS"}]
        put(self.bank / "private" / (ident + ".expected.json"), expected)
        put(self.bank / "private" / (ident + ".production.json"), {
            "measurement": "production_plan_checks_component", "answer": expected, "all_original_results": checks})
        # Integer zero must not pass merely because Python says 0 == False.
        put(self.native / "project/response.json", {"results": [{"id": ident, "reject": 0, "failed_checks": []}]})
        with patch.object(subject, "native_evidence", return_value=({"model_calls": 8,
                "usage": {}, "model_and_effort_verified": True}, [])):
            value = subject.collect_planning(self.root / "planning-dataset", self.bank, self.native,
                self.root / "broker", "frozen-image")["value"]
        self.assertTrue(value["rows"][0]["cc"]["correct"])
        self.assertEqual(value["rows"][0]["cc"]["checks"], checks)
        self.assertFalse(value["rows"][0]["native"]["correct"])


if __name__ == "__main__":
    unittest.main()
