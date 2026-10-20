"""Host-side immutable campaign preparation; workers cannot edit their schedule."""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from .cases import ID, MODULES
from .cases import schedule,validate_visible_case
from .evidence import canonical,read_verified,relative,write_once
from .frozen_records import strict_json


CAMPAIGN_FIELDS=set('schema campaign_id frozen_at milestone purpose suite_version cases configurations pairs pins repeats seeds order host_profile environment_profile evaluation_profile_id fault_plan analysis_policy judge_config_ref retry_policy unavailable_modules'.split())


def load_referee(case,raw):
    """Register/load exact private label bytes against one frozen visible case.

    Called only by protected preparation/referee code. The ordinary campaign
    loader and runner never open the label store. Verify original bytes before
    parsing; a canonical reserialization cannot replace the frozen raw hash.
    """
    if not isinstance(raw,bytes) or len(raw)>16*1024*1024:raise ValueError('one bounded raw referee body is required')
    pin=case.get('referee_ref') if isinstance(case,dict) else None
    if (not isinstance(pin,dict) or not isinstance(pin.get('referee_sha256'),str)
        or hashlib.sha256(raw).hexdigest()!=pin['referee_sha256']):raise ValueError('raw referee bytes differ from the frozen pin')
    # module is the derived registry correlation, not a visible case field.
    visible={k:v for k,v in case.items() if k!='module'}
    validate_visible_case(visible)
    from .referee import validate_referee
    label=strict_json(raw)
    validate_referee(label)
    if ((label['case_id'],label['case_version'],label['label_id'])
        !=(case['case_id'],case['case_version'],pin['label_id'])):raise ValueError('referee case/version/label identity mismatch')
    if label['expected_outcome']['expected_terminal']!=case['expected_behavior']:raise ValueError('referee expected terminal differs from the visible case')
    if (case['entry_mode']=='node_replay' or case['fault_plan_ref'] is not None or 'gate-decision' in case['required_evidence']) and label['expected_tier_verdicts'] is None:
        raise ValueError('replay/gate case requires frozen tier/action expectations')
    if case['capsule_binding'] is not None and label['valid_capsule_choices']:raise ValueError('static binding case cannot replace its pinned Capsule with choices')
    return label


def _validate_registry(module_map,case_ids):
    if (not isinstance(module_map,dict) or set(module_map)!=set(case_ids)
        or any(not isinstance(value,str) or value not in MODULES for value in module_map.values())
        or set(module_map.values())!=MODULES):
        raise ValueError('frozen module registry must cover the declared cases and all four modules')


def _validate_fixture_bytes(bench_root,cases):
    """Paths in benchmark-case:1 are relative to BENCH_ROOT, not the campaign.

    Check every declared role against original bytes. The ordinary immutable
    evidence reader also refuses traversals, symlinks and hard-linked files.
    This validates visible inputs only; it never opens the referee label store.
    """
    for case in cases:
        for fixture in case['input_fixtures']:
            path=relative(fixture['path'])
            if not path.parts:
                raise ValueError('visible fixture must identify a regular file')
            if path.parts[0]=='labels':
                raise ValueError('referee label store is not a visible input fixture')
            read_verified(bench_root,fixture)


