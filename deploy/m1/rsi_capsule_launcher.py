"""Fixed Root whole-capsule launcher and actual completed-result publication."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import time

IMAGE = 'sha256:00026931a8e236d255efca8d2e90ea49ae04989539fca4d418d318a98fa93ab2'
SOCKET = 'unix:///run/ai4r-rsi-docker/docker.sock'
FIELDS = set('schema id configuration runner restore seccomp publisher publication_template control_directory cgroup_root launcher_sha256'.split())


def need(value, reason):
    if not value: raise ValueError(reason)


def encoded(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
def sha(raw): return hashlib.sha256(raw).hexdigest()


def protected(path, *, directory=False, owner=0, maximum=16*1024*1024):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'ABSOLUTE_ROOT_PATH_REQUIRED')
    for parent in path.parents:
        meta = parent.lstat()
        need(stat.S_ISDIR(meta.st_mode) and meta.st_uid in {0, owner} and not meta.st_mode & 0o022, 'PROTECTED_ANCESTRY_DIFFERS')
    meta = path.lstat()
    need(not path.is_symlink() and meta.st_uid == owner and not meta.st_mode & 0o022
         and (stat.S_ISDIR(meta.st_mode) if directory else stat.S_ISREG(meta.st_mode)
              and meta.st_nlink == 1 and meta.st_size <= maximum), 'PROTECTED_PATH_DIFFERS')
    return path


def pinned(value):
    need(isinstance(value, dict) and set(value) == {'path','sha256'}, 'CLOSED_FILE_PIN_REQUIRED')
    path = protected(value['path'])
    need(sha(path.read_bytes()) == value['sha256'], 'PINNED_BYTES_DIFFER')
    return path


def exclusive(path, value):
    fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream: stream.write(encoded(value)); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(Path(path).parent, os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def load(path, digest):
    need(os.name == 'posix' and os.geteuid() == 0, 'ROOT_LAUNCHER_REQUIRED')
    raw = protected(path).read_bytes(); need(sha(raw) == digest, 'LAUNCH_CONFIGURATION_DIFFERS')
    value = json.loads(raw)
    need(set(value) == FIELDS and value['schema'] == 'ai4r-rsi-capsule-launcher:1'
         and value['launcher_sha256'] == sha(Path(__file__).read_bytes()), 'CLOSED_PINNED_LAUNCH_CONFIGURATION_REQUIRED')
    import re
    need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', value['id']) is not None, 'FINITE_SESSION_ID_REQUIRED')
    for key in ('configuration','runner','restore','seccomp','publisher','publication_template'): pinned(value[key])
    cfg = json.loads(pinned(value['configuration']).read_bytes())
    need(cfg['schema'] in ('ai4r-rsi-capsule-run-configuration:1','ai4r-rsi-capsule-run-configuration:2')
         and cfg['session']['id'] == value['id'], 'EXACT_SESSION_CONFIGURATION_REQUIRED')
    need(Path(value['runner']['path']).parent == Path(cfg['source_root']), 'RUNNER_SOURCE_ROOT_DIFFERS')
    protected(value['control_directory'], directory=True)
    protected(value['cgroup_root'], directory=True)
    need(Path(value['cgroup_root']).is_relative_to('/sys/fs/cgroup/ai4r-rsi-host/jobs')
         and cfg['evaluator']['cgroup_root'] == value['cgroup_root'], 'EXACT_CAPSULE_CGROUP_REQUIRED')
    return value, cfg


def docker(value, *args):
    return subprocess.run(['/usr/bin/python3','-B',value['restore']['path'],'client','/usr/bin/docker','--host',SOCKET,*args],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45,
        env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':'/root','PYTHONDONTWRITEBYTECODE':'1'}).stdout


def preflight(value, cfg):
    grant = cfg['session']['grant']
    need(type(grant['expires_unix_s']) is int and grant['expires_unix_s'] > time.time(), 'CAPSULE_GRANT_EXPIRED')
    need(not Path(cfg['claim_path']).exists(), 'CAPSULE_ALREADY_CLAIMED_NO_REPLAY')
    need(not docker(value, 'ps','-q').strip(), 'OWNED_RUNTIME_NOT_IDLE')
    for group in (Path(value['cgroup_root']), *Path(value['cgroup_root']).rglob('*')):
        if group.is_dir():
            need(not (group/'cgroup.procs').read_text().strip() and 'populated 0' in (group/'cgroup.events').read_text(), 'OWNED_GROUP_NOT_EMPTY')
    # Metadata-only worker preflight verifies every captured source, grant and
    # original. No resources/lease/model composition is opened here.
    result = subprocess.run(['/usr/bin/python3','-B',value['runner']['path'],'preflight',
        '--configuration',value['configuration']['path'],'--configuration-sha256',value['configuration']['sha256']],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':'/root','PYTHONDONTWRITEBYTECODE':'1',
             'PYTHONPATH':'/opt/ai4r-rsi-frozen-v18-03ed3199:/opt/ai4r-rsi-host-codex/site-packages'})
    need(len(result.stdout) <= 16384, 'FINITE_WORKER_PREFLIGHT_REQUIRED')
    reply = json.loads(result.stdout)
    need(reply['ready'] is True and reply['id'] == value['id']
         and reply['configuration_sha256'] == value['configuration']['sha256'] and reply['model_calls'] == 0,
         'EXACT_WORKER_PREFLIGHT_DIFFERS')
    return {'schema':'ai4r-rsi-capsule-launch-preflight:1','ready':True,'run_id':value['id'],
            'configuration_sha256':value['configuration']['sha256']}


def worker_command(value, cfg):
    args = ['create','--name','ai4r-capsule-'+value['id'],'--init','--read-only','--network','none','--user','0:0','--cap-drop','ALL']
    for cap in ('SETUID','SETGID','CHOWN','FOWNER','DAC_OVERRIDE','KILL'): args += ['--cap-add',cap]
    args += ['--security-opt','no-new-privileges:true','--security-opt','seccomp='+value['seccomp']['path'],
        '--cgroupns','host','--memory','512m','--memory-swap','512m','--pids-limit','64','--cpus','2',
        '--tmpfs','/tmp:rw,nosuid,nodev,size=64m','--entrypoint','/opt/venv/bin/python']
    comp = cfg['composition']; mounts = {}
    for key in ('core_root','input_root','record_root','native_lease_root','account_root','work_root'):
        protected(comp[key], directory=True, owner=12001); mounts[comp[key]] = False
    for path in (cfg['evaluator']['root'], str(Path(cfg['claim_path']).parent), str(Path(cfg['result_path']).parent)):
        # Controller output parent can be12001; Root claim stays Root-owned.
        owner = Path(path).stat().st_uid
        need(owner in {0,12001}, 'FINITE_RUNTIME_OWNER_REQUIRED')
        protected(path, directory=True, owner=owner); mounts[path] = False
    for path in (cfg['source_root'], cfg['evaluator']['runtime_root'], '/run/ai4r-rsi-host-codex'):
        protected(path, directory=True); mounts[path] = True
    mounts[value['configuration']['path']] = True
    mounts[cfg['evaluator']['grant_path']] = True
    if 'compatibility' in cfg:
        pinned(cfg['compatibility'])
        mounts[cfg['compatibility']['path']] = True
    for path, readonly in sorted(mounts.items()):
        need(',' not in path, 'MOUNT_DELIMITER_FORBIDDEN')
        args += ['--mount',f'type=bind,src={path},dst={path}'+(',readonly' if readonly else '')]
    args += ['--mount',f"type=bind,src={value['cgroup_root']},dst={value['cgroup_root']}"]
    args += [IMAGE,'-I','-B',value['runner']['path'],'run','--configuration',value['configuration']['path'],
             '--configuration-sha256',value['configuration']['sha256']]
    return args


def run(value, cfg):
    preflight(value, cfg)
    control = Path(value['control_directory']); argv = worker_command(value, cfg)
    exclusive(control/'run-claim.json', {'schema':'ai4r-rsi-capsule-worker-claim:1','id':value['id'],'argv':argv,'image':IMAGE})
    cid = docker(value,*argv).decode().strip()
    need(len(cid) == 64 and all(c in '0123456789abcdef' for c in cid), 'EXACT_WORKER_CID_REQUIRED')
    exclusive(control/'run-container.json',{'id':value['id'],'cid':cid,'image':IMAGE})
    docker(value,'start',cid); deadline = time.monotonic()+3700
    while True:
        info = json.loads(docker(value,'inspect',cid))[0]
        need(info['Id'] == cid and info['Image'] == IMAGE, 'WORKER_IDENTITY_DIFFERS')
        if not info['State']['Running']: break
        need(time.monotonic() < deadline,'WORKER_DEADLINE_EXPIRED_RECONCILE_NO_REPLAY'); time.sleep(2)
    need(info['State']['Pid'] == 0,'WORKER_TERMINATION_UNPROVEN')
    output = docker(value,'logs',cid)
    exclusive(control/'run-exit.json',{'cid':cid,'exit_code':info['State']['ExitCode'],
        'inspection_sha256':sha(encoded(info)),'stdout_sha256':sha(output)})
    fd = os.open(control/'run-stdout.log',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream: stream.write(output); stream.flush(); os.fsync(stream.fileno())
    # Failed sessions may still contain a candidate and actual failed evidence.
    # Publisher validates evidence; never re-execute to repair publication.
    if Path(cfg['result_path']).is_file():
        # The frozen host package deliberately lacks the new capsule modules.
        # Re-establish the exact Root-pinned overlay in this process; the prior
        # metadata preflight ran in a separate subprocess. Do not preflight an
        # already consumed claim or recompose model resources for publication.
        runner_spec = importlib.util.spec_from_file_location('capsule_publication_source_loader', pinned(value['runner']))
        runner = importlib.util.module_from_spec(runner_spec); runner_spec.loader.exec_module(runner)
        need(sha(pinned(value['configuration']).read_bytes()) == value['configuration']['sha256'], 'COMPLETED_CONFIGURATION_DIFFERS')
        runner.load_sources(cfg)
        spec = importlib.util.spec_from_file_location('capsule_actual_publication',pinned(value['publisher']))
        publisher = importlib.util.module_from_spec(spec); spec.loader.exec_module(publisher)
        result = publisher.publish_completed(pinned(value['publication_template']))
        exclusive(control/'publication-receipt.json',result)
    need(info['State']['ExitCode'] == 0,'ACTUAL_WORKER_FAILED_NO_REPLAY')
    return {'id':value['id'],'status':'COMPLETED_UNQUALIFIED','cid':cid,'security_status':'SECURITY_DEFERRED'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('operation',choices=('preflight','run'))
    parser.add_argument('--configuration',required=True)
    parser.add_argument('--configuration-sha256',required=True)
    args = parser.parse_args(); value,cfg = load(args.configuration,args.configuration_sha256)
    print(json.dumps(preflight(value,cfg) if args.operation == 'preflight' else run(value,cfg),sort_keys=True))
