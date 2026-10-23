from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
"""Private trial boundary controls; controlled assets are not qualification."""
import copy
import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from jiuwenswarm.research.binding import ContractFactory
from jiuwenswarm.research.compiler import input_port
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.isolated_evaluation import IsolatedEvaluation,SignedTrialReservations
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_budget_ceiling import installed_library
from tests.unit_tests.research_rsi.fixture_package import make_unit_package


async def trial_fixture(root):
    store,registry,checks,library,installed,_=await installed_library(root,scientific=True)
    library.rsi_security_guard=ControlledQualification()
    fixture=make_unit_package(root);store=fixture['store'];asset=installed['screening'];parent=store.read_record(asset['declaration_ref'])
    child=copy.deepcopy(fixture['store'].read_record(fixture['package']['child_declaration_ref']))
    child['identity']['body']=copy.deepcopy(parent['identity']['body']);bodies=copy.deepcopy(asset['body_refs'])
    bodies['screening_prompt.txt']=store.put_blob(store.read_blob(bodies['screening_prompt.txt'])+b'\nUnit text variant; no quality claim.\n')
    next(b for b in child['identity']['body'] if b['path']=='screening_prompt.txt')['sha256']=bodies['screening_prompt.txt']['sha256']
    child_ref=fixture['put'](child)
    target=store.read_record(fixture['package']['target_profile_ref']);target.update(parent_ref=asset['body_refs']['screening_prompt.txt'],mutable_paths=['screening_prompt.txt'])
    test_spec=fixture['put']({'schema':'unit-text-test:1','path':'screening_prompt.txt','predicate':'strict_utf8_nonempty'})
    target['required_test_refs']=[test_spec]
    target_ref=fixture['put'](target);session=copy.deepcopy(fixture['session']);session['target_profile_ref']=target_ref;session_ref=fixture['put'](session)
    opaque=target['configuration_ref'];selection=store.put_record('model-selection-profile',{'schema_version':'1.0.0','id':'fixed','policy_mode':'fixed_baseline','approved_model_ids':['codex-cli-default'],'extra_requirements':{},'selection_allowance':{'enabled':False,'deployment_ref':None,'model_calls':0,'time_s':0,'output_tokens':0,'disclosure_scope':[]},'alternate_model_id':None,'policy_ref':opaque})
    final=store.put_record('node-finalization-profile',{'schema_version':'2.0.0','id':'final','mandatory_deterministic':['internal_acceptance','external_output','aggregate_limits'],'semantic_assessment_reuse':'accepted_requirements','additional_model_calls':0})
    factory=ContractFactory(store,library,verifier_pin=installed['verifier']['pin'],finalization_profile_ref=final)
    store.create_run('parent-context',account_id='operator',workspace_id='isolated',submission={})
    source=Path('tests/fixtures/research/pipeline/source-valid')
    doc=store.put_blob(b'Controlled source document for fixture only',media_type='text/plain')
    def rewrite(value):
        if isinstance(value,dict):return doc if set(value)=={'id','sha256'} else {k:rewrite(v) for k,v in value.items()}
        if isinstance(value,list):return [rewrite(v) for v in value]
        return value
    from jiuwenswarm.research.intake import qualify_intake
    from jiuwenswarm.research.contracts import Principal
    intake_ref=qualify_intake(store,Principal('operator',frozenset({'isolated'}),frozenset({'ingest'})),
        'Compare an exact visible index with repeated lookup.',[],workspace_id='isolated',
        profile_ref=opaque,workspace_ref=opaque,input_directory_ref=opaque)
    brief_value=rewrite(json.loads((source/'lifecycle_research_brief.json').read_bytes()))
    # Current Screening declares Brief v3. The historical source fixture keeps
    # its qualitative target; adapt only this current-release test input.
    assert all(target['comparison'] is None for target in brief_value['target_metrics'])
    brief_value['schema_version']='3.0.0'
    for target in brief_value['target_metrics']:
        target['comparison_status']='qualitative'
    brief_value['intake_ref']=intake_ref
    brief=fixture['put'](brief_value)
    candidates=rewrite(json.loads((source/'candidate_set.json').read_bytes()));candidates.pop('ext',None);candidates['brief_ref']=brief
    values={'brief':brief,'candidate_set':fixture['put'](candidates),'screening_rubric':bodies['screening_rubric.json']}
    ports=[input_port(p['name'],p['schema_ref'],values[p['name']]) for p in parent['ports']['inputs']]
    outputs=[{'name':p['name'],'contract_id':p['schema_ref'],'version':ContractFactory._version(p['schema_ref']),'required':p['required']} for p in parent['ports']['outputs']]
    enclosing=factory.prepare_parent('parent-context','screening',[{'subnode_id':'screening','cc':asset['pin'],'depends_on':[]}],inputs=ports,outputs=outputs,
        objective='Controlled private trial boundary',requirement_ids=['screening'],limits={'time_s':300,'model_calls':3,'memory_mb':512},policy_ref=opaque,configuration_ref=opaque,template_ref=opaque,
        authority_ceiling={'network':'none','network_allowlist':[],'resource_reads':[r for p in ports for r in p['artifact_refs']]+[store.read_record(intake_ref)['request_ref']],'write_roots':[],'tools':[]})
    contract,_,_=factory.bind_subnode(enclosing,'screening',ports)
    row=library.get('research.screening',parent['identity']['version_label'])
    binding={'schema':'ai4r-isolated-evaluation-binding:1','id':'unit-trial','session_ref':session_ref,'target_ref':target_ref,
        'parent_admission_ref':row['admission_ref'],'parent_declaration_ref':asset['declaration_ref'],'parent_contract_ref':contract,'child_declaration_ref':child_ref,
        'child_body_refs':{p['path']:bodies[p['path']] for p in child['identity']['body']},'dependency_refs':store.read_record(contract)['bindings'][0]['dependency_refs'],
        'configuration_ref':opaque,'model_selection_profile_ref':selection,'deployment_ref':opaque,'inputs':[{k:p[k] for k in ('name','contract_id','artifact_refs')} for p in ports],
        'check_bundle_ref':asset['bundle_ref'],'checking_profile_ref':asset['profile_ref'],'limits':{'time_s':300,'model_calls':3,'memory_mb':512},'phase':'development','repeat_index':0}
    reservation={'schema':'ai4r-rsi-trial-reservation:1','id':'unit-reservation','session_ref':session_ref,'target_ref':target_ref,'child_declaration_ref':child_ref,
        'phase':'development','repeat_index':0,'inputs_sha256':hashlib.sha256(json_bytes(binding['inputs'])).hexdigest(),'configuration_ref':opaque,
        'action_id':'visible-unit-action','charge_kind':'development','queries_used':0,'queries_left':30}
    binding['reservation_ref']=fixture['put'](fixture['signer'].sign(reservation))
    composition=SimpleNamespace(library=library,checks=checks,installed=installed)
    settings={'rsi':{'custodian_public_key':base64.urlsafe_b64encode(fixture['signer'].public_bytes()).decode().rstrip('='),'custodian_key_id':fixture['signer'].key_id}}
    resources=SimpleNamespace(store=store,composition=composition,operator=SimpleNamespace(snapshot=lambda:copy.deepcopy(settings)),
        exact_binding_refs={'configuration_ref':opaque,'model_selection_profile_ref':selection,'deployment_ref':opaque,'workspace_id':'isolated'},principal=SimpleNamespace(account_id='operator'))
    return store,IsolatedEvaluation(resources),fixture,binding


