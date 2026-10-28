"""Fixed Root launcher for one reviewed development worker and publication.

No browser parameters, arbitrary commands or fixture selectors enter here.
doctor is a separately reviewed, model-free mechanical plan capture. preflight
is read-only. Only run starts the already approved two-call development run.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import time

CONFIG = Path('/etc/ai4r/cc-rsi-development-launch.json')
IMAGE = 'sha256:00026931a8e236d255efca8d2e90ea49ae04989539fca4d418d318a98fa93ab2'
SOCKET = 'unix:///run/ai4r-rsi-docker/docker.sock'
FIELDS = set(('schema id authorization seed_input seed_receipt launch_guard_receipt runner seed restore host_check '
              'publisher seccomp admin_directory evaluator_root namespace_root cgroup_root control_directory '
              'publication_template baseline_publication_sha256 approved_plan_sha256 worker_plan launcher_sha256').split())


def need(value, reason):
    if not value: raise ValueError(reason)


def encoded(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
def sha(raw): return hashlib.sha256(raw).hexdigest()


def protected(path, *, owner=0, directory=False, maximum=4*1024*1024):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'ABSOLUTE_ROOT_PATH_REQUIRED')
    for parent in path.parents:
        info = parent.lstat()
        need(stat.S_ISDIR(info.st_mode) and info.st_uid in {0, owner} and not info.st_mode & 0o022, 'ROOT_ANCESTRY_DIFFERS')
    info = path.lstat()
    need(not path.is_symlink() and info.st_uid == owner and not info.st_mode & 0o022
         and (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= maximum),
         'PROTECTED_PATH_DIFFERS')
    return path


def pinned(value):
    need(isinstance(value, dict) and set(value) == {'path', 'sha256'}, 'CLOSED_SOURCE_PIN_REQUIRED')
    path = protected(value['path'])
    need(sha(path.read_bytes()) == value['sha256'], 'PINNED_BYTES_DIFFER')
    return path


def load(path=CONFIG):
    need(os.name == 'posix' and os.geteuid() == 0, 'ROOT_LAUNCHER_REQUIRED')
    raw = protected(path).read_bytes(); value = json.loads(raw)
    need(isinstance(value, dict) and set(value) == FIELDS and value['schema'] == 'ai4r-rsi-development-launcher:1', 'CLOSED_LAUNCH_INSTALLATION_REQUIRED')
    import re
    need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', value['id']) is not None, 'FINITE_RUN_ID_REQUIRED')
    need(value['launcher_sha256'] == sha(Path(__file__).read_bytes()), 'LAUNCHER_SOURCE_DIFFERS')
    for key in ('authorization','seed_input','seed_receipt','launch_guard_receipt','runner','seed','restore','host_check','publisher','seccomp','publication_template'):
        pinned(value[key])
    for key in ('admin_directory','evaluator_root','cgroup_root','control_directory'):
        protected(value[key], directory=True)
    protected(value['namespace_root'], owner=12001, directory=True)
    need(Path(value['runner']['path']).parent == Path(value['seed']['path']).parent == Path(value['admin_directory']), 'FIXED_ADMIN_SIBLINGS_REQUIRED')
    need(Path(value['cgroup_root']).parent == Path('/sys/fs/cgroup/ai4r-rsi-host/jobs')
         and Path(value['cgroup_root']).name == 'development-' + value['id'], 'EXACT_DEVELOPMENT_CGROUP_REQUIRED')
    need(Path(value['evaluator_root']) == Path('/var/lib/ai4r-rsi-codex/development-evidence')/value['id'], 'FIXED_EVALUATOR_HOST_BIND_REQUIRED')
    return value, raw


def helper(pin, name):
    spec = importlib.util.spec_from_file_location(name, pinned(pin))
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def exclusive(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream: stream.write(encoded(value)); stream.flush(); os.fsync(stream.fileno())
    directory = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(directory)
    finally: os.close(directory)


def docker(value, *args, timeout=30):
    command = ['/usr/bin/python3', '-B', value['restore']['path'], 'client', '/usr/bin/docker', '--host', SOCKET, *args]
    return subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin', 'PYTHONDONTWRITEBYTECODE':'1', 'HOME':'/root'}).stdout


def worker_command(value, operation):
    need(operation in ('plan', 'run'), 'FINITE_WORKER_OPERATION_REQUIRED')
    claim_directory = protected(Path(value['authorization']['path']).parent, directory=True)
    need(stat.S_IMODE(claim_directory.stat().st_mode) == 0o700, 'PRIVATE_ROOT_AUTHORIZATION_CLAIM_DIRECTORY_REQUIRED')
    name = 'ai4r-development-' + value['id'] + ('-doctor' if operation == 'plan' else '')
    args = ['create', '--name', name, '--init', '--read-only', '--network', 'none', '--user', '0:0', '--cap-drop', 'ALL']
    for capability in ('SETUID','SETGID','CHOWN','FOWNER','DAC_OVERRIDE','KILL'): args += ['--cap-add', capability]
    args += ['--security-opt','no-new-privileges:true','--security-opt','seccomp='+value['seccomp']['path'],
        '--cgroupns','host','--memory','512m','--memory-swap','512m','--pids-limit','64','--cpus','2',
        '--tmpfs','/tmp:rw,nosuid,nodev,size=64m','--entrypoint','/opt/venv/bin/python']
    mounts = [(value['namespace_root'],False),(value['evaluator_root'],False),
        (value['admin_directory'],True),('/run/ai4r-rsi-host-codex',True),(str(claim_directory),False)]
    mounts += [(value[key]['path'],True) for key in ('authorization','seed_receipt','launch_guard_receipt')]
    for source, readonly in mounts:
        need(',' not in source, 'MOUNT_SOURCE_DELIMITER_FORBIDDEN')
        args += ['--mount', f'type=bind,src={source},dst={source}' + (',readonly' if readonly else '')]
    args += ['--mount', f"type=bind,src={value['cgroup_root']},dst=/run/ai4r-rsi-cgroups"]
    args += [IMAGE, '-I', '-B', value['runner']['path'], operation, '--authorization', value['authorization']['path']]
    if operation == 'run': args += ['--approved-plan-sha256', value['approved_plan_sha256']]
    return args


def observe(value):
    seed = helper(value['seed'], 'development_launch_seed')
    seed_input = seed.parse(pinned(value['seed_input']).read_bytes())
    completed = seed.read_completed_seed(value['seed_receipt'])
    guard = seed.read_launch_guard(value['launch_guard_receipt'], value['seed_receipt'])
    need(seed.observe_originals(seed_input)[1] == guard['original_guards'] == completed['original_guards'], 'FROZEN_ORIGINALS_CHANGED')
    need(completed['destination']['isolation_root'] == value['namespace_root'] and completed['id'] == value['id'], 'FRESH_SEED_DESTINATION_DIFFERS')
    auth = json.loads(pinned(value['authorization']).read_bytes())
    need(auth['id'] == value['id'] and auth['isolation_root'] == value['namespace_root']
         and auth['evaluator_root'] == value['evaluator_root'] and auth['cgroup_root'] == '/run/ai4r-rsi-cgroups', 'FIXED_AUTHORIZATION_TOPOLOGY_DIFFERS')
    from datetime import datetime, timezone
    need(datetime.fromisoformat(auth['expires_at'].replace('Z','+00:00')) > datetime.now(timezone.utc), 'DEVELOPMENT_AUTHORIZATION_EXPIRED')
    template = json.loads(pinned(value['publication_template']).read_bytes())
    publication = protected(Path(template['publication_directory'])/'publication.json')
    need(sha(publication.read_bytes()) == value['baseline_publication_sha256'] == template['expected_previous_sha256'], 'BASELINE_PUBLICATION_CHANGED')
    current = json.loads(publication.read_bytes())
    need(current['workspace_id'] == template['workspace_id']
         and any(t['id'] == template['target_id'] for t in current['snapshot']['targets']), 'PUBLISHED_TARGET_WORKSPACE_DIFFERS')
    need(not docker(value, 'ps', '-q').strip(), 'OWNED_RUNTIME_NOT_IDLE')
    for group in (Path(value['cgroup_root']), *Path(value['cgroup_root']).rglob('*')):
        if group.is_dir():
            need(not (group/'cgroup.procs').read_text().strip() and 'populated 0' in (group/'cgroup.events').read_text(), 'OWNED_GROUP_NOT_EMPTY')
    return {'authorization_sha256': value['authorization']['sha256'], 'seed_sha256': value['seed_receipt']['sha256'],
        'guard_sha256': value['launch_guard_receipt']['sha256'], 'baseline_sha256': value['baseline_publication_sha256']}


def preflight(value):
    observe(value)
    inner = json.loads(pinned(value['worker_plan']).read_bytes())
    need(inner['plan_sha256'] == value['approved_plan_sha256'] == sha(encoded(inner['plan'])), 'WORKER_PLAN_REVIEW_DIFFERS')
    # Current original bytes are checked again inside the actual V18 worker by
    # runner.plan immediately before its own durable claim and first effect.
    for path, digest in inner['plan']['core_originals'].items():
        target = Path(path)
        need(target.is_relative_to(Path(value['namespace_root'])) and sha(protected(target, owner=12001, maximum=256*1024*1024).read_bytes()) == digest,
             'FRESH_CORE_ORIGINALS_CHANGED')
    need(not Path(value['authorization']['path']).with_name('development-claim.json').exists(), 'DEVELOPMENT_ALREADY_ISSUED')
    return {'schema':'ai4r-cc-rsi-development-preflight:1','ready':True,'run_id':value['id'],
        'approved_plan_sha256':value['approved_plan_sha256'],'authorization_sha256':value['authorization']['sha256']}


def collect(value, operation):
    control = Path(value['control_directory'])
    exclusive(control/(operation+'-claim.json'), {'schema':'ai4r-rsi-development-worker-claim:1','id':value['id'],
        'operation':operation,'image':IMAGE,'argv':worker_command(value, operation)})
    cid = docker(value, *worker_command(value, operation)).decode().strip()
    need(len(cid) == 64 and all(c in '0123456789abcdef' for c in cid), 'EXACT_OWNED_CID_REQUIRED')
    exclusive(control/(operation+'-container.json'), {'id':value['id'],'cid':cid,'image':IMAGE})
    docker(value, 'start', cid)
    deadline = time.monotonic() + (120 if operation == 'plan' else 3700)
    while True:
        info = json.loads(docker(value, 'inspect', cid))[0]
        need(info['Id'] == cid and info['Image'] == IMAGE, 'OWNED_CONTAINER_CHANGED')
        if not info['State']['Running']: break
        need(time.monotonic() < deadline, 'OWNED_WORKER_DEADLINE_EXPIRED_RECONCILE_NO_REPLAY')
        time.sleep(2)
    need(info['State']['Pid'] == 0, 'OWNED_WORKER_NOT_STOPPED')
    output = docker(value, 'logs', cid)
    exclusive(control/(operation+'-exit.json'), {'cid':cid,'exit_code':info['State']['ExitCode'],
        'inspection_sha256':sha(encoded(info)),'stdout_sha256':sha(output)})
    fd = os.open(control/(operation+'-stdout.log'), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream: stream.write(output); stream.flush(); os.fsync(stream.fileno())
    need(info['State']['ExitCode'] == 0, 'ACTUAL_WORKER_FAILED_NO_REPLAY')
    return output


def run(value):
    preflight(value)
    collect(value, 'run')
    publisher = helper(value['publisher'], 'development_actual_publication')
    template = json.loads(pinned(value['publication_template']).read_bytes())
    result = protected(Path(template['record_root'])/'development-result.json', owner=12001).read_bytes()
    template['result_sha256'] = sha(result)
    from datetime import datetime, timezone
    template['published_at'] = datetime.now(timezone.utc).isoformat()
    need(template['development_plan_sha256'] == value['approved_plan_sha256'] and template['run_id'] == value['id'], 'FIXED_PUBLICATION_PLAN_DIFFERS')
    input_path = Path(value['control_directory'])/'actual-publication-input.json'
    exclusive(input_path, template)
    _, facts, _ = publisher.plan(input_path)
    exclusive(input_path.with_name('actual-publication-plan.json'), facts)
    outcome = publisher.publish(input_path, publisher.sha(publisher.encoded(facts)))
    exclusive(input_path.with_name('complete.json'), {'schema':'ai4r-rsi-development-ui-completion:1',
        'id':value['id'],'result_sha256':template['result_sha256'],'publication':outcome,
        'security':'UNQUALIFIED','security_campaigns':'DEFERRED'})
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('operation', choices=('preflight','run','doctor-plan','doctor'))
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--review-sha256')
    args = parser.parse_args(); value, raw = load(args.config)
    if args.operation == 'preflight': outcome = preflight(value)
    elif args.operation == 'run': outcome = run(value)
    else:
        observed = observe(value)
        facts = {'schema':'ai4r-rsi-development-doctor-plan:1','config_sha256':sha(raw),
                 'observed':observed,'argv':worker_command(value,'plan'),'model_calls':0}
        if args.operation == 'doctor-plan': outcome = {'plan':facts,'plan_sha256':sha(encoded(facts))}
        else:
            need(args.review_sha256 == sha(encoded(facts)), 'DOCTOR_PLAN_REVIEW_REQUIRED')
            outcome = json.loads(collect(value,'plan'))
            need(outcome['plan_sha256'] == sha(encoded(outcome['plan'])), 'ACTUAL_WORKER_PLAN_INVALID')
            exclusive(Path(value['control_directory'])/'worker-plan.json', outcome)
    print(json.dumps(outcome, sort_keys=True))


if __name__ == '__main__': main()
