"""A route choice alone cannot establish an actual model call."""


def validate_evidence(route,calls):
    if route['decision_source'] in {'codex_router_disabled','codex_router_failed'}:
        if route['route_decision_ref'] is not None:raise ValueError('fixed route requires null API decision ref')
    elif route['decision_source']=='router':
        if not route['route_decision_ref']:raise ValueError('API choice requires canonical decision ref')
    else:raise ValueError('unknown decision source')
    linked=[c for c in calls if c.get('invocation_id')==route['invocation_id'] and c.get('purpose')=='task_execution' and c.get('observed_runtime') is True
        and c.get('identity',{}).get('requested')==route['model_id'] and c.get('route_decision_ref')==route['route_decision_ref'] and c.get('model_selection_profile_ref')]
    if not linked:raise ValueError('actual governed call evidence absent')
    if any(c.get('outcome')=='synthetic_example' for c in linked):raise ValueError('synthetic model call cannot satisfy integration')
    return True
