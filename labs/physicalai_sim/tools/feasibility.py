"""X1.1 local feasibility (PAS-M1-001 B13, AC-001, V-X1.1; ARCHC A-13).

Proves (or disproves, with evidence) that the unmodified AI4R app, one real
model-route request and a SIMLAB simulator process run together on this laptop,
and records what they cost.

    python tools/feasibility.py start --output DIR   # AI4R app up on 127.0.0.1:5175
    (owner opens the bootstrap URL from the app log and signs in to ChatGPT)
    python tools/feasibility.py run   --output DIR   # simulator + one model call, sampled
    python tools/feasibility.py stop  --output DIR   # AI4R stopped; volumes kept

The single model request is AI4R's own governed local-chat call (WebSocket
method `codex.chat`, which calls `invoke_governed` once). The tool redeems the
app's reusable loopback bootstrap exactly as AI4R's CLI does
(`jiuwenswarm/channels/cli/research.py`), keeps the token in memory only and
never writes it or the bootstrap challenge to evidence.

The result is PASS only with a real non-empty answer from a confirmed model,
a simulator process that ran concurrently, and resource samples. Anything else
is FAIL or BLOCKED with the raw evidence. Imports no AI4R code.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hostmon  # noqa: E402

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parents[1]
COMPOSE = REPO / "deploy/m1/compose.benchmark-runner.yaml"
PROJECT = "ai4r-local"
ORIGIN = "http://127.0.0.1:5175"
SIM_IMAGE = "simlab-runner:dev"
SIM_NAME = "simlab-x11-sim"
CHALLENGE_RE = re.compile(r"research_bootstrap=([A-Za-z0-9_-]{43})")
REDACT = [(CHALLENGE_RE, "research_bootstrap=<redacted>"),
          (re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]{16,}"), r"\1<redacted>"),
          (re.compile(r"(user_code|device_code|code)([\"':=\s]+)[A-Z0-9-]{6,}"), r"\1\2<redacted>")]


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sh(cmd: list[str], timeout: float = 120, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, **(env or {})})


def redact(text: str) -> str:
    for rx, rep in REDACT:
        text = rx.sub(rep, text)
    return text


# AI4R_LOCAL_RESEARCH=0: on this baseline the local-research capture needs an imported public
# dataset (JIUWENSWARM_M1_EXTERNAL_DATASET) for any plan source, and X1.1 needs only the app, its
# model route and one governed call. The research side then runs in AI4R's own refusal-only mode.
COMPOSE_ENV = {"AI4R_LOCAL_CHAT": "1", "AI4R_LOCAL_WORKSPACE": "1",
               "AI4R_LOCAL_RESEARCH": os.environ.get("AI4R_LOCAL_RESEARCH", "0")}


def compose(*args: str, timeout: float = 300) -> subprocess.CompletedProcess:
    env = dict(COMPOSE_ENV)
    return sh(["docker", "compose", "-p", PROJECT, "-f", str(COMPOSE), *args], timeout=timeout, env=env)


def write(out: Path, name: str, data) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    p = out / name
    p.write_text(data if isinstance(data, str) else json.dumps(data, indent=2, sort_keys=True) + "\n")
    return p


def port_open(host="127.0.0.1", port=5175, timeout=1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def inventory() -> dict:
    cpu = ""
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            cpu = line.split(":", 1)[1].strip()
            break
    inv = {"utc": utc(), "cpu_model": cpu, "threads": os.cpu_count(), "kernel": os.uname().release,
           "vm_memory_mb": hostmon.meminfo_mb(), "gpu_mem_used_mb": hostmon.gpu_mb()}
    r = sh(["docker", "version", "--format", "{{.Server.Version}} {{.Server.Os}}/{{.Server.Arch}}"])
    inv["docker"] = r.stdout.strip() or r.stderr.strip()
    r = sh(["docker", "info", "--format", "{{.MemTotal}} {{.NCPU}} {{.OperatingSystem}}"])
    inv["docker_info"] = r.stdout.strip()
    r = sh(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
    inv["gpu"] = r.stdout.strip() if r.returncode == 0 else None
    r = sh(["git", "-C", str(REPO), "rev-parse", "HEAD"])
    inv["git_head"] = r.stdout.strip()
    r = sh(["git", "-C", str(REPO), "status", "--porcelain", "--", ".", ":(exclude)labs/physicalai_sim"])
    inv["ai4r_tree_modified_paths"] = [x for x in r.stdout.splitlines() if x.strip()]
    for img in ("ai4r:local", SIM_IMAGE):
        r = sh(["docker", "image", "inspect", "--format", "{{.Id}} {{.Size}} {{.Created}}", img])
        inv[f"image {img}"] = r.stdout.strip() or ("missing: " + r.stderr.strip())
    r = sh(["docker", "run", "--rm", "--network", "none", "--entrypoint", "cat", "ai4r:local",
            "/usr/local/share/ai4r-build-identity.json"])
    inv["ai4r_build_identity"] = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip().startswith("{") else r.stderr.strip()
    return inv


def http(method: str, path: str, token: str | None = None, body: dict | None = None, timeout: float = 30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(ORIGIN + path, data=data, method=method)
    req.add_header("Origin", ORIGIN)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except json.JSONDecodeError:
            return e.code, None


def challenge_from_logs() -> str | None:
    r = compose("logs", "--no-color", "ai4r", timeout=60)
    found = CHALLENGE_RE.findall(r.stdout + r.stderr)
    return found[-1] if found else None


def native_token() -> tuple[str | None, dict]:
    ch = challenge_from_logs()
    if not ch:
        return None, {"error": "no bootstrap link in the app log"}
    status, value = http("POST", "/auth/research/bootstrap", body={"challenge": ch})
    if status != 200 or not isinstance(value, dict) or not value.get("token"):
        return None, {"http_status": status, "error": (value or {}).get("error") if isinstance(value, dict) else value}
    return value["token"], {"http_status": status, "reusable_bootstrap": value.get("reusable_bootstrap")}


def model_prerequisite(readiness) -> dict | None:
    """Find the `model` prerequisite wherever the readiness document places it."""
    if isinstance(readiness, dict):
        for key in ("prerequisites", "items", "checks"):
            items = readiness.get(key)
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict) and (it.get("id") == "model" or it.get("name") == "model" or it.get("prerequisite") == "model"):
                        return it
            if isinstance(items, dict) and "model" in items:
                v = items["model"]
                return v if isinstance(v, dict) else {"state": v}
        for v in readiness.values():
            found = model_prerequisite(v)
            if found:
                return found
    elif isinstance(readiness, list):
        for v in readiness:
            found = model_prerequisite(v)
            if found:
                return found
    return None


def is_ready(item: dict | None) -> bool:
    if not item:
        return False
    return any(str(item.get(k, "")).lower() in {"ready", "available", "ok", "pass"} for k in ("state", "status", "readiness"))


async def subscription_status(token: str) -> dict:
    """AI4R's own `codex.auth.status`: the gate for its governed local-chat route."""
    from websockets.asyncio.client import connect

    req_id = "simlab-x11-status-" + uuid.uuid4().hex[:8]
    async with connect(ORIGIN.replace("http", "ws") + "/ws", additional_headers={"Authorization": "Bearer " + token},
                       open_timeout=30) as ws:
        await ws.send(json.dumps({"type": "req", "id": req_id, "method": "codex.auth.status", "params": {}}))
        async with asyncio.timeout(60):
            async for raw in ws:
                v = json.loads(raw)
                if isinstance(v, dict) and v.get("type") == "res" and v.get("id") == req_id:
                    p = v.get("payload") if isinstance(v.get("payload"), dict) else {}
                    return {"ok": v.get("ok"), "state": p.get("state"), "plan": p.get("plan"),
                            "milestone": p.get("milestone"), "error": p.get("error") or v.get("error")}
    return {"ok": False, "error": "no response"}


