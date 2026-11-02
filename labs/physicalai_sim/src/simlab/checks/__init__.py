"""Checks carried by every result (PAS-M1-001 B07; PRD SL-4; ARCHC failure behavior and evidence levels).

The runner never judges the science. Checks are about whether a measurement
can be trusted: watchdogs, reruns across engine settings and assumed values,
independent recomputation, known-answer comparisons and control arms. A failed
required check marks exactly the measurements that depend on it invalid; they
stay visible. An unexpected outcome in an ordinary control arm is a result,
not a failed check.
"""
from __future__ import annotations

import math
from typing import Any

DEFAULT_RECOMPUTE_TOL = {"abs": 1e-9, "rel": 1e-9}


def within(a: float | None, b: float | None, tol: dict | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if math.isnan(a) or math.isnan(b):
        return False
    tol = tol or {}
    d = abs(a - b)
    ok_abs = tol.get("abs") is not None and d <= tol["abs"]
    ok_rel = tol.get("rel") is not None and d <= tol["rel"] * max(abs(a), abs(b))
    if tol.get("abs") is None and tol.get("rel") is None:
        return d == 0
    return ok_abs or ok_rel


def watchdog_check(attempts: list[dict]) -> dict:
    numerical = [a["attempt_id"] for a in attempts if a["invalid_reason"] == "numerical_failure"]
    stops: dict[str, list[str]] = {}
    for a in attempts:
        if (a.get("stop") or "").startswith("watchdog:") and a["status"] == "COMPLETED":
            stops.setdefault(a["stop"], []).append(a["attempt_id"])
    return {"check_id": "watchdog", "check_kind": "watchdog", "required": True,
            "status": "fail" if numerical else "pass",
            "observed": {"numerical_failure_attempts": numerical, "divergence_stops": stops,
                         "note": "Physical divergence stops are results (trials COMPLETED at their declared bounds), not check failures."},
            "affected_measurements": []}


def known_answer_check(decl: dict, values: list[dict]) -> dict:
    sel = [v for v in values if v["measurement_id"] == decl["measurement_id"]
           and (decl.get("arm_id") is None or v["arm_id"] == decl["arm_id"])
           and (decl.get("condition_id") is None or v["condition"] == decl["condition_id"])]
    tol = decl.get("tolerance") or {}
    rows, bad = [], 0
    for v in sel:
        ok = v["value"] is not None and within(float(v["value"]), float(decl["expected"]), tol)
        err = None if v["value"] is None else float(v["value"]) - float(decl["expected"])
        rows.append({"trial_id": v["trial_id"], "value": v["value"], "error": err,
                     "relative_error": (None if err is None or decl["expected"] == 0 else err / abs(decl["expected"])), "within": ok})
        bad += 0 if ok else 1
    status = "not_run" if not sel else ("fail" if bad else "pass")
    return {"check_id": decl["check_id"], "check_kind": "known_answer", "required": bool(decl.get("required", True)), "status": status,
            "observed": {"expected": decl["expected"], "tolerance": tol, "origin": decl.get("origin"), "values": rows, "outside": bad},
            "affected_measurements": [decl["measurement_id"]]}


def control_arm_check(decl: dict, trials: list[dict]) -> dict:
    ran = {a: [t for t in trials if t["arm_id"] == a and t["final_status"] in {"COMPLETED", "LIMIT_REACHED"}] for a in decl["arms"]}
    missing = [a for a, ts in ran.items() if not ts]
    return {"check_id": decl["check_id"], "check_kind": "control_arm", "required": bool(decl.get("required", True)),
            "status": "fail" if missing else "pass",
            "observed": {"arms": decl["arms"], "completed_trials": {a: len(ts) for a, ts in ran.items()}, "arms_without_completed_trials": missing,
                         "note": "The control arm's outcome is a result reported in its measurements; this check only establishes that it ran."},
            "affected_measurements": []}


def rerun_summary(decl: dict, samples: list[dict], measurement_ids: list[str]) -> dict:
    """samples: [{trial_id, arm_id, variation, attempt, original: {mid: v}, rerun: {mid: v}}]"""
    prec = decl.get("required_precision") or {}
    variation: dict[str, dict[str, Any]] = {}
    exceeded = []
    for mid in measurement_ids:
        diffs = [abs(s["rerun"][mid] - s["original"][mid]) for s in samples
                 if s["rerun"].get(mid) is not None and s["original"].get(mid) is not None]
        rel = [abs(s["rerun"][mid] - s["original"][mid]) / max(abs(s["original"][mid]), 1e-300) for s in samples
               if s["rerun"].get(mid) is not None and s["original"].get(mid) is not None]
        variation[mid] = {"n": len(diffs), "max_abs_change": max(diffs) if diffs else None, "max_rel_change": max(rel) if rel else None}
        p = prec.get(mid)
        if p is not None and diffs:
            ok = all(within(s["rerun"][mid], s["original"][mid], p) for s in samples
                     if s["rerun"].get(mid) is not None and s["original"].get(mid) is not None)
            variation[mid]["required_precision"] = p
            variation[mid]["within_required_precision"] = ok
            if not ok:
                exceeded.append(mid)
    incomplete = [s for s in samples if s["attempt"]["status"] not in {"COMPLETED", "LIMIT_REACHED"}]
    status = "not_run" if not samples else ("fail" if exceeded else "pass")
    return {"check_id": decl["check_id"], "check_kind": "rerun", "required": bool(decl.get("required", True)), "status": status,
            "observed": {"samples_per_arm": decl.get("samples_per_arm", 5), "variations": decl.get("variations", []),
                         "variation_by_measurement": variation, "exceeded_required_precision": exceeded,
                         "samples": samples, "rerun_attempts_not_completed": len(incomplete),
                         "note": "The check fails only when a measurement varies beyond its declared required precision."},
            "affected_measurements": exceeded}


def recomputation_summary(decl: dict, rows: list[dict]) -> dict:
    """rows: [{trial_id, attempt_id, measurement_id, primary, recomputed, agree}]"""
    bad = sorted({r["measurement_id"] for r in rows if not r["agree"]})
    return {"check_id": decl["check_id"], "check_kind": "recomputation", "required": bool(decl.get("required", True)),
            "status": "not_run" if not rows else ("fail" if bad else "pass"),
            "observed": {"tolerance": decl.get("tolerance") or DEFAULT_RECOMPUTE_TOL, "compared": len(rows),
                         "disagreements": [r for r in rows if not r["agree"]][:50], "implementation": "simlab.checks.recompute (independent of simlab.measure)"},
            "affected_measurements": bad}


def anchoring(exp: dict) -> str:
    if any(a["role"] in {"control", "reference"} for a in exp["arms"]):
        return "anchored"
    if any(c["check_kind"] in {"known_answer", "control_arm"} for c in exp.get("checks", [])):
        return "anchored"
    return "unanchored"


def validity(checks: list[dict], measurements: list[dict]) -> dict[str, list[str]]:
    """measurement_id -> failed required check IDs; derived measurements inherit their inputs' failures."""
    failed: dict[str, list[str]] = {}
    for c in checks:
        if c["required"] and c["status"] == "fail":
            for mid in c["affected_measurements"]:
                failed.setdefault(mid, []).append(c["check_id"])
    for m in measurements:
        src = (m.get("definition") or {}).get("of")
        if src and src in failed:
            failed.setdefault(m["measurement_id"], [])
            for cid in failed[src]:
                if cid not in failed[m["measurement_id"]]:
                    failed[m["measurement_id"]].append(cid)
    return failed


def evidence_level(status: str, checks: list[dict]) -> str | None:
    if status != "COMPLETED":
        return None
    if any(c["required"] and c["status"] == "fail" for c in checks):
        return None
    return "simulation"
