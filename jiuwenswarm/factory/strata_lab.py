"""Contract-bound Strata lab worker and replay-safe evidence import."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from .contract import atomic_json
from .engine_adapters import inspect_assets, parse_protocol, protocol, sha, validate_contract, verify_cell_evidence
from .store import encoded


def submit(manager, task_id, admission, contract, run_config, idem_key, node_id=None):
    if contract.get("adapter")=="llama-server-v1":
        from .llama_adapter import validate_contract
    else:
        from .engine_adapters import validate_contract
    task=manager.store.get_task(task_id)
    if task['contract_id'] not in {contract['contract_id'], str(contract.path)}:
        raise ValueError('Lab contract must match the task')
    validate_contract(contract)
    wanted = task.get('constraints', {}).get('contract_sha256')
    if not wanted or sha(contract.path) != wanted:
        raise ValueError('Operator contract content identity missing or changed')
    if admission['target_profile']!=contract['target']:
        raise ValueError('Adapter target differs from admitted image')
    profile = run_config.get('profile')
    plain_config = {k: v for k, v in run_config.items() if k != 'profile'}
    if (profile not in ((None,) if contract['adapter']=='llama-server-v1' else (None,'strata-native')) or
        plain_config not in ({},{'env':{}}, {'env':contract['workload']['environment']})):
        raise ValueError('Repeatability workload is fixed; changes require a new contract/task')
    from .mission_supervisor import mission_root
    request=dict(quiet_root=str(mission_root(manager.store.home, task_id)), adapter=contract['adapter'],admission=admission,contract=dict(contract),
        quiet_required=bool(task.get('constraints',{}).get('quiet_required',False)),
        worker_sha256=sha(__file__),adapter_sha256=sha(Path(__file__).with_name('engine_adapters.py')),
        execution_sha256={name:sha(Path(__file__).with_name(name)) for name in ('lab_recorder.py','lab_lifecycle.py')})
    if contract['adapter']=='llama-server-v1':
        request['adapter_sha256']=sha(Path(__file__).with_name('llama_adapter.py'))
        request['execution_sha256']['llama_http_driver.py']=sha(Path(__file__).with_name('llama_http_driver.py'))
    if profile:
        request['profile'] = profile
    if node_id is not None:request['node_id']=node_id
    path=manager.spool_root/'configs'/(hashlib.sha256(encoded(request).encode()).hexdigest()+'.json')
    if not path.exists():atomic_json(path,request)
    argv=[os.environ.get('FACTORY_HOST_PYTHON',sys.executable),'-m','jiuwenswarm.factory.strata_lab',
        '--task',task_id,'--run','{attempt_id}','--config',str(path),'--spool',str(manager.spool_root)]
    return manager.jobs.submit(task_id,'lab',request,idem_key,'gpu',argv,
        contract['limits']['timeout_s']+180,dict(FACTORY_HOME=str(manager.store.home)))


def wait_quiet(home, attempt_id, timeout_s=120, quiet_root=None):
    quiet_root = Path(quiet_root) if quiet_root else home/'mission'
    deadline=time.monotonic()+timeout_s
    while time.monotonic()<deadline:
        try:
            receipt_path = quiet_root/'quiet'/f'{attempt_id}.json'
            if not receipt_path.exists(): receipt_path = quiet_root/'quiet.json'
            receipt=json.loads(receipt_path.read_text())
            if (receipt.get('attempt_id')==attempt_id and receipt.get('control_stopped') is True
                and receipt.get('boot_id')==Path('/proc/sys/kernel/random/boot_id').read_text().strip()):
                return receipt
        except (FileNotFoundError,ValueError):pass
        time.sleep(.2)
    raise ValueError('Quiet receipt missing; controller must exit before lab execution')


def run(home, task_id, attempt_id, request, spool):
    if request.get('adapter')=='llama-server-v1':
        from .llama_adapter import validate_contract, inspect_assets, parse_protocol
    else:
        from .engine_adapters import validate_contract, inspect_assets, parse_protocol
    from .lab_recorder import run_container
    from .store import Store
    from .targets import validate_image
    from .lab_runner import inspect_image
    root=spool/attempt_id;root.mkdir(parents=True,exist_ok=True)
    if (root/'manifest.json').exists():raise ValueError('Sealed lab run cannot execute twice')
    atomic_json(root/'config.json',dict(request,lab_run_id=attempt_id))
    result=dict(execution_outcome='measurement_failed',evidence_completeness='partial',
        comparison_group=hashlib.sha256(encoded(dict(contract=request['contract'],image=request['admission']['image']['id'])).encode()).hexdigest())
    try:
        with Store(home) as store:
            if store.read(task_id,attempt_id)['request']!=request:
                raise ValueError('Persisted worker request differs')
        if sha(__file__)!=request['worker_sha256'] or sha(Path(__file__).with_name('llama_adapter.py' if request['adapter']=='llama-server-v1' else 'engine_adapters.py'))!=request['adapter_sha256']:
            raise ValueError('Worker source changed')
        for name, want in request['execution_sha256'].items():
            if name not in {'lab_recorder.py','lab_lifecycle.py','llama_http_driver.py'} or sha(Path(__file__).with_name(name)) != want:
                raise ValueError('Admitted execution source changed')
        if request['quiet_required']:result['quiet']=wait_quiet(home,attempt_id,quiet_root=request.get('quiet_root'))
        contract=validate_contract(request['contract'])
        from .lab_recorder import host_available
        import subprocess
        gpu = subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],text=True).strip()
        result['admission'] = dict(gpu_processes=gpu, available_bytes=host_available())
        if gpu or result['admission']['available_bytes'] < 108*2**30:
            raise ValueError('Unrelated GPU compute or insufficient host memory')
        image=request['admission']['image']['id']
        validate_image(contract['target'],inspect_image(image),contract['target'])
        result['assets_before']=inspect_assets(contract)
        work=contract['workload'];limits=contract['limits']
        argv=['/opt/strata/strata-dsv41',*work['argv'],'--profile-readonly','--serve']
        mounts=[(work['pack'],work['pack']),(work['model_root'],work['model_root'])]
        wire=protocol(contract) if request['adapter']=='strata-v1' else None
        if request['adapter']=='llama-server-v1':
            from .llama_adapter import command
            argv,mounts=command(root,contract)
        collected=run_container(argv,output=root/'cell',image=image,
            mounts=mounts,
            gpu=True,environment=execution_environment(request),protocol=wire,
            timeout_s=limits['timeout_s'],guard_gib=limits['guard_gib'],
            memory_bytes=limits['memory_bytes'],cpus=limits['cpus'],lease_root=home.parent/'lab-lease')
        result['collector']=collected
        result['assets_after']=inspect_assets(contract)
        parsed=parse_protocol((root/'cell/stdout.log').read_text(),(root/'cell/stderr.log').read_text(),contract)
        result.update(parsed)
        if request.get('profile'):
            from .deep_profile import native_stages
            result.update(traced=True, scoring_eligible=False,
                native_profile=native_stages((root/'cell/stderr.log').read_text()))
        if (collected['reason']=='completed' and collected['quiescent'] and collected['container_removed']
            and collected.get('container_exit_code')==0):
            result.update(execution_outcome='ok',evidence_completeness='complete')
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc)
    atomic_json(root/'worker.json',result)
    seal(root,task_id,attempt_id,request)
    return 0 if result['execution_outcome']=='ok' else 1


def seal(root,task_id,attempt_id,request):
    files={str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file()
        and p.name not in {'manifest.json','ack.json'} and not p.name.endswith('.lock')}
    atomic_json(root/'manifest.json',dict(task_id=task_id,lab_run_id=attempt_id,
        admission_id=request['admission']['admission_id'],contract_id=request['contract']['contract_id'],files=files))


def recover_upload(manager, task_id, attempt_id, root):
    from .lab_lifecycle import recover_run
    request = manager.store.read(task_id, attempt_id)['request']
    root.mkdir(parents=True, exist_ok=True)
    if (root/'manifest.json').exists():
        return
    if (root/'cell/intent.json').exists():
        recover_run(root/'cell', reason='worker_lost')
    atomic_json(root/'config.json', dict(request, lab_run_id=attempt_id))
    atomic_json(root/'worker.json', dict(execution_outcome='measurement_failed',
        evidence_completeness='partial', error='Worker exited without sealing a complete lab result'))
    seal(root, task_id, attempt_id, request)


def ingest(manager,task_id,attempt_id,root):
    """Verify bytes before committing; parse metrics again instead of trusting worker summaries."""
    request=manager.store.read(task_id,attempt_id)['request']
    if request.get('adapter')=='llama-server-v1':
        from .llama_adapter import inspect_assets, parse_protocol, verify_cell_evidence
    else:
        from .engine_adapters import inspect_assets, parse_protocol, verify_cell_evidence
    raw=(root/'manifest.json').read_bytes();manifest=json.loads(raw)
    if (manifest['task_id']!=task_id or manifest['lab_run_id']!=attempt_id
        or manifest['admission_id']!=request['admission']['admission_id']
        or manifest['contract_id']!=request['contract']['contract_id']):
        raise ValueError('Strata upload identity differs')
    content={}
    for name,want in manifest['files'].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()) or name in {'manifest.json','ack.json'}:
            raise ValueError('Upload path escapes lab bundle')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=want:raise ValueError('Upload hash mismatch: '+name)
        content[name]=data
    if json.loads(content['config.json'])!=dict(request,lab_run_id=attempt_id):
        raise ValueError('Strata uploaded configuration differs')
    worker=json.loads(content['worker.json'])
    parsed={};outcome=worker['execution_outcome'];complete=worker['evidence_completeness']
    if outcome=='ok':
        verified = verify_cell_evidence(content, request)
        current_assets = inspect_assets(request['contract'])
        if worker.get('assets_before') != current_assets or worker.get('assets_after') != current_assets:
            raise ValueError('Asset verification evidence differs')
        parsed=parse_protocol(content['cell/stdout.log'].decode(),content['cell/stderr.log'].decode(),request['contract'])
        collector=json.loads(content['cell/report.json'])
        if not (collector['reason']=='completed' and collector['quiescent'] and collector['container_removed']
                and collector['container_exit_code']==0):raise ValueError('Successful upload lacks cleanup/exit evidence')
        if request['adapter']=='llama-server-v1':
            build=json.loads(manager.store.artifact_bytes(task_id,request['admission']['build_attempt_id']+':build-record'))
            if parsed['executable_sha256']!=build.get('executable_sha256'):raise ValueError('Executed binary differs from build receipt')
        if worker.get('requests')!=parsed['requests']:raise ValueError('Worker native metrics differ from raw records')
    digest=hashlib.sha256(raw).hexdigest()
    from .manager import UploadConflict
    with manager.jobs.locked():
        old=manager.store._db.execute('SELECT * FROM uploads WHERE task_id=? AND lab_run_id=?',(task_id,attempt_id)).fetchone()
        if old and old['sha256']!=digest:raise UploadConflict('Sealed Strata upload changed')
        ack=dict(upload_id=attempt_id+':upload',sha256=digest,ack_state='durable')
        if not old:
            refs=[]
            for name,data in dict(content,**{'manifest.json':raw}).items():
                art=manager.store.put_artifact(task_id,attempt_id+':'+name,data,'application/octet-stream',attempt_id)
                refs.append(art['artifact_id'])
            now=time.time();obs_id=attempt_id+':observation';eval_id=attempt_id+':evaluation'
            values=dict(worker,**parsed)
            identity = dict(contract=request['contract'],image=request['admission']['image']['id'])
            if request.get('profile'):
                from .deep_profile import native_stages
                identity['profile'] = request['profile']
                # Derive observer classification from the sealed host request,
                # never trust worker-supplied scoring/trace fields.
                values.update(traced=True, scoring_eligible=False,
                    native_profile=native_stages(content.get('cell/stderr.log', b'').decode()))
            values['comparison_group'] = hashlib.sha256(encoded(identity).encode()).hexdigest()
            if outcome == 'ok': values['verification'] = verified
            with manager.store._transaction():
                manager.store._insert('observations',dict(obs_id=obs_id,task_id=task_id,
                    kind='profile_result' if request.get('profile') else 'lab_result',values=values,
                    source_artifacts=refs.copy(),error={},host_run={'attempt_id':attempt_id},confidence=None,
                    limitations=request['contract'].get('scope', 'Native Strata evidence; quality and speedup not established.'),created=now))
                manager.store._insert('evaluations',dict(eval_id=eval_id,task_id=task_id,
                    contract_id=request['contract']['contract_id'],contract_version=str(request['contract']['version']),
                    contract=request['contract'],inputs=dict(run=values,source_artifacts=refs.copy(),observation_id=obs_id),
                    execution_outcome=outcome,correctness='not_evaluated',evidence_completeness=complete,created=now))
                manager.store._db.execute('UPDATE attempts SET result_refs=? WHERE task_id=? AND attempt_id=?',
                    (encoded(refs+[obs_id,eval_id]),task_id,attempt_id))
                manager.store._insert('uploads',dict(task_id=task_id,lab_run_id=attempt_id,**ack,created=now))
        atomic_json(root/'ack.json',ack)
    return ack


def execution_environment(request):
    """Host-controlled observer mode; no arbitrary profiling env or dump path."""
    environment = dict(request['contract']['workload']['environment'])
    profile = request.get('profile')
    if profile not in (None, 'strata-native'):
        raise ValueError('Unsupported native Strata profile mode')
    if profile:
        environment['DS4_PROF'] = '1'
    return environment


def main():
    p=argparse.ArgumentParser()
    for key in ('task','run','config','spool'):p.add_argument('--'+key,required=True)
    args=p.parse_args()
    return run(Path(os.environ['FACTORY_HOME']),args.task,args.run,json.loads(Path(args.config).read_text()),Path(args.spool))

if __name__=='__main__':raise SystemExit(main())
