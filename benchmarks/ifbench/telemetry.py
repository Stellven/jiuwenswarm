"""Telemetry records (plan section 6.1) and T1 collectors.

Every measurement becomes one record. A value that could not be obtained is null with
status "unavailable" -- never zero.
"""
import json, os, re, shutil, subprocess, threading, time
from datetime import datetime, timezone

# telemetry ID -> (layer, unit, tier): all 47 IDs of plan revision 3
CATALOG = {
    "L0.time_to_ready": ("L0", "s", "T1"),
    "L0.weight_load": ("L0", "s, GB", "T1"),
    "L0.first_request_ratio": ("L0", "ratio", "T1"),
    "L0.first_occurrence_cost": ("L0", "ms", "T2"),
    "L0.checkpoint_storage": ("L0", "GB", "T1"),
    "L0.run_environment": ("L0", "-", "T1"),
    "L1.ttft_client": ("L1", "ms", "T1"),
    "L1.api_overhead": ("L1", "ms", "T2"),
    "L1.token_count_check": ("L1", "tokens", "T1"),
    "L1.failed_requests": ("L1", "count", "T1"),
    "L1.server_cpu": ("L1", "% of one core", "T1"),
    "L2.queue_wait": ("L2", "s", "T2"),
    "L2.requests_active": ("L2", "count", "T2"),
    "L2.slot_states": ("L2", "count", "T2"),
    "L2.batch_rows": ("L2", "rows", "T2"),
    "L2.rejected_timeouts": ("L2", "count", "T2"),
    "L2.preemptions": ("L2", "count", "T2"),
    "L3.prefill_rate": ("L3", "tok/s", "T1"),
    "L3.decode_rate": ("L3", "tok/s", "T1"),
    "L3.ttft_engine": ("L3", "ms", "T2"),
    "L3.gpu_idle_share": ("L3", "ms, %", "T2"),
    "L3.draft_acceptance": ("L3", "%", "T2"),
    "L3.step_phase_split": ("L3", "ms", "T3"),
    "L4.gpu_time_by_op": ("L4", "%, ms", "T2"),
    "L4.kernels_executed": ("L4", "names, count", "T2"),
    "L4.expert_selection": ("L4", "count", "T3"),
    "L4.token_prob_match": ("L4", "KL, top-1", "T1"),
    "M.gpu_working_set": ("M", "GiB", "T1"),
    "M.host_memory": ("M", "GiB", "T1"),
    "M.mem_available_min": ("M", "GiB", "T1"),
    "M.startup_memory_plan": ("M", "GiB", "T1"),
    "M.kv_utilization": ("M", "%", "T2"),
    "M.prefix_cache_hit": ("M", "%", "T2"),
    "M.storage_read_per_token": ("M", "GB/token", "T1"),
    "M.expert_cache_hit": ("M", "%", "T3"),
    "L5.kernel_launches": ("L5", "count, us", "T2"),
    "L5.sync_points": ("L5", "count, ms", "T2"),
    "L5.bandwidth_ratio": ("L5", "%", "T2"),
    "L5.compute_ratio": ("L5", "%", "T2"),
    "L6.gpu_health": ("L6", "MHz, W, C, %", "T1"),
    "L6.cpu_per_core": ("L6", "%", "T1"),
    "L6.storage_read_rate": ("L6", "MB/s", "T1"),
    "L6.storage_capacity": ("L6", "GB", "T1"),
    "L6.other_workloads": ("L6", "list, GiB", "T1"),
    "L6.cal.storage_read": ("L6", "GB/s", "CAL"),
    "L6.cal.memory_bandwidth": ("L6", "GB/s", "CAL"),
    "L6.cal.compute": ("L6", "FLOP/s", "CAL"),
}

NSYS_IDS = ("L0.first_occurrence_cost", "L3.gpu_idle_share", "L4.gpu_time_by_op", "L4.kernels_executed",
            "L5.kernel_launches", "L5.sync_points")