@pytest.mark.asyncio
async def test_prepare_has_actual_child_identity_and_no_library_or_acceptance_write(tmp_path):
    store,service,fixture,binding=await trial_fixture(tmp_path)
    before={table:store.connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ['library_versions','acceptance','model_calls']}
    ref=fixture['put'](binding);trial=service.prepare_isolated_evaluation(ref)
    assert service.prepare_isolated_evaluation(ref)==trial
    assert store.read_record(trial)['child_declaration_ref']==binding['child_declaration_ref']
    assert store.read_record(trial)['accepted'] is False
    assert before=={table:store.connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in before}
    with pytest.raises(ResearchError,match='mandatory-test owner'):await service.execute_isolated_evaluation(trial)
    assert not list(store.iter_records(kinds=('isolated-reservation-claim','model-call')))


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['repeat','dependency','limits','parent_admission','reservation_signature','unknown_field','protected_child'])
async def test_private_trial_rejects_forged_or_widened_binding_before_effects(tmp_path,fault):
    store,service,fixture,binding=await trial_fixture(tmp_path)
    if fault=='repeat':binding['repeat_index']=3
    elif fault=='dependency':binding['dependency_refs']=[]
    elif fault=='limits':binding['limits']['model_calls']=4
    elif fault=='parent_admission':binding['parent_admission_ref']=binding['child_declaration_ref']
    elif fault=='reservation_signature':
        reservation=store.read_record(binding['reservation_ref']);reservation['action_id']='forged';binding['reservation_ref']=fixture['put'](reservation)
    elif fault=='unknown_field':binding['hidden_label']='forbidden'
    else:
        child=store.read_record(binding['child_declaration_ref']);child['ports']['outputs'][0]['name']='forged';binding['child_declaration_ref']=fixture['put'](child)
    with pytest.raises(ResearchError):service.prepare_isolated_evaluation(fixture['put'](binding))
    assert not list(store.iter_records(kinds=('isolated-reservation-claim','model-call','isolated-evaluation-trial')))


