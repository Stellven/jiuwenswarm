"""A/A noise and paired comparison of runs (plan 5.4). Reads run folders only; never talks to the engine.

noise:   several runs of the SAME engine and settings -> how much each number moves by itself.
compare: reference runs vs candidate runs, paired in the order given (run them interleaved: A B B A ...).
  speed    improved / regressed only if the 95% interval of the paired relative gain clears
           max(min_gain, multiplier x A/A noise); otherwise "no change".
  quality  same questions, paired: accuracy drop must stay within A/A flip rate + 1.645*sqrt(flips)/n.
  tokens   top-1 agreement and KL against the reference token probabilities; text identity.
  memory   reported side by side (budgets are checked against the use-case setting, not here).
Thresholds are inputs (flags or the noise file); freeze them before looking at candidate results.
"""
import glob, json, math, os, random, re
from .engine import compare_token_probs
from .benchmarks import scores as bench_scores

LOWER_IS_BETTER = ("ttft_ms", "time_to_ready_s")

def _json(path):
    try:
        return json.load(open(path))
    except Exception:
        return None

def _jsonl(path):
    try:
        return [json.loads(l) for l in open(path) if l.strip()]
    except Exception:
        return []

def load_run(run_dir):
    """One run folder -> {speed: {name: [values]}, score: {name: v}, items: {key: 0/1}, memory: {...}, token_probs: [...]}."""
    rep = _json(os.path.join(run_dir, "report.json")) or {}
    man = _json(os.path.join(run_dir, "manifest.json")) or {}
    run = {"run_id": rep.get("run_id") or os.path.basename(run_dir.rstrip("/")), "dir": run_dir,
           "status": rep.get("status"), "comparable": rep.get("comparable"),
           "engine": (man.get("engine") or {}).get("version"), "engine_command": (man.get("engine") or {}).get("command"),
           "checkpoint": (man.get("checkpoint") or {}).get("id"), "set": man.get("set"),
           "generation": man.get("generation"), "speed": {}, "score": {}, "items": {}, "memory": {}}
    for p in rep.get("probe") or []:
        e = p.get("engine") or {}
        k = f"probe depth {p['depth_words']}w"
        for name, v in (("prefill_tok_s", e.get("prompt_per_second") or p.get("prefill_tok_s_client")),
                        ("decode_tok_s", e.get("predicted_per_second") or p.get("decode_tok_s_client")),
                        ("ttft_ms", p.get("ttft_ms"))):
            if v:
                run["speed"][f"{k} {name}"] = [float(v)]
    for b in rep.get("benchmarks") or []:
        name = re.sub(r"_smoke$", "", b["benchmark"])
        bdir = os.path.join(run_dir, "bench", b["benchmark"])
        r = _json(os.path.join(bdir, "result.json"))
        if r:  # llama-benchy keeps every repeat
            for x in r.get("benchmarks", []):
                if x.get("is_context_prefill_phase"):
                    continue
                for src, short in (("pp_throughput", "prefill_tok_s"), ("tg_throughput", "decode_tok_s"), ("e2e_ttft", "ttft_ms")):
                    vals = (x.get(src) or {}).get("values")
                    if vals:
                        run["speed"][f"llama-benchy depth {x.get('context_size')} {short}"] = [float(v) for v in vals]
            continue
        sc = b.get("scores") if isinstance(b.get("scores"), dict) else bench_scores(b["benchmark"], bdir)
        for k, v in (sc or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and "sample_len" not in k and k != "prompts":
                run["score"][f"{name}: {k}"] = float(v)
        for f in glob.glob(os.path.join(bdir, "**", "samples_*.jsonl"), recursive=True):  # lm-eval per-question results
            task = re.match(r"samples_(.+)_\d{4}-\d\d-\d\dT", os.path.basename(f))
            task = task.group(1) if task else os.path.basename(f)
            for d in _jsonl(f):
                for m in d.get("metrics") or []:
                    if isinstance(d.get(m), (int, float)) and d[m] >= 0:  # RULER marks other lengths as -1
                        run["items"][f"{task}|{d.get('filter', 'none')}|{m}|{d.get('doc_id')}"] = 1 if d[m] >= 1.0 else 0
    host, avail, read = [], [], []
    for t in _jsonl(os.path.join(run_dir, "telemetry.jsonl")):
        v = t.get("value")
        if v is None:
            continue
        if t["id"] == "M.host_memory" and isinstance(v, dict) and v.get("host_working_set") is not None:
            host.append(v["host_working_set"])
        elif t["id"] == "M.mem_available_min" and isinstance(v, (int, float)):
            avail.append(v)
        elif t["id"] == "M.storage_read_per_token" and isinstance(v, (int, float)):
            read.append(v)
        elif t["id"] == "M.gpu_working_set" and isinstance(v, (int, float)):
            run["memory"]["gpu_working_set_gib"] = v
        elif t["id"] == "L0.time_to_ready" and isinstance(v, (int, float)):
            run["memory"]["time_to_ready_s"] = v
    if host: run["memory"]["host_working_set_peak_gib"] = max(host)
    if avail: run["memory"]["mem_available_min_gib"] = min(avail)
    if read: run["memory"]["storage_read_gb_per_token_mean"] = round(sum(read) / len(read), 4)
    run["token_probs"] = _jsonl(os.path.join(run_dir, "token_probs.jsonl"))
    return run

def _mean(v):
    return sum(v) / len(v)

def _rel_spread(values):
    m = _mean(values)
    return (max(values) - min(values)) / abs(m) if m else None

def _text_identity(a, b):
    pairs = [(x.get("text"), y.get("text")) for x, y in zip(a, b) if x.get("text") is not None and y.get("text") is not None]
    return round(sum(1 for x, y in pairs if x == y) / len(pairs), 4) if pairs else None

def _settings_warnings(runs, same_engine):
    w = []
    if len({r["checkpoint"] for r in runs}) > 1:
        w.append("runs use different checkpoints (must be the same file, by hash)")
    if len({json.dumps(r["generation"], sort_keys=True) for r in runs}) > 1:
        w.append("runs use different generation settings")
    if len({r["set"] for r in runs}) > 1:
        w.append("runs come from different sets (smoke / baseline); only shared numbers are compared")
    if same_engine and len({(r["engine"], r["engine_command"]) for r in runs}) > 1:
        w.append("A/A runs differ in engine version or server command")
    for r in runs:
        if r["comparable"] is False:
            w.append(f"{r['run_id']}: marked not comparable (other GPU workloads or a profiler)")
        if r["status"] != "completed":
            w.append(f"{r['run_id']}: status is '{r['status']}'")
    return w

def noise(run_dirs, out=None):
    """A/A: spread of every number across runs of the same engine. Needs at least 2 runs; 3+ recommended."""
    runs = [load_run(d) for d in run_dirs]
    res = {"kind": "aa_noise", "runs": [r["run_id"] for r in runs], "warnings": _settings_warnings(runs, True),
           "speed": {}, "score": {}, "items": {}, "token_probs": {}}
    for k in sorted(set.intersection(*[set(r["speed"]) for r in runs])):
        per_run = [_mean(r["speed"][k]) for r in runs]
        within = [_rel_spread(r["speed"][k]) for r in runs if len(r["speed"][k]) > 1]
        res["speed"][k] = {"per_run": [round(v, 3) for v in per_run], "mean": round(_mean(per_run), 3),
                           "noise_rel": round(_rel_spread(per_run), 5),
                           "within_run_rel": round(max(within), 5) if within else None}
    for k in sorted(set.intersection(*[set(r["score"]) for r in runs])):
        v = [r["score"][k] for r in runs]
        res["score"][k] = {"per_run": v, "spread_abs": round(max(v) - min(v), 5)}
    groups = {}
    for k in set.intersection(*[set(r["items"]) for r in runs]):
        g = groups.setdefault(k.rsplit("|", 1)[0], [0, 0])
        g[0] += 1; g[1] += len({r["items"][k] for r in runs}) > 1
    res["items"] = {g: {"questions": n, "flipped": f, "flip_rate": round(f / n, 5)} for g, (n, f) in sorted(groups.items())}
    tp = [compare_token_probs(runs[0]["token_probs"], r["token_probs"]) for r in runs[1:] if r["token_probs"] and runs[0]["token_probs"]]
    tp = [t for t in tp if t["top1_match"] is not None]
    if tp:
        ident = [i for i in (_text_identity(runs[0]["token_probs"], r["token_probs"]) for r in runs[1:]) if i is not None]
        res["token_probs"] = {"top1_match_min": min(t["top1_match"] for t in tp),
                              "mean_kl_max": max((t["mean_kl_on_shared_topk"] or 0) for t in tp),
                              "text_identity_min": min(ident) if ident else None}
    elif any(r["token_probs"] for r in runs):
        res["warnings"].append("token probabilities could not be compared (missing or failed in some runs)")
    if len(runs) < 3:
        res["warnings"].append("only 2 runs: the spread of 2 values underestimates noise; use 3 or more before freezing thresholds")
    if out:
        json.dump(res, open(out, "w"), indent=2)
    return res

def _bootstrap_ci(values, n=4000, seed=1234):
    rng = random.Random(seed)
    means = sorted(_mean([rng.choice(values) for _ in values]) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]

def compare(ref_dirs, cand_dirs, noise_file=None, multiplier=2.0, min_gain=0.01, min_top1=None, out_dir=None):
    ref, cand = [load_run(d) for d in ref_dirs], [load_run(d) for d in cand_dirs]
    if len(ref) != len(cand):
        raise SystemExit("compare needs the same number of reference and candidate runs (they are paired in order)")
    nz = _json(noise_file) if noise_file else None
    res = {"kind": "paired_comparison", "reference": [r["run_id"] for r in ref], "candidate": [r["run_id"] for r in cand],
           "thresholds": {"noise_file": noise_file, "multiplier": multiplier, "min_gain": min_gain, "min_top1": min_top1},
           "warnings": _settings_warnings(ref + cand, False), "speed": [], "quality": [], "score": [], "memory": [], "token_probs": None}
    if not nz:
        res["warnings"].append("no A/A noise file: speed verdicts use min_gain only and are provisional")
    if len(ref) < 3:
        res["warnings"].append(f"{len(ref)} pair(s): no confidence interval below 3 pairs; the worst pair is used as the lower bound")
    shared = set.intersection(*[set(r["speed"]) for r in ref + cand])
    for k in sorted(shared):
        lower_better = k.endswith(LOWER_IS_BETTER)
        gains = []
        for a, b in zip(ref, cand):
            ma, mb = _mean(a["speed"][k]), _mean(b["speed"][k])
            gains.append((ma / mb - 1) if lower_better else (mb / ma - 1))
        lo, hi = _bootstrap_ci(gains) if len(gains) >= 3 else (min(gains), max(gains))
        nrel = ((nz or {}).get("speed") or {}).get(k, {}).get("noise_rel")
        bar = max(min_gain, multiplier * nrel) if nrel is not None else min_gain
        verdict = "improved" if lo > bar else ("regressed" if hi < -bar else "no change")
        res["speed"].append({"metric": k, "reference": round(_mean([_mean(r["speed"][k]) for r in ref]), 3),
                             "candidate": round(_mean([_mean(r["speed"][k]) for r in cand]), 3),
                             "gain_rel": round(_mean(gains), 4), "ci95": [round(lo, 4), round(hi, 4)],
                             "aa_noise_rel": nrel, "bar_rel": round(bar, 4), "verdict": verdict})
    # quality, paired per question (first pair: correctness runs are deterministic at temperature 0)
    a, b = ref[0], cand[0]
    groups = {}
    for k in set(a["items"]) & set(b["items"]):
        g = groups.setdefault(k.rsplit("|", 1)[0], {"n": 0, "ref": 0, "cand": 0, "ref_only": 0, "cand_only": 0})
        g["n"] += 1; g["ref"] += a["items"][k]; g["cand"] += b["items"][k]
        g["ref_only"] += a["items"][k] > b["items"][k]; g["cand_only"] += b["items"][k] > a["items"][k]
    for name, g in sorted(groups.items()):
        drop = (g["ref"] - g["cand"]) / g["n"]
        aa = ((nz or {}).get("items") or {}).get(name, {}).get("flip_rate", 0.0)
        margin = aa + 1.645 * math.sqrt(g["ref_only"] + g["cand_only"]) / g["n"]
        res["quality"].append({"group": name, "questions": g["n"], "reference_acc": round(g["ref"] / g["n"], 4),
                               "candidate_acc": round(g["cand"] / g["n"], 4), "drop": round(drop, 4),
                               "ref_only_correct": g["ref_only"], "cand_only_correct": g["cand_only"],
                               "aa_flip_rate": aa, "margin": round(margin, 4), "verdict": "pass" if drop <= margin else "fail"})
    for k in sorted(set(a["score"]) & set(b["score"])):
        res["score"].append({"metric": k, "reference": a["score"][k], "candidate": b["score"][k],
                             "diff": round(b["score"][k] - a["score"][k], 4)})
    for k in sorted(set(a["memory"]) & set(b["memory"])):
        res["memory"].append({"metric": k, "reference": a["memory"][k], "candidate": b["memory"][k],
                              "diff": round(b["memory"][k] - a["memory"][k], 4)})
    if a["token_probs"] and b["token_probs"]:
        tp = compare_token_probs(a["token_probs"], b["token_probs"])
        tp["text_identity"] = _text_identity(a["token_probs"], b["token_probs"])
        tp["aa_top1_match"] = ((nz or {}).get("token_probs") or {}).get("top1_match_min")
        usable = lambda rows: sum(1 for x in rows if x.get("top_logprobs"))
        tp["prompts_compared"] = min(usable(a["token_probs"]), usable(b["token_probs"]))
        tp["prompts_expected"] = max(len(a["token_probs"]), len(b["token_probs"]))
        if tp["prompts_compared"] < tp["prompts_expected"]:
            res["warnings"].append(f"token probabilities: only {tp['prompts_compared']} of {tp['prompts_expected']} prompts usable in both runs")
        if tp["top1_match"] is None:
            tp["verdict"] = "unavailable"
        else:
            tp["verdict"] = "report only (no min_top1 set)" if min_top1 is None else ("pass" if tp["top1_match"] >= min_top1 else "fail")
        res["token_probs"] = tp
    bad = [q for q in res["quality"] if q["verdict"] == "fail"] or (res["token_probs"] or {}).get("verdict") == "fail"
    blocked = any("checkpoint" in w or "generation settings" in w or "status is" in w for w in res["warnings"])
    missing = not (res["speed"] and res["quality"]) or (res["token_probs"] or {}).get("verdict") == "unavailable"
    res["result"] = "blocked" if blocked else ("fail" if bad else ("incomplete" if missing else "pass"))
    res["result_note"] = "result covers quality and token probabilities; speed verdicts are reported, not gated (plan 5.4)"
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        json.dump(res, open(os.path.join(out_dir, "compare.json"), "w"), indent=2)
        open(os.path.join(out_dir, "compare.md"), "w").write(to_markdown(res))
    return res

def _pct(v):
    return "" if v is None else f"{v * 100:+.1f}%"

def to_markdown(res):
    if res["kind"] == "aa_noise":
        L = ["# A/A noise", "", "Runs: " + ", ".join(res["runs"]), ""] + [f"- Warning: {w}" for w in res["warnings"]] + [""]
        L += ["| speed metric | per run | noise (max-min)/mean | within one run |", "|---|---|---|---|"]
        for k, v in res["speed"].items():
            within = "" if v["within_run_rel"] is None else f"{v['within_run_rel'] * 100:.2f}%"
            L.append(f"| {k} | {', '.join(str(x) for x in v['per_run'])} | {v['noise_rel'] * 100:.2f}% | {within} |")
        L += ["", "| question group | questions | answers that flipped between runs |", "|---|---|---|"]
        L += [f"| {k} | {v['questions']} | {v['flipped']} ({v['flip_rate'] * 100:.1f}%) |" for k, v in res["items"].items()]
        if res["token_probs"]:
            t = res["token_probs"]
            L += ["", f"Token probabilities between runs: top-1 match {t['top1_match_min']}, mean KL {t['mean_kl_max']}, "
                      f"identical text {t['text_identity_min']}"]
        return "\n".join(L) + "\n"
    t = res["thresholds"]
    L = [f"# Comparison: **{res['result']}**", "", "Reference: " + ", ".join(res["reference"]), "",
         "Candidate: " + ", ".join(res["candidate"]), "",
         f"Speed bar: max({t['min_gain'] * 100:g}%, {t['multiplier']:g} x A/A noise). Noise file: {t['noise_file'] or 'none'}.", ""]
    L += [f"- Warning: {w}" for w in res["warnings"]] + ["", res["result_note"].capitalize() + ".", ""]
    L += ["## Speed", "", "| metric | reference | candidate | gain | 95% interval | bar | verdict |", "|---|---|---|---|---|---|---|"]
    L += [f"| {s['metric']} | {s['reference']} | {s['candidate']} | {_pct(s['gain_rel'])} | {_pct(s['ci95'][0])} to {_pct(s['ci95'][1])} | "
          f"{s['bar_rel'] * 100:.1f}% | {s['verdict']} |" for s in res["speed"]]
    L += ["", "## Quality (same questions)", "", "| group | questions | reference | candidate | drop | margin | verdict |", "|---|---|---|---|---|---|---|"]
    L += [f"| {q['group']} | {q['questions']} | {q['reference_acc']} | {q['candidate_acc']} | {q['drop']} | {q['margin']} | {q['verdict']} |"
          for q in res["quality"]]
    if res["token_probs"]:
        p = res["token_probs"]
        L += ["", "## Token probabilities", "", f"Prompts {p['prompts_compared']} of {p['prompts_expected']}, positions {p['positions']}, top-1 match {p['top1_match']} (A/A: {p['aa_top1_match']}), "
              f"mean KL on shared top-k {p['mean_kl_on_shared_topk']}, identical text {p['text_identity']}. Verdict: {p['verdict']}"]
    for title, key in (("Other scores", "score"), ("Memory and startup (reported; budgets are checked separately)", "memory")):
        if res[key]:
            L += ["", f"## {title}", "", "| metric | reference | candidate | difference |", "|---|---|---|---|"]
            L += [f"| {m['metric']} | {m['reference']} | {m['candidate']} | {m['diff']} |" for m in res[key]]
    return "\n".join(L) + "\n"
