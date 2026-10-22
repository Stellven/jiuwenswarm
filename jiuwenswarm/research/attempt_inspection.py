"""IF003r3 finite original whole-attempt evidence; never execution authority."""
from __future__ import annotations

import copy
import json
import math
import sqlite3
from datetime import datetime

from .binding import ContractFactory, committed_output_proof, validate_child_authority
from .contracts import ResearchError, contract_schema, validate
from .evaluation_projection import require
from .gate import assemble_assessment, zip_projection
from .measurement import all_mandatory_pass


def _original(store, ref, kind, contract=None, *, scope=None):
    validate('Ref', ref)
    with store._lock:
        row = store.connection.execute('SELECT kind,run_id,node_id,attempt_id FROM records WHERE id=?', (ref['id'],)).fetchone()
    require(row is not None and row['kind'] == kind, 'Original indexed evidence kind differs', 'integrity_fault')
    if scope is not None:
        require(all(row[key] == value for key, value in scope.items()), 'Original indexed evidence scope differs', 'integrity_fault')
    body = store.read_record(ref, **({'contract_id': contract} if contract else {}))
    require(type(body) is dict, 'Original evidence body is not a record', 'integrity_fault')
    return body


def _rows(store, run_id, node_id, kind):
    with store._lock:
        rows = store.connection.execute('SELECT id FROM records WHERE run_id=? AND node_id=? AND kind=? ORDER BY rowid',
            (run_id, node_id, kind)).fetchall()
    return [(store.record_ref(row['id']), _original(store, store.record_ref(row['id']), kind)) for row in rows]


def _order(store, ref):
    with store._lock:
        row=store.connection.execute('SELECT rowid FROM records WHERE id=?',(ref['id'],)).fetchone()
    require(row is not None,'Original indexed publication is missing','integrity_fault')
    store.read_blob(ref)
    return row['rowid']


def _declaration(store, ref, admission_ref, snapshot):
    admission=_original(store,admission_ref,'library-admission','library-admission')
    require(admission['status'] == 'admitted' and admission['candidate_ref'] == ref
        and admission['cc']['declaration_sha256'] == ref['sha256']
        and any(all(entry[key] == value for key,value in admission['cc'].items()) for entry in snapshot['entries']),
        'Declaration has no exact original captured admission/snapshot','integrity_fault')
    with store._lock:
        row=store.connection.execute('SELECT kind FROM records WHERE id=?',(ref['id'],)).fetchone()
    require(row is None or row['kind'] == 'capsule-declaration','Admitted declaration has a foreign indexed kind','integrity_fault')
    declaration=store.read_record(ref,contract_id='capsule-declaration');identity=declaration['identity']
    require(admission['cc'] == {'cc_name':identity['name'],'cc_version':identity['version_label'],'declaration_sha256':ref['sha256']},
        'Admitted declaration body differs from original candidate pin','integrity_fault')
    return declaration,admission


