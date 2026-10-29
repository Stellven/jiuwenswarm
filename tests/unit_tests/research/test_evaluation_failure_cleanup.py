"""Actual failed carrier/Bridge cleanup, without live model qualification."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.bridge import BridgeError
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.evaluation_authority import EvaluationMeasurementContext
from jiuwenswarm.research.evaluation_provider import PreparedEvaluation
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_evaluation_authority import source_fixture, capture_runtime, product_state
from tests.unit_tests.research.test_evaluation_resource_loss import private_snapshot


async def failed_fixture(root, fault='known'):
    store, provider, actor, request, prompts = await source_fixture(root)
    class FailedTransport:
        async def invoke_governed(self, prompt, *, model, timeout_s):
            prompts.append(prompt)
            raise BridgeError('CONTAINMENT_UNCERTAIN' if fault == 'uncertain' else 'provider_error')
    provider.resources.admitted.runner.model.subscription = FailedTransport()
    owner = provider.resources.bind_runtime(capture_runtime(store, provider, [request]))
    return store, provider, actor, request, prompts, owner


async def measured_failure(root):
    store, provider, actor, request, prompts, owner = await failed_fixture(root)
    ref = owner.accept_request(actor, request, 'E3')
    ctx, measured = await owner.execute(owner.prepare(ref))
    starts = [{'ref': row['capture_ref'], 'record': store.read_record(row['capture_ref'])}
        for row in owner.captures(ref, 'model_start')]
    result = provider._single_result(PreparedEvaluation(ctx, ctx.check_plan_ref, None), measured,
        provider._model_calls(ctx, measured, starts, replay=False))
    result.update(duration_s=store.read_record(measured.measurement_ref)['elapsed_s'], invalid_for_product=True)
    assert measured.status == 'failed' and measured.failure == 'provider_error' and len(prompts) == 1
    return store, provider, actor, request, prompts, owner, ref, measured, result


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['known', 'uncertain'])
async def test_actual_failed_measurement_keeps_exact_non_success_history_after_cleanup(tmp_path, fault):
    store, provider, actor, request, prompts, owner = await failed_fixture(tmp_path, fault)
    try:
        before = product_state(store)
        result = await provider.single_cc(actor, request)
        assert result['status'] == ('failed' if fault == 'known' else 'blocked')
        assert result['reason'] == ('provider_error' if fault == 'known' else 'containment_uncertain')
        row = store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
        ref = json.loads(row['request_ref']); terminal = owner.inspect(ref)
        assert terminal['state'] == ('failed' if fault == 'known' else 'outcome_unknown')
        assert row['cancel_id'] and bool(terminal['containment_ref']) == (fault == 'known')
        if fault == 'known':
            receipt = store.read_record(terminal['containment_ref'])
            assert receipt['cancel_id'] == row['cancel_id'] and receipt['receipts']
            assert all(item['contained'] is True for item in receipt['receipts'])
        measurement = store.read_record(terminal['measurement_refs'][0])
        assert measurement['failure'] == result['reason'] and measurement['status'] == result['status']
        assert measurement['output_refs'] == result['output_refs']
        failure = store.read_record(terminal['failure_ref'])
        assert failure['reason'] == result['reason']
        assert len(prompts) == 1 and len(result['model_calls']) == 1
        assert result['model_calls'][0]['outcome'] == ('failed' if fault == 'known' else 'outcome_unknown')
        captured_before = private_snapshot(store)
        provider.resources = None
        owner.runner._evaluation_owners.clear(); owner.runner.model = None; owner.runner.executor = None
        assert provider.get(actor, request['request_id'])['result'] == result
        assert await provider.single_cc(actor, request) == result
        assert len(prompts) == 1 and private_snapshot(store) == captured_before and product_state(store) == before
    finally:
        store.close()


@pytest.mark.asyncio
async def test_explicit_cancel_before_failure_cleanup_keeps_original_terminal_and_no_response(tmp_path, monkeypatch):
    store, provider, actor, request, prompts, owner = await failed_fixture(tmp_path)
    ready, release = asyncio.Event(), asyncio.Event()
    original = EvaluationMeasurementContext.contain; task = None
    async def held(ctx, reason):
        ready.set()
        await release.wait()
        return await original(ctx, reason)
    monkeypatch.setattr(EvaluationMeasurementContext, 'contain', held)
    try:
        task = asyncio.create_task(provider.single_cc(actor, request))
        await asyncio.wait_for(ready.wait(), 30)
        row = store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
        ref = json.loads(row['request_ref'])
        receipt = await owner.cancel(ref, 'explicit-cancel-before-cleanup')
        release.set()
        with pytest.raises(ResearchError): await asyncio.wait_for(task, 30)
        terminal = owner.inspect(ref)
        assert terminal['state'] == 'cancelled' and terminal['result_ref'] is None
        assert terminal['containment_ref'] == receipt['containment_ref']
        assert owner._row(ref)['cancel_id'] == 'explicit-cancel-before-cleanup'
        assert len(prompts) == 1 and owner.captures(ref, 'measurement')
    finally:
        release.set()
        if task is not None and not task.done(): await asyncio.gather(task, return_exceptions=True)
        store.close()


@pytest.mark.asyncio
async def test_failure_snapshot_cannot_renew_deadline_during_final_measurement_capture(tmp_path, monkeypatch):
    import jiuwenswarm.research.evaluation_authority as module
    store, provider, actor, request, prompts, owner = await failed_fixture(tmp_path)
    append = store.append_record; original_time = module.time
    def expires(kind, record, *args, **kwargs):
        ref = append(kind, record, *args, **kwargs)
        if kind == 'evaluation-trial-measurement':
            row = store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
            request_ref = json.loads(row['request_ref']); actual = store.read_record(request_ref)
            monkeypatch.setattr(module, 'time', SimpleNamespace(
                time_ns=lambda: actual['deadline_unix_ns'] + 1,
                monotonic=lambda: owner._deadlines[json_bytes(request_ref).decode()] + 1))
        return ref
    monkeypatch.setattr(store, 'append_record', expires)
    try:
        with pytest.raises(ResearchError): await provider.single_cc(actor, request)
        monkeypatch.setattr(module, 'time', original_time)
        row = store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
        ref = json.loads(row['request_ref']); terminal = owner.inspect(ref)
        assert terminal['state'] != 'completed' and terminal.get('result_ref') is None
        assert len(prompts) == 1 and owner.captures(ref, 'measurement')
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('forgery', ['successful', 'different_reason'])
async def test_actual_failed_measurement_never_authorizes_forged_response(tmp_path, forgery):
    values = await measured_failure(tmp_path)
    store, provider, actor, request, prompts, owner, ref, measured, result = values
    try:
        forged = copy.deepcopy(result)
        if forgery == 'successful': forged.update(status='completed', reason=None)
        else: forged['reason'] = 'unrelated_failure'
        with pytest.raises(ResearchError):
            owner.terminal(ref, result=forged, measurement_refs=[measured.measurement_ref])
        assert owner.inspect(ref).get('result_ref') is None and len(prompts) == 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_known_provider_failure_and_uncertain_containment_retain_both_original_reasons(tmp_path, monkeypatch):
    store, provider, actor, request, prompts, owner = await failed_fixture(tmp_path, 'mixed')
    bridge = owner.runner.model; capture = bridge._capture
    async def missing_ack(kind, record, *args, **kwargs):
        if kind == 'model-run-contained':
            raise ResearchError('audit_unavailable', 'Controlled actual containment acknowledgment capture failure')
        return await capture(kind, record, *args, **kwargs)
    monkeypatch.setattr(bridge, '_capture', missing_ack)
    try:
        result = await provider.single_cc(actor, request)
        row = store.connection.execute('SELECT * FROM evaluation_requests').fetchone()
        ref = json.loads(row['request_ref']); terminal = owner.inspect(ref)
        assert terminal['state'] == 'outcome_unknown' and terminal['containment_ref'] is None
        assert result['status'] == 'blocked' and result['reason'] == 'containment_uncertain'
        assert result['model_calls'][0]['outcome'] == 'failed' and len(prompts) == 1
        failures = [store.read_record(item['capture_ref'])['reason'] for item in owner.captures(ref, 'failure')]
        assert 'provider_error' in failures and 'containment_uncertain' in failures, failures
        assert provider.get(actor, request['request_id'])['result'] == result
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('join', ['checked_subject', 'basis_assignment'])
async def test_failed_response_rejects_wrong_original_check_subject_or_basis_assignment(tmp_path, join):
    store, provider, actor, request, prompts, owner, ref, measured, result = await measured_failure(tmp_path)
    try:
        raw = store.read_record(measured.measurement_ref)
        checked = copy.deepcopy(store.read_record(measured.deterministic_ref))
        if join == 'checked_subject':
            checked['subject_ref'] = owner._scope(json.loads(owner._row(ref)['scope_ref']))['source_contract_ref']
        else:
            basis = copy.deepcopy(store.read_record(checked['check_plan_ref']))
            basis['id'] += ':wrong-assignment'
            basis['assignment_context_ref'] = owner._scope(json.loads(owner._row(ref)['scope_ref']))['source_contract_ref']
            basis_ref = store.append_record('evaluation-checking-basis', basis)
            owner.register_capture(None, 'check_plan', basis_ref, request_ref=ref)
            checked['check_plan_ref'] = basis_ref
        checked_ref = store.append_record('evaluation-deterministic-check-result', checked)
        owner.register_capture(None, 'deterministic_result', checked_ref, request_ref=ref)
        raw['id'] += ':wrong-check-join'; raw['deterministic_ref'] = checked_ref
        measurement_ref = store.append_record('evaluation-trial-measurement', raw)
        owner.register_capture(None, 'measurement', measurement_ref, request_ref=ref)
        with pytest.raises(ResearchError): owner.terminal(ref, result=result, measurement_refs=[measurement_ref])
        assert owner.inspect(ref).get('result_ref') is None and len(prompts) == 1
    finally:
        store.close()
