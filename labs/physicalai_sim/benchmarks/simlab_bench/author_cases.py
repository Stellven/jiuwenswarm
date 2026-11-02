"""Author the SIMLAB-Bench F1 and F5 phase 1 cases (PAS-M1-001 B12, T034 to T038).

    python benchmarks/simlab_bench/author_cases.py          # writes cases/<id>/ (refuses to overwrite a frozen release's files)

Each case follows the Harbor authoring contract (benchmarks/harbor_suite/AUTHORING.md):
case.json, public/ (scene, experiment template, components), referee/criteria.json
(expected values and frozen tolerances, each with its reason; [confirm] where the
source gives none), a stdlib-only oracle.py, test_oracle.py and README.md.
Expected values live only in referee/; experiments carry no known-answer check (B12).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases"
G = 9.81
CFG = {"engine": "mujoco", "solver": "Newton", "iterations": 100, "tolerance": 1e-10}


def header(objective, arms, *, kind="claim_test", config=None, seed=1, replicates=1, factors=None, conditions=None, rvs=None,
           limits=None, origin="SIMLAB test plan"):
    return {"objective": objective, "objective_kind": kind, "arms": arms, "resolved_configuration": {**CFG, **(config or {})},
            "design": {"factors": factors or [], "conditions": conditions or [], "replicates": replicates, "episodes": 1,
                       "randomness": {"seed_policy": "derived", "base_seed": seed, "random_variables": rvs or []}},
            "limits": limits or {"max_sim_time_s": 60, "max_wall_s": 600},
            "protocol_items": [{"item_id": "arms", "item_kind": "arm", "value": [a["arm_id"] for a in arms], "origin": origin},
                               {"item_id": "trials", "item_kind": "trial_count", "value": replicates, "origin": origin}]}


def arm(scene="scene.xml", params=None, controller=None, arm_id="sim", role="baseline"):
    comps = [{"extension_point": "scene", "artifact": scene}]
    if controller:
        comps.append({"extension_point": "controller", "artifact": controller})
    return {"arm_id": arm_id, "role": role, "components": comps, "params": params or {}}


def tm(mid, kind, signal=None, unit="", required=True, **kw):
    d = {"kind": kind, **({"signal": signal} if signal else {}), **kw}
    return {"measurement_id": mid, "scope": "trial", "unit": unit, "required": required, "definition": d}


# =========================================================================== oracle building blocks (stdlib only)
COMMON = r'''
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
'''

ORACLE_TAIL = '''

def evaluate(evidence, criteria):
    variant = criteria["variants"].get(evidence.get("variant_id"))
    if variant is None:
        return {"checks": [_unavailable("variant", f"unknown variant {evidence.get('variant_id')!r}")], "metrics": {}, "critical_violations": []}
    return _evaluate(evidence, variant, criteria)
'''

ORACLES = {}

ORACLES["tb01"] = r'''
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
'''

ORACLES["tb02"] = r'''
def _evaluate(evidence, v, criteria):
    res, t, ex = _executed(evidence)
    checks = [ex]
    metrics = {"primary_metric": "fall distance relative error", "tolerance": v["tolerance_rel"]}
    if t is None:
        return {"checks": checks, "metrics": metrics, "critical_violations": []}
    ref = -0.5 * v["g"] * v["t"] ** 2
    meas = (t.get("measurements") or {}).get("drop")
    if meas is None:
        checks.append(_check("known-answer", False, "no drop measurement"))
    else:
        err = _rel(meas, ref)
        metrics.update(primary_value=err, measured=meas, reference=ref)
        checks.append(_check("known-answer", err <= v["tolerance_rel"], f"displacement {meas:.9g} m vs -g t^2/2 = {ref:.9g} m: relative error {err:.3e} (tolerance {v['tolerance_rel']})"))
    rows = _rows(evidence, "xpos:ball")
    if rows is None:
        checks.append(_unavailable("measurement-matches-trace", "xpos:ball trace missing"))
    else:
        checks.append(_consistent("measurement-matches-trace", meas, rows[-1][3] - rows[0][3]))
        checks.append(_check("duration", abs(rows[-1][0] - v["t"]) < 1e-9, f"trace ends at t={rows[-1][0]:.9g} s (declared {v['t']} s)"))
    return {"checks": checks, "metrics": metrics, "critical_violations": []}
'''

ORACLES["tb03"] = r'''
def _evaluate(evidence, v, criteria):
    res, t, ex = _executed(evidence)
    checks = [ex]
    g, th, mu = criteria["g"], math.radians(v["theta_deg"]), v["mu"]
    slides = math.tan(th) > mu
    metrics = {"primary_metric": "acceleration relative error" if slides else "displacement while sticking (m)",
               "tolerance": v["tolerance_rel"] if slides else v["tolerance_stick_m"]}
    if t is None:
        return {"checks": checks, "metrics": metrics, "critical_violations": []}
    m = t.get("measurements") or {}
    rows = _rows(evidence, "xipos:block")
    if slides:
        ref = g * (math.sin(th) - mu * math.cos(th))
        a = m.get("accel")
        if a is None:
            checks.append(_check("known-answer", False, "no acceleration measurement"))
        else:
            err = _rel(a, ref)
            metrics.update(primary_value=err, measured=a, reference=ref)
            checks.append(_check("known-answer", err <= v["tolerance_rel"], f"slides (tan th {math.tan(th):.4f} > mu {mu}): a {a:.6g} vs g(sin th - mu cos th) {ref:.6g}: relative error {err:.3e} (tolerance {v['tolerance_rel']})"))
        mine = _quad_accel(rows, 1, v["t_start"], v["t_end"]) if rows else None
        checks.append(_consistent("measurement-matches-trace", a, mine, rel=1e-6, abs_=1e-9) if rows else _unavailable("measurement-matches-trace", "trace missing"))
    else:
        dx = m.get("travel")
        if dx is None:
            checks.append(_check("known-answer", False, "no travel measurement"))
        else:
            metrics.update(primary_value=abs(dx), measured=dx, reference=0.0)
            checks.append(_check("known-answer", abs(dx) <= v["tolerance_stick_m"], f"sticks (tan th {math.tan(th):.4f} <= mu {mu}): travel {dx:.3e} m (tolerance {v['tolerance_stick_m']} m)"))
        if rows:
            w = [r for r in rows if v["t_start"] - 1e-12 <= r[0] <= v["t_end"] + 1e-12]
            checks.append(_consistent("measurement-matches-trace", dx, w[-1][1] - w[0][1], rel=1e-6, abs_=1e-12))
        else:
            checks.append(_unavailable("measurement-matches-trace", "trace missing"))
    return {"checks": checks, "metrics": metrics, "critical_violations": []}
'''

ORACLES["tb04"] = r'''
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
'''

ORACLES["tb05"] = r'''
def _evaluate(evidence, v, criteria):
    res, t, ex = _executed(evidence)
    checks = [ex]
    m_, k, c = v["m"], v["k"], v["c"]
    sigma = c / (2 * m_)
    wd = math.sqrt(k / m_ - sigma * sigma)
    Td = 2 * math.pi / wd
    metrics = {"primary_metric": "max relative error of period and decay rate", "tolerance": v["tolerance_rel"]}
    if t is None:
        return {"checks": checks, "metrics": metrics, "critical_violations": []}
    meas = t.get("measurements") or {}
    T, s = meas.get("period"), meas.get("decay")
    errs = []
    for name, got, ref in (("period", T, Td), ("decay-rate", s, sigma)):
        if got is None:
            checks.append(_check(f"known-answer-{name}", False, f"no {name} measurement"))
            continue
        e = _rel(got, ref)
        errs.append(e)
        metrics[f"{name}_measured"], metrics[f"{name}_reference"] = got, ref
        checks.append(_check(f"known-answer-{name}", e <= v["tolerance_rel"], f"{name} {got:.9g} vs closed form {ref:.9g}: relative error {e:.3e} (tolerance {v['tolerance_rel']})"))
    if errs:
        metrics["primary_value"] = max(errs)
    rows = _rows(evidence, "qpos:s")
    if rows:
        cr = _crossings(rows, 1, 0.0, "up")
        mine = (cr[-1] - cr[0]) / (len(cr) - 1) if len(cr) >= 2 else None
        checks.append(_consistent("measurement-matches-trace", T, mine))
    else:
        checks.append(_unavailable("measurement-matches-trace", "qpos:s trace missing"))
    return {"checks": checks, "metrics": metrics, "critical_violations": []}
'''

ORACLES["tb06"] = r'''
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
'''

ORACLES["tb07"] = r'''
def _evaluate(evidence, v, criteria):
    res, t, ex = _executed(evidence)
    checks = [ex]
    th = math.radians(v["theta_deg"])
    ref = criteria["g"] * math.sin(th) / (1.0 + v["inertia_ratio"])
    metrics = {"primary_metric": "acceleration relative error", "tolerance": v["tolerance_rel"]}
    if t is None:
        return {"checks": checks, "metrics": metrics, "critical_violations": []}
    a = (t.get("measurements") or {}).get("accel")
    if a is None:
        checks.append(_check("known-answer", False, "no acceleration measurement"))
    else:
        err = _rel(a, ref)
        metrics.update(primary_value=err, measured=a, reference=ref)
        checks.append(_check("known-answer", err <= v["tolerance_rel"], f"a {a:.6g} vs g sin th / (1 + I/mr^2) = {ref:.6g} (I/mr^2 = {v['inertia_ratio']:.6g}): relative error {err:.3e} (tolerance {v['tolerance_rel']})"))
    rows = _rows(evidence, "xipos:roller")
    checks.append(_consistent("measurement-matches-trace", a, _quad_accel(rows, 1, v["t_start"], v["t_end"])) if rows else _unavailable("measurement-matches-trace", "trace missing"))
    return {"checks": checks, "metrics": metrics, "critical_violations": []}
'''

ORACLES["tb08"] = r'''
def _evaluate(evidence, v, criteria):
    res, t, ex = _executed(evidence)
    checks = [ex]
    W = criteria["g"] * sum(v["masses"])
    metrics = {"primary_metric": "floor contact force relative error", "tolerance": v["tolerance_force_rel"]}
    if t is None:
        return {"checks": checks, "metrics": metrics, "critical_violations": []}
    m = t.get("measurements") or {}
    f, drift, pen = m.get("floor_force"), m.get("top_drift"), m.get("penetration")
    if f is None:
        checks.append(_check("forces-balance-gravity", False, "no floor force measurement"))
    else:
        err = _rel(f, W)
        metrics.update(primary_value=err, measured=f, reference=W)
        checks.append(_check("forces-balance-gravity", err <= v["tolerance_force_rel"], f"floor normal force {f:.6g} N vs total weight {W:.6g} N: relative error {err:.3e} (tolerance {v['tolerance_force_rel']})"))
    checks.append(_check("stays-still", drift is not None and drift <= v["tolerance_still_m"], f"top box height range after settling {drift} m (tolerance {v['tolerance_still_m']})"))
    checks.append(_check("penetration-bounded", pen is not None and pen <= v["tolerance_penetration_m"], f"max penetration {pen} m (tolerance {v['tolerance_penetration_m']})"))
    rows = _rows(evidence, "contact:normal_force:floor:g1")
    checks.append(_consistent("measurement-matches-trace", f, rows[-1][1]) if rows else _unavailable("measurement-matches-trace", "force trace missing"))
    return {"checks": checks, "metrics": metrics, "critical_violations": []}
'''

ORACLES["determinism"] = r'''
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
'''


# =========================================================================== oracle tests (unittest, stdlib)
def oracle_test(case_id, good, bad, extra=""):
    return f'''"""Oracle unit tests for {case_id}: correct evidence passes, defective evidence fails, missing evidence never passes."""
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("oracle_{case_id.replace('-', '_')}", HERE / "oracle.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
CRITERIA = json.loads((HERE / "referee" / "criteria.json").read_text())


def status(g):
    return {{c["id"]: c["status"] for c in g["checks"]}}


class OracleTests(unittest.TestCase):
    def test_correct_passes(self):
        g = oracle.evaluate({good}, CRITERIA)
        self.assertTrue(all(s == "pass" for s in status(g).values()), g)

    def test_defective_fails(self):
        g = oracle.evaluate({bad}, CRITERIA)
        self.assertIn("fail", status(g).values(), g)

    def test_missing_evidence_never_passes(self):
        for ev in ({{"variant_id": next(iter(CRITERIA["variants"]))}}, {{"variant_id": "nope"}}):
            g = oracle.evaluate(ev, CRITERIA)
            self.assertFalse(g["checks"] and all(c["status"] == "pass" for c in g["checks"]), g)

    def test_stdlib_only(self):
        import ast, sys
        tree = ast.parse((HERE / "oracle.py").read_text())
        mods = {{(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}} | {{
            a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}}
        self.assertTrue(mods <= set(sys.stdlib_module_names) | {{""}}, mods)
{extra}

if __name__ == "__main__":
    unittest.main()
'''


def result_ev(variant, measurements, traces, status="COMPLETED"):
    return {"variant_id": variant, "execution": {"status": status},
            "result": {"run_id": "run-x", "status": status, "trials": [{"attempts": [{"status": status, "state_digest": "a" * 64}],
                                                                         "measurements": measurements}]},
            "traces": traces}


def write_case(cid, *, family, tb_id, title, objective, metric, references, model_assumptions, procedure_kind, scene, experiment,
               variants, criteria, oracle, good, bad, components=None, extra_files=None, extra_tests="", readme_extra=""):
    d = CASES / cid
    (d / "public").mkdir(parents=True, exist_ok=True)
    (d / "referee").mkdir(parents=True, exist_ok=True)
    import mujoco  # noqa: PLC0415

    case = {"schema": "simlab-bench-case:1", "id": cid, "family": family, "tb_id": tb_id, "title": title, "milestone": "PAS-M1",
            "phase": 1, "classification": "phase1_exit", "requirements": ["B01", "B02", "B03", "B05", "B08", "B12", "B17"],
            "objective": objective, "primary_metric": metric, "procedure_kind": procedure_kind,
            "engine": {"mujoco": mujoco.__version__}, "references": references, "model_assumptions": model_assumptions,
            "budgets": {"wall_time_s": 600, "physical_memory_mb": 1024, "gpu_required": False, "max_model_calls": 0},
            "inputs": [{"path": "public/" + scene[0], "kind": "model_file"}, {"path": "public/experiment.json", "kind": "experiment_template"}],
            "variants": variants, "oracle_version": "1",
            "grading": "referee/criteria.json via oracle.py (stdlib only, run in a separate isolated interpreter)"}
    (d / "case.json").write_text(json.dumps(case, indent=1) + "\n")
    (d / "public" / scene[0]).write_text(scene[1])
    (d / "public" / "experiment.json").write_text(json.dumps(experiment, indent=1) + "\n")
    for name, text in (components or {}).items():
        (d / "public" / name).write_text(text)
    for name, text in (extra_files or {}).items():
        (d / name).write_text(text)
    (d / "referee" / "criteria.json").write_text(json.dumps(criteria, indent=1) + "\n")
    (d / "oracle.py").write_text(f'"""SIMLAB-Bench {cid} oracle ({tb_id}). Standard library only; independent of SIMLAB code."""\n' + COMMON + oracle + ORACLE_TAIL)
    (d / "test_oracle.py").write_text(oracle_test(cid, good, bad, extra_tests))
    tol_lines = []
    for vid, vv in criteria["variants"].items():
        tl = {k: v for k, v in vv.items() if k.startswith("tolerance")}
        tol_lines.append(f"| {vid} | {', '.join(f'{k} = {v}' for k, v in tl.items())} | {vv.get('tolerance_reason', '')} | {vv.get('confirm', False)} |")
    readme = [f"# {cid}: {title} ({tb_id})", "", objective, "", f"**Family:** {family}. **Procedure:** {procedure_kind}. **Engine:** MuJoCo {mujoco.__version__} (pinned; a version change forces a rerun, the release manifest records it).", "",
              "**Known answer and model assumptions:** " + model_assumptions, "", "**Adopted references (test plan, Official external benchmarks, phase 1):**"]
    readme += [f"- {r}" for r in references]
    readme += ["", "**Variants** (all development split; held-out material is never in this repository):", ""]
    readme += [f"- `{v['id']}`: {v['task']}" + (" Negative control: the oracle must report a failure." if v.get("negative_control") else "") for v in variants]
    readme += ["", "**Frozen tolerances** (referee/criteria.json; `[confirm]` = proposed by the coding agent with this reason, owner confirmation pending, spec Clarifications 2026-10-30):", "",
               "| Variant | Tolerance | Reason | [confirm] |", "|---|---|---|---|", *tol_lines, "", readme_extra,
               "The oracle grades SIMLAB's own records: the measurement it reports and the raw trace, which the oracle recomputes independently. Missing evidence never passes."]
    (d / "README.md").write_text("\n".join(readme) + "\n")


# =========================================================================== cases
def pendulum_case():
    scene = ("scene.xml", """<mujoco model="tb01-pendulum">
  <worldbody>
    <body name="bob" pos="0 0 0">
      <joint name="hinge" type="hinge" axis="0 1 0"/>
      <inertial pos="0 0 -${L}" mass="1" diaginertia="1e-9 1e-9 1e-9"/>
    </body>
  </worldbody>
