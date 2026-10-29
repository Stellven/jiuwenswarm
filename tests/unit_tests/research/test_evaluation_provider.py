"""Finite E2/E3 policy controls; no live model or calibrated campaign claim."""
import copy

import pytest

from tests.unit_tests.research.evaluation_runtime_fixture import bind_request_runtime, assert_private_measurement_origin

from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.library import LibraryService
from jiuwenswarm.research.operator_config import OperatorConfiguration
from jiuwenswarm.research.state import SQLiteRunStore
from tests.unit_tests.research.test_operator_config import valid_config


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome',['completed','timeout','network_error'])
async def test_model_call_duration_projection_preserves_actual_unknown_completion(tmp_path,outcome):
    """Actual Bridge/store capture, controlled provider; no live model claim."""
    from types import SimpleNamespace
    from jiuwenswarm.research.bridge import GovernedBridge,BridgeError
    from jiuwenswarm.research.evaluation_provider import EvaluationProvider
    from tests.unit_tests.research.test_bridge import authorized_context

    store=SQLiteRunStore(tmp_path)
    context=authorized_context()
    class Provider:
        async def invoke_governed(self,*args,**kwargs):
            if outcome=='timeout':raise TimeoutError('controlled timeout')
            if outcome=='network_error':raise ConnectionResetError('controlled connection loss')
            return {'text':'controlled completion','identity':{},'usage':{},'observed_runtime':True}
    bridge=GovernedBridge(persist=store.append_record,authorize=lambda _:context,revalidate=lambda _:context,
                          subscription_service=Provider())
    try:
        if outcome=='completed':await bridge.call({},'controlled projection input')
        else:
            with pytest.raises(BridgeError,match=outcome):await bridge.call({},'controlled projection input')
        starts=list(store.iter_records(run_id=context['run_id'],kinds=('model-call-start',)))
        rows=EvaluationProvider._model_calls(SimpleNamespace(store=store,contract_ref=context['contract_ref']),
            SimpleNamespace(observation_refs=[]),starts,replay=False)
        assert len(rows)==1
        call=store.read_record(rows[0]['call_ref'],contract_id='model-call')
        assert rows[0]['outcome']==call['outcome']==('completed' if outcome=='completed' else 'outcome_unknown')
        if outcome=='completed':assert rows[0]['duration_s'] is not None and rows[0]['duration_s']>=0
        else:assert rows[0]['duration_s'] is None and call['ended_at'] is None
        assert rows[0]['input_tokens'] is rows[0]['output_tokens'] is rows[0]['cost'] is None
    finally:store.close()


@pytest.mark.parametrize('inconsistent',['missing_known_end','unknown_with_end','negative_known_duration'])
def test_model_call_duration_projection_rejects_inconsistent_completion(tmp_path,inconsistent):
    from types import SimpleNamespace
    from jiuwenswarm.research.bridge import observed_usage
    from jiuwenswarm.research.evaluation_provider import EvaluationProvider

    store=SQLiteRunStore(tmp_path);pin=store.put_blob(b'controlled contract identity')
    call={'schema_version':'1.0.0','id':'call:inconsistent','route_attempt_id':'attempt:controlled','route_decision_ref':None,
          'execution_id':'execution','invocation_id':'invocation','purpose':'task_execution','call_function':'worker',
          'deployment_ref':pin,'model_selection_profile_ref':pin,'provider_request_id':None,
          'identity':{'requested':'controlled','effective':None,'basis':'not observed'},'started_at':'2026-10-19T00:00:01Z',
          'ended_at':'2026-10-19T00:00:02Z','outcome':'completed','provider_error_code':None,
          'usage':observed_usage(),'evidence_refs':[],'observed_runtime':True}
    if inconsistent=='missing_known_end':call['ended_at']=None
    elif inconsistent=='unknown_with_end':call['outcome']='outcome_unknown'
    else:call['ended_at']='2026-10-19T00:00:00Z'
    store.append_record('model-call',call)
    starts=[{'record':{'contract_ref':pin,'call_id':call['id'],'invocation_id':'invocation','execution_id':'execution'}}]
    try:
        with pytest.raises(ResearchError,match='completion|chronology'):
            EvaluationProvider._model_calls(SimpleNamespace(store=store,contract_ref=pin),SimpleNamespace(observation_refs=[]),starts,replay=False)
    finally:store.close()


