"""Offline trace construction, integrity and installed schema validation."""

import copy
import hashlib

import pytest
from jsonschema import Draft202012Validator

from jiuwenswarm.research.contracts import ResearchError, validate
from jiuwenswarm.research.contracts.validators import contract_schema
from jiuwenswarm.research.state import json_bytes
from jiuwenswarm.research.trace_manifest import TRACE_SCHEMA, TraceBuilder, verify_chain


def blob(value):
    return {"sha256": hashlib.sha256(json_bytes(value)).hexdigest()}


def builder():
    return TraceBuilder("invocation:example", blob("contract"), blob("declaration"), blob("profile"))


def seal(value, field):
    value[field] = hashlib.sha256(json_bytes({k: v for k, v in value.items() if k != field})).hexdigest()


def completed():
    trace = builder()
    for kind in ("model_call", "tool_call", "tool_result", "check_run", "artifact_write", "submit"):
        trace.append_event(kind, "host", args_ref=blob({"action": kind}),
                           input_refs=[blob("input")], result_ref=blob("result"),
                           detail={"before_sha256": blob("before")["sha256"],
                                   "after_sha256": blob("after")["sha256"]})
    terminal = {"status": "succeeded", "final_artifact_sha256": blob("artifact")["sha256"]}
    claims = [
        {"output_pointer": "/score", "kind": "evidence", "evidence_event_seqs": [4]},
        {"output_pointer": "/ratio", "kind": "derivation", "evidence_event_seqs": [3],
         "derivation": {"op": "divide", "operands": [
             {**blob({"count": 10}), "pointer": "/count"}, blob(2)]}},
        {"output_pointer": "/unknown", "kind": "unmeasured", "evidence_event_seqs": []},
        {"output_pointer": "", "kind": "unsupported", "evidence_event_seqs": []},
    ]
    return trace, trace.finalize(terminal, claims)


def test_build_and_finalize_are_canonical_and_deterministic():
    trace, manifest = completed()
    assert manifest == completed()[1]
    assert manifest == trace.finalize(manifest["terminal"], manifest["claims"])
    assert verify_chain(manifest) == []
    assert [event["seq"] for event in manifest["events"]] == list(range(1, 7))
    assert manifest["events"][0]["prev_event_sha256"] is None
    assert manifest["events"][1]["prev_event_sha256"] == manifest["events"][0]["event_sha256"]
    reordered_keys = dict(reversed(list(manifest.items())))
    assert json_bytes(manifest) == json_bytes(reordered_keys)
    expected = copy.deepcopy(manifest)
    seal(expected, "manifest_sha256")
    assert expected == manifest


@pytest.mark.parametrize("mutation,expected", [
    ("tamper", "bad_event_digest"),
    ("remove", "seq_gap"),
    ("reorder", "bad_prev_hash"),
    ("after_submit", "event_after_terminal"),
    ("manifest_digest", "bad_manifest_digest"),
])
def test_chain_detects_corruption(mutation, expected):
    _, manifest = completed()
    if mutation == "tamper":
        manifest["events"][0]["producer"] = "different-host"
    elif mutation == "remove":
        del manifest["events"][2]
    elif mutation == "reorder":
        manifest["events"][1:3] = reversed(manifest["events"][1:3])
    elif mutation == "after_submit":
        event = copy.deepcopy(manifest["events"][0])
        event.update(seq=7, prev_event_sha256=manifest["events"][-1]["event_sha256"])
        seal(event, "event_sha256")
        manifest["events"].append(event)
    else:
        manifest["manifest_sha256"] = "0" * 64
    # Re-sealing the envelope must not hide broken event integrity or order.
    if mutation != "manifest_digest":
        seal(manifest, "manifest_sha256")
    assert any(failure.startswith(expected) for failure in verify_chain(manifest))


def test_tampered_last_event_and_removed_last_event_break_envelope_digest():
    for mutation in ("tamper_last", "remove_last"):
        _, manifest = completed()
        if mutation == "tamper_last":
            manifest["events"][-1]["producer"] = "changed"
        else:
            manifest["events"].pop()
        assert "bad_manifest_digest" in verify_chain(manifest)


def test_schema_is_discovered_and_accepts_good_manifest():
    Draft202012Validator.check_schema(contract_schema(TRACE_SCHEMA))
    validate(TRACE_SCHEMA, completed()[1])


@pytest.mark.parametrize("path,value", [
    (("unexpected",), True),
    (("contract_ref", "sha256"), "not-a-digest"),
    (("declaration_ref", "payload"), "inline"),
    (("events", 0, "kind"), "unknown"),
    (("events", 0, "args_ref"), {"payload": "inline"}),
    (("events", 0, "input_refs"), ["inline"]),
    (("events", 0, "detail"), {"payload": {"nested": "content"}}),
    (("events", 0, "detail"), {"payload": "x" * 257}),
    (("events", 0, "seq"), 0),
    (("events", 0, "producer"), ""),
    (("terminal", "final_artifact_sha256"), "invalid"),
    (("claims", 0, "kind"), "verified"),
    (("claims", 0, "output_pointer"), "/bad~escape"),
    (("claims", 0, "evidence_event_seqs"), [0]),
    (("claims", 1, "derivation", "operands"), [{"value": 5}]),
    (("manifest_sha256",), "invalid"),
])
def test_repo_validator_rejects_bad_manifests(path, value):
    _, manifest = completed()
    target = manifest
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    with pytest.raises(ResearchError):
        validate(TRACE_SCHEMA, manifest)


def test_builder_copies_inputs_and_outputs_and_enforces_terminal():
    trace = builder()
    inputs = [blob("input")]
    detail = {"name": "original"}
    event = trace.append_event("tool_call", "host", input_refs=inputs, detail=detail)
    inputs.clear()
    detail["name"] = "changed"
    event["producer"] = "changed"
    claims = []
    terminal = {"status": "failed", "final_artifact_sha256": None}
    manifest = trace.finalize(terminal, claims)
    terminal["status"] = "changed"
    claims.append({})
    assert manifest["events"][0]["input_refs"] == [blob("input")]
    assert manifest["events"][0]["detail"] == {"name": "original"}
    assert manifest["events"][0]["producer"] == "host"
    original = copy.deepcopy(manifest)
    manifest["events"].clear()
    assert trace.finalize(original["terminal"], original["claims"]) == original
    with pytest.raises(ResearchError, match="trace_terminal"):
        trace.append_event("tool_result", "host")
    with pytest.raises(ResearchError, match="trace_terminal"):
        trace.finalize(terminal, [])
    trace = builder()
    trace.append_event("submit", "host")
    with pytest.raises(ResearchError, match="trace_terminal"):
        trace.append_event("tool_call", "host")


def test_invalid_append_or_finalize_does_not_poison_builder():
    trace = builder()
    with pytest.raises(ResearchError):
        trace.append_event("tool_call", "host", args_ref={"payload": "inline"})
    assert trace.append_event("check_run", "host")["seq"] == 1
    terminal = {"status": "failed", "final_artifact_sha256": None}
    with pytest.raises(ResearchError, match="trace_claim"):
        trace.finalize(terminal, [{"output_pointer": "", "kind": "evidence", "evidence_event_seqs": [2]}])
    assert verify_chain(trace.finalize(terminal, [])) == []


@pytest.mark.parametrize("value", [None, [], {}, {"events": [None]}, {"events": "invalid"}])
def test_verifier_reports_malformed_input(value):
    assert verify_chain(value)
