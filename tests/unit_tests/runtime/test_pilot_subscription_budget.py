import os
from pathlib import Path

import pytest

from jiuwenswarm.research.pilot_budget import PilotBudget, prepare
from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError
from tests.unit_tests.runtime.test_codex_subscription import FakeTransport


@pytest.mark.asyncio
async def test_governed_attempt_guard_uses_explicit_model_and_has_no_hidden_retry(tmp_path, monkeypatch):
    directory = tmp_path / 'budget';prepare(directory, 'pilot', max_calls=1)
    monkeypatch.setenv('AI4R_PILOT_BUDGET_DIRECTORY', str(directory))
    transport = FakeTransport();service = SubscriptionService(tmp_path / 'account', transport=transport)
    result = await service.invoke_governed('Return a value', model='gpt-6-luna', timeout_s=1)
    assert result['identity']['effective'] == 'gpt-6-luna'
    with pytest.raises(CodexError, match='PILOT_BUDGET_EXHAUSTED'):
        await service.invoke_governed('Again', model='gpt-6-luna', timeout_s=1)
    assert len([m for m,_ in transport.calls if m=='turn/start']) == 1
    budget=PilotBudget(directory)
    try:
        assert budget.inspect()['attempts']==1 and budget.inspect()['outcomes']=={'completed':1}
    finally:budget.close()


@pytest.mark.asyncio
async def test_failed_attempt_is_charged_and_unspecified_model_cannot_fallback(tmp_path, monkeypatch):
    directory=tmp_path/'budget';prepare(directory,'pilot',max_calls=1)
    monkeypatch.setenv('AI4R_PILOT_BUDGET_DIRECTORY',str(directory))
    transport=FakeTransport();transport.fail_turn=True
    service=SubscriptionService(tmp_path/'account',transport=transport)
    with pytest.raises(CodexError,match='PILOT_BUDGET_UNAVAILABLE'):
        await service.invoke_governed('No implicit default', timeout_s=1)
    with pytest.raises(CodexError,match='RUNTIME_ERROR'):
        await service.invoke_governed('Failure',model='gpt-6-luna',timeout_s=1)
    with pytest.raises(CodexError,match='PILOT_BUDGET_EXHAUSTED'):
        await service.invoke_governed('No retry',model='gpt-6.1-sol',timeout_s=1)
    budget=PilotBudget(directory)
    try:assert budget.inspect()['attempts']==1 and budget.inspect()['outcomes']=={'CodexError':1}
    finally:budget.close()
