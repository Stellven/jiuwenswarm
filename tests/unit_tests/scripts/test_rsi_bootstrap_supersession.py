"""Root selection tests only; never models, releases, admission or fixtures."""
import copy
import asyncio
import base64
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest

SOURCE=Path(__file__).parents[3]/'deploy/m1/rsi_bootstrap_supersession.py'
spec=importlib.util.spec_from_file_location('bootstrap_supersession_test',SOURCE)
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

def pin(name):return {'id':name,'sha256':s.digest(name.encode())}

def context():
    request={'schema':'ai4r-rsi-bootstrap-supersession-input:1','generation':'run-one','supersession_id':'capacity-one','stage':'planner',
        'fresh_profile_generation':'run-one-capacity','authorization':'Explicit bounded Root stage supersession after exact native containment',
        'original_bootstrap_sha256':'a'*64,'containment_receipt_ref':pin('containment'),'prior_uncertain_ref':pin('uncertain'),
        'release_record_ref':pin('release'),'failed_model_call_ref':pin('failed'),'blocked_measurement_ref':pin('blocked'),
        'budget_caps':{'pre_delivery':67,'setup':74,'including_rsi':76}}
    old_profile={'id':'authored-local-catalog:planner:source:generation:run-one','cases':[{'case_id':'planner:criteria:good','expected_ref':pin('expected')}],
        'measurement_runner_ref':pin('runner'),'bundle_ref':pin('bundle'),'profile_ref':pin('checking')}
    new_profile=copy.deepcopy(old_profile);new_profile['id']='authored-local-catalog:planner:source:generation:run-one-capacity'
    rows=[{'stage':name,'profile_ref':pin(name),'model_calls_ceiling':6,'declaration_ref':pin(name+'declaration')} for name in ('verifier','planner','delivery')]
    original={'schema':'ai4r-rsi-operational-bootstrap:3','generation':'run-one','account_id':'unchanged-account','root':'/own/controller',
        'model':'gpt-6.1-sol','installed_source_sha256':'b'*64,'binding_ref':pin('old-binding'),'calibration_runtime_ref':pin('old-runtime'),
        'configuration_ref':pin('configuration'),'model_selection_profile_ref':pin('selection'),'deployment_ref':pin('deployment'),
        'profile_generations':{row['stage']:'run-one' for row in rows},'stages':rows,'prior_namespaces':['legacy']}
    new_rows=copy.deepcopy(rows);new_rows[1]['profile_ref']=pin('new-planner')
    selected={**original,'binding_ref':pin('new-binding'),'calibration_runtime_ref':pin('new-runtime'),
        'profile_generations':{**original['profile_generations'],'planner':'run-one-capacity'},'stages':new_rows}
    old_runtime={'schema':'runtime','id':'old','approved_profile_refs':[row['profile_ref'] for row in rows],
        'case_context_refs':{row['profile_ref']['sha256']:{'unchanged-case':pin(row['stage']+'context')} for row in rows},
        'configuration_ref':pin('configuration')}
    new_runtime=copy.deepcopy(old_runtime);new_runtime['id']='new';new_runtime['approved_profile_refs'][1]=pin('new-planner')
    new_runtime['case_context_refs'][pin('new-planner')['sha256']]=new_runtime['case_context_refs'].pop(pin('planner')['sha256'])
    old_binding={'configuration_ref':pin('configuration'),'protected_options':{'calibration_runtime_ref':pin('old-runtime'),
        'calibration_profile_refs':old_runtime['approved_profile_refs'],'calibration_limitations':['unchanged limitation'],'development_builtin_catalog':False}}
    new_binding=copy.deepcopy(old_binding);new_binding['protected_options'].update(calibration_runtime_ref=pin('new-runtime'),calibration_profile_refs=new_runtime['approved_profile_refs'])
    return request,original,selected,old_runtime,new_runtime,old_binding,new_binding,(old_profile,new_profile)

def validate(values):s.validate_successor(values[1],values[2],values[0],*values[3:])

def test_complete_fresh_profile_preserves_every_other_profile_context_and_admission_binding():
    values=context();before=copy.deepcopy(values);validate(values);assert values==before