def _child(store, ref, parent_ref, parent, snapshot):
    scope = {key: parent[key] for key in ('run_id','node_id','attempt_id')}
    child = _original(store, ref, 'subnode-execution-contract', 'subnode-execution-contract', scope=scope)
    assignments = [row for row in parent['subnodes'] if row['subnode_id'] == child['subnode_id']]
    require(len(assignments) == 1 and len(child['bindings']) == 1 and child['node_contract_ref'] == parent_ref
        and all(child[key] == parent[key] for key in ('run_id','node_id','attempt_id','revision','policy_ref','configuration_ref')),
        'Original child is outside the exact parent attempt', 'integrity_fault')
    assignment, binding = assignments[0], child['bindings'][0]
    template = _original(store, assignment['template_ref'], 'subnode-template')
    require(binding['admission_ref'] == template['admission_ref'] and assignment['capsule_ref'] == binding['declaration_ref'] == template['capsule_ref'],
        'Original declaration/template admission association differs','integrity_fault')
    declaration,admission=_declaration(store,assignment['capsule_ref'],binding['admission_ref'],snapshot)
    identity = declaration['identity']; pin = {'cc_name':identity['name'], 'cc_version':identity['version_label'],
        'declaration_sha256':assignment['capsule_ref']['sha256']}
    require(child['template_ref'] == assignment['template_ref'] and template['subnode_id'] == child['subnode_id']
        and template['role'] == binding['role'] == assignment['role'] and template['capsule_ref'] == binding['declaration_ref'] == assignment['capsule_ref']
        and template['cc'] == admission['cc'] == pin and admission['status'] == 'admitted'
        and admission['candidate_ref'] == assignment['capsule_ref'] and binding['admission_ref'] == template['admission_ref']
        and template['ports'] == declaration['ports'] and any(all(entry[key] == value for key,value in pin.items()) for entry in snapshot['entries']),
        'Original child/template/admission/snapshot identity differs', 'integrity_fault')
    implementations = [template['body_refs'][body['path']] for body in identity['body']]
    pins = [pin for row in declaration['needs']['external'] for key in ('pin','lockfile') if (pin := row.get(key))]
    dependencies = [template['body_refs'][pin['ref']] for pin in pins]
    require(binding['implementation_refs'] == implementations and binding['dependency_refs'] == dependencies
        and all(ref['sha256'] == body['sha256'] for ref,body in zip(implementations,identity['body']))
        and all(ref['sha256'] == pin['sha256'] for ref,pin in zip(dependencies,pins)),
        'Original child body/dependency closure differs', 'integrity_fault')
    for pin in [*implementations,*dependencies]: store.read_blob(pin)
    outputs = [{'name':port['name'],'contract_id':port['schema_ref'],'version':ContractFactory._version(port['schema_ref']),
        'required':port['required']} for port in declaration['ports']['outputs']]
    require(child['outputs'] == outputs and child['required_outputs'] == [port['name'] for port in outputs if port['required']]
        and child['input_refs'] == [pin for port in child['inputs'] for pin in port['artifact_refs']]
        and child['checking_profile_ref'] == template['checking_profile_ref'], 'Original child ports/checking profile differ', 'integrity_fault')
    per = declaration['budget']['per_call']
    calls = per['invocations'] if any(row['service_key'] == 'audited_model_bridge' for row in declaration['needs']['injects']) else 0
    caps = {'time_s':min(per['wall_s'],parent['node_limits']['time_s']), 'model_calls':min(calls,parent['node_limits']['model_calls']),
        'memory_mb':min(admission['memory_mb'],parent['node_limits']['memory_mb'])}
    if assignment['role'] == 'verifier':
        profile = _original(store, template['checking_profile_ref'], 'checking-profile', 'checking-profile')
        caps['time_s'] = min(caps['time_s'],profile['time_s']);caps['model_calls'] = min(caps['model_calls'],profile['model_call_limit'],1)
    require(binding['limits'] == child['subnode_limits'] and all(child['subnode_limits'][key] <= value for key,value in caps.items()),
        'Original child limits exceed frozen declaration/admission', 'integrity_fault')
    validate_child_authority(store,parent_ref,child['subnode_id'],child['inputs'],effective_authority=binding['effective_authority'])
    return child, template, declaration


def _plan(store, ref, child_ref, child, template):
    scope = {key:child[key] for key in ('run_id','node_id','attempt_id')}
    plan = _original(store,ref,'bound-check-plan','bound-check-plan',scope=scope)
    bundle = _original(store,template['check_bundle_ref'],'check-bundle','check-bundle')
    profile = _original(store,template['checking_profile_ref'],'checking-profile','checking-profile')
    runners = list({pin['sha256']:pin for pin in [template['check_bundle_ref'],*[row['runner_ref'] for row in bundle['checks']]]}.values())
    mandatory = list(dict.fromkeys([*[row['check_id'] for row in bundle['checks'] if row['blocking']],
        'host_contract','host_identity','host_limits','host_authority']))
    require(plan['contract_ref'] == child_ref and plan['node_contract_ref'] == child['node_contract_ref']
        and plan['subnode_id'] == child['subnode_id'] and plan['input_refs'] == child['input_refs']
        and plan['profile_ref'] == child['checking_profile_ref'] and plan['policy_ref'] == child['policy_ref']
        and plan['mandatory_deterministic'] == mandatory and plan['mandatory_semantic'] == [row['criterion_id'] for row in profile['criteria'] if row['blocking']]
        and plan['runner_refs'] == runners, 'Original child checking plan differs', 'integrity_fault')
    for pin in runners: store.read_blob(pin)
    return plan,profile


def _observation(store, ref, child_ref, child):
    observed = _original(store,ref,'invocation-observation','invocation-observation',scope={key:child[key] for key in ('run_id','node_id','attempt_id')})
    require(observed['contract_ref'] == child_ref and observed['node_contract_ref'] == child['node_contract_ref']
        and all(observed[key] == child[key] for key in ('run_id','node_id','subnode_id','attempt_id','input_refs')),
        'Original invocation observation differs from child', 'integrity_fault')
    for pin in observed['output_refs']:store.read_blob(pin)
    return observed


