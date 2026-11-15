"""Bounded inline-JSON native CC; only bundled stdlib components execute."""
import json
import sys
from components import placement

CAPABILITIES = ['plan', 'execute_reference', 'overlap_schedule']

def dispatch(capability, data):
    if capability not in CAPABILITIES:
        raise ValueError('unknown capability')
    if not isinstance(data, dict):
        raise ValueError('request must be an object')
    return getattr(placement, capability)(data)

if __name__ == '__main__':
    try:
        raw = sys.stdin.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('packet too large')
        packet = json.loads(raw)
        result = dispatch(packet['capability'], packet['inputs']['request'])
        reply = {'outcome':'ok','outputs':{'result':result}}
    except Exception as error:
        reply = {'outcome':'error','outputs':{},'error':{'code':'INVALID_REQUEST','message':str(error)}}
    print(json.dumps(reply, allow_nan=False))