# Why an ID has no measured value, when nothing in the run recorded it (filled in at the end of every run,
# so report.md and `ifbench coverage` show all 47 IDs). status, note
GAP_REASON = {
    "L2.queue_wait": ("not_applicable", "concurrency 1: requests never queue; the waiting count is in L2.requests_active"),
    "L2.rejected_timeouts": ("not_applicable", "concurrency 1: nothing is rejected for load; client failures are in L1.failed_requests and each benchmark's outcome"),
    "L2.preemptions": ("not_applicable", "concurrency 1: nothing to preempt"),
    "L3.draft_acceptance": ("not_applicable", "speculative decoding is not enabled in this engine configuration"),
    "L3.step_phase_split": ("unavailable", "T3: needs per-step phase markers (NVTX) inside the engine; factory diagnostic image"),
    "L4.expert_selection": ("unavailable", "T3: needs a per-layer, per-expert counter inside the engine; factory diagnostic image"),
    "M.expert_cache_hit": ("unavailable", "exact value is T3 (engine counter); the estimate needs a speed probe with routed-expert sizes from the GGUF"),
    "L5.bandwidth_ratio": ("unavailable", "blocked: Nsight Compute needs GPU performance counters, admin only on this Spark (RmProfilingAdminOnly=1); the profile run re-checks"),
    "L5.compute_ratio": ("unavailable", "blocked: same as L5.bandwidth_ratio (Nsight Compute counters are admin only on this Spark)"),
    "L6.cal.memory_bandwidth": ("unavailable", "measured separately with `ifbench calibrate --babelstream`"),
    "L6.cal.compute": ("unavailable", "measured separately with `ifbench calibrate --cutlass-profiler`"),
    "L6.cal.storage_read": ("unavailable", "per-machine calibration, run once with `python3 -m ifbench calibrate`"),
}
for _tid in NSYS_IDS:
    GAP_REASON[_tid] = ("unavailable", "collected by the separate profile run (`--set profile`, Nsight Systems), never in timed runs")

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

class Recorder:
    """Writes telemetry records as JSON lines into <run_dir>/telemetry.jsonl."""
    def __init__(self, run_dir, run_id, image, checkpoint):
        self.path = os.path.join(run_dir, "telemetry.jsonl")
        self.ctx = {"run_id": run_id, "image": image, "checkpoint": checkpoint}
        self.comparable = True
        self.records = []

    @classmethod
    def reopen(cls, run_dir, drop_ids=(), drop_sources=("coverage check",)):
        """Reload a finished run's records (to re-derive some of them offline). Dropped records are
        removed from telemetry.jsonl, so re-adding them does not duplicate anything."""
        recs = [json.loads(l) for l in open(os.path.join(run_dir, "telemetry.jsonl"))]
        first = recs[0] if recs else {}
        self = cls(run_dir, first.get("run_id"), first.get("image"), first.get("checkpoint"))
        self.comparable = all(r.get("comparable", True) for r in recs)
        self.records = [r for r in recs if r["id"] not in drop_ids and r.get("source") not in drop_sources]
        with open(self.path, "w") as f:
            for r in self.records:
                f.write(json.dumps(r) + "\n")
        return self

    def add(self, tid, value, status="ok", source="", window=None, note=None, unit=None):
        layer, cunit, tier = CATALOG.get(tid, (tid.split(".")[0], "", ""))
        if value is None and status == "ok":
            status = "unavailable"
        rec = {"id": tid, "layer": layer, "value": value, "unit": unit or cunit, "status": status,
               "tier": tier, "source": source, **self.ctx,
               "window": window or {"start": now(), "end": now()}, "comparable": self.comparable}
        if note:
            rec["note"] = note
        self.records.append(rec)
        with open(self.path, "a") as f:
            f.write(json.dumps(rec) + "\n")
        return rec

    def fill_gaps(self, extra=None):
        """Add one record for every catalog ID this run did not record, with the reason (GAP_REASON)."""
        seen = {r["id"] for r in self.records}
        reasons = {**GAP_REASON, **(extra or {})}
        for tid in CATALOG:
            if tid not in seen:
                status, note = reasons.get(tid, ("unavailable", "not recorded in this run"))
                self.add(tid, None, status, "coverage check", note=note)

    def coverage(self):
        """ID -> (best status, short note). ok beats not_applicable beats unavailable."""
        rank = {"ok": 0, "not_applicable": 1, "unavailable": 2}
        out = {}
        for r in self.records:
            cur = out.get(r["id"])
            if cur is None or rank.get(r["status"], 3) < rank.get(cur[0], 3):
                out[r["id"]] = (r["status"], r.get("note") or r.get("source") or "")
        return out

# ---------------- low-level readers (Linux /proc, nvidia-smi) ----------------

def meminfo_gib():
    out = {}
    try:
        for line in open("/proc/meminfo"):
            k, v = line.split(":", 1)
            out[k] = int(v.split()[0]) / 1024 / 1024  # kB -> GiB
    except OSError:
        pass
    return out

