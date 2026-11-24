"""Native tools for static quant inventory and retained trace accounting."""
import json
import sys

from quant_kernel_profile import inventory, profile


def dispatch(packet):
    capability = packet['capability']
    inputs = packet['inputs']
    if capability in {'inventory', 'verify_inventory'}:
        report = inventory(inputs['pack_index'])
    elif capability in {'profile', 'verify_profile'}:
        report = profile(inputs['trace'])
    else:
        raise ValueError('Unknown quantized kernel profile capability')
    if capability.startswith('verify_'):
        saved = json.dumps(inputs['report'], sort_keys=True, allow_nan=False)
        return {'verified': saved == json.dumps(report, sort_keys=True)}
    return {'report': report}


if __name__ == '__main__':
    try:
        result = {'outcome': 'ok', 'outputs': dispatch(json.load(sys.stdin))}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'outcome': 'error', 'error': {'code': 'INVALID_INPUT', 'message': str(exc)}}
    print(json.dumps(result, allow_nan=False))
