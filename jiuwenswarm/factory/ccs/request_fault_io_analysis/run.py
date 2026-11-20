"""Native CC entry point; it reads pinned artifacts and launches no workload."""
import json
import sys

from fault_io import analyze_artifacts


def dispatch(packet):
    capability = packet['capability']
    inputs = packet['inputs']
    report = analyze_artifacts({name: inputs[name] for name in ('counters', 'request')})
    if capability == 'analyze':
        return {'report': report}
    if capability == 'verify':
        saved = json.dumps(inputs['report'], sort_keys=True, allow_nan=False)
        return {'verified': saved == json.dumps(report, sort_keys=True)}
    raise ValueError('Unknown request fault and I/O capability')


if __name__ == '__main__':
    try:
        result = {'outcome': 'ok', 'outputs': dispatch(json.load(sys.stdin))}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'outcome': 'error', 'error': {'code': 'INVALID_INPUT', 'message': str(exc)}}
    print(json.dumps(result, allow_nan=False))