def proc_smaps_gib(pid):
    """Anonymous / shared / file-backed memory of one process from smaps_rollup (GiB)."""
    try:
        d = {}
        for line in open(f"/proc/{pid}/smaps_rollup"):
            parts = line.split()
            if len(parts) >= 3 and parts[-1] == "kB":
                d[parts[0].rstrip(":")] = int(parts[-2]) / 1024 / 1024
        return {"rss": d.get("Rss"), "pss": d.get('Pss'), "anonymous": d.get("Anonymous"),
                "shared_mem": d.get("Pss_Shmem"), "file_backed": d.get("Pss_File")}
    except OSError:
        return None

def proc_io_read_bytes(pid):
    try:
        for line in open(f"/proc/{pid}/io"):
            if line.startswith("read_bytes:"):
                return int(line.split()[1])
    except OSError:
        return None

def proc_cpu_seconds(pid):
    try:
        f = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
        return (int(f[11]) + int(f[12])) / os.sysconf("SC_CLK_TCK")
    except (OSError, IndexError, ValueError):
        return None

def proc_faults(pid):
    """(minor, major) page faults of one process; major = page had to be read from storage."""
    try:
        f = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
        return int(f[7]), int(f[9])
    except (OSError, IndexError, ValueError):
        return None

def cpu_times():
    out = {}
    try:
        for line in open("/proc/stat"):
            if line.startswith("cpu") and line[3].isdigit():
                p = line.split()
                vals = list(map(int, p[1:]))
                out[p[0]] = (sum(vals), vals[3] + (vals[4] if len(vals) > 4 else 0))
    except OSError:
        pass
    return out

def disk_read_sectors():
    total = 0
    try:
        for line in open("/proc/diskstats"):
            p = line.split()
            name = p[2]
            if re.match(r"^(nvme\d+n\d+|sd[a-z]+|vd[a-z]+)$", name):
                total += int(p[5])
    except OSError:
        return None
    return total

def nvidia_smi_sample():
    q = "clocks.sm,clocks.max.sm,power.draw,temperature.gpu,utilization.gpu,clocks_event_reasons.active"
    try:
        r = subprocess.run(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10)
        v = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
        def num(x):
            try:
                return float(x)
            except ValueError:
                return None
        return {"sm_clock_mhz": num(v[0]), "max_sm_clock_mhz": num(v[1]), "power_w": num(v[2]),
                "temp_c": num(v[3]), "util_pct": num(v[4]), "clock_event_reasons": v[5]}
    except Exception:
        return None

def gpu_processes():
    try:
        r = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
        if r.returncode:
            return None
        out = []
        for line in r.stdout.strip().splitlines():
            p = [x.strip() for x in line.split(",")]
            if len(p) >= 3:
                out.append({"pid": int(p[0]), "name": p[1], "used_memory": p[2]})
        return out
    except Exception:
        return None

def scrape_metrics(base_url):
    """Parse a Prometheus text endpoint into {name: value} (labels dropped, last value wins)."""
    import urllib.request
    try:
        txt = urllib.request.urlopen(base_url.rstrip("/") + "/metrics", timeout=5).read().decode()
    except Exception:
        return None
    out = {}
    for line in txt.splitlines():
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([a-zA-Z_:][\w:]*)(\{[^}]*\})?\s+([-+0-9.eEnaNInf]+)", line)
        if m:
            try:
                out[m.group(1)] = float(m.group(3))
            except ValueError:
                pass
    return out

def get_json(url, timeout=5):
    import urllib.request
    try:
        return json.loads(urllib.request.urlopen(url, timeout=timeout).read().decode())
    except Exception:
        return None

# ---------------- background sampler ----------------

