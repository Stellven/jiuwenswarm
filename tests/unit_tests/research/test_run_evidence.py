"""Controlled evidence construction; no live-model or qualification claim."""
import hashlib
from pathlib import Path

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.run_evidence import RunEvidence, check_bundle_digest
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_budget_ceiling import installed_library
from tests.unit_tests.research.test_operator_config import valid_config


async def prepared_run(tmp_path):
    store, _, _, library, _, _ = await installed_library(tmp_path)
    policy = store.put_record('plan-policy', __import__('json').loads(Path('tests/fixtures/research/planning/plan_policy.json').read_bytes()))
    config = valid_config(); config['cc']['plan_policy_ref'] = policy
    configuration = store.append_record('controlled-configuration', config)
    protected = {'configuration_ref': configuration, 'plan_source': 'static', 'profile_id': None}
    current = library.current_pins()
    pins = {'app_build': 'controlled-component-build', 'client_contract_version': '1.0.0',
        'library_snapshot_sha256': current['library_snapshot_sha256'], 'plan_policy_ref': policy,
        'check_bundle_set_sha256': current['check_bundle_set_sha256'], 'router_enabled': False, 'router_version': None}
    evidence = RunEvidence(store, library)
    context = evidence.prepare(protected, pins)
    store.create_run('run:evidence', account_id='owner', workspace_id='project', submission={})
    return store, library, evidence, context


@pytest.mark.asyncio
async def test_source_bundle_digest_is_sorted_unique_hash_lines(tmp_path):
    store, library, _, _ = await prepared_run(tmp_path)
    snapshot = store.read_record(library.snapshot())
    expected = hashlib.sha256(''.join(value + '\n' for value in sorted({row['check_pins']['check_bundle_sha256']
        for row in snapshot['entries'] if row['check_pins'] is not None})).encode('utf-8')).hexdigest()
    assert check_bundle_digest(snapshot) == expected
    assert library.current_pins()['check_bundle_set_sha256'] == expected


@pytest.mark.asyncio
async def test_run_start_is_once_and_preplan_bundle_names_missing_evidence(tmp_path):
    store, _, evidence, context = await prepared_run(tmp_path)
    start = evidence.start('run:evidence', context)
    assert evidence.start('run:evidence', context) == start
    assert start['id'] == 'runs/run_evidence/run-start.json'
    captured = store.read_record(start)
    assert captured['configuration_ref'] == context['configuration_ref']
    assert captured['pins'] == context['run_pins']
    assert captured['host_facts']['scope'] == 'application_process'
    bundle_ref = evidence.build('run:evidence')
    bundle = store.read_record(bundle_ref, contract_id='run-bundle')
    assert bundle['status'] == 'in_progress' and bundle['plan_source'] is None and bundle['run_plan_ref'] is None
    assert bundle['pins'] == context['run_pins']
    assert any(item['obligation_id'] == 'run-plan' for item in bundle['missing_evidence'])
    assert bundle['effective_seed'] is None
    assert evidence.build('run:evidence') != bundle_ref


@pytest.mark.asyncio
async def test_bundle_retains_rejected_planner_candidate_and_advisory_diagnostics(tmp_path):
    store, _, evidence, context = await prepared_run(tmp_path)
    try:
        evidence.start('run:evidence', context)
        candidate = store.put_blob(b'{invalid')
        diagnostics = store.put_blob(b'{"advisory":true,"results":[]}')
        event = store.append_record('planner_attempt', {'run_id': 'run:evidence', 'node_id': 'planner',
            'subnode_id': 'planner', 'attempt_id': 'a1', 'ordinal': 1, 'candidate_ref': candidate,
            'diagnostics_ref': diagnostics, 'advisory': True, 'repair_requested': True})
        bundle = store.read_record(evidence.build('run:evidence'), contract_id='run-bundle')
        assert all(ref in bundle['artifact_refs'] for ref in (event, candidate, diagnostics))
        assert not store.is_accepted(candidate)
    finally:
        store.close()


