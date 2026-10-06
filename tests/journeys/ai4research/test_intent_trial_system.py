"""Actual local HTTP/CLI journeys with an explicit scripted mock model.

These tests exercise ordinary clients and durable wiring only. They do not
establish live-provider fidelity, native browser visual readiness or full M1.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile

import pytest
import uvicorn
from fastapi import FastAPI

from jiuwenswarm.ai4research.common import hash_json, sha256_bytes
from jiuwenswarm.ai4research.headless import run_client
from jiuwenswarm.ai4research.http import trial_router
from tests.fixtures.ai4research.trial_support import OBJECTIVE, make_trial


@pytest.fixture
def live_trial(tmp_path):
    trial = make_trial(tmp_path)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(16)
    port = listener.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    http = FastAPI()
    http.include_router(trial_router(trial.application, expected_origin=base))
    config = uvicorn.Config(http, host="127.0.0.1", port=port, log_level="error",
                            access_log=False, proxy_headers=False, lifespan="off")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started, "Actual local fixture service failed to start"
    try:
        yield trial, base
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        assert not thread.is_alive(), "Fixture service did not stop"


def authenticated_get(base, token, path):
    request = urllib.request.Request(base + "/api/intent-trial" + path,
                                     headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.read(), response.headers.get_content_type()


def test_actual_loopback_headless_accept_and_refuse_are_sequential(live_trial):
    trial, base = live_trial
    code, accepted = run_client(base=base, token=trial.token, text=OBJECTIVE,
                                request_id="sequential-1", timeout_seconds=5)
    assert code == 0 and accepted["status"] == "ACCEPTED" and accepted["mock"] is True
    assert len(trial.bridge.calls) == 2
    trial.bridge.failed_check = "F2"
    code, refused = run_client(base=base, token=trial.token, text="Different objective with a scripted unsupported addition.",
                               request_id="sequential-2", timeout_seconds=5)
    assert code == 2 and refused["status"] == "FAILED" and refused["accepted_ref"] is None
    assert refused["attention"] and refused["attention"][0]["mode"] == "headless"
    assert len(trial.bridge.calls) == 4
    assert [call["role"] for call in trial.bridge.calls] == ["compiler", "verifier", "compiler", "verifier"]
    payload, media = authenticated_get(base, trial.token, "/runs")
    assert media == "application/json"
    runs = json.loads(payload)
    assert [run["run_id"] for run in runs] == [accepted["run_id"], refused["run_id"]]
    assert all("full stages/M1 incomplete" in run["scope"] for run in runs)


def test_actual_headless_cli_process_is_noninteractive_and_does_not_own_gate(live_trial, tmp_path):
    trial, base = live_trial
    token_path = tmp_path / "client-session.txt"
    input_path = tmp_path / "objective.txt"
    token_path.write_text(trial.token, encoding="utf-8")
    input_path.write_text(OBJECTIVE, encoding="utf-8")
    command = [sys.executable, "-m", "jiuwenswarm.ai4research.headless", "--base", base,
               "--token-file", str(token_path), "--text-file", str(input_path), "--request-id", "cli-1"]
    process = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              encoding="utf-8", timeout=15)
    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    assert result["status"] == "ACCEPTED" and result["mock"] is True
    assert trial.token not in process.stdout + process.stderr
    assert len(trial.bridge.calls) == 2
    trial.bridge.inconclusive_check = "F4"
    refused = subprocess.run([*command[:-1], "cli-2"], stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert refused.returncode == 2
    result = json.loads(refused.stdout)
    assert result["status"] == "INCONCLUSIVE" and result["accepted_ref"] is None
    assert trial.token not in refused.stdout + refused.stderr
    assert len(trial.bridge.calls) == 4


def test_actual_http_bundle_hashes_exact_outputs_and_retains_mock_limit(live_trial):
    trial, base = live_trial
    code, run = run_client(base=base, token=trial.token, text=OBJECTIVE,
                           request_id="portable", timeout_seconds=5)
    assert code == 0
    payload, media = authenticated_get(base, trial.token, f"/runs/{run['run_id']}/bundle")
    assert media == "application/zip"
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        exported = json.loads(archive.read("manifest.json"))
        assert exported["manifest_sha256"] == hash_json(exported["manifest"])
        manifest = exported["manifest"]
        assert manifest["accepted_ref"] == run["accepted_ref"] and manifest["configuration"]["effective"]["mock"] is True
        assert manifest["pins"]["compiler"]["admission_scope"] == "fixture-only"
        for member in manifest["members"]:
            ref = member["reference"]
            raw = archive.read(ref["artifact_id"] + ".bin")
            assert len(raw) == member["size_bytes"] and sha256_bytes(raw) == ref["sha256"]
            assert trial.token.encode("utf-8") not in raw
        assert all(attempt["evidence"]["usage"]["cost"] is None for attempt in manifest["attempts"])


def test_actual_unauthenticated_headless_refusal_dispatches_nothing(live_trial):
    trial, base = live_trial
    code, refused = run_client(base=base, token="invalid", text=OBJECTIVE,
                               request_id="denied", timeout_seconds=5)
    assert code == 3 and refused["code"] == "submission_rejected"
    assert trial.bridge.calls == []
    assert trial.application.store.list_runs(caller_id=trial.context.user_id) == []


def test_client_endpoint_validation_cannot_select_an_alternate_provider(live_trial):
    trial, _ = live_trial
    for base in ("https://127.0.0.1:4311", "http://unrelated.example:4311", "http://127.0.0.1:4311/alternate"):
        code, result = run_client(base=base, token=trial.token, text=OBJECTIVE, request_id="wrong-route")
        assert code == 3 and result["code"] == "invalid_endpoint"
    assert trial.bridge.calls == []
