"""Orchestration: one run = manifest + server + sampler + probe + benchmarks + token probs + report."""
import hashlib, json, os, platform, re, shutil, signal, subprocess, time, tomllib
from datetime import datetime, timezone
from pathlib import Path
from . import __version__
from .telemetry import Recorder, Sampler, machine_static, summarize_window, proc_io_read_bytes, meminfo_gib, now, CATALOG, NSYS_IDS
from .engine import Server, healthy, find_pid, speed_probe, token_probs, stream_completion, filler_prompt
from . import profile as nsys_profile
from .gguf_info import expert_summary
from .benchmarks import estimate_minutes, run_one

def load(path):
    with open(path, "rb") as f:
        return tomllib.load(f)

def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return None

def sha256_cached(path, cache_dir):
    """Hash of the checkpoint files; cached by (path, size, mtime) because 300 GB takes minutes."""
    os.makedirs(cache_dir, exist_ok=True)
    st = os.stat(path)
    key = hashlib.sha1(f"{path}|{st.st_size}|{st.st_mtime}".encode()).hexdigest()
    cf = os.path.join(cache_dir, key + ".sha256")
    if os.path.exists(cf):
        return open(cf).read().strip()
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    open(cf, "w").write(h.hexdigest())
    return h.hexdigest()

def checkpoint_files(cfg):
    p = cfg["checkpoint"]["path"]
    if os.path.isdir(p):
        index = Path(p) / 'model.safetensors.index.json'
        if index.exists():
            shards = sorted(set(json.loads(index.read_text())['weight_map'].values()))
            root = Path(p).resolve()
            paths = [(root / name).resolve() for name in shards]
            if any(not path.is_relative_to(root) or not path.is_file() for path in paths):
                raise ValueError('Missing or unsafe safetensors shard in index')
            return [str(path) for path in paths]
        safe = sorted(Path(p).glob('*.safetensors'))
        if safe:
            return [str(path) for path in safe]
        return sorted(os.path.join(p, f) for f in os.listdir(p) if f.endswith(".gguf"))
    # split GGUF: name-00001-of-00005.gguf -> all parts
    m = re.match(r"(.*)-\d{5}-of-(\d{5})\.gguf$", p)
    if m:
        d = os.path.dirname(p) or "."
        return sorted(os.path.join(d, f) for f in os.listdir(d)
                      if re.match(re.escape(os.path.basename(m.group(1))) + r"-\d{5}-of-" + m.group(2) + r"\.gguf$", f))
    return [p]

def startup_plan_from_log(log_text):
    """llama.cpp prints buffer sizes at load. Sum them by device (MiB -> GiB)."""
    plan = {}
    for m in re.finditer(r"(\w+(?:_\w+)*)\s+(model|KV|compute)\s+buffer size\s*=\s*([\d.]+)\s*MiB", log_text):
        dev, kind, mib = m.group(1), m.group(2), float(m.group(3))
        plan.setdefault(kind, {}).setdefault(dev, 0.0)
        plan[kind][dev] += mib / 1024
    return {k: {d: round(v, 2) for d, v in devs.items()} for k, devs in plan.items()} or None

class MemoryFloorExceeded(KeyboardInterrupt):
    """Interrupt blocking engine and benchmark calls when host memory is too low."""