@pytest.fixture
def evaluation(tmp_path):
    store=SQLiteRunStore(tmp_path)
    declaration=store.put_blob(b'{"identity":{"name":"controlled.cc","version_label":"1"}}')
    output=store.put_blob(b'{"id":"actual","sha256":"1111111111111111111111111111111111111111111111111111111111111111"}')
    host=store.put_blob(b'{"private_host_marker":"NEVER_SEND_TO_SEMANTIC_REVIEW"}')
    binding=store.append_record('evaluation-case-binding',{'id':'binding:controlled','node_id':'probe','verifier_cc_id':'verifier@m1-1'})
    profile={'schema_version':'1.0.0','id':'profile:finite','profile_id':'controlled:finite','plan_source':'static',
             'router_enabled':False,'router_version':None,'model_route':'codex-cli-default','library_snapshot_sha256':'1'*64,
             'candidate_pins':[],'verifier_cc_ref':declaration,'invalid_for_product':True,'allowed_entry_points':['E2','E3']}
    profile_ref=store.put_record('evaluation-profile',profile)
    config=valid_config();config['cc']['evaluation_profile_ref']=profile_ref
    operator=OperatorConfiguration.from_mapping(config,resolve_profile=store.read_record)
    configuration=store.append_record('approved-configuration',{'operator':config})
    entries=[{'path':name,'sha256':ref['sha256'],'artifact_ref':ref,'role':role}
             for name,ref,role in [('capsule.json',declaration,'declaration'),('output.json',output,'output'),
                                  ('host.json',host,'host_runtime_observation'),('binding.json',binding,'binding')]]
    assets=store.append_record('evaluation-assets',{'schema':'ai4r-evaluation-assets:1','id':'assets:finite',
        'profile_ref':profile_ref,'configuration_ref':configuration,'account_id':'owner','workspace_id':'work',
        'campaign_id':'campaign','entries':entries,'cases':[{'case_id':'citation','entry_point':'E2',
        'binding_ref':binding,'record_gate':False},{'case_id':'capsule','entry_point':'E3','binding_ref':binding,'record_gate':False}]})
    actor=Principal('owner',frozenset({'work'}),frozenset({'evaluation_profile'}))
    request={'request_id':'replay-1','campaign_id':'campaign','case_id':'citation','evaluation_profile_id':profile['profile_id'],
             'verifier_cc_id':'verifier@m1-1','declaration':{'path':'capsule.json','sha256':declaration['sha256']},
             'output':{'path':'output.json','sha256':output['sha256']},'node_id':'probe',
             'host_records':[{'record_type':'runtime_observation','path':'host.json','sha256':host['sha256']}]}
    try:yield store,operator,assets,actor,request
    finally:store.close()


@pytest.mark.asyncio
async def test_product_or_unscoped_actor_cannot_replay(evaluation):
    from jiuwenswarm.research.evaluation_provider import EvaluationProvider
    store,operator,assets,actor,request=evaluation
    provider=EvaluationProvider(store,operator,assets_ref=assets,resources=None,library=LibraryService(store))
    ordinary=Principal('owner',frozenset({'work'}),frozenset({'submit'}))
    with pytest.raises(ResearchError) as observed:await provider.node_replay(ordinary,request)
    assert observed.value.code=='auth'
    with pytest.raises(ResearchError):await provider.node_replay(actor,request|{'campaign_id':'foreign'})
    assert not list(store.iter_records(kinds=('evaluation-request','model-call-start','gate-decision','acceptance-commit')))


@pytest.mark.asyncio
@pytest.mark.parametrize('change',[
    {'evaluation_profile_id':'foreign'},
    {'declaration':{'path':'../host.json','sha256':'1'*64}},
    {'output':{'path':'/var/lib/ai4r/private','sha256':'1'*64}},
    {'output':{'path':'output.json','sha256':'0'*64}},
    {'host_records':[{'record_type':'oracle','path':'host.json','sha256':'1'*64}]},
    {'callback':'client-supplied-code'},
])
async def test_request_cannot_widen_frozen_scope_or_resolve_host_paths(evaluation,change):
    from jiuwenswarm.research.evaluation_provider import EvaluationProvider
    store,operator,assets,actor,request=evaluation
    provider=EvaluationProvider(store,operator,assets_ref=assets,resources=None,library=LibraryService(store))
    with pytest.raises(ResearchError):await provider.node_replay(actor,request|change)
    assert not list(store.iter_records(kinds=('model-call-start','gate-decision','acceptance-commit')))


