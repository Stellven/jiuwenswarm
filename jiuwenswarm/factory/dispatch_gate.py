"""A task-pinned, sealed dispatch check gates all candidate work."""

import json


def checked_trace(store, task_id, checkpoint, nodes):
    from .node_check import accepted_output

    host = getattr(store, '_store', store)
    trace = nodes.get(checkpoint['node_id'])
    if trace is None:
        raise ValueError('Dispatch checkpoint node is missing')
    check = accepted_output(host, task_id, trace, checkpoint['output'])
    verifier = check.get('verifier') or {}
    artifact = verifier.get('sealed_artifact')
    if not artifact or artifact not in check.get('source_artifacts', []):
        raise ValueError('Dispatch checkpoint has no sealed result linked to the accepted check')
    result = json.loads(host.artifact_bytes(task_id, artifact))
    state = result.get('eligibility') if isinstance(result, dict) else None
    if state not in ('eligible', 'already_batched', 'no_eligible_shapes', 'unresolved'):
        raise ValueError('Dispatch checkpoint sealed an unknown eligibility')
    if result.get('may_build') is not (state == 'eligible'):
        raise ValueError('Dispatch checkpoint eligibility and build permission disagree')
    return check, result


def require_eligible(store, task_id, checkpoint, nodes):
    _, result = checked_trace(store, task_id, checkpoint, nodes)
    if not result['may_build']:
        raise ValueError(f"Dispatch checkpoint refused candidate work: {result['eligibility']}")


def validate_terminal(store, task_id, checkpoint, decision):
    from .taskgraph import plan_get

    action = decision.get('action') or {}
    kind = action.get('type')
    if kind not in {'stop_missing_prerequisite', 'accept', 'reject', 'report_inconclusive'}:
        return
    nodes = {node['node_id']: node for node in plan_get(store, task_id)['nodes']}
    check, result = checked_trace(store, task_id, checkpoint, nodes)
    state = result['eligibility']
    if kind == 'accept':
        raise ValueError('Factory delivery is not a target lab acceptance verdict')
    if state == 'eligible':
        if kind == 'stop_missing_prerequisite':
            raise ValueError('A positive dispatch checkpoint cannot be reported as a missing dispatch prerequisite')
        return
    if kind != 'stop_missing_prerequisite':
        raise ValueError('Close the dispatch checkpoint with stop_missing_prerequisite and cite the sealed trace')
    if (action.get('eligibility') != state or check['obs_id'] not in decision.get('evidence_ids', [])
            or not str(action.get('reason') or '').strip()):
        raise ValueError('A dispatch stop must state the sealed eligibility, explain it, and cite its accepted node check')