</mujoco>
""")
    exp = {"scene": "scene.xml", "engine_why": "MuJoCo is the admitted executor; a rigid hinge with a point mass is the textbook pendulum",
           "header": header("Measure the pendulum period for small and large swings", [arm(params={"L": 1.0, "theta0": 0.05})],
                            config={"timestep": 0.0002, "integrator": "RK4"}, origin="SIMLAB test plan TB-01"),
           "procedure": {"steps": [{"step_id": "swing", "duration_s": 13.0}], "initial_state": {"qpos": {"hinge": "${theta0}"}}},
           "measurements": [tm("period", "period", "qpos:hinge", "s", direction="up")],
           "observations": [{"signal": "qpos:hinge", "unit": "rad", "rate_hz": 2500}]}
    variants = [{"id": "small-swing", "split": "development", "task": "Point-mass pendulum, length 1.0 m, released from 0.05 rad.",
                 "params": {"L": 1.0, "theta0": 0.05}, "seed": 1},
                {"id": "large-swing-1p2", "split": "development", "task": "Length 0.8 m, released from 1.2 rad.", "params": {"L": 0.8, "theta0": 1.2}, "seed": 2},
                {"id": "large-swing-2p6", "split": "development", "task": "Length 1.2 m, released from 2.6 rad.", "params": {"L": 1.2, "theta0": 2.6}, "seed": 3}]
    reason = "Test plan TB-01 gives 0.5% ([confirm] value in the source, TASKS §6 Q-01)."
    crit = {"g": G, "traces": ["qpos:hinge"], "variants": {
        "small-swing": {"L": 1.0, "theta0": 0.05, "model": "small_angle", "tolerance_rel": 0.005, "tolerance_reason": reason + " The small-angle formula itself differs from the exact period by theta0^2/16 = 0.016% here.", "confirm": True},
        "large-swing-1p2": {"L": 0.8, "theta0": 1.2, "model": "elliptic", "tolerance_rel": 0.005, "tolerance_reason": reason, "confirm": True},
        "large-swing-2p6": {"L": 1.2, "theta0": 2.6, "model": "elliptic", "tolerance_rel": 0.005, "tolerance_reason": reason, "confirm": True}}}
    T = 2 * math.pi * math.sqrt(1.0 / G)
    rows = [[i * 0.01, 0.05 * math.sin(2 * math.pi * i * 0.01 / T)] for i in range(1300)]
    good = repr(result_ev("small-swing", {"period": (lambda c: (c[-1] - c[0]) / (len(c) - 1))(_cr(rows))}, {"qpos:hinge": rows}))
    bad = repr(result_ev("small-swing", {"period": T * 1.02}, {"qpos:hinge": [[r[0], 0.05 * math.sin(2 * math.pi * r[0] / (T * 1.02))] for r in rows]}))
    write_case("f1-tb01-pendulum", family="F1", tb_id="TB-01", title="Pendulum, small and large swing", objective=exp["header"]["objective"],
               metric={"name": "period relative error", "definition": "|T_measured - T_reference| / T_reference; reference 2 pi sqrt(L/g) (small) or 4 sqrt(L/g) K(sin(theta0/2)) (large)"},
               references=["arXiv 2603.14634, analytic pendulum test (the seven analytic tests)", "MuJoCo engine tests (hinge dynamics)", "Elliptic integral K by the arithmetic-geometric mean (Abramowitz and Stegun 17.6)"],
               model_assumptions="point mass (inertia 1e-9) on a massless rigid rod, no damping, no contact, g = 9.81 m/s^2, RK4 with 0.2 ms steps, period = mean interval between upward zero crossings over 13 s.",
               procedure_kind="single_run", scene=scene, experiment=exp, variants=variants, criteria=crit, oracle=ORACLES["tb01"], good=good, bad=bad)


def _cr(rows):
    out = []
    for i in range(len(rows) - 1):
        a, b = rows[i][1], rows[i + 1][1]
        if a < 0 <= b:
            out.append(rows[i][0] + a / (a - b) * (rows[i + 1][0] - rows[i][0]))
    return out


def freefall_case():
    scene = ("scene.xml", """<mujoco model="tb02-free-fall">
  <worldbody>
    <body name="ball" pos="0 0 10">
      <freejoint name="free"/>
      <geom name="ball_geom" type="sphere" size="0.05" mass="1" contype="0" conaffinity="0"/>
    </body>
  </worldbody>
