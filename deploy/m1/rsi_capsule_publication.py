"""Disclose finite capsule evidence while preserving existing UI history.

The Root caller supplies captured originals. This module does not grant Run,
qualification, admission or activation authority and never executes carriers.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import stat

from jiuwenswarm.research_rsi.records import encoded
from jiuwenswarm.research_rsi.targets.capsules import public_fixtures, registered_capsule
_validator=None
_project_loop=None
VISIBLE_V1='ai4r-rsi-whole-capsule-visible-result:1'
VISIBLE_V2='ai4r-rsi-whole-capsule-visible-result:2'
LOOP_GRANT='ai4r-rsi-whole-capsule-development-grant:3'
PROTECTED_SCOPE='public_m1_development_only'


def configure_projection(pin):
    """Use the pinned public validator without initializing the application."""
    import importlib.util
    global _validator
    need(isinstance(pin,dict) and set(pin)=={'path','sha256'},'CLOSED_PUBLIC_PROJECTION_PIN_REQUIRED')
    path=protected(pin['path'])
    need(sha(path.read_bytes())==pin['sha256'],'PUBLIC_PROJECTION_SOURCE_DIFFERS')
    spec=importlib.util.spec_from_file_location('_capsule_public_projection',path)
    projection=importlib.util.module_from_spec(spec);spec.loader.exec_module(projection)
    _validator=projection.validate_publication
    global _project_loop
    _project_loop=getattr(projection,'project_loop',None)


def validate_publication(value,**kwargs):
    if _validator is None:
        # Source-library callers and tests use the fixed lightweight loader.
        # Every Root effect entrypoint configures its pinned validator first.
        from jiuwenswarm.research.cc_ui_runtime import module
        from importlib import import_module
        module('cc_rsi_installation')
        validator=import_module('_ai4r_cc_runtime.cc_rsi_projection').validate_publication
    else:validator=_validator
    return validator(value,**kwargs)


def project_loop(result,**kwargs):
    """Lineage block from the same pinned projection as the validator."""
    projector=_project_loop
    if _validator is None:
        from jiuwenswarm.research.cc_ui_runtime import module
        from importlib import import_module
        module('cc_rsi_installation')
        projector=import_module('_ai4r_cc_runtime.cc_rsi_projection').project_loop
    need(callable(projector),'PINNED_PROJECTION_LACKS_LOOP_LINEAGE')
    return projector(result,**kwargs)


def need(value, reason):
    if not value:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def original(read, pin):
    need(isinstance(pin, dict) and set(pin) == {'id', 'sha256'}, 'EXACT_PUBLIC_EVIDENCE_REF_REQUIRED')
    raw = read(pin)
    need(isinstance(raw, bytes) and sha(raw) == pin['sha256'], 'PUBLIC_EVIDENCE_BYTES_DIFFER')
    return raw


def captured(read, pin):
    return json.loads(original(read, pin))


def visible_summary(result, *, name, body_ref, read, grant_ref=None):
    """Reconcile scalar summaries against immutable Root job originals."""
    need(result['schema'] == 'ai4r-rsi-whole-capsule-visible-result:1'
         and result['capsule_name'] == name and result['security'] == 'UNQUALIFIED'
         and result['model_calls'] == 0 and result['hidden_evaluation'] == 'NOT_RUN'
         and result['admission_ref'] is result['activation_ref'] is None,
         'ONLY_PUBLIC_UNQUALIFIED_CAPSULE_EVIDENCE_ALLOWED')
    persisted = captured(read, result['result_ref'])
    need(persisted == {k:v for k,v in result.items() if k != 'result_ref'}, 'ROOT_RESULT_ORIGINAL_DIFFERS')
    grant = captured(read, result['grant_ref'])
    need(grant_ref is None or result['grant_ref'] == grant_ref, 'SESSION_GRANT_DIFFERS')
    need(grant['capsule_name'] == name and result['role'] in grant['roles']
         and result['scope'] == grant['scope'] == 'public_m1_development_only', 'ROOT_GRANT_SCOPE_DIFFERS')
    manifest = captured(read, result['runtime_manifest_ref'])
    need(sha(encoded(manifest)) == grant['runtime_manifest_sha256'], 'RUNTIME_MANIFEST_DIFFERS')
    fixtures = public_fixtures(name)
    rows = result['rows']
    need(type(result['executions']) is int and 0 < len(rows) == result['executions'] <= len(fixtures)
         and [r['fixture_id'] for r in rows] == [f['id'] for f in fixtures[:len(rows)]],
         'FINITE_ORDERED_PUBLIC_CASES_REQUIRED')
    refs, elapsed, passed, jobs = [], 0.0, 0, set()
    for index, (row, fixture) in enumerate(zip(rows, fixtures)):
        proof = captured(read, row['evidence_ref'])
        need(proof == {k:v for k,v in row.items() if k != 'evidence_ref'}, 'ROOT_CHECK_ORIGINAL_DIFFERS')
        start = captured(read, row['start_ref'])
        ident = 'capsule-' + sha(encoded([grant['run_id'], result['role'], fixture['id']]))[:48]
        need(start['schema'] == 'ai4r-rsi-whole-capsule-execution-start:1'
             and start['job_id'] == ident and start['grant_ref'] == result['grant_ref']
             and start['grant_sha256'] == result['grant_ref']['sha256']
             and start['candidate_ref'] == row['candidate_ref'] == body_ref
             and start['role'] == result['role'] and start['fixture_id'] == fixture['id']
             and start['runtime_manifest_ref'] == result['runtime_manifest_ref']
             and start['runtime_manifest_sha256'] == row['runtime_manifest_sha256'] == grant['runtime_manifest_sha256']
             and start['input_ref'] == row['input_ref'] and start['program_ref'] == row['program_ref'],
             'ROOT_EXECUTION_START_DIFFERS')
        if grant['schema'].endswith(':2'):
            need(start['bootstrap_schema'] == row['bootstrap_schema'] == grant['bootstrap_schema']
                 == 'ai4r-rsi-capsule-bootstrap:2', 'VERSIONED_INPUT_GUARD_REQUIRED')
        need(captured(read, start['test_ref']) == fixture
             and captured(read, row['input_ref']) == {'packet': fixture['packet']}, 'PUBLIC_INPUT_OR_FIXTURE_DIFFERS')
        original(read, row['program_ref']); original(read, body_ref)
        receipt = row['receipt']
        need(receipt['job_id'] == receipt['invocation_id'] == ident and ident not in jobs
             and receipt['subject_ref'] == body_ref and receipt['contract_ref'] == grant['worker']['contract_ref']
             and receipt['hardware_ref'] == grant['worker']['hardware_ref']
             and receipt['identity'] == {'executor_uid':12003, 'executor_gid':12003}
             and receipt['argv'] == ['/usr/local/bin/python3','-I','-S','/resources/worker.py']
             and receipt['repeat_index'] == index and receipt['sequence'] == 1
             and receipt['role'] == 'treatment' and receipt['seed'] == 0
             and row['group_empty'] is True and receipt['observed_runtime'] is True,
             'ACTUAL_V18_JOB_IDENTITY_DIFFERS')
        for key in ('contract_ref','hardware_ref'):
            original(read, receipt[key])
        stdout = original(read, receipt['stdout_ref'])
        original(read, receipt['stderr_ref'])
        original(read, receipt['observed_limits']['isolation_probe_ref'])
        wall = receipt['wall_time_s']
        need(type(wall) in (int,float) and math.isfinite(wall) and 0 <= wall <= grant['limits']['timeout_s'] + 30
             and row['protected_wall_s'] == wall and row['output_bytes'] == len(stdout), 'PROTECTED_CLOCK_OR_OUTPUT_DIFFERS')
        need(type(row['task_success']) is bool, 'ACTUAL_CHECK_OUTCOME_REQUIRED')
        if row['task_success']:
            check = row['independent_check']
            need(receipt['termination_reason'] == 'completed' and receipt['exit_code'] == 0
                 and not receipt['observed_limits']['admin_output_truncated']
                 and check['task_success'] is True and check['capsule_name'] == name
                 and check['input_sha256'] == row['input_ref']['sha256']
                 and check['output_sha256'] == sha(stdout) and check['output_bytes'] == len(stdout)
                 and check['checks_sha256'] == row['checks_sha256'], 'PASS_WITHOUT_SUCCESSFUL_PROTECTED_CHECK')
        refs.append(row['evidence_ref']); jobs.add(ident); elapsed += wall; passed += int(row['task_success'])
    need(result['passed_count'] == passed and type(result['passed_count']) is int
         and result['passed'] is (passed == len(fixtures)) and result['protected_wall_s'] == elapsed,
         'CAPSULE_SUMMARY_DIFFERS_FROM_ROOT_JOBS')
    return {'passed':passed, 'total':len(fixtures), 'executions':len(rows), 'wall_s':elapsed, 'refs':refs}


def _denied():
    return {'allowed':False, 'blocker':'Development only; security campaigns deferred. Manual production gates remain required.'}


def baseline_packet(meta, body, declaration, result, root_read):
    name = result['capsule_name']; target = registered_capsule(name)
    need(meta['target_id'] == name and meta['mutable_path'] == target.carrier_path, 'FIXED_CAPSULE_PUBLICATION_TARGET_REQUIRED')
    identity = declaration['identity']; digest = sha(body)
    need(identity['name'] == name and identity['carrier']['ref'] == target.carrier_path.removeprefix('research/')
         and identity['carrier']['sha256'] == digest
         and any(r['path'] == identity['carrier']['ref'] and r['sha256'] == digest for r in identity['body']),
         'ORIGINAL_CAPSULE_DECLARATION_DIFFERS')
    body_ref = result['rows'][0]['candidate_ref']
    need(body_ref['sha256'] == digest and result['role'] == 'parent', 'ORIGINAL_BASELINE_BODY_REQUIRED')
    summary = visible_summary(result,name=name,body_ref=body_ref,read=root_read)
    node_id = 'base:'+digest; code = body.decode('utf8')
    node = {'id':node_id,'target_id':name,'run_id':None,'parent_id':None,'hash':digest,
        'label':identity['name']+' '+identity['version_label'], 'security_status':'UNQUALIFIED',
        'evaluation_status':'passed' if summary['passed']==summary['total'] else 'failed',
        'admission_status':'unknown','activation_status':'unknown',
        'correctness':f"{summary['passed']}/{summary['total']} public checks",
        'speed':f"{summary['wall_s']:.6f} s protected total; no improvement claim", 'noise':'Not measured',
        'evidence_refs':[result['result_ref'],*summary['refs']], 'operator_receipts':[],
        'admit':_denied(),'activate':_denied()}
    packet={'workspace_id':meta['workspace_id'],'snapshot':{'schema_version':'1','revision':sha(encoded(result['result_ref'])),
        'generated_at':meta['published_at'],'availability':'AVAILABLE','blocker':None,
        'targets':[{'id':name,'name':meta['target_name'],'parent_hash':digest,'active_hash':None,'run':_denied()}],
        'runs':[],'nodes':[node]},'candidates':[{'node_id':node_id,'candidate_hash':digest,
        'path':target.carrier_path,'parent_code':code,'candidate_code':code,'rationale':None,
        'blocker':'Public baseline only; original production RSI policy grants no mutation authority.'}]}
    return validate_publication(packet,workspace_id=meta['workspace_id'])


def merge_publication(previous, packet, published_at):
    """Append/replace exact identities within one target, retaining all others."""
    validate_publication(previous); validate_publication(packet)
    need(previous['workspace_id'] == packet['workspace_id'], 'PUBLIC_WORKSPACE_DIFFERS')
    output=copy.deepcopy(previous)
    for key in ('targets','runs','nodes'):
        incoming={row['id']:row for row in packet['snapshot'][key]}
        existing={row['id']:row for row in output['snapshot'][key]}
        # An identity may only be updated inside its original target.
        for ident,row in incoming.items():
            old=existing.get(ident)
            if old is not None and key!='targets':
                need(old['target_id']==row['target_id'], 'CROSS_TARGET_IDENTITY_REPLACEMENT_REFUSED')
        output['snapshot'][key]=[incoming.pop(row['id'],row) for row in output['snapshot'][key]]+list(incoming.values())
    incoming={row['node_id']:row for row in packet['candidates']}
    output['candidates']=[incoming.pop(row['node_id'],row) for row in output['candidates']]+list(incoming.values())
    output['snapshot'].update(generated_at=published_at,availability='AVAILABLE',blocker=None)
    output['snapshot']['revision']=sha(encoded({k:v for k,v in output['snapshot'].items() if k not in ('revision','generated_at')}))
    need(len(encoded(output))<=2*1024*1024,'PUBLIC_CAPSULE_VIEW_EXCEEDS_LIMIT')
    return validate_publication(output,workspace_id=output['workspace_id'])


def session_packet(meta, session, result, read, root_read, previous=None):
    """Publish actual successes, poor proposals and retained terminal errors."""
    need(result['schema']=='ai4r-rsi-capsule-session-result:1' and result['id']==session['id']
         and result['capsule_name']==session['capsule_name'] and result['security']=='UNQUALIFIED'
         and result['security_campaigns']=='DEFERRED'
         and all(result[k] is None for k in ('qualification_ref','package_ref','admission_ref','activation_ref')),
         'EXACT_UNQUALIFIED_SESSION_RESULT_REQUIRED')
    need(result['hidden_evaluation']==result['final_evaluation']=='NOT_RUN', 'HIDDEN_OR_FINAL_EVIDENCE_REFUSED')
    captured_session=captured(read,result['session_ref'])
    need(captured_session==session,'SESSION_ORIGINAL_DIFFERS')
    parent=original(read,session['parent_body_ref']); declaration=captured(read,session['parent_declaration_ref'])
    parent_result=result['parent_visible']
    if parent_result is not None:
        need(parent_result['grant_ref']==session['grant_ref']
             and session['grant']['schema']=='ai4r-rsi-whole-capsule-development-grant:2',
             'SAME_VERSIONED_SESSION_PARENT_GRANT_REQUIRED')
    if parent_result is None:
        need(previous is not None,'ORIGINAL_PUBLISHED_BASELINE_REQUIRED')
        nodes=[n for n in previous['snapshot']['nodes'] if n['target_id']==session['capsule_name'] and n['parent_id'] is None and n['run_id'] is None]
        need(len(nodes)==1 and nodes[0]['hash']==sha(parent),'ORIGINAL_PUBLISHED_PARENT_DIFFERS')
        packet=copy.deepcopy(previous)
        packet['snapshot']['targets']=[t for t in packet['snapshot']['targets'] if t['id']==session['capsule_name']]
        packet['snapshot']['nodes']=copy.deepcopy(nodes);packet['snapshot']['runs']=[]
        packet['candidates']=[c for c in packet['candidates'] if c['node_id']==nodes[0]['id']]
    else:
        packet=baseline_packet(meta,parent,declaration,parent_result,root_read)
    view=packet['snapshot']; baseline=view['nodes'][0]
    budget={'elapsed_seconds':None,'limit_seconds':3600,'setup_calls':0,'diagnosis_calls':None,
        'proposal_calls':None,'generation_call_limit':2,'cost':None,'currency':None}
    if result['model_calls']==2:
        budget.update(diagnosis_calls=1,proposal_calls=1)
    run={'id':session['id'],'target_id':session['capsule_name'],'stage':'Complete',
        'status':result['status'],'blockers':[],'budget':budget,'activity':[{
            'id':session['id']+':terminal','at':meta['published_at'],'stage':'Complete',
            'status':result['status'],'summary':'Actual terminal development result; security campaigns deferred.'}]}
    if result['exception_type'] is not None:
        run['blockers']=['Retained '+result['exception_type']+'; this attempt cannot be replayed.']
    view['runs'].append(run)
    child_ref=result['candidate_ref']
    if child_ref is None and isinstance(result.get('proposal_capture'),dict):
        child_ref=result['proposal_capture'].get('child_ref')
    if child_ref is not None:
        child=original(read,child_ref).decode('utf8'); need(len(child.encode())<=256*1024,'PUBLIC_CANDIDATE_EXCEEDS_BOUND')
        candidate=result['candidate_visible']
        summary=None if candidate is None else visible_summary(candidate,name=session['capsule_name'],
            body_ref=child_ref,read=root_read,grant_ref=session['grant_ref'])
        node={'id':'candidate:'+session['id']+':'+child_ref['sha256'],'target_id':session['capsule_name'],
            'run_id':session['id'],'parent_id':baseline['id'],'hash':child_ref['sha256'],
            'label':session['capsule_name']+' proposal','security_status':'SECURITY_DEFERRED',
            'evaluation_status':'not_evaluated' if summary is None else ('passed' if summary['passed']==summary['total'] else 'failed'),
            'admission_status':'unadmitted','activation_status':'inactive',
            'correctness':None if summary is None else f"{summary['passed']}/{summary['total']} public checks",
            'speed':None if summary is None else f"{summary['wall_s']:.6f} s protected total; uncalibrated",
            'noise':'Not measured','evidence_refs':[] if summary is None else summary['refs'],
            'operator_receipts':[],'admit':_denied(),'activate':_denied()}
        view['nodes'].append(node)
        packet['candidates'].append({'node_id':node['id'],'candidate_hash':node['hash'],
            'path':meta['mutable_path'],'parent_code':parent.decode('utf8'),'candidate_code':child,
            'rationale':result['rationale'][:4096] if isinstance(result['rationale'],str) else None,
            'blocker':_denied()['blocker'] if summary is not None else 'Proposal retained without a completed public evaluation.'})
    return validate_publication(packet,workspace_id=meta['workspace_id'])


def interrupted_parent_summary(session, result, completion, root_results, root_read):
    """Reconcile a failed Root parent result lost by the controller transport."""
    need(result['status']=='ERROR_NO_REPLAY' and result['exception_type'] is not None
         and result['parent_visible'] is result['candidate_visible'] is result['candidate_ref'] is None
         and result['model_calls']==0 and completion['completed_roles']==['parent']
         and completion['halted'] is True, 'EXACT_INTERRUPTED_PARENT_REQUIRED')
    need(len(root_results)==1, 'EXACT_INTERRUPTED_ROOT_RESULT_REQUIRED')
    parent=root_results[0]
    need(parent['role']=='parent' and parent['grant_ref']==session['grant_ref']
         and parent['passed'] is False, 'FAILED_ORIGINAL_PARENT_REQUIRED')
    summary=visible_summary(parent,name=session['capsule_name'],body_ref=session['parent_body_ref'],
        read=root_read,grant_ref=session['grant_ref'])
    need(summary['executions']==completion['executions'], 'ROOT_TERMINAL_EXECUTION_COUNT_DIFFERS')
    return summary


def controller_failure_packet(meta, session, failure, previous, *, model_calls=None, call_limit=2, limit_seconds=3600):
    """Expose an actual controller failure, never synthesize session evidence."""
    need(failure['schema']=='ai4r-rsi-capsule-controller-failure:1'
         and failure['id']==session['id'] and failure['status']=='ERROR_NO_REPLAY'
         and isinstance(failure['exception_type'],str) and 0<len(failure['exception_type'])<=128,
         'EXACT_CONTROLLER_FAILURE_REQUIRED')
    need(meta['target_id']==session['capsule_name'] and meta['mutable_path']==session['authorized_component'],
         'CONTROLLER_FAILURE_TARGET_DIFFERS')
    validate_publication(previous,workspace_id=meta['workspace_id'])
    nodes=[n for n in previous['snapshot']['nodes'] if n['target_id']==session['capsule_name']
           and n['parent_id'] is None and n['run_id'] is None]
    need(len(nodes)==1 and nodes[0]['hash']==session['parent_body_ref']['sha256'],
         'ORIGINAL_PUBLISHED_CONTROLLER_PARENT_DIFFERS')
    packet=copy.deepcopy(previous)
    view=packet['snapshot']
    view['targets']=[t for t in view['targets'] if t['id']==session['capsule_name']]
    need(len(view['targets'])==1,'EXACT_PUBLISHED_CONTROLLER_TARGET_REQUIRED')
    view['targets'][0]['run']=_denied()
    view['nodes']=copy.deepcopy(nodes);view['runs']=[]
    packet['candidates']=[c for c in packet['candidates'] if c['node_id']==nodes[0]['id']]
    need(model_calls is None or model_calls==0,'EARLY_CONTROLLER_CALL_COUNT_UNKNOWN')
    message='Controller failed ('+failure['exception_type']+'); inspect retained evidence. This attempt cannot replay.'
    calls=0 if model_calls==0 else None
    view['runs'].append({'id':session['id'],'target_id':session['capsule_name'],'stage':'Failed',
        'status':'ERROR_NO_REPLAY','blockers':[message],
        'budget':{'elapsed_seconds':None,'limit_seconds':limit_seconds,'setup_calls':0,'diagnosis_calls':calls,
            'proposal_calls':calls,'generation_call_limit':call_limit,'cost':None,'currency':None},
        'activity':[{'id':session['id']+':controller-failure','at':meta['published_at'],
            'stage':'Controller','status':'ERROR_NO_REPLAY','summary':message}]})
    view['generated_at']=meta['published_at']
    return validate_publication(packet,workspace_id=meta['workspace_id'])


# ---------------------------------------------------------------------------
# Iterative loop sessions (Interface C ``loop``) and v2 visible results.
#
# Legacy single-attempt results (no ``loop``) never enter this section; their
# publication bytes are unchanged. Every disclosed number is joined against
# immutable Root originals; nothing is re-executed, and an unknown value stays
# unknown (``None``).
# ---------------------------------------------------------------------------
def require_protected_scope(result):
    """Interface A v2 reader for publication: protected Root results only."""
    need(isinstance(result,dict) and result.get('schema') in (VISIBLE_V1,VISIBLE_V2),'KNOWN_VISIBLE_RESULT_SCHEMA_REQUIRED')
    need(result.get('scope')!='local_unprotected','LOCAL_UNPROTECTED_RESULT_NOT_PUBLISHABLE')
    need(result.get('scope')==PROTECTED_SCOPE,'PROTECTED_ROOT_RESULT_SCOPE_REQUIRED')
    return result


def visible_summary_v2(result, *, name, body_ref, read, grant_ref=None, role=None, iteration=None):
    """Reconcile a v2 (loop) visible result, every trial, against Root originals."""
    from jiuwenswarm.research_rsi.targets.capsule_executor import grant_fixtures
    require_protected_scope(result)
    need(result['schema']==VISIBLE_V2 and result['capsule_name']==name and result['security']=='UNQUALIFIED'
         and result['model_calls']==0 and result['hidden_evaluation']=='NOT_RUN'
         and result['admission_ref'] is result['activation_ref'] is None,
         'ONLY_PUBLIC_UNQUALIFIED_CAPSULE_EVIDENCE_ALLOWED')
    persisted=captured(read,result['result_ref'])
    need(persisted=={k:v for k,v in result.items() if k!='result_ref'},'ROOT_RESULT_ORIGINAL_DIFFERS')
    need(grant_ref is None or result['grant_ref']==grant_ref,'SESSION_GRANT_DIFFERS')
    grant=captured(read,result['grant_ref'])
    need(grant['schema']==LOOP_GRANT and grant['capsule_name']==name and result['role'] in grant['roles']
         and (role is None or result['role']==role) and (iteration is None or result['iteration']==iteration)
         and result['subject_sha256']==body_ref['sha256'] and grant['scope']==PROTECTED_SCOPE,'ROOT_GRANT_SCOPE_DIFFERS')
    manifest=captured(read,result['runtime_manifest_ref'])
    need(sha(encoded(manifest))==grant['runtime_manifest_sha256'],'RUNTIME_MANIFEST_DIFFERS')
    fixtures=grant_fixtures(grant)
    trials=[result['rows'],*result['trial_rows']]
    need(type(result['executions']) is int and result['executions']==sum(len(rows) for rows in trials)
         and all([r['fixture_id'] for r in rows]==[f['id'] for f in fixtures] for rows in trials)
         and result['case_count']==len(fixtures)
         and result['held_out_case_count']==sum(f['fixture_set']=='held_out' for f in fixtures),
         'FINITE_ORDERED_EVALUATION_CASES_REQUIRED')
    key=[grant['run_id'],result['role'],result['iteration'],body_ref['sha256']]
    refs,jobs,walls=[],set(),[]
    counts={'public':[0,0],'held_out':[0,0]}
    for trial,rows in enumerate(trials):
        elapsed=0.0
        for index,(row,fixture) in enumerate(zip(rows,fixtures)):
            proof=captured(read,row['evidence_ref'])
            need(proof=={k:v for k,v in row.items() if k!='evidence_ref'},'ROOT_CHECK_ORIGINAL_DIFFERS')
            need(row['role']==result['role'] and row['iteration']==result['iteration'] and row['trial']==trial
                 and row['fixture_set']==fixture['fixture_set'],'EVALUATION_ROW_IDENTITY_DIFFERS')
            start=captured(read,row['start_ref'])
            ident='capsule-'+sha(encoded([*key,trial,fixture['id']]))[:48]
            need(start['schema']=='ai4r-rsi-whole-capsule-execution-start:1' and 'scope' not in start
                 and start['job_id']==ident and start['grant_ref']==result['grant_ref']
                 and start['grant_sha256']==result['grant_ref']['sha256']
                 and start['candidate_ref']==row['candidate_ref']==body_ref
                 and start['role']==result['role'] and start['fixture_id']==fixture['id']
                 and start['runtime_manifest_ref']==result['runtime_manifest_ref']
                 and start['runtime_manifest_sha256']==row['runtime_manifest_sha256']==grant['runtime_manifest_sha256']
                 and start['input_ref']==row['input_ref'] and start['program_ref']==row['program_ref']
                 and start['bootstrap_schema']==row['bootstrap_schema']==grant['bootstrap_schema'],
                 'ROOT_EXECUTION_START_DIFFERS')
            need(captured(read,start['test_ref'])==fixture
                 and captured(read,row['input_ref'])=={'packet':fixture['packet']},'EVALUATION_INPUT_OR_FIXTURE_DIFFERS')
            original(read,row['program_ref']);original(read,body_ref)
            receipt=row['receipt']
            need(receipt['job_id']==receipt['invocation_id']==ident and ident not in jobs
                 and receipt['subject_ref']==body_ref and receipt['contract_ref']==grant['worker']['contract_ref']
                 and receipt['hardware_ref']==grant['worker']['hardware_ref']
                 and receipt['identity']=={'executor_uid':12003,'executor_gid':12003}
                 and receipt['argv']==['/usr/local/bin/python3','-I','-S','/resources/worker.py']
                 and receipt['repeat_index']==index and receipt['sequence']==1
                 and receipt['role']=='treatment' and receipt['seed']==0
                 and row['group_empty'] is True and receipt['observed_runtime'] is True,
                 'ACTUAL_V18_JOB_IDENTITY_DIFFERS')
            for item in ('contract_ref','hardware_ref'):original(read,receipt[item])
            stdout=original(read,receipt['stdout_ref']);original(read,receipt['stderr_ref'])
            original(read,receipt['observed_limits']['isolation_probe_ref'])
            wall=receipt['wall_time_s']
            need(type(wall) in (int,float) and math.isfinite(wall) and 0<=wall<=grant['limits']['timeout_s']+30
                 and row['protected_wall_s']==wall and row['output_bytes']==len(stdout),'PROTECTED_CLOCK_OR_OUTPUT_DIFFERS')
            need(type(row['task_success']) is bool,'ACTUAL_CHECK_OUTCOME_REQUIRED')
            if row['task_success']:
                check=row['independent_check']
                need(receipt['termination_reason']=='completed' and receipt['exit_code']==0
                     and not receipt['observed_limits']['admin_output_truncated']
                     and check['task_success'] is True and check['capsule_name']==name
                     and check['checks_sha256']==row['checks_sha256'] and check['output_bytes']==len(stdout)
                     and (fixture['fixture_set']=='held_out' or (check['input_sha256']==row['input_ref']['sha256']
                          and check['output_sha256']==sha(stdout))),'PASS_WITHOUT_SUCCESSFUL_PROTECTED_CHECK')
            jobs.add(ident);elapsed+=wall
            if trial==0:
                counts[fixture['fixture_set']][0]+=int(row['task_success']);counts[fixture['fixture_set']][1]+=1
                if fixture['fixture_set']=='public':refs.append(row['evidence_ref'])
        walls.append(elapsed)
    passed=counts['public'][0]+counts['held_out'][0]
    need(result['passed_count']==passed and result['passed'] is (passed==len(fixtures))
         and result['protected_wall_s']==walls[0] and result['trial_wall_s']==walls
         and (result['failure'] is None)==(passed==len(fixtures)),'CAPSULE_SUMMARY_DIFFERS_FROM_ROOT_JOBS')
    return {'passed':passed,'total':len(fixtures),'executions':result['executions'],'wall_s':walls[0],'refs':refs,
            'trial_wall_s':walls,'public':counts['public'],'held_out':counts['held_out']}


def reviewer_view(raw):
    """The loop's lineage view of an exact Root result (held-out rows reduced)."""
    rows=[]
    for row in raw.get('rows',[]):
        if row.get('fixture_set')=='held_out':
            row={k:row[k] for k in ('fixture_id','fixture_set','task_success','protected_wall_s','evidence_ref') if k in row}
        rows.append(row)
    return {**raw,'rows':rows}


