"""Container entry point for the session-directed bounded factory smoke."""
import argparse,hashlib,json,os
from pathlib import Path
from jiuwenswarm.factory.store import Store
from jiuwenswarm.factory.builder import Builder
from jiuwenswarm.factory.manager import Manager
from jiuwenswarm.factory.jobs import Jobs
parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path);args=parser.parse_args()
root=Path(os.environ['FACTORY_HOME']).parent;repo=root/'sources/cc-dgx-spark'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
with Store(root/'port-store') as s:
    build=json.loads((root/'results/port-build-handle.json').read_text())
    result=Builder(s).status(build['attempt_id'])
    assert result['state']=='succeeded',result
    receipt=json.loads(s.artifact_bytes('spark-deepseek-port',build['attempt_id']+':receipt'))
    image=receipt['image_id']
    admission=Manager(s,s.home/'lab-spool').admit('spark-deepseek-port',dict(tag=build['request']['tag'],id=image),build['attempt_id'])
    source=root/'sources/strata-deepseek'
    original=json.loads((args.config or Path(__file__).parent/'configs/strata-conservative.json').read_text())
    data=json.dumps(original,sort_keys=True,indent=2)
    config=root/'notes/run-configs'/(hashlib.sha256(data.encode()).hexdigest()+'.json')
    config.parent.mkdir(exist_ok=True)
    if not config.exists():config.write_text(data)
    timeout_s=original.get('timeout_s',3600)
    if type(timeout_s) is not int or not 1<=timeout_s<=3600:raise ValueError('Timeout outside bounds')
    workload=root/'notes/port-smoke-workload.json';w=json.loads(workload.read_text())
    protocol=root/'notes/port-smoke.protocol'
    protocol.write_text('GEN 32 temperature=0 top_p=1 top_k=1 min_p=0 seed=42 '+','.join(map(str,w['ids']))+'\nQUIT\n')
    collector=root/'sources/collector'
    pins=[*collector.rglob('*.py'),config,workload,protocol,root/'notes/port-pack-source.json']
    request=dict(image_id=image,build_attempt_id=build['attempt_id'],admission_id=admission['admission_id'],worker_sha256=sha(repo/'jiuwenswarm/factory/spark_run.py'),engine_config=str(config),workload=str(workload),protocol=str(protocol),pack_manifest=str(root/'notes/port-pack-source.json'),collector_root=str(collector),input_sha256={str(p):sha(p) for p in pins},resource_budget=dict(timeout_s=timeout_s,max_generated_tokens=32,cpus=8,memory_bytes=104*2**30,swap_bytes=0))
    request['input_sha256'].update(json.loads((root/'notes/port-pack-identity.json').read_text()))
    argv=['/usr/bin/python3','-m','jiuwenswarm.factory.spark_run','--task','spark-deepseek-port','--attempt','{attempt_id}']
    attempt=Jobs(s).submit('spark-deepseek-port','smoke',request,'deepseek-smoke-'+hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()[:16],'gpu',argv,timeout_s+60,{'FACTORY_HOME':str(s.home)})
    (root/('results/strata-smoke-'+attempt['attempt_id']+'-handle.json')).write_text(json.dumps(attempt,indent=2))
    print(json.dumps(dict(attempt_id=attempt['attempt_id'],state=attempt['state'],jobq_id=attempt['jobq_id'],image_id=image)))
