"""Real Gateway/AgentServer sockets with a fake provider in a fresh test profile.

No production fake-login flag is installed. The fixture is injected only in this
script's AgentServer child. It cannot establish real subscription acceptance.
"""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def agent_child():
    from tests.unit_tests.runtime.test_codex_subscription import FakeTransport
    from jiuwenswarm.server.runtime.codex_subscription import service

    class JourneyTransport(FakeTransport):
        def __init__(self, root):
            super().__init__()
            self.account = None
            self.turns = {}

        async def request(self, method, params=None):
            params = params or {}
            if method == "account/login/start":
                result = await super().request(method, params)
                self.account = {"type": "chatgpt", "email": "fixture@example.invalid", "planType": "plus"}
                asyncio.get_running_loop().call_later(0.1, self.emit, "account/login/completed", {"loginId": result["loginId"], "success": True})
                return result
            if method == "turn/start":
                self.hold_turn = "STOP" in params["input"][0]["text"]
                result = await super().request(method, params)
                self.turns[params["threadId"]] = result["turn"]["id"]
                return result
            if method == "turn/interrupt":
                self.emit("turn/completed", {"threadId": params["threadId"], "turn": {"id": params["turnId"], "status": "interrupted"}})
                return {}
            return await super().request(method, params)

    service.AppServerTransport = JourneyTransport
    from jiuwenswarm.server.app_agentserver import _run
    asyncio.run(_run("127.0.0.1", int(os.environ["AGENT_SERVER_PORT"])))


async def journey(port):
    import websockets
    url = f"ws://127.0.0.1:{port}/ws"
    events = []
    sequence = 0

    async def receive(ws, predicate):
        async with asyncio.timeout(35):
            while True:
                frame = json.loads(await ws.recv())
                events.append(frame)
                if predicate(frame):
                    return frame

    async def rpc(ws, method, params=None):
        nonlocal sequence
        sequence += 1
        rid = f"journey-{sequence}"
        await ws.send(json.dumps({"type": "req", "id": rid, "method": method, "params": params or {}}))
        frame = await receive(ws, lambda f: f.get("id") == rid)
        assert frame.get("ok"), (method, frame.get("error"), frame.get("code"))
        return rid, frame.get("payload") or {}

    async with websockets.connect(url, proxy=None) as ws:
        _, status = await rpc(ws, "codex.auth.status")
        assert status["state"] == "signed_out"
        await rpc(ws, "codex.auth.login")
        _, status = await rpc(ws, "codex.auth.status")
        assert status["state"] == "ready"
        _, catalog = await rpc(ws, "codex.models.list")
        assert catalog["models"]
        _, created = await rpc(ws, "session.create", {"session_id": "sess_journey", "mode": "agent", "work_mode": "work"})
        sid = created.get("session_id") or "sess_journey"
        rid, _ = await rpc(ws, "chat.send", {"session_id": sid, "content": "Hello fixture", "mode": "agent.work.normal", "skills": []})
        final = await receive(ws, lambda f: f.get("event") in {"chat.final", "chat.error"})
        assert final.get("event") == "chat.final", final
        assert final["payload"].get("content") == "Hello", final
        assert any(f.get("event") == "chat.delta" for f in events)
        rid, _ = await rpc(ws, "chat.send", {"session_id": sid, "content": "STOP fixture", "mode": "agent.work.normal", "skills": []})
        await receive(ws, lambda f: f.get("event") in {"chat.delta", "chat.error"})
        await rpc(ws, "chat.interrupt", {"session_id": sid, "intent": "cancel", "target_request_id": "stale"})
        rejected = await receive(ws, lambda f: f.get("event") == "chat.interrupt_result")
        assert rejected["payload"].get("success") is False, rejected
        await rpc(ws, "chat.interrupt", {"session_id": sid, "intent": "cancel", "target_request_id": rid})
        stopped = await receive(ws, lambda f: f.get("event") == "chat.interrupt_result")
        assert stopped["payload"].get("success") is True, stopped
        await rpc(ws, "chat.send", {"session_id": sid, "content": "After cancellation", "mode": "agent.work.normal", "skills": []})
        continued = await receive(ws, lambda f: f.get("event") in {"chat.final", "chat.error"})
        assert continued.get("event") == "chat.final", continued
    # Fresh connection models page refresh; history must come from the server.
    async with websockets.connect(url, proxy=None) as ws:
        start = len(events)
        _, history = await rpc(ws, "history.get", {"session_id": sid, "cursor": None, "limit": 50})
        if history.get("accepted"):
            await receive(ws, lambda f: f.get("event") == "history.message" and (f.get("payload") or {}).get("status") in {"done", "error"})
            history = [f.get("payload") for f in events[start:] if f.get("event") == "history.message"]
        text = json.dumps(history)
        assert "Hello fixture" in text and "Hello" in text, history
        assert "STOP fixture" in text, history
        assert "After cancellation" in text, history
        _, status = await rpc(ws, "codex.auth.status")
        assert status["state"] == "ready"
    return {"provider": "fake", "real_gateway_and_agentserver": True, "login_chat_cancel_reconnect_history": True, "session_id": sid}


