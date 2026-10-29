"""Truthful no-node display; real allocated/qualified provenance, controlled assets.

No test creates an accepted output, a fake Compiler/plan, or a new stage.
"""
import asyncio
import copy
import hashlib
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.control import ResearchService
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_finite_e1 import finite_execution_fixture


@asynccontextmanager
async def finite_service(tmp_path, *, selected=True):
    store, owner, protected, inputs, scheduler, prompts = await finite_execution_fixture(tmp_path, 'valid')
    context = copy.deepcopy(protected)
    if not selected:
        context.pop('finite_e1_binding_ref')
        context['invalid_for_product'] = True  # A marker must confer no selection.
    service = ResearchService(store, registry=scheduler.runner.registry, model=scheduler.runner.model,
        profiles=owner._component_profiles, binder=scheduler.binder, scheduler=scheduler,
        finite_e1=owner if selected else None)
    service.configure_workspace('owner', 'work', **context)
    principal = Principal('owner', frozenset({'work'}), frozenset({'submit', 'status', 'reconcile', 'export'}))
    value = SimpleNamespace(store=store, owner=owner, protected=protected, inputs=inputs,
        scheduler=scheduler, prompts=prompts, service=service, principal=principal)
    try:
        yield value
    finally:
        tasks = tuple(service._tasks.values())
        for task in tasks:
            if not task.done(): task.cancel()
        if tasks: await asyncio.gather(*tasks, return_exceptions=True)
        store.close()


async def allocate(f, *, request='status-request', changed_request=False):
    submission = copy.deepcopy(f.store.get_run('run:finite-visible')['submission'])
    if changed_request:
        intake = f.store.read_record(submission['intake_ref'], contract_id='qualified-intake')
        ids = [f.store.read_record(ref, contract_id='client-upload')['id'] for ref in intake['upload_refs']]
        text = f.store.read_blob(intake['request_ref']).decode('utf-8') + ' Changed after preregistration.'
        submission['intake_ref'] = await f.service.ingest(f.principal, text, ids, workspace_id='work')
    submission['client_request_id'] = request
    return await f.service.submit(f.principal, submission), submission


async def stop_before_execution(f):
    # submit/get contain no yielding operation after scheduling, so this cancels
    # the real coordinator before its first turn, not an already-started effect.
    tasks = tuple(f.service._tasks.values())
    for task in tasks: task.cancel()
    if tasks: await asyncio.gather(*tasks, return_exceptions=True)
    assert not f.prompts
    assert not list(f.store.iter_records(kinds=('dispatch-start', 'gate-decision', 'acceptance-commit', 'model-call-start')))


def selection_rows(f, run_id):
    return list(f.store.iter_records(run_id=run_id, kinds=('finite-e1-run-selection',)))


@pytest.mark.asyncio
async def test_actual_selected_pending_status_and_duplicate_are_empty_without_get_effects(tmp_path):
    async with finite_service(tmp_path) as f:
        first, submission = await allocate(f)
        assert first['stage'] == '' and first['node_statuses'] == []
        assert first['status'] == 'in_progress' and first['accepted_refs'] == []
        rows = selection_rows(f, first['run_id'])
        assert len(rows) == 1 and rows[0]['record']['invalid_for_product'] is True
        original_records = list(f.store.iter_records())
        changes = f.store.connection.total_changes
        def forbidden(*args, **kwargs):
            raise AssertionError('GET must not qualify or check current eligibility')
        f.owner.qualify = forbidden
        f.owner.library.eligible_association = forbidden
        duplicate = await f.service.submit(f.principal, submission)
        assert duplicate == first
        assert await f.service.get(f.principal, first['run_id']) == first
        assert await f.service.list(f.principal, client_request_id=submission['client_request_id']) == [first]
        assert list(f.store.iter_records()) == original_records
        assert f.store.connection.total_changes == changes and not f.prompts
        assert len(selection_rows(f, first['run_id'])) == 1


