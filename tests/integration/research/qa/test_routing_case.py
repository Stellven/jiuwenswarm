from jiuwenswarm.research_sidecar.adapters.routing import validate_evidence


def test_actual_route_and_governed_call(frozen_campaign,actual_runs):
    assert frozen_campaign['check']=='M1-QA/V07'
    routes=[]
    for row,case,run,folder,frozen in actual_runs('routing'):
        calls=[e['record'] for e in frozen.of_kind('model-call')]
        for envelope in frozen.of_kind('route-record'):
            route=envelope['record'];validate_evidence(route,calls);routes.append(route)
        assert frozen.of_kind('route-record') and calls
    assert any(r['decision_source']=='codex_router_disabled' and r['route_decision_ref'] is None for r in routes)
