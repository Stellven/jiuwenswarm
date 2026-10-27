"""Proof reconciliation/merge tests use explicit synthetic protected receipts."""
import copy
import importlib.util
import json
import math
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


# --------------------------------------------------------------------------
# Legacy publication bytes are unchanged by the loop publisher.
# --------------------------------------------------------------------------
EVIDENCE=Path(__file__).parents[3]/'docs/review/evidence-20261026'
# sha256(encoded(packet)) of these synthetic legacy scenarios as produced by
# the pre-loop publisher (rsi-loop commit 69d2921); the loop work must not
# change a single byte of legacy Screening/R1/R2-shaped publications.
LEGACY_DIGESTS={
    'baseline':'93cb4fb23297047778799fc51dae6d5686827f2038908bacda0c09bc888b8c07',
    'session_error':'cef45c62b3f4a2684efe1049546d0c83967bd842ff6c382f77c9585f97732052',
    'session_reuse':'cef45c62b3f4a2684efe1049546d0c83967bd842ff6c382f77c9585f97732052',
    'controller_failure':'1abc5188286222d121fccd894fe2d86346ac7099b394b32f145cd8df33d7b803',
    'controller_failure_zero':'1879a70e7d1299ccd09756f9c94ff0ad073e88e0f64c679e0e66c61db5b6e948',
    'merge':'540046136b762775b501ebc7f4efcb79cfbd8e4bc8ad6413cfe54a5bd60a66c3'}


def test_legacy_single_attempt_publications_are_byte_identical(baseline):
    v=baseline;out={}
    out['baseline']=pub.baseline_packet(v['meta'],v['body'],v['declaration'],v['result'],v['read'])
    session,result=_session_result(v)
    out['session_error']=pub.session_packet(v['meta'],session,copy.deepcopy(result),v['read'],v['read'])
    reuse=copy.deepcopy(result);reuse['parent_visible']=None
    out['session_reuse']=pub.session_packet(v['meta'],session,reuse,v['read'],v['read'],previous=out['baseline'])
    failure={'schema':'ai4r-rsi-capsule-controller-failure:1','id':session['id'],
        'exception_type':'FileNotFoundError','message':'x','status':'ERROR_NO_REPLAY'}
    out['controller_failure']=pub.controller_failure_packet(v['meta'],session,failure,out['baseline'])
    out['controller_failure_zero']=pub.controller_failure_packet(v['meta'],session,failure,out['baseline'],model_calls=0)
    out['merge']=pub.merge_publication(out['baseline'],out['session_error'],'2026-10-26T23:00:00Z')
    assert {key:pub.sha(encoded(value)) for key,value in out.items()}==LEGACY_DIGESTS
    assert pub.session_limits(session)==(2,3600)  # Legacy sessions keep the historical two-call budget.


def test_legacy_claim_and_no_effect_contracts_match_retained_evidence():
    plan=json.loads((EVIDENCE/'calculate-r2-interrupted-publication-plan.json').read_text())
    claim=plan['output']['claim']
    result_raw=b'retained'
    built=pub.completed_claim(claim['id'],claim['configuration_sha256'],result_raw)
    assert set(built)==set(claim) and built['schema']==claim['schema']
    assert {k:built[k] for k in ('id','configuration_sha256')}=={k:claim[k] for k in ('id','configuration_sha256')}
    observation=json.loads((EVIDENCE/'calculate-startup-no-effect-observation-r1.json').read_text())
    assert set(observation)==pub.NO_EFFECT_OBSERVATION_FIELDS


# --------------------------------------------------------------------------
# Iterative loop sessions: every terminal state from retained evidence.
# --------------------------------------------------------------------------
LOOP_GRANT='ai4r-rsi-whole-capsule-development-grant:3'