@pytest.mark.asyncio
async def test_terminal_capture_preserves_actual_logs_and_unknown_call_omission(tmp_path):
    store, _, evidence, context = await prepared_run(tmp_path)
    evidence.start('run:evidence', context)
    store.append_record('escalation', {'id': 'stop:actual', 'run_id': 'run:evidence', 'reason_code': 'controlled_failure'})
    store.append_record('model-call-start', {'id': 'start:uncertain', 'run_id': 'run:evidence', 'call_id': 'call:unknown'})
    store.set_run_state('run:evidence', 'halted', reason='controlled_failure')
    bundle_ref = evidence.finish('run:evidence')
    bundle = store.read_record(bundle_ref, contract_id='run-bundle')
    assert bundle['status'] == 'halted'
    assert bundle['model_call_refs'] == []
    assert any(item['obligation_id'] == 'model-call:call:unknown' for item in bundle['missing_evidence'])
    logs = [ref for ref in bundle['artifact_refs'] if ref['id'].endswith('/run-end/run-log.jsonl')]
    assert len(logs) == 1 and b'controlled_failure' in store.read_blob(logs[0])
    assert any(item['obligation_id'] == 'run-trace' for item in bundle['missing_evidence'])


@pytest.mark.asyncio
async def test_node_gate_original_bytes_are_copied_to_the_source_folder_and_bundle(tmp_path):
    import json
    store,_,evidence,context=await prepared_run(tmp_path);evidence.start('run:evidence',context)
    gate=json.loads(Path('tests/fixtures/research/pipeline/source-valid/gate_science_node_pass.json').read_bytes())
    gate['run_id']='run:evidence'
    ref=store.put_record('gate-decision',gate)
    captured=evidence.capture_node_gate(ref)
    assert captured['id']=='runs/run_evidence/evaluation/evaluation-a1/node-gate/decision.json'
    assert store.read_blob(captured)==store.read_blob(ref)
    bundle=store.read_record(evidence.build('run:evidence'))
    assert captured in bundle['artifact_refs']


