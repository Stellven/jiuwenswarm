"""A security halt is terminal; human clearance applies only to a new session."""


def validate_clearance(record,*,halted_operator,authorized_reviewers,validate):
    validate('security-clearance',record)
    if record['actor_id']==halted_operator or record['actor_id'] not in authorized_reviewers:raise ValueError('independent authorized security reviewer required')
    if record['decision']!='cleared' or record['effect_scope']!='new_rsi_session_only':raise ValueError('clearance does not authorize a new session')
    if not record['violation_refs'] or not record['guardrail_evidence_refs'] or not record['remediation_ref']:raise ValueError('clearance evidence incomplete')
    return True
