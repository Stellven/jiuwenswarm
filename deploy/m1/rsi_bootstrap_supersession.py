"""Root-selected, append-only catalog profile supersession after containment.

Staging only captures metadata through the installed catalog owner. It never
dispatches a model, releases a lease, changes a fixture, or selects a runtime.
Root selection is a separate reviewed operation, completed last.
"""
from __future__ import annotations
import argparse
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
from contextlib import contextmanager
from collections import Counter

HERE=Path(__file__).resolve().parent
SELECTION_DIRECTORY=Path('/run/ai4r-rsi/bootstrap-supersession')
DEFAULT_ROOT=Path('/var/lib/ai4r-rsi-codex')
CHILD_INPUT=Path('/run/ai4r-rsi/supersession-input.json')
CHILD_PREDECESSOR=Path('/run/ai4r-rsi/supersession-predecessor')
GEN=re.compile(r'[a-z][a-z0-9-]{0,47}\Z')
PRIOR_NAMESPACE=re.compile(r'[a-z0-9][a-z0-9_.-]{0,63}\Z')
HASH=re.compile(r'[a-f0-9]{64}\Z')
MAX_RECOVERIES=4
MAX_HISTORICAL_EXTRA_CALLS=24
MAX_REGISTRY_GENERATIONS=32
MAX_REGISTRY_ENTRIES=128

def need(value,code='BOOTSTRAP_SUPERSESSION_PREREQUISITE_UNAVAILABLE'):
    if not value:raise ValueError(code)

def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(raw):return hashlib.sha256(raw).hexdigest()
def ref(value):
    need(isinstance(value,dict) and set(value)=={'id','sha256'} and isinstance(value['id'],str) and value['id'] and HASH.fullmatch(value['sha256']))
    return value

