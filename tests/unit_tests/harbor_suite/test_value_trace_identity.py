import hashlib
import io
import json
import zipfile

from benchmarks.harbor_suite.contracts import canonical
from benchmarks.harbor_suite.value_trace_identity import project_archive, project_call, project_run


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


def _archive(path, *, call_ids, trace_ids):
    """Write a tiny exact-Ref run-evidence archive for archive projector tests."""
    members = {}
    files = []

    def add(zip_path, artifact_id, raw):
        ref = _ref(artifact_id, raw)
        members[zip_path] = raw
        files.append({"artifact_ref": ref, "audience": "researcher",
            "media_type": "application/json", "path": zip_path})
        return ref

    original_refs = {}
    for call_id in call_ids:
        raw = canonical({"id": call_id, "call_function": "worker"})
        original_refs[call_id] = add("evidence/model-call-" + call_id + ".json", call_id, raw)

    starts = {}
    for call_id in sorted(set(call_ids) | set(trace_ids)):
        start_id = call_id + ":start"
        raw = canonical({"id": start_id, "call_id": call_id})
        starts[call_id] = add("evidence/model-call-start-" + call_id + ".json", start_id, raw)

    for call_id in trace_ids:
        trace = _trace(call_id)
        scope = trace["summary"]["scope"]
        scope["model_call_start_ref"] = starts[call_id]
        for row in trace["events"]:
            row["event"]["scope"] = scope
            row["event_ref"] = _ref("native-governed-trace-event:" + str(row["event"]["sequence"]),
                                    canonical(row["event"]))
        trace["summary"]["event_refs"] = [row["event_ref"] for row in trace["events"]]
        trace["summary_ref"] = _ref("native-governed-trace:" + call_id, canonical(trace["summary"]))
        event_index = []
        for row in trace["events"]:
            seq = row["event"]["sequence"]
            add("records/" + call_id + "/" + f"{seq:08d}.event.json", row["event_ref"]["id"],
                canonical(row["event"]))
            add("records/" + call_id + "/" + f"{seq:08d}.packet", row["event"]["raw_ref"]["id"],
                row["packet"])
            event_index.append({"event_ref": row["event_ref"], "raw_ref": row["event"]["raw_ref"],
                "sequence": seq})
        summary_file_ref = add("records/" + call_id + "/summary.json",
            "runs/run-1/trace/" + call_id + "/summary.json", canonical(trace["summary"]))
        index = {"call_ref": original_refs.get(call_id, trace["call_ref"]),
            "events": event_index, "model_call_start_ref": starts[call_id],
            "schema": "ai4r-native-trace-file-index:2", "status": "completed",
            "summary_file_ref": summary_file_ref, "summary_ref": trace["summary_ref"]}
        index_path = "records/" + call_id + "/index.v2.json"
        add(index_path, "runs/run-1/trace/" + call_id + "/index.v2.json", canonical(index))

    retrieval = {"artifact_refs": [entry["artifact_ref"] for entry in files],
        "audience": "researcher", "files": files, "id": "client-retrieval:1",
        "redactions": [], "run_id": "run-1", "schema_version": "1.0.0"}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("client_retrieval.json", canonical(retrieval))
        for name, raw in members.items():
            archive.writestr(name, raw)


def test_project_archive_resolves_exact_model_call_trace_and_packet_refs(tmp_path):
    source = tmp_path / "closed.zip"
    _archive(source, call_ids=["call-1"], trace_ids=["call-1"])
    result = project_archive(source)
    assert result["original_model_calls"] == result["trace_indices"] == 1
    assert result["projection"]["comparison_eligible"] is True
    assert result["roles"] == {"worker": 1}
    assert result["projection"]["calls"][0]["effective_effort"] == "medium"
    assert result["closure_issues"] == []


def test_project_archive_reports_missing_and_unexpected_trace_call_ids(tmp_path):
    source = tmp_path / "incomplete.zip"
    _archive(source, call_ids=["call-1", "call-2"], trace_ids=["call-1", "call-extra"])
    result = project_archive(source)
    assert result["projection"]["comparison_eligible"] is False
    assert result["projection"]["missing_call_ids"] == ["call-2"]
    assert result["unexpected_trace_call_ids"] == ["call-extra"]
    assert "unassociated_trace_rows" in result["projection"]["reasons"]
    assert "unexpected_model_call_start:call-extra" in result["closure_issues"]