</mujoco>
""")
    exp = {"scene": "scene.xml", "engine_why": "MuJoCo is the admitted executor; a free body under uniform gravity",
           "header": header("Measure free-fall distance against g t^2 / 2", [arm()], config={"timestep": 0.001, "integrator": "RK4"},
                            origin="SIMLAB test plan TB-02"),
           "procedure": {"steps": [{"step_id": "fall", "duration_s": 1.0}]},
           "measurements": [tm("drop", "displacement", "xpos:ball", "m", component=2)],
           "observations": [{"signal": "xpos:ball", "unit": "m"}]}
    variants = [{"id": "earth-1s", "split": "development", "task": "Drop for 1.0 s at g = 9.81 m/s^2 (RK4, 1 ms).", "seed": 1},
                {"id": "moon-0p5s", "split": "development", "task": "Drop for 0.5 s at g = 1.62 m/s^2 (RK4, 1 ms).",
                 "config": {"gravity": [0, 0, -1.62]}, "procedure": {"steps": [{"step_id": "fall", "duration_s": 0.5}]}, "seed": 2},
                {"id": "earth-2s-euler", "split": "development", "task": "Drop for 2.0 s at g = 9.81 m/s^2 with semi-implicit Euler, 0.1 ms.",
                 "config": {"integrator": "Euler", "timestep": 0.0001}, "procedure": {"steps": [{"step_id": "fall", "duration_s": 2.0}]}, "seed": 3}]
    reason = "Test plan TB-02 gives 0.1%."
    crit = {"traces": ["xpos:ball"], "variants": {
        "earth-1s": {"g": 9.81, "t": 1.0, "tolerance_rel": 0.001, "tolerance_reason": reason, "confirm": False},
        "moon-0p5s": {"g": 1.62, "t": 0.5, "tolerance_rel": 0.001, "tolerance_reason": reason, "confirm": False},
        "earth-2s-euler": {"g": 9.81, "t": 2.0, "tolerance_rel": 0.001, "tolerance_reason": reason + " Semi-implicit Euler's error here is dt/t = 5e-5.", "confirm": False}}}
    rows = [[i * 0.001, 0, 0, 10 - 0.5 * 9.81 * (i * 0.001) ** 2] for i in range(1001)]
    good = repr(result_ev("earth-1s", {"drop": rows[-1][3] - rows[0][3]}, {"xpos:ball": rows}))
    bad = repr(result_ev("earth-1s", {"drop": -0.5 * 9.0 * 1.0}, {"xpos:ball": [[r[0], 0, 0, 10 - 0.5 * 9.0 * r[0] ** 2] for r in rows]}))
    write_case("f1-tb02-free-fall", family="F1", tb_id="TB-02", title="Free fall", objective=exp["header"]["objective"],
               metric={"name": "fall distance relative error", "definition": "|dz - (-g t^2/2)| / (g t^2/2)"},
               references=["arXiv 2603.14634, analytic free-fall test", "MuJoCo engine tests (free joint integration)"],
               model_assumptions="a free sphere with no contact (contype 0) under uniform gravity; displacement of the body origin from t = 0 to the declared time.",
               procedure_kind="single_run", scene=scene, experiment=exp, variants=variants, criteria=crit, oracle=ORACLES["tb02"], good=good, bad=bad,
               readme_extra="Each variant sets its own fall time through the procedure.")


def tilt(theta_deg, g=G):
    th = math.radians(theta_deg)
    return [round(g * math.sin(th), 12), 0.0, round(-g * math.cos(th), 12)]


def incline_case():
    scene = ("scene.xml", """<mujoco model="tb03-incline">
  <worldbody>
    <geom name="plane" type="plane" size="30 2 0.1" friction="${mu} 0 0"/>
    <body name="block" pos="0 0 0.02">
      <freejoint name="free"/>
      <geom name="block_geom" type="box" size="0.1 0.1 0.02" mass="1" friction="${mu} 0 0"/>
    </body>
  </worldbody>
