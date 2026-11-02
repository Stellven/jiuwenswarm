"""Independent recomputation of standard trial measurements (PAS-M1-001 B07; PRD SL-4.D).

Separate code from simlab.measure: pure Python over the raw trace file, read
with its own .npy parser, different algorithms where a choice exists (explicit
loops, least squares by normal equations, peak search without NumPy). It must
not import simlab.measure.
"""
from __future__ import annotations

import ast
import math
import struct
from pathlib import Path


def read_npy(path: str | Path) -> list[list[float]]:
    """Minimal .npy reader for little-endian float64 C-order 2-D arrays (what the worker writes)."""
    data = Path(path).read_bytes()
    if data[:6] != b"\x93NUMPY":
        raise ValueError("not an .npy file")
    major = data[6]
    if major == 1:
        hlen = struct.unpack("<H", data[8:10])[0]
        start = 10
    else:
        hlen = struct.unpack("<I", data[8:12])[0]
        start = 12
    header = ast.literal_eval(data[start:start + hlen].decode("latin1"))
    if header["descr"] != "<f8" or header["fortran_order"]:
        raise ValueError(f"unsupported array layout {header}")
    shape = header["shape"]
    rows, cols = (shape[0], shape[1]) if len(shape) == 2 else (shape[0], 1)
    body = data[start + hlen:]
    flat = struct.unpack(f"<{rows * cols}d", body[: rows * cols * 8])
    return [list(flat[r * cols:(r + 1) * cols]) for r in range(rows)]


def _window(rows, d):
    lo, hi = d.get("t_start"), d.get("t_end")
    out = []
    for r in rows:
        if lo is not None and r[0] < lo - 1e-12:
            continue
        if hi is not None and r[0] > hi + 1e-12:
            continue
        out.append(r)
    return out


def _cross(ts, xs, level, direction):
    out = []
    for k in range(len(xs) - 1):
        a, b = xs[k] - level, xs[k + 1] - level
        up = a < 0 <= b
        down = a > 0 >= b
        if (direction == "up" and up) or (direction == "down" and down) or (direction == "any" and (up or down)):
            out.append(ts[k] + (a / (a - b)) * (ts[k + 1] - ts[k]))
    return out


def _quadfit_a(ts, xs):
    t0 = ts[0]
    # Normal equations for x = c0 + c1 t + c2 t^2, solved by Cramer's rule.
    s = [0.0] * 5
    r = [0.0] * 3
    for t, x in zip(ts, xs):
        tt = t - t0
        p = 1.0
        for k in range(5):
            if k < 3:
                r[k] += x * p
            s[k] += p
            p *= tt
    m = [[s[0], s[1], s[2]], [s[1], s[2], s[3]], [s[2], s[3], s[4]]]

    def det(a):
        return (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
                + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
    D = det(m)
    if D == 0:
        return None
    m2 = [[m[i][0], m[i][1], r[i]] for i in range(3)]
    return 2.0 * det(m2) / D


def _peaks(ts, xs):
    out = []
    for k in range(1, len(xs) - 1):
        if xs[k] > xs[k - 1] and xs[k] >= xs[k + 1]:
            a, b, c = xs[k - 1], xs[k], xs[k + 1]
            den = a - 2 * b + c
            off = 0.5 * (a - c) / den if den != 0 else 0.0
            out.append((ts[k] + off * (ts[k + 1] - ts[k]), b - 0.25 * (a - c) * off))
    return out


def _linfit_slope(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx


def recompute(defn: dict, trace_files: dict[str, str], events: list[dict]):
    kind = defn["kind"]
    if kind in {"event_time", "event_count"}:
        ts = sorted(e["t"] for e in events if e["event_id"] == defn.get("event_id"))
        return float(len(ts)) if kind == "event_count" else (ts[0] if ts else None)
    sig = defn.get("signal")
    if sig not in trace_files:
        return None
    col = 1 + int(defn.get("component", 0))
    rows = _window(read_npy(trace_files[sig]), defn)
    if not rows:
        return None
    ts = [r[0] for r in rows]
    xs = [r[col] for r in rows]
    if kind == "final":
        return xs[-1]
    if kind == "initial":
        return xs[0]
    if kind == "at_time":
        t = defn["t"]
        if t < ts[0] - 1e-12 or t > ts[-1] + 1e-12:
            return None
        for k in range(len(ts) - 1):
            if ts[k] <= t <= ts[k + 1]:
                if ts[k + 1] == ts[k]:
                    return xs[k]
                return xs[k] + (xs[k + 1] - xs[k]) * (t - ts[k]) / (ts[k + 1] - ts[k])
        return xs[-1]
    if kind == "max":
        return max(xs)
    if kind == "min":
        return min(xs)
    if kind == "mean":
        return math.fsum(xs) / len(xs)
    if kind == "max_abs":
        return max(abs(x) for x in xs)
    if kind == "range":
        return max(xs) - min(xs)
    if kind == "displacement":
        return xs[-1] - xs[0]
    if kind == "first_crossing_time":
        c = _cross(ts, xs, float(defn.get("level") or 0.0), defn.get("direction", "any"))
        return c[0] if c else None
    if kind == "period":
        d = defn.get("direction") if defn.get("direction") in {"up", "down"} else "up"
        c = _cross(ts, xs, float(defn.get("level") or 0.0), d)
        return (c[-1] - c[0]) / (len(c) - 1) if len(c) >= 2 else None
    if kind == "fit_acceleration":
        return _quadfit_a(ts, xs) if len(ts) >= 3 else None
    if kind == "decay_rate":
        lvl = float(defn.get("level") or 0.0)
        pk = [(t, v) for t, v in _peaks(ts, [x - lvl for x in xs]) if v > 0]
        if len(pk) < 2:
            return None
        s = _linfit_slope([p[0] for p in pk], [math.log(p[1]) for p in pk])
        return None if s is None else -s
    if kind == "relative_drift":
        if xs[0] == 0:
            return None
        return max(abs(x - xs[0]) for x in xs) / abs(xs[0])
    if kind == "velocity_ratio_at_event":
        tb = sorted(e["t"] for e in events if e["event_id"] == defn.get("event_id"))
        if not tb:
            return None
        tb = tb[0]
        te = sorted(e["t"] for e in events if e["event_id"] == defn.get("t_end_event") and e["t"] >= tb)
        if not te:
            return None
        full = read_npy(trace_files[sig])
        vals = [r[col] for r in full]
        if defn.get("signal_b"):
            if defn["signal_b"] not in trace_files:
                return None
            fb = read_npy(trace_files[defn["signal_b"]])
            if [r[0] for r in fb] != [r[0] for r in full]:
                return None
            vals = [a - r[col] for a, r in zip(vals, fb)]
        w = float(defn.get("window_s") or 0.0)
        before = [k for k, r in enumerate(full) if r[0] <= tb - w]
        after = [k for k, r in enumerate(full) if r[0] >= te[0] + w]
        if not before or not after or vals[before[-1]] == 0:
            return None
        return -vals[after[0]] / vals[before[-1]]
    raise ValueError(f"not a standard trial kind: {kind}")