def budget_estimate(cfg, set_name, probe):
    if not probe or [row["depth_words"] for row in probe] != cfg["probe"]["depth_words"]:
        return None
    prefill = sorted(row.get("engine", {}).get("prompt_per_second") or row["prefill_tok_s_client"] or 0
                     for row in probe)
    decode = sorted(row.get("engine", {}).get("predicted_per_second") or row["decode_tok_s_client"] or 0
                    for row in probe)
    if prefill[0] <= 0 or decode[0] <= 0:
        return None
    pf, dc = prefill[len(probe) // 2], decode[len(probe) // 2]
    settings = cfg["sets"][set_name]
    rows, total = estimate_minutes(settings["budget"], pf, dc)
    return {"prefill_tok_s": pf, "decode_tok_s": dc, "rows": rows, "total_minutes": total,
            "budget_minutes": settings.get("time_budget_min")}


def over_budget(estimate):
    return estimate["budget_minutes"] is not None and estimate["total_minutes"] > estimate["budget_minutes"]


def matching_probe(cfg, manifest, out_root):
    # The HTTP read timeout does not change the prompts or generation settings.
    probe_settings = {key: value for key, value in cfg["probe"].items() if key != "read_timeout_s"}
    for folder in sorted(Path(out_root).glob("*-probe"), reverse=True):
        try:
            reference = json.loads((folder / "manifest.json").read_text())
            report = json.loads((folder / "report.json").read_text())
            reference_probe = load(folder / "config.toml")["probe"]
        except (OSError, ValueError, KeyError):
            continue
        reference_probe.pop("read_timeout_s", None)
        if (report.get("status") == "probe only" and reference_probe == probe_settings
                and all(reference.get(key) == manifest[key]
                        for key in ("engine", "checkpoint", "generation", "environment"))):
            return report
    return None


def run(config_path, set_name, out_root, no_server=False, min_mem_available_gib=None, *,
        reuse_probe=False, resume_from=None):
    cfg = load(config_path)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{set_name}"
    run_dir = os.path.join(out_root, run_id); os.makedirs(run_dir)
    shutil.copy(config_path, os.path.join(run_dir, "config.toml"))
    files = checkpoint_files(cfg)
    if not files or any(not Path(f).is_file() for f in files):
        raise ValueError('Checkpoint files missing; refuse to start an unidentifiable baseline')
    ck_size = sum(os.path.getsize(f) for f in files if os.path.exists(f))
    hashes = {os.path.basename(f): sha256_cached(f, os.path.join(out_root, ".hash-cache"))
              for f in files if os.path.exists(f) and cfg["checkpoint"].get("hash", True)}
    ck_id = hashlib.sha256("".join(sorted(hashes.values())).encode()).hexdigest()[:16] if hashes else "unhashed"
    engine_version = sh(cfg["server"].get("version_command", "")) if cfg["server"].get("version_command") else None
    gguf = [f for f in files if f.endswith(".gguf") and os.path.exists(f)]
    try:
        cfg["_experts"] = expert_summary(gguf) if gguf else {"error": "no GGUF files"}
    except Exception as e:  # header layout we do not understand: the estimate is skipped, nothing else
        cfg["_experts"] = {"error": repr(e)}
    settings = cfg["sets"][set_name]
    is_profile = bool(settings.get("profile"))
    manifest = {
        "run_id": run_id, "set": set_name, "created": now(), "ifbench_version": __version__,
        "config": os.path.abspath(config_path),
        "engine": {"name": cfg["server"].get("engine_name"), "version": engine_version,
                   "command": cfg["server"]["command"], "image": cfg["server"].get("image")},
        "checkpoint": {"files": files, "size_gb": round(ck_size / 1e9, 2), "sha256": hashes, "id": ck_id},
        "generation": cfg["generation"], "budget": cfg["sets"][set_name]["budget"],
        "benchmarks": list(cfg["sets"][set_name]["benchmarks"]), "thresholds": cfg.get("thresholds", {}),
        "environment": {"host": platform.node(), "kernel": platform.release(), "arch": platform.machine(),
                        "os": sh("grep PRETTY_NAME /etc/os-release | cut -d= -f2"),
                        "driver": sh("nvidia-smi --query-gpu=driver_version --format=csv,noheader"),
                        "cuda": sh("(nvcc --version || /usr/local/cuda/bin/nvcc --version) 2>/dev/null | tail -1"),
                        "python": platform.python_version()},
        "prompt_cache": {"server_default": "on (llama.cpp default) unless the server command has --no-cache-prompt",
                         "probe": "off", "token_probs": "off",
                         "benchmarks": {b: cfg["benchmarks"][b].get("prompt_cache", "default")
                                        for b in cfg["sets"][set_name]["benchmarks"] if b in cfg.get("benchmarks", {})}},
        "page_cache_before_start_gib": round(meminfo_gib().get("Cached", 0), 1),
        "experts": {k: v for k, v in cfg["_experts"].items()},
    }
    asset_files = set()
    if cfg.get('tokenizer') and Path(cfg['tokenizer']).is_dir():
        asset_files.update(p for p in Path(cfg['tokenizer']).rglob('*') if p.is_file() and '.cache' not in p.parts)
    if Path(cfg['checkpoint']['path']).is_dir():
        asset_files.update(p for p in Path(cfg['checkpoint']['path']).iterdir()
                           if p.is_file() and p.suffix in ('.json', '.jinja', '.model'))
    manifest['asset_sha256'] = {str(p): sha256_cached(str(p), os.path.join(out_root, '.hash-cache'))
                                for p in sorted(asset_files)}
    if is_profile:
        manifest["profiler"] = {"tool": "Nsight Systems", "settings": cfg.get("profile", {})}
    if min_mem_available_gib is not None:
        manifest["min_mem_available_gib"] = min_mem_available_gib
    prior_benchmarks = {}
    if resume_from:
        prior_dir = Path(resume_from)
        prior_manifest = json.loads((prior_dir / "manifest.json").read_text())
        prior_report = json.loads((prior_dir / "report.json").read_text())
        keys = ("set", "engine", "checkpoint", "generation", "budget", "benchmarks", "environment")
        if load(prior_dir / "config.toml") != cfg or any(prior_manifest.get(k) != manifest[k] for k in keys):
            raise ValueError("resume requires the same config, model, engine, and environment")
        if prior_report.get("status") != "completed" or not prior_report.get("comparable"):
            raise ValueError("resume requires a completed, comparable source report")
        prior_benchmarks = {row["benchmark"]: row for row in prior_report["benchmarks"]
                            if row["outcome"] == "ok" and (row.get("scores") or row["benchmark"] == "token_probs")}
    json.dump(manifest, open(os.path.join(run_dir, "manifest.json"), "w"), indent=2)
    rec = Recorder(run_dir, run_id, manifest["engine"]["version"] or cfg["server"].get("engine_name"), ck_id)
    if is_profile:
        rec.comparable = False  # a profiler is attached: never use this run's speed numbers
    rec.add("L0.run_environment", {"manifest": "manifest.json"}, source="ifbench")
    rec.add("L0.checkpoint_storage", {"size_gb": manifest["checkpoint"]["size_gb"], "files": len(files),
                                      "id": ck_id}, source="statvfs + sha256")
    if cfg['_experts'].get('architecture') and not cfg['_experts'].get('expert_count'):
        for tid in ('L4.expert_selection', 'M.expert_cache_hit'):
            rec.add(tid, None, 'not_applicable', 'GGUF architecture metadata', note='dense model has no routed MoE experts')

    prefix, nsys = None, None
    if is_profile:
        pcfg = cfg.get("profile", {})
        nsys = nsys_profile.find_tool(nsys_profile.NSYS_CANDIDATES, pcfg.get("nsys"))
        if not nsys:
            report = {"run_id": run_id, "other_workloads": [], "benchmarks": [], "status": "blocked: nsys not found"}
            return finish(run_dir, report, rec)
        os.makedirs(os.path.join(run_dir, "nsys"), exist_ok=True)
        prefix = nsys_profile.nsys_command(nsys, pcfg, os.path.abspath(os.path.join(run_dir, "nsys", "profile")))
        manifest["profiler"]["command"] = prefix
        manifest["profiler"]["version"] = sh(f"{nsys} --version")
        json.dump(manifest, open(os.path.join(run_dir, "manifest.json"), "w"), indent=2)
    server = Server(cfg, run_dir, prefix=prefix,
                    finalize_timeout_s=cfg.get("profile", {}).get("finalize_timeout_s", 1800))
    pid_fn = (lambda: server.pid) if not no_server else (lambda: find_pid(cfg["server"].get("pid_match", "llama-server")))
    others = machine_static(rec, os.path.dirname(files[0]) if files else "/", own_pids=())
    report = {"run_id": run_id, "other_workloads": others, "benchmarks": [], "status": "started"}
    if not is_profile and (reuse_probe or (cfg.get("reuse_probe_for_budget") and settings.get("time_budget_min") is not None)):
        previous = matching_probe(cfg, manifest, out_root)
        estimate = budget_estimate(cfg, set_name, previous.get("probe")) if previous else None
        if estimate and (reuse_probe or over_budget(estimate)):
            report.update(probe=previous["probe"], estimate=estimate, estimate_source_run=previous["run_id"])
            if over_budget(estimate):
                report["status"] = f"stopped: estimated {estimate['total_minutes']} min exceeds budget {estimate['budget_minutes']} min"
                return finish(run_dir, report, rec)
    sampler = Sampler(run_dir, cfg["server"]["base_url"], pid_fn, cfg.get("sample_interval_s", 1.0))
    sampler.start()
    previous_handler = None
    audit_proxy = None

    def check_memory(signum=None, frame=None):
        if signum is not None and not no_server and server.proc is None:
            return
        available = meminfo_gib().get("MemAvailable")
        if available is not None and available < min_mem_available_gib:
            signal.setitimer(signal.ITIMER_REAL, 0)
            raise MemoryFloorExceeded(available)

    try:
        if min_mem_available_gib is not None:
            previous_handler = signal.signal(signal.SIGALRM, check_memory)
            check_memory()
            signal.setitimer(signal.ITIMER_REAL, 0.25, 0.25)
        if not no_server:
            t0 = time.time()
            ready = server.start(cfg["server"].get("ready_timeout_s", 3600))
            if ready is None:
                rec.add("L0.time_to_ready", None, "unavailable", "health poll", note="engine did not become ready; see server.log")
                report["status"] = "blocked: engine did not start"
                return finish(run_dir, report, rec)
            rb = proc_io_read_bytes(server.pid)
            gb = round(rb / 1e9, 2) if rb is not None else None
            start_kind = None if gb is None else ("warm" if gb < 0.5 * manifest["checkpoint"]["size_gb"] else "cold")
            rec.add("L0.time_to_ready", round(ready, 1), source="health poll",
                    note=f"{start_kind or 'unknown'} start (warm = most weights were already in the OS file cache)")
            rec.add("L0.weight_load", {"seconds": round(ready, 1), "gb_read_from_disk": gb, "start": start_kind},
                    source="health poll + /proc/<pid>/io",
                    note="load time approximated by time to ready; 0 GB read = weights served from the OS file cache")
            summarize_window(rec, sampler, t0, time.time(), "startup")
        elif not healthy(cfg["server"]["base_url"]):
            report["status"] = "blocked: --no-server given but engine not healthy"
            return finish(run_dir, report, rec)
        from .proxy import start as start_proxy
        audit_proxy, audit_url = start_proxy(cfg['server']['base_url'], {},
                                           capture_path=os.path.join(run_dir, 'requests.jsonl'))
        cfg['server']['base_url'] = audit_url
        log_text = open(server.log_path).read() if os.path.exists(server.log_path) else ""
        plan = startup_plan_from_log(log_text)
        rec.add("M.startup_memory_plan", plan, source="engine startup log (llama.cpp buffer sizes)")
        gpu = None
        if plan:
            gpu = round(sum(v for kind in plan.values() for d, v in kind.items()
                            if d.upper().startswith("CUDA") and not d.upper().startswith('CUDA_HOST')), 2)
        rec.add("M.gpu_working_set", gpu, source="engine startup log, CUDA buffers",
                note="to verify on Spark against the drop in free CUDA memory")

        if is_profile:
            t_ready = time.time()
            report["profile"] = profile_requests(cfg, rec)
            report["status"] = "profile requests done"
            server.stop()  # engine stops, nsys writes its report
            rep = os.path.join(run_dir, "nsys", "profile.nsys-rep")
            with open(os.path.join(run_dir, "nsys", "export.log"), "w") as log:
                db = nsys_profile.export_sqlite(nsys, rep, log) if os.path.exists(rep) else None
            if not db:
                report["status"] = "incomplete: no Nsight Systems report or SQLite export (see nsys/export.log, server.log)"
                return finish(run_dir, report, rec)
            report["profile_clock"] = {"t_launch": server.t_start, "t_ready": t_ready}
            ok, why = nsys_profile.ncu_status(cfg.get("profile", {}))
            for tid in ("L5.bandwidth_ratio", "L5.compute_ratio"):
                rec.add(tid, None, "unavailable", "Nsight Compute check",
                        note=("blocked: " + why) if not ok else ("not run by ifbench: " + why + "; see README, Nsight Compute"))
            reqs = [r for r in report["profile"] if r.get("ok")]
            report["status"] = "completed" if len(reqs) == len(report["profile"]) else "incomplete: some profile requests failed"
            try:
                analyze_profile(cfg, rec, run_dir, report)
            except Exception as e:  # keep the trace; `ifbench profile-analyze <run>` re-derives offline
                report["status"] = f"incomplete: trace kept, analysis failed ({e!r}); rerun `python3 -m ifbench profile-analyze {run_dir}`"
            return finish(run_dir, report, rec)
        if "estimate" in report:
            estimate = report["estimate"]
        else:
            probe = speed_probe(cfg, rec, sampler)
            report["probe"] = probe
            estimate = budget_estimate(cfg, set_name, probe)
            if not estimate:
                report["status"] = "incomplete: speed probe did not finish all depths"
                return finish(run_dir, report, rec)
            report["estimate"] = estimate
            if probe and not any(r["id"] == "L1.failed_requests" for r in rec.records):
                rec.add("L1.failed_requests", 0, source="speed probe client", note="requests sent by ifbench itself; benchmark tools report their own failures in each outcome")
        if over_budget(estimate):
            report["status"] = f"stopped: estimated {estimate['total_minutes']} min exceeds budget {estimate['budget_minutes']} min"
            return finish(run_dir, report, rec)
        if cfg["sets"][set_name].get("probe_only"):
            report["status"] = "probe only"
            return finish(run_dir, report, rec)

        for name in cfg["sets"][set_name]["benchmarks"]:
            if name in prior_benchmarks:
                row = dict(prior_benchmarks[name], reused_from_run=prior_report["run_id"])
                if name == "token_probs":
                    shutil.copy2(prior_dir / "token_probs.jsonl", run_dir)
                else:
                    bench_dir = Path(run_dir) / "bench" / name
                    shutil.copytree(prior_dir / "bench" / name, bench_dir)
                    row["out_dir"] = str(bench_dir.resolve())
                report["benchmarks"].append(row)
                continue
            if name == "token_probs":
                tp = cfg["token_probs"]
                prompts = [l.strip() for l in open(tp["prompts_file"]) if l.strip()][: tp["n_prompts"]]
                t0 = time.time()
                out = token_probs(cfg, prompts, tp["n_tokens"], tp["top_k"])
                with open(os.path.join(run_dir, "token_probs.jsonl"), "w") as f:
                    for o in out:
                        f.write(json.dumps(o) + "\n")
                ok = sum(1 for o in out if o.get("top_logprobs"))
                rec.add("L4.token_prob_match", {"recorded_prompts": ok, "of": len(out), "file": "token_probs.jsonl"},
                        "ok" if ok else "unavailable", "/v1/completions logprobs",
                        note="baseline run: probabilities recorded as the reference; comparison happens on candidate runs")
                report["benchmarks"].append({"benchmark": name, "outcome": "ok" if ok == len(out) else ("incomplete" if ok else "fail"),
                                             "minutes": round((time.time() - t0) / 60, 1)})
                summarize_window(rec, sampler, t0, time.time(), "benchmark token_probs", engine_rates=True)
                continue
            spec = cfg["benchmarks"][name]
            r = run_one(name, spec, cfg, os.path.join(run_dir, "bench"), lambda: healthy(cfg["server"]["base_url"]))
            report["benchmarks"].append(r)
            if r.get("t_start"):
                summarize_window(rec, sampler, r["t_start"], r["t_end"], f"benchmark {name}", engine_rates=True)
        report["status"] = "completed"
        return finish(run_dir, report, rec)
    except MemoryFloorExceeded as exc:
        if not no_server:
            server.stop(grace_seconds=2)
        available = exc.args[0]
        report["status"] = f"stopped: MemAvailable {available:.3f} GiB below {min_mem_available_gib:g} GiB"
        rec.add("M.mem_available_min", round(available, 3), source="/proc/meminfo", note="memory stop")
        return finish(run_dir, report, rec)
    finally:
        if audit_proxy:
            audit_proxy.shutdown()
            audit_proxy.server_close()
        if previous_handler is not None:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
        sampler.stop()
        if not no_server:
            server.stop()

def analyze_profile(cfg, rec, run_dir, report):
    default_kc = "data/kernel_categories.json"
    if not os.path.exists(default_kc):
        default_kc = str(Path(__file__).parent / "data" / "kernel_categories.json")
    rules = nsys_profile.load_categories(cfg.get("profile", {}).get("kernel_categories", default_kc))
    if not rules:
        raise ValueError("kernel category table not found (profile.kernel_categories)")
    reqs = [r for r in report["profile"] if r.get("ok")]
    clock = report["profile_clock"]
    result = nsys_profile.analyze(rec, os.path.join(run_dir, "nsys", "profile.sqlite"), rules, reqs, clock["t_launch"], clock["t_ready"],
                                  os.path.join(run_dir, "nsys"))
    if result.get('error') or 'WARNING' in result.get('clock', ''):
        raise ValueError('Trace lacks GPU work or request-clock alignment: ' + str(result.get('error') or result.get('clock')))

def reanalyze_profile(run_dir, config=None):
    """Re-derive the Nsight records of a finished profile run from its saved SQLite (no engine, no GPU)."""
    cfg = load(config or os.path.join(run_dir, "config.toml"))
    report = json.load(open(os.path.join(run_dir, "report.json")))
    rec = Recorder.reopen(run_dir, drop_ids=NSYS_IDS)
    analyze_profile(cfg, rec, run_dir, report)
    if str(report.get("status", "")).startswith("incomplete: trace kept"):
        reqs = [r for r in report["profile"] if r.get("ok")]
        report["status"] = "completed" if len(reqs) == len(report["profile"]) else "incomplete: some profile requests failed"
    return finish(run_dir, report, rec)

def profile_requests(cfg, rec):
    """Scripted requests for the profile pass. No warm-up: request 1 is the engine's first real request,
    request 2 repeats it exactly (first-occurrence cost = 1 vs 2). Prompt cache off, like the probe."""
    s, p, pcfg = cfg["server"], cfg["probe"], cfg.get("profile", {})
    seed_text = open(p["filler_text"]).read() if os.path.exists(p.get("filler_text", "")) else "The quick brown fox. " * 50
    reqs = pcfg.get("requests") or [{"label": "first d0", "depth_words": 0, "gen_tokens": 32},
                                    {"label": "repeat d0", "depth_words": 0, "gen_tokens": 32, "same_prompt_as_first": True},
                                    {"label": "d3000", "depth_words": 3000, "gen_tokens": 32}]
    out = []
    for q in reqs:
        prompt = filler_prompt(q["depth_words"] + p["new_prompt_words"], seed_text) + "\n\nSummarize the text above."
        t0 = time.time()
        r = stream_completion(s["base_url"], s["model"], prompt, q["gen_tokens"], cfg["generation"], cache_prompt=False,
                              read_timeout_s=p.get("read_timeout_s", 600))
        t1 = time.time()
        row = {"label": q["label"], "depth_words": q["depth_words"], "ok": r.get("ok", False), "t0": t0, "t1": t1,
               "t_first": r.get("t_first"), "t_last": r.get("t_last"), "same_prompt_as_first": q.get("same_prompt_as_first", False),
               "tokens": r.get('output_tokens'),
               "prompt_tokens": (r.get("usage") or {}).get("prompt_tokens")}
        if not r.get("ok"):
            row["error"] = r.get("error")
            rec.add("L1.failed_requests", 1, source="profile request", note=str(r.get("error"))[:200])
        out.append(row)
    return out

def _fmt(v, n=1):
    return f"{v:.{n}f}" if isinstance(v, float) else ("" if v is None else str(v))

PROFILE_RUN_GAP = "measured by the timed runs (smoke / baseline); this run has a profiler attached"

def finish(run_dir, report, rec):
    from .requests import summary
    report['request_summary'] = summary(os.path.join(run_dir, 'requests.jsonl'))
    sample_path = Path(run_dir) / 'samples.jsonl'
    if sample_path.exists():
        interferers = []
        unknown = False
        for line in sample_path.open():
            sample = json.loads(line)
            if sample.get('pid'):
                interferers.extend(sample.get('other_gpu_processes') or [])
            unknown |= sample.get('gpu_compute_processes') is None
        if interferers or unknown:
            rec.comparable = False
            report['other_workloads_during_run'] = interferers
            report['gpu_contention_check_unavailable'] = unknown
    profile_run = report.get("profile") is not None or "nsys" in report.get("status", "")
    extra = {tid: ("unavailable", PROFILE_RUN_GAP) for tid in CATALOG
             if profile_run and tid not in NSYS_IDS and tid not in ("L5.bandwidth_ratio", "L5.compute_ratio")}
    rec.fill_gaps(extra)
    report["coverage"] = {tid: st for tid, (st, _) in rec.coverage().items()}
    report["comparable"] = rec.comparable
    json.dump(report, open(os.path.join(run_dir, "report.json"), "w"), indent=2, default=str)
    lines = [f"# Run {report['run_id']}", "", f"Status: **{report['status']}**",
             f"Comparable (no other GPU workloads, no profiler): **{rec.comparable}**", ""]
    lines += ['## Client request measurements', '', '```json', json.dumps(report['request_summary'], indent=2), '```', '',
              'Per-request E2E and client decode estimates: requests.jsonl. Token counts come from usage/timings, never chunk counts.', '']
    if report.get("other_workloads"):
        lines += ["Other GPU workloads during the run:", ""] + [f"- {o}" for o in report["other_workloads"]] + [""]
    if report.get("estimate_source_run"):
        lines += [f"Timing from probe `{report['estimate_source_run']}`. The budget gate ran before engine startup.", ""]
    reused = [b for b in report["benchmarks"] if b.get("reused_from_run")]
    if reused:
        lines += ["Benchmark results retained from an earlier attempt:", ""]
        lines += [f"- `{b['benchmark']}` from `{b['reused_from_run']}`" for b in reused] + [""]
    if report.get("probe"):
        lines += ["## Speed probe (prompt cache off)", "", "| depth (words) | prompt tok | out tok | TTFT ms | prefill tok/s | engine decode tok/s | client E2E output tok/s |",
                  "|---|---|---|---|---|---|---|"]
        for p in report["probe"]:
            e = p.get("engine") or {}
            lines.append(f"| {p['depth_words']} | {p['prompt_tokens']} | {p['output_tokens']} | {_fmt(p['ttft_ms'])} | "
                         f"{_fmt(e.get('prompt_per_second') or p['prefill_tok_s_client'])} | "
                         f"{_fmt(e.get('predicted_per_second') or p['decode_tok_s_client'])} | {_fmt(p.get('e2e_output_tok_s'))} |")
        lines.append("")
    if report.get("estimate"):
        e = report["estimate"]
        lines += ["## Time estimate (token budget)", "", f"Total: **{e['total_minutes']} min** (budget {e['budget_minutes']} min) "
                  f"at prefill {_fmt(e['prefill_tok_s'])} tok/s, decode {_fmt(e['decode_tok_s'])} tok/s", "",
                  "| benchmark | input tokens | output tokens | estimated min | actual min |", "|---|---|---|---|---|"]
        actual = {b["benchmark"]: b.get("minutes") for b in report["benchmarks"]}
        lines += [f"| {r['benchmark']} | {r['input_tokens']} | {r['output_tokens']} | {r['minutes']} | {_fmt(actual.get(r['benchmark']))} |"
                  for r in e["rows"]] + [""]
    if report["benchmarks"]:
        lines += ["## Benchmarks", "", "| benchmark | outcome | minutes | prompt cache | scores |", "|---|---|---|---|---|"]
        for b in report["benchmarks"]:
            sc = b.get("scores")
            sc = "; ".join(f"{k}: {json.dumps(v) if isinstance(v, dict) else v}" for k, v in sc.items()) if isinstance(sc, dict) else (b.get("reason") or "")
            lines.append(f"| {b['benchmark']} | {b['outcome']} | {_fmt(b.get('minutes'))} | {b.get('prompt_cache', 'off')} | {sc} |")
        lines.append("")
    # one row per telemetry ID; windows listed inside the row (full records in telemetry.jsonl)
    lines += ["## Telemetry (one row per ID; all records in telemetry.jsonl)", "", "| ID | unit | value by window |", "|---|---|---|"]
    by_id = {}
    for r in rec.records:
        by_id.setdefault(r["id"], []).append(r)
    for tid, rs in by_id.items():
        parts = []
        for r in rs[:6]:
            v = json.dumps(r["value"]) if r["value"] is not None else f"null ({r['status']})"
            lab = (r.get("window") or {}).get("label")
            parts.append(f"{lab}: {v[:70]}" if lab else v[:120])
        if len(rs) > 6:
            parts.append(f"... {len(rs) - 6} more")
        lines.append(f"| {tid} | {rs[0]['unit']} | {'<br>'.join(parts)} |")
    cov = rec.coverage()
    counts = {}
    for st, _ in cov.values():
        counts[st] = counts.get(st, 0) + 1
    lines += ["", f"## Coverage of the {len(CATALOG)} telemetry IDs: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())), "",
              "| ID | tier | status | note |", "|---|---|---|---|"]
    for tid, (layer, unit, tier) in CATALOG.items():
        st, note = cov.get(tid, ("unavailable", ""))
        lines.append(f"| {tid} | {tier} | {st} | {str(note)[:110]} |")
    open(os.path.join(run_dir, "report.md"), "w").write("\n".join(lines) + "\n")
    print(f"run dir: {run_dir}\nstatus: {report['status']}")
    return run_dir

def calibrate_storage(cfg, rec, seconds):
    """Use fio read-only on the checkpoint file itself."""
    f = max(checkpoint_files(cfg), key=os.path.getsize)  # split GGUF: shard 1 is only metadata
    fio = cfg.get('calibration', {}).get('fio') or shutil.which('fio')
    if not fio or not Path(fio).is_file():
        rec.add("L6.cal.storage_read", None, "unavailable", "fio", note="fio not installed")
        return None
    res = {}
    for name, rw, bs in (("sequential_1M", "read", "1M"), ("random_4M", "randread", "4M")):
        argv = [fio, f"--name={name}", f"--filename={f}", f"--rw={rw}", f"--bs={bs}", "--direct=1",
                              "--readonly", "--ioengine=libaio", "--iodepth=32", f"--runtime={seconds}", "--time_based",
                              "--output-format=json"]
        out = subprocess.run(argv, capture_output=True, text=True, timeout=seconds + 60)
        if cfg.get('_calibration_dir'):
            folder = Path(cfg['_calibration_dir']) / 'fio'; folder.mkdir(exist_ok=True)
            (folder / (name + '.json')).write_text(out.stdout)
            (folder / (name + '.stderr')).write_text(out.stderr)
            (folder / (name + '.command.json')).write_text(json.dumps({'argv': argv, 'returncode': out.returncode}))
        try:
            j = json.loads(out.stdout)
            res[name + "_GBps"] = round(j["jobs"][0]["read"]["bw_bytes"] / 1e9, 2) if out.returncode == 0 else None
        except Exception:
            res[name + "_GBps"] = None
    rec.add("L6.cal.storage_read", res, source="fio --readonly --direct=1 on the largest checkpoint file",
            note=os.path.basename(f))
    return res


def calibrate(config_path, out_root, seconds=30, *, gpu_only=False, babelstream=None, cutlass_profiler=None):
    cfg = load(config_path)
    run_dir = Path(out_root) / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-calibrate")
    run_dir.mkdir(parents=True)
    cfg['_calibration_dir'] = str(run_dir)
    shutil.copy2(config_path, run_dir / 'config.toml')
    (run_dir / 'manifest.json').write_text(json.dumps({
        'run_id': run_dir.name, 'set': 'calibrate', 'created': now(), 'ifbench_version': __version__,
        'engine': {'name': 'hardware calibration'}, 'checkpoint': {'files': checkpoint_files(cfg)},
        'environment': {'host': platform.node(), 'kernel': platform.release(), 'arch': platform.machine()}
    }, indent=2))
    rec = Recorder(run_dir, run_dir.name, None, None)
    if not gpu_only:
        storage = calibrate_storage(cfg, rec, seconds)
        if storage is not None:
            print(json.dumps(storage))
    if babelstream or cutlass_profiler:
        from .gpu_calibration import calibrate_gpu
        print(f"run dir: {run_dir}", flush=True)
        calibrate_gpu(run_dir, rec, babelstream, cutlass_profiler)
    finish(run_dir, {'run_id': run_dir.name, 'status': 'completed', 'benchmarks': [], 'other_workloads': []}, rec)
    return str(run_dir)
