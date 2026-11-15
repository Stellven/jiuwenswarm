"""Prepare an operator-owned Spark task and full asset identity outside timed runs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from jiuwenswarm.factory.contract import atomic_json
from jiuwenswarm.factory.engine_adapters import sha, validate_contract


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=Path('/home/user2/software-factory-spark-20261113'))
    p.add_argument('--home',type=Path)
    p.add_argument('--task',default='spark-strata-e2e-001')
    a=p.parse_args();root=a.root.resolve();home=(a.home or root/'mission-store').resolve()
    home.mkdir(parents=True,exist_ok=True)
    identity=root/'assets/deepseek-full-identity-v1.json'
    manifest=json.loads((root/'notes/port-pack-source.json').read_text())
    if identity.exists():
        inventory=json.loads(identity.read_text())
        for row in inventory['files']:
            stat=Path(row['path']).stat()
            if any(getattr(stat,k)!=row[k] for k in ('st_size','st_mtime_ns','st_ctime_ns')):
                raise ValueError('Existing asset inventory stale; investigate before creating a new version')
    else:
        files=[]
        for name,(size,mtime) in manifest['files'].items():
            path=(Path(manifest['model_dir'])/name).resolve();before=path.stat()
            if before.st_size!=size or before.st_mtime_ns!=mtime:raise ValueError('Transferred model metadata differs')
            print('Hashing model asset: '+path.name,flush=True)
            digest=sha(path);after=path.stat()
            if any(getattr(before,k)!=getattr(after,k) for k in ('st_size','st_mtime_ns','st_ctime_ns','st_ino','st_dev')):
                raise ValueError('Asset changed while hashing')
            files.append(dict(path=str(path),sha256=digest,**{k:getattr(after,k) for k in ('st_size','st_mtime_ns','st_ctime_ns')}))
        pack_files=json.loads((root/'notes/port-pack-identity.json').read_text())
        for path,want in pack_files.items():
            if sha(path)!=want:raise ValueError('Transferred pack identity differs')
        inventory=dict(version=1,files=files,pack_files=pack_files,full_hash_verification=True)
        atomic_json(identity,inventory)
    source=root/'sources/strata-deepseek';owned=home/'agent-workspace/strata'
    owned.parent.mkdir(parents=True,exist_ok=True)
    if not owned.exists():
        subprocess.run(['git','clone','--local','--no-hardlinks','--dissociate',str(source),str(owned)],check=True)
        subprocess.run(['git','-C',str(owned),'checkout','-b','spark-mission'],check=True)
    commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if subprocess.check_output(['git','-C',str(owned),'rev-parse','HEAD'],text=True).strip()!=commit:
        raise ValueError('Owned initial checkout differs; do not reset it')
    config=json.loads((root/'engine-investigation/measured-profile.json').read_text())
    args=config['args'];args[args.index('--dspark')+1]='none'
    if '--dspark-conf' in args:
        i=args.index('--dspark-conf');del args[i:i+2]
    if '--no-expert-cache' not in args:args.append('--no-expert-cache')
    cases=json.loads((root/'engine-investigation/long-workload.json').read_text())['cases'][:1]
    requests=[dict(ids=cases[0]['ids'],max_new_tokens=128)]*2
    c=dict(adapter='strata-v1',contract_id=a.task+'-repeatability-v1',version=1,target='spark-gb10',
        tolerance='canonical-token-ids-and-finish',scope='Full six experts; functional repeatability only, no task accuracy or scored speedup claim.',
        assets=dict(identity_path=str(identity),identity_sha256=sha(identity)),
        workload=dict(argv=args,environment=config['environment'],requests=requests,pack=config['pack'],model_root=config['model_root']),
        limits=dict(cpus=8,memory_bytes=104*2**30,extra_swap_bytes=0,guard_gib=8,timeout_s=900))
    validate_contract(c)
    contract=home/'operator-contract.json'
    if contract.exists() and json.loads(contract.read_text())!=c:raise ValueError('Refuse to change operator contract')
    atomic_json(contract,c)
    dependency=root/'sources/strata-ggml'
    dep_commit=subprocess.check_output(['git','-C',str(dependency),'rev-parse','HEAD'],text=True).strip()
    build=dict(target='spark-gb10',source=dict(path=str(owned),commit=commit),
        dependency=dict(path=str(dependency),commit=dep_commit),tag='factory/strata:'+a.task,deadline_s=5400,env={})
    task=dict(task_id=a.task,objective='Establish a reproducible full-six-expert oversized Strata reference. Inspect the operator contract, '
        'build the pinned source natively through builder.submit using constraints.build_request, then run three fresh lab cells '
        'through lab_client.submit (two identical requests per cell). Query and cite receipts. Use methodology diagnosis, '
        'cache protocol and followup CCs. Stop scored optimization on token differences. Return a report and proposed next input; '
        'a proposal is not authority to change this contract. Do not commit unmodified code or enable new mechanisms just to demonstrate activity.',
        constraints=dict(local_commits=True,methodology_driven=True,required_successful_cells=3,quiet_required=True,contract_sha256=sha(contract),build_request=build,
            attempt_limits=dict(build=2,lab=6),read_tasks=[]),
        allowed_effects=['process.exec','workspace.read','workspace.write','gpu.use'],target={'profile':'spark-gb10'},
        budget=dict(max_turns=24,wall_clock_s=14400),contract_id=str(contract),initial_run_config={'env':{}},
        component_cc='factory.methodology_out_of_core',capability_cc='factory.methodology_diagnosis',
        source=dict(subpath='strata',pre_integration_commit=commit,branch='spark-mission'),
        resources=dict(cell_timeout_s=900,cpus=8,memory_bytes=104*2**30))
    path=home/'operator-task.json'
    if path.exists() and json.loads(path.read_text())!=task:raise ValueError('Refuse to change existing task')
    atomic_json(path,task)
    print(json.dumps(dict(home=str(home),task_file=str(path),contract=str(contract),assets=str(identity),model_bytes=sum(r['st_size'] for r in inventory['files']))))

if __name__=='__main__':main()
