"""Collect a native batch versus original deterministic component observations.

One batch is one native trial. Its decisions are not independent model trials;
its complete model-call cost is never divided or assigned to individual cases.
No worker/semantic-verifier/E3/full-unit execution is inferred from check rows.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from pathlib import Path

from .contracts import canonical, read_json, strict_json
from .value_data import Dataset
from .value_pair import native_evidence


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def align_results(expected_ids, response):
    """Preserve incomplete/extra/duplicate observations without invented grades."""
    raw = response.get("results", []) if isinstance(response, dict) else []
    if not isinstance(raw, list):
        raw = []
    counts = Counter(row.get("id") for row in raw if isinstance(row, dict) and isinstance(row.get("id"), str))
    mapping = {row["id"]: row for row in raw if isinstance(row, dict) and isinstance(row.get("id"), str)
               and row["id"] in expected_ids and counts[row["id"]] == 1}
    return mapping, {"missing_ids": sorted(set(expected_ids) - set(counts)),
        "duplicate_ids": sorted(key for key, count in counts.items() if count > 1),
        "unexpected_ids": sorted(set(counts) - set(expected_ids)),
        "malformed_results": sum(not isinstance(row, dict) or not isinstance(row.get("id"), str) for row in raw)}


def _native_batch(bank, native_run, broker):
    bank, native_run = Path(bank), Path(native_run)
    original = (bank / "public/batch.json").read_bytes()
    mounted = (native_run / "project/batch.json").read_bytes()
    if original != mounted:
        raise ValueError("Native batch differs from exact frozen public batch bytes")
    result = read_json(native_run / "result.json")
    identity, sources = native_evidence(native_run, broker)
    response = read_json(native_run / "project/response.json")
    return result, identity, sources, response, _sha(original)


def _helper_control(bank):
    bank = Path(bank)
    available = any((bank / "public" / name).is_dir() for name in ("native_skill", "planning-validator-skill"))
    # A helper's existence or an agent's unit-test assertion is not a measured
    # helper execution. Do not manufacture a scored zero-call control receipt.
    return {"available": available, "measurement_status": "not_measured_by_this_collector",
            "correct": None, "model_calls": None,
            "note": "Ordinary Python helper is a competent available control; execution and score require an original separately retained receipt."}


def _save(dataset, *, component, bank, native_run, image, native_result, identity,
          sources, response, batch_sha, rows, alignment, extra_sources, helper_control=None):
    data = Dataset(dataset)
    bank, native_run = Path(bank), Path(native_run)
    receipts = [data.artifact(path) for path in [bank / "manifest.json", bank / "public/batch.json",
        native_run / "assignment.json", native_run / "result.json", native_run / "project/response.json",
        native_run / "skill-inventory.json", *sources, *extra_sources] if Path(path).is_file()]
    for name in ("controller-start.json", "controller-finished.json"):
        path = native_run / name
        if path.is_file():
            receipts.append(data.artifact(path))
    available = sum(row["cc"]["available"] and row["native"]["available"] for row in rows)
    counts = {arm: sum(row[arm]["correct"] is True for row in rows) for arm in ("cc", "native")}
    def clean_alignment(value):
        return all(clean_alignment(item) if isinstance(item, dict) else not item for item in value.values())
    eligible = (available == len(rows) and clean_alignment(alignment)
                and native_result["status"] == "completed" and identity.get("model_and_effort_verified") is True)
    value = {"schema": "ai4r-value-component-native-pair:1", "component": component,
        "public_batch_sha256": batch_sha, "rows": rows, "alignment": alignment,
        "native_status": native_result["status"], "native_identity": identity, "image": image,
        "batch_cost": {"cc_model_calls": 0, "native_model_calls": identity["model_calls"],
                       "native_usage": identity["usage"], "cost_usd": None,
                       "per_case_model_call_allocation": None},
        "population": {"native_batches": 1, "artifact_decisions": len(rows), "paired_available_decisions": available,
                       "independent_native_trials": 1, "new_independent_probe_trials_claimed": 0},
        "correct_decisions": counts, "comparison_eligible": eligible,
        "quality_delta_cc_minus_native": counts["cc"] - counts["native"] if eligible else None,
        "ordinary_helper_control": helper_control or _helper_control(bank),
        "retained_sources": receipts,
        "scope": "Actual deterministic checking component versus full native application batch; not worker-plus-semantic-verifier, E3, admission, or full-unit execution.",
        "interpretation": "Any model-call difference compares component invocation with agent orchestration, not intrinsic algorithm quality. No case-level cost allocation or independent-trial multiplication."}
    return data.append("component_native_pair", value, record_id="component-pair-" + _sha(canonical({
        "component": component, "batch": batch_sha, "native": _sha((native_run / "result.json").read_bytes()),
        "response": _sha((native_run / "project/response.json").read_bytes())})))


def collect_verification(dataset, bank, cc_output, native_run, broker, image, helper_receipt=None):
    from .value_verification_cases import load, grade
    bank, cc_output = Path(bank), Path(cc_output)
    cases = load(bank)
    summary = read_json(cc_output / "summary.json")
    if summary.get("model_calls") != 0:
        raise ValueError("Expected original zero-model-call deterministic component summary")
    native_result, identity, sources, response, batch_sha = _native_batch(bank, native_run, broker)
    expected_ids = {case["id"] for case in cases}
    public_cases, batch_alignment = align_results(expected_ids, {"results": read_json(bank / "public/batch.json")["cases"]})
    if (any(batch_alignment.values()) or any(_sha(canonical(public_cases[case["id"]])) != case["task_sha256"] for case in cases)):
        raise ValueError("Public batch cases differ from independently frozen per-case tasks")
    by_id, alignment = align_results(expected_ids, response)
    cc_rows, cc_alignment = align_results(expected_ids, {"results": summary["rows"]})
    alignment["cc"] = cc_alignment
    rows, extra = [], [cc_output / "summary.json"]
    for case in cases:
        ident = case["id"]
        cc = cc_rows.get(ident)
        original_path = cc_output / (ident + ".json")
        if cc is not None:
            if not original_path.is_file() or canonical(read_json(original_path)) != canonical(cc):
                raise ValueError("Original CC row differs from summary: " + ident)
            if cc.get("task_sha256") != case["task_sha256"] or cc.get("model_calls") != 0:
                raise ValueError("CC task identity or component model-call count differs")
            extra.append(original_path)
        native = by_id.get(ident)
        cc_available = cc is not None and cc.get("status") == "observed" and isinstance(cc.get("checks"), list)
        cc_grade = grade(case, cc["response"]) if cc_available else None
        native_grade = grade(case, native) if native is not None else None
        rows.append({"case_id": ident, "task_sha256": case["task_sha256"],
            "cc": {"available": cc_available, "correct": cc_grade["correct"] if cc_grade else None,
                   "grade": cc_grade, "checks": cc.get("checks") if cc else None},
            "native": {"available": native is not None, "correct": native_grade["correct"] if native_grade else None,
                       "grade": native_grade}, "per_case_call_allocation": None})
        extra.extend([bank / "public" / (ident + ".json"), bank / "private" / (ident + ".json")])
    helper_control = None
    if helper_receipt is not None:
        from .value_verification_cases import grade_batch
        helper = read_json(helper_receipt)
        helper_path = bank / "public/native_skill/verify_helper.py"
        if (helper.get("schema") != "ai4r-value-ordinary-helper-receipt:1" or helper.get("model_calls") != 0
                or helper.get("returncode") != 0 or helper.get("batch_sha256") != batch_sha
                or helper.get("helper_sha256") != _sha(helper_path.read_bytes())):
            raise ValueError("Ordinary helper receipt differs from original batch/helper execution")
        checked = grade_batch(bank, strict_json(helper["stdout"].encode("utf-8")))
        if not checked.get("response_valid") or checked["correct"] != helper["correct"] or checked["total"] != helper["decisions"]:
            raise ValueError("Ordinary helper stdout does not reproduce its independent grades")
        helper_control = {"available": True, "measurement_status": "observed_original_helper_receipt",
            "correct": checked["correct"], "decisions": checked["total"], "model_calls": 0,
            "elapsed_s": helper.get("elapsed_s"), "batch_sha256": batch_sha,
            "helper_sha256": helper["helper_sha256"], "grades": checked}
        extra.append(Path(helper_receipt))
    return _save(dataset, component="typed_artifact_verification", bank=bank, native_run=native_run,
        image=image, native_result=native_result, identity=identity, sources=sources, response=response,
        batch_sha=batch_sha, rows=rows, alignment=alignment, extra_sources=extra, helper_control=helper_control)


def collect_planning(dataset, bank, native_run, broker, image):
    """Collect the existing frozen eight-case component suite after native run.

    Batch response: results[{id,reject,failed_checks}]. Root stages batch.json;
    all per-case packets, labels and original production receipts predate calls.
    """
    bank = Path(bank)
    manifest = read_json(bank / "private/manifest.json")
    cases = manifest["cases"]
    native_result, identity, sources, response, batch_sha = _native_batch(bank, native_run, broker)
    by_id, alignment = align_results({case["case_id"] for case in cases}, response)
    rows, extra = [], [bank / "private/manifest.json"]
    for case in cases:
        ident = case["case_id"]
        packet_path = bank / "public" / ident / "candidate.json"
        if _sha(packet_path.read_bytes()) != case["public_sha256"]:
            raise ValueError("Frozen planning packet changed")
        mounted_packet = Path(native_run) / "project" / ident / "candidate.json"
        if mounted_packet.read_bytes() != packet_path.read_bytes():
            raise ValueError("Native planning packet differs from frozen public packet")
        expected_path, original_path = (bank / "private" / (ident + suffix) for suffix in (".expected.json", ".production.json"))
        expected, original = read_json(expected_path), read_json(original_path)
        native = by_id.get(ident)
        native_answer = {key: native.get(key) for key in ("reject", "failed_checks")} if native else None
        valid = (native_answer is not None and type(native_answer["reject"]) is bool
                 and isinstance(native_answer["failed_checks"], list)
                 and all(isinstance(item, str) for item in native_answer["failed_checks"])
                 and len(native_answer["failed_checks"]) == len(set(native_answer["failed_checks"])))
        if valid:
            native_answer["failed_checks"] = sorted(native_answer["failed_checks"])
        rows.append({"case_id": ident, "task_sha256": case["public_sha256"],
            "cc": {"available": original.get("measurement") == "production_plan_checks_component",
                   "correct": original["answer"] == expected, "checks": original["all_original_results"]},
            "native": {"available": native is not None, "correct": valid and native_answer == expected if native else None},
            "per_case_call_allocation": None})
        extra.extend([packet_path, expected_path, original_path])
    return _save(dataset, component="planning_constraints", bank=bank, native_run=native_run, image=image,
        native_result=native_result, identity=identity, sources=sources, response=response,
        batch_sha=batch_sha, rows=rows, alignment=alignment, extra_sources=extra)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", choices=("verification", "planning"))
    for name in ("dataset", "bank", "native-run", "broker", "image"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--cc-output")
    parser.add_argument("--helper-receipt")
    args = vars(parser.parse_args(argv))
    component = args.pop("component")
    if component == "planning":
        args.pop("cc_output")
        args.pop("helper_receipt")
    elif not args["cc_output"]:
        parser.error("verification requires --cc-output")
    result = (collect_verification if component == "verification" else collect_planning)(**args)
    print(__import__("json").dumps({"record_id": result["id"], "correct_decisions": result["value"]["correct_decisions"]}))


if __name__ == "__main__":
    main()