@pytest.fixture
def loop_world():
    from jiuwenswarm.research_rsi.targets.capsule_executor import grant_fixtures
    name='utility.calculate'; target=registered_capsule(name); raw={}
    def put(value):
        body=value if isinstance(value,bytes) else encoded(value)
        digest=pub.sha(body); raw[digest]=body
        return {'id':digest+'.json','sha256':digest}
    def read(pin): return raw[pin['sha256']]
    parent=b'# synthetic loop parent, never executed\n'; parent_ref=put(parent)
    contract=put({'unit_contract':True}); hardware=put({'unit_hardware':True})
    manifest={'files':[{'path':'source/jiuwenswarm/'+target.carrier_path,'sha256':parent_ref['sha256']}]}
    manifest_ref=put(manifest)
    grant={'schema':LOOP_GRANT,'bootstrap_schema':'ai4r-rsi-capsule-bootstrap:2','run_id':'unit-loop-r1','capsule_name':name,
        'roles':['parent','candidate'],'scope':'public_m1_development_only','runtime_manifest_sha256':manifest_ref['sha256'],
        'limits':{'timeout_s':20,'wall_s':1200},'worker':{'contract_ref':contract,'hardware_ref':hardware}}
    grant_ref=put(grant); fixtures=grant_fixtures(grant)
    def visible(role,body_ref,iteration,trials,*,fail=(),scope='public_m1_development_only'):
        trial_rows=[]
        for trial in range(trials):
            rows=[]
            for index,fixture in enumerate(fixtures):
                ident='capsule-'+pub.sha(encoded([grant['run_id'],role,iteration,body_ref['sha256'],trial,fixture['id']]))[:48]
                input_ref=put({'packet':fixture['packet']});program_ref=put(b'# synthetic worker')
                start={'schema':'ai4r-rsi-whole-capsule-execution-start:1','job_id':ident,'grant_ref':grant_ref,
                    'grant_sha256':grant_ref['sha256'],'binding_ref':None,'candidate_ref':body_ref,'role':role,'fixture_id':fixture['id'],
                    'runtime_manifest_ref':manifest_ref,'runtime_manifest_sha256':manifest_ref['sha256'],'input_ref':input_ref,
                    'program_ref':program_ref,'test_ref':put(fixture),'bootstrap_schema':grant['bootstrap_schema'],'recorded_unix_ns':1}
                stdout=b'{"unit":"synthetic output"}';stdout_ref=put(stdout)
                receipt={'job_id':ident,'invocation_id':ident,'subject_ref':body_ref,'contract_ref':contract,
                    'hardware_ref':hardware,'identity':{'executor_uid':12003,'executor_gid':12003},
                    'argv':['/usr/local/bin/python3','-I','-S','/resources/worker.py'],'repeat_index':index,
                    'sequence':1,'role':'treatment','seed':0,'observed_runtime':True,'stdout_ref':stdout_ref,'stderr_ref':put(b''),
                    'observed_limits':{'isolation_probe_ref':put({'unit':True}),'admin_output_truncated':False},
                    'wall_time_s':0.25,'termination_reason':'completed','exit_code':0}
                ok=fixture['id'] not in fail
                check={'task_success':True,'capsule_name':name,'checks_sha256':'c'*64,'output_bytes':len(stdout),'checks':[]}
                if fixture['fixture_set']=='public':
                    check.update(input_sha256=input_ref['sha256'],output_sha256=stdout_ref['sha256'])
                row={'schema':'ai4r-rsi-whole-capsule-visible-check:1','start_ref':put(start),'receipt':receipt,
                    'independent_check':check if ok else {'task_success':False,'checks':[]},'fixture_id':fixture['id'],
                    'task_success':ok,'group_empty':True,'output_bytes':len(stdout),'protected_wall_s':0.25,'batch_iterations':1,
                    'bootstrap_schema':grant['bootstrap_schema'],'candidate_ref':body_ref,'input_ref':input_ref,'program_ref':program_ref,
                    'runtime_manifest_sha256':manifest_ref['sha256'],'checks_sha256':'c'*64,'role':role,'iteration':iteration,
                    'trial':trial,'check_ref':put({'check':fixture['id']}),'fixture_set':fixture['fixture_set'],
                    'fixture_group':fixture['fixture_group'],'checks':[]}
                rows.append(dict(row,evidence_ref=put(row)))
            trial_rows.append(rows)
        rows=trial_rows[0];passed=sum(r['task_success'] for r in rows)
        result={'schema':'ai4r-rsi-whole-capsule-visible-result:2','capsule_name':name,'grant_ref':grant_ref,'binding_ref':None,
            'runtime_manifest_ref':manifest_ref,'role':role,'iteration':iteration,'subject_sha256':body_ref['sha256'],
            'executions':sum(len(t) for t in trial_rows),'passed_count':passed,'case_count':len(rows),
            'held_out_case_count':sum(r['fixture_set']=='held_out' for r in rows),'passed':passed==len(rows),
            'protected_wall_s':sum(r['protected_wall_s'] for r in rows),
            'trial_wall_s':[sum(r['protected_wall_s'] for r in t) for t in trial_rows],'rows':rows,'trial_rows':trial_rows[1:],
            'failure':None if passed==len(rows) else {'exception_type':'IndependentCheckFailed','message':'[x] failed'},
            'model_calls':0,'security':'UNQUALIFIED','hidden_evaluation':'NOT_RUN','admission_ref':None,'activation_ref':None,'scope':scope}
        return dict(result,result_ref=put(result))
    declaration={'identity':{'name':name,'version_label':'unit'}}
    session={'id':grant['run_id'],'capsule_name':name,'parent_body_ref':parent_ref,'parent_declaration_ref':put(declaration),
        'grant_ref':grant_ref,'grant':grant,'authorized_component':target.carrier_path,
        'loop':{'model_backend':{'kind':'fake'},'max_iterations':3,'max_model_calls':6}}
    parent_raw=visible('parent',parent_ref,0,3)
    held=[f['id'] for f in fixtures if f['fixture_set']=='held_out']
    bodies=[b'# synthetic candidate one\n',b'# synthetic candidate two\n']
    refs=[put(b) for b in bodies]
    first=visible('candidate',refs[0],1,1); second=visible('candidate',refs[1],2,1,fail=held[:1])
    def reduced(raw_result): return pub.reviewer_view(raw_result)
    def iteration(k,ref,raw_result,kept,outcome='kept',calls=2):
        return {'iteration':k,'candidate_ref':ref,'rationale':'Synthetic rationale %d'%k,
            'visible':None if raw_result is None else reduced(raw_result),
            'score':None if raw_result is None else {'correctness':{'parent':1.0,'candidate':raw_result['passed_count']/raw_result['case_count']},
                'latency_ratio':0.9,'noise_floor_ratio':0.05,'above_noise':True,'improved':kept,'regressed':not kept,
                'summary':'synthetic score %d'%k,'feedback':'synthetic feedback'},
            'kept':kept,'outcome':outcome,'reason':'synthetic reason %d'%k,'model_calls':calls,'elapsed_s':1.5,'failure':None}
    loop={'schema':'ai4r-rsi-capsule-loop:1','max_iterations':3,'completed_iterations':2,'stop_reason':'max_iterations',
        'stop_detail':None,'model_backend':{'kind':'fake','model':'scripted','pinned_sha256':None},
        'configuration':{'max_model_calls':6,'wall_s':1200,'max_iterations':3},'model_calls':4,
        'iterations':[iteration(1,refs[0],first,True),iteration(2,refs[1],second,False,'not_kept')],
        'best':{'iteration':1,'candidate_ref':refs[0],'score':None},'parent_visible':reduced(parent_raw),
        'noise':{'method':'capsule_objective.calibrate_noise','trials':3},'limitations':[]}
    loop['best']['score']=loop['iterations'][0]['score']
    result={'schema':'ai4r-rsi-capsule-session-result:1','id':session['id'],'capsule_name':name,'security':'UNQUALIFIED',
        'security_campaigns':'DEFERRED','qualification_ref':None,'package_ref':None,'admission_ref':None,'activation_ref':None,
        'hidden_evaluation':'NOT_RUN','final_evaluation':'NOT_RUN','session_ref':put(session),'parent_visible':parent_raw,
        'candidate_visible':first,'candidate_ref':refs[0],'model_calls':4,'status':'VISIBLE_EVALUATED_UNQUALIFIED',
        'exception_type':None,'rationale':'Synthetic rationale 1','loop':loop}
    meta={'workspace_id':'local','target_id':name,'target_name':'Calculate','mutable_path':target.carrier_path,
          'published_at':'2026-10-27T10:00:00Z'}
    served=parent_raw['executions']+first['executions']+second['executions']
    return locals()


