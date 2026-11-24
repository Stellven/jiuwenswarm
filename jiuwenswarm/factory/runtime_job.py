"""Host-queued llama.cpp runtime packaging and bounded functional qualification."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import csv
from .jobs import metadata
from .store import Store
from .targets import labels, validate_image


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def command(argv, timeout=45):
    return subprocess.check_output(argv, text=True, stderr=subprocess.STDOUT, timeout=timeout).strip()


def gpu_activity(raw, pids):
    """Only count device memory attributed to a process in this container's cgroup."""
    matches=[]
    for row in csv.reader(raw.splitlines()):
        if len(row)!=3:continue
        try:pid=int(row[0].strip());mib=int(row[2].strip())
        except ValueError:continue
        if pid in pids and mib>=1024:matches.append(dict(pid=pid,process=row[1].strip(),used_memory_mib=mib))
    return matches


def assess(records, expected_count, checks, model_unchanged):
    successful=len(records)==expected_count and all(
        r['collector']['reason']=='completed' and r['collector'].get('container_exit_code')==0
        and r['collector']['quiescent'] and r['container_removed'] and bool(r['output'].strip())
        and r['gpu_activity_confirmed'] and r['cuda_backend_reported'] for r in records)
    repeated=(len(records)>=2 and records[0]['output']==records[-1]['output']) if checks.get('repeat_first_last') else None
    normalized=records[0]['output'].replace('[end of text]','').strip() if records else ''
    arithmetic=(normalized==checks['arithmetic_expected']) if 'arithmetic_expected' in checks else None
    return dict(status='success' if successful and repeated is not False and arithmetic is not False and model_unchanged else 'failed',
                repeated_output_equal=repeated,arithmetic_check=arithmetic)


def package(request, out):
    """Add target labels to an existing, byte-pinned native build; never claim recompilation."""
    record=json.loads(Path(request['upstream_record']).read_text())
    base=request['base_image_id']
    if record['status']!='success' or record['image_id']!=base:raise ValueError('Successful upstream build required')
    if '-DCMAKE_CUDA_ARCHITECTURES=121' not in record['flags'] or '-DGGML_CUDA=ON' not in record['flags']:
        raise ValueError('Upstream build does not establish CUDA/SM121')
    info=json.loads(command(['docker','image','inspect',base]))[0]
    if info['Id']!=base or info['Architecture']!='arm64':raise ValueError('Base image mismatch')
    binary=command(['docker','run','--rm','--network=none','--read-only','--memory=256m','--memory-swap=256m',
                    '--entrypoint','sha256sum',base,'/app/llama-completion']).split()[0]
    if binary!=record['binary_hashes']['llama-completion']:raise ValueError('Executable differs from build receipt')
    # Local tag is checked on both sides of the label-only Docker build.
    local='factory/llamacpp:ssh-build-warm-002'
    if command(['docker','image','inspect','--format','{{.Id}}',local])!=base:raise ValueError('Local base tag changed')
    dockerfile=out/'Dockerfile';dockerfile.write_text('FROM '+local+'\n')
    tag='factory/llamacpp:cc-dgx-spark-stable'
    argv=['docker','build','--network=none','--pull=false','-f',str(dockerfile),'-t',tag]
    for key,value in labels('spark-gb10').items():argv+=['--label',key+'='+value]
    argv+=['--label','factory.owner=cc-dgx-spark','--label','factory.source='+record['source_commit'],str(out)]
    log=command(argv,timeout=120);(out/'package.log').write_text(log)
    final=json.loads(command(['docker','image','inspect',tag]))[0]
    if final['RootFS']['Layers']!=info['RootFS']['Layers']:raise ValueError('Label-only package changed executable layers')
    validate_image('spark-gb10',final,'spark-gb10')
    return dict(status='success',image_id=final['Id'],tag=tag,target='spark-gb10',base_image_id=base,
                source_commit=record['source_commit'],source_tree=record['source_tree'],executable_sha256=binary,
                provenance='Imported existing successful native build; this attempt only packages hardware labels.',recompiled=False)


