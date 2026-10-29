"""Read-only readiness snapshot for CC/verifier value campaigns.

This inspects local case release integrity, optional frozen Harbor evidence,
installed controller dependencies, and planned call/time ceilings. It never
contacts a model, Harbor service, deployment, or changes evidence files.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import zipfile

from .contracts import strict_json, validate_case, validate_bundle, read_json, regular

REPO = Path(__file__).resolve().parents[2]
DEFAULT_RELEASE = (Path(__file__).parent / "assets" /
                   "AI4Research-Benchmark-Cases-2026-10-26.zip")
DEFAULT_MATRIX = REPO / "VALUE_CAMPAIGN_CASE_MATRIX_LOCAL.json"
EXPECTED_RELEASE = "ai4r-benchmark-case-release:1"
EXPECTED_MATRIX = "cc-value-case-design-bank:1"
REQUIRED_PACKAGES = {"harbor": "0.24.0", "httpx": None, "jsonschema": None}


def _version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def inspect_release(archive=DEFAULT_RELEASE):
    """Verify the distributed ZIP without extracting it."""
    archive = regular(archive, 128 * 1024 * 1024)
    sidecar = archive.with_suffix(archive.suffix + ".sha256")
    expected = sidecar.read_text(encoding="ascii").split()[0].lower()
    if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
        raise ValueError("case release checksum sidecar is malformed")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != expected:
        raise ValueError("case release ZIP does not match its published checksum")
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise ValueError("case release ZIP CRC check failed")
        names = bundle.namelist()
        manifest_names = [name for name in names if name.endswith("/manifest.json")]
        if len(manifest_names) != 1:
            raise ValueError("case release must contain exactly one manifest")
        manifest_name = manifest_names[0]
        manifest = strict_json(bundle.read(manifest_name))
        if manifest.get("schema") != EXPECTED_RELEASE or manifest.get("classification") != "development":
            raise ValueError("unsupported or non-development case release")
        root = manifest_name.rsplit("/", 1)[0]
        expected_files = {}
        for row in manifest.get("files", []):
            path = row.get("path")
            if (not isinstance(path, str) or path.startswith("/") or ".." in Path(path).parts
                    or path in expected_files):
                raise ValueError("invalid/duplicate case release manifest path")
            expected_files[path] = row
        actual = {name[len(root) + 1:]: name for name in names
                  if name.startswith(root + "/") and name != manifest_name and not name.endswith("/")}
        if set(actual) != set(expected_files):
            raise ValueError("case release archive contents differ from its manifest")
        for relative, row in expected_files.items():
            raw = bundle.read(actual[relative])
            if (len(raw) != row.get("size") or hashlib.sha256(raw).hexdigest() != row.get("sha256")):
                raise ValueError("case release file hash/size mismatch: " + relative)
        cases = []
        case_rows = []
        case_dirs = sorted({name.split("/", 2)[1] for name in actual
                            if name.startswith("cases/") and name.endswith("/case.json")})
        for ident in case_dirs:
            name = f"cases/{ident}/case.json"
            case = validate_case(strict_json(bundle.read(actual[name])))
            if case["id"] != ident:
                raise ValueError("case release directory and case identity differ")
            cases.append(case)
            case_rows.append({"case_id": ident, "module": case["module"],
                              "entrypoint": case["entrypoint"], "variants": len(case["variants"])})
        if len(cases) != manifest.get("case_count") or sum(len(c["variants"]) for c in cases) != manifest.get("variant_count"):
            raise ValueError("case release manifest counts differ from case definitions")
        return {"status": "verified", "sha256": digest, "manifest_sha256": hashlib.sha256(
                    bundle.read(manifest_name)).hexdigest(), "classification": "development",
                "case_count": len(cases), "variant_count": sum(len(c["variants"]) for c in cases),
                "cases": case_rows, "extracted": False}


def inspect_matrix(path=DEFAULT_MATRIX, *, batch_size=8, call_budget=256,
                   reserve_calls=32, wall_budget_seconds=3 * 60 * 60,
                   reserve_wall_seconds=30 * 60, controller_batch_minutes=30):
    """Check design-bank accounting and conservative paired-batch arithmetic."""
    path = regular(path)
    matrix = strict_json(path.read_bytes())
    if matrix.get("schema") != EXPECTED_MATRIX or not isinstance(matrix.get("cases"), list):
        raise ValueError("unsupported local value case matrix")
    cases = matrix["cases"]
    ids = [row.get("case_id") for row in cases]
    if len(ids) != len(set(ids)) or len(ids) != matrix.get("base_case_count"):
        raise ValueError("case design IDs/count do not match the matrix header")
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError("batch size must be a positive integer")
    if type(call_budget) is not int or type(reserve_calls) is not int or not 0 <= reserve_calls < call_budget:
        raise ValueError("invalid total call budget/reserve")
    if type(wall_budget_seconds) is not int or type(reserve_wall_seconds) is not int or not 0 <= reserve_wall_seconds < wall_budget_seconds:
        raise ValueError("invalid total wall budget/reserve")
    if any(row.get("status") != "design_only_not_a_runnable_or_executed_trial" for row in cases):
        raise ValueError("matrix must not present design sketches as executable trials")
    if any(row.get("repeats") != 1 or len(row.get("primary_arms", [])) != 2 for row in cases):
        raise ValueError("design bank must use one repeat and two planned primary arms")
    if any(type(row.get("total_model_call_cap")) is not int or row["total_model_call_cap"] < 1
           or type(row.get("wall_cap_s")) is not int or row["wall_cap_s"] < 1 for row in cases):
        raise ValueError("invalid per-arm case budget")
    interactions = matrix.get("interaction_overlays", [])
    planning = matrix.get("planning_overlays", [])
    verification = matrix.get("verification_task_overlays", {})
    overlay_count = (len(interactions) + len(planning) + sum(
        value for key, value in verification.items() if key != "note" and type(value) is int))
    worst = sorted(cases, key=lambda row: (-row["total_model_call_cap"], -row["wall_cap_s"], row["case_id"]))[:batch_size]
    # Both arms run serially under the existing Harbor single-trial rule.
    paired_calls = 2 * sum(row["total_model_call_cap"] for row in worst)
    serial_seconds = 2 * sum(row["wall_cap_s"] for row in worst)
    batch_call_limit = matrix.get("batch_policy", {}).get("model_calls_max")
    time_limit = controller_batch_minutes * 60
    return {"status": "design_only", "base_designs": len(cases), "interaction_overlay_ideas": len(interactions),
            "planning_overlay_ideas": len(planning), "verification_overlay_ideas": overlay_count - len(interactions) - len(planning),
            "maximum_design_slots": len(cases) + overlay_count,
            "all_base_rows_design_only": True, "batch_preview": {"size": len(worst),
                "case_ids": [row["case_id"] for row in worst], "selection": "most expensive per-arm caps; arithmetic only",
                "worst_case_paired_calls": paired_calls, "total_call_budget": call_budget,
                "call_reserve": reserve_calls, "fits_total_budget_after_reserve": paired_calls <= call_budget - reserve_calls,
                "declared_batch_call_limit": batch_call_limit,
                "fits_declared_batch_limit": type(batch_call_limit) is int and paired_calls <= batch_call_limit,
                "worst_case_serial_seconds": serial_seconds,
                "controller_batch_limit_seconds": time_limit,
                "fits_controller_batch_limit": serial_seconds <= time_limit,
                "total_wall_budget_seconds": wall_budget_seconds,
                "wall_reserve_seconds": reserve_wall_seconds,
                "fits_total_wall_after_reserve": serial_seconds <= wall_budget_seconds - reserve_wall_seconds},
            "design_status_counts": dict(Counter(row["status"] for row in cases))}


def runtime_snapshot():
    versions = {name: _version(name) for name in ("harbor", "openjiuwen", "httpx", "jsonschema")}
    blockers = []
    if versions["harbor"] != REQUIRED_PACKAGES["harbor"]:
        blockers.append("Harbor 0.24.0 is not installed in this interpreter")
    if not versions["httpx"] or not versions["jsonschema"]:
        blockers.append("required HTTP/schema libraries are missing from this interpreter")
    if os.name != "posix":
        blockers.append("live Harbor observer/cancellation is qualified for Linux/WSL, not this Windows controller")
    helper = REPO / "jiuwenswarm/research/local_model_codex.py"
    comparator = REPO / "benchmarks/harbor_suite/comparison_harbor.py"
    full_adapter = REPO / "jiuwenswarm/server/runtime/agent_adapter/interface_deep.py"
    return {"os_name": os.name, "platform": platform.platform(), "python": sys.version.split()[0],
            "interpreter": str(Path(sys.executable).resolve()), "packages": versions,
            "required_package_versions": REQUIRED_PACKAGES,
            "live_controller_prerequisites_passed": not blockers, "blockers": blockers,
            "source_paths_present": {"tool_free_host_codex_helper": helper.is_file(),
                "native_codex_harbor_agent": comparator.is_file(), "native_deep_adapter_source": full_adapter.is_file()},
            "native_full_tool_using_codex_route": "not demonstrated by source presence; requires a separate real native smoke",
            "existing_tool_free_codex_scope": "one host App Server turn with tools unavailable",
            "credential_or_model_probe_performed": False}


def readiness(*, archive=DEFAULT_RELEASE, matrix=DEFAULT_MATRIX, bundle=None,
              job_results=None, batch_size=8, call_budget=256, reserve_calls=32,
              wall_budget_seconds=10800, reserve_wall_seconds=1800,
              controller_batch_minutes=30):
    result = {"schema": "ai4r-value-readiness:1", "checked_at": datetime.now(timezone.utc).isoformat(),
              "read_only": True, "model_calls": 0, "release": inspect_release(archive),
              "design_bank": inspect_matrix(matrix, batch_size=batch_size, call_budget=call_budget,
                  reserve_calls=reserve_calls, wall_budget_seconds=wall_budget_seconds,
                  reserve_wall_seconds=reserve_wall_seconds, controller_batch_minutes=controller_batch_minutes),
              "runtime": runtime_snapshot(), "evidence": {"status": "not_supplied",
                  "scope": "No live case readiness or product telemetry is inferred from source code, catalog metadata or narrative reports."}}
    if (bundle is None) != (job_results is None):
        raise ValueError("bundle and job-results must be supplied together")
    if bundle is not None:
        index = validate_bundle(bundle)
        results_path = Path(job_results)
        if not results_path.is_dir():
            raise ValueError("job-results must be an existing directory")
        assessments = [read_json(path) for path in sorted(results_path.glob("*/verifier/assessment.json"))]
        from .report import summarize
        summary = summarize(index, assessments)
        result["evidence"] = {"status": "assessment_accounting_verified", "scope":
            "Harbor task identity and assessment accounting only; not independently re-scored E1/E3 source telemetry.",
            "bundle_root": str(Path(bundle).resolve()), "job_results": str(results_path.resolve()),
            "scheduled": summary["scheduled"], "observed": summary["observed"],
            "missing": summary["missing"], "cases": summary["cases"]}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--job-results", type=Path)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--call-budget", type=int, default=256)
    parser.add_argument("--reserve-calls", type=int, default=32)
    parser.add_argument("--wall-budget-seconds", type=int, default=10800)
    parser.add_argument("--reserve-wall-seconds", type=int, default=1800)
    parser.add_argument("--controller-batch-minutes", type=int, default=30)
    args = parser.parse_args(argv)
    print(json.dumps(readiness(archive=args.archive, matrix=args.matrix, bundle=args.bundle,
        job_results=args.job_results, batch_size=args.batch_size, call_budget=args.call_budget,
        reserve_calls=args.reserve_calls, wall_budget_seconds=args.wall_budget_seconds,
        reserve_wall_seconds=args.reserve_wall_seconds,
        controller_batch_minutes=args.controller_batch_minutes), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
