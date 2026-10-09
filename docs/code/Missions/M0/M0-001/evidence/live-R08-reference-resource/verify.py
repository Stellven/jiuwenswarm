"""Frozen resources-only reference-document journey over authenticated real HTTP."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid

import uvicorn

root = Path.cwd()
sys.path.insert(0, str(root / "standalone/intent_compiler"))
sys.path.insert(0, str(root / "standalone/intent_compiler/tools"))
from intent_compiler.api import create_app
from intent_compiler.client import CompilerClient
from intent_compiler.config import Config
from intent_compiler.runtime import Runtime
from intent_compiler.store import Store
from record_candidate import capture
from live_verify import export_available

output = Path(__file__).resolve().parent
input_root = output / "visible-input"
(input_root / "docs").mkdir(parents=True, exist_ok=True)
source_text = "Mandatory project constraints: keep all work local. No cloud training is permitted. No new datasets may be used.\nThe existing document retrieval baseline uses latency and retrieval quality as relevant metrics. No empirical measurements are supplied.\n"
resource_path = input_root / "reference-only.md"
resource_path.write_bytes(source_text.encode("utf-8"))
request = "Investigate ways to reduce latency of the supplied document retrieval baseline while preserving retrieval quality. Return an evidence-grounded research report and follow all mandatory constraints in the supplied reference document."
resource = {"path": "reference-only.md", "role": "reference_document", "required": True, "license": "internal-research"}
config = replace(Config.from_env(), state_dir=output / "state", input_root=input_root, input_directory=None,
                 model_mode="codex", profile_id="compiler-only", auth_token=secrets.token_urlsafe(32))

def write(name, value):
    (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

candidate = capture(output / "candidate.json")
write("frozen-case.json", {"case": "resources-only-reference-document", "request": request, "documents": [], "resources": [resource],
      "source_bytes_sha256": hashlib.sha256(resource_path.read_bytes()).hexdigest(), "source_text": source_text, "expected": "completed",
      "expected_material_constraints": ["local", "cloud", "datasets"], "repetitions": 1, "automatic_retries": 0,
      "basis": "PRD Context 3.1.2: declared reference_document participates in original reasoning context; qualification and provenance same as document input",
      "quality_threshold": None, "limitation": "One labelled actual model sample; no reliability claim"})
write("frozen-configuration.json", config.freeze())
executable = Path(shutil.which(str(config.codex_path)))
write("native-cli-dependency.json", {"executable": str(executable), "sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
      "version": subprocess.check_output([str(executable), "--version"], text=True).strip()})
store = Store(config.state_dir)
runtime = Runtime(config, store)
sock = socket.socket()
sock.bind(("127.0.0.1", 0))
server = uvicorn.Server(uvicorn.Config(create_app(config, store, runtime), log_level="warning"))
thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
thread.start()
deadline = time.monotonic() + 10
while not server.started and time.monotonic() < deadline:
    time.sleep(0.05)
client = CompilerClient("http://127.0.0.1:" + str(sock.getsockname()[1]), config.auth_token, config.account_id, config.workspace_id)
item = {"case": "resources-only-reference-document", "candidate": candidate["candidate"], "expected": "completed", "result": "FAIL"}
run_id = None
began = time.monotonic()
try:
    readiness = client.readiness()
    write("readiness.json", readiness)
    assert readiness["ready"], readiness["prerequisites"]
    status = client.submit(request, client_request_id="reference-resource-" + uuid.uuid4().hex, resources=[resource], documents=[],
                           profile_id=config.profile_id, readiness=readiness)
    run_id = status["run_id"]
    terminal = client.wait(run_id, timeout=config.node_time_s + 30)
    write("status.json", terminal)
    item.update(run_id=run_id, actual=terminal["status"], reasons=terminal["reasons"])
    item["model_calls"] = sum(store.get_json(run_id, a["ref"])["model_calls"] or 0 for a in store.artifacts(run_id) if a["artifact_type"] == "invocation-observation")
    assert terminal["status"] == "completed", terminal["reasons"]
    result = client.result(run_id)
    write("consumer-result.json", result)
    qualification = store.get_run(run_id)["qualified"]
    source_ref = qualification["intake"]["source_refs"][0]
    registration = store.get_json(run_id, qualification["resource_refs"][0])
    assert registration["kind"] == "reference_document" and registration["license"] == "internal-research"
    assert store.read_bytes(run_id, registration["files"][0]["artifact_ref"]) == resource_path.read_bytes()
    assert qualification["sources"][source_ref["id"]]["text"] == source_text
    disclosed = store.get_json(run_id, "intention_Disclosed_Input.json")
    assert disclosed["sources"][source_ref["id"]]["text"] == source_text
    intent = store.get_json(run_id, "Intent_IR.json")
    for term in ("local", "cloud", "datasets"):
        assert any(term in c["text"].lower() and any(span["source_ref"] == source_ref for span in c["source_spans"]) for c in intent["constraints"]), term
        assert any(term in c["text"].lower() and c["origin"] != "system_default" for c in result["research_brief"]["constraints"]), term
    assert item["model_calls"] == 4 and store.accepted(run_id, "node") == result["output_refs"][0]
    assert result["invalid_for_product"] is False
    item.update(result="PASS", source_bytes_verified=True, license_verified=True, protected_source_disclosure_verified=True,
                attributed_constraint_spans_verified=True, brief_constraints_preserved=True, enclosing_node_durably_accepted=True)
except Exception as exc:
    item.update(reason=type(exc).__name__ + ": " + str(exc))
finally:
    export_available(client, run_id, output, item)
    item["elapsed_s"] = time.monotonic() - began
    write("outcome.json", item)
    print(json.dumps(item, ensure_ascii=False), flush=True)
    client.close()
    server.should_exit = True
    thread.join(10)
    sock.close()
sys.exit(0 if item["result"] == "PASS" and item.get("export") == "captured" else 2)
