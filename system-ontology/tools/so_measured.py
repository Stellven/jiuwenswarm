#!/usr/bin/env python3
"""What the assessment computed beforehand, beside what was measured on the DGX Spark.

Reads the two current assessments (runs/muse-assessment-08-budget-80 and -128) and the records of the measured runs
(runs/muse-measured-2026-11-20/<run>/: the evidence file written by tools/spark_kit/measure.py, the server's log and
the run record; and the storage probes of the day). Every verdict word is decided by comparing the two numbers on
its line; none is a fixed sentence.

    python tools/so_measured.py [RUN ...]        default: every run in the folder
"""
import json
import pathlib
import re
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8")
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

REPO = pathlib.Path(__file__).resolve().parent.parent
MEASURED = REPO / "runs" / "muse-measured-2026-11-20"


def described(object_id):
    """The description with this id among the given files."""
    for p in sorted((REPO / "examples" / "given").glob("*.yaml")):
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and d.get("id") == object_id:
            return d
    raise SystemExit(f"no description with id {object_id}")


def assessment(name):
    return json.loads((REPO / "runs" / name / "assessment.json").read_text(encoding="utf-8"))


def measured(run):
    d = MEASURED / run
    ev = next(d.glob("evidence-*.yaml"))
    e = json.loads("".join(ln for ln in ev.read_text(encoding="utf-8").splitlines(True) if not ln.startswith("#")))
    s = [x for x in e["results"]["samples"] if x.get("engine_timings")]
    rec = (d / "record.txt").read_text(encoding="utf-8")
    log = (d / "server.log").read_text(encoding="utf-8", errors="replace")
    kv = [(float(m.group(1)), int(m.group(2)), int(m.group(3)))
          for m in re.finditer(r"llama_kv_cache: size =\s*([\d.]+) MiB \(\s*(\d+) cells,\s*(\d+) layers", log)]
    grab = lambda pat: (re.search(pat, rec) or [None, None])[1]
    # an expert cache on the GPU, when the server was started with one: its size against all experts, and what the
    # server counted over the decode steps of the whole run
    size = re.search(r"MoE cache size =\s*([\d.]+) MiB for\s*([\d.]+) MiB of host experts", log)
    hits = re.search(r"llama_moe_cache: ubatch <= \d+: hits = (\d+), misses = (\d+)", log)
    cache = ({"share": float(size.group(1)) / float(size.group(2)), "mib": float(size.group(1)),
              "hits": int(hits.group(1)), "misses": int(hits.group(2))} if size and hits else None)
    return {"run": run, "artifact": e["engine_build_digest"], "n": len(s), "warm": len(e["results"].get("warmups", [])),
            "decode": [x["engine_timings"]["predicted_per_second"] for x in s],
            "prompt_n": [x["engine_timings"]["prompt_n"] for x in s],
            "prompt_s": [x["engine_timings"]["prompt_ms"] / 1000 for x in s],
            "ttft": [x["ttft_s"] for x in s], "out": [x["completion_tokens"] for x in s],
            "kv_bytes_per_cell_layer": sorted({round(mib * 1048576 / cells / layers) for mib, cells, layers in kv}),
            "ready": grab(r"ready after: (\d+) s"), "gpu": grab(r"gpu when ready: \d+, (\d+) MiB"),
            "mapped": grab(r"process when ready:.*?Pss_File: ([\d.]+) GiB"), "cache": cache, "extra": e["engine_build_digest"].split("extra arguments:")[-1].strip()}


def probes():
    out = []
    for p in sorted((MEASURED / "probe").glob("*.yaml")):
        d = json.loads("".join(ln for ln in p.read_text(encoding="utf-8").splitlines(True) if not ln.startswith("#")))
        for st in d.get("statements", []):
            if st.get("property") == "scattered_read_bandwidth":
                out.append((p.stem.split("measured-")[-1], st["conditions"].get("object_mb"), st["conditions"]["concurrency"], st["value"]))
    return out


def rng(v, f="{:.2f}"):
    lo, hi = min(v), max(v)
    return f.format(lo) if f.format(lo) == f.format(hi) else f.format(lo) + " to " + f.format(hi)


def place(value, lo, hi):
    """Where a measured value lies against a computed range, in words."""
    if value < lo:
        return f"below the range, {lo / value:.2f} times under its low end"
    if value > hi:
        return f"above the range, {value / hi:.2f} times over its high end"
    return "inside the range"


