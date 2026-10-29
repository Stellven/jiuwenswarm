"""Offline independent scoring. This module never invokes models or repairs answers."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from benchmarks.harbor_suite.contracts import pin, read_json, strict_json
from .protocol import PROTOCOL, load_plan


def equal(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual)==set(expected) and all(equal(actual[k],v) for k,v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual)==len(expected) and all(equal(a,b) for a,b in zip(actual,expected))
    if type(expected) in (float,int):
        return type(actual) in (float,int) and math.isfinite(actual) and actual==expected
    return type(actual) is type(expected) and actual==expected


def wilson(passed, total):
    if not total: return None
    z=1.959963984540054; p=passed/total
    return (p+z*z/(2*total)-z*math.sqrt(p*(1-p)/total+z*z/(4*total*total)))/(1+z*z/total)


def original(root, ref):
    digest=ref['sha256']
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('Invalid original digest')
    path=root/'capture/artifacts/sha256'/digest[:2]/digest
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('Symlink original record')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError('Original captured bytes changed')
    return strict_json(raw)


def validate_observation(root, value):
    """Join complete captured bridge effects, never trust summary booleans."""
    from jiuwenswarm.research_records.contracts import ContractData
    contracts=ContractData()
    rows=value['records']; indexed={}
    for row in rows:
        ref=row['ref']; key=(ref['id'],ref['sha256'])
        if key in indexed or original(root,ref)!=row['record']:
            raise ValueError('Duplicate or changed original record')
        indexed[key]=row
        if row['kind'] in {'model-call','route-record'}:
            contracts.validate(row['kind'],row['record'])
    calls=[r for r in rows if r['kind']=='model-call']
    if calls!=value['model_calls']:
        raise ValueError('Model call summary omitted or changed original calls')
    if [r for r in rows if r['kind']=='automatic-route-decision']!=value['decisions']:
        raise ValueError('Decision summary differs from original decisions')
    claims=[r for r in rows if r['kind']=='model-call-claim']
    if len({r['record']['call_id'] for r in claims})!=len(claims):
        raise ValueError('Duplicate call claims')
    if {r['record']['call_id'] for r in claims}!={r['record']['id'] for r in calls}:
        raise ValueError('Unresolved claim; complete expense/call inventory unavailable')
    routes={r['record']['route_id']:r for r in rows if r['kind']=='route-record'}
    starts={r['record']['call_id']:r['record'] for r in rows if r['kind']=='model-call-start'}
    for row in calls:
        call=row['record']; start=starts[call['id']]; route=routes[start['route_id']]['record']
        if (call['observed_runtime'] is not True or call['invocation_id']!=route['invocation_id']
                or call['identity']['requested']!=route['model_id']
                or call['route_decision_ref']!=route['route_decision_ref']):
            raise ValueError('Actual call and route identities do not join')
        if call['outcome']=='completed' and call['identity']['effective']!=call['identity']['requested']:
            raise ValueError('Effective model attribution missing')
    if value.get('worker'):
        callrow=indexed[(value['worker']['call_ref']['id'],value['worker']['call_ref']['sha256'])]
        payloads=[r['record'] for r in rows if r['kind']=='model-call-output'
            and r['record']['call_id']==callrow['record']['id']]
        if len(payloads)!=1 or payloads[0]['text']!=value['worker']['text']:
            raise ValueError('Answer is not the actual original call output')
    reviewers=[r['record'] for r in calls if r['record']['call_function']=='verifier']
    snapshot=original(root,value['pool_ref'])
    qwen=next(c['model_id'] for c in snapshot['candidates'] if c['preset_id']=='qwen')
    if any(r['identity']['requested']!=qwen for r in reviewers):
        raise ValueError('Verifier switched from fixed Qwen')
    return calls


def score(workspace):
    workspace=Path(workspace).absolute(); plan=load_plan(workspace)
    results=[]
    for job in plan['cases']:
        reviewer=Path(plan['reviewer_directory'])
        if reviewer==workspace or reviewer.is_relative_to(workspace):
            raise ValueError('Reviewer criteria must be outside the inference workspace')
        if pin(reviewer/(job['case_id']+'.json')) != plan['reviewer_pins'][job['case_id']]:
            raise ValueError('Independent reviewer criteria changed')
        criteria=read_json(reviewer/(job['case_id']+'.json'))
        arms=[('calibration',t) for t in plan['executor_pool']]+[('fixed','qwen'),('routed',None)] if job['case_id']=='mr01-quality' else [('routed',None)]
        for phase,tier in arms:
            for repeat in range(plan['repeats']):
                key=job['variant_id']+'-'+phase+'-'+str(tier or 'auto')+'-r'+str(repeat)
                root=workspace/'runs'/key
                row={'case_id':job['case_id'],'variant_id':job['variant_id'],'phase':phase,'tier':tier,
                    'repeat':repeat,'status':'unavailable','exact_answer':None,'gated_exact_answer':None,
                    'disposition_correct':None,'calls':0,'usage_by_role':{},'cost':None,'savings':None,'reason':None}
                if not (root/'result.json').is_file():
                    row['reason']='Scheduled observation missing'; results.append(row); continue
                value=read_json(root/'result.json'); row['reason']=value.get('reason')
                if value['status']=='unavailable':
                    results.append(row); continue
                try:
                    calls=validate_observation(root,value)
                    assignment=original(root,value['assignment_ref'])
                    if assignment!={'protocol':PROTOCOL,'declaration':job['declaration'],'task':job['task'],
                            'input_sha256':[x['sha256'] for x in job['inputs']],'limits':plan['limits']}:
                        raise ValueError('Observation differs from frozen public assignment')
                    row.update(status='observed', calls=len(calls), elapsed_s=value['elapsed_s'],gate=value['gate'])
                    for r in calls:
                        call=r['record']; role=call['call_function']; usage=call['usage']
                        bucket=row['usage_by_role'].setdefault(role,{'calls':0,'input_tokens':0,'output_tokens':0})
                        bucket['calls']+=1
                        for name in ('input_tokens','output_tokens'):
                            bucket[name]=None if bucket[name] is None or usage[name] is None else bucket[name]+usage[name]
                    decisions=[r['record'] for r in value['decisions'] if r['record']['subnode_id']=='worker']
                    worker_calls=[r['record'] for r in calls if r['record']['call_function']=='worker']
                    if len(worker_calls)!=1 or len(decisions)!=1:
                        raise ValueError('One original worker call and decision required; no replay/switch allowed')
                    decision=decisions[0]; row['selected_preset']=decision['selected_candidate_id']
                    row['selection_method']=decision['selection_method']
                    if job['case_id']=='mr01-quality':
                        expected=criteria['variants'][job['variant_id']]['answer']
                        try: actual=strict_json(value['worker']['text']) if value.get('worker') else None
                        except ValueError: actual=None
                        row['exact_answer']=equal(actual,expected)
                        row['gated_exact_answer']=row['exact_answer'] and value['gate']=='advance'
                        if phase!='routed' and decision['selected_candidate_id']!='local:'+str(tier):
                            raise ValueError('Calibration/fixed arm used a different model')
                    else:
                        fault=job['fault']; call=worker_calls[0]
                        if fault=='context-window':
                            correct=(any(e['candidate_id']=='local:e4b' and e['reason']=='CONTEXT_EXCEEDED' for e in decision['exclusions'])
                                and decision['selected_candidate_id']!='local:e4b' and call['outcome']=='completed')
                        elif fault=='endpoint-unavailable':
                            correct=(any(e['preset']=='e4b' and e['fault']=='http_503' and not e['forwarded'] for e in value['fault_events'])
                                and decision['selected_candidate_id']!='local:e4b' and call['outcome']=='completed')
                        elif fault=='router-timeout':
                            correct=(decision['selection_method']=='compatible_baseline' and decision['selector_failure']=='timeout'
                                and decision['selected_candidate_id']=='local:qwen' and call['outcome']=='completed'
                                and any(e['role']=='selection' and e['fault']=='delayed_response' and not e['forwarded'] for e in value['fault_events']))
                        else:
                            error='rate_limited' if fault=='provider-quota' else 'timeout'
                            correct=(call['outcome'] in {'failed','outcome_unknown'} and call['provider_error_code'] in {error,None}
                                and value.get('worker') is None and value['gate']=='not_run'
                                and sum(e['method']=='POST' and e['role']=='task' for e in value['fault_events'])==1
                                and any(e['role']=='task' and e['fault']==('http_429' if error=='rate_limited' else 'delayed_response')
                                    and not e['forwarded'] for e in value['fault_events']))
                        row['disposition_correct']=correct
                except (ValueError,KeyError,TypeError,OSError) as error:
                    row.update(status='invalid_evidence',reason=str(error),exact_answer=None,disposition_correct=None)
                results.append(row)
    domains=[]
    for job in plan['cases']:
        if job['case_id']!='mr01-quality': continue
        group=[r for r in results if r['variant_id']==job['variant_id']]
        stats={}
        for phase,tier in [('calibration',t) for t in plan['executor_pool']]+[('fixed','qwen'),('routed',None)]:
            arm=[r for r in group if r['phase']==phase and r['tier']==tier]
            passed=sum(r['exact_answer'] is True for r in arm)
            stats[phase+':'+str(tier or 'auto')]={'passed':passed,'denominator':plan['repeats'],
                'observed':sum(r['status']=='observed' for r in arm), 'wilson95_lower':wilson(passed,plan['repeats'])}
        for tier in plan['executor_pool']:
            stat=stats['calibration:'+tier]
            stat['qualifying']=(plan['mode']=='campaign' and stat['observed']==3 and stat['passed']==3
                and stat['wilson95_lower']>=0.4)
        fixed=stats['fixed:qwen']; routed=stats['routed:auto']
        complete=(plan['mode']=='campaign' and all(s['observed']==3 for s in stats.values()))
        routed_rows=[r for r in group if r['phase']=='routed' and r.get('selected_preset')]
        domains.append({'variant_id':job['variant_id'],'arms':stats,'comparison_complete':complete,
            'quality_delta':(routed['passed']-fixed['passed'])/plan['repeats'] if complete else None,
            'insufficient_tier_choices':sum(not stats['calibration:'+r['selected_preset'].split(':')[1]]['qualifying'] for r in routed_rows) if complete else None,
            'routed_choice_denominator':plan['repeats'],'monetary_regret':None,'quality_preserving_savings':None})
    return {'schema':PROTOCOL,'mode':plan['mode'],'scope':plan['scope'],'commit':plan['commit'],
        'repeated_measurement_protocol':plan['mode']=='campaign' and plan['repeats']==3,
        'quality_comparison_complete':bool(domains) and all(d['comparison_complete'] for d in domains),
        'original_benchmark_acceptance':'not_established','cost':None,'savings':None,
        'cost_unavailable_reason':plan['cost_policy'],'rows':results,'domains':domains,
        'scheduled':len(results),'observed':sum(r['status']=='observed' for r in results)}