</mujoco>
""")
    exp = {"scene": "scene.xml", "engine_why": "MuJoCo is the admitted executor; Coulomb friction on a plane",
           "header": header("Block on an incline: slides when tan theta > mu with a = g(sin theta - mu cos theta)", [arm(params={"mu": 0.2})],
                            config={"timestep": 0.0005, "integrator": "implicitfast", "cone": "elliptic", "impratio": 10, "gravity": tilt(30)},
                            origin="SIMLAB test plan TB-03; Drake inclined-plane test pattern"),
           "procedure": {"steps": [{"step_id": "release", "duration_s": 1.0}]},
           "measurements": [tm("accel", "fit_acceleration", "xipos:block", "m/s^2", component=0, t_start=0.1, t_end=1.0),
                            tm("travel", "displacement", "xipos:block", "m", component=0, t_start=0.1, t_end=1.0)],
           "observations": [{"signal": "xipos:block", "unit": "m", "rate_hz": 1000}]}
    variants = [{"id": "slide-30deg-mu0p2", "split": "development", "task": "30 degree incline (tilted gravity), friction 0.2.",
                 "params": {"mu": 0.2}, "config": {"gravity": tilt(30)}, "seed": 1},
                {"id": "slide-40deg-mu0p5", "split": "development", "task": "40 degree incline, friction 0.5.", "params": {"mu": 0.5}, "config": {"gravity": tilt(40)}, "seed": 2},
                {"id": "stick-20deg-mu0p5", "split": "development", "task": "20 degree incline, friction 0.5 (tan 20 = 0.364 < 0.5).",
                 "params": {"mu": 0.5}, "config": {"gravity": tilt(20)}, "seed": 3}]
    rs = ("Proposed 1% [confirm]. The source gives no tolerance (TP 'Test benches'). MuJoCo friction is a soft, regularized constraint "
          "(elliptic cone, impratio 10); exploratory runs on this build differed from the formula by at most 0.03%, so 1% leaves margin for "
          "solver settings while still failing a wrong friction law (a frictionless block would be off by more than 30%).")
    st = ("Proposed 1 mm over 0.9 s [confirm]. Soft contacts creep slightly while sticking (exploratory: 0.08 mm); a block that slid "
          "at these values would travel more than 0.1 m.")
    crit = {"g": G, "traces": ["xipos:block"], "variants": {
        "slide-30deg-mu0p2": {"theta_deg": 30, "mu": 0.2, "t_start": 0.1, "t_end": 1.0, "tolerance_rel": 0.01, "tolerance_stick_m": None, "tolerance_reason": rs, "confirm": True},
        "slide-40deg-mu0p5": {"theta_deg": 40, "mu": 0.5, "t_start": 0.1, "t_end": 1.0, "tolerance_rel": 0.01, "tolerance_stick_m": None, "tolerance_reason": rs, "confirm": True},
        "stick-20deg-mu0p5": {"theta_deg": 20, "mu": 0.5, "t_start": 0.1, "t_end": 1.0, "tolerance_rel": None, "tolerance_stick_m": 0.001, "tolerance_reason": st, "confirm": True}}}
    a = G * (math.sin(math.radians(30)) - 0.2 * math.cos(math.radians(30)))
    rows = [[i * 0.001, 0.5 * a * (i * 0.001) ** 2, 0, 0.02] for i in range(1001)]
    good = repr(result_ev("slide-30deg-mu0p2", {"accel": a, "travel": rows[-1][1] - rows[100][1]}, {"xipos:block": rows}))
    rows_bad = [[i * 0.001, 0.5 * (G * 0.5) * (i * 0.001) ** 2, 0, 0.02] for i in range(1001)]
    bad = repr(result_ev("slide-30deg-mu0p2", {"accel": G * 0.5, "travel": 1.0}, {"xipos:block": rows_bad}))
    write_case("f1-tb03-incline", family="F1", tb_id="TB-03", title="Block on an incline", objective=exp["header"]["objective"],
               metric={"name": "acceleration relative error (sliding) or travel while sticking", "definition": "|a - g(sin th - mu cos th)| / that value; or |travel| between 0.1 and 1.0 s"},
               references=["Drake inclined-plane and friction tests (pattern)", "ContactBench contact criteria (Coulomb law: stick inside the cone, slide on it)", "arXiv 2603.14634, analytic sliding test"],
               model_assumptions="flat box (0.2 x 0.2 x 0.04 m, 1 kg) on a plane with Coulomb friction mu on both geoms; the incline is represented by tilting gravity by theta (equivalent physics); acceleration from a quadratic fit of the box's centre of mass along the slope between 0.1 and 1.0 s.",
               procedure_kind="single_run", scene=scene, experiment=exp, variants=variants, criteria=crit, oracle=ORACLES["tb03"], good=good, bad=bad)


def collision_case():
    scene = ("scene.xml", """<mujoco model="tb04-collision">
  <default><geom condim="1" friction="0 0 0" solref="-${k} -${b}" solimp="0.9999 0.9999 0.001 0.5 2"/></default>
  <worldbody>
    <body name="a" pos="0 0 0"><joint name="ja" type="slide" axis="1 0 0"/><geom name="ga" type="sphere" size="0.05" mass="${m1}"/></body>
    <body name="b" pos="0.2 0 0"><joint name="jb" type="slide" axis="1 0 0"/><geom name="gb" type="sphere" size="0.05" mass="${m2}"/></body>
  </worldbody>
</mujoco>
""")
    exp = {"scene": "scene.xml", "engine_why": "MuJoCo is the admitted executor; a direct-stiffness contact sets the restitution",
           "header": header("1D collision: momentum is conserved and restitution sets the ratio of relative normal velocities",
                            [arm(params={"k": 1000000.0, "b": 0.0, "m1": 1.0, "m2": 1.0, "v1": 1.0})],
                            config={"timestep": 0.00001, "integrator": "RK4", "cone": "elliptic", "gravity": [0, 0, 0]},
                            origin="SIMLAB test plan TB-04"),
           "procedure": {"steps": [{"step_id": "collide", "duration_s": 0.3}], "initial_state": {"qvel": {"ja": "${v1}"}},
                         "events": [{"event_id": "touch", "kind": "contact_begin", "geoms": ["ga", "gb"]},
                                    {"event_id": "release", "kind": "contact_end", "geoms": ["ga", "gb"]}]},
           "measurements": [tm("restitution", "velocity_ratio_at_event", "qvel:ja", "1", signal_b="qvel:jb", event_id="touch", t_end_event="release", window_s=0.0),
                            tm("momentum_drift", "relative_drift", "momentum:total", "1", component=0)],
           "observations": [{"signal": "qvel:ja", "unit": "m/s"}, {"signal": "qvel:jb", "unit": "m/s"}, {"signal": "momentum:total", "unit": "kg m/s", "rate_hz": 10000}]}

    def zb(e, k=1e6):
        z = -math.log(e) / math.sqrt(math.pi ** 2 + math.log(e) ** 2)
        return round(2 * z * math.sqrt(k), 6)
    variants = [{"id": "elastic-1to1", "split": "development", "task": "Equal masses, undamped contact.", "params": {"k": 1e6, "b": 0.0, "m1": 1.0, "m2": 1.0, "v1": 1.0}, "seed": 1},
                {"id": "damped-1to3", "split": "development", "task": "Masses 1:3, damped contact.", "params": {"k": 1e6, "b": zb(0.5), "m1": 1.0, "m2": 3.0, "v1": 1.0}, "seed": 2},
                {"id": "damped-2to1", "split": "development", "task": "Masses 2:1, lightly damped contact.", "params": {"k": 1e6, "b": zb(0.8), "m1": 2.0, "m2": 1.0, "v1": 0.5}, "seed": 3}]
    re_ = ("Proposed 0.005 absolute [confirm]. The source gives none. The expected restitution comes from the contact law itself (linear "
           "spring-dashpot with force-based separation, Schwager and Poeschel 2007); MuJoCo's impedance 0.9999 and the step size leave a small "
           "residual (exploratory: up to 3e-4).")
    rm = "Proposed 1e-9 relative [confirm]: equal and opposite contact forces conserve momentum to rounding (exploratory 1e-15)."
    crit = {"traces": ["qvel:ja", "qvel:jb"], "variants": {
        v["id"]: {**v["params"], "tolerance_e": 0.005, "tolerance_momentum": 1e-9, "tolerance_reason": re_ + " " + rm, "confirm": True} for v in variants}}
    rows_a = [[0.0, 1.0], [0.3, 0.0]]
    rows_b = [[0.0, 0.0], [0.3, 1.0]]
    good = repr({**result_ev("elastic-1to1", {"restitution": 1.0, "momentum_drift": 1e-15}, {"qvel:ja": rows_a, "qvel:jb": rows_b}),
                 "events": [{"t": 0.1, "event_id": "touch", "kind": "contact_begin"}, {"t": 0.2, "event_id": "release", "kind": "contact_end"}]})
    bad = repr(result_ev("elastic-1to1", {"restitution": 0.7, "momentum_drift": 0.2}, {"qvel:ja": [[0.0, 1.0], [0.3, 0.1]], "qvel:jb": [[0.0, 0.0], [0.3, 0.8]]}))
    write_case("f1-tb04-collision", family="F1", tb_id="TB-04", title="1D collisions", objective=exp["header"]["objective"],
               metric={"name": "restitution absolute error", "definition": "|e_measured - e_contact_law|; plus momentum relative drift"},
               references=["ContactBench contact criteria (impulse balance, restitution)", "Acosta et al. impact data (phase 5 real-data follow-up)",
                           "Schwager T., Poeschel T., Coefficient of restitution and linear-dashpot model revisited, Granular Matter 9 (2007)"],
               model_assumptions="two spheres on frictionless slide joints with gravity off; contact stiffness k and damping b given directly (MuJoCo negative solref, per unit effective mass), impedance 0.9999; restitution measured as -(va - vb)after / (va - vb)before around the contact.",
               procedure_kind="single_run", scene=scene, experiment=exp, variants=variants, criteria=crit, oracle=ORACLES["tb04"], good=good, bad=bad)


def damped_case():
    scene = ("scene.xml", """<mujoco model="tb05-damped-oscillator">
  <worldbody>
    <body name="mass">
      <joint name="s" type="slide" axis="1 0 0" stiffness="${k}" damping="${c}"/>
      <geom type="sphere" size="0.05" mass="${m}" contype="0" conaffinity="0"/>
    </body>
  </worldbody>
