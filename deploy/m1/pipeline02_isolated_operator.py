"""Isolated Pipeline02 operator staging and explicit startup actions.

Run on the Linux Docker host as root. No action touches another deployment;
relay configuration is read via the existing supported local-model operator.
Commands never print bootstrap URLs, session bytes, or runner token contents.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import time

PYTHON='/opt/venv/bin/python'


def local_operator():
    spec=importlib.util.spec_from_file_location('pipeline02_local_model_operator',Path(__file__).resolve().with_name('local_model_operator.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def docker(deployment,*args,data=None,timeout=180):
    result=subprocess.run(['docker',*args],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if result.returncode:
        # Runtime output may contain a bootstrap credential. Keep it private.
        raise RuntimeError('Docker action failed; inspect this deployment privately: '+str(args[0]))
    return result.stdout


def compose(p,*args,**kwargs):
    return docker(p,'compose','-p',p['project'],'-f',str(Path(p['root'])/'compose.json'),*args,**kwargs)


def publish(path,value):
    path=Path(path);temporary=path.with_suffix('.new');temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.chmod(0o600);temporary.replace(path)


def mount_volume(name,target,readonly=False):
    return {'type':'volume','source':name,'target':target,'read_only':readonly,'volume':{'nocopy':True}}


def bind(source,target):
    return {'type':'bind','source':str(source),'target':target,'read_only':True,'bind':{'create_host_path':False}}


def stage(args):
    if os.name!='posix' or os.geteuid()!=0:raise ValueError('Run staging on the Linux Docker host as root')
    if not re.fullmatch(r'ai4r-pipeline02-[a-z0-9-]{1,48}',args.project):raise ValueError('Use a new ai4r-pipeline02-* project')
    for image in (args.app_image,args.runner_image):
        if not re.fullmatch(r'sha256:[0-9a-f]{64}',image):raise ValueError('Use exact built local image IDs')
    root=Path(args.directory).absolute()
    if root.exists():raise ValueError('Use a fresh isolated deployment directory')
    public=Path(args.public_data).resolve(strict=True);suite=Path(args.suite_root).resolve(strict=True)
    if not public.is_file() or not suite.is_dir():raise ValueError('Explicit public cache file and suite directory required')
    profile,catalog_raw,_=local_operator().inspect_sources(args.relay_catalog,args.relay_session,args.relay_sockets,ready=True)
    existing=docker({},'volume','ls','--format','{{.Name}}').decode().splitlines()
    if any(name.startswith(args.project+'_') for name in existing):raise ValueError('Fresh deployment volumes required')
    root.mkdir(mode=0o700,parents=True)
    p={'schema':'ai4r-pipeline02-deployment:1','root':str(root),'project':args.project,'deployment_id':args.project,
       'app_image':args.app_image,'runner_image':args.runner_image,'local_model':profile,
       'docker_context':None,'public_data':str(public),'suite_root':str(suite)}
    names=['state','accounts','ipc','poc','inputs','executor','private_qa','runner_credentials','control','operator','custody','results']
    env={'JIUWENSWARM_M1_PROFILE':'1','JIUWENSWARM_M1_REUSABLE_BOOTSTRAP':'1',
         'JIUWENSWARM_M1_LOCAL_WORKSPACE':'0','JIUWENSWARM_M1_LOCAL_CHAT':'0','JIUWENSWARM_M1_LOCAL_RESEARCH':'1',
         'AI4R_EXECUTION_MODE':'m1_app_process','JIUWENSWARM_M1_ORIGIN':'http://127.0.0.1:5180',
         'JIUWENSWARM_M1_BIND_ADDRESS':'127.0.0.1','JIUWENSWARM_M1_CONFIG':'/var/lib/ai4r/operator/local-research-unified-v5/config.json',
         'JIUWENSWARM_M1_STATE':'/var/lib/ai4r','JIUWENSWARM_M1_ACCOUNTS':'/var/lib/ai4r-accounts',
         'JIUWENSWARM_DATA_DIR':'/var/lib/ai4r/native','FRONTEND_HOST':'0.0.0.0','FRONTEND_PORT':'5173',
         'JIUWENSWARM_AGENT_SDK':'codex_subscription','JIUWENSWARM_M1_CACHE_DATASET':'/run/ai4r-public/cache-traces.json',
         'AI4R_PROTECTED_DISPATCH_CONTROL':'/run/ai4r-benchmark-control/app'}
    mounts=[mount_volume(k,v) for k,v in {'state':'/var/lib/ai4r','accounts':'/var/lib/ai4r-accounts','ipc':'/run/ai4r','poc':'/workspace/poc','inputs':'/workspace/input','executor':'/var/lib/ai4r-executor','private_qa':'/run/ai4r-private-qa','control':'/run/ai4r-benchmark-control','runner_credentials':'/run/benchmark-runner'}.items()]
    mounts.append(bind(public,'/run/ai4r-public/cache-traces.json'))
    app={'image':args.app_image,'init':True,'mem_limit':'4g','pids_limit':256,'read_only':True,'cap_drop':['ALL'],
         'cap_add':['SETUID','SETGID','CHOWN','FOWNER','DAC_OVERRIDE','KILL'],
         'security_opt':['no-new-privileges:true','seccomp='+str(Path(__file__).resolve().parent/'seccomp/executor.json')],
         'environment':env,'ports':['127.0.0.1:5180:5173'],'volumes':mounts,
         'tmpfs':['/tmp:rw,nosuid,nodev,size=256m','/home/ai4r/.cache:rw,nosuid,nodev,size=64m,uid=10001,gid=10001',
                  '/run/ai4r-supervisor:rw,nosuid,nodev,size=1m,mode=0700','/run/ai4r-executor:rw,nosuid,nodev,size=8m,mode=0710,gid=10001',
                  '/run/ai4r-store:rw,nosuid,nodev,size=64m,mode=0710,gid=10001','/resources:rw,nosuid,nodev,size=128m,mode=0711,uid=0,gid=0'],
         'networks':['private'],'stop_grace_period':'45s','labels':{'ai4r.owner':args.project,'ai4r.component':'ai4r'}}
    if args.cgroup_host:
        source=Path(args.cgroup_host).resolve(strict=True)
        app['cgroup']='host';app['environment']['AI4R_EXECUTOR_CGROUP_ROOT']='/run/ai4r-cgroups'
        app['volumes'].append({'type':'bind','source':str(source),'target':'/run/ai4r-cgroups','bind':{'create_host_path':False}})
    runner={'image':args.runner_image,'profiles':['benchmark'],'init':True,'user':'0:0','read_only':True,
            'pids_limit':128,'mem_limit':'2g','cap_drop':['ALL'],'cap_add':['SETUID','SETGID','CHOWN','FOWNER','DAC_OVERRIDE','KILL'],
            'security_opt':['no-new-privileges:true'],'entrypoint':[PYTHON,'-c','import signal; signal.pause()'],
            'environment':{'AI4R_ENDPOINT':'http://ai4r:5173','AI4R_HTTP_AUTHORITY':'127.0.0.1:5180','AI4R_TOKEN_FILE':'/run/benchmark-runner/token','AI4R_EXPECTED_BUILD':'unconfigured'},
            'volumes':[mount_volume('runner_credentials','/run/benchmark-runner',True),mount_volume('control','/run/ai4r-benchmark-control'),
                       mount_volume('operator','/operator'),mount_volume('custody','/custody'),mount_volume('results','/results'),bind(suite,'/suite')],
            'tmpfs':['/tmp:rw,nosuid,nodev,size=128m,mode=1777'],'networks':['private'],'stop_grace_period':'45s',
            'labels':{'ai4r.owner':args.project,'ai4r.component':'root-runner'}}
    config={'services':{'ai4r':app,'root-runner':runner},'networks':{'private':{}},
            'volumes':{name:{'name':args.project+'_'+name,'labels':{'ai4r.owner':args.project}} for name in names}}
    local_operator().apply_compose(p,config)
    publish(root/'compose.json',config);publish(root/'deployment.json',p)
    return {'status':'staged','directory':str(root),'project':args.project,'origin':'http://127.0.0.1:5180','model_choices':[{'id':m['id'],'model_name':m['model_name']} for m in json.loads(catalog_raw)['models'] if m['enabled']]}


VOLUME_INIT='''import os,stat
from pathlib import Path
for name in ('control','operator','custody','results','credentials'):
 p=Path('/volumes')/name
 assert not p.is_symlink() and not any(p.iterdir()),'fresh volumes required'
 os.chown(p,0,0);p.chmod(0o700 if name in ('operator','custody') else 0o755)
r=Path('/volumes/control')
for name,uid,mode in [('app',0,0o755),('app/requests',0,0o755),('app/events',10001,0o700),('runner',0,0o755)]:
 p=r/name;p.mkdir();os.chown(p,uid,uid);p.chmod(mode)
'''


def wait_sockets(p):
    for i in range(60):
        try:
            compose(p,'exec','-T','--user','10001:10001','ai4r',PYTHON,'-c',
                    "import os,stat; assert all(stat.S_ISSOCK(os.stat(p).st_mode) for p in ('/run/ai4r/model.sock','/run/ai4r-executor/executor.sock'))")
            return
        except RuntimeError:
            if i==59:raise
            time.sleep(1)


def action(args):
    root=Path(args.directory).resolve(strict=True);p=json.loads((root/'deployment.json').read_bytes())
    if str(root)!=p['root'] or not p['project'].startswith('ai4r-pipeline02-'):raise ValueError('Exact isolated deployment required')
    if args.operation=='start':
        if (root/'started.json').exists():raise ValueError('Already started; use explicit isolated compose commands to resume')
        existing=docker(p,'volume','ls','--format','{{.Name}}').decode().splitlines()
        if any(name.startswith(p['project']+'_') for name in existing):raise ValueError('Refuse reuse of deployment volumes')
        local_operator().provision(p,docker)
        command=['run','--rm','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN','--cap-add','FOWNER']
        for name,target in [('control','control'),('operator','operator'),('custody','custody'),('results','results'),('runner_credentials','credentials')]:
            command += ['--mount','type=volume,src='+p['project']+'_'+name+',dst=/volumes/'+target]
        command += ['--entrypoint',PYTHON,p['app_image'],'-c',VOLUME_INIT]
        docker(p,*command)
        compose(p,'up','-d','--no-build','--pull','never','ai4r');wait_sockets(p)
        publish(root/'started.json',{'app_image':p['app_image']})
        return {'status':'app_started','origin':'http://127.0.0.1:5180','next':'initialize'}
    if args.operation=='select-model':
        if not args.model_id.startswith('local-'):raise ValueError('Select an actual operator local model ID')
        code = """import asyncio,json,sys
