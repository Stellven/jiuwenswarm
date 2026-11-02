"""SIMLAB-Bench f1-tb09-determinism oracle (TB-09). Standard library only; independent of SIMLAB code."""

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

def _digests(summary):
    return [[a.get("state_digest") for a in t.get("attempts", [])] for t in (summary or {}).get("trials", [])]


def _values(summary):
    return [t.get("measurements") for t in (summary or {}).get("trials", [])]


def _evaluate(evidence, v, criteria):
    res, t, ex = _executed(evidence)
    checks = [ex]
    metrics = {"primary_metric": "identity (all comparisons bitwise equal)", "tolerance": "identity"}
    if t is None:
        return {"checks": checks, "metrics": metrics, "critical_violations": []}
    second, replay = evidence.get("second_run"), evidence.get("replay")
    d0 = _digests(res)
    if not d0 or any(None in x for x in d0):
        checks.append(_unavailable("digests", "state digests missing"))
    if second is None:
        checks.append(_unavailable("repeat-identical", "no second run"))
    else:
        checks.append(_check("repeat-identical", _digests(second) == d0 and _values(second) == _values(res),
                             f"second execution {second.get('run_id')}: trajectories and measurements {'equal' if _digests(second) == d0 else 'differ'}"))
    if replay is None:
        checks.append(_unavailable("replay-identical", "no replay"))
    else:
        own = next((c for c in replay.get("checks", []) if c.get("check_id") == "replay_identity"), None)
        same = _digests(replay) == d0 and _values(replay) == _values(res)
        checks.append(_check("replay-identical", same and replay.get("run_kind") == "replay", f"replay {replay.get('run_id')} kind {replay.get('run_kind')}: {'equal' if same else 'differs'} (SIMLAB's own replay_identity check: {own and own.get('status')})"))
    if criteria.get("checkpoint_required"):
        a, b = evidence.get("original_after_checkpoint") or {}, evidence.get("branch_after_checkpoint") or {}
        sig = v.get("compare_signal") or criteria["compare_signal"]
        if not a.get(sig) or not b.get(sig):
            checks.append(_unavailable("restore-continue", "continuation traces missing"))
        else:
            checks.append(_check("restore-continue", a[sig] == b[sig] and len(a[sig]) > 10,
                                 f"{len(a[sig])} samples after the checkpoint at t={(evidence.get('checkpoint') or {}).get('time_s')}: {'bitwise equal' if a[sig] == b[sig] else 'different'}"))
    metrics["primary_value"] = all(c["status"] == "pass" for c in checks)
    return {"checks": checks, "metrics": metrics, "critical_violations": []}


def evaluate(evidence, criteria):
    variant = criteria["variants"].get(evidence.get("variant_id"))
    if variant is None:
        return {"checks": [_unavailable("variant", f"unknown variant {evidence.get('variant_id')!r}")], "metrics": {}, "critical_violations": []}
    return _evaluate(evidence, variant, criteria)
