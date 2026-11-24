#!/usr/bin/env python3
"""Portable resource observation: tegrastats / proc / sysfs_tegra / nvml -> JSONL (resource-observe/0)."""
import argparse, glob, hashlib, json, os, re, shutil, socket, subprocess, sys, threading, queue, time
from datetime import datetime, timezone
from io_watchdog import IOSampler, watchdog

SCHEMA = "resource-observe/0"
DEVFREQ_ROOT = "/sys/class/devfreq"
ALL_BACKENDS = ["tegrastats", "proc", "sysfs_tegra", "nvml", "io"]


def M(name, value, unit, scope, source):
    return {"name": name, "value": value, "unit": unit, "scope": scope, "source": source}


def U(name, backend, reason):
    return {"name": name, "backend": backend, "reason": reason}


def campaign_host_id():
    try:
        with open(next((q for q in map(os.path.expanduser, ("~/.config/jiuwenswarm-factory/host_id", "~/.config/siminfeng/host_id")) if os.path.exists(q)), os.path.expanduser("~/.config/jiuwenswarm-factory/host_id"))) as f:
            return f.read().strip() or socket.gethostname()
    except OSError:
        return socket.gethostname()


def record(backend, seq, metrics, unavailable=(), parse_errors=(), host_id=None, mono=None):
    return {"schema": SCHEMA, "ts": datetime.now(timezone.utc).isoformat(),
            "mono_s": time.monotonic() if mono is None else mono,
            "host_id": host_id or campaign_host_id(), "backend": backend, "seq": seq,
            "metrics": list(metrics), "unavailable": list(unavailable), "parse_errors": list(parse_errors)}


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


# ---------------- tegrastats ----------------
_RAM = re.compile(r"RAM (\d+)/(\d+)MB(?: \(lfb (\d+)x(\d+)MB\))?")
_SWAP = re.compile(r"SWAP (\d+)/(\d+)MB(?: \(cached (\d+)MB\))?")
_CPU = re.compile(r"CPU \[([^\]]*)\]")
_GR3D = re.compile(r"GR3D_FREQ (\d+)%(?:@\[?(\d+)\]?)?")
_EMC = re.compile(r"EMC_FREQ (\d+)%(?:@(\d+))?")
_TEMP = re.compile(r"\b([A-Za-z0-9_]+)@(-?\d+(?:\.\d+)?)C\b")
_RAIL = re.compile(r"\b([A-Z][A-Z0-9_]+) (\d+)mW/(\d+)mW")


def line_hash(line):
    return hashlib.sha256(line.encode("utf-8", "replace")).hexdigest()[:16]


