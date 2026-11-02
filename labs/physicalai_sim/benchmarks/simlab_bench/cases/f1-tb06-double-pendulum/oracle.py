"""SIMLAB-Bench f1-tb06-double-pendulum oracle (TB-06). Standard library only; independent of SIMLAB code."""

import math


def _check(cid, ok, reason, refs=None):
    return {"id": cid, "status": "pass" if ok else "fail", "reason": reason, "evidence_refs": refs or []}


def _unavailable(cid, reason):
    return {"id": cid, "status": "unavailable", "reason": reason, "evidence_refs": []}


def _first_trial(evidence):
    res = evidence.get("result") or {}
    trials = res.get("trials") or []
    return res, (trials[0] if trials else None)


def _executed(evidence):
    """The run must have executed and completed; missing evidence never passes."""
    res, t = _first_trial(evidence)
    if not res or t is None:
        return None, None, _unavailable("execution", "no SIMLAB result in the evidence")
    attempt = (t.get("attempts") or [{}])[-1]
    ok = res.get("status") == "COMPLETED" and attempt.get("status") == "COMPLETED"
    return res, t, _check("execution", ok, f"run {res.get('status')}, attempt {attempt.get('status')} {attempt.get('invalid_reason') or ''}".strip(),
                          [res.get("run_id")])


def _rows(evidence, signal, key="traces"):
    rows = (evidence.get(key) or {}).get(signal)
    return rows if rows else None


def _rel(a, b):
    return abs(a - b) / abs(b) if b else abs(a - b)


def _crossings(rows, col=1, level=0.0, direction="up"):
    out = []
    for i in range(len(rows) - 1):
        a, b = rows[i][col] - level, rows[i + 1][col] - level
        if (direction == "up" and a < 0 <= b) or (direction == "down" and a > 0 >= b):
            out.append(rows[i][0] + a / (a - b) * (rows[i + 1][0] - rows[i][0]))
    return out


def _quad_accel(rows, col, t0, t1):
    pts = [(r[0], r[col]) for r in rows if t0 - 1e-12 <= r[0] <= t1 + 1e-12]
    if len(pts) < 3:
        return None
    ta = pts[0][0]
    s = [0.0] * 5
    q = [0.0] * 3
    for t, x in pts:
        u, p = t - ta, 1.0
        for k in range(5):
            if k < 3:
                q[k] += x * p
            s[k] += p
            p *= u
    m = [[s[0], s[1], s[2]], [s[1], s[2], s[3]], [s[2], s[3], s[4]]]

    def det(a):
        return (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
                + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
    D = det(m)
    return None if D == 0 else 2.0 * det([[m[i][0], m[i][1], q[i]] for i in range(3)]) / D


def _consistent(cid, simlab_value, oracle_value, rel=1e-6, abs_=1e-9):
    if simlab_value is None or oracle_value is None:
        return _check(cid, False, f"SIMLAB measurement {simlab_value} or trace recomputation {oracle_value} missing")
    ok = abs(simlab_value - oracle_value) <= max(abs_, rel * abs(oracle_value))
    return _check(cid, ok, f"SIMLAB measurement {simlab_value:.12g} vs oracle recomputation from the trace {oracle_value:.12g}")

import json as _json
from pathlib import Path as _Path


def _reference(name):
    return _json.loads((_Path(__file__).resolve().parent / "referee" / name).read_text())


def _interp(rows, t):
    lo, hi = 0, len(rows) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if rows[mid][0] <= t:
            lo = mid
        else:
            hi = mid
    a, b = rows[lo], rows[hi]
    if b[0] == a[0]:
        return a[1], a[2]
    f = (t - a[0]) / (b[0] - a[0])
    return a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2])


def _evaluate(evidence, v, criteria):
    res, t, ex = _executed(evidence)
    checks = [ex]
    metrics = {"primary_metric": "max absolute angle error vs reference (rad)", "tolerance": v["tolerance_angle_rad"]}
    if t is None:
        return {"checks": checks, "metrics": metrics, "critical_violations": []}
    ref = _reference(v["reference"])["rows"]  # (t, phi1, phi2) absolute angles, independent RK4
    q1, q2 = _rows(evidence, "qpos:j1"), _rows(evidence, "qpos:j2")
    if not q1 or not q2:
        checks.append(_unavailable("trajectory", "joint angle traces missing"))
        return {"checks": checks, "metrics": metrics, "critical_violations": []}
    worst = 0.0
    n = 0
    for r1, r2 in zip(q1, q2):
        if r1[0] > v["horizon_s"] + 1e-9:
            break
        p1, p2 = _interp(ref, r1[0])
        worst = max(worst, abs(r1[1] - p1), abs(r1[1] + r2[1] - p2))
        n += 1
    metrics.update(primary_value=worst, samples=n)
    checks.append(_check("trajectory", n > 100 and worst <= v["tolerance_angle_rad"], f"max angle error {worst:.3e} rad over {n} samples to {v['horizon_s']} s (tolerance {v['tolerance_angle_rad']})"))
    drift = (t.get("measurements") or {}).get("energy_drift")
    if drift is None:
        checks.append(_check("energy-bounded", False, "no energy measurement"))
    else:
        metrics["energy_relative_drift"] = drift
        checks.append(_check("energy-bounded", drift <= v["tolerance_energy_rel"], f"energy relative drift {drift:.3e} (tolerance {v['tolerance_energy_rel']})"))
    moved = max(abs(r[1] - q1[0][1]) for r in q1)
    checks.append(_check("moves", moved > 0.1, f"first joint moved {moved:.3g} rad (a frozen simulation does not)"))
    return {"checks": checks, "metrics": metrics, "critical_violations": []}


def evaluate(evidence, criteria):
    variant = criteria["variants"].get(evidence.get("variant_id"))
    if variant is None:
        return {"checks": [_unavailable("variant", f"unknown variant {evidence.get('variant_id')!r}")], "metrics": {}, "critical_violations": []}
    return _evaluate(evidence, variant, criteria)
