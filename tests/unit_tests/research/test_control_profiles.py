"""Finite evaluation authority; controlled policy/mechanics, no live campaign."""
import asyncio
import copy
import json
from pathlib import Path
import time

import pytest

from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.operator_config import OperatorConfiguration
from jiuwenswarm.research.state import SQLiteRunStore
from tests.unit_tests.research.test_operator_config import valid_config


def capture(tmp_path, *, faults=True):
    from jiuwenswarm.research.profiles import EvaluationProfiles
    store=SQLiteRunStore(tmp_path)
    library=json.loads(Path('tests/fixtures/research/planning/library_snapshot.json').read_bytes())
    snapshot=store.put_record('library-snapshot',library)
    verifier=store.put_record('capsule-declaration',json.loads(Path('/opt/ai4r/jiuwenswarm/research_assets/compiler/verifier.declaration.json').read_bytes()))
    profile={'schema_version':'1.0.0','id':'profile:controlled','profile_id':'controlled:fixed','plan_source':'static',
             'router_enabled':False,'router_version':None,'model_route':'codex-cli-default',
             'library_snapshot_sha256':snapshot['sha256'],'candidate_pins':[],'verifier_cc_ref':verifier,
             'invalid_for_product':faults,'allowed_entry_points':['E1','E4'] if faults else ['E1']}
    profile_ref=store.put_record('evaluation-profile',profile)
    config=valid_config();config['cc']['evaluation_profile_ref']=profile_ref
    operator=OperatorConfiguration.from_mapping(config,resolve_profile=store.read_record)
    configuration_ref=store.append_record('approved-configuration',{'operator':config})
    replacement=store.put_blob(b'{"run_id":"foreign-run","capsule_id":"foreign-capsule"}',media_type='application/json')
    definitions=[{'fault_id':'delay','kind':'delay_gate_persistence','target':{'node_id':'probe','artifact_type':None},
                  'parameters':{'node_id':'probe','delay_s':1},'expected_observation_sha256':'1'*64},
                 {'fault_id':'swap','kind':'swap_artifact','target':{'node_id':'probe','artifact_type':'urn:jiuwenswarm:m1-design:intent-ir:1.0.0'},
                  'parameters':{'node_id':'probe','swap_fixture_id':'foreign'},'expected_observation_sha256':'2'*64}]
    plan=store.append_record('evaluation-fault-plan',{'schema':'ai4r-evaluation-faults:1','id':'faults:fixed',
        'profile_ref':profile_ref,'campaign_id':'controlled','fault_plan':definitions}) if faults else None
    index=store.append_record('evaluation-fixture-index',{'schema':'ai4r-evaluation-fixtures:1','id':'fixtures:fixed',
        'profile_ref':profile_ref,'campaign_id':'controlled','entries':[{'fixture_id':'foreign','artifact_type':'urn:jiuwenswarm:m1-design:intent-ir:1.0.0','artifact_ref':replacement}]}) if faults else None
    registry=EvaluationProfiles(store,operator,fault_plan_ref=plan,fixture_index_ref=index)
    protected={'configuration_ref':configuration_ref,'profile_id':profile['profile_id'],'library_snapshot_ref':snapshot,
        'verifier_cc_ref':verifier,'candidate_pins':[],'plan_source':'static',
        'run_pins':{'app_build':'controlled-build','client_contract_version':'1.0.0','library_snapshot_sha256':snapshot['sha256'],
                    'plan_policy_ref':config['cc']['plan_policy_ref'],'check_bundle_set_sha256':'3'*64,'router_enabled':False,'router_version':None}}
    actor=Principal('owner',frozenset({'work'}),frozenset({'submit','evaluation_profile'}))
    submission={'schema_version':'1.0.0','id':'submission:fixed','client_request_id':'request-1','workspace_id':'work',
                'account_id':'owner','intake_ref':replacement,'configuration_ref':configuration_ref,'plan_source':'static',
                'evaluation':{'campaign_id':'controlled','run_id':'controlled__case__fixed__r01','inventory_id':'inventory'},
                'profile_id':profile['profile_id'],'fault_id':None}
    return store,registry,protected,actor,submission,replacement


