"""Talking to the engine: start/stop, readiness, speed probe, token probabilities.

Uses only the OpenAI-compatible API plus llama.cpp's optional extras (/health, /tokenize,
"timings" in responses). Anything an engine does not provide is reported as unavailable.
"""
import json, math, os, shlex, signal, subprocess, time, urllib.request
from .requests import counts, rates

def _post(url, body, timeout=600):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)

def healthy(base_url):
    for path in ("/health", "/v1/models"):
        try:
            if urllib.request.urlopen(base_url.rstrip("/") + path, timeout=3).status == 200:
                return True
        except Exception:
            pass
    return False

class Server:
    """Starts the engine from a command template and records L0.time_to_ready."""
    def __init__(self, cfg, run_dir, prefix=None, finalize_timeout_s=1800):
        """prefix: a launcher put in front of the engine command (e.g. `nsys profile ...`)."""
        self.cfg, self.run_dir = cfg, run_dir
        self.prefix, self.finalize_timeout_s = list(prefix or []), finalize_timeout_s
        cmd = cfg["server"]["command"]
        self.engine_name = os.path.basename((cmd if isinstance(cmd, list) else shlex.split(cmd))[0])
        self.proc, self.log_path = None, os.path.join(run_dir, "server.log")
        match = cfg["server"].get("pid_match", "")
        self.server_exe = os.path.realpath(match) if os.path.isabs(match) else None
        self.server_pid = None

    def start(self, timeout_s):
        cmd = self.cfg["server"]["command"]
        self.t_start = time.time()
        self.log = open(self.log_path, "w")
        argv = self.prefix + (cmd if isinstance(cmd, list) else shlex.split(cmd))
        self.log.write("$ " + " ".join(shlex.quote(a) for a in argv) + "\n"); self.log.flush()
        self.proc = subprocess.Popen(argv, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        base = self.cfg["server"]["base_url"]
        while time.time() - self.t_start < timeout_s:
            if self.proc.poll() is not None:
                return None  # crashed
            if healthy(base):
                return time.time() - self.t_start
            time.sleep(1)
        return None

    @property
    def pid(self):
        if self.proc is None or self.proc.poll() is not None:
            return None
        if self.prefix:  # the engine is a child of the launcher: find it by executable name
            if self.server_pid is None or not os.path.exists(f"/proc/{self.server_pid}"):
                self.server_pid = descendant_named(self.proc.pid, self.engine_name)
            return self.server_pid
        if self.server_exe is None:
            return self.proc.pid
        if self.server_pid is not None and self._matches_executable(self.server_pid):
            return self.server_pid
        # Some launchers supervise the engine in a separate cgroup. Match the
        # private executable so samples cover the engine, including SSD reads.
        self.server_pid = next((int(pid) for pid in os.listdir("/proc")
                                if pid.isdigit() and self._matches_executable(pid)), None)
        return self.server_pid

    def _matches_executable(self, pid):
        try:
            return os.readlink(f"/proc/{pid}/exe") == self.server_exe
        except OSError:
            return False

    def stop(self, grace_seconds=30):
        if self.prefix and self.proc and self.proc.poll() is None:
            # stop only the engine; the launcher (profiler) then writes its report and exits by itself
            child = self.pid
            if child:
                try:
                    os.kill(child, signal.SIGTERM)
                except OSError:
                    pass
                try:
                    self.proc.wait(self.finalize_timeout_s)
                except subprocess.TimeoutExpired:
                    os.killpg(self.proc.pid, signal.SIGINT)
                    try:
                        self.proc.wait(300)
                    except subprocess.TimeoutExpired:
                        pass
        if self.proc and self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(grace_seconds)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait()
        if getattr(self, "log", None):
            self.log.close()

def descendant_named(root_pid, name):
    """First process below root_pid (any depth) whose executable name is `name`."""
    children = {}
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                stat = open(f"/proc/{p}/stat").read()
                ppid = int(stat.rsplit(")", 1)[1].split()[1])
                children.setdefault(ppid, []).append(int(p))
            except (OSError, ValueError, IndexError):
                pass
    todo = list(children.get(root_pid, []))
    while todo:
        pid = todo.pop(0)
        try:
            exe = os.path.basename(os.readlink(f"/proc/{pid}/exe"))
        except OSError:
            exe = ""
        if exe == name:
            return pid
        todo += children.get(pid, [])
    return None

def find_pid(pattern):
    """For an engine started elsewhere (e.g. already running): newest process whose cmdline matches."""
    best = None
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                cmd = open(f"/proc/{p}/cmdline").read().replace("\0", " ")
            except OSError:
                continue
            if pattern in cmd and "ifbench" not in cmd:
                best = int(p) if best is None else max(best, int(p))
    return best

def tokenize(base_url, text):
    try:
        r = json.loads(_post(base_url.rstrip("/") + "/tokenize", {"content": text}, 60).read())
        return len(r.get("tokens", []))
    except Exception:
        return None

def stream_completion(base_url, model, prompt, max_tokens, gen, cache_prompt=None, read_timeout_s=600):
    """One streamed /v1/completions request. Returns timing and token counts measured at the client."""
    body = {"model": model, "prompt": prompt, "max_tokens": max_tokens, "stream": True,
            "stream_options": {"include_usage": True}, **gen}
    if cache_prompt is not None:
        body["cache_prompt"] = cache_prompt
    t0 = time.time(); mono0 = time.monotonic(); first_mono = last_mono = None
    t_first = None; t_last = None; n_chunks = 0; text = []; finish_reason = None; done = False
    usage = timings = None
    try:
        with _post(base_url.rstrip("/") + "/v1/completions", body, timeout=read_timeout_s) as resp:
            for raw in resp:
                line = raw.decode().strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    done = True
                    break
                obj = json.loads(data)
                usage = obj.get("usage") or usage
                timings = obj.get("timings") or timings
                ch = (obj.get("choices") or [{}])[0]
                finish_reason = ch.get('finish_reason') or finish_reason
                piece = ch.get("text") or ""
                if piece:
                    now = time.time()
                    first_mono = time.monotonic() if first_mono is None else first_mono
                    last_mono = time.monotonic()
                    t_first = t_first or now
                    t_last = now
                    n_chunks += 1
                    text.append(piece)
    except Exception as e:
        return {"ok": False, "error": repr(e)}
    elapsed = time.monotonic() - mono0
    ni, no, source = counts(usage, timings)
    return {"ok": t_first is not None and (done or finish_reason is not None),
            "ttft_ms": (first_mono - mono0) * 1000 if first_mono is not None else None,
            "total_ms": elapsed * 1000, "t_first": t_first, "t_last": t_last,
            "chunks": n_chunks, "text": "".join(text), "usage": usage, "timings": timings,
            "input_tokens": ni, "output_tokens": no, "token_count_source": source,
            "finish_reason": finish_reason, **rates(no, elapsed, first_mono, last_mono)}

def filler_prompt(n_words, seed_text):
    words = seed_text.split()
    reps = (n_words // max(1, len(words))) + 1
    return " ".join((words * reps)[:n_words])

def speed_probe(cfg, rec, sampler):
    """About five minutes: warm-up, then prefill/decode at each configured depth (plan 5.5)."""
    s = cfg["server"]; p = cfg["probe"]; gen = cfg["generation"]
    base, model = s["base_url"], s["model"]
    seed_text = open(p["filler_text"]).read() if os.path.exists(p.get("filler_text", "")) else \
        "The quick brown fox jumps over the lazy dog while the engine reads every token carefully. " * 20
    # warm-up: same short request until latency settles
    lat = []
    for _ in range(p.get("warmup_max", 6)):
        r = stream_completion(base, model, "Say hello in one short sentence.", 16, gen)
        if not r["ok"]:
            rec.add("L1.failed_requests", 1, source="probe", note=r.get("error"))
            return None
        lat.append(r["total_ms"])
        if len(lat) >= 3 and abs(lat[-1] - lat[-2]) / lat[-2] < 0.1:
            break
    steady = sorted(lat[1:])[len(lat[1:]) // 2] if len(lat) > 1 else None
    rec.add("L0.first_request_ratio", round(lat[0] / steady, 2) if steady else None, source="probe",
            note=f"latencies ms: {[round(x) for x in lat]}; warm-up requests to discard: {len(lat)}")
    results = []
    for depth in p["depth_words"]:
        prompt = filler_prompt(depth + p["new_prompt_words"], seed_text) + "\n\nSummarize the text above."
        from .telemetry import proc_io_read_bytes
        pid = sampler.pid_fn()
        rb0 = proc_io_read_bytes(pid) if pid else None
        t0 = time.time()
        # prompts at different depths share a prefix: turn the prefix cache off so prefill is measured in full
        r = stream_completion(base, model, prompt, p["gen_tokens"], gen, cache_prompt=False,
                              read_timeout_s=p.get("read_timeout_s", 600))
        t1 = time.time()
        rb1 = proc_io_read_bytes(pid) if pid else None
        if not r["ok"]:
            rec.add("L1.failed_requests", 1, source="probe", note=r.get("error"))
            continue
        prompt_tokens = (r["usage"] or {}).get("prompt_tokens") or (r["timings"] or {}).get("prompt_n")
        out_tokens = r['output_tokens']
        dec_s = (r["t_last"] - r["t_first"]) if r["t_last"] and r["t_first"] else None
        res = {"depth_words": depth, "prompt_tokens": prompt_tokens, "output_tokens": out_tokens,
               "ttft_ms": round(r["ttft_ms"], 1), "cache_prompt": False,
               "prefill_tok_s_client": round(prompt_tokens / (r["ttft_ms"] / 1000), 1) if prompt_tokens else None,
               "decode_tok_s_client": r['decode_tok_s_client_estimate'],
               "e2e_output_tok_s": r['e2e_output_tok_s'], "total_ms": r['total_ms'],
               "token_count_source": r['token_count_source'], "finish_reason": r['finish_reason']}
        if depth == 0:
            res["text"] = r["text"]
        tm = r["timings"] or {}
        if tm:
            res["engine"] = {k: (round(tm[k], 2) if isinstance(tm.get(k), float) else tm.get(k))
                             for k in ("prompt_n", "prompt_ms", "prompt_per_second",
                                       "predicted_n", "predicted_ms", "predicted_per_second", "cache_n")}
        results.append(res)
        win = {"start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)),
               "end": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t1)), "label": f"probe depth {depth}"}
        rec.add("L1.ttft_client", res["ttft_ms"], source="probe (client clock)", window=win,
                note=f"prompt_tokens={prompt_tokens}")
        r1 = lambda v: round(v, 1) if isinstance(v, float) else v
        rec.add("L3.prefill_rate", r1(tm.get("prompt_per_second") or res["prefill_tok_s_client"]),
                source="engine timings" if tm.get("prompt_per_second") else "client estimate", window=win)
        rec.add("L3.decode_rate", r1(tm.get("predicted_per_second") or res["decode_tok_s_client"]),
                source="engine timings" if tm.get("predicted_per_second") else "client estimate", window=win)
        if tm.get("prompt_ms") is not None:
            rec.add("L3.ttft_engine", round(tm["prompt_ms"], 1), source="engine timings.prompt_ms", window=win,
                    note="prefill time inside the engine; excludes queueing")
            rec.add("L1.api_overhead", round(res["ttft_ms"] - tm["prompt_ms"], 1),
                    source="client TTFT - engine timings.prompt_ms", window=win,
                    note="time outside the engine's prefill: HTTP, template, tokenization, queueing, first chunk")
        n_tok = tokenize(base, prompt)
        rec.add("L1.token_count_check", {"engine_reported": prompt_tokens, "tokenize_endpoint": n_tok,
                                         "match": (n_tok is not None and prompt_tokens is not None and abs(n_tok - prompt_tokens) <= 2)},
                source="usage vs /tokenize", window=win)
        if rb0 is not None and rb1 is not None and out_tokens:
            rec.add("M.storage_read_per_token", round((rb1 - rb0) / 1e9 / out_tokens, 4), source="/proc/<pid>/io read_bytes",
                    window=win, note=f"{(rb1-rb0)/1e9:.2f} GB read during the whole request (prefill + {out_tokens} generated tokens)")
        else:
            rec.add("M.storage_read_per_token", None, "unavailable", "/proc/<pid>/io", window=win, note="engine pid not found")
        from .telemetry import summarize_window
        summarize_window(rec, sampler, r["t_first"], r["t_last"] or t1, f"decode at depth {depth}", out_tokens)
        expert_cache_estimate(cfg, rec, sampler, r["t_first"], r["t_last"] or t1, out_tokens, depth)
    return results

def expert_cache_estimate(cfg, rec, sampler, t0, t1, out_tokens, depth):
    """M.expert_cache_hit, estimated without engine counters (T1-derived).

    During decode, each token needs the routed experts it selects: expert_bytes / expert_count *
    expert_used_count per layer (from the GGUF header). Whatever the engine had to read from the SSD
    in that window was not in memory. hit ~= 1 - (SSD bytes read per token / routed-expert bytes per
    token). Read-ahead can read more than was needed, so this is a lower bound on the true hit rate.
    """
    ex = cfg.get("_experts") or {}
    if ex.get('architecture') and not ex.get('expert_count'):
        return
    need = ex.get("routed_bytes_per_token")
    win = {"start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)),
           "end": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t1)), "label": f"decode at depth {depth}"}
    rb = [s["proc_read_bytes"] for s in sampler.window(t0, t1) if s.get("proc_read_bytes") is not None]
    if not need or len(rb) < 2 or not out_tokens or out_tokens < 2:
        rec.add("M.expert_cache_hit", None, "unavailable", "GGUF header + /proc/<pid>/io", win,
                note="needs routed-expert sizes from the GGUF and two read-byte samples in the decode window"
                     + (f" ({ex.get('error')})" if ex.get("error") else ""))
        return
    read_per_tok = (rb[-1] - rb[0]) / (out_tokens - 1)
    hit = max(0.0, 1 - read_per_tok / need)
    flt = [s["proc_faults"] for s in sampler.window(t0, t1) if s.get("proc_faults")]
    maj = round((flt[-1][1] - flt[0][1]) / (out_tokens - 1), 1) if len(flt) >= 2 else None
    rec.add("M.expert_cache_hit", {"hit_pct_estimate": round(100 * hit, 1),
                                   "ssd_gb_per_token": round(read_per_tok / 1e9, 4),
                                   "routed_expert_gb_per_token": round(need / 1e9, 4),
                                   "major_page_faults_per_token": maj},
            source="estimate: 1 - SSD read per decoded token / routed-expert bytes per token (GGUF header)", window=win,
            note=f"lower bound (read-ahead inflates reads); {ex.get('expert_used_count')} of {ex.get('expert_count')} experts "
                 f"in {ex.get('moe_layers')} layers; exact per-expert hit rate is T3")

