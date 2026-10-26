import hashlib
import json

from benchmarks.harbor_suite.contracts import canonical
from benchmarks.harbor_suite.value_trace_identity import project_call, project_run


def _ref(ident, raw):
    return {"id": ident, "sha256": hashlib.sha256(raw).hexdigest()}


def _trace(call_id="call-1", *, requested_model="gpt-6.1-sol",
           resolved_model="gpt-6.1-sol", resolved_effort="medium",
           configured_effort=None, terminal="completed", rerouted=False):
    scope = {"run_id": "run-1", "node_id": "summary", "subnode_id": "summary",
        "attempt_id": "summary-a1", "execution_id": "exec-1", "invocation_id": "invoke-1",
        "call_id": call_id, "contract_ref": _ref("contract-1", b"contract"),
        "model_call_start_ref": _ref("start-1", b"start")}
    config = {} if configured_effort is None else {"model_reasoning_effort": configured_effort}
    packets = [
        ("out", "thread/start", {"id": 1, "method": "thread/start", "params": {
            "model": requested_model, "config": config}}),
        ("in", "thread/start", {"id": 1, "result": {"thread": {"id": "thread-1"},
            "model": resolved_model, "reasoningEffort": resolved_effort}}),
        ("out", "turn/start", {"id": 2, "method": "turn/start", "params": {
            "threadId": "thread-1", "model": requested_model}}),
        ("in", "turn/start", {"id": 2, "result": {"turn": {"id": "turn-1", "status": "inProgress"}}}),
    ]
    if rerouted:
        packets.append(("in", "model/rerouted", {"method": "model/rerouted",
            "params": {"threadId": "thread-1"}}))
    packets.append(("in", "turn/completed", {"method": "turn/completed", "params": {
        "threadId": "thread-1", "turn": {"id": "turn-1", "status": terminal}}}))
    events = []
    event_refs = []
    for seq, (direction, method, packet) in enumerate(packets):
        raw = (json.dumps(packet, sort_keys=True, separators=(",", ":")) + "\n").encode()
        raw_ref = _ref("packet-" + str(seq), raw)
        event = {"schema": "ai4r-native-governed-trace-event:1", "scope": scope,
            "sequence": seq, "direction": direction, "method": method, "raw_ref": raw_ref}
        event_ref = _ref("event-" + str(seq), canonical(event))
        event_refs.append(event_ref)
        events.append({"event_ref": event_ref, "event": event, "packet": raw})
    summary = {"schema": "ai4r-native-governed-trace:1", "scope": scope,
        "status": "completed" if terminal == "completed" else "failed", "event_refs": event_refs}
    return {"call_ref": _ref(call_id, canonical({"id": call_id})),
        "summary_ref": _ref("summary-" + call_id, canonical(summary)),
        "summary": summary, "events": events}


def _run_row(trace):
    return {"call_ref": trace["call_ref"], "summary_ref": trace["summary_ref"], "summary": trace["summary"],
            "events": trace["events"]}


def test_one_call_joins_exact_request_and_resolved_model_effort():
    trace = _trace()
    call = project_call(**trace, expected_call_id="call-1")
    assert call["comparison_eligible"] is True
    assert call["effective_model"] == "gpt-6.1-sol"
    assert call["effective_effort"] == "medium"
    assert call["effort_explicitly_pinned"] is False

    run = project_run(expected_call_ids=["call-1"], expected_call_refs=[trace["call_ref"]],
        traces=[_run_row(trace)])
    assert run["comparison_eligible"] is True
    assert run["effective_models"] == ["gpt-6.1-sol"]
    assert run["effective_efforts"] == ["medium"]