def main():
    evidence = Path(os.environ["LOCALAPPDATA"]) / "ai4r-tools/evidence/AI4R-001"
    run = Path(tempfile.mkdtemp(prefix="m1-wire-", dir=evidence))
    os.environ["JIUWENSWARM_DATA_DIR"] = str(run / "profile")
    os.environ["JIUWENSWARM_AGENT_SDK"] = "codex_subscription"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    from jiuwenswarm.common.utils import prepare_workspace
    prepare_workspace(overwrite=False, workspace_dir=run / "profile")
    ports = []
    for _ in range(3):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            ports.append(sock.getsockname()[1])
    env = os.environ.copy()
    for key, port in zip(("AGENT_SERVER_PORT", "WEB_PORT", "GATEWAY_PORT"), ports):
        env[key] = str(port)
    env["AGENT_SERVER_HOST"] = env["WEB_HOST"] = env["GATEWAY_HOST"] = "127.0.0.1"
    # The ordinary loader uses override=True; give the test its own explicit file.
    dotenv = run / "profile/config/.env"
    with dotenv.open("a", encoding="utf-8") as f:
        for key in ("AGENT_SERVER_PORT", "WEB_PORT", "GATEWAY_PORT", "AGENT_SERVER_HOST", "WEB_HOST", "GATEWAY_HOST", "JIUWENSWARM_AGENT_SDK"):
            f.write(f"\n{key}={env[key]}\n")
    commands = [[sys.executable, str(Path(__file__).resolve()), "--agent"], [sys.executable, "-m", "jiuwenswarm.gateway.app_gateway"]]
    processes = []
    logs = []
    try:
        for name, command in zip(("agent", "gateway"), commands):
            log = (run / f"{name}.log").open("w", encoding="utf-8")
            logs.append(log)
            processes.append(subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if any(p.poll() is not None for p in processes):
                raise RuntimeError(f"Fixture process exited; evidence: {run}")
            try:
                with socket.create_connection(("127.0.0.1", ports[1]), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.25)
        result = asyncio.run(journey(ports[1]))
        (run / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"passed": True, "evidence": str(run), **result}))
    finally:
        for process in processes:
            # psutil includes Windows venv launcher children; only owned descendants.
            import psutil
            try:
                descendants = psutil.Process(process.pid).children(recursive=True)
                for child in reversed(descendants):
                    child.terminate()
                process.terminate()
                process.wait(timeout=10)
            except (psutil.NoSuchProcess, ProcessLookupError):
                pass
        for log in logs:
            log.close()
        print(f"Fixture evidence retained: {run}")


if __name__ == "__main__":
    if "--agent" in sys.argv:
        sys.argv = [sys.argv[0]]
        agent_child()
    else:
        main()
