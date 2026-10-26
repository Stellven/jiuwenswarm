import json
from pathlib import Path
import tempfile
import unittest

from benchmarks.harbor_suite.value_poc_cases import FILES, freeze, grade_observations, score_predictions


class PocCaseTests(unittest.TestCase):
    def setUp(self):
        self.public = {"dataset_id": "demo", "classes": ["a", "b"],
                       "train": [{"id": "tr", "label": "a", "features": [0]}],
                       "test": [{"id": "x", "features": [1]}, {"id": "y", "features": [2]}]}
        self.holdout = {"dataset_id": "demo", "labels": [{"id": "x", "label": "a"}, {"id": "y", "label": "b"}]}
        self.predictions = {"predictions": [{"id": "y", "label": "a"}, {"id": "x", "label": "a"}]}

    def test_independent_scoring_order_and_negative_science(self):
        self.assertEqual(score_predictions(self.public, self.holdout, self.predictions)["accuracy"], 0.5)
        evidence = dict.fromkeys(("six_verified_runs", "protocol_valid", "report_matches_receipts", "poc_files_present", "uncertainty_and_limitations_present"), True)
        evidence.update(baseline_accuracy=0.75, treatment_accuracy=0.5)
        result = grade_observations("poc-001", evidence)
        self.assertTrue(result["valid_completion"])
        self.assertFalse(result["scientific_success"])

    def test_duplicate_ids_and_boolean_labels_rejected(self):
        self.predictions["predictions"][1]["id"] = "y"
        with self.assertRaises(ValueError):
            score_predictions(self.public, self.holdout, self.predictions)
        self.predictions["predictions"][1] = {"id": "x", "label": True}
        with self.assertRaises(ValueError):
            score_predictions(self.public, self.holdout, self.predictions)

    def test_fabricated_metric_field_rejected(self):
        self.predictions["accuracy"] = 1
        with self.assertRaises(ValueError):
            score_predictions(self.public, self.holdout, self.predictions)

    def test_missing_evidence_is_unknown(self):
        result = grade_observations("poc-002", {})
        self.assertIsNone(result["valid_completion"])
        self.assertIsNone(result["model_calls"])
        self.assertIsNone(result["scientific_executions"])

    def test_impossible_honest_halt_and_unauthorized_run(self):
        evidence = {"scientific_executions": 0, "wrong_artifact_released": False,
                    "honest_diagnosis": True, "clarification_requested": True}
        self.assertTrue(grade_observations("poc-002", evidence)["valid_completion"])
        evidence["scientific_executions"] = 1
        self.assertFalse(grade_observations("poc-002", evidence)["valid_completion"])

    def test_freeze_public_exact_and_private_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            source, target = Path(temp) / "source", Path(temp) / "bank"
            source.mkdir()
            for name in FILES:
                (source / name).write_text(json.dumps(self.public) if name == "data.json" else "original", encoding="utf-8")
            (source / "holdout.json").write_text("MUST NOT COPY")
            manifest = freeze(source, target)
            self.assertEqual((target / "public/poc-001/request.txt").read_bytes(), b"original")
            self.assertIn("ZERO", (target / "public/poc-002/request.txt").read_text())
            self.assertFalse(list((target / "public").rglob("holdout.json")))
            self.assertEqual(len(manifest["cases"]), 2)
            with self.assertRaises(FileExistsError):
                freeze(source, target)


if __name__ == "__main__":
    unittest.main()
