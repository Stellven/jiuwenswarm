"""Independent deterministic proof of the exact summary-to-packet projection."""
from ...contracts import ResearchError
from ..packet import inherited, validate_packet
from .worker import convert


def check(ctx, inputs, outputs):
    schema = integrity = False
    try:
        expected = convert(inputs['summary'])
        actual = outputs['result']
        validate_packet(actual)
        schema = True
        integrity = actual == expected and inherited(expected, actual)
    except (ResearchError, KeyError, TypeError, ValueError):
        pass
    return [{'check_id': key, 'outcome': 'PASS' if okay else 'FAIL', 'reason': reason,
        'evidence_refs': list(ctx.output_refs.values())} for key, okay, reason in [
        ('result_schema', schema, 'Output matches the exact work-packet v1 envelope'),
        ('result_integrity', integrity, 'Summary, brief/document/source refs, citations, hashes and low trust are preserved')]]
