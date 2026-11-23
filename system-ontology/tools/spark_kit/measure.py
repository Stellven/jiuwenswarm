#!/usr/bin/env python3
"""Baseline measurement: against an OpenAI-compatible streaming endpoint (llama.cpp server, vLLM and the like), measures time to first
token, decode rate and system memory use, and writes them as a System Ontology evidence file.

Uses only the Python standard library. It does not start an engine; it measures an endpoint that is already running.

Usage:
  python3 measure.py --base-url http://127.0.0.1:8080/v1 --model <model name> \\
      --artifact "llama.cpp <commit> + <sha256 of the weight file>" \\
      --verifies spec/muse-spark-open-on-dgx-spark/target#c-ttft \\
      --verifies spec/muse-spark-open-on-dgx-spark/target#c-decode \\
      --name baseline-01

How this script measures each quantity (written into the evidence file, to be compared with what the contract says):
  ttft        the clock starts before the client sends the request and stops when the client receives the first non-empty content delta
  decode_rate (completed tokens - 1) / (time of the last delta - time of the first delta); the first token is not counted
              the token count is usage.completion_tokens when the endpoint returns it; otherwise the number of deltas is used, and this is noted
  peak_memory whole machine: the largest drop in the available memory of the system during the measurement, not the engine process's own use; Linux only
"""
import argparse
import datetime
import json
import os
import statistics
import sys
import threading
import time
import urllib.request

DEFAULT_PROMPTS = [
    "Explain in three sentences what the page cache of an operating system is.",
    "Write a C function that reverses a singly linked list in place, with a short comment for each step.",
    "List five common sorting algorithms and give the time complexity of each in one sentence.",
]


def mem_available():
    if not sys.platform.startswith("linux"):
        return None
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    return None


class MemWatch(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.start_value = mem_available()
        self.low = self.start_value
        self.stop = False

    def run(self):
        while not self.stop and self.start_value is not None:
            v = mem_available()
            if v is not None and v < self.low:
                self.low = v
            time.sleep(0.2)


def one_request(base_url, model, prompt, max_tokens, api_key, timeout, extra_body=None):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
            "temperature": 0, "stream": True, "stream_options": {"include_usage": True}}
    body.update(extra_body or {})
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key})
    t0 = time.perf_counter()
    first = last = None
    deltas = 0
    usage_tokens = prompt_tokens = engine = None
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                event = json.loads(payload)
            except ValueError:
                continue
            if event.get("usage"):
                usage_tokens = event["usage"].get("completion_tokens", usage_tokens)
                prompt_tokens = event["usage"].get("prompt_tokens", prompt_tokens)
            if isinstance(event.get("timings"), dict):          # the runtime's own timings (llama.cpp gives them in the last event)
                engine = event["timings"]
            for choice in event.get("choices") or []:
                d = choice.get("delta") or {}
                if d.get("content") or d.get("reasoning_content"):
                    now = time.perf_counter()
                    first = first if first is not None else now
                    last = now
                    deltas += 1
    if first is None:
        raise RuntimeError("the endpoint returned no content delta")
    tokens = usage_tokens if usage_tokens else deltas
    rate = (tokens - 1) / (last - first) if tokens > 1 and last > first else None
    return {"ttft_s": first - t0, "decode_tok_per_s": rate, "completion_tokens": tokens,
            "token_count_from": "usage" if usage_tokens else "delta_count", "total_s": last - t0,
            "prompt_tokens": prompt_tokens, "engine_timings": engine}