def root_visible(view, root_read):
    """Exact Root bytes behind a session-carried (possibly reduced) view."""
    require_protected_scope(view)
    raw=dict(captured(root_read,view['result_ref']),result_ref=view['result_ref'])
    need(view==raw or view==reviewer_view(raw),'SESSION_VIEW_DIFFERS_FROM_ROOT_RESULT')
    return raw


def _correctness(summary):
    public,held=summary['public'],summary['held_out']
    return (f"{summary['passed']}/{summary['total']} checks "
            f"({public[0]}/{public[1]} public, {held[0]}/{held[1]} held-out)")


def loop_baseline(meta, session, result, root_read, previous, parent):
    """The published original baseline, or (first loop run) the measured parent."""
    name=session['capsule_name']
    nodes=[] if previous is None else [n for n in previous['snapshot']['nodes'] if n['target_id']==name
           and n['parent_id'] is None and n['run_id'] is None]
    if nodes:
        need(len(nodes)==1 and nodes[0]['hash']==sha(parent),'ORIGINAL_PUBLISHED_PARENT_DIFFERS')
        packet=copy.deepcopy(previous)
        packet['snapshot']['targets']=[t for t in packet['snapshot']['targets'] if t['id']==name]
        packet['snapshot']['nodes']=copy.deepcopy(nodes);packet['snapshot']['runs']=[]
        packet['candidates']=[c for c in packet['candidates'] if c['node_id']==nodes[0]['id']]
        return packet
    raw=result['parent_visible']
    need(raw is not None,'ORIGINAL_PUBLISHED_BASELINE_REQUIRED')
    summary=visible_summary_v2(raw,name=name,body_ref=session['parent_body_ref'],read=root_read,
        grant_ref=session['grant_ref'],role='parent',iteration=0)
    target=registered_capsule(name);digest=sha(parent);node_id='base:'+digest
    node={'id':node_id,'target_id':name,'run_id':None,'parent_id':None,'hash':digest,'label':name+' baseline',
        'security_status':'UNQUALIFIED','evaluation_status':'passed' if summary['passed']==summary['total'] else 'failed',
        'admission_status':'unknown','activation_status':'unknown','correctness':_correctness(summary),
        'speed':f"{summary['wall_s']:.6f} s protected total; no improvement claim",'noise':'Not measured',
        'evidence_refs':[raw['result_ref'],*summary['refs']],'operator_receipts':[],'admit':_denied(),'activate':_denied()}
    packet={'workspace_id':meta['workspace_id'],'snapshot':{'schema_version':'1','revision':sha(encoded(raw['result_ref'])),
        'generated_at':meta['published_at'],'availability':'AVAILABLE','blocker':None,
        'targets':[{'id':name,'name':meta['target_name'],'parent_hash':digest,'active_hash':None,'run':_denied()}],
        'runs':[],'nodes':[node]},'candidates':[{'node_id':node_id,'candidate_hash':digest,'path':target.carrier_path,
        'parent_code':parent.decode('utf8'),'candidate_code':parent.decode('utf8'),'rationale':None,
        'blocker':'Public baseline only; original production RSI policy grants no mutation authority.'}]}
    return validate_publication(packet,workspace_id=meta['workspace_id'])


