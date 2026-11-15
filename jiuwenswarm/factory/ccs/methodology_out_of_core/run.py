"""Task-scoped read-only methodology CC wrapper; no experiment execution."""
import json
import os
import subprocess
import sys
from jiuwenswarm.factory.telemetry import set_turn_env
set_turn_env()
packet = json.load(sys.stdin)
packet['capability'] = 'methodology.' + packet['capability']
try:
    process = subprocess.run([os.environ.get('FACTORY_PYTHON', sys.executable), '-m',
                              'jiuwenswarm.factory.api', packet['capability']],
                             input=json.dumps(packet), capture_output=True, text=True, timeout=49)
    result = json.loads(process.stdout)
except subprocess.TimeoutExpired:
    result = {'outcome': 'error', 'error': {'code': 'TIMEOUT', 'message': 'Bounded methodology analysis timed out'}}
except (ValueError, TypeError):
    result = {'outcome': 'error', 'error': {'code': 'API_FAILED', 'message': 'Methodology API returned no valid JSON envelope'}}
print(json.dumps(result, allow_nan=False))
