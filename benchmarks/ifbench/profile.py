"""Profile pass with Nsight Systems (T2: only the launch command changes, no engine code).

The engine runs under `nsys profile` (CUDA + NVTX trace, CPU sampling off), receives a few scripted
requests, and is stopped; the report is exported to SQLite and turned into telemetry records:
L0.first_occurrence_cost, L3.gpu_idle_share, L4.gpu_time_by_op, L4.kernels_executed,
L5.kernel_launches, L5.sync_points. A profiler is attached, so this run's speed numbers are never
used as results (the run is marked not comparable).

Nsight Compute (L5.bandwidth_ratio / L5.compute_ratio) needs GPU performance counters; see ncu_status().
"""
import csv, glob, json, os, re, shutil, sqlite3, subprocess, time
from datetime import datetime, timezone

NSYS_CANDIDATES = ("nsys", "/usr/local/bin/nsys", "/usr/local/cuda/bin/nsys", "/opt/nvidia/nsight-systems/*/bin/nsys")
NCU_CANDIDATES = ("ncu", "/usr/local/cuda/bin/ncu", "/opt/nvidia/nsight-compute/*/ncu", "/usr/local/cuda/nsight-compute*/ncu")


def find_tool(candidates, configured=None):
    for c in ([configured] if configured else []) + list(candidates):
        if "*" in c:
            hits = sorted(glob.glob(c))
            if hits:
                return hits[-1]
        elif shutil.which(c) or os.path.isfile(c):
            return shutil.which(c) or c
    return None


def nsys_command(nsys, pcfg, out_base):
    """Prefix for the server command. Options only from the `nsys profile` switch list."""
    return [nsys, "profile", f"--trace={pcfg.get('trace', 'cuda,nvtx')}", "--sample=none", "--cpuctxsw=none",
            f"--cuda-graph-trace={pcfg.get('cuda_graph_trace', 'node')}", "--force-overwrite=true",
            "-o", out_base] + list(pcfg.get("extra_nsys_args", []))


def export_sqlite(nsys, rep, log):
    out = rep[: -len(".nsys-rep")] + ".sqlite"
    p = subprocess.run([nsys, "export", "--type", "sqlite", "--force-overwrite=true", "-o", out, rep],
                       capture_output=True, text=True, timeout=3600)
    log.write(f"$ nsys export ...\n{p.stdout}\n{p.stderr}\n")
    if not os.path.exists(out):  # older/newer CLI spelling: `nsys stats` creates the SQLite file as a side effect
        p = subprocess.run([nsys, "stats", "--report", "cuda_gpu_kern_sum", "--format", "csv", "--output",
                            rep[: -len(".nsys-rep")] + "_stats", rep], capture_output=True, text=True, timeout=3600)
        log.write(f"$ nsys stats (fallback) ...\n{p.stdout}\n{p.stderr}\n")
    return out if os.path.exists(out) else None


def ncu_status(pcfg):
    """Can Nsight Compute read GPU counters here? Returns (ok, reason)."""
    ncu = find_tool(NCU_CANDIDATES, pcfg.get("ncu"))
    admin_only = None
    try:
        for line in open("/proc/driver/nvidia/params"):
            if line.startswith("RmProfilingAdminOnly"):
                admin_only = line.split(":")[1].strip()
    except OSError:
        pass
    if ncu is None:
        return False, f"ncu not found; RmProfilingAdminOnly={admin_only}"
    if admin_only == "1" and os.geteuid() != 0:
        return False, f"ncu at {ncu}, but RmProfilingAdminOnly=1: GPU counters are admin only (needs an administrator)"
    return True, f"ncu at {ncu}; RmProfilingAdminOnly={admin_only}"


# ---------------- kernel categories ----------------

def load_categories(path):
    try:
        rules = json.load(open(path))["rules"]
        return [(name, re.compile(rx, re.I)) for name, rx in rules]
    except (OSError, ValueError, KeyError):
        return []


def categorize(name, rules):
    for cat, rx in rules:
        if rx.search(name or ""):
            return cat
    return "uncategorized"


# ---------------- SQLite analysis ----------------

LAUNCH_RX = re.compile(r"LaunchKernel|LaunchCooperativeKernel|GraphLaunch", re.I)
SYNC_RX = re.compile(r"Synchronize", re.I)
SYNC_COPY_RX = re.compile(r"^cu(da)?Memcpy(?!.*Async)|^cu(da)?Memset(?!.*Async)", re.I)
COPY_KIND = {1: "copy H2D", 2: "copy D2H", 8: "copy D2D", 10: "copy P2P"}


