"""Stopgap: one retry of a definitely failed transient model call.

Live run pl4b (2026-10-29): Builder halted on a provider_error after 7 calls.
Unknown outcomes are never retried; a second failure still halts.
"""
import asyncio
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.runner import InvocationContext, transient_retries

CONTRACT = {'run_id': 'run:1', 'node_id': 'screening', 'subnode_id': 'screening', 'attempt_id': 'screening-a1'}


class _Store:
    def __init__(self, outcomes):
        self.records, self.outcomes = [], outcomes

    def read_record(self, ref, contract_id=None):
        outcome, code = self.outcomes[ref]
        return {'execution_id': 'e', 'invocation_id': 'i', 'id': ref, 'outcome': outcome, 'provider_error_code': code}

    def append_record(self, kind, record):
        self.records.append((kind, record))

    def iter_records(self, run_id=None, kinds=None):
        return [{'kind': k, 'record': r} for k, r in self.records if kinds is None or k in kinds]


def _context(results, *, declaration=None, owner=None):
    """results: per call either ('ok', text) or (outcome, provider_error_code)."""
    store = _Store({'call:%d' % n: r for n, r in enumerate(results, 1) if r[0] != 'ok'})
    calls = []

    async def call(context, text):
        calls.append(context['call_ordinal'])
        kind, value = results[context['call_ordinal'] - 1]
        if kind == 'ok':
            return {'text': value}
        error = RuntimeError(value)
        error.call_ref = 'call:%d' % context['call_ordinal']
        raise error

    runner = SimpleNamespace(store=store, model=SimpleNamespace(call=call), evidence=None, resolve_evaluation_owner=lambda **kw: owner,
                             _executions={'e': {'calls': [], 'invocation_id': 'i', 'declaration': declaration or {}}})
    ctx = object.__new__(InvocationContext)
    ctx._runner, ctx.contract, ctx.execution_id, ctx._ordinal, ctx._retried = runner, CONTRACT, 'e', 0, False
    return ctx, calls, store


def test_failed_transient_call_is_retried_once_with_the_next_ordinal():
    ctx, calls, store = _context([('failed', 'provider_error'), ('ok', 'answer')])
    assert asyncio.run(ctx.model('p')) == 'answer'
    assert calls == [1, 2]
    retry = [r for k, r in store.records if k == 'model-call-retry']
    assert len(retry) == 1 and retry[0]['failed_call_ordinal'] == 1 and retry[0]['reason_code'] == 'provider_error'
    assert transient_retries(store, 'run:1', node_id='screening') == 1


def test_second_failure_halts_and_only_one_retry_is_granted():
    ctx, calls, store = _context([('failed', 'rate_limited'), ('failed', 'provider_error')])
    with pytest.raises(RuntimeError):
        asyncio.run(ctx.model('p'))
    assert calls == [1, 2] and transient_retries(store, 'run:1') == 1


@pytest.mark.parametrize('result', [('outcome_unknown', None), ('failed', 'auth_failed'), ('failed', 'invalid_output')])
def test_unknown_outcomes_and_non_transient_codes_are_never_retried(result):
    ctx, calls, store = _context([result, ('ok', 'never')])
    with pytest.raises(RuntimeError):
        asyncio.run(ctx.model('p'))
    assert calls == [1] and transient_retries(store, 'run:1') == 0


def test_agent_builder_marks_the_error_retryable_instead_of_hiding_a_call():
    declaration = {'identity': {'name': 'research.builder', 'carrier': {'ref': 'builder_agent.py'}},
                   'needs': {'model': {'tool_calling': False}, 'injects': []}}
    ctx, calls, store = _context([('failed', 'provider_error'), ('ok', 'answer')], declaration=declaration)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(ctx.model('p'))
    assert getattr(caught.value, 'retryable', False) is True and calls == [1]
    assert asyncio.run(ctx.model('p')) == 'answer' and calls == [1, 2]


def test_evaluation_owned_calls_keep_their_measured_single_call():
    ctx, calls, store = _context([('failed', 'provider_error'), ('ok', 'never')], owner=object())
    with pytest.raises(RuntimeError):
        asyncio.run(ctx.model('p'))
    assert calls == [1] and transient_retries(store, 'run:1') == 0


def test_retry_record_names_the_failed_call_and_counts_per_subnode_attempt():
    ctx, calls, store = _context([('failed', 'timeout'), ('ok', 'answer')])
    asyncio.run(ctx.model('p'))
    retry = [r for k, r in store.records if k == 'model-call-retry'][0]
    assert retry['failed_call_id'] == 'call:1'
    # host_limits counts the granted retry for exactly this subnode attempt.
    assert transient_retries(store, 'run:1', subnode_id='screening', attempt_id='screening-a1') == 1
    assert transient_retries(store, 'run:1', subnode_id='screening.verifier', attempt_id='screening-a1') == 0