@pytest.mark.asyncio
async def test_signed_charged_reservation_is_once_claimed_without_query_refund(tmp_path):
    store,service,fixture,binding=await trial_fixture(tmp_path)
    ref=fixture['put'](binding);trial=service.prepare_isolated_evaluation(ref)
    service.reservations.claim(trial,ref,binding)
    reopened=SignedTrialReservations(store,fixture['signer'].public_bytes(),fixture['signer'].key_id)
    with pytest.raises(ResearchError,match='already issued'):reopened.claim(trial,ref,binding)
    assert store.read_record(binding['reservation_ref'])['queries_left']==30


@pytest.mark.asyncio
async def test_full_private_measurement_uses_changed_prompt_actual_bridge_and_never_accepts(tmp_path):
    from jiuwenswarm.research.router_client import CodexRouter
    from jiuwenswarm.research.contracts import validate
    store,service,fixture,binding=await trial_fixture(tmp_path)
    prompts=[]
    class ControlledSubscription:
        async def invoke_governed(self,prompt,*,model,timeout_s):
            prompts.append(prompt)
            payload=json.loads(prompt.split('<subject_payload>\n',1)[1].split('\n</subject_payload>',1)[0])
            if set(payload)=={'subject_declaration','subject_output'}:
                criteria=json.loads(prompt.split('Criteria for this output:\n',1)[1].split('\n\n<subject_payload>',1)[0])
                reply={'findings':[{'criterion_id':c['criterion_id'],'outcome':'PASS','reason':'Controlled structural reply; no model quality claim'} for c in criteria],'uncertainties':[],'limitations':[],'required_correction':None}
            else:
                scores=json.loads(Path('tests/fixtures/research/pipeline/source-valid/screening_result.json').read_bytes())['scores']
                reply={'scores':scores,'opportunity_statement':'The frozen mechanism avoids repeated lookup work.'}
            return {'text':json.dumps(reply),'identity':{'effective':None,'basis':'Controlled in-process provider fixture'},'usage':{},'provider_request_id':None,'observed_runtime':True}
    service.resources.bridge=SimpleNamespace(subscription=ControlledSubscription(),router=CodexRouter('codex-cli-default'),providers=None,fixed_route_id='codex-cli-default',health_check=None)
    original_snapshot=service.resources.operator.snapshot
    service.resources.operator.snapshot=lambda:{**original_snapshot(),'cc':{'router':{'enabled':False,'profile_ref':None,'deadline_s':30}}}
    class ActualUnitTextTest:
        async def run(self,binding_ref,test_refs):
            value=store.read_record(binding_ref);proofs=[]
            for test_ref in test_refs:
                test=store.read_record(test_ref);raw=store.read_blob(value['child_body_refs'][test['path']]);passed=bool(raw.decode('utf-8',errors='strict').strip())
                plan={'schema_version':'2.0.0','id':'unit_text_test','contract_ref':value['child_declaration_ref'],'node_contract_ref':value['parent_contract_ref'],
                    'input_refs':[],'profile_ref':value['checking_profile_ref'],'policy_ref':value['configuration_ref'],'mandatory_deterministic':['strict_utf8_nonempty'],'mandatory_semantic':[],'runner_refs':[test_ref],'subnode_id':None}
                pref=store.put_record('bound-check-plan',plan)
                checked=store.put_record('deterministic-check-result',{'schema_version':'1.0.0','subject_ref':value['child_declaration_ref'],'check_plan_ref':pref,
                    'results':[{'check_id':'strict_utf8_nonempty','outcome':'PASS' if passed else 'FAIL','reason':'Actual pinned unit text predicate evaluated','evidence_refs':[value['child_body_refs'][test['path']]]}]})
                proofs.append(store.append_record('isolated-required-test',{'id':'unit-test:'+test_ref['sha256'],'test_ref':test_ref,'child_declaration_ref':value['child_declaration_ref'],
                    'configuration_ref':value['configuration_ref'],'outcome':'PASS' if passed else 'FAIL','deterministic_result_ref':checked,'execution_receipt_ref':None,'evidence_refs':[test_ref]}))
            return proofs
        async def contain(self,trial_ref):return {'contained':True}
    service.required_tests=ActualUnitTextTest()
    # Register the exact installed independent Screening checks, no production admission bypass.
    from jiuwenswarm.research.checks.stages import ResearchChecks
    asset=service.resources.composition.installed['screening']
    bundle=store.read_record(asset['bundle_ref'])
    service.resources.composition.checks.register_bundle(bundle['bundle_id'],[c['check_id'] for c in bundle['checks']],ResearchChecks('screening'),implementation_ref=bundle['checks'][0]['runner_ref'],profile_ref=asset['profile_ref'])
    before={table:store.connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ['library_versions','acceptance']}
    authority_before=[row['ref'] for row in store.iter_records(kinds=('gate-decision','activation-record'))]
    bref=fixture['put'](binding);trial=service.prepare_isolated_evaluation(bref);result_ref=await service.execute_isolated_evaluation(trial)
    result=store.read_record(result_ref)
    assert result['status']=='completed',result['failure']
    assert result['accepted'] is False and result['mandatory_tests_passed'] is True
    assert len(result['assessment_refs'])==2 and result['observation_refs']
    assert len(prompts)==3 and 'Unit text variant; no quality claim.' in prompts[0]
    assert before=={table:store.connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in before}
    assert [row['ref'] for row in store.iter_records(kinds=('gate-decision','activation-record'))]==authority_before
    assert await service.execute_isolated_evaluation(trial)==result_ref and len(prompts)==3
    private_contract=next(store.iter_records(kinds=('isolated-evaluation-contract',)))['record']
    assert 'admission_ref' not in private_contract['bindings'][0]
    assert private_contract['bindings'][0]['declaration_ref']==binding['child_declaration_ref']


