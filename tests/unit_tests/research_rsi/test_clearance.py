import pytest
from jiuwenswarm.research_rsi.clearance import validate_clearance


def test_independent_authorized_reviewer_new_session_only():
    record={'actor_id':'reviewer','decision':'cleared','effect_scope':'new_rsi_session_only','violation_refs':['v'],'guardrail_evidence_refs':['g'],'remediation_ref':'r'}
    assert validate_clearance(record,halted_operator='operator',authorized_reviewers={'reviewer'},validate=lambda n,v:None)
    with pytest.raises(ValueError):validate_clearance(record,halted_operator='reviewer',authorized_reviewers={'reviewer'},validate=lambda n,v:None)
    with pytest.raises(ValueError):validate_clearance({**record,'effect_scope':'live_plans'},halted_operator='operator',authorized_reviewers={'reviewer'},validate=lambda n,v:None)
