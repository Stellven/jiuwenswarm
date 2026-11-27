"""Expert routing trace (L4.expert_selection) and expert-cache replay, for MoE GGUF models.

The trace comes from `llama-expert-trace`, a small diagnostic program built from the same llama.cpp
commit as the baseline engine. It reads the router's choice ("ffn_moe_topk-<layer>") through llama.cpp's
public eval callback, so the engine's code is unchanged. Greedy decoding on the baseline's own prompts.

prompts : routing_prompts(baseline_run, cfg) -> list of {"id", "prompt", "n_predict"}
analyze : analyze(trace, cfg, baseline_run, out_dir) -> routing.json, routing.md, telemetry.jsonl
"""
import glob, heapq, json, os
from collections import defaultdict, OrderedDict
from .engine import filler_prompt
from .gguf_info import read_header
from .telemetry import Recorder


def routing_prompts(baseline_dir, cfg, n_gsm8k=10):
    """The baseline's own prompts: 20 token-probability prompts (64 tokens), the first n GSM8K prompts
    (128 tokens) and the speed probe's depth-0 prompt (128 tokens)."""
    out = []
    for line in open(os.path.join(baseline_dir, "token_probs.jsonl")):
        r = json.loads(line)
        out.append({"id": f"tp{r['i']:02d}", "prompt": r["prompt"], "n_predict": cfg["token_probs"]["n_tokens"]})
    samples = sorted(glob.glob(os.path.join(baseline_dir, "bench", "gsm8k*", "**", "samples_gsm8k*.jsonl"), recursive=True))
    if samples:
        seen = set()
        for line in open(samples[-1]):
            r = json.loads(line)
            if r["doc_id"] in seen:
                continue
            seen.add(r["doc_id"])
            out.append({"id": f"gsm{r['doc_id']:02d}", "prompt": r["arguments"]["gen_args_0"]["arg_0"], "n_predict": 128})
            if len(seen) >= n_gsm8k:
                break
    p = cfg["probe"]
    seed = open(p["filler_text"]).read()
    out.append({"id": "probe0", "prompt": filler_prompt(p["new_prompt_words"], seed) + "\n\nSummarize the text above.",
                "n_predict": 128})
    return out


def expert_bytes(files):
    """Bytes of one routed expert in each MoE layer (all its ffn_*_exps tensors / expert_count)."""
    per_layer, n_exp = defaultdict(int), None
    for f in files:
        meta, tensors = read_header(f)
        for k, v in meta.items():
            if k.endswith(".expert_count"):
                n_exp = v
        for name, dims, gtype, size in tensors:
            if "_exps." in name and name.startswith("blk."):
                per_layer[int(name.split(".")[1])] += size
    return {l: b / n_exp for l, b in per_layer.items()}, n_exp


def load_trace(path):
    rows, done = [], []
    for line in open(path):
        r = json.loads(line)
        (done if "prompt_done" in r else rows).append(r)
    return rows, done


def lru_hits(seq, slots):
    cache, hits = OrderedDict(), 0
    for e in seq:
        if e in cache:
            hits += 1
            cache.move_to_end(e)
        else:
            cache[e] = True
            if len(cache) > slots:
                cache.popitem(last=False)
    return hits


def optimal_hits(seq, slots):
    """Belady: evict the expert whose next use is farthest away (upper bound for any cache policy)."""
    nxt, last = [0] * len(seq), {}
    for i in range(len(seq) - 1, -1, -1):
        nxt[i] = last.get(seq[i], float("inf"))
        last[seq[i]] = i
    cache, heap, hits = {}, [], 0
    for i, e in enumerate(seq):
        if e in cache:
            hits += 1
        elif len(cache) >= slots:
            while True:
                negn, x = heapq.heappop(heap)
                if x in cache and cache[x] == -negn:
                    del cache[x]
                    break
        cache[e] = nxt[i]
        heapq.heappush(heap, (-nxt[i], e))
    return hits