def main():
    for stream in (sys.stdout, sys.stderr):        # so that non-ASCII text prints even when the terminal is not UTF-8
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Baseline measurement of an OpenAI-compatible streaming endpoint; writes an evidence file")
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--name", default="baseline-01")
    ap.add_argument("--artifact", default="UNSET: give the runtime version and the identifier of the weight file")
    ap.add_argument("--verifies", action="append", default=[])
    ap.add_argument("--hardware", default="hw/dgx-spark")
    ap.add_argument("--environment", default="env/dgx-spark-measured")
    ap.add_argument("--prompts", help="text file with one prompt per line; when not given, the three built-in prompts are used")
    ap.add_argument("--max-tokens", type=int, default=128)
    ap.add_argument("--runs", type=int, default=3, help="how many times each prompt is sent")
    ap.add_argument("--warmup", type=int, default=0, help="this many first lines of the prompt file are used only to warm up: each is sent once and not counted in the results")
    ap.add_argument("--extra-body", help="JSON merged into the request body, for the runtime's own fields, for example '{\"cache_prompt\": false}'")
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", "none"))
    ap.add_argument("--timeout", type=float, default=1800.0)
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()

    prompts = DEFAULT_PROMPTS
    if args.prompts:
        with open(args.prompts, encoding="utf-8") as f:
            prompts = [l.strip() for l in f if l.strip()]
    extra = json.loads(args.extra_body) if args.extra_body else None
    warm, prompts = prompts[:args.warmup], prompts[args.warmup:]
    warmups = []
    for w_i, prompt in enumerate(warm):
        try:
            s = one_request(args.base_url, args.model, prompt, args.max_tokens, args.api_key, args.timeout, extra)
            warmups.append(s)
            print("warm-up %d: TTFT %.3f s, decode %s tok/s (not counted)" % (
                w_i, s["ttft_s"], "—" if s["decode_tok_per_s"] is None else "%.2f" % s["decode_tok_per_s"]))
        except Exception as e:
            warmups.append({"error": repr(e)})
            print("warm-up %d failed: %r" % (w_i, e))
    watch = MemWatch()
    watch.start()
    samples, errors = [], []
    for p_i, prompt in enumerate(prompts):
        for r in range(args.runs):
            try:
                s = one_request(args.base_url, args.model, prompt, args.max_tokens, args.api_key, args.timeout, extra)
                s.update({"prompt": p_i, "run": r})
                samples.append(s)
                print("prompt %d run %d: TTFT %.3f s, decode %s tok/s, %d tokens" % (
                    p_i, r, s["ttft_s"], "—" if s["decode_tok_per_s"] is None else "%.2f" % s["decode_tok_per_s"],
                    s["completion_tokens"]))
            except Exception as e:
                errors.append({"prompt": p_i, "run": r, "error": repr(e)})
                print("prompt %d run %d failed: %r" % (p_i, r, e))
    watch.stop = True
    watch.join(1)

    def med(key):
        vals = [s[key] for s in samples if s[key] is not None]
        return round(statistics.median(vals), 4) if vals else None

    def med_engine(key):
        vals = [s["engine_timings"][key] for s in samples
                if s.get("engine_timings") and isinstance(s["engine_timings"].get(key), (int, float))]
        return round(statistics.median(vals), 4) if vals else None

    when = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    drop = None if watch.start_value is None else round((watch.start_value - watch.low) / 1e9, 2)
    evidence = {
        "kind": "evidence", "id": "evidence/" + args.name, "verifies": args.verifies,
        "engine_build_digest": args.artifact,
        "quality": "median_of_n" if len(samples) >= 3 else "single_run",
        "workload": "%d prompts, %d runs each, max_tokens=%d, temperature=0, one request at a time in order; %d warm-up requests not counted%s" % (
            len(prompts), args.runs, args.max_tokens, len(warm), "; added to the request body: " + args.extra_body if args.extra_body else ""),
        "measured_under": {
            "hardware": args.hardware, "environment": args.environment, "endpoint": args.base_url,
            "model_name": args.model, "time": when,
            "definitions": {
                "ttft": "starts before the client sends the request; ends when the client receives the first non-empty content delta",
                "decode_rate": "(completed tokens - 1) / (time of the last delta - time of the first delta); the first token is not counted",
                "peak_memory": "whole machine: the largest drop in the system's MemAvailable during the measurement; not the engine process's own use",
                "token_count_from": sorted({s["token_count_from"] for s in samples}),
            },
        },
        "baseline": "none; this is itself the baseline measurement of an off-the-shelf runtime",
        "results": {
            "ttft_s_median": med("ttft_s"), "decode_tok_per_s_median": med("decode_tok_per_s"),
            "prompt_tokens_median": med("prompt_tokens"),
            # the runtime's own timings, present only when it gives them in the stream (llama.cpp times the prompt phase and the generation phase separately)
            "engine_prompt_tok_per_s_median": med_engine("prompt_per_second"),
            "engine_prompt_ms_median": med_engine("prompt_ms"),
            "engine_decode_tok_per_s_median": med_engine("predicted_per_second"),
            "system_memory_drop_gb": drop, "samples": samples, "warmups": warmups, "errors": errors,
            "requests_ok": len(samples), "requests_failed": len(errors),
        },
    }
    os.makedirs(args.out_dir, exist_ok=True)
    out = os.path.join(args.out_dir, "evidence-%s.yaml" % args.name)
    with open(out, "w", encoding="utf-8") as f:
        f.write("# Measured evidence written by spark_kit/measure.py. The content is JSON, which is also valid YAML.\n")
        json.dump(evidence, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("median TTFT %s s; median decode %s tok/s; largest drop in system memory %s GB" % (
        evidence["results"]["ttft_s_median"], evidence["results"]["decode_tok_per_s_median"], drop))
    if evidence["results"]["engine_decode_tok_per_s_median"] is not None:
        print("the runtime's own timings: prompt %s tok/s, generation %s tok/s" % (
            evidence["results"]["engine_prompt_tok_per_s_median"], evidence["results"]["engine_decode_tok_per_s_median"]))
    print("wrote %s" % out)
    return 0 if samples else 1


if __name__ == "__main__":
    sys.exit(main())
