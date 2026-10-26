"""Offline operator recovery: no provider calls or changes to original results."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from jiuwenswarm.research.contracts.types import ResearchError
from jiuwenswarm.research.local_model_relay import LocalModelRelay
from jiuwenswarm.research.local_model_recovery import acknowledge, paths, RuntimeLock


PIN = 'a' * 64


class Catalog:
    def resolve(self, *args, **kwargs):
        return {'model': {'model_name': 'fixture', 'timeout_s': 1, 'max_prompt_bytes': 1024}}


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = Path(self.temp.name)
        self.runtime.chmod(0o700)
        self.custody = patch('jiuwenswarm.research.local_model_relay.private_path') if os.name == 'nt' else None
        if self.custody:
            self.custody.start()
        self.backend = AsyncMock(side_effect=TimeoutError())
        self.relay = LocalModelRelay(Catalog(), self.runtime, backend=self.backend)
        self.payload = dict(request_id='unknown', endpoint_id='fixture', binding_sha256=PIN,
                            model='fixture', prompt='fixture', timeout_s=1)
        self.evidence = self.runtime / 'operator-evidence.txt'
        self.evidence.write_text('Fixture: relay stopped, owned helper exited; provider terminal unknown.')
        self.evidence.chmod(0o600)

    def tearDown(self):
        self.relay.close()
        if self.custody:
            self.custody.stop()
        self.temp.cleanup()

    async def original(self):
        result = await self.relay.invoke(self.payload)
        self.row = self.relay.db.execute('SELECT id,digest,result FROM requests').fetchone()
        self.relay.close()
        self.original_bytes = (self.runtime / 'requests.sqlite3').read_bytes()
        return result

    def ack(self, **overrides):
        options = dict(runtime=self.runtime, request_id=self.row[0], payload_sha256=self.row[1],
                       evidence_file=self.evidence, operator_note='Authorize distinct fixture work after local containment.',
                       authorize_new_work=True, confirm_local_process_containment=True,
                       acknowledge_provider_status_unknown=True)
        return acknowledge(**{**options, **overrides})

    def restart(self):
        self.relay = LocalModelRelay(Catalog(), self.runtime, backend=self.backend)

    async def test_ack_preserves_sqlite_and_original_replay_across_restart(self):
        original = await self.original()
        value = self.ack()
        self.assertEqual(value['provider_status'], 'unknown')
        self.assertEqual((self.runtime / 'requests.sqlite3').read_bytes(), self.original_bytes)
        self.restart()
        self.assertEqual(await self.relay.invoke(self.payload), original)
        self.backend.side_effect = None
        self.backend.return_value = dict(outcome='failed', http_status=503,
                                         response_text=None, provider_request_id=None)
        result = await self.relay.invoke({**self.payload, 'request_id': 'distinct'})
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(self.backend.await_count, 2)
        self.assertEqual(self.relay.db.execute('SELECT id,digest,result FROM requests WHERE id=?',
                                             (self.row[0],)).fetchone(), self.row)

    async def test_later_unknown_blocks_even_after_acknowledgement(self):
        await self.original()
        self.ack()
        self.restart()
        self.assertEqual((await self.relay.invoke({**self.payload, 'request_id': 'second'}))['outcome'], 'outcome_unknown')
        with self.assertRaises(ResearchError):
            await self.relay.invoke({**self.payload, 'request_id': 'third'})
        self.assertEqual(self.backend.await_count, 2)

    async def test_null_claim_cannot_be_acknowledged_and_still_blocks(self):
        await self.original()
        self.ack()
        self.restart()
        self.relay.db.execute('INSERT INTO requests VALUES (?,?,NULL)', ('pending', PIN))
        self.relay.db.commit()
        self.relay.close()
        with self.assertRaises(ResearchError):
            self.ack(request_id='pending', payload_sha256=PIN)
        self.restart()
        with self.assertRaises(ResearchError):
            await self.relay.invoke({**self.payload, 'request_id': 'fresh'})

    async def test_ack_requires_exact_digest_existing_unknown_and_all_attestations(self):
        await self.original()
        for override in ({'payload_sha256': PIN}, {'request_id': 'absent'},
                         {'authorize_new_work': False}, {'confirm_local_process_containment': False},
                         {'acknowledge_provider_status_unknown': False}, {'operator_note': ' '}):
            with self.subTest(override=override), self.assertRaises(ResearchError):
                self.ack(**override)
        self.assertEqual((self.runtime / 'requests.sqlite3').read_bytes(), self.original_bytes)

    async def test_append_only_ack_and_tampered_evidence_fail_closed(self):
        await self.original()
        self.ack()
        with self.assertRaises(ResearchError):
            self.ack()
        _, _, _, evidence = paths(self.runtime, self.row[0])
        evidence.write_bytes(b'tampered')
        self.restart()
        with self.assertRaises(ResearchError):
            await self.relay.invoke({**self.payload, 'request_id': 'fresh'})

    async def test_forged_cross_request_or_result_binding_fails_closed(self):
        await self.original()
        self.ack()
        _, target, _, _ = paths(self.runtime, self.row[0])
        original_ack = target.read_bytes()
        for key, value in (('request_id', 'different'), ('result_sha256', PIN),
                           ('payload_sha256', PIN), ('provider_status', 'completed'),
                           ('ledger_snapshot_sha256', PIN), ('ledger_file_sha256', PIN)):
            with self.subTest(key=key):
                document = json.loads(original_ack)
                document[key] = value
                target.write_text(json.dumps(document))
                self.restart()
                with self.assertRaises(ResearchError):
                    await self.relay.invoke({**self.payload, 'request_id': 'fresh'})
                self.relay.close()

    async def test_runtime_lock_excludes_relay_and_offline_ack(self):
        await self.relay.invoke(self.payload)
        self.row = self.relay.db.execute('SELECT id,digest,result FROM requests').fetchone()
        with self.assertRaises(ResearchError):
            LocalModelRelay(Catalog(), self.runtime, backend=self.backend)
        with self.assertRaises(ResearchError):
            self.ack()
        self.relay.close()
        self.relay.close()
        with RuntimeLock(self.runtime):
            with self.assertRaises(ResearchError):
                LocalModelRelay(Catalog(), self.runtime, backend=self.backend)

    async def test_failed_constructor_releases_its_lock(self):
        self.relay.close()
        with patch('jiuwenswarm.research.local_model_relay.sqlite3.connect', side_effect=OSError()):
            with self.assertRaises(OSError):
                LocalModelRelay(Catalog(), self.runtime, backend=self.backend)
        self.restart()


if __name__ == '__main__':
    unittest.main()
