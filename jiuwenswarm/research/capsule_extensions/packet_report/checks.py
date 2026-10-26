"""Independent output reconstruction from the exact original packet."""
from ...contracts import ResearchError
from ..packet import inherited, validate_packet
from .worker import render


def check(ctx, inputs, outputs):
    schema = integrity = False
    try:
        source, result = inputs['packet'], outputs['result']
        validate_packet(source)
        validate_packet(result)
        schema = True
        expected = render(source)
        integrity = result == expected and inherited(source, result)
    except (ResearchError, KeyError, ValueError, TypeError):
        pass
    return [{'check_id': key, 'outcome': 'PASS' if okay else 'FAIL', 'reason': reason,
        'evidence_refs': list(ctx.output_refs.values())} for key, okay, reason in [
        ('result_schema', schema, 'Output matches the exact work-packet v1 envelope'),
        ('result_integrity', integrity, 'Input bytes, selected fields, hashes and low trust are preserved')]]