async def one_model_call(token: str, prompt: str, model: str) -> dict:
    from websockets.asyncio.client import connect  # SIMLAB venv dependency (via mujoco)

    req_id = "simlab-x11-" + uuid.uuid4().hex[:12]
    rec = {"request_id": req_id, "method": "codex.chat", "prompt": prompt, "requested_model": model,
           "sent_utc": None, "received_utc": None, "latency_s": None, "frames_seen": []}
    async with connect(ORIGIN.replace("http", "ws") + "/ws", additional_headers={"Authorization": "Bearer " + token},
                       open_timeout=30, max_size=2**22) as ws:
        # AI4R accepts codex.chat only on a conversation it created (session.create; metadata only, no model call).
        cid = "simlab-x11-create-" + uuid.uuid4().hex[:8]
        await ws.send(json.dumps({"type": "req", "id": cid, "method": "session.create",
                                  "params": {"create_token": uuid.uuid4().hex, "title": "SIMLAB X1.1 connectivity check"}}))
        session_id = None
        async with asyncio.timeout(60):
            async for raw in ws:
                v = json.loads(raw)
                if isinstance(v, dict) and v.get("type") == "res" and v.get("id") == cid:
                    p = v.get("payload") if isinstance(v.get("payload"), dict) else {}
                    session_id = p.get("session_id")
                    rec["session_create"] = {"ok": v.get("ok"), "error": v.get("error"), "session_id_shape_ok":
                                             bool(session_id and session_id.startswith("chat-"))}
                    break
        if not session_id:
            rec["error"] = "session.create refused: " + json.dumps(rec.get("session_create"))
            return rec
        frame = {"type": "req", "id": req_id, "method": "codex.chat",
                 "params": {"session_id": session_id, "content": prompt, "codex_model": model}}
        t0 = time.monotonic()
        rec["sent_utc"] = utc()
        await ws.send(json.dumps(frame))
        async with asyncio.timeout(300):
            async for raw in ws:
                value = json.loads(raw)
                if not isinstance(value, dict):
                    continue
                rec["frames_seen"].append({k: value.get(k) for k in ("type", "id", "event") if k in value})
                if value.get("type") == "res" and value.get("id") == req_id:
                    rec["received_utc"] = utc()
                    rec["latency_s"] = round(time.monotonic() - t0, 3)
                    rec["ok"] = bool(value.get("ok"))
                    payload = value.get("payload")
                    if rec["ok"] and isinstance(payload, dict):
                        rec["answer"] = payload.get("content")
                        rec["effective_model"] = payload.get("model")
                    else:
                        rec["error"] = value.get("error") or payload
                    return rec
    rec["error"] = "connection closed without a response"
    return rec


