"""Prepare and qualify the existing llama.cpp build through the factory queue."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
from jiuwenswarm.factory.store import Store,NotFound
from jiuwenswarm.factory.jobs import Jobs
from jiuwenswarm.factory.manager import Manager
p=argparse.ArgumentParser();p.add_argument('operation',choices=['package','qualify','run']);p.add_argument('--prompt');p.add_argument('--wait',action='store_true');a=p.parse_args()
root=Path(os.environ['FACTORY_HOME']).parent;repo=root/'sources/cc-dgx-spark';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
with Store(root/'port-store') as store:
    task='spark-llamacpp-stable'
    try:store.get_task(task)
    except NotFound:store.create_task(dict(task_id=task,objective='Provide a stable bounded llama.cpp GPU fallback using existing GPT-OSS 20B',target={'profile':'spark-gb10'},allowed_effects=['process.exec']))
    request=dict(operation='package' if a.operation=='package' else 'collect',worker_sha256=sha(repo/'jiuwenswarm/factory/runtime_job.py'),input_sha256={})
    if a.operation=='package':
        record=root/'results/build-warm-002/build-record.json'
        request.update(upstream_record=str(record),base_image_id='sha256:a454b72160a58e0e1236b81fddfa32fc8e8bd48f09f149528d8b60c64ddc23d6',target='spark-gb10')
        request['input_sha256'][str(record)]=sha(record)
    else:
        if a.operation=='run':
            if not a.prompt or len(a.prompt.encode())>8192:raise ValueError('A prompt of 1..8192 bytes is required')
            qualified=json.loads((root/'results/stable-llama-qualify-handle.json').read_text())
            prior=Jobs(store).status(qualified['attempt_id'])
            if prior['state']!='succeeded':raise ValueError('Successful qualification required')
        build=json.loads((root/'results/stable-llama-package-handle.json').read_text());jobs=Jobs(store);build=jobs.status(build['attempt_id'])
        if build['state']!='succeeded':raise ValueError('Package not successful: '+build['state'])
        receipt=json.loads(store.artifact_bytes(task,build['attempt_id']+':receipt'))
        admission=Manager(store,store.home/'lab-spool').admit(task,dict(tag='factory/llamacpp:cc-dgx-spark-stable',id=receipt['image_id']),build['attempt_id'])
        collector=root/'sources/collector'
        request.update(image_id=receipt['image_id'],admission_id=admission['admission_id'],build_attempt_id=build['attempt_id'],collector_root=str(collector),
            model=dict(path='/home/user2/ai4r-data/inference-v3/models/gptoss20/gpt-oss-20b-MXFP4.gguf',bytes=12109566624,sha256='27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901'),
            prompts=['What is 17 + 25? Reply with only the number.','Name three basic parts of a computer in one short sentence.','What is 17 + 25? Reply with only the number.'])
        if a.operation=='run':request['prompts']=[a.prompt]
        else:request['qualification_checks']={'repeat_first_last':True,'arithmetic_expected':'42'}
        request['input_sha256'].update({str(path):sha(path) for path in collector.rglob('*.py')})
    key='stable-llama-'+a.operation+'-'+hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()[:16]
    argv=['/usr/bin/python3','-m','jiuwenswarm.factory.runtime_job','--task',task,'--attempt','{attempt_id}']
    attempt=Jobs(store).submit(task,'build' if a.operation=='package' else 'qualification',request,key,'build' if a.operation=='package' else 'gpu',argv,300 if a.operation=='package' else 960,{'FACTORY_HOME':str(store.home)})
    (root/('results/stable-llama-'+a.operation+'-handle.json')).write_text(json.dumps(attempt,indent=2))
    print(json.dumps({k:attempt[k] for k in ('attempt_id','state','jobq_id')}),file=sys.stderr,flush=True)
    if a.wait:
        deadline=time.monotonic()+1020
        while time.monotonic()<deadline:
            observed=Jobs(store).status(attempt['attempt_id'])
            if observed['state'] in ('succeeded','failed','cancelled'):break
            time.sleep(.5)
        else:raise TimeoutError('Queue wait expired; durable attempt retained for reconciliation')
        result=json.loads((store.home/'runtime-jobs'/attempt['attempt_id']/'result.json').read_text())
        for record in result.get('records',[]):print(record['output'].strip(),flush=True)
        if observed['state']!='succeeded' or result['status']!='success':raise SystemExit(1)