def sibling(name):
    spec=importlib.util.spec_from_file_location('bootstrap_supersession_'+name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def read(path,uid=0,gid=12001,mode=0o440,limit=4*1024*1024):
    need(path.is_absolute() and not any(p.is_symlink() for p in (path,*path.parents)),'UNSAFE_SUPERSESSION_PATH')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        if uid==0:
            for parent in path.parents:
                info=parent.stat();need(info.st_uid==0 and (not info.st_mode&0o022 or info.st_mode&stat.S_ISVTX),'ROOT_ONLY_SELECTION_ANCESTRY_REQUIRED')
        meta=os.fstat(fd)
        need(stat.S_ISREG(meta.st_mode) and meta.st_nlink==1 and (meta.st_uid,meta.st_gid,stat.S_IMODE(meta.st_mode))==(uid,gid,mode) and meta.st_size<=limit)
        with os.fdopen(fd,'rb',closefd=False) as stream:body=stream.read(limit+1)
        need(len(body)<=limit);return body
    finally:os.close(fd)

def get(path,**kwargs):return json.loads(read(path,**kwargs))

def directory(path,mode=0o750):
    need(not any(p.is_symlink() for p in (path,*path.parents)))
    meta=path.stat();need(stat.S_ISDIR(meta.st_mode) and (meta.st_uid,meta.st_gid,stat.S_IMODE(meta.st_mode))==(0,12001,mode))
    for parent in path.parents:
        info=parent.stat();need(info.st_uid==0 and (not info.st_mode&0o022 or info.st_mode&stat.S_ISVTX),'ROOT_ONLY_SELECTION_ANCESTRY_REQUIRED')

def sync(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

def new(path,body):
    directory(path.parent)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o440)
    with os.fdopen(fd,'wb') as stream:
        os.fchown(stream.fileno(),0,12001);os.fchmod(stream.fileno(),0o440);stream.write(body);stream.flush();os.fsync(stream.fileno())
    sync(path.parent)

def mkdir(path):
    path.mkdir(mode=0o750);os.chown(path,0,12001);os.chmod(path,0o750);sync(path.parent)

def validate_input(value):
    fields={'schema','generation','supersession_id','stage','fresh_profile_generation','authorization','original_bootstrap_sha256',
        'containment_receipt_ref','prior_uncertain_ref','release_record_ref','failed_model_call_ref','blocked_measurement_ref','budget_caps'}
    chained=value.get('schema')=='ai4r-rsi-bootstrap-supersession-input:2'
    if chained:fields.add('predecessor')
    need(set(value)==fields and value['schema'] in ('ai4r-rsi-bootstrap-supersession-input:1','ai4r-rsi-bootstrap-supersession-input:2'))
    if chained:
        prior=value['predecessor']
        need(prior is None or isinstance(prior,dict) and set(prior)=={'supersession_id','completion_sha256','selected_manifest_sha256'}
            and GEN.fullmatch(prior['supersession_id']) and all(HASH.fullmatch(prior[k]) for k in ('completion_sha256','selected_manifest_sha256'))
            and prior['supersession_id']!=value['supersession_id'],'EXACT_PREDECESSOR_REQUIRED')
    need(all(isinstance(value[k],str) and GEN.fullmatch(value[k]) for k in ('generation','supersession_id','stage','fresh_profile_generation')))
    need(isinstance(value['authorization'],str) and 0<len(value['authorization'])<=4096 and HASH.fullmatch(value['original_bootstrap_sha256']))
    for key in ('containment_receipt_ref','prior_uncertain_ref','release_record_ref','failed_model_call_ref','blocked_measurement_ref'):ref(value[key])
    caps=value['budget_caps'];need(set(caps)=={'pre_delivery','setup','including_rsi'} and all(type(v) is int for v in caps.values())
        and 0<caps['pre_delivery']<=(88 if chained else 67) and caps['pre_delivery']<caps['setup']<=(95 if chained else 74)
        and caps['including_rsi']==caps['setup']+2<=(97 if chained else 76),'CLOSED_BOUNDED_SUPERSESSION_BUDGET_REQUIRED')

def validate_successor(original,selected,request,old_runtime,new_runtime,old_binding,new_binding,profiles):
    """Only one whole profile identity changes; case bytes and all pins stay."""
    validate_input(request)
    old_rows={row['stage']:row for row in original['stages']};new_rows={row['stage']:row for row in selected['stages']}
    stage=request['stage'];need(stage in old_rows and set(old_rows)==set(new_rows))
    unchanged=set(original)-{'binding_ref','calibration_runtime_ref','profile_generations','stages'}
    need(set(selected)==set(original) and all(selected[key]==original[key] for key in unchanged),'ORIGINAL_BOOTSTRAP_CONTEXT_CHANGED')
    generations={**original['profile_generations'],stage:request['fresh_profile_generation']}
    need(generations[stage]!=original['profile_generations'][stage] and selected['profile_generations']==generations,'FRESH_SINGLE_STAGE_PROFILE_GENERATION_REQUIRED')
    for name in old_rows:
        if name!=stage:need(new_rows[name]==old_rows[name],'UNRELATED_STAGE_PROFILE_CHANGED')
    before=old_rows[stage];after=new_rows[stage]
    need({k:v for k,v in before.items() if k!='profile_ref'}=={k:v for k,v in after.items() if k!='profile_ref'}
        and before['profile_ref']!=after['profile_ref'],'SAME_COMPLETE_STAGE_CASE_INVENTORY_REQUIRED')
    old_profile,new_profile=profiles
    need(set(old_profile)==set(new_profile) and all(new_profile[k]==old_profile[k] for k in old_profile if k!='id')
        and new_profile['id']==old_profile['id'].rsplit(':generation:',1)[0]+':generation:'+request['fresh_profile_generation'], 'ORIGINAL_CASE_OR_CHECKING_POLICY_CHANGED')
    need(set(new_runtime)==set(old_runtime) and all(new_runtime[k]==old_runtime[k] for k in old_runtime if k not in {'id','approved_profile_refs','case_context_refs'}))
    expected_profiles=[after['profile_ref'] if value==before['profile_ref'] else value for value in old_runtime['approved_profile_refs']]
    expected_contexts={key:value for key,value in old_runtime['case_context_refs'].items() if key!=before['profile_ref']['sha256']}
    expected_contexts[after['profile_ref']['sha256']]=old_runtime['case_context_refs'][before['profile_ref']['sha256']]
    need(new_runtime['approved_profile_refs']==expected_profiles and new_runtime['case_context_refs']==expected_contexts,'ORIGINAL_CASE_CONTEXT_CHANGED_OR_PARTIAL_DATA_MERGED')
    need(set(old_binding)==set(new_binding) and all(new_binding[k]==old_binding[k] for k in old_binding if k!='protected_options'))
    old_options=old_binding['protected_options'];new_options=new_binding['protected_options']
    allowed={'calibration_runtime_ref','calibration_profile_refs','calibration_limitations'}
    need(set(new_options)==set(old_options) and all(new_options[k]==old_options[k] for k in old_options if k not in allowed)
        and new_options['calibration_runtime_ref']==selected['calibration_runtime_ref']
        and new_options['calibration_profile_refs']==expected_profiles
        and new_options['calibration_limitations']==old_options['calibration_limitations'],'ORIGINAL_RUNTIME_BINDING_CHANGED')

def completed_selection(path):
    directory(path)
    names={p.name for p in path.iterdir()}
    required={'input.json','claim.json','original-bootstrap.json','original-generation.json','generation.json','prepared.json','plan.json','selector.json','complete.json'}
    need(required<=names and names<=required|{'stage-failure.json','ancestry'},'PARTIAL_BOOTSTRAP_SUPERSESSION_BLOCKS_START')
    request=get(path/'input.json');validate_input(request)
    claim_raw=read(path/'claim.json');claim=json.loads(claim_raw)
    original_generation=get(path/'original-generation.json')
    expected_generation={**original_generation,'schema':'ai4r-rsi-bootstrap-generation:4','selection_required':{'supersession_id':request['supersession_id'],'claim_sha256':digest(claim_raw)}}
    need(get(path/'generation.json')==expected_generation,'ROOT_GENERATION_EXPECTATION_DIFFERS')
    prepared_raw=read(path/'prepared.json');prepared=json.loads(prepared_raw)
    plan_raw=read(path/'plan.json');plan=json.loads(plan_raw)
    selector_raw=read(path/'selector.json');selector=json.loads(selector_raw)
    complete=get(path/'complete.json')
    need(digest(read(path/'original-bootstrap.json'))==request['original_bootstrap_sha256'])
    need(claim=={'schema':'ai4r-rsi-bootstrap-supersession-claim:1','input_sha256':digest(read(path/'input.json')),
        'original_bootstrap_sha256':request['original_bootstrap_sha256'],'generation':request['generation'],'supersession_id':request['supersession_id']})
    need(plan['request']==request and plan['claim_sha256']==digest(claim_raw) and plan['prepared_sha256']==digest(prepared_raw)
        and selector=={'schema':'ai4r-rsi-bootstrap-selector:1','generation':request['generation'],
            'supersession_id':request['supersession_id'],'plan_sha256':digest(plan_raw),'prepared_sha256':digest(prepared_raw)})
    need(complete=={'schema':'ai4r-rsi-bootstrap-supersession-complete:1','claim_sha256':digest(claim_raw),
        'plan_sha256':digest(plan_raw),'selector_sha256':digest(selector_raw),'prepared_sha256':digest(prepared_raw)},'BOOTSTRAP_SUPERSESSION_COMPLETION_DIFFERS')
    need(prepared['request_sha256']==digest(encoded(request)) and prepared['model_calls']==0 and prepared['qualification_adopted'] is False)
    return request,prepared


def transition(original,selected,request):
    unchanged=set(original)-{'binding_ref','calibration_runtime_ref','profile_generations','stages'}
    need(set(selected)==set(original) and all(selected[k]==original[k] for k in unchanged))
    need(selected['profile_generations']=={**original['profile_generations'],request['stage']:request['fresh_profile_generation']})
    old={row['stage']:row for row in original['stages']};newrows={row['stage']:row for row in selected['stages']}
    need(request['stage'] in old and set(old)==set(newrows) and all(newrows[k]==old[k] for k in old if k!=request['stage']))
    stage=request['stage']
    need(old[stage]['profile_ref']!=newrows[stage]['profile_ref']
        and {k:v for k,v in old[stage].items() if k!='profile_ref'}=={k:v for k,v in newrows[stage].items() if k!='profile_ref'})


def has_predecessor(request):return request.get('predecessor') is not None


def selection_chain(path,seen=()):
    request,prepared=completed_selection(path)
    identity=request['supersession_id']
    need(identity not in seen and len(seen)<MAX_RECOVERIES,'CYCLIC_OR_EXCESSIVE_SUPERSESSION_CHAIN')
    if has_predecessor(request):
        prior_path=path/'ancestry'
        chain=selection_chain(prior_path,(*seen,identity))
        prior_request,prior_prepared,_=chain[-1]
        need(request['predecessor']=={'supersession_id':prior_request['supersession_id'],
            'completion_sha256':digest(read(prior_path/'complete.json')),
            'selected_manifest_sha256':digest(encoded(prior_prepared['manifest']))},'PREDECESSOR_CHAIN_DIFFERS')
        need(request['generation']==prior_request['generation'] and request['original_bootstrap_sha256']==prior_request['original_bootstrap_sha256']
            and read(path/'original-bootstrap.json')==read(prior_path/'original-bootstrap.json')
            and read(path/'original-generation.json')==read(prior_path/'original-generation.json'),'ORIGINAL_CHAIN_ROOT_CHANGED')
        base=prior_prepared['manifest']
    else:
        need(not os.path.lexists(path/'ancestry'),'UNEXPECTED_SELECTOR_ANCESTRY')
        chain=[];base=get(path/'original-bootstrap.json')
    transition(base,prepared['manifest'],request)
    need(all(row[0]['fresh_profile_generation']!=request['fresh_profile_generation']
             and row[0]['failed_model_call_ref']!=request['failed_model_call_ref'] for row in chain),'PROFILE_OR_FAILURE_REPLAY')
    return [*chain,(request,prepared,path)]


def issued_chains(root,*,pending=None):
    """Validate every generation, even when selecting only one for recovery."""
    parent=Path(root)/'config/bootstrap-supersessions'
    if not os.path.lexists(parent):return {}
    directory(parent);paths=list(parent.iterdir())
    need(len(paths)<=MAX_REGISTRY_ENTRIES,'EXCESSIVE_SUPERSESSION_REGISTRY')
    if pending is not None:paths=[p for p in paths if p!=pending]
    groups={};identities=set()
    for path in paths:
        need(GEN.fullmatch(path.name),'UNKNOWN_BOOTSTRAP_SUPERSESSION_GENERATION')
        chain=selection_chain(path)
        need(path.name==(chain[-1][0]['generation'] if len(chain)==1 else chain[-1][0]['supersession_id']),'SELECTOR_DIRECTORY_IDENTITY_DIFFERS')
        item=chain[-1][0]
        need(item['supersession_id'] not in identities,'DUPLICATE_REGISTRY_SUPERSESSION_ID')
        identities.add(item['supersession_id']);groups.setdefault(item['generation'],[]).append(chain)
    need(len(groups)<=MAX_REGISTRY_GENERATIONS,'EXCESSIVE_SUPERSESSION_GENERATIONS')
    result={}
    for generation,chains in groups.items():
        need(len(chains)<=MAX_RECOVERIES,'EXCESSIVE_SUPERSESSION_CHAIN')
        leaf=max(chains,key=len)
        need(len(leaf)==len(chains),'BRANCHED_OR_ORPHAN_SUPERSESSION_CHAIN')
        for chain in chains:
            need([(r,p) for r,p,_ in chain]==[(r,p) for r,p,_ in leaf[:len(chain)]],'PREDECESSOR_OR_BRANCH_CHANGED')
            # Copied ancestry must retain each original Root file's exact bytes.
            for (_,_,copy_path),(_,_,original_path) in zip(chain,leaf):
                for name in (p.name for p in original_path.iterdir() if p.is_file()):
                    need(read(copy_path/name)==read(original_path/name),'ANCESTOR_ORIGINAL_BYTES_CHANGED')
        result[generation]=leaf
    return result


def issued_chain(root,*,generation=None,pending=None):
    groups=issued_chains(root,pending=pending)
    if generation is not None:
        need(isinstance(generation,str) and GEN.fullmatch(generation),'EXPLICIT_BOOTSTRAP_GENERATION_REQUIRED')
        return groups.get(generation,[])
    need(len(groups)<=1,'EXPLICIT_BOOTSTRAP_GENERATION_REQUIRED')
    return next(iter(groups.values()),[])


def target_path(root,request):
    return root/'config/bootstrap-supersessions'/(request['supersession_id'] if has_predecessor(request) else request['generation'])


def copy_selection(source,target):
    selection_chain(source)
    mkdir(target)
    for path in source.iterdir():
        if path.is_dir():copy_selection(path,target/path.name)
        else:new(target/path.name,read(path))


def same_selection_copy(source,target):
    selection_chain(source);selection_chain(target)
    need({p.name for p in source.iterdir()}=={p.name for p in target.iterdir()},'ANCESTOR_COPY_ENTRIES_CHANGED')
    for path in source.iterdir():
        if path.is_dir():same_selection_copy(path,target/path.name)
        else:need(read(path)==read(target/path.name),'ANCESTOR_ORIGINAL_BYTES_CHANGED')


def predecessor(original,request,chain):
    if not has_predecessor(request):
        need(not chain,'ONLY_ONE_ROOT_INITIAL_SUPERSESSION_AUTHORIZED')
        return original
    need(chain and len(chain)<MAX_RECOVERIES,'COMPLETED_BOUNDED_PREDECESSOR_REQUIRED')
    prior,prepared,path=chain[-1]
    need(request['predecessor']=={'supersession_id':prior['supersession_id'],
        'completion_sha256':digest(read(path/'complete.json')),
        'selected_manifest_sha256':digest(encoded(prepared['manifest']))}
        and request['generation']==prior['generation']
        and request['original_bootstrap_sha256']==prior['original_bootstrap_sha256'],'EXACT_CURRENT_PREDECESSOR_REQUIRED')
    need(all(request['supersession_id']!=r['supersession_id'] and request['fresh_profile_generation']!=r['fresh_profile_generation']
             and request['failed_model_call_ref']!=r['failed_model_call_ref'] for r,_,_ in chain),'PROFILE_OR_FAILURE_REPLAY')
    return prepared['manifest']


def check_transition(store,base,selected,request):
    before=next(row for row in base['stages'] if row['stage']==request['stage'])
    after=next(row for row in selected['stages'] if row['stage']==request['stage'])
    validate_successor(base,selected,request,store.read_record(base['calibration_runtime_ref']),store.read_record(selected['calibration_runtime_ref']),
        store.read_record(base['binding_ref']),store.read_record(selected['binding_ref']),
        [store.read_record(before['profile_ref']),store.read_record(after['profile_ref'])])


def history_facts(store,leases,scope_ref,original,request,chain):
    """Rejoin every historical failure/release, then the current released effect."""
    current=predecessor(original,request,chain)
    all_requests=[r for r,_,_ in chain]+[request]
    failures=[];base=original;charged=[]
    for index,(item,prepared,path) in enumerate([*chain,(request,None,None)]):
        _,start=release_chain(leases,scope_ref,item,require_current=prepared is None)
        failure=failed_capacity(store,base,item,known_failed_refs=[r['failed_model_call_ref'] for r in all_requests if r!=item])
        need(start['contract_ref']==failure['profile_ref'])
        released_failure_join(leases,item,failure)
        need(not any(pin in charged for pin in failure['old_stage_calls']),'HISTORICAL_STAGE_CHARGE_REUSED')
        charged.extend(failure['old_stage_calls']);failures.append(failure)
        if prepared is not None:
            need({k:v for k,v in failure.items() if k!='all_started_model_calls'}==
                 {k:v for k,v in prepared['failure'].items() if k!='all_started_model_calls'},'HISTORICAL_FAILURE_OR_CHARGES_CHANGED')
            check_transition(store,base,prepared['manifest'],item)
            base=prepared['manifest']
    need(base==current and len(charged)<=MAX_HISTORICAL_EXTRA_CALLS,'BOUNDED_HISTORICAL_CHARGES_REQUIRED')
    baseline_setup=sum(row['model_calls_ceiling'] for row in original['stages'])
    baseline_pre=sum(row['model_calls_ceiling'] for row in original['stages'] if row['stage']!='delivery')
    caps={'pre_delivery':baseline_pre+len(charged),'setup':baseline_setup+len(charged),'including_rsi':baseline_setup+len(charged)+2}
    need(request['budget_caps']==caps,'CUMULATIVE_ORIGINAL_CHARGES_MUST_FIT_REVIEWED_CAPS')
    return current,failures[-1],len(charged)

def selected_bootstrap(original,original_raw,*,path=SELECTION_DIRECTORY,expected=None):
    if not os.path.lexists(path):
        need(expected is None,'REQUIRED_ROOT_BOOTSTRAP_SELECTOR_MOUNT_ABSENT')
        return original,None
    chain=selection_chain(path)
    request,prepared,_=chain[-1]
    need(expected=={'supersession_id':request['supersession_id'],'claim_sha256':digest(read(path/'claim.json'))},'ROOT_SELECTOR_EXPECTATION_REQUIRED')
    need(request['generation']==original.get('generation') and digest(original_raw)==request['original_bootstrap_sha256']
        and json.loads(read(path/'original-bootstrap.json'))==original,'ORIGINAL_BOOTSTRAP_GENERATION_DIFFERS')
    return prepared['manifest'],{'request':request,'prepared':prepared,'directory':str(path)}

def verify_deployment_selections(root):
    issued_chains(root)

def source_pins():
    from jiuwenswarm.research_rsi import native_lease
    return {**{name:digest((HERE/name).read_bytes()) for name in ('rsi_bootstrap_supersession.py','rsi_operational_bootstrap.py','rsi_local.py')},
        'native_lease.py':digest(Path(native_lease.__file__).read_bytes())}

def assert_released(leases,scope_ref,containment_ref,*,require_current=True):
    row=leases.db.execute('SELECT state,ref FROM native_effect_leases WHERE scope=?',(encoded(scope_ref).decode(),)).fetchone()
    current=None if row is None else {'state':row[0],'ref':json.loads(row[1])}
    if require_current:need(current=={'state':'complete','ref':containment_ref},'EXACT_SUPPORTED_NATIVE_RELEASE_REQUIRED')
    receipt=leases.get(containment_ref)
    fields={'schema','scope_ref','prior_lease_ref','owned_container_id','prior_pid_namespace','observed_exited','observed_no_owned_processes','evidence_refs','recorded_at'}
    need(set(receipt)==fields and receipt['schema']=='ai4r-rsi-native-containment:1' and receipt['scope_ref']==scope_ref
        and receipt['observed_exited'] is receipt['observed_no_owned_processes'] is True
        and HASH.fullmatch(receipt['owned_container_id']) and receipt['evidence_refs'],'ACTUAL_NATIVE_CONTAINMENT_RECEIPT_REQUIRED')
    start=leases.get(receipt['prior_lease_ref'])
    need(start['record_kind']=='rsi-native-effect-start:1' and start['scope_ref']==scope_ref
        and start['pid_namespace']==receipt['prior_pid_namespace'])
    for value in receipt['evidence_refs']:need(digest(leases.read(value))==value['sha256'])
    return receipt,start

def release_chain(leases,scope_ref,request,*,require_current=True):
    receipt,start=assert_released(leases,scope_ref,request['containment_receipt_ref'],require_current=require_current)
    uncertain=leases.get(request['prior_uncertain_ref']);release=leases.get(request['release_record_ref'])
    need(uncertain['record_kind']=='rsi-native-effect-completion:1' and uncertain['state']=='uncertain'
        and uncertain['scope_ref']==scope_ref and uncertain['prior_lease_ref']==receipt['prior_lease_ref'])
    need(set(release)=={'record_kind','scope_ref','prior_state','host_containment_ref','recorded_at'}
        and release['record_kind']=='rsi-native-effect-release:1' and release['scope_ref']==scope_ref
        and release['prior_state']=={'state':'uncertain','ref':request['prior_uncertain_ref']}
        and release['host_containment_ref']==request['containment_receipt_ref'],'SUPPORTED_EXACT_NATIVE_RELEASE_CHAIN_REQUIRED')
    return receipt,start

def released_failure_join(leases,request,failure):
    proof=leases.get(request['prior_uncertain_ref'])['proof']
    need(proof['no_dispatch_start_observed'] is False
        and sorted(proof['known_terminal_call_refs'],key=encoded)==sorted(failure['old_stage_calls'],key=encoded)
        and request['failed_model_call_ref'] in proof['known_terminal_call_refs'], 'EXACT_FAILED_EFFECT_LEASE_POPULATION_REQUIRED')

def failed_capacity(store,original,request,*,known_failed_refs=()):
    """Exact case/request/start/native-error joins; terminal text is insufficient."""
    from jiuwenswarm.research.local_model_codex import unpack_bundle
    rows={row['stage']:row for row in original['stages']};need(request['stage'] in rows)
    profile_ref=rows[request['stage']]['profile_ref']
    measurement=store.read_record(request['blocked_measurement_ref']);call=store.read_record(request['failed_model_call_ref'],contract_id='model-call')
    need(store.record_kind(request['blocked_measurement_ref'])=='calibration-measurement' and measurement['profile_ref']==profile_ref
        and measurement['status']=='blocked' and measurement['reason_code']=='provider_error' and measurement['result'] is None)
    profile=store.read_record(profile_ref)
    case=next(row for row in profile['cases'] if row['case_id']==measurement['case_id']);need(case['asset_kind']=='criteria')
    need(call['outcome']=='failed' and call['call_function']=='verifier' and call['observed_runtime'] is True
        and call['provider_error_code']=='provider_error','KNOWN_PROVIDER_CAPACITY_REFUSAL_REQUIRED')
    indexed=store.connection.execute('SELECT request_id,case_id,claim_ref FROM private_calibration_calls WHERE call_id=? AND execution_id=?',(call['id'],call['execution_id'])).fetchall()
    need(len(indexed)==1 and indexed[0]['case_id']==case['case_id'])
    claim_ref=json.loads(indexed[0]['claim_ref']);claim=store.read_record(claim_ref)
    grant=store.read_record(claim['grant_ref']);private_request=store.read_record(grant['request_ref'])
    need(private_request['calibration_profile_ref']==profile_ref and private_request['runtime_ref']==original['calibration_runtime_ref']
        and grant['case_id']==case['case_id'] and grant['subject_ref']==case['subject_ref']
        and claim['call_id']==call['id'] and claim['invocation_id']==call['invocation_id']==grant['invocation_id']
        and claim['execution_id']==call['execution_id']==grant['execution_id'])
    starts=[row for row in store.iter_records(kinds=('model-call-start',)) if row['record'].get('call_id')==call['id']]
    need(len(starts)==1 and starts[0]['record']['call_claim_ref']==claim_ref)
    natives=[value for value in call['evidence_refs'] if store.record_kind(value)=='host-codex-native-original']
    need(len(natives)==1);native=store.read_record(natives[0]);scope=native['scope']
    need(scope['call_id']==call['id'] and scope['invocation_id']==call['invocation_id'] and scope['execution_id']==call['execution_id'])
    bundle=unpack_bundle(json.loads(store.read_blob(native['raw_ref'])))
    need(bundle['outcome']=='failed' and bundle['error_code']=='provider_error' and bundle['requested_model']=='gpt-6.1-sol'
        and bundle['reasoning_effort']=='medium' and bundle['turn_completed']['turn']['status']=='failed'
        and bundle['turn_completed']['turn']['error']['codexErrorInfo']=='serverOverloaded','EXACT_STRUCTURED_SERVER_OVERLOAD_REQUIRED')
    old_calls=store.connection.execute('SELECT call_id,case_id FROM private_calibration_calls WHERE request_id=? ORDER BY case_id',(private_request['id'],)).fetchall()
    need(old_calls and sum(row['call_id']==call['id'] for row in old_calls)==1)
    attempts=store.connection.execute('SELECT case_id,state,receipt_ref FROM calibration_attempts WHERE profile_sha=?',(profile_ref['sha256'],)).fetchall()
    expected_cases=[row['case_id'] for row in profile['cases']]
    need({row['case_id'] for row in attempts}==set(expected_cases[:expected_cases.index(case['case_id'])+1]),'ORIGINAL_STAGE_HAS_EXTRA_OR_MISSING_CASE_EFFECTS')
    measurements=[]
    for row in attempts:
        measured_ref=json.loads(row['receipt_ref']);measured=store.read_record(measured_ref)
        need(store.record_kind(measured_ref)=='calibration-measurement' and measured['profile_ref']==profile_ref and measured['case_id']==row['case_id'])
        if row['case_id']==case['case_id']:
            need(measured_ref==request['blocked_measurement_ref'] and row['state']=='blocked')
        else:
            need(row['state']==measured['status']=='matched' and measured['reason_code'] is None and measured['result'] is not None,'EARLIER_SEMANTIC_OR_BUNDLE_MISMATCH_REQUIRES_SEPARATE_REVIEW')
            store.read_blob(measured['result']['result_ref'])
            for result_call in measured['result']['model_call_refs']:
                matched=[value for value in old_calls if value['call_id']==store.read_record(result_call)['id'] and value['case_id']==row['case_id']]
                need(len(matched)==1,'ORIGINAL_MATCHED_MEASUREMENT_REQUEST_JOIN_DIFFERS')
        measurements.append(measured_ref)
    terminal_rows=list(store.iter_records(kinds=('model-call',)))
    call_rows={row['record']['id']:row for row in terminal_rows}
    need(len(call_rows)==len(terminal_rows),'DUPLICATE_TERMINAL_MODEL_CALL_ID')
    for row in old_calls:need(row['call_id'] in call_rows and call_rows[row['call_id']]['record']['outcome']==('failed' if row['call_id']==call['id'] else 'completed'))
    all_starts=list(store.iter_records(kinds=('model-call-start',)))
    expected_failures=[*known_failed_refs,request['failed_model_call_ref']]
    actual_failures=[row['ref'] for row in call_rows.values() if row['record']['outcome']=='failed']
    need(len(all_starts)==len(call_rows) and {row['record']['call_id'] for row in all_starts}==set(call_rows)
        and all(row['record'].get('outcome') in {'completed','failed'} for row in call_rows.values())
        and sorted(actual_failures,key=encoded)==sorted(expected_failures,key=encoded),'UNCERTAIN_OR_ADDITIONAL_MODEL_EFFECT_PRESENT')
    return {'profile_ref':profile_ref,'case_id':case['case_id'],'request_ref':grant['request_ref'],
        'failed_model_call_ref':request['failed_model_call_ref'],'blocked_measurement_ref':request['blocked_measurement_ref'],
        'native_original_ref':natives[0],'old_stage_calls':[call_rows[row['call_id']]['ref'] for row in old_calls],
        'original_measurement_refs':sorted(measurements,key=encoded),
        'old_stage_calls_charged':len(old_calls),'all_started_model_calls':len(all_starts)}

def table_snapshot(store):
    def safe(value):return {'sqlite_blob_sha256':digest(value)} if isinstance(value,bytes) else value
    result={}
    for (name,) in store.connection.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        quoted='"'+name.replace('"','""')+'"'
        rows=[encoded([safe(value) for value in row]) for row in store.connection.execute('SELECT * FROM '+quoted)]
        result[name]=sorted(rows)
    return result

def preserves_snapshot(before,after):
    need(set(before)<=set(after))
    for name,rows in before.items():need(not (Counter(rows)-Counter(after[name])),'ORIGINAL_SQL_ROW_WAS_CHANGED_OR_REMOVED')

async def prepare_child(request):
    bootstrap=sibling('rsi_operational_bootstrap');bootstrap.select_generation(request['generation'])
    original=bootstrap.load_original()
    need(digest((bootstrap.ROOT/'bootstrap.json').read_bytes())==request['original_bootstrap_sha256'])
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research_rsi.records import RecordStore
    from jiuwenswarm.research.catalog_calibration import capture_catalog_calibration
    store=SQLiteRunStore(bootstrap.ROOT/'core',recover=False,input_root=bootstrap.ROOT/'input')
    leases=RecordStore(bootstrap.ROOT/'native-leases')
    try:
        scope_ref=leases.put({'schema':'ai4r-rsi-bootstrap-native-scope:1','account_root':str(bootstrap.ACCOUNT_ROOT),'root':str(bootstrap.ROOT)})
        chain=selection_chain(CHILD_PREDECESSOR) if has_predecessor(request) else []
        original,failure,historical_charges=history_facts(store,leases,scope_ref,original,request,chain)
        receipt=leases.get(request['containment_receipt_ref'])
        original_binding=bootstrap.validate_capture(store,original);before=table_snapshot(store)
        generations={**original['profile_generations'],request['stage']:request['fresh_profile_generation']}
        generated=await capture_catalog_calibration(store,configuration_ref=original['configuration_ref'],
            model_selection_profile_ref=original['model_selection_profile_ref'],deployment_ref=original['deployment_ref'],profile_generations=generations)
        binding=copy.deepcopy(original_binding)
        binding['protected_options'].update(calibration_runtime_ref=generated['runtime_ref'],calibration_profile_refs=generated['profile_refs'],calibration_limitations=generated['limitations'])
        binding_ref=store.put_blob(encoded(binding),media_type='application/json')
        selected={**original,'binding_ref':binding_ref,'calibration_runtime_ref':generated['runtime_ref'],
            'profile_generations':generations,'stages':bootstrap.calibration_plan(store,generated['profile_refs'])}
        oldrow=next(row for row in original['stages'] if row['stage']==request['stage']);newrow=next(row for row in selected['stages'] if row['stage']==request['stage'])
        validate_successor(original,selected,request,store.read_record(original['calibration_runtime_ref']),store.read_record(generated['runtime_ref']),
            original_binding,binding,[store.read_record(oldrow['profile_ref']),store.read_record(newrow['profile_ref'])])
        expected=request['budget_caps']
        preserves_snapshot(before,table_snapshot(store))
        need(len(list(store.iter_records(kinds=('model-call-start',))))==failure['all_started_model_calls'])
        prepared={'schema':'ai4r-rsi-bootstrap-supersession-prepared:1','request_sha256':digest(encoded(request)),
            'original_bootstrap_sha256':request['original_bootstrap_sha256'],'manifest':selected,'failure':failure,
            'containment_receipt_ref':request['containment_receipt_ref'],'prior_native_lease_ref':receipt['prior_lease_ref'],
            'original_sql_rows_sha256':digest(encoded({name:[digest(row) for row in rows] for name,rows in before.items()})),
            'replaced_profile_ref':oldrow['profile_ref'],'fresh_profile_ref':newrow['profile_ref'],
            'fresh_stage_model_calls':newrow['model_calls_ceiling'],'budget_caps':expected,'model_calls':0,'qualification_adopted':False}
        if chain:prepared['historical_extra_model_calls']=historical_charges
        return prepared
    finally:store.close();leases.close()

@contextmanager
def root_lock(root):
    import fcntl
    path=root/'config/bootstrap-supersession.lock'
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        meta=os.fstat(fd);need(stat.S_ISREG(meta.st_mode) and meta.st_nlink==1 and (meta.st_uid,meta.st_gid,stat.S_IMODE(meta.st_mode))==(0,0,0o600))
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);yield
    finally:os.close(fd)