@pytest.mark.parametrize('fault',['case','other-profile','context','source','account','model','configuration','binding','generation'])
def test_successor_cannot_change_cases_source_identity_or_unrelated_stage(fault):
    values=list(copy.deepcopy(context()))
    if fault=='case':values[7][1]['cases'][0]['expected_ref']=pin('new-expected')
    elif fault=='other-profile':values[2]['stages'][0]['profile_ref']=pin('changed-verifier')
    elif fault=='context':values[4]['case_context_refs'][pin('new-planner')['sha256']]={'foreign':pin('new-context')}
    elif fault=='source':values[2]['installed_source_sha256']='c'*64
    elif fault=='account':values[2]['account_id']='foreign'
    elif fault=='model':values[2]['model']='another-model'
    elif fault=='configuration':values[2]['configuration_ref']=pin('new-configuration')
    elif fault=='binding':values[6]['protected_options']['development_builtin_catalog']=True
    else:values[2]['profile_generations']['planner']='run-one'
    with pytest.raises(ValueError):validate(values)

def test_root_budget_cannot_widen_or_exclude_historical_call_charges():
    request=context()[0]
    for key in request['budget_caps']:
        changed=copy.deepcopy(request);changed['budget_caps'][key]+=1000
        with pytest.raises(ValueError):s.validate_input(changed)

def test_missing_expected_selector_never_falls_back_to_original(tmp_path):
    original={'generation':'run-one'}
    assert s.selected_bootstrap(original,b'{}',path=tmp_path/'absent')==(original,None)
    with pytest.raises(ValueError,match='MOUNT_ABSENT'):
        s.selected_bootstrap(original,b'{}',path=tmp_path/'absent',expected={'supersession_id':'capacity-one','claim_sha256':'a'*64})

def test_original_sql_rows_cannot_be_reset_or_reclassified():
    before={'calls':[b'failed',b'completed'],'cases':[b'blocked']}
    s.preserves_snapshot(before,{'calls':[b'failed',b'completed'],'cases':[b'blocked'],'new':[]})
    with pytest.raises(ValueError):s.preserves_snapshot(before,{'calls':[b'completed'],'cases':[b'matched']})

ROOT=pytest.mark.skipif(os.name!='posix' or os.geteuid()!=0,reason='actual Root custody')

def write(path,value):s.new(path,s.encoded(value))

@ROOT
@pytest.mark.parametrize('fault',[None,'claim-only','missing-complete','changed-case-selector','repeated','user-owned-parent'])
def test_completion_last_root_selector_and_required_mount(tmp_path,fault):
    path=tmp_path/'selection';s.mkdir(path)
    request,original,selected,*_=context();original_raw=s.encoded(original);request['original_bootstrap_sha256']=s.digest(original_raw)
    generation={'schema':'ai4r-rsi-bootstrap-generation:3','generation':'run-one','profile_generations':original['profile_generations']}
    write(path/'input.json',request);s.new(path/'original-bootstrap.json',original_raw)
    claim={'schema':'ai4r-rsi-bootstrap-supersession-claim:1','input_sha256':s.digest(s.encoded(request)),
        'original_bootstrap_sha256':request['original_bootstrap_sha256'],'generation':'run-one','supersession_id':'capacity-one'}
    write(path/'claim.json',claim)
    if fault=='claim-only':
        with pytest.raises(ValueError,match='PARTIAL'):s.completed_selection(path)
        return
    write(path/'original-generation.json',generation)
    expected={'supersession_id':'capacity-one','claim_sha256':s.digest(s.encoded(claim))}
    write(path/'generation.json',{**generation,'schema':'ai4r-rsi-bootstrap-generation:4','selection_required':expected})
    prepared={'manifest':selected,'request_sha256':s.digest(s.encoded(request)),'model_calls':0,'qualification_adopted':False}
    write(path/'prepared.json',prepared)
    plan={'request':request,'claim_sha256':s.digest(s.encoded(claim)),'prepared_sha256':s.digest(s.encoded(prepared))}
    write(path/'plan.json',plan)
    selector={'schema':'ai4r-rsi-bootstrap-selector:1','generation':'run-one','supersession_id':'capacity-one',
        'plan_sha256':s.digest(s.encoded(plan)),'prepared_sha256':s.digest(s.encoded(prepared))}
    write(path/'selector.json',selector)
    if fault!='missing-complete':
        write(path/'complete.json',{'schema':'ai4r-rsi-bootstrap-supersession-complete:1','claim_sha256':s.digest(s.encoded(claim)),
            'plan_sha256':s.digest(s.encoded(plan)),'selector_sha256':s.digest(s.encoded(selector)),'prepared_sha256':s.digest(s.encoded(prepared))})
    if fault=='changed-case-selector':(path/'selector.json').chmod(0o600);(path/'selector.json').write_bytes(b'{}');(path/'selector.json').chmod(0o440)
    if fault=='user-owned-parent':os.chown(tmp_path,12001,12001)
    if fault in {'missing-complete','changed-case-selector','user-owned-parent'}:
        with pytest.raises(ValueError):s.selected_bootstrap(original,original_raw,path=path,expected=expected)
    elif fault=='repeated':
        with pytest.raises(FileExistsError):write(path/'claim.json',claim)
    else:
        assert s.selected_bootstrap(original,original_raw,path=path,expected=expected)[0]==selected

