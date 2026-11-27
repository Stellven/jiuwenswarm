"""Runs the four core benchmarks as external command-line tools (plan 5.1).

Commands live in the config as templates, so a tool's flags can be fixed without touching code.
Placeholders: {base_url} {model} {out} {tokenizer} {python}.
Outcomes (plan 5.4): ok / fail / blocked (tool missing, engine down) / incomplete (timeout).
A benchmark with prompt_cache = "off" in its config talks to the engine through a local proxy
that adds cache_prompt=false to every request (llama.cpp caches prompt prefixes by default).
"""
import glob, json, os, shlex, shutil, subprocess, sys, time
from . import proxy

def estimate_minutes(budget, prefill_tok_s, decode_tok_s):
    """time = input tokens / prefill speed + output tokens / decode speed (plan 5.5)."""
    rows, total = [], 0.0
    for name, b in budget.items():
        m = (b["input_tokens"] / prefill_tok_s + b["output_tokens"] / decode_tok_s) / 60
        rows.append({"benchmark": name, **b, "minutes": round(m, 1)})
        total += m
    return rows, round(total, 1)

def run_one(name, spec, cfg, out_dir, engine_alive):
    bdir = os.path.abspath(os.path.join(out_dir, name)); os.makedirs(bdir, exist_ok=True)
    s = cfg["server"]
    base = s["base_url"].rstrip("/")
    srv = None
    cache = spec.get("prompt_cache", "default")
    if cache == "off":
        srv, base = proxy.start(base, {"cache_prompt": False})
    fill = {"base_url": base, "model": s["model"], "out": bdir,
            "tokenizer": cfg.get("tokenizer", ""), "python": sys.executable}
    cmd = spec["command"].format(**fill)
    exe = shlex.split(cmd)[0]
    res = {"benchmark": name, "command": cmd, "out_dir": bdir, "prompt_cache": cache}
    try:
        if not shutil.which(exe) and not os.path.exists(exe):
            return {**res, "outcome": "blocked", "reason": f"tool not found: {exe}"}
        if not engine_alive():
            return {**res, "outcome": "blocked", "reason": "engine not healthy before start"}
        res = _execute(res, cmd, spec, bdir, engine_alive)
        res["scores"] = scores(name, bdir)
        if name.startswith("infer_check") and res["outcome"] == "ok":
            with open(os.path.join(bdir, "stdout.log"), encoding="utf-8", errors="replace") as log:
                failed_request = any("Determinism run failed" in line for line in log)
            if failed_request or "determinism_score_mean" not in (res["scores"] or {}):
                res.update(outcome="incomplete", reason="infer-check did not complete every request; see stdout.log")
        return res
    finally:
        if srv:
            srv.shutdown()

def _execute(res, cmd, spec, bdir, engine_alive):
    t0 = time.time()
    with open(os.path.join(bdir, "stdout.log"), "w") as log:
        try:
            p = subprocess.run(shlex.split(cmd), stdout=log, stderr=subprocess.STDOUT,
                               timeout=spec.get("timeout_min", 240) * 60, cwd=bdir)
            outcome = "ok" if p.returncode == 0 else ("blocked" if not engine_alive() else "fail")
            res.update(returncode=p.returncode)
        except subprocess.TimeoutExpired:
            outcome = "incomplete"
    res.update(outcome=outcome, t_start=t0, t_end=time.time(), minutes=round((time.time() - t0) / 60, 1))
    if outcome == "fail":
        res["reason"] = "non-zero exit; see stdout.log"
    return res


# ---------------- scores for the report (raw files stay in bench/<name>/) ----------------

def _newest(pattern):
    f = sorted(glob.glob(pattern, recursive=True), key=os.path.getmtime)
    return f[-1] if f else None

def scores(name, bdir):
    """Headline numbers from each tool's own output files. Unknown layout -> None."""
    try:
        r = _newest(os.path.join(bdir, "**", "results_*.json"))
        if r:  # lm-evaluation-harness (gsm8k, ruler)
            out = {}
            for task, d in json.load(open(r))["results"].items():
                for k, v in d.items():
                    if isinstance(v, (int, float)) and "stderr" not in k and k != "alias":
                        out[f"{task} {k.replace(',none', '')}"] = round(v, 4)
            return out
        r = _newest(os.path.join(bdir, "**", "determinism*.json"))
        if r:  # infer-check
            d = json.load(open(r))
            rows = d if isinstance(d, list) else d.get("results", [])
            sc = [x.get("determinism_score") for x in rows if isinstance(x, dict) and x.get("determinism_score") is not None]
            if sc:
                return {"determinism_score_mean": round(sum(sc) / len(sc), 4), "prompts": len(sc),
                        "fully_identical_prompts": sum(1 for x in sc if x >= 1.0)}
        r = os.path.join(bdir, "result.json")
        if os.path.exists(r):  # llama-benchy 0.4: {"benchmarks": [{context_size, pp_throughput{mean}, ...}]}
            d = json.load(open(r)); out = {}
            for x in d.get("benchmarks", []):
                if x.get("is_context_prefill_phase"):
                    continue
                m = lambda k: round(x[k]["mean"], 1) if isinstance(x.get(k), dict) and x[k].get("mean") is not None else None
                out[f"depth {x.get('context_size')}"] = {"prefill_tok_s": m("pp_throughput"), "decode_tok_s": m("tg_throughput"),
                                                         "ttft_ms": m("e2e_ttft")}
            if out:
                out["prefix_caching_enabled"] = d.get("prefix_caching_enabled")
            return out or None
    except Exception as e:
        return {"parse_error": repr(e)}
    return None
