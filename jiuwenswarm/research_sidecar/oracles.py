"""Independent frozen authority; product verifier output is only an observation."""
import math


def validate_mandatory_checks(checks):
    """Validate the frozen benchmark-referee:1 assertion population.

    Zero is a valid source weight, but it never makes a mandatory assertion
    optional. Empty/duplicate populations cannot establish independent success.
    """
    if not isinstance(checks, list) or not checks:
        raise ValueError('mandatory checks must be a nonempty array')
    seen = set()
    for check in checks:
        if (not isinstance(check, dict)
            or set(check) != {'check_id', 'kind', 'check_family', 'weight', 'description'}):
            raise ValueError('mandatory check fields differ from the frozen contract')
        from .cases import ID
        ident = check['check_id']
        if (not isinstance(ident, str) or not ID.fullmatch(ident) or ident in seen
            or check['kind'] not in {'deterministic', 'human_adjudicated', 'model_judged'}
            or not isinstance(check['check_family'], str) or not check['check_family']
            or not isinstance(check['description'], str) or not check['description']):
            raise ValueError('mandatory check identity or authority is invalid')
        weight = check['weight']
        if type(weight) not in (int, float) or weight < 0 or (type(weight) is float and not math.isfinite(weight)):
            raise ValueError('mandatory check weight must be finite and nonnegative')
        seen.add(ident)
    return checks


def judge_eligible(audit,required_families=()):
    if not isinstance(audit,dict):return False
    def eligible(row):
        return isinstance(row,dict) and all(isinstance(row.get(k),(int,float)) and not isinstance(row[k],bool) and math.isfinite(row[k]) and 0<=row[k]<.45 for k in ('false_pass_rate','upper_95'))
    return eligible(audit.get('overall')) and set(required_families)<=set(audit.get('families',{})) and all(eligible(x) for x in audit.get('families',{}).values())


def score_checks(checks,observations,*,judge_audit=None):
    validate_mandatory_checks(checks)
    if not isinstance(observations,dict):raise ValueError('independent observations must be an object')
    result=[];withheld=False
    families={x['check_family'] for x in checks if x['kind']=='model_judged'}
    judge_ok=judge_eligible(judge_audit,families)
    for check in checks:
        if check['kind'] not in {'deterministic','human_adjudicated','model_judged'} or not isinstance(check['weight'],(int,float)) or check['weight']<0:raise ValueError('invalid frozen check authority')
        observation=observations.get(check['check_id'])
        reason='independent evidence unavailable';status='unavailable'
        if check['kind']=='model_judged' and not judge_ok:withheld=True;reason='model-judged check withheld: eligibility audit absent or failed'
        elif check['kind']=='human_adjudicated' and (not observation or not observation.get('reviewer_a') or not observation.get('reviewer_b') or observation['reviewer_a']==observation['reviewer_b'] or observation.get('resolved') is not True):reason='two independent resolved reviewer labels required'
        elif observation is not None and isinstance(observation.get('passed'),bool):
            status='pass' if observation['passed'] else 'fail';reason=observation.get('reason','independent frozen oracle result')
        result.append({'check_id':check['check_id'],'kind':check['kind'],'check_family':check['check_family'],
            'status':status,'weight':check['weight'],'awarded':check['weight'] if status=='pass' else 0,
            'observed_evidence':observation.get('evidence',[]) if observation else [],'explanation':reason[:500]})
    return result,withheld
