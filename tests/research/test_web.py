"""Loopback-only contract tests, without any model or external request."""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer
from unittest.mock import Mock, patch
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from jiuwenswarm.research.cli import (
    ClientError, EXIT_CONFIGURATION, EXIT_FAILURE, EXIT_TRANSPORT, ResearchClient, main,
)
from jiuwenswarm.research.web import ResearchHTTPApplication, make_server


class FakeService:
    def __init__(self, state_dir: Path, *, profile: str, **kwargs) -> None:
        self.runs = {}
        self.tasks = []
        self.profile = profile
        self.owner_thread = threading.get_ident()
        self.calls = 0

    def _owner(self):
        if threading.get_ident() != self.owner_thread:
            raise AssertionError("service escaped its owner loop")

    async def readiness(self):
        self._owner()
        return {"ready": True, "profile": self.profile, "product_valid": self.profile != "mock"}

    async def submit(self, text, client_request_id, session_id, mode="web", options=None):
        self._owner()
        if not isinstance(text, str) or not text.strip():
            raise ValueError("empty input")
        if not isinstance(client_request_id, str):
            raise ValueError("missing request identity")
        existing = self.reconcile(client_request_id, session_id)
        if existing:
            return dict(existing)
        run_id = "run-" + str(len(self.runs) + 1)
        run = {"run_id": run_id, "client_request_id": client_request_id,
               "status": "RUNNING", "verdict": None, "session": session_id,
               "accepted_intent": None, "reason": None, "configuration": {"profile": self.profile}}
        self.runs[run_id] = run
        self.calls += 1

        async def finish():
            await asyncio.sleep(0.06)
            if run["status"] == "RUNNING":
                run.update(status="ACCEPTED", verdict="PASS", accepted_intent={"objective": text})

        self.tasks.append(asyncio.create_task(finish()))
        return dict(run)

    def get(self, run_id, session_id):
        self._owner()
        value = self.runs[run_id]
        if value["session"] != session_id:
            raise KeyError("run not found")
        return dict(value)

    def list_runs(self, session_id):
        self._owner()
        return [dict(value) for value in self.runs.values() if value["session"] == session_id]

    def reconcile(self, client_request_id, session_id):
        self._owner()
        return next((dict(value) for value in self.runs.values()
                     if value["client_request_id"] == client_request_id and value["session"] == session_id), None)

    def bundle(self, run_id, session_id):
        self._owner()
        return {"run": self.get(run_id, session_id), "evidence": []}

    async def cancel(self, run_id, session_id):
        self._owner()
        self.get(run_id, session_id)
        self.runs[run_id].update(status="CANCELLED", reason="user cancellation")
        return self.get(run_id, session_id)

    async def close(self):
        self._owner()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)


class WebContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.token = "private-test-credential-" + "x" * 32
        self.app = ResearchHTTPApplication(Path(self.temp.name), token=self.token,
                                           profile="mock", service_factory=FakeService)
        dist = Path(self.temp.name) / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html>existing frontend</html>", encoding="utf-8")
        self.server = make_server(self.app, "127.0.0.1", 0, dist)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_address[1])
        self.client = ResearchClient(self.base, self.token, "test-session")
        self.opener = build_opener(ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.app.close()
        self.temp.cleanup()

    def http(self, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        req = Request(self.base + path, data=data,
                      headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with self.opener.open(req, timeout=2) as response:
                return response.status, dict(response.headers), json.loads(response.read())
        except HTTPError as exc:
            return exc.code, dict(exc.headers), json.loads(exc.read())

    def test_readiness_and_work_are_authenticated(self):
        for path in ["/api/research/readiness", "/api/research/runs", "/api/research/requests/a"]:
            self.assertEqual(self.http(path)[0], 401)
        self.assertTrue(self.client.request("/readiness")["ready"])

    def test_submit_response_ends_but_background_run_survives(self):
        run = self.client.submit("Preserve the scope", "client-a")
        self.assertEqual(run["status"], "RUNNING")
        # No request remains connected during this interval.
        time.sleep(0.12)
        accepted = self.client.request("/runs/" + run["run_id"])
        self.assertEqual(accepted["status"], "ACCEPTED")
        self.assertEqual(accepted["accepted_intent"], {"objective": "Preserve the scope"})
        self.assertEqual(self.client.request("/runs/" + run["run_id"] + "/bundle")["run"], accepted)

    def test_reconciliation_and_duplicate_identity_do_not_repeat_work(self):
        one = self.client.submit("Same input", "same-identity")
        two = self.client.submit("Same input", "same-identity")
        discovered = self.client.request("/requests/same-identity")
        self.assertEqual(one["run_id"], two["run_id"])
        self.assertEqual(one["run_id"], discovered["run_id"])
        self.assertEqual(self.app._service.calls, 1)

    def test_runs_and_bundle_are_session_scoped(self):
        run = self.client.submit("Only mine", "private-a")
        stranger = ResearchClient(self.base, self.token, "other-session")
        self.assertEqual(stranger.request("/runs")["runs"], [])
        for suffix in ["", "/bundle"]:
            with self.assertRaises(ClientError) as raised:
                stranger.request("/runs/" + run["run_id"] + suffix)
            self.assertEqual(raised.exception.payload["http_status"], 404)

    def test_cancel_is_explicit_and_retained(self):
        run = self.client.submit("A cancellable run", "cancel-a")
        cancelled = self.client.request("/runs/" + run["run_id"] + "/cancel", {})
        self.assertEqual(cancelled["status"], "CANCELLED")
        time.sleep(0.1)
        self.assertEqual(self.client.request("/runs/" + run["run_id"])["status"], "CANCELLED")

    def test_browser_login_requires_same_origin_and_httponly_cookie(self):
        self.assertEqual(self.http("/api/research/session", {"token": self.token})[0], 403)
        status, headers, body = self.http("/api/research/session", {"token": self.token}, {"Origin": self.base})
        self.assertEqual(status, 200)
        self.assertNotIn(self.token, json.dumps(body))
        cookie = headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        browser_headers = {"Cookie": cookie.split(";")[0], "Origin": self.base, "X-Research-Session": "spoof"}
        status, _, created = self.http("/api/research/runs", {"text": "browser", "client_request_id": "browser-a"}, browser_headers)
        self.assertEqual(status, 202)
        self.assertEqual(created["session"], "local-browser")
        browser_headers["Origin"] = "http://attacker.invalid"
        self.assertEqual(self.http("/api/research/runs", {}, browser_headers)[0], 403)

    def test_host_rebinding_and_token_url_are_rejected(self):
        headers = {"Authorization": "Bearer " + self.token, "Host": "attacker.invalid"}
        self.assertEqual(self.http("/api/research/readiness", headers=headers)[0], 403)
        self.assertEqual(self.http("/api/research/readiness?token=" + self.token)[0], 403)

    def test_intake_rejects_empty_and_identity_injection(self):
        for body in [
            {"text": " ", "client_request_id": "empty"},
            {"text": "input", "client_request_id": "forged", "product_user_id": "administrator"},
        ]:
            with self.assertRaises(ClientError) as raised:
                self.client.request("/runs", body)
            self.assertEqual(raised.exception.payload["http_status"], 400)
        self.assertEqual(self.app._service.calls, 0)

    def test_headless_smoke_is_sequential_and_mock_labelled(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"AI4RESEARCH_TOKEN": self.token}), contextlib.redirect_stdout(output):
            code = main(["--base", self.base, "--session", "smoke-test", "smoke"])
        self.assertEqual(code, 0)
        record = json.loads(output.getvalue())
        self.assertTrue(record["passed"])
        self.assertIn("wiring only", record["label"])
        self.assertEqual(len(record["cases"]), 3)
        self.assertEqual(self.app._service.calls, 2)

    def test_fallback_ui_and_assets_run_without_a_react_build_or_external_resources(self):
        (Path(self.temp.name) / "dist/index.html").unlink()
        with self.opener.open(self.base + "/research", timeout=2) as response:
            page = response.read().decode()
            self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
            self.assertIn('data-testid="research-panel"', page)
            self.assertNotIn("https://", page)
            self.assertNotIn(self.token, page)
        with self.opener.open(self.base + "/research-assets/local_ui.js", timeout=2) as response:
            script = response.read().decode()
            self.assertIn("textContent", script)
            self.assertNotIn("innerHTML", script)
            self.assertIn("/api/research", script)

    def test_token_file_is_private_and_rejects_a_symlink(self):
        path = self.app.write_token_file()
        self.assertEqual(path.read_text(), self.token)
        if os.name != "nt":
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaises(ValueError):
                self.app.write_token_file()

    def test_colon_request_identity_reconciles_without_contract_drift(self):
        run = self.client.submit("bounded", "campaign:case-1")
        self.assertEqual(self.client.request("/requests/campaign%3Acase-1")["run_id"], run["run_id"])


class HeadlessTransportTests(unittest.TestCase):
    def test_uncertain_submission_queries_identity_once_without_retry(self):
        client = ResearchClient("http://127.0.0.1:5173", "x" * 32)
        expected = {"run_id": "existing-run", "status": "RUNNING"}
        with patch.object(client, "request", side_effect=[ClientError(EXIT_TRANSPORT, {"error": "lost"}), expected]) as request:
            self.assertEqual(client.submit("input", "id"), expected)
        self.assertEqual([call.args[0] for call in request.call_args_list], ["/runs", "/requests/id"])

    def test_unresolved_delivery_has_stable_nonzero_without_prompt(self):
        client = ResearchClient("http://127.0.0.1:5173", "x" * 32)
        with patch.object(client, "request", side_effect=ClientError(EXIT_TRANSPORT, {"error": "lost"})) as request:
            with self.assertRaises(ClientError) as raised:
                client.submit("input", "id")
        self.assertEqual(raised.exception.code, EXIT_TRANSPORT)
        self.assertEqual(request.call_count, 2)

    def test_remote_urls_and_missing_credentials_fail_before_any_request(self):
        for base, token in [("https://example.com", "x" * 32), ("http://127.0.0.1:5173", "")]:
            with self.assertRaises(ClientError) as raised:
                ResearchClient(base, token)
            self.assertEqual(raised.exception.code, EXIT_CONFIGURATION)

    def test_private_container_hostname_requires_explicit_operator_flag(self):
        with self.assertRaises(ClientError):
            ResearchClient("http://workflow:5173", "x" * 32)
        allowed = ResearchClient("http://workflow:5173", "x" * 32, container_workflow_host="workflow")
        self.assertEqual(allowed.base, "http://workflow:5173")
        with self.assertRaises(ClientError):
            ResearchClient("http://attacker.invalid:5173", "x" * 32, container_workflow_host="workflow")

    def test_nonfinite_cli_limits_fail_before_observation_or_submission(self):
        cases = [
            ["--timeout", "nan", "status", "run-1"],
            ["--timeout", "inf", "status", "run-1"],
            ["submit", "--text", "bounded", "--wait", "--deadline", "nan"],
            ["submit", "--text", "bounded", "--wait", "--deadline", "inf"],
            ["submit", "--text", "bounded", "--wait", "--poll", "nan"],
            ["submit", "--text", "bounded", "--wait", "--poll", "inf"],
            ["smoke", "--deadline", "nan"],
            ["smoke", "--deadline", "inf"],
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                output = io.StringIO()
                with patch.dict(os.environ, {"AI4RESEARCH_TOKEN": "x" * 32}), \
                        patch.object(ResearchClient, "request") as request, \
                        contextlib.redirect_stdout(output):
                    code = main(arguments)
                self.assertEqual(code, EXIT_CONFIGURATION)
                self.assertIn("positive_", json.loads(output.getvalue())["error"])
                request.assert_not_called()

    def test_direct_wait_rejects_invalid_limits_without_sleeping_or_polling(self):
        client = ResearchClient("http://127.0.0.1:5173", "x" * 32)
        for deadline, poll in [(float("nan"), 1), (float("inf"), 1), (1, float("inf")),
                               (1, float("nan")), (0, 1), (1, 0), (-1, 1), (1, -1)]:
            with self.subTest(deadline=deadline, poll=poll), \
                    patch.object(client, "request") as request, patch("time.sleep") as sleep:
                with self.assertRaises(ClientError) as raised:
                    client.wait({"status": "RUNNING", "run_id": "bounded"}, deadline, poll)
                self.assertEqual(raised.exception.code, EXIT_CONFIGURATION)
                request.assert_not_called()
                sleep.assert_not_called()

    def test_direct_client_rejects_nonfinite_timeout_before_creating_transport(self):
        for timeout in [float("nan"), float("inf"), float("-inf"), 0, -1]:
            with self.subTest(timeout=timeout), patch("jiuwenswarm.research.cli.build_opener") as opener:
                with self.assertRaises(ClientError) as raised:
                    ResearchClient("http://127.0.0.1:5173", "x" * 32, timeout=timeout)
                self.assertEqual(raised.exception.code, EXIT_CONFIGURATION)
                opener.assert_not_called()

    def test_paused_headless_status_returns_failure_and_machine_readable_output(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"AI4RESEARCH_TOKEN": "x" * 32}), \
                patch.object(ResearchClient, "request", return_value={"status": "PAUSED", "verdict": "INCONCLUSIVE"}), \
                patch("builtins.input", side_effect=AssertionError("headless prompted")), \
                contextlib.redirect_stdout(output):
            code = main(["status", "run-1"])
        self.assertEqual(code, EXIT_FAILURE)
        self.assertEqual(json.loads(output.getvalue())["status"], "PAUSED")

    def test_explicit_invalid_operator_configuration_is_json_and_stable_nonzero(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(output):
            code = main(["serve", "--config", str(Path(temporary) / "missing.yaml")])
        self.assertEqual(code, EXIT_CONFIGURATION)
        self.assertEqual(json.loads(output.getvalue())["error"], "INVALID_CONFIGURATION")


class ConnectedMockHTTPTests(unittest.TestCase):
    def test_service_gate_http_headless_and_restart_preserve_the_same_accepted_artifact(self):
        # No fake service here: the real library, compiler/verifier runner,
        # protected gate and durable store are exercised by the ordinary client.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.dict(os.environ, {"AI4R_ACCOUNT_HOME": str(root / "account")}):
                app = ResearchHTTPApplication(root / "state", profile="mock")
                server = make_server(app, "127.0.0.1", 0, root / "missing-dist")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = "http://127.0.0.1:" + str(server.server_address[1])
                client = ResearchClient(base, app.token, "connected-test")
                try:
                    readiness = client.request("/readiness")
                    self.assertTrue(readiness["ready"])
                    self.assertFalse(readiness["product_valid"])
                    run = client.wait(client.submit("Compare existing methods. Keep the dataset unchanged.", "connected-a"), 10, 0.05)
                    self.assertEqual(run["status"], "ACCEPTED")
                    self.assertEqual(run["verdict"], "PASS")
                    self.assertIsNotNone(run["accepted_ref"])
                    duplicate = client.submit("Compare existing methods. Keep the dataset unchanged.", "connected-a")
                    self.assertEqual(duplicate["run_id"], run["run_id"])
                    bundle = client.request("/runs/" + run["run_id"] + "/bundle")
                    self.assertFalse(bundle["model_backed"])
                    self.assertFalse(bundle["product_valid"])
                    self.assertEqual(bundle["run"]["accepted_ref"], run["accepted_ref"])
                    self.assertEqual([attempt["call_count"] for attempt in run["attempts"]], [1, 1])
                    corrected = client.wait(client.submit("Compare methods with the existing dataset.", "connected-b", {"parent_run_id": run["run_id"]}), 10, 0.05)
                    self.assertNotEqual(corrected["run_id"], run["run_id"])
                    self.assertEqual(corrected["parent_run_id"], run["run_id"])
                    with self.assertRaises(ClientError) as invalid:
                        client.submit(" ", "connected-empty")
                    self.assertEqual(invalid.exception.payload["error"], "EMPTY_INPUT")
                    with self.assertRaises(ClientError) as bypass:
                        client.submit("bounded", "connected-bypass", {"disable_gate": True})
                    self.assertEqual(bypass.exception.payload["http_status"], 400)
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=2)
                    app.close()
                restarted = ResearchHTTPApplication(root / "state", profile="mock")
                try:
                    recovered = restarted.call("get", run["run_id"], "connected-test")
                    self.assertEqual(recovered["status"], "ACCEPTED")
                    self.assertEqual(recovered["accepted_ref"], run["accepted_ref"])
                finally:
                    restarted.close()


class NativeWebCompatibilityTests(unittest.TestCase):
    def test_native_access_log_cannot_capture_rejected_token_urls(self):
        from jiuwenswarm.channels.web.app_web import _SpaStaticHandler

        handler = object.__new__(_SpaStaticHandler)
        handler.path = "/api/research/readiness?token=credential-in-rejected-url"
        handler.logger = Mock()
        handler.log_message("%s", handler.path)
        handler.logger.info.assert_not_called()
        handler.research_application = SimpleNamespace(token="test-credential-value")
        self.assertEqual(handler._redact_desktop_token("test-credential-value"), "[REDACTED]")

    def test_research_routes_precede_proxy_and_existing_static_cache_is_preserved(self):
        from jiuwenswarm.channels.web.app_web import _SpaStaticHandler

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dist = root / "dist"
            (dist / "assets").mkdir(parents=True)
            (dist / "index.html").write_text("<html>existing app</html>", encoding="utf-8")
            (dist / "assets/index-Byh9IHKO.js").write_text("console.log(1)", encoding="utf-8")
            app = ResearchHTTPApplication(root / "state", profile="mock", service_factory=FakeService)

            class Handler(_SpaStaticHandler):
                research_application = app
                api_target = "http://127.0.0.1:9"

                def log_message(self, *args):
                    pass

            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(dist)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "http://127.0.0.1:" + str(server.server_address[1])
            try:
                client = ResearchClient(base, app.token)
                self.assertTrue(client.request("/readiness")["ready"])
                opener = build_opener(ProxyHandler({}))
                with opener.open(base + "/assets/index-Byh9IHKO.js", timeout=2) as response:
                    self.assertEqual(response.read(), b"console.log(1)")
                    self.assertEqual(response.headers["Cache-Control"], "public, max-age=31536000, immutable")
                with opener.open(base + "/research", timeout=2) as response:
                    self.assertEqual(response.read(), b"<html>existing app</html>")
                    self.assertEqual(response.headers["Cache-Control"], "no-cache")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
                app.close()


if __name__ == "__main__":
    unittest.main()
