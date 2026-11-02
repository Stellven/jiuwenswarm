"""SIMLAB-Bench f1-tb04-collision oracle (TB-04). Standard library only; independent of SIMLAB code."""

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

def restitution(k, b):
    """Linear spring-dashpot contact with force-based separation (Schwager and Poeschel, Granular Matter 2007)."""
    beta = b / 2.0
    if beta == 0:
        return 1.0
    w = math.sqrt(k - beta * beta)
    if beta < math.sqrt(k / 2.0):
        return math.exp(-(beta / w) * (math.pi - math.atan(2 * beta * w / (w * w - beta * beta))))
    return math.exp(-(beta / w) * math.atan(2 * beta * w / (beta * beta - w * w)))


def _evaluate(evidence, v, criteria):
    res, t, ex = _executed(evidence)
    checks = [ex]
    e_ref = restitution(v["k"], v["b"])
    metrics = {"primary_metric": "restitution absolute error", "tolerance": v["tolerance_e"]}
    if t is None:
        return {"checks": checks, "metrics": metrics, "critical_violations": []}
    m = t.get("measurements") or {}
    e, drift = m.get("restitution"), m.get("momentum_drift")
    if e is None:
        checks.append(_check("known-answer-restitution", False, "no restitution measurement (no collision observed)"))
    else:
        metrics.update(primary_value=abs(e - e_ref), measured=e, reference=e_ref)
        checks.append(_check("known-answer-restitution", abs(e - e_ref) <= v["tolerance_e"], f"velocity ratio {e:.6g} vs contact-model restitution {e_ref:.6g} (tolerance {v['tolerance_e']})"))
    if drift is None:
        checks.append(_check("momentum-conserved", False, "no momentum measurement"))
    else:
        metrics["momentum_relative_drift"] = drift
        checks.append(_check("momentum-conserved", drift <= v["tolerance_momentum"], f"momentum relative drift {drift:.3e} (tolerance {v['tolerance_momentum']})"))
    ra, rb = _rows(evidence, "qvel:ja"), _rows(evidence, "qvel:jb")
    if ra and rb:
        p0 = v["m1"] * ra[0][1] + v["m2"] * rb[0][1]
        p1 = v["m1"] * ra[-1][1] + v["m2"] * rb[-1][1]
        checks.append(_check("momentum-from-trace", abs(p1 - p0) <= v["tolerance_momentum"] * abs(p0), f"oracle: p0 {p0:.12g}, p_end {p1:.12g}"))
        ev_ = evidence.get("events") or []
        tb = sorted(x["t"] for x in ev_ if x.get("event_id") == "touch")
        te = sorted(x["t"] for x in ev_ if x.get("event_id") == "release")
        if tb and te and len(ra) == len(rb):
            before = [i for i, r in enumerate(ra) if r[0] <= tb[0]]
            after = [i for i, r in enumerate(ra) if r[0] >= te[0]]
            vr0 = ra[before[-1]][1] - rb[before[-1]][1] if before else 0
            vr1 = ra[after[0]][1] - rb[after[0]][1] if after else None
            mine = -vr1 / vr0 if vr0 and vr1 is not None else None
            checks.append(_consistent("measurement-matches-trace", e, mine, rel=1e-9))
        else:
            checks.append(_unavailable("measurement-matches-trace", "contact events missing from the evidence"))
    else:
        checks.append(_unavailable("measurement-matches-trace", "velocity traces missing"))
    return {"checks": checks, "metrics": metrics, "critical_violations": []}


def evaluate(evidence, criteria):
    variant = criteria["variants"].get(evidence.get("variant_id"))
    if variant is None:
        return {"checks": [_unavailable("variant", f"unknown variant {evidence.get('variant_id')!r}")], "metrics": {}, "critical_violations": []}
    return _evaluate(evidence, variant, criteria)
