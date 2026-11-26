"""Capped runs (build, convert, quantize, serve, accuracy) through the factory API, without a shell."""
import json
import os
import subprocess
import sys
from jiuwenswarm.factory.telemetry import set_turn_env
set_turn_env()
packet = json.load(sys.stdin)
capability = 'capped_runner.' + packet['capability']
packet['capability'] = capability
try:
    process = subprocess.run([os.environ.get('FACTORY_PYTHON', sys.executable), '-m',
        'jiuwenswarm.factory.api', capability], input=json.dumps(packet),
        capture_output=True, text=True, timeout=120)
    result = json.loads(process.stdout)
except subprocess.TimeoutExpired:
    result = {'outcome': 'error', 'error': {'code': 'TIMEOUT', 'message': 'Read capped_runner.status before starting again'}}
except (ValueError, TypeError):
    result = {'outcome': 'error', 'error': {'code': 'API_FAILED', 'message': 'Capped runner API returned no valid JSON envelope'}}
print(json.dumps(result, allow_nan=False))
