"""A security halt is terminal; human clearance applies only to a new session."""


def validate_clearance(record,*,halted_operator,authorized_reviewers,validate):
    validate('security-clearance',record)
    if record['actor_id']==halted_operator or record['actor_id'] not in authorized_reviewers:raise ValueError('independent authorized security reviewer required')
    if record['decision']!='cleared' or record['effect_scope']!='new_rsi_session_only':raise ValueError('clearance does not authorize a new session')
    if not record['violation_refs'] or not record['guardrail_evidence_refs'] or not record['remediation_ref']:raise ValueError('clearance evidence incomplete')
    return True


class SessionClearance:
    """Only a policy pinned by protected startup can authorize incident clearance.

    A job/model cannot nominate reviewers or supply its own clearance Ref. The
    existing security-clearance record remains the human decision authority;
    this private policy captures the authenticated owner's approved originals.
    """
    def __init__(self,store,policy_ref=None):self.store,self.policy_ref=store,policy_ref
    def require(self,session_id):
        from datetime import datetime
        from .session_policy import validate_private
        from jiuwenswarm.research_records.contracts import ContractData
        incidents=self.store.security_halts()
        if not incidents:return True
        if any(row['session_id']==session_id for row in incidents):raise ValueError('Security-halted session cannot resume')
        if self.policy_ref is None:raise ValueError('Independent security clearance required before a new session')
        policy=self.store.get(self.policy_ref)
        validate_private('urn:ai4r:private:rsi-clearance-policy:1',policy)
        validate=ContractData().validate
        clearances=[(pin,self.store.get(pin)) for pin in policy['clearance_refs']]
        approvals=[]
        for row in incidents:
            incident=self.store.get(row['incident_ref'])
            validate_private('urn:ai4r:private:rsi-security-incident:1',incident)
            if incident['session_id']!=row['session_id']:raise ValueError('Security clearance incident index differs')
            matches=[(pin,value) for pin,value in clearances if value.get('halted_session_id')==row['session_id']]
            if len(matches)!=1:raise ValueError('Unambiguous independently approved security clearance required')
            pin,record=matches[0]
            validate_clearance(record,halted_operator=incident['operator_id'],
                authorized_reviewers=set(policy['authorized_reviewers']),validate=validate)
            if row['incident_ref'] not in record['violation_refs']:raise ValueError('Security clearance omits the original incident')
            if datetime.fromisoformat(record['recorded_at'].replace('Z','+00:00'))<datetime.fromisoformat(incident['recorded_at'].replace('Z','+00:00')):
                raise ValueError('Security clearance predates the incident')
            for ref in [*record['violation_refs'],record['remediation_ref'],*record['guardrail_evidence_refs']]:self.store.read(ref)
            approvals.append((row['session_id'],row['incident_ref'],pin))
        self.store.record_clearances(approvals)
        return True
