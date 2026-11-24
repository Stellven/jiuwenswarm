"""Standalone CC native transport; standard library only, no factory API bridge."""
import json
import sys
from components import TOOLS

MAX_BYTES = 32 * 1024 * 1024


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('nonfinite JSON constant')


try:
    raw = sys.stdin.buffer.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('request exceeds 32MiB')
    packet = json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=reject_constant)
    capability = packet['capability']
    if capability not in TOOLS or type(packet['inputs']) is not dict:
        raise ValueError('unsupported capability or inputs')
    output = TOOLS[capability](**packet['inputs'])
    result = {'outcome': 'ok', 'outputs': {'result': output}}
except (ValueError, TypeError, KeyError, OverflowError, RecursionError, OSError) as exc:
    result = {'outcome': 'error', 'error': {'code': 'INVALID_NUMERICAL_INPUT', 'message': str(exc)[:300]}}
print(json.dumps(result, allow_nan=False, separators=(',', ':'), sort_keys=True))
