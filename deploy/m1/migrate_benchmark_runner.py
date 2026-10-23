"""Guarded transition of the existing 5175 installation to the two service roles.

Windows operator helper. Reuses the installed local operator's metadata-only
capture and zero-active-run/lease guards. It never reads external task or answer
files and never deletes Docker volumes or output directories.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import time
import uuid


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'activate', 'finish'])
    parser.add_argument('--image')
    parser.add_argument('--runner-image')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--cases', help='Explicit canonical Docker-host cases directory')
    parser.add_argument('--inputs', help='Explicit canonical Docker-host inputs directory')
    parser.add_argument('--output', help='Explicit canonical existing Docker-host output directory')
    parser.add_argument('--remove-both', action='store_true', help='Remove both idle owned containers before recreation; never remove volumes')
    parser.add_argument('--runtime', type=Path, default=Path(os.environ.get('LOCALAPPDATA', '')) / 'AI4Research/runtime')
    args = parser.parse_args(argv)
    runtime = args.runtime.resolve(strict=True)
    spec = importlib.util.spec_from_file_location('retained_ai4r_operator', runtime / 'poc-clean-isolation.py')
    operator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(operator)
    ops, project = operator.ops, operator.PROJECT
    prior = json.loads(operator.ACTIVE.read_bytes())
    old = json.loads(ops.wsl('cat', '--', prior['compose']))
    old_role = 'ai4r' if 'ai4r' in old['services'] else 'app'
    old_container = project + '-' + old_role + '-1'
    old_service = old['services'][old_role]
    expected_volumes = {name: {'name': project + '_' + name} for name in ops.VOLUMES}
    if old['name'] != project or old['volumes'] != expected_volumes:
        raise ValueError('EXACT_EXISTING_PROJECT_VOLUMES_REQUIRED')

    def guard(stopped=False):
        current = json.loads(ops.docker('inspect', old_container))[0]
        if current['Config']['Labels']['com.docker.compose.project'] != project:
            raise ValueError('FOREIGN_CONTAINER')
        if current['State']['Running']:
            return operator.guard(old_container)
        result = json.loads(ops.docker('run', '--rm', '--pull', 'never', '--network', 'none', '--read-only',
            '--user', '0:0', '--cap-drop', 'ALL', '--cap-add', 'DAC_OVERRIDE',
            '--mount', 'type=volume,source=' + project + '_state,target=/var/lib/ai4r,readonly',
            '--mount', 'type=volume,source=' + project + '_executor,target=/var/lib/ai4r-executor,readonly',
            '--entrypoint', '/opt/venv/bin/python', old_service['image'], '-c', operator.STOPPED_GUARD))
        if result != {'active_runs': 0, 'unreleased_leases': 0}:
            raise ValueError('ACTIVE_EXECUTION_REFUSES_MIGRATION')
        return result

    if args.command == 'prepare':
        if not args.image or not args.runner_image:
            parser.error('prepare requires --image and --runner-image')
        guard()
        image = json.loads(ops.docker('image', 'inspect', args.image))[0]['Id']
        runner = json.loads(ops.docker('image', 'inspect', args.runner_image))[0]['Id']
        build = json.loads(ops.docker('run', '--rm', '--pull', 'never', '--network', 'none', '--read-only',
            '--entrypoint', '/opt/venv/bin/python', image, '-c',
            "from pathlib import Path;print(Path('/usr/local/share/ai4r-build-identity.json').read_text())"))
        if any(row['path'].startswith('research_sidecar/') for row in build['files']):
            raise ValueError('RUNNER_MODULES_IN_APP_IMAGE')
        fresh = operator.PARENT + 'two-images-' + uuid.uuid4().hex
        ops.wsl('mkdir', '--mode=0700', fresh)
        service = copy.deepcopy(old_service)
        service['image'] = image
        package = '/opt/venv/lib/python3.12/site-packages/jiuwenswarm/'
        service['volumes'] = [mount for mount in service['volumes'] if not isinstance(mount, dict)
            or not (mount['target'].startswith(package)
                    or mount['target'] == '/usr/local/share/ai4r-build-identity.json'
                    or mount['target'].startswith('/opt/ai4r-paper-dev/')
                    or mount['target'] == '/run/benchmark-runner-operator')]
        service.setdefault('labels', {})['ai4r.component'] = 'ai4r'
        directory = '/var/lib/ai4r/operator/two-images-' + uuid.uuid4().hex
        previous_bootstrap = service['environment']['JIUWENSWARM_M1_BOOTSTRAP_BINDINGS']
        for key, name in [('JIUWENSWARM_M1_CONFIG', 'config.json'),
                          ('JIUWENSWARM_M1_BOOTSTRAP_BINDINGS', 'bootstrap.json'),
                          ('JIUWENSWARM_M1_SCIENCE_BINDINGS', 'science.json')]:
            if key in service['environment']:
                service['environment'][key] = directory + '/' + name
        runner_service = {'image': runner, 'init': True, 'user': '11001:11001', 'read_only': True,
            'pids_limit': 128, 'mem_limit': '2g',
            'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true'],
            'entrypoint': ['python', '-c', 'import signal; signal.pause()'],
            'networks': copy.deepcopy(service['networks']),
            'tmpfs': ['/tmp:rw,nosuid,nodev,size=128m,uid=11001,gid=11001'],
            'labels': {'ai4r.owner': project, 'ai4r.component': 'benchmark-runner'}}
        paths = {name: getattr(args, name) for name in ('cases', 'inputs', 'output')}
        if not all(paths.values()):
            parser.error('prepare requires explicit --cases, --inputs and --output Docker-host paths')
        from pathlib import PurePosixPath
        roots = [PurePosixPath(path) for path in paths.values()]
        if any(not path.is_absolute() or '..' in path.parts for path in roots):
            raise ValueError('ABSOLUTE_CANONICAL_HOST_PATHS_REQUIRED')
        if any(first.is_relative_to(second) or second.is_relative_to(first)
               for index, first in enumerate(roots) for second in roots[index + 1:]):
            raise ValueError('CONFLICTING_MOUNT_ROOTS')
        # Validate daemon resolution and real UID access before stopping or
        # changing the app, including an exclusive output fsync probe.
        from benchmark_runner_host import PROBE
        probe = ['run', '--rm', '--pull', 'never', '--network', 'none', '--read-only',
                 '--user', '11001:11001', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                 '--env', 'AI4R_PROBE_DATA_ONLY=1', '--entrypoint', 'python']
        for name, target in [('cases', '/mnt/cases'), ('inputs', '/mnt/inputs'), ('output', '/mnt/results')]:
            if ops.wsl('readlink', '-e', '--', paths[name]).decode().strip() != paths[name]:
                raise ValueError('CANONICAL_DOCKER_HOST_PATH_REQUIRED:' + name)
            probe += ['--mount', 'type=bind,src=' + paths[name] + ',dst=' + target + (',readonly' if name != 'output' else '')]
        ops.docker(*probe, runner, '-c', PROBE)
        credentials = fresh + '/runner-credentials'
        ops.wsl('mkdir', '--mode=0700', credentials)
        service['volumes'].append({'type': 'bind', 'source': credentials,
            'target': '/run/benchmark-runner-operator', 'bind': {'create_host_path': False}})
        runner_service['environment'] = {'AI4R_ENDPOINT': 'http://ai4r:5173',
            'AI4R_TOKEN_FILE': '/run/benchmark-runner/token', 'AI4R_EXPECTED_BUILD': build['build_id'],
            'AI4R_HTTP_AUTHORITY': '127.0.0.1:5175'}
        runner_service['volumes'] = []
        for name, target in [('cases', '/cases'), ('inputs', '/inputs'), ('output', '/results')]:
            runner_service['volumes'].append({'type': 'bind', 'source': paths[name], 'target': target,
                'read_only': name != 'output', 'bind': {'create_host_path': False}})
        runner_service['volumes'].append({'type': 'bind', 'source': credentials + '/runner-token',
            'target': '/run/benchmark-runner/token', 'read_only': True, 'bind': {'create_host_path': False}})
        compose = copy.deepcopy(old)
        compose['services'] = {'ai4r': service, 'benchmark-runner': runner_service}
        compose_path = fresh + '/compose.json'
        raw = json.dumps(compose, separators=(',', ':')).encode()
        ops.write_new(compose_path, raw)
        script = fresh + '/prepare-executor.sh'
        ops.write_new(script, ops.wsl('cat', '--', prior['cgroup_script']))
        capture_raw = (runtime / 'poc-clean-capture.py').read_bytes()
        capture_path = fresh + '/capture.py'
        ops.write_new(capture_path, capture_raw)
        manifest = dict(prior, compose=compose_path, patch_root=fresh,
            build_id=build['build_id'], image_id=image, runner_image_id=runner,
            cgroup_script=script, operator_directory=directory,
            previous_bootstrap=previous_bootstrap, prepared_from_compose=prior['compose'],
            files=[], migration='existing-project-two-images', app_service='ai4r',
            compose_sha256=hashlib.sha256(raw).hexdigest(),
            capture_path=capture_path, capture_sha256=hashlib.sha256(capture_raw).hexdigest())
        manifest['runner_paths'] = paths
        manifest['runner_credential'] = credentials + '/runner-token'
        destination = runtime / ('ai4r-two-images-prepared-' + Path(fresh).name + '.json')
        with destination.open('x', encoding='utf8') as stream:
            json.dump(manifest, stream, separators=(',', ':'))
        print(json.dumps({'status': 'prepared_not_started', 'manifest': str(destination),
                          'build_id': build['build_id'], 'model_calls': 0}))
        return 0

    if not args.manifest:
        parser.error('activate requires --manifest')
    manifest = json.loads(args.manifest.read_bytes())
    if (manifest['migration'] != 'existing-project-two-images'
            or manifest['project'] != project or (manifest['prepared_from_compose'] != prior['compose'] and manifest['compose'] != prior['compose'])):
        raise ValueError('STALE_OR_FOREIGN_MIGRATION')
    raw = ops.wsl('cat', '--', manifest['compose'])
    capture = ops.wsl('cat', '--', manifest['capture_path'])
    if (hashlib.sha256(raw).hexdigest() != manifest['compose_sha256']
            or hashlib.sha256(capture).hexdigest() != manifest['capture_sha256']):
        raise ValueError('IMMUTABLE_MIGRATION_INPUT_CHANGED')
    compose = json.loads(raw)
    if compose['volumes'] != expected_volumes or set(compose['services']) != {'ai4r', 'benchmark-runner'}:
        raise ValueError('MIGRATION_SERVICE_OR_VOLUME_MISMATCH')
    if args.command == 'finish':
        current = json.loads(ops.docker('inspect', project + '-ai4r-1'))[0]
        if not current['State']['Running'] or current['Config']['Image'] != manifest['image_id']:
            raise ValueError('EXACT_STARTED_NEW_APP_REQUIRED')
        expected = {project + '_' + key for key in ops.VOLUMES}
        if {mount.get('Name') for mount in current['Mounts'] if mount['Type'] == 'volume'} != expected:
            raise ValueError('EXACT_RETAINED_VOLUMES_REQUIRED')
        return _finish_activation(ops, operator, project, manifest, ('compose', '-p', project, '-f', manifest['compose']))
    guard()
    if args.remove_both:
        idle = """import psutil
