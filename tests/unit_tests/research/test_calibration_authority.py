"""IF014 controls use explicit unit profiles and controlled model transcripts only."""
import copy
import hashlib
import inspect
import json
import time
import pytest
from jiuwenswarm.research.contracts import Principal,ResearchError
from jiuwenswarm.research.state import SQLiteRunStore,json_bytes,utc_now


async def prepared(tmp_path,*,calls=5,wall=120):
    from jiuwenswarm.research.calibration_authority import CalibrationAuthority
    from jiuwenswarm.research.checks import CheckRegistry
    from jiuwenswarm.research.checks.assets import CheckAssetAdmissions,CHALLENGES
    from jiuwenswarm.research.checks.calibration import CalibrationMeasurements
    from jiuwenswarm.research.checks.calibration_runtime import prepare_calibration_checks
    store=SQLiteRunStore(tmp_path);checks=CheckRegistry();assets=await prepare_calibration_checks(store,checks)
    asset=assets['intent'];subject=store.put_blob(b'{"controlled_invalid_subject":true}')
    checking=store.read_record(asset['profile_ref']);bundle=store.read_record(asset['bundle_ref'])
    cases=[]
    for kind,ids in [('bundle',[c['check_id'] for c in bundle['checks']]),('criteria',[c['criterion_id'] for c in checking['criteria']])]:
        expected=store.put_blob(json_bytes({key:'FAIL' for key in ids}))
        for challenge in sorted(CHALLENGES):cases.append({'case_id':kind+':'+challenge,'asset_kind':kind,'challenge_class':challenge,
            'declaration_ref':asset['declaration_ref'],'subject_ref':subject,'expected_ref':expected,'output_port':'intent'})
    runner=store.put_blob(__import__('pathlib').Path(inspect.getfile(CalibrationMeasurements)).read_bytes())
    profile=store.put_blob(json_bytes({'schema':'ai4r-check-calibration:1','id':'explicit-unit-profile','bundle_ref':asset['bundle_ref'],
        'profile_ref':asset['profile_ref'],'measurement_runner_ref':runner,'cases':cases}))
    contexts={}
    for case in cases:
        contract=store.append_record('calibration-subject',{'schema':'ai4r-calibration-subject:1','id':'unit-subject:'+case['case_id'],
            'declaration_ref':asset['declaration_ref'],'inputs':[],'input_refs':[],'outputs':[{'name':'intent','contract_id':'intent-ir','required':True}]})
        contexts[case['case_id']]=store.append_record('calibration-context',{'contract_ref':contract,'observation_ref':None,'output_refs':{'intent':subject}})
    policy=store.put_record('plan-policy',{'schema_version':'1.0.0','id':'unit-calibration-policy','max_nodes':12,
        'allowed_effect_classes':['pure','read'],'allow_network':False,'required_stages':[],
        'aggregate_limits':{'time_s':600,'model_calls':10,'memory_mb':512},'max_attempts_per_node':1})
    config=store.put_blob(json_bytes({'cc':{'plan_policy_ref':policy}}));deployment=store.put_blob(b'explicit fixed subscription deployment')
    selection=store.put_record('model-selection-profile',{'schema_version':'1.0.0','id':'unit-fixed','policy_mode':'fixed_baseline',
        'approved_model_ids':['codex-cli-default'],'extra_requirements':{},'selection_allowance':{'enabled':False,'deployment_ref':None,
        'model_calls':0,'time_s':0,'output_tokens':0,'disclosure_scope':[]},'alternate_model_id':None,'policy_ref':policy})
    runtime=store.append_record('calibration-runtime',{'schema':'ai4r-calibration-runtime:1','id':'explicit-unit-runtime',
        'configuration_ref':config,'model_selection_profile_ref':selection,'deployment_ref':deployment,
        'verifier_declaration_ref':assets['verifier']['declaration_ref'],'approved_profile_refs':[profile],
        'case_context_refs':{profile['sha256']:contexts},'limits':{'time_s':wall,'model_calls':calls,'memory_mb':256}})
    authority=CalibrationAuthority(store,runtime,configuration_ref=config,model_selection_profile_ref=selection,
        deployment_ref=deployment,policy_ref=policy)
    actor=Principal('os:0:unit-operator',operations=frozenset({'verifier_assets'}))
    return store,checks,assets,profile,authority,actor


