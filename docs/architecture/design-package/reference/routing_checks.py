"""Offline checks of documented routing fixtures; no router or provider execution.

Executed by validate.py with its validated schemas, field projections and helpers.
These checks cannot establish authenticated trust, atomicity or runtime readiness.
"""
from datetime import datetime

def routing_ref(value):
    path=(EX/value['id']).resolve()
    if not path.is_relative_to(EX.resolve()) or not path.is_file():
        raise ValueError('missing or escaping original artifact')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=value['sha256']:
        raise ValueError('changed original bytes')
    return path

def export_issues(selected):
    result=[]
    try:
        if not validators['urn:jiuwenswarm:m1-design:capsule-declaration:1.0.0'].is_valid(selected['declaration']):result.append('declaration schema')
        declaration=load(routing_ref(selected['declaration_ref']))
        child=load(routing_ref(selected['subnode_contract_ref']))
        parent=load(routing_ref(selected['node_contract_ref']))
        if declaration!=selected['declaration']:result.append('parsed declaration differs from pinned bytes')
        if child['node_contract_ref']!=selected['node_contract_ref']:result.append('wrong parent')
        if len(child['bindings'])!=1:return result+['not one binding']
        binding=child['bindings'][0];ctx=selected['bound_context']
        if binding['declaration_ref']!=selected['declaration_ref']:result.append('different bound declaration')
        for key in ('run_id','node_id','subnode_id','attempt_id'):
            if ctx['runtime'][key]!=child[key]:result.append('wrong runtime identity')
        for key,expected in [('binding_id',binding['id']),('role',binding['role']),('objective',child['objective']),('inputs',child['inputs']),('outputs',child['outputs']),('implementation_refs',binding['implementation_refs']),('dependency_refs',binding['dependency_refs']),('admission_ref',binding['admission_ref']),('effective_authority',binding['effective_authority']),('invocation_limits',binding['limits']),('subnode_limits',child['subnode_limits']),('node_limits',parent['node_limits']),('policy_ref',child['policy_ref']),('configuration_ref',child['configuration_ref'])]:
            if ctx[key]!=expected:result.append('projection mismatch: '+key)
        if ctx['eligibility']!='eligible':result.append('ineligible')
        overlays=[{'id':x['ref'],'sha256':x['sha256']} for x in declaration['identity'].get('overlays',[])]
        if ctx['overlay_refs']!=overlays:result.append('overlay mismatch')
        for pin in [selected['declaration_ref'],ctx['admission_ref']]+ctx['implementation_refs']+ctx['overlay_refs']+ctx['dependency_refs']:
            routing_ref(pin)
        snapshot=ctx['budget_snapshot'];record=load(routing_ref(snapshot['snapshot_ref']))
        if {k:v for k,v in snapshot.items() if k!='snapshot_ref'}!={k:v for k,v in record.items() if k!='id'}:result.append('budget snapshot differs')
        for scope in ('node_remaining','subnode_remaining','other_work_reserved','verifier_reserved','routing_reserved'):
            balance=snapshot[scope]
            if balance['time_s']<0 or balance['model_calls']<0 or not 0<balance['memory_mb']<=ctx['node_limits']['memory_mb']:result.append('invalid budget balance')
        for dimension in ('model_calls','time_s'):
            if snapshot['subnode_remaining'][dimension]>min(ctx['invocation_limits'][dimension],ctx['subnode_limits'][dimension]):result.append('child balance exceeds ceiling')
            if snapshot['node_remaining'][dimension]<0:result.append('negative balance')
            if snapshot['node_remaining'][dimension]>ctx['node_limits'][dimension]:result.append('balance exceeds ceiling')
            reserved=sum(snapshot[key][dimension] for key in ('subnode_remaining','other_work_reserved','verifier_reserved','routing_reserved'))
            if reserved>snapshot['node_remaining'][dimension]:result.append('reservation overcommit')
        predicates={x['id']:x for x in declaration['needs']['when']}
        if {x['id'] for x in ctx['prerequisite_results']}!=set(predicates):result.append('missing predicate result')
        for item in ctx['prerequisite_results']:
            p=predicates[item['id']]
            if item['evaluable_at']!=p['evaluable_at']:result.append('predicate timing changed')
            if item['status'] not in ('pass','deferred'):result.append('mandatory prerequisite not ready')
            if item['status']=='deferred' and not (p['evaluable_at'] in ('dispatch','both') and p['on_unknown']=='defer_to_dispatch'):result.append('illegal deferral')
    except (KeyError,TypeError,ValueError) as exc:result.append('invalid export: '+str(exc))
    return result