def _internal(store, ref, parent_ref, parent, snapshot, frozen_node, children):
    scope = {key:parent[key] for key in ('run_id','node_id','attempt_id')}
    gate = _original(store,ref,'gate-decision','gate-decision',scope=scope)
    require(gate['scope_kind'] == 'subnode' and gate['node_contract_ref'] == parent_ref and gate['subnode_id']
        and all(gate[key] == parent[key] for key in scope), 'Original internal Gate has another attempt', 'integrity_fault')
    child_ref = gate['contract_ref']; child,template,declaration = _child(store,child_ref,parent_ref,parent,snapshot)
    require(child['bindings'][0]['role'] == 'work' and child['subnode_id'] == gate['subnode_id']
        and gate['policy_ref'] == child['policy_ref'] and gate['input_refs'] == child['input_refs'], 'Internal Gate does not target exact work', 'integrity_fault')
    require(template['cc'] == frozen_node['cc'] and template['check_bundle_ref']['sha256'] == frozen_node['check_pins']['check_bundle_sha256']
        and template['checking_profile_ref']['sha256'] == frozen_node['check_pins']['checking_profile_sha256'],
        'Work checking pins differ from frozen RunPlan', 'integrity_fault')
    plan,profile = _plan(store,gate['check_plan_ref'],child_ref,child,template)
    checked = _original(store,gate['deterministic_result_ref'],'deterministic-check-result','deterministic-check-result',scope=scope)
    require(checked['check_plan_ref'] == gate['check_plan_ref'] and (gate['output_port'] is None
        or gate['output_port'] in {port['name'] for port in child['outputs']} and len(gate['output_refs']) == 1)
        and gate['invocation_refs'], 'Internal Gate/check/output inventory differs', 'integrity_fault')
    observations = [(pin,_original(store,pin,'invocation-observation','invocation-observation',scope=scope)) for pin in gate['invocation_refs']]
    workers = [item for item in observations if item[1]['contract_ref'] == child_ref]
    require(len(workers) == 1, 'Internal Gate has no unique original worker observation', 'integrity_fault')
    worker_ref,worker = workers[0];_observation(store,worker_ref,child_ref,child);children[child['subnode_id']] = (child_ref,child,worker_ref)
    if gate['output_port'] is None:
        require(gate['action'] == 'halt' and gate['assessment_ref'] is None and len(observations) == 1
            and gate['output_refs'] == worker['output_refs'], 'Suppressed-review Gate differs from actual original work', 'integrity_fault')
    subjects = checked.get('subject_refs',[checked['subject_ref']])
    require(subjects == worker['output_refs'] or not worker['output_refs'] and subjects == [worker_ref], 'Work checks target another original output', 'integrity_fault')
    if gate['assessment_ref'] is not None:
        assessment = _original(store,gate['assessment_ref'],'verifier-assessment','verifier-assessment')
        review = _original(store,assessment['review_context_ref'],'review-context','review-context')
        require(gate['output_refs'] and review['subject_ref'] == gate['output_refs'][0] and review['contract_ref'] == child_ref
            and review['node_contract_ref'] == parent_ref and review['check_plan_ref'] == gate['check_plan_ref']
            and review['deterministic_result_ref'] == gate['deterministic_result_ref'] and worker_ref in review['observations'],
            'Assessment context does not join its original work', 'integrity_fault')
        if assessment['subject_ref'] != gate['output_refs'][0]:
            require(store.read_blob(assessment['subject_ref']) == zip_projection(store.read_blob(gate['output_refs'][0])), 'Assessment subject bytes differ', 'integrity_fault')
        body={key:assessment[key] for key in ('uncertainties','limitations','required_correction')}
        body['findings']=[{key:item[key] for key in ('criterion_id','outcome','reason')} for item in assessment['findings']]
        criteria=[row for row in profile['criteria'] if row['target_port'] in (None,gate['output_port'])]
        require(assemble_assessment(body,criteria,child['bindings'][0]['declaration_ref'],assessment['subject_ref'],assessment['review_context_ref']) == assessment,
            'Assessment does not follow exact original profile', 'integrity_fault')
    for observed_ref,observed in observations:
        if observed['contract_ref'] == child_ref:continue
        reviewer_ref=observed['contract_ref'];reviewer,vtemplate,_ = _child(store,reviewer_ref,parent_ref,parent,snapshot)
        require(reviewer['bindings'][0]['role'] == 'verifier' and vtemplate['subject_subnode_id'] == child['subnode_id']
            and vtemplate['output_port'] == gate['output_port'], 'Original verifier is not assigned to this output', 'integrity_fault')
        _observation(store,observed_ref,reviewer_ref,reviewer)
        children[reviewer['subnode_id']] = (reviewer_ref,reviewer,observed_ref)
        plans=[(pin,value) for pin,value in _rows(store,parent['run_id'],parent['node_id'],'bound-check-plan') if value.get('contract_ref') == reviewer_ref]
        require(len(plans) == 1, 'Reviewer has no unique original checking plan', 'integrity_fault')
        plan_ref,vplan=plans[0];_plan(store,plan_ref,reviewer_ref,reviewer,vtemplate)
        checks=[(pin,value) for pin,value in _rows(store,parent['run_id'],parent['node_id'],'deterministic-check-result') if value.get('check_plan_ref') == plan_ref]
        require(len(checks) == 1, 'Reviewer has no unique original mechanical result', 'integrity_fault')
        checked_ref,vchecked=checks[0];_original(store,checked_ref,'deterministic-check-result','deterministic-check-result',scope=scope)
        require(vchecked['subject_ref'] == (gate['assessment_ref'] or observed_ref), 'Reviewer checks target another subject', 'integrity_fault')
        if gate['action'] == 'advance':
            require(gate['assessment_ref'] in observed['output_refs'] and all_mandatory_pass(vplan,vchecked['results']), 'Advancing review lacks valid mechanical proof', 'integrity_fault')
    if gate['action'] == 'advance':
        require(all_mandatory_pass(plan,checked['results']) and gate['assessment_ref'] is not None
            and gate['verdict'] in {'PASS','PASS_WITH_KNOWN_LIMITATIONS'} and gate['accepted_refs'] == gate['output_refs']
            and len(observations) == 2, 'Advancing output lacks independent original closure', 'integrity_fault')
    else:require(not gate['accepted_refs'], 'Halting output claims acceptance', 'integrity_fault')
    return gate


