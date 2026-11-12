"""Operator: build bare llama.cpp cf34d311 through the factory Builder (reference for qwen36-bare-greedy-v1).

  python artifacts/factory/operator_bare_build.py   -> prints the build-record path for FACTORY_REFERENCE_RECORD
"""
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jiuwenswarm.factory.store import Store, NotFound
from jiuwenswarm.factory.builder import Builder

HOME = Path(os.environ.get('FACTORY_HOME', Path.home() / '.jiuwenswarm-factory'))
TASK = 'operator-bare-build'
REQ = dict(target='jetson-orin', tag='factory/llamacpp:bare-cf34d311', deadline_s=5400,
           source=dict(path=str(HOME / 'agent-workspace/llama.cpp'),
                       commit='cf34d311332e362198f0a410c466d1e940287d02',
                       tree='2265e2c6dcf4294ba1cdc8b64ead0519925ef4f6'),
           env=dict(CUDA_HOME='/usr/local/cuda'))
s = Store(HOME)
try:
    s.get_task(TASK)
except NotFound:
    s.create_task(dict(task_id=TASK, objective='Operator: bare cf34d311 reference build for qwen36-bare-greedy-v1',
                       target={'profile': 'jetson-orin'}))
b = Builder(s)
a = b.submit(TASK, REQ, 'bare-cf34d311-1')
print('submitted', a['attempt_id'], a['state'], flush=True)
while a['state'] not in {'succeeded', 'failed', 'cancelled', 'unknown'}:
    time.sleep(15)
    a = b.status(a['attempt_id'])
print('terminal', a['state'], json.dumps(b.result(a['attempt_id']))[:600])
print('record', next(HOME.glob(f"builds/{a['attempt_id']}*/engine/build-record.json"), None))