@pytest.mark.asyncio
async def test_private_calibration_claims_one_call_per_case_without_product_run_and_binds_prompt(tmp_path):
    store,checks,assets,profile,authority,actor=await prepared(tmp_path)
    request=authority.start(profile,actor,'unit-action');authority.register(profile,actor)
    grant=authority.prepare_calibration_case({'request_ref':request,'case_id':'criteria:ambiguity'})['grant_ref']
    value=store.read_record(grant);protected=authority.authorize_model_context({'execution_id':value['execution_id'],'call_ordinal':1})
    assert protected['contract_ref']==grant and protected['call_function']=='verifier'
    assert protected['limits']['model_calls']==1 and protected['expected_prompt_sha256']==value['expected_prompt_sha256']
    assert 'expected_ref' not in authority.prompt(grant) and 'controlled_invalid_subject' in authority.prompt(grant)
    assert hashlib.sha256(authority.prompt(grant).encode()).hexdigest()==protected['expected_prompt_sha256']
    with pytest.raises(ResearchError):authority.authorize_model_context({'execution_id':value['execution_id'],'call_ordinal':1})
    live=authority.authorize_model_dispatch({key:protected[key] for key in ('execution_id','invocation_id','call_id','call_claim_ref','contract_ref')})
    assert live['expected_prompt_sha256']==protected['expected_prompt_sha256']
    assert not store.connection.execute('SELECT 1 FROM runs').fetchone()
    assert not list(store.iter_records(kinds=('library-admission','activation-record','gate-decision')))


@pytest.mark.asyncio
async def test_request_deadline_is_anchored_before_preparation_and_survives_reopen(tmp_path):
    store,_,_,profile,authority,actor=await prepared(tmp_path,wall=120)
    request=authority.start(profile,actor,'deadline-action');authority.register(profile,actor)
    with store.transaction() as db:db.execute('UPDATE private_calibration_requests SET deadline_epoch=?',(time.time()-1,))
    with pytest.raises(ResearchError,match='calibration_deadline'):
        authority.prepare_calibration_case({'request_ref':request,'case_id':'criteria:ambiguity'})
    assert authority.start(profile,actor,'deadline-action')==request
    with pytest.raises(ResearchError):authority.prepare_calibration_case({'request_ref':request,'case_id':'criteria:ambiguity'})
    from jiuwenswarm.research.calibration_authority import CalibrationAuthority
    reopened=SQLiteRunStore(tmp_path,recover=False)
    another=CalibrationAuthority(reopened,authority.runtime_ref,configuration_ref=authority.runtime['configuration_ref'],
        model_selection_profile_ref=authority.runtime['model_selection_profile_ref'],deployment_ref=authority.runtime['deployment_ref'],policy_ref=authority.policy_ref)
    assert another.start(profile,actor,'deadline-action')==request
    with pytest.raises(ResearchError):another.prepare_calibration_case({'request_ref':request,'case_id':'criteria:ambiguity'})


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['foreign_profile','worker_case','ordinal','caller_hash','aggregate','changed_context'])
async def test_finite_calibration_authority_rejects_before_model_effect(tmp_path,fault):
    store,_,_,profile,authority,actor=await prepared(tmp_path,calls=1 if fault=='aggregate' else 5)
    request=authority.start(profile,actor,'negative-action');authority.register(profile,actor)
    if fault=='foreign_profile':
        with pytest.raises(ResearchError):authority.start(store.put_blob(b'{}'),actor,'other')
        return
    if fault=='worker_case':
        with pytest.raises(ResearchError):authority.prepare_calibration_case({'request_ref':request,'case_id':'bundle:ambiguity'})
        return
    grant=authority.prepare_calibration_case({'request_ref':request,'case_id':'criteria:ambiguity'})['grant_ref'];value=store.read_record(grant)
    context={'execution_id':value['execution_id'],'call_ordinal':2 if fault=='ordinal' else 1}
    if fault=='caller_hash':context['expected_prompt_sha256']='0'*64
    if fault=='changed_context':
        with store.transaction() as db:db.execute("UPDATE private_calibration_requests SET state='cancelled'")
    if fault=='aggregate':
        authority.authorize_model_context(context)
        other=authority.prepare_calibration_case({'request_ref':request,'case_id':'criteria:omissions'})['grant_ref']
        context={'execution_id':store.read_record(other)['execution_id'],'call_ordinal':1}
    with pytest.raises(ResearchError):authority.authorize_model_context(context)


