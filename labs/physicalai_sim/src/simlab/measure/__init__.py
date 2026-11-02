"""Standard measurements, primary implementation (NumPy) (PAS-M1-001 B05/B07).

Each trial-scope kind is computed from the recorded trace of one signal
(an array [n, 1 + dim]: time, values). The independent recomputation used by
the recomputation check lives in simlab.checks.recompute and shares no code
with this module.

A value of None means the observation is missing (for example no crossing, or
no event); for a required measurement that makes the attempt INVALID with
`missing_required_observation`.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

STANDARD_TRIAL_KINDS = {"final", "initial", "at_time", "max", "min", "mean", "max_abs", "range", "displacement",
                        "first_crossing_time", "period", "fit_acceleration", "decay_rate", "relative_drift",
                        "event_time", "event_count", "velocity_ratio_at_event"}
PAIR_KINDS = {"pair_difference", "pair_ratio"}
SET_KINDS = {"set_mean", "set_std", "set_min", "set_max", "set_count"}


def _window(arr: np.ndarray, d: dict) -> np.ndarray:
    t = arr[:, 0]
    lo = d.get("t_start")
    hi = d.get("t_end")
    mask = np.ones(len(t), dtype=bool)
    if lo is not None:
        mask &= t >= lo - 1e-12
    if hi is not None:
        mask &= t <= hi + 1e-12
    return arr[mask]


def _crossings(t: np.ndarray, x: np.ndarray, level: float, direction: str) -> np.ndarray:
    y = x - level
    s0, s1 = y[:-1], y[1:]
    up = (s0 < 0) & (s1 >= 0)
    down = (s0 > 0) & (s1 <= 0)
    sel = up if direction == "up" else down if direction == "down" else (up | down)
    idx = np.nonzero(sel)[0]
    frac = s0[idx] / (s0[idx] - s1[idx])
    return t[idx] + frac * (t[idx + 1] - t[idx])


def _peaks(t: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Local maxima refined by a parabola through the three samples around each."""
    i = np.nonzero((x[1:-1] > x[:-2]) & (x[1:-1] >= x[2:]))[0] + 1
    a, b, c = x[i - 1], x[i], x[i + 1]
    den = a - 2 * b + c
    with np.errstate(divide="ignore", invalid="ignore"):
        off = np.where(den != 0, 0.5 * (a - c) / den, 0.0)
    h = t[i + 1] - t[i]
    return t[i] + off * h, b - 0.25 * (a - c) * off


def trial_value(defn: dict, traces: dict[str, np.ndarray], events: list[dict]) -> float | None:
    kind = defn["kind"]
    if kind in {"event_time", "event_count"}:
        ts = sorted(e["t"] for e in events if e["event_id"] == defn.get("event_id"))
        if kind == "event_count":
            return float(len(ts))
        return float(ts[0]) if ts else None
    sig = defn.get("signal")
    if sig not in traces:
        return None
    arr = _window(traces[sig], defn)
    if arr.shape[0] == 0:
        return None
    t = arr[:, 0]
    x = arr[:, 1 + int(defn.get("component", 0))]
    if kind == "final":
        return float(x[-1])
    if kind == "initial":
        return float(x[0])
    if kind == "at_time":
        tt = defn["t"]
        if tt < t[0] - 1e-12 or tt > t[-1] + 1e-12:
            return None
        return float(np.interp(tt, t, x))
    if kind == "max":
        return float(np.max(x))
    if kind == "min":
        return float(np.min(x))
    if kind == "mean":
        return float(np.mean(x))
    if kind == "max_abs":
        return float(np.max(np.abs(x)))
    if kind == "range":
        return float(np.max(x) - np.min(x))
    if kind == "displacement":
        return float(x[-1] - x[0])
    if kind == "first_crossing_time":
        c = _crossings(t, x, float(defn.get("level") or 0.0), defn.get("direction", "any"))
        return float(c[0]) if c.size else None
    if kind == "period":
        c = _crossings(t, x, float(defn.get("level") or 0.0), defn.get("direction") if defn.get("direction") in {"up", "down"} else "up")
        if c.size < 2:
            return None
        return float((c[-1] - c[0]) / (c.size - 1))
    if kind == "fit_acceleration":
        if t.size < 3:
            return None
        tc = t - t[0]
        coef = np.polyfit(tc, x, 2)
        return float(2.0 * coef[0])
    if kind == "decay_rate":
        pt, pv = _peaks(t, x - float(defn.get("level") or 0.0))
        keep = pv > 0
        pt, pv = pt[keep], pv[keep]
        if pt.size < 2:
            return None
        slope = np.polyfit(pt, np.log(pv), 1)[0]
        return float(-slope)
    if kind == "relative_drift":
        ref = x[0]
        if ref == 0:
            return None
        return float(np.max(np.abs(x - ref)) / abs(ref))
    if kind == "velocity_ratio_at_event":
        ts = sorted(e["t"] for e in events if e["event_id"] == defn.get("event_id"))
        if not ts:
            return None
        tb = ts[0]
        tend = defn.get("t_end_event")
        te = sorted(e["t"] for e in events if e["event_id"] == tend and e["t"] >= tb) if tend else []
        after_t = te[0] if te else None
        sigb = defn.get("signal_b")
        xb = None
        if sigb:
            if sigb not in traces:
                return None
            xb = traces[sigb][:, 1 + int(defn.get("component", 0))]
            tb_arr = traces[sigb][:, 0]
            if tb_arr.shape != traces[sig][:, 0].shape or not np.array_equal(tb_arr, traces[sig][:, 0]):
                return None
        full_t = traces[sig][:, 0]
        full_x = traces[sig][:, 1 + int(defn.get("component", 0))] - (xb if xb is not None else 0.0)
        w = float(defn.get("window_s") or 0.0)
        before = np.nonzero(full_t <= tb - w)[0]
        if before.size == 0 or after_t is None:
            return None
        after = np.nonzero(full_t >= after_t + w)[0]
        if after.size == 0:
            return None
        v0, v1 = full_x[before[-1]], full_x[after[0]]
        if v0 == 0:
            return None
        return float(-v1 / v0)
    raise ValueError(f"not a standard trial kind: {kind}")


def pair_value(defn: dict, a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    if defn["kind"] == "pair_difference":
        return float(b - a)
    if defn["kind"] == "pair_ratio":
        return None if a == 0 else float(b / a)
    raise ValueError(defn["kind"])


def set_value(defn: dict, values: list[float]) -> tuple[float | None, int]:
    vals = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    k = defn["kind"]
    if k == "set_count":
        return float(len(vals)), len(vals)
    if not vals:
        return None, 0
    arr = np.asarray(vals, dtype=float)
    if k == "set_mean":
        return float(arr.mean()), len(vals)
    if k == "set_std":
        return (float(arr.std(ddof=1)) if len(vals) > 1 else None), len(vals)
    if k == "set_min":
        return float(arr.min()), len(vals)
    if k == "set_max":
        return float(arr.max()), len(vals)
    raise ValueError(k)


def predicate(op: str, value: Any, ref: float) -> bool | None:
    if value is None:
        return None
    return {"<": value < ref, "<=": value <= ref, ">": value > ref, ">=": value >= ref, "==": value == ref, "!=": value != ref}[op]
