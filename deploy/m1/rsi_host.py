"""Finite, separate native Linux RSI host runtime. Never installs Debian packages.

prepare downloads from a private, freshly authenticated Ubuntu APT index, checks
its SHA256 records, and extracts payloads without running maintainer scripts.
start touches only the named services, private storage and named cgroup branch.
status is observation, never RSI security qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tarfile

ROOT = Path('/opt/ai4r-rsi-host')
DATA = Path('/var/lib/ai4r-rsi-docker')
RUN = Path('/run/ai4r-rsi-docker')
CG = Path('/sys/fs/cgroup/ai4r-rsi-host')
SOCKET = 'unix:///run/ai4r-rsi-docker/docker.sock'
PACKAGES = {'docker.io': '29.1.3-0ubuntu3~24.04.2',
            'containerd': '2.2.1-0ubuntu1~24.04.4',
            'runc': '1.3.4-0ubuntu1~24.04.1',
            'bubblewrap': '0.9.0-1ubuntu0.3'}
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/root'}


def run(args, *, cwd=None, env=None, binary=False):
    result = subprocess.run(list(map(str, args)), cwd=cwd, env=env or ENV,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=600, check=True)
    return result.stdout if binary else result.stdout.decode('utf8')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('UNSAFE_HOST_PATH')
    return path


def secure(path):
    safe(path)
    meta = path.stat()
    if meta.st_uid != 0 or meta.st_mode & 0o022:
        raise ValueError('UNPROTECTED_HOST_PATH')
    for parent in path.parents:
        meta = parent.stat()
        if meta.st_uid != 0 or meta.st_mode & 0o022:
            raise ValueError('UNPROTECTED_HOST_ANCESTRY')


def archive_path(name):
    while name.startswith('./'):
        name = name[2:]
    p = PurePosixPath(name)
    if not name or p.is_absolute() or '..' in p.parts or '\\' in name:
        raise ValueError('UNSAFE_DEB_ARCHIVE_PATH')
    return p


def extract_payload(payload, destination):
    """No tarfile.extract: reject devices, escaping links and symlink parents."""
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:') as archive:
        members = archive.getmembers()
        if len(members) > 100000 or sum(m.size for m in members) > 1024 ** 3:
            raise ValueError('DEB_PAYLOAD_LIMIT')
        for member in members:
            if member.name in ('.', './'):
                continue
            relative = archive_path(member.name)
            path = destination.joinpath(*relative.parts)
            if any(p.is_symlink() for p in path.parents if p != destination.parent):
                raise ValueError('DEB_SYMLINK_PARENT')
            path.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                path.mkdir(exist_ok=True)
            elif member.isfile():
                if path.exists() or path.is_symlink():
                    # Packages may share identical files, never replace code.
                    if not path.is_file() or path.is_symlink() or path.read_bytes() != archive.extractfile(member).read():
                        raise ValueError('DEB_PAYLOAD_COLLISION')
                else:
                    with path.open('xb') as out, archive.extractfile(member) as source:
                        shutil.copyfileobj(source, out)
                    path.chmod(member.mode & 0o755)
            elif member.issym():
                target = PurePosixPath(member.linkname)
                resolved = (path.parent / str(target)).resolve()
                if target.is_absolute() or not resolved.is_relative_to(destination.resolve()):
                    raise ValueError('DEB_LINK_ESCAPE')
                if path.is_symlink() and os.readlink(path) == member.linkname:
                    continue
                path.symlink_to(member.linkname)
            else:
                raise ValueError('UNSUPPORTED_DEB_ENTRY')


def apt_options():
    apt = ROOT / 'apt'
    settings = {'Dir::Etc::sourcelist': str(apt / 'sources.list'),
                'Dir::Etc::sourceparts': '-', 'Dir::Etc::parts': '-',
                'Dir::Etc::main': '-', 'Dir::State::lists': str(apt / 'lists'),
                'Dir::Cache::archives': str(ROOT / 'debs'),
                'APT::Get::AllowUnauthenticated': 'false',
                'Acquire::AllowInsecureRepositories': 'false',
                'Acquire::AllowDowngradeToInsecureRepositories': 'false',
                'APT::Install-Recommends': 'false', 'APT::Install-Suggests': 'false'}
    return [part for key, value in settings.items() for part in ('-o', key + '=' + value)]


def prepare():
    # A partial or foreign prefix is never silently adopted.
    if run(['/usr/bin/dpkg', '--print-architecture']).strip() != 'amd64':
        raise ValueError('PINNED_AMD64_RUNTIME_REQUIRED')
    safe(ROOT).mkdir(mode=0o700)
    apt = ROOT / 'apt'
    for path in (apt / 'lists/partial', ROOT / 'debs/partial', ROOT / 'payload'):
        path.mkdir(parents=True, mode=0o700)
    (apt / 'sources.list').write_text(
        'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] '
        'http://archive.ubuntu.com/ubuntu noble main universe\n'
        'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] '
        'http://archive.ubuntu.com/ubuntu noble-updates main universe\n'
        'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] '
        'http://security.ubuntu.com/ubuntu noble-security main universe\n')
    options = apt_options()
    run(['/usr/bin/apt-get', *options, 'update'])
    specs = [name + '=' + version for name, version in PACKAGES.items()]
    plan = run(['/usr/bin/apt-get', *options, '-s', '--no-install-recommends', 'install', *specs])
    if re.search(r'^(Remv|Purg) ', plan, re.M):
        raise ValueError('APT_REMOVAL_PLAN_REFUSED')
    packages = dict(PACKAGES)
    for name, version in re.findall(r'^Inst ([a-z0-9.+:-]+)(?: \[[^\]]+\])? \(([^\s]+)', plan, re.M):
        packages[name] = version
    records = []
    for name, version in sorted(packages.items()):
        if not re.fullmatch(r'[a-z0-9.+:-]+', name) or not re.fullmatch(r'[A-Za-z0-9.+:~_-]+', version):
            raise ValueError('INVALID_APT_PACKAGE')
        metadata = run(['/usr/bin/apt-cache', *options, 'show', name + '=' + version])
        hashes = set(re.findall(r'^SHA256: ([0-9a-f]{64})$', metadata, re.M))
        if len(hashes) != 1:
            raise ValueError('AMBIGUOUS_APT_SHA256')
        before = set((ROOT / 'debs').glob('*.deb'))
        run(['/usr/bin/apt-get', *options, 'download', name + '=' + version], cwd=ROOT / 'debs')
        added = set((ROOT / 'debs').glob('*.deb')) - before
        if len(added) != 1:
            raise ValueError('AMBIGUOUS_APT_DOWNLOAD')
        deb = added.pop()
        if digest(deb) != hashes.pop():
            raise ValueError('APT_DEB_SHA256_MISMATCH')
        extract_payload(run(['/usr/bin/dpkg-deb', '--fsys-tarfile', deb], binary=True), ROOT / 'payload')
        records.append({'package': name, 'version': version, 'deb': deb.name, 'sha256': digest(deb)})
    files = {str(p.relative_to(ROOT)): digest(p) for p in (ROOT / 'payload').rglob('*') if p.is_file() and not p.is_symlink()}
    links = {str(p.relative_to(ROOT)): os.readlink(p) for p in (ROOT / 'payload').rglob('*') if p.is_symlink()}
    manifest = {'schema': 'ai4r-rsi-native-host:1', 'packages': records, 'files': files, 'links': links}
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    return {'prepared': True, 'root': str(ROOT), 'packages': records}


def verified():
    secure(ROOT)
    manifest_path = ROOT / 'manifest.json'
    secure(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('schema') != 'ai4r-rsi-native-host:1':
        raise ValueError('HOST_MANIFEST_SCHEMA')
    current_files = {str(p.relative_to(ROOT)) for p in (ROOT / 'payload').rglob('*') if p.is_file() and not p.is_symlink()}
    current_links = {str(p.relative_to(ROOT)) for p in (ROOT / 'payload').rglob('*') if p.is_symlink()}
    if current_files != set(manifest['files']) or current_links != set(manifest['links']):
        raise ValueError('HOST_PAYLOAD_INVENTORY_CHANGED')
    for name, expected in manifest['files'].items():
        path = ROOT.joinpath(*archive_path(name).parts)
        secure(path)
        if digest(path) != expected:
            raise ValueError('HOST_BINARY_HASH_CHANGED')
    for name, expected in manifest['links'].items():
        path = ROOT.joinpath(*archive_path(name).parts)
        if not path.is_symlink() or os.readlink(path) != expected:
            raise ValueError('HOST_LINK_CHANGED')
    for package in manifest['packages']:
        path = ROOT / 'debs' / package['deb']
        secure(path)
        if path.parent != ROOT / 'debs' or digest(path) != package['sha256']:
            raise ValueError('HOST_DEB_CHANGED')
    return manifest


def executable(name):
    for sub in ('usr/bin', 'usr/sbin', 'bin', 'sbin'):
        path = ROOT / 'payload' / sub / name
        if path.is_file() and not path.is_symlink() and os.access(path, os.X_OK):
            return str(path)
    raise ValueError('PRIVATE_RUNTIME_BINARY_MISSING:' + name)


def daemon_environment():
    env = dict(ENV)
    env['PATH'] = ':'.join(str(ROOT / 'payload' / p) for p in ('usr/bin', 'usr/sbin', 'bin', 'sbin')) + ':' + ENV['PATH']
    env['LD_LIBRARY_PATH'] = ':'.join(str(ROOT / 'payload' / p) for p in ('usr/lib/x86_64-linux-gnu', 'lib/x86_64-linux-gnu', 'usr/lib', 'lib'))
    return env


def bounds(memory_mb, pids_max, cpu_percent=200):
    if not 256 <= memory_mb <= 65536 or not 32 <= pids_max <= 32768 or not 1 <= cpu_percent <= 6400:
        raise ValueError('FINITE_EXPLICIT_HOST_LIMITS_REQUIRED')


def service_command(name, command, memory_mb, pids_max, cpu_percent=200):
    env = daemon_environment()
    return ['/usr/bin/systemd-run', '--unit=ai4r-rsi-' + name, '--service-type=exec',
            '--property=Delegate=yes', '--property=MemoryMax=' + str(memory_mb * 1024 ** 2),
            '--property=TasksMax=' + str(pids_max), '--property=KillMode=control-group',
            '--property=CPUQuota=' + str(cpu_percent) + '%',
            '--property=Restart=no', '--setenv=PATH=' + env['PATH'],
            '--setenv=LD_LIBRARY_PATH=' + env['LD_LIBRARY_PATH'], *command]


def docker_command():
    return [executable('dockerd'), '--config-file=' + str(ROOT / 'daemon.json'),
            '--host=' + SOCKET, '--data-root=' + str(DATA / 'docker'),
            '--exec-root=' + str(RUN / 'docker-exec'), '--pidfile=' + str(RUN / 'docker.pid'),
            '--containerd=' + str(RUN / 'containerd.sock'),
            '--containerd-namespace=ai4r-rsi', '--containerd-plugins-namespace=ai4r-rsi-plugins',
            '--exec-opt=native.cgroupdriver=cgroupfs', '--cgroup-parent=' + str(CG / 'containers').removeprefix('/sys/fs/cgroup'),
            '--bridge=none', '--iptables=false', '--ip6tables=false', '--ip-forward=false',
            '--ip-masq=false', '--userland-proxy=false']


def start(memory_mb, pids_max, cpu_percent=200):
    bounds(memory_mb, pids_max, cpu_percent)
    verified()
    for unit in ('containerd', 'docker'):
        state = run(['/usr/bin/systemctl', 'show', 'ai4r-rsi-' + unit + '.service', '-p', 'LoadState', '--value']).strip()
        if state != 'not-found':
            raise ValueError('EXISTING_RSI_SERVICE_REFUSED')
    for path in (DATA, RUN, CG):
        safe(path).mkdir(mode=0o700)
    controls = set((CG / 'cgroup.controllers').read_text().split())
    if not {'cpu', 'memory', 'pids'} <= controls:
        raise ValueError('HOST_CONTROLLERS_UNAVAILABLE')
    (CG / 'memory.max').write_text(str(memory_mb * 1024 ** 2))
    (CG / 'memory.swap.max').write_text('0')
    (CG / 'pids.max').write_text(str(pids_max))
    (CG / 'cpu.max').write_text(str(cpu_percent * 1000) + ' 100000')
    (CG / 'cgroup.max.depth').write_text('8')
    (CG / 'cgroup.max.descendants').write_text('512')
    (CG / 'cgroup.subtree_control').write_text('+cpu +memory +pids')
    for name in ('jobs', 'containers'):
        path = CG / name
        path.mkdir(mode=0o700)
        (path / 'cgroup.subtree_control').write_text('+cpu +memory +pids')
    # Empty private config prevents ambient /etc/docker or containerd settings.
    (ROOT / 'daemon.json').write_text('{}\n')
    (ROOT / 'containerd.toml').write_text('version = 2\n')
    receipt = {'memory_max': str(memory_mb * 1024 ** 2), 'pids_max': str(pids_max),
               'cpu_max': str(cpu_percent * 1000) + ' 100000', 'cgroup_inode': CG.stat().st_ino}
    (ROOT / 'started.json').write_text(json.dumps(receipt) + '\n')
    run(service_command('containerd', [executable('containerd'), '--config', ROOT / 'containerd.toml',
        '--address', RUN / 'containerd.sock', '--root', DATA / 'containerd', '--state', RUN / 'containerd'], memory_mb, pids_max, cpu_percent))
    import time
    for _ in range(100):
        if (RUN / 'containerd.sock').is_socket():
            break
        time.sleep(.1)
    else:
        raise ValueError('PRIVATE_CONTAINERD_SOCKET_UNAVAILABLE')
    run(service_command('docker', docker_command(), memory_mb, pids_max, cpu_percent))
    return {'started': True, 'socket': SOCKET, 'cgroup_root': str(CG / 'jobs'), **receipt}


def incarnation():
    """WSL can replace a distro's PID1 without replacing the shared kernel."""
    return {'kernel_boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'pid1_start_ticks': Path('/proc/1/stat').read_text().rsplit(')', 1)[1].split()[19],
            'pid1_mount_namespace': os.readlink('/proc/1/ns/mnt'),
            'pid1_pid_namespace': os.readlink('/proc/1/ns/pid')}


