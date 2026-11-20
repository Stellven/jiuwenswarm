"""Native CC entry point; it reads pinned artifacts and launches no workload."""
import json
import sys

from calibration_intervals import analyze_artifacts as analyze_calibration_artifacts
from fault_io import analyze_artifacts


def dispatch(packet):
    capability = packet['capability']
    inputs = packet['inputs']
    if capability in {'analyze_calibration', 'verify_calibration'}:
        report = analyze_calibration_artifacts({name: inputs[name] for name in ('trace', 'engine_log')})
    else:
        report = analyze_artifacts({name: inputs[name] for name in ('counters', 'request')})
    if capability in {'analyze', 'analyze_calibration'}:
        return {'report': report}
    if capability in {'verify', 'verify_calibration'}:
        saved = json.dumps(inputs['report'], sort_keys=True, allow_nan=False)
        return {'verified': saved == json.dumps(report, sort_keys=True)}
    raise ValueError('Unknown request fault and I/O capability')


if __name__ == '__main__':
    try:
        result = {'outcome': 'ok', 'outputs': dispatch(json.load(sys.stdin))}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'outcome': 'error', 'error': {'code': 'INVALID_INPUT', 'message': str(exc)}}
    print(json.dumps(result, allow_nan=False))