def cmd_start(a) -> int:
    out = a.output
    t0 = time.monotonic()
    pre = {"inventory": inventory(), "port_5175_open_before": port_open(), "compose_env": COMPOSE_ENV,
           "compose_file": str(COMPOSE.relative_to(REPO))}
    write(out, "preflight.json", pre)
    r = compose("up", "-d", "ai4r", timeout=600)
    up = {"utc": utc(), "exit_code": r.returncode, "stdout": redact(r.stdout), "stderr": redact(r.stderr)}
    deadline = time.monotonic() + a.wait_s
    while time.monotonic() < deadline and not port_open():
        time.sleep(2)
    up["port_5175_open"] = port_open()
    up["seconds_to_port"] = round(time.monotonic() - t0, 1)
    while time.monotonic() < deadline and not challenge_from_logs():
        st = sh(["docker", "inspect", "--format", "{{.State.Status}} {{.State.ExitCode}}", f"{PROJECT}-ai4r-1"])
        if st.stdout.split()[:1] in (["exited"], ["dead"]):
            up["container_exited"] = st.stdout.strip()
            break
        time.sleep(2)
    up["bootstrap_link_in_log"] = challenge_from_logs() is not None
    tail = compose("logs", "--no-color", "--tail", "40", "ai4r", timeout=60)
    up["log_tail"] = redact(tail.stdout + tail.stderr)[-4000:]
    r = sh(["docker", "ps", "--filter", f"label=com.docker.compose.project={PROJECT}", "--format", "{{json .}}"])
    up["containers"] = [json.loads(x) for x in r.stdout.splitlines() if x.strip()]
    up["host_after_start"] = hostmon.meminfo_mb()
    write(out, "start.json", up)
    print(json.dumps({k: up[k] for k in ("exit_code", "port_5175_open", "seconds_to_port", "bootstrap_link_in_log")}))
    if up["exit_code"] == 0 and up["port_5175_open"] and up["bootstrap_link_in_log"]:
        print("Owner action: run\n  docker compose -p ai4r-local -f deploy/m1/compose.benchmark-runner.yaml logs ai4r | grep research_bootstrap\n"
              "open that full URL in a browser, sign in to ChatGPT in Settings and choose ChatGPT (codex) as the model.")
        return 0
    return 1


