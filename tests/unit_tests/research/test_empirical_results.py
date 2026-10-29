"""C002 rows are facts about each actual execution, including failed executions."""
import unittest

from jiuwenswarm.research.science import ScienceError, empirical_row, validate_empirical


class EmpiricalTests(unittest.TestCase):
    def test_all_statuses_and_failure_numbers(self):
        ids = ["latency", "accuracy"]
        measured = empirical_row(1, ids, '{"metrics":{"latency":1,"accuracy":0.8}}', 0)
        partial = empirical_row(2, ids, '{"metrics":{"latency":2}}', 0)
        absent = empirical_row(3, ids, '{"metrics":{"latency":3,"accuracy":1}}', 7)
        self.assertEqual([x["status"] for x in [measured, partial, absent]],
                         ["measured", "partial", "unmeasured"])
        self.assertEqual(partial["unmeasured_metrics"], {"accuracy": "metric_not_emitted"})
        self.assertEqual(absent["metrics"], {})
        self.assertEqual(set(absent["unmeasured_metrics"].values()), {"run_failed"})
        validate_empirical([measured, partial, absent], ids, [1, 2, 3])

    def test_nonfinite_missing_and_terminal_reasons(self):
        row = empirical_row(1, ["x", "y"], '{"metrics":{"x":NaN,"y":2}}', 0)
        self.assertEqual(row["unmeasured_metrics"], {"x": "non_finite_value"})
        for reason in ["timeout", "resource_limit_exceeded"]:
            r = empirical_row(1, ["x"], '{"metrics":{"x":1}}', -9, reason)
            self.assertEqual(r["unmeasured_metrics"], {"x": reason})
        self.assertEqual(empirical_row(1, ["x"], "no metrics", 0)["status"], "unmeasured")

    def test_duplicate_unknown_and_unexecuted_are_rejected(self):
        for text in ['{"metrics":{"x":1,"x":2}}', '{"metrics":{"unknown":1}}',
                     '{"metrics":{"x":1}}\n{"metrics":{"x":2}}']:
            with self.assertRaises(ScienceError):
                empirical_row(1, ["x"], text, 0)
        valid = empirical_row(1, ["x"], '{"metrics":{"x":1}}', 0)
        for rows, receipts in [([valid, valid], [1, 2]), ([valid], [1, 2]), ([valid], [])]:
            with self.assertRaises(ScienceError):
                validate_empirical(rows, ["x"], receipts)


if __name__ == "__main__":
    unittest.main()
