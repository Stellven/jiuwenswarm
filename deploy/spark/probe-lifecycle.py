import hashlib,json,os,sys,time
from pathlib import Path
from jiuwenswarm.factory.jobs import Jobs
from jiuwenswarm.factory.store import Store
root=Path(os.environ['FACTORY_HOME']);workspace=root.parent
with Store(root) as s:
    jobs=Jobs(s)
    for mode in ('cancel','timeout'):
        request=dict(mode=mode,worker_sha256=hashlib.sha256(Path('/factory/jiuwenswarm/factory/spark_probe.py').read_bytes()).hexdigest())
        argv=['/usr/bin/python3','-m','jiuwenswarm.factory.spark_probe','--attempt','{attempt_id}']
        a=jobs.submit('spark-deepseek-port','probe',request,'lifecycle-'+mode,'cpu',argv,15 if mode=='timeout' else 120,{'FACTORY_HOME':str(root)})
        aid=a['attempt_id'];out=root/'probes'/aid
        end=time.monotonic()+45
        while not (out/'started.json').exists() and time.monotonic()<end:
            time.sleep(.2)
        if not (out/'started.json').exists():raise RuntimeError('Probe did not start')
        if mode=='cancel':jobs.cancel(aid)
        while time.monotonic()<end:
            a=jobs.status(aid)
            if a['state'] in ('cancelled','failed','succeeded'):break
            time.sleep(.2)
        record=json.loads((out/'cleanup.json').read_text())
        assert record['child_reaped'] and record['container_removed'],record
        assert a['state']==('cancelled' if mode=='cancel' else 'failed'),a
        assert 'process_groups_reaped' in a['cleanup_state'],a
        artifact=s.put_artifact('spark-deepseek-port',aid+':cleanup',(out/'cleanup.json'),'application/json',aid)
        s.append_observation('spark-deepseek-port',dict(obs_id=aid+':lifecycle',kind='lifecycle_probe',values=dict(mode=mode,state=a['state'],cleanup=a['cleanup_state'],**record),source_artifacts=[artifact['artifact_id']]))
        print(json.dumps(dict(mode=mode,attempt=aid,state=a['state'],**record)),flush=True)