class ReadCore:
    def __init__(self,path):
        self.root=path;self.connection=sibling('rsi_stopped_repair')._database(path/'state/research.sqlite3',12001)
        self.connection.row_factory=sqlite3.Row
    def read_blob(self,value):
        ref(value);row=self.connection.execute('SELECT sha256 FROM artifacts WHERE id=?',(value['id'],)).fetchone()
        need(row is not None and row['sha256']==value['sha256'])
        body=read(self.root/'artifacts/sha256'/value['sha256'][:2]/value['sha256'],uid=12001,gid=12001,mode=0o600)
        need(digest(body)==value['sha256']);return body
    def read_record(self,value,contract_id=None):
        result=json.loads(self.read_blob(value))
        if contract_id:
            from jiuwenswarm.research.contracts import validate
            validate(contract_id,result)
        return result
    def record_kind(self,value):
        self.read_blob(value);row=self.connection.execute('SELECT kind FROM records WHERE id=?',(value['id'],)).fetchone()
        need(row is not None);return row['kind']
    def iter_records(self,kinds):
        for row in self.connection.execute('SELECT r.kind,a.id,a.sha256 FROM records r JOIN artifacts a ON a.id=r.id ORDER BY r.rowid'):
            if row['kind'] not in kinds:continue
            value={'id':row['id'],'sha256':row['sha256']}
            yield {'kind':row['kind'],'ref':value,'record':self.read_record(value)}
    def close(self):self.connection.close()

