"""Frozen finite case scheduling; no automatic retries or hidden labels."""
import hashlib
import random
import re
import math
from .evidence import relative
from .evidence import canonical


MODULES={'capsule','verifier','routing','rsi'}
ID=re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$')

VISIBLE_FIELDS=set('schema case_id case_version supersedes scenario_id variant_id topic research_question domain_codes module_requirements delivery_profile milestone classification split expected_behavior entry_mode task_prompt permitted_resources input_fixtures seed budgets gpu_required host_profile hardware_requirements human_intervention repair_policy fault_plan_ref checkpoints node_bundle_ref capsule_binding model_configuration_ref repeat_policy required_evidence oracle_version referee_ref'.split())


def validate_visible_case(case):
    """Implement benchmark-runner.md benchmark-case:1 without adding fields."""
    if not isinstance(case,dict) or set(case)!=VISIBLE_FIELDS or case['schema']!='benchmark-case:1':raise ValueError('missing/unknown visible case field')
    strings={'case_id','scenario_id','variant_id','topic','research_question','task_prompt','model_configuration_ref','oracle_version'}
    arrays={'domain_codes','module_requirements','permitted_resources','input_fixtures','checkpoints','required_evidence'}
    objects={'budgets','hardware_requirements','repeat_policy','referee_ref'}
    if any(not isinstance(case[k],str) for k in strings) or any(not isinstance(case[k],list) for k in arrays) or any(not isinstance(case[k],dict) for k in objects):raise ValueError('visible field has wrong type')
    if any(not isinstance(x,str) for k in ('domain_codes','module_requirements','required_evidence') for x in case[k]):raise ValueError('string array expected')
    if not ID.fullmatch(case['case_id']) or not ID.fullmatch(case['variant_id']) or type(case['case_version']) is not int or case['case_version']<1:raise ValueError('invalid frozen case identity')
    if case['supersedes'] is not None and (type(case['supersedes']) is not int or not 0<case['supersedes']<case['case_version']):raise ValueError('invalid supersedes version')
    if not re.fullmatch(r's(?:0[1-9]|10)',case['scenario_id']) or not 3<=len(case['topic'])<=200 or not 10<=len(case['research_question'])<=500 or not 1<=len(case['task_prompt'])<=20000:raise ValueError('case family/topic/obligation bound')
    if not case['domain_codes'] or any(not re.fullmatch('c0[1-8]',x) for x in case['domain_codes']):raise ValueError('invalid domain taxonomy')
    if not case['module_requirements'] or any(not re.fullmatch('(cc|pl|vf|rt|rs|lh|su)[0-9]{2}',x) for x in case['module_requirements']):raise ValueError('invalid requirement mapping')
    choices={'delivery_profile':{'core_m1_phase1_baseline','core_m1_phase1_verifier','phase3_conditional','m2_m3_routing','m2_m3_rsi','extended'},
        'milestone':{'m1','m2','m3','m4','later'},'classification':{'core_m1_acceptance','phase3_progress','m2_m3_progress','extended_performance'},
        'split':{'development','held_out','milestone_tracking'},'expected_behavior':{'complete','halt'},'entry_mode':{'run','node_replay','single_cc','long_horizon'},
        'host_profile':{'mrgf_x_default','gb10','other_declared'},'human_intervention':{'none','escalation_record_only'},'repair_policy':{'none'}}
    if any(case[key] not in allowed for key,allowed in choices.items()):raise ValueError('unsupported source enum')
    if case['seed'] is not None and (type(case['seed']) is not int or case['seed']<0):raise ValueError('invalid requested seed')
    if type(case['gpu_required']) is not bool:raise ValueError('GPU requirement must be explicit')
    budget=case['budgets'];keys={'wall_time_s','invocations','compute','memory_physical_mb','memory_committed_mb','storage_mb','concurrency','tools','effects'}
    if set(budget)!=keys or any(type(budget[k]) is not int or budget[k]<1 for k in ('wall_time_s','invocations','memory_physical_mb','memory_committed_mb','storage_mb','concurrency')):raise ValueError('invalid case budget')
    if budget['concurrency']!=1 or budget['memory_committed_mb']<budget['memory_physical_mb'] or not isinstance(budget['compute'],dict) or set(budget['compute'])!={'cpu_s','gpu_s'} or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in budget['compute'].values()):raise ValueError('M1 budget/enforcement inconsistency')
    if any(not isinstance(budget[k],list) or any(not isinstance(v,str) for v in budget[k]) for k in ('tools','effects')):raise ValueError('invalid allowed tool/effect list')
    hardware=case['hardware_requirements']
    if set(hardware)!={'min_physical_mb','min_commit_mb','arch','accelerator'} or any(type(hardware[k]) is not int or hardware[k]<0 for k in ('min_physical_mb','min_commit_mb')) or hardware['arch'] not in {'any','x86_64','aarch64'} or hardware['accelerator'] not in {'none','required'}:raise ValueError('invalid declared hardware requirements')
    for resource in case['permitted_resources']:
        if not isinstance(resource,dict) or set(resource)!={'resource_id','kind','ref'} or not isinstance(resource['resource_id'],str) or not ID.fullmatch(resource['resource_id']) or resource['kind'] not in {'tool','source','dataset'} or not isinstance(resource['ref'],(str,dict)):raise ValueError('invalid visible resource binding')
        if isinstance(resource['ref'],dict):
            from .frozen_records import ref_key
            ref_key(resource['ref'])
    for fixture in case['input_fixtures']:
        if not isinstance(fixture,dict) or set(fixture)!={'fixture_id','path','sha256','provenance','role'} or any(not isinstance(fixture[k],str) for k in ('fixture_id','path','sha256','role')) or fixture['role'] not in {'input','replay_bundle','binding','source_snapshot','fault_asset'} or not ID.fullmatch(fixture['fixture_id']) or not re.fullmatch('[a-f0-9]{64}',fixture['sha256']):raise ValueError('invalid visible fixture pin')
        relative(fixture['path'])
    fixtures={f['fixture_id']:f for f in case['input_fixtures']}
    if len(fixtures)!=len(case['input_fixtures']):raise ValueError('duplicate fixture identity')
    if case['entry_mode']=='node_replay' and not case['node_bundle_ref'] or case['entry_mode']=='single_cc' and not case['capsule_binding']:raise ValueError('required entry binding absent')
    if case['node_bundle_ref'] is not None and (not isinstance(case['node_bundle_ref'],str) or case['node_bundle_ref'] not in fixtures or fixtures[case['node_bundle_ref']]['role']!='replay_bundle'):raise ValueError('replay bundle must identify an exact replay fixture')
    if case['capsule_binding'] is not None:
        binding=case['capsule_binding']
        if not isinstance(binding,dict) or set(binding)!={'capsule_id','capsule_version','binding_fixture_id'} or any(not isinstance(v,str) or not v for v in binding.values()) or binding['binding_fixture_id'] not in fixtures or fixtures[binding['binding_fixture_id']]['role']!='binding':raise ValueError('Capsule binding fixture unavailable')
    if case['fault_plan_ref'] is not None and (not isinstance(case['fault_plan_ref'],str) or not ID.fullmatch(case['fault_plan_ref'])):raise ValueError('invalid fault binding')
    if case['entry_mode']!='long_horizon' and case['checkpoints']:raise ValueError('checkpoints require declared long-horizon entry')
    if any(not isinstance(c,dict) or set(c)!={'checkpoint_id','after_node'} or any(not isinstance(v,str) or not v for v in c.values()) for c in case['checkpoints']):raise ValueError('invalid checkpoint binding')
    repeat=case['repeat_policy']
    if set(repeat)!={'repeats','stochastic'} or type(repeat['repeats']) is not int or repeat['repeats']<1 or type(repeat['stochastic']) is not bool:raise ValueError('invalid declared repeat policy')
    if not re.fullmatch('oracle:[1-9][0-9]*',case['oracle_version']):raise ValueError('invalid oracle version')
    if set(case['referee_ref'])!={'label_id','referee_sha256','visible_sha256'} or not isinstance(case['referee_ref']['label_id'],str) or not ID.fullmatch(case['referee_ref']['label_id']):raise ValueError('independent referee binding missing')
    for key in ('referee_sha256','visible_sha256'):
        if not isinstance(case['referee_ref'][key],str) or not re.fullmatch('[a-f0-9]{64}',case['referee_ref'][key]):raise ValueError('invalid referee hash pin')
    visible={k:v for k,v in case.items() if k!='referee_ref'}
    if hashlib.sha256(canonical(visible)).hexdigest()!=case['referee_ref']['visible_sha256']:raise ValueError('visible/referee binding hash drift')
    return case