@pytest.mark.asyncio
async def test_missing_actual_resources_are_unavailable_without_dispatch(evaluation):
    from jiuwenswarm.research.evaluation_provider import EvaluationProvider
    store,operator,assets,actor,request=evaluation
    provider=EvaluationProvider(store,operator,assets_ref=assets,resources=None,library=LibraryService(store))
    assert provider.available_entry_points==()
    with pytest.raises(ResearchError) as observed:await provider.node_replay(actor,request)
    assert observed.value.code=='entry_point_unavailable'
    assert not list(store.iter_records(kinds=('model-call-start','invocation-observation','gate-decision','acceptance-commit')))


@pytest.mark.asyncio
async def test_single_cc_rejects_unadmitted_version_before_worker(evaluation):
    from jiuwenswarm.research.evaluation_provider import EvaluationProvider
    store,operator,assets,actor,_=evaluation
    class NoWorker:
        available_entry_points=('E3',)
        async def prepare_single_cc(self,**kwargs):pytest.fail('Unadmitted capsule must not reach a worker context')
    provider=EvaluationProvider(store,operator,assets_ref=assets,resources=NoWorker(),library=LibraryService(store))
    request={'request_id':'single-1','campaign_id':'campaign','case_id':'capsule','evaluation_profile_id':'controlled:finite',
             'capsule_id':'unadmitted','capsule_version':'1','capsule_declaration_sha256':'1'*64,
             'binding':{'path':'binding.json','sha256':store.read_record(assets)['cases'][1]['binding_ref']['sha256']},
             'inputs':[],'model_route':'codex-cli-default'}
    with pytest.raises(ResearchError):await provider.single_cc(actor,request)
    assert not list(store.iter_records(kinds=('model-call-start','gate-decision','acceptance-commit')))


async def installed_provider(root,*,allowed_entry_points=None):
    """Actual normal admitted owner with an explicit unavailable test carrier.

    Controlled check-asset admissions are test scaffolding, never qualification.
    """
    from types import SimpleNamespace
    from tests.unit_tests.research.test_admitted_measurement import adapter_fixture
    from jiuwenswarm.research.evaluation_provider import EvaluationProvider,InstalledEvaluationResources
    store,adapter,contract_ref,checks_ref,_=await adapter_fixture(root)
    library=adapter.library;snapshot=library.snapshot();installed=adapter.resources.composition.installed
    profile={'schema_version':'1.0.0','id':'profile:installed','profile_id':'controlled:installed','plan_source':'static',
        'router_enabled':False,'router_version':None,'model_route':'codex-cli-default','library_snapshot_sha256':snapshot['sha256'],
        'candidate_pins':[],'verifier_cc_ref':installed['verifier']['declaration_ref'],'invalid_for_product':True,'allowed_entry_points':allowed_entry_points or ['E3']}
    profile_ref=store.put_record('evaluation-profile',profile)
    settings=adapter.resources.operator.snapshot();settings['cc']['evaluation_profile_ref']=profile_ref
    operator=SimpleNamespace(snapshot=lambda:copy.deepcopy(settings))
    configuration=store.append_record('approved-configuration',{'operator':settings})
    adapter.resources.operator=operator;adapter.resources.exact_binding_refs['configuration_ref']=configuration
    contract=store.read_record(contract_ref);node=store.read_record(contract['node_contract_ref'])
    node['configuration_ref']=configuration
    node_ref=store.put_record('node-execution-contract',node,record_id='evaluation-node')
    contract.update(configuration_ref=configuration,node_contract_ref=node_ref)
    contract_ref=store.put_record('subnode-execution-contract',contract,record_id='evaluation-subnode')
    checks=store.read_record(checks_ref);checks.update(contract_ref=contract_ref,node_contract_ref=node_ref)
    store.put_record('bound-check-plan',checks,record_id='evaluation-checks')
    declaration=contract['bindings'][0]['declaration_ref'];identity=store.read_record(declaration)['identity']
    entries=[{'path':'binding.json','sha256':contract_ref['sha256'],'artifact_ref':contract_ref,'role':'binding'}]
    inputs=[]
    for port in contract['inputs']:
        for index,ref in enumerate(port['artifact_refs']):
            path=port['name']+str(index)+'.json'
            entries.append({'path':path,'sha256':ref['sha256'],'artifact_ref':ref,'role':'input'})
            inputs.append({'port':port['name'],'path':path,'sha256':ref['sha256']})
    assets=store.append_record('evaluation-assets',{'schema':'ai4r-evaluation-assets:1','id':'assets:installed',
        'profile_ref':profile_ref,'configuration_ref':configuration,'account_id':'operator','workspace_id':'isolated',
        'campaign_id':'campaign','entries':entries,'cases':[{'case_id':'capsule','entry_point':'E3','binding_ref':contract_ref,'record_gate':False}]})
    resources=InstalledEvaluationResources(adapter,profile_ref=profile_ref,assets_ref=assets,library_snapshot_ref=snapshot)
    provider=EvaluationProvider(store,operator,assets_ref=assets,resources=resources,library=library)
    actor=Principal('operator',frozenset({'isolated'}),frozenset({'evaluation_profile'}))
    request={'request_id':'actual-single','campaign_id':'campaign','case_id':'capsule','evaluation_profile_id':profile['profile_id'],
        'capsule_id':identity['name'],'capsule_version':identity['version_label'],'capsule_declaration_sha256':declaration['sha256'],
        'binding':{'path':'binding.json','sha256':contract_ref['sha256']},'inputs':inputs,'model_route':'codex-cli-default'}
    return store,provider,actor,request


