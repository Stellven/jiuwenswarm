"""Task-local digest bridge; no source paths or arbitrary capability dispatch."""
import json
import os
import subprocess
import sys
try:
    raw = sys.stdin.buffer.read(65537)
    if len(raw) > 65536:
        raise ValueError('Digest request exceeds 64KiB')
    packet = json.loads(raw)
    if packet['capability'] not in {'index', 'project'}:
        raise ValueError('Unknown digest capability')
    packet['capability'] = 'evidence_digest.' + packet['capability']
    child = subprocess.run([os.environ.get('FACTORY_PYTHON', sys.executable), '-m', 'jiuwenswarm.factory.api', packet['capability']],
                           input=json.dumps(packet), text=True, capture_output=True, timeout=49)
    result = json.loads(child.stdout)
except subprocess.TimeoutExpired:
    result = {'outcome':'error','error':{'code':'TIMEOUT','message':'Digest API exceeded deadline'}}
except (ValueError, TypeError, KeyError):
    result = {'outcome':'error','error':{'code':'INVALID_DIGEST_INPUT','message':'Invalid bounded digest packet or API response'}}
# Use the same deterministic serialization as the API budget calculation.
print(json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':'), sort_keys=True))
