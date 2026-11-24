"""Translate lab manager capability names to the task-scoped factory native API."""
import json
import os
import subprocess
import sys

from jiuwenswarm.factory.telemetry import set_turn_env
set_turn_env()

packet = json.load(sys.stdin)
packet['capability'] = 'lab_manager.' + packet['capability']
try:
    process = subprocess.run([os.environ.get('FACTORY_PYTHON', sys.executable), '-m', 'jiuwenswarm.factory.api', packet['capability']],
                             input=json.dumps(packet), capture_output=True, text=True, timeout=49)
    result = json.loads(process.stdout)
except subprocess.TimeoutExpired:
    result = {'outcome': 'error', 'error': {'code': 'TIMEOUT', 'message': 'Factory API exceeded the bounded call deadline'}}
except (ValueError, TypeError):
    detail = ' | '.join(process.stderr.strip().splitlines()[-3:])[-600:] if process.stderr else 'no stderr'
    result = {'outcome': 'error', 'error': {'code': 'API_FAILED', 'message': 'Factory API did not return a JSON result: ' + detail}}
if result.get('outcome') == 'ok':
    result['outputs'] = {'result': result['outputs']}
print(json.dumps(result))