class Sampler(threading.Thread):
    """Samples machine, process and engine state every `interval` seconds into samples.jsonl.

    `marks` lets other code tag windows (e.g. "decode") so per-window deltas can be computed.
    """
    def __init__(self, run_dir, base_url, pid_fn, interval=1.0, other_pids_fn=None):
        super().__init__(daemon=True)
        self.path = os.path.join(run_dir, "samples.jsonl")
        self.base_url, self.pid_fn, self.interval = base_url, pid_fn, interval
        self.stop_evt = threading.Event()
        self.samples = []
        self.lock = threading.Lock()

    def run(self):
        prev_cpu = cpu_times()
        with open(self.path, "a") as f:
            while not self.stop_evt.is_set():
                t = time.time()
                pid = self.pid_fn()
                cur_cpu = cpu_times()
                per_core = {}
                for c, (tot, idle) in cur_cpu.items():
                    if c in prev_cpu:
                        dt = tot - prev_cpu[c][0]
                        di = idle - prev_cpu[c][1]
                        per_core[c] = round(100 * (dt - di) / dt, 1) if dt > 0 else None
                prev_cpu = cur_cpu
                mi = meminfo_gib()
                s = {"t": t, "mem_available_gib": mi.get("MemAvailable"), "cached_gib": mi.get("Cached"),
                     "cpu_per_core": per_core, "disk_read_sectors": disk_read_sectors(),
                     "gpu": nvidia_smi_sample()}
                if pid:
                    s.update({"pid": pid, "proc_mem": proc_smaps_gib(pid),
                              "proc_read_bytes": proc_io_read_bytes(pid), "proc_cpu_s": proc_cpu_seconds(pid),
                              "proc_faults": proc_faults(pid)})
                    # Preserve per-process values: RSS may count shared pages more than once.
                    descendants = process_tree(pid)
                    s['process_tree'] = [{'pid': child, 'memory_gib': proc_smaps_gib(child),
                                          'cpu_seconds': proc_cpu_seconds(child),
                                          'read_bytes': proc_io_read_bytes(child)} for child in descendants]
                    s['tree_pss_gib'] = sum((row['memory_gib'] or {}).get('pss') or 0 for row in s['process_tree'])
                apps = gpu_processes()
                s['gpu_compute_processes'] = apps
                s['other_gpu_processes'] = [row for row in (apps or []) if row['pid'] not in process_tree(pid)] if pid else apps
                if self.base_url:
                    s["metrics"] = scrape_metrics(self.base_url)
                    s["slots"] = get_json(self.base_url.rstrip("/") + "/slots", timeout=2)
                with self.lock:
                    self.samples.append(s)
                f.write(json.dumps(s) + "\n"); f.flush()
                self.stop_evt.wait(max(0.0, self.interval - (time.time() - t)))

    def stop(self):
        self.stop_evt.set(); self.join(timeout=10)

    def window(self, t0, t1):
        with self.lock:
            return [s for s in self.samples if t0 <= s["t"] <= t1]

# ---------------- summaries -> records ----------------

def process_tree(root):
    if not root:
        return []
    children = {}
    for folder in os.scandir('/proc'):
        if folder.name.isdigit():
            try:
                parent = int(open(folder.path + '/stat').read().rsplit(')', 1)[1].split()[1])
                children.setdefault(parent, []).append(int(folder.name))
            except (OSError, ValueError, IndexError):
                pass
    result, pending = [], [root]
    while pending:
        child = pending.pop()
        if child not in result:
            result.append(child)
            pending.extend(children.get(child, []))
    return result

def first_metric(metrics, *names):
    if not metrics:
        return None
    for n in names:
        if n in metrics:
            return metrics[n]
    return None