def request_issues(request,profile):
    result=field_errors(request,interfaces['route-request:field-contract:1']['fields'])
    result+=export_issues(request['selected_capsule'])
    try:
        if load(routing_ref(request['model_selection_profile_ref']))!=profile:result.append('profile mismatch')
        ctx=request['selected_capsule']['bound_context']
        if request['input_refs']!=[r for port in ctx['inputs'] for r in port['artifact_refs']]:result.append('input inventory mismatch')
        if request['policy_ref']!=ctx['policy_ref'] or profile['policy_ref']!=request['policy_ref']:result.append('policy mismatch')
        if request['domain']!='cs_ml':result.append('out-of-scope domain')
        if request['task_category'] not in ('ml_methods_and_inference','retrieval_and_knowledge_systems','algorithms_optimization_and_formal','software_systems_and_performance','databases_and_data_processing','networking_and_distributed_algorithms','security_and_reliability','experimental_evaluation_and_technical_data'):result.append('unknown task category')
        if request['call_function'] not in ('worker','verifier','planner'):result.append('unknown call function')
        if not profile['approved_model_ids']:result.append('empty approved scope')
        if 'model_allowlist' in request['requirements'] and not set(request['requirements']['model_allowlist']) & set(profile['approved_model_ids']):result.append('empty request scope')
        if profile['policy_mode'] not in ('development_profile','fixed_baseline','bounded_llm_ablation'):result.append('invalid policy mode')
        allowance=profile['selection_allowance']
        if allowance['enabled']:
            if profile['policy_mode']!='bounded_llm_ablation':result.append('selection call outside ablation')
            if allowance['model_calls']!=1 or not allowance['deployment_ref'] or allowance['time_s']<=0 or allowance['output_tokens']<=0:result.append('unbounded selection call')
            if ctx['budget_snapshot']['routing_reserved']['model_calls']<1:result.append('unreserved selection call')
        elif allowance['model_calls']!=0:result.append('disabled selection call consumes calls')
        if profile['policy_mode']=='fixed_baseline' and (allowance['enabled'] or profile['alternate_model_id'] is not None or len(profile['approved_model_ids'])!=1):result.append('fixed baseline expanded')
        alternate=profile['alternate_model_id']
        if alternate is not None and alternate not in profile['approved_model_ids']:result.append('alternate outside profile')
    except (KeyError,TypeError,ValueError) as exc:result.append('invalid request/profile: '+str(exc))
    return result

def decision_issues(decision,request,profile):
    result=field_errors(decision,interfaces['model-route:field-contract:2']['fields'])
    try:
        ctx=request['selected_capsule']['bound_context']
        effective_limits=copy.deepcopy(ctx['invocation_limits'])
        effective_limits['time_s']=min(effective_limits['time_s'],ctx['subnode_limits']['time_s'],ctx['node_limits']['time_s'],ctx['budget_snapshot']['subnode_remaining']['time_s'],request['selected_capsule']['declaration']['budget']['per_call']['wall_s'])
        for key,expected in [('request_ref',ref_for('route_request.json')),('selected_capsule_ref',ref_for('selected_capsule_input.json')),('runtime',ctx['runtime']),('execution_id',request['execution_id']),('binding_id',ctx['binding_id']),('role',ctx['role']),('model_selection_profile_ref',request['model_selection_profile_ref']),('limits',effective_limits)]:
            if decision[key]!=expected:result.append('decision mismatch: '+key)
        if decision['selected_endpoint'] not in decision['eligible_endpoints'] or not set(decision['eligible_endpoints'])<=set(profile['approved_model_ids']):result.append('ineligible model')
        if decision['selection_method'] not in ('fixed_profile','single_candidate','development_profile_policy','bounded_llm_selection','compatible_baseline','router_alternate_model'):result.append('unknown selection method')
        if decision['alternate_used']!=(decision['selection_method']=='router_alternate_model'):result.append('false alternate attribution')
        if decision['alternate_used'] and decision['selected_endpoint']!=profile['alternate_model_id']:result.append('different alternate model')
        if profile['policy_mode']=='fixed_baseline' and (decision['selection_method'] not in ('fixed_profile','single_candidate') or decision['registry_snapshot_ref'] is not None):result.append('fixed baseline uses API selection')
        if datetime.fromisoformat(decision['valid_until'].replace('Z','+00:00'))<=datetime.fromisoformat(decision['ready_at'].replace('Z','+00:00')):result.append('invalid validity')
        routing_ref(decision['deployment_ref'])
        context=load(routing_ref(decision['routing_context_ref']))
        if context['selected_capsule_ref']!=decision['selected_capsule_ref'] or context['model_selection_profile_ref']!=decision['model_selection_profile_ref'] or context['adapter_revision']!=decision['adapter_revision'] or context['capsule_budget']!=request['selected_capsule']['declaration']['budget'] or context['effective_limits']!=decision['limits']:result.append('derived context mismatch')
        if decision['selection_method']=='single_candidate' and len(decision['eligible_endpoints'])!=1:result.append('not sole candidate')
        if decision['selection_method']=='bounded_llm_selection' and (not profile['selection_allowance']['enabled'] or len(decision['eligible_endpoints'])<2):result.append('unauthorized selection call')
    except (KeyError,TypeError,ValueError) as exc:result.append('invalid decision: '+str(exc))
    return result

