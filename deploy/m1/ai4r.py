"""Build, deploy and operate AI4R locally or over SSH. Host dependencies: Python3,
Docker/Compose/Buildx; SSH/SCP for remote targets. No application imports.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid

import operator_host as host

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_PROFILE = Path.home() / '.local/share/ai4r/operator.json'
SSH_OPTIONS = ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
               '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3']
# Fixed command: source and request travel on stdin, never interpolated into a
# remote shell command or imported from a workstation's private runtime folder.
REMOTE = "import sys,json; e=json.load(sys.stdin); n={'__name__':'ai4r_rpc'};exec(compile(e['source'],'<repository-ai4r-host>','exec'),n);\ntry: print(json.dumps({'ok':True,'result':n['dispatch'](e['request'])}))\nexcept Exception as x: print(json.dumps({'ok':False,'error':str(x) if isinstance(x,ValueError) else type(x).__name__+': host operation failed'}))"


def host_source():
    helper = (HERE / 'local_model_operator.py').read_text(encoding='utf-8')
    spark_helper = (HERE / 'spark_model_operator.py').read_text(encoding='utf-8')
    source = (HERE / 'operator_host.py').read_text(encoding='utf-8')
    # Keep future imports first; host RPC needs no separately installed module.
    marker = 'from __future__ import annotations'
    return source.replace(marker, marker + '\nLOCAL_MODEL_OPERATOR_SOURCE = ' + repr(helper)
        + '\nSPARK_MODEL_OPERATOR_SOURCE = ' + repr(spark_helper)
        + '\nSPARK_POOL_SELECTION = ' + repr(json.loads((HERE/'spark-pool-v2.json').read_text(encoding='utf-8')))
        + '\nSPARK_POOL_SELECTION_V3 = ' + repr(json.loads((HERE/'spark-pool-v3.json').read_text(encoding='utf-8'))), 1)


def load(path):
    if not Path(path).exists():
        raise ValueError('Operator profile not found; run setup first (use --profile PATH before the command)')
    data = json.loads(host.checked(path).read_bytes())
    if data.get('schema') != 'ai4r-operator:1':
        raise ValueError('Unsupported operator profile; run setup with a new --profile path')
    return data


def save(path, value):
    host.publish(path, host.canonical(value), replace=Path(path).exists())


def docker_prefix(config, *, build=False):
    distro = config.get('build_wsl_distro') if build else config.get('wsl_distro')
    context = config.get('build_context') if build else config.get('docker_context')
    if distro:
        return ['wsl.exe', '-d', distro, '--exec', 'docker']
    return ['docker'] + (['--context', context] if context else [])


class Transport:
    def __init__(self, config):
        self.config = config

    def request(self, action, **values):
        request = {'action': action, 'profile': self.config['deployment'], **values}
        if not self.config.get('ssh') and not self.config.get('wsl_distro'):
            return host.dispatch(request)
        code = host_source()
        envelope = host.canonical({'source': code, 'request': request})
        if self.config.get('ssh'):
            args = [self.config.get('ssh_executable') or 'ssh', *SSH_OPTIONS, self.config['ssh'], 'python3 -c ' + shlex.quote(REMOTE)]
        else:
            args = ['wsl.exe', '-d', self.config['wsl_distro'], '--exec', 'python3', '-c', REMOTE]
        result = subprocess.run(args, input=envelope, stdout=subprocess.PIPE, stderr=sys.stderr)
        if result.returncode:
            raise ValueError('Host connection failed; check SSH trust/access or the selected WSL distribution')
        try:
            response = json.loads(result.stdout)
        except ValueError:
            raise ValueError('Host did not return the repository operator protocol') from None
        if not response['ok']:
            raise ValueError(response['error'])
        return response['result']

    def transfer(self, source, *, kind, name='', image=None):
        info = host.file_info(source)
        if kind != 'image' and self.request('file-check', kind=kind, path=name, info=info)['matches']:
            return {'skipped': True}
        folder = self.request('begin-transfer', size=info['size'])['id']
        copied = False
        if self.config.get('ssh') and self.config.get('scp_executable', True) is not False:
            target = str(Path(self.config['deployment']['root']) / 'temporary' / folder / 'payload').replace('\\', '/')
            # Force SFTP: remote paths are data, never evaluated by a shell.
            result = subprocess.run([self.config.get('scp_executable') or 'scp', '-s', *SSH_OPTIONS, '--', str(source), self.config['ssh'] + ':' + target],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            copied = result.returncode == 0
            if not copied:
                # Keep the failed attempt for diagnosis. A fresh transfer avoids
                # appending to bytes whose offset/custody we cannot establish.
                folder = self.request('begin-transfer', size=info['size'])['id']
        if not copied:
            with source.open('rb') as stream:
                offset = 0
                while block := stream.read(host.CHUNK):
                    self.request('put', id=folder, offset=offset, data=base64.b64encode(block).decode())
                    offset += len(block)
                if offset == 0:
                    self.request('put', id=folder, offset=0, data='')
        extra = {'image_id': image['image_id'], 'unpacked_bytes': image['unpacked_bytes']} if image else {}
        return self.request('publish-transfer', id=folder, kind=kind, path=name, info=info, **extra)


def setup(args):
    # Relative paths are convenient locally; remote/WSL paths belong to that
    # host and must never be resolved as workstation paths.
    if not args.ssh and not args.wsl_distro:
        for key in ('root', 'output'):
            value = getattr(args, key)
            if value is not None:
                setattr(args, key, str(host.checked(Path(value).expanduser())))
    path = args.profile
    if path.exists():
        config = load(path)
        # Do not quietly accept requested changes that a repeat cannot apply.
        supplied = {'ssh': args.ssh, 'wsl_distro': args.wsl_distro, 'docker_context': args.docker_context}
        if any(value is not None and config.get(key) != value for key, value in supplied.items()):
            raise ValueError('Existing profile has a different target; use another --profile')
        for key, supplied_value in (('root', args.root), ('output', args.output), ('platform', args.platform), ('project', args.project)):
            if supplied_value is not None and config['deployment'].get(key) != supplied_value:
                raise ValueError('Repeated setup cannot change ' + key)
        if args.ttl_days is not None and config['deployment']['ttl_days'] != args.ttl_days:
            raise ValueError('Existing TTL differs; edit the operator profile explicitly before reconfiguring')
        transport = Transport(config)
        config['deployment'] = transport.request('setup', seccomp=(HERE / 'seccomp/executor.json').read_text())
        save(path, config)
        try: expiry = transport.request('gc')
        except ValueError: expiry = {'skipped': 'Deployment busy or execution unresolved; data retained'}
        return {'profile': str(path), 'preserved': True, 'expiry': expiry, 'next': 'doctor, build, stage, start'}
    project = args.project or 'ai4r-bench'
    if args.ssh and (args.ssh.startswith('-') or not re.fullmatch(r'[A-Za-z0-9_.@-]+', args.ssh)):
        raise ValueError('Use an SSH config alias or user@host; configure port/key in ~/.ssh/config')
    if args.ssh and args.wsl_distro:
        raise ValueError('Select SSH or WSL, not both')
    arch = args.platform or ('linux/arm64' if args.ssh or platform.machine().lower() in {'arm64', 'aarch64'} else 'linux/amd64')
    config = {'schema': 'ai4r-operator:1', 'ssh': args.ssh, 'wsl_distro': args.wsl_distro,
        'docker_context': args.docker_context, 'build_context': args.build_context,
        'build_wsl_distro': args.build_wsl_distro or args.wsl_distro,
        'deployment': {'project': project, 'root': args.root, 'output': args.output,
                       'platform': arch, 'docker_context': args.docker_context, 'ttl_days': args.ttl_days or 7},
        'builds': {}}
    path.parent.mkdir(parents=True, exist_ok=True)
    config['deployment'] = Transport(config).request('setup', seccomp=(HERE / 'seccomp/executor.json').read_text())
    save(path, config)
    maintenance = install_maintenance(path, config)
    return {'profile': str(path), 'deployment': config['deployment'], 'maintenance': maintenance,
            'next': 'Run doctor, build, stage and start. Start explains the human authentication step.'}


def build(config, args):
    validate_release_checkout()
    target = config['deployment']; output = args.output.resolve()
    if output.exists():
        raise ValueError('Build output must be a fresh directory')
    host.capacity(output.parent)
    # Expiry is best effort only when there are no unresolved campaigns; a
    # failed storage check is never ignored.
    try: Transport(config).request('gc')
    except ValueError:
        print('Target expiry deferred while execution is unresolved; this independent build can continue.', file=sys.stderr)
    local_gc(config)
    output.mkdir(mode=0o700)
    docker = docker_prefix(config, build=True)
    builder = target['project'] + '-builder'
    inspected = subprocess.run(docker + ['buildx', 'inspect', builder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if inspected.returncode:
        host.run(docker + ['buildx', 'create', '--name', builder, '--driver', 'docker-container',
                          '--buildkitd-flags', '--oci-worker-gc --oci-worker-gc-keepstorage 10000'])
    commit = host.run(['git', '-C', str(REPO), 'rev-parse', 'HEAD']).decode().strip()
    # Hash exact public build input bytes, including dirty/untracked source;
    # source snapshot creation follows each Dockerfile's deny-by-default ignore.
    tree = hashlib.sha256()
    for rel in ('pyproject.toml', 'uv.lock'):
        tree.update(rel.encode()); tree.update((REPO / rel).read_bytes())
    dirty = host.run(['git', '-C', str(REPO), 'status', '--porcelain', '--untracked-files=normal']).decode()
    receipt = {'schema': 'ai4r-build:1', 'commit': commit, 'dirty': bool(dirty),
        'working_tree_status_sha256': hashlib.sha256(dirty.encode()).hexdigest(),
        'dependency_files_sha256': tree.hexdigest(), 'platform': target['platform'], 'images': {}}
    for role, filename, stage in [('ai4r', 'Dockerfile.app', 'production'),
                                  ('benchmark-runner', 'Dockerfile.sidecar', 'benchmark-runner')]:
        tag = role + ':' + uuid.uuid4().hex
        context = output / (role + '-context')
        context.mkdir()
        record = {'owner': host.OWNER, 'project': target['project'], 'kind': 'build-context',
                  'status': 'incomplete', 'created_at': time.time()}
        host.publish(context / 'temporary.json', host.canonical(record))
        config.setdefault('local_temporary', []).append(str(context))
        save(args.profile, config)
        files = freeze_context(role, context / 'source.tar')
        command = docker + ['buildx', 'build', '--builder', builder, '--platform', target['platform'],
            '--file', 'deploy/m1/' + filename, '--target', stage, '--tag', tag, '--load',
            '--label', 'ai4r.owner=' + target['project'], '--label', 'ai4r.deployment=' + target['deployment_id'], '-']
        with (context / 'source.tar').open('rb') as source:
            process = subprocess.Popen(command, stdin=source)
            try:
                while process.poll() is None:
                    host.capacity(output)
                    time.sleep(2)
                if process.returncode:
                    raise ValueError('Image build failed; context/receipt staging retained for diagnosis')
            except BaseException:
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired: process.kill(); process.wait()
                raise
        image = json.loads(host.run(docker + ['image', 'inspect', tag]))[0]
        if 'linux/' + image['Architecture'] != target['platform']:
            raise ValueError('Builder returned the wrong platform')
        receipt['images'][role] = {'image_id': image['Id'], 'tag': tag, 'unpacked_bytes': image['Size'],
            'context_sha256': host.digest(context / 'source.tar'), 'source_files': files}
        host.finish_temporary(context)
    host.publish(output / 'receipt.json', host.canonical(receipt))
    config['builds'] = receipt
    for role, key in [('ai4r', 'app_image'), ('benchmark-runner', 'runner_image')]:
        target[key] = receipt['images'][role]['image_id']
    return {'receipt': str(output / 'receipt.json'), **receipt}


def validate_release_checkout():
    """Fail before building if a checkout violates its explicit release EOLs."""
    raw = host.run(['git', '-C', str(REPO), 'ls-files', '--eol', '-z', '--',
        'jiuwenswarm/research', 'jiuwenswarm/research_assets', 'jiuwenswarm/research_contracts'])
    invalid = []
    for entry in raw.decode('utf-8').split('\0'):
        if not entry:
            continue
        header, name = entry.split('\t', 1)
        desired = re.search(r'eol=(lf|crlf)', header)
        working = re.search(r'w/(lf|crlf|mixed|none)', header)
        if desired and working and working[1] not in {desired[1], 'none'}:
            invalid.append(name)
    if invalid:
        raise ValueError('Release source checkout violates .gitattributes; restore the declared line endings before building: '
            + ', '.join(invalid[:8]))


def freeze_context(role, destination):
    """Freeze only public production inputs; never archive arbitrary repo state."""
    roots = ['pyproject.toml', 'uv.lock', 'LICENSE', 'OPEN_SOURCE_SOFTWARE_NOTICE.md',
             'jiuwenswarm', 'jiuwenbox', 'packages/jiuwenswarm-tui', 'scripts', 'deploy/m1']
    if role == 'benchmark-runner':
        roots = ['uv.lock', 'jiuwenswarm/research_sidecar', 'jiuwenswarm/research_records',
                 'jiuwenswarm/research_contracts', 'jiuwenswarm/research_router', 'deploy/m1']
    denied = {'.git', '.venv', '__pycache__', 'node_modules', 'dist', 'private', 'protected', 'evidence', '.ai4r'}
    inventory = []
    with tarfile.open(destination, 'x') as archive:
        for name in roots:
            start = REPO / name
            paths = [start] if start.is_file() else []
            for parent, dirs, names in os.walk(start, followlinks=False):
                for directory in dirs:
                    host.checked(Path(parent) / directory)
                dirs[:] = [d for d in dirs if d not in denied and not (role == 'ai4r' and d == 'research_sidecar')]
                paths.extend(Path(parent) / n for n in sorted(names))
            for path in sorted(paths):
                if (path.name.startswith('.env') and path.name != '.env.template'
                        or path.name in {'auth.json', 'credentials.json', 'secrets.json'}
                        or path.suffix in {'.key', '.pem', '.p12', '.pyc'}):
                    continue
                host.checked(path)
                if not path.is_file() or path.stat().st_nlink != 1:
                    raise ValueError('Nonregular public build input')
                relative = path.relative_to(REPO).as_posix()
                # Read once: the inventory identifies exactly the frozen bytes,
                # even if another developer edits the checkout during a build.
                data = path.read_bytes()
                import io
                member = tarfile.TarInfo(relative); member.size = len(data)
                member.mode = 0o755 if path.suffix == '.sh' else 0o644
                archive.addfile(member, io.BytesIO(data))
                inventory.append({'path': relative, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    return inventory


def selected_files(case, inputs):
    case = host.checked(case).resolve(strict=True); inputs = host.checked(inputs).resolve(strict=True)
    if case.suffix.lower() not in {'.json', '.yaml', '.yml'} or not case.is_file() or not inputs.is_dir():
        raise ValueError('Choose a case JSON/YAML file and an explicit input directory')
    if inputs == REPO or REPO.is_relative_to(inputs):
        raise ValueError('An entire checkout is not a campaign input directory')
    rows = [('cases', case.name, case)]
    for path in sorted(inputs.rglob('*')):
        host.checked(path)
        if path.is_file():
            if path.name in {'.env', 'auth.json', 'credentials.json', 'secrets.json'} or path.suffix in {'.pem', '.key', '.p12'}:
                raise ValueError('Credential-like file in selected input root; choose only permitted benchmark inputs')
            host.file_info(path)
            rows.append(('inputs', path.relative_to(inputs).as_posix(), path))
    manifest = [{'kind': kind, 'path': name, **host.file_info(path)} for kind, name, path in rows]
    return rows, hashlib.sha256(host.canonical(manifest)).hexdigest()


def select_images(config, app_image, runner_image):
    """Use already-built/loaded images; do not claim their source was rebuilt."""
    selected = {}
    for role, reference in [('ai4r', app_image), ('benchmark-runner', runner_image)]:
        if not isinstance(reference, str) or not reference.strip() or reference.startswith('-'):
            raise ValueError('Supply a Docker image name or immutable ID for ' + role)
        image = json.loads(host.run(docker_prefix(config, build=True) + ['image', 'inspect', reference]))[0]
        if ('linux/' + image['Architecture'] != config['deployment']['platform']
                or image.get('Os', 'linux') != 'linux'):
            raise ValueError('Selected ' + role + ' image does not match the deployment platform')
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', image['Id']) or type(image['Size']) is not int or image['Size'] < 0:
            raise ValueError('Docker returned an invalid image identity')
        selected[role] = {'image_id': image['Id'], 'tag': reference, 'unpacked_bytes': image['Size'],
            'source_revision': (image.get('Config', {}).get('Labels') or {}).get('org.opencontainers.image.revision')}
    config['builds'] = {'schema': 'ai4r-build:1', 'platform': config['deployment']['platform'],
        'provenance': 'existing Docker images; source build not performed', 'images': selected}
    for role, key in [('ai4r', 'app_image'), ('benchmark-runner', 'runner_image')]:
        config['deployment'][key] = selected[role]['image_id']


def stage_selection(config, args):
    if args.receipt and (args.app_image or args.runner_image):
        raise ValueError('Select a build receipt or an image pair, not both')
    if bool(args.app_image) != bool(args.runner_image):
        raise ValueError('Supply both --app-image and --runner-image')
    if args.receipt:
        receipt = json.loads(args.receipt.read_bytes())
        if receipt['schema'] != 'ai4r-build:1' or receipt['platform'] != config['deployment']['platform']:
            raise ValueError('Build receipt differs from the target platform')
        if set(receipt['images']) != {'ai4r', 'benchmark-runner'}:
            raise ValueError('Build receipt must contain the app and runner images')
        config['builds'] = receipt
        for role, key in [('ai4r', 'app_image'), ('benchmark-runner', 'runner_image')]:
            config['deployment'][key] = receipt['images'][role]['image_id']
    elif args.app_image:
        select_images(config, args.app_image, args.runner_image)
    return stage(config, args)


def up(args):
    """One local/SSH entry point using existing images; never build implicitly."""
    if args.ttl_days is not None and args.ttl_days < 1:
        raise ValueError('TTL must be at least one day')
    setup(args)
    config = load(args.profile)
    if not config.get('builds', {}).get('images') and not (args.receipt or args.app_image or args.runner_image):
        args.app_image, args.runner_image = 'ai4r:local', 'benchmark-runner:local'
    try:
        staged = stage_selection(config, args)
        result = Transport(config).request('start', refresh_credential=args.refresh_credential,
            template=(HERE / 'compose.benchmark-runner.yaml').read_text())
        config['deployment'] = result.pop('deployment')
        return {'profile': str(args.profile), 'compose_file': str(Path(config['deployment']['root']) / 'compose.json'), 'stage': staged, **result,
            'host_setup': 'No sudo, host cgroup preparation or service installation; app execution prerequisites remain enforced'}
    finally:
        # Retain exact selected image/input identities if startup needs login
        # or fails. A retry resumes this deployment rather than losing staging.
        save(args.profile, config)


def stage(config, args):
    transport = Transport(config)
    if not config.get('builds', {}).get('images'):
        raise ValueError('Run build first, or stage with --receipt from a completed build')
    docker = docker_prefix(config, build=True)
    for role, image in config['builds']['images'].items():
        if transport.request('image-check', image_id=image['image_id'])['matches']:
            continue
        # Archives are transient, not additional permanent image histories.
        with tempfile.TemporaryDirectory(prefix='ai4r-image-') as tmp:
            host.capacity(tmp, image['unpacked_bytes'] * 2)
            archive = Path(tmp) / 'image.tar'
            with archive.open('xb') as stream:
                subprocess.run(docker + ['save', image['image_id']], stdout=stream, check=True)
            transport.transfer(archive, kind='image', image=image)
    rows, identity = selected_files(args.cases, args.inputs)
    for kind, name, path in rows:
        transport.transfer(path, kind=kind, name=identity + '/' + name)
    config['deployment']['input_stage'] = identity
    config['case_file'] = '/cases/' + identity + '/' + args.cases.name
    config['deployment'] = transport.request('configure')['deployment']
    return {'stage': identity, 'case_file': config['case_file'], 'files': len(rows),
            'note': 'Only the selected case file/input root transferred; task submission remains runner-owned'}


def fetch(config, args):
    destination = host.checked(args.output)
    if destination.exists():
        raise ValueError('Fetch destination must be new; existing user files are never overwritten')
    transport = Transport(config)
    if not host.NAME.fullmatch(args.campaign): raise ValueError('Unsafe campaign ID')
    temporary = destination.with_name('.ai4r-fetch-' + hashlib.sha256(str(destination).encode()).hexdigest()[:24])
    manifest_path = temporary / '.transfer-manifest.json'
    fingerprint = hashlib.sha256(host.canonical({'ssh': config.get('ssh'), 'root': config['deployment']['root'],
                                                  'campaign': args.campaign})).hexdigest()
    if temporary.exists():
        record = json.loads(host.checked(manifest_path).read_bytes())
        if record['source'] != fingerprint: raise ValueError('Existing partial fetch belongs to another source')
        snapshot = record['snapshot']
    else:
        snapshot = transport.request('snapshot', campaign=args.campaign)
        temporary.mkdir(mode=0o700)
        host.publish(manifest_path, host.canonical({'source': fingerprint, 'snapshot': snapshot}))
    host.capacity(destination.parent, sum(row['size'] for row in snapshot['files']))
    try:
        for row in snapshot['files']:
            path = host.checked(temporary / host.relative(row['path'])); path.parent.mkdir(parents=True, exist_ok=True)
            if path == manifest_path: raise ValueError('Reserved transfer manifest name')
            if path.exists():
                if host.file_info(path) != {'size': row['size'], 'sha256': row['sha256']}:
                    raise ValueError('Existing fetched evidence changed; refusing overwrite')
                continue
            partial = path.with_name('.partial-' + path.name)
            host.checked(partial).unlink(missing_ok=True)
            with partial.open('xb') as f:
                offset = 0
                while offset < row['size']:
                    chunk = base64.b64decode(transport.request('read-chunk', id=snapshot['id'], path=row['path'], offset=offset)['data'], validate=True)
                    if not chunk or len(chunk) > row['size'] - offset:
                        raise ValueError('Truncated or oversized fetch')
                    f.write(chunk); offset += len(chunk)
                f.flush(); os.fsync(f.fileno())
            if host.file_info(partial) != {'size': row['size'], 'sha256': row['sha256']}:
                raise ValueError('Fetch integrity verification failed')
            os.link(partial, path); partial.unlink()
        # Rename only into a still-absent destination. Parent lock serializes our
        # own operators; no existing destination is ever intentionally replaced.
        with host.lock(destination.parent / '.ai4r-fetch.lock'):
            if destination.exists(): raise ValueError('Fetch destination appeared during transfer')
            temporary.rename(destination)
    except Exception:
        # Retain incomplete bytes/manifest for diagnosis, never publish success.
        raise
    return {'output': str(destination), 'verified_files': len(snapshot['files']), 'source_retained': True}


def install_maintenance(profile, config):
    # Scheduler commands refer only to checked-in code, with a generated data
    # profile. No hidden script is copied into a private runtime directory.
    return {'installed': False, 'mode': 'Expiry runs on setup/start/allocation; run maintenance install for daily expiry. Workstation schedules can also service SSH targets.'}


def local_gc(config, dry_run=False):
    removed = []
    for value in config.get('local_temporary', []):
        folder = host.checked(value)
        if not folder.exists(): continue
        marker = json.loads((folder / 'temporary.json').read_bytes())
        if marker.get('owner') != host.OWNER or marker.get('project') != config['deployment']['project']:
            raise ValueError('Foreign local temporary resource')
        if marker.get('status') != 'complete' or time.time() - marker['completed_at'] < config['deployment']['ttl_days'] * 86400:
            continue
        for item in folder.rglob('*'):
            host.checked(item)
            if item.is_file() and item.stat().st_nlink != 1: raise ValueError('Unsafe temporary hardlink')
        removed.append(str(folder))
        if not dry_run: shutil.rmtree(folder)
    return {'expired_build_contexts': removed, 'dry_run': dry_run}


def maintenance(config, args):
    if config.get('ssh') or config.get('wsl_distro') or os.name != 'nt':
        result = Transport(config).request('install-maintenance', source=host_source())
        return result
    invocation = [sys.executable, str(HERE / 'ai4r.py'), '--profile', str(args.profile.resolve()), 'gc']
    name = config['deployment']['project'] + '-expiry-' + hashlib.sha256(str(args.profile.resolve()).encode()).hexdigest()[:8]
    if os.name == 'nt':
        task = subprocess.list2cmdline(invocation)
        # No /F: a foreign or changed existing task is never silently replaced.
        present = subprocess.run(['schtasks', '/Query', '/TN', name, '/XML'], capture_output=True)
        if not present.returncode:
            import xml.etree.ElementTree as ET
            text = present.stdout.decode('utf-16' if present.stdout.startswith(b'\xff\xfe') else 'utf-8-sig')
            document = ET.fromstring(text)
            ns = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
            command = document.find('.//t:Exec/t:Command', ns)
            arguments = document.find('.//t:Exec/t:Arguments', ns)
            if command is None or str(HERE / 'ai4r.py') not in (arguments.text if arguments is not None else ''):
                raise ValueError('Existing scheduled task is not this repository operator')
            if (os.path.normcase(command.text or '') != os.path.normcase(sys.executable)
                    or (arguments.text or '') != subprocess.list2cmdline(invocation[1:])):
                raise ValueError('Existing scheduled task command differs; refusing replacement')
            return {'installed': True, 'scheduler': 'Task Scheduler', 'task': name, 'preserved': True}
        host.run(['schtasks', '/Create', '/TN', name, '/SC', 'DAILY', '/ST', '03:00', '/TR', task])
        return {'installed': True, 'scheduler': 'Task Scheduler', 'task': name}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile', type=Path, default=DEFAULT_PROFILE)
    sub = p.add_subparsers(dest='command', required=True)
    s = sub.add_parser('setup')
    for flag in ('ssh', 'wsl-distro', 'docker-context', 'build-context', 'build-wsl-distro', 'root', 'output', 'project'):
        s.add_argument('--' + flag)
    s.add_argument('--platform', choices=('linux/amd64', 'linux/arm64'))
    s.add_argument('--ttl-days', type=int)
    sub.add_parser('doctor')
    b = sub.add_parser('build'); b.add_argument('--output', type=Path, required=True)
    s = sub.add_parser('stage'); s.add_argument('--cases', type=Path, required=True); s.add_argument('--inputs', type=Path, required=True)
    s.add_argument('--receipt', type=Path)
    s.add_argument('--app-image'); s.add_argument('--runner-image')
    s = sub.add_parser('up', help='Stage existing images and supplied cases/inputs, then start; no sudo or implicit builds')
    for flag in ('ssh', 'wsl-distro', 'docker-context', 'build-context', 'build-wsl-distro', 'root', 'output', 'project'):
        s.add_argument('--' + flag)
    s.add_argument('--platform', choices=('linux/amd64', 'linux/arm64'))
    s.add_argument('--ttl-days', type=int)
    s.add_argument('--cases', type=Path, required=True); s.add_argument('--inputs', type=Path, required=True)
    s.add_argument('--receipt', type=Path); s.add_argument('--app-image'); s.add_argument('--runner-image')
    s.add_argument('--refresh-credential', action='store_true')
    s = sub.add_parser('start'); s.add_argument('--refresh-credential', action='store_true')
    s = sub.add_parser('local-model', help='Configure optional private model mounts without activating a relay')
    lm = s.add_subparsers(dest='local_model_command', required=True)
    c = lm.add_parser('configure')
    c.add_argument('--catalog', required=True)
    c.add_argument('--session-file', required=True)
    c.add_argument('--socket-directory', required=True)
    s = sub.add_parser('local-pool', help='Manage the key-free model pool on a single 128 GB Spark')
    pool = s.add_subparsers(dest='local_pool_command', required=True)
    c = pool.add_parser('configure', help='Pin public model revisions; no weight downloads')
    c.add_argument('--data-root', required=True)
    c.add_argument('--share-address', help='Expose shared inference on this Tailscale IPv4, plus host loopback')
    c = pool.add_parser('migrate', help='Pin the approved local reasoning pool; retain older pool pins')
    c.add_argument('--data-root', required=True)
    c.add_argument('--share-address', help='Shared Tailscale IPv4 plus loopback')
    pool.add_parser('weights', help='Download and verify pinned public weights on Spark; no Docker access needed')
    pool.add_parser('prepare', help='Download pinned images/weights on Spark, after disk checks')
    sub.add_parser('stop')
    s = sub.add_parser('logs'); s.add_argument('--service', choices=('ai4r', 'benchmark-runner'), default='ai4r'); s.add_argument('--tail', type=int, default=100)
    s = sub.add_parser('fetch'); s.add_argument('--campaign', required=True); s.add_argument('--output', type=Path, required=True)
    s = sub.add_parser('gc'); s.add_argument('--dry-run', action='store_true')
    s = sub.add_parser('maintenance'); s.add_argument('operation', choices=('install',))
    s = sub.add_parser('runner', description='Forward doctor, run, status, resume, cancel, export or cleanup to the separate runner container.')
    s.add_argument('args', nargs=argparse.REMAINDER)
    s = sub.add_parser('harbor', help='Prepare, stage, inspect and run Harbor above this deployment')
    hs = s.add_subparsers(dest='harbor_command', required=True)
    b = hs.add_parser('prepare', help='Create a new local control workspace; no target contact')
    b.add_argument('--bundle', type=Path, required=True)
    b.add_argument('--workspace', type=Path, required=True)
    b.add_argument('--mode', choices=('preflight','live'), default='preflight')
    b.add_argument('--case', dest='cases', action='append', default=[])
    b.add_argument('--ssh-executable', type=Path)
    for name in ('stage','doctor','run'):
        b = hs.add_parser(name)
        b.add_argument('--workspace', type=Path, required=True)
        if name in ('doctor','run'): b.add_argument('--python', default=sys.executable)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    args.profile = host.checked(args.profile)
    args.profile.parent.mkdir(parents=True, exist_ok=True)
    # Serialize profile edits and local GC; runner cancellation/status stay
    # available while its controlling process is active.
    if args.command in {'runner', 'harbor'}:
        return execute(args)
    try:
        with host.lock(args.profile.with_name(args.profile.name + '.lock')):
            return execute(args)
    except (OSError, ValueError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}), file=sys.stderr)
        return 2


def execute(args):
    try:
        if args.command == 'harbor':
            if str(REPO) not in sys.path: sys.path.insert(0,str(REPO))
            from benchmarks.harbor_suite import deployment
            if args.harbor_command == 'prepare':
                result = deployment.prepare(args.profile,args.bundle,args.workspace,mode=args.mode,
                                            cases=args.cases,ssh_executable=args.ssh_executable)
            else:
                value,_ = deployment.workspace_config(args.workspace)
                if Path(value['operator_profile']) != args.profile:
                    raise ValueError('Selected --profile differs from the Harbor workspace')
                if args.harbor_command == 'stage': result = deployment.stage(args.workspace)
                elif args.harbor_command == 'doctor': result = deployment.doctor(args.workspace,python=args.python)
                else: result = deployment.run(args.workspace,python=args.python)
            print(json.dumps(result,indent=2))
            if args.harbor_command == 'doctor': return 0 if result['ready'] else 2
            return result.get('returncode',0)
        elif args.command == 'up':
            result = up(args)
        elif args.command == 'setup':
            if args.ttl_days is not None and args.ttl_days < 1: raise ValueError('TTL must be at least one day')
            result = setup(args)
        else:
            config = load(args.profile); transport = Transport(config)
            if args.command == 'build': result = build(config, args)
            elif args.command == 'stage': result = stage_selection(config, args)
            elif args.command == 'fetch': result = fetch(config, args)
            elif args.command == 'maintenance': result = maintenance(config, args)
            elif args.command == 'local-model':
                result = transport.request('local-model-configure', catalog=args.catalog,
                    session_file=args.session_file, socket_directory=args.socket_directory)
                config['deployment'] = result.pop('deployment')
            elif args.command == 'local-pool':
                # Keep image selections made by build in the same deployment
                # before the host adds its model pins to that deployment.
                config['deployment'] = transport.request('configure')['deployment']
                values = {'data_root': args.data_root, 'share_address': args.share_address} if args.local_pool_command in {'configure','migrate'} else {}
                result = transport.request('local-pool-' + args.local_pool_command, **values)
                config['deployment'] = result.pop('deployment')
            elif args.command == 'start':
                result = transport.request('start', refresh_credential=args.refresh_credential,
                    template=(HERE / 'compose.benchmark-runner.yaml').read_text())
                config['deployment'] = result.pop('deployment')
            elif args.command == 'runner':
                forwarded = args.args
                if forwarded and forwarded[0] in {'doctor', 'run'}:
                    for key, value in [('--cases', config.get('case_file')), ('--inputs', '/inputs'), ('--output', '/results')]:
                        if key not in forwarded and value: forwarded.extend([key, value])
                result = transport.request('runner', args=forwarded)
                print(result['stdout'], end=''); return result['returncode']
            elif args.command == 'gc':
                result = transport.request('gc', dry_run=args.dry_run)
                result['local'] = local_gc(config, args.dry_run)
            elif args.command == 'logs': result = transport.request('logs', service=args.service, tail=args.tail)
            else: result = transport.request(args.command)
            if args.command in {'build', 'stage', 'start', 'local-model', 'local-pool'}:
                save(args.profile, config)
        print(json.dumps(result, indent=2))
        return 2 if args.command == 'doctor' and result.get('prerequisite_error') else 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc) if isinstance(exc, ValueError) else type(exc).__name__ + ': prerequisite/host operation failed; run doctor'}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
