"""Independent original-deadline, terminal-custody and cancellation races.

Controlled status variants exercise host response publication over actual
captured worker measurements; they do not claim three producer outcomes.
"""
import asyncio
import copy
import json
import threading
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_evaluation_authority import source_fixture, capture_runtime, product_state


async def pending_result(root):
    from jiuwenswarm.research.evaluation_provider import PreparedEvaluation
    store, provider, actor, request, prompts = await source_fixture(root)
    owner = provider.resources.bind_runtime(capture_runtime(store, provider, [request]))
    req = owner.accept_request(actor, request, 'E3')
    scope = owner.prepare(req)
    ctx, measurement = await owner.execute(scope)
    starts = [{'ref': e['capture_ref'], 'record': store.read_record(e['capture_ref'])}
        for e in owner.captures(req, 'model_start')]
    calls = provider._model_calls(ctx, measurement, starts, replay=False)
    result = provider._single_result(PreparedEvaluation(ctx, ctx.check_plan_ref, None), measurement, calls)
    result.update(duration_s=0.0, invalid_for_product=True)
    assert result['status'] == 'completed' and len(prompts) == 1
    return store, provider, actor, request, prompts, owner, req, measurement, result, ctx


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['completed', 'failed', 'blocked'])
async def test_every_late_result_is_refused_without_completed_publication(tmp_path, monkeypatch, status):
    import jiuwenswarm.research.evaluation_authority as module
    values = await pending_result(tmp_path)
    store, provider, actor, request, prompts, owner, req, measurement, result, ctx = values
    try:
        before = product_state(store)
        original = store.read_record(req)
        old_clock = module.time
        # Exact first durable wall deadline, plus protected monotonic deadline;
        # no wall-clock sleep or renewed allowance is needed for this control.
        monkeypatch.setattr(module, 'time', SimpleNamespace(
            time_ns=lambda: original['deadline_unix_ns'] + 1,
            monotonic=lambda: owner._deadlines[json_bytes(req).decode()] + 1))
        with pytest.raises(ResearchError):
            owner.terminal(req, result=result | {'status': status}, measurement_refs=[measurement.measurement_ref])
        monkeypatch.setattr(module, 'time', old_clock)
        row = owner._row(req)
        assert row['terminal_ref'] is None and row['state'] != 'completed'
        assert store.read_record(req) == original and len(prompts) == 1 and product_state(store) == before
    finally:
        store.close()


@pytest.mark.asyncio
async def test_orphan_terminal_is_not_returned_by_inspect_or_duplicate_post(tmp_path):
    from jiuwenswarm.research.evaluation_history import EvaluationReader
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        owner = provider.resources.bind_runtime(capture_runtime(store, provider, [request]))
        await provider.single_cc(actor, request)
        row = store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
        req = json.loads(row['request_ref']); terminal = store.read_record(json.loads(row['terminal_ref']))
        # Simulate the old crash window: the row/object exists, but its exact
        # terminal journal publication was never committed.
        with store.transaction() as db:
            db.execute('UPDATE evaluation_requests SET head_ref=?,sequence=? WHERE request_ref=?',
                (json_bytes(terminal['through_event_ref']).decode(), row['sequence'] - 1, row['request_ref']))
        before = product_state(store)
        rejected = []
        try: owner.inspect(req)
        except ResearchError: rejected.append('inspect')
        try: await provider.single_cc(actor, request)
        except ResearchError: rejected.append('duplicate')
        try: EvaluationReader(store, runtime_ref=owner.runtime_ref).get(actor, request['request_id'])
        except ResearchError: rejected.append('history')
        assert rejected == ['inspect', 'duplicate', 'history'], rejected
        assert len(prompts) == 1 and product_state(store) == before
    finally:
        store.close()


