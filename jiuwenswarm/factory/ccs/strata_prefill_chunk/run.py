"""Native pure-profile capability; no model, subprocess or persistent state."""
import json
import sys
from jiuwenswarm.factory.strata_prefill import dispatch
try:
    packet = json.load(sys.stdin)
    result = {'outcome': 'ok', 'outputs': dispatch(packet.get('inputs', {}), packet.get('capability'))}
except (ValueError, TypeError, KeyError) as exc:
    result = {'outcome': 'error', 'error': {'code': 'INVALID_INPUT', 'message': str(exc)}}
print(json.dumps(result, allow_nan=False))
