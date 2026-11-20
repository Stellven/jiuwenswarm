"""CC v2 entry point for routing-profile analysis."""
import json
import sys

from routing_profile import analyze, verify


def dispatch(packet):
    inputs = packet['inputs']
    artifacts = {name: inputs[name] for name in ('before', 'after', 'tensor_index')}
    request = {
        **inputs['configuration'],
        **{name: artifact['path'] for name, artifact in artifacts.items()},
        'sha256': {name: artifact['sha256'] for name, artifact in artifacts.items()},
    }
    capability = packet['capability']
    if capability == 'analyze':
        return {'report': analyze(request)}
    if capability == 'verify':
        return {'verified': verify(request, inputs['report'])}
    raise ValueError('Unknown routing-profile capability')


if __name__ == '__main__':
    try:
        result = {'outcome': 'ok', 'outputs': dispatch(json.load(sys.stdin))}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'outcome': 'error', 'error': {'code': 'INVALID_INPUT', 'message': str(exc)}}
    print(json.dumps(result, allow_nan=False))