selected=load(EX/'selected_capsule_input.json');request=load(EX/'route_request.json');profile=load(EX/'model_selection_profile.json');decision=load(EX/'route_decision.json');call=load(EX/'model_call_record.json')
require(not export_issues(selected),'Routing teaching export inconsistent: '+str(export_issues(selected)))
require(not request_issues(request,profile),'Routing request/profile inconsistent: '+str(request_issues(request,profile)))
require(not decision_issues(decision,request,profile),'Routing decision inconsistent: '+str(decision_issues(decision,request,profile)))
require(call['purpose']=='task_execution' and call['route_decision_ref']==ref_for('route_decision.json') and call['deployment_ref']==decision['deployment_ref'] and call['execution_id']==request['execution_id'] and call['invocation_id']==decision['runtime']['invocation_id'],'Call provenance mismatch')
require(not call['observed_runtime'] and all(call['usage'][key] is None for key in ('input_tokens','output_tokens','cost_amount')) and bool(call['usage']['unavailable_reasons']),'Synthetic call invents runtime usage')

routing_seed_valid=not export_issues(selected) and not request_issues(request,profile) and not decision_issues(decision,request,profile)
if routing_seed_valid:
    for mode in ('hash','parsed_declaration','implementation','overlay','parent','runtime','authority','eligibility','reservation','balance'):
        bad=copy.deepcopy(selected)
        if mode=='hash':bad['declaration_ref']['sha256']='0'*64
        elif mode=='parsed_declaration':bad['declaration']['identity']['summary']='Changed method'
        elif mode=='implementation':bad['bound_context']['implementation_refs']=[]
        elif mode=='overlay':bad['bound_context']['overlay_refs']=[{'id':'missing-overlay','sha256':'0'*64}]
        elif mode=='parent':bad['node_contract_ref']['sha256']='0'*64
        elif mode=='runtime':bad['bound_context']['runtime']['run_id']='other-run'
        elif mode=='authority':bad['bound_context']['effective_authority']['tools'].append('shell')
        elif mode=='eligibility':bad['bound_context']['eligibility']='suspended'
        elif mode=='reservation':bad['bound_context']['budget_snapshot']['verifier_reserved']['model_calls']=999
        else:bad['bound_context']['budget_snapshot']['node_remaining']['model_calls']=999
        require(bool(export_issues(bad)),'Routing negative export accepted: '+mode);negative_count+=1
    for mode in ('client_role','unknown_task','input','profile_pin','empty_scope'):
        bad=copy.deepcopy(request)
        if mode=='client_role':bad['role']='reviewer'
        elif mode=='unknown_task':bad['task_category']='invented'
        elif mode=='input':bad['input_refs']=[]
        elif mode=='empty_scope':bad['requirements']['model_allowlist']=[]
        else:bad['model_selection_profile_ref']['sha256']='0'*64
        require(bool(request_issues(bad,profile)),'Routing negative request accepted: '+mode);negative_count+=1
    for mode in ('model','scope','alternate','binding','decision_version','expiry','context_hash','context_adapter','effective_limit'):
        bad=copy.deepcopy(decision)
        if mode=='model':bad['selected_endpoint']='unauthorized'
        elif mode=='scope':bad['eligible_endpoints'].append('unauthorized')
        elif mode=='alternate':bad['alternate_used']=True
        elif mode=='binding':bad['binding_id']='other-binding'
        elif mode=='decision_version':bad['schema_version']='1.0.0'
        elif mode=='context_hash':bad['routing_context_ref']['sha256']='0'*64
        elif mode=='context_adapter':bad['adapter_revision']='changed'
        elif mode=='effective_limit':bad['limits']['time_s']=120
        else:bad['valid_until']=bad['ready_at']
        require(bool(decision_issues(bad,request,profile)),'Routing negative decision accepted: '+mode);negative_count+=1
else:
    require(False, 'Routing negative checks require consistent original fixtures; malformed fixture rejected')
if routing_seed_valid:
    print('PASS: synthetic Capsule export/request/profile/decision/call relationships; 24 negative routing cases')
print('LIMIT: no authenticated exporter, live admission/dispatch, model selection, provider call, atomicity or runtime budget enforcement exercised')
