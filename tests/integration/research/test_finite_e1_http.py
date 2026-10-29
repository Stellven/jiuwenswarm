"""Actual native intake/HTTP finite run; eligibility and model replies controlled.

This exercises the mounted ASGI service and native message handler, not sockets,
APP/root isolation, live readiness/calibration or full benchmark acceptance.
"""
import asyncio
import copy
import hashlib
import io
import json
import zipfile
from types import SimpleNamespace
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi import FastAPI

from jiuwenswarm.gateway.channel_manager.web.research_http import mount_research_routes, native_research_message
from jiuwenswarm.research.contracts import Principal
from jiuwenswarm.research.control import ResearchService
from jiuwenswarm.research.operator_config import OperatorConfiguration
from jiuwenswarm.research.profiles import EvaluationProfiles
from jiuwenswarm.research.shell_auth import SessionAuthority
from tests.unit_tests.research.test_finite_e1 import finite_execution_fixture


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', ['valid', 'invalid_score', 'review_failure', 'changed_request'])
async def test_native_intake_and_http_submit_execute_one_actual_finite_run(tmp_path, fault):
    store, owner, protected, inputs, scheduler, prompts = await finite_execution_fixture(
        tmp_path, 'valid' if fault == 'changed_request' else fault)
    authority = client = service = None
    try:
        operator = OperatorConfiguration.from_mapping(owner._operator, resolve_profile=store.read_record)
        profiles = EvaluationProfiles(store, operator)
        service = ResearchService(store, registry=scheduler.runner.registry,
            model=scheduler.runner.model, profiles=profiles, compiler=None,
            binder=scheduler.binder, scheduler=scheduler, finite_e1=owner)
        service.configure_workspace('owner', 'work', **protected)
        principal = Principal('owner', frozenset({'work'}), frozenset({
            'submit', 'status', 'reconcile', 'export', 'upload', 'list_uploads', 'readiness'}))
        origin = 'http://testserver'
        authority = SessionAuthority(tmp_path/'native-sessions', origin)
        channel = SimpleNamespace(research_profile=True, research_service=service,
            research_authority=authority, set_handshake_auth=lambda callback: None)
        app = FastAPI()
        mount_research_routes(app, channel)
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=origin)
        challenge = urlsplit(authority.initialize(principal)).fragment.split('=', 1)[1]
        bootstrap = await client.post('/auth/research/bootstrap', json={'challenge': challenge},
            headers={'Origin': origin})
        assert bootstrap.status_code == 200, bootstrap.text
        headers = {'Authorization': 'Bearer '+bootstrap.json()['token']}
        ws = SimpleNamespace(request_headers={'Host': 'testserver', 'Origin': origin,
            'Cookie': authority.cookie_name+'='+client.cookies.get(authority.cookie_name)})

        original = store.get_run('run:finite-visible')['submission']
        original_intake = store.read_record(original['intake_ref'], contract_id='qualified-intake')
        upload_ids = [store.read_record(ref, contract_id='client-upload')['id']
            for ref in original_intake['upload_refs']]
        original_request = store.read_blob(inputs['original_request']).decode('utf-8')
        text = original_request + (' Changed after preregistration.' if fault == 'changed_request' else '')
        preparation_runs = store.list_runs(account_id='owner')
        assert len(preparation_runs) == 1 and not prompts
        assert not list(store.iter_records(kinds=('dispatch-start', 'model-call-start',
            'gate-decision', 'acceptance-commit')))

        handled, captured = await native_research_message(channel, ws, 'chat.send', {
            'content': text, 'workspace_id': 'work', 'upload_refs': upload_ids,
            'user_id': 'client-cannot-select-actor'})
        assert handled and captured['qualified'] is True
        intake = store.read_record(captured['intake_ref'], contract_id='qualified-intake')
        assert intake['user_id'] == 'owner' and intake['upload_refs'] == original_intake['upload_refs']
        assert store.read_blob(intake['request_ref']) == text.encode('utf-8')
        assert store.list_runs(account_id='owner') == preparation_runs and not prompts
        assert not list(store.iter_records(kinds=('dispatch-start', 'model-call-start',
            'gate-decision', 'acceptance-commit')))

        submission = copy.deepcopy(original)
        submission.update(client_request_id='finite-http-'+fault, intake_ref=captured['intake_ref'],
            account_id='untrusted-client-account')
        unauthenticated = await client.post('/api/v1/runs', json=submission)
        assert unauthenticated.status_code == 401
        first, duplicate = await asyncio.gather(*[
            client.post('/api/v1/runs', json=submission, headers=headers) for _ in range(2)])
        assert first.status_code == duplicate.status_code == 200, (first.text, duplicate.text)
        run_id = first.json()['run_id']
        assert duplicate.json()['run_id'] == run_id and run_id != 'run:finite-visible'
        pending = tuple(service._tasks.values())
        if pending:
            await asyncio.wait_for(asyncio.gather(*pending), 75)
        runs = store.list_runs(account_id='owner', request_id=submission['client_request_id'])
        assert len(runs) == 1 and runs[0]['id'] == run_id
        assert store.get_run(run_id)['account_id'] == 'owner'
        assert store.get_run('run:finite-visible')['state'] == 'pending'
        assert not list(store.iter_records(run_id='run:finite-visible', kinds=(
            'dispatch-start', 'model-call-start', 'gate-decision', 'acceptance-commit')))
        binding = store.evaluation_binding(run_id)['record']
        assert binding['invalid_for_product'] is True and binding['evaluation'] == original['evaluation']

        status = await client.get('/api/v1/runs/'+run_id, headers=headers)
        assert status.status_code == 200, status.text
        expected_status = 'halted' if fault == 'changed_request' else 'completed' if fault == 'valid' else 'partial'
        assert status.json()['status'] == expected_status, status.json()
        qualifications = list(store.iter_records(run_id=run_id, kinds=('finite-e1-fixture-qualification',)))
        assert len(qualifications) == 1
        qualification = qualifications[0]['record']
        assert qualification['status'] == ('rejected' if fault == 'changed_request' else 'qualified')
        assert qualification['intake_ref'] == captured['intake_ref']
        plans = list(store.iter_records(run_id=run_id, kinds=('finite-e1-plan-binding',)))
        if fault == 'changed_request':
            assert qualification['reason'] == 'finite_fixture' and not plans
            assert not prompts and not list(store.iter_records(run_id=run_id, kinds=(
                'dispatch-start', 'gate-decision', 'acceptance-commit', 'model-call-start')))
        else:
            assert len(plans) == 1
            plan = store.read_record(plans[0]['record']['plan_ref'], contract_id='run-plan')
            assert [node['cc']['cc_name'] for node in plan['nodes']] == ['research.screening']
            dispatches = list(store.iter_records(run_id=run_id, kinds=('dispatch-record',)))
            assert len(dispatches) == 1 and dispatches[0]['record']['phase'] == 'planned'
            assert dispatches[0]['record']['run_plan_ref'] == plans[0]['record']['plan_ref']
            accepted = store.accepted_outputs(run_id, 'screening')
            assessments = list(store.iter_records(kinds=('verifier-assessment',)))
            if fault == 'valid':
                assert set(accepted) == {'screening_result', 'opportunity_card'}
                assert len(assessments) == 2 and len(prompts) == 3
                assert {(ref['id'], ref['sha256']) for ref in status.json()['accepted_refs']} == {
                    (ref['id'], ref['sha256']) for ref in accepted.values()}
                assert all(store.is_accepted(ref, run_id=run_id) for ref in accepted.values())
            else:
                assert not accepted and not status.json()['accepted_refs']
                assert len(assessments) == (0 if fault == 'invalid_score' else 2)
                assert len(prompts) == (1 if fault == 'invalid_score' else 3)
                assert list(store.iter_records(run_id=run_id, kinds=('gate-decision',)))
                assert not list(store.iter_records(run_id=run_id, kinds=('acceptance-commit',)))
        assert not store.is_accepted(inputs['brief']) and not store.is_accepted(inputs['candidate_set'])
        assert all(row['record']['node_id'] == 'screening'
            for row in store.iter_records(run_id=run_id, kinds=('invocation-observation',)))

        frozen_database = tuple(store.connection.iterdump())
        frozen_calls = len(prompts)
        conflict = await client.post('/api/v1/runs', json=dict(submission, interaction_mode='headless'), headers=headers)
        assert conflict.status_code == 409, conflict.text
        reconciled = await client.get('/api/v1/runs', params={'client_request_id': submission['client_request_id']}, headers=headers)
        assert reconciled.status_code == 200 and reconciled.json() == status.json()
        exported = await client.get('/api/v1/runs/'+run_id+'/export', headers=headers)
        assert exported.status_code == 200, exported.text
        manifest = exported.json()
        assert manifest['run_id'] == run_id and manifest['audience'] == 'researcher'
        assert qualifications[0]['ref'] in manifest['artifact_refs']
        zipped = await client.get('/api/v1/runs/'+run_id+'/export', headers=dict(headers, Accept='application/zip'))
        assert zipped.status_code == 200, zipped.text
        with zipfile.ZipFile(io.BytesIO(zipped.content)) as archive:
            assert json.loads(archive.read('client_retrieval.json')) == manifest
            assert set(archive.namelist()) == {'client_retrieval.json', *[row['path'] for row in manifest['files']]}
            for row in manifest['files']:
                raw = archive.read(row['path'])
                assert hashlib.sha256(raw).hexdigest() == row['artifact_ref']['sha256']
                assert raw == store.read_blob(row['artifact_ref'])
        assert len(prompts) == frozen_calls and tuple(store.connection.iterdump()) == frozen_database
        assert len(store.list_runs(account_id='owner', request_id=submission['client_request_id'])) == 1
    finally:
        if service is not None:
            tasks = tuple(service._tasks.values())
            for task in tasks:
                if not task.done(): task.cancel()
            if tasks: await asyncio.gather(*tasks, return_exceptions=True)
        if client is not None: await client.aclose()
        if authority is not None: authority.close()
        store.close()
