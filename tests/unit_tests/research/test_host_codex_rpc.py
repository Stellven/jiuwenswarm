"""Real Unix transport with an injected native process; never runs a model."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import unittest

from jiuwenswarm.research import local_model_codex as helper
from jiuwenswarm.research.local_model_relay import LocalModelRelay, backend_output, host_backend_output
from jiuwenswarm.research.local_models import LocalModelCatalog, LocalModelClient, PROTOCOL
from jiuwenswarm.research.private_rpc import PrivateRPCServer
from jiuwenswarm.research.providers import ProviderError
from tests.unit_tests.research.test_host_codex_helper import EMAIL, FakeProcess
from tests.unit_tests.research.test_host_codex_route import document


@unittest.skipUnless(os.name == 'posix', 'Actual Unix sockets and peer credentials required')
class HostCodexRPCTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = self.root / 'runtime'
        self.runtime.mkdir(mode=0o700)
        self.binary = self.root / 'fixture-codex'
        self.binary.write_bytes(b'Never executed: injected native process')
        self.doc = document()
        self.doc['backend'].update(codex_executable=str(self.binary), working_directory=str(self.root),
            codex_sha256=hashlib.sha256(self.binary.read_bytes()).hexdigest(),
            account_fingerprint=hashlib.sha256(EMAIL.encode()).hexdigest())
        self.doc['transport'].update(socket_path=str(self.runtime/'model.sock'),
            session_file=str(self.runtime/'session.json'), peer_uid=os.geteuid(), socket_mode=0o600)
        self.doc['models'][0]['timeout_s'] = 3
        path = self.root / 'catalog.json'
        path.write_text(json.dumps(self.doc), encoding='utf-8')
        path.chmod(0o600)
        session = {'session_id':secrets.token_hex(16), 'capability':secrets.token_hex(32)}
        session_path = self.runtime / 'session.json'
        session_path.write_text(json.dumps(session), encoding='utf-8')
        session_path.chmod(0o600)
        self.catalog = LocalModelCatalog(path, owner_uid=os.geteuid())
        self.options = {}
        self.processes = []
        self.backend_calls = 0

        async def backend(binding, request):
            self.backend_calls += 1
            async def spawn(*args, **kwargs):
                process = FakeProcess(**self.options)
                self.processes.append(process)
                return process
            payload = {'model':binding['model'], 'prompt':request['prompt'],
                'timeout_s':min(request['timeout_s'], 0.8),
                **{key:binding['backend'][key] for key in
                   ('codex_executable','codex_sha256','account_fingerprint','working_directory')}}
            response = await helper.execute_async(payload, spawn=spawn, profile_resolver=lambda:self.root)
            return backend_output(helper._json(response).encode('utf-8'), 0, host_backend_output)

        self.relay = LocalModelRelay(self.catalog, self.runtime, backend=backend)
        self.server = PrivateRPCServer(self.runtime/'model.sock', protocol=PROTOCOL,
            allowed_uids={os.geteuid()}, handlers={'invoke':self.relay.invoke}, **session)
        await self.server.start()

    async def asyncTearDown(self):
        await self.server.close()
        self.relay.close()
        self.temp.cleanup()

    def client(self):
        return LocalModelClient(self.catalog.resolve('local-host-codex61'))

    async def test_large_completed_original_survives_actual_socket(self):
        self.options = {'large_output':True}
        result = await self.client().invoke('Original public fixture prompt', timeout_s=2, call_function='worker')
        self.assertEqual(result['text'], 'x'*600000)
        self.assertEqual(result['identity']['effective'], 'gpt-6.1-sol')
        self.assertEqual(self.backend_calls, 1)
        self.assertEqual(len(list((self.runtime/'backend-receipts').glob('*.receipt'))), 1)

    async def test_exact_refusal_is_known_failure_and_does_not_poison_next_call(self):
        self.options = {'tool_request':True}
        with self.assertRaises(ProviderError) as failure:
            await self.client().invoke('Refusal fixture', timeout_s=2, call_function='worker')
        self.assertEqual(failure.exception.code, 'provider_error')
        self.assertFalse(failure.exception.outcome_unknown)
        self.assertEqual(sum(x.get('method')=='turn/interrupt' for x in self.processes[0].requests), 1)
        self.options = {}
        result = await self.client().invoke('A new independently authorized fixture', timeout_s=2, call_function='worker')
        self.assertEqual(result['text'], '{"answer":4}')
        self.assertEqual(self.backend_calls, 2)

    async def test_missing_terminal_keeps_original_receipt_and_blocks_new_effects(self):
        self.options = {'deltas':5000, 'hang':True, 'terminal_interrupt':False}
        with self.assertRaises(ProviderError) as failure:
            await self.client().invoke('Uncertain fixture', timeout_s=2, call_function='worker')
        self.assertTrue(failure.exception.outcome_unknown)
        self.assertEqual(failure.exception.observation['identity']['effective'], 'gpt-6.1-sol')
        with self.assertRaises(ProviderError) as blocked:
            await self.client().invoke('This must not dispatch', timeout_s=2, call_function='worker')
        self.assertTrue(blocked.exception.outcome_unknown)
        self.assertEqual(self.backend_calls, 1)
        self.assertEqual(len(list((self.runtime/'backend-receipts').glob('*.receipt'))), 1)


if __name__ == '__main__':
    unittest.main()
