"""B03/V02: independent architecture fixtures and adversarial boundaries.

All source examples are synthetic representation fixtures. These tests do not
assert configured-model availability, semantic accuracy or durable acceptance.
"""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from intent_compiler.checks import (
    CONTRACTS, check_assessment, check_brief, check_gate, check_intent,
    validate_field_contract, validate_schema,
)

FIXTURES = Path(__file__).with_name("fixtures") / "contracts"


def load(name):
    return json.loads((FIXTURES / name).read_bytes())


def ref(name):
    return {"id": name, "sha256": hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()}


def intent_check(payload):
    name = payload["request_ref"]["id"]
    text = (FIXTURES / name).read_bytes().decode("utf-8")
    return check_intent(payload, {name: text}, ref(name), [])


def brief_check(payload, resources=None, sources=None):
    original = load("Research_Brief_Defaults.json")
    return check_brief(payload, original["intake_ref"], original["intent_ref"], sources or {
        "Request_Permissible_Omissions.txt": (FIXTURES / "Request_Permissible_Omissions.txt").read_bytes().decode("utf-8"),
    }, resources or [], ref("Default_Policy.json"), load("Default_Policy.json"))


@pytest.mark.parametrize("name,file", [
    ("intent-ir", "Intent_IR.json"),
    ("intent-ir", "Intent_Topic_Only.json"),
    ("intent-ir", "Intent_Contradictory.json"),
    ("research-brief", "Research_Brief.json"),
    ("research-brief", "Research_Brief_Defaults.json"),
    ("deterministic-check-result", "Intent_Checks.json"),
    ("verifier-assessment", "Intent_Assessment.json"),
    ("gate-decision", "Gate_Decision.json"),
    ("gate-decision", "Gate_Intention_Compiler_Pass.json"),
    ("gate-decision", "Gate_Compiler_No_Output.json"),
    ("capsule-declaration", "Capsule_Declaration.json"),
    ("subnode-execution-contract", "Intention_Subnode_Contract.json"),
])
def test_supplied_current_schema_examples(name, file):
    assert validate_schema(name, load(file)) == []


def test_contract_bytes_match_registered_source_receipt():
    receipt = json.loads((CONTRACTS / "provenance.json").read_bytes())
    assert receipt["interface_revisions"] == ["M0-IF-001@r1", "M0-IF-002@r1", "M0-IF-003@r1"]
    assert len([x for x in receipt["files"] if x["path"].endswith(".schema.json")]) == 8
    for item in receipt["files"]:
        assert hashlib.sha256((CONTRACTS / item["path"]).read_bytes()).hexdigest() == item["sha256"]


@pytest.mark.parametrize("mutation", ["missing", "version", "control", "extension", "enum", "hash", "not_object"])
def test_schema_rejects_incompatible_or_control_bearing_intent(mutation):
    payload = load("Intent_IR.json")
    if mutation == "missing":
        del payload["interpretation"]
    elif mutation == "version":
        payload["schema_version"] = "2.0.0"
    elif mutation == "control":
        payload["workflow_action"] = "advance"
    elif mutation == "extension":
        payload["ext"] = {"unqualified": True}
    elif mutation == "enum":
        payload["readiness"]["status"] = "auto_advance"
    elif mutation == "hash":
        payload["request_ref"]["sha256"] = "not-a-digest"
    else:
        payload = []
    assert validate_schema("intent-ir", payload)


@pytest.mark.parametrize("name", ["Intent_IR.json", "Intent_Topic_Only.json", "Intent_Contradictory.json"])
def test_valid_candidates_include_unusable_and_conflicting_meaning(name):
    assert intent_check(load(name)) == []


@pytest.mark.parametrize("mutation", ["duplicate_id", "empty_span", "past_end", "stale_span", "foreign_context", "wrong_request"])
def test_intent_exact_source_relationships(mutation):
    payload = load("Intent_IR.json")
    statement = payload["interpretation"]["problem"]
    span = statement["source_spans"][0]
    if mutation == "duplicate_id":
        payload["interpretation"]["requested_result"]["id"] = statement["id"]
    elif mutation == "empty_span":
        span["end"] = span["start"]
    elif mutation == "past_end":
        span["end"] = 100000
    elif mutation == "stale_span":
        span["source_ref"]["sha256"] = "0" * 64
    elif mutation == "foreign_context":
        payload["context_refs"] = [ref("Default_Policy.json")]
    else:
        payload["request_ref"]["sha256"] = "0" * 64
    assert intent_check(payload)


