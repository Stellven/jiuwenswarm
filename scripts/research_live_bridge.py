"""Finite trusted HOST producer for I027; no controller Docker authority.

A capture supplies original observations, never complete V10 acceptance. The
preissued private target profile and active ordinary contexts are not created
by this producer. All unavailable prerequisites block before model effects.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

try:
    from scripts.research_candidate import DEFAULT_SCOPE, verify_candidate
    from scripts.research_foundation import read_regular, read_pin
    from scripts.research_image_closure import inspect_closure
    from scripts.research_system import DockerHost
    from scripts.research_live_bridge_probe import check_capture, encoded, sha
except ModuleNotFoundError:
    from research_candidate import DEFAULT_SCOPE, verify_candidate
    from research_foundation import read_regular, read_pin
    from research_image_closure import inspect_closure
    from research_system import DockerHost
    from research_live_bridge_probe import check_capture, encoded, sha

FIELDS={'schema','job_id','project','container_id','image_id','build_id','instance_id',
    'candidate_id','platform','source_build_pin','profile_sha256'}
MAX_CAPTURE=96*1024**2
PREFIX=b'AI4R_LIVE_PROBE_START:'
PROBE_CLEANUP=r'''import hashlib,json,os,pathlib,signal,sys,time
v=json.loads(sys.stdin.buffer.read(4096));p=pathlib.Path('/proc')/str(v['pid'])
r={'attempted':False,'confirmed':False}
try:
 s=p.stat();fields=(p/'stat').read_text().rsplit(')',1)[1].split();args=(p/'cmdline').read_bytes().split(b'\0')
 if s.st_uid!=10001 or fields[19]!=v['start_time'] or b'-c' not in args or hashlib.sha256(args[args.index(b'-c')+1]).hexdigest()!=v['program_sha256']:raise ValueError('PROBE_IDENTITY_MISMATCH')
 os.kill(v['pid'],signal.SIGTERM);r['attempted']=True
 for _ in range(20):
  if not p.exists():r['confirmed']=True;break
  time.sleep(.1)
except FileNotFoundError:r['confirmed']=True
except Exception as e:r['error']=str(e) if isinstance(e,ValueError) else type(e).__name__
print(json.dumps(r,sort_keys=True))
'''


class LiveBlocked(ValueError):
    pass


def _execute(command,**options):
    return subprocess.run(command,**options)


def validate_target(value):
    if not isinstance(value,dict) or set(value)!=FIELDS or value['schema']!='ai4r-live-bridge-host-target:1':
        raise LiveBlocked('CLOSED_OWNED_LIVE_TARGET_REQUIRED')
    for key in ('container_id','build_id','candidate_id','profile_sha256'):
        if not isinstance(value[key],str) or re.fullmatch('[a-f0-9]{64}',value[key]) is None:
            raise LiveBlocked('EXACT_TARGET_IDENTITY_REQUIRED')
    if (not re.fullmatch('sha256:[a-f0-9]{64}',value.get('image_id',''))
        or value['platform'] not in {'linux/amd64','linux/arm64'}
        or not re.fullmatch('ai4r-live-codex-[a-z0-9][a-z0-9-]{0,60}',value.get('job_id',''))
        or not re.fullmatch('ai4r-[a-z0-9][a-z0-9-]{0,65}',value.get('project',''))
        or not isinstance(value['instance_id'],str) or not value['instance_id'] or len(value['instance_id'])>128):
        raise LiveBlocked('FINITE_TARGET_IDENTITY_REQUIRED')
    pin=value['source_build_pin']
    if (not isinstance(pin,dict) or set(pin)!={'path','sha256'} or not isinstance(pin['path'],str)
        or Path(pin['path']).name!='receipt.json' or not re.fullmatch('[a-f0-9]{64}',pin.get('sha256',''))):
        raise LiveBlocked('ORIGINAL_SOURCE_BUILD_PIN_REQUIRED')
    return value


def verify_container(host,target):
    rows=host.json(['container','inspect',target['container_id']])
    if not isinstance(rows,list) or len(rows)!=1:raise LiveBlocked('OWNED_NATIVE_CONTAINER_REQUIRED')
    item=rows[0];labels=item.get('Config',{}).get('Labels') or {}
    if (item.get('Id')!=target['container_id'] or item.get('Image')!=target['image_id']
        or item.get('State',{}).get('Running') is not True
        or labels.get('com.docker.compose.project')!=target['project']
        or labels.get('com.docker.compose.service')!='app'
        or labels.get('ai4r.owner')!=target['job_id']):
        raise LiveBlocked('RUNNING_OWNED_NATIVE_IDENTITY_MISMATCH')
    images=host.json(['image','inspect',target['image_id']])
    if (len(images)!=1 or images[0].get('Id')!=target['image_id']
        or images[0].get('Os','')+'/'+images[0].get('Architecture','')!=target['platform']
        or any(item.get('Config',{}).get(key)!=images[0].get('Config',{}).get(key) for key in ('Entrypoint','Cmd'))
        or item.get('HostConfig',{}).get('Privileged') is not False
        or item.get('HostConfig',{}).get('ReadonlyRootfs') is not True):
        raise LiveBlocked('FROZEN_NATIVE_STARTUP_REQUIRED')
    protected=tuple(PurePosixPath(path) for path in ('/opt','/usr','/bin','/sbin','/lib','/lib64','/app','/src'))
    for mount in item.get('Mounts',[]):
        path=PurePosixPath(mount.get('Destination',''))
        if not path.is_absolute() or any(path.is_relative_to(root) or root.is_relative_to(path) for root in protected):
            raise LiveBlocked('NATIVE_SOURCE_OR_RUNTIME_OVERLAY_DENIED')
        if 'docker.sock' in str(mount.get('Source','')) or 'docker.sock' in str(path):
            raise LiveBlocked('TARGET_DOCKER_SOCKET_DENIED')
    return item


def parse_stdout(raw):
    if len(raw)>MAX_CAPTURE:raise LiveBlocked('LIVE_CAPTURE_OUTPUT_BOUND')
    lines=raw.splitlines()
    if len(lines)!=2 or not lines[0].startswith(PREFIX):raise LiveBlocked('ORIGINAL_PROBE_FRAMING_REQUIRED')
    start=json.loads(lines[0][len(PREFIX):]);capture=json.loads(lines[1])
    if (set(start)!={'pid','start_time','uid','program_sha256'} or type(start['pid']) is not int
        or start['pid']<=1 or start['uid']!=10001 or not str(start['start_time']).isdigit()
        or not re.fullmatch('[a-f0-9]{64}',start['program_sha256'])):
        raise LiveBlocked('ORIGINAL_PROBE_PROCESS_IDENTITY_REQUIRED')
    return start,capture


def validate_receipt(path):
    """External controller independently recomputes original public evidence."""
    path=Path(path);receipt=json.loads(read_regular(path,maximum=4*1024**2));directory=path.parent
    if receipt.get('schema')!='ai4r-live-bridge-host-receipt:1' or receipt.get('outcome')!='CAPTURED':
        raise LiveBlocked('LIVE_RECEIPT_BLOCKED_OR_INCOMPLETE')
    target=validate_target(json.loads(read_regular(directory/'target.json',maximum=65536)))
    program=read_regular(Path(__file__).with_name('research_live_bridge_probe.py'))
    raw=read_regular(directory/'probe.stdout.jsonl',maximum=MAX_CAPTURE)
    stderr=read_regular(directory/'probe.stderr.log',maximum=1024**2)
    command_raw=read_regular(directory/'command.json',maximum=128*1024)
    command=json.loads(command_raw)
    if not isinstance(command,list) or 'exec' not in command:raise LiveBlocked('FIXED_ORIGINAL_HOST_COMMAND_REQUIRED')
    split=command.index('exec');prefix=command[:split]
    local=prefix==['docker','--context','default']
    wsl=(len(prefix)==11 and prefix[:6]==['wsl','-d','Ubuntu','-u','root','--cd']
        and isinstance(prefix[6],str) and prefix[6].startswith('/') and prefix[7:]==['--exec','docker','--context','default'])
    if (not (local or wsl) or command[split:]!=['exec','-i','--user','10001:10001',target['container_id'],
        '/usr/local/bin/python3','-I','-S','-c',program.decode('utf8')]
        or sha(command_raw)!=receipt.get('command_sha256')):
        raise LiveBlocked('FIXED_ORIGINAL_HOST_COMMAND_REQUIRED')
    if (sha(program)!=receipt.get('program_sha256') or sha(encoded(target))!=receipt.get('input_sha256')
        or sha(raw)!=receipt.get('stdout_sha256') or sha(stderr)!=receipt.get('stderr_sha256')
        or receipt.get('target_sha256')!=sha(read_regular(directory/'target.json',maximum=65536))
        or receipt.get('returncode')!=0 or receipt.get('checkout_current_before') is not True
        or receipt.get('checkout_current_after') is not True or receipt.get('target_unchanged') is not True
        or receipt.get('cleanup')!={'attempted':False,'confirmed':True}):
        raise LiveBlocked('ORIGINAL_HOST_RECEIPT_INPUT_OR_TERMINAL_MISMATCH')
    # Re-read the original independent closure, including its frozen hashes;
    # reported qualified/current booleans alone never establish identity.
    closure_raw=read_regular(directory/'closure/result.json',maximum=4*1024**2)
    closure=json.loads(closure_raw)
    if sha(closure_raw)!=receipt.get('closure_sha256'):
        raise LiveBlocked('ORIGINAL_CLOSURE_RECEIPT_CHANGED')
    if closure.get('image_id')!=target['image_id'] or closure.get('candidate_id')!=target['candidate_id']:
        raise LiveBlocked('INDEPENDENT_INSTALLED_CLOSURE_REQUIRED')
    input_raw=read_regular(directory/'closure/image-closure-input.json',maximum=32*1024**2)
    output_raw=read_regular(directory/'closure/image-closure.stdout.json',maximum=4*1024**2)
    closure_program=read_regular(Path(__file__).with_name('research_image_closure_probe.py'))
    observation=json.loads(output_raw)
    source_raw=read_regular(directory/'source-build-receipt.json',maximum=4*1024**2)
    source=json.loads(source_raw);closure_input=json.loads(input_raw)
    try:from scripts.research_build import validate_manifest
    except ModuleNotFoundError:from research_build import validate_manifest
    candidate=closure_input.get('candidate');validate_manifest(candidate)
    inventory={row['path']:row for row in candidate['files']}
    original_programs={
        'scripts/research_live_bridge_probe.py':program,
        'scripts/research_live_bridge.py':read_regular(Path(__file__)),
        'scripts/research_image_closure_probe.py':closure_program,
    }
    if (sha(source_raw)!=target['source_build_pin']['sha256']
        or source.get('schema')!='ai4r-source-build:1' or source.get('outcome')!='BUILT'
        or source.get('target')!='app-production' or source.get('image',{}).get('image_id')!=target['image_id']
        or source.get('candidate_id')!=target['candidate_id'] or candidate['candidate_id']!=target['candidate_id']
        or source.get('context',{}).get('sha256')!=closure.get('context_sha256')
        or source.get('snapshot_sha256')!=closure.get('snapshot_sha256')
        or any(inventory.get(name,{}).get('sha256')!=sha(raw) for name,raw in original_programs.items())):
        raise LiveBlocked('ORIGINAL_FROZEN_SOURCE_PROGRAM_CLOSURE_REQUIRED')
    try:from scripts.research_image_closure_probe import CHECKS
    except ModuleNotFoundError:from research_image_closure_probe import CHECKS
    if (sha(input_raw)!=closure.get('input_sha256') or sha(output_raw)!=closure.get('stdout_sha256')
        or sha(closure_program)!=closure.get('program_sha256') or observation!=closure.get('observation')
        or set(observation.get('assertions',{}))!=set(CHECKS)
        or not all(value is True for value in observation['assertions'].values())
        or observation.get('installed_build_id')!=target['build_id']
        or observation.get('mode')!='installed' or closure.get('returncode')!=0
        or closure.get('cleanup',{}).get('confirmed') is not True
        or observation.get('joins',{}).get('candidate_id')!=target['candidate_id']
        or observation.get('joins',{}).get('image_id')!=target['image_id']
        or observation.get('joins',{}).get('build_id')!=target['build_id']
        or observation.get('joins',{}).get('platform')!=target['platform']
        or observation.get('joins',{}).get('source_build_receipt_sha256')!=target['source_build_pin']['sha256']):
        raise LiveBlocked('ORIGINAL_INDEPENDENT_CLOSURE_BYTES_REQUIRED')
    start,capture=parse_stdout(raw)
    if start['program_sha256']!=sha(program):raise LiveBlocked('ACTUAL_PROBE_PROGRAM_MISMATCH')
    # Outside the stdlib probe, validate full public source record schemas using
    # the installed neutral contracts. This does not authorize any operation.
    from jiuwenswarm.research.contracts import validate
    import base64
    for row in capture.get('records',[]):
        if row['kind'] in {'model-call','route-record'}:
            validate(row['kind'],json.loads(base64.b64decode(row['raw_b64'],validate=True)))
    checks=check_capture(capture,target)
    return {'roles':checks,'complete_v10':False,'limitations':['ordinary_native_chat_and_account_assertions_remain_required']}


def run_probe(root,target_file,output,*,host=None):
    root=Path(root).resolve();output=Path(output);output.mkdir(parents=True,exist_ok=False,mode=0o700)
    result={'schema':'ai4r-live-bridge-host-receipt:1','outcome':'BLOCKED','effect_attempted':False,
        'cleanup':{'attempted':False,'confirmed':True},'complete_v10':False}
    issued=False;target=None;candidate=None
    try:
        if target_file is None:raise LiveBlocked('OWNED_LIVE_TARGET_REQUIRED')
        target_raw=read_regular(target_file,maximum=65536);target=validate_target(json.loads(target_raw))
        (output/'target.json').write_bytes(target_raw);result['target_sha256']=sha(target_raw)
        result['input_sha256']=sha(encoded(target));result['target']=target
        receipt_path=Path(target['source_build_pin']['path']).absolute()
        if not receipt_path.is_relative_to(root/'.test_logs/m1') or receipt_path.parent.name!='app-production':
            raise LiveBlocked('PUBLIC_OWNED_I014_RECEIPT_PATH_REQUIRED')
        build=read_pin(target['source_build_pin']);directory=receipt_path.parent
        if (build.get('schema')!='ai4r-source-build:1' or build.get('outcome')!='BUILT'
            or build.get('target')!='app-production' or build.get('platform')!=target['platform']
            or build.get('image',{}).get('image_id')!=target['image_id']):
            raise LiveBlocked('ORIGINAL_I014_SOURCE_BUILD_REQUIRED')
        candidate=json.loads(read_regular(directory/'candidate.json',maximum=32*1024**2))
        if (candidate.get('scope')!=list(DEFAULT_SCOPE) or candidate.get('candidate_id')!=target['candidate_id']
            or build.get('candidate_id')!=target['candidate_id'] or verify_candidate(root,candidate)):
            raise LiveBlocked('FULL_CURRENT_FROZEN_CANDIDATE_REQUIRED')
        inventory={row['path']:row for row in candidate.get('files',[])}
        for name in ('research_live_bridge.py','research_live_bridge_probe.py','research_image_closure_probe.py'):
            if inventory.get('scripts/'+name,{}).get('sha256')!=sha(read_regular(Path(__file__).with_name(name))):
                raise LiveBlocked('FROZEN_HOST_PROGRAM_SOURCE_REQUIRED')
        result['checkout_current_before']=True
        host=host or DockerHost(root);before=verify_container(host,target)
        closure_directory=output/'closure';closure_directory.mkdir()
        closure=inspect_closure(host,target,target['source_build_pin'],closure_directory)
        (closure_directory/'result.json').write_bytes(encoded(closure))
        result['closure_sha256']=sha(encoded(closure))
        if (not closure.get('qualified') or closure.get('image_id')!=target['image_id']
            or closure.get('candidate_id')!=target['candidate_id']):raise LiveBlocked('INDEPENDENT_INSTALLED_CLOSURE_UNAVAILABLE')
        (output/'source-build-receipt.json').write_bytes(read_regular(receipt_path))
        result['closure_verified']=True
        program=read_regular(Path(__file__).with_name('research_live_bridge_probe.py'));result['program_sha256']=sha(program)
        command=host.prefix+['exec','-i','--user','10001:10001',target['container_id'],
            '/usr/local/bin/python3','-I','-S','-c',program.decode('utf8')]
        (output/'command.json').write_bytes(encoded(command))
        result.update(command_sha256=sha(encoded(command)),effect_attempted=True,outcome='OUTCOME_UNKNOWN')
        issued=True
        try:
            call=_execute(command,cwd=root,input=encoded(target),capture_output=True,timeout=300,check=False)
            raw,error=call.stdout,call.stderr;result['returncode']=call.returncode
        except subprocess.TimeoutExpired as timeout:
            raw,error=timeout.stdout or b'',timeout.stderr or b''
            result.update(error='HOST_PROBE_TIMEOUT',returncode=None)
            result['model_containment']='UNRESOLVED_DISCONNECT_IS_NOT_CANCELLATION'
            # Client termination is not model containment. Attempt only an exact
            # observed probe PID/start/code cleanup; never cancel a foreign run.
            result['cleanup']={'attempted':False,'confirmed':False,'reason':'probe_identity_or_containment_unresolved'}
            try:
                first=raw.splitlines()[0]
                if first.startswith(PREFIX):
                    identity=json.loads(first[len(PREFIX):])
                    if identity.get('program_sha256')==sha(program) and identity.get('uid')==10001:
                        cleanup_command=host.prefix+['exec','-i','--user','10001:10001',target['container_id'],
                            '/usr/local/bin/python3','-I','-S','-c',PROBE_CLEANUP]
                        cleanup=_execute(cleanup_command,cwd=root,input=encoded(identity),capture_output=True,timeout=10,check=False)
                        result['cleanup']=json.loads(cleanup.stdout)
                        (output/'cleanup.stdout.json').write_bytes(cleanup.stdout)
            except Exception:pass
        (output/'probe.stdout.jsonl').write_bytes(raw);(output/'probe.stderr.log').write_bytes(error)
        result.update(stdout_sha256=sha(raw),stderr_sha256=sha(error))
        after=verify_container(host,target)
        result['target_unchanged']=(before['Id'],before['Image'],before['State'].get('StartedAt'))==(after['Id'],after['Image'],after['State'].get('StartedAt'))
        result['checkout_current_after']=not verify_candidate(root,candidate)
        if result.get('returncode') is not None:
            start,capture=parse_stdout(raw)
            if start['program_sha256']!=sha(program):raise LiveBlocked('ACTUAL_PROBE_PROGRAM_MISMATCH')
            if capture.get('outcome')=='BLOCKED' and capture.get('effect_attempted') is False:
                result.update(outcome='BLOCKED',effect_attempted=False,error=capture.get('error','TARGET_PREREQUISITE_UNAVAILABLE'))
            elif result['returncode']==0 and capture.get('outcome')=='CAPTURED':
                check_capture(capture,target)
                if result['target_unchanged'] and result['checkout_current_after']:result['outcome']='CAPTURED'
                else:result['error']='POST_DISPATCH_IDENTITY_OR_CURRENTNESS_DRIFT'
            else:result['error']=capture.get('error','LIVE_NATIVE_EFFECT_NON_SUCCESS')
    except Exception as error:
        result['error']=str(error) if isinstance(error,LiveBlocked) else type(error).__name__
        if issued:result['outcome']='OUTCOME_UNKNOWN'
    finally:
        (output/'receipt.json').write_bytes(encoded(result))
        if host is not None and isinstance(host,DockerHost):(output/'host-commands.json').write_bytes(encoded(host.commands))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default='.');parser.add_argument('--target-file');parser.add_argument('--output',required=True)
    args=parser.parse_args();result=run_probe(args.root,args.target_file,args.output)
    print(json.dumps({key:result[key] for key in ('schema','outcome','effect_attempted','complete_v10')},sort_keys=True))
    return 0 if result['outcome']=='CAPTURED' else 2


if __name__=='__main__':raise SystemExit(main())