def _loop_packet(w,result,*,issued=None,previous=None,exit_code=0):
    served=sum(x['executions'] for x in [result['parent_visible'],*[r['visible'] for r in result['loop']['iterations']]] if x is not None)
    return pub.loop_session_packet(w['meta'],w['session'],result,w['read'],w['read'],previous,served=served,
        issued=served if issued is None else issued,evaluator={'status':'STOPPED','stop':None,'exit_code':exit_code})


def test_loop_success_publishes_every_iteration_candidate_and_score(loop_world):
    w=loop_world
    packet=_loop_packet(w,w['result'])
    nodes={n['id']:n for n in packet['snapshot']['nodes']}
    base='base:'+w['parent_ref']['sha256']
    assert nodes[base]['correctness']=='%d/%d checks (%d/%d public, %d/%d held-out)'%(
        (len(w['fixtures']),)*2+(len(w['fixtures'])-len(w['held']),)*2+(len(w['held']),)*2)
    one,two=('candidate:unit-loop-r1:'+r['sha256'] for r in w['refs'])
    assert nodes[one]['evaluation_status']=='passed' and nodes[two]['evaluation_status']=='failed'
    assert nodes[one]['parent_id']==nodes[two]['parent_id']==base and nodes[two]['run_id']=='unit-loop-r1'
    assert nodes[two]['correctness'].startswith('%d/%d checks'%(len(w['fixtures'])-1,len(w['fixtures'])))
    run=packet['snapshot']['runs'][0]
    assert run['stage']=='Complete' and run['status']=='VISIBLE_EVALUATED_UNQUALIFIED' and run['blockers']==[]
    assert run['budget']['generation_call_limit']==6 and run['budget']['limit_seconds']==1200  # From the loop config.
    assert run['budget']['diagnosis_calls']==run['budget']['proposal_calls']==2 and run['budget']['elapsed_seconds']==3.0
    lineage=run['lineage']
    assert lineage['parent_node_id']==base and lineage['best_iteration']==1 and lineage['best_node_id']==one
    assert [r['node_id'] for r in lineage['iterations']]==[one,two]
    assert lineage['iterations'][1]['failing_cases']==[{'id':w['held'][0],'fixture_set':'held_out'}]
    assert [c['candidate_code'] for c in packet['candidates'][1:]]==[b.decode() for b in w['bodies']]
    assert all(n['admit']['allowed'] is n['activate']['allowed'] is False for n in nodes.values())
    assert w['held'][0] in json.dumps(lineage) and 'packet' not in json.dumps(run)
    # A later run keeps the published baseline node and every earlier row.
    merged=pub.merge_publication(packet,packet,'2026-10-27T11:00:00Z')
    assert len(merged['snapshot']['nodes'])==3 and merged['snapshot']['runs'][0]['lineage']==lineage
    again=_loop_packet(w,w['result'],previous=merged)
    assert again['snapshot']['nodes'][0]==merged['snapshot']['nodes'][0]


