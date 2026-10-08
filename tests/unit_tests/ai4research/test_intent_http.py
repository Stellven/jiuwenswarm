"""M1-INTENT/V05: real HTTP/local lifecycle with bounded model fixtures."""
import asyncio
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from jiuwenswarm.ai4research.intent.models import InvocationEvidence, sha256_text
from jiuwenswarm.ai4research.intent.service import IntentService
from jiuwenswarm.ai4research.intent.store import IntentStore
from jiuwenswarm.gateway.channel_manager.web.intent_http import LocalIntentContext, register_intent_routes
from tests.unit_tests.ai4research.test_intent_gate import ORIGINAL, candidate_fixture, assessment_fixture


class ModelFixture:
    def __init__(self):
        self.malformed = False
        self.hold = False
        self.calls = []
        self.raw = ""

    async def invoke(self, role, prompt, run_id, policy):
        self.calls.append(role)
        if self.hold:
            await asyncio.Event().wait()
        if role == "compiler":
            payload = candidate_fixture()
            payload["run_id"] = run_id
            self.raw = "{" if self.malformed else json.dumps(payload)
            raw = self.raw
        else:
            payload = assessment_fixture(self.raw)
            payload["run_id"] = run_id
            raw = json.dumps(payload)
        return InvocationEvidence(invocation_id=role + run_id, role=role, run_id=run_id,
                                  conversation_id=role + run_id, prompt_sha256=sha256_text(prompt),
                                  status="completed", elapsed_seconds=0.01, raw_output=raw)


class IntentHttpTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bridge = ModelFixture()
        self.service = IntentService(IntentStore(self.root), self.bridge)
        self.context = LocalIntentContext("random-fixture-credential-0123456789", "owner", "profile", "workspace", self.root)
        self.app = FastAPI()
        register_intent_routes(self.app, service=self.service, context=self.context)

    async def asyncTearDown(self):
        for task in list(self.service.tasks.values()):
            task.cancel()
            await task
        self.tmp.cleanup()

    def client(self, *, peer="127.0.0.1", headers=None):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=(peer, 1234)),
                                 base_url="http://127.0.0.1:19000", headers=headers or {
                                     "Authorization": "Bearer " + self.context.token, "X-Jiuwen-Intent": "1"})

    async def wait(self, client, run_id):
        for _ in range(100):
            result = await client.get(f"/api/intent/runs/{run_id}")
            if result.json().get("state") in {"ACCEPTED", "HALTED", "PAUSED"}:
                return result.json()
            await asyncio.sleep(0.001)
        self.fail("Run did not terminate")

    async def test_authenticated_actual_http_submit_inspect_and_reconnect(self):
        async with self.client() as client:
            submitted = await client.post("/api/intent/runs", json={"text": ORIGINAL})
            self.assertEqual(submitted.status_code, 202)
            run_id = submitted.json()["run_id"]
        # Reconnecting does not own or cancel the accepted server task.
        async with self.client() as reconnected:
            result = await self.wait(reconnected, run_id)
        self.assertEqual(result["state"], "ACCEPTED")
        self.assertIsNotNone(result["accepted_reference"])
        self.assertTrue(result["durable"])
        self.assertEqual(self.bridge.calls, ["compiler", "verifier"])

    async def test_missing_auth_nonloopback_origin_and_request_identity_are_denied(self):
        for options, headers, expected in (
            ({}, {"X-Jiuwen-Intent": "1"}, 401),
            ({"peer": "192.0.2.1"}, None, 403),
            ({}, {"Authorization": "Bearer " + self.context.token, "X-Jiuwen-Intent": "1", "Origin": "https://evil.invalid"}, 403),
            ({}, {"Authorization": "Bearer " + self.context.token}, 403),
        ):
            async with self.client(headers=headers, **options) as client:
                self.assertEqual((await client.post("/api/intent/runs", json={"text": ORIGINAL})).status_code, expected)
        async with self.client() as client:
            self.assertEqual((await client.post("/api/intent/runs", json={"text": ORIGINAL, "owner_id": "attacker"})).status_code, 422)
        self.assertFalse(self.bridge.calls)

    async def test_unauthorized_malformed_body_is_rejected_before_parsing(self):
        async with self.client(headers={"X-Jiuwen-Intent": "1"}) as client:
            response = await client.post("/api/intent/runs", content="{", headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 401)
        self.assertFalse(self.bridge.calls)

    async def test_active_run_busy_is_stable_409(self):
        self.bridge.hold = True
        async with self.client() as client:
            first = await client.post("/api/intent/runs", json={"text": ORIGINAL})
            second = await client.post("/api/intent/runs", json={"text": ORIGINAL})
            self.assertEqual(second.status_code, 409)
            self.assertEqual(second.json()["code"], "RUNTIME_BUSY")
            await client.post(f"/api/intent/runs/{first.json()['run_id']}/cancel")

    async def test_storage_initialization_errors_are_stable_503_without_model_call(self):
        for failure in (OSError("fixture unavailable storage"), sqlite3.OperationalError("fixture unreadable SQLite")):
            with self.subTest(error=type(failure).__name__):
                app = FastAPI()
                register_intent_routes(app, context=self.context)
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:19000",
                                             headers={"Authorization": "Bearer " + self.context.token, "X-Jiuwen-Intent": "1"}) as client:
                    with patch("jiuwenswarm.ai4research.intent.store.IntentStore", side_effect=failure):
                        response = await client.post("/api/intent/runs", json={"text": ORIGINAL})
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["code"], "INTENT_STORAGE_UNAVAILABLE")
                self.assertNotIn(str(failure), response.text)
        app = FastAPI()
        register_intent_routes(app)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:19000") as client:
            with patch.object(LocalIntentContext, "configured", side_effect=sqlite3.OperationalError("fixture profile SQLite")):
                response = await client.post("/api/intent/runs", json={"text": ORIGINAL})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "INTENT_STORAGE_UNAVAILABLE")
        self.assertFalse(self.bridge.calls)

    async def test_cookie_native_origin_and_wrong_owner_scope(self):
        headers = {"X-Jiuwen-Intent": "1", "Origin": "http://127.0.0.1:5173",
                   "Cookie": f"{self.context.cookie_name}={self.context.token}"}
        async with self.client(headers=headers) as client:
            submitted = await client.post("/api/intent/runs", json={"text": ORIGINAL})
            self.assertEqual(submitted.status_code, 202)
            run_id = submitted.json()["run_id"]
            await self.wait(client, run_id)
        other_app = FastAPI()
        other = LocalIntentContext(self.context.token, "another-owner", "profile", "workspace", self.root)
        register_intent_routes(other_app, service=self.service, context=other)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=other_app), base_url="http://127.0.0.1:19000", headers={"Authorization": "Bearer " + self.context.token, "X-Jiuwen-Intent": "1"}) as client:
            self.assertEqual((await client.get(f"/api/intent/runs/{run_id}")).status_code, 404)

    async def test_halt_correction_and_cancellation_never_override_old_run(self):
        self.bridge.malformed = True
        async with self.client() as client:
            old = (await client.post("/api/intent/runs", json={"text": ORIGINAL})).json()["run_id"]
            failed = await self.wait(client, old)
            self.assertEqual(failed["state"], "HALTED")
            self.assertIsNone(failed["accepted_reference"])
            self.assertEqual(self.bridge.calls, ["compiler"])
            self.bridge.malformed = False
            new = (await client.post("/api/intent/runs", json={"text": ORIGINAL, "corrects_run_id": old})).json()["run_id"]
            self.assertEqual((await self.wait(client, new))["state"], "ACCEPTED")
            self.assertEqual((await client.get(f"/api/intent/runs/{old}")).json()["state"], "HALTED")
            self.bridge.hold = True
            cancelled = (await client.post("/api/intent/runs", json={"text": ORIGINAL})).json()["run_id"]
            result = await client.post(f"/api/intent/runs/{cancelled}/cancel")
            self.assertEqual(result.json()["state"], "HALTED")
            self.assertIsNone(result.json()["accepted_reference"])


if __name__ == "__main__":
    unittest.main()