</mujoco>
""")
    exp = {"scene": "scene.xml", "engine_why": "MuJoCo is the admitted executor; joint stiffness and damping are a linear oscillator",
           "header": header("Damped oscillator decay rate and frequency", [arm(params={"k": 100.0, "c": 1.0, "m": 1.0})],
                            config={"timestep": 0.0001, "integrator": "RK4", "gravity": [0, 0, 0]}, origin="SIMLAB test plan TB-05"),
           "procedure": {"steps": [{"step_id": "ring", "duration_s": 8.0}], "initial_state": {"qpos": {"s": 0.1}}},
           "measurements": [tm("period", "period", "qpos:s", "s", direction="up"), tm("decay", "decay_rate", "qpos:s", "1/s")],
           "observations": [{"signal": "qpos:s", "unit": "m", "rate_hz": 5000}]}
    variants = [{"id": "light-damping", "split": "development", "task": "m 1 kg, k 100 N/m, c 1 N s/m.", "params": {"k": 100.0, "c": 1.0, "m": 1.0}, "seed": 1},
                {"id": "medium-damping", "split": "development", "task": "m 2 kg, k 50 N/m, c 4 N s/m.", "params": {"k": 50.0, "c": 4.0, "m": 2.0}, "seed": 2},
                {"id": "stiff-light", "split": "development", "task": "m 0.5 kg, k 200 N/m, c 0.5 N s/m.", "params": {"k": 200.0, "c": 0.5, "m": 0.5}, "seed": 3}]
    rs = ("Proposed 0.5% [confirm], the same as the source's pendulum tolerance; the source gives none for TB-05. RK4 at 0.1 ms "
          "integrates this linear system far more accurately; peak and crossing interpolation at 5 kHz bound the measurement error.")
    crit = {"traces": ["qpos:s"], "variants": {v["id"]: {**v["params"], "tolerance_rel": 0.005, "tolerance_reason": rs, "confirm": True} for v in variants}}
    sig, wd = 0.5, math.sqrt(100 - 0.25)
    rows = [[i * 0.001, 0.1 * math.exp(-sig * i * 0.001) * math.cos(wd * i * 0.001)] for i in range(0, 8001, 4)]
    good = repr(result_ev("light-damping", {"period": (lambda c: (c[-1] - c[0]) / (len(c) - 1))(_cr(rows)), "decay": sig}, {"qpos:s": rows}))
    bad = repr(result_ev("light-damping", {"period": 2 * math.pi / 10 * 1.05, "decay": 0.0}, {"qpos:s": rows}))
    write_case("f1-tb05-damped-oscillator", family="F1", tb_id="TB-05", title="Damped oscillator", objective=exp["header"]["objective"],
               metric={"name": "max relative error of period and decay rate", "definition": "against T_d = 2 pi / sqrt(k/m - (c/2m)^2) and sigma = c / 2m"},
               references=["arXiv 2603.14634, analytic damped-oscillator test", "MuJoCo engine tests (passive joint stiffness and damping)"],
               model_assumptions="a mass on a slide joint with linear stiffness and viscous damping, no gravity, no contact; period from upward zero crossings, decay rate from a log-linear fit of the peaks.",
               procedure_kind="single_run", scene=scene, experiment=exp, variants=variants, criteria=crit, oracle=ORACLES["tb05"], good=good, bad=bad)


def double_pendulum_reference(m1, m2, L1, L2, p1, p2, horizon=2.0, dt=1e-5, every=100, g=G):
    """Independent fixed-step RK4 of the textbook double pendulum (point masses, massless rods), absolute angles."""
    def f(s):
        a1, a2, w1, w2 = s
        d = a1 - a2
        den = 2 * m1 + m2 - m2 * math.cos(2 * d)
        dw1 = (-g * (2 * m1 + m2) * math.sin(a1) - m2 * g * math.sin(a1 - 2 * a2) - 2 * math.sin(d) * m2 * (w2 * w2 * L2 + w1 * w1 * L1 * math.cos(d))) / (L1 * den)
        dw2 = (2 * math.sin(d) * (w1 * w1 * L1 * (m1 + m2) + g * (m1 + m2) * math.cos(a1) + w2 * w2 * L2 * m2 * math.cos(d))) / (L2 * den)
        return (w1, w2, dw1, dw2)
    s = (p1, p2, 0.0, 0.0)
    rows = [[0.0, p1, p2]]
    n = int(round(horizon / dt))
    for i in range(1, n + 1):
        k1 = f(s)
        k2 = f(tuple(x + dt / 2 * k for x, k in zip(s, k1)))
        k3 = f(tuple(x + dt / 2 * k for x, k in zip(s, k2)))
        k4 = f(tuple(x + dt * k for x, k in zip(s, k3)))
        s = tuple(x + dt / 6 * (a + 2 * b + 2 * c + e) for x, a, b, c, e in zip(s, k1, k2, k3, k4))
        if i % every == 0:
            rows.append([round(i * dt, 10), s[0], s[1]])
    return rows


def double_pendulum_case():
    scene = ("scene.xml", """<mujoco model="tb06-double-pendulum">
  <worldbody>
    <body name="upper" pos="0 0 0">
      <joint name="j1" type="hinge" axis="0 1 0" damping="${damping}"/>
      <inertial pos="0 0 -${L1}" mass="${m1}" diaginertia="1e-9 1e-9 1e-9"/>
      <body name="lower" pos="0 0 -${L1}">
        <joint name="j2" type="hinge" axis="0 1 0" damping="${damping}"/>
        <inertial pos="0 0 -${L2}" mass="${m2}" diaginertia="1e-9 1e-9 1e-9"/>
      </body>
    </body>
  </worldbody>
