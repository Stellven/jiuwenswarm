"""Native CC v2 entrypoint for CPU reference operations and factory evidence."""
import json
import sys

import prefix_store
import reference
import verification

OPERATIONS = {'prefix': 'prefix', 'allocator': 'replay', 'estimate': 'estimate'}
FACTORY_CHECKS = {
    'verify_pins': ('pinned_inputs', 'Verified the AQB image, prefill plan, pack and trial evidence pins'),
    'plan': ('prefix_plan', 'Verified phase 0 refusal and phase 0b engagement, legal diff and device budget'),
    'verify_factory_stage': ('factory_stage', 'Verified the built image layers, executable, pack and launch config'),
}


def run(capability, inputs):
    if capability == 'verify':
        return {'result': verification.verify()}
    if capability in FACTORY_CHECKS:
        name, detail = FACTORY_CHECKS[capability]
        result = getattr(prefix_store, capability)(**inputs)
        checks = [dict(name=capability, status='pass', stage='native CC execution', detail=detail)]
        return {'done': True, 'checks': checks, name: result}
    if capability == 'verify_runtime_stage':
        from jiuwenswarm.factory.muse_r9_runtime import verify_runtime_stage

        policy = inputs.get('policy')
        result = verify_runtime_stage(inputs['measurements'], policy=policy)
        checks = result['checks']
        return dict(done=result['done'], checks=checks, result=result)
    return {'result': getattr(reference, OPERATIONS[capability])(inputs['spec'])}


def main():
    try:
        packet = json.load(sys.stdin)
        output = {'outcome': 'ok', 'outputs': run(packet['capability'], packet['inputs'])}
    except (ValueError, KeyError, TypeError, IndexError, OverflowError, OSError, StopIteration) as error:
        output = {'outcome': 'error', 'error': {'code': 'INVALID_REFERENCE_INPUT', 'message': str(error)}}
    print(json.dumps(output, allow_nan=False))


if __name__ == '__main__':
    main()