def test_loop_partial_error_publishes_evaluated_iterations_and_unreported_jobs(loop_world):
    w=loop_world;result=copy.deepcopy(w['result']);loop=result['loop']
    loop['iterations'][1].update(visible=None,score=None,kept=False,outcome='error',
        reason='CANDIDATE_EVALUATION_FAILED: ROOT_EVALUATION_FAILED_NO_REPLAY',
        failure={'exception_type':'ValueError','message':'ROOT_EVALUATION_FAILED_NO_REPLAY'})
    loop.update(stop_reason='error',stop_detail='CANDIDATE_EVALUATION_FAILED')
    result.update(exception_type='ValueError')
    served=w['parent_raw']['executions']+w['first']['executions']
    packet=_loop_packet(w,result,issued=served+3,exit_code=2)
    run=packet['snapshot']['runs'][0]
    assert run['stage']=='Partial' and run['blockers']==['Retained ValueError; this attempt cannot be replayed.']
    unreported=next(a for a in run['activity'] if a['id'].endswith(':unreported-jobs'))
    assert unreported['summary'].startswith('3 protected job(s)') and 'evaluator exit 2' in unreported['summary']
    nodes={n['id']:n for n in packet['snapshot']['nodes']}
    two='candidate:unit-loop-r1:'+w['refs'][1]['sha256']
    assert nodes[two]['evaluation_status']=='not_evaluated' and nodes[two]['evidence_refs']==[]
    assert run['lineage']['stop_reason']=='error' and run['lineage']['iterations'][1]['status']=='not_evaluated'
    assert next(c for c in packet['candidates'] if c['node_id']==two)['blocker']=='Proposal retained without a completed public evaluation.'


def test_loop_interrupted_parent_reuses_published_baseline_without_inventing_results(loop_world):
    w=loop_world;previous=_loop_packet(w,w['result'])
    result=copy.deepcopy(w['result']);loop=result['loop']
    result.update(parent_visible=None,candidate_visible=None,candidate_ref=None,model_calls=0,
                  status='ERROR_NO_REPLAY',exception_type='ValueError')
    loop.update(parent_visible=None,iterations=[],completed_iterations=0,best=None,stop_reason='error',model_calls=0)
    packet=_loop_packet(w,result,issued=len(w['fixtures']),previous=previous)
    run=packet['snapshot']['runs'][0]
    assert run['stage']=='Failed' and 'interrupted' in run['activity'][-1]['summary']
    assert [n['id'] for n in packet['snapshot']['nodes']]==['base:'+w['parent_ref']['sha256']]
    assert run['budget']['diagnosis_calls']==run['budget']['proposal_calls']==0
    assert run['lineage']['parent']['status']=='not_evaluated' and run['lineage']['iterations']==[]
    with pytest.raises(ValueError,match='ORIGINAL_PUBLISHED_BASELINE_REQUIRED'):
        _loop_packet(w,result,issued=len(w['fixtures']))


def test_loop_startup_and_resultless_worker_failures_use_loop_budget(loop_world):
    w=loop_world;previous=_loop_packet(w,w['result'])
    failure={'schema':'ai4r-rsi-capsule-controller-failure:1','id':w['session']['id'],
        'exception_type':'FileNotFoundError','message':'retained','status':'ERROR_NO_REPLAY'}
    calls,wall=pub.session_limits(w['session'])
    assert (calls,wall)==(6,1200)
    packet=pub.controller_failure_packet(w['meta'],w['session'],failure,previous,model_calls=0,call_limit=calls,limit_seconds=wall)
    assert packet['snapshot']['runs'][0]['budget']['generation_call_limit']==6
    worker=pub.worker_terminal_packet(w['meta'],w['session'],{'exit_code':137},previous,
        evaluator_state='no terminal record',call_limit=calls,limit_seconds=wall)
    run=worker['snapshot']['runs'][0]
    assert run['stage']=='Failed' and 'Worker exited 137 without a session result' in run['blockers'][0]
    assert run['budget']['diagnosis_calls'] is None and run['activity'][0]['id'].endswith(':worker-terminal')
    assert [n['id'] for n in worker['snapshot']['nodes']]==['base:'+w['parent_ref']['sha256']]