@pytest.mark.asyncio
async def test_installed_single_cc_retains_actual_failure_once_and_reconciles_after_resources_disappear(tmp_path):
    store,provider,actor,request=await installed_provider(tmp_path)
    owner=bind_request_runtime(store,provider,request,'E3')
    assert provider.available_entry_points==('E3',)
    before=[r['ref'] for r in store.iter_records(kinds=('gate-decision','activation-record','acceptance-commit'))]
    result=await provider.single_cc(actor,request)
    # This fixture has no actual containment owner; preserve that uncertainty
    # instead of treating the unavailable carrier as a contained operation.
    assert result['status']=='blocked' and result['reason']=='containment_uncertain' and result['invalid_for_product'] is True
    assert result['tool_effects_observed'] is None and result['model_calls']==[]
    observed=list(store.iter_records(kinds=('evaluation-invocation-observation',)))
    assert len(observed)==1 and observed[0]['record']['outcome']=='failed'
    assert_private_measurement_origin(store,owner)
    assert not list(store.iter_records(kinds=('invocation-observation',)))
    provider.resources=None
    assert await provider.single_cc(actor,request)==result
    assert provider.get(actor,request['request_id'])['result']==result
    assert len(list(store.iter_records(kinds=('evaluation-invocation-observation',))))==1
    assert not list(store.iter_records(kinds=('invocation-observation',)))
    assert before==[r['ref'] for r in store.iter_records(kinds=('gate-decision','activation-record','acceptance-commit'))]
    with pytest.raises(ResearchError) as error:await provider.single_cc(actor,request|{'model_route':'changed'})
    assert error.value.code=='identity_conflict'
    store.close()


@pytest.mark.asyncio
async def test_claimed_request_with_no_terminal_capture_never_starts_again(tmp_path):
    store,provider,actor,request=await installed_provider(tmp_path)
    owner=bind_request_runtime(store,provider,request,'E3')
    request_ref=owner.accept_request(actor,request,'E3')
    scope=owner.prepare(request_ref)
    grant_ref=owner.prepare_assignment(scope,'worker',None)
    grant=store.read_record(grant_ref)
    child=store.read_record(grant['contract_ref'])
    # Publish the actual once-owned start without invoking a worker. Its unknown
    # result cannot be replayed, and no model or scientific effect is performed.
    context=owner.start_assignment(grant_ref,owner.runner._decode_inputs(child))
    await owner.runner._await_start(context)
    assert owner.inspect(request_ref)['state']=='executing'
    with pytest.raises(ResearchError) as error:await provider.single_cc(actor,request)
    assert error.value.code=='evaluation_outcome_unknown'
    assert not list(store.iter_records(kinds=('invocation-observation','admitted-measurement-grant','model-call-start')))
    assert not list(store.iter_records(kinds=('evaluation-invocation-observation',)))
    store.close()