@pytest.mark.asyncio
async def test_cancellation_ack_requires_actual_owner_and_revokes_even_closed_grants(tmp_path):
    store,_,_,profile,authority,actor=await prepared(tmp_path)
    request=authority.start(profile,actor,'cancel-action');authority.register(profile,actor)
    grant=authority.prepare_calibration_case({'request_ref':request,'case_id':'criteria:ambiguity'})['grant_ref']
    class Unknown:
        async def contain_run(self,*args):return {'contained':False}
    authority.model=Unknown()
    with pytest.raises(ResearchError,match='calibration_containment_uncertain'):await authority.cancel_calibration({'request_ref':request})
    assert authority.inspect_calibration({'request_ref':request})['state']=='containment_unknown'
    with pytest.raises(ResearchError):authority.authorize_model_context({'execution_id':store.read_record(grant)['execution_id'],'call_ordinal':1})


@pytest.mark.asyncio
@pytest.mark.parametrize('final_fault',[None,'deadline','audit'])
async def test_actual_private_bridge_and_independent_criteria_admission_do_not_qualify_missing_bundle_context(tmp_path,final_fault):
    from jiuwenswarm.research.bridge import GovernedBridge
    from jiuwenswarm.research.contracts import validate
    store,_,_,profile,authority,actor=await prepared(tmp_path,wall=240)
    calls=[]
    class ControlledSubscription:
        async def invoke_governed(self,prompt,**kwargs):
            payload=json.loads(prompt.split('<subject_payload>\n')[1].split('\n</subject_payload>')[0])
            assert set(payload)=={'subject_declaration','subject_output'}
            assert 'expected_ref' not in prompt and 'unit-subject:' not in prompt
            criteria=json.loads(prompt.split('Criteria for this output:\n')[1].split('\n\n<subject_payload>')[0]);calls.append(prompt)
            return {'text':json.dumps({'findings':[{'criterion_id':c['criterion_id'],'outcome':'FAIL','reason':'Explicit controlled invalid unit subject'} for c in criteria],
                'uncertainties':[],'limitations':[],'required_correction':'Controlled fixture lacks required fields'}),'observed_runtime':True,
                'identity':{'effective':None,'basis':'Controlled subscription transcript, no live model qualification'},'usage':{}}
    bridge=GovernedBridge(persist=store.append_record,authorize=authority.authorize_model_context,revalidate=authority.authorize_model_dispatch,
        subscription_service=ControlledSubscription(),validate_record=validate)
    class OwnedBridgePort:
        async def call(self,context,prompt):return await bridge.call(context,prompt)
        async def contain_run(self,run_id,request_id):return await bridge.contain_run(authority.authorize_containment({'run_id':run_id,'request_id':request_id}))
    authority.model=OwnedBridgePort()
    original_append=store.append_record
    def capture(kind,record):
        if final_fault and kind=='calibration-request-result' and record['id'].endswith(':result'):
            if final_fault=='audit':raise OSError('Controlled final evidence publication failure')
            with store.transaction() as db:db.execute('UPDATE private_calibration_requests SET deadline_epoch=?',(time.time()-1,))
        return original_append(kind,record)
    store.append_record=capture
    result=await authority.execute(profile,actor,'actual-private-controlled')
    assert len(calls)==5,[(store.read_record(ref)['case_id'],store.read_record(ref)['status'],store.read_record(ref)['reason_code']) for ref in result['measurement_refs']]
    assert result['status']=='blocked'
    if final_fault:
        assert result['reason_code'] is not None
        assert not store.connection.execute('SELECT 1 FROM checking_asset_admissions').fetchone()
        with pytest.raises(ResearchError):authority.admissions.require(store.read_record(profile)['bundle_ref'],store.read_record(profile)['profile_ref'])
        with pytest.raises(ResearchError,match='calibration_only'):store.require_product_material([result['criteria_admission_ref']])
        return
    assert store.read_record(result['bundle_admission_ref'])['status']=='blocked'
    for ref in result['measurement_refs']:
        measured=store.read_record(ref)
        if measured['asset_kind']=='criteria' and measured['result'] is not None:
            fixed=store.read_record(profile);case=next(c for c in fixed['cases'] if c['case_id']==measured['case_id'])
            assert authority.admissions._outcomes(fixed,case,measured['result'],measured['registration_ref'])
    assert store.read_record(result['criteria_admission_ref'])['status']=='admitted',[(store.read_record(ref)['case_id'],store.read_record(ref)['status'],store.read_record(ref)['reason_code']) for ref in result['measurement_refs']]
    store.require_product_material([result['criteria_admission_ref']])
    measured=next(store.read_record(ref) for ref in result['measurement_refs'] if store.read_record(ref)['asset_kind']=='criteria')
    with pytest.raises(ResearchError,match='calibration_only'):store.require_product_material([measured['result']['result_ref']])
    renamed=store.put_blob(store.read_blob(measured['result']['result_ref']),record_id='unit-republished-calibration')
    with pytest.raises(ResearchError,match='calibration_only'):store.require_product_material([renamed])
    wrapped=store.put_blob(json_bytes({'hidden_raw_ref':measured['result']['result_ref']}))
    with pytest.raises(ResearchError,match='calibration_only'):store.require_product_material([wrapped])
    twice=store.put_blob(json_bytes({'indirect_ref':wrapped}))
    with pytest.raises(ResearchError,match='calibration_only'):store.require_product_material([twice])
    assert not store.connection.execute('SELECT 1 FROM runs').fetchone()
    assert not list(store.iter_records(kinds=('library-admission','gate-decision','activation-record')))
    assert await authority.execute(profile,actor,'actual-private-controlled')==result and len(calls)==5
    fixed=store.read_record(profile);case=next(c for c in fixed['cases'] if c['case_id']==measured['case_id'])
    with store.transaction() as db:db.execute('UPDATE private_calibration_requests SET calls=calls+1')
    with pytest.raises(ResearchError,match='calibration_attribution'):authority.admissions._outcomes(fixed,case,measured['result'],measured['registration_ref'])
    with store.transaction() as db:db.execute('UPDATE private_calibration_requests SET calls=calls-1')
    assert authority.admissions._outcomes(fixed,case,measured['result'],measured['registration_ref'])
    original_return=next(r['record'] for r in store.iter_records(kinds=('calibration-call-return',)) if r['record']['call_ref']==measured['result']['model_call_refs'][0])
    store.append_record('calibration-call-return',dict(original_return,id='unit-foreign-call-return',returned_epoch=time.time()+1000))
    with pytest.raises(ResearchError,match='calibration_attribution'):authority.admissions._outcomes(fixed,case,measured['result'],measured['registration_ref'])


