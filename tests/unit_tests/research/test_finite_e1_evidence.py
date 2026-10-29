"""Failed finite qualification evidence is inspection, never qualification."""
import copy
import hashlib

import pytest

from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.control import ResearchService
from jiuwenswarm.research.finite_evaluation import QUALIFICATION_CHECKS, finite_evidence_refs
from jiuwenswarm.research.intake import qualify_intake
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_finite_e1 import visible_run


async def changed_request_run(tmp_path):
    store,owner,protected,uploads,_,registry,_ = await visible_run(tmp_path)
    actor = Principal('owner',frozenset({'work'}),frozenset({'ingest','submit','status','export'}))
    original = store.get_run('run:finite-visible')
    intake = store.read_record(original['submission']['intake_ref'],contract_id='qualified-intake')
    request = store.read_blob(intake['request_ref']).decode() + '\nChanged actual owned request for rejection evidence.'
    intake_ref = qualify_intake(store,actor,request,[row['id'] for row in uploads],workspace_id='work',
        **{key:protected[key] for key in ('profile_ref','workspace_ref','input_directory_ref')})
    submission = copy.deepcopy(original['submission'])
    submission.update(id='submission:finite-rejected-reader',client_request_id='finite-rejected-reader',intake_ref=intake_ref)
    run_id = 'run:finite-rejected-reader'
    store.create_run(run_id,account_id='owner',workspace_id='work',submission=submission)
    owner._component_profiles.bind_run(run_id,submission,protected,principal=actor)
    return store,owner,protected,actor,registry,run_id


def no_effects(store):
    assert not list(store.iter_records(kinds=('gate-decision','acceptance-commit','model-call','dispatch-start')))
    assert store.connection.execute('SELECT COUNT(*) FROM acceptance').fetchone()[0] == 0


@pytest.mark.asyncio
async def test_rejected_changed_request_exports_actual_original_bytes_without_qualification(tmp_path):
    store,owner,protected,actor,registry,run_id = await changed_request_run(tmp_path)
    try:
        qualification_ref = owner.qualify(run_id,protected)
        qualification = store.read_record(qualification_ref)
        assert qualification['status'] == 'rejected' and qualification['reason'] == 'finite_fixture'
        assert [row['check_id'] for row in qualification['results']] == list(QUALIFICATION_CHECKS)
        assert qualification['results'][0]['outcome'] == 'FAIL'
        intake_ref = store.get_run(run_id)['submission']['intake_ref']
        intake = store.read_record(intake_ref)
        request_ref = intake['request_ref'];request_bytes = store.read_blob(request_ref)
        binding = store.read_record(owner.binding_ref)
        policy_ref = binding['qualification_policy_ref']
        case = store.read_record(policy_ref)['cases'][0]
        assert request_ref['sha256'] != case['request_sha256']
        unrelated = store.put_blob(b'Unrelated ambient bytes are not evidence of this run')
        original_receipt = store.read_blob(qualification_ref)
        evidence = finite_evidence_refs(store,run_id)
        assert evidence['qualification_ref'] == qualification_ref and evidence['plan_binding_ref'] is None
        service = ResearchService(store,registry=registry,model=None)
        manifest,contents = await service.artifact_bytes(actor,run_id)
        assert await service.artifact(actor,run_id) == manifest
        assert all(ref in manifest['artifact_refs'] for ref in (qualification_ref,intake_ref,request_ref))
        assert policy_ref not in manifest['artifact_refs'] and unrelated not in manifest['artifact_refs']
        for item in manifest['files']:
            assert contents[item['path']] == store.read_blob(item['artifact_ref'])
        assert request_bytes in contents.values() and original_receipt in contents.values()
        assert store.read_blob(request_ref) == request_bytes and store.read_blob(qualification_ref) == original_receipt
        assert store.read_record(qualification_ref)['status'] == 'rejected'
        assert not list(store.iter_records(run_id=run_id,kinds=('finite-e1-plan-binding',)))
        no_effects(store)
    finally:
        store.close()


def adversarial_capture(store,owner,protected,run_id,*,qualified):
    """Negative-only forged capture over real owned joins; never execution proof."""
    original_ref = owner.qualify('run:finite-visible',protected)
    result = copy.deepcopy(store.read_record(original_ref))
    assert result['status'] == 'qualified'
    old_run = store.get_run('run:finite-visible');target = store.get_run(run_id)
    old_intake = old_run['submission']['intake_ref'];new_intake = target['submission']['intake_ref']
    old_request = store.read_record(old_intake)['request_ref'];new_request = store.read_record(new_intake)['request_ref']
    def replace(value):
        if value == old_intake:return copy.deepcopy(new_intake)
        if value == old_request:return copy.deepcopy(new_request)
        if isinstance(value,dict):return {key:replace(item) for key,item in value.items()}
        if isinstance(value,list):return [replace(item) for item in value]
        return value
    result = replace(result)
    result.update(id='finite-qualification:'+hashlib.sha256(json_bytes([run_id,owner.binding_ref,new_intake])).hexdigest(),
                  run_id=run_id,intake_ref=new_intake)
    if not qualified:
        result.update(status='rejected',reason='finite_fixture')
        for row in result['results']:
            row.update(outcome='FAIL',reason='Retained rejected qualification for negative inspection control')
    return result


@pytest.mark.asyncio
async def test_qualified_capture_cannot_bypass_frozen_request_hash(tmp_path):
    store,owner,protected,_,_,run_id = await changed_request_run(tmp_path)
    try:
        forged = adversarial_capture(store,owner,protected,run_id,qualified=True)
        assert all(row['outcome'] == 'PASS' for row in forged['results']) and forged['reason'] is None
        intake = store.read_record(forged['intake_ref'])
        case = store.read_record(store.read_record(owner.binding_ref)['qualification_policy_ref'])['cases'][0]
        assert intake['request_ref']['sha256'] != case['request_sha256']
        store.append_record('finite-e1-fixture-qualification',forged)
        with pytest.raises(ResearchError) as error:
            finite_evidence_refs(store,run_id)
        assert error.value.code == 'finite_evidence'
        no_effects(store)
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['uploads','checks','ambient'])
async def test_rejected_capture_preserves_existing_inspection_guards(tmp_path,fault):
    store,owner,protected,_,_,run_id = await changed_request_run(tmp_path)
    try:
        forged = adversarial_capture(store,owner,protected,run_id,qualified=False)
        if fault == 'uploads':
            forged['upload_refs'] = []
        elif fault == 'checks':
            forged['results'].pop()
        else:
            forged['visible_refs'].append(store.put_blob(b'Private ambient bytes outside every pinned visible slot'))
        store.append_record('finite-e1-fixture-qualification',forged)
        with pytest.raises(ResearchError) as error:
            finite_evidence_refs(store,run_id)
        assert error.value.code == 'finite_evidence'
        no_effects(store)
    finally:
        store.close()


@pytest.mark.asyncio
async def test_rejected_export_keeps_authenticated_account_boundary(tmp_path):
    store,owner,protected,_,registry,run_id = await changed_request_run(tmp_path)
    try:
        result = store.read_record(owner.qualify(run_id,protected))
        assert result['status'] == 'rejected'
        foreign = Principal('foreign',frozenset({'work'}),frozenset({'export'}))
        service = ResearchService(store,registry=registry,model=None)
        with pytest.raises(ResearchError) as error:
            await service.artifact_bytes(foreign,run_id)
        assert error.value.code == 'not_found'
        no_effects(store)
    finally:
        store.close()