def validate_prestart_failure(store, parent_ref, parent, dispatch_ref, dispatch):
    """Read an original zero-worker failure, never start/cessation authority.

    The Scheduler's observed failed-processing interval is not a worker start.
    Prepared contracts/check plans and partial native receipts may exist, but
    actual invocation, model, output, check, Gate and commit evidence may not.
    """
    scope={key:parent[key] for key in ('run_id','node_id','attempt_id')}
    require(_original(store,dispatch_ref,'dispatch-record','dispatch-record',scope=scope) == dispatch
        and dispatch['schema_version'] == '2.0.0'
        # Runner.put_record preserves the body's ID inside a content-addressed
        # capture. _original above independently verifies its bytes/kind/scope.
        and (dispatch['id'] == dispatch_ref['id'] or dispatch_ref['id'] == 'blob:' + dispatch_ref['sha256'])
        and dispatch['node_contract_ref'] == parent_ref
        and all(dispatch[key] == parent[key] for key in scope)
        and dispatch['bound_input_refs'] == [{'name':port['name'],'ref':pin} for port in parent['inputs'] for pin in port['artifact_refs']]
        and dispatch['outcome'] in {'failed','budget_exhausted','interrupted'}
        and dispatch['gate_decision_ref'] is None and dispatch['output_gate_decision_refs'] == []
        and dispatch['output_refs'] == [] and dispatch['model_calls_used'] is None,
        'Pre-start failure does not retain its exact source-null closure','integrity_fault')
    require(dispatch['started_at'] is not None,'Failed Scheduler processing interval is unavailable','integrity_fault')
    began=datetime.fromisoformat(dispatch['started_at'].replace('Z','+00:00'))
    if dispatch['outcome'] == 'interrupted':
        require(dispatch['ended_at'] is None,'Interrupted pre-start failure claims a finished end','integrity_fault')
    else:
        require(dispatch['ended_at'] is not None
            and datetime.fromisoformat(dispatch['ended_at'].replace('Z','+00:00')) >= began,
            'Failed Scheduler processing chronology differs','integrity_fault')
    elapsed=dispatch['elapsed_s']
    require(elapsed is None or type(elapsed) in (int,float) and math.isfinite(elapsed) and elapsed >= 0,
        'Failed Scheduler elapsed observation is malformed','integrity_fault')
    plan_ref=dispatch['check_plan_ref']
    plan=_original(store,plan_ref,'bound-check-plan','bound-check-plan',scope=scope)
    profile=store.read_record(parent['checking_profile_ref'],contract_id='node-finalization-profile')
    mandatory=['internal_acceptance','external_output','aggregate_limits']
    require((plan['id'] == plan_ref['id'] or plan_ref['id'] == 'blob:' + plan_ref['sha256'])
        and plan['contract_ref'] == plan['node_contract_ref'] == parent_ref and plan['subnode_id'] is None
        and plan['input_refs'] == parent['input_refs'] and plan['profile_ref'] == parent['checking_profile_ref']
        and plan['policy_ref'] == parent['policy_ref'] and plan['mandatory_deterministic'] == profile['mandatory_deterministic'] == mandatory
        and plan['mandatory_semantic'] == [] and len(plan['runner_refs']) == 1
        and _order(store,parent_ref) < _order(store,plan_ref) < _order(store,dispatch_ref),
        'Pre-start failure has no exact original node-scope check plan','integrity_fault')
    for pin in [*parent['input_refs'],*plan['runner_refs']]:store.read_blob(pin)
    preparations=[(pin,value) for pin,value in _rows(store,parent['run_id'],parent['node_id'],'dispatch-preparation')
        if value.get('node_contract_ref') == parent_ref]
    require(len(preparations) <= 1,'Pre-start failure has ambiguous original inert ownership','integrity_fault')
    for pin,value in preparations:
        require(set(value) == {'id','run_id','node_id','recorded_at','node_contract_ref','run_plan_ref','predecessor_commits','bound_input_refs'}
            and value['id'] == pin['id'] and value['id'].startswith('dispatch-preparation:')
            and value['run_id'] == parent['run_id'] and value['node_id'] == parent['node_id']
            and value['run_plan_ref'] == dispatch['run_plan_ref'] and value['bound_input_refs'] == dispatch['bound_input_refs']
            and _order(store,parent_ref) < _order(store,pin) < _order(store,dispatch_ref),
            'Pre-start failure differs from its original inert preparation','integrity_fault')
    if dispatch['run_plan_ref'] is not None:
        for kind in ('run-plan-binding','finite-e1-plan-binding'):
            bindings=list(store.iter_records(run_id=parent['run_id'],kinds=(kind,)))
            require(len(bindings) <= 1 and all(value['record'].get('run_id') == parent['run_id']
                and value['record'].get('plan_ref') == dispatch['run_plan_ref'] for value in bindings),
                'Pre-start failure differs from protected original plan binding','integrity_fault')
            if bindings and kind == 'finite-e1-plan-binding':
                from .finite_evaluation import finite_evidence_refs
                proof=finite_evidence_refs(store,parent['run_id'])
                require(proof is not None and proof['plan_binding_ref'] == bindings[0]['ref'],
                    'Pre-start finite ownership differs from original qualification','integrity_fault')
    forbidden=('dispatch-start','invocation-observation','invocation-record','capsule-record','captured-output','gate-decision',
        'acceptance-commit','deterministic-check-result','verifier-assessment','review-context',
        'protected-invocation-stop','model-call-start','model-call','model-call-refused','model-call-input','model-call-output',
        'model-provider-observation','native-governed-trace','native-governed-trace-event')
    with store._lock:
        contradiction=store.connection.execute('SELECT 1 FROM records WHERE run_id=? AND node_id=? AND kind IN ('
            + ','.join('?' for _ in forbidden) + ') LIMIT 1',(parent['run_id'],parent['node_id'],*forbidden)).fetchone()
        attempts=store.connection.execute('SELECT * FROM attempts WHERE run_id=? AND node_id=? AND attempt_id=?',
            tuple(scope.values())).fetchall()
        acceptance=store.connection.execute('SELECT 1 FROM acceptance WHERE run_id=? AND node_id=? LIMIT 1',
            (parent['run_id'],parent['node_id'])).fetchone()
        model=store.connection.execute('SELECT 1 FROM model_calls WHERE run_id=? AND node_id=? LIMIT 1',
            (parent['run_id'],parent['node_id'])).fetchone()
        tools=store.connection.execute('SELECT 1 FROM tool_calls WHERE run_id=? AND node_id=? LIMIT 1',
            (parent['run_id'],parent['node_id'])).fetchone()
    require(not contradiction and not acceptance and not model and not tools and len(attempts) <= 1,
        'Pre-start failure contradicts an original started assignment/effect publication','integrity_fault')
    for row in attempts:
        child_ref=json.loads(row['contract_ref'])
        child=_original(store,child_ref,'subnode-execution-contract','subnode-execution-contract',scope=scope)
        assigned=[item for item in parent['subnodes'] if item['subnode_id'] == row['subnode_id']]
        require(row['state'] in {'interrupted','paused'} and child['node_contract_ref'] == parent_ref
            and child['subnode_id'] == row['subnode_id'] and len(assigned) == len(child['bindings']) == 1
            and assigned[0]['role'] == child['bindings'][0]['role'] == 'work'
            and child['template_ref'] == assigned[0]['template_ref']
            and child['bindings'][0]['declaration_ref'] == assigned[0]['capsule_ref'],
            'Pre-start failure has an unclosed or different prepared assignment','integrity_fault')


