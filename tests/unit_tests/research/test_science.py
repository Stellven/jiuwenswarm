"""Literal scientific oracles; deliberately independent of production arithmetic."""
import math
import unittest

from jiuwenswarm.research.science import (
    ScienceError, aggregate, classify_metric, overall_classification,
    validate_rule_regions, metric_payload,
)


def rule(op, value, reference="constant"):
    return {"operand": "treatment", "comparator": op, "reference": reference,
            "factor": value if reference == "baseline" else 0,
            "offset": value if reference == "constant" else 0}


class ScienceTests(unittest.TestCase):
    def test_independent_aggregates(self):
        for name, expected in [("min", 1), ("max", 10), ("mean", 5), ("median", 4.5)]:
            self.assertEqual(aggregate([1, 2, 7, 10], name), expected)
        self.assertEqual(aggregate([1, 3, 9], "median"), 3)
        for value in [[], [math.nan], [math.inf], [True]]:
            with self.assertRaises(ScienceError):
                aggregate(value, "mean")

    def test_regions_and_registered_conditional(self):
        source = {"metric_id": "mae", "success": rule("le", 1),
                  "falsification": rule("ge", 2), "middle": "CONDITIONALLY_ACCEPTABLE",
                  "conditional_rule": rule("eq", 1.5), "conditional_meaning": "bounded improvement"}
        validate_rule_regions(source, "lower_better")
        for value, expected in [(0, ("PASS", "success", 1)), (4, ("FAIL", "falsification", 2)),
                                (1.5, ("CONDITIONALLY_ACCEPTABLE", "conditional", 1.5)),
                                (1.7, ("INCONCLUSIVE", "middle", None))]:
            self.assertEqual(classify_metric(2, value, source), expected)
        self.assertEqual(classify_metric(2, None, source), ("INCONCLUSIVE", "unmeasured", None))
        broken = dict(source, falsification=rule("ge", 1))
        with self.assertRaises(ScienceError):
            validate_rule_regions(broken, "lower_better")
        validate_rule_regions(dict(source, falsification=rule("gt", 1),
                                   middle="INCONCLUSIVE", conditional_rule=None,
                                   conditional_meaning=None), "lower_better")

    def test_baseline_and_actual_overlap(self):
        r = {"success": rule("le", .5, "baseline"), "falsification": rule("ge", 1, "baseline"),
             "middle": "INCONCLUSIVE", "conditional_rule": None, "conditional_meaning": None}
        validate_rule_regions(r, "lower_better")
        self.assertEqual(classify_metric(2, 0, r), ("PASS", "success", 1))
        with self.assertRaises(ScienceError):
            classify_metric(0, 0, r)

    def test_precedence_and_missing_metric(self):
        self.assertEqual(overall_classification(["FAIL", "INCONCLUSIVE"], "plausible"), "FAIL")
        self.assertEqual(overall_classification(["FAIL"], "implausible"), "INCONCLUSIVE")
        self.assertEqual(overall_classification(["FAIL"], "not_assessable"), "FAIL")
        self.assertEqual(overall_classification(["PASS", "CONDITIONALLY_ACCEPTABLE"], "plausible"),
                         "CONDITIONALLY_ACCEPTABLE")

    def test_payload_incomplete_and_range(self):
        m = {"metric_id": "mae", "unit": "error", "aggregation": "mean", "valid_min": 0, "valid_max": None}
        result = metric_payload(m, [2, 2, 2], [0, 0, 0], 3)
        self.assertEqual(result["delta"], -2)
        partial = metric_payload(m, [2, 2, 2], [0], 3, treatment_reason="timeout")
        self.assertIsNone(partial["treatment"]["value"])
        self.assertEqual(partial["treatment"]["repeats"], [0])
        self.assertIsNone(partial["delta"])
        with self.assertRaises(ScienceError):
            metric_payload(m, [-1, 0, 0], [0, 0, 0], 3)


if __name__ == "__main__":
    unittest.main()