def test_local_unprotected_or_tampered_results_are_never_published(loop_world):
    w=loop_world
    local=w['visible']('candidate',w['refs'][0],1,1,scope='local_unprotected')
    with pytest.raises(ValueError,match='LOCAL_UNPROTECTED_RESULT_NOT_PUBLISHABLE'):
        pub.require_protected_scope(local)
    result=copy.deepcopy(w['result']);result['loop']['iterations'][0]['visible']=pub.reviewer_view(local)
    with pytest.raises(ValueError,match='LOCAL_UNPROTECTED_RESULT_NOT_PUBLISHABLE'):
        _loop_packet(w,result)
    tampered=copy.deepcopy(w['first']);tampered['passed_count']-=1
    with pytest.raises(ValueError,match='ROOT_RESULT_ORIGINAL_DIFFERS'):
        pub.visible_summary_v2(tampered,name=w['name'],body_ref=w['refs'][0],read=w['read'])
    result=copy.deepcopy(w['result']);result['loop']['iterations'][0]['visible']['passed_count']=0
    with pytest.raises(ValueError,match='SESSION_VIEW_DIFFERS_FROM_ROOT_RESULT'):
        _loop_packet(w,result)
    with pytest.raises(ValueError,match='ROOT_GRANT_SCOPE_DIFFERS'):  # A body is joined only to its own result.
        pub.visible_summary_v2(w['first'],name=w['name'],body_ref=w['refs'][1],read=w['read'])


def test_loop_evidence_reconciles_completion_failure_and_start_claims(loop_world,tmp_path,monkeypatch):
    w=loop_world;monkeypatch.setattr(pub,'protected',lambda path,*a,**k:Path(path))
    evaluator=tmp_path/'evidence';(evaluator/'claims').mkdir(parents=True);control=tmp_path/'control';control.mkdir()
    pin={'path':str(tmp_path/'run.json'),'sha256':'f'*64}
    result_raw=encoded(w['result'])
    def start_claims(count):
        for index in range(count):
            ident='capsule-%048x'%index
            (evaluator/'claims'/(ident+'.json')).write_bytes(encoded({'schema':'ai4r-rsi-whole-capsule-execution-start:1','job_id':ident}))
    start_claims(w['served'])
    (evaluator/'claims'/('0'*64+'.json')).write_bytes(b'{}')  # Evaluation claims are not jobs.
    completion={'schema':'ai4r-rsi-capsule-evaluator-completion:1','id':w['session']['id'],'configuration_sha256':pin['sha256'],
        'grant_ref':w['session']['grant_ref'],'status':'STOPPED','stop':'CONTROLLER_CLOSED','executions':w['served'],
        'plan':{'grant_sha256':w['session']['grant_ref']['sha256']},
        'evaluations':[{'role':'parent','executions':w['parent_raw']['executions']},{'role':'candidate','executions':w['first']['executions']},
                       {'role':'candidate','executions':w['second']['executions']}]}
    (evaluator/'complete.json').write_bytes(encoded(completion))
    (control/'run-stdout.log').write_bytes(b'noise\n'+encoded({'schema':'ai4r-rsi-capsule-run-terminal:1',
        'result_sha256':pub.sha(result_raw),'evaluator_exit_code':0})+b'\n')
    evidence=type('E',(),{'root':evaluator})()
    cfg={'composition':{'core_root':str(tmp_path/'core'),'run_contexts':{}}}
    assert pub.loop_evidence(cfg,pin,w['session'],w['result'],result_raw,control,evidence)[:2]==(w['served'],w['served'])
    completion['executions']+=1;(evaluator/'complete.json').write_bytes(encoded(completion))
    with pytest.raises(ValueError,match='ROOT_EVALUATOR_TERMINAL_DIFFERS'):
        pub.loop_evidence(cfg,pin,w['session'],w['result'],result_raw,control,evidence)
    # Evaluator failed mid-evaluation: its retained failure record, a nonzero
    # exit and stop_reason == error; three issued jobs never reached the session.
    (evaluator/'complete.json').unlink()
    for index in range(w['served'],w['served']+3):
        ident='capsule-%048x'%index
        (evaluator/'claims'/(ident+'.json')).write_bytes(encoded({'schema':'ai4r-rsi-whole-capsule-execution-start:1','job_id':ident}))
    result=copy.deepcopy(w['result']);result['loop']['stop_reason']='error'
    result_raw=encoded(result)
    (evaluator/'failure.json').write_bytes(encoded({'schema':'ai4r-rsi-capsule-evaluator-failure:1','id':w['session']['id'],
        'configuration_sha256':pin['sha256'],'exception_type':'TimeoutError','message':'x','status':'ERROR_NO_REPLAY'}))
    (control/'run-stdout.log').write_bytes(encoded({'schema':'ai4r-rsi-capsule-run-terminal:1',
        'result_sha256':pub.sha(result_raw),'evaluator_exit_code':2})+b'\n')
    served,issued,outcome=pub.loop_evidence(cfg,pin,w['session'],result,result_raw,control,evidence)
    assert (served,issued,outcome)==(w['served'],w['served']+3,{'status':'ERROR_NO_REPLAY','stop':'TimeoutError','exit_code':2})
    with pytest.raises(ValueError,match='RUN_TERMINAL_RESULT_DIFFERS'):
        pub.loop_evidence(cfg,pin,w['session'],w['result'],encoded(w['result']),control,evidence)
    with pytest.raises(ValueError,match='RETAINED_EVALUATOR_FAILURE_REQUIRED'):  # Not a recorded error stop.
        pub.loop_evidence(cfg,pin,w['session'],w['result'],encoded(w['result']),tmp_path/'nowhere',evidence)


