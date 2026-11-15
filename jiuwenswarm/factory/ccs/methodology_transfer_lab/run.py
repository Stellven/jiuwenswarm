"""Self-contained CC packet entry point; never fetches or executes supplied code."""
import json
import sys
from components import TOOLS

try:
    packet = json.load(sys.stdin)
    result = TOOLS[packet['capability']](packet['inputs']['request'])
    print(json.dumps(dict(outcome='ok', outputs=dict(result=result)), allow_nan=False))
except (KeyError, ValueError, TypeError, OverflowError) as exc:
    print(json.dumps(dict(outcome='error', error=dict(code='INVALID_INPUT', message=str(exc)))))