</mujoco>
""")
    base = {"m1": 1.0, "m2": 1.0, "L1": 1.0, "L2": 1.0, "q1": 0.8, "q2": 0.4, "damping": 0.0}
    exp = {"scene": "scene.xml", "engine_why": "MuJoCo is the admitted executor; two hinges with point masses are the textbook double pendulum",
           "header": header("Passive double pendulum: bounded energy error and agreement with a high-accuracy reference over a short horizon",
                            [arm(params=dict(base))], config={"timestep": 0.0001, "integrator": "RK4"}, origin="SIMLAB test plan TB-06"),
           "procedure": {"steps": [{"step_id": "swing", "duration_s": 2.0}], "initial_state": {"qpos": {"j1": "${q1}", "j2": "${q2}"}}},
           "measurements": [tm("energy_drift", "relative_drift", "energy:total", "1")],
           "observations": [{"signal": "qpos:j1", "unit": "rad", "rate_hz": 1000}, {"signal": "qpos:j2", "unit": "rad", "rate_hz": 1000},
                            {"signal": "energy:total", "unit": "J", "rate_hz": 1000}]}
    regular = [("swing-a", {"m1": 1.0, "m2": 1.0, "L1": 1.0, "L2": 1.0, "p1": 0.8, "p2": 1.2}, "Equal masses and lengths, released at 0.8 and 1.2 rad."),
               ("swing-b", {"m1": 1.0, "m2": 2.0, "L1": 1.0, "L2": 0.6, "p1": 1.5, "p2": 0.5}, "Masses 1 and 2 kg, lengths 1.0 and 0.6 m, released at 1.5 and 0.5 rad."),
               ("swing-c", {"m1": 2.0, "m2": 1.0, "L1": 0.7, "L2": 1.0, "p1": -0.5, "p2": 2.0}, "Masses 2 and 1 kg, lengths 0.7 and 1.0 m, released at -0.5 and 2.0 rad.")]
    variants, crit_v, extra = [], {}, {}
    ta = ("Proposed 1e-3 rad [confirm]: the source asks for agreement 'over a short horizon' without a number; RK4 at 0.1 ms agrees with "
          "the 0.01 ms reference to about 1e-7 rad over 2 s before chaotic growth, so 1e-3 rad fails a frozen, damped or wrongly coupled model by orders of magnitude.")
    te = "Proposed 1e-6 relative [confirm]: RK4 at 0.1 ms conserves energy far better on this passive system; an over-damped simulation loses most of it."
    for i, (vid, p, task) in enumerate(regular):
        params = {"m1": p["m1"], "m2": p["m2"], "L1": p["L1"], "L2": p["L2"], "q1": p["p1"], "q2": p["p2"] - p["p1"], "damping": 0.0}
        variants.append({"id": vid, "split": "development", "task": task + " MuJoCo's second angle is relative (q2 = phi2 - phi1).", "params": params, "seed": i + 1})
        ref_name = f"reference_{vid}.json"
        crit_v[vid] = {**p, "reference": ref_name, "horizon_s": 2.0, "tolerance_angle_rad": 1e-3, "tolerance_energy_rel": 1e-6,
                       "tolerance_reason": ta + " " + te, "confirm": True}
        extra[f"referee/{ref_name}"] = json.dumps({"method": "independent fixed-step RK4, dt 1e-5 s, pure Python (author_cases.py)",
                                                   "columns": ["t", "phi1", "phi2"], "rows": double_pendulum_reference(p["m1"], p["m2"], p["L1"], p["L2"], p["p1"], p["p2"])})
    p = regular[0][1]
    for vid, change, task in (("frozen-gravity-off", {"config": {"gravity": [0, 0, 0]}}, "Negative control: gravity off, so the pendulum stays frozen."),
                              ("over-damped", {"params_extra": {"damping": 5.0}}, "Negative control: heavy joint damping.")):
        params = {"m1": p["m1"], "m2": p["m2"], "L1": p["L1"], "L2": p["L2"], "q1": p["p1"], "q2": p["p2"] - p["p1"], "damping": 0.0,
                  **change.get("params_extra", {})}
        variants.append({"id": vid, "split": "development", "task": task, "params": params, "negative_control": True, "seed": 9,
                         **({"config": change["config"]} if "config" in change else {})})
        crit_v[vid] = {**crit_v["swing-a"], "tolerance_reason": "Negative control (test plan TB-06: a frozen or over-damped simulation fails)."}
    crit = {"traces": ["qpos:j1", "qpos:j2"], "variants": crit_v}
    ref = double_pendulum_reference(1, 1, 1, 1, 0.8, 1.2, every=100)
    q1 = [[r[0], r[1]] for r in ref]
    q2 = [[r[0], r[2] - r[1]] for r in ref]
    good = repr({"variant_id": "swing-a", "result": {"run_id": "r", "status": "COMPLETED", "trials": [{"attempts": [{"status": "COMPLETED"}], "measurements": {"energy_drift": 1e-9}}]},
                 "traces": {"qpos:j1": q1, "qpos:j2": q2}})
    bad = repr({"variant_id": "swing-a", "result": {"run_id": "r", "status": "COMPLETED", "trials": [{"attempts": [{"status": "COMPLETED"}], "measurements": {"energy_drift": 1e-9}}]},
                "traces": {"qpos:j1": [[r[0], 0.8] for r in q1], "qpos:j2": [[r[0], 0.4] for r in q1]}})
    conv = '''
    def test_reference_converges(self):
        import math
        sys_path = HERE.parents[2]
        import importlib.util as u
        s = u.spec_from_file_location("author", HERE.parents[1] / "author_cases.py")
        a = u.module_from_spec(s); s.loader.exec_module(a)
        fine = a.double_pendulum_reference(1, 1, 1, 1, 0.8, 1.2, horizon=0.5, dt=1e-5, every=500)
        coarse = a.double_pendulum_reference(1, 1, 1, 1, 0.8, 1.2, horizon=0.5, dt=2e-5, every=250)
        self.assertLess(max(abs(x[1] - y[1]) + abs(x[2] - y[2]) for x, y in zip(fine, coarse)), 1e-9)
        frozen = json.loads((HERE / "referee" / "reference_swing-a.json").read_text())["rows"]
        self.assertEqual(len(frozen), 2001)
'''
    write_case("f1-tb06-double-pendulum", family="F1", tb_id="TB-06", title="Passive double pendulum", objective=exp["header"]["objective"],
               metric={"name": "max absolute angle error vs reference (rad)", "definition": "max over samples to 2 s of |phi_sim - phi_ref| for both absolute angles; plus energy relative drift"},
               references=["arXiv 2603.14634, analytic double-pendulum test", "MuJoCo engine tests (multi-joint chains)", "Textbook double-pendulum equations (point masses, massless rods)"],
               model_assumptions="two point masses on massless rods; MuJoCo's second hinge angle is relative to the first, so phi1 = q1 and phi2 = q1 + q2; the reference is an independent pure-Python RK4 at 0.01 ms frozen in referee/ with its own convergence test.",
               procedure_kind="single_run", scene=scene, experiment=exp, variants=variants, criteria=crit, oracle=ORACLES["tb06"], good=good, bad=bad,
               extra_files=extra, extra_tests=conv)


def rolling_case():
    scene = ("scene.xml", """<mujoco model="tb07-rolling">
  <worldbody>
    <geom name="plane" type="plane" size="50 5 0.1" friction="1 0 0"/>
    <body name="roller" pos="0 0 0.1">
      <freejoint name="free"/>
      <geom name="roller_geom" type="${gtype}" size="${gsize}" euler="${geuler}" shellinertia="${shell}" mass="1" friction="1 0 0"/>
    </body>
  </worldbody>
