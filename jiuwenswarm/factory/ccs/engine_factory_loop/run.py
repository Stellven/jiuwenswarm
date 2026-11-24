"""Use the existing factory API and task-scoped telemetry envelope."""
import json
import os
import subprocess
import sys
from jiuwenswarm.factory.telemetry import set_turn_env
set_turn_env()
packet = json.load(sys.stdin)
capability = 'factory_loop.' + packet['capability']
packet['capability'] = capability
try:
    process = subprocess.run([os.environ.get('FACTORY_PYTHON', sys.executable), '-m',
        'jiuwenswarm.factory.api', capability], input=json.dumps(packet),
        capture_output=True, text=True, timeout=49)
    result = json.loads(process.stdout)
except subprocess.TimeoutExpired:
    result = {'outcome': 'error', 'error': {'code': 'TIMEOUT', 'message': 'Loop call interrupted; recover using the same cycle_id'}}
except (ValueError, TypeError):
    result = {'outcome': 'error', 'error': {'code': 'API_FAILED', 'message': 'Loop API returned no valid JSON envelope'}}
print(json.dumps(result, allow_nan=False))
