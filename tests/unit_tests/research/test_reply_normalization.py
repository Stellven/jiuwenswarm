"""Deterministic, meaning-preserving reply cleanup (24-run census, 2026-10-29).

Live run pl4a: a reviewer FAILed a non-blocking criterion and added a
correction; the advancing review was rejected and the run halted.
"""
import pytest

from jiuwenswarm.research.capsules.evaluation import fill_recomputed
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.gate import assemble_assessment, normalize_reply, strip_json_fence

REFS = [{"id": str(n), "sha256": str(n) * 64} for n in range(1, 4)]
CRITERIA = [{"criterion_id": "shape", "blocking": True}, {"criterion_id": "specific", "blocking": False}]


def _reply(specific="FAIL", correction="Make scores[1] specific."):
    return {"findings": [{"criterion_id": "shape", "outcome": "PASS", "reason": "ok"},
                         {"criterion_id": "specific", "outcome": specific, "reason": "scores[1] is generic"}],
            "uncertainties": [], "limitations": [], "required_correction": correction}


def test_non_blocking_correction_is_kept_as_a_limitation_and_the_review_advances():
    with pytest.raises(ResearchError, match="verdict_follows_findings"):
        assemble_assessment(_reply(), CRITERIA, *REFS)
    record = assemble_assessment(normalize_reply(_reply(), CRITERIA), CRITERIA, *REFS)
    assert record["verdict"] == "PASS_WITH_KNOWN_LIMITATIONS" and record["required_correction"] is None
    assert record["limitations"] == ["Non-blocking correction: Make scores[1] specific."]


def test_blocking_failure_keeps_its_correction_and_halts():
    reply = _reply()
    reply["findings"][0]["outcome"] = "FAIL"
    record = assemble_assessment(normalize_reply(reply, CRITERIA), CRITERIA, *REFS)
    assert record["verdict"] == "FAIL" and record["required_correction"] == "Make scores[1] specific."


def test_blank_strings_casing_and_spacing_are_normalized():
    reply = _reply(specific=" pass ", correction="  ")
    reply["findings"][1]["criterion_id"] = " specific "
    reply["limitations"] = ["", "kept"]
    record = assemble_assessment(normalize_reply(reply, CRITERIA), CRITERIA, *REFS)
    assert record["verdict"] == "PASS_WITH_KNOWN_LIMITATIONS" and record["limitations"] == ["kept"]


def test_one_outer_reviewer_fence_is_stripped_and_inner_text_kept():
    assert strip_json_fence('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_json_fence('{"a": "```"}') == '{"a": "```"}'


def _blueprint():
    rule = {"metric_id": "accuracy", "success": {"operand": "treatment", "comparator": "gt", "reference": "baseline", "factor": 1.0, "offset": 0.0},
            "falsification": {"operand": "treatment", "comparator": "le", "reference": "baseline", "factor": 1.0, "offset": 0.0},
            "middle": "INCONCLUSIVE", "conditional_rule": None, "conditional_meaning": None}
    return {"metrics": [{"metric_id": "accuracy"}], "outcome_rules": [rule]}


def test_evaluation_carrier_recomputes_owned_fields_and_keeps_judgment():
    payload = {"metrics": [{"metric_id": "accuracy", "baseline": {"value": 0.5}, "treatment": {"value": 0.7}}]}
    verdict = {"findings": [{"metric_id": "accuracy", "classification": "INCONCLUSIVE", "rule_applied": "middle",
                             "rule_text": "x", "baseline_value": 0.1, "treatment_value": 0.2, "threshold": 9.0,
                             "rationale": "Treatment beat\nbaseline.  "}],
               "classification": "INCONCLUSIVE", "aggregation_rule": "other",
               "completeness": {"status": "incomplete", "notes": []}, "plausibility": {"status": "plausible", "notes": []},
               "blockers": [], "residual_risks": [], "followups": []}
    filled = fill_recomputed(verdict, _blueprint(), payload)
    assert filled is not verdict
    finding = filled["findings"][0]
    assert (finding["baseline_value"], finding["treatment_value"]) == (0.5, 0.7)
    assert finding["classification"] == "PASS" and finding["rule_applied"] == "success"
    assert finding["rationale"] == "Treatment beat baseline."
    assert filled["classification"] == "PASS" and filled["completeness"]["status"] == "complete"
    assert filled["aggregation_rule"] == "m1_conjunctive_v1"


def test_evaluation_carrier_leaves_misaligned_findings_for_the_checks():
    payload = {"metrics": [{"metric_id": "accuracy", "baseline": {"value": 0.5}, "treatment": {"value": 0.7}}]}
    verdict = {"findings": [], "plausibility": {"status": "plausible", "notes": []}, "completeness": {"status": "complete", "notes": []}}
    assert fill_recomputed(verdict, _blueprint(), payload) is verdict