def loop_limits(loop):
    """Configured loop ceilings recorded in the session result."""
    cfg=loop.get('configuration') if isinstance(loop.get('configuration'),dict) else {}
    calls=cfg.get('max_model_calls');wall=cfg.get('wall_s')
    return (calls if type(calls) is int and calls>=0 else None), (wall if type(wall) is int and wall>0 else None)


def session_limits(session):
    """Configured loop ceilings when only the prepared session is known."""
    loop=session.get('loop')
    if not isinstance(loop,dict):return 2,3600
    iterations=loop.get('max_iterations',5)
    calls=loop.get('max_model_calls',min(100,2*iterations) if type(iterations) is int else None)
    wall=loop.get('wall_s',min(3600,session['grant']['limits']['wall_s']))
    return calls,wall


def terminal_state(result, served, issued):
    """success | partial | interrupted | failed, from retained evidence only."""
    loop=result['loop'];evaluated=[row for row in loop['iterations'] if row.get('visible') is not None]
    if result['parent_visible'] is None:return 'interrupted' if issued else 'failed'
    if loop['stop_reason']=='error' or served!=issued:return 'partial' if evaluated else 'failed'
    return 'success'


def loop_session_packet(meta, session, result, read, root_read, previous, *, served, issued, evaluator):
    """Every loop iteration, candidate and score from retained evidence.

    ``served``: executions of the evaluations the session validated;
    ``issued``: protected jobs Root started (its durable start claims);
    ``evaluator``: ``{'status','stop','exit_code'}`` of the Root evaluator.
    Jobs Root issued that the session never received (a failed or interrupted
    evaluation) are reported, never invented or re-run.
    """
    need(result['schema']=='ai4r-rsi-capsule-session-result:1' and result['id']==session['id']
         and result['capsule_name']==session['capsule_name'] and result['security']=='UNQUALIFIED'
         and result['security_campaigns']=='DEFERRED'
         and all(result[k] is None for k in ('qualification_ref','package_ref','admission_ref','activation_ref')),
         'EXACT_UNQUALIFIED_SESSION_RESULT_REQUIRED')
    need(result['hidden_evaluation']==result['final_evaluation']=='NOT_RUN','HIDDEN_OR_FINAL_EVIDENCE_REFUSED')
    need(captured(read,result['session_ref'])==session,'SESSION_ORIGINAL_DIFFERS')
    loop=result['loop']
    need(isinstance(loop,dict) and loop.get('schema')=='ai4r-rsi-capsule-loop:1' and isinstance(loop.get('iterations'),list)
         and session['grant']['schema']==LOOP_GRANT,'EXACT_LOOP_SESSION_REQUIRED')
    name=session['capsule_name'];parent=original(read,session['parent_body_ref'])
    if result['parent_visible'] is not None:
        need(result['parent_visible']['grant_ref']==session['grant_ref'],'SAME_VERSIONED_SESSION_PARENT_GRANT_REQUIRED')
        parent_summary=visible_summary_v2(result['parent_visible'],name=name,body_ref=session['parent_body_ref'],
            read=root_read,grant_ref=session['grant_ref'],role='parent',iteration=0)
        need(loop['parent_visible']==reviewer_view(result['parent_visible']),'LOOP_PARENT_VIEW_DIFFERS')
    else:
        parent_summary=None
        need(loop['parent_visible'] is None and not loop['iterations'],'NO_ITERATION_WITHOUT_PARENT_CONTROL')
    packet=loop_baseline(meta,session,result,root_read,previous,parent)
    view=packet['snapshot'];baseline=view['nodes'][0]
    calls_limit,wall_limit=loop_limits(loop)
    rows=loop['iterations'];known=result['model_calls'] is not None
    budget={'elapsed_seconds':None,'limit_seconds':wall_limit,'setup_calls':0,
        'diagnosis_calls':sum(1 for r in rows if type(r.get('model_calls')) is int and r['model_calls']>=1) if known else None,
        'proposal_calls':sum(1 for r in rows if type(r.get('model_calls')) is int and r['model_calls']>=2) if known else None,
        'generation_call_limit':calls_limit,'cost':None,'currency':None}
    elapsed=[r.get('elapsed_s') for r in rows]
    if rows and all(type(x) in (int,float) and math.isfinite(x) and x>=0 for x in elapsed):budget['elapsed_seconds']=sum(elapsed)
    state=terminal_state(result,served,issued)
    stage={'success':'Complete','partial':'Partial','interrupted':'Failed','failed':'Failed'}[state]
    run={'id':session['id'],'target_id':name,'stage':stage,'status':result['status'],'blockers':[],'budget':budget,'activity':[]}
    if result['exception_type'] is not None:
        run['blockers']=['Retained '+result['exception_type']+'; this attempt cannot be replayed.']
    at=meta['published_at'];activity=run['activity']
    if parent_summary is not None:
        activity.append({'id':session['id']+':parent','at':at,'stage':'Parent evaluation','status':'evaluated',
            'summary':_correctness(parent_summary)+'; '+str(len(parent_summary['trial_wall_s']))+' protected trial(s).'})
    for row in rows:
        activity.append({'id':session['id']+':iteration:'+str(row['iteration']),'at':at,
            'stage':'Iteration '+str(row['iteration']),'status':str(row.get('outcome') or 'unknown')[:64],
            'summary':(str(row.get('reason') or '') or 'No recorded reason.')[:1024]})
    if issued>served:
        code=evaluator.get('exit_code')
        activity.append({'id':session['id']+':unreported-jobs','at':at,'stage':'Protected evaluation','status':'ERROR_NO_REPLAY',
            'summary':str(issued-served)+' protected job(s) Root issued were not returned to the session'
                +(' (evaluator exit '+str(code)+')' if code not in (None,0) else '')
                +'; original evidence retained, nothing re-executed.'})
    activity.append({'id':session['id']+':terminal','at':at,'stage':stage,'status':result['status'],
        'summary':'Actual '+state+' loop result (stop: '+str(loop.get('stop_reason'))+', '
            +str(loop.get('completed_iterations'))+'/'+str(loop.get('max_iterations'))+' iterations); security campaigns deferred.'})
    view['runs'].append(run)
    node_ids={}
    for row in rows:
        ref=row.get('candidate_ref')
        if ref is None or ref['sha256']==baseline['hash']:continue
        visible=row.get('visible');summary=None
        if visible is not None:
            raw=root_visible(visible,root_read)
            summary=visible_summary_v2(raw,name=name,body_ref=ref,read=root_read,grant_ref=session['grant_ref'],
                role='candidate',iteration=row['iteration'])
        if ref['sha256'] in node_ids:
            continue  # A duplicate proposal is one node; the lineage keeps both iterations.
        node_id='candidate:'+session['id']+':'+ref['sha256']
        child=original(read,ref).decode('utf8');need(len(child.encode())<=256*1024,'PUBLIC_CANDIDATE_EXCEEDS_BOUND')
        node={'id':node_id,'target_id':name,'run_id':session['id'],'parent_id':baseline['id'],'hash':ref['sha256'],
            'label':name+' iteration '+str(row['iteration']),'security_status':'SECURITY_DEFERRED',
            'evaluation_status':'not_evaluated' if summary is None else ('passed' if summary['passed']==summary['total'] else 'failed'),
            'admission_status':'unadmitted','activation_status':'inactive',
            'correctness':None if summary is None else _correctness(summary),
            'speed':None if summary is None else f"{summary['wall_s']:.6f} s protected total; uncalibrated",
            'noise':'Not measured' if not isinstance(loop.get('noise'),dict) else
                'Parent timing noise calibrated over '+str(loop['noise'].get('trials'))+' trial(s)',
            'evidence_refs':[] if summary is None else [visible['result_ref'],*summary['refs']],
            'operator_receipts':[],'admit':_denied(),'activate':_denied()}
        view['nodes'].append(node);node_ids[ref['sha256']]=node_id
        packet['candidates'].append({'node_id':node_id,'candidate_hash':ref['sha256'],'path':meta['mutable_path'],
            'parent_code':parent.decode('utf8'),'candidate_code':child,
            'rationale':row['rationale'][:4096] if isinstance(row.get('rationale'),str) else None,
            'blocker':_denied()['blocker'] if summary is not None else 'Proposal retained without a completed public evaluation.'})
    run['lineage']=project_loop(result,node_ids=node_ids,parent_node_id=baseline['id'])
    return validate_publication(packet,workspace_id=meta['workspace_id'])


