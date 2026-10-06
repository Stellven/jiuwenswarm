"""Exact host aggregation, frozen upstream identity and no averaging bypass."""
import json
from pathlib import Path

import pytest

from jiuwenswarm.ai4research.common import GovernanceError, canonical_json, hash_json
from jiuwenswarm.ai4research.service import validate_adaptation
from jiuwenswarm.ai4research.verification.gate import aggregate

SUBJECT = {"sha256": "a" * 64}
ORIGINAL = {"sha256": "b" * 64}
CONTRACT = {"responsibility": "faithful Intent"}
PROFILE = "c" * 64


def assessment():
    return {"schema_revision": "assessment-r2", "subject_sha256": SUBJECT["sha256"],
        "source_sha256": ORIGINAL["sha256"], "contract_sha256": hash_json(CONTRACT), "profile_sha256": PROFILE,
        "findings": [{"check_id": f"F{i}", "status": "PASS", "reason": "Supported by original obligation and locked extraction.",
                      "evidence_refs": ["original", "candidate"]} for i in range(1, 7)], "limitations": []}


def apply(value):
    return aggregate(canonical_json(value), subject_ref=SUBJECT, original_ref=ORIGINAL,
                     contract=CONTRACT, profile_sha256=PROFILE,
                     deterministic=[{"check_id": "D1", "status": "PASS", "reason": "Exact schema and evidence."}], evidence_refs=[SUBJECT])


def test_m0_007_b01_host_policy_advances_only_all_mandatory_findings():
    assert apply(assessment())["verdict"] == "PASS"
    for status, expected in (("FAIL", "FAIL"), ("INCONCLUSIVE", "INCONCLUSIVE")):
        value = assessment()
        value["findings"][0]["status"] = status
        value["limitations"] = ["All other findings look good."]
        decision = apply(value)
        assert decision["verdict"] == expected
        assert not decision["mandatory_pass"]


@pytest.mark.parametrize("field", ["subject_sha256", "source_sha256", "contract_sha256", "profile_sha256"])
def test_m0_007_b04_rejects_stale_swapped_profile_and_contract(field):
    value = assessment()
    value[field] = "d" * 64
    with pytest.raises(GovernanceError, match="stale, swapped"):
        apply(value)


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(verdict="PASS"),
    lambda x: x["findings"].pop(),
    lambda x: x["findings"][0].update(check_id="F2"),
    lambda x: x["findings"][0].update(status="ACCEPT_AND_PROCEED"),
    lambda x: x["findings"][0].update(evidence_refs=[]),
    lambda x: x["findings"][0].update(evidence_refs=["external_unavailable"]),
    lambda x: x["findings"][0].update(reason=" "),
])
def test_m0_007_b05_malformed_assessor_and_embedded_gate_authority_block(mutation):
    value = assessment()
    mutation(value)
    with pytest.raises(GovernanceError):
        apply(value)


def test_m0_007_b06_known_limitation_cannot_override_mandatory_failure():
    value = assessment()
    value["limitations"] = ["Same-provider errors may correlate."]
    assert apply(value)["verdict"] == "PASS_WITH_KNOWN_LIMITATIONS"
    value["findings"][1]["status"] = "FAIL"
    assert apply(value)["verdict"] == "FAIL"


def test_m0_007_b10_applicable_upstream_adaptation_is_pinned_and_scoped():
    adaptation = validate_adaptation()
    assert len(adaptation["upstream_revision"]) == 40
    assert {s["name"] for s in adaptation["sources"]} == {"result-evaluator", "citation-reviewer"}
    assert {check for mapping in adaptation["adopted_checks"] for check in mapping["profile_checks"]} == {f"F{i}" for i in range(1, 7)}
    assert all(mapping["cases"] for mapping in adaptation["adopted_checks"])
    assert "no gate authority" in str(adaptation["inapplicable"])
    assert "Stage 3.8" in str(adaptation["inapplicable"])


def test_m0_007_b11_frozen_labels_cover_required_categories_without_reliability_claim():
    path = Path(__file__).parents[2] / "fixtures/ai4research/intent/characterization/cases.json"
    corpus = json.loads(path.read_bytes())
    assert corpus["repetitions_real"] == 3
    assert len(corpus["semantic_cases"]) == 9
    assert len(corpus["control_cases"]) == 9
    assert "false_acceptance" in corpus["report_fields"]
    assert "no universal reliability" in corpus["acceptance_rule"]
