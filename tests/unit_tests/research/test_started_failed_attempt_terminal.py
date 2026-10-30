"""A started attempt whose final dispatch failed before any Node Gate is finished.

Real finite Scheduler/Runner fixture; the failure is injected right after the
actual dispatch-start boundary (the live Builder case). Controlled mechanics,
not a qualification claim.
"""
import asyncio
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.control import status_reasons
from jiuwenswarm.research.executor import ExecutorBlocked
from jiuwenswarm.research.runner import CapsuleRunner
from tests.unit_tests.research.inspection_fixture import inspect_ordinary


async def _run_with_failure_after_start(tmp_path, monkeypatch, make_error):
    from tests.unit_tests.research.test_finite_e1 import finite_execution_fixture
    store, owner, protected, _, scheduler, _ = await finite_execution_fixture(tmp_path, 'valid')
    runner = scheduler.runner
    original = runner._await_start

    async def start_then_fail(context, **kwargs):
        result = await original(context, **kwargs)
        raise make_error()

    monkeypatch.setattr(runner, '_await_start', start_then_fail)
    task = asyncio.create_task(owner.execute('run:finite-visible', protected, scheduler=scheduler))
    outcome = (await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 60))[0]
    return store, outcome


def _only(store, kind):
    rows = list(store.iter_records(kinds=(kind,)))
    assert len(rows) == 1, (kind, len(rows))
    return rows[0]['record']


@pytest.mark.asyncio
@pytest.mark.parametrize('error', [ExecutorBlocked('WHOLE_ATTEMPT_RESOURCE_HELD_OR_UNKNOWN'), RuntimeError('secret detail text')],
                         ids=['executor_blocked', 'generic'])
async def test_started_attempt_with_failed_dispatch_and_no_gate_is_terminal(tmp_path, monkeypatch, error):
    store, _ = await _run_with_failure_after_start(tmp_path, monkeypatch, lambda: error)
    try:
        start = _only(store, 'dispatch-start')
        dispatch = _only(store, 'dispatch-record')
        assert dispatch['outcome'] == 'failed' and dispatch['gate_decision_ref'] is None and dispatch['ended_at'] is not None
        assert not list(store.iter_records(kinds=('gate-decision',)))
        result = inspect_ordinary(store, {'node_contract_ref': start['node_contract_ref']})
        assert result['state'] == 'terminal' and result['source_outcome'] == 'failed'
        # The cause record carries identifiers only, never a message.
        cause = _only(store, 'start-failure-cause')
        assert cause['exception_class'] == type(error).__name__ and cause['node_id'] == dispatch['node_id']
        assert cause['attempt_id'] == dispatch['attempt_id']
        if isinstance(error, ExecutorBlocked):
            assert (cause['code'], cause['reason']) == ('ENVIRONMENT_BLOCKED', 'WHOLE_ATTEMPT_RESOURCE_HELD_OR_UNKNOWN')
            reasons = status_reasons({'reason': None}, [{'kind': 'start-failure-cause', 'record': cause}])
            assert reasons == ['start refused in %s: ExecutorBlocked ENVIRONMENT_BLOCKED WHOLE_ATTEMPT_RESOURCE_HELD_OR_UNKNOWN' % cause['node_id']]
        else:
            assert (cause['code'], cause['reason']) == (None, None)
            assert 'secret' not in repr(cause)
            assert 'secret' not in repr(status_reasons({'reason': None}, [{'kind': 'start-failure-cause', 'record': cause}]))
    finally:
        store.close()


@pytest.mark.asyncio
async def test_started_attempt_with_interrupted_dispatch_is_not_terminal(tmp_path, monkeypatch):
    store, _ = await _run_with_failure_after_start(tmp_path, monkeypatch, asyncio.CancelledError)
    try:
        start = _only(store, 'dispatch-start')
        dispatch = _only(store, 'dispatch-record')
        assert dispatch['outcome'] == 'interrupted' and dispatch['ended_at'] is None
        result = inspect_ordinary(store, {'node_contract_ref': start['node_contract_ref']})
        assert result['state'] == 'outcome_unknown'
    finally:
        store.close()


def _capture(error):
    appended = []
    store = SimpleNamespace(
        read_record=lambda ref, **_: {'run_id': 'run:1', 'node_id': 'builder', 'attempt_id': 'builder-a1', 'inputs': []},
        put_record=lambda kind, record, scope=None: {'id': 'dispatch-ref', 'sha256': 'a' * 64},
        append_record=lambda kind, record: appended.append((kind, record)))
    runner = SimpleNamespace(store=store, prepare_node_check_plan=lambda ref: {'id': 'plan', 'sha256': 'b' * 64})
    ref = CapsuleRunner.capture_start_failure(runner, {'id': 'n'}, started_at='2026-10-30T00:00:00Z', elapsed_s=0.1,
                                              error=error, phase='planned')
    assert ref == {'id': 'dispatch-ref', 'sha256': 'a' * 64}
    assert [kind for kind, _ in appended] == ['start-failure-cause']
    return appended[0][1]


def test_capture_start_failure_records_executor_blocked_cause_and_status_shows_it():
    cause = _capture(ExecutorBlocked('WHOLE_ATTEMPT_RESOURCE_HELD_OR_UNKNOWN'))
    assert cause['exception_class'] == 'ExecutorBlocked' and cause['code'] == 'ENVIRONMENT_BLOCKED'
    assert cause['reason'] == 'WHOLE_ATTEMPT_RESOURCE_HELD_OR_UNKNOWN' and cause['dispatch_ref'] == {'id': 'dispatch-ref', 'sha256': 'a' * 64}
    assert status_reasons({'reason': 'x'}, [{'kind': 'start-failure-cause', 'record': cause}]) == [
        'x', 'start refused in builder: ExecutorBlocked ENVIRONMENT_BLOCKED WHOLE_ATTEMPT_RESOURCE_HELD_OR_UNKNOWN']


@pytest.mark.parametrize('error', [RuntimeError('secret path /etc/passwd'), ExecutorBlocked('has spaces and secret text')])
def test_capture_start_failure_never_leaks_messages(error):
    cause = _capture(error)
    assert 'secret' not in repr(cause) and '/etc' not in repr(cause)
    assert cause['reason'] is None
    assert 'secret' not in repr(status_reasons({'reason': None}, [{'kind': 'start-failure-cause', 'record': cause}]))
