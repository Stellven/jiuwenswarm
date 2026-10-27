"""Repository-owned host operations; stdlib only, also executed over SSH/WSL.

RPC code is supplied by the checkout on stdin. Deployment directories contain
configuration and data, never an independently maintained private operator.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid

OWNER = 'ai4r-deployment:1'
NAME = re.compile(r'^[a-z0-9][a-z0-9_-]{0,47}$')
SHA = re.compile(r'^[a-f0-9]{64}$')
CHUNK = 4 * 1024 * 1024


def local_model_operator():
    """Load repository source, including the bundled copy in host RPC/timers."""
    source = globals().get('LOCAL_MODEL_OPERATOR_SOURCE')
    if source is None:
        source = Path(__file__).with_name('local_model_operator.py').read_text(encoding='utf-8')
    namespace = {'__name__': 'ai4r_local_model_operator'}
    exec(compile(source, '<repository-local-model-operator>', 'exec'), namespace)
    return namespace


def spark_model_operator():
    source = globals().get('SPARK_MODEL_OPERATOR_SOURCE')
    if source is None:
        source = Path(__file__).with_name('spark_model_operator.py').read_text(encoding='utf-8')
    selection = globals().get('SPARK_POOL_SELECTION')
    if selection is None:
        selection = json.loads(Path(__file__).with_name('spark-pool-v2.json').read_text(encoding='utf-8'))
    selection3 = globals().get('SPARK_POOL_SELECTION_V3')
    if selection3 is None:
        selection3 = json.loads(Path(__file__).with_name('spark-pool-v3.json').read_text(encoding='utf-8'))
    namespace = {'__name__': 'ai4r_spark_model_operator', 'SPARK_POOL_SELECTION': selection,
        'SPARK_POOL_SELECTION_V3':selection3}
    exec(compile(source, '<repository-spark-model-operator>', 'exec'), namespace)
    return namespace

# Read-only, operator-only inspection inside the owned app/container or its
# stopped volumes. Never mounted into the runner; never invokes store recovery.
IDLE_PROBE = '''import hashlib,json,os,sqlite3,stat,sys,tempfile
from pathlib import Path
root=Path(sys.argv[1] if len(sys.argv)>1 else '/var/lib/ai4r')
executor=Path(sys.argv[2] if len(sys.argv)>2 else '/var/lib/ai4r-executor')
snapshot=len(sys.argv)>3 and sys.argv[3]=='--stopped-snapshot'
checks=[(root/'state/research.sqlite3',"SELECT count(*) FROM runs WHERE state NOT IN ('completed','halted','partial')"),
        (executor/'ledger/claims.sqlite3',"SELECT count(*) FROM claims WHERE state!='completed'"),
        (executor/'attempts/attempts.sqlite3',"SELECT count(*) FROM leases WHERE state!='released'")]
budget=48*1024*1024
def fingerprint(path):
 if not path.exists():return None
 assert not any(p.is_symlink() for p in (path,*path.parents))
 fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
 try:
  meta=os.fstat(fd);assert stat.S_ISREG(meta.st_mode) and meta.st_nlink==1 and meta.st_size<=budget
  digest=hashlib.sha256();size=0
  with os.fdopen(fd,'rb',closefd=False) as stream:
   while True:
    block=stream.read(1024*1024)
    if not block:break
    size+=len(block);assert size<=budget;digest.update(block)
  return size,digest.hexdigest()
 finally:os.close(fd)
def observe(folder=None):
 paths=[];optional=checks[-1][0].parent
 absent=not optional.exists()
 for path,query in checks:
  if path==checks[-1][0] and absent:continue
  assert path.is_file() and not any(p.is_symlink() for p in (path,*path.parents))
  paths.extend(Path(str(path)+suffix) for suffix in ('','-wal','-shm'))
 before={p:fingerprint(p) for p in paths} if folder else {}
 assert sum(value[0] for value in before.values() if value is not None)<=budget
 copied={}
 if folder:
  for index,(path,query) in enumerate(checks):
   if path==checks[-1][0] and absent:continue
   target=folder/str(index)/path.name;target.parent.mkdir(mode=0o700)
   for suffix in ('','-wal','-shm'):
    source=Path(str(path)+suffix)
    if before[source] is None:continue
    destination=Path(str(target)+suffix)
    fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as output,source.open('rb') as stream:
     total=0
     while True:
      block=stream.read(1024*1024)
      if not block:break
      total+=len(block);assert total<=before[source][0];output.write(block)
    assert fingerprint(destination)==before[source]
   copied[path]=target
  assert before=={p:fingerprint(p) for p in paths},'Stopped database changed during inspection'
  assert absent==(not optional.exists()),'Stopped database topology changed during inspection'
 counts=[]
 for path,query in checks:
  if path==checks[-1][0] and absent:counts.append(0);continue
  # Query the complete copied WAL view. Never ignore WAL via immutable=1.
  target=copied.get(path,path)
  db=sqlite3.connect(target.as_uri()+'?mode=ro',uri=True)
  try:counts.append(db.execute(query).fetchone()[0])
  finally:db.close()
 return counts
counts=[]
if snapshot:
 with tempfile.TemporaryDirectory(prefix='ai4r-idle-') as directory:counts=observe(Path(directory))
else:counts=observe()
assert not any(counts),'Active/unknown research execution refuses lifecycle changes'
print(json.dumps({'idle':True,'active_runs':counts[0],'unfinished_claims':counts[1],'unreleased_leases':counts[2]}))
'''


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def checked(path):
    path = Path(path).absolute()
    if any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)() for p in (path, *path.parents)):
        raise ValueError('Symlink/junction paths are not allowed')
    return path


def relative(value):
    p = PurePosixPath(value)
    if (not value or not p.parts or p.is_absolute() or '..' in p.parts or '\\' in value
            or ':' in value or str(p) != value or any(ord(c) < 32 for c in value)):
        raise ValueError('Unsafe relative path')
    return p


def digest(path):
    h = hashlib.sha256()
    with checked(path).open('rb') as f:
        while block := f.read(CHUNK):
            h.update(block)
    return h.hexdigest()


def publish(path, data, replace=False, mode=0o600):
    path = checked(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.publish-' + uuid.uuid4().hex)
    try:
        with temporary.open('xb') as f:
            os.chmod(temporary, mode)
            f.write(data); f.flush(); os.fsync(f.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            # Hard-link publication is exclusive; never replace existing bytes.
            os.link(temporary, path)
        if os.name == 'posix':
            descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try: os.fsync(descriptor)
            finally: os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def lock(path):
    path = checked(path)
    with path.open('a+b') as f:
        if os.name == 'nt':
            import msvcrt
            f.write(b'0'); f.flush(); f.seek(0)
            try: msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError: raise ValueError('Deployment is busy') from None
        else:
            import fcntl
            try: fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise ValueError('Deployment is busy') from None
        yield


def run(argv, *, data=None, env=None, timeout=120):
    p = subprocess.run(argv, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       env=env, timeout=timeout)
    if p.returncode:
        # Tools may print bootstrap URLs/tokens. Do not propagate their output.
        raise ValueError('Command failed: ' + ' '.join(argv[:3]) + '; inspect the owned service logs privately')
    return p.stdout


def docker(p, *args, **kwargs):
    prefix = ['docker'] + (['--context', p['docker_context']] if p.get('docker_context') else [])
    return run(prefix + list(args), **kwargs)


def compose(p, *args, **kwargs):
    return docker(p, 'compose', '-p', p['project'], '-f', str(Path(p['root']) / 'compose.json'),
                  '--profile', 'benchmark', *args, **kwargs)


def capacity(path, additional=0):
    usage = shutil.disk_usage(checked(path))
    if additional < 0 or usage.free - additional < usage.total * .20:
        raise ValueError('Insufficient storage: preserve 20% filesystem headroom')
    return {'total_bytes': usage.total, 'free_bytes': usage.free, 'additional_bytes': additional}


def owned(p):
    root = checked(p['root'])
    if json.loads((root / 'owner.json').read_bytes()) != {'schema': OWNER, 'project': p['project']}:
        raise ValueError('Foreign deployment directory')
    return root


def assert_idle(p):
    """Do not infer stopped execution from process/heartbeat loss."""
    output = checked(p['output'])
    for state in output.glob('*/campaign_state.json'):
        value = json.loads(checked(state).read_bytes())
        if value.get('state') not in {'complete', 'stopped'}:
            raise ValueError('Active/unknown campaign; reconcile before changing deployment or expiring data')
        for record in state.parent.glob('runs/*/run_record.json'):
            row = json.loads(checked(record).read_bytes())
            if row.get('app_run_id') and (row.get('execution_state') not in {
                    'completed', 'partial', 'interrupted', 'failed', 'cancelled', 'blocked', 'halted', 'timed_out', 'rejected'}
                    or row.get('collection_state') != 'complete'):
                raise ValueError('Unresolved execution or uncollected evidence')


def assert_app_idle(p):
    root = Path(p['root'])
    if not (root / 'compose.json').exists(): return
    ids = compose(p, 'ps', '-aq', 'ai4r').decode().split()
    if not ids: return
    if len(ids) != 1: raise ValueError('Ambiguous app instance; refusing lifecycle changes')
    container = json.loads(docker(p, 'inspect', ids[0]))[0]
    if container['Config']['Labels'].get('ai4r.deployment') != p['deployment_id']:
        raise ValueError('Foreign app instance')
    try:
        if container['State']['Running']:
            result = json.loads(compose(p, 'exec', '-T', '--user', '0:0', 'ai4r',
                                '/opt/venv/bin/python', '-c', IDLE_PROBE))
        else:
            result = json.loads(docker(p, 'run', '--rm', '--network', 'none', '--read-only',
                '--user', '0:0', '--cap-drop', 'ALL', '--cap-add', 'DAC_READ_SEARCH',
                '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
                '--mount', 'type=volume,src=' + p['project'] + '_state,dst=/var/lib/ai4r,readonly',
                '--mount', 'type=volume,src=' + p['project'] + '_executor,dst=/var/lib/ai4r-executor,readonly',
                '--entrypoint', '/opt/venv/bin/python', container['Image'], '-c', IDLE_PROBE,
                '/var/lib/ai4r', '/var/lib/ai4r-executor', '--stopped-snapshot'))
        if result.get('idle') is not True: raise ValueError('App is not idle')
    except (OSError, ValueError):
        raise ValueError('App has active/unknown runs, executor claims or leases, or inspection is unavailable; reconcile through the app before lifecycle changes') from None


def render(p, template):
    """Resolve the existing checked-in Compose contract, then pin runtime only."""
    root = Path(p['root'])
    env = os.environ.copy()
    # Host variables must never accidentally redirect mounts/volumes.
    for key in list(env):
        if key.startswith(('AI4R_', 'COMPOSE_', 'JIUWENSWARM_M1_')):
            env.pop(key)
    env.update(COMPOSE_PROJECT_NAME=p['project'], AI4R_APP_IMAGE=p.get('app_image', 'ai4r:local'),
        AI4R_RUNNER_IMAGE=p.get('runner_image', 'benchmark-runner:local'),
        AI4R_SECCOMP_PROFILE=str(root / 'seccomp.json'),
        AI4R_REUSABLE_LOGIN='1', AI4R_LOCAL_WORKSPACE='1', AI4R_LOCAL_CHAT='1', AI4R_LOCAL_RESEARCH='1',
        AI4R_BENCH_CASES=str(root / 'cases'), AI4R_BENCH_INPUTS=str(root / 'inputs' / p.get('input_stage', '')),
        AI4R_EXPECTED_BUILD=p.get('build_id', 'unconfigured'))
    source = root / 'compose.source.yaml'
    publish(source, template.encode(), replace=True)
    result = json.loads(docker(p, 'compose', '-p', p['project'], '-f', str(source),
                               '--profile', 'benchmark', 'config', '--format', 'json', env=env))
    for service in result['services'].values():
        service.pop('build', None)
        service.setdefault('labels', {})['ai4r.deployment'] = p['deployment_id']
        service['logging'] = {'driver': 'json-file', 'options': {'max-size': '10m', 'max-file': '3'}}
    for volume in result['volumes'].values():
        volume.setdefault('labels', {})['ai4r.deployment'] = p['deployment_id']
    for network in result['networks'].values():
        network.setdefault('labels', {})['ai4r.deployment'] = p['deployment_id']
    if p.get('cgroup_root'):
        app = result['services']['ai4r']
        app['cgroup'] = 'host'
        app['environment']['AI4R_EXECUTOR_CGROUP_ROOT'] = '/run/ai4r-cgroups'
        app['volumes'].append({'type': 'bind', 'source': p['cgroup_root'], 'target': '/run/ai4r-cgroups',
                               'bind': {'create_host_path': False}})
    result['services']['ai4r']['platform'] = p['platform']
    runner = result['services']['benchmark-runner']
    runner['platform'] = p['platform']
    runner['user'] = str(p['runner_uid']) + ':' + str(p['runner_gid'])
    runner['tmpfs'] = ['/tmp:rw,nosuid,nodev,size=128m,uid=' + str(p['runner_uid']) + ',gid=' + str(p['runner_gid'])]
    runner['volumes'] = [m for m in runner['volumes'] if m['target'] not in {'/run/benchmark-runner', '/results'}]
    runner['volumes'].append({'type': 'volume', 'source': 'runner_credentials', 'target': '/run/benchmark-runner',
                              'read_only': True, 'volume': {'nocopy': True}})
    runner['volumes'].append({'type': 'bind', 'source': p['output'], 'target': '/results',
                              'bind': {'create_host_path': False}})
    result['volumes']['runner_credentials'] = {'name': p['project'] + '_runner_credentials',
        'labels': {'ai4r.deployment': p['deployment_id']}}
    if p.get('local_model') is not None:
        local_model_operator()['apply_compose'](p, result)
    if p.get('local_pool') is not None:
        spark_model_operator()['apply_compose'](p, result)
    publish(root / 'compose.json', canonical(result), replace=True)


def setup(request):
    p = request['profile']
    if not NAME.fullmatch(p['project']) or not p['project'].startswith('ai4r-'):
        raise ValueError('Project must start ai4r- and use lowercase letters/digits/-/_')
    raw = p.get('root')
    if raw and not Path(raw).is_absolute():
        raise ValueError('Deployment root must be an absolute path on the execution host')
    if p.get('output') and not Path(p['output']).is_absolute():
        raise ValueError('Output must be an absolute path on the execution host')
    root = checked(Path.home() / '.local/share/ai4r' / p['project'] if not raw else raw)
    if not root.is_absolute() or root == Path(root.anchor) or root == Path.home():
        raise ValueError('Choose a dedicated deployment directory')
    p['root'] = str(root)
    p['output'] = str(checked(p.get('output') or root / 'results'))
    output = Path(p['output'])
    if output == root or root.is_relative_to(output) or any(
            output == root / name or output.is_relative_to(root / name)
            for name in ('credentials', 'temporary', 'cases', 'inputs')):
        raise ValueError('Output must be separate from deployment control/input/temporary state')
    if p['platform'] not in {'linux/amd64', 'linux/arm64'}:
        raise ValueError('Unsupported target platform')
    if root.exists():
        owned(p)
        old = json.loads((root / 'deployment.json').read_bytes())
        # Repeated setup never resets images, tokens or paths.
        for key in ('project', 'root', 'output', 'platform', 'docker_context'):
            if old.get(key) != p.get(key):
                raise ValueError('Existing setup differs; choose a new deployment/profile')
        return old
    p['deployment_id'] = uuid.uuid4().hex
    p['runner_uid'] = os.geteuid() if os.name == 'posix' and os.geteuid() else 11001
    p['runner_gid'] = os.getegid() if os.name == 'posix' and os.geteuid() else 11001
    root.mkdir(parents=True, mode=0o700)
    publish(root / 'owner.json', canonical({'schema': OWNER, 'project': p['project']}))
    for name in ('cases', 'inputs', 'credentials', 'temporary'):
        (root / name).mkdir(mode=0o700)
    output = checked(p['output']); new_output = not output.exists()
    output.mkdir(parents=True, exist_ok=True)
    # Only new owned directories receive permissions; user files are untouched.
    for name in ('cases', 'inputs'):
        (root / name).chmod(0o755)
    if new_output:
        # Outer root is private; this bind root must admit runner UID11001.
        output.chmod(0o700 if os.name == 'posix' and os.geteuid() else 0o1777)
    publish(root / 'config.json', b'{}\n', mode=0o644)
    publish(root / 'seccomp.json', request['seccomp'].encode(), mode=0o644)
    publish(root / 'deployment.json', canonical(p))
    return p


def gc(p, *, dry_run=False, now=None):
    root = owned(p); now = time.time() if now is None else now
    assert_idle(p)
    removed = []; eligible = []
    for folder in (root / 'temporary').iterdir():
        folder = checked(folder)
        if not folder.is_dir():
            continue
        marker = folder / 'temporary.json'
        if not marker.is_file():
            continue
        record = json.loads(checked(marker).read_bytes())
        if (record.get('owner') != OWNER or record.get('project') != p['project']
                or record.get('status') != 'complete' or record.get('kind') not in {'transfer', 'build-context', 'snapshot'}):
            continue
        if now - record['completed_at'] < p['ttl_days'] * 86400:
            continue
        # Never traverse symlinks, junctions, hardlinks or protected roots.
        for item in folder.rglob('*'):
            checked(item)
            if item.is_file() and item.stat().st_nlink != 1:
                raise ValueError('Temporary resource contains hardlinks; refusing expiry')
        eligible.append(folder.name)
        if not dry_run:
            shutil.rmtree(folder); removed.append(folder.name)
    receipt = {'at': now, 'dry_run': dry_run, 'eligible': eligible, 'removed': removed,
               'retained': ['results', 'inputs', 'credentials', 'app/account volumes', 'models', 'deployed/rollback image pins']}
    if not dry_run:
        log = checked(root / 'gc.jsonl')
        if log.exists() and log.stat().st_size >= 1024 * 1024:
            previous = checked(root / 'gc.jsonl.1'); previous.unlink(missing_ok=True)
            log.rename(previous)
        with log.open('ab') as stream:
            stream.write(canonical(receipt) + b'\n'); stream.flush(); os.fsync(stream.fileno())
    return receipt


def gc_images(p, dry_run=False):
    """Only unused, expired build candidates with our exact owner label.

    Deployed/current/rollback images are pinned; Docker must also confirm no
    container references the candidate. Removal never uses force or prune.
    """
    from datetime import datetime
    pinned = set(p.get('image_pins', [])) | {p.get('app_image'), p.get('runner_image')}
    eligible = []; removed = []
    try:
        stored = json.loads((Path(p['root']) / 'deployment.json').read_bytes())
        pinned |= set(stored.get('image_pins', [])) | {stored.get('app_image'), stored.get('runner_image')}
        ids = docker(p, 'image', 'ls', '--no-trunc', '--filter', 'label=ai4r.owner=' + p['project'],
                     '--filter', 'label=ai4r.deployment=' + p['deployment_id'],
                     '--format', '{{.ID}}').decode().split()
        for ident in set(ids):
            if ident in pinned: continue
            image = json.loads(docker(p, 'image', 'inspect', ident))[0]
            if image.get('Config', {}).get('Labels', {}).get('ai4r.owner') != p['project']: continue
            if image['Config']['Labels'].get('ai4r.deployment') != p['deployment_id']: continue
            created = datetime.fromisoformat(image['Created'].replace('Z', '+00:00')).timestamp()
            if time.time() - created < p['ttl_days'] * 86400: continue
            if docker(p, 'ps', '-aq', '--filter', 'ancestor=' + ident).strip(): continue
            eligible.append(ident)
            if not dry_run:
                docker(p, 'image', 'rm', ident); removed.append(ident)
        return {'eligible': eligible, 'removed': removed}
    except (OSError, ValueError, KeyError):
        return {'eligible': eligible, 'removed': removed, 'unavailable': 'Docker unavailable or candidate ownership changed; no global cleanup attempted'}


def temporary(p, kind):
    root = owned(p)
    capacity(root)
    folder = root / 'temporary' / uuid.uuid4().hex
    folder.mkdir()
    publish(folder / 'temporary.json', canonical({'owner': OWNER, 'project': p['project'],
            'kind': kind, 'status': 'incomplete', 'created_at': time.time()}))
    return folder


def finish_temporary(folder):
    marker = folder / 'temporary.json'; value = json.loads(marker.read_bytes())
    value.update(status='complete', completed_at=time.time())
    publish(marker, canonical(value), replace=True)


def file_info(path):
    path = checked(path); info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Expected a single-link regular file')
    return {'size': info.st_size, 'sha256': digest(path)}


def dispatch(r):
    action = r['action']; p = r['profile']
    if action == 'setup':
        return setup(r)
    root = owned(p)
    if action == 'runner':
        args = r['args']
        if not args or args[0] not in {'doctor', 'run', 'status', 'resume', 'cancel', 'export', 'cleanup'}:
            raise ValueError('Unknown runner command')
        prefix = ['docker'] + (['--context', p['docker_context']] if p.get('docker_context') else [])
        cmd = prefix + ['compose', '-p', p['project'], '-f', str(root / 'compose.json'),
            'exec', '-T', '--user', str(p['runner_uid']) + ':' + str(p['runner_gid']), 'benchmark-runner', 'benchmark-runner', *args]
        if args[0] in {'run', 'resume', 'export', 'cleanup'}:
            with lock(root / 'execution.lock'):
                return execute_cli(cmd)
        return execute_cli(cmd)
    with lock(root / 'operator.lock'):
        if action == 'gc':
            with lock(root / 'execution.lock'):
                result = gc(p, dry_run=r.get('dry_run', False))
                result['images'] = gc_images(p, r.get('dry_run', False))
                return result
        if action == 'doctor':
            result = {'storage': capacity(root), 'output_storage': capacity(p['output']),
                      'platform': p['platform'], 'project': p['project'],
                      'authentication': 'Run start, complete browser sign-in, then start --refresh-credential'}
            try:
                info = json.loads(docker(p, 'info', '--format', '{{json .}}'))
                result['docker'] = {key: info.get(key) for key in (
                    'Architecture', 'OSType', 'ServerVersion', 'DockerRootDir', 'CgroupDriver', 'CgroupVersion', 'Driver')}
                if (root / 'compose.json').exists():
                    raw = compose(p, 'ps', '--format', 'json').decode().strip()
                    try: result['services'] = json.loads(raw or '[]')
                    except ValueError: result['services'] = [json.loads(line) for line in raw.splitlines()]
                else:
                    result['services'] = []; result['deployment_state'] = 'not_started'
            except (ValueError, FileNotFoundError) as exc:
                result['prerequisite_error'] = str(exc)
            return result
        if action == 'configure':
            with lock(root / 'execution.lock'):
                assert_idle(p)
                previous = json.loads((root / 'deployment.json').read_bytes())
                p['image_pins'] = sorted(set(previous.get('image_pins', [])) | {
                    previous[key] for key in ('app_image', 'runner_image') if previous.get(key)})
                if p.get('input_stage'):
                    if not SHA.fullmatch(p['input_stage']): raise ValueError('Invalid stage identity')
                    (root / 'inputs' / p['input_stage']).mkdir(mode=0o755, exist_ok=True)
                publish(root / 'deployment.json', canonical(p), replace=True)
                return {'configured': True, 'deployment': p}
        if action == 'local-model-configure':
            with lock(root / 'execution.lock'):
                assert_idle(p)
                assert_app_idle(p)
                if set(r) != {'action', 'profile', 'catalog', 'session_file', 'socket_directory'}:
                    raise ValueError('Invalid local-model configuration request')
                selected, _, _ = local_model_operator()['inspect_sources'](
                    r['catalog'], r['session_file'], r['socket_directory'])
                previous = json.loads((root / 'deployment.json').read_bytes())
                previous['local_model'] = selected
                publish(root / 'deployment.json', canonical(previous), replace=True)
                return {'configured': True, 'deployment': previous, 'activated': False}
        if action in {'local-pool-configure', 'local-pool-migrate', 'local-pool-prepare', 'local-pool-weights'}:
            with lock(root / 'execution.lock'):
                assert_idle(p)
                assert_app_idle(p)
                previous = json.loads((root / 'deployment.json').read_bytes())
                helper = spark_model_operator()
                if action == 'local-pool-migrate':
                    old = previous.get('local_pool')
                    if (not old or old.get('schema') not in {'ai4r-spark-pool:1','ai4r-spark-pool:2'}
                            or old.get('selection_generation')==3):
                        raise ValueError('Migration requires an older pinned local pool')
                    previous.setdefault('retired_local_pools', []).append(old)
                    previous['local_pool'] = helper['configure_v2'](previous, r['data_root'], docker, checked,
                        share_address=r.get('share_address'))
                elif action == 'local-pool-configure':
                    if previous.get('local_pool'):
                        raise ValueError('Local pool is already pinned; retain it or explicitly migrate the idle deployment')
                    previous['local_pool'] = helper['configure_v2'](previous, r['data_root'], docker, checked,
                        share_address=r.get('share_address'))
                elif action=='local-pool-weights':
                    previous['local_pool'] = helper['fetch_weights'](previous, docker, checked, publish, canonical)
                else:
                    previous['local_pool'] = helper['prepare'](previous, docker, checked, publish, canonical)
                publish(root / 'deployment.json', canonical(previous), replace=True)
                return {'configured': True, 'prepared': previous['local_pool']['prepared'],
                        'weights_ready': previous['local_pool'].get('weights_ready',False),
                        'deployment': previous, 'activated': False}
        if action == 'begin-transfer':
            with lock(root / 'execution.lock'):
                assert_idle(p)
                gc(p)
                capacity(root, r['size'])
                folder = temporary(p, 'transfer')
                return {'id': folder.name}
        if action == 'put':
            folder = transfer_folder(p, r['id'])
            target = checked(folder / 'payload')
            block = base64.b64decode(r['data'], validate=True)
            if len(block) > CHUNK:
                raise ValueError('Transfer chunk exceeds bound')
            capacity(root, len(block))
            mode = 'xb' if r['offset'] == 0 else 'r+b'
            if r['offset'] and (not target.exists() or target.stat().st_size != r['offset']):
                raise ValueError('Unexpected transfer offset')
            with target.open(mode) as f:
                f.seek(0, 2)
                if f.tell() != r['offset']:
                    raise ValueError('Unexpected transfer offset')
                f.write(block); f.flush(); os.fsync(f.fileno())
            return {'written': len(block)}
        if action == 'file-check':
            destination = data_destination(p, r['kind'], r['path'])
            return {'matches': destination.is_file() and file_info(destination) == r['info']}
        if action == 'publish-transfer':
            with lock(root / 'execution.lock'):
                assert_idle(p)
                folder = transfer_folder(p, r['id']); source = folder / 'payload'
                if file_info(source) != r['info']:
                    raise ValueError('Transferred size/hash mismatch')
                if r['kind'] == 'image':
                    capacity(root, r['unpacked_bytes'])
                    docker(p, 'load', '--input', str(source), timeout=3600)
                    observed = json.loads(docker(p, 'image', 'inspect', r['image_id']))[0]
                    if observed['Id'] != r['image_id'] or 'linux/' + observed['Architecture'] != p['platform']:
                        raise ValueError('Loaded image identity/platform mismatch')
                    source.unlink()  # Verified engine image replaces disposable transport TAR.
                else:
                    dest = data_destination(p, r['kind'], r['path'])
                    if dest.exists():
                        if file_info(dest) != r['info']:
                            raise ValueError('Existing staged file differs; use a new stage identity')
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        for parent in (dest.parent, *dest.parents):
                            if parent == root: break
                            parent.chmod(0o755)
                        os.link(source, dest); dest.chmod(0o644)
                        source.unlink()
                finish_temporary(folder)
                return {'verified': True}
        if action == 'image-check':
            try:
                image = json.loads(docker(p, 'image', 'inspect', r['image_id']))[0]
                return {'matches': image['Id'] == r['image_id'] and 'linux/' + image['Architecture'] == p['platform']}
            except ValueError:
                return {'matches': False}
        if action == 'snapshot':
            with lock(root / 'execution.lock'):
                return make_snapshot(p, r['campaign'])
        if action == 'read-chunk':
            folder = transfer_folder(p, r['id'], kind='snapshot')
            path = checked(folder / 'data' / relative(r['path']))
            with path.open('rb') as f:
                f.seek(r['offset']); data = f.read(CHUNK)
            return {'data': base64.b64encode(data).decode()}
        if action == 'start':
            with lock(root / 'execution.lock'):
                assert_idle(p); gc(p); capacity(root)
                return start(p, r)
        if action == 'stop':
            with lock(root / 'execution.lock'):
                assert_idle(p)
                assert_app_idle(p)
                retained = bool(p.get('local_pool', {}).get('shared_access'))
                services = ('ai4r', 'benchmark-runner') if retained else ()
                compose(p, 'stop', '--timeout', '45', *services, timeout=120)
                return {'stopped': True, 'state_retained': True, 'shared_models_retained': retained}
        if action == 'logs':
            # Logs are intentionally private; returned only on an explicit command.
            return {'stdout': compose(p, 'logs', '--no-color', '--tail', str(r['tail']), r['service']).decode(errors='replace')}
        if action == 'install-maintenance':
            return install_timer(p, r['source'])
    raise ValueError('Unknown host operation')


def execute_cli(cmd):
    # Stream runner progress to the caller, including over SSH. JSON response
    # remains a single final line; stderr is never mistaken for structured data.
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=sys.stderr)
    out = process.communicate()[0]
    return {'returncode': process.returncode, 'stdout': out.decode(errors='replace')}


def transfer_folder(p, ident, kind='transfer'):
    if not SHA.fullmatch(ident) and not re.fullmatch('[a-f0-9]{32}', ident):
        raise ValueError('Unsafe transfer identity')
    folder = checked(Path(p['root']) / 'temporary' / ident)
    record = json.loads((folder / 'temporary.json').read_bytes())
    if record.get('owner') != OWNER or record.get('project') != p['project'] or record.get('kind') != kind:
        raise ValueError('Foreign transfer')
    return folder


def data_destination(p, kind, name):
    if kind not in {'cases', 'inputs'}:
        raise ValueError('Only selected case/input staging is allowed')
    return checked(Path(p['root']) / kind / relative(name))


def make_snapshot(p, campaign):
    if not NAME.fullmatch(campaign):
        raise ValueError('Unsafe campaign ID')
    source = checked(Path(p['output']) / campaign)
    marker = json.loads((source / '.runner-owner.json').read_bytes())
    if marker != {'owner': 'ai4r-sequential-runner:1', 'campaign_id': campaign}:
        raise ValueError('Foreign campaign')
    # Acquire the actual runner lock even if another client controls it.
    with lock(source / '.runner.lock'):
        rows = []
        for file in sorted(source.rglob('*')):
            checked(file)
            if file.is_file() and file.name != '.runner.lock':
                rows.append({'path': file.relative_to(source).as_posix(), **file_info(file)})
        capacity(p['root'], sum(row['size'] for row in rows))
        folder = temporary(p, 'snapshot')
        for row in rows:
            target = folder / 'data' / relative(row['path']); target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / row['path'], target)
            if file_info(target) != {'size': row['size'], 'sha256': row['sha256']}:
                raise ValueError('Campaign changed during snapshot; no export published')
        finish_temporary(folder)
        return {'id': folder.name, 'campaign': campaign, 'files': rows}


def start(p, r):
    root = Path(p['root'])
    if any(not re.fullmatch('sha256:[a-f0-9]{64}', p.get(key, '')) for key in ('app_image', 'runner_image')):
        raise ValueError('Run build and stage first to select immutable app and runner images')
    resources = docker(p, 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + p['project']).decode().split()
    for ident in resources:
        observed = json.loads(docker(p, 'inspect', ident))[0]
        if observed['Config']['Labels'].get('ai4r.deployment') != p['deployment_id']:
            raise ValueError('Existing installation requires explicit migration; refusing replacement')
    for kind, name in [('volume', p['project'] + '_' + n) for n in ('state', 'accounts', 'ipc', 'poc', 'inputs', 'executor', 'runner_credentials')] + [('network', p['project'] + '_private')]:
        try: values = json.loads(docker(p, kind, 'inspect', name))
        except ValueError: continue
        if values[0].get('Labels', {}).get('ai4r.deployment') != p['deployment_id']:
            raise ValueError('Foreign existing ' + kind + '; choose a new project or migrate explicitly')
    # Ordinary Docker launch never changes host cgroups or invokes elevation.
    # A separately provisioned bounded delegation can still be recorded in an
    # existing profile; unavailable execution features retain their app guards.
    initialized = root / 'initialized.json'
    if initialized.exists() and json.loads(initialized.read_bytes())['app_image'] != p['app_image']:
        raise ValueError('App image changed; use another deployment or an explicit reviewed app upgrade')
    assert_app_idle(p)
    if p.get('local_model') is not None:
        local_model_operator()['provision'](p, docker)
    if p.get('local_pool') is not None:
        spark_model_operator()['preflight_start'](p, docker)
        spark_model_operator()['provision'](p, docker, canonical)
    render(p, r['template'])
    for key in ('app_image', 'runner_image'):
        image = json.loads(docker(p, 'image', 'inspect', p[key]))[0]
        if 'linux/' + image['Architecture'] != p['platform']:
            raise ValueError('Image architecture does not match target')
    compose(p, 'up', '-d', '--no-build', '--pull', 'never', 'ai4r', timeout=1200 if p.get('local_pool') else 180)
    # Wait for native ownership sockets, not model login or model execution.
    for attempt in range(60):
        try:
            compose(p, 'exec', '-T', '--user', '10001:10001', 'ai4r', 'sh', '-c',
                    'test -S /run/ai4r/model.sock && test -S /run/ai4r-executor/executor.sock')
            break
        except ValueError:
            if attempt == 59: raise
            time.sleep(1)
    if not initialized.exists():
        result = json.loads(compose(p, 'exec', '-T', '--user', '10001:10001', 'ai4r',
            '/opt/venv/bin/python', '-m', 'jiuwenswarm.research.initialize', '--json', timeout=300))
        if result.get('status') != 'initialized':
            raise ValueError('App catalog initialization blocked; inspect app prerequisites')
        publish(initialized, canonical({'app_image': p['app_image']}))
        assert_app_idle(p)
        compose(p, 'up', '-d', '--force-recreate', '--no-deps', '--no-build', '--pull', 'never', 'ai4r', timeout=180)
        publish(root / 'deployment.json', canonical(p), replace=True)
        return {'deployment': p, 'app_started': True, 'next': 'Complete sign-in at http://127.0.0.1:5175, then run start --refresh-credential. For SSH use an SSH port-forward.'}
    container = compose(p, 'ps', '-q', 'ai4r').decode().strip()
    started_at = json.loads(docker(p, 'inspect', container))[0]['State']['StartedAt']
    refresh = (r.get('refresh_credential') or started_at != p.get('app_started_at')
               or p.get('grant', {}).get('expires_at', 0) <= time.time())
    if refresh:
        issue_credential(p)
        p['app_started_at'] = started_at
    if not p.get('credential_ready'):
        return {'deployment': p, 'app_started': True, 'next': 'Complete sign-in at localhost:5175; run start --refresh-credential'}
    mount_probe(p)
    options = ['--force-recreate'] if refresh else []
    compose(p, 'up', '-d', *options, '--no-build', '--pull', 'never', 'benchmark-runner', timeout=120)
    publish(root / 'deployment.json', canonical(p), replace=True)
    return {'deployment': p, 'app_started': True, 'runner_started': True, 'build_id': p.get('build_id'),
            'next': 'Run runner doctor against your staged case file to check authenticated benchmark readiness'}


def issue_credential(p):
    # Only public, checked-in code executes as operator. Existing app authority
    # selects the account/workspace; the host never exports browser credentials.
    code = '''import json,os,time
from pathlib import Path
from jiuwenswarm.research.evaluation_grants import open_operator_authority
root=Path('/run/ai4r-supervisor')
p=json.loads(Path('/var/lib/ai4r-accounts/sessions/reusable-bootstrap.json').read_bytes())['principal']
if isinstance(p,str):p=json.loads(p)
assert len(p['workspace_ids'])==1
target=root/('runner-'+str(time.time_ns()))
a=open_operator_authority()
try:
 result=a.issue_runner({'schema':'ai4r-runner-grant:1','account_id':p['account_id'],'workspace_id':p['workspace_ids'][0],'expires_in_s':86400},str(target))
 assert result['status']=='issued'
 # Transport secret bytes only through stdin/stdout pipes; never report them.
 print(json.dumps({'token':target.read_text(),'grant':result}))
finally:
 a.close();target.unlink(missing_ok=True)
'''
    response = json.loads(compose(p, 'exec', '-T', '--user', '0:0', 'ai4r',
                                 '/opt/venv/bin/python', '-c', code))
    volume = p['project'] + '_runner_credentials'
    docker(p, 'volume', 'create', '--label', 'ai4r.deployment=' + p['deployment_id'], volume)
    writer = '''import json,os,sys,uuid
from pathlib import Path
p=json.load(sys.stdin);root=Path('/operator');root.chmod(0o755)
t=root/('.token-'+uuid.uuid4().hex)
try:
 fd=os.open(t,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'wb') as f:
  f.write(p['token'].encode());f.flush();os.fsync(f.fileno());os.fchown(f.fileno(),p['uid'],p['gid'])
 os.replace(t,root/'token')
 fd=os.open(root,os.O_RDONLY);os.fsync(fd);os.close(fd)
finally:t.unlink(missing_ok=True)
'''
    docker(p, 'run', '--rm', '-i', '--network', 'none', '--read-only', '--user', '0:0',
        '--cap-drop', 'ALL', '--cap-add', 'CHOWN', '--cap-add', 'DAC_OVERRIDE', '--cap-add', 'FOWNER',
        '--security-opt', 'no-new-privileges', '--mount', 'type=volume,src=' + volume + ',dst=/operator',
        '--entrypoint', '/opt/venv/bin/python', p['app_image'], '-c', writer,
        data=canonical({'token': response['token'], 'uid': p['runner_uid'], 'gid': p['runner_gid']}))
    p['credential_ready'] = True
    p['credential_reference'] = {'volume': volume, 'path': '/run/benchmark-runner/token'}
    identity = json.loads(compose(p, 'exec', '-T', 'ai4r', 'cat', '/usr/local/share/ai4r-build-identity.json'))
    p['build_id'] = identity['build_id']
    p['grant'] = response['grant']
    # The render reads the original repo-supplied template, never private code.
    render(p, (Path(p['root']) / 'compose.source.yaml').read_text())


def mount_probe(p):
    config = json.loads((Path(p['root']) / 'compose.json').read_bytes())
    args = ['run', '--rm', '--network', 'none', '--read-only', '--user', str(p['runner_uid']) + ':' + str(p['runner_gid']),
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--entrypoint', 'python']
    for item in config['services']['benchmark-runner']['volumes']:
        source = checked(item['source']) if item['type'] == 'bind' else p['project'] + '_runner_credentials'
        if ',' in str(source): raise ValueError('Comma in bind path is unsupported by Docker --mount')
        args += ['--mount', 'type=' + item['type'] + ',src=' + str(source) + ',dst=' + item['target'] +
                 (',readonly' if item.get('read_only') else '')]
    probe = '''import os,pathlib,uuid
for root in ('/cases','/inputs'):
 p=pathlib.Path(root);assert p.is_dir() and os.access(p,os.R_OK|os.X_OK)
 assert os.statvfs(p).f_flag & os.ST_RDONLY
assert pathlib.Path('/run/benchmark-runner/token').is_file()
assert os.access('/run/benchmark-runner/token',os.R_OK)
p=pathlib.Path('/results')/('.probe-'+uuid.uuid4().hex)
try:
 with p.open('xb') as f:f.write(b'owned probe');f.flush();os.fsync(f.fileno())
 assert p.read_bytes()==b'owned probe'
finally:p.unlink(missing_ok=True)
'''
    try: docker(p, *args, p['runner_image'], '-c', probe)
    except ValueError:
        raise ValueError('Runner mount preflight failed: UID11001 needs readable case/input/token binds and a writable output bind') from None


def install_timer(p, source):
    """Install an immutable copy of repository code, not a private custom script."""
    digest_value = hashlib.sha256(source.encode()).hexdigest()
    installed = checked(Path.home() / '.local/lib/ai4r' / digest_value / 'operator_host.py')
    if not installed.exists(): publish(installed, source.encode(), mode=0o755)
    if digest(installed) != digest_value: raise ValueError('Installed repository helper bytes differ')
    directory = checked(Path.home() / '.config/systemd/user'); directory.mkdir(parents=True, exist_ok=True)
    name = p['project'] + '-expiry-' + p['deployment_id'][:8]
    def quote(value):
        if any(c in value for c in '\n\r%'): raise ValueError('Unsupported systemd path')
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
    command = ' '.join(map(quote, [sys.executable, str(installed), '--gc-profile', str(Path(p['root']) / 'deployment.json')]))
    service = '[Unit]\nDescription=AI4R owned temporary expiry\n[Service]\nType=oneshot\nExecStart=' + command + '\n'
    timer = '[Unit]\nDescription=Daily AI4R expiry\n[Timer]\nOnCalendar=daily\nPersistent=true\n[Install]\nWantedBy=timers.target\n'
    for suffix, text in [('service', service), ('timer', timer)]:
        target = directory / (name + '.' + suffix)
        if target.exists() and target.read_text() != text: raise ValueError('Existing timer definition differs; refusing overwrite')
        if not target.exists(): publish(target, text.encode(), mode=0o644)
    try:
        run(['systemctl', '--user', 'daemon-reload'])
        run(['systemctl', '--user', 'enable', '--now', name + '.timer'])
        return {'installed': True, 'timer': name, 'source_sha256': digest_value,
                'note': 'Unattended logout execution requires an available user manager/host-managed lingering'}
    except (OSError, ValueError):
        return {'installed': False, 'reason': 'systemd user manager unavailable; use gc manually or install a workstation schedule',
                'source_sha256': digest_value}


def rpc_main():
    request = json.load(sys.stdin)
    try:
        result = dispatch(request)
        print(json.dumps({'ok': True, 'result': result}, allow_nan=False))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        # Exceptions can contain credential material from tool output. Fixed
        # diagnostic categories plus explicit doctor/logs avoid accidental leaks.
        exc = sys.exc_info()[1]
        message = str(exc) if isinstance(exc, ValueError) else type(exc).__name__ + ': host prerequisite or filesystem operation failed'
        print(json.dumps({'ok': False, 'error': message}))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--gc-profile':
        profile = json.loads(checked(sys.argv[2]).read_bytes())
        try: print(json.dumps(dispatch({'action': 'gc', 'profile': profile})))
        except (OSError, ValueError):
            print('Expiry deferred: deployment busy, unavailable or unresolved', file=sys.stderr); sys.exit(2)
    else:
        rpc_main()