from jiuwenswarm.research.accounts import AccountStore
from jiuwenswarm.research.native_ports import _session,STATUS_PROTOCOL
from jiuwenswarm.research.private_rpc import PrivateRPCClient
value=json.load(sys.stdin);accounts=AccountStore('/var/lib/ai4r-accounts')
try:account=accounts.primary()['account_id']
finally:accounts.close()
session=_session('/run/ai4r',10001)
client=PrivateRPCClient('/run/ai4r/agent-status.sock',protocol=STATUS_PROTOCOL,peer_uid=10001,**session)
async def choose():
 result=await client.call('model_settings',{'account_id':account,'action':'select','values':{'preset_id':value['model_id']},'include_chatgpt_models':False},timeout_s=30)
 assert result['selected_id']==value['model_id'] and result.get('api_ready') is True,'selected relay transport unavailable'
 print(json.dumps({'selected_id':result['selected_id'],'api_ready':result['api_ready']}))
asyncio.run(choose())
"""
        return json.loads(compose(p,'exec','-T','--user','10001:10001','ai4r',PYTHON,'-c',code,data=json.dumps({'model_id':args.model_id}).encode()))
    if args.operation=='initialize':
        wait_sockets(p)
        result=json.loads(compose(p,'exec','-T','--user','10001:10001','ai4r',PYTHON,'-m','jiuwenswarm.research.initialize','--json',timeout=300))
        if result.get('status')!='initialized':raise ValueError('Catalog initialization blocked; inspect isolated app privately')
        publish(root/'initialized.json',result)
        compose(p,'up','-d','--force-recreate','--no-deps','--no-build','--pull','never','ai4r');wait_sockets(p)
        return {'status':'initialized','next':'grant'}
    if args.operation=='grant':
        # Token bytes stay solely in this fresh shared protected volume.
        result=json.loads(compose(p,'exec','-T','--user','0:0','ai4r',PYTHON,'-m','jiuwenswarm.research.runner_grants','issue-runner','--expires-in-s','86400','--output','/run/benchmark-runner/token'))
        if result.get('status')!='issued':raise ValueError('Finite native runner grant blocked')
        identity=json.loads(compose(p,'exec','-T','ai4r','cat','/usr/local/share/ai4r-build-identity.json'))
        config=json.loads((root/'compose.json').read_bytes());config['services']['root-runner']['environment']['AI4R_EXPECTED_BUILD']=identity['build_id'];publish(root/'compose.json',config)
        p['expected_build']=identity['build_id'];p['grant']=result;publish(root/'deployment.json',p)
        return {'status':'issued','build_id':identity['build_id'],'next':'start-runner'}
    if args.operation=='start-runner':
        if not p.get('expected_build'):raise ValueError('Issue an actual finite runner grant first')
        compose(p,'--profile','benchmark','up','-d','--no-deps','--no-build','--pull','never','root-runner')
        return {'status':'root_runner_started','build_id':p['expected_build']}
    if args.operation=='controller-setup':
        if not p.get('expected_build'):raise ValueError('Issue a finite runner grant first')
        code = """import json,os,sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
