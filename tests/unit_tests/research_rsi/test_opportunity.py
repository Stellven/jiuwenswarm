from jiuwenswarm.research_rsi.opportunity import decide


def test_measured_opportunity_and_honest_no_attempt():
    kw=dict(attribution='implementation',symptom_reproduced=True,mandatory_passed=True,headroom=.1,headroom_minimum=.1,diagnosis=dict(cause='c',alternatives=['a'],falsification='f'))
    assert decide(**kw)['decision']=='START'
    assert decide(**{**kw,'headroom':None})['decision']=='NO_ATTEMPT'
    assert decide(**{**kw,'attribution':'uncertain'})['decision']=='NEEDS_REVIEW'
    assert decide(**{**kw,'resource_ready':False})['readiness']=='BLOCKED'