def parse_tegrastats(line):
    """Return (metrics, unavailable, parse_errors) for one tegrastats line. Never raises."""
    line = (line or "").strip()
    S, B = "system-shared-dram", "tegrastats"
    if not line:
        return [], [], [{"error": "empty line", "line_sha256_16": line_hash(line)}]
    m, un, errs = [], [], []
    r = _RAM.search(line)
    if r:
        m += [M("ram_used", int(r[1]), "MiB", S, B), M("ram_total", int(r[2]), "MiB", S, B)]
        if r[3]:
            m.append(M("ram_lfb", int(r[3]) * int(r[4]), "MiB", S, B))
        else:
            un.append(U("ram_lfb", B, "lfb not in line"))
    else:
        un.append(U("ram_used", B, "RAM field missing or truncated"))
        errs.append({"error": "RAM field not parsed", "line_sha256_16": line_hash(line)})
    s = _SWAP.search(line)
    if s:
        m += [M("swap_used", int(s[1]), "MiB", "system", B), M("swap_total", int(s[2]), "MiB", "system", B)]
        if s[3] is not None:
            m.append(M("swap_cached", int(s[3]), "MiB", "system", B))
    else:
        un.append(U("swap_used", B, "SWAP field missing"))
    c = _CPU.search(line)
    if c:
        for i, ent in enumerate(x.strip() for x in c[1].split(",")):
            cm = re.fullmatch(r"(\d+)%(?:@(\d+))?", ent)
            if cm:
                m.append(M("cpu%d_load" % i, int(cm[1]), "percent", "system", B))
                if cm[2]:
                    m.append(M("cpu%d_freq" % i, int(cm[2]), "MHz", "system", B))
            elif ent == "off":
                un.append(U("cpu%d_load" % i, B, "core offline"))
            else:
                errs.append({"error": "bad cpu entry %r" % ent, "line_sha256_16": line_hash(line)})
    else:
        un.append(U("cpu_load", B, "CPU field missing"))
    g = _GR3D.search(line)
    if g:
        m.append(M("gpu_util", int(g[1]), "percent", "gpu", B))
        if g[2]:
            m.append(M("gpu_freq", int(g[2]), "MHz", "gpu", B))
        else:
            un.append(U("gpu_freq", B, "no @MHz in GR3D_FREQ"))
    else:
        un.append(U("gpu_util", B, "GR3D_FREQ missing"))
    e = _EMC.search(line)
    if e:
        m.append(M("emc_util", int(e[1]), "percent", "system", B))
        if e[2]:
            m.append(M("emc_freq", int(e[2]), "MHz", "system", B))
    else:
        un.append(U("emc_freq", B, "EMC_FREQ not reported on this board/release"))
    for name, val in _TEMP.findall(line):
        m.append(M("temp_" + name, float(val), "celsius", "sensor", B))
    for name, inst, avg in _RAIL.findall(line):
        m += [M("power_%s_instant" % name, int(inst), "mW", "rail", B),
              M("power_%s_avg" % name, int(avg), "mW", "rail", B)]
    if not m:
        errs.append({"error": "no fields parsed", "line_sha256_16": line_hash(line)})
    return m, un, errs


class TegrastatsReader:
    def __init__(self, interval_ms, cmd=None):
        self.q = queue.Queue()
        self.p = subprocess.Popen(cmd or ["tegrastats", "--interval", str(interval_ms)], stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, errors="replace")
        threading.Thread(target=lambda: [self.q.put(l) for l in self.p.stdout], daemon=True).start()

    def drain(self):
        out = []
        while True:
            try:
                out.append(self.q.get_nowait())
            except queue.Empty:
                return out

    def close(self):
        self.p.terminate()


def tegrastats_available():
    return (True, "") if shutil.which("tegrastats") else (False, "tegrastats not on PATH")


# ---------------- proc ----------------
_NVMAP = re.compile(r"^(NvMap\w*|Nvmap\w*)")


def parse_meminfo(text):
    d = {}
    for l in (text or "").splitlines():
        k, _, v = l.partition(":")
        p = v.split()
        if p and p[0].isdigit():
            d[k] = int(p[0]) * (1 if len(p) > 1 and p[1] == "B" else 1024) if len(p) > 1 else int(p[0])
    return d


def parse_status_kb(text, key):
    mm = re.search(r"^%s:\s+(\d+) kB" % key, text or "", re.M)
    return int(mm[1]) * 1024 if mm else None