# ---------------- token probabilities (L4.token_prob_match) ----------------

def token_probs(cfg, prompts, n_tokens, top_k):
    """Greedy continuation with top-k log-probabilities per position, via /v1/completions."""
    s = cfg["server"]; out = []
    for i, prompt in enumerate(prompts):
        body = {"model": s["model"], "prompt": prompt, "max_tokens": n_tokens, "temperature": 0,
                "logprobs": top_k, "seed": cfg["generation"].get("seed", 1234), "cache_prompt": False}
        try:
            r = json.loads(_post(s["base_url"].rstrip("/") + "/v1/completions", body).read())
            lp = r["choices"][0].get("logprobs") or {}
            top = lp.get("top_logprobs")
            if top is None and "content" in lp:  # chat-style shape
                top = [{t["token"]: t["logprob"] for t in c.get("top_logprobs", [])} for c in lp["content"]]
            out.append({"i": i, "prompt": prompt, "text": r["choices"][0].get("text"),
                        "tokens": lp.get("tokens"), "top_logprobs": top})
        except Exception as e:
            out.append({"i": i, "prompt": prompt, "error": repr(e)})
    return out

def compare_token_probs(ref, cand):
    """Mean KL(ref || cand) over shared top-k tokens and top-1 agreement. For later candidate runs."""
    kls, agree, n = [], 0, 0
    for a, b in zip(ref, cand):
        for pa, pb in zip(a.get("top_logprobs") or [], b.get("top_logprobs") or []):
            if not pa or not pb:
                continue
            n += 1
            agree += max(pa, key=pa.get) == max(pb, key=pb.get)
            common = set(pa) & set(pb)
            if common:
                za = sum(math.exp(pa[t]) for t in common); zb = sum(math.exp(pb[t]) for t in common)
                kls.append(sum(math.exp(pa[t]) / za * (pa[t] - math.log(za) - pb[t] + math.log(zb)) for t in common))
    return {"positions": n, "top1_match": round(agree / n, 4) if n else None,
            "mean_kl_on_shared_topk": round(sum(kls) / len(kls), 5) if kls else None}