def main():
    runs = sys.argv[1:] or sorted((p.name for p in MEASURED.iterdir() if p.is_dir() and any(p.glob("evidence-*.yaml"))),
                                  key=lambda n: (n != "control", n))
    a80, a128 = assessment("muse-assessment-08-budget-80"), assessment("muse-assessment-08-budget-128")
    bound = a80["memory_bound_tok_per_s"]
    print("Muse Spark Open, the model files the bench runs, on DGX Spark")
    print("computed beforehand by tools/so_assess.py, beside measured on 2026-11-20\n")
    print("Computed, from the descriptions alone:")
    print(f"  upper bound on decode (memory bandwidth)      {bound:.1f} tok/s")
    for a, name in ((a80, " 80 GB"), (a128, "128 GB")):
        d, t = a["decode_estimate_range"], a["ttft_estimate_range_s"]
        print(f"  estimates within {name}: decode {d[0]:.2f} to {d[1]:.2f} tok/s; first token {t[0]:.0f} to {t[1]:.0f} s")
    for run in runs:
        m = measured(run)
        dec = statistics.median(m["decode"])
        held = (float(m["mapped"]) + int(m["gpu"]) / 1024) * 1.073741824 if m["mapped"] and m["gpu"] else None
        print(f"\nMeasured, run `{run}`: llama.cpp with the bench's configuration" + (f" and {m['extra']}" if m["extra"] else ""))
        print(f"  {m['n']} requests, prompts of {rng(m['prompt_n'], '{:,.0f}')} tokens, {rng(m['out'], '{:.0f}')} tokens out; "
              f"{m['warm']} warm-up requests not counted; the engine's own timings")
        if held:
            print(f"  the process held {m['mapped']} GiB of mapped model files and {int(m['gpu']) / 1024:.1f} GiB on the GPU when ready "
                  f"({held:.0f} GB together); ready {m['ready']} s after start")
        print(f"  decode                {rng(m['decode'])} tok/s (median {dec:.2f})")
        print(f"    against the bound   {'holds' if max(m['decode']) <= bound else 'DOES NOT HOLD'}: "
              f"the fastest request is {bound / max(m['decode']):.1f} times below {bound:.1f}")
        for a, name in ((a80, " 80 GB"), (a128, "128 GB")):
            lo, hi = a["decode_estimate_range"]
            print(f"    against {name}      {place(dec, lo, hi)} ({lo:.2f} to {hi:.2f})")
        tt = statistics.median(m["ttft"])
        print(f"  first token           {rng(m['ttft'], '{:.0f}')} s after the request (median {tt:.0f} s), of which reading the prompt "
              f"{rng(m['prompt_s'], '{:.0f}')} s")
        for a, name in ((a80, " 80 GB"), (a128, "128 GB")):
            lo, hi = a["ttft_estimate_range_s"]
            word = (f"{tt / hi:.0f} times longer than the high end" if tt > hi else
                    f"{lo / tt:.1f} times shorter than the low end" if tt < lo else "inside the range")
            print(f"    against {name}      {word} ({lo:.0f} to {hi:.0f} s)")
        if m["kv_bytes_per_cell_layer"]:
            per = m["kv_bytes_per_cell_layer"]
            model = described(a80["model"])
            fact = lambda prop: next(s["value"] for s in model["statements"] if s["property"] == prop)
            layers, mine = fact("layers"), fact("attention_state_per_token") / fact("layers")
            print(f"  attention state       {', '.join(f'{x:,}' for x in per)} bytes per token per layer in the server's buffers; "
                  f"the model description gives {mine:,.0f}: {'equal' if per == [round(mine)] else 'DIFFERENT'}")
        if m["cache"]:
            import so_assess
            c = m["cache"]
            n = next(o["selects"]["out_of"] for o in described(a80["model"])["operations"] if o.get("selects"))
            found = c["hits"] / (c["hits"] + c["misses"])
            most = so_assess.hit_rate(n, c["share"] * n, a80["max_skew"])
            print(f"  expert cache on GPU   {c['mib'] / 1024:.0f} GiB, {c['share']:.1%} of the experts; over the decode steps it held "
                  f"{found:.1%} of the experts asked for")
            print(f"    against the model   the arithmetic allows {c['share']:.1%} (even use) to {most:.1%} (the most uneven use possible) "
                  f"when each token chooses its experts independently: "
                  + ("above that" if found > most + 0.005 else "at its upper end" if found > most - 0.01 else "inside that"))
    pr = probes()
    if pr:
        env = described(a80["environment"])
        scattered = [(s["conditions"]["concurrency"], s["value"]) for s in env["statements"] if s.get("property") == "scattered_read_bandwidth"]
        picks = next(o["selects"]["pick"] for o in described(a80["model"])["operations"] if o.get("selects"))
        used = min(scattered, key=lambda x: abs(x[0] - picks))[1]      # the rate the assessment takes: nearest to the experts routed per layer
        print("\nStorage read rate, scattered ranges, three probes on the idle machine today:")
        for size in sorted({p[1] for p in pr}):
            v = [p[3] for p in pr if p[1] == size and p[0].startswith("20261120")]
            if v:
                print(f"  ranges of {size:g} MB      {rng(v)} GB/s over 1 to 32 reads in flight; the figures use {used:.2f}: "
                      f"{'inside what was measured' if min(v) <= used <= max(v) else 'outside what was measured'}")
    print("\nWhat the measured engine is and is not: the bench's baseline, which keeps what fits of the model files in the")
    print("page cache and computes the experts on the CPU. The estimates are for an engine that reads missing experts")
    print("while it computes and whose computing takes no time beyond reading memory.")


if __name__ == "__main__":
    main()
