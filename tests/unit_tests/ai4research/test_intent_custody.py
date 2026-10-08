"""Regression checks at the real SQLite/artifact release boundary, M1-INTENT/V02."""
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from jiuwenswarm.ai4research.intent.models import Claim, GateDecision, IntentCandidate
from jiuwenswarm.ai4research.intent.service import IntentService
from jiuwenswarm.ai4research.intent.store import IntentStore, StoreError
from tests.unit_tests.ai4research.test_intent_service import FixtureBridge, TEXT


class IntentCustodyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = IntentStore(Path(self.directory.name))

    async def stage_candidate(self):
        # Use the real host pipeline to capture every required artifact, holding
        # only the final commit. Change the release subject after review.
        service = IntentService(self.store, FixtureBridge())
        with patch.object(self.store, "complete", return_value=None):
            result = await service.execute(TEXT, "owner", "profile", "workspace")
        run_id = result["run_id"]
        candidate = IntentCandidate.model_validate_json(
            (self.store.artifact_root / run_id / "candidate.raw.json").read_bytes())
        return run_id, candidate

    async def test_release_rejects_candidate_different_from_reviewed_raw_bytes(self):
        run_id, candidate = await self.stage_candidate()
        changed = candidate.model_copy(update={"objective": Claim(text="Unrelated objective",
                                                                   source_quote=candidate.objective.source_quote)})
        decision = GateDecision(verdict="PASS", tier1=True, tier2=True)
        with self.assertRaisesRegex(StoreError, "RELEASE_SUBJECT_MISMATCH"):
            self.store.complete(run_id, decision, changed)
        observed = self.store.read(run_id, "owner")
        self.assertNotEqual(observed["state"], "ACCEPTED")
        self.assertIsNone(observed["accepted_reference"])

    async def test_release_rejects_wrong_run_and_original_bindings(self):
        for changes in ({"run_id": uuid.uuid4().hex}, {"input_sha256": "0" * 64}):
            with self.subTest(changes=changes):
                run_id, candidate = await self.stage_candidate()
                decision = GateDecision(verdict="PASS", tier1=True, tier2=True)
                with self.assertRaisesRegex(StoreError, "RELEASE_SUBJECT_MISMATCH"):
                    self.store.complete(run_id, decision, candidate.model_copy(update=changes))
                self.assertIsNone(self.store.read(run_id, "owner")["accepted_reference"])

    async def test_missing_required_database_artifact_row_hides_accepted_reference(self):
        service = IntentService(self.store, FixtureBridge())
        result = await service.execute(TEXT, "owner", "profile", "workspace")
        self.assertEqual(result["state"], "ACCEPTED")
        with sqlite3.connect(self.store.database) as database:
            database.execute("DELETE FROM artifacts WHERE run_id=? AND name='assessment.raw.json'", (result["run_id"],))
        database.close()
        # The physical file still exists; missing authoritative registration
        # must nevertheless invalidate the accepted reference.
        self.assertTrue((self.store.artifact_root / result["run_id"] / "assessment.raw.json").exists())
        with self.assertRaisesRegex(StoreError, "EVIDENCE_INTEGRITY_FAILED"):
            self.store.read(result["run_id"], "owner")
        observed = service.get(result["run_id"], "owner")
        self.assertIsNone(observed["accepted_reference"])
        self.assertFalse(observed["durable"])


if __name__ == "__main__":
    unittest.main()