def proc_sample(root="/proc", pid=None, cgroup=None, cgroup_root="/sys/fs/cgroup"):
    B = "proc"
    m, un = [], []
    mi = _read(os.path.join(root, "meminfo"))
    if mi is None:
        un.append(U("meminfo", B, "%s/meminfo unreadable" % root))
    else:
        d = parse_meminfo(mi)
        for name, key, unit in [("mem_total", "MemTotal", "MiB"), ("mem_available", "MemAvailable", "MiB"),
                                ("mem_cached", "Cached", "MiB"), ("swap_total", "SwapTotal", "MiB"),
                                ("swap_free", "SwapFree", "MiB")]:
            if key in d:
                m.append(M(name, round(d[key] / 1048576, 3), unit, "system", "meminfo:" + key))
            else:
                un.append(U(name, B, "%s absent from meminfo" % key))
        nv = [k for k in d if _NVMAP.match(k)]
        for k in nv:
            m.append(M("meminfo_" + k, round(d[k] / 1048576, 3), "MiB", "system", "meminfo:" + k))
        if not nv:
            un.append(U("nvmap", B, "no NvMap* fields in meminfo"))
    la = _read(os.path.join(root, "loadavg"))
    p = la.split() if la else []
    if len(p) >= 3:
        try:
            for n, v in zip(("load1", "load5", "load15"), p[:3]):
                m.append(M(n, float(v), "load", "system", "loadavg"))
        except ValueError:
            un.append(U("loadavg", B, "unparseable loadavg"))
    else:
        un.append(U("loadavg", B, "loadavg missing/short"))
    if pid is not None:
        st = _read(os.path.join(root, str(pid), "status"))
        for name, key in (("pid_rss", "VmRSS"), ("pid_hwm", "VmHWM")):
            v = parse_status_kb(st, key) if st else None
            if v is None:
                un.append(U(name, B, "pid %s status missing or no %s" % (pid, key)))
            else:
                m.append(M(name, round(v / 1048576, 3), "MiB", "process", "status:" + key))
    if cgroup:
        base = os.path.join(cgroup_root, cgroup.lstrip("/")) if not os.path.isabs(cgroup) or not os.path.isdir(cgroup) else cgroup
        note = "cgroup memory may not include nvmap/driver GPU allocations on Tegra"
        for name, f in (("cgroup_current", "memory.current"), ("cgroup_peak", "memory.peak"), ("cgroup_max", "memory.max")):
            t = _read(os.path.join(base, f))
            t = t.strip() if t else None
            if t is None:
                un.append(U(name, B, "%s unreadable in %s" % (f, base)))
            elif t == "max":
                un.append(U(name, B, "unlimited (max)"))
            elif t.isdigit():
                x = M(name, round(int(t) / 1048576, 3), "MiB", "cgroup", f)
                x["accounting_note"] = note
                m.append(x)
            else:
                un.append(U(name, B, "unparseable %r" % t))
    return m, un


# ---------------- sysfs_tegra ----------------
def discover_gpu_devfreq(root=DEVFREQ_ROOT):
    return next(iter(sorted(glob.glob(os.path.join(root, "*.gpu")))), None)


def frequency_sample(devfreq=None, devfreq_root=DEVFREQ_ROOT):
    """Read public devfreq clocks without sudo; raw frequencies are Hz."""
    devfreq = devfreq or discover_gpu_devfreq(devfreq_root)
    m, un = [], []
    t = (_read(os.path.join(devfreq, "cur_freq")) or "").strip() if devfreq else ""
    if t.isdigit():
        m.append(M("gpu_freq", int(t), "Hz", "gpu", str(devfreq) + "/cur_freq"))
    else:
        un.append(U("gpu_freq", "sysfs_tegra", "*.gpu/cur_freq absent or unreadable"))
    emc = sorted(glob.glob(os.path.join(devfreq_root, "*emc*")))
    for path in emc:
        t = (_read(os.path.join(path, "cur_freq")) or "").strip()
        if t.isdigit():
            m.append(M("emc_freq", int(t), "Hz", "system", path + "/cur_freq"))
            break
    return m, un