def analyze(trace_path, cfg, files, out_dir, baseline_dir=None, budgets_gib=(8, 16, 32, 64, 96)):
    os.makedirs(out_dir, exist_ok=True)
    rows, done = load_trace(trace_path)
    eb, n_exp = expert_bytes(files)
    layers = sorted({r["l"] for r in rows})
    k = rows[0]["k"] if rows else None
    # decode: one token per row; sequences per layer in time order (prompts back to back, as a server would see them)
    dec = defaultdict(list)
    counts = {ph: defaultdict(lambda: defaultdict(int)) for ph in ("prefill", "decode")}
    prefill_touch = []
    for r in rows:
        ids = r["ids"]
        for e in ids:
            counts[r["ph"]][r["l"]][e] += 1
        if r["ph"] == "decode":
            dec[r["l"]].append(ids)
        else:
            prefill_touch.append((r["n"], len(set(ids))))
    n_dec_tokens = len(dec[layers[0]]) if layers else 0
    res = {"layers": len(layers), "experts_per_layer": n_exp, "experts_per_token": k, "decode_tokens": n_dec_tokens,
           "prefill_tokens": sum(d["prompt_tokens"] for d in done), "prompts": len(done),
           "expert_mb": round(sum(eb.values()) / len(eb) / 1e6, 2) if eb else None}
    # concentration in decode
    top10 = max(1, round(0.10 * n_exp))
    shares, used, never = [], [], []
    for l in layers:
        c = sorted(counts["decode"][l].values(), reverse=True)
        tot = sum(c) or 1
        shares.append(sum(c[:top10]) / tot)
        used.append(len(c))
        never.append(n_exp - len(c))
    res["decode"] = {"top10pct_share_mean": round(100 * sum(shares) / len(shares), 1),
                     "top10pct_share_range": [round(100 * min(shares), 1), round(100 * max(shares), 1)],
                     "experts_used_mean": round(sum(used) / len(used), 1), "experts_never_used_mean": round(sum(never) / len(never), 1)}
    # prefill: how many distinct experts one batch touches (why prefill re-reads most weights)
    res["prefill"] = {"batches": len(prefill_touch) // max(1, len(layers)),
                      "distinct_experts_per_batch_per_layer_mean": round(sum(t for _, t in prefill_touch) / max(1, len(prefill_touch)), 1),
                      "tokens_per_batch_mean": round(sum(n for n, _ in prefill_touch) / max(1, len(prefill_touch)), 1)}
    # cache replay on decode: one budget for all layers, split by layer in proportion to its expert size
    total_exp_bytes = sum(eb[l] for l in layers)
    replay = []
    for g in budgets_gib:
        slots = min(n_exp, max(k or 1, int(g * 2**30 / total_exp_bytes)))  # same number of slots in every layer
        acc = lru = opt = 0
        for l in layers:
            seq = [e for ids in dec[l] for e in ids]
            acc += len(seq)
            lru += lru_hits(seq, slots)
            opt += optimal_hits(seq, slots)
        replay.append({"budget_gib": g, "slots_per_layer": slots, "of": n_exp,
                       "lru_hit_pct": round(100 * lru / max(1, acc), 1), "optimal_hit_pct": round(100 * opt / max(1, acc), 1)})
    res["decode_cache_replay"] = replay
    res["per_layer_decode_counts"] = {str(l): dict(sorted(counts["decode"][l].items())) for l in layers}
    res["per_layer_prefill_counts"] = {str(l): dict(sorted(counts["prefill"][l].items())) for l in layers}
    # sanity: the trace program's greedy text vs the engine's recorded token-probability text (same prompts)
    if baseline_dir and os.path.exists(os.path.join(baseline_dir, "token_probs.jsonl")):
        ref = {f"tp{json.loads(l)['i']:02d}": json.loads(l).get("text") or "" for l in open(os.path.join(baseline_dir, "token_probs.jsonl"))}
        pairs = [(d["text"], ref[d["prompt_done"]]) for d in done if d["prompt_done"] in ref]
        same = sum(1 for a, b in pairs if a.strip() and (a.startswith(b[:40]) or b.startswith(a[:40])))
        res["text_check"] = {"prompts": len(pairs), "same_start_as_engine": same,
                             "note": "first 40 characters of the greedy continuation agree with llama-server's recorded text"}
    res["timing"] = [{k2: d[k2] for k2 in ("prompt_done", "prompt_tokens", "generated_tokens", "prefill_s", "decode_s")} for d in done]
    json.dump(res, open(os.path.join(out_dir, "routing.json"), "w"), indent=1)
    run_id = os.path.basename(os.path.normpath(out_dir))
    rec = Recorder(out_dir, run_id, "llama-expert-trace (same llama.cpp commit)", None)
    rec.add("L4.expert_selection", {k2: res[k2] for k2 in ("prompts", "decode_tokens", "prefill_tokens", "decode", "prefill")} | {"file": "routing.json"},
            source="llama-expert-trace: llama.cpp eval callback on ffn_moe_topk (diagnostic binary, engine code unchanged)",
            note="per-layer, per-expert counts for prefill and decode are in routing.json")
    rec.add("M.expert_cache_hit", {"replay": replay}, source="decode routing trace replayed through LRU and optimal (Belady) caches",
            note="what an expert cache of each size would hit on this workload; the measured page-cache estimate is in the baseline run")
    lines = [f"# Expert routing: {res['prompts']} prompts, {res['prefill_tokens']} prompt tokens, {n_dec_tokens} decoded tokens", "",
             f"{res['layers']} MoE layers x {n_exp} experts, {k} selected per token, {res['expert_mb']} MB per expert (mean).", "",
             f"- Decode: the most-used 10% of experts take {res['decode']['top10pct_share_mean']}% of selections "
             f"(range over layers {res['decode']['top10pct_share_range']}); {res['decode']['experts_used_mean']} of {n_exp} experts used per layer.",
             f"- Prefill: one batch of ~{res['prefill']['tokens_per_batch_mean']} tokens touches {res['prefill']['distinct_experts_per_batch_per_layer_mean']} distinct experts per layer.",
             "", "| Cache budget (GiB) | Slots per layer | LRU hit % | Optimal hit % |", "|---|---|---|---|"]
    lines += [f"| {r['budget_gib']} | {r['slots_per_layer']} | {r['lru_hit_pct']} | {r['optimal_hit_pct']} |" for r in replay]
    if "text_check" in res:
        lines += ["", f"Text check: {res['text_check']['same_start_as_engine']} of {res['text_check']['prompts']} prompts start like the engine's recorded output."]
    open(os.path.join(out_dir, "routing.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return res
