"""Retain every scheduled variant/repeat in campaign outcome denominators."""
import argparse
import hashlib
import json
from pathlib import Path

from .contracts import canonical, read_json


def summarize(index, assessments):
    expected = {(t["case_id"], t["variant_id"], t["repeat"]): t for t in index["tasks"]}
    if len(expected) != len(index["tasks"]):
        raise ValueError("duplicate frozen scheduled task")
    observed = {}
    for result in assessments:
        key = (result["case_id"], result["variant_id"], result["repeat"])
        if key not in expected or key in observed:
            raise ValueError("foreign/duplicate assessment; select exactly one immutable Harbor job")
        if result.get("expected_model") != expected[key]["expected_model"]:
            raise ValueError("assessment model baseline differs")
        if result.get("task_sha256") != hashlib.sha256(canonical(expected[key])).hexdigest():
            raise ValueError("assessment belongs to a different frozen task")
        observed[key] = result
    rows = []
    for case_id in dict.fromkeys(t["case_id"] for t in index["tasks"]):
        keys = [k for k in expected if k[0] == case_id]
        results = [observed[k] for k in keys if k in observed]
        available = sum(r.get("execution_available") is True for r in results)
        scored = [r for r in results if type(r.get("case_correctness")) is bool]
        rows.append({"case_id": case_id, "classification": expected[keys[0]]["case"]["classification"],
                     "scheduled": len(keys), "observed": len(results), "missing": len(keys)-len(results),
                     "available": available, "scored": len(scored),
                     "correct": sum(r["case_correctness"] is True for r in scored),
                     "baseline_success": sum(r.get("reward", {}).get("baseline_success") == 1 for r in results),
                     "unavailable": sum(r.get("status") == "unavailable" for r in results),
                     "invalid_evidence": sum(r.get("status") == "invalid_evidence" for r in results),
                     "critical_violations": sum(len(r.get("critical_violations", [])) for r in results),
                     "availability_rate": available/len(keys),
                     "correctness_given_scored": sum(r["case_correctness"] is True for r in scored)/len(scored) if scored else None})
    return {"schema": "ai4r-harbor-suite-report:1", "split": "development", "cases": rows,
            "scheduled": len(expected), "observed": len(observed), "missing": len(expected)-len(observed),
            "release_acceptance": "not_established", "aggregate_quality_score": None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--job-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    assessments = [read_json(p) for p in args.job_results.glob("*/verifier/assessment.json")]
    result = summarize(read_json(args.bundle/"task-index.json"), assessments)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write("\n")
    print(json.dumps({k: result[k] for k in ("scheduled", "observed", "missing", "release_acceptance")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
