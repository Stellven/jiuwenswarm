"""Reconcile durable attempts and retain an accurate, session-directed handoff."""
import hashlib,json,os
from pathlib import Path
from jiuwenswarm.factory.store import Store
from jiuwenswarm.factory.jobs import Jobs,metadata
root=Path(os.environ['FACTORY_HOME']).parent
with Store(root/'port-store') as store:
    jobs=Jobs(store);rows=[]
    for a in store.dump('spark-deepseek-port')['attempts']:
        current=jobs.status(a['attempt_id']);aid=a['attempt_id']
        refs=[v['artifact_id'] for v in store.dump('spark-deepseek-port')['artifacts'] if v.get('producer_attempt')==aid]
        observations=[v['obs_id'] for v in store.dump('spark-deepseek-port')['observations'] if v['obs_id'].startswith(aid+':')]
        if refs or observations:current=metadata(store,current,result_refs=sorted(set(refs+observations)))
        rows.append({k:current[k] for k in ('attempt_id','kind','state','jobq_id','cleanup_state','result_refs')})
    (root/'results/port-final-attempts.json').write_text(json.dumps(rows,indent=2))
    for name in ('port-executed-spark-engine.py','port-tests.log','port-regression-tests.log','port-factory-image-build.log','port-complete-tests.log','port-builder-tests.log','port-live-bridge-check.json','port-builder-cc-receipt.json'):
        path=root/'results'/name
        if path.exists():store.put_artifact('spark-deepseek-port','port:'+name+':'+hashlib.sha256(path.read_bytes()).hexdigest()[:16],path,'application/octet-stream',None)
    print(json.dumps([dict(attempt_id=a['attempt_id'],kind=a['kind'],state=a['state'],cleanup_state=a['cleanup_state']) for a in rows]))
