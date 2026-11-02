"""SIMLAB-Bench f1-tb01-pendulum oracle (TB-01). Standard library only; independent of SIMLAB code."""

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

def _agm(a, b):
    for _ in range(60):
        a, b = (a + b) / 2.0, math.sqrt(a * b)
    return a


def reference_period(L, g, theta0, model):
    if model == "small_angle":
        return 2 * math.pi * math.sqrt(L / g)
    k = math.sin(theta0 / 2.0)
    K = math.pi / (2.0 * _agm(1.0, math.sqrt(1.0 - k * k)))
    return 4.0 * math.sqrt(L / g) * K


def _evaluate(evidence, v, criteria):
    res, t, ex = _executed(evidence)
    checks = [ex]
    metrics = {"primary_metric": "period relative error", "tolerance": v["tolerance_rel"]}
    if t is None:
        return {"checks": checks, "metrics": metrics, "critical_violations": []}
    ref = reference_period(v["L"], criteria["g"], v["theta0"], v["model"])
    meas = (t.get("measurements") or {}).get("period")
    rows = _rows(evidence, "qpos:hinge")
    if meas is None:
        checks.append(_check("known-answer", False, "no period measurement"))
    else:
        err = _rel(meas, ref)
        metrics.update(primary_value=err, measured=meas, reference=ref)
        checks.append(_check("known-answer", err <= v["tolerance_rel"], f"period {meas:.9g} s vs {v['model']} reference {ref:.9g} s: relative error {err:.3e} (tolerance {v['tolerance_rel']})"))
    if rows is None:
        checks.append(_unavailable("measurement-matches-trace", "qpos:hinge trace missing"))
    else:
        c = _crossings(rows, 1, 0.0, "up")
        mine = (c[-1] - c[0]) / (len(c) - 1) if len(c) >= 2 else None
        checks.append(_consistent("measurement-matches-trace", meas, mine))
    return {"checks": checks, "metrics": metrics, "critical_violations": []}


def evaluate(evidence, criteria):
    variant = criteria["variants"].get(evidence.get("variant_id"))
    if variant is None:
        return {"checks": [_unavailable("variant", f"unknown variant {evidence.get('variant_id')!r}")], "metrics": {}, "critical_violations": []}
    return _evaluate(evidence, variant, criteria)
