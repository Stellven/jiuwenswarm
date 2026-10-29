import pytest
from jiuwenswarm.research_sidecar.cases import schedule,validate_case


def test_four_cases_small_frozen_schedule_and_no_retry():
    cases=[{'case_id':x,'case_version':1,'module':x,'variant_id':'baseline','repeat_policy':{'repeats':1,'stochastic':False}} for x in ('capsule','verifier','routing','rsi')]
    campaign={'campaign_id':'four_case_v1','repeats':1,'retry_policy':'none','configurations':[{'config_id':'fixed'}],'order':{'randomized':False,'order_seed':0}}
    rows=schedule(campaign,cases)
    assert len(rows)==4 and len({r['run_id'] for r in rows})==4
    with pytest.raises(ValueError):schedule({**campaign,'retry_policy':'on_failure'},cases)
