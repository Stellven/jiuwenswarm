"""Controlled transport fixtures test host mechanics, never live model quality."""
import json
from pathlib import Path

import pytest

from jiuwenswarm.research.binding import ContractFactory
from jiuwenswarm.research.checks import CheckRegistry
from jiuwenswarm.research.compiler import IntentionCompiler,register_compiler_capsules
from jiuwenswarm.research.contracts import Principal
from jiuwenswarm.research.intake import qualify_intake
from tests.unit_tests.research.controlled_assets import ControlledLibraryService as LibraryService
from jiuwenswarm.research.runner import CapsuleRunner,Registry
from jiuwenswarm.research.state import SQLiteRunStore,json_bytes


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',[None,'bad_span','malformed_verifier','semantic_failure','acceptance_storage_failure','record_hook_failure'])
@pytest.mark.parametrize('route_mode',['fixed_baseline','development_profile'])
async def test_compiler_requires_internal_acceptance_and_commits_one_external_brief(tmp_path,fault,route_mode):
    await controlled_compiler(tmp_path, fault, route_mode)


async def controlled_compiler(tmp_path, fault=None, route_mode='fixed_baseline', *, planner_model=None, run_model_calls=4, review_reject_node=None):
    store=SQLiteRunStore(tmp_path);registry=Registry();checks=CheckRegistry();library=LibraryService(store)
    actor=Principal('operator',operations=frozenset({'verifier_assets','library_admit','library_standing'}))
    installed=await register_compiler_capsules(registry,checks,library,store,actor,activate=True)
    opaque=store.put_blob(b'protected fixture binding');defaults=store.put_record('default-policy',{'schema_version':'1.0.0','id':'defaults','hardware_profile':'single_gpu','automatic_retries':0})
    finalization=store.put_record('node-finalization-profile',{'schema_version':'2.0.0','id':'node_profile','mandatory_deterministic':['internal_acceptance','external_output','aggregate_limits'],'semantic_assessment_reuse':'accepted_requirements','additional_model_calls':0})
    user=Principal('alice',frozenset({'project'}),frozenset({'ingest'}));fixtures=Path('tests/fixtures/research/compiler')
    intake_ref=qualify_intake(store,user,(fixtures/'request.txt').read_text('utf-8'),[],workspace_id='project',profile_ref=opaque,workspace_ref=opaque,input_directory_ref=opaque)
    intake=store.read_record(intake_ref)
    store.create_run('run:compiler',account_id='alice',workspace_id='project',submission={'schema_version':'1.0.0','id':'submission:controlled','client_request_id':'controlled-request','workspace_id':'project','account_id':'alice','intake_ref':intake_ref,'configuration_ref':opaque,'plan_source':'planned'})
    calls=[]
    class ControlledBridge:
        async def call(self,context,prompt):
            protected=runner.authorize_model_context(context);calls.append(protected['call_function'])
            assert protected['model_selection_profile']['policy_mode']==route_mode
            if route_mode=='development_profile' and protected['call_function']!='verifier':
                assert 'routing_export_error' not in protected
                request=protected['route_request'];selected=protected['selected_capsule']
                assert request['user_id']=='alice' and request['selected_capsule']==selected
                assert selected['subnode_contract_ref']==protected['contract_ref']
                assert selected['bound_context']['budget_snapshot']['tokens_remaining'] is None
            store.append_record('model-call-start',dict(protected,id=protected['call_id']+':start'))
            cc=protected['cc_name']
            if cc=='intent.compiler':
                value=json.loads((fixtures/'intent_ir.json').read_text('utf-8'))
                def rewrite(v):
                    if isinstance(v,dict):
                        if set(v)=={'id','sha256'}:return intake['request_ref']
                        return {k:rewrite(x) for k,x in v.items()}
                    if isinstance(v,list):return [rewrite(x) for x in v]
                    return v
                value=rewrite(value)
                if fault=='bad_span':value['interpretation']['problem']['source_spans'][0]['end']=100000
                text=json.dumps(value)
            elif cc=='requirements.compiler':
                intent_ref=store.accepted_outputs('run:compiler','intention_compiler',subnode_id='intent')['intent']
                value=json.loads((fixtures/'research_brief.json').read_text('utf-8'))
                def rewrite(v):
                    if isinstance(v,dict):
                        if set(v)=={'id','sha256'}:
                            return {'intent_ir.json':intent_ref,'qualified_intake.json':intake_ref,'default_policy.json':defaults,'request.txt':intake['request_ref']}[v['id']]
                        return {k:rewrite(x) for k,x in v.items()}
                    if isinstance(v,list):return [rewrite(x) for x in v]
                    return v
                value=rewrite(value);value['in_scope'][0]['id']='scope:1';text=json.dumps(value)
            elif cc == 'research.planner' and planner_model is not None:
                text = planner_model(prompt)
            else:
                payload=json.loads(prompt.split('<subject_payload>\n',1)[1].split('\n</subject_payload>',1)[0])
                assert set(payload)=={'subject_declaration','subject_output'}
                profile=json.loads(prompt.split('Criteria for this output:\n',1)[1].split('\n\n<subject_payload>',1)[0])
                text=json.dumps({'findings':[] if fault=='malformed_verifier' else [{'criterion_id':c['criterion_id'],
                                 'outcome':'FAIL' if fault=='semantic_failure' else 'PASS',
                                 'reason':'Controlled semantic contradiction' if fault=='semantic_failure' else 'Controlled output-shape fixture'} for c in profile],
                                 'uncertainties':[],'limitations':[],
                                 'required_correction':'Resolve the contradiction' if fault=='semantic_failure' else None})
                if protected['node_id'] == review_reject_node:
                    value=json.loads(text)
                    if value['findings']:
                        value['findings'][0].update(outcome='FAIL',reason='Controlled independent rejection')
                    text=json.dumps(value)
            return {'text':text,'identity':{'requested':'fixture','effective':None,'basis':'Controlled transport, not endpoint evidence'},'observed_runtime':True}
    runner=CapsuleRunner(store,registry,checks,model=ControlledBridge(),check_assets=library.check_assets)
    factory=ContractFactory(store,library,verifier_pin=installed['verifier']['pin'],finalization_profile_ref=finalization)
    compiler=IntentionCompiler(store,runner,factory,intent_pin=installed['intent']['pin'],requirements_pin=installed['requirements']['pin'],default_policy_ref=defaults,
        template_ref=opaque,node_limits={'time_s':600,'model_calls':4,'memory_mb':256},policy_ref=defaults,
        authority_ceiling={'network':'none','network_allowlist':[],'resource_reads':[],'write_roots':[],'tools':[]})
    model_profile=store.put_record('model-selection-profile',{'schema_version':'1.0.0','id':'fixed:test','policy_mode':route_mode,
        'approved_model_ids':['codex-cli-default'],'extra_requirements':{},'selection_allowance':{'enabled':False,'deployment_ref':None,'model_calls':0,'time_s':0,'output_tokens':0,'disclosure_scope':[]},'alternate_model_id':None,'policy_ref':defaults})
    protected={'model_selection_profile_ref':model_profile,'deployment_ref':opaque,'router':{'enabled':route_mode=='development_profile','deadline_s':30,'profile_ref':model_profile if route_mode=='development_profile' else None},
        'routing_context':{'workflow_id':'workflow:fixture','task_id':'task:fixture','task_category':'experimental_evaluation_and_technical_data','requirements':{},'preferences':{}},
        'configuration_ref':opaque,'run_limits':{'time_s':600,'model_calls':run_model_calls,'memory_mb':256}}
    if fault=='acceptance_storage_failure':
        def crash(point):
            if point=='before_acceptance':raise OSError('Controlled acceptance storage failure')
        store._fault=crash
        with pytest.raises(OSError,match='Controlled acceptance storage failure'):await compiler.run('run:compiler',protected)
        assert calls==['worker','verifier'] and store.accepted_outputs('run:compiler','intention_compiler',subnode_id='intent')=={}
        return
    if fault=='record_hook_failure':
        def missing_optional_record(point):
            if point=='before_capsule_record_append':raise OSError('Controlled optional record journal failure')
        store._fault=missing_optional_record
    result=await compiler.run('run:compiler',protected)
    if fault not in (None,'record_hook_failure'):
        assert result['accepted'] is False
        assert calls==(['worker'] if fault=='bad_span' else ['worker','verifier'])
        assert store.accepted_outputs('run:compiler','intention_compiler')=={}
        if fault=='semantic_failure':
            gates=[r['record'] for r in store.iter_records(run_id='run:compiler',kinds=('gate-decision',))
                   if r['record']['scope_kind']=='subnode']
            assert gates and all(g['action']=='halt' for g in gates)
            messages=[reason['message'] for gate in gates for reason in gate['reasons']]
            assert any('Controlled semantic contradiction' in message for message in messages)
            assert not any('All mandatory checks and semantic criteria passed' in message for message in messages)
        return
    assert result['accepted'], [row for r in store.iter_records(kinds=('deterministic-check-result',)) for row in r['record']['results'] if row['outcome']!='PASS']
    assert calls==['worker','verifier','worker','verifier']
    assert store.accepted_outputs('run:compiler','intention_compiler')=={'brief':result['brief_ref']}
    completed=list(store.iter_records(kinds=('capsule-run-record',)))
    if fault=='record_hook_failure':
        assert completed==[] and len(list(store.iter_records(kinds=('capture-hook-failure',))))==4
    else:
        assert len(completed)==4 and all(row['record']['failure_class']=='none' for row in completed)
        links=list(store.iter_records(kinds=('capsule-run-record-link',)))
        assert len(links)==4 and all(row['record']['decision_refs'] for row in links)
        raw=list(store.iter_records(kinds=('invocation-observation',)))
        assert all(row['record']['failure_class'] is None for row in raw)
        assert all(row['record']['check_result_refs'] for row in completed)

    if fault is None:
        from jiuwenswarm.research.control import ResearchService
        service=ResearchService(store,registry=registry,model=None)
        export_actor=Principal('alice',workspace_ids=frozenset({'project'}),operations=frozenset({'export'}))
        _,contents=await service.artifact_bytes(export_actor,'run:compiler')
        index=json.loads(contents['contracts/index.json'])
        assert {'research-brief','node-execution-contract','subnode-execution-contract','bound-check-plan'} <= {e['kind'] for e in index['contracts']}
        assert any(e['kind']=='research-brief' and e['schema_version']=='3.0.0' and e['accepted'] for e in index['contracts'])
        assert any(e['kind']=='run-plan' and e['reason']=='not_created_at_this_run_stage' for e in index['missing'])
    return {'store': store, 'registry': registry, 'checks': checks, 'library': library, 'actor': actor,
        'installed': installed, 'runner': runner, 'factory': factory, 'protected': protected, 'brief_ref': result['brief_ref'], 'calls': calls}
