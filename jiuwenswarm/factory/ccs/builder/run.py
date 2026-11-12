"""Translate capsule capability names to the task-scoped factory native API."""
import json
import subprocess
import sys

from jiuwenswarm.factory.telemetry import set_turn_env
set_turn_env()

PREFIX = 'builder'
packet = json.load(sys.stdin)
cap = packet['capability']
packet['capability'] = PREFIX + '.' + cap
try:
    process = subprocess.run([sys.executable, '-m', 'jiuwenswarm.factory.api', packet['capability']],
                             input=json.dumps(packet), capture_output=True, text=True, timeout=49)
    result = json.loads(process.stdout)
except subprocess.TimeoutExpired:
    result = {'outcome': 'error', 'error': {'code': 'TIMEOUT', 'message': 'Factory API exceeded the bounded call deadline'}}
except (ValueError, TypeError):
    result = {'outcome': 'error', 'error': {'code': 'API_FAILED', 'message': 'Factory API did not return a JSON result'}}
if PREFIX == 'lab' and result.get('error', {}).get('code') == 'INVALID_INPUT':
    # F06 installs lab.* dispatch. Until then the evidence API rejects it.
    result = {'outcome': 'error', 'error': {'code': 'NOT_IMPLEMENTED', 'message': 'Lab API is not installed'}}
if result.get('outcome') == 'ok':
    outputs = result['outputs']
    if PREFIX == 'evidence' and cap in {'read', 'publish'}:
        result['outputs'] = {'record': outputs}
    elif PREFIX in {'builder', 'lab'}:
        if cap == 'submit':
            result['outputs'] = {k: outputs[k] for k in ('attempt_id', 'state', 'jobq_id')}
print(json.dumps(result))