def test_uncertain_or_generic_complete_native_lease_cannot_authorize_staging():
    class DB:
        def __init__(self,state):self.state=state
        def execute(self,*args):return SimpleNamespace(fetchone=lambda:(self.state,json.dumps(pin('different'))))
    for state in ('uncertain','active','complete'):
        with pytest.raises(ValueError,match='EXACT_SUPPORTED_NATIVE_RELEASE'):
            s.assert_released(SimpleNamespace(db=DB(state)),pin('scope'),pin('containment'))

def test_release_of_another_effect_with_the_same_profile_cannot_authorize_capacity_retry():
    request=context()[0];failure={'old_stage_calls':[request['failed_model_call_ref'],pin('partial-one'),pin('partial-two')]}
    good={'no_dispatch_start_observed':False,'known_terminal_call_refs':failure['old_stage_calls']}
    for proof in (dict(good,no_dispatch_start_observed=True),dict(good,known_terminal_call_refs=[pin('foreign')])):
        with pytest.raises(ValueError,match='FAILED_EFFECT_LEASE'):
            s.released_failure_join(SimpleNamespace(get=lambda _:dict(proof=proof)),request,failure)
    s.released_failure_join(SimpleNamespace(get=lambda _:dict(proof=good)),request,failure)

@pytest.mark.parametrize('fault',[None,'semantic-mismatch','foreign-case','other-provider','unknown','prior-contained','prior-unaccounted','wrong-stage','duplicate-start'])
def test_structured_capacity_failure_requires_original_request_case_and_matched_partial_history(fault):
    request,original,*_=context();profile_ref=original['stages'][1]['profile_ref']
    cases=[{'case_id':'planner:criteria:'+name,'asset_kind':'criteria','subject_ref':pin(name)} for name in ('positive','injection','omissions')]
    records={};kinds={}
    def put(value,record,kind):records[value['id']]=record;kinds[value['id']]=kind;return value
    put(profile_ref,{'cases':cases},'blob')
    callids=['partial-one','partial-two','failed'];calls=[];starts=[];attempts=[];indexed=[]
    private=put(pin('private-request'),{'id':'private-request','calibration_profile_ref':profile_ref,'runtime_ref':original['calibration_runtime_ref']},'check-calibration-request')
    for index,name in enumerate(callids):
        callref=request['failed_model_call_ref'] if index==2 else pin(name)
        call={'id':name,'execution_id':'execution:'+name,'invocation_id':'invocation:'+name,
            'outcome':'failed' if index==2 else 'completed','call_function':'verifier','observed_runtime':True,'provider_error_code':'provider_error'}
        put(callref,call,'model-call');calls.append({'ref':callref,'record':call})
        grant=put(pin('grant:'+name),{'request_ref':private,'case_id':cases[index]['case_id'],'subject_ref':cases[index]['subject_ref'],
            'execution_id':call['execution_id'],'invocation_id':call['invocation_id']},'calibration-case-grant')
        claim=put(pin('claim:'+name),{'grant_ref':grant,'call_id':name,'execution_id':call['execution_id'],'invocation_id':call['invocation_id']},'calibration-call-claim')
        indexed.append({'request_id':'private-request','call_id':name,'case_id':cases[index]['case_id'],'claim_ref':json.dumps(claim)})
        starts.append({'ref':pin('start:'+name),'record':{'call_id':name,'call_claim_ref':claim}})
        result=put(pin('assessment:'+name),{'unit':'synthetic result'},'assessment')
        measurement_ref=request['blocked_measurement_ref'] if index==2 else pin('measurement:'+name)
        measurement={'profile_ref':profile_ref,'case_id':cases[index]['case_id'],'status':'blocked' if index==2 else 'matched',
            'reason_code':'provider_error' if index==2 else None,'result':None if index==2 else {'result_ref':result,'model_call_refs':[callref]}}
        put(measurement_ref,measurement,'calibration-measurement')
        attempts.append({'case_id':cases[index]['case_id'],'state':measurement['status'],'receipt_ref':json.dumps(measurement_ref)})
    frame=json.dumps({'method':'turn/completed','params':{'turn':{'status':'failed','error':{'codexErrorInfo':'serverOverloaded'}}}})+'\n'
    bundle={'schema':'ai4r-host-codex-response:2','requested_model':'gpt-6.1-sol','account_fingerprint':'unit-no-account',
        'binary_sha256':'a'*64,'reasoning_effort':'medium','thread_start':None,'turn_start':None,'turn_completed':0,
        'wire_frames':[{'direction':'in','raw_b64':base64.b64encode(frame.encode()).decode()}],
        'error_code':'provider_error','outcome':'failed','evidence':{'full_original_trace':True,'unavailable_reason':None,'observed_frames':1,'observed_bytes':len(frame.encode())}}
    native=put(pin('native'),{'scope':{'call_id':'failed','invocation_id':'invocation:failed','execution_id':'execution:failed'},'raw_ref':pin('native-raw')},'host-codex-native-original')
    records[request['failed_model_call_ref']['id']]['evidence_refs']=[native]
    if fault=='semantic-mismatch':records[pin('measurement:partial-one')['id']]['status']='mismatched';attempts[0]['state']='mismatched'
    if fault=='foreign-case':records[pin('grant:failed')['id']]['case_id']='foreign'
    if fault=='other-provider':bundle['error_code']='auth_failed'
    if fault=='unknown':records[request['failed_model_call_ref']['id']]['outcome']='outcome_unknown'
    known=[]
    if fault in {'prior-contained','prior-unaccounted'}:
        previous=pin('previous-failed');calls.append({'ref':previous,'record':{'id':'previous-failed','outcome':'failed'}})
        starts.append({'ref':pin('previous-start'),'record':{'call_id':'previous-failed'}})
        if fault=='prior-contained':known=[previous]
    if fault=='wrong-stage':request['stage']='verifier'
    if fault=='duplicate-start':starts[0]['record']['call_id']=starts[1]['record']['call_id']
    records['native-raw']=bundle
    class DB:
        def execute(self,query,args):
            rows=[indexed[2]] if 'WHERE call_id' in query else indexed if 'FROM private_calibration_calls' in query else attempts
            return SimpleNamespace(fetchall=lambda:rows)
    class Store:
        connection=DB()
        def read_record(self,value,contract_id=None):return copy.deepcopy(records[value['id']])
        def read_blob(self,value):return s.encoded(records[value['id']])
        def record_kind(self,value):return kinds[value['id']]
        def iter_records(self,kinds):return iter(calls if kinds==('model-call',) else starts)
    if fault and fault!='prior-contained':
        with pytest.raises(ValueError):s.failed_capacity(Store(),original,request,known_failed_refs=known)
    else:
        result=s.failed_capacity(Store(),original,request,known_failed_refs=known)
        assert result['old_stage_calls_charged']==3 and result['all_started_model_calls']==(4 if known else 3)

