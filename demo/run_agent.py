"""Drive a real JiuwenSwarm agent session (Codex as the model) that uses CCs.

    python demo/run_agent.py login                 # once; opens a ChatGPT sign-in URL
    python demo/run_agent.py status
    python demo/run_agent.py run PROMPT_FILE [--name NAME] [--grant EFFECT ...]

The agent is the JiuWenSwarm facade in `codex_subscription` mode with the opt-in
agent profile (workspace-write sandbox, Codex shell/patch tools) plus the CC
catalog MCP server. Every event is written to artifacts/ccv2-demo/sessions/NAME.jsonl
with credentials scrubbed. Nothing here is mocked: no login, no run.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
DATA = Path(os.environ.get("CCV2_DEMO_HOME") or (Path.home() / ".jiuwenswarm-ccv2")).resolve()
WORKSPACE = DATA / "agent-workspace"
DEFAULT_GRANTS = ["process.exec", "network.listen", "network.request", "workspace.read", "workspace.write"]

SCRUB = [
    (re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"), "<jwt>"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{16,}"), r"\1<token>"),
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "<key>"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<email>"),
    (re.compile(r"(?i)(state|code|code_challenge)=[A-Za-z0-9_\-%.~]{12,}"), r"\1=<redacted>"),
]


def scrub(value):
    if isinstance(value, str):
        for pattern, repl in SCRUB:
            value = pattern.sub(repl, value)
        return value
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def toml_str(text: str) -> str:
    return json.dumps(str(text))  # JSON strings are valid TOML basic strings


def configure(grants: list[str]) -> Path:
    """Set the process environment for the agent profile and write the MCP config."""
    DATA.mkdir(parents=True, exist_ok=True)
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    store = DATA / "ccstore"
    args = ["-m", "jiuwenswarm.ccv2.agent_mcp", "--ccs", str(DEMO / "ccs"), "--store", str(store),
            "--workspace", str(WORKSPACE)]
    for grant in grants:
        args += ["--grant", grant]
    forward = ["PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
               "COMSPEC", "PATHEXT", "HOME", "DOCKER_HOST", "DOCKER_CONTEXT"]
    mcp = DATA / "agent-mcp.toml"
    mcp.write_text(
        "[mcp_servers.cc]\n"
        f"command = {toml_str(sys.executable)}\n"
        f"args = [{', '.join(toml_str(a) for a in args)}]\n"
        f"env_vars = [{', '.join(toml_str(v) for v in forward)}]\n"
        "startup_timeout_sec = 60\ntool_timeout_sec = 300\n"
        f"[mcp_servers.cc.env]\nPYTHONPATH = {toml_str(str(ROOT))}\n",
        encoding="utf-8")
    os.environ.update({
        "JIUWENSWARM_DATA_DIR": str(DATA),
        "JIUWENSWARM_AGENT_SDK": "codex_subscription",
        "JIUWENSWARM_CODEX_AGENT": "1",
        "JIUWENSWARM_CODEX_AGENT_MCP": str(mcp),
        "JIUWENSWARM_CODEX_AGENT_CWD": str(WORKSPACE),
        "JIUWENSWARM_SKIP_DOTENV": "1",
        "PYTHONPATH": str(ROOT),
    })
    return mcp


async def cmd_status(_a):
    configure(DEFAULT_GRANTS)
    from jiuwenswarm.server.runtime.codex_subscription.service import get_service
    service = get_service()
    print(json.dumps(scrub(await service.status()), indent=2))
    await service.transport.close()


async def cmd_login(_a):
    configure(DEFAULT_GRANTS)
    from jiuwenswarm.server.runtime.codex_subscription.service import get_service
    service = get_service()
    started = await service.login()
    print("Open this URL in a browser and sign in with the ChatGPT account to use:\n", started["auth_url"], flush=True)
    for _ in range(180):
        await asyncio.sleep(2)
        status = await service.status()
        if status.get("state") not in {"signing_in", "signed_out"}:
            print(json.dumps(scrub(status), indent=2))
            break
    else:
        print("Timed out waiting for sign-in.")
    await service.transport.close()


async def cmd_run(a):
    configure(a.grant or DEFAULT_GRANTS)
    from jiuwenswarm.common.schema.agent import AgentRequest
    from jiuwenswarm.common.schema.message import ReqMethod
    from jiuwenswarm.server.runtime.agent_adapter.interface import JiuWenSwarm
    from jiuwenswarm.server.runtime.codex_subscription.service import get_service

    prompt = Path(a.prompt_file).read_text(encoding="utf-8")
    log = ROOT / "artifacts" / "ccv2-demo" / "sessions" / f"{a.name}.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    facade = JiuWenSwarm()
    facade._sdk_name = "codex_subscription"
    request = AgentRequest(request_id=f"{a.name}-{int(time.time())}", channel_id="web", session_id=a.name,
                           req_method=ReqMethod.CHAT_SEND, params={"query": prompt, "mode": "agent.work.normal"})
    final, counts = "", {}
    with log.open("w", encoding="utf-8") as out:
        out.write(json.dumps({"event": "session.start", "prompt": scrub(prompt), "workspace": str(WORKSPACE),
                              "t": time.time()}) + "\n")
        async for chunk in facade.process_message_stream(request):
            payload = chunk.payload if isinstance(chunk.payload, dict) else {"raw": str(chunk.payload)}
            kind = payload.get("event_type", "?")
            counts[kind] = counts.get(kind, 0) + 1
            out.write(json.dumps({"t": time.time(), **scrub(payload)}, ensure_ascii=False, default=str) + "\n")
            if kind == "chat.final":
                final = payload.get("content", "")
            if kind in {"chat.tool_call"}:
                print("  tool>", payload["tool_call"]["name"], json.dumps(scrub(payload["tool_call"]["arguments"]))[:160], flush=True)
            if kind == "chat.error":
                print("ERROR:", payload, flush=True)
    await get_service().transport.close()
    print("\n=== final ===\n" + scrub(final))
    print("\nevents:", counts, "\nlog:", log)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login").set_defaults(fn=cmd_login)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    r = sub.add_parser("run")
    r.add_argument("prompt_file")
    r.add_argument("--name", default="session")
    r.add_argument("--grant", action="append")
    r.set_defaults(fn=cmd_run)
    a = p.parse_args()
    asyncio.run(a.fn(a))


if __name__ == "__main__":
    main()
