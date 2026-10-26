"""Fail-closed model/effort projection from original native call traces.

Input rows are the exact protected trace summary, event records, and original
packet bytes exported by ``run_evidence``. This module does not reinterpret
provider summaries or synthesize call records; missing, mixed, rerouted, or
truncated trace evidence makes the whole run ineligible for a same-model,
same-effort comparison.
"""
from __future__ import annotations

import hashlib
import argparse
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any
import zipfile

from .contracts import canonical, strict_json


TRACE_SCHEMA = "ai4r-native-governed-trace:1"
EVENT_SCHEMA = "ai4r-native-governed-trace-event:1"
SCOPE_FIELDS = {"run_id", "node_id", "subnode_id", "attempt_id", "execution_id",
                "invocation_id", "call_id", "contract_ref", "model_call_start_ref"}
# Normal application runs can produce several thousand UI/progress events for
# one valid call. Keep a finite bound while accommodating the observed 5,347
# event paper-summary worker trace.
MAX_EVENTS = 8192
MAX_PACKET_BYTES = 1024 * 1024
MAX_TRACE_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 100_000
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024 * 1024


def _ref(value: Any, label: str) -> dict:
    if (type(value) is not dict or set(value) != {"id", "sha256"}
            or not isinstance(value["id"], str) or not value["id"]
            or not isinstance(value["sha256"], str) or len(value["sha256"]) != 64
            or any(ch not in "0123456789abcdef" for ch in value["sha256"])):
        raise ValueError(f"{label} is not an exact artifact Ref")
    return value


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _checked_record(ref: dict, record: dict, label: str) -> None:
    _ref(ref, label + " Ref")
    if type(record) is not dict or _digest(canonical(record)) != ref["sha256"]:
        raise ValueError(f"{label} bytes do not match their original Ref")


def _packet(row: dict, scope: dict, sequence: int, total_bytes: list[int]) -> tuple[dict, dict]:
    if type(row) is not dict or set(row) != {"event_ref", "event", "packet"}:
        raise ValueError("trace event row has an unsupported shape")
    event_ref, event, packet = row["event_ref"], row["event"], row["packet"]
    _checked_record(event_ref, event, "native trace event")
    if (set(event) != {"schema", "scope", "sequence", "direction", "method", "raw_ref"}
            or event["schema"] != EVENT_SCHEMA or event["scope"] != scope
            or type(event["sequence"]) is not int or event["sequence"] != sequence
            or event["direction"] not in {"in", "out"}
            or not isinstance(event["method"], str) or not event["method"]):
        raise ValueError("trace event differs from its ordered original call scope")
    raw_ref = _ref(event["raw_ref"], "native packet Ref")
    if not isinstance(packet, bytes) or len(packet) > MAX_PACKET_BYTES:
        raise ValueError("native packet is absent or exceeds its byte limit")
    total_bytes[0] += len(packet)
    if total_bytes[0] > MAX_TRACE_BYTES or _digest(packet) != raw_ref["sha256"]:
        raise ValueError("native packet closure is incomplete or digest-mismatched")
    value = strict_json(packet)
    if type(value) is not dict:
        raise ValueError("native protocol packet is not a JSON object")
    packet_method = value.get("method")
    if packet_method is not None and packet_method != event["method"]:
        raise ValueError("native packet method differs from the indexed event")
    return event, value


