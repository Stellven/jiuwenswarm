"""Deterministic private helper-session compilation; no execution authority.

Draft calibration and final operational profiles compile under distinct session
identities. Nothing here admits a parent, approves fixtures, contacts a model,
qualifies a runtime, publishes a job file or starts a session.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import asdict
from datetime import datetime
from fractions import Fraction
import hashlib
import json
import math

from .records import RecordStore,encoded
from .profiles import Limits,freeze_profile
from .session_policy import FinalBudget,validate_private,_contracts,BUDGET_SCHEMA
from .targets import registered_helper
from .targets.ranking_preparation import require_custodian_store
from .worker import ref,validate_profile
from .process_policy import POLICY

REQUEST_SCHEMA='urn:ai4r:private:rsi-helper-session-request:1'
RESULT_SCHEMA='urn:ai4r:private:rsi-helper-session-compilation:1'
MAX_BYTES=4*1024*1024


class SessionCompilationUnavailable(ValueError):pass


def _need(value):
    if not value:raise SessionCompilationUnavailable('Exact private helper compilation facts or a fresh session identity are unavailable')


def _read(store,pin):
    ref(pin);raw=store.read(pin)
    _need(isinstance(raw,bytes) and 0<len(raw)<=MAX_BYTES and hashlib.sha256(raw).hexdigest()==pin['sha256'])
    return raw


def _get(store,pin):
    from .diagnosis import closed_json
    value=closed_json(_read(store,pin));_need(isinstance(value,dict));return value


def _pin(value):
    digest=hashlib.sha256(encoded(value)).hexdigest();return {'id':digest+'.json','sha256':digest}


def _manifest(store,target,target_ref,pin,helper):
    value=_get(store,pin)
    fields={'schema','fixture_identity','target_ref','partitions','independent','independence_evidence_ref','calibration_ref'}
    _need(set(value)==fields and value['schema']=='ai4r-rsi-fixtures:1' and value['target_ref']==target_ref
          and value['calibration_ref']==target['calibration_ref'] and type(value['independent']) is bool
          and isinstance(value['fixture_identity'],str) and value['fixture_identity'])
    partitions=value['partitions'];names={'development','hidden_loop','hidden_final','platform'}
    _need(isinstance(partitions,dict) and set(partitions)==names)
    identities=set();inputs=set()
    for split,rows in partitions.items():
        _need(isinstance(rows,list) and 0<len(rows)<=256 and (not split.startswith('hidden_') or len(rows)>=20))
        for row in rows:
            _need(isinstance(row,dict) and set(row)=={'id','input_ref','expected_ref'}
                  and isinstance(row['id'],str) and row['id'] and row['id'] not in identities)
            identities.add(row['id'])
            _need(row['input_ref']['sha256'] not in inputs);inputs.add(row['input_ref']['sha256'])
            helper.validate_inputs(_get(store,row['input_ref']))
            _get(store,row['expected_ref'])
    _read(store,value['independence_evidence_ref'])
    return value


def _history_unused(store,sid):
    for table in ('session_history','session_phases','attempts','proposer_starts','security_halts'):
        column='session'
        _need(store.db.execute('SELECT 1 FROM '+table+' WHERE '+column+'=? LIMIT 1',(sid,)).fetchone() is None)


def compile_helper_session(store,*,target_ref,fixture_manifest_ref,session_id,started_by,limits,worker,
                           hash_profile_ref,invocation_wall_s,evidence_wall_s,frozen_at):
    """Return exact private refs and COMPILED_NOT_STARTED, never readiness."""
    require_custodian_store(store)
    _need(type(store) is RecordStore)
    narrowed=Limits.from_mapping(limits);limit_values=asdict(narrowed)
    request={'schema':'ai4r-rsi-helper-session-request:1','target_ref':copy.deepcopy(target_ref),
        'fixture_manifest_ref':copy.deepcopy(fixture_manifest_ref),'session_id':session_id,'started_by':started_by,
        'limits':limit_values,'worker':copy.deepcopy(worker),'hash_profile_ref':copy.deepcopy(hash_profile_ref),
        'invocation_wall_s':invocation_wall_s,'evidence_wall_s':evidence_wall_s,'frozen_at':frozen_at}
    validate_private(REQUEST_SCHEMA,request)
    _need(datetime.fromisoformat(frozen_at.replace('Z','+00:00')).utcoffset().total_seconds()==0)
    target=_get(store,target_ref);parent=_get(store,target['parent_declaration_ref'])
    _contracts().validate('capsule-declaration',parent)
    freeze_profile(target,parent,_contracts().validate)
    _need(narrowed.session_query_limit<=target['session_query_limit'] and narrowed.lifetime_query_limit<=target['lifetime_query_limit'])
    helper=registered_helper(worker['target_kind'])
    body=_read(store,target['parent_ref'])
    try:tree=ast.parse(body.decode('utf8'))
    except (SyntaxError,UnicodeError,RecursionError):raise SessionCompilationUnavailable('Frozen helper source is not a bounded parseable implementation') from None
    _need(sum(isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==helper.entrypoint for node in tree.body)==1)
    _need(not any(isinstance(node,ast.AsyncFunctionDef) and node.name==helper.entrypoint for node in tree.body))
    manifest=_manifest(store,target,target_ref,fixture_manifest_ref,helper)
    for key in ('frozen_contract_ref','configuration_ref','improver_ref','scoring_adapter_ref','calibration_ref'):_read(store,target[key])
    for pin in target['required_test_refs']+target['protected_refs']:_read(store,pin)
    _read(store,hash_profile_ref)
    for key in ('contract_ref','environment_ref','hardware_ref'):_read(store,worker[key])
    score=target['scoring']
    _need(score['warmup_batches']==5 and score['paired_rounds']==7 and score['min_relative_gain']>=.1
          and score['noise_multiplier']>=3 and worker['process_policy']==POLICY
          and worker['memory_mb']<=target['limits']['memory_mb']
          and worker['timeout_s']<=min(target['limits']['time_s'],narrowed.per_call_s))
    final_units=len(manifest['partitions']['hidden_final']);mandatory_units=len(manifest['partitions']['platform'])
    calls=2*(mandatory_units+final_units*(1+5+7))
    reserve=math.ceil(calls*Fraction(str(invocation_wall_s))+Fraction(str(evidence_wall_s)))
    budget={'schema':'ai4r-rsi-final-budget:1','id':session_id+':final-budget','target_ref':copy.deepcopy(target_ref),
        'hidden_final_units':final_units,'mandatory_units':mandatory_units,'pass_count_repeats':1,
        'worker_timeout_s':worker['timeout_s'],'invocation_wall_s':invocation_wall_s,
        'evidence_wall_s':evidence_wall_s,'final_reserve_s':reserve}
    FinalBudget.from_record(budget,wall_s=narrowed.wall_s,target_ref=target_ref,repeats=1)
    budget_ref=_pin(budget)
    genesis={'session_id':session_id,'target_ref':copy.deepcopy(target_ref),'hash_profile_ref':copy.deepcopy(hash_profile_ref),
        'interface_revision':'M1-IF-009@r2','final_budget_ref':budget_ref}
    genesis_ref=_pin(genesis)
    session={'schema_version':'1.0.0','id':session_id,'session_id':session_id,'target_profile_ref':copy.deepcopy(target_ref),
        'parent':{'cc_name':parent['identity']['name'],'cc_version':parent['identity']['version_label'],
                  'declaration_sha256':target['parent_declaration_ref']['sha256']},
        'parent_declaration_ref':copy.deepcopy(target['parent_declaration_ref']),
        **{key:copy.deepcopy(target[key]) for key in ('improver_ref','scoring_adapter_ref','configuration_ref')},
        'hash_profile_ref':copy.deepcopy(hash_profile_ref),'chain_root_ref':genesis_ref,'limits':limit_values,
        'pass_count_repeats':1,'qualification':{'min_pass_rate_gain':.05,'alpha':.05,
            'min_timing_gain':score['min_relative_gain'],'noise_multiplier':score['noise_multiplier'],
            'warmup_batches':5,'paired_rounds':7},'started_by':started_by,'frozen_at':frozen_at}
    _contracts().validate('rsi-session',session);session_ref=_pin(session)
    profile={'schema':'ai4r-rsi-worker-profile:3',**copy.deepcopy(worker),'session_ref':session_ref,
        'target_ref':copy.deepcopy(target_ref),'parent_ref':copy.deepcopy(target['parent_ref'])}
    validate_profile(profile);profile_ref=_pin(profile)
    result={'status':'COMPILED_NOT_STARTED','session_ref':session_ref,'worker_profile_ref':profile_ref,
            'genesis_ref':genesis_ref,'final_budget_ref':budget_ref}
    request_ref=_pin(request)
    compilation={'schema':'ai4r-rsi-helper-session-compilation:1','request_ref':request_ref,**result}
    validate_private(RESULT_SCHEMA,compilation)
    with store.lock:
        store.db.execute('CREATE TABLE IF NOT EXISTS session_compilations(session TEXT PRIMARY KEY,request_ref TEXT NOT NULL,result_ref TEXT NOT NULL)')
        store.db.execute('BEGIN IMMEDIATE')
        try:
            _history_unused(store,session_id)
            old=store.db.execute('SELECT request_ref,result_ref FROM session_compilations WHERE session=?',(session_id,)).fetchone()
            if old is not None:
                _need(json.loads(old[0])==request_ref)
                existing=store.get(json.loads(old[1]));_need(existing==compilation)
            else:
                for value in (request,budget,genesis,session,profile):_need(store.put(value)==_pin(value))
                record_ref=store.put(compilation)
                store.db.execute('INSERT INTO session_compilations VALUES(?,?,?)',
                    (session_id,encoded(request_ref).decode(),encoded(record_ref).decode()))
            store.db.execute('COMMIT')
        except BaseException:store.db.execute('ROLLBACK');raise
    # Reconcile the public session and private budget using the existing owner
    # implementation too; actual fixture counts were used without evaluation.
    FinalBudget.for_session(session,store,worker_profile=profile,manifest=manifest)
    return copy.deepcopy(result)


def assemble_job2(store,*,session_ref,preparation_ref,approved_preparation_refs,visible_context_ref,
                  diagnosis_contract_ref,proposer_contract_refs,worker_profile_ref,fixture_identity,target_kind):
    """Capture a closed private job; ROOTPREFIX publication remains separate."""
    require_custodian_store(store)
    from .opportunity import validated_preparation
    _need(preparation_ref in approved_preparation_refs)
    session=_get(store,session_ref);_contracts().validate('rsi-session',session)
    limits=Limits.from_mapping(session['limits']);target=_get(store,session['target_profile_ref'])
    parent=_get(store,session['parent_declaration_ref']);freeze_profile(target,parent,_contracts().validate)
    profile=validate_profile(_get(store,worker_profile_ref));registered_helper(target_kind)
    _need(profile['schema']=='ai4r-rsi-worker-profile:3' and profile['session_ref']==session_ref
          and profile['target_ref']==session['target_profile_ref'] and profile['parent_ref']==target['parent_ref']
          and profile['target_kind']==target_kind and profile['process_policy']==POLICY)
    _need(store.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='session_compilations'").fetchone() is not None)
    compiled=store.db.execute('SELECT request_ref,result_ref FROM session_compilations WHERE session=?',(session['session_id'],)).fetchone()
    _need(compiled is not None)
    compilation=store.get(json.loads(compiled[1]))
    _need(compilation['session_ref']==session_ref and compilation['worker_profile_ref']==worker_profile_ref)
    compiler_request=store.get(json.loads(compiled[0]))
    manifest=_get(store,compiler_request['fixture_manifest_ref'])
    _need(manifest['fixture_identity']==fixture_identity and manifest['target_ref']==session['target_profile_ref'])
    facts=validated_preparation(store,preparation_ref,approved_preparation_refs=approved_preparation_refs,
        profile_ref=session['target_profile_ref'],parent=session['parent'])
    _need(facts['preparation']['worker_profile_ref']==worker_profile_ref)
    visible=_get(store,visible_context_ref)
    _need(set(visible)=={'context','mandatory_fixtures','required_test_refs'}
          and visible['required_test_refs']==target['required_test_refs'] and bool(visible['mandatory_fixtures']))
    tests=set()
    for row in visible['mandatory_fixtures']:
        _need(set(row)=={'input_ref','test_ref'} and row['test_ref'] in target['required_test_refs'])
        _read(store,row['input_ref']);tests.add(encoded(row['test_ref']))
    _need(tests=={encoded(pin) for pin in target['required_test_refs']})
    _need(len(proposer_contract_refs)==limits.max_attempts and len({encoded(pin) for pin in proposer_contract_refs})==len(proposer_contract_refs)
          and diagnosis_contract_ref not in proposer_contract_refs and isinstance(fixture_identity,str) and fixture_identity)
    identities=set()
    for pin in [diagnosis_contract_ref,*proposer_contract_refs]:
        contract=_get(store,pin);_contracts().validate('subnode-execution-contract',contract)
        _need(contract['configuration_ref']==session['configuration_ref'])
        for bound in [contract['subnode_limits'],*[row['limits'] for row in contract['bindings']]]:
            _need(bound['model_calls']==1 and bound['time_s']<=limits.per_call_s and bound['memory_mb']<=target['limits']['memory_mb'])
        identity=(contract['run_id'],contract['node_id'],contract.get('subnode_id',contract['bindings'][0]['id']),contract['attempt_id'])
        _need(identity not in identities);identities.add(identity)
    job={'schema':'ai4r-rsi-session-job:2','session_ref':session_ref,'preparation_ref':preparation_ref,
        'diagnosis_contract_ref':diagnosis_contract_ref,'visible_context_ref':visible_context_ref,
        'proposer_contract_refs':copy.deepcopy(proposer_contract_refs),'worker_profile_ref':worker_profile_ref,
        'fixture_identity':fixture_identity,'target_kind':target_kind}
    validate_private('urn:ai4r:private:rsi-session-job:2',job)
    with store.lock:
        store.db.execute('CREATE TABLE IF NOT EXISTS session_jobs(session TEXT PRIMARY KEY,session_ref TEXT NOT NULL,job_ref TEXT NOT NULL)')
        store.db.execute('BEGIN IMMEDIATE')
        try:
            old=store.db.execute('SELECT session_ref,job_ref FROM session_jobs WHERE session=?',(session['session_id'],)).fetchone()
            pin=_pin(job)
            if old is not None:_need(json.loads(old[0])==session_ref and json.loads(old[1])==pin)
            else:
                _need(store.put(job)==pin)
                store.db.execute('INSERT INTO session_jobs VALUES(?,?,?)',
                    (session['session_id'],encoded(session_ref).decode(),encoded(pin).decode()))
            store.db.execute('COMMIT')
        except BaseException:store.db.execute('ROLLBACK');raise
    return pin


def session_public_materials(store,*,session_ref,worker_profile_ref,parent_body_refs,
                             approved_public_refs=(),visible_context_ref=None,job_ref=None,
                             approved_preparation_refs=()):
    """Return a finite projection plus explicit external/private requirements.

    This is a private candidate bundle, not publication permission. Root must
    independently review it. Context originals absent from approved_public_refs
    remain external requirements. Never follow calibration, review, oracle or
    preparation records, even when their opaque pointers occur in public data.
    """
    require_custodian_store(store)
    session=_get(store,session_ref);_contracts().validate('rsi-session',session)
    profile=validate_profile(_get(store,worker_profile_ref))
    _need(profile['schema']=='ai4r-rsi-worker-profile:3' and profile['session_ref']==session_ref)
    _need(store.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='session_compilations'").fetchone() is not None)
    row=store.db.execute('SELECT request_ref,result_ref FROM session_compilations WHERE session=?',(session['session_id'],)).fetchone()
    _need(row is not None)
    compiled=store.get(json.loads(row[1]));request=store.get(json.loads(row[0]))
    _need(compiled['session_ref']==session_ref and compiled['worker_profile_ref']==worker_profile_ref)
    target=_get(store,session['target_profile_ref']);parent=_get(store,session['parent_declaration_ref'])
    freeze_profile(target,parent,_contracts().validate)
    _need(profile['target_ref']==session['target_profile_ref'] and profile['parent_ref']==target['parent_ref'])
    helper=registered_helper(profile['target_kind'])
    # Read only this known manifest's partition metadata to establish explicit
    # negative disclosure sets. Hidden input/expected bodies are never opened.
    manifest=_get(store,request['fixture_manifest_ref'])
    private=[request['fixture_manifest_ref'],target['calibration_ref'],manifest['calibration_ref'],manifest['independence_evidence_ref']]
    if job_ref is not None:
        _need(store.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='session_jobs'").fetchone() is not None)
        job_row=store.db.execute('SELECT session_ref,job_ref FROM session_jobs WHERE session=?',(session['session_id'],)).fetchone()
        _need(job_row is not None and json.loads(job_row[0])==session_ref and json.loads(job_row[1])==job_ref)
        selected_job=_get(store,job_ref);validate_private('urn:ai4r:private:rsi-session-job:2',selected_job)
        private.append(selected_job['preparation_ref'])
    for split in ('hidden_loop','hidden_final','platform'):
        for item in manifest['partitions'][split]:private.extend((item['input_ref'],item['expected_ref']))
    private_refs={encoded(pin) for pin in private};private_hashes={pin['sha256'] for pin in private}
    materials={};required=[];private_runtime=[]
    def include(pin):
        ref(pin);_need(encoded(pin) not in private_refs and pin['sha256'] not in private_hashes)
        raw=store.read(pin)
        _need(isinstance(raw,bytes) and len(raw)<=MAX_BYTES and hashlib.sha256(raw).hexdigest()==pin['sha256'])
        try:document=json.loads(raw)
        except (ValueError,UnicodeError):document=None
        if isinstance(document,dict):
            kind=document.get('schema','')
            _need(not isinstance(kind,str) or not kind.startswith(('ai4r-rsi-calibration','ai4r-rsi-fixture',
                'ai4r-rsi-ranking-preparation','ai4r-rsi-helper-preparation','ai4r-rsi-opportunity-preparation',
                'ai4r-rsi-ranking-review','ai4r-rsi-opportunity-review','ai4r-rsi-oracle')))
        old=materials.get(pin['id']);item={'ref':copy.deepcopy(pin),'bytes':raw}
        _need(old is None or old==item);materials[pin['id']]=item
    genesis=_get(store,session['chain_root_ref'])
    _need(genesis['final_budget_ref']==compiled['final_budget_ref'] and session['chain_root_ref']==compiled['genesis_ref'])
    FinalBudget.for_session(session,store,worker_profile=profile)
    for pin in (session_ref,worker_profile_ref,session['chain_root_ref'],genesis['final_budget_ref'],
                session['hash_profile_ref'],session['target_profile_ref'],session['parent_declaration_ref']):include(pin)
    expected={item['path']:item['sha256'] for item in parent['identity']['body']}
    _need(isinstance(parent_body_refs,dict) and set(parent_body_refs)==set(expected))
    from .profiles import safe_path
    for name,pin in parent_body_refs.items():
        safe_path(name);_need(pin['sha256']==expected[name]);include(pin)
    _need(parent_body_refs[target['mutable_paths'][0]]==target['parent_ref'])
    approved={encoded(pin) for pin in approved_public_refs}
    contexts=[session['configuration_ref'],session['improver_ref'],session['scoring_adapter_ref'],target['frozen_contract_ref'],
              *target['required_test_refs'],*target['protected_refs']]
    for pin in contexts:
        if pin['id'] in materials:continue
        if encoded(pin) in private_refs or pin['sha256'] in private_hashes:
            # Hidden/custody originals are deliberately excluded, not a request
            # to import them into any public or controller runtime store.
            continue
        elif encoded(pin) in approved:include(pin)
        elif pin not in required:required.append(pin)
    if visible_context_ref is not None:
        visible=_get(store,visible_context_ref)
        _need(set(visible)=={'context','mandatory_fixtures','required_test_refs'}
              and visible['required_test_refs']==target['required_test_refs'] and bool(visible['mandatory_fixtures']))
        tests=set()
        for item in visible['mandatory_fixtures']:
            _need(set(item)=={'input_ref','test_ref'} and item['test_ref'] in target['required_test_refs'])
            # Check negative disclosure before reading even an alleged visible input.
            _need(encoded(item['input_ref']) not in private_refs and item['input_ref']['sha256'] not in private_hashes)
            helper.validate_inputs(_get(store,item['input_ref']));include(item['input_ref']);tests.add(encoded(item['test_ref']))
        _need(tests=={encoded(pin) for pin in target['required_test_refs']});include(visible_context_ref)
    if job_ref is not None:
        _need(store.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='session_jobs'").fetchone() is not None)
        job_row=store.db.execute('SELECT session_ref,job_ref FROM session_jobs WHERE session=?',(session['session_id'],)).fetchone()
        _need(job_row is not None and json.loads(job_row[0])==session_ref and json.loads(job_row[1])==job_ref)
        job=_get(store,job_ref);validate_private('urn:ai4r:private:rsi-session-job:2',job)
        _need(job['session_ref']==session_ref and job['worker_profile_ref']==worker_profile_ref
              and job['target_kind']==profile['target_kind'] and job['fixture_identity']==manifest['fixture_identity']
              and job['preparation_ref'] in approved_preparation_refs)
        if visible_context_ref is not None:_need(job['visible_context_ref']==visible_context_ref)
        elif job['visible_context_ref'] not in required:required.append(job['visible_context_ref'])
        private_runtime.append(job['preparation_ref']);include(job_ref)
        # Contracts are public only when separately approved; the job merely
        # names their immutable refs and never grants the core runner authority.
        for pin in [job['diagnosis_contract_ref'],*job['proposer_contract_refs']]:
            if encoded(pin) in approved:include(pin)
            elif pin not in required:required.append(pin)
    return {'materials':tuple(materials[key] for key in sorted(materials)),
            'required_original_refs':tuple(copy.deepcopy(required)),
            'private_runtime_refs':tuple(copy.deepcopy(private_runtime))}