for process in psutil.process_iter(['cmdline']):
 args=process.info['cmdline'] or []
 assert not ('benchmark-runner' in ' '.join(args) and any(value in args for value in ('run','resume'))),'RUNNER_CAMPAIGN_ACTIVE'
"""
        runner_name = project + '-benchmark-runner-1'
        observed = json.loads(ops.docker('inspect', runner_name))[0]
        if observed['Config']['Labels']['com.docker.compose.project'] != project:
            raise ValueError('FOREIGN_RUNNER_CONTAINER')
        if observed['State']['Running']:
            ops.docker('exec', runner_name, 'python', '-c', idle)
            ops.docker('stop', '--time', '10', runner_name)
        ops.docker('rm', runner_name)
    current = json.loads(ops.docker('inspect', old_container))[0]
    if current['State']['Running']:
        ops.docker('stop', '--time', '45', old_container)
    guard(stopped=True)
    ops.wsl('bash', manifest['cgroup_script'])
    base = ('compose', '-p', project, '-f', manifest['compose'])
    # Capture preserves previous imported resource/scoring references and reads
    # metadata only. No model calls, task replay, source patching or answer reads.
    ops.docker(*base, 'run', '--rm', '--no-deps', '--pull', 'never', '-T', '--user', '10001:10001',
        '--env', 'AI4R_PREVIOUS_BOOTSTRAP=' + manifest['previous_bootstrap'],
        '--entrypoint', '/opt/venv/bin/python', 'ai4r', '-c', capture.decode('utf8'))
    science = manifest['operator_directory'] + '/science.json'
    protect = """import os,stat,json