@pytest.mark.asyncio
async def test_failed_claim_publication_retains_once_charge_and_never_resends(tmp_path):
    store,_,_,profile,authority,actor=await prepared(tmp_path)
    request=authority.start(profile,actor,'audit-action');authority.register(profile,actor)
    grant=authority.prepare_calibration_case({'request_ref':request,'case_id':'criteria:ambiguity'})['grant_ref']
    context={'execution_id':store.read_record(grant)['execution_id'],'call_ordinal':1};original=store.append_record
    def fail(kind,record):
        if kind=='calibration-call-claim':raise OSError('Controlled durable publication failure')
        return original(kind,record)
    store.append_record=fail
    with pytest.raises(OSError):authority.authorize_model_context(context)
    store.append_record=original
    with pytest.raises(ResearchError):authority.authorize_model_context(context)
    assert store.connection.execute('SELECT calls FROM private_calibration_requests').fetchone()['calls']==1
    assert not list(store.iter_records(kinds=('model-call-start',)))


@pytest.mark.asyncio
async def test_native_composite_authorization_uses_real_private_ipc_and_cannot_fall_through(tmp_path):
    import os
    from types import SimpleNamespace
    from jiuwenswarm.research.native_ports import NativePorts,AUTH_PROTOCOL
    from jiuwenswarm.research.private_rpc import PrivateRPCClient
    store,_,_,profile,authority,actor=await prepared(tmp_path/'state')
    request=authority.start(profile,actor,'ipc-action');authority.register(profile,actor)
    root=tmp_path/'ipc';root.mkdir(mode=0o700);root.chmod(0o700)
    session={'session_id':'explicit-unit-session','capability':'explicit-unit-private-capability-value'}
    (root/'session.json').write_bytes(json_bytes(session));(root/'session.json').chmod(0o600)
    ports=NativePorts(ipc_root=root,app_uid=os.geteuid())
    class Ordinary:
        def authorize_model_context(self,payload):raise AssertionError('Private authority fell through to an ordinary run')
        def authorize_model_dispatch(self,payload):raise AssertionError('Private dispatch fell through')
        def authorize_containment(self,payload):raise AssertionError('Private containment fell through')
        def authorize_executor_binding(self,payload):raise ResearchError('invalid_request','No executor permission in calibration')
    await ports.bind_composition(SimpleNamespace(library=SimpleNamespace(self_test_provider=None),calibration_authority=authority),{},None)
    await ports.bind_runner(Ordinary())
    rpc=PrivateRPCClient(root/'authorization.sock',protocol=AUTH_PROTOCOL,peer_uid=os.geteuid(),**session)
    try:
        granted=await rpc.call('prepare_calibration_case',{'request_ref':request,'case_id':'criteria:ambiguity'})
        grant=store.read_record(granted['grant_ref'])
        protected=await rpc.call('authorize_model_context',{'execution_id':grant['execution_id'],'call_ordinal':1})
        live=await rpc.call('authorize_model_dispatch',{key:protected[key] for key in ('execution_id','invocation_id','call_id','call_claim_ref','contract_ref')})
        assert live['expected_prompt_sha256']==grant['expected_prompt_sha256']
        with pytest.raises(Exception):await rpc.call('authorize_model_context',{'execution_id':'calibration-execution:unknown','call_ordinal':1})
        with pytest.raises(Exception):await rpc.call('authorize_executor_binding',{'contract_ref':granted['grant_ref'],'invocation_id':grant['invocation_id'],'execution_id':grant['execution_id']})
    finally:await ports.close()


