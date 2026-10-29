"""Ordinary proof9 via bounded finite canonical runs; no full science claim."""
import asyncio
import copy

import pytest

from jiuwenswarm.research.contracts import ResearchError,validate
from jiuwenswarm.research.state import SQLiteRunStore
from tests.unit_tests.research.inspection_fixture import inspect_ordinary
from tests.unit_tests.research.test_finite_e1 import finite_execution_fixture

RUN='run:finite-visible'


async def completed_finite(root,fault='valid'):
    store,owner,protected,inputs,scheduler,prompts=await finite_execution_fixture(root,fault)
    result=await owner.execute(RUN,protected,scheduler=scheduler)
    assert result['status']==('completed' if fault=='valid' else 'partial')
    plan_ref=result['plan_ref']; plan=store.read_record(plan_ref,contract_id='run-plan')
    assert [n['node_id'] for n in plan['nodes']]==['screening']
    qualified=list(store.iter_records(run_id=RUN,kinds=('finite-e1-fixture-qualification',)))
    assert qualified and qualified[-1]['record']['status']=='qualified'
    rows=list(store.iter_records(run_id=RUN,kinds=('dispatch-record',))); assert len(rows)==1
    dispatch_ref=rows[0]['ref']; dispatch=rows[0]['record']; validate('dispatch-record',dispatch)
    assert dispatch['phase']=='planned' and dispatch['run_plan_ref']==plan_ref
    parent_ref=dispatch['node_contract_ref']; parent=store.read_record(parent_ref,contract_id='node-execution-contract')
    assert (parent['run_id'],parent['node_id'],parent['attempt_id'])==(RUN,'screening','screening-a1')
    assert dispatch['gate_decision_ref'] is not None
    gate=store.read_record(dispatch['gate_decision_ref'],contract_id='gate-decision')
    assert gate['scope_kind']=='node' and gate['contract_ref']==parent_ref
    accepted=store.accepted_outputs(RUN,'screening')
    if fault=='valid':
        assert len(prompts)==3 and set(accepted)=={'screening_result','opportunity_card'}
        assert dispatch['outcome']=='accepted' and gate['action']=='advance'
        assert dispatch['output_gate_decision_refs']==gate['internal_decision_refs']
        decisions=[store.read_record(ref,contract_id='gate-decision') for ref in gate['internal_decision_refs']]
        assert len(decisions)==2 and {d['output_port'] for d in decisions}==set(accepted)
        assessment_refs=[d['assessment_ref'] for d in decisions]
        assert all(assessment_refs) and len({(ref['id'],ref['sha256']) for ref in assessment_refs})==2
        for decision in decisions:
            assert (decision['run_id'],decision['node_id'],decision['attempt_id'])==(RUN,'screening','screening-a1')
            assert decision['scope_kind']=='subnode' and decision['node_contract_ref']==parent_ref
            assert decision['output_refs']==[accepted[decision['output_port']]]
            assessment_ref=decision['assessment_ref']
            assert store.record_kind(assessment_ref)=='verifier-assessment'
            assessment=store.read_record(assessment_ref,contract_id='verifier-assessment')
            review=store.read_record(assessment['review_context_ref'],contract_id='review-context')
            checked_plan=store.read_record(decision['check_plan_ref'],contract_id='bound-check-plan')
            assert assessment['subject_ref']==review['subject_ref']==decision['output_refs'][0]
            assert review['node_contract_ref']==checked_plan['node_contract_ref']==parent_ref
            assert review['contract_ref']==checked_plan['contract_ref']==decision['contract_ref']
            assert review['check_plan_ref']==decision['check_plan_ref']
            assert checked_plan['profile_ref']['sha256']==plan['nodes'][0]['check_pins']['checking_profile_sha256']
    else:
        assert not accepted and dispatch['outcome']=='rejected' and gate['action']=='halt'
        assert len(prompts)==(1 if fault=='invalid_score' else 3)
    assert not store.is_accepted(inputs['brief']) and not store.is_accepted(inputs['candidate_set'])
    return store,owner,scheduler,prompts,plan_ref,parent_ref,parent,dispatch_ref,dispatch


def closed(response,parent_ref,parent,plan_ref):
    assert set(response)=={'node_contract_ref','run_plan_ref','run_id','node_id','attempt_id','state','dispatch_ref','source_outcome','cancellation_record'}
    assert response['node_contract_ref']==parent_ref and response['run_plan_ref']==plan_ref
    assert all(response[k]==parent[k] for k in ('run_id','node_id','attempt_id'))


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['valid','invalid_score','review_failure'])
async def test_ordinary_inspector_returns_original_finite_canonical_whole_attempt(tmp_path,fault):
    store,owner,scheduler,prompts,plan_ref,parent_ref,parent,dispatch_ref,dispatch=await completed_finite(tmp_path,fault)
    try:
        raw=store.read_blob(dispatch_ref); response=inspect_ordinary(store,{'node_contract_ref':parent_ref})
        closed(response,parent_ref,parent,plan_ref)
        assert response['state']=='terminal' and response['dispatch_ref']==dispatch_ref
        assert response['source_outcome']==dispatch['outcome'] and response['cancellation_record'] is None
        scheduler.runner.model=None; scheduler.runner._executions.clear(); scheduler.library=None; owner.library=None
        root=store.root; count=len(prompts); store.close(); store=SQLiteRunStore(root,recover=False)
        assert inspect_ordinary(store,{'node_contract_ref':parent_ref})==response
        assert store.read_blob(dispatch_ref)==raw and len(prompts)==count
    finally: store.close()


