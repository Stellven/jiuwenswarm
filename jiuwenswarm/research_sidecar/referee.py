"""Offline scorer, with no client import, token, or product API access."""
import math
import re
from fractions import Fraction

from .cases import ID
from .oracles import score_checks,judge_eligible,validate_mandatory_checks


REFEREE_FIELDS = set('label_id case_id case_version expected_outcome expected_tier_verdicts prd_case_number valid_capsule_choices dependency_obligations mandatory_checks rubric primary_metric secondary_metrics failure_conditions reference_reasons labels judge_audit_ref'.split())


def _text(value):
    return isinstance(value,str) and bool(value)


def _closed(value,keys):
    if not isinstance(value,dict) or set(value)!=set(keys):raise ValueError('referee fields differ from the frozen contract')


def validate_referee(label):
    """The assigned benchmark-runner.md Referee part, without extra fields.

    This validates independent source data, not a product verdict or an oracle
    qualification. Its source version has no runtime oracle_version field.
    """
    if not isinstance(label,dict):raise ValueError('referee must be an object')
    validate_mandatory_checks(label.get('mandatory_checks'))
    _closed(label,REFEREE_FIELDS)
    if (any(not isinstance(label[k],str) or not ID.fullmatch(label[k]) for k in ('label_id','case_id'))
        or type(label['case_version']) is not int or label['case_version']<1):
        raise ValueError('referee case identity is invalid')
    expected=label['expected_outcome']
    _closed(expected,('population','expected_terminal','expected_halt_decision'))
    if (expected['population'] not in {'completion_expected','expected_stop','isolated_module'}
        or expected['expected_terminal'] not in {'complete','halt'}
        or (expected['expected_terminal']=='complete' and expected['expected_halt_decision'] is not None)
        or (expected['expected_terminal']=='halt' and not _text(expected['expected_halt_decision']))):
        raise ValueError('referee expected outcome is invalid')
    tiers=label['expected_tier_verdicts']
    if tiers is not None:
        _closed(tiers,('tier1','tier2','advance','downstream_action'))
        if (not _text(tiers['tier1']) or not _text(tiers['tier2']) or type(tiers['advance']) is not bool
            or tiers['downstream_action'] not in {'advance','locked','halt'}
            or tiers['advance']!=(tiers['downstream_action']=='advance')):
            raise ValueError('referee tier/action expectation is invalid')
    number=label['prd_case_number']
    if number is not None and (type(number) is not int or not 1<=number<=10):raise ValueError('invalid source PRD case number')
    choices=label['valid_capsule_choices']
    if not isinstance(choices,list):raise ValueError('valid Capsule choices must be an array')
    identities=set()
    for choice in choices:
        _closed(choice,('capsule_id','capsule_version'))
        if any(not _text(v) for v in choice.values()):raise ValueError('invalid Capsule choice')
        identity=(choice['capsule_id'],choice['capsule_version'])
        if identity in identities:raise ValueError('duplicate Capsule choice')
        identities.add(identity)
    for key in ('dependency_obligations','secondary_metrics','failure_conditions','reference_reasons'):
        if not isinstance(label[key],list) or any(not _text(v) for v in label[key]):raise ValueError('referee string array is invalid')
    if not _text(label['primary_metric']):raise ValueError('referee primary metric is absent')
    if label['judge_audit_ref'] is not None and not _text(label['judge_audit_ref']):raise ValueError('invalid judge audit reference')
    if not isinstance(label['labels'],dict) or any(k not in {c['check_id'] for c in label['mandatory_checks']} for k in label['labels']):
        raise ValueError('ground truth is not keyed by declared check identity')
    rubric=label['rubric']
    if rubric is not None:
        _closed(rubric,('rubric_id','criteria'))
        if not _text(rubric['rubric_id']) or not isinstance(rubric['criteria'],list):raise ValueError('invalid referee rubric')
        ids=set();total=Fraction(0)
        for criterion in rubric['criteria']:
            _closed(criterion,('criterion_id','weight'))
            ident=criterion['criterion_id'];weight=criterion['weight']
            if (not _text(ident) or ident in ids or type(weight) not in (int,float) or weight<0
                or (type(weight) is float and not math.isfinite(weight))):raise ValueError('invalid rubric criterion or weight')
            ids.add(ident);total+=Fraction(str(weight))
        if total!=1:raise ValueError('rubric weights must sum to one')
    return label


def score_run(run,label,observations,*,scored_at,oracle_version=None,referee_version='m1:1',judge_audit=None,integrity_violations=()):
    validate_referee(label)
    if not isinstance(oracle_version,str) or not re.fullmatch('oracle:[1-9][0-9]*',oracle_version):raise ValueError('frozen runtime oracle version is required')
    if (not isinstance(run,dict) or type(run.get('case_version')) is not int or type(run.get('launched')) is not bool
        or run.get('population')!=label['expected_outcome']['population']):raise ValueError('run identity/population differs from its frozen referee')
    if (run['case_id'],run['case_version'])!=(label['case_id'],label['case_version']):raise ValueError('referee label binding mismatch')
    checks,withheld=score_checks(label['mandatory_checks'],observations,judge_audit=judge_audit)
    passed=all(x['status']=='pass' for x in checks) and not any(not x['attempted_only'] for x in integrity_violations)
    unavailable=not run['launched']
    expected=label['expected_outcome'];expected_stop=expected['expected_terminal']=='halt'
    if unavailable:result='unavailable'
    elif expected_stop:
        met=run['outcome'] in {'failed','blocked'} and run['outcome_detail']['product_decision']==expected['expected_halt_decision'] and passed
        result='expected_behavior_met' if met else 'expected_behavior_missed'
    else:result='success' if run['outcome']=='completed' and passed and not withheld else 'fail'
    shares={k:{'count':0,'weight':0,'awarded':0} for k in ('deterministic','human_adjudicated','model_judged')}
    for c in checks:
        s=shares[c['kind']];s['count']+=1;s['weight']+=c['weight'];s['awarded']+=c['awarded']
    total=sum(c['weight'] for c in checks);judged=shares['model_judged']['weight']
    return {'schema':'score-record:1',**{k:run[k] for k in ('run_id','campaign_id','case_id','case_version','population')},
        'oracle_version':oracle_version,'scored_at':scored_at,'referee_version':referee_version,'result':result,
        'result_reason':'All mandatory independent checks passed.' if result in {'success','expected_behavior_met'} else 'Required evidence, behavior or independent checks did not establish success.',
        'checks':checks,'integrity_violations':list(integrity_violations),'earliest_failure':None,'affected_obligations':[],
        'judge':{'used':judged>0,'judge_config_sha256':None,'audit_ref':label.get('judge_audit_ref'),'eligible':judge_eligible(judge_audit) if judged else None,'judge_model_calls':0,'judge_cost':None},
        'component_shares':shares,'judged_weight_share':judged/total if total else 0,'outcome_depends_on_judged':judged>0,'withheld':withheld,
        'verifier_confusion':None,'metrics':[{'metric_id':'launched','numerator':int(run['launched']),'denominator':1,'value':int(run['launched']),'status':'measured'}],
        'hardware_diff':None,'improvement_direction':'' if passed else 'Inspect the first failed obligation and its immutable evidence before changing implementation.','supersedes':None}
