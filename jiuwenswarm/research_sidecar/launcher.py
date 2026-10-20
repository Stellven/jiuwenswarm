"""Finite host orchestration. This module is never granted to the sidecar driver."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import argparse
import platform
import sys
import uuid
from datetime import datetime,timezone
from .cleanup import cleanup_plan
from .evidence import write_once


PROJECT=re.compile(r'^ai4r-(qa|verify)-[a-z0-9][a-z0-9-]{0,48}$')
OVERLAYS=frozenset({'deploy/m1/compose.sidecar.yaml','deploy/m1/compose.rsi.yaml',
    'deploy/m1/compose.routing.yaml','deploy/m1/compose.rsi-inbox.yaml','deploy/m1/compose.qa-rsi.yaml'})
SERVICES=frozenset({'app','rsi-workbench','rsi-custodian','rsi-worker-broker'})


def protected_json(path):
    p=Path(path)
    if not p.is_absolute() or any(q.is_symlink() for q in (p,*p.parents)) or not p.is_file() or p.stat().st_size>4*1024*1024:
        raise ValueError('Protected host manifest path required')
    if os.name=='posix' and p.stat().st_mode&0o022:raise ValueError('Host manifest permits an untrusted writer')
    return json.loads(p.read_bytes())


def docker_prefix():
    if shutil.which('docker'):return ['docker']
    if os.name=='nt' and shutil.which('wsl'):return ['wsl','-d','Ubuntu','-u','root','--']
    raise ValueError('Qualified Docker host command is unavailable')


def docker_path(path):
    path=Path(path).resolve()
    if os.name=='nt':
        text=path.as_posix()
        if len(text)>2 and text[1]==':':return '/mnt/'+text[0].lower()+text[2:]
    return str(path)


class HostLauncher:
    def __init__(self,repo,manifest):
        self.repo=Path(repo).resolve(strict=True);self.manifest=manifest
        if not PROJECT.fullmatch(manifest['project']) or not manifest['job_id']:raise ValueError('unique job-scoped project required')
        if not re.fullmatch('[a-z0-9][a-z0-9-]{0,47}',manifest['job_id']):raise ValueError('invalid owned job identity')
        self.overlays=list(manifest.get('compose_files',['deploy/m1/compose.sidecar.yaml']))
        if len(set(self.overlays))!=len(self.overlays) or any(v not in OVERLAYS for v in self.overlays):raise ValueError('Unknown or duplicate host Compose overlay')
        if 'deploy/m1/compose.sidecar.yaml' not in self.overlays:raise ValueError('Supported benchmark overlay required')
    def _docker(self,args,*,environment=None,timeout=300):
        prefix=docker_prefix();environment={**os.environ,'AI4R_JOB_ID':self.manifest['job_id'],**(environment or {})}
        if prefix[0]=='wsl':
            values={key:environment[key] for key in ('AI4R_JOB_ID','AI4R_BENCH_JOB') if key in environment}
            prefix += ['env',*[key+'='+value for key,value in values.items()],'docker']
        return subprocess.run([*prefix,*args],cwd=self.repo,env=environment,capture_output=True,text=True,timeout=timeout,check=False)
    def _compose(self,args,*,environment=None):
        command=['compose','-p',self.manifest['project']]
        if self.manifest.get('environment_file'):
            path=Path(self.manifest['environment_file']);protected_json_check=path.stat()
            if path.is_symlink() or not path.is_file() or os.name=='posix' and protected_json_check.st_mode&0o022:raise ValueError('Protected Compose environment file required')
            command+=['--env-file',docker_path(path)]
        for name in ['deploy/m1/compose.yaml',*self.overlays]:command+=['-f',name]
        return self._docker([*command,*args],environment=environment)
    def start(self):
        services=self.manifest.get('services',['app'])
        if not services or any(v not in SERVICES for v in services):raise ValueError('Unapproved host service requested')
        return self._compose(['--profile','benchmark','--profile','rsi','up','-d',*services])
    def run_case(self,*,campaign,case,variant,run_id=None,job_file=None):
        if case not in {'capsule','verifier','routing','rsi'} or not re.fullmatch('[a-z0-9_.-]+',variant):raise ValueError('unsupported case')
        if not re.fullmatch('[a-z0-9_.-]+',campaign) or run_id is not None and not re.fullmatch('[a-z0-9_.-]+',run_id):raise ValueError('Invalid frozen case/run identity')
        args=['--profile','benchmark','run','--rm','--no-deps','sidecar','run','--campaign',campaign,'--case',case,'--variant',variant]
        if run_id:args+=['--run-id',run_id]
        return self._compose(args,environment={'AI4R_BENCH_JOB':docker_path(job_file)} if job_file else None)
    def _observed(self,resource):
        if resource['kind']=='scratch':return None
        if resource['kind'] not in {'container','network'}:return None
        result=self._docker([resource['kind'],'inspect',resource['id']],timeout=30)
        if result.returncode:raise ValueError('Owned resource cannot be inspected')
        rows=json.loads(result.stdout)
        if len(rows)!=1:raise ValueError('Ambiguous resource identity')
        row=rows[0];labels=row.get('Config',{}).get('Labels',{}) if resource['kind']=='container' else row.get('Labels',{})
        return {'job_id':labels.get('ai4r.owner'),'project':labels.get('com.docker.compose.project')}
    def cleanup(self,observed=None):
        actual={r['id']:self._observed(r) for r in self.manifest['resources'] if r['disposable'] and r['kind']!='scratch'}
        if observed is not None and any(observed.get(k)!=v for k,v in actual.items()):raise ValueError('Cleanup ownership observation changed')
        result=[{'kind':'scratch','id':row['id'],'status':'retained','reason':'No qualified owned-path deletion adapter; no filesystem deletion attempted'}
            for row in self.manifest['resources'] if row['disposable'] and row['kind']=='scratch']
        scoped={**self.manifest,'resources':[row for row in self.manifest['resources'] if row['kind']!='scratch']}
        for row in cleanup_plan(scoped,actual):
            if row['kind']=='scratch':
                # Scratch deletion is deliberately left to an exact owned path adapter;
                # never turn an untrusted resource ID into a recursive filesystem delete.
                result.append({**row,'status':'retained','reason':'explicit path adapter required'});continue
            if self._observed(row)!={'job_id':self.manifest['job_id'],'project':self.manifest['project']}:raise ValueError('Cleanup ownership changed')
            if row['kind']=='container':self._docker(['stop','--time','45',row['id']],timeout=60)
            completed=self._docker([row['kind'],'rm',row['id']],timeout=60)
            result.append({**row,'status':'removed' if completed.returncode==0 else 'failed','exit_code':completed.returncode})
        return result


def launch_main(argv=None):
    """Host-only finite preflight/run/cleanup, using a protected job manifest."""
    parser=argparse.ArgumentParser(prog='benchmark-host launch')
    parser.add_argument('--campaign',required=True);parser.add_argument('--project',required=True)
    parser.add_argument('--job-manifest',default=os.environ.get('AI4R_QA_HOST_JOB'))
    parser.add_argument('--phase',choices=['preflight','run','cleanup'],default='preflight')
    parser.add_argument('--case',choices=['capsule','verifier','routing','rsi']);parser.add_argument('--variant')
    parser.add_argument('--custodian-session-ref',default=None)
    args=parser.parse_args(argv)
    try:
        if not args.job_manifest:raise ValueError('Protected host-job manifest is absent')
        manifest=protected_json(Path(args.job_manifest).resolve());launcher=HostLauncher(manifest['repo'],manifest)
        if manifest['project']!=args.project:raise ValueError('Project differs from protected ownership grant')
        destination=Path(manifest['output_root'])/'host'/('launch-'+uuid.uuid4().hex)
        destination.mkdir(mode=0o750,parents=True,exist_ok=False)
        if args.phase=='cleanup':
            write_once(destination/'cleanup.json',launcher.cleanup());return 0
        from .cli import _campaign
        path=Path(args.campaign).resolve(strict=True);frozen=json.loads(path.read_bytes())
        if path.name!='campaign.json':raise ValueError('Use the actual frozen campaign.json beside cases/module-map/schedule')
        folder,campaign,cases=_campaign(path.parent.parent.parent,frozen['campaign_id'])
        if folder.resolve()!=path.parent:raise ValueError('Campaign file is outside its registered layout')
        from .cases import schedule
        rows=[r for r in schedule(campaign,cases) if (not args.case or r['module']==args.case) and (not args.variant or r['variant_id']==args.variant)]
        if not rows:raise ValueError('No frozen scheduled population selected')
        started=launcher.start()
        write_once(destination/'start.stdout',started.stdout.encode());write_once(destination/'start.stderr',started.stderr.encode())
        write_once(destination/'start.json',{'exit_code':started.returncode,'project':manifest['project'],'job_id':manifest['job_id']})
        if started.returncode:return 2
        from .inventory import collect
        from .evidence import read_verified
        job=protected_json(Path(manifest['job_grant_file']).resolve())
        if job['campaign_id']!=campaign['campaign_id']:raise ValueError('Job grant differs from frozen campaign')
        blocked=False
        for row in rows:
            case=next(c for c in cases if c['case_id']==row['case_id'])
            role='orchestration' if platform.system()=='Windows' else 'experiment'
            inventory=collect(campaign_id=row['campaign_id'],run_id=row['run_id'],repeat_index=row['repeat_index'],
                host_profile='other_declared' if role=='orchestration' else case['host_profile'],role=role,budgets=case['budgets'],
                workspace=launcher.repo,requirements={} if role=='orchestration' else case['hardware_requirements'],
                capture=lambda name,value:write_once(destination/(row['run_id']+'-'+name+'.json'),value))
            companion=None
            if role=='orchestration':
                companion=write_once(folder/'host-inventories'/(inventory['inventory_id']+'.json'),inventory)
                try:
                    experiment_ref=job['inventories'][row['run_id']]
                    experiment=json.loads(read_verified(folder,experiment_ref))
                    if (experiment['campaign_id'],experiment['run_id'],experiment['repeat_index'],experiment['role'])!=(row['campaign_id'],row['run_id'],row['repeat_index'],'experiment'):raise ValueError('Experiment inventory identity/role differs')
                    captured=datetime.fromisoformat(experiment['collected_at'].replace('Z','+00:00'))
                    if captured<datetime.fromisoformat(campaign['frozen_at'].replace('Z','+00:00')) or captured>datetime.now(timezone.utc):raise ValueError('Experiment inventory is outside the actual frozen attempt period')
                    inventory=experiment
                except (ValueError,KeyError,OSError):
                    inventory={**inventory,'readiness':'blocked','readiness_reasons':[*inventory['readiness_reasons'],
                        'Separate fresh qualified experiment-host inventory is required; Windows observations do not stand in for Docker VM facts']}
            blocked=blocked or inventory['readiness']!='ready'
            reference=write_once(folder/'host-inventories'/(inventory['inventory_id']+'-'+uuid.uuid4().hex[:8]+'.json'),inventory)
            relative_path=str(Path(reference['path']).relative_to(folder).as_posix())
            if args.phase=='preflight':continue
            current=json.loads(json.dumps(job));current['inventories']={**current.get('inventories',{}),row['run_id']:{'path':relative_path,'sha256':reference['sha256']}}
            if companion:
                current['orchestration_inventories']={**current.get('orchestration_inventories',{}),row['run_id']:{
                    'path':Path(companion['path']).relative_to(folder).as_posix(),'sha256':companion['sha256']}}
            if args.custodian_session_ref is not None:
                expected=json.loads(args.custodian_session_ref)
                if row['module']!='rsi' or current['rsi_jobs'][row['run_id']]['job_ref']!=expected:raise ValueError('RSI argument differs from the already approved exact job grant')
            grant=destination/(row['run_id']+'-job.json');write_once(grant,current)
            if os.name=='posix':
                os.chown(destination,-1,11001);os.chmod(destination,0o2750);os.chown(grant,-1,11001);os.chmod(grant,0o640)
            completed=launcher.run_case(campaign=row['campaign_id'],case=row['module'],variant=row['variant_id'],run_id=row['run_id'],job_file=grant)
            blocked=blocked or completed.returncode!=0
            write_once(destination/(row['run_id']+'.stdout'),completed.stdout.encode());write_once(destination/(row['run_id']+'.stderr'),completed.stderr.encode())
            write_once(destination/(row['run_id']+'.json'),{'run_id':row['run_id'],'exit_code':completed.returncode,'inventory_ref':reference})
        return 2 if blocked else 0
    except (OSError,ValueError,KeyError,subprocess.TimeoutExpired):
        print('BLOCKED: protected finite host job, frozen campaign, qualified host/image or owned resources unavailable.',file=sys.stderr);return 2
