"""Observe all recovery attempts against their recorded shared queue."""
import json,os
from pathlib import Path
from jiuwenswarm.factory.jobs import Jobs
from jiuwenswarm.factory.store import Store
root=Path(os.environ['FACTORY_HOME']).parent
with Store(root/'port-store') as store:
    rows=[]
    for task in ('spark-deepseek-port','spark-llamacpp-stable'):
        for a in store.dump(task)['attempts']:
            current=Jobs(store).status(a['attempt_id'])
            rows.append({k:current[k] for k in ('task_id','attempt_id','kind','state','cleanup_state')})
    (root/'results/recovery-final-attempts.json').write_text(json.dumps(rows,indent=2))
    print(json.dumps(rows))