def bind(store,registry,protected,actor,submission,fault):
    submission=copy.deepcopy(submission);submission['fault_id']=fault
    registry.validate_submission(submission,protected,principal=actor)
    store.create_run('run:controlled',account_id='owner',workspace_id='work',submission=submission)
    registry.bind_run('run:controlled',submission,protected,principal=actor)
    name='intention_node_contract.json' if fault=='delay' else 'intention_subnode_contract.json'
    contract=json.loads((Path('tests/fixtures/research/router/protected-capture')/name).read_bytes())
    contract.update(run_id='run:controlled',node_id='probe')
    ref=store.put_record('node-execution-contract' if fault=='delay' else 'subnode-execution-contract',contract)
    return ref


def test_profile_rejects_wrong_plan_and_unscoped_fault_before_allocation(tmp_path):
    store,registry,protected,actor,submission,_=capture(tmp_path)
    try:
        for change in [{'profile_id':'unapproved'},{'plan_source':'planned'},{'fault_id':'arbitrary'},
                       {'evaluation':None},{'fault_id':'delay','evaluation':{'campaign_id':'foreign','run_id':'r','inventory_id':'i'}}]:
            with pytest.raises(ResearchError):registry.validate_submission(submission|change,protected,principal=actor)
        ordinary=Principal('owner',frozenset({'work'}),frozenset({'submit'}))
        with pytest.raises(ResearchError) as observed:
            registry.validate_submission(submission|{'fault_id':'delay'},protected,principal=ordinary)
        assert observed.value.code=='auth'
        assert not store.list_runs(account_id='owner',request_id='request-1')
    finally:store.close()


def test_profile_rechecks_snapshot_and_verifier_without_altering_pins(tmp_path):
    store,registry,protected,actor,submission,_=capture(tmp_path)
    try:
        original=copy.deepcopy(protected)
        changed=copy.deepcopy(protected);changed['run_pins']['library_snapshot_sha256']='0'*64
        with pytest.raises(ResearchError):registry.validate_submission(submission,changed,principal=actor)
        changed=copy.deepcopy(protected);changed['verifier_cc_ref']=store.put_blob(b'other verifier')
        with pytest.raises(ResearchError):registry.validate_submission(submission,changed,principal=actor)
        assert protected==original
    finally:store.close()


@pytest.mark.asyncio
async def test_swap_uses_real_foreign_ref_and_preserves_original_bytes(tmp_path):
    store,registry,protected,actor,submission,replacement=capture(tmp_path)
    try:
        contract=bind(store,registry,protected,actor,submission,'swap')
        original=store.put_blob(b'actual worker bytes')
        changed=await registry.after_capture({'run_id':'run:controlled','contract_ref':contract,'output_refs':{'intent':original}})
        assert changed=={'output_refs':{'intent':replacement}}
        assert store.read_blob(original)==b'actual worker bytes'
        assert store.read_blob(replacement).startswith(b'{"run_id":"foreign-run"')
        records=list(store.iter_records(run_id='run:controlled',kinds=('fault-injection',)))
        assert len(records)==1 and records[0]['record']['original_refs']=={'intent':original}
        assert records[0]['record']['replacement_refs']=={'intent':replacement}
        assert not list(store.iter_records(kinds=('gate-decision','acceptance-commit','library-admission')))
    finally:store.close()