</mujoco>
""")
    exp = {"scene": "scene.xml", "engine_why": "MuJoCo is the admitted executor; rolling contact without rolling resistance (condim 3)",
           "header": header("Rolling without slipping: a = g sin theta / (1 + I/mr^2)", [arm(params={"gtype": "sphere", "gsize": "0.1", "geuler": "0 0 0", "shell": "false"})],
                            config={"timestep": 0.0002, "integrator": "implicitfast", "cone": "elliptic", "impratio": 10, "gravity": tilt(20)},
                            origin="SIMLAB test plan TB-07"),
           "procedure": {"steps": [{"step_id": "roll", "duration_s": 1.0}]},
           "measurements": [tm("accel", "fit_acceleration", "xipos:roller", "m/s^2", component=0, t_start=0.1, t_end=1.0)],
           "observations": [{"signal": "xipos:roller", "unit": "m", "rate_hz": 1000}]}
    variants = [{"id": "solid-sphere", "split": "development", "task": "Solid sphere, radius 0.1 m, 20 degree incline.",
                 "params": {"gtype": "sphere", "gsize": "0.1", "geuler": "0 0 0", "shell": "false"}, "seed": 1},
                {"id": "hollow-sphere", "split": "development", "task": "Thin spherical shell (shell inertia), radius 0.1 m.",
                 "params": {"gtype": "sphere", "gsize": "0.1", "geuler": "0 0 0", "shell": "true"}, "seed": 2},
                {"id": "solid-cylinder", "split": "development", "task": "Solid cylinder, radius 0.1 m, rolling about its axis.",
                 "params": {"gtype": "cylinder", "gsize": "0.1 0.05", "geuler": "90 0 0", "shell": "false"}, "seed": 3}]
    rs = ("Proposed 0.5% [confirm]: the source gives none. MuJoCo's soft contact lets the roller slip slightly (exploratory error at most 0.14%); "
          "0.5% still separates the three inertias (their accelerations differ by 6% or more).")
    crit = {"g": G, "traces": ["xipos:roller"], "variants": {
        "solid-sphere": {"theta_deg": 20, "inertia_ratio": 0.4, "t_start": 0.1, "t_end": 1.0, "tolerance_rel": 0.005, "tolerance_reason": rs, "confirm": True},
        "hollow-sphere": {"theta_deg": 20, "inertia_ratio": 2.0 / 3.0, "t_start": 0.1, "t_end": 1.0, "tolerance_rel": 0.005, "tolerance_reason": rs, "confirm": True},
        "solid-cylinder": {"theta_deg": 20, "inertia_ratio": 0.5, "t_start": 0.1, "t_end": 1.0, "tolerance_rel": 0.005, "tolerance_reason": rs, "confirm": True}}}
    a = G * math.sin(math.radians(20)) / 1.4
    rows = [[i * 0.001, 0.5 * a * (i * 0.001) ** 2] for i in range(1001)]
    good = repr(result_ev("solid-sphere", {"accel": a}, {"xipos:roller": rows}))
    bad = repr(result_ev("solid-sphere", {"accel": G * math.sin(math.radians(20))}, {"xipos:roller": [[r[0], 0.5 * G * math.sin(math.radians(20)) * r[0] ** 2] for r in rows]}))
    write_case("f1-tb07-rolling", family="F1", tb_id="TB-07", title="Rolling without slipping", objective=exp["header"]["objective"],
               metric={"name": "acceleration relative error", "definition": "|a - g sin th / (1 + I/mr^2)| / that value"},
               references=["arXiv 2603.14634, analytic rolling test", "ContactBench contact criteria (rolling, no slip inside the friction cone)"],
               model_assumptions="sphere, shell or cylinder (1 kg, radius 0.1 m) on a plane, friction 1, condim 3 (no rolling resistance); incline by tilted gravity (20 degrees); acceleration from a quadratic fit of the centre of mass along the slope.",
               procedure_kind="single_run", scene=scene, experiment=exp, variants=variants, criteria=crit, oracle=ORACLES["tb07"], good=good, bad=bad)


def stack_case():
    scene = ("scene.xml", """<mujoco model="tb08-box-stack">
  <worldbody>
    <geom name="floor" type="plane" size="2 2 0.1"/>
    <body name="b1" pos="0 0 0.05"><freejoint name="f1"/><geom name="g1" type="box" size="0.05 0.05 0.05" mass="${m1}"/></body>
    <body name="b2" pos="0 0 0.15"><freejoint name="f2"/><geom name="g2" type="box" size="0.05 0.05 0.05" mass="${m2}"/></body>
    <body name="b3" pos="0 0 0.25"><freejoint name="f3"/><geom name="g3" type="box" size="0.05 0.05 0.05" mass="${m3}"/></body>
  </worldbody>
</mujoco>
""")
    exp = {"scene": "scene.xml", "engine_why": "MuJoCo is the admitted executor; resting contact in a stack",
           "header": header("Box stack at rest: stays still, contact forces balance gravity, penetration bounded", [arm(params={"m1": 1.0, "m2": 1.0, "m3": 1.0})],
                            config={"timestep": 0.001, "integrator": "implicitfast", "cone": "elliptic"}, origin="SIMLAB test plan TB-08"),
           "procedure": {"steps": [{"step_id": "settle", "duration_s": 1.0}, {"step_id": "rest", "duration_s": 1.0}]},
           "measurements": [tm("floor_force", "final", "contact:normal_force:floor:g1", "N"),
                            tm("top_drift", "range", "xpos:b3", "m", component=2, t_start=1.0, t_end=2.0),
                            tm("penetration", "max", "contact:penetration_max", "m")],
           "observations": [{"signal": "contact:normal_force:floor:g1", "unit": "N", "rate_hz": 100}, {"signal": "xpos:b3", "unit": "m", "rate_hz": 200},
                            {"signal": "contact:penetration_max", "unit": "m"}]}
    variants = [{"id": "equal-masses", "split": "development", "task": "Three 1 kg boxes.", "params": {"m1": 1.0, "m2": 1.0, "m3": 1.0}, "seed": 1},
                {"id": "heavy-bottom", "split": "development", "task": "Boxes of 2, 1 and 0.5 kg from the bottom.", "params": {"m1": 2.0, "m2": 1.0, "m3": 0.5}, "seed": 2},
                {"id": "heavy-top", "split": "development", "task": "Boxes of 0.5, 1 and 2 kg from the bottom.", "params": {"m1": 0.5, "m2": 1.0, "m3": 2.0}, "seed": 3},
                {"id": "gravity-off", "split": "development", "task": "Negative control: gravity off (contact forces vanish).",
                 "params": {"m1": 1.0, "m2": 1.0, "m3": 1.0}, "config": {"gravity": [0, 0, 0]}, "negative_control": True, "seed": 4}]
    rs = ("Proposed [confirm]: force within 1% of the total weight (exploratory: exact to rounding), top box height range at most 0.1 mm "
          "after the 1 s settle, penetration at most 1 mm (exploratory 0.37 mm with MuJoCo's default soft contact). The source gives no numbers.")
    def vv(ms):
        return {"masses": ms, "tolerance_force_rel": 0.01, "tolerance_still_m": 1e-4, "tolerance_penetration_m": 1e-3, "tolerance_reason": rs, "confirm": True}
    crit = {"g": G, "traces": ["contact:normal_force:floor:g1"], "variants": {
        "equal-masses": vv([1, 1, 1]), "heavy-bottom": vv([2, 1, 0.5]), "heavy-top": vv([0.5, 1, 2]),
        "gravity-off": {**vv([1, 1, 1]), "tolerance_reason": "Negative control (test plan TB-08: a stack with gravity off fails)."}}}
    good = repr(result_ev("equal-masses", {"floor_force": 29.43, "top_drift": 1e-7, "penetration": 4e-4}, {"contact:normal_force:floor:g1": [[0, 29.0], [2, 29.43]]}))
    bad = repr(result_ev("equal-masses", {"floor_force": 0.0, "top_drift": 1e-7, "penetration": 0.0}, {"contact:normal_force:floor:g1": [[0, 0.0], [2, 0.0]]}))
    write_case("f1-tb08-box-stack", family="F1", tb_id="TB-08", title="Box stack at rest", objective=exp["header"]["objective"],
               metric={"name": "floor contact force relative error", "definition": "|F_floor - g sum(m)| / (g sum(m)); plus top box stillness and penetration"},
               references=["MuJoCo engine tests (resting contact)", "ContactBench contact criteria (non-penetration, force balance)"],
               model_assumptions="three 10 cm boxes stacked on a plane with MuJoCo's default soft contact; force = summed normal force between the floor and the bottom box at the end; stillness measured after a 1 s settle.",
               procedure_kind="single_run", scene=scene, experiment=exp, variants=variants, criteria=crit, oracle=ORACLES["tb08"], good=good, bad=bad)


NOISY = '''def control(obs, params, ctx):
    """PD hold plus seeded noise: deterministic given the trial's random state."""
    return [float(ctx.rng.normal(0.0, params.get("noise", 0.3))) - params.get("kp", 3.0) * obs["qpos"][0] - 0.3 * obs["qvel"][0]]