def issued_jobs(evaluator_root):
    """Protected jobs Root durably started (its exclusive start claims)."""
    claims=Path(evaluator_root)/'claims'
    if not claims.exists():return 0
    count=0
    for path in sorted(claims.glob('capsule-*.json')):
        item=json.loads(protected(path).read_bytes())
        need(isinstance(item,dict) and item.get('schema')=='ai4r-rsi-whole-capsule-execution-start:1'
             and item.get('job_id')==path.stem,'ROOT_START_CLAIM_DIFFERS')
        count+=1
    return count


def run_terminal(control, result_raw):
    """The runner's own terminal line, when the stopped worker printed one."""
    path=Path(control)/'run-stdout.log'
    if not path.exists():return None
    for line in reversed(protected(path,maximum=16*1024*1024).read_bytes().splitlines()):
        try:item=json.loads(line)
        except (ValueError,UnicodeError):continue
        if isinstance(item,dict) and item.get('schema')=='ai4r-rsi-capsule-run-terminal:1':
            need(item.get('result_sha256')==sha(result_raw),'RUN_TERMINAL_RESULT_DIFFERS')
            return item
    return None


def loop_evidence(cfg, pin, session, result, result_raw, control, evaluator):
    """Reconcile Root execution counts for every loop terminal state."""
    loop=result['loop']
    served=sum(x['executions'] for x in [result['parent_visible'],*[r.get('visible') for r in loop['iterations']]]
               if x is not None)
    issued=issued_jobs(evaluator.root)
    terminal=run_terminal(control,result_raw)
    code=None if terminal is None else terminal.get('evaluator_exit_code')
    if (evaluator.root/'complete.json').exists():
        completion=_read_json(evaluator.root/'complete.json')
        need(completion['schema']=='ai4r-rsi-capsule-evaluator-completion:1' and completion['id']==session['id']
             and completion['configuration_sha256']==pin['sha256'] and completion['grant_ref']==session['grant_ref']
             and completion['status']=='STOPPED' and completion['plan']['grant_sha256']==session['grant_ref']['sha256']
             and completion['executions']==issued,'ROOT_EVALUATOR_TERMINAL_DIFFERS')
        if 'evaluations' in completion:
            reported=sum(row['executions'] for row in completion['evaluations'] if type(row.get('executions')) is int)
            need(served<=reported<=issued,'ROOT_SERVED_EVALUATIONS_DIFFER')
        outcome={'status':'STOPPED','stop':completion.get('stop'),'exit_code':code}
    else:
        failure=_read_json(evaluator.root/'failure.json')
        need(failure['schema']=='ai4r-rsi-capsule-evaluator-failure:1' and failure['id']==session['id']
             and failure['configuration_sha256']==pin['sha256'] and failure['status']=='ERROR_NO_REPLAY'
             and loop['stop_reason']=='error' and code!=0,'RETAINED_EVALUATOR_FAILURE_REQUIRED')
        outcome={'status':'ERROR_NO_REPLAY','stop':failure['exception_type'],'exit_code':code}
    need(served<=issued,'ROOT_TERMINAL_EXECUTION_COUNT_DIFFERS')
    if result['parent_visible'] is None and issued:
        # An interrupted parent: prove zero own Core effects before model work.
        import sqlite3
        core=protected(cfg['composition']['core_root'],12001,directory=True)
        ids=sorted(cfg['composition']['run_contexts'])
        db=sqlite3.connect((core/'state/research.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:
            marks=','.join('?'*len(ids))
            need(all(db.execute('SELECT COUNT(*) FROM '+table+' WHERE run_id IN ('+marks+')',ids).fetchone()[0]==0
                for table in ('model_calls','tool_calls','attempts')),'INTERRUPTED_PARENT_CORE_EFFECT_EXISTS')
        finally:db.close()
    return served,issued,outcome


def worker_terminal_packet(meta, session, run_exit, previous, *, evaluator_state, call_limit, limit_seconds):
    """A stopped worker that left no session result: retained facts only."""
    message=('Worker exited '+str(run_exit['exit_code'])+' without a session result (evaluator: '+evaluator_state
             +'); inspect retained evidence. This attempt cannot replay.')
    failure={'schema':'ai4r-rsi-capsule-controller-failure:1','id':session['id'],'status':'ERROR_NO_REPLAY',
             'exception_type':'WorkerExit'+str(run_exit['exit_code'])}
    packet=controller_failure_packet(meta,session,failure,previous,call_limit=call_limit,limit_seconds=limit_seconds)
    run=packet['snapshot']['runs'][0]
    run['blockers']=[message];run['activity'][0].update(id=session['id']+':worker-terminal',stage='Worker',summary=message)
    return validate_publication(packet,workspace_id=meta['workspace_id'])


def completed_claim(session_id, configuration_sha256, result_raw):
    return {'schema':'ai4r-capsule-completed-publication-claim:1','id':session_id,
            'configuration_sha256':configuration_sha256,'result_sha256':sha(result_raw)}


def publish_worker_terminal(template_path, *, published_at=None):
    """Called by the fixed Root launcher when a known stopped worker left no result."""
    need(os.name=='posix' and os.geteuid()==0,'ROOT_CAPSULE_PUBLISHER_REQUIRED')
    template=_read_json(template_path)
    need(set(template)=={'schema','projection','meta','configuration','control_directory','publication_directory'}
         and template['schema']=='ai4r-capsule-completed-publication:1','CLOSED_COMPLETED_PUBLICATION_TEMPLATE_REQUIRED')
    configure_projection(template['projection'])
    pin=template['configuration'];raw=protected(pin['path']).read_bytes()
    need(sha(raw)==pin['sha256'],'PUBLISHED_RUN_CONFIGURATION_DIFFERS')
    cfg=json.loads(raw);session=cfg['session']
    control=protected(template['control_directory'],directory=True)
    run_exit=_read_json(control/'run-exit.json');container=_read_json(control/'run-container.json')
    need(run_exit['cid']==container['cid'] and container['id']==session['id'] and type(run_exit['exit_code']) is int
         and not os.path.lexists(cfg['result_path']),'KNOWN_RESULTLESS_WORKER_TERMINAL_REQUIRED')
    root=Path(cfg['evaluator']['root'])
    state=('stopped' if (root/'complete.json').exists() else 'failed' if (root/'failure.json').exists() else 'no terminal record')
    calls,wall=session_limits(session)
    meta=dict(template['meta'])
    from datetime import datetime,timezone
    meta['published_at']=published_at or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    directory=_directory(template['publication_directory']);fd=_lock(directory)
    try:
        previous=_read_json(directory/'publication.json')
        packet=worker_terminal_packet(meta,session,run_exit,previous,evaluator_state=state,call_limit=calls,limit_seconds=wall)
        return _replace(directory,merge_publication(previous,packet,meta['published_at']),{
            'schema':'ai4r-capsule-worker-terminal-publication-claim:1','id':session['id'],
            'configuration_sha256':pin['sha256'],'run_exit_sha256':sha(protected(control/'run-exit.json').read_bytes())})
    finally:os.close(fd)


def protected(path, owner=0, *, directory=False, maximum=4*1024*1024):
    path=Path(path)
    need(path.is_absolute() and '..' not in path.parts,'ABSOLUTE_PUBLICATION_PATH_REQUIRED')
    for item in (path,*path.parents):
        m=item.lstat()
        need(not stat.S_ISLNK(m.st_mode) and m.st_uid in {0,owner} and not m.st_mode&0o022,'PROTECTED_PUBLICATION_CUSTODY_REQUIRED')
    m=path.lstat()
    need(m.st_uid==owner and (stat.S_ISDIR(m.st_mode) if directory else stat.S_ISREG(m.st_mode) and m.st_nlink==1 and m.st_size<=maximum),
         'PROTECTED_PUBLICATION_SOURCE_REQUIRED')
    return path


class RootEvidence:
    def __init__(self,root):
        self.root=protected(root,directory=True); self.originals={}
    def __call__(self,pin):
        path=self.root/'captures'/(pin['sha256']+'.json')
        sealed=self.root/'sealed-captures'/(pin['sha256']+'.json')
        # Held-out originals stay in the evaluator's Root-only sealed store;
        # they are joined here for verification and never disclosed.
        if not os.path.lexists(path) and os.path.lexists(sealed):path=sealed
        path=protected(path)
        raw=path.read_bytes(); need(sha(raw)==pin['sha256'],'ROOT_PUBLICATION_CAPTURE_DIFFERS')
        self.originals[str(path)]=sha(raw); return raw


def _read_json(path,owner=0):
    return json.loads(protected(path,owner).read_bytes())


def _directory(value):
    directory=protected(value, directory=True); m=directory.stat()
    need(m.st_gid==10001 and stat.S_IMODE(m.st_mode)==0o750,'ROOT_PUBLIC_DIRECTORY_REQUIRED')
    return directory


def baseline_plan(input_path):
    value=_read_json(input_path)
    need(set(value)=={'schema','projection','publication_directory','expected_previous_sha256','published_at','targets'}
         and value['schema']=='ai4r-capsule-baseline-publication:1' and 1<=len(value['targets'])<=2,
         'CLOSED_BASELINE_PUBLICATION_CONFIGURATION_REQUIRED')
    configure_projection(value['projection'])
    directory=_directory(value['publication_directory']); previous_raw=protected(directory/'publication.json').read_bytes()
    need(sha(previous_raw)==value['expected_previous_sha256'],'PUBLICATION_PREVIOUS_REVISION_DIFFERS')
    packet=json.loads(previous_raw); originals={}
    for target in value['targets']:
        need(set(target)=={'meta','body_path','declaration_path','evaluator_root','result_sha256'},'CLOSED_BASELINE_TARGET_REQUIRED')
        evidence=RootEvidence(target['evaluator_root'])
        body=protected(target['body_path']).read_bytes(); declaration=_read_json(target['declaration_path'])
        result_path=protected(Path(target['evaluator_root'])/'result.json')
        result_raw=result_path.read_bytes(); need(sha(result_raw)==target['result_sha256'],'BASELINE_RESULT_FILE_DIFFERS')
        result=json.loads(result_raw)
        packet=merge_publication(packet,baseline_packet(target['meta'],body,declaration,result,evidence),value['published_at'])
        originals.update(evidence.originals)
        for p in [Path(target['body_path']),Path(target['declaration_path']),result_path]: originals[str(p)]=sha(p.read_bytes())
    facts={'schema':'ai4r-capsule-baseline-publication-plan:1','input_sha256':sha(protected(input_path).read_bytes()),
        'source_sha256':sha(Path(__file__).read_bytes()),'previous_sha256':sha(previous_raw),
        'publication_sha256':sha(encoded(packet)),'originals':originals,'model_calls':0,'qualification':False}
    return value,facts,packet


def _exclusive(path,raw,mode=0o600,gid=0):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    with os.fdopen(fd,'wb') as f:
        os.fchown(f.fileno(),0,gid); os.fchmod(f.fileno(),mode); f.write(raw); f.flush(); os.fsync(f.fileno())
    fd=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def _replace(directory,packet,claim_identity):
    current=protected(directory/'publication.json').read_bytes()
    history=directory/'.capsule-history'; history.mkdir(mode=0o750,exist_ok=True); os.chown(history,0,10001)
    old=history/(sha(current)+'.json')
    if not old.exists():_exclusive(old,current,0o440,10001)
    else:need(protected(old).read_bytes()==current,'PUBLICATION_HISTORY_DIFFERS')
    claims=directory/'.capsule-claims'; claims.mkdir(mode=0o700,exist_ok=True)
    _exclusive(claims/(sha(encoded(claim_identity))+'.json'),encoded(claim_identity))
    raw=encoded(packet); temporary=directory/('.capsule-'+sha(raw)+'.pending')
    _exclusive(temporary,raw,0o440,10001); os.replace(temporary,directory/'publication.json')
    fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return {'publication_sha256':sha(raw),'model_calls':0,'qualification':False}


def _lock(directory):
    import fcntl
    lock=directory/'.capsule-publication.lock'
    fd=os.open(lock,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    m=os.fstat(fd); need(stat.S_ISREG(m.st_mode) and m.st_uid==0 and m.st_nlink==1 and not m.st_mode&0o077,'PUBLICATION_LOCK_CUSTODY_DIFFERS')
    fcntl.flock(fd,fcntl.LOCK_EX); return fd


def publish_baselines(input_path,reviewed):
    value,facts,packet=baseline_plan(input_path); need(sha(encoded(facts))==reviewed,'REVIEWED_BASELINE_PUBLICATION_REQUIRED')
    directory=_directory(value['publication_directory']); fd=_lock(directory)
    try:
        repeated=baseline_plan(input_path); need(repeated[1]==facts,'BASELINE_PLAN_CHANGED_BEFORE_PUBLICATION')
        return _replace(directory,packet,{'schema':'ai4r-capsule-baseline-publication-claim:1','plan_sha256':reviewed})
    finally:os.close(fd)


def publish_completed(template_path, *, published_at=None):
    """Called only by the fixed Root launcher after a known stopped worker."""
    need(os.name=='posix' and os.geteuid()==0,'ROOT_CAPSULE_PUBLISHER_REQUIRED')
    template=_read_json(template_path)
    need(set(template)=={'schema','projection','meta','configuration','control_directory','publication_directory'}
         and template['schema']=='ai4r-capsule-completed-publication:1','CLOSED_COMPLETED_PUBLICATION_TEMPLATE_REQUIRED')
    configure_projection(template['projection'])
    pin=template['configuration']; configuration_raw=protected(pin['path']).read_bytes()
    need(sha(configuration_raw)==pin['sha256'],'PUBLISHED_RUN_CONFIGURATION_DIFFERS')
    cfg=json.loads(configuration_raw);session=cfg['session']
    control=protected(template['control_directory'],directory=True)
    run_exit=_read_json(control/'run-exit.json'); container=_read_json(control/'run-container.json')
    need(run_exit['cid']==container['cid'] and container['id']==session['id']
         and type(run_exit['exit_code']) is int,'KNOWN_WORKER_TERMINAL_REQUIRED')
    evaluator=RootEvidence(cfg['evaluator']['root'])
    # A loop session's evaluator may instead have retained its failure record
    # (partial run); ``loop_evidence`` joins either. Legacy always completes.
    completion=None
    if 'loop' not in session or (evaluator.root/'complete.json').exists():
        completion=_read_json(evaluator.root/'complete.json')
        need(completion['schema']=='ai4r-rsi-capsule-evaluator-completion:1' and completion['id']==session['id']
             and completion['configuration_sha256']==pin['sha256'] and completion['grant_ref']==session['grant_ref']
             and completion['status']=='STOPPED','ROOT_EVALUATOR_TERMINAL_DIFFERS')
    owner=_read_json(evaluator.root/'owner.json')
    need(owner['schema']=='ai4r-rsi-capsule-evaluator-owner:1' and owner['id']==session['id']
         and owner['configuration_sha256']==pin['sha256'] and owner['uid']==owner['gid']==0 and owner['groups']==[]
         and type(owner['pid']) is int and owner['pid']>0 and type(owner['start_ticks']) is int and owner['start_ticks']>0,
         'ROOT_EVALUATOR_OWNER_DIFFERS')
    result_path=protected(cfg['result_path'],12001)
    result=json.loads(result_path.read_bytes())
    if result.get('schema')=='ai4r-rsi-capsule-controller-terminal:1':
        need(result['id']==session['id'] and result['configuration_sha256']==pin['sha256']
             and result['status']=='ERROR_NO_REPLAY','EXACT_CONTROLLER_TERMINAL_REQUIRED')
        failure_raw=protected(Path(cfg['composition']['record_root'])/'controller-failure.json',12001).read_bytes()
        need(sha(failure_raw)==result['controller_failure_sha256'],'CONTROLLER_FAILURE_BYTES_DIFFER')
        failure=json.loads(failure_raw)
        need(failure['configuration_sha256']==pin['sha256'] and failure['phase']==result['phase'],
             'CONTROLLER_FAILURE_CONFIGURATION_DIFFERS')
        if result['model_calls']==0:
            need(result['phase'] in ('WAITING_FOR_EVALUATOR','COMPOSING') and completion is not None
                 and completion['executions']==0 and completion['completed_roles']==[],
                 'EARLY_CONTROLLER_ZERO_EFFECT_PROOF_REQUIRED')
        meta=dict(template['meta'])
        from datetime import datetime,timezone
        meta['published_at']=published_at or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        directory=_directory(template['publication_directory']);fd=_lock(directory)
        try:
            previous=_read_json(directory/'publication.json')
            calls,wall=session_limits(session)
            packet=controller_failure_packet(meta,session,failure,previous,model_calls=result['model_calls'],
                                             call_limit=calls,limit_seconds=wall)
            return _replace(directory,merge_publication(previous,packet,meta['published_at']),{
                'schema':'ai4r-capsule-controller-failure-publication-claim:1','id':session['id'],
                'configuration_sha256':pin['sha256'],'terminal_sha256':sha(result_path.read_bytes())})
        finally:os.close(fd)
    records=protected(cfg['composition']['record_root'],12001,directory=True)
    core=protected(cfg['composition']['core_root'],12001,directory=True)
    def read(ref):
        for p in [records/(ref['sha256']+'.json'),core/'artifacts/sha256'/ref['sha256'][:2]/ref['sha256']]:
            if p.exists():return protected(p,12001).read_bytes()
        raise ValueError('ACTUAL_SESSION_PUBLIC_ORIGINAL_ABSENT')
    need(captured(read,result['result_ref'])=={k:v for k,v in result.items() if k!='result_ref'},'SESSION_RESULT_CAPTURE_DIFFERS')
    if result.get('loop') is not None:
        return _publish_loop(template,pin,cfg,session,result,result_path,read,evaluator,control,published_at)
    expected_executions=sum(x['executions'] for x in [result['parent_visible'],result['candidate_visible']] if x is not None)
    interrupted=None
    if completion['executions']!=expected_executions:
        roots=[]
        for path in (evaluator.root/'captures').glob('*.json'):
            raw=protected(path).read_bytes()
            try:item=json.loads(raw)
            except (ValueError,UnicodeError):continue
            if isinstance(item,dict) and item.get('schema')=='ai4r-rsi-whole-capsule-visible-result:1':
                need(sha(raw)==path.stem,'ROOT_CAPTURE_FILENAME_DIFFERS')
                roots.append(dict(item,result_ref={'id':path.name,'sha256':path.stem}))
        interrupted=interrupted_parent_summary(session,result,completion,roots,evaluator)
        import sqlite3
        db=sqlite3.connect((core/'state/research.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:
            ids=list(cfg['composition']['run_contexts'])
            need(len(ids)==2 and all(db.execute('SELECT COUNT(*) FROM '+table+' WHERE run_id IN (?,?)',ids).fetchone()[0]==0
                for table in ('model_calls','tool_calls','attempts')), 'INTERRUPTED_PARENT_CORE_EFFECT_EXISTS')
        finally:db.close()
    need((interrupted is not None or completion['executions']==expected_executions)
         and completion['plan']['grant_sha256']==session['grant_ref']['sha256'], 'ROOT_TERMINAL_EXECUTION_COUNT_DIFFERS')
    meta=dict(template['meta'])
    from datetime import datetime,timezone
    meta['published_at']=published_at or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    directory=_directory(template['publication_directory']);fd=_lock(directory)
    try:
        previous=_read_json(directory/'publication.json')
        packet=session_packet(meta,session,result,read,evaluator,previous=previous)
        if interrupted is not None:
            run=packet['snapshot']['runs'][0]
            run['budget'].update(diagnosis_calls=0,proposal_calls=0)
            run['activity'].append({'id':session['id']+':interrupted-parent','at':meta['published_at'],
                'stage':'Parent evaluation','status':'ERROR_NO_REPLAY',
                'summary':str(interrupted['executions'])+' protected parent job(s) stopped before model work; original evidence retained.'})
        output=merge_publication(previous,packet,meta['published_at'])
        return _replace(directory,output,completed_claim(session['id'],pin['sha256'],result_path.read_bytes()))
    finally:os.close(fd)


def _publish_loop(template,pin,cfg,session,result,result_path,read,evaluator,control,published_at):
    result_raw=result_path.read_bytes()
    served,issued,outcome=loop_evidence(cfg,pin,session,result,result_raw,control,evaluator)
    meta=dict(template['meta'])
    from datetime import datetime,timezone
    meta['published_at']=published_at or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    directory=_directory(template['publication_directory']);fd=_lock(directory)
    try:
        previous=_read_json(directory/'publication.json')
        packet=loop_session_packet(meta,session,result,read,evaluator,previous,served=served,issued=issued,evaluator=outcome)
        output=merge_publication(previous,packet,meta['published_at'])
        return _replace(directory,output,completed_claim(session['id'],pin['sha256'],result_raw))
    finally:os.close(fd)


NO_EFFECT_OBSERVATION_FIELDS=frozenset(('schema run_id configuration observed_unix_s container core native_lease_rows '
    'relay_ledger_sha256 benchmark_ledger_sha256 evaluator_completion controller_failure run_exit '
    'accepted_claim accepted_ack launcher_exit execution_jobs all_job_groups_empty job_group_count '
    'model_calls tool_calls attempt_starts no_replay_authority').split())


def startup_failure_plan(input_path):
    """Reconcile a retained legacy startup failure, with no result invented."""
    value=_read_json(input_path)
    fields={'schema','projection','meta','configuration','control_directory','publication_directory',
         'expected_previous_sha256','controller_failure_sha256','evaluator_completion_sha256','run_exit_sha256'}
    need(set(value) in (fields,fields|{'no_effect_observation'})
         and value['schema']=='ai4r-capsule-startup-failure-publication:1',
         'CLOSED_STARTUP_FAILURE_PUBLICATION_INPUT_REQUIRED')
    configure_projection(value['projection'])
    pin=value['configuration'];need(set(pin)=={'path','sha256'},'CLOSED_STARTUP_CONFIGURATION_PIN_REQUIRED')
    cfg_raw=protected(pin['path']).read_bytes();need(sha(cfg_raw)==pin['sha256'],'STARTUP_CONFIGURATION_BYTES_DIFFER')
    cfg=json.loads(cfg_raw);session=cfg['session'];control=protected(value['control_directory'],directory=True)
    originals={str(pin['path']):sha(cfg_raw)}
    def proof(path,owner=0):
        raw=protected(path,owner).read_bytes();originals[str(path)]=sha(raw);return json.loads(raw)
    run_exit=proof(control/'run-exit.json');container=proof(control/'run-container.json')
    need(originals[str(control/'run-exit.json')]==value['run_exit_sha256']
         and run_exit['cid']==container['cid'] and container['id']==session['id']
         and type(run_exit['exit_code']) is int and run_exit['exit_code']!=0,
         'KNOWN_FAILED_STARTUP_WORKER_REQUIRED')
    evaluator=Path(cfg['evaluator']['root']);completion=proof(evaluator/'complete.json')
    need(originals[str(evaluator/'complete.json')]==value['evaluator_completion_sha256']
         and completion['schema']=='ai4r-rsi-capsule-evaluator-completion:1'
         and completion['id']==session['id'] and completion['configuration_sha256']==pin['sha256']
         and completion['grant_ref']==session['grant_ref'] and completion['status']=='STOPPED'
         and completion['executions']==0 and completion['completed_roles']==[],
         'STOPPED_ZERO_EXECUTION_STARTUP_EVALUATOR_REQUIRED')
    owner=proof(evaluator/'owner.json')
    need(owner['schema']=='ai4r-rsi-capsule-evaluator-owner:1' and owner['id']==session['id']
         and owner['configuration_sha256']==pin['sha256'] and owner['uid']==owner['gid']==0
         and owner['groups']==[], 'ACTUAL_ROOT_STARTUP_EVALUATOR_OWNER_REQUIRED')
    claim=proof(Path(cfg['claim_path']))
    need(claim['schema']=='ai4r-rsi-capsule-run-claim:1' and claim['id']==session['id']
         and claim['configuration_sha256']==pin['sha256'],'ACTUAL_STARTUP_CLAIM_REQUIRED')
    failure_path=Path(cfg['composition']['record_root'])/'controller-failure.json'
    failure=proof(failure_path,12001)
    need(originals[str(failure_path)]==value['controller_failure_sha256'], 'ACTUAL_STARTUP_FAILURE_BYTES_DIFFER')
    need(not Path(cfg['result_path']).exists(),'STARTUP_REPAIR_MUST_NOT_REPLACE_EXISTING_RESULT')
    directory=_directory(value['publication_directory']);previous_raw=protected(directory/'publication.json').read_bytes()
    need(sha(previous_raw)==value['expected_previous_sha256'],'STARTUP_PUBLICATION_PREVIOUS_REVISION_DIFFERS')
    model_calls=None
    if 'no_effect_observation' in value:
        observation_pin=value['no_effect_observation']
        need(set(observation_pin)=={'path','sha256'},'CLOSED_NO_EFFECT_OBSERVATION_PIN_REQUIRED')
        observation=proof(Path(observation_pin['path']))
        need(originals[observation_pin['path']]==observation_pin['sha256'],'NO_EFFECT_OBSERVATION_BYTES_DIFFER')
        need(set(observation)==NO_EFFECT_OBSERVATION_FIELDS and observation['schema']=='ai4r-capsule-no-effect-observation:1'
             and observation['run_id']==session['id'] and observation['configuration']==pin,
             'EXACT_ROOT_NO_EFFECT_OBSERVATION_REQUIRED')
        actual_container=observation['container']
        need(set(actual_container)=={'id','image','running','pid','exit_code'}
             and actual_container['id']==container['cid'] and actual_container['image']==container['image']
             and actual_container['running'] is False and actual_container['pid']==0
             and actual_container['exit_code']==run_exit['exit_code'], 'STOPPED_NO_EFFECT_CONTAINER_REQUIRED')
        for key in ('model_calls','tool_calls','attempt_starts','execution_jobs','native_lease_rows'):
            need(type(observation[key]) is int and observation[key]==0,'ZERO_OWN_EFFECT_OBSERVATION_REQUIRED')
        need(observation['all_job_groups_empty'] is True and observation['job_group_count']==1
             and observation['no_replay_authority'] is True,'EMPTY_NO_REPLAY_OBSERVATION_REQUIRED')
        for key,path in [('evaluator_completion',evaluator/'complete.json'),('controller_failure',failure_path),
                         ('run_exit',control/'run-exit.json')]:
            need(observation[key]=={'path':str(path),'sha256':originals[str(path)]},'NO_EFFECT_ORIGINAL_PROOF_DIFFERS')
        for key in ('relay_ledger_sha256','benchmark_ledger_sha256'):
            need(isinstance(observation[key],str) and len(observation[key])==64
                 and all(c in '0123456789abcdef' for c in observation[key]),'ORIGINAL_EFFECT_LEDGER_DIGEST_REQUIRED')
        journal={}
        for key in ('accepted_claim','accepted_ack','launcher_exit'):
            record_pin=observation[key];need(set(record_pin)=={'path','sha256'},'CLOSED_ACCEPTED_EFFECT_PIN_REQUIRED')
            journal[key]=proof(Path(record_pin['path']))
            need(originals[record_pin['path']]==record_pin['sha256'],'ACCEPTED_EFFECT_ORIGINAL_DIFFERS')
        identity=journal['accepted_claim']['identity'];ack=journal['accepted_ack']
        need(identity['target_id']==ack['target_id']==session['capsule_name'] and ack['run_id']==session['id']
             and all(identity[k]==ack[k] for k in ('revision','client_request_id'))
             and ack['status']=='ACCEPTED_UNQUALIFIED'
             and os.waitstatus_to_exitcode(journal['launcher_exit']['wait_status'])==run_exit['exit_code'],
             'EXACT_ACCEPTED_FAILED_RUN_REQUIRED')
        core=observation['core']
        own_ids=sorted(cfg['composition']['run_contexts'])
        need(set(core)=={'root','own_run_ids','own_counts','global_tables'}
             and core['root']==cfg['composition']['core_root'] and sorted(core['own_run_ids'])==own_ids
             and core['own_counts']=={'model_calls':0,'tool_calls':0,'attempts':0},
             'EXACT_OWN_CORE_NO_EFFECT_OBSERVATION_REQUIRED')
        import sqlite3
        database=protected(Path(core['root'])/'state/research.sqlite3',12001,maximum=256*1024*1024)
        db=sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
        try:
            for table in ('model_calls','tool_calls','attempts'):
                rows=db.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall()
                actual={'count':len(rows),'rows_sha256':sha(repr([tuple(row) for row in rows]).encode())}
                need(actual==core['global_tables'][table]
                     and not any(dict(row).get('run_id') in own_ids for row in rows),
                     'ACTUAL_CORE_CHANGED_SINCE_NO_EFFECT_OBSERVATION')
        finally:db.close()
        model_calls=0
    packet=controller_failure_packet(value['meta'],session,failure,json.loads(previous_raw),model_calls=model_calls)
    packet=merge_publication(json.loads(previous_raw),packet,value['meta']['published_at'])
    facts={'schema':'ai4r-capsule-startup-failure-publication-plan:1','input_sha256':sha(protected(input_path).read_bytes()),
        'source_sha256':sha(Path(__file__).read_bytes()),'configuration_sha256':pin['sha256'],
        'failure_sha256':value['controller_failure_sha256'],'originals':originals,'previous_sha256':sha(previous_raw),
        'publication_sha256':sha(encoded(packet)),'id':session['id'],'model_calls':model_calls,'publication_model_calls':0,
        'code_jobs':0,'qualification':False,'reexecuted':False}
    return value,facts,packet


def publish_startup_failure(input_path,reviewed):
    value,facts,packet=startup_failure_plan(input_path)
    need(sha(encoded(facts))==reviewed,'REVIEWED_STARTUP_FAILURE_PLAN_REQUIRED')
    directory=_directory(value['publication_directory']);fd=_lock(directory)
    try:
        need(startup_failure_plan(input_path)[1]==facts,'STARTUP_FAILURE_PROOFS_CHANGED')
        return _replace(directory,packet,{'schema':'ai4r-capsule-startup-failure-repair-claim:1',
            'id':facts['id'],'plan_sha256':reviewed})
    finally:os.close(fd)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('operation',choices=['baseline-plan','baseline-publish','completed-publish','startup-failure-plan','startup-failure-publish'])
    parser.add_argument('--input',required=True);parser.add_argument('--review-sha256')
    args=parser.parse_args();need(os.name=='posix' and os.geteuid()==0,'ROOT_CAPSULE_PUBLISHER_REQUIRED')
    result=(startup_failure_plan(args.input)[1] if args.operation=='startup-failure-plan' else
        publish_startup_failure(args.input,args.review_sha256) if args.operation=='startup-failure-publish' else
        baseline_plan(args.input)[1] if args.operation=='baseline-plan' else
        publish_baselines(args.input,args.review_sha256) if args.operation=='baseline-publish' else publish_completed(args.input))
    print(json.dumps(result,sort_keys=True))