async def rubric_v2_fixture(root):
    store,service,fixture,binding=await trial_fixture(root)
    parent=store.read_record(binding['parent_declaration_ref']);child=store.read_record(binding['child_declaration_ref'])
    row=service.library.get(parent['identity']['name'],parent['identity']['version_label'])
    binding['child_body_refs']['screening_prompt.txt']=row['body_refs']['screening_prompt.txt']
    next(b for b in child['identity']['body'] if b['path']=='screening_prompt.txt')['sha256']=row['body_refs']['screening_prompt.txt']['sha256']
    rubric=store.read_record(row['body_refs']['screening_rubric.json'])
    rubric['dimensions'][0]['anchors'][0]['description']+=' Controlled unit wording.'
    changed=fixture['put'](rubric);binding['child_body_refs']['screening_rubric.json']=changed
    next(b for b in child['identity']['body'] if b['path']=='screening_rubric.json')['sha256']=changed['sha256']
    binding['child_declaration_ref']=fixture['put'](child)
    target=store.read_record(binding['target_ref']);target.update(parent_ref=row['body_refs']['screening_rubric.json'],mutable_paths=['screening_rubric.json'])
    binding['target_ref']=fixture['put'](target);session=store.read_record(binding['session_ref']);session['target_profile_ref']=binding['target_ref'];binding['session_ref']=fixture['put'](session)
    binding['schema']='ai4r-isolated-evaluation-binding:2';binding['inputs']=[p for p in binding['inputs'] if p['name']!='screening_rubric']
    reservation=store.read_record(binding['reservation_ref']);reservation.update(schema='ai4r-rsi-trial-reservation:2',
        **{k:binding[k] for k in ('session_ref','target_ref','child_declaration_ref')},inputs_sha256=hashlib.sha256(json_bytes(binding['inputs'])).hexdigest())
    binding['reservation_ref']=fixture['put'](fixture['signer'].sign(reservation))
    return store,service,fixture,binding