def _tables(db):
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _cols(db, table):
    return {r[1] for r in db.execute(f"PRAGMA table_info({table})")}


def _union_ns(intervals, lo, hi):
    """Total length of the union of [s, e) intervals clipped to [lo, hi)."""
    total, cur_s, cur_e = 0, None, None
    for s, e in sorted((max(s, lo), min(e, hi)) for s, e in intervals if e > lo and s < hi):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s
    return total


def load_trace(sqlite_path, rules):
    db = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    t = _tables(db)
    strings = dict(db.execute("SELECT id, value FROM StringIds")) if "StringIds" in t else {}
    epoch = None
    if "TARGET_INFO_SESSION_START_TIME" in t:
        row = db.execute("SELECT utcEpochNs FROM TARGET_INFO_SESSION_START_TIME").fetchone()
        epoch = row[0] if row else None
    kernels = []
    if "CUPTI_ACTIVITY_KIND_KERNEL" in t:
        cols = _cols(db, "CUPTI_ACTIVITY_KIND_KERNEL")
        name_col = "shortName" if "shortName" in cols else "demangledName"
        for s, e, nid in db.execute(f"SELECT start, end, {name_col} FROM CUPTI_ACTIVITY_KIND_KERNEL"):
            name = strings.get(nid, str(nid))
            kernels.append((s, e, name, categorize(name, rules)))
    copies = []
    if "CUPTI_ACTIVITY_KIND_MEMCPY" in t:
        for s, e, kind, nbytes in db.execute("SELECT start, end, copyKind, bytes FROM CUPTI_ACTIVITY_KIND_MEMCPY"):
            copies.append((s, e, COPY_KIND.get(kind, "copy other"), nbytes or 0))
    api = []
    if "CUPTI_ACTIVITY_KIND_RUNTIME" in t:
        for s, e, nid in db.execute("SELECT start, end, nameId FROM CUPTI_ACTIVITY_KIND_RUNTIME"):
            api.append((s, e, strings.get(nid, str(nid))))
    db.close()
    return {"epoch_ns": epoch, "kernels": kernels, "copies": copies, "api": api}


def window_stats(tr, lo, hi, tokens=None):
    """All profile numbers for one window [lo, hi) in trace nanoseconds."""
    ks = [k for k in tr["kernels"] if k[1] > lo and k[0] < hi]
    cs = [c for c in tr["copies"] if c[1] > lo and c[0] < hi]
    ap = [a for a in tr["api"] if a[0] >= lo and a[0] < hi]
    span = max(1, hi - lo)
    busy = _union_ns([(k[0], k[1]) for k in ks], lo, hi)
    by_cat = {}
    for s, e, name, cat in ks:
        by_cat[cat] = by_cat.get(cat, 0) + (min(e, hi) - max(s, lo))
    copy_bytes = {}
    for s, e, kind, nb in cs:
        by_cat[kind] = by_cat.get(kind, 0) + (min(e, hi) - max(s, lo))
        copy_bytes[kind] = copy_bytes.get(kind, 0) + nb
    total_cat = sum(by_cat.values()) or 1
    launches = [a for a in ap if LAUNCH_RX.search(a[2])]
    graph_launches = [a for a in launches if "Graph" in a[2]]
    syncs = [a for a in ap if SYNC_RX.search(a[2])]
    sync_copies = [a for a in ap if SYNC_COPY_RX.search(a[2])]
    by_sync = {}
    for s, e, n in syncs + sync_copies:
        d = by_sync.setdefault(re.sub(r"_v\d+$", "", n), [0, 0]); d[0] += 1; d[1] += e - s
    per_tok = (lambda v: round(v / tokens, 3)) if tokens else (lambda v: None)
    return {
        "window_s": round(span / 1e9, 2),
        "gpu_busy_pct": round(100 * busy / span, 2), "gpu_idle_pct": round(100 - 100 * busy / span, 2),
        "gpu_busy_ms": round(busy / 1e6, 1), "gpu_busy_ms_per_token": per_tok(busy / 1e6),
        "kernels": len(ks), "kernels_per_token": per_tok(len(ks)),
        "by_category_ms": {c: round(v / 1e6, 2) for c, v in sorted(by_cat.items(), key=lambda x: -x[1])},
        "by_category_pct": {c: round(100 * v / total_cat, 1) for c, v in sorted(by_cat.items(), key=lambda x: -x[1])},
        "copy_gb": {k: round(v / 1e9, 3) for k, v in copy_bytes.items()},
        "launch_calls": len(launches), "graph_launches": len(graph_launches),
        "launch_api_ms": round(sum(e - s for s, e, _ in launches) / 1e6, 2),
        "mean_launch_api_us": round(sum(e - s for s, e, _ in launches) / len(launches) / 1e3, 2) if launches else None,
        "launch_calls_per_token": per_tok(len(launches)),
        "sync_calls": len(syncs), "sync_ms": round(sum(e - s for s, e, _ in syncs) / 1e6, 2),
        "sync_copy_calls": len(sync_copies),
        "sync_by_api": {k: {"calls": v[0], "ms": round(v[1] / 1e6, 2)} for k, v in sorted(by_sync.items(), key=lambda x: -x[1][1])[:8]},
        "cuda_api_ms": round(sum(e - s for s, e, _ in ap) / 1e6, 1),
    }