def test_real_installed_catalog_metadata_recapture_changes_only_one_profile_identity(tmp_path):
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.catalog_calibration import capture_catalog_calibration
    store=SQLiteRunStore(tmp_path/'core')
    try:
        refs={name:store.put_blob(s.encoded({'unit':name,'models':'never constructed'})) for name in ('configuration_ref','model_selection_profile_ref','deployment_ref')}
        first=asyncio.run(capture_catalog_calibration(store,**refs,profile_generations={'planner':'one'}))
        second=asyncio.run(capture_catalog_calibration(store,**refs,profile_generations={'planner':'two'}))
        before={store.read_record(value)['id'].split(':')[1]:value for value in first['profile_refs']}
        after={store.read_record(value)['id'].split(':')[1]:value for value in second['profile_refs']}
        assert set(before)==set(after) and all(before[name]==after[name] for name in before if name!='planner')
        old=store.read_record(before['planner']);new=store.read_record(after['planner'])
        assert old['id']!=new['id'] and {k:v for k,v in old.items() if k!='id'}=={k:v for k,v in new.items() if k!='id'}
        assert not list(store.iter_records(kinds=('model-call-start','model-call','calibration-measurement','library-admission')))
    finally:store.close()

@pytest.mark.parametrize('kind',['check-calibration-request','calibration-case-grant','calibration-call-claim','calibration-measurement'])
def test_fresh_profile_cannot_reuse_any_prior_request_grant_call_or_measurement(kind):
    profile=pin('fresh-profile');runtime=pin('fresh-runtime')
    record={'calibration_profile_ref':profile} if kind!='calibration-measurement' else {'profile_ref':profile}
    core=SimpleNamespace(connection=SimpleNamespace(execute=lambda *args:SimpleNamespace(fetchone=lambda:None)),
        iter_records=lambda **kwargs:iter([{'kind':kind,'record':record}]))
    with pytest.raises(ValueError,match='FRESH_PROFILE_HAS_PRIOR'):
        s.assert_fresh(core,profile,runtime)

