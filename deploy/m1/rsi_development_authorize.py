"""Root model-free plan/stage for a sealed, explicitly unqualified run.

Derives all work/target/worker references from completed metadata and the sealed
context. The old qualification-required envelope is an observation only.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path

HERE=Path(__file__).resolve().parent
def sibling(name):
    spec=importlib.util.spec_from_file_location('development_authorize_'+name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
seed=sibling('rsi_development_seed')
run=sibling('rsi_development_run')
FIELDS={'schema','id','preparation_receipt','seed_receipt','launch_guard_receipt','context_ref','expires_at',
        'evaluator_root','forbidden_roots','cgroup_root'}
IMAGE='sha256:00026931a8e236d255efca8d2e90ea49ae04989539fca4d418d318a98fa93ab2'


def file_ref(value,owner=0):
    seed.need(isinstance(value,dict) and set(value)=={'path','sha256'},'CLOSED_FILE_PIN_REQUIRED')
    raw=seed.read(value['path'],owner)
    seed.need(seed.digest(raw)==value['sha256'],'FILE_PIN_DIFFERS')
    return raw


def validate_source_revision(auth,execution,old,old_execution):
    source_changed=old_execution['admin_runner_sha256']!=execution['admin_runner_sha256']
    window_changed=auth['expires_at']!=old['expires_at']
    seed.need(source_changed or window_changed,'UNISSUED_REVISION_MUST_CHANGE_SOURCE_OR_WINDOW')
    if auth['expires_at']!=old['expires_at']:
        from datetime import datetime,timedelta,timezone
        parse=lambda text:datetime.fromisoformat(text.replace('Z','+00:00'))
        prior,current=parse(old['expires_at']),parse(auth['expires_at'])
        seed.need(prior.tzinfo is not None and current.tzinfo is not None
            and prior.utcoffset()==current.utcoffset()==timedelta(0)
            and prior<current<=prior+timedelta(hours=1)
            and current<=datetime.now(timezone.utc)+timedelta(hours=1),'BOUNDED_UTC_UNISSUED_WINDOW_REQUIRED')
    old_copy=dict(old,expires_at=auth['expires_at'],worker=dict(old['worker'],contract_ref=auth['worker']['contract_ref']))
    seed.need(old_copy==auth,'AUTHORIZATION_REVISION_MAY_ONLY_REBIND_SOURCE')
    seed.need(dict(old_execution,admin_runner_sha256=execution['admin_runner_sha256'])==execution,
        'EXECUTION_REVISION_MAY_ONLY_REBIND_SOURCE')


def derive(value,preparation,complete,reader):
    dest=complete['destination'];id=value['id']
    seed.need(id==complete['id']==preparation['id'],'EXACT_DEVELOPMENT_RUN_REQUIRED')
    context=reader.get(value['context_ref'])
    interface=reader.get(context['interface_ref'])
    observation=reader.get(context['execution_contract_ref'])
    seed.need(context['schema']=='ai4r-rsi-root-helper-context:1' and context['worker_image']==IMAGE
        and interface['worker_program_ref']==observation['worker_program_ref']
        and observation['execution_authorized'] is False and observation['qualification_required_before_effects'] is True,
        'ORIGINAL_EXECUTION_ENVELOPE_IS_OBSERVATION_ONLY')
    target=reader.get(preparation['target_profile_ref'])
    visible=reader.get(preparation['visible_context_ref'])
    seed.need(target['parent_ref']==context['parent_ref'] and target['parent_declaration_ref']==context['parent_declaration_ref']
        and visible['required_test_refs']==target['required_test_refs'] and len(visible['mandatory_fixtures'])==12,
        'SEALED_WORKER_TARGET_CONTEXT_DIFFERS')
    # New explicitly reviewed development bounds. The old observation's512MiB/
    # 1-second envelope is retained, not promoted or treated as permission.
    effective={'memory_mb':128,'pids_max':8,'timeout_s':5}
    runs=[]
    for key in ('diagnosis_contract_ref','proposal_contract_ref'):
        contract=reader.get(preparation[key])
        row=reader.db.execute('SELECT account_id,workspace_id,state FROM runs WHERE id=?',(contract['run_id'],)).fetchone()
        seed.need(row is not None and row[2]=='pending','FRESH_WORK_RUN_REQUIRED')
        runs.append(row[:2])
    seed.need(runs[0]==runs[1] and runs[0][1]==preparation['exact_binding_refs']['workspace_id'],'SAME_ISOLATED_PRINCIPAL_REQUIRED')
    intake=reader.get(preparation['intake_ref'])
    symptom=reader.read(intake['request_ref']).decode('utf8')
    execution={'schema':'ai4r-rsi-development-public-execution:1','id':id,
        'purpose':'public_development_observation_only','authority':'separate_Root_AUTH_and_once_plan_required',
        'observation_ref':context['execution_contract_ref'],'context_ref':value['context_ref'],
        'worker_image':IMAGE,'worker_program_ref':interface['worker_program_ref'],'process_policy':'single_process_seccomp_v1',
        'admin_runner_sha256':seed.digest(Path(run.__file__).read_bytes()),'canonical_executor_sha256':run.V18_EXECUTOR_SHA256,
        'environment_ref':context['environment_ref'],'hardware_ref':context['hardware_ref'],
        'parent_ref':target['parent_ref'],'target_profile_ref':preparation['target_profile_ref'],
        'visible_context_ref':preparation['visible_context_ref'],'public_fixtures':visible['mandatory_fixtures'],
        'resource_bounds':effective,'maximum_jobs':24,'maximum_candidates':1,'security':'UNQUALIFIED',
        'security_campaigns':'DEFERRED','hidden_evaluation':False,'final_evaluation':False,'signing':False,
        'qualification_ref':None,'package_ref':None,'admission_ref':None,'activation_ref':None}
    digest=seed.digest(seed.encoded(execution));execution_ref={'id':digest+'.json','sha256':digest}
    auth={'schema':run.AUTH_SCHEMA,'id':id,'expires_at':value['expires_at'],**dest,
        **{key:preparation[key] for key in ('diagnosis_contract_ref','proposal_contract_ref','run_contexts','host_binding_ref','host_id',
            'exact_binding_refs','work_capsule_refs','parent_declaration_ref','target_profile_ref','visible_context_ref','preparation_ref','public_original_refs')},
        'worker':dict(effective,contract_ref=execution_ref,environment_ref=context['environment_ref'],hardware_ref=context['hardware_ref']),
        'principal':{'account_id':runs[0][0],'workspace_ids':[runs[0][1]],'operations':['status'],'audiences':['researcher']},
        'target_kind':interface['target_kind'],'limits':{'max_attempts':1,'max_no_progress':1,'wall_s':3600,
            'per_call_s':120,'session_query_limit':2,'lifetime_query_limit':2},
        'seed_receipt':value['seed_receipt'],'launch_guard_receipt':value['launch_guard_receipt'],
        'forbidden_roots':value['forbidden_roots'],'cgroup_root':value['cgroup_root'],'evaluator_root':value['evaluator_root'],
        'observed_symptom':symptom,'authorized_component':target['mutable_paths'][0]}
    run.validate_authorization(auth)
    seed.need(execution_ref not in auth['public_original_refs'],'EXECUTION_AUTHORITY_NOT_MODEL_INTAKE')
    return auth,execution,execution_ref


def plan(input_path):
    seed.need(os.name=='posix' and os.geteuid()==0,'ROOT_AUTHORIZATION_STAGING_REQUIRED')
    raw=seed.read(input_path);value=seed.parse(raw)
    seed.need(set(value) in (FIELDS,FIELDS|{'supersedes'}) and value['schema']=='ai4r-rsi-development-authorize-input:1','CLOSED_AUTHORIZATION_INPUT_REQUIRED')
    done=seed.parse(file_ref(value['preparation_receipt']))
    seed.need(done['schema']=='ai4r-rsi-development-preparation-completion:1' and done['model_calls']==0
        and done['qualification'] is False,'REAL_ZERO_MODEL_PREPARATION_REQUIRED')
    preparation=seed.parse(file_ref(done['output'],12001))
    complete=seed.read_completed_seed(value['seed_receipt']);seed.read_launch_guard(value['launch_guard_receipt'],value['seed_receipt'])
    reader=run.Originals(complete['destination'])
    try:
        auth,execution,pin=derive(value,preparation,complete,reader)
        seed.need(reader.db.execute('SELECT COUNT(*) FROM model_calls').fetchone()[0]==0
            and reader.db.execute('SELECT COUNT(*) FROM tool_calls').fetchone()[0]==0
            and reader.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==0,'UNISSUED_ZERO_DISPATCH_REQUIRED')
        if 'supersedes' in value:
            old=seed.parse(file_ref(value['supersedes']))
            old_execution=reader.get(old['worker']['contract_ref'])
            validate_source_revision(auth,execution,old,old_execution)
            seed.need(not Path(value['supersedes']['path']).with_name('development-claim.json').exists(),
                'PREVIOUS_RUN_ALREADY_ISSUED')
            seed.need(not os.path.lexists(Path('/var/lib/ai4r-cc-rsi-development')/auth['id']/'claim.json'),
                'NATIVE_UI_RUN_ALREADY_ISSUED')
            run.empty_native_scope(auth)
    finally:reader.close()
    output=Path(input_path).with_name('authorization.json')
    seed.need(not output.exists() and not Path(input_path).with_name('claim.json').exists(),'AUTHORIZATION_ALREADY_ISSUED_NO_REPLAY')
    seed.need('supersedes' in value or not any(Path(auth['record_root']).iterdir()),'NEW_OWN_CAPTURE_STORE_REQUIRED')
    facts={'schema':'ai4r-rsi-development-authorize-plan:1','id':value['id'],'input_sha256':seed.digest(raw),
        'source_pins':{Path(__file__).name:seed.digest(Path(__file__).read_bytes()),'runner':seed.digest(Path(run.__file__).read_bytes()),
            'seed':seed.digest(Path(seed.__file__).read_bytes())},'authorization_sha256':seed.digest(seed.encoded(auth)),
        'execution_ref':pin,'observation_ref':execution['observation_ref'],'worker':auth['worker'],
        'supersedes':value.get('supersedes'),
        'launch_window':{'previous_expires_at':old['expires_at'] if 'supersedes' in value else None,'expires_at':auth['expires_at']},
        'output':str(output),'maximum_model_calls':2,'maximum_jobs':24,'security':'UNQUALIFIED','qualification':False}
    return facts,auth,execution,pin


def stage(input_path,reviewed):
    facts,auth,execution,pin=plan(input_path)
    seed.need(seed.digest(seed.encoded(facts))==reviewed and plan(input_path)[0]==facts,'EXACT_AUTHORIZATION_PLAN_REVIEW_REQUIRED')
    seed.exclusive(Path(input_path).with_name('claim.json'),{'schema':'ai4r-rsi-development-authorize-claim:1','plan_sha256':reviewed})
    # Reuse the canonical own RecordStore. It was proven empty before claim;
    # only these newly created files are handed to the isolated caller.
    from jiuwenswarm.research_rsi.records import RecordStore
    # A source-only unissued revision may append to the existing caller-owned
    # store. put() uses only the canonical immutable byte writer, not indexes.
    path=Path(auth['record_root'])/pin['id']
    new_capture=not os.path.lexists(path)
    store=object.__new__(RecordStore);store.root=Path(auth['record_root']);store.file_mode=0o600
    try:seed.need(store.put(execution)==pin,'CAPTURED_DEVELOPMENT_EXECUTION_DIFFERS')
    finally:pass
    if new_capture:
        os.chown(path,12001,12001);path.chmod(0o600)
    else:
        # Window renewal reuses the same immutable execution record without
        # changing its ownership, mode or timestamps.
        seed.protected(path,12001)
    seed.exclusive(Path(facts['output']),auth,owner=0,gid=12001,mode=0o440)
    result={'schema':'ai4r-rsi-development-authorize-completion:1','id':auth['id'],'plan_sha256':reviewed,
        'authorization':{'path':facts['output'],'sha256':facts['authorization_sha256']},'execution_ref':pin,
        'observation_ref':execution['observation_ref'],'model_calls':0,'qualification':False}
    seed.exclusive(Path(input_path).with_name('complete.json'),result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('operation',choices=('plan','stage'));parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--review-sha256');args=parser.parse_args()
    result=plan(args.input)[0] if args.operation=='plan' else stage(args.input,args.review_sha256)
    print(json.dumps(result,sort_keys=True))
