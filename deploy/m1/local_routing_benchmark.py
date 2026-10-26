"""Run the local MR development protocol alongside the existing Spark app.

Run on the Linux Docker host. Uses its already built app image and shared model
ports. Does not rebuild/restart the app, mount its state or acquire credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
from benchmarks.local_routing.protocol import CODE


def command(args):
    return subprocess.check_output(args,text=True).strip()


def checked(path):
    path=Path(path).absolute()
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('Non-symlink controller paths required')
    return path


def stage_sources(root):
    names=[*CODE,'benchmarks/__init__.py','benchmarks/local_routing/__init__.py',
        'benchmarks/harbor_suite/__init__.py','benchmarks/harbor_suite/contracts.py']
    raw={n:(REPO/n).read_bytes() for n in names}
    commit=command(['git','-C',str(REPO),'rev-parse','HEAD'])
    raw['source-identity.json']=json.dumps({'base_commit':commit,'source_status':'exact staged hashes; not a clean-build claim'}).encode()
    identity=hashlib.sha256(b''.join(n.encode()+hashlib.sha256(v).digest() for n,v in sorted(raw.items()))).hexdigest()
    dest=root/'controllers'/identity
    for name,data in raw.items():
        target=dest/name; target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            if target.read_bytes()!=data: raise ValueError('Frozen controller bytes changed')
        else:
            with target.open('xb') as stream: stream.write(data)
    return dest


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--root',type=Path,required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare'); p.add_argument('--cases-root',type=Path,required=True)
    p.add_argument('--workspace',required=True); p.add_argument('--mode',choices=['smoke','campaign'],default='smoke')
    p.add_argument('--case',action='append',default=[]);p.add_argument('--variant',action='append',default=[])
    for name in ('doctor','run','score','status'):
        p=sub.add_parser(name);p.add_argument('--workspace',required=True)
    args=parser.parse_args(argv)
    if os.name!='posix': raise ValueError('Run this launcher on the Linux/Spark Docker host over SSH')
    if not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}',args.workspace): raise ValueError('Invalid workspace name')
    root=checked(args.root); root.mkdir(parents=True,exist_ok=True)
    config=json.loads(checked(args.profile).read_text()); dep=config['deployment']
    image=dep['app_image']
    if not re.fullmatch('sha256:[a-f0-9]{64}',image): raise ValueError('Use the existing digest-pinned app image')
    workspace=root/'results'/args.workspace; control=root/(args.workspace+'-control.json')
    if args.command=='prepare':
        if control.exists() or workspace.exists(): raise ValueError('Use a new workspace; no overwrite/replay')
        source=stage_sources(root)
        script="import os;from pathlib import Path;print(Path(os.environ['JIUWENSWARM_M1_LOCAL_MODELS']).read_text())"
        models=json.loads(command(['docker','exec',dep['project']+'-ai4r-1','/opt/venv/bin/python','-c',script]))
        ports=dep['local_pool']['shared_access']['ports']
        for entry in models['models']:
            entry['base_url']='http://127.0.0.1:'+str(ports[entry['id']])+'/v1'
        model_file=root/(args.workspace+'-models.json')
        with model_file.open('x') as stream:json.dump(models,stream)
        metadata={'image':image,'controller':str(source),'models':str(model_file),
            'workspace':str(workspace),'container':dep['project']+'-mr-'+args.workspace,
            'inference_images':dep['local_pool']['images'],'weights':dep['local_pool']['models']}
        with control.open('x') as stream:json.dump(metadata,stream)
    else:
        metadata=json.loads(control.read_text());source=Path(metadata['controller']);model_file=Path(metadata['models'])
        if metadata['image']!=image: raise ValueError('Deployment image changed; prepare a new workspace')
    if args.command=='status':
        print(command(['docker','inspect',metadata['container'],'--format','{{json .State}}']))
        print(command(['docker','logs','--tail','12',metadata['container']]))
        return 0
    run=['docker','run','--read-only','--hostname',socket.gethostname(),'--user',str(os.getuid())+':'+str(os.getgid()),
        '--workdir','/tmp','--tmpfs','/tmp:rw,size=32m','--memory','1g','--cpus','1',
        '-e','PYTHONDONTWRITEBYTECODE=1','-e','PYTHONPATH=/controller',
        '--mount',f'type=bind,src={source},dst=/controller,readonly',
        '--mount',f'type=bind,src={model_file},dst=/control/models.json,readonly']
    # Exact measured core source is overlaid ONLY inside the isolated controller.
    # The running app image and its installed-build qualification are untouched.
    for name in CODE:
        if name.startswith('jiuwenswarm/'):
            run.extend(['--mount',f'type=bind,src={source/name},dst=/opt/venv/lib/python3.12/site-packages/{name},readonly'])
    run.extend(['--network','none' if args.command=='score' else 'host'])
    if args.command=='prepare':
        (root/'results').mkdir(exist_ok=True)
        run.extend(['--rm','--mount',f'type=bind,src={checked(args.cases_root)},dst=/cases,readonly',
            '--mount',f'type=bind,src={root}/results,dst=/results'])
    else:
        run.extend(['--mount',f'type=bind,src={workspace},dst=/results/{args.workspace}'+(',readonly' if args.command in {'doctor','score'} else '')])
        if args.command=='score':
            reviewer=workspace.with_name(workspace.name+'-reviewer')
            run.extend(['--mount',f'type=bind,src={reviewer},dst=/results/{args.workspace}-reviewer,readonly'])
        if args.command=='run':
            run.extend(['--detach','--name',metadata['container'],'--log-driver','local',
                '--log-opt','max-size=2m','--log-opt','max-file=2'])
        else: run.append('--rm')
    run.extend(['--entrypoint','/opt/venv/bin/python',image,'-B','-m','benchmarks.local_routing.protocol',args.command,
        '--workspace','/results/'+args.workspace])
    if args.command=='prepare':
        run.extend(['--cases-root','/cases','--models','/control/models.json','--mode',args.mode])
        for name in ('case','variant'):
            for value in getattr(args,name): run.extend(['--'+name,value])
    if args.command=='score':
        raw=subprocess.check_output(run)
        value=json.loads(raw)
        output=workspace/('assessment-'+hashlib.sha256(raw).hexdigest()[:12]+'.json')
        if not output.exists():
            with output.open('xb') as stream:stream.write(raw)
        print(json.dumps({'assessment':str(output),'scheduled':value['scheduled'],'observed':value['observed'],
            'quality_comparison_complete':value.get('quality_comparison_complete',False),
            'compatibility_correct':sum(r['disposition_correct'] is True for r in value['rows']),
            'unavailable':sum(r['status']=='unavailable' for r in value['rows'])}))
        return 0
    status=subprocess.call(run)
    if status==0 and args.command=='prepare':
        raw=json.dumps(metadata,sort_keys=True,separators=(',',':')).encode()
        with (workspace/'deployment.json').open('xb') as stream:stream.write(raw)
        with (workspace/'deployment-sha256.txt').open('x') as stream:stream.write(hashlib.sha256(raw).hexdigest())
    return status


if __name__=='__main__':
    raise SystemExit(main())