@pytest.mark.skipif(not hasattr(__import__('os'),'geteuid') or __import__('os').geteuid()!=0,
                    reason='publish_completed is the Root publisher entrypoint (requires euid 0)')
def test_completed_loop_publication_joins_retained_files_and_archives_history(loop_world,tmp_path,monkeypatch):
    w=loop_world
    monkeypatch.setattr(pub,'protected',lambda path,*a,**k:Path(path))
    monkeypatch.setattr(pub,'_directory',lambda path:Path(path))
    monkeypatch.setattr(pub,'configure_projection',lambda pin:None)
    records=tmp_path/'records';evidence=tmp_path/'evidence';control=tmp_path/'control';public=tmp_path/'public'
    for path in (records,evidence/'captures',evidence/'claims',control,public):path.mkdir(parents=True)
    result=dict(w['result'],result_ref=w['put'](w['result']))
    for digest,raw in w['raw'].items():
        (records/(digest+'.json')).write_bytes(raw);(evidence/'captures'/(digest+'.json')).write_bytes(raw)
    cfg={'session':w['session'],'evaluator':{'root':str(evidence)},'result_path':str(records/'capsule-result.json'),
         'composition':{'record_root':str(records),'core_root':str(tmp_path/'core'),'run_contexts':{}}}
    cfg_raw=encoded(cfg);(tmp_path/'run.json').write_bytes(cfg_raw);pin={'path':str(tmp_path/'run.json'),'sha256':pub.sha(cfg_raw)}
    (records/'capsule-result.json').write_bytes(encoded(result))
    for index in range(w['served']):
        ident='capsule-%048x'%index
        (evidence/'claims'/(ident+'.json')).write_bytes(encoded({'schema':'ai4r-rsi-whole-capsule-execution-start:1','job_id':ident}))
    (evidence/'complete.json').write_bytes(encoded({'schema':'ai4r-rsi-capsule-evaluator-completion:1','id':w['session']['id'],
        'configuration_sha256':pin['sha256'],'grant_ref':w['session']['grant_ref'],'status':'STOPPED','stop':'CONTROLLER_CLOSED',
        'executions':w['served'],'plan':{'grant_sha256':w['session']['grant_ref']['sha256']},'completed_roles':['parent','candidate']}))
    (evidence/'owner.json').write_bytes(encoded({'schema':'ai4r-rsi-capsule-evaluator-owner:1','id':w['session']['id'],
        'configuration_sha256':pin['sha256'],'uid':0,'gid':0,'groups':[],'pid':10,'start_ticks':20}))
    (control/'run-exit.json').write_bytes(encoded({'cid':'f'*64,'exit_code':0}))
    (control/'run-container.json').write_bytes(encoded({'cid':'f'*64,'id':w['session']['id']}))
    previous=_loop_packet(w,w['result'])
    previous_raw=encoded(previous);(public/'publication.json').write_bytes(previous_raw)
    template={'schema':'ai4r-capsule-completed-publication:1','projection':{'path':'unit','sha256':'a'*64},'meta':w['meta'],
              'configuration':pin,'control_directory':str(control),'publication_directory':str(public)}
    (tmp_path/'template.json').write_bytes(encoded(template))
    receipt=pub.publish_completed(tmp_path/'template.json',published_at='2026-10-27T12:00:00Z')
    published=json.loads((public/'publication.json').read_bytes())
    assert receipt['publication_sha256']==pub.sha((public/'publication.json').read_bytes()) and receipt['model_calls']==0
    assert (public/'.capsule-history'/(pub.sha(previous_raw)+'.json')).read_bytes()==previous_raw
    assert published['snapshot']['runs'][0]['lineage']['best_node_id']=='candidate:unit-loop-r1:'+w['refs'][0]['sha256']
    with pytest.raises(FileExistsError):  # One completed publication claim per result; never re-entered.
        pub.publish_completed(tmp_path/'template.json',published_at='2026-10-27T12:00:00Z')


