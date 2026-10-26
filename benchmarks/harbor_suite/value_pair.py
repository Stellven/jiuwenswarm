"""Collect one completed back-and-forth paper pair from original evidence.

No inference or product writes. Costs cover the full exported E1 pipeline,
including compiler, planner and shared verifiers, versus the native application.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from .contracts import canonical, read_json, strict_json
from .value_data import Dataset
from .value_paper_cases import load_pdf_cases, grade, request_text
from .value_product_evidence import audit_archive


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def native_evidence(run, broker, *, expected_model="gpt-6.1-sol"):
    if expected_model not in {"gpt-6.1-sol", "gpt-6-luna"}:
        raise ValueError("Explicit approved comparison model required")
    run, broker = Path(run), Path(broker)
    result = read_json(run / "result.json")
    requests = sorted((run / "evidence").glob("completion-*-request.json"))
    responses = sorted((run / "evidence").glob("completion-*-response.json"))
    if not requests or len(requests) != len(responses) or len(responses) != result.get("model_calls"):
        raise ValueError("Native completion population differs from original result")
    ids, calls, sources = set(), [], []
    for request_path, response_path in zip(requests, responses):
        if request_path.name.replace("-request.json", "") != response_path.name.replace("-response.json", ""):
            raise ValueError("Native request/response ordinal mismatch")
        packet, response = read_json(request_path), read_json(response_path)
        ident = response.get("request_id")
        if not isinstance(ident, str) or len(ident) != 32 or any(c not in "0123456789abcdef" for c in ident) or ident in ids:
            raise ValueError("Native completion ID absent, duplicate or malformed")
        ids.add(ident)
        submitted_path, received_path = broker / (ident + ".request.json"), broker / (ident + ".response.json")
        submitted, received = read_json(submitted_path), read_json(received_path)
        if (submitted.get("request_id") != ident or submitted.get("model") != expected_model
                or submitted.get("reasoning_effort") != "medium" or canonical(received) != canonical(response)
                or canonical(strict_json(submitted["prompt"].rsplit("\n", 1)[-1].encode())) != canonical(
                    {key: packet[key] for key in ("messages", "tools")})):
            raise ValueError("Native broker and original packet do not join exactly")
        if (response.get("status") != "completed" or response.get("identity", {}).get("effective") != expected_model
                or response.get("reasoning_effort") != "medium"):
            raise ValueError("Native call lacks completed exact model/effort identity")
        calls.append(response)
        sources.extend([request_path, response_path, submitted_path, received_path])
    totals = {}
    for field in ("input_tokens", "output_tokens"):
        values = [(call.get("usage") or {}).get(field) for call in calls]
        totals[field] = sum(values) if all(type(value) is int and value >= 0 for value in values) else None
    return {"call_ids": sorted(ids), "model_calls": len(calls), "usage": totals,
            "model_and_effort_verified": True}, sources


def product_identity(archive, audit):
    from .value_trace_identity import project_archive
    original = project_archive(archive)
    projection = original["projection"]
    if (original["source_archive"]["sha256"] != audit["archive_sha256"]
            or set(projection["expected_call_ids"]) != {call["id"] for call in audit["original_model_calls"]}):
        raise ValueError("Raw-wire projection differs from full original pipeline inventory")
    return {**projection, "original_archive_projection": original}


def _product_location(root, shared_task):
    root = Path(root)
    paths = [root / "run_record.json"] if (root / "run_record.json").is_file() else list(root.glob("runs/*/run_record.json"))
    candidates = [(path.parent, read_json(path)) for path in paths]
    matching = [(folder, row) for folder, row in candidates if row.get("task") == shared_task]
    if len(matching) != 1:
        raise ValueError("Need one actual product run with the exact arm-shared request")
    return matching[0]


def collect_pair(dataset, bank, case_id, product_run, native_run, broker, image):
    cases = load_pdf_cases(bank)
    selected = [case for case in cases if case["task"]["id"] == case_id]
    if len(selected) != 1:
        raise ValueError("Unknown or duplicate frozen PDF case")
    case = selected[0]
    shared = request_text(case)
    folder, record = _product_location(product_run, shared)
    native_run = Path(native_run)
    assignment, native_result = read_json(native_run / "assignment.json"), read_json(native_run / "result.json")
    if assignment.get("variant") != "native-skills" or native_result.get("variant") != "native-skills":
        raise ValueError("This collector requires the declared native-skills application arm")
    if assignment["task"] != shared:
        raise ValueError("Native request differs from exact product/public request")
    native_task = read_json(native_run / "project/task.json")
    native_schema = read_json(native_run / "project/output-schema.json")
    if native_schema != case["task"]["response_schema"] or native_task.get("response_schema") != native_schema:
        raise ValueError("Native public output schema differs from frozen arm-shared contract")
    archive = folder / "artifacts/originals.zip"
    run_id = record.get("app_run_id") or record.get("status", {}).get("run_id")
    audited = audit_archive(archive, expected_run_id=run_id)
    identity = product_identity(archive, audited)
    native, native_sources = native_evidence(native_run, broker)
    if not audited["all_model_calls_joined"] or audited["missing_output_refs"]:
        raise ValueError("Product calls/outputs do not close over original invocation evidence")
    with zipfile.ZipFile(archive) as zipped:
        summary_invocations = [row for row in audited["invocations"] if row["cc_name"] == "research.paper_summary"
                               and row["outcome"] == "success"]
        if len(summary_invocations) != 1 or len(summary_invocations[0]["output_refs"]) != 1:
            raise ValueError("Need exactly one original successful paper-summary output Ref")
        output = summary_invocations[0]["output_refs"][0]
        product_bytes = zipped.read(output["archive_paths"][0])
        product_summary = strict_json(product_bytes)
        if _sha(product_bytes) != output["ref"]["sha256"]:
            raise ValueError("Selected summary differs from original producing invocation")
        plans = [path for path in zipped.namelist() if path.startswith("contracts/run-plan-")]
        if len(plans) != 1:
            raise ValueError("Need exact exported run plan for policy/cap proof")
        plan = strict_json(zipped.read(plans[0]))
        from jiuwenswarm.research.unified_planning import integrated_plan_policy
        policy = integrated_plan_policy()
        if _sha(canonical(policy)) != plan["policy_ref"]["sha256"]:
            raise ValueError("Actual frozen policy pin differs from reviewed aggregate cap definition")
        cap = policy["aggregate_limits"]["model_calls"]
        if cap != 80 or assignment["max_model_calls"] != cap or record["limits"]["deadline_s"] != 600 or assignment["wall_time_s"] != 600:
            raise ValueError("Per-arm declared model/observer caps do not match 80/600")
        for index, document in enumerate(case["task"]["documents"], 1):
            expected_pdf = (Path(bank) / case_id / document["path"]).read_bytes()
            actual_pdf = (native_run / "project" / document["path"]).read_bytes()
            canonical_bytes = document["text"].encode("utf-8")
            if actual_pdf != expected_pdf or zipped.read(f"sources/document_{index:03d}.txt") != canonical_bytes:
                raise ValueError("Original PDF or product canonical source differs between arms")
            native_documents = [row for row in native_task["documents"] if row["path"] == document["path"]]
            if len(native_documents) != 1 or native_documents[0]["text"].encode("utf-8") != canonical_bytes:
                raise ValueError("Native compiled public document text differs from product canonical buffer")
            native_canonical = native_run / "project" / document.get("canonical_text_filename", "canonical.txt")
            uploads = [item for item in record["inputs"] if item["path"] == document["path"]]
            if (len(uploads) != 1 or uploads[0]["sha256"] != _sha(expected_pdf)
                    or uploads[0]["upload_record"]["text_sha256"] != _sha(canonical_bytes)
                    or native_canonical.read_bytes() != canonical_bytes):
                raise ValueError("Upload/PDF/native canonical byte identity failed")
    native_bytes = (native_run / "project/paper_summary.json").read_bytes()
    product_grade, native_grade = grade(case, product_summary), grade(case, strict_json(native_bytes))
    eligible = (identity.get("comparison_eligible") is True
        and set(identity.get("expected_call_ids", [])) == {call["id"] for call in audited["original_model_calls"]}
        and record["execution_state"] == "completed" and native_result["status"] == "completed")
    data = Dataset(dataset)
    retained = [data.artifact(path) for path in [folder / "run_record.json", native_run / "assignment.json",
        native_run / "result.json", native_run / "skill-inventory.json", native_run / "project/task.json",
        native_run / "project/output-schema.json", *native_sources] if path.is_file()]
    for path in (native_run / "controller-start.json", native_run / "controller-finished.json"):
        if path.is_file():
            retained.append(data.artifact(path))
    retained.extend([data.json_artifact(product_bytes), data.json_artifact(native_bytes),
        data.json_artifact(canonical(audited)), data.json_artifact(canonical(identity)),
        data.json_artifact(canonical({"policy_ref": plan["policy_ref"], "hash_matched_policy_definition": policy}))])
    timing = read_json(native_run / "controller-finished.json").get("elapsed_s") if (native_run / "controller-finished.json").is_file() else None
    arms = {"cc": {"status": record["execution_state"], "correct": product_grade["content_correct"],
            "model_calls": audited["model_calls"], "call_functions": audited["call_functions"],
            "usage": {key: audited["usage"][key]["total"] for key in ("input_tokens", "output_tokens")},
            "cost_usd": None, "grade": product_grade, "binding_conformance": "product_gates_observed_separate_from_content"},
        "native-skills": {"status": native_result["status"], "correct": native_grade["content_correct"],
            "model_calls": native["model_calls"], "usage": native["usage"], "cost_usd": None,
            "grade": native_grade, "binding_conformance": "not_applicable", "controller_elapsed_s": timing}}
    value = {"schema": "ai4r-value-paper-pair:1", "case_id": case_id, "task_sha256": case["task_sha256"],
        "comparison_eligible": eligible, "arms": arms,
        "content_delta_cc_minus_native": int(product_grade["content_correct"]) - int(native_grade["content_correct"]) if eligible else None,
        "caps": {"model_calls_per_arm": cap, "observer_deadline_s_per_arm": 600,
            "cc_policy_ref": plan["policy_ref"], "cc_actual_run_plan_limits": plan["limits"],
            "note": "Policy aggregate cap and observer deadline are distinct from phase/DAG limits; all exported pipeline calls are counted."},
        "image": image, "native_identity": native, "product_identity": identity,
        "archive": {"path": str(archive.resolve()), "sha256": audited["archive_sha256"], "bytes": archive.stat().st_size},
        "retained_sources": retained, "comparison_scope": "Full E1 compiler/planner/worker/check/shared-verifier pipeline versus native-skills application; not an isolated capsule microbenchmark.",
        "population": {"paired_tasks": 1, "fact_checks_are_independent_tasks": False},
        "limitations": "Locally authored finite synthetic document; no scientific reliability, external generalization, or E3 acceptance claim."}
    return data.append("native_cc_pair", value, record_id="paper-pair-" + _sha(canonical({
        "archive": audited["archive_sha256"], "native": _sha((native_run / "result.json").read_bytes()), "case": case_id})))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "bank", "case-id", "product-run", "native-run", "broker", "image"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    record = collect_pair(**vars(args))
    print(json.dumps({"record_id": record["id"], "comparison_eligible": record["value"]["comparison_eligible"]}))


if __name__ == "__main__":
    main()