@pytest.mark.asyncio
async def test_single_cc_actual_carrier_bridge_and_checks_do_not_authorize_product_material(tmp_path):
    import json
    from pathlib import Path
    from jiuwenswarm.research.bridge import GovernedBridge
    from jiuwenswarm.research.contracts import validate
    from jiuwenswarm.research.capsules.assets import register_research_capsules
    store,provider,actor,request=await installed_provider(tmp_path)
    adapter=provider.resources.admitted;runner=adapter.runner;prompts=[]
    class ControlledSubscription:
        async def invoke_governed(self,prompt,*,model,timeout_s):
            prompts.append(prompt)
            scores=json.loads(Path('tests/fixtures/research/pipeline/source-valid/screening_result.json').read_bytes())['scores']
            return {'text':json.dumps({'scores':scores,'opportunity_statement':'The frozen mechanism avoids repeated lookup work.'}),
                'identity':{'effective':None,'basis':'Controlled in-process provider fixture'},'usage':{},
                'provider_request_id':None,'observed_runtime':True}
    # The real installed carrier, governed call authorizer, captures and source
    # checks execute; only the external subscription response is controlled.
    from jiuwenswarm.research.runner import Registry
    registry=Registry();runner.registry=registry;adapter.resources.registry=registry
    register_research_capsules(registry,runner.check_registry,adapter.library,store,
        assets={'screening':adapter.resources.composition.installed['screening']})
    runner.model=GovernedBridge(persist=store.append_record,authorize=runner.authorize_model_context,
        revalidate=runner.authorize_model_dispatch,subscription_service=ControlledSubscription(),validate_record=validate)
    bind_request_runtime(store,provider,request,'E3')
    result=await provider.single_cc(actor,request)
    assert result['status']=='completed',result['reason']
    assert len(prompts)==1 and len(result['model_calls'])==1
    assert result['model_calls'][0]['role']=='worker'
    assert result['model_calls'][0]['effective_model'] is None
    assert result['model_calls'][0]['input_tokens'] is None and result['model_calls'][0]['cost'] is None
    assert all(r['status']=='PASS' for r in result['check_results'])
    assert result['output_refs'] and result['invalid_for_product'] is True
    with pytest.raises(ResearchError):store.require_product_material(list(result['output_refs'].values()))
    assert not list(store.iter_records(kinds=('gate-decision','acceptance-commit','verifier-assessment','evaluation-verifier-assessment')))
    assert await provider.single_cc(actor,request)==result and len(prompts)==1
    store.close()


@pytest.mark.asyncio
async def test_profile_verifier_must_be_the_actual_installed_independent_reviewer(tmp_path):
    from jiuwenswarm.research.evaluation_provider import InstalledEvaluationResources
    store,provider,_,_=await installed_provider(tmp_path)
    profile=copy.deepcopy(provider.profile)
    profile['verifier_cc_ref']=provider.resources.admitted.resources.composition.installed['screening']['declaration_ref']
    profile_ref=store.put_record('evaluation-profile',profile,record_id='mismatched-verifier-profile')
    assets=copy.deepcopy(provider.assets);assets.update(id='assets:mismatched-verifier',profile_ref=profile_ref)
    assets_ref=store.append_record('evaluation-assets',assets)
    with pytest.raises(ResearchError):InstalledEvaluationResources(provider.resources.admitted,profile_ref=profile_ref,
        assets_ref=assets_ref,library_snapshot_ref=provider.resources.snapshot_ref)
    assert not list(store.iter_records(kinds=('model-call-start','admitted-measurement-grant')))
    store.close()


