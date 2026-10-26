"""Independent offline case assessment and Harbor reward emission."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

try:
    from .contracts import canonical, read_json, regular
    from .evidence import Unavailable, normalize_run, normalize_single_cc, validate_receipt
except ImportError:
    from pilot_grade import canonical, read_json
    from evidence import Unavailable, normalize_run, normalize_single_cc, validate_receipt, regular


def load_oracle(path):
    spec = importlib.util.spec_from_file_location("frozen_case_oracle", regular(path))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.evaluate


def assess(root, task, criteria, oracle):
    result = {"schema": "ai4r-harbor-suite-assessment:1", "case_id": task["case_id"],
              "task_sha256": hashlib.sha256(canonical(task)).hexdigest(),
              "variant_id": task["variant_id"], "repeat": task["repeat"], "split": "development",
              "classification": task["case"]["classification"], "expected_model": task["expected_model"],
              "status": "unavailable", "evidence_integrity": False, "execution_available": False,
              "case_correctness": None, "baseline_model_verified": False,
              "checks": [], "metrics": {}, "critical_violations": [], "errors": []}
    try:
        validate_receipt(root, task)
        if task['entrypoint'] == 'single_cc' and task.get('evaluation_binding'):
            normalized = normalize_single_cc(root, task)
        elif task["entrypoint"] != "run":
            raise Unavailable("protected module launcher/projection is not installed; ordinary prompts cannot substitute")
        else:
            normalized = normalize_run(root, task)
        result.update(evidence_integrity=True, execution_available=True)
        calls = [r["record"] for r in normalized["records"] if r["kind"] in {"model-call", "model_call"}]
        result["baseline_model_verified"] = bool(calls) and all(
            (c.get("identity") or {}).get("effective") == task["expected_model"]
            and (c.get("identity") or {}).get("basis") not in {None, "unknown", "requested_only"} for c in calls)
        evaluated = oracle(normalized, criteria)
        if not isinstance(evaluated, dict) or set(evaluated) != {"checks", "metrics", "critical_violations"}:
            raise ValueError("invalid independent oracle result")
        checks = evaluated["checks"]
        if not isinstance(checks, list) or not checks or any(
            not isinstance(c, dict) or set(c) != {"id", "status", "reason", "evidence_refs"}
            or c["status"] not in {"pass", "fail", "unavailable"} for c in checks):
            raise ValueError("invalid independent oracle checks")
        if len({c["id"] for c in checks}) != len(checks):
            raise ValueError("duplicate independent oracle checks")
        result.update(evaluated)
        if any(c["status"] == "fail" for c in checks) or evaluated["critical_violations"]:
            result.update(status="failed", case_correctness=False)
        elif any(c["status"] == "unavailable" for c in checks):
            result["status"] = "unavailable"
        else:
            correct = all(c["status"] == "pass" for c in checks) and not evaluated["critical_violations"]
            result.update(status="passed" if correct else "failed", case_correctness=correct)
    except Unavailable as error:
        result["errors"].append(str(error))
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, RuntimeError, zipfile.BadZipFile, RecursionError) as error:
        result.update(status="invalid_evidence", case_correctness=None)
        result["errors"].append(str(error))
    # Availability has its own denominator. No missing/blocked result is called
    # a scientific zero or silently dropped from the campaign.
    result["reward"] = {"evidence_integrity": int(result["evidence_integrity"]),
                        "execution_available": int(result["execution_available"]),
                        "case_correctness": int(result["case_correctness"] is True),
                        "baseline_success": int(result["case_correctness"] is True and result["baseline_model_verified"])}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("evidence", "task", "criteria", "output"):
        parser.add_argument("--"+key, type=Path, required=True)
    args = parser.parse_args(argv)
    task = read_json(regular(args.task)); criteria_path = regular(args.criteria)
    for name, expected in {**task["protected_material_pins"], **task["implementation_pins"]}.items():
        path = regular(args.task.parent / name)
        if path.stat().st_size != expected["size"] or hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
            raise ValueError("protected implementation/material changed: " + name)
    if hashlib.sha256(criteria_path.read_bytes()).hexdigest() != task["criteria_pin"]["sha256"]:
        raise ValueError("protected criteria differs from frozen task")
    oracle_path = regular(args.task.parent / "oracle.py")
    if hashlib.sha256(oracle_path.read_bytes()).hexdigest() != task["oracle_pin"]["sha256"]:
        raise ValueError("protected oracle differs from frozen task")
    result = assess(args.evidence, task, read_json(criteria_path), load_oracle(oracle_path))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "assessment.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    (args.output / "reward.json").write_text(json.dumps(result["reward"])+"\n", encoding="utf-8")
    print(json.dumps({"case_id": task["case_id"], "variant_id": task["variant_id"], "status": result["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
