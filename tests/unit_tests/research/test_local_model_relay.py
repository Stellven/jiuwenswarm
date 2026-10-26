"""Offline effect-claim fixtures. Never instantiate a real SSH backend."""
import asyncio
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from jiuwenswarm.research.contracts.types import ResearchError
from jiuwenswarm.research.local_model_relay import (
    BackendStageFailure, HostCodexBackend, LocalModelRelay, PROTOCOL,
)
from jiuwenswarm.research.private_rpc import PrivateRPCServer


PIN = 'a' * 64


class Catalog:
    def resolve(self, endpoint_id, binding_sha256=None):
        if endpoint_id != 'fixture' or binding_sha256 != PIN:
            raise ResearchError('invalid_request')
        return {'model': {'model_name': 'fixture-model', 'timeout_s': 1,
                          'max_prompt_bytes': 2048}, 'binding_sha256': PIN}


class RelayTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = Path(self.temp.name)
        self.runtime.chmod(0o700)
        # Windows lacks Unix UID/mode semantics; production custody is Linux-only.
        self.custody = patch('jiuwenswarm.research.local_model_relay.private_path') if os.name == 'nt' else None
        if self.custody:
            self.custody.start()
        self.backend = AsyncMock(return_value=dict(outcome='completed', http_status=200,
            response_text=' { "choices" : [] }\n', provider_request_id='fixture-receipt'))
        self.relay = LocalModelRelay(Catalog(), self.runtime, backend=self.backend)
        self.payload = dict(request_id='one', endpoint_id='fixture', binding_sha256=PIN,
            model='fixture-model', prompt='fixture prompt', timeout_s=1)

    def tearDown(self):
        self.relay.close()
        if self.custody:
            self.custody.stop()
        self.temp.cleanup()

    async def test_saved_original_response_and_conflict(self):
        first = await self.relay.invoke(self.payload)
        self.assertEqual(first, await self.relay.invoke(copy.deepcopy(self.payload)))
        self.assertEqual(first['response_text'], ' { "choices" : [] }\n')
        self.backend.assert_awaited_once()
        with self.assertRaises(ResearchError):
            await self.relay.invoke({**self.payload, 'prompt': 'changed'})
        self.backend.assert_awaited_once()

    async def test_restart_unknown_blocks_every_new_effect(self):
        self.backend.side_effect = TimeoutError()
        unknown = await self.relay.invoke(self.payload)
        self.assertEqual(unknown['outcome'], 'outcome_unknown')
        self.relay.close()
        self.relay = LocalModelRelay(Catalog(), self.runtime, backend=self.backend)
        self.assertEqual(await self.relay.invoke(self.payload), unknown)
        with self.assertRaises(ResearchError) as caught:
            await self.relay.invoke({**self.payload, 'request_id': 'two'})
        self.assertEqual(caught.exception.code, 'DELIVERY_UNKNOWN')
        self.backend.assert_awaited_once()

    async def test_backend_failure_diagnostics_are_closed_and_never_retry(self):
        self.backend.side_effect=BackendStageFailure('helper_stdin',BrokenPipeError('SECRET prompt/token'))
        unknown=await self.relay.invoke(self.payload)
        self.assertEqual(unknown['outcome'],'outcome_unknown')
        name=hashlib.sha256(self.payload['request_id'].encode()).hexdigest()+'.json'
        raw=(self.runtime/'backend-receipts'/name).read_text()
        diagnostic=json.loads(raw)
        self.assertEqual(diagnostic['failure'],{'stage':'helper_stdin','exception_class':'BrokenPipeError'})
        self.assertIsNone(diagnostic['receipt'])
        self.assertNotIn('SECRET',raw)
        self.assertNotIn('failure',unknown)
        self.assertEqual(await self.relay.invoke(self.payload),unknown)
        with self.assertRaises(ResearchError):
            await self.relay.invoke({**self.payload,'request_id':'another'})
        self.backend.assert_awaited_once()

    async def test_unrecognized_exception_has_no_arbitrary_name_or_message(self):
        class SecretTokenException(Exception):pass
        self.backend.side_effect=SecretTokenException('SECRET')
        await self.relay.invoke(self.payload)
        diagnostic=json.loads(next((self.runtime/'backend-receipts').glob('*.json')).read_text())
        self.assertEqual(diagnostic['failure'],{'stage':'backend_error','exception_class':'other'})
        self.assertNotIn('SECRET',json.dumps(diagnostic))

    async def test_host_spawn_failure_has_stage_without_launching_helper(self):
        with patch('jiuwenswarm.research.local_model_relay.asyncio.create_subprocess_exec',
                   AsyncMock(side_effect=FileNotFoundError('SECRET executable'))) as spawn:
            with self.assertRaises(BackendStageFailure) as caught:
                await HostCodexBackend()({'backend':{'kind':'host-codex-app-server',
                    'host_python':'/fixture/python'}},self.payload)
        self.assertEqual(caught.exception.diagnostic,
                         {'stage':'helper_spawn','exception_class':'FileNotFoundError'})
        self.assertNotIn('SECRET',str(caught.exception))
        spawn.assert_awaited_once()

    async def test_host_stdin_failure_has_stage_and_joins_observer(self):
        process=SimpleNamespace(returncode=1,stdin=unittest.mock.Mock(),wait=AsyncMock())
        process.stdin.write.side_effect=BrokenPipeError('SECRET wire')
        binding={'model':{},'backend':{'kind':'host-codex-app-server',
            'host_python':'/fixture/python','codex_executable':'/fixture/codex',
            'codex_sha256':PIN,'account_fingerprint':PIN,'working_directory':'/fixture'}}
        with patch('jiuwenswarm.research.local_model_relay.asyncio.create_subprocess_exec',
                   AsyncMock(return_value=process)):
            with self.assertRaises(BackendStageFailure) as caught:
                await HostCodexBackend()(binding,self.payload)
        self.assertEqual(caught.exception.diagnostic,
                         {'stage':'helper_stdin','exception_class':'BrokenPipeError'})
        self.assertNotIn('SECRET',str(caught.exception))

    async def test_crash_claim_is_never_retried(self):
        self.relay.db.execute('INSERT INTO requests VALUES (?,?,NULL)', ('crashed', 'digest'))
        self.relay.db.commit()
        with self.assertRaises(ResearchError):
            await self.relay.invoke(self.payload)
        self.backend.assert_not_awaited()

    def probe_fixture(self):
        binding={'backend':{'kind':'host-codex-app-server','codex_sha256':PIN},
                 'model':{'model_name':'fixture-model','reasoning_effort':'medium','timeout_s':120,'max_prompt_bytes':2048}}
        native=dict(schema='ai4r-host-codex-response:1',requested_model='fixture-model',
                    reasoning_effort='medium',account_fingerprint=None,binary_sha256=None,
                    thread_start=None,turn_start=None,turn_completed=None,wire_frames=[],
                    error_code='invalid_request',outcome='failed')
        self.relay.catalog.resolve=unittest.mock.Mock(return_value=binding)
        self.backend.side_effect=None
        self.backend.return_value=dict(outcome='failed',http_status=None,
                                       response_text=json.dumps(native),provider_request_id=None)
        return binding,native,dict(endpoint_id='fixture',binding_sha256=PIN)

    async def test_probe_bypasses_unknown_without_changing_ledger_or_original_binding(self):
        self.backend.side_effect=TimeoutError()
        await self.relay.invoke(self.payload)
        before=(self.runtime/'requests.sqlite3').read_bytes()
        binding,_,request=self.probe_fixture()
        result=await self.relay.probe(request)
        self.assertTrue(result['ready'])
        self.assertFalse(result['inference_requested'])
        actual_binding,actual_payload=self.backend.await_args.args
        self.assertEqual(actual_binding['backend']['codex_sha256'],'0'*64)
        self.assertEqual(binding['backend']['codex_sha256'],PIN)
        self.assertEqual(set(actual_payload),{'prompt','timeout_s'})
        self.assertLessEqual(actual_payload['timeout_s'],20)
        self.assertEqual((self.runtime/'requests.sqlite3').read_bytes(),before)
        self.assertEqual(self.relay.db.execute('SELECT count(*) FROM requests').fetchone()[0],1)
        self.assertEqual((await self.relay.invoke(self.payload))['outcome'],'outcome_unknown')

    async def test_probe_rejects_payload_injection_wrong_backend_and_busy_without_dispatch(self):
        binding,_,request=self.probe_fixture()
        for extra in ('prompt','model','timeout_s','request_id','backend'):
            with self.subTest(extra=extra),self.assertRaises(ResearchError):
                await self.relay.probe({**request,extra:'injected'})
        async with self.relay.lock:
            with self.assertRaises(ResearchError):await self.relay.probe(request)
        binding['backend']['kind']='ssh-loopback-openai'
        with self.assertRaises(ResearchError):await self.relay.probe(request)
        binding['backend']['kind']='host-codex-app-server';binding['backend']['codex_sha256']='0'*64
        with self.assertRaises(ResearchError):await self.relay.probe(request)
        self.backend.assert_not_awaited()

    async def test_probe_failure_retains_unknown_and_no_ledger_writes(self):
        self.backend.side_effect=TimeoutError()
        await self.relay.invoke(self.payload)
        before=(self.runtime/'requests.sqlite3').read_bytes()
        _,native,request=self.probe_fixture()
        native['turn_start']={'id':'unexpected'}
        self.backend.return_value['response_text']=json.dumps(native)
        self.assertFalse((await self.relay.probe(request))['ready'])
        self.backend.side_effect=BackendStageFailure('helper_spawn',OSError('SECRET'))
        result=await self.relay.probe(request)
        self.assertFalse(result['ready']);self.assertNotIn('SECRET',json.dumps(result))
        self.assertEqual((self.runtime/'requests.sqlite3').read_bytes(),before)

    async def test_native_nonzero_exit_retains_only_closed_stderr_diagnostics(self):
        stderr=b'WSL (123) ERROR: UtilAcceptVsock: accept4 failed 110 SECRET token/prompt\n'
        process=SimpleNamespace(returncode=7,pid=123,stdin=unittest.mock.Mock(),
            stdout=SimpleNamespace(read=AsyncMock(return_value=b'')),
            stderr=SimpleNamespace(read=AsyncMock(side_effect=[stderr,b''])),wait=AsyncMock())
        process.stdin.drain=AsyncMock()
        binding={'model':{},'backend':{'kind':'host-codex-app-server',
            'host_python':'/fixture/python','codex_executable':'/fixture/codex',
            'codex_sha256':PIN,'account_fingerprint':PIN,'working_directory':'/fixture'}}
        with patch('jiuwenswarm.research.local_model_relay.asyncio.create_subprocess_exec',
                   AsyncMock(return_value=process)):
            result=await HostCodexBackend()(binding,self.payload)
        self.assertEqual(result['outcome'],'outcome_unknown')
        self.assertEqual(result.original_bytes,b'')
        self.assertEqual(result.transport_diagnostic['exit_code'],7)
        self.assertEqual(result.transport_diagnostic['stderr_class'],'wsl_interop_error')
        self.assertEqual(result.transport_diagnostic['stderr_sha256'],hashlib.sha256(stderr).hexdigest())
        self.backend.side_effect=None;self.backend.return_value=result
        public=await self.relay.invoke(self.payload)
        private=next((self.runtime/'backend-receipts').glob('*.json')).read_text()
        self.assertIn('wsl_interop_error',private)
        self.assertNotIn('SECRET',private)
        self.assertNotIn('transport_diagnostic',public)

    async def test_stderr_capture_drains_large_output_with_bounded_classification(self):
        chunks=[b'x'*65536,b'Traceback (most recent call last): SECRET',b'']
        process=SimpleNamespace(returncode=1,pid=123,stdin=unittest.mock.Mock(),
            stdout=SimpleNamespace(read=AsyncMock(return_value=b'')),
            stderr=SimpleNamespace(read=AsyncMock(side_effect=chunks)),wait=AsyncMock())
        process.stdin.drain=AsyncMock()
        binding={'model':{},'backend':{'kind':'host-codex-app-server',
            'host_python':'/fixture/python','codex_executable':'/fixture/codex',
            'codex_sha256':PIN,'account_fingerprint':PIN,'working_directory':'/fixture'}}
        with patch('jiuwenswarm.research.local_model_relay.asyncio.create_subprocess_exec',
                   AsyncMock(return_value=process)):
            result=await HostCodexBackend()(binding,self.payload)
        diagnostic=result.transport_diagnostic
        self.assertEqual(diagnostic['stderr_classification_prefix_bytes'],65536)
        self.assertTrue(diagnostic['stderr_classification_truncated'])
        self.assertEqual(diagnostic['stderr_class'],'unclassified')
        self.assertEqual(diagnostic['stderr_bytes'],sum(map(len,chunks)))
        self.assertEqual(diagnostic['stderr_sha256'],hashlib.sha256(b''.join(chunks)).hexdigest())

    async def test_provider_error_body_and_receipt_are_sanitized(self):
        self.backend.return_value = dict(outcome='failed', http_status=503,
            response_text='private provider diagnostics', provider_request_id='private token')
        result = await self.relay.invoke(self.payload)
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(result['http_status'], 503)
        self.assertIsNone(result['response_text'])
        self.assertIsNone(result['provider_request_id'])
        self.assertNotIn('private', json.dumps(result))

    async def test_cancel_records_unknown_and_joins_backend(self):
        started, joined = asyncio.Event(), asyncio.Event()
        async def observer(binding, payload):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                joined.set()
        self.relay.backend = observer
        task = asyncio.create_task(self.relay.invoke(self.payload))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(joined.is_set())
        self.assertEqual((await self.relay.invoke(self.payload))['outcome'], 'outcome_unknown')
        with self.assertRaises(ResearchError):
            await self.relay.invoke({**self.payload, 'request_id': 'two'})

    async def test_closed_payload_and_injection_isolation(self):
        for change in ({'endpoint_id': 'fixture; arbitrary-command'}, {'command': 'anything'},
                       {'url': 'https://example.invalid'}, {'timeout_s': float('nan')},
                       {'timeout_s': True}, {'prompt': 'x' * 2049}, {'model': 'other'}):
            with self.assertRaises(ResearchError):
                await self.relay.invoke({**self.payload, **change})
        self.backend.assert_not_awaited()
        prompt = "$(arbitrary-command); 'quoted'\n--anything"
        await self.relay.invoke({**self.payload, 'prompt': prompt})
        self.assertEqual(self.backend.await_args.args[1]['prompt'], prompt)

    async def test_simultaneous_requests_are_serialized(self):
        active = 0
        async def backend(binding, payload):
            nonlocal active
            active += 1
            self.assertEqual(active, 1)
            await asyncio.sleep(0)
            active -= 1
            return dict(outcome='failed', http_status=400, response_text=None, provider_request_id=None)
        self.relay.backend = backend
        results = await asyncio.gather(*(self.relay.invoke({**self.payload, 'request_id': str(i)}) for i in range(4)))
        self.assertTrue(all(r['outcome'] == 'failed' for r in results))
        self.assertEqual(len([r for r in results if r['http_status']==400]),1)

    async def test_busy_requests_never_dispatch_later_and_rejections_are_durable(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def backend(binding, payload):
            entered.set()
            await release.wait()
            return dict(outcome='failed', http_status=400, response_text=None, provider_request_id=None)
        self.relay.backend=AsyncMock(side_effect=backend)
        active=asyncio.create_task(self.relay.invoke(self.payload))
        await entered.wait()
        queued={**self.payload,'request_id':'must-not-queue','timeout_s':0.001}
        refused=await self.relay.invoke(queued)
        self.assertEqual(refused['http_status'],429)
        release.set();await active
        self.assertEqual(await self.relay.invoke(queued),refused)
        self.relay.backend.assert_awaited_once()

    async def test_capability_boundary_prevents_dispatch(self):
        handler = AsyncMock()
        server = PrivateRPCServer(self.runtime / 'unused.sock', protocol=PROTOCOL,
            session_id='session', capability='private-secret', handlers={'invoke': handler}, allowed_uids=[42])
        writer = unittest.mock.Mock()
        request = dict(protocol=PROTOCOL, session_id='session', capability='wrong',
                       operation='invoke', payload=self.payload)
        with patch('jiuwenswarm.research.private_rpc.peer_credentials', return_value=(1, 42, 42)), \
             patch('jiuwenswarm.research.private_rpc.read_frame', AsyncMock(return_value=request)), \
             patch('jiuwenswarm.research.private_rpc.close_writer', AsyncMock()):
            await server._handle(None, writer)
        handler.assert_not_awaited()
        writer.write.assert_not_called()


if __name__ == '__main__':
    unittest.main()
