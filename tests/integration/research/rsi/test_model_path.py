"""Actual model/session and private paired measurements; no substituted execution."""
import json
import os

import pytest


def test_real_bounded_session(public_session):
    records, session, result = public_session()
    assert os.geteuid() == 12001, "BLOCKED: workbench-owned real native context required"
    assert result["attempts_used"] > 0 and result["queries_used"] > 0
    assert result["attempts_used"] <= session["limits"]["max_attempts"]
    assert result["queries_used"] <= session["limits"]["session_query_limit"]
    calls = [row["record"] for row in records if row["kind"] == "model-call"]
    assert any(call["observed_runtime"] and call["outcome"] == "completed" for call in calls)
    assert any(row["kind"] == "native-governed-trace" for row in records), "Actual native call-owned original trace required"
    assert result["outcome"] in {"QUALIFIED", "NO_IMPROVEMENT", "UNEVALUATED_CANDIDATE", "INCONCLUSIVE", "ERROR", "CANCELLED", "SECURITY_HALTED"}
    assert not result.get("activated", False)


@pytest.mark.parametrize("body_path,export_variable", [
    ("screening_prompt.txt", "AI4R_RSI_PROMPT_FROZEN_EXPORT"),
    ("screening_rubric.json", "AI4R_RSI_RUBRIC_FROZEN_EXPORT"),
])
def test_conditional_target2(public_session, isolated_capture, body_path, export_variable):
    from jiuwenswarm.research.contracts import validate
    from jiuwenswarm.research.measurement_slots import parse_slot
    records, session, result = public_session(export_variable)
    capture = isolated_capture
    target = capture.get(session["target_profile_ref"])
    assert body_path in target["mutable_paths"] and session["pass_count_repeats"] == 3
    children = []
    for pin, measured in capture.records("isolated-evaluation-result"):
        if measured["session_ref"] != result["session_ref"]:
            continue
        trial = capture.get(measured["trial_ref"])
        binding = capture.get(trial["binding_ref"])
        assert binding["schema"] == "ai4r-isolated-evaluation-binding:2"
        assert binding["target_ref"] == session["target_profile_ref"]
        assert measured["accepted"] is False and measured["status"] == "completed"
        parent = capture.get(binding["parent_declaration_ref"])
        child = capture.get(binding["child_declaration_ref"])
        old = {row["path"]: row["sha256"] for row in parent["identity"]["body"]}
        new = {row["path"]: row["sha256"] for row in child["identity"]["body"]}
        assert set(old) == set(new)
        assert [name for name in old if old[name] != new[name]] == [body_path]
        assert all(child[field] == parent[field] for field in
                   ("ports", "needs", "budget", "changes", "guarantees", "coverage", "evolution"))
        assert [port["name"] for port in binding["inputs"]] == ["brief", "candidate_set"]
        reservation = capture.get(binding["reservation_ref"])
        assert reservation["schema"] == "ai4r-rsi-trial-reservation:3"
        slot = parse_slot(reservation, binding, target, session)
        assert measured["mandatory_tests_passed"] and measured["deterministic_result_ref"]
        checked = capture.get(measured["deterministic_result_ref"])
        validate("deterministic-check-result", checked)
        assert measured["assessment_refs"] and measured["observation_refs"] and measured["trace_refs"]
        assert any(capture.get(ref)["observed_runtime"] for ref in measured["trace_refs"] if "observed_runtime" in capture.get(ref))
        children.append((binding, reservation, slot))
    assert children, "BLOCKED: no actual changed-child Screening measurements for this authorized body"
    parents = []
    for pin, measured in capture.records("admitted-parent-result"):
        if measured["session_ref"] != result["session_ref"]:
            continue
        binding = capture.get(measured["binding_ref"])
        assert binding["schema"] == "ai4r-admitted-measurement-binding:2"
        assert measured["accepted"] is False and measured["status"] == "completed"
        raw = capture.get(measured["measurement_ref"])
        assert raw["accepted"] is False and raw["contract_ref"] == measured["contract_ref"]
        contract = capture.get(measured["contract_ref"])
        assert contract["bindings"][0]["declaration_ref"] == binding["parent_declaration_ref"]
        reservation = capture.get(binding["reservation_ref"])
        slot = parse_slot(reservation, binding, target, session)
        parents.append((binding, reservation, slot))
    assert parents, "BLOCKED: original admitted parent measurement is absent; an identical child is not a baseline"
    for child, charge, slot in children:
        matches = [(parent, reservation) for parent, reservation, parent_slot in parents
            if parent_slot == slot and parent["phase"] == child["phase"]
            and parent["repeat_index"] == child["repeat_index"] and parent["inputs"] == child["inputs"]
            and all(parent[key] == child[key] for key in ("session_ref", "target_ref", "parent_declaration_ref", "configuration_ref", "model_selection_profile_ref", "deployment_ref"))
            and reservation["action_id"] == charge["action_id"]]
        assert len(matches) == 1, "Exact same-charge parent/child input/repeat/slot match is absent or ambiguous"
    assert capture.db.execute("SELECT count(*) FROM acceptance").fetchone()[0] == 0
    child_ids = {binding["child_declaration_ref"]["id"] for binding, _, _ in children}
    for _, entry in capture.records("library-admission"):
        assert entry.get("declaration_ref", {}).get("id") not in child_ids
    for row in capture.db.execute("SELECT declaration_ref FROM library_versions"):
        assert json.loads(row[0])["id"] not in child_ids
