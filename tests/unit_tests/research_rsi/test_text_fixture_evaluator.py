from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
"""Frozen data-only Screening expectations never enter model inputs."""
import pytest


def test_fixed_expectations_compare_actual_outputs_and_refuse_unknown_forms():
    from jiuwenswarm.research_rsi.text_evaluation import evaluate_expectation
    actual={'screening_result':{'selected_idea_id':'one','ranking':[{'idea_id':'one','rank':1}]}}
    expected={'schema':'ai4r-rsi-json-expectation:1','tests':[{'output':'screening_result','pointer':'/selected_idea_id','value':'one'}]}
    assert evaluate_expectation(actual,expected)
    assert not evaluate_expectation({'screening_result':{'selected_idea_id':'two'}},expected)
    assert not evaluate_expectation(actual,expected|{'callback':'private code'})
    assert not evaluate_expectation(actual,expected|{'tests':[{'output':'screening_result','pointer':'/missing','value':None}]})
    assert not evaluate_expectation(actual,expected|{'tests':[]})


def test_text_subject_requires_exact_mutable_body_and_inherited_closure(tmp_path):
    from jiuwenswarm.research_rsi.text_evaluation import child_subject
    from jiuwenswarm.research_rsi.records import RecordStore
    store=RecordStore(tmp_path/'records');old=store.put_bytes(b'original prompt');new=store.put_bytes(b'changed prompt')
    parent={'identity':{'body':[{'path':'screening_prompt.txt','sha256':old['sha256']}]}}
    child={'identity':{'body':[{'path':'screening_prompt.txt','sha256':new['sha256']}]}}
    target={'parent_ref':old,'mutable_paths':['screening_prompt.txt']}
    result=child_subject(store,parent,child,target,{'session_ref':old,'target_ref':old,'configuration_ref':old},
        parent_declaration_ref=old,child_declaration_ref=new,body_refs={'screening_prompt.txt':new},dependency_refs=[])
    assert result['candidate_ref']==new and result['child_body_refs']=={'screening_prompt.txt':new}
    with pytest.raises(ValueError):child_subject(store,parent,child,target,{'session_ref':old,'target_ref':old,'configuration_ref':old},
        parent_declaration_ref=old,child_declaration_ref=new,body_refs={'screening_prompt.txt':old},dependency_refs=[])
    store.close()


def test_reservation_versions_make_external_only_hash_interpretation_explicit(tmp_path):
    from jiuwenswarm.research_rsi.trial_port import TrialReservationIssuer,verify_reservation
    from jiuwenswarm.research_rsi.custody import ExposureLedger
    from jiuwenswarm.research_rsi.records import RecordStore,encoded
    from jiuwenswarm.research_rsi.signing import Signer
    from tests.unit_tests.research_rsi.test_isolated_trial_client import binding,pin
    import hashlib
    store=RecordStore(tmp_path/'records');ledger=ExposureLedger(tmp_path/'ledger');signer=Signer.generate('test-key')
    value=binding();value['schema']='ai4r-isolated-evaluation-binding:2'
    value['inputs']=[{'name':'brief','contract_id':'research-brief','artifact_refs':[pin('brief')]},{'name':'candidate_set','contract_id':'candidate-set','artifact_refs':[pin('ideas')]}]
    session=store.put({'session_id':'one','pass_count_repeats':3,'configuration_ref':value['configuration_ref'],'target_profile_ref':value['target_ref']});value['session_ref']=session
    partitions={n:[n+str(i) for i in range(20)] for n in ['development','hidden_loop','hidden_final','platform']}
    ledger.register('fixture',partitions,known_bad=10,known_good=3);ledger.open_session('one','fixture')
    candidate=pin('actual-child');ledger.reserve('one','loop','loop',fingerprint=hashlib.sha256(encoded(candidate)).hexdigest())
    issuer=TrialReservationIssuer(ledger,store,signer,approved_sessions=[session])
    ref=issuer.issue(value,action_id='loop',charge_kind='loop',candidate_ref=candidate);record=store.get(ref)
    assert record['schema']=='ai4r-rsi-trial-reservation:2'
    verify_reservation(record,value,signer.public_bytes(),'test-key')
    for inputs in [value['inputs'][::-1],value['inputs']+[{'name':'screening_rubric','contract_id':'screening-rubric','artifact_refs':[pin('rubric')]}]]:
        with pytest.raises(ValueError):issuer.issue(value|{'inputs':inputs},action_id='loop',charge_kind='loop',candidate_ref=candidate)
    with pytest.raises(ValueError):verify_reservation(record,value|{'schema':'ai4r-isolated-evaluation-binding:1'},signer.public_bytes(),'test-key')
    assert ledger.state('one')['used']==1
    store.close();ledger.close()


