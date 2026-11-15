"""Native CC entry point; inline JSON only."""
import json
import sys
from workflow import DISPATCH

def main():
    try:
        raw = sys.stdin.buffer.read(1048577)
        if len(raw) > 1048576:
            raise ValueError('packet exceeds 1 MiB bound')
        packet = json.loads(raw)
        if not isinstance(packet, dict) or not isinstance(packet.get('inputs'), dict) or not isinstance(packet['inputs'].get('spec'), dict):
            raise ValueError('packet inputs.spec must be an object')
        result = DISPATCH[packet['capability']](packet['inputs']['spec'])
        response = {'outcome': 'ok', 'outputs': {'result': result}}
    except (ValueError, KeyError, TypeError, OverflowError) as error:
        response = {'outcome': 'error', 'error': {'code': 'INVALID_WORKFLOW_INPUT', 'message': str(error)}}
    print(json.dumps(response, allow_nan=False))

if __name__ == '__main__':
    main()