@pytest.mark.asyncio
async def test_original_prompt_file_is_durable_before_actual_bridge_authorization(tmp_path,monkeypatch):
    from jiuwenswarm.research.runner import CapsuleRunner
    from jiuwenswarm.research.state import SQLiteRunStore
    from tests.unit_tests.research.test_compiler import test_compiler_requires_internal_acceptance_and_commits_one_external_brief
    original_init=CapsuleRunner.__init__;original_authorize=CapsuleRunner.authorize_model_context;before=[]
    def initialize(self,*args,**kwargs):original_init(self,*args,**kwargs);self.evidence=RunEvidence(self.store,None)
    def authorize(self,context):
        execution=self._executions[context['execution_id']];contract=execution['contract']
        prefix='/'.join(['runs',contract['run_id'].replace(':','_'),contract['node_id'],contract['attempt_id'],contract['subnode_id']])
        ref=self.store.record_ref(prefix+'/prompt.txt')
        assert self.store.read_blob(ref)
        before.append(ref)
        return original_authorize(self,context)
    monkeypatch.setattr(CapsuleRunner,'__init__',initialize);monkeypatch.setattr(CapsuleRunner,'authorize_model_context',authorize)
    await test_compiler_requires_internal_acceptance_and_commits_one_external_brief(tmp_path,None,'fixed_baseline')
    assert len(before)==4
    store=SQLiteRunStore(tmp_path,recover=False)
    observations=list(store.iter_records(kinds=('invocation-observation',)))
    assert all(any(ref in row['record']['trace_refs'] for ref in before) for row in observations)


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',[None,'scope','sequence','direction','kind'])
async def test_native_trace_copies_original_packets_and_rejects_swapped_capture(tmp_path,fault):
    store,_,evidence,context=await prepared_run(tmp_path);evidence.start('run:evidence',context)
    contract=store.put_blob(b'actual private test contract')
    observation={'run_id':'run:evidence','node_id':'intent','subnode_id':'worker','attempt_id':'a1','contract_ref':contract}
    start=store.append_record('model-call-start',{'id':'start:trace','run_id':'run:evidence','invocation_id':'inv:trace','execution_id':'exec:trace','call_id':'call:trace','contract_ref':contract})
    scope={**observation,'invocation_id':'inv:trace','execution_id':'exec:trace','call_id':'call:trace','model_call_start_ref':start}
    packet=b'  { "method" : "turn/completed", "params": {} }\r\n'
    raw=store.put_blob(packet)
    event={'schema':'ai4r-native-governed-trace-event:1','scope':dict(scope),'sequence':0,'direction':'in','method':'turn/completed','raw_ref':raw}
    if fault=='scope':event['scope']['call_id']='call:foreign'
    elif fault=='sequence':event['sequence']=1
    elif fault=='direction':event['direction']='unknown'
    event_ref=store.append_record('untrusted-copy' if fault=='kind' else 'native-governed-trace-event',event)
    summary=store.append_record('native-governed-trace',{'schema':'ai4r-native-governed-trace:1','scope':scope,'status':'completed','event_refs':[event_ref]})
    from jiuwenswarm.research.bridge import observed_usage
    from jiuwenswarm.research.state import utc_now
    call=store.put_record('model-call',{'schema_version':'1.0.0','id':'call:trace','route_attempt_id':'route-attempt:trace',
        'route_decision_ref':None,'invocation_id':'inv:trace','execution_id':'exec:trace','purpose':'task_execution',
        'call_function':'worker','deployment_ref':contract,'model_selection_profile_ref':contract,'provider_request_id':None,
        'identity':{'requested':'codex-cli-default','effective':None,'basis':'Controlled unit packet capture'},
        'started_at':utc_now(),'ended_at':utc_now(),'outcome':'completed','provider_error_code':None,
        'usage':observed_usage(),'observed_runtime':True,'evidence_refs':[summary]},record_id='call:trace')
    if fault is not None:
        with pytest.raises(ResearchError):evidence.capture_native_trace(observation,start,call,summary)
        assert not [r for r in store.iter_records(kinds=('run-evidence-file',)) if '/trace/native/' in r['record']['artifact_ref']['id']]
    else:
        files=evidence.capture_native_trace(observation,start,call,summary)
        assert len(files)==2  # v2 retains an index, projecting packets at export
        copied = next(r['record'] for r in store.iter_records(kinds=('run-evidence-file',))
            if r['record']['artifact_ref'] == files[-1])
        exported = evidence.native_trace_export_files('run:evidence', copied)
        assert len(exported) == 2
        assert any(store.read_blob(item['artifact_ref']) == packet for item in exported)
        assert any(store.read_blob(item['artifact_ref']) == store.read_blob(event_ref) for item in exported)
        with pytest.raises(ResearchError): evidence.native_trace_export_files('run:foreign', copied)
        assert any(store.read_blob(ref)==store.read_blob(summary) for ref in files)
        bundle=store.read_record(evidence.build('run:evidence'))
        assert not any(ref in bundle['artifact_refs'] for ref in files)
        assert files[-1] in evidence.invocation_trace_refs(observation)


@pytest.mark.asyncio
async def test_false_pin_and_router_claims_are_refused(tmp_path):
    _, _, evidence, context = await prepared_run(tmp_path)
    for delta in [{'check_bundle_set_sha256': '0' * 64}, {'library_snapshot_sha256': '0' * 64},
                  {'router_enabled': True, 'router_version': None}]:
        with pytest.raises(ResearchError): evidence.prepare(context, context['run_pins'] | delta)


@pytest.mark.asyncio
async def test_records_files_are_write_once_exact_relative_refs(tmp_path):
    store, _, _, _ = await prepared_run(tmp_path)
    ref = store.capture_record_file('runs/run_evidence/output.json', b'{"exact":1}\r\n')
    assert ref['id'] == 'runs/run_evidence/output.json'
    assert store.read_blob(ref) == b'{"exact":1}\r\n'
    assert store.capture_record_file(ref['id'], store.read_blob(ref)) == ref
    for path in ['../escape', '/absolute', 'runs/../escape']:
        with pytest.raises(ResearchError): store.capture_record_file(path, b'wrong')
    with pytest.raises(ResearchError): store.capture_record_file(ref['id'], b'different')