class ReadLeases:
    def __init__(self,path):
        self.root=path;self.db=sibling('rsi_stopped_repair')._database(path/'index.sqlite',12001)
    def read(self,value):
        ref(value);need(value['id']==value['sha256']+'.json')
        body=read(self.root/value['id'],uid=12001,gid=12001,mode=0o600);need(digest(body)==value['sha256']);return body
    def get(self,value):return json.loads(self.read(value))
    def close(self):self.db.close()


def historical_capacity_dispositions(root,generation,*,pending=None):
    """Read-only completed Root recovery ancestry; grants no new dispatch."""
    chain=issued_chain(root,generation=generation,pending=pending)
    if not chain:return {'failed_refs':[],'links':[],'historical_extra_model_calls':0}
    need(all(item['generation']==generation for item,_,_ in chain),'CAPACITY_HISTORY_BOOTSTRAP_GENERATION_DIFFERS')
    namespace=root/'controller'/('operational-bootstrap.'+generation)
    original_raw=read(namespace/'bootstrap.json',uid=12001,gid=12001,mode=0o600)
    original=get(chain[0][2]/'original-bootstrap.json')
    need(read(chain[0][2]/'original-bootstrap.json')==original_raw
         and digest(original_raw)==chain[0][0]['original_bootstrap_sha256'],'ORIGINAL_CAPACITY_BOOTSTRAP_CHANGED')
    scope={'schema':'ai4r-rsi-bootstrap-native-scope:1','account_root':'/var/lib/ai4r-rsi/controller/accounts','root':original['root']}
    scope_sha=digest(encoded(scope));scope_ref={'id':scope_sha+'.json','sha256':scope_sha}
    core=ReadCore(namespace/'core');leases=ReadLeases(namespace/'native-leases')
    try:return rejoin_completed_capacity_history(core,leases,scope_ref,original,chain)
    finally:leases.close();core.close()


