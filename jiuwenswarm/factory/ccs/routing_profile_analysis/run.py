"""CC v2 entry point for routing-profile analysis."""
import json
import sys

from copy_timing import timing_artifacts
from residency_counterfactual import compare_artifacts as compare_residency_artifacts
from routing_profile import analyze, verify
from routing_transfer import compare_artifacts


def dispatch(packet):
    inputs = packet['inputs']
    capability = packet['capability']
    methods = [
        ('compare', 'verify_transfer', compare_artifacts, ('trace', 'ranks')),
        ('time_copies', 'verify_copy_timing', timing_artifacts, ('transfer', 'replay', 'request', 'activation', 'baseline')),
        ('estimate_residency', 'verify_residency', compare_residency_artifacts, ('trace', 'ranks', 'transfer', 'tensor_index', 'timing')),
    ]
    for analysis, verification, method, names in methods:
        if capability in {analysis, verification}:
            report = method({name: inputs[name] for name in names})
            if capability == analysis:
                return {'report': report}
            saved = json.dumps(inputs['report'], sort_keys=True, allow_nan=False)
            return {'verified': saved == json.dumps(report, sort_keys=True)}
    if capability == 'rank_trace':
        from trace_rank import rank_trace
        return rank_trace(inputs['trace'], inputs['pack'], inputs.get('profile_out'), inputs.get('prompt_set_sha256'))
    artifacts = {name: inputs[name] for name in ('before', 'after', 'tensor_index')}
    request = {
        **inputs['configuration'],
        **{name: artifact['path'] for name, artifact in artifacts.items()},
        'sha256': {name: artifact['sha256'] for name, artifact in artifacts.items()},
    }
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