@pytest.mark.asyncio
async def test_os_action_missing_optional_runtime_blocks_only_the_explicit_calibration_operation(tmp_path):
    from types import SimpleNamespace
    from jiuwenswarm.research.library import LibraryService
    from jiuwenswarm.research.library_operator import OperatorLibrary
    store=SQLiteRunStore(tmp_path);settings={'cc':{'plan_policy_ref':store.put_blob(b'explicit unit policy')}}
    configuration=store.put_blob(json_bytes(settings));actor=Principal('os:0:unit',operations=frozenset({'verifier_assets'}))
    owner=OperatorLibrary(store,LibraryService(store),SimpleNamespace(snapshot=lambda:settings),{'configuration_ref':configuration},actor)
    action=store.put_blob(json_bytes({'schema':'ai4r-library-action:1','id':'missing-runtime','calibration_profile_ref':store.put_blob(b'explicit missing-profile bytes')}))
    result=await owner.execute('calibrate-checks',action)
    assert result['status']=='blocked' and not list(store.iter_records(kinds=('model-call','library-admission','activation-record')))


@pytest.mark.asyncio
async def test_original_whole_request_deadline_covers_slow_preparation_and_prevents_asset_publication(tmp_path,monkeypatch):
    import asyncio
    from jiuwenswarm.research.checks import calibration_runtime
    store,_,_,profile,authority,actor=await prepared(tmp_path,wall=3)
    contained=[]
    class Owned:
        async def contain_run(self,run_id,request_id):
            contained.append((run_id,request_id));return {'contained':True,'run_id':run_id,'request_id':request_id}
    authority.model=Owned()
    async def slow(*args,**kwargs):await asyncio.sleep(4)
    monkeypatch.setattr(calibration_runtime,'prepare_calibration_checks',slow)
    result=await authority.execute(profile,actor,'slow-preparation')
    assert result['status']=='blocked' and result['reason_code']=='TimeoutError'
    assert len(contained)==1 and authority.inspect_calibration({'request_ref':result['request_ref']})['state']=='cancelled'
    assert not store.connection.execute('SELECT 1 FROM checking_asset_admissions').fetchone()
    assert not list(store.iter_records(kinds=('model-call-start','checking-asset-admission')))
    assert await authority.cancel_calibration({'request_ref':result['request_ref']})=={'contained':True,'request_ref':result['request_ref']}
    assert len(contained)==1