def volume_sizes() -> dict:
    r = sh(["docker", "volume", "ls", "-q", "--filter", f"name={PROJECT}_"])
    sizes = {}
    for vol in r.stdout.split():
        d = sh(["docker", "run", "--rm", "--network", "none", "-v", f"{vol}:/v:ro", "--entrypoint", "du",
                SIM_IMAGE, "-sk", "/v"], timeout=120)
        try:
            sizes[vol] = round(int(d.stdout.split()[0]) / 1024, 2)
        except (ValueError, IndexError):
            sizes[vol] = None
    return sizes


def cmd_run(a) -> int:
    out = a.output
    record = {"record": "simlab-feasibility-x11", "v_id": "V-X1.1", "ac": "PAS-M1-001/AC-001", "started_utc": utc(),
              "failures": [], "inventory": inventory()}
    mon = hostmon.HostMonitor(interval_s=a.interval_s).start()
    record["port_5175_open"] = port_open()
    record["volumes_before_mb"] = volume_sizes()
    if not record["port_5175_open"]:
        record["failures"].append("AI4R app is not listening on 127.0.0.1:5175")
    token, boot = native_token() if record["port_5175_open"] else (None, {"error": "app not up"})
    record["bootstrap"] = boot
    # Gate: the ChatGPT subscription behind AI4R's governed local-chat route is signed in.
    # AI4R's research readiness `model` item is recorded too; it reports ready only for the
    # manual `codex` research mode, which the local-chat route does not use.
    readiness_log = []
    model_ready = False
    deadline = time.monotonic() + a.wait_signin_s
    while token:
        try:
            sub = asyncio.run(subscription_status(token))
        except Exception as exc:
            sub = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        st, rd = http("GET", "/api/v1/readiness", token)
        readiness_log.append({"utc": utc(), "subscription": sub, "readiness_http_status": st,
                              "readiness_model_item": model_prerequisite(rd)})
        record["readiness"] = rd
        if sub.get("state") == "ready":
            model_ready = True
            break
        if time.monotonic() > deadline:
            break
        time.sleep(10)
    record["readiness_polls"] = readiness_log
    record["model_route_signed_in"] = model_ready
    record["subscription_plan"] = (readiness_log[-1]["subscription"].get("plan") if readiness_log else None)

    # The simulator process, started before the model call so they overlap.
    sim_cmd = ["docker", "run", "--rm", "--name", SIM_NAME, "--network", "none", "--read-only",
               "--memory", a.sim_memory, "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
               SIM_IMAGE, "feasibility-sim", "--wall-s", str(a.sim_wall_s), "--report-every-s", "10"]
    record["simulator_cmd"] = sim_cmd
    sh(["docker", "rm", "-f", SIM_NAME])
    sim_t0 = utc()
    sim = subprocess.Popen(sim_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(min(10.0, a.sim_wall_s / 4))
    call = None
    if token and model_ready:
        try:
            call = asyncio.run(one_model_call(token, a.prompt, a.model))
        except Exception as exc:  # the real failure is the evidence
            call = {"error": f"{type(exc).__name__}: {exc}"}
    else:
        call = {"not_sent": "ChatGPT subscription not signed in" if token else "no native session", "bootstrap": boot}
    record["model_call"] = call
    try:
        sim_out, sim_err = sim.communicate(timeout=a.sim_wall_s + 120)
    except subprocess.TimeoutExpired:
        sim.kill()
        sim_out, sim_err = sim.communicate()
        record["failures"].append("simulator process exceeded its wall time")
    record["simulator"] = {"started_utc": sim_t0, "ended_utc": utc(), "exit_code": sim.returncode,
                           "stderr_tail": sim_err[-2000:]}
    try:
        record["simulator"]["report"] = json.loads(sim_out.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        record["simulator"]["stdout_tail"] = sim_out[-2000:]
    summary = mon.stop()
    record["resources"] = {"host": summary}
    record["volumes_after_mb"] = volume_sizes()
    record["port_5175_open_after"] = port_open()
    logs = compose("logs", "--no-color", "--tail", "400", "ai4r", timeout=60)
    write(out, "ai4r-app.log", redact(logs.stdout + logs.stderr))
    oom = sh(["docker", "inspect", "--format", "{{.State.OOMKilled}} {{.State.Status}} {{.RestartCount}}",
              f"{PROJECT}-ai4r-1"])
    record["ai4r_container_state"] = oom.stdout.strip()
    write(out, "samples.json", mon.samples)

    # Disk written: growth of the app's volumes during the run (the simulator writes nothing).
    before, after = record["volumes_before_mb"], record["volumes_after_mb"]
    record["resources"]["disk_written_mb"] = round(sum((after.get(k) or 0) - (before.get(k) or 0) for k in after), 2)
    sim_rep = record["simulator"].get("report") or {}
    record["resources"]["simulator_cpu_s"] = sim_rep.get("cpu_s")
    record["resources"]["simulator_peak_rss_mb"] = sim_rep.get("peak_rss_mb")

    # Classification: the evidence decides; nothing is converted to PASS.
    answered = bool(call and call.get("ok") and isinstance(call.get("answer"), str) and call["answer"].strip()
                    and call.get("effective_model"))
    sim_ok = record["simulator"]["exit_code"] == 0 and sim_rep.get("steps", 0) > 0
    overlap = bool(call and call.get("sent_utc") and sim_t0 <= call["sent_utc"] <= record["simulator"]["ended_utc"])
    sampled = summary.get("n_samples", 0) > 0
    if not sim_ok:
        record["failures"].append("simulator process did not complete with steps")
    if call and call.get("error"):
        record["failures"].append("model request failed: " + json.dumps(call.get("error"))[:500])
    if "true" in record["ai4r_container_state"].lower().split()[:1]:
        record["failures"].append("AI4R container was OOM-killed")
    if record["port_5175_open"] and answered and sim_ok and overlap and sampled and not record["failures"]:
        record["result"] = "PASS"
    elif not model_ready and not record["failures"]:
        record["result"] = "BLOCKED"
        record["blocked_reason"] = "model sign-in not completed (owner action U-01)" if token else "no native session"
    else:
        record["result"] = "FAIL"
    record["checks"] = {"ai4r_on_5175": record["port_5175_open"], "real_answer_from_confirmed_model": answered,
                        "simulator_completed": sim_ok, "model_call_during_simulation": overlap,
                        "resource_samples": sampled}
    record["ended_utc"] = utc()
    write(out, "feasibility.json", record)
    print(json.dumps({"result": record["result"], "checks": record["checks"], "failures": record["failures"],
                      "host": summary, "latency_s": (call or {}).get("latency_s"),
                      "effective_model": (call or {}).get("effective_model")}, indent=1))
    return 0 if record["result"] == "PASS" else 1


def cmd_stop(a) -> int:
    r = compose("stop", "ai4r", timeout=180)
    rec = {"utc": utc(), "exit_code": r.returncode, "stderr": redact(r.stderr), "port_5175_open_after": port_open()}
    write(a.output, "stop.json", rec)
    print(json.dumps(rec))
    return r.returncode


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="op", required=True)
    for name in ("start", "run", "stop"):
        p = sub.add_parser(name)
        p.add_argument("--output", type=Path, required=True)
    sub.choices["start"].add_argument("--wait-s", type=float, default=300)
    r = sub.choices["run"]
    r.add_argument("--wait-signin-s", type=float, default=0, help="poll readiness this long for the owner's sign-in")
    r.add_argument("--sim-wall-s", type=float, default=90)
    r.add_argument("--sim-memory", default="1g")
    r.add_argument("--interval-s", type=float, default=2.0)
    r.add_argument("--prompt", default="This is a connectivity check from the SIMLAB lab. Reply with the single word OK.")
    r.add_argument("--model", default="gpt-6.1-sol")
    a = ap.parse_args(argv)
    return {"start": cmd_start, "run": cmd_run, "stop": cmd_stop}[a.op](a)


if __name__ == "__main__":
    raise SystemExit(main())