def test_unicode_crlf_spans_use_original_codepoints_and_allow_distinct_original_ref():
    text = (FIXTURES / "CRLF_Source.txt").read_bytes().decode("utf-8")
    assert "\r\n" in text
    illustration = load("Source_Spans_CRLF.json")
    assert [text[s["start"]:s["end"]] for s in illustration["source_spans"]] == illustration["expected_text"]
    payload = load("Intent_IR.json")
    original_ref = {"id": "request-with-bom.txt", "sha256": hashlib.sha256(b"\xef\xbb\xbf" + text.encode()).hexdigest()}
    payload["request_ref"] = original_ref
    for value in payload["interpretation"].values():
        if value is not None:
            value["source_spans"] = [{"source_ref": original_ref, "start": 3, "end": 4}]
    for name in ("context", "in_scope", "out_of_scope", "constraints", "preferences", "user_targets", "uncertainties"):
        payload[name] = []
    assert check_intent(payload, {original_ref["id"]: {"text": text, "ref": original_ref}}, original_ref, []) == []


def test_authorized_default_and_scalar_field_pointer():
    payload = load("Research_Brief_Defaults.json")
    assert brief_check(payload) == []
    payload["assumptions"][0]["affected_fields"] = ["/constraints/0/normalized_value"]
    assert brief_check(payload) == []


@pytest.mark.parametrize("mutation", ["duplicate_id", "unknown_requirement", "missing_coverage", "stale_intent",
    "missing_assumption", "invented_pointer", "unattributed_pointer", "unsupported_default", "purpose_default",
    "blocking", "nonfinite", "numeric_without_unit", "qualitative_with_value", "default_confirmation"])
def test_brief_rejects_unresolved_obligations_and_defaults(mutation):
    payload = load("Research_Brief_Defaults.json")
    if mutation == "duplicate_id":
        payload["deliverables"][0]["id"] = payload["objective"]["id"]
    elif mutation == "unknown_requirement":
        payload["evidence_obligations"][0]["requirement_ids"] = ["unknown"]
    elif mutation == "missing_coverage":
        row = copy.deepcopy(payload["mandatory_requirements"][0]); row["id"] = "requirement:uncovered"
        payload["mandatory_requirements"].append(row)
    elif mutation == "stale_intent":
        payload["intent_ref"]["sha256"] = "0" * 64
    elif mutation == "missing_assumption":
        payload["assumptions"] = []
    elif mutation == "invented_pointer":
        payload["assumptions"][0]["affected_fields"] = ["/future_protocol/repeat_count"]
    elif mutation == "unattributed_pointer":
        payload["assumptions"][0]["affected_fields"] = ["/objective/text"]
    elif mutation == "unsupported_default":
        payload["constraints"][0]["normalized_value"] = "cloud_cluster"
    elif mutation == "purpose_default":
        payload["objective"]["origin"] = "system_default"
    elif mutation == "blocking":
        payload["unresolved_items"] = load("Intent_Contradictory.json")["uncertainties"]
    elif mutation == "nonfinite":
        payload["constraints"][0].update(operator="le", normalized_value=float("nan"), unit="seconds")
    elif mutation == "numeric_without_unit":
        payload["constraints"][0].update(operator="le", normalized_value=1, unit=None)
    elif mutation == "qualitative_with_value":
        payload["constraints"][0].update(operator="qualitative", normalized_value=1, unit=None)
    else:
        payload["confirmation"]["basis"] = "user_request"
    assert brief_check(payload)


def test_resource_inventory_and_named_binding_are_exact():
    payload = load("Research_Brief_Defaults.json")
    resource = {"id": "Resource.json", "sha256": "1" * 64}
    payload["resource_refs"] = [resource]
    payload["input_bindings"] = [{"id": "input:1", "role": "validation_data", "resource_ref": resource}]
    assert brief_check(payload, [resource]) == []
    payload["input_bindings"] = []
    assert brief_check(payload, [resource])


def assessment_check(payload):
    original = load("Intent_Assessment.json")
    criteria = [row["criterion_id"] for row in original["findings"]]
    refs = [ref for row in original["findings"] for ref in row["evidence_refs"]]
    return check_assessment(payload, original["subject_ref"], original["review_context_ref"], criteria, refs)


