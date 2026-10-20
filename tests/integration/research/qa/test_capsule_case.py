from jiuwenswarm.research_sidecar.frozen_records import strict_json
from jiuwenswarm.research_sidecar.independent_oracles import evaluate_checks


def test_actual_screening_gate_and_independent_score(frozen_campaign,actual_runs,label_for_case):
    assert frozen_campaign['check']=='M1-QA/V04'
    for row,case,run,folder,frozen in actual_runs('capsule'):
        assert frozen.of_kind('route-record') and frozen.of_kind('model-call')
        assert any(g['scope_kind']=='node' and g['action']=='advance' for g in [e['record'] for e in frozen.of_kind('gate-decision')])
        bench_root=frozen_campaign['root'].parent.parent
        score=strict_json((bench_root/'scores'/run['campaign_id']/run['run_id']/case['oracle_version']/'score_record.json').read_bytes())
        assert score['result']=='success' and score['checks'] and all(c['status']=='pass' for c in score['checks'])
        assert any(c['kind']=='deterministic' for c in score['checks'])
        label=label_for_case(case);observations=evaluate_checks(label,frozen,run,folder)
        assert all(c['check_id'] in observations and observations[c['check_id']]['passed'] for c in label['mandatory_checks'] if c['kind']=='deterministic')
