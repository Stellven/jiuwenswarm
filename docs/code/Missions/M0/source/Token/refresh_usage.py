"""Capture this trial's observable Codex usage without reading credentials.

Run from the repository root: python docs/code/Missions/M0/source/Token/refresh_usage.py
For a post-answer snapshot, launch --wait-complete in a hidden background process.
Runtime API attempts go in runtime_usage.jsonl: each JSON line must contain an
independently unique call_id, model, usage (same fields as Codex), and evidence.
Unavailable native counters must be null, including failed dispatched attempts.
Do not populate runtime usage from invented token estimates.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
SESSION = "01a11caa-99f3-7822-80a9-4c65e5c15873"
ROOT_TURN = "01a11caa-bf7c-7161-9f18-b7c4ee8b4fc0"
START = "2026-10-08T17:58:25.124Z"
FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")
AGGREGATE_FIELDS = (*FIELDS, "uncached_input_tokens")
UNAVAILABLE_MODEL_IDENTITIES = {"unavailable-native-served-identity"}


def known_model_ids(records):
    return sorted({r["model"] for r in records
                   if r.get("model") and r["model"] not in UNAVAILABLE_MODEL_IDENTITIES})


def read_lines(path):
    # Preserve CRLF/LF bytes so source_line_sha256 identifies the actual raw line.
    with path.open(encoding="utf-8", newline="") as stream:
        for number, line in enumerate(stream, 1):
            try:
                yield number, line, json.loads(line)
            except json.JSONDecodeError:
                # An active writer may leave its newest line incomplete.
                continue


def capture():
    records = {}
    complete = False
    sessions = Path.home() / ".codex" / "sessions"
    # The trial starts on this date. Descendants can continue on subsequent dates.
    for path in sessions.glob("2026/*/*/*.jsonl"):
        if path.stat().st_mtime < datetime.fromisoformat(START.replace("Z", "+00:00")).timestamp():
            continue
        models = {}
        thread = None
        agent_path = "/root"
        for number, line, item in read_lines(path):
            payload = item.get("payload", {})
            if item.get("type") == "session_meta" and thread is None:
                thread = payload.get("id")
                source = payload.get("source", {})
                if isinstance(source, dict):
                    agent_path = source.get("subagent", {}).get("thread_spawn", {}).get("agent_path", "/unknown")
            if item.get("type") == "turn_context":
                models[payload.get("turn_id")] = payload.get("model")
            if (thread == SESSION and item.get("type") == "event_msg"
                    and payload.get("type") == "task_complete" and payload.get("turn_id") == ROOT_TURN):
                complete = True
            if item.get("type") != "token_usage_record":
                continue
            if payload.get("session_id") != SESSION or payload.get("root_turn_id") != ROOT_TURN:
                continue
            # Inherited cumulative token_count events are deliberately excluded.
            if payload.get("thread_id") != thread:
                continue
            identity = payload.get("response_id")
            if not identity:
                raise ValueError("A usage record lacks its response identity")
            record = {
                "source_path": str(path), "source_line": number,
                "source_line_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                "timestamp": item.get("timestamp"), "thread_id": thread,
                "agent_path": agent_path, "turn_id": payload.get("turn_id"),
                "response_id": identity, "model": models.get(payload.get("turn_id")),
                "usage": payload["usage"], "kind": "coding_agent_generation",
            }
            if identity in records and records[identity]["usage"] != record["usage"]:
                raise ValueError("Conflicting duplicate usage: " + identity)
            records[identity] = record
    runtime = HERE / "runtime_usage.jsonl"
    if runtime.exists():
        for number, line, item in read_lines(runtime):
            identity = "runtime:" + item["call_id"]
            if identity in records:
                raise ValueError("Duplicate runtime call identity")
            record = {
                "source_path": str(runtime), "source_line": number,
                "source_line_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                "model": item["model"], "usage": item["usage"],
                "evidence": item["evidence"], "response_id": identity,
                "kind": "compiler_runtime_generation",
            }
            records[identity] = record
    return sorted(records.values(), key=lambda x: (x.get("timestamp") or "", x["response_id"])), complete


def aggregate(records):
    """Sum each known field without turning unavailable usage into zero."""
    observed = {key: [] for key in AGGREGATE_FIELDS}
    calls_without_any_usage = 0
    calls_with_unavailable_counters = 0
    derived_totals = 0
    for record in records:
        usage = {key: record["usage"].get(key) for key in FIELDS}
        for key, value in usage.items():
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError("Invalid counter " + key + " in " + record["response_id"])
        input_tokens, output_tokens = usage["input_tokens"], usage["output_tokens"]
        if input_tokens is not None and output_tokens is not None:
            exact_total = input_tokens + output_tokens
            if usage["total_tokens"] is None:
                usage["total_tokens"] = exact_total
                derived_totals += 1
            elif usage["total_tokens"] != exact_total:
                raise ValueError("Invalid total in " + record["response_id"])
        cache, reasoning = usage["cached_input_tokens"], usage["reasoning_output_tokens"]
        if input_tokens is not None and cache is not None and cache > input_tokens:
            raise ValueError("Invalid cached-input counter in " + record["response_id"])
        if output_tokens is not None and reasoning is not None and reasoning > output_tokens:
            raise ValueError("Invalid reasoning counter in " + record["response_id"])
        usage["uncached_input_tokens"] = input_tokens - cache if input_tokens is not None and cache is not None else None
        if all(usage[key] is None for key in FIELDS):
            calls_without_any_usage += 1
        if any(usage[key] is None for key in AGGREGATE_FIELDS):
            calls_with_unavailable_counters += 1
        for key, value in usage.items():
            if value is not None:
                observed[key].append(value)
    # An empty group exposes no measured subtotal; it is not evidence of zero API calls.
    fields = {key: {"known_call_count": len(values), "unavailable_call_count": len(records) - len(values),
                    "status": "unavailable" if not values else "complete" if len(values) == len(records) else "partial"}
              for key, values in observed.items()}
    return {"recorded_model_calls": len(records),
            "calls_without_any_usage": calls_without_any_usage,
            "calls_with_unavailable_counters": calls_with_unavailable_counters,
            "derived_total_call_count": derived_totals,
            "totals": {key: sum(values) if values and len(values) == len(records) else None for key, values in observed.items()},
            "observed_subtotals": {key: sum(values) if values else None for key, values in observed.items()},
            "field_completeness": fields}


def write_snapshot(records, complete):
    now = datetime.now(timezone.utc).isoformat()
    if not records:
        raise ValueError("No matching trial records found; do not write fabricated zeros")
    accounting = {"coding_agent": aggregate([r for r in records if r["kind"] == "coding_agent_generation"]),
                  "compiler_runtime": aggregate([r for r in records if r["kind"] == "compiler_runtime_generation"]),
                  "all_recorded_calls": aggregate(records)}
    native_records = [r for r in records if r["kind"] == "compiler_runtime_generation"]
    native_known_identities = sum(bool(r.get("model") and r["model"] not in UNAVAILABLE_MODEL_IDENTITIES)
                                  for r in native_records)
    accounting["compiler_runtime"].update({"known_served_identity_call_count": native_known_identities,
                                           "unavailable_served_identity_call_count": len(native_records) - native_known_identities})
    totals = accounting["all_recorded_calls"]["totals"]
    evidence = HERE / "usage_records.jsonl"
    evidence.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    report = json.loads((HERE / "token_usage.json").read_text(encoding="utf-8"))
    report["experiment_arm"] = "with_spec_kit_full"
    report["usage_source"] = "Codex local per-response token_usage_record plus native compiler runtime attempt ledger; unique response_id/call_id; source/Token/usage_records.jsonl"
    report["models_used"] = known_model_ids(records)
    report["currency"] = None
    report["implementation"].update({
        "model_calls": len(records), "input_tokens": totals["input_tokens"],
        "cached_input_tokens": totals["cached_input_tokens"],
        "uncached_input_tokens": totals["uncached_input_tokens"],
        "output_tokens": totals["output_tokens"], "reasoning_tokens": totals["reasoning_output_tokens"],
        "total_tokens": totals["total_tokens"], "actual_api_cost": None,
    })
    report["observed_usage"] = accounting
    report["measurement_notes"] = [
        "Trial start/baseline: " + START + "; root session " + SESSION + "; root turn " + ROOT_TURN + ". The first root turn_token_usage equals its per-response usage, establishing a zero prior-usage baseline for this new turn. All matching per-response records since this request are included; the first saved running snapshot was taken during source preparation before implementation.",
        "Snapshot at " + now + "; root turn complete observed: " + str(complete).lower() + ". " + ("Post-turn observable snapshot." if complete else "Running snapshot: subsequent agent generations and the final response are not yet counted; refresh after completion."),
        "Implementation means the entire requested coding trial: source reading, Spec Kit spec/plan/tasks/analyze/implement/converge, root and descendant planning, edits, testing, debugging, fixes, retries, and accounting work.",
        "Raw evidence copies only usage metadata, models and log references/hashes; no credentials or conversation text. Summation uses usage rather than inherited cumulative event_msg.token_count values. Root and descendant records are filtered by session_id and root_turn_id.",
        "Preparation for creating the supplied source documents before this request is unverified. Keep preparation.status=pending_verification and counters null; end_to_end remains null until that usage is known.",
        "Compiler runtime API attempts, including failed dispatched calls from every trial campaign, are separate from Codex coding-agent generations. runtime_usage.jsonl supplies unique call_id, model, nullable measured counters and raw evidence. Synthetic model fixtures do not consume API tokens and are excluded. This snapshot includes " + str(accounting["compiler_runtime"]["recorded_model_calls"]) + " recorded native attempts; " + str(accounting["compiler_runtime"]["calls_without_any_usage"]) + " have no exposed usage and " + str(accounting["compiler_runtime"]["calls_with_unavailable_counters"]) + " lack at least one category. The ledger is harvested again after each campaign; unharvested calls cannot yet be counted.",
        "Mandatory implementation counters are null whenever any recorded call lacks that category. observed_usage provides exact measured subtotals, coding-agent-only totals and per-field known/unavailable call counts. Missing native reasoning/cache usage remains null; total is derived from exact input plus output only when both exist. A measured subtotal is not the full trial total. Recorded call count includes a dispatched failure even when all its counters are unavailable.",
        "models_used contains only known model identifiers; the raw runtime placeholder unavailable-native-served-identity is preserved as evidence but excluded from that list. Native served identity is known for " + str(native_known_identities) + " recorded calls and unavailable for " + str(len(native_records) - native_known_identities) + "; the requested model/default route does not establish the provider-served identity.",
        "No actual billed-cost or billing-currency data is exposed in local usage records. Cost remains null; subscription limits are not money and public pricing would produce an estimate, not an actual bill.",
        "Observable counts are not a billing receipt and may be delayed or incomplete for failed calls without usage. The accounting scope is the named trial, excluding unrelated concurrent experiment arms and earlier sessions.",
        "Token category interpretation verified against official OpenAI documentation: https://developers.openai.com/api/docs/guides/agents-api/observability (accessed 2026-10-08): cached input is included in input, reasoning is included in output, missing usage is not zero and best-effort usage is not the final bill.",
        "Experiment arm corrected from without_spec_kit_cut_detail using Code_Prompt/sign.md (SK; FULL) and Code_prompt.txt requiring Spec Kit.",
    ]
    (HERE / "token_usage.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    snapshot = {"measured_at_utc": now, "trial_start_utc": START, "session_id": SESSION,
                "root_turn_id": ROOT_TURN, "root_turn_complete": complete,
                "model_calls": len(records), "totals": totals,
                "observed_usage": accounting,
                "usage_evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}
    with (HERE / "measurement_snapshots.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(snapshot) + "\n")
    print(json.dumps(snapshot))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-complete", action="store_true")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    deadline = time.monotonic() + args.timeout
    while True:
        records, complete = capture()
        if not args.wait_complete or complete or time.monotonic() >= deadline:
            write_snapshot(records, complete)
            break
        time.sleep(2)


if __name__ == "__main__":
    main()