def project_call(*, call_ref: dict, summary_ref: dict, summary: dict, events: list[dict],
                 expected_call_id: str, expected_model: str = "gpt-6.1-sol",
                 expected_effort: str = "medium") -> dict:
    """Validate one complete original call trace and project resolved identity."""
    _ref(call_ref, "native trace index call Ref")
    if call_ref["id"] != expected_call_id:
        raise ValueError("native trace index is attached to another original model call")
    _checked_record(summary_ref, summary, "native trace summary")
    if (not isinstance(expected_call_id, str) or not expected_call_id
            or not isinstance(expected_model, str) or not expected_model
            or not isinstance(expected_effort, str) or not expected_effort):
        raise ValueError("expected call, model, and effort identities are required")
    if (set(summary) != {"schema", "scope", "status", "event_refs"}
            or summary["schema"] != TRACE_SCHEMA or summary["status"] not in {"completed", "failed", "interrupted"}
            or type(summary["scope"]) is not dict or set(summary["scope"]) != SCOPE_FIELDS
            or summary["scope"].get("call_id") != expected_call_id
            or type(summary["event_refs"]) is not list or len(summary["event_refs"]) > MAX_EVENTS
            or type(events) is not list or len(events) != len(summary["event_refs"])):
        raise ValueError("native trace summary does not close over the expected original model call")

    scope = summary["scope"]
    for key in ("run_id", "node_id", "subnode_id", "attempt_id", "execution_id", "invocation_id", "call_id"):
        if not isinstance(scope.get(key), str) or not scope[key]:
            raise ValueError("native trace scope is incomplete")
    for key in ("contract_ref", "model_call_start_ref"):
        _ref(scope.get(key), "native trace scope " + key)
    for ref in summary["event_refs"]:
        _ref(ref, "native trace event")
    if (len(set((ref["id"], ref["sha256"]) for ref in summary["event_refs"]))
            != len(summary["event_refs"])):
        raise ValueError("native trace repeats an event Ref")

    total_bytes = [0]
    frames = []
    for sequence, row in enumerate(events):
        event, packet = _packet(row, scope, sequence, total_bytes)
        if row["event_ref"] != summary["event_refs"][sequence]:
            raise ValueError("event Ref order differs from the original trace summary")
        if event["method"] == "model/rerouted" or packet.get("method") == "model/rerouted":
            raise ValueError("native provider reported a model reroute")
        frames.append((event["direction"], event["method"], packet))

    requests: dict[str, list[tuple[dict, dict]]] = {"thread/start": [], "turn/start": []}
    for direction, event_method, packet in frames:
        if direction == "out" and event_method in requests:
            if packet.get("method") != event_method or "id" not in packet or type(packet["id"]) not in (int, str):
                raise ValueError("native start request is malformed")
            params = packet.get("params")
            if type(params) is not dict:
                raise ValueError("native start request has no original params")
            requests[event_method].append((packet, params))
    if any(len(requests[name]) != 1 for name in requests):
        raise ValueError("trace must contain exactly one thread/start and one turn/start request")

    replies: dict[str, list[dict]] = {"thread/start": [], "turn/start": []}
    for direction, event_method, packet in frames:
        if direction != "in" or event_method not in replies or "id" not in packet:
            continue
        request = requests[event_method][0][0]
        if type(packet["id"]) is type(request["id"]) and packet["id"] == request["id"]:
            replies[event_method].append(packet)
    if any(len(replies[name]) != 1 for name in replies):
        raise ValueError("trace lacks one correlated original response for each start request")

    thread_request, thread_params = requests["thread/start"][0]
    thread_reply = replies["thread/start"][0]
    turn_request, turn_params = requests["turn/start"][0]
    turn_reply = replies["turn/start"][0]
    if "error" in thread_reply or type(thread_reply.get("result")) is not dict:
        raise ValueError("thread/start did not resolve successfully")
    if "error" in turn_reply or type(turn_reply.get("result")) is not dict:
        raise ValueError("turn/start did not resolve successfully")
    thread_result = thread_reply["result"]
    thread_id = (thread_result.get("thread") or {}).get("id") if type(thread_result.get("thread")) is dict else None
    turn_result = turn_reply["result"]
    turn_id = (turn_result.get("turn") or {}).get("id") if type(turn_result.get("turn")) is dict else None
    if not isinstance(thread_id, str) or not thread_id or not isinstance(turn_id, str) or not turn_id:
        raise ValueError("original start responses have no thread/turn identity")
    positions = {}
    for index, (direction, method, packet) in enumerate(frames):
        if direction == "out" and method in {"thread/start", "turn/start"}:
            positions[(method, "request")] = index
        elif direction == "in" and method in {"thread/start", "turn/start"} and "id" in packet:
            positions[(method, "response")] = index
        elif direction == "in" and method == "turn/completed" and packet.get("method") == "turn/completed":
            positions[(method, "terminal")] = index
    if not (positions[("thread/start", "request")] < positions[("thread/start", "response")]
            < positions[("turn/start", "request")] < positions[("turn/start", "response")]
            < positions[("turn/completed", "terminal")]):
        raise ValueError("original thread and turn protocol packets are out of order")

    configured_effort = None
    config = thread_params.get("config")
    if type(config) is dict:
        configured_effort = config.get("model_reasoning_effort")
    turn_effort = turn_params.get("effort")
    if turn_effort is not None:
        if configured_effort is not None and configured_effort != turn_effort:
            raise ValueError("thread and turn effort pins disagree")
        configured_effort = turn_effort

    completed = [packet for direction, method, packet in frames
        if direction == "in" and method == "turn/completed"
        and type(packet.get("params")) is dict
        and packet["params"].get("threadId") == thread_id
        and type(packet["params"].get("turn")) is dict
        and packet["params"]["turn"].get("id") == turn_id]
    if len(completed) != 1:
        raise ValueError("trace lacks one terminal notification for this exact turn")
    terminal_status = completed[0]["params"]["turn"].get("status")

    requested_model = thread_params.get("model")
    turn_model = turn_params.get("model")
    effective_model = thread_result.get("model")
    effective_effort = thread_result.get("reasoningEffort")
    model_matches = (requested_model == expected_model and turn_model == expected_model
                     and effective_model == expected_model and turn_params.get("threadId") == thread_id)
    effort_matches = effective_effort == expected_effort and configured_effort in (None, expected_effort)
    reasons = []
    if summary["status"] != "completed" or terminal_status != "completed":
        reasons.append("call_not_completed")
    if requested_model != expected_model:
        reasons.append("requested_model_mismatch")
    if turn_model != expected_model:
        reasons.append("turn_start_model_mismatch")
    if effective_model is None:
        reasons.append("effective_model_missing")
    elif effective_model != expected_model:
        reasons.append("effective_model_mismatch")
    if turn_params.get("threadId") != thread_id:
        reasons.append("turn_thread_mismatch")
    if effective_effort is None:
        reasons.append("effective_effort_missing")
    elif effective_effort != expected_effort:
        reasons.append("effective_effort_mismatch")
    if configured_effort is not None and configured_effort != expected_effort:
        reasons.append("configured_effort_mismatch")
    return {"call_id": expected_call_id, "trace_status": summary["status"],
        "terminal_status": terminal_status, "requested_model": requested_model,
        "turn_requested_model": turn_model, "effective_model": effective_model,
        "configured_effort": configured_effort, "effective_effort": effective_effort,
        "model_matches_expected": model_matches, "effort_matches_expected": effort_matches,
        "effort_explicitly_pinned": configured_effort is not None,
        "thread_start_request_sequence": positions[("thread/start", "request")],
        "thread_start_response_sequence": positions[("thread/start", "response")],
        "comparison_eligible": not reasons, "reasons": reasons}


