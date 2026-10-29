from jiuwenswarm.research_sidecar.reports import build_report


def test_reproducible_denominators_and_no_fake_success():
    scores=[{'run_id':'a','campaign_id':'c','case_id':'secret_case','case_version':1,'oracle_version':'oracle:1','population':'completion_expected','result':'fail','launched':True,'scenario_id':'s01','split':'held_out','checks':[],'integrity_violations':[],'judged_weight_share':0,'metrics':[]}]
    a=build_report(scores,audience='public',report_id='r',generated_at='2026-10-16T00:00:00Z')
    assert a==build_report(scores,audience='public',report_id='r',generated_at='2026-10-16T00:00:00Z')
    assert a['populations']['completion_expected']['launched']==1
    assert a['populations']['completion_expected']['success']==0
    assert 'secret_case' not in str(a)