@pytest.mark.asyncio
async def test_v2_child_rubric_is_derived_from_subject_body_without_external_read_expansion(tmp_path):
    store,service,fixture,binding=await rubric_v2_fixture(tmp_path)
    original=store.read_record(binding['parent_contract_ref'])['bindings'][0]['effective_authority']
    validated=service._validate(binding);inputs=validated[-1]
    assert [p['name'] for p in inputs]==['brief','candidate_set','screening_rubric']
    assert inputs[-1]['artifact_refs']==[binding['child_body_refs']['screening_rubric.json']]
    assert store.read_record(binding['parent_contract_ref'])['bindings'][0]['effective_authority']==original
    trial=service.prepare_isolated_evaluation(fixture['put'](binding))
    assert store.read_record(trial)['interface_revision']=='M1-IF-011@r2'


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['caller_rubric','order','old_reservation','v1_changed_rubric'])
async def test_v2_rubric_cannot_be_selected_or_hashed_by_caller(tmp_path,fault):
    store,service,fixture,binding=await rubric_v2_fixture(tmp_path)
    if fault=='caller_rubric':binding['inputs'].append({'name':'screening_rubric','contract_id':'screening-rubric:field-contract:1','artifact_refs':[binding['child_body_refs']['screening_rubric.json']]})
    elif fault=='order':binding['inputs'].reverse()
    elif fault=='old_reservation':
        value=store.read_record(binding['reservation_ref']);value['schema']='ai4r-rsi-trial-reservation:1';binding['reservation_ref']=fixture['put'](fixture['signer'].sign(value))
    else:
        binding['schema']='ai4r-isolated-evaluation-binding:1'
        binding['inputs'].append({'name':'screening_rubric','contract_id':'screening-rubric:field-contract:1','artifact_refs':[binding['child_body_refs']['screening_rubric.json']]})
        value=store.read_record(binding['reservation_ref']);value.update(schema='ai4r-rsi-trial-reservation:1',inputs_sha256=hashlib.sha256(json_bytes(binding['inputs'])).hexdigest());binding['reservation_ref']=fixture['put'](fixture['signer'].sign(value))
    with pytest.raises(ResearchError):service.prepare_isolated_evaluation(fixture['put'](binding))
    assert not list(store.iter_records(kinds=('model-call','isolated-reservation-claim')))