def project_run(*, expected_call_ids: list[str], expected_call_refs: list[dict], traces: list[dict],
                expected_model: str = "gpt-6.1-sol", expected_effort: str = "medium") -> dict:
    """Require full, one-to-one model-call trace coverage for parity claims.

    Each trace item has ``summary_ref``, ``summary``, and ``events`` in the
    shape accepted by :func:`project_call`. The IDs come from original
    ``model-call`` records; they are never generated here.
    """
    if (type(expected_call_ids) is not list or not expected_call_ids
            or any(not isinstance(value, str) or not value for value in expected_call_ids)
            or len(expected_call_ids) != len(set(expected_call_ids))
            or type(expected_call_refs) is not list or len(expected_call_refs) != len(expected_call_ids)
            or type(traces) is not list):
        raise ValueError("run parity requires a unique nonempty original model-call inventory")
    expected_ref_by_id = {}
    for ref in expected_call_refs:
        _ref(ref, "original model-call")
        if ref["id"] not in expected_call_ids or ref["id"] in expected_ref_by_id:
            raise ValueError("original model-call Refs do not match their unique call IDs")
        expected_ref_by_id[ref["id"]] = ref
    if set(expected_ref_by_id) != set(expected_call_ids):
        raise ValueError("original model-call inventory is missing an exact Ref")
    by_call: dict[str, list[dict]] = {}
    malformed = 0
    for item in traces:
        try:
            summary = item["summary"]
            call_id = summary["scope"]["call_id"]
            call_ref = _ref(item["call_ref"], "native trace index call")
            if (not isinstance(call_id, str) or not call_id
                    or call_ref["id"] != call_id or expected_ref_by_id.get(call_id) != call_ref):
                malformed += 1
                continue
            by_call.setdefault(call_id, []).append(item)
        except (KeyError, TypeError):
            malformed += 1

    projections = []
    missing = [call for call in expected_call_ids if call not in by_call]
    duplicate = [call for call, rows in by_call.items() if len(rows) != 1]
    unexpected = sorted(set(by_call) - set(expected_call_ids))
    for call_id in expected_call_ids:
        rows = by_call.get(call_id, [])
        if len(rows) != 1:
            continue
        item = rows[0]
        try:
            projections.append(project_call(call_ref=item["call_ref"],
                summary_ref=item["summary_ref"], summary=item["summary"],
                events=item["events"], expected_call_id=call_id,
                expected_model=expected_model, expected_effort=expected_effort))
        except (KeyError, TypeError, ValueError) as error:
            projections.append({"call_id": call_id, "comparison_eligible": False,
                "effective_model": None, "effective_effort": None,
                "reasons": ["original_trace_invalid:" + type(error).__name__]})

    models = sorted({row["effective_model"] for row in projections if row.get("effective_model") is not None})
    efforts = sorted({row["effective_effort"] for row in projections if row.get("effective_effort") is not None})
    reasons = []
    if missing:
        reasons.append("missing_call_traces")
    if duplicate:
        reasons.append("duplicate_call_traces")
    if unexpected:
        reasons.append("traces_outside_original_call_inventory")
    if malformed:
        reasons.append("unassociated_trace_rows")
    if any(not row.get("comparison_eligible") for row in projections):
        reasons.append("one_or_more_calls_not_identity_eligible")
    if any("effective_effort_missing" in row.get("reasons", []) for row in projections):
        reasons.append("effective_effort_unobserved")
    if len(models) > 1:
        reasons.append("mixed_effective_models")
    if len(efforts) > 1:
        reasons.append("mixed_effective_efforts")
    eligible = (not reasons and len(projections) == len(expected_call_ids)
                and len(models) == len(efforts) == 1)
    return {"expected_call_ids": list(expected_call_ids), "traced_call_ids": sorted(by_call),
        "calls": projections, "effective_models": models, "effective_efforts": efforts,
        "missing_call_ids": missing, "duplicate_call_ids": duplicate,
        "unexpected_call_ids": unexpected, "comparison_eligible": eligible,
        "reasons": reasons,
        "scope": "Original call-level native thread/start resolution and turn terminal only; not output-quality evidence."}