def incarnation_key(value=None):
    return hashlib.sha256(json.dumps(value or incarnation(), sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def hold(seconds):
    """Finite foreground lease; systemd services alone do not keep WSL alive."""
    import signal
    import time
    if not isinstance(seconds, int) or not 1 <= seconds <= 7200:
        raise ValueError('FINITE_HOST_HOLD_SECONDS_REQUIRED')
    identity = incarnation()
    key = incarnation_key(identity)
    stopping = []
    def stop(signum, _frame):
        stopping.append(signum)
    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    started = time.monotonic()
    print(json.dumps({'status': 'FOREGROUND_HOST_HOLD_STARTED', 'pid': os.getpid(),
        'maximum_seconds': seconds, 'incarnation': identity, 'incarnation_key': key,
        'daemon_or_model_started': False}), flush=True)
    try:
        while not stopping and time.monotonic() - started < seconds:
            if incarnation() != identity:
                raise ValueError('HOST_INCARNATION_CHANGED')
            time.sleep(min(1, max(0, seconds - (time.monotonic() - started))))
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return {'status': 'FOREGROUND_HOST_HOLD_ENDED', 'incarnation_key': key,
            'elapsed_seconds': time.monotonic() - started, 'signal': stopping[0] if stopping else None}


def active_receipt():
    receipt_path = ROOT / 'started.json'
    secure(receipt_path)
    receipt = json.loads(receipt_path.read_text())
    # Reboot restoration preserves started.json and issues a boot-bound successor.
    identity = incarnation()
    key = incarnation_key(identity)
    successor = ROOT / ('started.instance.' + key + '.json')
    if successor.exists():
        secure(successor)
        candidate = json.loads(successor.read_text())
        if (candidate.get('schema') != 'ai4r-rsi-host-restored-bounds:1'
                or candidate.get('incarnation') != identity
                or candidate.get('original_started_sha256') != digest(receipt_path)):
            raise ValueError('HOST_BOOT_RECEIPT_CHANGED')
        pin = candidate.get('plan_sha256')
        if not isinstance(pin, str) or not re.fullmatch('[a-f0-9]{64}', pin):
            raise ValueError('HOST_BOOT_PLAN_HASH_REQUIRED')
        plan = (Path('/var/lib/ai4r-rsi-codex/config/host-boot-restoration') / key /
                ('plan.' + pin + '.json'))
        complete = plan.with_suffix('.complete.json')
        secure(plan)
        secure(complete)
        if (candidate.get('plan_path') != str(plan)
                or candidate.get('plan_sha256') != digest(plan)
                or candidate.get('completion_sha256') != digest(complete)
                or json.loads(complete.read_text()).get('cgroup_inode') != candidate['cgroup_inode']):
            raise ValueError('HOST_BOOT_RESTORATION_CHAIN_CHANGED')
        receipt = candidate
    elif list(ROOT.glob('started.boot.*.json')) or list(ROOT.glob('started.instance.*.json')):
        raise ValueError('HOST_INCARNATION_RESTORATION_REQUIRED')
    return receipt


def status():
    verified()
    receipt = active_receipt()
    limits = {key: (CG / name).read_text().strip() for key, name in (('memory_max', 'memory.max'), ('pids_max', 'pids.max'), ('cpu_max', 'cpu.max'))}
    if CG.stat().st_ino != receipt['cgroup_inode'] or any(limits[key] != receipt[key] for key in limits):
        raise ValueError('HOST_CGROUP_IDENTITY_OR_LIMIT_CHANGED')
    for value in (limits['memory_max'], limits['pids_max'], limits['cpu_max'].split()[0]):
        if not value.isdigit() or int(value) <= 0:
            raise ValueError('HOST_CGROUP_NOT_BOUNDED')
    socket = RUN / 'docker.sock'
    safe(socket)
    if not socket.is_socket() or socket.stat().st_uid != 0:
        raise ValueError('PRIVATE_DOCKER_SOCKET_UNAVAILABLE')
    info = json.loads(run(['/usr/bin/docker', '--host', SOCKET, 'info', '--format', '{{json .}}']))
    if info.get('DockerRootDir') != str(DATA / 'docker') or str(info.get('CgroupVersion')) != '2':
        raise ValueError('PRIVATE_DOCKER_IDENTITY_MISMATCH')
    for name, binary in (('docker', 'dockerd'), ('containerd', 'containerd')):
        pid = run(['/usr/bin/systemctl', 'show', 'ai4r-rsi-' + name + '.service', '-p', 'MainPID', '--value']).strip()
        if not pid.isdigit() or int(pid) <= 0 or Path('/proc', pid, 'exe').resolve() != Path(executable(binary)):
            raise ValueError('PRIVATE_DAEMON_HOST_PROCESS_MISMATCH')
    return {'status': 'OBSERVED_NOT_QUALIFIED', 'socket': SOCKET, 'daemon_id': info['ID'],
            'cgroup_root': str(CG / 'jobs'), **limits}


def observer_command(command):
    if not command or not Path(command[0]).is_absolute():
        raise ValueError('ABSOLUTE_TRUSTED_OBSERVER_REQUIRED')
    return ['/usr/bin/unshare', '--mount', '--propagation', 'private', '/bin/sh', '-ec',
            'mount --bind /run/ai4r-rsi-docker/docker.sock /run/docker.sock; exec "$@"',
            'rsi-host-observer', *command]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    sub.add_parser('prepare')
    start_parser = sub.add_parser('start')
    start_parser.add_argument('--memory-mb', type=int, required=True)
    start_parser.add_argument('--pids-max', type=int, required=True)
    start_parser.add_argument('--cpu-quota-percent', type=int, default=200)
    sub.add_parser('status')
    hold_parser = sub.add_parser('hold')
    hold_parser.add_argument('--seconds', type=int, required=True)
    observe = sub.add_parser('observe')
    observe.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if os.name != 'posix' or os.geteuid() != 0:
        parser.error('LINUX_HOST_ROOT_REQUIRED')
    if args.operation == 'observe':
        status()
        command = observer_command(args.command)
        os.execve(command[0], command, ENV)
    result = (hold(args.seconds) if args.operation == 'hold' else prepare() if args.operation == 'prepare'
              else start(args.memory_mb, args.pids_max, args.cpu_quota_percent)
              if args.operation == 'start' else status())
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
