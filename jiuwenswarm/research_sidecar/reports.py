"""Deterministic coverage reports from frozen score records only."""
from collections import Counter
import hashlib
from .evidence import canonical


def build_report(scores,*,audience,report_id,generated_at,pins=None,source_scores=(),case_metadata=None):
    if audience not in {'public','referee'} or not scores:raise ValueError('report audience/population invalid')
    scores=sorted(scores,key=lambda s:(s['campaign_id'],s['run_id'],s['oracle_version']))
    if len({(s['run_id'],s['oracle_version']) for s in scores})!=len(scores):raise ValueError('duplicate score population')
    populations={'completion_expected':{'launched':0,'success':0,'readiness_blocked':0},'expected_stop':{'launched':0,'met':0},'isolated_module':{'launched':0}}
    families={};violations=Counter();case_metadata=case_metadata or {}
    for s in scores:
        launch=next((bool(m['numerator']) for m in s.get('metrics',[]) if m['metric_id']=='launched'),s.get('launched',s['result']!='unavailable'))
        pop=populations[s['population']];pop['launched']+=launch
        if s['population']=='completion_expected':pop['success']+=s['result']=='success';pop['readiness_blocked']+=not launch
        if s['population']=='expected_stop':pop['met']+=s['result']=='expected_behavior_met'
        metadata=case_metadata.get(s['case_id'],{});family=metadata.get('scenario_id',s.get('scenario_id','unavailable'))
        row=families.setdefault(family,{'scenario_id':family,'milestone':'m1','classification':metadata.get('classification','core_m1_acceptance'),'status':'incomplete','case_count':0,'repeats':0,'metrics':[]})
        row['case_count']+=1;row['repeats']+=1
        for violation in s['integrity_violations']:violations[violation['kind']]+=not violation['attempted_only']
    known=['Four-case tooling does not establish complete M1 Phase 1, all ten verifier cases, dynamic routing savings, RSI improvement or transfer.']
    for module in ('planner','long_horizon','whole_workflow'):known.append(module+': scheduled_later in this bounded tooling campaign')
    report={'schema':'benchmark-report:1','report_id':report_id,'report_format_version':'report-format:1','audience':audience,'generated_at':generated_at,
        'campaign_ids':sorted({s['campaign_id'] for s in scores}),'milestone':'m1','baseline_campaign_id':None,
        'comparability':{'comparable_case_keys':[],'excluded':[]},'pins':pins or {},
        'hardware_summary':{'inventory_count':0,'hosts':[],'profiles':[],'blocked_count':sum(s['result']=='unavailable' for s in scores),'differences':['Host inventory aggregation is unavailable unless separately linked.']},
        'populations':populations,'family_rows':list(families.values()),
        'metric_row':{'metric_id':'coverage','scope':'four_case','numerator':None,'denominator':None,'value':None,'ci_low':None,'ci_high':None,'ci_method':'none','n_clusters':0,'status':'unavailable','reason':'No registered cross-family overall score.'},
        'm1_checklist':[{'prd_case_number':i,'case_key':None,'expected':None,'observed':None,'result':'unresolved','action_observed':None} for i in range(1,11)],
        'verifier_confusion':None,'judged_share':{'overall_weight_share':sum(s['judged_weight_share'] for s in scores)/len(scores),'per_score':[] if audience=='public' else [{'run_id':s['run_id'],'weight_share':s['judged_weight_share']} for s in scores]},
        'integrity_gates':[{'gate':kind,'violations':n,'attempted':0,'status':'fail' if n else 'pass'} for kind,n in sorted(violations.items())],
        'comparisons':[],'failures':[],'known_gaps':known,'source_scores':list(source_scores) if audience=='referee' else [hashlib.sha256(canonical(scores)).hexdigest()]}
    if audience=='referee':report['comparability']['comparable_case_keys']=sorted({f"{s['case_id']}@{s['case_version']}@{s['oracle_version']}" for s in scores})
    return report


def markdown(report):
    lines=['# Four-case benchmark coverage','',f"Audience: {report['audience']}",'','| Population | Launched | Successful / met |','| --- | ---: | ---: |']
    for key,value in report['populations'].items():lines.append(f"| {key} | {value['launched']} | {value.get('success',value.get('met','unavailable'))} |")
    lines.extend(['','Coverage gaps:']+['- '+gap for gap in report['known_gaps']])
    return '\n'.join(lines)+'\n'