@pytest.mark.asyncio
async def test_replay_selects_one_output_but_keeps_complete_original_multioutput_checks(tmp_path):
    import json
    from pathlib import Path
    from jiuwenswarm.research.bridge import GovernedBridge
    from jiuwenswarm.research.contracts import validate
    from jiuwenswarm.research.capsules.assets import register_research_capsules
    from jiuwenswarm.research.evaluation_provider import EvaluationProvider,InstalledEvaluationResources
    from jiuwenswarm.research.runner import Registry
    store,producer,actor,single=await installed_provider(tmp_path,allowed_entry_points=['E2','E3'])
    owner=producer.resources.admitted;runner=owner.runner;prompts=[]
    class ControlledSubscription:
        async def invoke_governed(self,prompt,*,model,timeout_s):
            prompts.append(prompt)
            payload=json.loads(prompt.split('<subject_payload>\n',1)[1].split('\n</subject_payload>',1)[0])
            if set(payload)=={'subject_declaration','subject_output'}:
                criteria=json.loads(prompt.split('Criteria for this output:\n',1)[1].split('\n\n<subject_payload>',1)[0])
                value={'findings':[{'criterion_id':c['criterion_id'],'outcome':'PASS','reason':'Controlled structural response only'} for c in criteria],
                    'uncertainties':[],'limitations':[],'required_correction':None}
            else:
                value={'scores':json.loads(Path('tests/fixtures/research/pipeline/source-valid/screening_result.json').read_bytes())['scores'],
                    'opportunity_statement':'The frozen mechanism avoids repeated lookup work.'}
            return {'text':json.dumps(value),'identity':{'effective':None,'basis':'Controlled in-process provider fixture'},
                'usage':{},'provider_request_id':None,'observed_runtime':True}
    registry=Registry();runner.registry=registry;owner.resources.registry=registry
    register_research_capsules(registry,runner.check_registry,owner.library,store,assets={'screening':owner.resources.composition.installed['screening']})
    runner.model=GovernedBridge(persist=store.append_record,authorize=runner.authorize_model_context,revalidate=runner.authorize_model_dispatch,
        subscription_service=ControlledSubscription(),validate_record=validate)
    # Produce the original through the actual canonical admitted source owner,
    # as the dedicated two-port replay control does. Public E3 now has a private
    # context and cannot masquerade as this source producer.
    contract_ref=producer.assets['cases'][0]['binding_ref'];contract=store.read_record(contract_ref)
    checks=next(r['ref'] for r in store.iter_records(kinds=('bound-check-plan',)) if r['record']['contract_ref']==contract_ref)
    original=await owner.execute(owner.prepare(contract_ref,checks,semantic_review=False))
    assert original.status=='completed' and len(original.output_refs)==2 and len(prompts)==1
    observation=original.observation_ref
    assert store.record_kind(observation)=='invocation-observation'
    assert store.read_record(observation)['contract_ref']==contract_ref
    declaration=contract['bindings'][0]['declaration_ref'];selected='screening_result';output=original.output_refs[selected]
    verifier=owner.resources.composition.installed['verifier']['pin'];verifier_id=verifier['cc_name']+'@'+verifier['cc_version']
    binding=store.append_record('evaluation-case-binding',{'schema':'ai4r-node-replay-binding:2','id':'multioutput:binding',
        'contract_ref':contract_ref,'check_plan_ref':checks,'output_refs':original.output_refs,'original_observation_ref':observation,
        'verifier_cc_id':verifier_id,'host_records':[],'selected_output_port':selected})
    assets=store.append_record('evaluation-assets',{'schema':'ai4r-evaluation-assets:1','id':'assets:multioutput',
        **{k:producer.assets[k] for k in ('profile_ref','configuration_ref','account_id','workspace_id','campaign_id')},
        'entries':[{'path':path,'sha256':ref['sha256'],'artifact_ref':ref,'role':role}
            for path,ref,role in [('capsule.json',declaration,'declaration'),('selected.json',output,'output')]],
        'cases':[{'case_id':'selected','entry_point':'E2','binding_ref':binding,'record_gate':False}]})
    resources=InstalledEvaluationResources(owner,profile_ref=producer.profile_ref,assets_ref=assets,library_snapshot_ref=producer.resources.snapshot_ref)
    replay=EvaluationProvider(store,owner.resources.operator,assets_ref=assets,resources=resources,library=owner.library)
    request={'request_id':'selected:replay','campaign_id':'campaign','case_id':'selected','evaluation_profile_id':producer.profile['profile_id'],
        'node_id':contract['node_id'],'verifier_cc_id':verifier_id,'declaration':{'path':'capsule.json','sha256':declaration['sha256']},
        'output':{'path':'selected.json','sha256':output['sha256']}}
    subject_ref,plan_ref,_=resources._subject(resources.assets['cases'][0])
    owner._validate(subject_ref,plan_ref,replay=True)
    bind_request_runtime(store,replay,request,'E2')
    original_observations=[r['ref'] for r in store.iter_records(kinds=('invocation-observation',))]
    assert replay.available_entry_points==('E2',),resources.unavailable_reasons
    result=await replay.node_replay(actor,request)
    assert result['tier1_verdict']=='PASS' and result['tier2_verdict']=='PASS',result['reason']
    assert len(prompts)==2 and len(result['model_calls'])==1 and result['model_calls'][0]['role']=='verifier'
    measured=store.read_record(result['evidence_refs'][0])
    assert measured['output_refs']==original.output_refs and len(measured['assessment_refs'])==1
    assert result['gate_decision']['output_refs']==[output] and result['advanced'] is False
    assert not list(store.iter_records(kinds=('gate-decision','acceptance-commit')))
    assert [r['ref'] for r in store.iter_records(kinds=('invocation-observation',))]==original_observations
    assert await replay.node_replay(actor,request)==result and len(prompts)==2
    store.close()