p=json.load(sys.stdin);root=Path('/operator');assert os.geteuid()==0 and root.stat().st_uid==0 and root.stat().st_mode&0o077==0
key=Ed25519PrivateKey.generate()
with (root/'controller.key').open('xb') as f:
 os.fchmod(f.fileno(),0o600);f.write(key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()));f.flush();os.fsync(f.fileno())
values={'controller.json':{'schema':'ai4r-native-controller-config:1','key_file':'/operator/controller.key','custody_root':'/custody','hook_root':'/run/ai4r-benchmark-control','worker_uid':11001,'worker_gid':11001,'app_uid':10001},
 'runner.json':{'schema':'ai4r-harbor-config:1','bundle_root':'/suite/bundle','output_root':'/results','endpoint':'http://ai4r:5173','token_file':'/run/benchmark-runner/token','expected_build':p['expected_build'],'http_authority':'127.0.0.1:5180'},
 'suite.json':{'schema':'ai4r-harbor-suite-config:1','bundle_root':'/suite/bundle','output_root':'/results','mode':'live','runner_config':'/operator/runner.json','controller_config':'/operator/controller.json'}}
for name,value in values.items():
 with (root/name).open('x') as f:
  os.fchmod(f.fileno(),0o600);json.dump(value,f,sort_keys=True);f.flush();os.fsync(f.fileno())
print(json.dumps({'controller_public_key':key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex(),'suite_config':'/operator/suite.json'}))
"""
        return json.loads(compose(p,'exec','-T','--user','0:0','root-runner',PYTHON,'-c',code,data=json.dumps({'expected_build':p['expected_build']}).encode()))
    raise ValueError('Unknown operation')


def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='operation',required=True)
    stage_parser=sub.add_parser('stage')
    for name in ('directory','project','app-image','runner-image','public-data','suite-root','relay-catalog','relay-session','relay-sockets'):
        stage_parser.add_argument('--'+name,required=True)
    stage_parser.add_argument('--cgroup-host')
    for name in ('start','initialize','grant','start-runner','controller-setup'):
        sub.add_parser(name).add_argument('--directory',required=True)
    model_parser=sub.add_parser('select-model');model_parser.add_argument('--directory',required=True);model_parser.add_argument('--model-id',required=True)
    args=parser.parse_args()
    if os.name!='posix' or os.geteuid()!=0:raise ValueError('Run on the Linux Docker host as root')
    print(json.dumps(stage(args) if args.operation=='stage' else action(args),sort_keys=True))


if __name__=='__main__':main()