# --------------------------------------------------------------------------
# Merge wave: the paired batched benchmark (Interface E) is the latency judge.
# --------------------------------------------------------------------------
def _benchmark(w, ref, *, gain, ci, met, jobs=3, gates=None, **extra):
    """A Root-retained benchmark report for ``ref`` with one original per job."""
    gates = gates if gates is not None else {key: met for key in pub.BENCHMARK_GATES}
    report = {'schema': pub.BENCHMARK_REPORT, 'capsule_name': w['name'], 'parent_sha256': w['parent_ref']['sha256'],
              'candidate_sha256': ref['sha256'], 'relative_gain': gain, 'ratio_confidence_interval': ci,
              'gates': {key: {'passed': value} for key, value in gates.items()}, 'objective_met': met,
              'protected_jobs': jobs, 'repetitions': 11,
              'workloads': [{'id': 'small-numbers', 'median_ratio': 1 - gain}],
              'evidence_refs': [w['put']({'benchmark_job': index, 'candidate': ref['sha256']}) for index in range(jobs)],
              **extra}
    return dict(report, report_ref=w['put'](report))


def _benchmark_result(w):
    result = copy.deepcopy(w['result']); loop = result['loop']
    first, second = loop['iterations']
    first['score'].update(latency_method='paired_batched_benchmark', improved=True, regressed=False)
    first['benchmark'] = _benchmark(w, w['refs'][0], gain=0.16782382665021112,
                                    ci=[0.8185217253623219, 0.8417550863553439], met=True)
    second['score'].update(latency_method='single_job_floor')
    loop['best']['score'] = first['score']
    loop['benchmark_baseline'] = _benchmark(w, w['parent_ref'], gain=0.0, ci=[0.98, 1.02], met=False, jobs=2,
                                            gates={'minimum_gain': False, 'ci_upper_bound': False, 'max_workload_regression': True})
    return result


def test_benchmark_iteration_publishes_codex_gain_and_interval_text(loop_world):
    w = loop_world; result = _benchmark_result(w)
    packet = _loop_packet(w, result)
    nodes = {n['id']: n for n in packet['snapshot']['nodes']}
    one, two = ('candidate:unit-loop-r1:' + r['sha256'] for r in w['refs'])
    parent_wall = w['parent_raw']['protected_wall_s']; candidate_wall = w['first']['protected_wall_s']
    assert nodes[one]['speed'] == ('Measured improvement: 16.78% amortized protected batch gain; original job latency separate.'
        f' Uncalibrated public job totals: parent {parent_wall:.6f} s, candidate {candidate_wall:.6f} s.')
    assert nodes[one]['noise'] == '95% paired ratio interval [0.8185, 0.8418]; 11 AB/BA pairs per workload.'
    report_ref = result['loop']['iterations'][0]['benchmark']['report_ref']
    assert nodes[one]['evidence_refs'][-1] == report_ref
    # Single-job floor: labelled, never a measured speedup.
    assert nodes[two]['speed'].endswith(' s protected total; single-job floor, not a measured speedup')
    run = packet['snapshot']['runs'][0]
    performance = [a for a in run['activity'] if a['stage'] == 'Performance evaluation']
    assert performance == [{'id': 'unit-loop-r1:performance:' + report_ref['sha256'], 'at': w['meta']['published_at'],
        'stage': 'Performance evaluation', 'status': 'OBJECTIVE_MET',
        'summary': 'Measured improvement under the frozen protected batch protocol; security remains deferred.'}]
    assert run['activity'][-1]['id'].endswith(':terminal')
    lineage = run['lineage']
    assert lineage['schema'] == 'ai4r-cc-rsi-lineage:2' and lineage['best_node_id'] == one
    best = lineage['iterations'][0]
    assert best['improvement_basis'] == 'paired_batched_benchmark' and best['benchmark']['report_ref'] == report_ref
    assert best['benchmark']['ratio_confidence_interval'] == [0.8185217253623219, 0.8417550863553439]
    assert lineage['iterations'][1]['latency_method'] == 'single_job_floor' and lineage['iterations'][1]['improvement_basis'] is None
    assert lineage['benchmark_baseline']['protected_jobs'] == 2
    # Root issued every evaluation job plus every benchmark job; both are served.
    assert pub.served_jobs(result) == w['served'] + 3 + 2
    assert run['stage'] == 'Complete'
    # A run without benchmark data keeps its lineage:1 rows and node text unchanged.
    plain = _loop_packet(w, w['result'])
    assert plain['snapshot']['runs'][0]['lineage']['schema'] == 'ai4r-cc-rsi-lineage:1'
    assert {n['id']: n['speed'] for n in plain['snapshot']['nodes']}[one] == f'{candidate_wall:.6f} s protected total; uncalibrated'


def test_benchmark_budget_counts_in_published_limit(loop_world):
    w = loop_world; session = copy.deepcopy(w['session'])
    session['loop']['benchmark'] = {'workloads': 8, 'repetitions': 11, 'warmups': 2, 'per_job_s': 6, 'wall_s': 7488}
    assert pub.session_limits(session) == (6, 1200 + 7488)
    session['loop']['benchmark'] = {'workloads': 8}
    with pytest.raises(ValueError, match='MATERIALIZED_BENCHMARK_WALL_REQUIRED'):
        pub.session_limits(session)


