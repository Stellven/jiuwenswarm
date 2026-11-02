"""X1.4 part (b): a coding agent with no other access builds, runs and inspects an experiment only through the
SIMLAB tools (PAS-M1-001 V-X1.4 (b), AC-015; research.md R9). Opt-in live run; never mocked.

    python tools/agent_only.py --output DIR [--budget-usd 3] [--model MODEL]

The agent is a headless Claude Code session in an empty temporary directory with no
built-in tools (--tools ""), no settings sources, and one MCP server: SIMLAB
(`docker exec -i simlab-runner simlab mcp`). Only mcp__simlab__* tools are allowed.
Grading is independent of the agent: its own tool log must contain only SIMLAB
tools, and the SIMLAB store (read through a separate client, not the agent) must hold
a completed run with two arms that the session created and inspected.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TASK = """You can use only the SIMLAB tools (an MCP server); you have no shell, no files and no web.
Using only those tools, build, run and inspect a two-arm physics experiment:

- Question: how does the swing period of a simple pendulum change between a 0.5 m and a 1.0 m length?
- Author the apparatus yourself as an MJCF model file (a point-mass pendulum on a hinge), with one arm per length,
  a procedure that releases it from a small angle and lets it swing for several periods, a recorded signal for the
  joint angle, and a trial measurement of the period.
- Bind it, validate it, fix any findings, submit it, wait for it, then inspect the result and use query and fetch to look
  at some of the recorded joint-angle data.
- Finish with one short paragraph that names the run_id and the two measured periods. Do not interpret beyond that.
Start by calling capability, and read each tool's description; errors come back as typed {code, message, path}."""


def tool_log(stream: Path) -> list[dict]:
    calls = []
    for line in stream.read_text().splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = ev.get("message") or {}
        for part in msg.get("content") or [] if isinstance(msg.get("content"), list) else []:
            if isinstance(part, dict) and part.get("type") == "tool_use":
                calls.append({"name": part.get("name"), "input_keys": sorted((part.get("input") or {}).keys())})
    return calls


def final_text(stream: Path) -> tuple[str, dict]:
    text, meta = "", {}
    for line in stream.read_text().splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "result":
            text = ev.get("result") or ""
            meta = {k: ev.get(k) for k in ("subtype", "is_error", "num_turns", "duration_ms", "total_cost_usd", "session_id")}
    return text, meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--budget-usd", type=float, default=3.0)
    ap.add_argument("--model")
    ap.add_argument("--timeout-s", type=int, default=1500)
    ap.add_argument("--data-dir", default=os.environ.get("SIMLAB_DATA_DIR", os.path.expanduser("~/simlab-data")))
    a = ap.parse_args(argv)
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    claude = shutil.which("claude")
    if not claude:
        (out / "agent-only.json").write_text(json.dumps({"result": "BLOCKED", "reason": "no claude CLI on PATH"}))
        return 1
    ps = subprocess.run(["docker", "ps", "--filter", "name=^simlab-runner$", "--format", "{{.Names}}"], capture_output=True, text=True).stdout.strip()
    if ps != "simlab-runner":
        (out / "agent-only.json").write_text(json.dumps({"result": "BLOCKED", "reason": "simlab-runner container is not running (tools/runner.py up)"}))
        return 1
    work = Path(tempfile.mkdtemp(prefix="simlab-agent-only-"))
    mcp = {"mcpServers": {"simlab": {"type": "stdio", "command": "docker", "args": ["exec", "-i", "simlab-runner", "simlab", "mcp"]}}}
    (out / "mcp-config.json").write_text(json.dumps(mcp, indent=1))
    def dx(*args, stdin=None):  # the grader's own channel into the runner; the agent never sees it
        r = subprocess.run(["docker", "exec", "-i", "simlab-runner", *args], input=stdin, capture_output=True, text=True, timeout=300)
        return json.loads(r.stdout)

    def runs():
        code = "import json,sqlite3; print(json.dumps([r[0] for r in sqlite3.connect('/data/simlab.sqlite').execute('SELECT run_id FROM runs')]))"
        return set(dx("python", "-c", code))
    before = runs()
    cmd = [claude, "-p", TASK, "--output-format", "stream-json", "--verbose", "--strict-mcp-config", "--mcp-config", str(out / "mcp-config.json"),
           "--tools", "", "--allowedTools", "mcp__simlab__*", "--setting-sources", "", "--no-session-persistence",
           "--max-budget-usd", str(a.budget_usd), *(["--model", a.model] if a.model else [])]
    record = {"record": "simlab-agent-only", "v_id": "V-X1.4 (b)", "ac": "PAS-M1-001/AC-015", "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "cwd": str(work), "command": [c if c != TASK else "<task prompt below>" for c in cmd], "task": TASK,
              "claude_version": subprocess.run([claude, "--version"], capture_output=True, text=True).stdout.strip()}
    t0 = time.monotonic()
    env = {k: v for k, v in os.environ.items() if not k.startswith("SIMLAB_")}
    with (out / "transcript.jsonl").open("w") as fh:
        try:
            p = subprocess.run(cmd, cwd=work, stdout=fh, stderr=subprocess.PIPE, text=True, timeout=a.timeout_s, env=env)
            record["exit_code"], record["stderr_tail"] = p.returncode, p.stderr[-2000:]
        except subprocess.TimeoutExpired:
            record["exit_code"], record["stderr_tail"] = 124, "timeout"
    record["wall_s"] = round(time.monotonic() - t0, 1)
    calls = tool_log(out / "transcript.jsonl")
    text, meta = final_text(out / "transcript.jsonl")
    record.update(tool_calls=calls, final_answer=text, session=meta)
    names = [c["name"] for c in calls]
    non_simlab = [n for n in names if not str(n).startswith("mcp__simlab__")]
    new_runs = sorted(runs() - before)
    inspected = []
    for rid in new_runs:
        res = dx("simlab", "result", "--params", "-", stdin=json.dumps({"run_id": rid}))
        arms = sorted({t["arm_id"] for t in res["trials"]})
        done = [t for t in res["trials"] if t["attempts"] and t["attempts"][-1]["status"] == "COMPLETED"]
        inspected.append({"run_id": rid, "status": res["status"], "arms": arms, "completed_trials": len(done),
                          "measurements": {t["arm_id"]: {m["measurement_id"]: m["value"] for m in t["measurements"]} for t in done},
                          "named_in_answer": rid in text})
    good = [r for r in inspected if r["status"] == "COMPLETED" and len(r["arms"]) >= 2 and r["completed_trials"] >= 2]
    used = set(names)
    checks = {"only_simlab_tools": bool(names) and not non_simlab, "no_builtin_tools_available": True,
              "built_through_authoring_tools": {"mcp__simlab__model_file_put", "mcp__simlab__bind"} <= used,
              "ran_a_two_arm_experiment": bool(good),
              "inspected_result_query_fetch": {"mcp__simlab__result", "mcp__simlab__query", "mcp__simlab__fetch"} <= used,
              "run_named_in_answer": any(r["named_in_answer"] for r in good)}
    record.update(non_simlab_tools=non_simlab, new_runs=inspected, checks=checks,
                  result="PASS" if all(checks.values()) else "FAIL", ended_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    (out / "agent-only.json").write_text(json.dumps(record, indent=1))
    shutil.rmtree(work, ignore_errors=True)
    print(json.dumps({"result": record["result"], "checks": checks, "tool_calls": len(calls), "runs": inspected, "session": meta}, indent=1))
    return 0 if record["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
