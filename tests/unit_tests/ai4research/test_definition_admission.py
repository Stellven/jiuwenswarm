"""Receipt-validation fixtures; these do not admit any real model package."""
import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.ai4research.admission import validate_admission_receipt
from jiuwenswarm.ai4research.common import GovernanceError, canonical_json, sha256_bytes


def receipt_fixture(root):
    pins = {role: SimpleNamespace(decl_hash=letter * 64) for role, letter in (("compiler", "a"), ("verifier", "b"))}
    hashes = {role: pin.decl_hash for role, pin in pins.items()}
    required = ["fixture.test_m0_003::declaration", "fixture.test_intent_compiler::contract", "fixture.test_m0_007::profile"]
    report = b'<testsuites><testsuite tests="3"><testcase classname="fixture.test_m0_003" name="declaration"/><testcase classname="fixture.test_intent_compiler" name="contract"/><testcase classname="fixture.test_m0_007" name="profile"/></testsuite></testsuites>'
    review = {"schema_revision": "definition-review-r2", "pins": hashes,
              "source": "independently scoped code and source assessment", "result": "PASS",
              "limitations": ["Explicit receipt-validation fixtures; no actual package admission."],
              "observations": [{"obligation": key, "result": "PASS", "reason": "Fixture receipt parser assertion."}
                               for key in ("two_cc_scope", "closure_and_provenance", "typed_contracts", "protected_fidelity_rubric", "upstream_adaptation", "no_gate_authority")]}
    (root / "checks.xml").write_bytes(report)
    (root / "review.json").write_bytes(canonical_json(review))
    def reference(name):
        return {"path": name, "sha256": sha256_bytes((root / name).read_bytes())}
    receipt = {"schema_revision": "definition-admission-r2", "scope": "provisional-definition-eligibility; not connected trial acceptance",
               "pins": hashes, "checks": {"junit": reference("checks.xml"), "required_cases": required},
               "independent_review": reference("review.json")}
    path = root / "receipt.json"
    path.write_bytes(canonical_json(receipt))
    return path, pins, receipt, reference


def test_definition_receipt_requires_observed_cases_and_review_exact_pins(tmp_path):
    path, pins, _, _ = receipt_fixture(tmp_path)
    result = validate_admission_receipt(path, pins)
    assert result["ready"] and result["observed_cases"] == 3
    assert "not connected trial acceptance" in result["scope"]
    assert len(result["evidence_refs"]) == 3
    pins["compiler"].decl_hash = "c" * 64
    with pytest.raises(GovernanceError) as error:
        validate_admission_receipt(path, pins)
    assert error.value.code == "admission_evidence_stale"


@pytest.mark.parametrize("tag", ["failure", "error", "skipped"])
def test_definition_receipt_failed_or_skipped_checks_are_never_eligible(tmp_path, tag):
    path, pins, receipt, reference = receipt_fixture(tmp_path)
    raw = (tmp_path / "checks.xml").read_bytes().replace(b'name="declaration"/>', f'name="declaration"><{tag}/></testcase>'.encode())
    (tmp_path / "checks.xml").write_bytes(raw)
    receipt["checks"]["junit"] = reference("checks.xml")
    path.write_bytes(canonical_json(receipt))
    with pytest.raises(GovernanceError) as error:
        validate_admission_receipt(path, pins)
    assert error.value.code == "admission_checks_failed"


@pytest.mark.parametrize("mutation", ["missing_case", "missing_review", "review_failure", "changed_evidence", "empty_report"])
def test_definition_receipt_incomplete_or_changed_evidence_refuses(tmp_path, mutation):
    path, pins, receipt, reference = receipt_fixture(tmp_path)
    if mutation == "missing_case":
        receipt["checks"]["required_cases"].append("fixture::not_observed")
    elif mutation == "missing_review":
        (tmp_path / "review.json").unlink()
    elif mutation == "review_failure":
        review = json.loads((tmp_path / "review.json").read_bytes())
        review["observations"][0]["result"] = "FAIL"
        (tmp_path / "review.json").write_bytes(canonical_json(review))
        receipt["independent_review"] = reference("review.json")
    elif mutation == "changed_evidence":
        (tmp_path / "checks.xml").write_bytes(b"changed")
    else:
        (tmp_path / "checks.xml").write_bytes(b"<testsuites/>")
        receipt["checks"]["junit"] = reference("checks.xml")
    path.write_bytes(canonical_json(receipt))
    with pytest.raises(GovernanceError):
        validate_admission_receipt(path, pins)


def test_definition_receipt_missing_never_synthesizes_review():
    with pytest.raises(GovernanceError) as error:
        validate_admission_receipt(None, {})
    assert error.value.code == "admission_evidence_missing"
