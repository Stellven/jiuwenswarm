"""Real carrier pipes, no native Codex, account, network or inference."""
import asyncio
import hashlib
import json
import os
import sys

import pytest

from jiuwenswarm.research import local_model_relay as relay
from jiuwenswarm.research.contracts import ResearchError


@pytest.mark.asyncio
async def test_actual_carrier_keeps_nonzero_original_stdout_and_stderr():
    code = ('import sys; sys.stdin.buffer.read(); '
            'sys.stdout.buffer.write("original 雪\\n".encode("utf8")); '
            'sys.stderr.buffer.write(b"original diagnostic\\n"); sys.exit(7)')
    receipt = await relay.HostCodexBackend._observe([sys.executable, '-X', 'utf8', '-c', code], b'public fixture')
    assert receipt['outcome'] == 'outcome_unknown'
    assert receipt.transport_error == 'nonzero_exit'
    assert receipt.original_bytes == 'original 雪\n'.encode()
    assert receipt.stderr_bytes == b'original diagnostic\n'
    assert receipt.transport_observation['returncode'] == 7
    assert receipt.transport_observation['stdin_complete']
    assert receipt.transport_observation['stdout_complete']
    assert receipt.transport_observation['observer_joined']


@pytest.mark.asyncio
async def test_spawn_error_attaches_closed_observation_without_exception_text(tmp_path):
    with pytest.raises(FileNotFoundError) as caught:
        await relay.HostCodexBackend._observe([str(tmp_path / 'missing-carrier')], b'public')
    receipt = caught.value.backend_receipt
    assert receipt.original_bytes == b'' and receipt.stderr_bytes == b''
    assert receipt.transport_observation['phase'] == 'spawn'
    assert receipt.transport_observation['exception_class'] == 'FileNotFoundError'
    assert str(tmp_path) not in json.dumps(receipt.transport_observation)


@pytest.mark.asyncio
async def test_stderr_overflow_is_drained_bounded_and_never_claimed_valid():
    code = ('import sys; sys.stdin.buffer.read(); '
            'sys.stderr.buffer.write(b"x"*300000); '
            'sys.stdout.buffer.write(b"{}")')
    receipt = await relay.HostCodexBackend._observe([sys.executable, '-c', code], b'public')
    assert receipt['outcome'] != 'completed'
    assert receipt.transport_error == 'stderr_overflow'
    assert len(receipt.stderr_bytes) == relay.MAX_BACKEND_STDERR_BYTES
    assert receipt.transport_observation['stderr_overflow']
    assert receipt.transport_observation['stderr_bytes_observed'] == 300000
    assert receipt.transport_observation['stderr_complete']


@pytest.mark.skipif(os.name != 'posix', reason='Production Linux observer process-group termination')
@pytest.mark.asyncio
async def test_stdout_overflow_retains_explicit_incomplete_original_prefix():
    code = ('import sys; sys.stdin.buffer.read(); '
            'sys.stdout.buffer.write(b"y"*4500000); sys.stdout.buffer.flush()')
    with pytest.raises(ResearchError) as caught:
        await relay.HostCodexBackend._observe([sys.executable, '-c', code], b'public')
    receipt = caught.value.backend_receipt
    assert receipt['outcome'] == 'outcome_unknown'
    assert len(receipt.original_bytes) == relay.MAX_BACKEND_RECEIPT_BYTES
    assert receipt.transport_observation['stdout_overflow']
    assert receipt.transport_observation['observer_joined']


@pytest.mark.skipif(os.name != 'posix', reason='Production Linux observer process-group termination')
@pytest.mark.asyncio
async def test_cancelled_real_carrier_preserves_partial_bytes_without_claiming_native_terminal():
    code = ('import sys,time; sys.stdin.buffer.read(); '
            'sys.stdout.buffer.write(b"partial original"); sys.stdout.buffer.flush(); '
            'sys.stderr.buffer.write(b"partial stderr"); sys.stderr.buffer.flush(); time.sleep(30)')
    with pytest.raises(TimeoutError) as caught:
        async with asyncio.timeout(.5):
            await relay.HostCodexBackend._observe([sys.executable, '-c', code], b'public')
    receipt = caught.value.__cause__.backend_receipt
    assert receipt.original_bytes == b'partial original'
    assert receipt.stderr_bytes == b'partial stderr'
    assert receipt.transport_observation['exception_class'] == 'CancelledError'
    assert receipt.transport_observation['observer_joined']
    assert receipt['outcome'] == 'outcome_unknown'


@pytest.mark.asyncio
async def test_relay_persists_carrier_failure_bytes_and_error_phase_then_blocks_new_ids(tmp_path, monkeypatch):
    if os.name != 'posix': monkeypatch.setattr(relay, 'private_path', lambda *a, **k: None)
    binding = {'backend': {'kind': 'host-codex-app-server'},
               'model': {'model_name': 'gpt-6.1-sol', 'timeout_s': 120, 'max_prompt_bytes': 4096}}
    class Catalog:
        def resolve(self, *a, **k): return binding
    class Backend:
        calls = 0
        async def __call__(self, bound, request):
            self.calls += 1
            error = BrokenPipeError('sensitive exception text stays out of diagnostics')
            error.backend_receipt = relay.CapturedBackendReceipt(relay.LocalModelRelay._unknown(),
                b'partial original stdout', 'carrier_error', stderr=b'private stderr',
                observation={'phase': 'stdin_write', 'exception_class': 'BrokenPipeError', 'errno': 32})
            raise error
    runtime = tmp_path / 'private'; runtime.mkdir(mode=0o700)
    backend = Backend(); owner = relay.LocalModelRelay(Catalog(), runtime, backend=backend)
    request = dict(request_id='offline-carrier-failure', endpoint_id='fixture', binding_sha256='a'*64,
                   model='gpt-6.1-sol', prompt='public fixture', timeout_s=30)
    try:
        result = await owner.invoke(request)
        assert result['outcome'] == 'outcome_unknown'
        stem = hashlib.sha256(request['request_id'].encode()).hexdigest()
        assert (runtime/'backend-receipts'/f'{stem}.receipt').read_bytes() == b'partial original stdout'
        assert (runtime/'backend-receipts'/f'{stem}.stderr').read_bytes() == b'private stderr'
        diagnostic = json.loads((runtime/'backend-receipts'/f'{stem}.json').read_text())
        assert diagnostic['transport_observation']['phase'] == 'stdin_write'
        assert diagnostic['requested_timeout_s'] == 30
        assert 'sensitive' not in json.dumps(diagnostic)
        assert await owner.invoke(request) == result
        with pytest.raises(ResearchError, match='DELIVERY_UNKNOWN'):
            await owner.invoke(dict(request, request_id='different-id'))
        assert backend.calls == 1
    finally: owner.close()