def sysfs_sample(devfreq=None, thermal="/sys/class/thermal", nvpmodel_mode=None, query_nvpmodel=True):
    B = "sysfs_tegra"
    m, un = [], []
    devfreq = devfreq or discover_gpu_devfreq()
    if not devfreq or not os.path.isdir(devfreq):
        un.append(U("gpu_devfreq", B, "%s absent (not a Jetson?)" % devfreq))
    else:
        for n, f in (("gpu_freq_cur", "cur_freq"), ("gpu_freq_min", "min_freq"), ("gpu_freq_max", "max_freq")):
            t = (_read(os.path.join(devfreq, f)) or "").strip()
            if t.isdigit():
                m.append(M(n, int(t) / 1e6, "MHz", "gpu", "devfreq:" + f))
            else:
                un.append(U(n, B, "%s unreadable" % f))
    fm, fu = frequency_sample(devfreq)
    m.extend(fm)
    un.extend(fu)
    zones = sorted(glob.glob(os.path.join(thermal, "thermal_zone*")))
    if not zones:
        un.append(U("thermal", B, "no thermal zones"))
    for z in zones:
        ty = (_read(os.path.join(z, "type")) or "").strip()
        t = (_read(os.path.join(z, "temp")) or "").strip()
        zn = os.path.basename(z)
        if ty and re.fullmatch(r"-?\d+", t):
            m.append(M("thermal_%s_%s" % (zn, ty), int(t) / 1000.0, "celsius", "sensor", "thermal:" + zn))
        else:
            un.append(U("thermal_" + zn, B, "type/temp unreadable"))
    mode = nvpmodel_mode
    if mode is None and query_nvpmodel and shutil.which("nvpmodel"):
        try:
            out = subprocess.run(["nvpmodel", "-q"], capture_output=True, text=True, timeout=5).stdout
            mm = re.search(r"NV Power Mode:\s*(\S+)", out)
            mode = mm[1] if mm else None
        except Exception:
            mode = None
    if mode:
        m.append(M("nvpmodel_mode", mode, "string", "system", "nvpmodel -q"))
    else:
        un.append(U("nvpmodel_mode", B, "not provided and query failed/unavailable"))
    return m, un


# ---------------- nvml ----------------
GPU_FIELDS = [("gpu_mem_used", "MiB"), ("gpu_mem_total", "MiB"), ("gpu_util", "percent"),
              ("gpu_sm_clock", "MHz"), ("gpu_temp", "celsius"), ("gpu_power", "W")]


def parse_nvml_csv(text, apps_text=""):
    B, S = "nvml", "device-discrete"
    m, un = [], []
    rows = [l for l in (text or "").splitlines() if l.strip()]
    if not rows:
        return [], [U("gpu", B, "no nvidia-smi output")]
    for gi, row in enumerate(rows):
        cells = [c.strip() for c in row.split(",")]
        sfx = "" if len(rows) == 1 else str(gi)
        for (name, unit), c in zip(GPU_FIELDS, cells + [None] * (len(GPU_FIELDS) - len(cells))):
            try:
                if c is None or re.search(r"N/A|Not Supported", c, re.I) or c == "":
                    raise ValueError
                m.append(M(name + sfx, float(c), unit, S, "nvidia-smi"))
            except ValueError:
                un.append(U(name + sfx, B, "field %r N/A or missing" % c))
    for l in (apps_text or "").splitlines():
        c = [x.strip() for x in l.split(",")]
        if len(c) >= 3 and c[0].isdigit() and re.fullmatch(r"\d+(\.\d+)?", c[-1]):
            m.append(M("gpu_proc_mem_pid%s" % c[0], float(c[-1]), "MiB", "process", "nvidia-smi compute-apps"))
    return m, un


def nvml_available():
    if not shutil.which("nvidia-smi"):
        return False, "nvidia-smi not on PATH"
    return True, ""


