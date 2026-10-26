import json

import pytest

from benchmarks.harbor_suite.value_host import complete, validate_request
from benchmarks.harbor_suite.value_schedule import Schedule


def request():
    return {'schema': 'native-value-completion-request:1', 'request_id': 'a' * 32,
            'prompt': 'Public task', 'timeout_s': 30, 'model': 'gpt-6.1-sol',
            'reasoning_effort': 'medium'}


def test_request_identity_and_policy():
    value = request()
    assert validate_request(value, 'a' * 32 + '.request.json') == value
    for change in ({'request_id': '../escape'}, {'model': 'fallback'}, {'reasoning_effort': 'low'},
                   {'timeout_s': float('nan')}, {'timeout_s': True}):
        with pytest.raises(ValueError):
            validate_request(value | change, 'a' * 32 + '.request.json')


@pytest.mark.asyncio
async def test_receipt_saved_and_verified_before_success(tmp_path, monkeypatch):
    from jiuwenswarm.research import local_model_codex, local_models
    binary = tmp_path / 'codex.exe'
    binary.write_bytes(b'fixture binary')
    ledger = Schedule.create(tmp_path / 'budget.sqlite3')
    ledger.reserve('pair', 'b' * 64, {'native-skills': 1, 'cc': 1})
    original = {'outcome': 'completed', 'response_text': 'original wire bytes'}
    async def execute(payload):
        assert ledger.status()['calls_consumed'] == 1
        return original
    def validate(raw, binding, *, prompt):
        assert raw == 'original wire bytes' and prompt == 'Public task'
        return ({'outcome': 'completed', 'reasoning_effort': 'medium', 'error_code': None},
                {'identity': {'effective': 'gpt-6.1-sol'}, 'usage': {'input_tokens': 10}}, 'answer')
    monkeypatch.setattr(local_model_codex, 'execute_async', execute)
    monkeypatch.setattr(local_models, 'native_codex_response', validate)
    try:
        result = await complete(request(), binary=binary, working=tmp_path, fingerprint='c' * 64,
                                ledger=ledger, pair='pair', arm='native-skills', private=tmp_path)
        assert result['text'] == 'answer'
        assert ledger.status()['attempts'][0]['state'] == 'completed'
        assert json.loads((tmp_path / ('a' * 32 + '.receipt.json')).read_text()) == original
    finally:
        ledger.close()


@pytest.mark.asyncio
async def test_invalid_receipt_preserves_unknown_and_blocks_dispatch(tmp_path, monkeypatch):
    from jiuwenswarm.research import local_model_codex, local_models
    binary = tmp_path / 'codex.exe'
    binary.write_bytes(b'fixture binary')
    ledger = Schedule.create(tmp_path / 'budget.sqlite3')
    ledger.reserve('pair', 'b' * 64, {'native-skills': 1, 'cc': 1})
    async def execute(payload):
        return {'outcome': 'completed', 'response_text': 'unverifiable'}
    def invalid(*args, **kwargs):
        raise ValueError('bad receipt')
    monkeypatch.setattr(local_model_codex, 'execute_async', execute)
    monkeypatch.setattr(local_models, 'native_codex_response', invalid)
    try:
        result = await complete(request(), binary=binary, working=tmp_path, fingerprint='c' * 64,
                                ledger=ledger, pair='pair', arm='native-skills', private=tmp_path)
        assert result['status'] == 'outcome_unknown'
        with pytest.raises(ValueError, match='unknown'):
            ledger.claim('pair', 'cc', 'next')
    finally:
        ledger.close()
