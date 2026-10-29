"""Offline host-helper boundary checks. Never executes Codex or reads real auth."""
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jiuwenswarm.research import local_model_codex as helper

EMAIL = 'fixture@example.invalid'


class FakeProcess:
    def __init__(self, *, mismatch=False, wrong_account=False, hang=False, terminal_interrupt=True,
                 reroute=False, tool_request=False, lost_ack=False, large_output=False,
                 deltas=0, delta_text='x' * 180, output_text=None, foreign_terminals=0):
        self.stdout = asyncio.StreamReader(limit=helper.MAX_RESPONSE_BYTES + 1)
        self.stdin = self
        self.returncode = None
        self.requests = []
        self.mismatch, self.wrong_account, self.hang = mismatch, wrong_account, hang
        self.terminal_interrupt, self.reroute = terminal_interrupt, reroute
        self.tool_request, self.lost_ack, self.large_output = tool_request, lost_ack, large_output
        self.deltas, self.delta_text, self.output_text = deltas, delta_text, output_text
        self.foreign_terminals = foreign_terminals
        self.killed = False

    def feed(self, envelope):
        self.stdout.feed_data((json.dumps(envelope, ensure_ascii=False, separators=(',', ':')) + '\n').encode())

    def write(self, raw):
        msg = json.loads(raw)
        self.requests.append(msg)
        if 'id' not in msg or 'method' not in msg:
            return
        method = msg['method']
        result = {}
        if method == 'account/read':
            result = {'account': {'type': 'chatgpt', 'email': 'other@example.invalid' if self.wrong_account else EMAIL}}
        elif method == 'model/list':
            result = {'data': [{'model': 'fixture-catalog-only'}]}
        elif method == 'thread/start':
            result = {'thread': {'id': 'thread-1'}, 'model': 'wrong-model' if self.mismatch else 'gpt-6.1-sol',
                      'reasoningEffort': 'medium'}
            self.feed({'method': 'thread/started', 'params': {'thread': {'id': 'thread-1'}}})
        elif method == 'turn/start':
            result = {'turn': {'id': 'turn-1'}}
        if method == 'turn/start' and self.lost_ack:
            return
        self.feed({'id': msg['id'], 'result': result})
        if method == 'turn/start':
            for method_name in ('account/updated', 'account/login/completed', 'model/list'):
                self.feed({'method': method_name, 'params': {'threadId': 'thread-1', 'email': EMAIL, 'token': 'fixture-private'}})
            if self.reroute:
                self.feed({'method': 'model/rerouted', 'params': {'threadId': 'thread-1', 'turnId': 'turn-1'}})
            if self.tool_request:
                self.feed({'id': 999, 'method': 'item/commandExecution/requestApproval',
                           'params': {'threadId': 'thread-1', 'turnId': 'turn-1'}})
            for index in range(self.deltas):
                self.feed({'method': 'item/agentMessage/delta', 'params': {'threadId': 'thread-1',
                           'turnId': 'turn-1', 'delta': self.delta_text}})
            for index in range(self.foreign_terminals):
                self.feed({'method': 'turn/completed', 'params': {'threadId': 'thread-1',
                    'turn': {'id': 'foreign-turn', 'status': 'completed', 'items': []}}})
            if not self.hang and not self.reroute and not self.tool_request:
                self.feed({'method': 'thread/tokenUsage/updated', 'params': {'threadId': 'thread-1',
                    'turnId': 'turn-1', 'tokenUsage': {'last': {'inputTokens': 12, 'outputTokens': 9}}}})
                self.complete('completed')
        elif method == 'turn/interrupt' and self.terminal_interrupt:
            self.complete('interrupted')

    def complete(self, status):
        text = self.output_text if self.output_text is not None else 'x' * 600000 if self.large_output else '{"answer":4}'
        self.feed({'method': 'turn/completed', 'params': {'threadId': 'thread-1', 'turn': {
            'id': 'turn-1', 'status': status, 'items': [{'type': 'agentMessage', 'text': text}]}}})

    async def drain(self):
        return None

    def kill(self):
        self.killed = True
        self.returncode = -9
        self.stdout.feed_eof()

    async def wait(self):
        return self.returncode


class HostCodexHelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.binary = self.root / ('fixture.exe' if os.name == 'nt' else 'fixture-codex')
        self.binary.write_bytes(b'public executable fixture')
        self.payload = {'model': {'id': 'host-sol', 'name': 'Host Sol', 'model_name': 'gpt-6.1-sol',
            'revision': 'fixture:1', 'enabled': True, 'context_window': 128000,
            'max_prompt_bytes': 10000, 'timeout_s': 2, 'reasoning_effort': 'medium'},
            'prompt': 'Return the integer sum of two and two.', 'timeout_s': 2,
            'codex_executable': str(self.binary), 'codex_sha256': hashlib.sha256(self.binary.read_bytes()).hexdigest(),
            'account_fingerprint': hashlib.sha256(EMAIL.encode()).hexdigest(), 'working_directory': str(self.root)}

    def tearDown(self):
        self.temp.cleanup()

    def run_fake(self, **options):
        calls = []
        async def spawn(*argv, **kwargs):
            proc = FakeProcess(**options)
            calls.append((argv, kwargs, proc))
            return proc
        result = helper.execute(self.payload, spawn=spawn, profile_resolver=lambda: self.root)
        return result, helper.unpack_bundle(json.loads(result['response_text'])) if result['response_text'] else None, calls

    def test_original_evidence_and_no_auth_leak(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'fixture-private', 'CODEX_HOME': '/linux/secret', 'HTTPS_PROXY': 'fixture-private'}):
            result, bundle, calls = self.run_fake()
        self.assertEqual(result['outcome'], 'completed')
        self.assertIsNone(result['http_status'])
        self.assertEqual(result['provider_request_id'], 'turn-1')
        self.assertEqual(bundle['thread_start']['model'], 'gpt-6.1-sol')
        self.assertEqual(bundle['turn_completed']['turn']['items'][0]['text'], '{"answer":4}')
        raw = helper._json(result)
        self.assertNotIn(EMAIL, raw)
        self.assertNotIn('fixture-private', raw)
        for frame in bundle['wire_frames']:
            self.assertNotIn(EMAIL, frame['raw'])
            self.assertNotIn('fixture-private', frame['raw'])
            self.assertNotIn('account/read', frame['raw'])
            self.assertNotIn('model/list', frame['raw'])
        self.assertTrue(any('thread/tokenUsage/updated' in frame['raw'] for frame in bundle['wire_frames']))
        frames = [json.loads(frame['raw']) for frame in bundle['wire_frames']]
        started_index = next(i for i, frame in enumerate(frames) if frame.get('method') == 'thread/started')
        reply_index = next(i for i, frame in enumerate(frames) if frame.get('result', {}).get('thread', {}).get('id') == 'thread-1')
        self.assertLess(started_index, reply_index)
        argv, kwargs, proc = calls[0]
        self.assertIn('mcp_servers={}', argv)
        for key in ('OPENAI_API_KEY', 'CODEX_HOME', 'HTTPS_PROXY'):
            self.assertNotIn(key, kwargs['env'])
        request = next(x for x in proc.requests if x.get('method') == 'turn/start')
        self.assertEqual(request['params']['input'], [{'type': 'text', 'text': self.payload['prompt']}])
        self.assertTrue(proc.killed)
        self.assertFalse(Path(kwargs['cwd']).exists())

    def test_identity_mismatch_never_submits_inference(self):
        result, bundle, calls = self.run_fake(wrong_account=True)
        self.assertEqual(bundle['error_code'], 'auth_failed')
        self.assertEqual(result['outcome'], 'failed')
        self.assertFalse(any(x.get('method') == 'thread/start' for x in calls[0][2].requests))

    def test_model_mismatch_never_submits_turn(self):
        result, bundle, calls = self.run_fake(mismatch=True)
        self.assertEqual(bundle['error_code'], 'invalid_output')
        self.assertEqual(result['outcome'], 'failed')
        self.assertFalse(any(x.get('method') == 'turn/start' for x in calls[0][2].requests))

    def test_binary_mismatch_never_spawns(self):
        self.payload['codex_sha256'] = '0' * 64
        result, bundle, calls = self.run_fake()
        self.assertEqual(bundle['error_code'], 'invalid_request')
        self.assertEqual(calls, [])

    def test_timeout_without_terminal_is_unknown_and_retains_frames(self):
        self.payload['timeout_s'] = 0.3
        result, bundle, calls = self.run_fake(hang=True, terminal_interrupt=False)
        self.assertEqual(result['outcome'], 'outcome_unknown')
        self.assertEqual(bundle['error_code'], 'CONTAINMENT_UNCERTAIN')
        self.assertIsNotNone(bundle['turn_start'])
        self.assertTrue(any('turn/interrupt' in x['raw'] for x in bundle['wire_frames']))
        self.assertEqual(sum(x.get('method') == 'turn/start' for x in calls[0][2].requests), 1)

    def test_timeout_with_observed_interrupt_is_failed(self):
        self.payload['timeout_s'] = 0.3
        result, bundle, _ = self.run_fake(hang=True)
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(bundle['error_code'], 'timeout')
        self.assertEqual(bundle['turn_completed']['turn']['status'], 'interrupted')

    def test_reroute_never_becomes_success(self):
        result, bundle, _ = self.run_fake(reroute=True)
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(bundle['error_code'], 'invalid_output')

    def test_unsupported_generation_caps_rejected(self):
        self.payload['model']['max_output_tokens'] = 100
        _, bundle, calls = self.run_fake()
        self.assertEqual(bundle['error_code'], 'invalid_request')
        self.assertEqual(calls, [])

    def test_lost_turn_acknowledgement_is_never_replayed(self):
        self.payload['timeout_s'] = 0.3
        result, bundle, calls = self.run_fake(lost_ack=True)
        self.assertEqual(result['outcome'], 'outcome_unknown')
        self.assertEqual(bundle['error_code'], 'CONTAINMENT_UNCERTAIN')
        self.assertEqual(sum(x.get('method') == 'turn/start' for x in calls[0][2].requests), 1)

    def test_tool_request_is_refused_without_execution(self):
        result, bundle, calls = self.run_fake(tool_request=True)
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(bundle['error_code'], 'provider_error')
        self.assertTrue(any(x.get('id') == 999 and x.get('error', {}).get('code') == -32601 for x in calls[0][2].requests))

    def test_large_original_terminal_fits_without_duplicate_payloads(self):
        result, bundle, _ = self.run_fake(large_output=True)
        self.assertEqual(result['outcome'], 'completed')
        self.assertEqual(bundle['turn_completed']['turn']['items'][0]['text'], 'x' * 600000)
        packed = json.loads(result['response_text'])
        self.assertEqual(packed['schema'], 'ai4r-host-codex-response:2')
        self.assertIs(type(packed['turn_completed']), int)
        self.assertTrue(packed['evidence']['full_original_trace'])
        self.assertLessEqual(len(helper._json(result).encode('utf-8')), helper.MAX_RESPONSE_BYTES)

    def test_stream_overflow_still_sends_one_interrupt_and_keeps_actual_terminal(self):
        result, bundle, calls = self.run_fake(deltas=5000, hang=True)
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(bundle['error_code'], 'invalid_output')
        self.assertEqual(bundle['turn_completed']['turn']['status'], 'interrupted')
        self.assertEqual(sum(msg.get('method') == 'turn/interrupt' for msg in calls[0][2].requests), 1)
        public = {key: val for key, val in result.items() if key != '_private_evidence'}
        self.assertLessEqual(len(helper._json(public).encode('utf-8')), helper.MAX_RESPONSE_BYTES)
        self.assertLessEqual(len(helper._json(result).encode('utf-8')), helper.MAX_PRIVATE_RECEIPT_BYTES)
        packed = json.loads(result['response_text'])
        self.assertFalse(packed['evidence']['full_original_trace'])
        self.assertEqual(packed['evidence']['unavailable_reason'], 'wire_budget')
        self.assertGreater(packed['evidence']['observed_frames'], len(packed['wire_frames']))
        self.assertIn('_private_evidence', result)
        for frame in result['_private_evidence']['wire_frames']:
            original = base64.b64decode(frame['raw_b64']).decode()
            self.assertNotIn(EMAIL, original)
            self.assertNotIn('fixture-private', original)

    def test_stream_overflow_without_terminal_stays_unknown(self):
        self.payload['timeout_s'] = 0.8
        result, bundle, calls = self.run_fake(deltas=5000, hang=True, terminal_interrupt=False)
        self.assertEqual(result['outcome'], 'outcome_unknown')
        self.assertEqual(bundle['error_code'], 'CONTAINMENT_UNCERTAIN')
        self.assertIsNone(bundle['turn_completed'])
        self.assertEqual(sum(msg.get('method') == 'turn/interrupt' for msg in calls[0][2].requests), 1)

    def test_many_small_emitted_deltas_have_one_consistent_byte_bound(self):
        result, bundle, _ = self.run_fake(deltas=4200, delta_text='a')
        self.assertEqual(result['outcome'], 'completed')
        self.assertGreater(len(bundle['wire_frames']), 4096)
        packed = json.loads(result['response_text'])
        self.assertEqual(packed['evidence']['observed_frames'], len(bundle['wire_frames']))
        self.assertEqual(packed['evidence']['observed_bytes'], sum(len(f['raw'].encode('utf-8')) for f in bundle['wire_frames']))
        self.assertLessEqual(len(helper._json(result).encode('utf-8')), helper.MAX_RESPONSE_BYTES)

    def test_escape_heavy_multibyte_output_uses_exact_wire_byte_budget(self):
        text = '\\"\u03a9\n' * 30000
        result, bundle, _ = self.run_fake(output_text=text)
        self.assertEqual(result['outcome'], 'completed')
        self.assertEqual(bundle['turn_completed']['turn']['items'][0]['text'], text)
        self.assertLessEqual(len(helper._json(result).encode('utf-8')), helper.MAX_RESPONSE_BYTES)
        packed = json.loads(result['response_text'])
        self.assertEqual(packed['evidence']['observed_bytes'], sum(len(f['raw'].encode('utf-8')) for f in bundle['wire_frames']))

    def test_unrepresentable_terminal_is_explicit_unavailable_and_private_original_survives(self):
        result, bundle, calls = self.run_fake(output_text='x' * 850000)
        self.assertEqual(result['outcome'], 'outcome_unknown')
        self.assertEqual(bundle['error_code'], 'CONTAINMENT_UNCERTAIN')
        self.assertIsNone(bundle['turn_completed'])
        self.assertFalse(json.loads(result['response_text'])['evidence']['full_original_trace'])
        self.assertIn('_private_evidence', result)
        private = result['_private_evidence']
        self.assertTrue(any('turn/completed' in base64.b64decode(f['raw_b64']).decode() for f in private['wire_frames']))
        self.assertFalse(any(msg.get('method') == 'turn/interrupt' for msg in calls[0][2].requests))

    def test_oversize_generation_request_is_rejected_before_turn_write(self):
        self.payload['model']['max_prompt_bytes'] = helper.MAX_RESPONSE_BYTES
        self.payload['prompt'] = 'x' * 800000
        result, bundle, calls = self.run_fake()
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(bundle['error_code'], 'invalid_output')
        self.assertFalse(any(msg.get('method') == 'turn/start' for msg in calls[0][2].requests))
        self.assertTrue(json.loads(result['response_text'])['evidence']['full_original_trace'])

    def test_repeated_foreign_terminal_frames_cannot_grow_proof_storage_or_claim_success(self):
        result, bundle, calls = self.run_fake(foreign_terminals=6000, hang=True)
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(bundle['turn_completed']['turn']['id'], 'turn-1')
        self.assertEqual(bundle['turn_completed']['turn']['status'], 'interrupted')
        self.assertEqual(sum(msg.get('method') == 'turn/interrupt' for msg in calls[0][2].requests), 1)
        public = {key: val for key, val in result.items() if key != '_private_evidence'}
        self.assertLessEqual(len(helper._json(public).encode('utf-8')), helper.MAX_RESPONSE_BYTES)
        self.assertLessEqual(len(helper._json(result).encode('utf-8')), helper.MAX_PRIVATE_RECEIPT_BYTES)


if __name__ == '__main__':
    unittest.main()
