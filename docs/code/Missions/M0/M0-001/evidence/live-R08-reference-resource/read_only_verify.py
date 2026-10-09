"""Verify the completed R08 result through authenticated reads, without replay."""
from dataclasses import replace
import hashlib
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

base = Path(__file__).resolve().parent
output = base / "read-only-verification"
output.mkdir(exist_ok=True)
original = json.loads((base / "outcome.json").read_text(encoding="utf-8"))
frozen = json.loads((base / "frozen-case.json").read_text(encoding="utf-8"))
run_id = original["run_id"]
config = replace(Config.from_env(), state_dir=base / "state", input_root=base / "visible-input", input_directory=None,
                 model_mode="codex", profile_id="compiler-only", auth_token=secrets.token_urlsafe(32))
store = Store(config.state_dir)

class NoDispatch(Runtime):
    dispatches = 0

    def run(self, run_id):
        self.dispatches += 1
        raise AssertionError("Read-only verification must never dispatch a model")

runtime = NoDispatch(config, store)
before = store.get_run(run_id)
before_refs = [a["ref"] for a in store.artifacts(run_id)]
sock = socket.socket()
sock.bind(("127.0.0.1", 0))
server = uvicorn.Server(uvicorn.Config(create_app(config, store, runtime), log_level="warning"))
thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
thread.start()
deadline = time.monotonic() + 10
while not server.started and time.monotonic() < deadline:
    time.sleep(0.05)
client = CompilerClient("http://127.0.0.1:" + str(sock.getsockname()[1]), config.auth_token, config.account_id, config.workspace_id)
item = {"case": frozen["case"], "candidate": original["candidate"], "run_id": run_id, "result": "FAIL",
        "purpose": "Correct evidence-helper field lookup through ordinary authenticated reads; no replay",
        "original_outcome_path": str((base / "outcome.json").resolve()),
        "original_outcome_sha256": hashlib.sha256((base / "outcome.json").read_bytes()).hexdigest(),
        "original_harness_failure": original["reason"], "new_model_calls": 0}
try:
    terminal = client.status(run_id)
    result = client.result(run_id)
    (output / "status.json").write_text(json.dumps(terminal, indent=2) + "\n", encoding="utf-8")
    (output / "consumer-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    assert terminal["status"] == "completed"
    assert result["ext"]["m0.intent"]["invalid_for_product"] is False
    assert result["ext"]["m0.intent"]["profile_id"] == "compiler-only"
    qualification = store.get_run(run_id)["qualified"]
    source_ref = qualification["intake"]["source_refs"][0]
    registration = store.get_json(run_id, qualification["resource_refs"][0])
    original_bytes = (base / "visible-input/reference-only.md").read_bytes()
    assert hashlib.sha256(original_bytes).hexdigest() == frozen["source_bytes_sha256"]
    assert store.read_bytes(run_id, registration["files"][0]["artifact_ref"]) == original_bytes
    assert registration["kind"] == "reference_document" and registration["license"] == "internal-research"
    assert qualification["sources"][source_ref["id"]]["text"] == frozen["source_text"]
    disclosed = store.get_json(run_id, "intention_Disclosed_Input.json")
    assert disclosed["sources"][source_ref["id"]]["text"] == frozen["source_text"]
    intent = store.get_json(run_id, "Intent_IR.json")
    for term in frozen["expected_material_constraints"]:
        assert any(term in c["text"].lower() and any(s["source_ref"] == source_ref for s in c["source_spans"]) for c in intent["constraints"]), term
        assert any(term in c["text"].lower() and c["origin"] != "system_default" for c in result["research_brief"]["constraints"]), term
    observations = [store.get_json(run_id, a["ref"]) for a in store.artifacts(run_id) if a["artifact_type"] == "invocation-observation"]
    assert sum(o["model_calls"] or 0 for o in observations) == 4
    assert store.accepted(run_id, "node") == result["output_refs"][0]
    assert runtime.dispatches == 0
    assert store.get_run(run_id) == before
    assert [a["ref"] for a in store.artifacts(run_id)] == before_refs
    item.update(result="PASS", actual=terminal["status"], model_calls=4, source_bytes_verified=True, license_verified=True,
                protected_source_disclosure_verified=True, attributed_constraint_spans_verified=True,
                brief_constraints_preserved=True, enclosing_node_durably_accepted=True,
                product_profile_verified=True, no_replay_verified=True,
                node_acceptance_ref=result["node_acceptance_ref"], brief_ref=result["output_refs"][0])
except Exception as exc:
    item["reason"] = type(exc).__name__ + ": " + str(exc)
finally:
    export_available(client, run_id, output, item)
    item["model_dispatches"] = runtime.dispatches
    (output / "outcome.json").write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(item), flush=True)
    client.close()
    server.should_exit = True
    thread.join(10)
    sock.close()
sys.exit(0 if item["result"] == "PASS" and item.get("export") == "captured" else 2)