@pytest.mark.parametrize('fault', ['tampered-report', 'other-candidate', 'local-scope', 'objective-without-gates',
                                   'missing-job-original', 'job-count', 'paired-without-report', 'regressed-objective'])
def test_benchmark_claims_are_joined_to_root_originals_or_refused(loop_world, fault):
    w = loop_world; result = _benchmark_result(w)
    row = result['loop']['iterations'][0]
    if fault == 'tampered-report':
        row['benchmark']['relative_gain'] = 0.3
    elif fault == 'other-candidate':
        row['benchmark'] = _benchmark(w, w['refs'][1], gain=0.2, ci=[0.7, 0.8], met=True)
    elif fault == 'local-scope':
        row['benchmark'] = _benchmark(w, w['refs'][0], gain=0.2, ci=[0.7, 0.8], met=True, scope='local_unprotected')
    elif fault == 'objective-without-gates':
        row['benchmark'] = _benchmark(w, w['refs'][0], gain=0.2, ci=[0.7, 0.8], met=True,
                                      gates={'minimum_gain': True, 'ci_upper_bound': False, 'max_workload_regression': True})
    elif fault == 'missing-job-original':
        report = {k: v for k, v in row['benchmark'].items() if k != 'report_ref'}
        report['evidence_refs'] = report['evidence_refs'][:-1] + [{'id': 'absent.json', 'sha256': 'a' * 64}]
        row['benchmark'] = dict(report, report_ref=w['put'](report))
    elif fault == 'job-count':
        report = {k: v for k, v in row['benchmark'].items() if k != 'report_ref'}
        report['protected_jobs'] += 1
        row['benchmark'] = dict(report, report_ref=w['put'](report))
    elif fault == 'paired-without-report':
        del row['benchmark']
    else:
        row['score'].update(regressed=True)
    with pytest.raises((ValueError, KeyError)):
        _loop_packet(w, result)


CODEX_EVIDENCE = Path(__file__).parents[3] / 'docs/review/evidence-20261027-codex'


def test_codex_performance_history_renders_unchanged_through_our_projection():
    """Codex's live app published gain/CI on nodes via ``performance-publish``;
    our formatter reproduces those exact strings from its measured results and
    our projection serves its published nodes byte-identically."""
    import re
    index = json.loads((CODEX_EVIDENCE / 'final-integration-index.json').read_text())
    verified = json.loads((CODEX_EVIDENCE / 'verified-capsule-improvements-r2.json').read_text())
    published = json.loads((CODEX_EVIDENCE / 'final-authenticated-native-ws.json').read_text())['snapshot']
    nodes = {node['hash']: node for node in published['nodes']}
    reps = verified['method']['paired_repetitions_per_workload']
    targets = {row['candidate_sha256']: row for row in verified['targets']}
    assert len(index['measured_results']) == 2
    for measured in index['measured_results']:
        node = nodes[measured['candidate_sha256']]
        walls = re.fullmatch(r'.* parent ([0-9.]+) s, candidate ([0-9.]+) s\.', node['speed'])
        speed, noise, _ = pub.performance_text(measured['relative_gain'], measured['ratio_confidence_interval'],
            measured['objective_met'], reps, float(walls[1]), float(walls[2]))
        assert (speed, noise) == (node['speed'], node['noise'])
        target = targets[measured['candidate_sha256']]
        assert math.isclose(target['time_reduction_percent'], measured['relative_gain'] * 100)
        lower, upper = measured['ratio_confidence_interval']
        assert all(math.isclose(a, b) for a, b in zip(target['confidence_95_percent_gain'], [(1 - upper) * 100, (1 - lower) * 100]))
    for history in verified['preserved_history']:  # Round 1: measured, not met.
        prefix = f"No demonstrated improvement: {history['round_1_time_reduction_percent']:.2f}% amortized protected batch gain;"
        assert history['round_1_objective_met'] is False and sum(n['speed'].startswith(prefix) for n in published['nodes']) == 1
    spec = importlib.util.spec_from_file_location('codex_compat_projection',
        Path(__file__).parents[3] / 'jiuwenswarm/server/rsi/cc_rsi_projection.py')
    projection = importlib.util.module_from_spec(spec); spec.loader.exec_module(projection)
    value = {'snapshot': copy.deepcopy(published), 'candidates': []}
    projection.validate_publication(value)
    service = projection.CcRsiProjection(); service._read = lambda: copy.deepcopy(value)
    served = service.snapshot({})
    assert [(n['id'], n['speed'], n['noise'], n['evidence_refs']) for n in served['nodes']] == [
        (n['id'], n['speed'], n['noise'], n['evidence_refs']) for n in published['nodes']]
    assert [r['activity'] for r in served['runs']] == [r['activity'] for r in published['runs']]
    assert all('lineage' not in run for run in served['runs'])  # Codex rows stay legacy rows.