def summarize_window(rec, sampler, t0, t1, label, tokens_generated=None, engine_rates=False):
    """Turn the samples of one window into telemetry records.

    engine_rates: also derive prefill / decode speed, generated tokens and SSD reads per generated token
    for the whole window from the engine's cumulative /metrics counters (used for benchmark windows).
    """
    w = sampler.window(t0, t1)
    win = {"start": datetime.fromtimestamp(t0, timezone.utc).isoformat(timespec="seconds"),
           "end": datetime.fromtimestamp(t1, timezone.utc).isoformat(timespec="seconds"), "label": label}
    if len(w) < 2:
        return  # window shorter than the sampling interval; nothing reliable to summarize
    avail = [s["mem_available_gib"] for s in w if s.get("mem_available_gib") is not None]
    rec.add("M.mem_available_min", round(min(avail), 2) if avail else None, source="/proc/meminfo", window=win)
    mems = [s["proc_mem"] for s in w if s.get("proc_mem")]
    if mems:
        peak = {k: round(max((m[k] or 0) for m in mems), 2) for k in ("rss", "anonymous", "shared_mem", "file_backed")}
        peak["host_working_set"] = round(max((m["anonymous"] or 0) + (m["shared_mem"] or 0) for m in mems), 2)
        rec.add("M.host_memory", peak, source="/proc/<pid>/smaps_rollup", window=win)
    else:
        rec.add("M.host_memory", None, "unavailable", "/proc/<pid>/smaps_rollup", win, "engine pid not found")
    mets_all = [s["metrics"] for s in w if s.get("metrics")]
    def mdelta(name):
        v = [m.get(name) for m in mets_all if m.get(name) is not None]
        return v[-1] - v[0] if len(v) >= 2 else None
    if engine_rates:
        pt, ps = mdelta("llamacpp:prompt_tokens_total"), mdelta("llamacpp:prompt_seconds_total")
        dt_, ds_ = mdelta("llamacpp:tokens_predicted_total"), mdelta("llamacpp:tokens_predicted_seconds_total")
        if pt and ps:
            rec.add("L3.prefill_rate", round(pt / ps, 2), source="engine /metrics deltas (prompt_tokens_total / prompt_seconds_total)",
                    window=win, note=f"{int(pt)} prompt tokens computed in {ps:.0f} s of engine prefill time")
        if dt_ and ds_:
            rec.add("L3.decode_rate", round(dt_ / ds_, 2), source="engine /metrics deltas (tokens_predicted_total / tokens_predicted_seconds_total)",
                    window=win, note=f"{int(dt_)} tokens generated in {ds_:.0f} s of engine decode time")
        if tokens_generated is None and dt_:
            tokens_generated = int(dt_)
        drafts = mdelta("llamacpp:spec_decode_num_draft_tokens_total")
        if drafts:
            acc = mdelta("llamacpp:spec_decode_num_accepted_tokens_total") or 0
            rec.add("L3.draft_acceptance", round(100 * acc / drafts, 1), source="engine /metrics deltas", window=win)
        elif drafts == 0:
            rec.add("L3.draft_acceptance", None, "not_applicable", "engine /metrics", win,
                    "no draft tokens: speculative decoding is not enabled")
    rb = [s["proc_read_bytes"] for s in w if s.get("proc_read_bytes") is not None]
    if len(rb) >= 2 and tokens_generated:
        rec.add("M.storage_read_per_token", round((rb[-1] - rb[0]) / 1e9 / tokens_generated, 4),
                source="/proc/<pid>/io read_bytes", window=win,
                note=f"{(rb[-1]-rb[0])/1e9:.2f} GB read for {tokens_generated} generated tokens"
                + ("; whole window, so prefill reads are included" if engine_rates else ""))
    elif tokens_generated:
        rec.add("M.storage_read_per_token", None, "unavailable", "/proc/<pid>/io", win)
    ds = [s["disk_read_sectors"] for s in w if s.get("disk_read_sectors") is not None]
    if len(ds) >= 2 and t1 > t0:
        rec.add("L6.storage_read_rate", round((ds[-1] - ds[0]) * 512 / 1e6 / (t1 - t0), 1),
                source="/proc/diskstats", window=win, note="average over window, all NVMe/SATA devices")
    cpu = [s["proc_cpu_s"] for s in w if s.get("proc_cpu_s") is not None]
    if len(cpu) >= 2:
        rec.add("L1.server_cpu", round(100 * (cpu[-1] - cpu[0]) / (w[-1]["t"] - w[0]["t"]), 1),
                source="/proc/<pid>/stat", window=win, note="100 = one core fully busy")
    cores = {}
    for s in w:
        for c, v in (s.get("cpu_per_core") or {}).items():
            if v is not None:
                cores.setdefault(c, []).append(v)
    if cores:
        rec.add("L6.cpu_per_core", {c: round(sum(v) / len(v), 1) for c, v in sorted(cores.items())},
                source="/proc/stat", window=win, note="mean busy % per core")
    gpus = [s["gpu"] for s in w if s.get("gpu")]
    if gpus:
        def stat(k, f):
            v = [g[k] for g in gpus if g.get(k) is not None]
            return round(f(v), 1) if v else None
        rec.add("L6.gpu_health", {"sm_clock_mhz_min": stat("sm_clock_mhz", min),
                                  "sm_clock_mhz_mean": stat("sm_clock_mhz", lambda v: sum(v) / len(v)),
                                  "max_sm_clock_mhz": stat("max_sm_clock_mhz", max),
                                  "power_w_mean": stat("power_w", lambda v: sum(v) / len(v)),
                                  "temp_c_max": stat("temp_c", max),
                                  "util_pct_mean": stat("util_pct", lambda v: sum(v) / len(v)),
                                  "clock_event_reasons": sorted({g["clock_event_reasons"] for g in gpus})},
                source="nvidia-smi", window=win)
    else:
        rec.add("L6.gpu_health", None, "unavailable", "nvidia-smi", win)
    mets = [s["metrics"] for s in w if s.get("metrics")]
    if mets:
        busy = [first_metric(m, "llamacpp:requests_processing", "vllm:num_requests_running") for m in mets]
        wait = [first_metric(m, "llamacpp:requests_deferred", "vllm:num_requests_waiting") for m in mets]
        rec.add("L2.requests_active", {"running_max": max([b for b in busy if b is not None], default=None),
                                       "waiting_max": max([x for x in wait if x is not None], default=None)},
                source="engine /metrics", window=win)
        rows = [first_metric(m, "llamacpp:n_busy_slots_per_decode") for m in mets]
        rows = [r for r in rows if r is not None]
        rec.add("L2.batch_rows", round(sum(rows) / len(rows), 2) if rows else None,
                source="engine /metrics (llamacpp:n_busy_slots_per_decode)", window=win)
        kv = [first_metric(m, "llamacpp:kv_cache_usage_ratio", "vllm:kv_cache_usage_perc") for m in mets]
        kv = [k for k in kv if k is not None]
        if kv:
            rec.add("M.kv_utilization", round(100 * max(kv), 1), source="engine /metrics", window=win, note="peak in window")
        else:
            kv_from_slots(rec, w, win)
        def delta(name):
            v = [m.get(name) for m in mets if m.get(name) is not None]
            return v[-1] - v[0] if len(v) >= 2 else None
        cached, processed = delta("llamacpp:prompt_tokens_cached_total"), delta("llamacpp:prompt_tokens_total")
        if cached is not None and processed is not None and cached + processed > 0:
            rec.add("M.prefix_cache_hit", round(100 * cached / (cached + processed), 1),
                    source="engine /metrics (prompt_tokens_cached_total, prompt_tokens_total)", window=win,
                    note=f"{int(cached)} prompt tokens reused, {int(processed)} computed")
        elif cached is not None:
            rec.add("M.prefix_cache_hit", None, "unavailable", "engine /metrics", win, "no prompt tokens in window")
    else:
        for tid in ("L2.requests_active", "L2.batch_rows"):
            rec.add(tid, None, "unavailable", "engine /metrics", win, "metrics endpoint not reachable or disabled")
        kv_from_slots(rec, w, win)
    slots = [s["slots"] for s in w if isinstance(s.get("slots"), list)]
    if slots:
        last = slots[-1]
        states = {"processing": sum(1 for x in last if x.get("is_processing")),
                  "idle": sum(1 for x in last if not x.get("is_processing")), "total": len(last)}
        rec.add("L2.slot_states", states, source="engine /slots", window=win, note="state at end of window")
    else:
        rec.add("L2.slot_states", None, "unavailable", "engine /slots", win)

