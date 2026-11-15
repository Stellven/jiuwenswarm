"""Finite, same-user file bridge. Docker and jobq remain exclusively on the host.

The inbox is a trusted local operator channel, not a multi-user security boundary.
Requests and responses are content addressed; queue names recover lost submit ACKs.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import re
import sys
import time
import uuid


def atomic(path, value):
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex)
    with temp.open('x') as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def call(operation, **values):
    root = Path(os.environ['FACTORY_BRIDGE_DIR'])
    packet = dict(operation=operation, **values)
    key = digest(packet)
    # Reads need a fresh response; mutations retain identity for replay.
    if operation != 'queue' or values['args'][0] != 'submit':
        key += '-' + uuid.uuid4().hex
    request, response = root / (key + '.request.json'), root / (key + '.response.json')
    atomic(request, packet)
    deadline = time.monotonic() + 60
    while not response.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError('Host bridge acknowledgement missing; reconcile before retry')
        time.sleep(.05)
    value = json.loads(response.read_text())
    if 'error' in value:
        raise ValueError(value['error'])
    return subprocess.CompletedProcess(value['args'], value['returncode'], value['stdout'], value['stderr'])


def handle(packet, workspace, queue, jobq):
    operation = packet['operation']
    if operation == 'lab_evidence_inspect':
        from .store import Store
        from .lab_evidence import inspect_evidence
        previous = os.environ.pop('FACTORY_BRIDGE_DIR', None)
        try:
            with Store(Path(os.environ.get('FACTORY_BRIDGE_HOME', str(workspace/'port-store')))) as store:
                result = inspect_evidence(store.scoped(packet['task_id']), packet['task_id'], packet['cycle_id'])
        finally:
            if previous is not None:
                os.environ['FACTORY_BRIDGE_DIR'] = previous
        return dict(args=[operation, packet['cycle_id']], returncode=0, stdout=json.dumps(result), stderr='')
    if operation in {'benchmark_result', 'prefill_workbench_result'}:
        attempt_id, task_id = packet['attempt_id'], packet['task_id']
        if not re.fullmatch(r'[a-f0-9]{32}', attempt_id):
            raise ValueError('Invalid benchmark attempt identity')
        from .store import Store
        from .benchmark import Benchmark
        # The finite host bridge is the trusted caller; avoid recursive bridge calls.
        previous = os.environ.pop('FACTORY_BRIDGE_DIR', None)
        try:
            with Store(Path(os.environ.get('FACTORY_BRIDGE_HOME', str(workspace/'port-store')))) as store:
                if operation == 'prefill_workbench_result':
                    from .prefill_workbench import Workbench
                    result = Workbench(store).result(task_id, attempt_id)
                else:
                    result = Benchmark(store).result(task_id, attempt_id)
        finally:
            if previous is not None:
                os.environ['FACTORY_BRIDGE_DIR'] = previous
        return dict(args=[operation,attempt_id],returncode=0,stdout=json.dumps(result),stderr='')
    if operation == 'recover_lab':
        attempt_id = packet['attempt_id']
        if not re.fullmatch(r'[a-f0-9]{32}', attempt_id):
            raise ValueError('Invalid attempt id')
        from .store import Store
        from .manager import Manager
        from .strata_lab import recover_upload
        with Store(Path(os.environ.get('FACTORY_BRIDGE_HOME', str(workspace/'port-store')))) as store:
            row = store._db.execute('SELECT * FROM attempts WHERE attempt_id=?', (attempt_id,)).fetchone()
            if row is None:
                raise ValueError('Unknown attempt')
            attempt = store._decode('attempts', row)
            if attempt['kind'] != 'lab' or attempt['state'] not in {'succeeded','failed','cancelled'} or attempt['request'].get('adapter') != 'strata-v1':
                raise ValueError('Only terminal owned Strata attempts may be recovered')
            manager = Manager(store, store.home/'lab-spool')
            recover_upload(manager, attempt['task_id'], attempt_id, manager.spool_root/attempt_id)
        return dict(args=['recover_lab',attempt_id],returncode=0,stdout='recovered',stderr='')
    if operation == 'cleanup':
        jid = packet['job_id']
        if not re.fullmatch(r'job-[a-f0-9]+', jid):
            raise ValueError('Invalid queue ID')
        job = json.loads((queue/(jid+'.json')).read_text())
        with sqlite3.connect('file:'+str(Path(os.environ.get('FACTORY_BRIDGE_HOME', str(workspace/'port-store')))/'factory.sqlite')+'?mode=ro', uri=True) as db:
            owned = db.execute('SELECT 1 FROM attempts WHERE jobq_id=? AND attempt_id=?', (jid, job['name'].removeprefix('factory:'))).fetchone()
        if not owned:
            raise ValueError('Cleanup query outside bridge store')
        from .jobs import Jobs
        value = Jobs._cleanup(job)
        return dict(args=['cleanup',jid],returncode=0,stdout=value,stderr='')
    if operation == 'queue':
        args = packet['args']
        if not args or args[0] not in ('submit', 'show', 'cancel') or Path(packet['qdir']).resolve() != queue:
            raise ValueError('Queue operation outside configured authority')
        if args[0] == 'submit':
            name = args[args.index('--name') + 1]
            if not name.startswith('factory:'):
                raise ValueError('Owned factory queue name required')
            timeout = float(args[args.index('--timeout') + 1])
            if not 0 < timeout <= 5400:
                raise ValueError('Queue deadline outside bounds')
            command = args[args.index('--') + 1:]
            if len(command) < 3 or command[1] != '-m' or command[2] not in (
                    'jiuwenswarm.factory.build_job', 'jiuwenswarm.factory.spark_run', 'jiuwenswarm.factory.spark_probe', 'jiuwenswarm.factory.runtime_job', 'jiuwenswarm.factory.strata_lab',
                    'jiuwenswarm.factory.lab_runner', 'jiuwenswarm.factory.ab_runner', 'jiuwenswarm.factory.benchmark_worker', 'jiuwenswarm.factory.prefill_worker'):
                raise ValueError('Unsupported host worker')
            if not re.fullmatch(r'factory:[a-f0-9]{32}', name):
                raise ValueError('Invalid attempt ownership')
            with sqlite3.connect('file:'+str(Path(os.environ.get('FACTORY_BRIDGE_HOME', str(workspace/'port-store')))/'factory.sqlite')+'?mode=ro', uri=True) as db:
                row = db.execute('SELECT resources FROM attempts WHERE attempt_id=?', (name.split(':',1)[1],)).fetchone()
            if row is None:
                raise ValueError('Attempt is outside bridge store')
            resources = json.loads(row[0])
            expected = [v.replace('{attempt_id}', name.split(':',1)[1]) for v in resources['argv']]
            if command != expected or resources['job_class'] != args[args.index('--class')+1] or resources['timeout_s'] != timeout:
                raise ValueError('Queue request differs from persisted identity')
            command[0] = sys.executable
            for path in queue.glob('job-*.json'):
                job = json.loads(path.read_text())
                if job['name'] == name:
                    prior_env = json.loads(Path(job['env_file']).read_text())
                    if job['argv'] != command or job['timeout'] != timeout or job['class'] != resources['job_class'] or any(prior_env.get(k) != v for k,v in packet.get('env',{}).items()):
                        raise ValueError('Same-name queue job conflicts with persisted request')
                    return dict(args=args, returncode=0, stdout=job['id']+'\n', stderr='')
            args = list(args)
            args[args.index('--') + 1] = sys.executable
        else:
            if len(args) != 2 or not re.fullmatch(r'job-[a-f0-9]+', args[1]):
                raise ValueError('Invalid queue ID')
            job = json.loads((queue / (args[1] + '.json')).read_text())
            with sqlite3.connect('file:'+str(Path(os.environ.get('FACTORY_BRIDGE_HOME', str(workspace/'port-store')))/'factory.sqlite')+'?mode=ro', uri=True) as db:
                owned = db.execute('SELECT 1 FROM attempts WHERE jobq_id=? AND attempt_id=?', (job['id'], job['name'].removeprefix('factory:'))).fetchone()
            if not job['name'].startswith('factory:') or not owned:
                raise ValueError('Refuse operation on unowned queue job')
        extra = packet.get('env', {})
        allowed = {'PATH', 'LD_LIBRARY_PATH', 'BUILD_JOBS', 'CC', 'CXX', 'CUDAHOSTCXX', 'CUDACXX',
                   'CUDA_HOME', 'CUDA_PATH', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS', 'FACTORY_HOME',
                   'BASE_RUNTIME', 'FACTORY_BUILD_ENGINE', 'PYTHONPATH', 'FACTORY_NATIVE_BUILDER_IMAGE', 'FACTORY_BENCHMARK_QUIET_ROOT', 'FACTORY_PREFILL_QUIET_ROOT'}
        if set(extra) - allowed:
            raise ValueError('Unsupported worker environment')
        env = dict(os.environ, **extra, JOBQ_DIR=str(queue), DOCKER_CMD_PREFIX='')
        env.pop('FACTORY_BRIDGE_DIR', None)
        argv = [sys.executable, str(jobq), *args]
    elif operation == 'git':
        source = Path(packet['path']).resolve()
        if not source.is_relative_to(workspace):
            raise ValueError('Source outside workspace')
        if packet['args'] not in (['rev-parse','HEAD'], ['rev-parse','HEAD^{tree}'], ['status','--porcelain','--untracked-files=all']):
            raise ValueError('Read-only git inspection required')
        argv, env = ['git', '-C', str(source), *packet['args']], dict(os.environ)
    elif operation == 'image':
        ref = packet['ref']
        if not isinstance(ref, str) or not ref or ref.startswith('-'):
            raise ValueError('Invalid image reference')
        argv, env = ['docker', 'image', 'inspect', ref], dict(os.environ)
    else:
        raise ValueError('Unknown bridge operation')
    result = subprocess.run(argv, env=env, cwd=workspace, capture_output=True, text=True, timeout=45)
    return dict(args=argv, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--queue', type=Path, required=True)
    p.add_argument('--jobq', type=Path, required=True)
    p.add_argument('--inbox', type=Path, required=True)
    p.add_argument('--seconds', type=int, default=10800)
    a = p.parse_args()
    a.inbox.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = (a.inbox/'bridge.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    deadline = time.monotonic() + a.seconds
    while time.monotonic() < deadline and not (a.inbox/'STOP').exists():
        for path in a.inbox.glob('*.request.json'):
            response = path.with_name(path.name.replace('.request.', '.response.'))
            if response.exists():
                continue
            try:
                packet = json.loads(path.read_text())
                if path.name.split('.')[0].split('-')[0] != digest(packet):
                    raise ValueError('Request hash mismatch')
                value = handle(packet, a.workspace.resolve(), a.queue.resolve(), a.jobq.resolve())
            except Exception as exc:
                value = {'error': str(exc)}
            atomic(response, value)
        time.sleep(.05)

if __name__ == '__main__':
    main()