@ROOT
def test_second_root_generation_cannot_expand_single_supersession_authority(tmp_path):
    (tmp_path/'config').mkdir()
    parent=tmp_path/'config/bootstrap-supersessions';s.mkdir(parent)
    s.mkdir(parent/'one');s.mkdir(parent/'two')
    with pytest.raises(ValueError,match='PARTIAL'):
        s.verify_deployment_selections(tmp_path)


def completed_fixture(path,request,original,selected,prior=None):
    s.mkdir(path)
    if prior:s.copy_selection(prior,path/'ancestry')
    request=copy.deepcopy(request);request['original_bootstrap_sha256']=s.digest(s.encoded(original))
    generation={'schema':'ai4r-rsi-bootstrap-generation:3','generation':original['generation'],'profile_generations':original['profile_generations']}
    claim={'schema':'ai4r-rsi-bootstrap-supersession-claim:1','input_sha256':s.digest(s.encoded(request)),
        'original_bootstrap_sha256':request['original_bootstrap_sha256'],'generation':request['generation'],'supersession_id':request['supersession_id']}
    prepared={'manifest':selected,'request_sha256':s.digest(s.encoded(request)),'model_calls':0,'qualification_adopted':False}
    plan={'request':request,'claim_sha256':s.digest(s.encoded(claim)),'prepared_sha256':s.digest(s.encoded(prepared))}
    selector={'schema':'ai4r-rsi-bootstrap-selector:1','generation':request['generation'],'supersession_id':request['supersession_id'],
        'plan_sha256':s.digest(s.encoded(plan)),'prepared_sha256':s.digest(s.encoded(prepared))}
    complete={'schema':'ai4r-rsi-bootstrap-supersession-complete:1','claim_sha256':s.digest(s.encoded(claim)),
        'plan_sha256':s.digest(s.encoded(plan)),'selector_sha256':s.digest(s.encoded(selector)),'prepared_sha256':s.digest(s.encoded(prepared))}
    expectation={'supersession_id':request['supersession_id'],'claim_sha256':s.digest(s.encoded(claim))}
    rows={'input.json':request,'original-bootstrap.json':original,'claim.json':claim,'original-generation.json':generation,
        'generation.json':{**generation,'schema':'ai4r-rsi-bootstrap-generation:4','selection_required':expectation},
        'prepared.json':prepared,'plan.json':plan,'selector.json':selector,'complete.json':complete}
    for name,value in rows.items():write(path/name,value)
    return request,prepared,expectation