def top_apis(tr, lo, hi, n=8):
    agg = {}
    for s, e, name in tr["api"]:
        if lo <= s < hi:
            d = agg.setdefault(re.sub(r"_v\d+$", "", name), [0, 0]); d[0] += 1; d[1] += e - s
    return {k: {"calls": v[0], "ms": round(v[1] / 1e6, 1)} for k, v in sorted(agg.items(), key=lambda x: -x[1][1])[:n]}


def kernel_table(tr, lo, hi):
    agg = {}
    for s, e, name, cat in tr["kernels"]:
        if e > lo and s < hi:
            d = agg.setdefault(name, [0, 0, cat]); d[0] += 1; d[1] += e - s
    return sorted(((n, c, ns, cat) for n, (c, ns, cat) in agg.items()), key=lambda x: -x[2])


def _iso(epoch_s):
    return datetime.fromtimestamp(epoch_s, timezone.utc).isoformat(timespec="seconds")


def analyze(rec, sqlite_path, rules, requests, t_launch, t_ready, out_dir):
    """requests: [{label, t0, t_first, t_last, t1, tokens}] in wall-clock seconds.

    Trace time 0 = session start (TARGET_INFO_SESSION_START_TIME); without that table the server
    launch time is used, which can be off by the profiler's own start-up (noted in the records).
    """
    tr = load_trace(sqlite_path, rules)
    if not tr["kernels"]:
        for tid in ("L0.first_occurrence_cost", "L3.gpu_idle_share", "L4.gpu_time_by_op", "L4.kernels_executed",
                    "L5.kernel_launches", "L5.sync_points"):
            rec.add(tid, None, "unavailable", "Nsight Systems", note="no CUDA kernels in the trace (CUPTI not available?)")
        return {"error": "no kernels"}
    # Clock check: every request window must contain GPU work. Take the session start from the trace;
    # if that leaves request windows empty and the launch time does not, the trace clock is suspect.
    cands = ([(tr["epoch_ns"], "TARGET_INFO_SESSION_START_TIME")] if tr["epoch_ns"] else []) + \
            [(int(t_launch * 1e9), "server launch time (approximate)")]
    starts = sorted(k[0] for k in tr["kernels"])
    def covered(b):
        import bisect
        n = 0
        for r in requests:
            lo_, hi_ = int(r["t0"] * 1e9) - b, int(r["t1"] * 1e9) - b
            i = bisect.bisect_left(starts, lo_)
            n += i < len(starts) and starts[i] < hi_
        return n
    base, clock = max(cands, key=lambda c: covered(c[0]))
    if covered(base) < len(requests):
        clock += f"; WARNING: only {covered(base)} of {len(requests)} request windows contain kernels"
    ns = lambda t: int(t * 1e9) - base
    src = f"Nsight Systems trace (clock: {clock})"
    summary = {"clock": clock, "windows": {}}
    # startup: everything the engine did before it answered the health check
    lo, hi = 0, ns(t_ready)
    st = window_stats(tr, lo, hi)
    first, repeat = (requests + [None, None])[:2]
    foc = {"startup_s": round((t_ready - t_launch), 1), "startup_top_cuda_api": top_apis(tr, lo, hi),
           "startup_copy_gb": st["copy_gb"], "startup_kernels": st["kernels"]}
    if first and repeat and repeat.get("same_prompt_as_first"):
        a = window_stats(tr, ns(first["t0"]), ns(first["t1"]), first.get("tokens"))
        b = window_stats(tr, ns(repeat["t0"]), ns(repeat["t1"]), repeat.get("tokens"))
        foc["first_vs_repeat_request"] = {
            "wall_s": [round(first["t1"] - first["t0"], 1), round(repeat["t1"] - repeat["t0"], 1)],
            "gpu_busy_ms": [a["gpu_busy_ms"], b["gpu_busy_ms"]], "cuda_api_ms": [a["cuda_api_ms"], b["cuda_api_ms"]],
            "kernels": [a["kernels"], b["kernels"]],
            "first_request_top_cuda_api": top_apis(tr, ns(first["t0"]), ns(first["t1"]), 5)}
    rec.add("L0.first_occurrence_cost", foc, source=src, window={"start": _iso(t_launch), "end": _iso(t_ready), "label": "startup + first request"},
            note="one-time work: startup CUDA API time (allocation, module load, weight upload) and first vs identical repeat request")
    summary["windows"]["startup"] = st
    for r in requests:
        for phase, t0, t1, toks in (("prefill", r["t0"], r["t_first"], None), ("decode", r["t_first"], r["t_last"], max(1, (r.get("tokens") or 1) - 1))):
            if not t0 or not t1 or t1 <= t0:
                continue
            w = window_stats(tr, ns(t0), ns(t1), toks)
            label = f"{r['label']} {phase}"
            summary["windows"][label] = w
            win = {"start": _iso(t0), "end": _iso(t1), "label": label}
            rec.add("L3.gpu_idle_share", {k: w[k] for k in ("gpu_busy_pct", "gpu_idle_pct", "gpu_busy_ms", "gpu_busy_ms_per_token", "window_s")},
                    source=src, window=win, note="GPU busy = union of kernel time; idle = the GPU waits (CPU work, SSD reads, sync)")
            rec.add("L4.gpu_time_by_op", {"pct": w["by_category_pct"], "ms": w["by_category_ms"], "copy_gb": w["copy_gb"]},
                    source=src + " + data/kernel_categories.json", window=win)
            rec.add("L5.kernel_launches", {k: w[k] for k in ("launch_calls", "graph_launches", "kernels", "kernels_per_token",
                                                               "launch_calls_per_token", "mean_launch_api_us", "launch_api_ms")},
                    source=src, window=win)
            rec.add("L5.sync_points", {k: w[k] for k in ("sync_calls", "sync_ms", "sync_copy_calls", "sync_by_api")},
                    source=src, window=win, note="host waits for the GPU (Synchronize calls) and synchronous copies")
    lo_r = ns(min(r["t0"] for r in requests)) if requests else 0
    hi_r = ns(max(r["t1"] for r in requests)) if requests else ns(time.time())
    table = kernel_table(tr, lo_r, hi_r)
    total = sum(x[2] for x in table) or 1
    unc = [(n, c, t) for n, c, t, cat in table if cat == "uncategorized"]
    rec.add("L4.kernels_executed", {"distinct_kernels": len(table), "launches": sum(x[1] for x in table),
                                    "top": [{"name": n[:120], "category": cat, "count": c, "ms": round(t / 1e6, 2),
                                             "pct": round(100 * t / total, 1)} for n, c, t, cat in table[:25]],
                                    "uncategorized_pct": round(100 * sum(t for _, _, t in unc) / total, 1),
                                    "uncategorized_top": [n[:120] for n, _, _ in unc[:10]]},
            source=src, window={"start": _iso(min(r["t0"] for r in requests)) if requests else None,
                                "end": _iso(max(r["t1"] for r in requests)) if requests else None, "label": "all profiled requests"},
            note="full list in nsys/kernels.csv")
    with open(os.path.join(out_dir, "kernels.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["kernel", "category", "count", "total_ms", "pct"])
        for n, c, t, cat in table:
            w.writerow([n, cat, c, round(t / 1e6, 3), round(100 * t / total, 2)])
    json.dump(summary, open(os.path.join(out_dir, "profile_summary.json"), "w"), indent=2)
    return summary