def _inspect(store, request):
    require(type(request) is dict and set(request) == {'node_contract_ref'}, 'Malformed exact ordinary inspection request')
    ref=request['node_contract_ref'];parent=_original(store,ref,'node-execution-contract','node-execution-contract')
    require(all(isinstance(parent[key],str) and parent[key] for key in ('run_id','node_id','attempt_id')), 'Missing exact whole-attempt identity', 'integrity_fault')
    scope={key:parent[key] for key in ('run_id','node_id','attempt_id')};_original(store,ref,'node-execution-contract',scope=scope)
    starts=[(pin,value) for pin,value in _rows(store,parent['run_id'],parent['node_id'],'dispatch-start') if value.get('node_contract_ref') == ref]
    dispatches=[(pin,value) for pin,value in _rows(store,parent['run_id'],parent['node_id'],'dispatch-record') if value.get('node_contract_ref') == ref]
    require(len(starts) <= 1 and len(dispatches) <= 1 and (starts or dispatches), 'No unique original planned dispatch ownership', 'integrity_fault')
    ownership=starts[0][1] if starts else dispatches[0][1]
    require(ownership['run_plan_ref'] is not None,'Pre-plan context is outside the scientific attempt inspector','integrity_fault')
    plan_ref=ownership['run_plan_ref'];plan=_original(store,plan_ref,'run-plan','run-plan')
    require(plan['frozen'] is True and ownership['run_id'] == parent['run_id'] and ownership['node_id'] == parent['node_id']
        and plan['configuration_ref'] == parent['configuration_ref'] and plan['policy_ref'] == parent['policy_ref']
        and plan['source_ref'] == parent['template_ref'], 'Original parent differs from frozen RunPlan', 'integrity_fault')
    nodes=[node for node in plan['nodes'] if node['node_id'] == parent['node_id']]
    require(len(nodes) == 1 and nodes[0]['limits'] == parent['node_limits'], 'Original parent has no exact frozen node', 'integrity_fault')
    node=nodes[0];works=[row for row in parent['subnodes'] if row['role'] == 'work']
    require(len(works) == 1 and works[0]['subnode_id'] == parent['node_id'] and works[0]['capsule_ref']['sha256'] == node['cc']['declaration_sha256']
        and ownership['bound_input_refs'] == [{'name':port['name'],'ref':pin} for port in parent['inputs'] for pin in port['artifact_refs']],
        'Original planned work/input inventory differs', 'integrity_fault')
    snapshot=_original(store,plan['library_snapshot_ref'],'library-snapshot','library-snapshot')
    work=works[0];template=_original(store,work['template_ref'],'subnode-template')
    require(template['capsule_ref'] == work['capsule_ref'],'Original work template declaration differs','integrity_fault')
    declaration,_=_declaration(store,work['capsule_ref'],template['admission_ref'],snapshot)
    bundle=_original(store,template['check_bundle_ref'],'check-bundle','check-bundle')
    profile=_original(store,template['checking_profile_ref'],'checking-profile','checking-profile')
    require(parent['input_refs'] == [pin for port in parent['inputs'] for pin in port['artifact_refs']]
        and [port['name'] for port in parent['inputs']] == [port['name'] for port in node['inputs']]
        and parent['objective'] == node['objective'] and parent['requirement_ids'] == (node['requirement_ids'] or node['deliverable_ids'])
        and parent['required_outputs'] == [port['name'] for port in parent['outputs'] if port['required']]
        and [(port['name'],port['required']) for port in parent['outputs']] == [(port['name'],port['required']) for port in node['outputs']]
        and template['role'] == 'work' and template['subnode_id'] == work['subnode_id'] and template['capsule_ref'] == work['capsule_ref']
        and template['cc'] == node['cc'] and declaration['identity']['name'] == node['cc']['cc_name']
        and declaration['identity']['version_label'] == node['cc']['cc_version'] and template['ports'] == declaration['ports']
        and template['check_bundle_ref']['sha256'] == node['check_pins']['check_bundle_sha256']
        and template['checking_profile_ref']['sha256'] == node['check_pins']['checking_profile_sha256']
        and node['check_pins'] == {'check_bundle_id':bundle['bundle_id'],'check_bundle_version':bundle['version'],
            'check_bundle_sha256':template['check_bundle_ref']['sha256'],'checking_profile_id':profile['profile_id'],
            'checking_profile_version':profile['version'],'checking_profile_sha256':template['checking_profile_ref']['sha256']}
        and all(any(port['name'] == declared['name'] and contract_schema(port['contract_id']) == contract_schema(declared['schema_ref'])
            for declared in declaration['ports']['outputs']) for port in parent['outputs']),
        'Original inert parent/work/check pins differ from frozen node','integrity_fault')
    for pin in parent['input_refs']:store.read_blob(pin)
    with store._lock:
        run=store.get_run(parent['run_id'])
        legacy=store.connection.execute('SELECT 1 FROM artifacts WHERE id=?',(parent['run_id']+':created',)).fetchone()
        if legacy is not None:
            created_ref=store.record_ref(parent['run_id']+':created');created=_original(store,created_ref,'run-created')
            require(created['id'] == created_ref['id'] and created['run_id'] == parent['run_id']
                and created['account_id'] == run['account_id'] and created['workspace_id'] == run['workspace_id'],
                'Original run account/workspace ownership differs','integrity_fault')
        else:
            from .restart_recovery import _ownership
            _ownership(store,store.connection,run,_order(store,ref))
    with store._lock:
        cancellations=store.connection.execute('SELECT * FROM cancellation WHERE run_id=? ORDER BY request_id',(parent['run_id'],)).fetchall()
    original_cancel=[]
    for row in cancellations:
        value=json.loads(row['record']);validate('client-cancellation',value)
        require(row['account_id'] == run['account_id'] and value['run_id'] == row['run_id'] == parent['run_id']
            and value['request_id'] == row['request_id'] and value['status'] == row['state'], 'Original cancellation scope/row differs', 'integrity_fault')
        original_cancel.append(value)
    if original_cancel:
        require(len({value['id'] for value in original_cancel}) == len(original_cancel)
            and all(value['status'] == original_cancel[0]['status'] and value['preserved_effects'] == original_cancel[0]['preserved_effects'] for value in original_cancel),
            'Conflicting original cancellation records', 'integrity_fault')
    cancel=min(original_cancel,key=lambda value:value['id']) if original_cancel else None
    state='cancelled' if cancel and cancel['status'] == 'terminal' and run['state'] == 'halted' and run['reason'] == 'cancelled' else 'outcome_unknown'
    dispatch_ref,dispatch = dispatches[0] if dispatches else (None,None)
    if dispatch is not None:
        _original(store,dispatch_ref,'dispatch-record','dispatch-record',scope=scope)
        require(dispatch['phase'] == 'planned' and dispatch['run_plan_ref'] == plan_ref and dispatch['cc'] == node['cc']
            and dispatch['check_pins'] == node['check_pins'] and dispatch['bound_input_refs'] == ownership['bound_input_refs']
            and all(dispatch[key] == parent[key] for key in scope), 'Original dispatch frozen ownership differs', 'integrity_fault')
        if not starts:
            validate_prestart_failure(store,ref,parent,dispatch_ref,dispatch)
            if dispatch['outcome'] != 'interrupted' and state != 'cancelled':state='terminal'
        gates=[(pin,value) for pin,value in _rows(store,parent['run_id'],parent['node_id'],'gate-decision')
            if value.get('scope_kind') == 'node' and value.get('contract_ref') == ref and value.get('check_plan_ref') == dispatch['check_plan_ref']]
        if dispatch['gate_decision_ref'] is not None:
            require(dispatch['outcome'] not in {'failed','budget_exhausted','interrupted'}
                and len(gates) == 1 and gates[0][0] == dispatch['gate_decision_ref'], 'Dispatch final Gate publication differs', 'integrity_fault')
        else:require(dispatch['outcome'] in {'failed','budget_exhausted','interrupted'} and not dispatch['output_gate_decision_refs'], 'Source-null Gate is not permitted', 'integrity_fault')
        if len(gates) == 1:
            gate_ref,gate=gates[0];_original(store,gate_ref,'gate-decision','gate-decision',scope=scope)
            require(gate['node_contract_ref'] == ref and gate['subnode_id'] is None and gate['policy_ref'] == parent['policy_ref']
                and gate['input_refs'] == parent['input_refs'] and all(gate[key] == parent[key] for key in scope), 'Final Node Gate scope differs', 'integrity_fault')
            final_plan=_original(store,gate['check_plan_ref'],'bound-check-plan','bound-check-plan',scope=scope)
            require(final_plan['contract_ref'] == final_plan['node_contract_ref'] == ref and final_plan['profile_ref'] == parent['checking_profile_ref']
                and final_plan['input_refs'] == parent['input_refs'] and final_plan['policy_ref'] == parent['policy_ref']
                and final_plan['subnode_id'] is None and final_plan['mandatory_semantic'] == []
                and final_plan['mandatory_deterministic'] == ['internal_acceptance','external_output','aggregate_limits'], 'Final Node check plan differs', 'integrity_fault')
            for pin in final_plan['runner_refs']:store.read_blob(pin)
            checked=_original(store,gate['deterministic_result_ref'],'deterministic-check-result','deterministic-check-result',scope=scope)
            require(checked['check_plan_ref'] == gate['check_plan_ref'], 'Final Node checks differ', 'integrity_fault')
            children={};internal=[_internal(store,pin,ref,parent,snapshot,node,children) for pin in gate['internal_decision_refs']]
            require(internal and (dispatch['gate_decision_ref'] is None or dispatch['output_gate_decision_refs'] == gate['internal_decision_refs']), 'Original internal Gate inventory differs', 'integrity_fault')
            for subnode_id in {decision['subnode_id'] for decision in internal}:
                group=[(pin,decision) for pin,decision in zip(gate['internal_decision_refs'],internal) if decision['subnode_id'] == subnode_id]
                if not all(decision['action'] == 'advance' for _,decision in group):continue
                proof=committed_output_proof(store,parent['run_id'],parent['node_id'],subnode_id=subnode_id,
                    attempt_id=parent['attempt_id'],parent_ref=ref)
                _original(store,proof['receipt_ref'],'acceptance-commit',scope=scope)
                require(proof['receipt']['gate_decision_refs'] == [pin for pin,_ in group]
                    and proof['outputs'] == {decision['output_port']:decision['output_refs'][0] for _,decision in group}
                    and _order(store,proof['receipt_ref']) < _order(store,gate_ref) < _order(store,dispatch_ref),
                    'Original accepted work commit/Gates/ports/publication differs','integrity_fault')
            invocations=list({pin['id']:pin for decision in internal for pin in decision['invocation_refs']}.values())
            require(gate['invocation_refs'] == invocations, 'Node Gate omitted an original assignment observation', 'integrity_fault')
            with store._lock:
                attempts=store.connection.execute('SELECT * FROM attempts WHERE run_id=? AND node_id=? AND attempt_id=?',tuple(scope.values())).fetchall()
            require({row['subnode_id'] for row in attempts} == set(children) and all(json.loads(row['contract_ref']) == children[row['subnode_id']][0] for row in attempts),
                'Started assignment inventory is not closed by original observations', 'integrity_fault')
            accepted=dispatch['outcome'] == 'accepted'
            require((gate['action'] == 'advance') == accepted and dispatch['output_refs'] == (gate['accepted_refs'] if accepted else []), 'Dispatch outcome/output differs from final Node Gate', 'integrity_fault')
            if accepted:
                proof=committed_output_proof(store,parent['run_id'],parent['node_id'],attempt_id=parent['attempt_id'],parent_ref=ref)
                require(proof['receipt']['gate_decision_refs'] == [gate_ref]
                    and sorted(json.dumps(pin,sort_keys=True) for pin in proof['outputs'].values()) == sorted(json.dumps(pin,sort_keys=True) for pin in dispatch['output_refs'])
                    and set(proof['outputs']) == set(parent['required_outputs']) and all_mandatory_pass(final_plan,checked['results']), 'Original node acceptance closure differs', 'integrity_fault')
                require(_order(store,proof['receipt_ref']) < _order(store,dispatch_ref),'Dispatch precedes original node acceptance publication','integrity_fault')
            published=[gate_ref,gate['check_plan_ref'],gate['deterministic_result_ref'],*gate['internal_decision_refs'],*gate['invocation_refs']]
            require(all(_order(store,pin) < _order(store,dispatch_ref) for pin in published)
                and _order(store,starts[0][0]) < _order(store,gate_ref), 'Dispatch precedes original finalization/assignment publication','integrity_fault')
            if dispatch['outcome'] == 'interrupted':
                require(dispatch['ended_at'] is None,'Interrupted dispatch claims a finished end','integrity_fault')
            else:require(dispatch['started_at'] is not None and dispatch['ended_at'] is not None
                and datetime.fromisoformat(dispatch['ended_at'].replace('Z','+00:00')) >= datetime.fromisoformat(dispatch['started_at'].replace('Z','+00:00'))
                and type(dispatch['elapsed_s']) in (int,float) and math.isfinite(dispatch['elapsed_s']) and dispatch['elapsed_s'] >= 0,
                'Original Scheduler processing chronology is unavailable', 'integrity_fault')
            if dispatch['outcome'] != 'interrupted' and state != 'cancelled':state='terminal'
    return {'node_contract_ref':copy.deepcopy(ref),'run_plan_ref':plan_ref,**scope,'state':state,
        'dispatch_ref':dispatch_ref,'source_outcome':dispatch['outcome'] if dispatch else None,'cancellation_record':cancel}


def inspect_node_attempt(store, request):
    try:return _inspect(store,request)
    except ResearchError:raise
    except (KeyError,TypeError,ValueError,IndexError,UnicodeError,AttributeError,sqlite3.Error) as error:
        raise ResearchError('integrity_fault','Original ordinary inspection closure is malformed or unavailable') from error