def test_valid_nonadvancing_assessment_is_data():
    payload = load("Intent_Assessment.json")
    assert assessment_check(payload) == []
    payload["verdict"] = "FAIL"
    payload["findings"][0]["outcome"] = "FAIL"
    payload["required_correction"] = "Resolve the identified fidelity error."
    assert assessment_check(payload) == []


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "wrong_subject", "wrong_context", "foreign_evidence",
                                      "failed_finding", "uncertainty", "correction", "action", "replacement"])
def test_assessment_exact_assignment_and_evidence(mutation):
    payload = load("Intent_Assessment.json")
    if mutation == "missing":
        payload["findings"].pop()
    elif mutation == "duplicate":
        payload["findings"].append(copy.deepcopy(payload["findings"][0]))
    elif mutation == "wrong_subject":
        payload["subject_ref"]["sha256"] = "0" * 64
    elif mutation == "wrong_context":
        payload["review_context_ref"]["sha256"] = "0" * 64
    elif mutation == "foreign_evidence":
        payload["findings"][0]["evidence_refs"] = [ref("Default_Policy.json")]
    elif mutation == "failed_finding":
        payload["findings"][0]["outcome"] = "FAIL"
    elif mutation == "uncertainty":
        payload["uncertainties"] = ["Purpose unavailable"]
    elif mutation == "correction":
        payload["required_correction"] = "Rewrite objective"
    elif mutation == "action":
        payload["action"] = "advance"
    else:
        payload["replacement_artifact"] = {}
    assert assessment_check(payload)


@pytest.mark.parametrize("name", ["Gate_Decision.json", "Gate_Intention_Compiler_Pass.json", "Gate_Compiler_No_Output.json"])
def test_gate_current_scope_and_no_output_halt(name):
    assert check_gate(load(name)) == []


@pytest.mark.parametrize("mutation", ["fail_advance", "no_assessment", "wrong_parent", "missing_internal", "duplicate_internal", "unreviewed"])
def test_gate_cannot_publish_invalid_local_acceptance(mutation):
    payload = load("Gate_Intention_Compiler_Pass.json")
    if mutation == "fail_advance":
        payload["verdict"] = "FAIL"
    elif mutation == "no_assessment":
        payload["assessment_ref"] = None
    elif mutation == "wrong_parent":
        payload["contract_ref"] = ref("Intent_IR.json")
    elif mutation == "missing_internal":
        payload["internal_decision_refs"].pop()
    elif mutation == "duplicate_internal":
        payload["internal_decision_refs"] = [payload["internal_decision_refs"][0]] * 2
    else:
        payload["accepted_refs"] = [ref("Intent_IR.json")]
    assert check_gate(payload)


def readiness():
    return {"schema_version": "1.0.0", "id": "readiness:1", "client_contract_version": "1.0.0",
        "instance_id": "instance:1", "build_id": "build:1", "operations": ["submit", "status", "retrieve"],
        "prerequisites": [{"name": "model", "status": "unavailable", "reason": "No configured endpoint"}],
        "ready": False, "ext": {"intent_compiler.profiles": ["compiler-only"]}}


def test_field_contract_preserves_unavailable_readiness_and_closed_core():
    payload = readiness()
    assert validate_field_contract("client-readiness", payload) == []
    payload["ready"] = True
    # The field validator establishes representation, not runtime prerequisite truth.
    assert validate_field_contract("client-readiness:field-contract:1", payload) == []
    payload["invented_core_field"] = True
    assert validate_field_contract("client-readiness", payload)


@pytest.mark.parametrize("mutation", ["missing", "wrong_version", "bool_integer", "bad_extension", "bad_hash"])
def test_field_contract_nested_types_and_versions(mutation):
    payload = {"schema_version": "1.0.0", "id": "status:1", "client_request_id": "request:1", "run_id": None,
        "revision": 1, "stage": "intake", "status": "halted", "candidate_refs": [], "accepted_refs": [],
        "decision_ref": None, "reasons": ["Unavailable endpoint"], "bundle_ref": None}
    assert validate_field_contract("client-status", payload) == []
    if mutation == "missing":
        del payload["candidate_refs"]
    elif mutation == "wrong_version":
        payload["schema_version"] = "2.0.0"
    elif mutation == "bool_integer":
        payload["revision"] = True
    elif mutation == "bad_extension":
        payload["ext"] = {"ordinary": 1}
    else:
        payload["decision_ref"] = {"id": "gate", "sha256": "bad"}
    assert validate_field_contract("client-status", payload)