def kv_from_slots(rec, w, win):
    """llama.cpp b11671 has no KV-usage metric. Use /slots: tokens held per slot / slot context size.

    Tokens stay in a slot after its request ends (they are the prefix cache), so this is KV cells in use,
    not only tokens of running requests.
    """
    vals = []
    for s in w:
        sl = s.get("slots")
        if isinstance(sl, list) and sl:
            ctx = sum(x.get("n_ctx") or 0 for x in sl)
            held = sum(x.get("n_prompt_tokens") or 0 for x in sl)
            if ctx:
                vals.append(100 * held / ctx)
    if vals:
        rec.add("M.kv_utilization", round(max(vals), 1), source="engine /slots (n_prompt_tokens / n_ctx)",
                window=win, note="peak in window; includes tokens kept for prefix reuse")
    else:
        rec.add("M.kv_utilization", None, "unavailable", "engine /metrics and /slots", win)

def machine_static(rec, model_dir, own_pids=()):
    du = shutil.disk_usage(model_dir if os.path.exists(model_dir) else "/")
    rec.add("L6.storage_capacity", {"total_gb": round(du.total / 1e9, 1), "free_gb": round(du.free / 1e9, 1),
                                    "path": model_dir}, source="statvfs")
    procs = gpu_processes()
    if procs is None:
        rec.add("L6.other_workloads", None, "unavailable", "nvidia-smi")
        return []
    others = [p for p in procs if p["pid"] not in own_pids]
    if others:
        rec.comparable = False
    rec.add("L6.other_workloads", others, source="nvidia-smi --query-compute-apps",
            note="non-empty list => speed and memory results of this run are marked not comparable")
    return others
