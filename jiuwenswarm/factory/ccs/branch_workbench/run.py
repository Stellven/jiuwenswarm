"""Native branch-record CC; route through the existing scoped factory API."""
import json
import os
import subprocess
import sys
packet = json.load(sys.stdin)
packet['capability'] = 'branch_workbench.' + packet['capability']
try:
    process = subprocess.run([os.environ.get('FACTORY_PYTHON', sys.executable), '-m', 'jiuwenswarm.factory.api', packet['capability']], input=json.dumps(packet), capture_output=True, text=True, timeout=49)
    result = json.loads(process.stdout)
except subprocess.TimeoutExpired:
    result = {'outcome':'error','error':{'code':'TIMEOUT','message':'Branch record request timed out; retry the same idempotency key.'}}
except (ValueError, TypeError):
    result = {'outcome':'error','error':{'code':'API_FAILED','message':'Factory API returned no valid envelope'}}
print(json.dumps(result, allow_nan=False))