def rejoin_completed_capacity_history(core,leases,scope_ref,original,chain):
    """Revalidate historical released effects even after a later normal finish."""
    need(chain and len(chain)<=MAX_RECOVERIES and leases.get(scope_ref)=={
        'schema':'ai4r-rsi-bootstrap-native-scope:1','account_root':'/var/lib/ai4r-rsi/controller/accounts','root':original['root']},'EXACT_CAPACITY_SCOPE_REQUIRED')
    failed_refs=[item['failed_model_call_ref'] for item,_,_ in chain]
    need(len({encoded(pin) for pin in failed_refs})==len(failed_refs),'DUPLICATE_HISTORICAL_FAILED_REF')
    base=original;charged=[];links=[]
    baseline_setup=sum(row['model_calls_ceiling'] for row in original['stages'])
    baseline_pre=sum(row['model_calls_ceiling'] for row in original['stages'] if row['stage']!='delivery')
    for index,(item,prepared,path) in enumerate(chain):
        need(predecessor(original,item,chain[:index])==base)
        _,start=release_chain(leases,scope_ref,item,require_current=False)
        failure=failed_capacity(core,base,item,known_failed_refs=[pin for pin in failed_refs if pin!=item['failed_model_call_ref']])
        need(start['contract_ref']==failure['profile_ref'],'HISTORICAL_FAILED_PROFILE_DIFFERS')
        released_failure_join(leases,item,failure)
        need({k:v for k,v in failure.items() if k!='all_started_model_calls'}==
             {k:v for k,v in prepared['failure'].items() if k!='all_started_model_calls'},'HISTORICAL_FAILURE_OR_CHARGES_CHANGED')
        need(not any(pin in charged for pin in failure['old_stage_calls']),'HISTORICAL_STAGE_CHARGE_REUSED')
        charged.extend(failure['old_stage_calls'])
        caps={'pre_delivery':baseline_pre+len(charged),'setup':baseline_setup+len(charged),'including_rsi':baseline_setup+len(charged)+2}
        need(len(charged)<=MAX_HISTORICAL_EXTRA_CALLS and item['budget_caps']==prepared['budget_caps']==caps,'HISTORICAL_CHARGED_CAPS_DIFFER')
        check_transition(core,base,prepared['manifest'],item)
        links.append({'supersession_id':item['supersession_id'],'completion_sha256':digest(read(path/'complete.json')),
            'selected_manifest_sha256':digest(encoded(prepared['manifest'])),'failed_model_call_ref':item['failed_model_call_ref'],
            'containment_receipt_ref':item['containment_receipt_ref'],'release_record_ref':item['release_record_ref'],
            'original_stage_call_refs':failure['old_stage_calls'],'cumulative_extra_model_calls':len(charged),'budget_caps':caps})
        base=prepared['manifest']
    current=completed_scope_lease(core,leases,scope_ref,base,chain)
    return {'failed_refs':failed_refs,'links':links,'historical_extra_model_calls':len(charged),'current_native_lease':current}


