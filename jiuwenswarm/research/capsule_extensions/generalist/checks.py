"""Host checks bind output task text to the original frozen work contract."""
from ...contracts import ResearchError
from ..packet import inherited, validate_packet
from .expression import evaluate


def check(ctx, inputs, outputs):
    schema = integrity = False
    try:
        original, result = inputs['packet'], outputs['result']
        validate_packet(result)
        schema = True
        contract = ctx.contract
        expected = {'schema': 'ai4r-generalist-task:1', 'objective': contract['objective'],
            'requirement_ids': contract['requirement_ids'], 'policy_ref': contract['policy_ref'],
            'node_contract_ref': contract['node_contract_ref'], 'node_id': contract['node_id'], 'attempt_id': contract['attempt_id']}
        execution = result['data']['generalist_execution']
        expression = execution['expression']
        actual = evaluate(expression, original['data'], {f['path']: f['text'] for f in original['files']}) if expression is not None else None
        contract_ref = ctx.observation.get('contract_ref')
        integrity = (inherited(original, result) and result['trust'] == 'low'
            and result['data']['generalist_task'] == expected
            and execution == {'expression': expression, 'status': 'executed' if expression is not None else 'not_requested', 'result': actual}
            and contract_ref is not None and contract_ref in result['provenance'])
    except (ResearchError, KeyError, TypeError, ValueError):
        pass
    return [{'check_id': key, 'outcome': 'PASS' if ok else 'FAIL', 'reason': reason, 'evidence_refs': list(ctx.output_refs.values())}
        for key, ok, reason in [('packet_schema', schema, 'Bounded file/data envelope and exact digests'),
            ('packet_integrity', integrity, 'Frozen task identity, original input, actual expression result and low-trust provenance')]]
