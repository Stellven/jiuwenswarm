"""Bounded DeepSeek host collector job with durable factory evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from .store import Store
from .targets import validate_image


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def metadata_check(manifest):
    checks=[]
    for name,(size,mtime) in manifest['files'].items():
        path=(Path(manifest['model_dir'])/name).resolve();st=path.stat()
        checks.append(dict(path=str(path),bytes=st.st_size,size_matches=st.st_size==size,mtime_matches=st.st_mtime_ns==mtime))
    if not all(c['size_matches'] and c['mtime_matches'] for c in checks):raise ValueError('Model pack metadata changed')
    return checks


def decoded(ids,vocab):
    bs=list(range(33,127))+list(range(161,173))+list(range(174,256));cs=list(bs);n=0
    for b in range(256):
        if b not in bs:bs.append(b);cs.append(256+n);n+=1
    reverse={chr(c):b for b,c in zip(bs,cs)};tokens={v:k for k,v in vocab.items()}
    return b''.join(bytes([reverse[c]]) if c in reverse else c.encode() for i in ids for c in tokens[i]).decode(errors='replace')


def main():
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--task',required=True);a=p.parse_args()
    home=Path(os.environ['FACTORY_HOME']);root=home/'runs'/a.attempt;root.mkdir(parents=True)
    report=dict(status='failed',limitations=['Matching model sizes and timestamps do not establish full hash verification.',
        'Cgroup/RSS accounting does not establish all physical GPU unified-memory usage.'])
    collector=None;rc=1
    def stop(signum,frame):raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,stop)
    try:
        with Store(home) as store:
            attempt=store.read(a.task,a.attempt);request=attempt['request']
            if request['worker_sha256']!=sha(__file__):raise ValueError('Worker identity changed')
            build=store.read(a.task,request['build_attempt_id'])
            if build['state']!='succeeded':raise ValueError('Successful build required')
            receipt=json.loads(store.artifact_bytes(a.task,request['build_attempt_id']+':receipt'))
            if receipt['image_id']!=request['image_id']:raise ValueError('Build receipt image mismatch')
        for path,want in request['input_sha256'].items():
            if sha(path)!=want:raise ValueError('Pinned input changed: '+path)
        image=request['image_id'];info=json.loads(subprocess.check_output(['docker','image','inspect',image]))[0]
        validate_image('spark-gb10',info,build['request']['target'])
        config=json.loads(Path(request['engine_config']).read_text());manifest=json.loads(Path(request['pack_manifest']).read_text())
        report['model_before']=metadata_check(manifest)
        gpu=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],text=True).strip()
        available=int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))*1024
        report['admission']=dict(gpu_processes=gpu,available_bytes=available,minimum_bytes=108*2**30)
        if gpu or available<108*2**30:raise ValueError('Compute or available-memory admission failed')
        # Reuse the existing bounded collector without changing its retained source.
        sys.path.insert(0,request['collector_root'])
        from spark_comparison import docker_cell as dc
        collector=dc;dc.MEMORY=104*2**30
        old_sample=dc.memory_sample
        def sample(*args,**kwargs):
            try:return old_sample(*args,**kwargs)
            except OSError as exc:
                if exc.errno==19:raise FileNotFoundError(str(exc)) from exc
                raise
        dc.memory_sample=sample
        old_create,old_verify=dc.create_argv,dc.verify_boundary
        def create(argv,**kwargs):
            env=dict(kwargs.get('environment') or {})
            supported={'DS4_ASYNC_T','DS4_UMA_HEADROOM_GIB','DS4_STORE_GB','DS4_COPY_ALL','DS4_AHEAD','DS4_ENGRAM_THREADS','DS4_ENGRAM_CACHE_MB'}
            if set(env)-supported or env.get('DS4_ASYNC_T')!='4' or any(not isinstance(v,str) or '\n' in v or '\0' in v for v in env.values()):
                raise ValueError('Unsupported bounded Spark environment')
            kwargs['environment']={};cmd=old_create(argv,**kwargs);pos=cmd.index(kwargs['image'])
            opts=[arg for k,v in sorted(env.items()) for arg in ('--env',k+'='+v)]
            return cmd[:pos]+opts+cmd[pos:]
        def verify(info,image,gpu):
            old_verify(info,image,gpu)
            if any(k+'='+v not in info['Config']['Env'] for k,v in config['env'].items()):raise ValueError('Engine environment mismatch')
        dc.create_argv,dc.verify_boundary=create,verify
        cuda_check = """import ctypes
r=ctypes.CDLL('/opt/strata/libcudart.so.13')
p=ctypes.c_void_p()
assert r.cudaMalloc(ctypes.byref(p),4)==0
try:
 assert r.cudaMemset(p,42,4)==0
 assert r.cudaDeviceSynchronize()==0
 out=ctypes.create_string_buffer(4)
 assert r.cudaMemcpy(out,p,4,2)==0
 assert out.raw==bytes([42])*4,out.raw
 print('cuda-runtime-check-ok',flush=True)