def nvml_sample(runner=None):
    runner = runner or (lambda a: subprocess.run(a, capture_output=True, text=True, timeout=10))
    q = ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,clocks.sm,temperature.gpu,power.draw",
         "--format=csv,noheader,nounits"]
    try:
        r = runner(q)
        if r.returncode != 0:
            return [], [U("gpu", "nvml", "nvidia-smi failed: %s" % (r.stderr or "").strip()[:100])]
        a = runner(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"])
        m, un = parse_nvml_csv(r.stdout, a.stdout if a.returncode == 0 else "")
    except Exception as ex:
        return [], [U("gpu", "nvml", "nvidia-smi error: %s" % ex)]
    if not m:
        un.append(U("gpu_mem", "nvml", "no usable memory fields (integrated GPU?)"))
    return m, un


# ---------------- capabilities / sampling ----------------
def capabilities(devfreq=None, root="/proc", runner=None):
    caps = {}
    ok, why = tegrastats_available()
    caps["tegrastats"] = {"available": ok, "reason": why or "tegrastats found",
                          "metrics": ["ram_used", "ram_total", "ram_lfb", "swap_*", "cpuN_load/freq", "gpu_util", "gpu_freq", "emc_freq", "temp_*", "power_*"] if ok else []}
    pm, pu = proc_sample(root)
    caps["proc"] = {"available": bool(pm), "reason": "ok" if pm else "no /proc fields", "metrics": [x["name"] for x in pm],
                    "missing": [x["name"] + ": " + x["reason"] for x in pu]}
    sm, su = sysfs_sample(devfreq, query_nvpmodel=True)
    has = bool(devfreq and os.path.isdir(devfreq)) if devfreq else bool(discover_gpu_devfreq())
    caps["sysfs_tegra"] = {"available": has, "reason": "ok" if has else "no Tegra GPU devfreq node",
                           "metrics": [x["name"] for x in sm][:6], "missing": [x["name"] + ": " + x["reason"] for x in su][:6]}
    ok, why = nvml_available()
    if ok:
        nm, nu = nvml_sample(runner)
        ok = bool(nm)
        why = "ok" if ok else (nu[-1]["reason"] if nu else "no memory fields")
    caps["nvml"] = {"available": ok, "reason": why or "ok", "metrics": [n for n, _ in GPU_FIELDS] if ok else []}
    im, iu = IOSampler(procroot=root).sample()
    caps["io"] = {"available": bool(im), "reason": "ok" if im else "no I/O counters",
                  "metrics": [x["name"] for x in im], "missing": iu}
    return caps


def resolve_backends(spec):
    if spec == "auto":
        c = capabilities()
        return [b for b in ALL_BACKENDS if c[b]["available"]]
    bs = [b.strip() for b in spec.split(",") if b.strip()]
    bad = [b for b in bs if b not in ALL_BACKENDS]
    if bad:
        raise SystemExit("unknown backend(s): %s" % bad)
    return bs


def sample_once(backend, seq, a):
    if backend == "io":
        m, u = a.io_sampler.sample()
    elif backend == "proc":
        m, u = proc_sample(pid=a.pid, cgroup=a.cgroup)
    elif backend == "sysfs_tegra":
        m, u = sysfs_sample(nvpmodel_mode=a.nvpmodel_mode)
    elif backend == "nvml":
        m, u = nvml_sample()
    else:
        raise ValueError(backend)
    return record(backend, seq, m, u)


def observed_tegrastats(line):
    m, u, e = parse_tegrastats(line)
    clocks, missing = frequency_sample()
    have = {x["name"] for x in clocks}
    m = [x for x in m if x["name"] not in have] + clocks
    u = [x for x in u if x["name"] not in have]
    u.extend(x for x in missing if not any(y["name"] == x["name"] for y in m + u))
    return m, u, e


def cmd_sample(a):
    a.io_sampler = IOSampler(path=a.path, device=a.device, pid=a.pid,
                             pid_from_cgroup=a.pid_from_cgroup, cgroup=a.cgroup)
    backends = resolve_backends(a.backends)
    seq = 0
    end = time.monotonic() + a.duration_s if a.duration_s else None
    tg = None
    n = 0
    with open(a.out, "w") as out:
        def emit(r):
            out.write(json.dumps(r) + "\n"); out.flush()
        for b in backends:
            if b == "tegrastats":
                ok, why = tegrastats_available()
                if ok:
                    tg = TegrastatsReader(a.interval_ms)
                else:
                    emit(record(b, seq, [], [U("tegrastats", b, why)])); seq += 1
        try:
            while True:
                t0 = time.monotonic()
                if tg:
                    for l in tg.drain():
                        m, u, e = observed_tegrastats(l)
                        emit(record("tegrastats", seq, m, u, e)); seq += 1
                for b in backends:
                    if b != "tegrastats":
                        emit(sample_once(b, seq, a)); seq += 1
                n += 1
                if end and time.monotonic() >= end:
                    break
                time.sleep(max(0, a.interval_ms / 1000 - (time.monotonic() - t0)))
            if tg:
                time.sleep(a.interval_ms / 1000 + 0.1)
                for l in tg.drain():
                    m, u, e = observed_tegrastats(l)
                    emit(record("tegrastats", seq, m, u, e)); seq += 1
        finally:
            if tg:
                tg.close()
    return 0


def summarize(path, interval_ms=None):
    stats, times, nrec, errs = {}, {}, {}, 0
    for l in open(path):
        if not l.strip():
            continue
        r = json.loads(l)
        b = r["backend"]
        nrec[b] = nrec.get(b, 0) + 1
        times.setdefault(b, []).append(r["mono_s"])
        errs += len(r.get("parse_errors", []))
        for x in r["metrics"]:
            if isinstance(x["value"], (int, float)):
                stats.setdefault((b, x["name"], x["unit"], x["scope"]), []).append(x["value"])
    metrics = {"%s/%s" % (k[0], k[1]): {"unit": k[2], "scope": k[3], "n": len(v), "min": min(v), "max": max(v),
               "mean": sum(v) / len(v), "high_water": max(v)} for k, v in stats.items()}
    cov = {}
    for b, ts in times.items():
        ts = sorted(ts)
        d = [y - x for x, y in zip(ts, ts[1:])]
        iv = interval_ms / 1000 if interval_ms else (sorted(d)[len(d) // 2] if d else 0)
        span = ts[-1] - ts[0]
        exp = int(round(span / iv)) + 1 if iv else len(ts)
        gaps = [{"after_mono_s": x, "gap_s": round(y - x, 3)} for x, y in zip(ts, ts[1:]) if iv and y - x > 2 * iv]
        cov[b] = {"received": len(ts), "expected": exp, "interval_s": iv, "gaps_gt_2x": gaps}
    return {"metrics": metrics, "coverage": cov, "parse_error_count": errs}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="resource_observe.py")
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("sample")
    s.add_argument("--backends", default="auto")
    s.add_argument("--interval-ms", type=int, default=500)
    s.add_argument("--duration-s", type=float, default=0)
    pids = s.add_mutually_exclusive_group()
    pids.add_argument("--pid", type=int)
    pids.add_argument("--pid-from-cgroup")
    s.add_argument("--path", default=".")
    s.add_argument("--device")
    s.add_argument("--cgroup")
    s.add_argument("--nvpmodel-mode")
    s.add_argument("--out", required=True)
    z = sp.add_parser("summarize"); z.add_argument("file"); z.add_argument("--interval-ms", type=int)
    sp.add_parser("capabilities")
    w = sp.add_parser("watchdog")
    w.add_argument("--min-available-mib", type=float, default=900)
    w.add_argument("--max-swap-used-mib", type=float, default=512)
    w.add_argument("--max-swap-rate-mibs", type=float, default=20)
    w.add_argument("--interval-ms", type=int, default=250)
    target = w.add_mutually_exclusive_group()
    target.add_argument("--kill-cgroup")
    target.add_argument("--kill-pid", type=int)
    target.add_argument("--kill-cmd")
    w.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd in ("sample", "watchdog") and a.interval_ms <= 0:
        ap.error("--interval-ms must be positive")
    if a.cmd == "sample" and (a.duration_s < 0 or (a.pid is not None and a.pid <= 0)):
        ap.error("duration must be nonnegative and pid positive")
    if a.cmd == "watchdog":
        if a.kill_pid is not None and a.kill_pid <= 0:
            ap.error("--kill-pid must be positive (process groups are not allowed)")
        if any(not __import__('math').isfinite(v) or v < 0 for v in
               (a.min_available_mib, a.max_swap_used_mib, a.max_swap_rate_mibs)):
            ap.error("watchdog thresholds must be finite and nonnegative")
        with open(a.out, "w") as out:
            seq = 0
            def emit(event, data):
                nonlocal seq
                r = record("watchdog", seq, [])
                r.update(event=event, **data)
                out.write(json.dumps(r) + "\n")
                out.flush()
                seq += 1
            return watchdog(a, emit)
    if a.cmd == "sample":
        return cmd_sample(a)
    if a.cmd == "summarize":
        print(json.dumps(summarize(a.file, a.interval_ms), indent=1)); return 0
    print(json.dumps(capabilities(), indent=1)); return 0


if __name__ == "__main__":
    sys.exit(main())