def validate_case(case):
    if case.get('module') not in MODULES or not ID.fullmatch(case['case_id']) or not ID.fullmatch(case['variant_id']):raise ValueError('case outside four-case scope')
    if not isinstance(case['case_version'],int) or case['case_version']<1:raise ValueError('invalid case version')
    if any(k in case for k in ('labels','mandatory_checks','private_key','app_token','hidden_fixtures')):raise ValueError('protected referee content in visible case')
    return case


def schedule(campaign,cases):
    if campaign['retry_policy']!='none':raise ValueError('M1 retry policy is none')
    if not ID.fullmatch(campaign['campaign_id']):raise ValueError('invalid campaign identity')
    if len({(c['case_id'],c['case_version']) for c in cases})!=len(cases):raise ValueError('duplicate case identity')
    rows=[]
    for case in cases:
        validate_case(case)
        for config in campaign['configurations']:
            if not ID.fullmatch(config['config_id']):raise ValueError('invalid configuration identity')
            for repeat in range(max(campaign['repeats'],case['repeat_policy']['repeats'])):
                rows.append({'run_id':f"{campaign['campaign_id']}__{case['case_id']}__{config['config_id']}__r{repeat:02d}",
                    'campaign_id':campaign['campaign_id'],'case_id':case['case_id'],'case_version':case['case_version'],
                    'module':case['module'],'variant_id':case['variant_id'],'config_id':config['config_id'],'repeat_index':repeat})
    if campaign['order']['randomized']:random.Random(campaign['order']['order_seed']).shuffle(rows)
    return rows