@pytest.mark.asyncio
async def test_containment_true_with_foreign_scope_does_not_claim_stopped(tmp_path):
    store,_,_,profile,authority,actor=await prepared(tmp_path)
    request=authority.start(profile,actor,'foreign-ack')
    class Foreign:
        async def contain_run(self,run_id,request_id):return {'contained':True,'run_id':'wrong-run','request_id':request_id}
    authority.model=Foreign()
    with pytest.raises(ResearchError,match='calibration_containment_uncertain'):await authority.cancel_calibration({'request_ref':request})
    assert authority.inspect_calibration({'request_ref':request})['state']=='containment_unknown'


@pytest.mark.asyncio
async def test_forged_staged_admitted_boolean_without_complete_original_measurements_never_publishes(tmp_path):
    store,_,_,profile,authority,actor=await prepared(tmp_path)
    authority.start(profile,actor,'forged-stage');registration=authority.register(profile,actor)
    fixed,closure,_=authority.admissions._registered(profile)
    forged=store.append_record('checking-asset-admission',{'id':'unit-forged-staged-admission','asset_kind':'criteria',
        'asset_ref':fixed['profile_ref'],'calibration_profile_ref':profile,'registration_ref':registration,'closure':closure,
        'measurement_refs':[],'status':'admitted','reasons':[],'actor':actor.account_id,'recorded_at':'2026-10-17T01:00:00Z'})
    with pytest.raises(ResearchError):authority.admissions.publish_admissions({'criteria':forged},guard=lambda:None,commit=lambda db:None)
    assert not store.connection.execute('SELECT 1 FROM checking_asset_admissions').fetchone()


@pytest.mark.asyncio
async def test_timeout_retains_original_completed_partial_measurements_and_origin_exclusion(tmp_path,monkeypatch):
    import asyncio
    store,_,_,profile,authority,actor=await prepared(tmp_path,wall=3)
    captured=[]
    class Owned:
        async def contain_run(self,run_id,request_id):return {'contained':True,'run_id':run_id,'request_id':request_id}
    authority.model=Owned()
    async def partial(profile_ref,actual_actor):
        fixed,_,registration=authority.admissions._registered(profile_ref);case=fixed['cases'][0]
        ref=store.append_record('calibration-measurement',{'id':'unit-original-partial-measurement',
            'profile_ref':profile_ref,'registration_ref':registration,'case_id':case['case_id'],'asset_kind':case['asset_kind'],
            'result':None,'status':'blocked','reason_code':'Explicit controlled partial receipt','recorded_at':utc_now()})
        with store.transaction() as db:db.execute('INSERT INTO calibration_attempts VALUES(?,?,?,?)',
            (profile_ref['sha256'],case['case_id'],'blocked',json_bytes(ref).decode()))
        captured.append(ref);await asyncio.sleep(4)
    monkeypatch.setattr(authority.admissions,'measure',partial)
    result=await authority.execute(profile,actor,'partial-timeout')
    assert result['status']=='blocked' and result['measurement_refs']==captured
    assert not store.connection.execute('SELECT 1 FROM checking_asset_admissions').fetchone()
    with pytest.raises(ResearchError,match='calibration_only'):store.require_product_material(captured)