@pytest.mark.asyncio
async def test_selected_pending_history_survives_current_owner_workspace_and_model_loss(tmp_path):
    async with finite_service(tmp_path) as f:
        first, _ = await allocate(f)
        await stop_before_execution(f)
        f.service.finite_e1 = f.service.profiles = f.service.model = None
        f.service._workspaces.clear()
        before = list(f.store.iter_records()); changes = f.store.connection.total_changes
        status = await f.service.get(f.principal, first['run_id'])
        assert status['stage'] == '' and status['node_statuses'] == []
        assert status['status'] == 'in_progress' and status['reasons'] == []
        assert list(f.store.iter_records()) == before and f.store.connection.total_changes == changes
        assert not f.prompts


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['qualified', 'rejected'])
async def test_genuine_legacy_qualification_without_selection_reads_after_owner_loss(tmp_path, outcome):
    async with finite_service(tmp_path) as f:
        # Use the existing actual allocated finite fixture for qualified history;
        # rejected history originates a fresh changed-request service allocation.
        if outcome == 'qualified':
            run_id = 'run:finite-visible'
            receipt = f.owner.qualify(run_id, f.protected)
        else:
            status, _ = await allocate(f, changed_request=True)
            run_id = status['run_id']; await stop_before_execution(f)
            result = await f.owner.execute(run_id, f.protected, scheduler=f.scheduler)
            assert result['status'] == 'halted'
            receipt = result['qualification_ref']
            # This is the old-path reader control, so remove only the newly
            # introduced optional display index in the test's owned SQLite.
            with f.store.transaction() as db:
                db.execute("DELETE FROM records WHERE kind='finite-e1-run-selection' AND run_id=?", (run_id,))
        original = f.store.read_record(receipt)
        assert original['status'] == outcome
        assert len(original['results']) == 9 and not f.prompts
        assert not selection_rows(f, run_id)
        f.service.finite_e1 = f.service.profiles = f.service.model = None
        f.service._workspaces.clear()
        before = list(f.store.iter_records()); changes = f.store.connection.total_changes
        status = await f.service.get(f.principal, run_id)
        assert status['stage'] == '' and status['node_statuses'] == []
        assert status['status'] == ('halted' if outcome == 'rejected' else 'in_progress')
        assert status['reasons'] == (['finite_fixture'] if outcome == 'rejected' else [])
        assert list(f.store.iter_records()) == before and f.store.connection.total_changes == changes
        assert not f.prompts


@pytest.mark.asyncio
async def test_selected_actual_rejection_preserves_reason_and_no_compiler_stage(tmp_path):
    async with finite_service(tmp_path) as f:
        first, _ = await allocate(f, changed_request=True)
        tasks = tuple(f.service._tasks.values())
        if tasks: await asyncio.gather(*tasks)
        status = await f.service.get(f.principal, first['run_id'])
        receipt = list(f.store.iter_records(run_id=first['run_id'], kinds=('finite-e1-fixture-qualification',)))
        assert len(receipt) == 1 and receipt[0]['record']['status'] == 'rejected'
        assert status['stage'] == '' and status['node_statuses'] == []
        assert status['status'] == 'halted' and status['reasons'] == ['finite_fixture']
        assert not f.prompts and not list(f.store.iter_records(kinds=('dispatch-start', 'gate-decision', 'acceptance-commit')))


@pytest.mark.asyncio
async def test_profile_and_invalid_markers_alone_keep_ordinary_preplan_projection(tmp_path):
    async with finite_service(tmp_path, selected=False) as f:
        status, _ = await allocate(f)
        assert status['stage'] == 'intention_compiler' and status['node_statuses'] == []
        assert not selection_rows(f, status['run_id']) and not f.prompts