finally:
 assert r.cudaFree(p)==0
"""
        launch=dc.run_docker(['/usr/bin/python3','-c',cuda_check],output=root/'gpu-check',image=image,gpu=True,
            environment=config['env'],timeout_s=30,guard_gib=8,name='strata-rsi-spark-launch-'+a.attempt)
        report['gpu_launch_check']=launch
        launch_id=launch.get('container_id')
        if launch_id:
            subprocess.run(['docker','rm','-f',launch_id],capture_output=True,check=True,timeout=15)
        if launch['reason']!='completed' or not launch['quiescent'] or launch.get('container_exit_code')!=0:
            raise ValueError('GPU runtime launch check failed')
        pack=Path(config['args'][config['args'].index('--pack')+1]);model_root=Path(manifest['model_dir']).parent
        argv=['/opt/strata/strata-dsv41',*config['args'],'--profile-readonly','--serve']
        protocol=Path(request['protocol'])
        timeout_s=request['resource_budget']['timeout_s']
        if type(timeout_s) is not int or not 1<=timeout_s<=3600:raise ValueError('Inference timeout outside bounds')
        result=dc.run_docker(argv,output=root/'collector',mounts=[(pack,pack),(model_root,model_root)],
            image=image,gpu=True,environment=config['env'],protocol=protocol,protocol_sha256=sha(protocol),
            timeout_s=timeout_s,interval_ms=1000,guard_gib=8,name='strata-rsi-spark-'+a.attempt)
        report['collector']=result
        report['model_after']=metadata_check(manifest)
        text=(root/'collector/stdout.log').read_text();ids=[int(l.split()[1]) for l in text.splitlines() if l.startswith('T ')]
        done=[l for l in text.splitlines() if l.startswith('DONE ')]
        vocab=json.loads((pack/'tokenizer/vocab.json').read_text())
        report.update(generated_ids=ids,generated_text=decoded(ids,vocab),done=done,
                      prompt=json.loads(Path(request['workload']).read_text())['prompt'])
        if len(ids)>32:raise ValueError('Token cap violated')
        framing_ok = len(done)==1 and len(done[0].split())==11 and int(done[0].split()[1])==len(ids) and done[0].split()[5] in ('stop','length')
        report['status']='success' if result['reason']=='completed' and result['quiescent'] and result.get('container_exit_code')==0 and ids and framing_ok and not any(l.startswith('ERR') for l in text.splitlines()) else ('protocol_invalid' if result['reason']=='completed' else result['reason'])
        rc=0 if report['status']=='success' else 1
    except BaseException as exc:
        report['error']=type(exc).__name__+': '+str(exc)
        if isinstance(exc,SystemExit):report['status']='cancelled_or_timeout'
    finally:
        signal.signal(signal.SIGTERM,signal.SIG_IGN)
        collected=root/'collector/report.json'
        if collected.exists() and 'collector' not in report:report['collector']=json.loads(collected.read_text())
        cid=report.get('collector',{}).get('container_id')
        if cid:
            # Collector verifies quiescence; remove only its recorded, named container.
            info=json.loads(subprocess.check_output(['docker','inspect',cid]))[0]
            if info['Name']!='/strata-rsi-spark-'+a.attempt:raise ValueError('Cleanup container identity mismatch')
            subprocess.run(['docker','rm','-f',cid],capture_output=True,check=True,timeout=15)
            report['container_removed']=subprocess.run(['docker','inspect',cid],capture_output=True,timeout=15).returncode!=0
        report['input_identity_after']={path:sha(path)==want for path,want in request['input_sha256'].items()}
        if not all(report['input_identity_after'].values()):report['status']='input_changed';rc=1
        (root/'smoke-result.json').write_text(json.dumps(report,indent=2))
        with Store(home) as store:
            from .jobs import metadata
            refs=[]
            for path in root.rglob('*'):
                if path.is_file():
                    item=store.put_artifact(a.task,a.attempt+':'+str(path.relative_to(root)),path,'application/octet-stream',a.attempt);refs.append(item['artifact_id'])
            store.append_observation(a.task,dict(obs_id=a.attempt+':smoke',kind='deepseek_smoke',values=report,source_artifacts=refs,limitations='Model metadata matches only; full hashes not recomputed. Unified GPU memory may not be completely cgroup accounted.'))
            metadata(store, store.read(a.task,a.attempt), result_refs=refs+[a.attempt+':smoke'])
        print(json.dumps(dict(attempt=a.attempt,status=report['status'],output=report.get('generated_text'),container_removed=report.get('container_removed'))),flush=True)
    return rc

if __name__=='__main__':raise SystemExit(main())