async def held_finite(root):
    store,owner,protected,_,scheduler,prompts=await finite_execution_fixture(root,'valid',segment=True,injected_fault='hold')
    task=asyncio.create_task(owner.execute(RUN,protected,scheduler=scheduler))
    async def wait_hold():
        while not list(store.iter_records(run_id=RUN,kinds=('fault-injection',))):
            if task.done():
                await task
                pytest.fail('Actual source fixture had no registered hold boundary')
            await asyncio.sleep(.02)
    try:
        await asyncio.wait_for(wait_hold(),60)
        rows=list(store.iter_records(run_id=RUN,kinds=('dispatch-start',))); assert len(rows)==1 and len(prompts)==3
        start=rows[0]['record']; parent_ref=start['node_contract_ref']
        parent=store.read_record(parent_ref,contract_id='node-execution-contract')
        assert parent['node_id']=='screening' and start['run_plan_ref'] is not None
        assert not list(store.iter_records(run_id=RUN,kinds=('dispatch-record',))) and not store.accepted_outputs(RUN,'screening')
        return store,prompts,task,start['run_plan_ref'],parent_ref,parent
    except BaseException:
        task.cancel(); await asyncio.gather(task,return_exceptions=True); store.close()
        raise


async def close_hold(store,task):
    if not task.done(): task.cancel()
    await asyncio.gather(task,return_exceptions=True); store.close()


@pytest.mark.asyncio
async def test_ordinary_inspector_never_uses_completed_mutable_node_without_final_publication(tmp_path):
    store,prompts,task,plan_ref,parent_ref,parent=await held_finite(tmp_path)
    try:
        store.set_node_state(RUN,'screening','completed',attempt_id='screening-a1')
        response=inspect_ordinary(store,{'node_contract_ref':parent_ref}); closed(response,parent_ref,parent,plan_ref)
        assert response['state']=='outcome_unknown' and response['dispatch_ref'] is None
        assert response['source_outcome'] is None and response['cancellation_record'] is None
        assert len(prompts)==3 and not store.accepted_outputs(RUN,'screening')
    finally: await close_hold(store,task)


@pytest.mark.asyncio
@pytest.mark.parametrize('terminal',[False,True],ids=['requested_only','original_terminal_row'])
async def test_ordinary_inspector_joins_exact_original_cancellation_not_fabricated_ref(tmp_path,terminal):
    store,prompts,task,plan_ref,parent_ref,parent=await held_finite(tmp_path)
    try:
        original=store.request_cancellation(RUN,'owner','cancel:i032-original')
        if terminal:
            # Original source lifecycle API/typed row, never a fabricated Ref or cessation proof.
            store.finish_cancellation(RUN,['Original internal candidate evidence retained'])
        expected=store.get_cancellation(RUN,'cancel:i032-original'); validate('client-cancellation',expected)
        assert expected['id']==original['id'] and expected['status']==('terminal' if terminal else 'requested')
        response=inspect_ordinary(store,{'node_contract_ref':parent_ref}); closed(response,parent_ref,parent,plan_ref)
        assert response['state']==('cancelled' if terminal else 'outcome_unknown')
        assert response['cancellation_record']==expected and response['dispatch_ref'] is None
        assert response['source_outcome'] is None and len(prompts)==3
    finally: await close_hold(store,task)


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['gate_kind','commit_identity','dispatch_hash'])
async def test_ordinary_inspector_rejects_corrupted_original_closure(tmp_path,fault):
    store,_,_,prompts,_,parent_ref,_,dispatch_ref,dispatch=await completed_finite(tmp_path)
    try:
        raw=store.read_blob(dispatch_ref)
        if fault=='gate_kind':
            with store.transaction() as db:
                changed=db.execute('UPDATE records SET kind=? WHERE id=?',('foreign-gate',dispatch['gate_decision_ref']['id']))
                assert changed.rowcount==1
        elif fault=='commit_identity':
            with store.transaction() as db:
                changed=db.execute("UPDATE acceptance SET attempt_id=? WHERE run_id=? AND node_id=? AND subnode_id=''",('screening-a9',RUN,'screening'))
                assert changed.rowcount==2
        else: store.blobs.path_for(dispatch_ref['sha256']).write_bytes(raw+b' ')
        with pytest.raises(ResearchError): inspect_ordinary(store,{'node_contract_ref':parent_ref})
        assert len(prompts)==3
        if fault!='dispatch_hash': assert store.read_blob(dispatch_ref)==raw
    finally: store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['extra_field','wrong_hash','private_kind'])
async def test_ordinary_inspector_requires_exact_canonical_parent_request(tmp_path,fault):
    store,_,_,prompts,_,parent_ref,_,_,_=await completed_finite(tmp_path)
    try:
        request={'node_contract_ref':copy.deepcopy(parent_ref)}
        if fault=='extra_field': request['authorized']=True
        elif fault=='wrong_hash': request['node_contract_ref']['sha256']='0'*64
        else:
            request['node_contract_ref']=store.append_record('evaluation-node-context',store.read_record(parent_ref))
            assert store.record_kind(request['node_contract_ref'])=='evaluation-node-context'
        with pytest.raises(ResearchError): inspect_ordinary(store,request)
        assert len(prompts)==3
    finally: store.close()


@pytest.mark.asyncio
async def test_ordinary_inspector_requires_real_frozen_plan_and_dispatch_ownership(tmp_path):
    from tests.integration.research.test_governed_boundary import concrete_screening_parent
    store,_,_,_,prompts,parent_ref,_=await concrete_screening_parent(tmp_path)
    try:
        assert store.record_kind(parent_ref)=='node-execution-contract'
        assert not list(store.iter_records(run_id=RUN,kinds=('run-plan','dispatch-start','dispatch-record')))
        with pytest.raises(ResearchError): inspect_ordinary(store,{'node_contract_ref':parent_ref})
        assert not prompts
    finally: store.close()