def project_archive(path, *, expected_model="gpt-6.1-sol", expected_effort="medium") -> dict:
    """Project model/effort identity directly from an original run-evidence ZIP.

    The archive's client retrieval manifest is treated as an index only. Every
    call, start, trace index, summary, event, and packet is resolved through an
    exact exported Ref and digest-checked before the native call projector sees
    it. No files are extracted and no model/provider summary is trusted.
    """
    archive = Path(path).absolute()
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("bounded regular original run archive required")
    try:
        container = zipfile.ZipFile(archive)
    except (OSError, zipfile.BadZipFile) as error:
        raise ValueError("original run archive is unreadable") from error
    with container as zf:
        infos = zf.infolist()
        names = [item.filename for item in infos]
        if (len(infos) > MAX_ARCHIVE_MEMBERS or len(names) != len(set(names))
                or sum(item.file_size for item in infos) > MAX_ARCHIVE_BYTES
                or any(item.is_dir() or item.flag_bits & 1 for item in infos)):
            raise ValueError("archive members are duplicated, encrypted, directories, or over bounded limits")
        for name in names:
            candidate = PurePosixPath(name)
            if (candidate.is_absolute() or ".." in candidate.parts or "\\" in name
                    or not candidate.parts):
                raise ValueError("archive contains a noncanonical member path")
        if names.count("client_retrieval.json") != 1:
            raise ValueError("archive must contain one client_retrieval.json")
        if zf.getinfo("client_retrieval.json").file_size > MAX_MANIFEST_BYTES:
            raise ValueError("client retrieval manifest exceeds its byte bound")
        manifest = strict_json(zf.read("client_retrieval.json"))
        if type(manifest) is not dict or type(manifest.get("files")) is not list:
            raise ValueError("client retrieval manifest has no files list")
        entries = manifest["files"]
        by_path = {}
        by_id: dict[str, dict[str, list[dict]]] = {}
        for entry in entries:
            if type(entry) is not dict or not isinstance(entry.get("path"), str):
                raise ValueError("client manifest contains a malformed file entry")
            rel = PurePosixPath(entry["path"])
            ref = _ref(entry.get("artifact_ref"), "client manifest artifact")
            if (rel.is_absolute() or ".." in rel.parts or "\\" in entry["path"]
                    or entry["path"] not in names or entry["path"] == "client_retrieval.json"
                    or entry["path"] in by_path):
                raise ValueError("client manifest path is missing, duplicated, or noncanonical")
            by_path[entry["path"]] = entry
            by_id.setdefault(ref["id"], {}).setdefault(ref["sha256"], []).append(entry)
        if set(by_path) != set(names) - {"client_retrieval.json"}:
            raise ValueError("client manifest does not cover exactly the archive members")

        def read_ref(ref, label, *, max_bytes=MAX_TRACE_BYTES):
            ref = _ref(ref, label)
            options = by_id.get(ref["id"], {}).get(ref["sha256"], [])
            if not options:
                raise ValueError(f"{label} Ref is absent from the exported client manifest")
            for option in options:
                info = zf.getinfo(option["path"])
                if info.file_size > max_bytes:
                    continue
                raw = zf.read(option["path"])
                if _digest(raw) == ref["sha256"]:
                    return raw
            raise ValueError(f"{label} bytes do not match the exact exported Ref")

        # These are the original terminal model-call records. Start records are
        # deliberately excluded from the measured call inventory.
        call_entries = [entry for entry in entries
            if entry["path"].startswith("evidence/model-call-")
            and entry["path"].endswith(".json")
            and not entry["path"].startswith("evidence/model-call-start-")]
        call_records = []
        for entry in call_entries:
            ref = entry["artifact_ref"]
            record = strict_json(read_ref(ref, "original model-call", max_bytes=1024 * 1024))
            if type(record) is not dict or record.get("id") != ref["id"]:
                raise ValueError("original model-call record does not match its artifact Ref")
            call_records.append((ref, record))
        call_records.sort(key=lambda pair: pair[0]["id"])
        call_ids = [ref["id"] for ref, _ in call_records]
        call_refs = [ref for ref, _ in call_records]
        if not call_ids or len(set(call_ids)) != len(call_ids):
            raise ValueError("archive has no unique original model-call inventory")

        start_entries = [entry for entry in entries
            if entry["path"].startswith("evidence/model-call-start-")
            and entry["path"].endswith(".json")]
        starts: dict[str, list[dict]] = {}
        for entry in start_entries:
            ref = entry["artifact_ref"]
            record = strict_json(read_ref(ref, "original model-call start", max_bytes=1024 * 1024))
            if type(record) is not dict or record.get("id") != ref["id"]:
                raise ValueError("original model-call start does not match its artifact Ref")
            start_id = record.get("call_id")
            if not isinstance(start_id, str) or not start_id or ref["id"] != start_id + ":start":
                raise ValueError("original model-call start is not attached to its exact call ID")
            starts.setdefault(start_id, []).append(ref)

        closure_issues = []
        expected_set = set(call_ids)
        for call_id in call_ids:
            if len(starts.get(call_id, [])) != 1:
                closure_issues.append("model_call_start_missing_or_duplicate:" + call_id)
        for call_id in sorted(set(starts) - expected_set):
            closure_issues.append("unexpected_model_call_start:" + call_id)

        trace_indices = []
        trace_index_call_ids = []
        for entry in entries:
            if not entry["path"].endswith("/index.v2.json"):
                continue
            index_raw = read_ref(entry["artifact_ref"], "native trace index", max_bytes=4 * 1024 * 1024)
            index = strict_json(index_raw)
            required = {"call_ref", "events", "model_call_start_ref", "schema", "status",
                        "summary_file_ref", "summary_ref"}
            if type(index) is not dict or set(index) != required or index.get("schema") != "ai4r-native-trace-file-index:2":
                raise ValueError("native trace index has an unsupported schema or shape")
            call_ref = _ref(index["call_ref"], "native trace index call")
            call_id = call_ref["id"]
            trace_index_call_ids.append(call_id)
            start_ref = _ref(index["model_call_start_ref"], "native trace index start")
            known_starts = starts.get(call_id, [])
            if len(known_starts) != 1 or known_starts[0] != start_ref:
                closure_issues.append("trace_model_call_start_ref_mismatch:" + call_id)

            summary_file_ref = _ref(index["summary_file_ref"], "native trace summary file")
            summary_raw = read_ref(summary_file_ref, "native trace summary file", max_bytes=4 * 1024 * 1024)
            summary = strict_json(summary_raw)
            summary_ref = _ref(index["summary_ref"], "native trace summary")
            if summary_ref["sha256"] != summary_file_ref["sha256"]:
                raise ValueError("native trace summary Refs disagree on their content digest")
            scope = summary.get("scope") if type(summary) is dict else None
            if type(scope) is not dict or scope.get("model_call_start_ref") != start_ref:
                closure_issues.append("summary_model_call_start_ref_mismatch:" + call_id)
            if index["status"] != summary.get("status"):
                raise ValueError("native trace index and summary statuses disagree")
            indexed_events = index["events"]
            if type(indexed_events) is not list or len(indexed_events) > MAX_EVENTS:
                raise ValueError("native trace index exceeds its bounded event count")
            event_rows = []
            for sequence, indexed in enumerate(indexed_events):
                if (type(indexed) is not dict or set(indexed) != {"event_ref", "raw_ref", "sequence"}
                        or type(indexed["sequence"]) is not int or indexed["sequence"] != sequence):
                    raise ValueError("native trace index has a malformed event row")
                event_ref = _ref(indexed["event_ref"], "native trace event")
                event_raw = read_ref(event_ref, "native trace event", max_bytes=1024 * 1024)
                event = strict_json(event_raw)
                raw_ref = _ref(indexed["raw_ref"], "native packet")
                packet = read_ref(raw_ref, "native packet", max_bytes=MAX_PACKET_BYTES)
                if type(event) is not dict or event.get("raw_ref") != raw_ref:
                    raise ValueError("native trace event packet Ref differs from the index")
                event_rows.append({"event_ref": event_ref, "event": event, "packet": packet})
            trace_indices.append({"call_ref": call_ref, "summary_ref": summary_ref,
                "summary": summary, "events": event_rows})

        projection = project_run(expected_call_ids=call_ids, expected_call_refs=call_refs,
            traces=trace_indices, expected_model=expected_model, expected_effort=expected_effort)
        if closure_issues:
            projection["comparison_eligible"] = False
            projection["reasons"] = list(dict.fromkeys(projection["reasons"] + ["model_call_start_closure_invalid"]))
        role_by_id = {ref["id"]: record.get("call_function") for ref, record in call_records}
        projection["calls"] = [{**call, "call_function": role_by_id.get(call.get("call_id"))}
                                for call in projection["calls"]]
        return {"schema": "ai4r-native-trace-archive-projection:1",
            "source_archive": {"filename": archive.name, "sha256": _digest(archive.read_bytes()),
                "bytes": archive.stat().st_size, "zip_members": len(names),
                "manifest_files": len(entries)},
            "original_model_calls": len(call_ids), "trace_indices": len(trace_indices),
            "trace_index_call_ids": trace_index_call_ids,
            "unexpected_trace_call_ids": sorted(set(trace_index_call_ids) - expected_set),
            "closure_issues": closure_issues,
            "roles": dict(Counter(role_by_id.values())), "projection": projection}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.archive.resolve() == args.output.resolve():
        parser.error("projection output must be separate from the immutable source archive")
    result = project_archive(args.archive)
    from .value_data import write_once
    output = (canonical(result) + b"\n")
    write_once(args.output, output, raw=True)
    print(__import__("json").dumps({"output": str(args.output),
        "comparison_eligible": result["projection"]["comparison_eligible"],
        "original_model_calls": result["original_model_calls"],
        "trace_indices": result["trace_indices"], "reasons": result["projection"]["reasons"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