@pytest.mark.asyncio
async def test_interrupted_record_publication_leaves_no_partial_target(tmp_path):
    store,_,_,_=await prepared_run(tmp_path)
    original=store._fault
    def fail(point):
        if point=='before_record_file_link':raise OSError('controlled interruption')
        return original(point)
    store._fault=fail
    with pytest.raises(OSError):store.capture_record_file('runs/interrupted/output.bin',b'complete original bytes')
    assert not (store.root/'records/runs/interrupted/output.bin').exists()
    assert not list((store.root/'records/runs/interrupted').glob('.capture-*'))
    store._fault=original
    ref=store.capture_record_file('runs/interrupted/output.bin',b'complete original bytes')
    assert store.read_blob(ref)==b'complete original bytes'


@pytest.mark.asyncio
async def test_existing_hardlinked_record_target_is_refused(tmp_path):
    import os
    store,_,_,_=await prepared_run(tmp_path)
    store.capture_record_file('runs/existing/original',b'exact')
    os.link(store.root/'records/runs/existing/original',store.root/'records/runs/existing/alias')
    with pytest.raises(ResearchError):store.capture_record_file('runs/existing/original',b'exact')


@pytest.mark.asyncio
async def test_bundle_faults_count_actual_injections_not_requested_faults(tmp_path):
    store,_,evidence,context=await prepared_run(tmp_path)
    context['profile_id']='evaluation:test'
    binding={'id':'evaluation:run','run_id':'run:evidence','evaluation_profile_id':'evaluation:test','invalid_for_product':True,'profile_ref':store.put_blob(b'public approved profile'),'fault_id':'requested:only'}
    store.append_record('evaluation-run-binding',binding)
    evidence.start('run:evidence',context)
    initial=store.read_record(evidence.build('run:evidence'))
    assert initial['fault_ids']==[]
    applied=store.append_record('fault-injection',{'id':'actual:swap','run_id':'run:evidence','fault_id':'actual:applied','evaluation_profile_id':'evaluation:test','kind':'swap_artifact'})
    actual=store.read_record(evidence.build('run:evidence'))
    assert actual['fault_ids']==['actual:applied']
    labels=[store.read_record(ref) for ref in actual['artifact_refs'] if 'evaluation-labels' in ref['id']]
    assert len(labels)==1 and labels[0]['invalid_for_product'] is True and labels[0]['injection_refs']==[applied]
    assert 'requested:only' not in str(labels)


@pytest.mark.asyncio
async def test_finite_run_bundle_retains_original_qualification_and_omitted_stage_reasons(tmp_path):
    from tests.unit_tests.research.test_finite_e1 import finite_execution_fixture
    store, owner, protected, inputs, scheduler, prompts = await finite_execution_fixture(tmp_path, 'valid')
    try:
        evidence = RunEvidence(store, owner.library)
        evidence.start('run:finite-visible', protected)
        scheduler.evidence = scheduler.runner.evidence = evidence
        result = await owner.execute('run:finite-visible', protected, scheduler=scheduler)
        assert result['status'] == 'completed', result
        bundle_ref = evidence.finish('run:finite-visible')
        bundle = store.read_record(bundle_ref, contract_id='run-bundle')
        qualification = next(store.iter_records(run_id='run:finite-visible', kinds=('finite-e1-fixture-qualification',)))
        binding = next(store.iter_records(run_id='run:finite-visible', kinds=('finite-e1-plan-binding',)))
        for ref in [qualification['ref'], binding['ref'], owner.binding_ref, result['plan_ref'], *inputs.values(), *qualification['record']['visible_refs']]:
            assert ref in bundle['artifact_refs']
        assert owner._binding['qualification_policy_ref'] not in bundle['artifact_refs']
        assert bundle['run_plan_ref'] == result['plan_ref'] and len(bundle['node_dispatches']) == 1
        assert bundle['node_dispatches'][0]['node_id'] == 'screening'
        assert any(row['obligation_id'] == 'finite-scope:intention_compiler' and row['reason'] for row in bundle['missing_evidence'])
        assert any(row['obligation_id'] == 'finite-scope:delivery' and row['reason'] for row in bundle['missing_evidence'])
        assert len(prompts) == 3 and evidence.finish('run:finite-visible') == bundle_ref
        assert not store.is_accepted(inputs['brief'])
    finally:
        store.close()
