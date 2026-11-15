#!/usr/bin/env python3
"""Freeze or execute a single operator-authorized Strata drafting comparison.

Run on the Spark host, using its existing queue. No builds or agent turns run
while the campaign owns the lab. Re-running reconciles its stable task/key.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import shutil
import time

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--root',type=Path,default=Path('/home/user2/software-factory-spark-20261113'))
p.add_argument('--stage',choices=['pilot','main'],required=True)
p.add_argument('--name',default='001')
p.add_argument('--freeze-only',action='store_true')
a=p.parse_args();root=a.root.resolve();repo=root/'sources/cc-dgx-spark'
sys.path.insert(0,str(repo))
os.environ.update(FACTORY_JOBQ_BIN='/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/lab-source/bin/jobq',
 JOBQ_DIR='/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/jobq',DOCKER_PREFIX='',DOCKER_CMD_PREFIX='')
os.environ.pop('FACTORY_BRIDGE_DIR',None)
from jiuwenswarm.factory.benchmark import Benchmark,EXECUTION_FILES,validate_contract,load_dataset,validate_assets,sha
from jiuwenswarm.factory.contract import atomic_json
from jiuwenswarm.factory.store import Store,NotFound
profiles=root/'benchmarks/component-apply-001'
arms={v:json.loads((profiles/f'{v}-profile.json').read_text()) for v in 'AB'}
folder=root/f'benchmarks/arc-drafting-{a.stage}-{a.name}';folder.mkdir(parents=True,exist_ok=True)
path=folder/'contract.json';task_id=f'spark-arc-drafting-{a.stage}-{a.name}'
if not path.exists():
 if a.stage=='main':
  pilot=root/'benchmarks/arc-drafting-pilot-001/result.json'
  if not pilot.exists() or json.loads(pilot.read_text()).get('analysis',{}).get('verdict')!='pilot_ok':
   raise ValueError('Complete the operational pilot before admitting main comparison')
 c=dict(adapter='strata-benchmark-v1',version=1,contract_id=task_id,stage=a.stage,
  tolerance='arc-exact-answer-regression-v1',target='spark-gb10',
  image=dict(id=arms['A']['image'],tag='factory/strata:spark-strata-e2e-001'),
  arms={v:dict(args=arms[v]['args'],environment=arms[v]['environment']) for v in 'AB'},
  order=list('AB' if a.stage=='pilot' else 'ABBAABBA'),
  workload={k:arms['A'][k] for k in ('pack','model_root')},workspace_root=str(root),
  limits=dict(cpus=8,memory_bytes=104*2**30,guard_gib=8,extra_swap_bytes=0,quality_timeout_s=900,speed_timeout_s=300),
  gates=dict(minimum_accuracy=0.5,minimum_speedup=1.05,confidence=0.95,bootstrap_resamples=20000,seed=42,correctness='no_per_question_regression'),
  campaign_timeout_s=5280,dataset_path=str(root/'benchmark-data/arc-v1/dataset.json'),
  dataset_sha256=sha(root/'benchmark-data/arc-v1/dataset.json'),
  assets=dict(identity_path=str(root/'assets/deepseek-full-identity-v1.json'),identity_sha256=sha(root/'assets/deepseek-full-identity-v1.json')),
  execution_sha256={v:sha(repo/'jiuwenswarm/factory'/v) for v in EXECUTION_FILES},
  component=dict(capability='engine.strata_verified_drafting.apply',receipts={v:dict(path=str(profiles/f'{v}-receipt.json'),sha256=sha(profiles/f'{v}-receipt.json')) for v in 'AB'}))
 validate_contract(c);load_dataset(c);validate_assets(c)
 snapshot=folder/'execution-source';snapshot.mkdir(exist_ok=False)
 for name,expected in c['execution_sha256'].items():
  source=repo/'jiuwenswarm/factory'/name
  if sha(source)!=expected:raise ValueError('Source changed while freezing: '+name)
  shutil.copy2(source,snapshot/name)
 atomic_json(snapshot/'sha256.json',c['execution_sha256'])
 atomic_json(path,c)
else:c=validate_contract(json.loads(path.read_text()))
print(json.dumps(dict(contract=str(path),sha256=sha(path),stage=a.stage)),flush=True)
if a.freeze_only:raise SystemExit(0)
with Store(root/'mission-store') as store:
 try:task=store.get_task(task_id)
 except NotFound:
  task=store.create_task(dict(task_id=task_id,objective='Measure the isolated verified-drafting CC against pinned public-task correctness and native speed gates',
   target='spark-gb10',contract_id=str(path),constraints=dict(benchmark_contract_sha256=sha(path),attempt_limits=dict(lab=1)),allowed_effects=['process.exec']))
 manager=Benchmark(store);attempt=manager.submit(task_id,str(path),'frozen-campaign-v1')
 atomic_json(folder/'attempt.json',attempt);print(json.dumps(dict(attempt_id=attempt['attempt_id'],state=attempt['state'])),flush=True)
 prior=None
 while True:
  attempt=manager.status(task_id,attempt['attempt_id'])
  progress=store.home/'benchmark-spool'/attempt['attempt_id']/'progress.json'
  state=json.loads(progress.read_text()) if progress.exists() else dict(state=attempt['state'])
  if state!=prior:print(json.dumps(state),flush=True);prior=state
  if attempt['state'] in {'succeeded','failed','cancelled'}:break
  time.sleep(5)
 result=manager.result(task_id,attempt['attempt_id']);atomic_json(folder/'result.json',result)
 print(json.dumps(result),flush=True)