from pathlib import Path
p=Path(SCIENCE)
if p.exists():
 m=p.lstat();assert stat.S_ISREG(m.st_mode) and not p.is_symlink() and m.st_uid==10001 and m.st_nlink==1
 assert set(json.loads(p.read_bytes()))=={'binding_ref'};os.chown(p,0,0);os.chmod(p,0o600)
""".replace('SCIENCE', repr(science))
    ops.docker(*base, 'run', '--rm', '--no-deps', '--pull', 'never', '-T', '--user', '0:0',
        '--entrypoint', '/opt/venv/bin/python', 'ai4r', '-c', protect)
    guard(stopped=True)
    # Remove only the old, stopped app container. Its six volumes are retained.
    ops.docker('rm', old_container)
    ops.docker(*base, 'up', '-d', '--no-build', '--pull', 'never', 'ai4r')
    return _finish_activation(ops, operator, project, manifest, base)


def _publish_active(operator, manifest):
    temporary = operator.ACTIVE.with_name(operator.ACTIVE.name + '.two-images-' + uuid.uuid4().hex)
    with temporary.open('x', encoding='utf8') as stream:
        json.dump(manifest, stream, separators=(',', ':'))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, operator.ACTIVE)


def _finish_activation(ops, operator, project, manifest, base):
    manifest['runner_grant_pending'] = True
    _publish_active(operator, manifest)
    # Native startup renews its family; issue the finite runner grant only after
    # that initialization, never copy a broad browser/settings credential.
    new_container = project + '-ai4r-1'
    startup_check = """from pathlib import Path