@pytest.mark.asyncio
async def test_delay_is_async_cancellable_and_never_writes_gate_or_acceptance(tmp_path):
    store,registry,protected,actor,submission,_=capture(tmp_path)
    try:
        contract=bind(store,registry,protected,actor,submission,'delay')
        task=asyncio.create_task(registry.before_advance({'run_id':'run:controlled','contract_ref':contract,
                                      'node_id':'probe','decision_id':'gate:controlled','deadline_monotonic_s':time.monotonic()+10}))
        await asyncio.sleep(.02);assert not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert not list(store.iter_records(kinds=('gate-decision','acceptance-commit')))
        with pytest.raises(ResearchError) as observed:
            await registry.before_advance({'run_id':'run:controlled','contract_ref':contract,
                                           'node_id':'probe','decision_id':'gate:controlled','deadline_monotonic_s':time.monotonic()+.01})
        assert observed.value.code in {'budget_exhausted','fault_already_claimed'}
    finally:store.close()


def test_source_e1_profile_has_no_fault_authority(tmp_path):
    store,registry,protected,actor,submission,_=capture(tmp_path,faults=False)
    try:
        assert registry.fault_injection is False
        registry.validate_submission(submission,protected,principal=actor)
        with pytest.raises(ResearchError):registry.validate_submission(submission|{'fault_id':'delay'},protected,principal=actor)
    finally:store.close()


def test_binding_names_actual_allocated_submission_and_is_immutable(tmp_path):
    store,registry,protected,actor,submission,_=capture(tmp_path)
    try:
        requested=submission|{'fault_id':'swap'}
        with pytest.raises(ResearchError):
            registry.bind_run('absent',requested,protected,principal=actor)
        store.create_run('run:controlled',account_id='owner',workspace_id='work',submission=requested)
        registry.bind_run('run:controlled',requested,protected,principal=actor)
        registry.bind_run('run:controlled',requested,protected,principal=actor)
        rows=list(store.iter_records(run_id='run:controlled',kinds=('evaluation-run-binding',)))
        assert len(rows)==1
        assert rows[0]['record']['invalid_for_product'] is True
        assert not list(store.iter_records(kinds=('fault-injection',)))
        with pytest.raises(ResearchError):
            registry.bind_run('run:controlled',requested|{'fault_id':'delay'},protected,principal=actor)
    finally:store.close()


@pytest.mark.asyncio
async def test_swap_claim_survives_reopen_and_wrong_node_has_no_effect(tmp_path):
    store,registry,protected,actor,submission,replacement=capture(tmp_path)
    contract=bind(store,registry,protected,actor,submission,'swap')
    original=store.put_blob(b'original worker output')
    try:
        other=store.read_record(contract);other['node_id']='other'
        other_ref=store.put_record('subnode-execution-contract',other)
        assert await registry.after_capture({'run_id':'run:controlled','contract_ref':other_ref,
                                             'output_refs':{'intent':original}})=={'output_refs':{'intent':original}}
        changed=await registry.after_capture({'run_id':'run:controlled','contract_ref':contract,
                                              'output_refs':{'intent':original}})
        assert changed['output_refs']['intent']==replacement
        profile_ref=registry.profile_ref
        fault_plan_ref=registry.fault_plan_ref
        fixture_index_ref=registry.fixture_index_ref
    finally:store.close()
    from jiuwenswarm.research.profiles import EvaluationProfiles
    store=SQLiteRunStore(tmp_path)
    try:
        config=valid_config();config['cc']['evaluation_profile_ref']=profile_ref
        operator=OperatorConfiguration.from_mapping(config,resolve_profile=store.read_record)
        registry=EvaluationProfiles(store,operator,fault_plan_ref=fault_plan_ref,fixture_index_ref=fixture_index_ref)
        with pytest.raises(ResearchError) as observed:
            await registry.after_capture({'run_id':'run:controlled','contract_ref':contract,
                                         'output_refs':{'intent':original}})
        assert observed.value.code=='fault_already_claimed'
        assert len(list(store.iter_records(kinds=('fault-injection',))))==1
    finally:store.close()