def completed_scope_lease(core,leases,scope_ref,selected,chain):
    row=leases.db.execute('SELECT state,ref FROM native_effect_leases WHERE scope=?',(encoded(scope_ref).decode(),)).fetchone()
    need(row is not None and row[0]=='complete','CURRENT_EXACT_SCOPE_LEASE_NOT_COMPLETE')
    pin=json.loads(row[1]);value=leases.get(pin)
    if value.get('schema')=='ai4r-rsi-native-containment:1':
        matched=[item for item,_,_ in chain if item['containment_receipt_ref']==pin]
        need(len(matched)==1,'CURRENT_CONTAINMENT_OUTSIDE_COMPLETED_CHAIN')
        release_chain(leases,scope_ref,matched[0],require_current=True)
    else:
        need(set(value)=={'record_kind','prior_lease_ref','scope_ref','state','proof','recorded_at'}
            and value['record_kind']=='rsi-native-effect-completion:1' and value['scope_ref']==scope_ref
            and value['state']=='complete','CURRENT_SCOPE_COMPLETION_PAYLOAD_DIFFERS')
        start=leases.get(value['prior_lease_ref'])
        need(set(start)=={'record_kind','scope_ref','session_id','contract_ref','pid_namespace','owner_pid','recorded_at'}
            and start['record_kind']=='rsi-native-effect-start:1' and start['scope_ref']==scope_ref
            and start['contract_ref'] in [row['profile_ref'] for row in selected['stages']]
            and isinstance(start['session_id'],str) and start['session_id'].startswith('catalog-calibration:')
            and type(start['owner_pid']) is int and start['owner_pid']>0
            and isinstance(start['pid_namespace'],str) and re.fullmatch(r'pid:\[\d+\]',start['pid_namespace'])
            and all(isinstance(value,str) and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ',value) for value in (start['recorded_at'],value['recorded_at'])), 'CURRENT_SCOPE_START_PROFILE_DIFFERS')
        starts=[]
        for entry in core.iter_records(kinds=('model-call-start',)):
            claim=core.read_record(entry['record']['call_claim_ref'])
            grant=core.read_record(claim['grant_ref']);request=core.read_record(grant['request_ref'])
            if request['calibration_profile_ref']==start['contract_ref']:starts.append(entry)
        from jiuwenswarm.research_rsi.native_lease import native_completion_proof
        known,proof=native_completion_proof(core,starts)
        need(known and value['proof']==proof,'CURRENT_SCOPE_COMPLETION_PROOF_DIFFERS')
    return {'ref':pin,'state':'complete','payload_sha256':digest(encoded(value))}


def foreign_namespace_facts(root,generation,original,*,pending=None):
    """Retain every prior namespace and reject foreign active/uncertain work."""
    prior=original['prior_namespaces']
    need(isinstance(prior,list) and len(prior)<=32 and len(set(prior))==len(prior)
         and all(isinstance(name,str) and PRIOR_NAMESPACE.fullmatch(name) and name!=generation for name in prior),
         'CLOSED_PRIOR_NAMESPACE_SET_REQUIRED')
    def namespace(name):return root/'controller'/('operational-bootstrap'+('' if name=='legacy' else '.'+name))
    expected={namespace(name).name for name in [*prior,generation]}
    need({path.name for path in (root/'controller').iterdir()}==expected,'PRIOR_NAMESPACE_CLOSURE_DIFFERS')
    groups=issued_chains(root,pending=pending)
    need(set(groups)<={*prior,generation},'FOREIGN_SELECTOR_NAMESPACE_OUTSIDE_CAPTURE')
    facts=[]
    for name in sorted(prior):
        path=namespace(name);meta=path.lstat()
        need(stat.S_ISDIR(meta.st_mode) and (meta.st_uid,meta.st_gid,stat.S_IMODE(meta.st_mode))==(12001,12001,0o700),'PRIOR_NAMESPACE_CUSTODY_DIFFERS')
        files={key:path/relative for key,relative in {'bootstrap':'bootstrap.json','core_index':'core/state/research.sqlite3','lease_index':'native-leases/index.sqlite'}.items()}
        hashes={key:digest(read(value,uid=12001,gid=12001,mode=0o600,limit=256*1024*1024)) for key,value in files.items()}
        leases=ReadLeases(path/'native-leases')
        try:
            counts=dict(leases.db.execute('SELECT state,count(*) FROM native_effect_leases GROUP BY state'))
            need(set(counts)<={'complete'},'FOREIGN_NATIVE_LEASE_NOT_COMPLETE')
        finally:leases.close()
        completed=historical_capacity_dispositions(root,name,pending=pending) if name in groups else None
        need(hashes=={key:digest(read(value,uid=12001,gid=12001,mode=0o600,limit=256*1024*1024)) for key,value in files.items()},'FOREIGN_NAMESPACE_CHANGED_DURING_CAPTURE')
        facts.append({'generation':name,'original_sha256':hashes,'native_states':counts,'completed_capacity_dispositions':completed})
    return facts

def root_observe(root,request):
    """No writers: actual released lease and original failure before staging."""
    repair=sibling('rsi_stopped_repair');repair.verify_repair_complete(root)
    value=json.loads(read(root/'local.json',gid=0,mode=0o600))
    need(value['root']==str(root) and value['model_backend']=='host-codex')
    namespace=root/'controller'/('operational-bootstrap.'+request['generation'])
    original_raw=read(namespace/'bootstrap.json',uid=12001,gid=12001,mode=0o600)
    need(digest(original_raw)==request['original_bootstrap_sha256'])
    original=json.loads(original_raw)
    need(original['generation']==request['generation'] and original['model']=='gpt-6.1-sol'
        and original['model_backend']=='host-codex-app-server' and original['reasoning_effort']=='medium')
    scope={'schema':'ai4r-rsi-bootstrap-native-scope:1','account_root':'/var/lib/ai4r-rsi/controller/accounts','root':original['root']}
    scope_sha=digest(encoded(scope));scope_ref={'id':scope_sha+'.json','sha256':scope_sha}
    pending=target_path(root,request)
    chain=issued_chain(root,generation=request['generation'],pending=pending)
    foreign=foreign_namespace_facts(root,request['generation'],original,pending=pending)
    leases=ReadLeases(namespace/'native-leases');core=ReadCore(namespace/'core')
    try:
        current,failure,historical_charges=history_facts(core,leases,scope_ref,original,request,chain)
        need(leases.get(scope_ref)==scope)
        return {'manifest':value,'original':current,'original_raw':original_raw,'namespace':namespace,'chain':chain,'foreign_namespaces':foreign,
            'failure':failure,'containment_receipt_sha256':digest(leases.read(request['containment_receipt_ref'])),
            'release_record_sha256':digest(leases.read(request['release_record_ref'])),
            'source_sha256':source_pins()}
    finally:leases.close();core.close()

def root_stage(root,input_path):
    request=get(input_path,gid=0,mode=0o600);validate_input(request)
    need(input_path==root/'config/bootstrap-supersession-inputs'/request['supersession_id']/'input.json')
    observed=root_observe(root,request)
    parent=root/'config/bootstrap-supersessions';target=target_path(root,request)
    need(not os.path.lexists(target),'ONE_SUPERSESSION_ONLY_NO_STAGING_REPLAY')
    groups=issued_chains(root)
    need(sum(len(chain) for chain in groups.values())<MAX_REGISTRY_ENTRIES
         and (request['generation'] in groups or len(groups)<MAX_REGISTRY_GENERATIONS),'SUPERSESSION_REGISTRY_CAPACITY_EXHAUSTED')
    if not parent.exists():mkdir(parent)
    directory(parent);mkdir(target)
    new(target/'input.json',encoded(request));new(target/'original-bootstrap.json',observed['original_raw'])
    if observed['chain']:copy_selection(observed['chain'][-1][2],target/'ancestry')
    claim={'schema':'ai4r-rsi-bootstrap-supersession-claim:1','input_sha256':digest(encoded(request)),
        'original_bootstrap_sha256':request['original_bootstrap_sha256'],'generation':request['generation'],'supersession_id':request['supersession_id']}
    new(target/'claim.json',encoded(claim))
    original_generation=read(root/'config'/('bootstrap-generation.'+request['generation']+'.json'))
    new(target/'original-generation.json',original_generation)
    generation={**json.loads(original_generation),'schema':'ai4r-rsi-bootstrap-generation:4',
        'selection_required':{'supersession_id':request['supersession_id'],'claim_sha256':digest(encoded(claim))}}
    new(target/'generation.json',encoded(generation))
    value=observed['manifest'];namespace=observed['namespace'];bootstrap=sibling('rsi_operational_bootstrap')
    command=sibling('rsi_stopped_repair').DOCKER+['run','--rm','--pull','never','--read-only','--network','none',
        '--cap-drop','ALL','--security-opt','no-new-privileges:true','--user','12001:12001','--group-add','13000',
        '--memory','1g','--pids-limit','64','--cpus','1','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=128m']
    mounts=[(namespace,observed['original']['root'],False),(target/'input.json',str(CHILD_INPUT),True),
        (target/'original-generation.json',str(bootstrap.GENERATION_CONFIG),True)]
    if observed['chain']:mounts.append((target/'ancestry',str(CHILD_PREDECESSOR),True))
    for name in ('rsi_bootstrap_supersession.py','rsi_operational_bootstrap.py'):
        mounts.append((HERE/name,'/run/setup/'+name,True))
    for source,destination,readonly in mounts:command+=['--mount','type=bind,src='+str(source)+',dst='+destination+(',readonly' if readonly else '')]
    command+=['--entrypoint','/opt/venv/bin/python',value['images']['rsi'],'-I','-B','/run/setup/rsi_bootstrap_supersession.py','child-prepare']
    response=subprocess.run(command,capture_output=True,timeout=180,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8'})
    need(response.returncode==0 and len(response.stdout)<=4*1024*1024,'CAPTURE_ONLY_SUPERSESSION_STAGING_FAILED_NO_REPLAY')
    prepared=json.loads(response.stdout)
    need(prepared['request_sha256']==digest(encoded(request)) and prepared['model_calls']==0 and prepared['failure']==observed['failure'])
    new(target/'prepared.json',encoded(prepared))
    return build_plan(root,request)

def build_plan(root,request):
    target=target_path(root,request);directory(target)
    need(not os.path.lexists(target/'selector.json') and not os.path.lexists(target/'complete.json'),'SUPERSESSION_ALREADY_SELECTED_OR_INTERRUPTED')
    observed=root_observe(root,request);prepared=get(target/'prepared.json')
    if observed['chain']:same_selection_copy(observed['chain'][-1][2],target/'ancestry')
    need(read(target/'original-bootstrap.json')==observed['original_raw'] and prepared['failure']==observed['failure']
        and prepared['request_sha256']==digest(encoded(request)) and prepared['model_calls']==0)
    core=ReadCore(observed['namespace']/'core')
    try:
        old=observed['original'];selected=prepared['manifest']
        old_binding=core.read_record(old['binding_ref']);new_binding=core.read_record(selected['binding_ref'])
        before=next(row for row in old['stages'] if row['stage']==request['stage']);after=next(row for row in selected['stages'] if row['stage']==request['stage'])
        validate_successor(old,selected,request,core.read_record(old['calibration_runtime_ref']),core.read_record(selected['calibration_runtime_ref']),
            old_binding,new_binding,[core.read_record(before['profile_ref']),core.read_record(after['profile_ref'])])
        assert_fresh(core,after['profile_ref'],selected['calibration_runtime_ref'])
    finally:core.close()
    return {'schema':'ai4r-rsi-bootstrap-supersession-plan:1','actor':'os:0:root','request':request,
        'claim_sha256':digest(read(target/'claim.json')),'prepared_sha256':digest(read(target/'prepared.json')),
        'source_sha256':observed['source_sha256'],'original_failure':observed['failure'],
        'foreign_namespaces':observed.get('foreign_namespaces',[]),
        'containment_receipt_sha256':observed['containment_receipt_sha256'],'release_record_sha256':observed['release_record_sha256'],
        'selected_manifest':prepared['manifest'],'model_calls':0,'selection_performed':False}

def assert_fresh(core,profile_ref,runtime_ref):
    for table,column in (('calibration_attempts','profile_sha'),('calibration_profiles','profile_sha'),('checking_asset_admissions','profile_sha')):
        need(core.connection.execute('SELECT 1 FROM '+table+' WHERE '+column+'=? LIMIT 1',(profile_ref['sha256'],)).fetchone() is None,'FRESH_PROFILE_ALREADY_REGISTERED_OR_ISSUED')
    for entry in core.iter_records(kinds=('check-calibration-request','calibration-case-grant','calibration-call-claim','calibration-measurement')):
        record=entry['record']
        need(record.get('calibration_profile_ref')!=profile_ref
            and record.get('runtime_ref')!=runtime_ref
            and not (entry['kind']=='calibration-measurement' and record.get('profile_ref')==profile_ref),
            'FRESH_PROFILE_HAS_PRIOR_REQUEST_GRANT_CALL_OR_MEASUREMENT')


def root_apply(root,request,review_sha256):
    need(isinstance(review_sha256,str) and HASH.fullmatch(review_sha256))
    plan=build_plan(root,request);need(digest(encoded(plan))==review_sha256,'EXACT_ROOT_SUPERSESSION_PLAN_REVIEW_REQUIRED')
    need(build_plan(root,request)==plan,'RELEASED_SOURCE_OR_CASE_STATE_CHANGED')
    target=target_path(root,request)
    new(target/'plan.json',encoded(plan))
    selector={'schema':'ai4r-rsi-bootstrap-selector:1','generation':request['generation'],'supersession_id':request['supersession_id'],
        'plan_sha256':review_sha256,'prepared_sha256':plan['prepared_sha256']}
    new(target/'selector.json',encoded(selector))
    done={'schema':'ai4r-rsi-bootstrap-supersession-complete:1','claim_sha256':plan['claim_sha256'],'plan_sha256':review_sha256,
        'selector_sha256':digest(encoded(selector)),'prepared_sha256':plan['prepared_sha256']}
    new(target/'complete.json',encoded(done));verify_deployment_selections(root)
    return {'status':'FRESH_WHOLE_STAGE_SELECTED_NOT_DISPATCHED','generation':request['generation'],'stage':request['stage'],
        'fresh_stage_model_calls':plan['selected_manifest']['stages'][[row['stage'] for row in plan['selected_manifest']['stages']].index(request['stage'])]['model_calls_ceiling'],
        'budget_caps':request['budget_caps'],'model_calls':0,'completion_sha256':digest(encoded(done))}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('operation',choices=('stage','plan','apply','child-prepare'));parser.add_argument('--root',type=Path,default=DEFAULT_ROOT)
    parser.add_argument('--input',type=Path);parser.add_argument('--review-sha256');args=parser.parse_args(argv)
    try:
        if args.operation=='child-prepare':
            need(os.geteuid()==os.getegid()==12001)
            request=get(CHILD_INPUT);validate_input(request)
            print(json.dumps(asyncio.run(prepare_child(request)),sort_keys=True));return 0
        need(os.geteuid()==os.getegid()==0)
        with root_lock(args.root):
            if args.operation=='stage':result=root_stage(args.root,args.input)
            else:
                request=get(args.input,gid=0,mode=0o600);validate_input(request)
                result=build_plan(args.root,request) if args.operation=='plan' else root_apply(args.root,request,args.review_sha256)
        print(json.dumps(result,sort_keys=True));return 0
    except Exception:
        print(json.dumps({'status':'BLOCKED','reason':'EXACT_RELEASED_KNOWN_CAPACITY_FAILURE_OR_ROOT_SUCCESSOR_UNAVAILABLE'}));return 2

if __name__=='__main__':raise SystemExit(main())