def original_selection(f, run_id):
    run = f.store.get_run(run_id); submission = run['submission']
    return {'schema': 'ai4r-finite-e1-run-selection:1',
        'id': 'finite-selection:'+hashlib.sha256(json_bytes([run_id, f.owner.binding_ref, submission['intake_ref']])).hexdigest(),
        'run_id': run_id, 'account_id': run['account_id'], 'workspace_id': run['workspace_id'],
        'submission_sha256': hashlib.sha256(json_bytes(submission)).hexdigest(),
        'binding_ref': f.owner.binding_ref, 'configuration_ref': submission['configuration_ref'],
        'intake_ref': submission['intake_ref'], 'evaluation_binding_ref': f.store.evaluation_binding(run_id)['ref'],
        'invalid_for_product': True}


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['account', 'workspace', 'submission_hash', 'binding', 'evaluation', 'extra', 'missing_origin', 'false_origin', 'duplicate'])
async def test_foreign_or_corrupt_private_selection_is_unavailable_without_get_writes(tmp_path, fault):
    async with finite_service(tmp_path) as f:
        run_id = 'run:finite-visible'
        value = original_selection(f, run_id)
        if fault == 'account': value['account_id'] = 'foreign'
        elif fault == 'workspace': value['workspace_id'] = 'foreign'
        elif fault == 'submission_hash': value['submission_sha256'] = '0'*64
        elif fault == 'binding': value['binding_ref'] = f.store.put_blob(b'foreign binding')
        elif fault == 'evaluation': value['evaluation_binding_ref'] = f.store.put_blob(b'foreign evaluation')
        elif fault == 'extra': value['caller_authority'] = True
        elif fault == 'missing_origin': value.pop('invalid_for_product')
        elif fault == 'false_origin': value['invalid_for_product'] = False
        f.store.append_record('finite-e1-run-selection', value)
        if fault == 'duplicate':
            f.store.append_record('finite-e1-run-selection', dict(value, id=value['id']+'-duplicate'))
        before = list(f.store.iter_records()); changes = f.store.connection.total_changes
        with pytest.raises(ResearchError): await f.service.get(f.principal, run_id)
        assert list(f.store.iter_records()) == before and f.store.connection.total_changes == changes
        assert not f.prompts


@pytest.mark.asyncio
@pytest.mark.parametrize('representation', ['record', 'blob', 'wrapper'])
async def test_actual_selection_material_is_excluded_and_not_publicly_exported(tmp_path, representation):
    async with finite_service(tmp_path) as f:
        first, _ = await allocate(f)
        rows = selection_rows(f, first['run_id']); assert len(rows) == 1
        original = rows[0]['ref']
        ref = original if representation == 'record' else f.store.put_blob(f.store.read_blob(original))
        if representation == 'wrapper': ref = f.store.put_blob(json_bytes({'wrapped_display_selection': ref}))
        before = list(f.store.iter_records())
        with pytest.raises(ResearchError, match='evaluation_only'): f.store.require_product_material([ref])
        actor = Principal('operator', operations=frozenset({'library_admit'}))
        with pytest.raises(ResearchError, match='evaluation_only'):
            await f.owner.library.admit(ref, {}, actor, memory_mb=64)
        manifest = await f.service.artifact(f.principal, first['run_id'])
        assert original not in manifest['artifact_refs'] and ref not in manifest['artifact_refs']
        assert list(f.store.iter_records()) == before and not f.prompts


@pytest.mark.asyncio
async def test_actual_finite_node_projection_remains_the_real_node(tmp_path):
    async with finite_service(tmp_path) as f:
        result = await f.owner.execute('run:finite-visible', f.protected, scheduler=f.scheduler)
        assert result['status'] == 'completed'
        status = await f.service.get(f.principal, 'run:finite-visible')
        assert status['stage'] == 'screening'
        assert status['node_statuses'][0]['lifecycle_status'] == 'Completed'
        assert len(f.prompts) == 3 and len(status['accepted_refs']) == 2
