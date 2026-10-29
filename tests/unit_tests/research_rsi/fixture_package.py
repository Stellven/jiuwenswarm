"""Signed schema-complete unit vectors; never runtime qualification evidence.

The parent is the real installed authoring asset. The child only adds a comment;
the paired scores below are explicit arithmetic test vectors, not measurements
of these implementations. They must never enter a production campaign.
"""
import copy
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.capsules.assets import build_research_assets
from jiuwenswarm.research.contracts import validate
from jiuwenswarm.research_rsi.mutation import child_declaration
from jiuwenswarm.research_rsi.records import encoded
from jiuwenswarm.research_rsi.signing import Signer
from jiuwenswarm.research_rsi.statistics import qualify


def make_unit_package(root):
    store=SQLiteRunStore(root);signer=Signer.generate('unit:custodian');at='2026-10-16T00:00:00Z'
    put=lambda value:store.put_blob(encoded(value),media_type='application/json')
    asset=build_research_assets(store,verify_catalog=False)['screening'];parent_ref=asset['declaration_ref'];parent=store.read_record(parent_ref)
    body_refs=asset['body_refs'];path='ranking_parent.txt';body=body_refs[path]
    child_body=store.put_blob(store.read_blob(body)+b'\n# Unit-only byte-distinct child; no performance claim.\n')
    unit=put({'unit_control':'Arithmetic vectors only; no hidden fixture or execution evidence'})
    hashes={row['path']:row['sha256'] for row in parent['identity']['body']};hashes[path]=child_body['sha256']
    child=child_declaration(parent,body_hashes=hashes,version_label=parent['identity']['version_label']+'.unit1',carrier=parent['identity']['carrier'],
        lineage={'parent':parent_ref,'co_parents':[],'relation':'supersedes','builder':'rsi_workbench','build_trigger':'unit:rsi',
            'context_capsules':[],'diagnosis_inputs':[],'builder_ref':unit,'provenance':{'generating_model':None,'prompt_ref':unit,'trajectory_ref':unit}},validate=validate)
    child_ref=put(child);pin=lambda decl,ref:{'cc_name':decl['identity']['name'],'cc_version':decl['identity']['version_label'],'declaration_sha256':ref['sha256']}
    parent_pin=pin(parent,parent_ref);child_pin=pin(child,child_ref)
    target={'schema_version':'1.0.0','id':'unit_target','parent_ref':body,'parent_declaration_ref':parent_ref,'frozen_contract_ref':unit,
        'required_test_refs':[unit],'mutable_paths':[path],'protected_refs':[asset['bundle_ref'],asset['profile_ref']],
        'splits':dict(development='unit:development',hidden_loop='unit:hidden_loop',hidden_final='unit:hidden_final',platform='unit:platform'),
        'scoring':dict(primary='passed_test_count',secondary='paired_time_at_equal_counts',warmup_batches=5,paired_rounds=7,min_relative_gain=.1,
            noise_multiplier=3,batch_iterations=1000,calibrated_relative_noise=.02),'calibration_ref':unit,'session_query_limit':30,'lifetime_query_limit':90,
        'limits':dict(time_s=600,model_calls=5,memory_mb=512),'scoring_adapter_ref':unit,'improver_ref':unit,'configuration_ref':unit}
    validate('rsi-target-profile',target);target_ref=put(target)
    genesis=put({'session_id':'unit:rsi','target_ref':target_ref,'hash_profile_ref':unit,'interface_revision':'M1-IF-009@r2'})
    session={'schema_version':'1.0.0','id':'unit_session','session_id':'unit:rsi','target_profile_ref':target_ref,'parent':parent_pin,
        'parent_declaration_ref':parent_ref,'improver_ref':unit,'scoring_adapter_ref':unit,'configuration_ref':unit,'hash_profile_ref':unit,'chain_root_ref':genesis,
        'limits':dict(max_attempts=20,max_no_progress=5,wall_s=3600,per_call_s=300,session_query_limit=30,lifetime_query_limit=90),
        'pass_count_repeats':3,'qualification':dict(min_pass_rate_gain=.05,alpha=.05,min_timing_gain=.1,noise_multiplier=3,warmup_batches=5,paired_rounds=7),
        'started_by':'unit:operator','frozen_at':at}
    validate('rsi-session',session);session_ref=put(session)
    diff=put({'format':'ai4r-body-diff-v1','files':[{'path':path,'before_ref':body,'after_ref':child_body}]})
    attempt={'schema_version':'2.0.0','id':'unit_attempt_1','session_id':session['session_id'],'sequence':1,'previous_ref':None,
        'target_ref':target_ref,'parent_ref':body,'child_ref':child_body,'diff_ref':diff,'rationale':'Byte-distinct unit child; no runtime claim',
        'visible_evidence_refs':[unit],'queries_used':2,'violations':[],'stop_reason':None,'configuration_ref':unit,'observation_refs':[],
        'time_s':1,'model_calls':None,'unavailable_reasons':['Unit vectors do not contain a model call'],'hash_profile_ref':unit,'chain_root_ref':genesis,
        'attempt_status':'proposed','rejection_reason':None,'failure_evidence_refs':[]}
    validate('rsi-attempt',attempt);attempt_ref=put(attempt)
    child['identity']['lineage']['builder_ref']=attempt_ref
    child_ref=put(child);child_pin=pin(child,child_ref)
    rejected=copy.deepcopy(attempt);rejected.update(id='unit_attempt_2',sequence=2,previous_ref=attempt_ref,child_ref=None,diff_ref=None,rationale=None,
        attempt_status='rejected',rejection_reason='Unit malformed-response control',failure_evidence_refs=[unit],stop_reason='Unit malformed-response control')
    validate('rsi-attempt',rejected);rejected_ref=put(rejected)
    decision=qualify([[1,0,0]]*20,[[1,1,0]]*10+[[1,0,0]]*10,repeats=3)
    stats=decision['statistics']
    referee=signer.sign({'schema_version':'2.0.0','id':'unit_referee','attempt_ref':attempt_ref,'target_ref':target_ref,'parent_ref':body,'child_ref':child_body,
        'pairs':[dict(split=target['splits']['hidden_final'],total=20,parent_passed=stats['parent_passed'],child_passed=stats['child_passed'],gain_units=10,loss_units=0,parent_time_s=[2.0]*7,child_time_s=[1.0]*7)],
        'mandatory_parent_tests_passed':True,'integrity_passed':True,'final_evaluations':1,'violations':[],'configuration_ref':unit})
    validate('rsi-referee-evidence',referee);referee_ref=put(referee)
    result=signer.sign({'schema_version':'2.0.0','id':'unit_result','session_ref':session_ref,'outcome':decision['outcome'],'parent':parent_pin,'child':child_pin,
        'child_declaration_ref':child_ref,'attempt_refs':[attempt_ref,rejected_ref],'final_attempt_ref':attempt_ref,'referee_evidence_ref':referee_ref,
        'qualified_by':decision['qualified_by'],'statistics':stats,'attempts_used':2,'queries_used':2,'stop_reason':'Unit arithmetic vectors only',
        'limitations':['Unit vectors; no actual model, helper measurement, custody or improvement qualification'],'recorded_at':at})
    validate('rsi-session-result',result);result_ref=put(result)
    implementations=[child_body if row['path']==path else body_refs[row['path']] for row in child['identity']['body']]
    provenance={'schema_version':'1.0.0','id':'unit_provenance','declaration_ref':child_ref,'implementation_refs':implementations,
        'parent_ref':body,'builder_ref':attempt_ref,'evidence_refs':[referee_ref,unit]}
    validate('candidate-provenance',provenance);provenance_ref=put(provenance)
    package={'schema_version':'1.0.0','id':'unit_package','target_profile_ref':target_ref,'session_ref':session_ref,'session_result_ref':result_ref,
        'provenance_ref':provenance_ref,'parent':parent_pin,'child':child_pin,'parent_declaration_ref':parent_ref,'child_declaration_ref':child_ref,
        'diff_ref':diff,'referee_evidence_ref':referee_ref,'mutable_paths_touched':[path],'created_at':at}
    validate('candidate-package',package)
    return dict(package=package,store=store,signer=signer,result=result,referee=referee,session=session,attempt=attempt,rejected=rejected,put=put)