@pytest.mark.asyncio
async def test_literal_controller_factory_uses_actual_parent_handles_and_captures_real_text_subject(tmp_path,monkeypatch):
    import copy
    from types import SimpleNamespace
    from pathlib import Path
    from tests.unit_tests.research.test_parent_measurement import parent_fixture
    from jiuwenswarm.research_rsi.text_resources import assemble_text_job
    from jiuwenswarm.research_rsi.fixed_resources import CombinedRecords
    from jiuwenswarm.research_rsi.records import RecordStore
    from jiuwenswarm.research_rsi.native_lease import NativeEffectLease
    from jiuwenswarm.research_records.original_bytes import OriginalBytes
    core,owner,fixture,original=await parent_fixture(tmp_path/'core')
    resources=owner.resources;records=RecordStore(tmp_path/'records');public=OriginalBytes(tmp_path/'public',writable=True)
    store=CombinedRecords(records,core,publisher=public)
    parent=core.read_record(original['parent_declaration_ref']);target=core.read_record(original['target_ref'])
    installed=resources.composition.library.get(parent['identity']['name'],parent['identity']['version_label'])
    target.update(mutable_paths=['screening_prompt.txt'],parent_ref=installed['body_refs']['screening_prompt.txt'])
    test=core.append_record('rsi-parent-test',{'schema':'ai4r-screening-parent-test:1','id':'fixed-utf8','kind':'prompt_utf8','parent_declaration_ref':original['parent_declaration_ref']})
    target['required_test_refs']=[test];target_ref=store.put(target)
    session=core.read_record(original['session_ref']);session.update(target_profile_ref=target_ref,pass_count_repeats=3,started_by=resources.principal.account_id)
    session['limits'].update(max_attempts=1,max_no_progress=1)
    session_ref=store.put(session)
    row=resources.composition.library.get(session['parent']['cc_name'],session['parent']['cc_version'])
    parent_directory=tmp_path/'parent';parent_directory.mkdir()
    for path,ref in row['body_refs'].items():
        output=parent_directory/path;output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(core.read_blob(ref))
    work=tmp_path/'work';work.mkdir()
    profile={'schema':'ai4r-rsi-screening-text-profile:2','session_ref':session_ref,'target_ref':target_ref,
        **{k:original[k] for k in ['parent_admission_ref','parent_contract_ref','parent_check_plan_ref','model_selection_profile_ref','deployment_ref','limits']},
        'check_bundle_ref':resources.composition.installed['screening']['bundle_ref'],'checking_profile_ref':resources.composition.installed['screening']['profile_ref']}
    profile_ref=store.put(profile)
    opportunity=store.put({'schema':'ai4r-rsi-opportunity:1','attribution':'implementation','symptom_reproduced':True,'mandatory_passed':True,
        'headroom':1,'headroom_minimum':.1,'diagnosis':{'cause':'Controlled constructor fixture only','alternatives':['Explicit local test'],'falsification':'No operational headroom claim'},'resource_ready':True,'evidence_refs':[test],'parent_visible_time_s':1})
    visible=store.put({'context':{'control':'Visible fixture only'},'mandatory_fixtures':[],'required_test_refs':[test]})
    requests=RecordStore(tmp_path/'custody-requests')
    lease=NativeEffectLease(records,store.put({'scope':'no model call in constructor test'}))
    # This unit double only bypasses OS custody to exercise installed assembly;
    # actual cross-UID/mount qualification remains a separate required boundary.
    monkeypatch.setattr('jiuwenswarm.research_rsi.text_resources.owned_directory',lambda path,uid:Path(path).resolve())
    job={'session_ref':session_ref,'opportunity_ref':opportunity,'visible_context_ref':visible,'proposer_contract_refs':[original['parent_contract_ref']],
        'worker_profile_ref':profile_ref,'fixture_identity':'controlled-only','target_kind':'screening-text-v1'}
    runtime=SimpleNamespace(parent_bindings=[{k:profile[k] for k in ['session_ref','parent_contract_ref','parent_check_plan_ref']}])
    controller,args=await assemble_text_job(job,resources=resources,store=store,binding={'parent_directory':str(parent_directory),'work_root':str(work)},
        custody={'socket_path':'/not-connected-custodian.sock','peer_uid':12002},custody_requests=requests,native_lease=lease,publication=public,
        trial_runtime=runtime,principal=resources.principal,qualification=ControlledQualification())
    assert args['session_ref']==session_ref and args['parent_body_ref']==target['parent_ref']
    store.record_proposer_start(session['session_id'],{'record_kind':'rsi-proposer-start:1','session_id':session['session_id'],'sequence':1,'previous_ref':None,'recorded_at':'2026-10-16T00:00:00Z','configuration_ref':session['configuration_ref'],'improver_ref':session['improver_ref']})
    result=await controller.assess({'path':'screening_prompt.txt','body':'A real changed prompt in this controlled constructor test.','rationale':'Local assembly control'})
    assert result['mandatory_passed'] and result['child_declaration_ref']!=original['parent_declaration_ref']
    assert not list(core.iter_records(kinds=('model-call-start','isolated-evaluation-result','admitted-parent-result')))
    lease.assert_available();requests.close();records.close();core.close()