def test_mixed_or_fallback_call_excludes_run_comparison():
    first = _trace("call-1")
    mixed = _trace("call-2", resolved_effort="high")
    result = project_run(expected_call_ids=["call-1", "call-2"],
        expected_call_refs=[first["call_ref"], mixed["call_ref"]],
        traces=[_run_row(first), _run_row(mixed)])
    assert result["comparison_eligible"] is False
    assert "mixed_effective_efforts" in result["reasons"]

    fallback = _trace("call-2", rerouted=True)
    result = project_run(expected_call_ids=["call-1", "call-2"],
        expected_call_refs=[first["call_ref"], fallback["call_ref"]],
        traces=[_run_row(first), _run_row(fallback)])
    assert result["comparison_eligible"] is False
    assert "one_or_more_calls_not_identity_eligible" in result["reasons"]
    assert result["calls"][1]["reasons"] == ["original_trace_invalid:ValueError"]


def test_missing_call_trace_prevents_parity_claim():
    trace = _trace()
    missing = _trace("call-2")
    result = project_run(expected_call_ids=["call-1", "call-2"],
        expected_call_refs=[trace["call_ref"], missing["call_ref"]], traces=[_run_row(trace)])
    assert result["comparison_eligible"] is False
    assert result["missing_call_ids"] == ["call-2"]
    assert "missing_call_traces" in result["reasons"]


def test_requested_or_resolved_model_mismatch_fails_closed():
    trace = _trace("call-1", resolved_model="gpt-6.2-sol")
    result = project_run(expected_call_ids=["call-1"], expected_call_refs=[trace["call_ref"]],
        traces=[_run_row(trace)])
    assert result["comparison_eligible"] is False
    assert result["calls"][0]["effective_model"] == "gpt-6.2-sol"
    assert result["calls"][0]["reasons"] == ["effective_model_mismatch"]


def test_explicit_effort_mismatch_and_packet_digest_tamper_fail_closed():
    trace = _trace(configured_effort="high")
    result = project_run(expected_call_ids=["call-1"], expected_call_refs=[trace["call_ref"]],
        traces=[_run_row(trace)])
    assert result["comparison_eligible"] is False
    assert result["calls"][0]["reasons"] == ["configured_effort_mismatch"]

    tampered = _trace()
    tampered["events"][0]["packet"] = b'{"id":1,"method":"thread/start"}\n'
    result = project_run(expected_call_ids=["call-1"], expected_call_refs=[tampered["call_ref"]],
        traces=[_run_row(tampered)])
    assert result["comparison_eligible"] is False
    assert result["calls"][0]["reasons"] == ["original_trace_invalid:ValueError"]


def test_missing_resolved_effort_is_not_inferred_from_the_target_model():
    trace = _trace("call-1", resolved_effort=None)
    result = project_run(expected_call_ids=["call-1"], expected_call_refs=[trace["call_ref"]],
        traces=[_run_row(trace)])
    assert result["comparison_eligible"] is False
    assert result["calls"][0]["effective_model"] == "gpt-6.1-sol"
    assert result["calls"][0]["effective_effort"] is None
    assert result["calls"][0]["reasons"] == ["effective_effort_missing"]
    assert "effective_effort_unobserved" in result["reasons"]


def test_valid_trace_with_more_than_4096_events_is_still_projected():
    trace = _trace()
    events = trace["events"]
    for seq in range(len(events), 4100):
        packet = {"method": "progress/event", "params": {"sequence": seq}}
        raw = (json.dumps(packet, sort_keys=True, separators=(",", ":")) + "\n").encode()
        raw_ref = _ref("packet-" + str(seq), raw)
        event = {"schema": "ai4r-native-governed-trace-event:1", "scope": trace["summary"]["scope"],
            "sequence": seq, "direction": "in", "method": "progress/event", "raw_ref": raw_ref}
        event_ref = _ref("event-" + str(seq), canonical(event))
        trace["summary"]["event_refs"].append(event_ref)
        events.append({"event_ref": event_ref, "event": event, "packet": raw})
    trace["summary_ref"] = _ref("summary-call-1", canonical(trace["summary"]))
    projected = project_call(**trace, expected_call_id="call-1")
    assert projected["comparison_eligible"] is True