def next_request(prior,path,stage='verifier'):
    request,prepared,_=prior
    return {**request,'schema':'ai4r-rsi-bootstrap-supersession-input:2','supersession_id':'capacity-two','stage':stage,
        'fresh_profile_generation':'run-two-capacity','failed_model_call_ref':pin('failed-two'),'blocked_measurement_ref':pin('blocked-two'),
        'predecessor':{'supersession_id':request['supersession_id'],'completion_sha256':s.digest(s.read(path/'complete.json')),
            'selected_manifest_sha256':s.digest(s.encoded(prepared['manifest']))},'budget_caps':{'pre_delivery':68,'setup':75,'including_rsi':77}}


@ROOT
@pytest.mark.parametrize('fault',[None,'ancestor-tamper','missing-completion','cycle','wrong-predecessor','wrong-stage','reuse-generation','source','branch'])
def test_linear_root_chain_preserves_planner_and_rejects_tamper_cycles_or_branches(tmp_path,fault):
    config=tmp_path/'config';config.mkdir();parent=config/'bootstrap-supersessions';s.mkdir(parent)
    request,original,planner,*_=context();first_path=parent/request['generation']
    first=completed_fixture(first_path,request,original,planner)
    request2=next_request(first,first_path)
    second=copy.deepcopy(planner);second['binding_ref']=pin('binding-two');second['calibration_runtime_ref']=pin('runtime-two')
    second['profile_generations']['verifier']=request2['fresh_profile_generation'];second['stages'][0]['profile_ref']=pin('fresh-verifier')
    if fault=='wrong-predecessor':request2['predecessor']['completion_sha256']='f'*64
    if fault=='cycle':request2['predecessor']['supersession_id']=request2['supersession_id']
    if fault=='reuse-generation':request2['fresh_profile_generation']=request['fresh_profile_generation'];second['profile_generations']['verifier']=request2['fresh_profile_generation']
    if fault=='wrong-stage':request2['stage']='planner'
    if fault=='source':second['installed_source_sha256']='f'*64
    second_path=parent/request2['supersession_id']
    second_fixture=completed_fixture(second_path,request2,original,second,first_path)
    if fault=='ancestor-tamper':
        path=second_path/'ancestry/plan.json';path.chmod(0o600);path.write_bytes(b'{}');path.chmod(0o440)
    if fault=='missing-completion':(second_path/'ancestry/complete.json').unlink()
    if fault=='branch':
        branch=copy.deepcopy(request2);branch['supersession_id']='capacity-branch'
        completed_fixture(parent/'capacity-branch',branch,original,second,first_path)
    if fault:
        with pytest.raises((ValueError,KeyError,FileNotFoundError)):s.verify_deployment_selections(tmp_path)
    else:
        original_bytes={p.name:p.read_bytes() for p in first_path.iterdir() if p.is_file()}
        s.verify_deployment_selections(tmp_path)
        selected,_=s.selected_bootstrap(original,s.encoded(original),path=second_path,expected=second_fixture[2])
        assert selected==second and selected['stages'][1]==planner['stages'][1]
        assert len(s.issued_chain(tmp_path))==2
        assert s.predecessor(original,request2,s.issued_chain(tmp_path,pending=second_path))==planner
        assert {p.name:p.read_bytes() for p in first_path.iterdir() if p.is_file()}==original_bytes


def test_chain_source_ceiling_is_finite_and_not_dispatch_authorization():
    first=context()[0]
    request={**first,'schema':'ai4r-rsi-bootstrap-supersession-input:2','supersession_id':'capacity-two',
        'predecessor':{'supersession_id':'capacity-one','completion_sha256':'a'*64,'selected_manifest_sha256':'b'*64},
        'budget_caps':{'pre_delivery':68,'setup':75,'including_rsi':77}}
    s.validate_input(request)
    request['budget_caps']={'pre_delivery':89,'setup':96,'including_rsi':98}
    with pytest.raises(ValueError,match='BOUNDED'):s.validate_input(request)