def collect(request,out):
    image=request['image_id'];info=json.loads(command(['docker','image','inspect',image]))[0]
    validate_image('spark-gb10',info,'spark-gb10')
    model=Path(request['model']['path']);before=model.stat()
    if before.st_size!=request['model']['bytes'] or sha(model)!=request['model']['sha256']:raise ValueError('Model content identity mismatch')
    gpu=command(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'])
    available=int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))*1024
    if gpu or available<32*2**30:raise ValueError('Host compute/memory admission failed')
    sys.path.insert(0,request['collector_root'])
    from spark_comparison import docker_cell as dc
    dc.MEMORY=24*2**30
    old=dc.memory_sample
    gpu_observations=[]
    def sample(*args,**kwargs):
        try:value=old(*args,**kwargs)
        except OSError as exc:
            if exc.errno==19:raise FileNotFoundError(str(exc)) from exc
            raise
        raw=command(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits'])
        pids={p['pid'] for p in value.get('processes',[])}
        rows=gpu_activity(raw,pids)
        if rows:gpu_observations.append(rows)
        value['gpu_compute_processes']=rows
        return value
    dc.memory_sample=sample
    records=[]
    for index,prompt in enumerate(request['prompts']):
        gpu_observations.clear()
        # GPT-OSS Harmony final-channel prefix avoids spending the bounded budget on hidden reasoning.
        wire='<|start|>system<|message|>You are a helpful assistant. Answer briefly.<|end|><|start|>user<|message|>'+prompt+'<|end|><|start|>assistant<|channel|>final<|message|>'
        argv=['/app/llama-completion','-m','/model/model.gguf','-p',wire,'-n','32','-c','1024','--temp','0','-s','42',
              '-t','8','-ngl','99','-no-cnv','--no-display-prompt','--no-repack','-lm','mmap','--no-warmup','--verbosity','3']
        name='strata-rsi-llama-'+request['attempt_id']+'-'+str(index)
        result=dc.run_docker(argv,output=out/('case-'+str(index)),mounts=[(model,'/model/model.gguf')],image=image,gpu=True,
                             timeout_s=300,interval_ms=1000,guard_gib=8,name=name)
        cid=result.get('container_id');removed=False
        if cid:
            saved=json.loads(command(['docker','inspect',cid]))[0]
            if saved['Name']!='/'+name:raise ValueError('Cleanup ownership mismatch')
            command(['docker','rm','-f',cid]);removed=subprocess.run(['docker','inspect',cid],capture_output=True).returncode!=0
        output=(out/('case-'+str(index))/'stdout.log').read_text()
        stderr=(out/('case-'+str(index))/'stderr.log').read_text()
        records.append(dict(prompt=prompt,output=output,collector=result,container_removed=removed,
                            gpu_activity_confirmed=bool(gpu_observations),gpu_observations=list(gpu_observations),
                            cuda_backend_reported='CUDA : ARCHS = 1210' in stderr))
        if result['reason']!='completed' or not result['quiescent'] or result.get('container_exit_code')!=0 or not output.strip() or not removed:break
    after=model.stat()
    unchanged=(before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_size,after.st_mtime_ns,after.st_ctime_ns)
    verdict=assess(records,len(request['prompts']),request.get('qualification_checks',{}),unchanged)
    return dict(**verdict,image_id=image,
                model=request['model'],model_stat_unchanged=unchanged,admission=dict(available_bytes=available,gpu_processes=gpu),
                records=records,
                limits=dict(cpus=8,memory_bytes=24*2**30,swap_extra_bytes=0,timeout_per_case_s=300,max_tokens_per_case=32),
                limitations=['Bounded functional cases are not a general accuracy, load or performance benchmark.',
                             'Shared model fully hashed before testing; no cold-cache claim.',
                             'Unified GPU physical memory may be incompletely cgroup accounted; host guard remains active.'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--task',required=True);p.add_argument('--attempt',required=True);a=p.parse_args()
    home=Path(os.environ['FACTORY_HOME']);out=home/'runtime-jobs'/a.attempt;out.mkdir(parents=True)
    result=dict(status='failed');request={};rc=1
    def stop(signum,frame):raise SystemExit(128+signum)
    previous_handler=signal.signal(signal.SIGTERM,stop)
    try:
        with Store(home) as store:attempt=store.read(a.task,a.attempt);request=attempt['request']
        if request['worker_sha256']!=sha(__file__):raise ValueError('Worker changed')
        (out/'worker.py').write_bytes(Path(__file__).read_bytes())
        for path,want in request['input_sha256'].items():
            if sha(path)!=want:raise ValueError('Pinned input changed: '+path)
        result=package(request,out) if request['operation']=='package' else collect(dict(request,attempt_id=a.attempt),out)
        rc=0 if result['status']=='success' else 1
    except BaseException as exc:result.update(status='failed',error=type(exc).__name__+': '+str(exc))
    finally:
        signal.signal(signal.SIGTERM,signal.SIG_IGN)
        # Even cancellation inside the collector must remove only this attempt's recorded containers.
        for path in out.glob('case-*/report.json'):
            report=json.loads(path.read_text());cid=report.get('container_id')
            if cid:
                found=subprocess.run(['docker','inspect',cid],capture_output=True,text=True)
                if found.returncode==0:
                    info=json.loads(found.stdout)[0]
                    if not info['Name'].startswith('/strata-rsi-llama-'+a.attempt+'-'):raise ValueError('Container ownership mismatch')
                    subprocess.run(['docker','rm','-f',cid],capture_output=True,check=True,timeout=15)
        (out/'result.json').write_text(json.dumps(result,indent=2))
        with Store(home) as store:
            refs=[]
            for path in out.rglob('*'):
                if path.is_file():refs.append(store.put_artifact(a.task,a.attempt+':'+str(path.relative_to(out)),path,'application/octet-stream',a.attempt)['artifact_id'])
            if request.get('operation')=='package' and result.get('image_id'):
                receipt=dict(image_id=result['image_id'],target='spark-gb10',provenance=result['provenance'])
                refs.append(store.put_artifact(a.task,a.attempt+':receipt',json.dumps(receipt).encode(),'application/json',a.attempt)['artifact_id'])
            obs=store.append_observation(a.task,dict(obs_id=a.attempt+':runtime',kind='llamacpp_'+request.get('operation','unknown'),values=result,source_artifacts=refs))
            metadata(store,store.read(a.task,a.attempt),result_refs=refs+[obs['obs_id']])
        print(json.dumps(dict(attempt_id=a.attempt,status=result['status'],image_id=result.get('image_id'),error=result.get('error'))),flush=True)
    signal.signal(signal.SIGTERM,previous_handler)
    return rc

if __name__=='__main__':raise SystemExit(main())