@pytest.mark.asyncio
async def test_completed_delay_has_actual_start_and_completion_without_gate_write(tmp_path):
    store,registry,protected,actor,submission,_=capture(tmp_path)
    try:
        contract=bind(store,registry,protected,actor,submission,'delay')
        started=time.monotonic()
        await registry.before_advance({'run_id':'run:controlled','node_id':'probe','contract_ref':contract,
                                      'decision_id':'gate:controlled','deadline_monotonic_s':started+5})
        assert time.monotonic()-started>=1
        rows=list(store.iter_records(run_id='run:controlled',kinds=('fault-injection',)))
        assert len(rows)==1 and rows[0]['record']['kind']=='delay_gate_persistence'
        outcomes=list(store.iter_records(run_id='run:controlled',kinds=('fault-injection-outcome',)))
        assert len(outcomes)==1 and outcomes[0]['record']['outcome']=='completed'
        assert not list(store.iter_records(kinds=('gate-decision','acceptance-commit')))
    finally:store.close()


@pytest.mark.parametrize('change',[
    {'kind':'stale_artifact'},
    {'parameters':{'node_id':'probe','delay_s':0}},
    {'parameters':{'node_id':'probe','delay_s':601}},
    {'parameters':{'node_id':'probe','delay_s':True}},
    {'parameters':{'node_id':'probe','delay_s':1,'client_callback':'forbidden'}},
    {'target':{'node_id':'other','artifact_type':None}},
])
def test_unsupported_or_widened_fault_definition_never_installs(tmp_path,change):
    store,registry,_,_,_,_=capture(tmp_path)
    try:
        from jiuwenswarm.research.profiles import EvaluationProfiles
        plan=store.read_record(registry.fault_plan_ref)
        plan['id']='faults:invalid';plan['fault_plan'][0].update(change)
        invalid=store.append_record('evaluation-fault-plan',plan)
        config=valid_config();config['cc']['evaluation_profile_ref']=registry.profile_ref
        operator=OperatorConfiguration.from_mapping(config,resolve_profile=store.read_record)
        with pytest.raises(ResearchError):
            EvaluationProfiles(store,operator,fault_plan_ref=invalid,fixture_index_ref=registry.fixture_index_ref)
        assert not list(store.iter_records(kinds=('fault-injection',)))
    finally:store.close()


@pytest.mark.asyncio
async def test_fault_definition_corruption_after_binding_blocks_effect(tmp_path):
    store,registry,protected,actor,submission,_=capture(tmp_path)
    try:
        contract=bind(store,registry,protected,actor,submission,'swap')
        original=store.put_blob(b'actual worker output')
        store.blobs.path_for(registry.fault_plan_ref['sha256']).write_bytes(b'changed private definition')
        with pytest.raises(ResearchError) as observed:
            await registry.after_capture({'run_id':'run:controlled','contract_ref':contract,'output_refs':{'intent':original}})
        assert observed.value.code=='integrity_fault'
        assert not list(store.iter_records(kinds=('fault-injection',)))
    finally:store.close()


@pytest.mark.asyncio
async def test_cancellation_propagates_when_last_audit_capture_fails(tmp_path,monkeypatch):
    store,registry,protected,actor,submission,_=capture(tmp_path)
    try:
        contract=bind(store,registry,protected,actor,submission,'delay')
        append=store.append_record
        def fail_outcome(kind,record):
            if kind=='fault-injection-outcome':raise OSError('controlled audit persistence failure')
            return append(kind,record)
        monkeypatch.setattr(store,'append_record',fail_outcome)
        task=asyncio.create_task(registry.before_advance({'run_id':'run:controlled','node_id':'probe',
            'contract_ref':contract,'decision_id':'gate:controlled','deadline_monotonic_s':time.monotonic()+10}))
        await asyncio.sleep(.02);task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert len(list(store.iter_records(kinds=('fault-injection',))))==1
        assert not list(store.iter_records(kinds=('gate-decision','acceptance-commit')))
    finally:store.close()
