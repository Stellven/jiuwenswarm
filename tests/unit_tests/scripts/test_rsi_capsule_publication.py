"""Proof reconciliation/merge tests use explicit synthetic protected receipts."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest
from jiuwenswarm.research_rsi.records import encoded
from jiuwenswarm.research_rsi.targets.capsules import public_fixtures, registered_capsule

spec=importlib.util.spec_from_file_location('capsule_publication',Path(__file__).parents[3]/'deploy/m1/rsi_capsule_publication.py')
pub=importlib.util.module_from_spec(spec);spec.loader.exec_module(pub)


@pytest.fixture
def baseline():
    name='utility.calculate'; target=registered_capsule(name)
    raw={}
    def put(value):
        body=value if isinstance(value,bytes) else encoded(value)
        digest=pub.sha(body); raw[digest]=body
        return {'id':digest+'.json','sha256':digest}
    def read(pin): return raw[pin['sha256']]
    body=b'# synthetic source only, never executed\n'
    body_ref=put(body); contract=put({'unit_contract':True}); hardware=put({'unit_hardware':True})
    manifest={'files':[{'path':'source/jiuwenswarm/'+target.carrier_path,'sha256':body_ref['sha256']}]}
    manifest_ref=put(manifest)
    grant={'schema':'ai4r-rsi-whole-capsule-development-grant:2','bootstrap_schema':'ai4r-rsi-capsule-bootstrap:2','run_id':'unit-baseline','capsule_name':name,
        'roles':['parent','candidate'],'scope':'public_m1_development_only','runtime_manifest_sha256':manifest_ref['sha256'],
        'limits':{'timeout_s':20},'worker':{'contract_ref':contract,'hardware_ref':hardware}}
    grant_ref=put(grant); rows=[]
    for index,fixture in enumerate(public_fixtures(name)):
        ident='capsule-'+pub.sha(encoded([grant['run_id'],'parent',fixture['id']]))[:48]
        input_ref=put({'packet':fixture['packet']});program_ref=put(b'# synthetic worker')
        start={'schema':'ai4r-rsi-whole-capsule-execution-start:1','job_id':ident,'grant_ref':grant_ref,
            'grant_sha256':grant_ref['sha256'],'candidate_ref':body_ref,'role':'parent','fixture_id':fixture['id'],
            'runtime_manifest_ref':manifest_ref,'runtime_manifest_sha256':manifest_ref['sha256'],
            'input_ref':input_ref,'program_ref':program_ref,'test_ref':put(fixture),'bootstrap_schema':grant['bootstrap_schema']}
        stdout=b'{"unit":"synthetic output"}';stdout_ref=put(stdout)
        receipt={'job_id':ident,'invocation_id':ident,'subject_ref':body_ref,'contract_ref':contract,
            'hardware_ref':hardware,'identity':{'executor_uid':12003,'executor_gid':12003},
            'argv':['/usr/local/bin/python3','-I','-S','/resources/worker.py'],'repeat_index':index,
            'sequence':1,'role':'treatment','seed':0,'observed_runtime':True,
            'stdout_ref':stdout_ref,'stderr_ref':put(b''),'observed_limits':{'isolation_probe_ref':put({'unit':True}),'admin_output_truncated':False},
            'wall_time_s':0.25,'termination_reason':'completed','exit_code':0}
        row={'start_ref':put(start),'candidate_ref':body_ref,'fixture_id':fixture['id'],
            'runtime_manifest_sha256':manifest_ref['sha256'],'input_ref':input_ref,'program_ref':program_ref,
            'receipt':receipt,'group_empty':True,'protected_wall_s':0.25,'output_bytes':len(stdout),
            'task_success':True,'checks_sha256':'c'*64,'bootstrap_schema':grant['bootstrap_schema'],'independent_check':{'task_success':True,'capsule_name':name,
                'input_sha256':input_ref['sha256'],'output_sha256':stdout_ref['sha256'],'output_bytes':len(stdout),'checks_sha256':'c'*64}}
        rows.append(dict(row,evidence_ref=put(row)))
    result={'schema':'ai4r-rsi-whole-capsule-visible-result:1','capsule_name':name,'security':'UNQUALIFIED',
        'model_calls':0,'hidden_evaluation':'NOT_RUN','admission_ref':None,'activation_ref':None,
        'grant_ref':grant_ref,'runtime_manifest_ref':manifest_ref,'role':'parent','scope':'public_m1_development_only',
        'executions':len(rows),'rows':rows,'passed_count':len(rows),'passed':True,'protected_wall_s':len(rows)*0.25}
    result['result_ref']=put(result)
    declaration={'identity':{'name':name,'version_label':'unit','carrier':{'ref':target.carrier_path.removeprefix('research/'),'sha256':body_ref['sha256']},
        'body':[{'path':target.carrier_path.removeprefix('research/'),'sha256':body_ref['sha256']}]}}
    meta={'workspace_id':'local','target_id':name,'target_name':'Calculate','mutable_path':target.carrier_path,'published_at':'2026-10-26T22:00:00Z'}
    return locals()


def test_complete_receipt_join_reports_measured_public_baseline(baseline):
    v=baseline
    packet=pub.baseline_packet(v['meta'],v['body'],v['declaration'],v['result'],v['read'])
    node=packet['snapshot']['nodes'][0]
    assert node['correctness']=='4/4 public checks'
    assert node['security_status']=='UNQUALIFIED'
    assert '1.000000 s' in node['speed']
    assert node['admit']['allowed'] is node['activate']['allowed'] is False


def test_interrupted_parent_reconciles_actual_failed_job_without_inventing_session_result(baseline):
    v=baseline;session,result=_session_result(v)
    result.update(status='ERROR_NO_REPLAY',exception_type='ValueError',model_calls=0,
        parent_visible=None,candidate_visible=None,candidate_ref=None)
    parent=copy.deepcopy(v['result']);parent.pop('result_ref')
    row=parent['rows'][0];row.pop('evidence_ref')
    row.update(task_success=False,independent_check=None)
    row['receipt'].update(exit_code=1,termination_reason='isolation_failure')
    row['evidence_ref']=v['put'](row)
    parent.update(rows=[row],executions=1,passed=False,passed_count=0,protected_wall_s=.25)
    parent['result_ref']=v['put'](parent)
    completion={'executions':1,'completed_roles':['parent'],'halted':True}
    before=copy.deepcopy(result)
    summary=pub.interrupted_parent_summary(session,result,completion,[parent],v['read'])
    assert summary['executions']==1 and summary['passed']==0 and result==before
    with pytest.raises(ValueError,match='ROOT_TERMINAL_EXECUTION_COUNT_DIFFERS'):
        pub.interrupted_parent_summary(session,result,dict(completion,executions=2),[parent],v['read'])


@pytest.mark.parametrize('field,value',[('passed_count',3),('protected_wall_s',0.0),('executions',3)])
def test_summary_cannot_replace_actual_root_original(baseline,field,value):
    v=baseline; result=copy.deepcopy(v['result']);result[field]=value
    with pytest.raises(ValueError,match='ROOT_RESULT_ORIGINAL_DIFFERS'):
        pub.visible_summary(result,name=v['name'],body_ref=v['body_ref'],read=v['read'])


def test_root_receipt_byte_capture_required(baseline):
    v=baseline; del v['raw'][v['result']['rows'][0]['receipt']['stdout_ref']['sha256']]
    with pytest.raises(KeyError): pub.visible_summary(v['result'],name=v['name'],body_ref=v['body_ref'],read=v['read'])


def test_merge_retains_existing_screening_tree_and_candidate(baseline):
    v=baseline; packet=pub.baseline_packet(v['meta'],v['body'],v['declaration'],v['result'],v['read'])
    previous=copy.deepcopy(packet); view=previous['snapshot'];view['targets'][0]['id']='screening-ranking-helper'
    view['nodes'][0].update(id='base:screening-unit',target_id='screening-ranking-helper')
    previous['candidates'][0]['node_id']='base:screening-unit'
    previous=pub.validate_publication(previous,workspace_id='local')
    merged=pub.merge_publication(previous,packet,'2026-10-26T23:00:00Z')
    assert merged['snapshot']['targets'][0]==previous['snapshot']['targets'][0]
    assert merged['snapshot']['nodes'][0]==previous['snapshot']['nodes'][0]
    assert merged['candidates'][0]==previous['candidates'][0]
    assert len(merged['snapshot']['targets'])==len(merged['snapshot']['nodes'])==2
    assert merged['snapshot']['revision']!=previous['snapshot']['revision']


def _session_result(v):
    session={'id':v['grant']['run_id'],'capsule_name':v['name'],'parent_body_ref':v['body_ref'],
        'parent_declaration_ref':v['put'](v['declaration']),'grant_ref':v['grant_ref'],'grant':v['grant'],
        'authorized_component':v['target'].carrier_path}
    result={'schema':'ai4r-rsi-capsule-session-result:1','id':session['id'],'capsule_name':v['name'],
        'security':'UNQUALIFIED','security_campaigns':'DEFERRED','qualification_ref':None,'package_ref':None,
        'admission_ref':None,'activation_ref':None,'hidden_evaluation':'NOT_RUN','final_evaluation':'NOT_RUN',
        'session_ref':v['put'](session),'parent_visible':v['result'],'candidate_visible':None,
        'candidate_ref':None,'model_calls':0,'status':'ERROR_NO_REPLAY','exception_type':'UnitFailure','rationale':None}
    return session,result


def test_poor_candidate_is_retained_with_actual_failed_public_outcome(baseline):
    v=baseline;session,result=_session_result(v)
    row=copy.deepcopy(v['rows'][0]); row.pop('evidence_ref')
    start=pub.captured(v['read'],row['start_ref']);start['role']='candidate'
    ident='capsule-'+pub.sha(encoded([v['grant']['run_id'],'candidate',row['fixture_id']]))[:48]
    start['job_id']=ident;row['start_ref']=v['put'](start)
    row['receipt'].update(job_id=ident,invocation_id=ident)
    row.update(task_success=False,independent_check={'task_success':False})
    row['evidence_ref']=v['put'](row)
    candidate=copy.deepcopy(v['result']);candidate.pop('result_ref')
    candidate.update(role='candidate',executions=1,rows=[row],passed_count=0,passed=False,protected_wall_s=0.25)
    candidate['result_ref']=v['put'](candidate)
    result.update(candidate_visible=candidate,candidate_ref=v['body_ref'],model_calls=2,
        status='VISIBLE_EVALUATED_UNQUALIFIED',exception_type=None,rationale='Synthetic failed proposal fixture')
    packet=pub.session_packet(v['meta'],session,result,v['read'],v['read'])
    node=packet['snapshot']['nodes'][1]
    assert node['evaluation_status']=='failed' and node['correctness']=='0/4 public checks'
    assert node['security_status']=='SECURITY_DEFERRED' and node['admission_status']=='unadmitted'
    assert packet['candidates'][1]['candidate_code']==v['body'].decode()


def test_session_error_before_new_parent_reuses_prior_proved_baseline(baseline):
    v=baseline;session,result=_session_result(v)
    previous=pub.baseline_packet(v['meta'],v['body'],v['declaration'],v['result'],v['read'])
    result['parent_visible']=None
    packet=pub.session_packet(v['meta'],session,result,v['read'],v['read'],previous=previous)
    assert packet['snapshot']['nodes']==previous['snapshot']['nodes']
    assert packet['snapshot']['runs'][0]['status']=='ERROR_NO_REPLAY'
    assert 'UnitFailure' in packet['snapshot']['runs'][0]['blockers'][0]


def test_pinned_projection_loads_lightweight_and_refuses_changed_bytes(baseline,monkeypatch):
    path=Path(__file__).parents[3]/'jiuwenswarm/server/rsi/cc_rsi_projection.py'
    monkeypatch.setattr(pub,'protected',lambda value,*a,**kw:Path(value))
    monkeypatch.setattr(pub,'_validator',None)
    pin={'path':str(path),'sha256':pub.sha(path.read_bytes())}
    pub.configure_projection(pin)
    assert pub._validator.__module__=='_capsule_public_projection'
    v=baseline
    packet=pub.baseline_packet(v['meta'],v['body'],v['declaration'],v['result'],v['read'])
    assert pub.validate_publication(packet,workspace_id='local')==packet
    with pytest.raises(ValueError,match='PUBLIC_PROJECTION_SOURCE_DIFFERS'):
        pub.configure_projection(dict(pin,sha256='0'*64))


def test_actual_controller_failure_has_terminal_activity_without_invented_candidate_or_calls(baseline):
    v=baseline;session,_=_session_result(v)
    previous=pub.baseline_packet(v['meta'],v['body'],v['declaration'],v['result'],v['read'])
    failure={'schema':'ai4r-rsi-capsule-controller-failure:1','id':session['id'],
        'exception_type':'FileNotFoundError','message':'/private/runtime/missing.py','status':'ERROR_NO_REPLAY'}
    packet=pub.controller_failure_packet(v['meta'],session,failure,previous)
    assert packet['snapshot']['nodes']==previous['snapshot']['nodes']
    assert packet['candidates']==previous['candidates']
    run=packet['snapshot']['runs'][0]
    assert run['status']=='ERROR_NO_REPLAY' and run['stage']=='Failed'
    assert run['budget']['diagnosis_calls'] is run['budget']['proposal_calls'] is None
    assert 'FileNotFoundError' in run['activity'][0]['summary']
    assert '/private/' not in str(packet)


def test_startup_failure_plan_joins_actual_zero_job_proofs_and_refuses_tampered_failure(baseline,tmp_path,monkeypatch):
    v=baseline;session,_=_session_result(v)
    def save(path,value):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(encoded(value));return pub.sha(path.read_bytes())
    control=tmp_path/'control';evidence=tmp_path/'evidence';records=tmp_path/'records';public=tmp_path/'public'
    cfg={'session':session,'evaluator':{'root':str(evidence)},'composition':{'record_root':str(records)},
        'claim_path':str(control/'run-claim.json'),'result_path':str(records/'capsule-result.json')}
    cfg_path=tmp_path/'configuration.json';cfg_sha=save(cfg_path,cfg)
    cid='f'*64
    exit_sha=save(control/'run-exit.json',{'cid':cid,'exit_code':1})
    save(control/'run-container.json',{'cid':cid,'id':session['id']})
    complete_sha=save(evidence/'complete.json',{'schema':'ai4r-rsi-capsule-evaluator-completion:1',
        'id':session['id'],'configuration_sha256':cfg_sha,'grant_ref':session['grant_ref'],
        'status':'STOPPED','executions':0,'completed_roles':[]})
    save(evidence/'owner.json',{'schema':'ai4r-rsi-capsule-evaluator-owner:1','id':session['id'],
        'configuration_sha256':cfg_sha,'uid':0,'gid':0,'groups':[]})
    save(control/'run-claim.json',{'schema':'ai4r-rsi-capsule-run-claim:1','id':session['id'],'configuration_sha256':cfg_sha})
    failure_path=records/'controller-failure.json'
    failure_sha=save(failure_path,{'schema':'ai4r-rsi-capsule-controller-failure:1','id':session['id'],
        'exception_type':'FileNotFoundError','message':'retained actual startup exception','status':'ERROR_NO_REPLAY'})
    previous=pub.baseline_packet(v['meta'],v['body'],v['declaration'],v['result'],v['read'])
    previous_sha=save(public/'publication.json',previous)
    value={'schema':'ai4r-capsule-startup-failure-publication:1','projection':{'path':'unit','sha256':'a'*64},
        'meta':v['meta'],'configuration':{'path':str(cfg_path),'sha256':cfg_sha},'control_directory':str(control),
        'publication_directory':str(public),'expected_previous_sha256':previous_sha,
        'controller_failure_sha256':failure_sha,'evaluator_completion_sha256':complete_sha,'run_exit_sha256':exit_sha}
    input_path=tmp_path/'input.json';save(input_path,value)
    monkeypatch.setattr(pub,'protected',lambda path,*a,**k:Path(path))
    monkeypatch.setattr(pub,'_directory',lambda path:Path(path))
    monkeypatch.setattr(pub,'configure_projection',lambda pin:None)
    _,facts,packet=pub.startup_failure_plan(input_path)
    assert facts['reexecuted'] is False and facts['model_calls'] is None
    assert facts['code_jobs']==facts['publication_model_calls']==0
    assert packet['snapshot']['nodes']==previous['snapshot']['nodes']
    assert pub.sha((public/'publication.json').read_bytes())==previous_sha
    # An independently captured Root no-effect observation can establish zero
    # calls, but stale Core rows invalidate it before any public write.
    import sqlite3
    core_root=tmp_path/'core';(core_root/'state').mkdir(parents=True)
    db=sqlite3.connect(core_root/'state/research.sqlite3')
    for table in ('model_calls','tool_calls','attempts'):db.execute('CREATE TABLE '+table+' (run_id TEXT)')
    db.commit();db.close()
    own_ids=['rsi-development:'+session['id']+':'+role for role in ('diagnosis','proposal')]
    cfg['composition'].update(core_root=str(core_root),run_contexts={ident:{} for ident in own_ids})
    cfg_sha=save(cfg_path,cfg);value['configuration']['sha256']=cfg_sha
    completion=json.loads((evidence/'complete.json').read_bytes());completion['configuration_sha256']=cfg_sha
    complete_sha=save(evidence/'complete.json',completion);value['evaluator_completion_sha256']=complete_sha
    owner=json.loads((evidence/'owner.json').read_bytes());owner['configuration_sha256']=cfg_sha;save(evidence/'owner.json',owner)
    claim=json.loads((control/'run-claim.json').read_bytes());claim['configuration_sha256']=cfg_sha;save(control/'run-claim.json',claim)
    image='sha256:'+'1'*64;save(control/'run-container.json',{'cid':cid,'id':session['id'],'image':image})
    def pin(path):return {'path':str(path),'sha256':pub.sha(path.read_bytes())}
    journal=tmp_path/'journal'
    identity={'target_id':session['capsule_name'],'revision':'d'*64,'client_request_id':'unit-click'}
    save(journal/'claim.json',{'identity':identity})
    save(journal/'ack.json',dict(identity,run_id=session['id'],status='ACCEPTED_UNQUALIFIED'))
    save(journal/'launcher-exit.json',{'pid':123,'wait_status':256})
    observation={'schema':'ai4r-capsule-no-effect-observation:1','run_id':session['id'],
        'configuration':value['configuration'],'observed_unix_s':1000,
        'container':{'id':cid,'image':image,'running':False,'pid':0,'exit_code':1},
        'core':{'root':str(core_root),'own_run_ids':own_ids,'own_counts':{'model_calls':0,'tool_calls':0,'attempts':0},
            'global_tables':{table:{'count':0,'rows_sha256':pub.sha(b'[]')} for table in ('model_calls','tool_calls','attempts')}},
        'native_lease_rows':0,'relay_ledger_sha256':'a'*64,'benchmark_ledger_sha256':'b'*64,
        'evaluator_completion':pin(evidence/'complete.json'),'controller_failure':pin(failure_path),
        'run_exit':pin(control/'run-exit.json'),'accepted_claim':pin(journal/'claim.json'),
        'accepted_ack':pin(journal/'ack.json'),'launcher_exit':pin(journal/'launcher-exit.json'),
        'execution_jobs':0,'all_job_groups_empty':True,'job_group_count':1,'model_calls':0,'tool_calls':0,
        'attempt_starts':0,'no_replay_authority':True}
    observation_path=tmp_path/'no-effect.json';save(observation_path,observation)
    value['no_effect_observation']=pin(observation_path);save(input_path,value)
    _,facts,packet=pub.startup_failure_plan(input_path)
    assert facts['model_calls']==0 and packet['snapshot']['runs'][0]['budget']['diagnosis_calls']==0
    db=sqlite3.connect(core_root/'state/research.sqlite3');db.execute('INSERT INTO model_calls VALUES (?)',('foreign',));db.commit();db.close()
    with pytest.raises(ValueError,match='ACTUAL_CORE_CHANGED_SINCE_NO_EFFECT_OBSERVATION'):
        pub.startup_failure_plan(input_path)
    value.pop('no_effect_observation');save(input_path,value)
    failure_path.write_bytes(b'{}')
    with pytest.raises(ValueError,match='ACTUAL_STARTUP_FAILURE_BYTES_DIFFER'):
        pub.startup_failure_plan(input_path)