@pytest.mark.parametrize('slot',[('score',),('warmup',0,0),('warmup',4,1),('paired',0,0),('paired',6,1)])
def test_finite_signed_slots_are_deterministic_private_and_do_not_charge_again(tmp_path,slot):
    import hashlib
    from jiuwenswarm.research_rsi.records import RecordStore,encoded
    from jiuwenswarm.research_rsi.signing import Signer
    from jiuwenswarm.research_rsi.custody import ExposureLedger
    from jiuwenswarm.research_rsi.trial_port import TrialReservationIssuer,verify_reservation
    from tests.unit_tests.research_rsi.test_isolated_trial_client import binding,pin
    store=RecordStore(tmp_path/'store');ledger=ExposureLedger(tmp_path/'ledger.sqlite');signer=Signer.generate('custodian')
    partitions={name:[name+str(i) for i in range(20)] for name in ('development','hidden_loop','hidden_final','platform')}
    ledger.register('fixture',partitions,known_bad=10,known_good=3);ledger.open_session('s','fixture')
    value=binding();value.update(schema='ai4r-isolated-evaluation-binding:2',phase='hidden_final',inputs=[{'name':n,'contract_id':n,'artifact_refs':[pin(n)]} for n in ('brief','candidate_set')])
    target=store.put({'scoring':{'warmup_batches':5,'paired_rounds':7,'batch_iterations':2}});value['target_ref']=target
    session={'session_id':'s','target_profile_ref':target,'configuration_ref':value['configuration_ref'],'pass_count_repeats':3,'qualification':{'warmup_batches':5,'paired_rounds':7}}
    sr=store.put(session);value['session_ref']=sr
    comparison={'attempt_ref':pin('a'),'target_ref':target,'parent_ref':pin('p'),'child_ref':pin('c'),'configuration_ref':value['configuration_ref'],'repeats':3,'qualification':session['qualification']}
    ledger.reserve('s','original-parent-final','final',fingerprint=hashlib.sha256(encoded(comparison)).hexdigest())
    issuer=TrialReservationIssuer(ledger,store,signer,approved_sessions=[sr]);before=ledger.state('s')
    first=issuer.issue(value,action_id='original-parent-final',charge_kind='final',comparison=comparison,slot=slot)
    second=issuer.issue(value,action_id='original-parent-final',charge_kind='final',comparison=comparison,slot=slot)
    assert first==second and store.get(first)['schema']=='ai4r-rsi-trial-reservation:3'
    verify_reservation(store.get(first),value,signer.public_bytes(),'custodian',target=store.get(target),session=session)
    assert before==ledger.state('s') and 'fixture_id' not in store.get(first)
    for bad in [('warmup',5,0),('paired',7,0),('paired',0,2),('nonce',)]:
        with pytest.raises(ValueError):issuer.issue(value,action_id='original-parent-final',charge_kind='final',comparison=comparison,slot=bad)
    ledger.close();store.close()