import httpx
assert Path('/run/ai4r/model.sock').is_socket()
token=Path('/var/lib/ai4r-accounts/sessions/session-token').read_text().strip()
response=httpx.get('http://127.0.0.1:5173/api/v1/readiness',headers={'Authorization':'Bearer '+token,'Host':'127.0.0.1:5175'},timeout=3)
assert response.status_code==200 and response.json()['build_id']==EXPECTED
""".replace('EXPECTED', repr(manifest['build_id']))
    initialized = False
    for attempt in range(60):
        try:
            ops.docker('exec', '--user', '0:0', new_container, '/opt/venv/bin/python', '-c',
                startup_check)
            initialized = True
            break
        except ops.OperationError:
            time.sleep(1)
    if not initialized:
        raise ValueError('APP_STARTUP_INCOMPLETE_RUNNER_GRANT_NOT_ISSUED')
    binding_code = """import json,os
from pathlib import Path
p=json.loads(Path('/var/lib/ai4r-accounts/sessions/reusable-bootstrap.json').read_bytes())['principal']
if isinstance(p,str):p=json.loads(p)
assert len(p['workspace_ids'])==1
binding={'schema':'ai4r-runner-grant:1','account_id':p['account_id'],'workspace_id':p['workspace_ids'][0],'expires_in_s':86400}
target=Path('/run/benchmark-runner-operator/binding.json')
if target.exists():
 assert json.loads(target.read_bytes())==binding
else:
 with target.open('x') as stream:json.dump(binding,stream);stream.flush();os.fsync(stream.fileno())
target.chmod(0o600)
"""
    ops.docker('exec', '--user', '0:0', new_container, '/opt/venv/bin/python', '-c', binding_code)
    grant = json.loads(ops.docker('exec', '--user', '0:0', new_container, '/opt/venv/bin/python',
        '-m', 'jiuwenswarm.research.runner_grants', 'issue',
        '--binding-file', '/run/benchmark-runner-operator/binding.json',
        '--output', '/run/benchmark-runner-operator/runner-token'))
    if grant.get('status') != 'issued':
        raise ValueError('SCOPED_RUNNER_GRANT_UNAVAILABLE')
    manifest['runner_grant'] = grant
    manifest['runner_grant_pending'] = False
    ops.docker(*base, 'up', '-d', '--no-build', '--pull', 'never', 'benchmark-runner')
    _publish_active(operator, manifest)
    print(json.dumps({'status': 'started', 'project': project, 'build_id': manifest['build_id'],
                      'origin': 'http://127.0.0.1:5175', 'same_volumes': True, 'model_calls': 0,
                      'runner_mounts_configured': True}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
