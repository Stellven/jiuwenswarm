import json
import unittest
from benchmarks.harbor_suite.value_poc_evidence import receipt_inventory, response_labels


class ReceiptTests(unittest.TestCase):
    def row(self, ident="score1", job="job1"):
        return json.dumps({"schema": "ai4r-classification-scoring-receipt:1", "id": ident, "job_id": job}).encode()

    def test_missing_is_unknown_not_zero(self):
        self.assertIsNone(receipt_inventory([])["unique_scoring_receipts_observed"])

    def test_duplicate_original_not_double_counted(self):
        result = receipt_inventory([("a", self.row()), ("b", self.row())])
        self.assertEqual(result["unique_scoring_receipts_observed"], 1)
        self.assertEqual(result["original_receipts"][0]["locations"], ["a", "b"])
        self.assertIsNone(result["scientific_runs_complete"])

    def test_conflicting_original_rejected(self):
        with self.assertRaises(ValueError):
            receipt_inventory([("a", self.row()), ("b", self.row(job="job2"))])

    def test_duplicate_job_rejected(self):
        with self.assertRaises(ValueError):
            receipt_inventory([("a", self.row()), ("b", self.row(ident="score2"))])

    def test_arbitrary_accuracy_not_scientific_receipt(self):
        result = receipt_inventory([("untrusted", b'{"accuracy":1,"runs":6}')])
        self.assertIsNone(result["unique_scoring_receipts_observed"])

    def test_honest_halt_never_scientific_completion(self):
        result = response_labels("poc-002", {"valid_completion": True})
        self.assertTrue(result["valid_response"])
        self.assertTrue(result["correct_impossibility_handling"])
        self.assertFalse(result["usable_scientific_completion"])
        self.assertNotIn("valid_completion", result)


if __name__ == "__main__":
    unittest.main()