@pytest.mark.asyncio
async def test_text_timing_uses_each_frozen_iteration_slot_and_never_sends_expected_labels(tmp_path):
    import json
    from types import SimpleNamespace
    from jiuwenswarm.research_rsi.records import RecordStore
    from jiuwenswarm.research_rsi.text_evaluation import TextFixtureEvaluator
    store=RecordStore(tmp_path/'store');capture=RecordStore(tmp_path/'capture');issued=[];bindings=[]
    def pin(value):return store.put(value)
    external=[{'name':name,'contract_id':name,'artifact_refs':[pin({'public':name})]} for name in ('brief','candidate_set')]
    expected=pin({'schema':'ai4r-rsi-json-expectation:1','tests':[{'output':'screening_result','pointer':'/selected','value':'custody-only-label'}]})
    candidate=pin({'actual':'original-body'});row={'id':'private-fixture','input_ref':pin({'schema':'ai4r-rsi-legitimate-inputs:2','inputs':external}),'expected_ref':expected}
    output=capture.put({'selected':'custody-only-label'});plan=capture.put({'mandatory_deterministic':['fixed']})
    checked=capture.put({'check_plan_ref':plan,'results':[{'check_id':'fixed','outcome':'PASS'}]});observation=capture.put({'duration_s':.25})
    assessment=capture.put({'verdict':'PASS'});raw=capture.put({'status':'completed','failure':None,'output_refs':{'screening_result':output},'deterministic_ref':checked,
        'observation_ref':observation,'observation_refs':[],'assessment_refs':[assessment]})
    class ClientDouble:
        async def execute(self,ref):
            value=store.get(ref);bindings.append(value)
            return {'measurement_ref':raw},store.put({'controlled_result':len(bindings)})
    client=ClientDouble();client.capture=capture
    class IssuerDouble:
        def issue_parent(self,binding,**kwargs):issued.append(kwargs['slot']);return pin({'controlled_reservation':len(issued)})
    evaluator=object.__new__(TextFixtureEvaluator);evaluator.version=2;evaluator.store=store;evaluator.session_ref=pin({'session':'s'})
    evaluator.manifest={'target_ref':pin({'target':'t'})};evaluator.target={'parent_ref':candidate,'parent_declaration_ref':pin({'parent':'p'}),'configuration_ref':pin({'cfg':'c'}),'scoring':{'batch_iterations':2}}
    evaluator.profile={key:pin({'context':key}) for key in ('parent_admission_ref','parent_contract_ref','parent_check_plan_ref','model_selection_profile_ref','deployment_ref')}
    evaluator.profile['limits']={'time_s':30,'model_calls':3,'memory_mb':128};evaluator.parent=client;evaluator.child=None
    evaluator.issuer=IssuerDouble();evaluator.publication=SimpleNamespace(put_ref=lambda ref,raw:None);evaluator.last_evidence=[];evaluator.all_evidence=[]
    evaluator.comparison={'frozen':'same already charged action'};evaluator._action=lambda *args:('original-parent-final','final')
    assert await evaluator.one(candidate,row,'hidden_final','timing:4:parent',1,timing=True)==(1,.5)
    assert issued==[('warmup',4,0),('warmup',4,1)]
    issued.clear()
    assert await evaluator.one(candidate,row,'hidden_final','timing:11:parent',1,timing=True)==(1,.5)
    assert issued==[('paired',6,0),('paired',6,1)]
    assert all('custody-only-label' not in json.dumps(value) and 'private-fixture' not in json.dumps(value) for value in bindings)
    issued.clear()
    assert await evaluator.one(candidate,row,'hidden_final','final-parent',1)==(1,.25)
    assert issued==[('score',)]
    capture.close();store.close()