@pytest.mark.asyncio
async def test_failed_terminal_event_capture_never_exposes_a_completed_duplicate(tmp_path, monkeypatch):
    values = await pending_result(tmp_path)
    store, provider, actor, request, prompts, owner, req, measurement, result, ctx = values
    try:
        append = store.append_record
        def broken(kind, record, *args, **kwargs):
            if kind == 'evaluation-event' and record.get('kind') == 'terminal':
                raise ResearchError('audit_unavailable', 'Controlled terminal-publication crash')
            return append(kind, record, *args, **kwargs)
        monkeypatch.setattr(store, 'append_record', broken)
        with pytest.raises(ResearchError): owner.terminal(req, result=result, measurement_refs=[measurement.measurement_ref])
        monkeypatch.setattr(store, 'append_record', append)
        try:
            inspected = owner.inspect(req)
        except ResearchError:
            inspected = {}
        assert inspected.get('state') != 'completed' and inspected.get('result_ref') is None
        with pytest.raises(ResearchError): await provider.single_cc(actor, request)
        assert len(prompts) == 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_cancel_and_terminal_compare_current_durable_identity_before_publication(tmp_path, monkeypatch):
    values = await pending_result(tmp_path)
    store, provider, actor, request, prompts, owner, req, measurement, result, ctx = values
    ready, release = threading.Event(), threading.Event()
    worker = None; cancel_task = None
    try:
        before = product_state(store); append = store.append_record
        def paused(kind, record, *args, **kwargs):
            ref = append(kind, record, *args, **kwargs)
            if kind == 'evaluation-terminal' and record.get('state') == 'completed':
                ready.set()
                if not release.wait(8): raise ResearchError('audit_unavailable', 'Controlled race barrier expired')
            return ref
        monkeypatch.setattr(store, 'append_record', paused)
        def finish():
            try: return owner.terminal(req, result=result, measurement_refs=[measurement.measurement_ref])
            except ResearchError as error: return error
        worker = asyncio.create_task(asyncio.to_thread(finish))
        assert await asyncio.wait_for(asyncio.to_thread(ready.wait, 8), 10)
        cancel_task = asyncio.create_task(owner.cancel(req, 'cancel-race-original'))
        done, _ = await asyncio.wait({cancel_task}, timeout=.5)
        cancellation_won = bool(done)
        release.set()
        terminal_result = await asyncio.wait_for(worker, 10)
        cancel_result = await asyncio.gather(cancel_task, return_exceptions=True)
        row = owner._row(req)
        if cancellation_won:
            assert not isinstance(cancel_result[0], BaseException), cancel_result[0]
            assert row['cancel_id'] == 'cancel-race-original'
            assert row['state'] != 'completed', 'A stale terminal snapshot overrode the durable cancellation winner'
            assert owner.inspect(req).get('result_ref') is None
            repeated = await ctx.contain('Controlled repeated containment after cancellation')
            assert repeated == cancel_result[0] and owner._row(req)['cancel_id'] == 'cancel-race-original'
        else:
            # An implementation may linearize terminal first by retaining its
            # lock. A later cancel must not fabricate a different grant/receipt.
            assert not isinstance(terminal_result, ResearchError)
            assert row['state'] == 'completed' and row['cancel_id'] is None
            assert isinstance(cancel_result[0], ResearchError) or cancel_result[0].get('contained') is not True
        assert len(prompts) == 1 and product_state(store) == before
    finally:
        release.set()
        if worker is not None and not worker.done(): await asyncio.gather(worker, return_exceptions=True)
        if cancel_task is not None and not cancel_task.done(): await asyncio.gather(cancel_task, return_exceptions=True)
        store.close()


@pytest.mark.asyncio
async def test_result_capture_time_is_inside_original_terminal_deadline(tmp_path, monkeypatch):
    import jiuwenswarm.research.evaluation_authority as module
    values = await pending_result(tmp_path)
    store, provider, actor, request, prompts, owner, req, measurement, result, ctx = values
    try:
        original = store.read_record(req); append = store.append_record; old_clock = module.time
        def expires(kind, record, *args, **kwargs):
            ref = append(kind, record, *args, **kwargs)
            if kind == 'evaluation-terminal':
                monkeypatch.setattr(module, 'time', SimpleNamespace(
                    time_ns=lambda: original['deadline_unix_ns'] + 1,
                    monotonic=lambda: owner._deadlines[json_bytes(req).decode()] + 1))
            return ref
        monkeypatch.setattr(store, 'append_record', expires)
        with pytest.raises(ResearchError): owner.terminal(req, result=result, measurement_refs=[measurement.measurement_ref])
        monkeypatch.setattr(module, 'time', old_clock)
        assert owner._row(req)['terminal_ref'] is None and len(prompts) == 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_cancel_before_preparation_publishes_stable_original_terminal_and_identity(tmp_path):
    from jiuwenswarm.research.evaluation_history import EvaluationReader
    store, provider, actor, request, prompts = await source_fixture(tmp_path)
    try:
        owner = provider.resources.bind_runtime(capture_runtime(store, provider, [request]))
        req = owner.accept_request(actor, request, 'E3'); before = product_state(store)
        receipt = await owner.cancel(req, 'cancel-before-prepare')
        terminal = owner.inspect(req)
        assert terminal['state'] == 'cancelled' and terminal['result_ref'] is None
        assert terminal['containment_ref'] == receipt['containment_ref']
        row = dict(owner._row(req)); assert row['cancel_id'] == 'cancel-before-prepare'
        assert await owner.cancel(req, 'cancel-before-prepare') == receipt
        assert dict(owner._row(req)) == row
        with pytest.raises(ResearchError): await owner.cancel(req, 'foreign-cancel')
        result = EvaluationReader(store, runtime_ref=owner.runtime_ref).get(actor, request['request_id'])
        assert result['status'] == 'interrupted' and result['result'] is None
        assert prompts == [] and not owner.runner._executions and product_state(store) == before
    finally:
        store.close()