@ROOT
@pytest.mark.parametrize('fault',[None,'uncontained','undercharge','historical-tamper','reused-charge'])
def test_history_rejoins_each_original_failure_release_and_full_charge_population(tmp_path,monkeypatch,fault):
    request,original,planner,*_=context();first_path=tmp_path/'first'
    first=completed_fixture(first_path,request,original,planner)
    next_item=next_request(first,first_path)
    next_item['budget_caps']={'pre_delivery':16,'setup':22,'including_rsi':24}
    failures=[{'profile_ref':original['stages'][1]['profile_ref'],'old_stage_calls':[pin('old-one'),pin('old-two'),request['failed_model_call_ref']],
        'old_stage_calls_charged':3,'all_started_model_calls':10},
        {'profile_ref':planner['stages'][0]['profile_ref'],'old_stage_calls':[next_item['failed_model_call_ref']],
        'old_stage_calls_charged':1,'all_started_model_calls':10}]
    prepared=dict(first[1],failure=dict(failures[0],all_started_model_calls=3))
    chain=[(first[0],prepared,first_path)]
    # The predecessor pin is tied to the immutable prepared manifest; a cached
    # historical count cannot authorize current effects without reclassification.
    calls=[];releases=[];transitions=[]
    def classify(store,base,item,known_failed_refs=()):
        index=0 if item['supersession_id']==request['supersession_id'] else 1
        assert base==(original if index==0 else planner)
        assert known_failed_refs==[next_item['failed_model_call_ref'] if index==0 else request['failed_model_call_ref']]
        calls.append(index)
        return copy.deepcopy(failures[index])
    def release(leases,scope,item,require_current=True):
        releases.append(require_current)
        if fault=='uncontained' and require_current:raise ValueError('EXACT_SUPPORTED_NATIVE_RELEASE_REQUIRED')
        index=0 if item['supersession_id']==request['supersession_id'] else 1
        return {},{'contract_ref':failures[index]['profile_ref']}
    monkeypatch.setattr(s,'failed_capacity',classify);monkeypatch.setattr(s,'release_chain',release)
    monkeypatch.setattr(s,'check_transition',lambda *args:transitions.append(args))
    proof_by_ref={request['prior_uncertain_ref']['id']:{'proof':{'no_dispatch_start_observed':False,'known_terminal_call_refs':failures[0]['old_stage_calls']}}}
    next_item['prior_uncertain_ref']=pin('uncertain-two')
    proof_by_ref['uncertain-two']={'proof':{'no_dispatch_start_observed':False,'known_terminal_call_refs':failures[1]['old_stage_calls']}}
    if fault=='undercharge':next_item['budget_caps']['pre_delivery']-=1
    if fault=='historical-tamper':prepared['failure']['old_stage_calls_charged']=2
    if fault=='reused-charge':failures[1]['old_stage_calls'].append(pin('old-one'))
    leases=SimpleNamespace(get=lambda ref:proof_by_ref[ref['id']])
    if fault:
        with pytest.raises(ValueError):s.history_facts(None,leases,pin('scope'),original,next_item,chain)
    else:
        current,failure,charges=s.history_facts(None,leases,pin('scope'),original,next_item,chain)
        assert current==planner and failure==failures[1] and charges==4
        assert calls==[0,1] and releases==[False,True] and len(transitions)==1


@ROOT
def test_four_link_ceiling_and_repeated_stage_never_reuse_prior_profile_generation(tmp_path):
    request,original,selected,*_=context();path=tmp_path/'first'
    prior=completed_fixture(path,request,original,selected)
    for index in range(2,5):
        item=next_request(prior,path,stage='planner')
        item.update(supersession_id='capacity-'+str(index),fresh_profile_generation='fresh-'+str(index),failed_model_call_ref=pin('failed-'+str(index)))
        child=copy.deepcopy(prior[1]['manifest']);child['profile_generations']['planner']=item['fresh_profile_generation']
        child['stages'][1]['profile_ref']=pin('profile-'+str(index))
        child['binding_ref']=pin('binding-'+str(index));child['calibration_runtime_ref']=pin('runtime-'+str(index))
        next_path=tmp_path/('link-'+str(index));prior=completed_fixture(next_path,item,original,child,path);path=next_path
    chain=s.selection_chain(path);assert len(chain)==4
    with pytest.raises(ValueError,match='BOUNDED_PREDECESSOR'):
        s.predecessor(original,next_request(prior,path),chain)
