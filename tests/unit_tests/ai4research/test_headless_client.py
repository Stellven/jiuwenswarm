"""Actual loopback HTTP client probes, explicitly scripted server responses."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from jiuwenswarm.ai4research.headless import run_client


@pytest.fixture
def server():
    observed = {"posts": 0, "gets": [], "status": "FAILED", "drop_response": False,
                "post_status": 200, "get_status": 200, "redirect": None}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def response(self, status=200):
            result = {"run_id": "fixture-run", "status": observed["status"],
                      "bundle_url": "/fixture-bundle", "accepted_ref": None}
            payload = json.dumps(result).encode()
            self.send_response(status)
            if observed["redirect"]:
                self.send_header("Location", observed["redirect"])
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            assert self.headers["Authorization"] == "Bearer fixture-token"
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert body["options"]["mode"] == "headless"
            observed["posts"] += 1
            if observed["drop_response"]:
                self.connection.close()
                return
            self.response(observed["post_status"])

        def do_GET(self):
            assert self.headers["Authorization"] == "Bearer fixture-token"
            observed["gets"].append(self.path)
            self.response(observed["get_status"])
    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{http.server_port}", observed
    finally:
        http.shutdown()
        http.server_close()
        worker.join(timeout=2)


def test_m0_trial_1_b09_headless_halt_returns_nonzero_and_never_prompts(server, monkeypatch):
    def trap(*args):
        raise AssertionError("Headless must not prompt")
    monkeypatch.setattr("builtins.input", trap)
    base, observed = server
    code, result = run_client(base=base, token="fixture-token", text="Compare batteries", request_id="request-1")
    assert code == 2 and result["status"] == "FAILED"
    assert result["run_id"] and result["bundle_url"]
    assert observed["posts"] == 1


def test_m0_trial_1_b10_uncertain_submit_retrieves_identity_without_resubmission(server):
    base, observed = server
    observed["drop_response"] = True
    code, result = run_client(base=base, token="fixture-token", text="Compare batteries", request_id="request-1")
    assert code == 2 and result["run_id"] == "fixture-run"
    assert observed["posts"] == 1
    assert observed["gets"] == ["/api/intent-trial/requests/request-1"]


def test_m0_trial_1_b09_foreign_endpoint_never_receives_token():
    code, result = run_client(base="http://example.com", token="fixture-canary", text="x", request_id="r")
    assert code == 3 and result["code"] == "invalid_endpoint"


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_m0_trial_1_b10_committed_server_error_reconciles_same_identity_without_post_replay(server, status):
    base, observed = server
    observed["post_status"] = status
    code, result = run_client(base=base, token="fixture-token", text="Compare batteries", request_id="request/with space")
    assert code == 2 and result["run_id"] == "fixture-run" and result["status"] == "FAILED"
    assert observed["posts"] == 1
    assert observed["gets"] == ["/api/intent-trial/requests/request%2Fwith%20space"]


def test_m0_trial_1_b10_server_error_without_reconciled_run_stays_unknown_without_resubmission(server):
    base, observed = server
    observed.update(post_status=503, get_status=404)
    code, result = run_client(base=base, token="fixture-token", text="Compare batteries", request_id="unknown")
    assert code == 3 and result["code"] == "client_unavailable"
    assert "may be unknown" in result["message"] and result["client_request_id"] == "unknown"
    assert observed["posts"] == 1 and observed["gets"] == ["/api/intent-trial/requests/unknown"]


@pytest.mark.parametrize("status", [400, 401, 403, 409, 422])
def test_m0_trial_1_b09_confirmed_intake_rejection_never_retries_or_reconciles(server, status):
    base, observed = server
    observed["post_status"] = status
    code, result = run_client(base=base, token="fixture-token", text="Compare batteries", request_id="rejected")
    assert code == 3 and result["code"] == "submission_rejected" and result["http_status"] == status
    assert observed["posts"] == 1 and observed["gets"] == []


@pytest.mark.parametrize("status", [302, 307])
def test_m0_trial_1_b09_redirect_cannot_forward_credential_or_replay_post(server, status):
    base, origin = server
    observed = {"requests": 0, "authorization": []}
    class Receiver(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def receive(self):
            observed["requests"] += 1
            observed["authorization"].append(self.headers.get("Authorization"))
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
        do_POST = receive
        do_GET = receive
    target = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    worker = threading.Thread(target=target.serve_forever, daemon=True)
    worker.start()
    try:
        origin.update(post_status=status, redirect=f"http://127.0.0.1:{target.server_port}/foreign-audience")
        code, result = run_client(base=base, token="fixture-token", text="Compare batteries", request_id="redirected")
        assert code == 3 and result["code"] == "redirect_denied" and result["http_status"] == status
        assert origin["posts"] == 1 and origin["gets"] == []
        assert observed["requests"] == 0 and observed["authorization"] == []
    finally:
        target.shutdown()
        target.server_close()
        worker.join(timeout=2)
        assert not worker.is_alive()