'''
ACT_SCENE = """<mujoco model="controlled-pendulum">
  <worldbody>
    <body name="arm" pos="0 0 1">
      <joint name="hinge" type="hinge" axis="0 1 0" damping="0.05"/>
      <geom type="capsule" fromto="0 0 0 0 0 -0.5" size="0.02" mass="1"/>
    </body>
  </worldbody>
  <actuator><motor name="torque" joint="hinge" ctrlrange="-5 5"/></actuator>
</mujoco>
"""
DROP_SCENE = """<mujoco model="contact-rich-drop">
  <worldbody>
    <geom name="floor" type="plane" size="2 2 0.1"/>
    <body name="base" pos="0 0 0.05"><freejoint name="fb"/><geom name="gb" type="box" size="0.1 0.1 0.05" mass="2"/></body>
    <body name="top" pos="0.02 0.01 ${z0}"><freejoint name="ft"/><geom name="gt" type="box" size="0.04 0.04 0.04" mass="0.5" euler="0 0.3 0.2"/></body>
  </worldbody>
</mujoco>
"""


def identity_experiments(kind_objective, with_checkpoint):
    cp = [{"checkpoint_point_id": "midway", "step_end": "first"}] if with_checkpoint else []
    ctl = {"scene": "controlled.xml", "engine_why": "MuJoCo is the admitted executor",
           "header": header(kind_objective, [arm("controlled.xml", {"kp": 3.0, "noise": 0.3}, controller="noisy.py")],
                            config={"timestep": 0.001, "integrator": "RK4"}, replicates=2,
                            rvs=[{"name": "theta0", "distribution": {"kind": "uniform", "low": 0.1, "high": 0.6}}], origin="SIMLAB test plan TB-09 / F5"),
           "procedure": {"steps": [{"step_id": "first", "duration_s": 1.0}, {"step_id": "second", "duration_s": 1.0}],
                         "initial_state": {"qpos": {"hinge": "${theta0}"}},
                         "interventions": [{"intervention_id": "kick", "at_s": 1.5, "action": "add_qvel", "target": "hinge", "value": 0.7}],
                         "checkpoints": cp},
           "measurements": [tm("final_angle", "final", "qpos:hinge", "rad"), tm("peak", "max_abs", "qpos:hinge", "rad")],
           "observations": [{"signal": "qpos:hinge", "unit": "rad"}, {"signal": "ctrl:torque", "unit": "N m"}],
           "components": {"noisy.py": {"extension_point": "controller", "file": "noisy.py"}}}
    drop = {"scene": "drop.xml", "engine_why": "MuJoCo is the admitted executor",
            "header": header(kind_objective, [arm("drop.xml", {"z0": 0.4})], config={"timestep": 0.001, "integrator": "implicitfast", "cone": "elliptic"},
                             replicates=2, rvs=[{"name": "z0", "distribution": {"kind": "uniform", "low": 0.3, "high": 0.6}}], origin="SIMLAB test plan TB-09 / F5"),
            "procedure": {"steps": [{"step_id": "first", "duration_s": 0.8}, {"step_id": "second", "duration_s": 0.8}], "checkpoints": cp},
            "measurements": [tm("final_height", "final", "xpos:top", "m", component=2), tm("impact_speed", "min", "qvel:ft", "m/s", component=2)],
            "observations": [{"signal": "xpos:top", "unit": "m"}, {"signal": "qvel:ft", "unit": "m/s"}, {"signal": "contacts", "unit": "", "rate_hz": 100}]}
    fac = {"scene": "controlled.xml", "engine_why": "MuJoCo is the admitted executor",
           "header": header(kind_objective, [arm("controlled.xml", {"kp": 3.0, "noise": 0.3}, controller="noisy.py")],
                            config={"timestep": 0.001, "integrator": "RK4"}, replicates=1,
                            factors=[{"factor_id": "gain", "levels": [{"level_id": "soft", "settings": {"kp": 1.0}}, {"level_id": "stiff", "settings": {"kp": 6.0}}]}],
                            rvs=[{"name": "theta0", "distribution": {"kind": "normal", "mean": 0.3, "std": 0.1}}], origin="SIMLAB test plan TB-09 / F5"),
           "procedure": {"steps": [{"step_id": "first", "duration_s": 1.0}, {"step_id": "second", "duration_s": 1.0}],
                         "initial_state": {"qpos": {"hinge": "${theta0}"}}, "checkpoints": cp},
           "measurements": [tm("final_angle", "final", "qpos:hinge", "rad")],
           "observations": [{"signal": "qpos:hinge", "unit": "rad"}],
           "components": {"noisy.py": {"extension_point": "controller", "file": "noisy.py"}}}
    return ctl, drop, fac


def identity_case(cid, family, tb_id, title, objective, kind, with_checkpoint, references):
    ctl, drop, fac = identity_experiments(objective, with_checkpoint)
    d = CASES / cid / "public"
    d.mkdir(parents=True, exist_ok=True)
    (d / "experiment-drop.json").write_text(json.dumps(drop, indent=1) + "\n")
    (d / "experiment-factor.json").write_text(json.dumps(fac, indent=1) + "\n")
    (d / "drop.xml").write_text(DROP_SCENE)
    variants = [{"id": "controlled-noisy", "split": "development", "task": "Controlled pendulum with a seeded noisy controller and a random start angle.", "seed": 11},
                {"id": "contact-rich", "split": "development", "task": "A box dropped onto a box from a random height (contact-rich).", "experiment": "experiment-drop.json", "seed": 12},
                {"id": "factor-random", "split": "development", "task": "Two controller gains (a factor) with a normally distributed start angle.", "experiment": "experiment-factor.json", "seed": 13}]
    crit = {"traces": ["qpos:hinge", "xpos:top"], "checkpoint_required": with_checkpoint, "compare_signal": "qpos:hinge",
            "variants": {v["id"]: {"rule": "bitwise identity on the same machine and build (test plan Rules); no tolerance", "tolerance_reason": "Identity rule, not a tolerance.", "confirm": False} for v in variants}}
    crit["variants"]["contact-rich"]["compare_signal"] = "xpos:top"
    s = {"run_id": "r1", "run_kind": "original", "status": "COMPLETED", "trials": [{"attempts": [{"status": "COMPLETED", "state_digest": "d" * 64}], "measurements": {"x": 1.0}}], "checks": []}
    rep = dict(s, run_id="r3", run_kind="replay", checks=[{"check_id": "replay_identity", "status": "pass"}])
    good_ev = {"variant_id": "controlled-noisy", "result": s, "second_run": dict(s, run_id="r2"), "replay": rep}
    if with_checkpoint:
        good_ev.update(checkpoint={"time_s": 1.0}, original_after_checkpoint={"qpos:hinge": [[1 + i * 0.01, i] for i in range(20)]},
                       branch_after_checkpoint={"qpos:hinge": [[1 + i * 0.01, i] for i in range(20)]})
    bad_ev = json.loads(json.dumps(good_ev))
    bad_ev["replay"]["trials"][0]["attempts"][0]["state_digest"] = "e" * 64
    write_case(cid, family=family, tb_id=tb_id, title=title, objective=objective,
               metric={"name": "identity", "definition": "every comparison bitwise equal: per-step state digests (time, qpos, qvel, act, qacc_warmstart) and measurement values"},
               references=references,
               model_assumptions="same machine and same build only (test plan Rules); seeds, recorded actions and checkpoints come from SIMLAB's own records.",
               procedure_kind=kind, scene=("controlled.xml", ACT_SCENE), experiment=ctl, variants=variants, criteria=crit, oracle=ORACLES["determinism"],
               good=repr(good_ev), bad=repr(bad_ev), components={"noisy.py": NOISY})
    # the extra experiment files sit beside the main one
    (d / "experiment-drop.json").write_text(json.dumps(drop, indent=1) + "\n")
    (d / "experiment-factor.json").write_text(json.dumps(fac, indent=1) + "\n")
    (d / "drop.xml").write_text(DROP_SCENE)


def main() -> int:
    CASES.mkdir(parents=True, exist_ok=True)
    pendulum_case()
    freefall_case()
    incline_case()
    collision_case()
    damped_case()
    double_pendulum_case()
    rolling_case()
    stack_case()
    identity_case("f1-tb09-determinism", "F1", "TB-09", "Determinism and checkpoint restore",
                  "Two executions are identical, replay is identical, and restore-and-continue equals the uninterrupted run", "determinism", True,
                  ["MuJoCo state API (mj_getState with mjSTATE_INTEGRATION; 3.17 batch runs bit-identical to a plain loop)", "SIMLAB test plan TB-09"])
    identity_case("f5-replay", "F5", None, "Replay agreement on the same machine and build",
                  "A replay of a recorded run reproduces it exactly on the same machine and build", "replay", False,
                  ["MuJoCo state API (mj_getState, mjSTATE_INTEGRATION)", "SIMLAB test plan F5 (identity on the same machine and build)"])
    print("\n".join(sorted(p.name for p in CASES.iterdir())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
