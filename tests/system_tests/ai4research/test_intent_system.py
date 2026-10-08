"""Connected slice complete journeys; local real host with explicit model fixtures."""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi import FastAPI

from jiuwenswarm.ai4research.intent.service import IntentService
from jiuwenswarm.ai4research.intent.store import IntentStore
from jiuwenswarm.gateway.channel_manager.web.intent_http import LocalIntentContext, register_intent_routes

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "unit_tests" / "ai4research"
sys.path.insert(0, str(FIXTURE_DIR))
from test_intent_service import FixtureBridge, TEXT  # Frozen explicit fake model, actual gate/store below.


class IntentSystemTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = IntentStore(self.root)
        self.headers = {"Authorization": "Bearer " + "s" * 48, "X-Jiuwen-Intent": "1", "Origin": "http://127.0.0.1:5173"}
        self.context = LocalIntentContext("s" * 48, "owner", "profile", "workspace", self.root)

    def client(self, bridge):
        app = FastAPI()
        service = IntentService(self.store, bridge)
        register_intent_routes(app, service=service, context=self.context)
        return service, httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 65432)),
                                           base_url="http://127.0.0.1:19000", headers=self.headers)

    async def test_submit_disconnect_status_and_durable_accepted_intent(self):
        service, client = self.client(FixtureBridge(delay=0.01))
        async with client:
            reply = await client.post("/api/intent/runs", json={"text": TEXT})
            self.assertEqual(reply.status_code, 202)
            run_id = reply.json()["run_id"]
        # Browser/client connection has ended; server-owned work continues.
        await service.tasks[run_id]
        _, reconnected = self.client(FixtureBridge())
        async with reconnected:
            observed = await reconnected.get(f"/api/intent/runs/{run_id}")
            self.assertEqual(observed.json()["state"], "ACCEPTED")
            self.assertEqual(observed.json()["accepted_intent"]["constraints"][0]["text"], "Do not use network.")

    async def test_semantic_halt_then_linked_correction(self):
        service, client = self.client(FixtureBridge(semantic_status="FAIL"))
        async with client:
            failed_id = (await client.post("/api/intent/runs", json={"text": TEXT})).json()["run_id"]
            await service.tasks[failed_id]
            failed = (await client.get(f"/api/intent/runs/{failed_id}")).json()
            self.assertEqual(failed["state"], "HALTED")
            self.assertIsNone(failed["accepted_reference"])
            self.assertTrue(failed["correction"])
            service.bridge = FixtureBridge()
            new_id = (await client.post("/api/intent/runs", json={"text": TEXT, "corrects_run_id": failed_id})).json()["run_id"]
            await service.tasks[new_id]
            new = (await client.get(f"/api/intent/runs/{new_id}")).json()
            self.assertEqual(new["state"], "ACCEPTED")
            self.assertEqual(new["corrects_run_id"], failed_id)
            self.assertEqual((await client.get(f"/api/intent/runs/{failed_id}")).json()["verdict"], "FAIL")

    async def test_headless_invalid_input_returns_stable_nonzero_without_wait(self):
        command = [sys.executable, "-m", "jiuwenswarm.ai4research.intent.cli", "--state-dir", str(self.root),
                   "--owner", "owner", "--text", " "]
        result = await asyncio.to_thread(subprocess.run, command, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 2)
        completion = json.loads(result.stdout)
        self.assertIsNone(completion["accepted_reference"])
        self.assertIn("EMPTY_INPUT", completion["reasons"])

    async def test_headless_status_reads_identical_durable_reference(self):
        service = IntentService(self.store, FixtureBridge())
        accepted = await service.execute(TEXT, "owner", "profile", "workspace")
        command = [sys.executable, "-m", "jiuwenswarm.ai4research.intent.cli", "--state-dir", str(self.root),
                   "--owner", "owner", "--status", accepted["run_id"]]
        result = await asyncio.to_thread(subprocess.run, command, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["accepted_reference"], accepted["accepted_reference"])


if __name__ == "__main__":
    unittest.main()