def load_campaign(bench_root,ident):
    """Load the complete frozen visible closure before any client/result effect.

    The campaign and its case metadata retain the registered campaign layout;
    input fixture paths retain the adopted BENCH_ROOT-relative interpretation.
    A valid loader result establishes no runtime, oracle or model qualification.
    """
    if not isinstance(ident,str) or not ID.fullmatch(ident):
        raise ValueError('campaign ID must be a single registered identity')
    bench_root=Path(bench_root)
    folder=bench_root/'campaigns'/ident
    campaign=strict_json((folder/'campaign.json').read_bytes())
    if not isinstance(campaign,dict) or campaign.get('campaign_id')!=ident:
        raise ValueError('campaign identity mismatch')
    pins=campaign.get('cases')
    if not isinstance(pins,list) or not pins:
        raise ValueError('frozen case set is absent')
    case_ids=[]
    for pin in pins:
        if (not isinstance(pin,dict) or set(pin)!={'case_id','case_version','case_sha256'}
            or not isinstance(pin['case_id'],str) or not ID.fullmatch(pin['case_id'])
            or type(pin['case_version']) is not int or pin['case_version']<1
            or not isinstance(pin['case_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',pin['case_sha256'])):
            raise ValueError('invalid frozen case pin')
        case_ids.append(pin['case_id'])
    if len(set(case_ids))!=len(case_ids):
        raise ValueError('duplicate frozen case identity')
    registry=strict_json((folder/'module-map.json').read_bytes())
    _validate_registry(registry,case_ids)
    cases=[]
    for pin in pins:
        raw=read_verified(folder,{'path':'cases/'+pin['case_id']+'/case.json','sha256':pin['case_sha256']})
        case=strict_json(raw)
        validate_visible_case(case)
        if (case['case_id'],case['case_version'])!=(pin['case_id'],pin['case_version']):
            raise ValueError('frozen case identity changed')
        cases.append({**case,'module':registry[case['case_id']]})
    validate_campaign(campaign,cases)
    _validate_fixture_bytes(bench_root,cases)
    if strict_json((folder/'schedule.json').read_bytes())!=schedule(campaign,cases):
        raise ValueError('frozen host-prepared schedule absent or changed')
    return folder,campaign,cases


def validate_campaign(campaign,cases):
    """The adopted benchmark-campaign:1 fields, fixed before any execution."""
    if not isinstance(campaign,dict) or set(campaign)!=CAMPAIGN_FIELDS or campaign['schema']!='benchmark-campaign:1':raise ValueError('campaign contract fields mismatch')
    if not isinstance(campaign['campaign_id'],str) or not ID.fullmatch(campaign['campaign_id']) or campaign['retry_policy']!='none':raise ValueError('campaign identity/retry policy invalid')
    if campaign['milestone'] not in {'m1','m2','m3','m4','later'} or campaign['purpose'] not in {'baseline','milestone_progress','ablation','pilot','feasibility','judge_audit','calibration'}:raise ValueError('invalid campaign applicability')
    if not re.fullmatch('suite:'+campaign['milestone']+':[1-9][0-9]*',campaign['suite_version']):raise ValueError('suite version does not identify milestone')
    try:
        timestamp=datetime.fromisoformat(campaign['frozen_at'].replace('Z','+00:00'))
        if timestamp.utcoffset() is None or timestamp.utcoffset().total_seconds()!=0:raise ValueError('campaign time must be UTC')
    except (ValueError,TypeError,AttributeError):raise ValueError('invalid campaign freeze time') from None
    if type(campaign['repeats']) is not int or campaign['repeats']<1:raise ValueError('campaign repeats must be explicit')
    if not isinstance(campaign['configurations'],list) or not campaign['configurations']:raise ValueError('campaign configuration absent')
    configs={}
    for c in campaign['configurations']:
        if not isinstance(c,dict) or set(c)!=set('config_id kind adapter model_identifier model_route profile_id adapter_pin notes'.split()) or not isinstance(c['config_id'],str) or not ID.fullmatch(c['config_id']):raise ValueError('configuration contract mismatch')
        if c['kind'] not in {'ai4research_fixed_dag','ai4research_dynamic','ai4research_routed','ai4research_rsi_child','plain_model_agent','codex','claude_code'} or c['adapter'] not in {'product_client','external_adapter'}:raise ValueError('unknown configuration adapter')
        if c['kind'].startswith('ai4research_') and c['adapter']!='product_client':raise ValueError('product configuration requires supported client')
        if c['adapter']=='external_adapter' and (not isinstance(c['adapter_pin'],dict) or set(c['adapter_pin'])!={'name','version','image_digest'} or any(not isinstance(v,str) or not v for v in c['adapter_pin'].values())):raise ValueError('external adapter pin unavailable')
        if c['config_id'] in configs or any(not isinstance(c[k],str) for k in ('model_identifier','model_route','notes')):raise ValueError('duplicate or malformed configuration')
        configs[c['config_id']]=c
    if any(c['model_configuration_ref'] not in configs for c in cases):raise ValueError('case model configuration slot is not frozen')
    if not isinstance(campaign['pairs'],list):raise ValueError('pairs must be explicit')
    for pair in campaign['pairs']:
        if set(pair)!={'pair_id','config_ids','difference'} or len(pair['config_ids'])!=2 or len(set(pair['config_ids']))!=2 or any(x not in configs for x in pair['config_ids']) or not isinstance(pair['difference'],str) or not pair['difference']:raise ValueError('invalid preregistered comparison')
    seeds=campaign['seeds'];order=campaign['order']
    repeats=max([campaign['repeats'],*[c['repeat_policy']['repeats'] for c in cases]])
    if not isinstance(seeds,dict) or set(seeds)!={'base_seed','per_repeat'} or type(seeds['base_seed']) is not int or not isinstance(seeds['per_repeat'],list) or len(seeds['per_repeat'])<repeats or any(type(v) is not int for v in seeds['per_repeat']):raise ValueError('repeat seed schedule incomplete')
    if not isinstance(order,dict) or set(order)!={'randomized','order_seed'} or type(order['randomized']) is not bool or type(order['order_seed']) is not int:raise ValueError('order must be frozen')
    policy=campaign['analysis_policy']
    if not isinstance(policy,dict) or set(policy)!={'ci_methods','cluster_by','alpha','reporting_criteria_ref'} or not isinstance(policy['ci_methods'],list) or any(x not in {'wilson','paired_bootstrap_cluster'} for x in policy['ci_methods']) or policy['cluster_by']!='variant' or type(policy['alpha']) not in (int,float) or policy['alpha']!=.05 or not isinstance(policy['reporting_criteria_ref'],str):raise ValueError('source analysis policy mismatch')
    environment=campaign['environment_profile']
    if not isinstance(environment,dict) or set(environment)!={'os','background_workload','power','pagefile_policy','concurrency'} or any(not isinstance(v,str) for v in environment.values()):raise ValueError('environment profile incomplete')
    if campaign['host_profile'] not in {'mrgf_x_default','gb10','other_declared'} or any(c['host_profile']!=campaign['host_profile'] for c in cases):raise ValueError('campaign host profile mismatch')
    if campaign['evaluation_profile_id'] is not None and not isinstance(campaign['evaluation_profile_id'],str):raise ValueError('invalid evaluation profile identity')
    if any(c['entry_mode'] in {'node_replay','single_cc'} or c['fault_plan_ref'] for c in cases) and not campaign['evaluation_profile_id']:raise ValueError('evaluation entry/fault requires an approved frozen profile')
    pins=campaign['pins']
    if not isinstance(pins,dict) or set(pins)!=set('benchmark_runner_version oracle_versions app_build client_contract_version capsule_catalogue planner router verifier model_settings runtime_config_sha256 external_snapshots'.split()):raise ValueError('campaign pins incomplete')
    if pins['oracle_versions']!={c['case_id']:c['oracle_version'] for c in cases}:raise ValueError('campaign oracle pins differ from cases')
    faults={}
    for fault in campaign['fault_plan']:
        if not isinstance(fault,dict) or set(fault)!={'fault_id','kind','target','parameters','expected_observation_sha256'} or fault['kind'] not in {'delay_gate_persistence','swap_artifact','stale_artifact','force_timeout','block_dependency'} or not re.fullmatch('[a-f0-9]{64}',fault['expected_observation_sha256']):raise ValueError('invalid protected fault declaration')
        if fault['fault_id'] in faults:raise ValueError('duplicate fault identity')
        if not isinstance(fault['target'],dict) or set(fault['target'])!={'node_id','artifact_type'} or any(v is not None and not isinstance(v,str) for v in fault['target'].values()) or not isinstance(fault['parameters'],dict):raise ValueError('invalid declared fault scope')
        faults[fault['fault_id']]=fault
    if any(c['fault_plan_ref'] is not None and c['fault_plan_ref'] not in faults for c in cases):raise ValueError('case fault was not frozen in campaign')
    for row in campaign['unavailable_modules']:
        if set(row)!={'module','status','reason'} or row['status'] not in {'blocked','not_applicable','scheduled_later'} or not isinstance(row['reason'],str) or not row['reason']:raise ValueError('unavailable module disposition missing')
    canonical(campaign)
    return campaign


def freeze_campaign(root,campaign,cases,module_map,*,referee_pins,judge_audit=None):
    root=Path(root)
    if root.name!=campaign['campaign_id'] or root.parent.name!='campaigns':
        raise ValueError('freeze into the registered BENCH_ROOT/campaigns/campaign_id directory')
    case_ids=[case['case_id'] for case in cases]
    if len(set(case_ids))!=len(case_ids):raise ValueError('duplicate frozen case identity')
    _validate_registry(module_map,case_ids)
    if campaign['retry_policy']!='none':raise ValueError('this integration foundation has no retries')
    if campaign['judge_config_ref'] is not None:
        from .oracles import judge_eligible
        if not judge_eligible(judge_audit):raise ValueError('conditional authoritative judge eligibility unavailable')
    registered=[];prepared=[]
    for case in cases:
        validate_visible_case(case)
        if case['case_id'] not in module_map:raise ValueError('module correlation missing')
        pin=referee_pins[case['case_id']]
        if case['referee_ref']!=pin:raise ValueError('protected independent referee binding is not frozen')
        raw=canonical(case);registered.append({'case_id':case['case_id'],'case_version':case['case_version'],'case_sha256':hashlib.sha256(raw).hexdigest()})
        prepared.append((root/'cases'/case['case_id']/'case.json',raw))
    if campaign['cases']!=registered:raise ValueError('campaign case hashes are not exact frozen visible bytes')
    validate_campaign(campaign,cases)
    _validate_fixture_bytes(root.parent.parent,cases)
    rows=schedule(campaign,[{**c,'module':module_map[c['case_id']]} for c in cases])
    for path,raw in prepared:write_once(path,raw)
    write_once(root/'module-map.json',module_map);write_once(root/'schedule.json',rows);write_once(root/'campaign.json',campaign)
    return rows
