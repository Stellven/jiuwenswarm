"""Later authenticated retrieval of the original failed R06 case; no replay."""
from dataclasses import replace
import json
from pathlib import Path
import secrets
import socket
import sys
import threading
import time

import uvicorn

root = Path.cwd()
sys.path.insert(0, str(root / "standalone/intent_compiler"))
sys.path.insert(0, str(root / "standalone/intent_compiler/tools"))
from intent_compiler.api import create_app
from intent_compiler.client import CompilerClient
from intent_compiler.config import Config
from intent_compiler.runtime import Runtime
from intent_compiler.store import Store
from live_verify import export_available

folder = Path(__file__).resolve().parent
campaign = folder.parents[1]
run_id = "5b10a488-59b2-4b0b-beed-c90a7488be9e"
store = Store(folder.parent / "state")
before = store.get_run(run_id)
config = replace(Config.from_env(), state_dir=store.root,
                 input_root=campaign / "visible-input", input_directory=campaign / "visible-input/docs",
                 auth_token=secrets.token_urlsafe(32), account_id=before["account_id"], workspace_id=before["workspace_id"],
                 model_mode="codex", profile_id="compiler-evaluation")

class NoDispatch(Runtime):
    dispatch_calls = 0
    def run(self, run_id):
        self.dispatch_calls += 1
        raise RuntimeError("Read-only recovery must not dispatch or replay any model")

runtime = NoDispatch(config, store)
sock = socket.socket()
sock.bind(("127.0.0.1", 0))
server = uvicorn.Server(uvicorn.Config(create_app(config, store, runtime), log_level="warning"))
thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
thread.start()
deadline = time.monotonic() + 10
while not server.started and time.monotonic() < deadline:
    time.sleep(0.05)
client = CompilerClient("http://127.0.0.1:" + str(sock.getsockname()[1]), config.auth_token, config.account_id, config.workspace_id)
item = {"case": "lost_constraint", "original_campaign_result": "FAIL",
        "original_semantic_challenge": "not_dispatched", "retrieval_only": True, "model_calls": 0}
try:
    status = client.status(run_id)
    export_available(client, run_id, folder, item)
    assert item.get("export") == "captured", item
    after = store.get_run(run_id)
    assert (before["status"], before["stage"], before["reasons"]) == (after["status"], after["stage"], after["reasons"])
    assert runtime.dispatch_calls == 0 and store.accepted(run_id, "node") is None
    item.update(result="PASS", meaning="Available evidence retrieval verified; original failed campaign result unchanged", run_id=run_id,
                original_terminal_status=status["status"], node_accepted=False, model_dispatch_calls=runtime.dispatch_calls)
finally:
    (folder / "outcome.json").write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8")
    client.close()
    server.should_exit = True
    thread.join(10)
    sock.close()
print(json.dumps(item), flush=True)
