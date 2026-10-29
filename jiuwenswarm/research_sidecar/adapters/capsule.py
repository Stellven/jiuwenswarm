"""Finite E1 Screening qualification, deliberately distinct from E3 execution."""


PROFILE='qa_capsule_screening_v1'


def submission(base,readiness):
    if readiness['evaluation_profile']!=PROFILE:raise ValueError('entry_point_unavailable: qualified Screening E1 profile absent')
    return {**base,'profile_id':PROFILE,'interaction_mode':'headless','plan_source':'static'}


def validate_evidence(records):
    if records.get('mode')!='actual' or not records.get('work_observations') or not records.get('outputs') or not records.get('deterministic_checks'):raise ValueError('actual Screening work/output/check evidence required')
    decisions=records.get('gates',[])
    if not any(x.get('scope_kind')=='node' and x.get('action')=='advance' for x in decisions):raise ValueError('E3 or output-only evidence cannot establish Capsule node gate')
    if not records.get('verifier_observations') or not records.get('accepted_outputs'):raise ValueError('independent verifiers and committed outputs required')
    return True
