"""Explicit, nonreplayable restoration of the dedicated RSI host after a boot.

Retains original configuration/receipts and stopped containers. Never starts a
worker, relay, model, or shared Docker service. Review plan before apply.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

spec = importlib.util.spec_from_file_location('rsi_owned_host', Path(__file__).with_name('rsi_host.py'))
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)
ROOT = Path('/var/lib/ai4r-rsi-codex')
BOOT = Path('/proc/sys/kernel/random/boot_id')
CLIENT = Path('/usr/bin/docker')
OBSERVER_SOCKET = Path('/run/docker.sock')
DESKTOP_TARGET = '/mnt/wsl/docker-desktop/cli-tools/usr/bin/docker'
COMPOSE_LINK = Path('/usr/local/lib/docker/cli-plugins/docker-compose')
COMPOSE_TARGET = '/mnt/wsl/docker-desktop/cli-tools/usr/local/lib/docker/cli-plugins/docker-compose'


def compose_helper():
    owner_spec = importlib.util.spec_from_file_location('_owned_compose', Path(__file__).with_name('rsi_compose.py'))
    owner = importlib.util.module_from_spec(owner_spec); owner_spec.loader.exec_module(owner)
    value = owner.verify()
    meta = COMPOSE_LINK.lstat()
    need(COMPOSE_LINK.is_symlink() and meta.st_uid == 0 and os.readlink(COMPOSE_LINK) == COMPOSE_TARGET,
         'ORIGINAL_COMPOSE_LINK_REQUIRED')
    return {**value, 'original_link': {'target': os.readlink(COMPOSE_LINK), 'inode': meta.st_ino,
            'uid': meta.st_uid, 'gid': meta.st_gid, 'mode': meta.st_mode, 'mtime_ns': meta.st_mtime_ns}}


def client_link():
    meta = CLIENT.lstat()
    need(CLIENT.is_symlink() and meta.st_uid == 0 and os.readlink(CLIENT) == DESKTOP_TARGET,
         'ORIGINAL_CLIENT_LINK_REQUIRED')
    return {'target': os.readlink(CLIENT), 'inode': meta.st_ino, 'mode': meta.st_mode,
            'uid': meta.st_uid, 'gid': meta.st_gid, 'mtime_ns': meta.st_mtime_ns}


def plan_path(key, plan_sha256):
    need(re.fullmatch(r'[a-f0-9]{64}', key), 'INCARNATION_KEY_REQUIRED')
    need(re.fullmatch(r'[a-f0-9]{64}', plan_sha256), 'PLAN_HASH_REQUIRED')
    return ROOT / 'config/host-boot-restoration' / key / ('plan.' + plan_sha256 + '.json')


def need(value, code):
    if not value:
        raise ValueError(code)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def new(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def stopped_configuration(configuration, policy):
    state = configuration['State']
    need(not state['Running'] and not state['Restarting'] and state['Pid'] == 0,
         'RETAINED_CONTAINER_NOT_STOPPED')
    need(policy.get('RestartPolicy') == {'Name': 'no', 'MaximumRetryCount': 0},
         'AUTOMATIC_CONTAINER_RESTART_REFUSED')


def observe(previous_boot):
    need(os.geteuid() == 0, 'LINUX_ROOT_REQUIRED')
    need(re.fullmatch(r'[a-f0-9-]{36}', previous_boot), 'PREVIOUS_BOOT_REQUIRED')
    current = BOOT.read_text().strip()
    identity = host.incarnation()
    key = host.incarnation_key(identity)
    histories = {}
    for claim in (ROOT / 'config').glob('host-boot-restoration.*.claim.json'):
        host.secure(claim)
        claim_value = json.loads(claim.read_bytes())
        prior_key = claim.name[len('host-boot-restoration.'):-len('.claim.json')]
        legacy_plan = ROOT / 'config/host-boot-restoration' / prior_key / 'plan.json'
        prior_plan = Path(claim_value.get('plan_path', str(legacy_plan)))
        need(prior_plan == legacy_plan or prior_plan == plan_path(prior_key, claim_value['plan_sha256']),
             'PRIOR_PLAN_CUSTODY_PATH_DIFFERS')
        complete = prior_plan.with_suffix('.complete.json')
        host.secure(prior_plan); host.secure(complete)
        finished = json.loads(complete.read_bytes())
        need(claim_value['plan_sha256'] == sha(prior_plan.read_bytes()) == finished['plan_sha256'],
             'INCOMPLETE_PRIOR_HOST_RESTORATION')
        need(finished.get('incarnation_key') != key, 'SAME_INCARNATION_RESTORATION_REFUSED')
        histories[str(complete)] = sha(complete.read_bytes())
    need(current != previous_boot or histories, 'UNPROVEN_PRIOR_INCARNATION')
    manifest = host.verified()
    need(not host.RUN.exists() and not host.CG.exists(), 'PARTIAL_HOST_RESTORATION_REFUSED')
    for name in ('docker', 'containerd'):
        state = host.run(['/usr/bin/systemctl', 'show', 'ai4r-rsi-' + name + '.service',
                          '-p', 'LoadState', '--value']).strip()
        need(state == 'not-found', 'EXISTING_OWNED_UNIT_REFUSED')
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            try:
                executable = (path / 'exe').resolve(strict=True)
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                continue
            need(executable not in {Path(host.executable(n)) for n in ('dockerd', 'containerd')},
                 'EXISTING_OWNED_DAEMON_REFUSED')
    link = client_link()
    compose = compose_helper()
    need(not CLIENT.exists(), 'ACTIVE_DESKTOP_CLIENT_REFUSED')
    need(not os.path.lexists(OBSERVER_SOCKET), 'EXISTING_OBSERVER_SOCKET_REFUSED')
    proofs = {}
    for path in (host.ROOT / 'manifest.json', host.ROOT / 'started.json',
                 host.ROOT / 'daemon.json', host.ROOT / 'containerd.toml', ROOT / 'local.json',
                 host.DATA / 'docker/engine-id'):
        host.secure(path)
        proofs[str(path)] = sha(path.read_bytes())
    need((host.ROOT / 'daemon.json').read_bytes() == b'{}\n', 'DAEMON_CONFIG_CHANGED')
    need((host.ROOT / 'containerd.toml').read_bytes() == b'version = 2\n', 'CONTAINERD_CONFIG_CHANGED')
    receipt = json.loads((host.ROOT / 'started.json').read_bytes())
    bounds = (int(receipt['memory_max']) // 1024 ** 2, int(receipt['pids_max']),
              int(receipt['cpu_max'].split()[0]) // 1000)
    host.bounds(*bounds)
    need(str(bounds[0] * 1024 ** 2) == receipt['memory_max'] and
         receipt['cpu_max'] == str(bounds[2] * 1000) + ' 100000', 'ORIGINAL_BOUNDS_INVALID')
    containers = []
    base = host.DATA / 'docker/containers'
    host.secure(base)
    for folder in sorted(base.iterdir()):
        need(re.fullmatch('[a-f0-9]{64}', folder.name), 'UNEXPECTED_CONTAINER_DIRECTORY')
        config, policy = folder / 'config.v2.json', folder / 'hostconfig.json'
        host.secure(config)
        host.secure(policy)
        stopped_configuration(json.loads(config.read_bytes()), json.loads(policy.read_bytes()))
        for path in (config, policy):
            proofs[str(path)] = sha(path.read_bytes())
        containers.append(folder.name)
    need(containers, 'RETAINED_CONTAINERS_REQUIRED')
    return {'schema': 'ai4r-rsi-host-boot-restoration:1', 'previous_boot_id': previous_boot,
            'current_boot_id': current, 'proof_sha256': proofs, 'container_ids': containers,
            'incarnation': identity, 'incarnation_key': key, 'prior_completion_sha256': histories,
            'bounds': list(bounds), 'payload_files': len(manifest['files']),
            'docker_binary_sha256': manifest['files']['payload/usr/bin/docker'],
            'daemon_id': (host.DATA / 'docker/engine-id').read_text().strip(),
            'original_client_link': link,
            'compose_helper': compose,
            'source_sha256': {str(p): sha(p.read_bytes()) for p in
                              (Path(__file__).resolve(), Path(host.__file__).resolve(),
                               Path(__file__).with_name('rsi_compose.py').resolve())},
            'starts_models_or_workers': False, 'shared_services_changed': False}


def namespace_command(command, compose_binary):
    need(command and Path(command[0]).is_absolute(), 'ABSOLUTE_COMMAND_REQUIRED')
    return ['/usr/bin/unshare', '--mount', '--propagation', 'private', '/bin/sh', '-ec',
            'mount -t tmpfs -o size=1m,nosuid,nodev tmpfs /mnt/wsl; '
            'mkdir -p /mnt/wsl/docker-desktop/cli-tools/usr/bin; '
            'touch /mnt/wsl/docker-desktop/cli-tools/usr/bin/docker; '
            'mount --bind "$1" /mnt/wsl/docker-desktop/cli-tools/usr/bin/docker; '
            'mkdir -p /mnt/wsl/docker-desktop/cli-tools/usr/local/lib/docker/cli-plugins; '
            'touch /mnt/wsl/docker-desktop/cli-tools/usr/local/lib/docker/cli-plugins/docker-compose; '
            'mount --bind "$2" /mnt/wsl/docker-desktop/cli-tools/usr/local/lib/docker/cli-plugins/docker-compose; '
            'shift 2; exec "$@"',
            'rsi-owned-client', host.executable('docker'), compose_binary, *command]


def client(command):
    host.verified()
    before = client_link()
    compose = compose_helper()
    result = subprocess.run(namespace_command(command, compose['binary']), env=host.ENV, timeout=600, check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    need(client_link() == before, 'GLOBAL_CLIENT_LINK_CHANGED')
    need(compose_helper() == compose, 'GLOBAL_COMPOSE_HELPER_CHANGED')
    return result


def apply(path, approval):
    need(path == plan_path(host.incarnation_key(), approval), 'ROOT_CUSTODY_PLAN_REQUIRED')
    host.secure(path)
    raw = path.read_bytes()
    need(sha(raw) == approval, 'PLAN_APPROVAL_MISMATCH')
    plan = json.loads(raw)
    need(observe(plan['previous_boot_id']) == plan, 'PLAN_STATE_CHANGED')
    claim = ROOT / 'config' / ('host-boot-restoration.' + plan['incarnation_key'] + '.claim.json')
    new(claim, encoded({'plan_sha256': approval, 'plan_path': str(path), 'incarnation': plan['incarnation']}))
    # A durable claim forbids replay after any partial effect below.
    new(OBSERVER_SOCKET, b'')
    os.chmod(OBSERVER_SOCKET, 0)
    memory, pids, cpu = plan['bounds']
    host.RUN.mkdir(mode=0o700)
    host.CG.mkdir(mode=0o700)
    controls = set((host.CG / 'cgroup.controllers').read_text().split())
    need({'cpu', 'memory', 'pids'} <= controls, 'HOST_CONTROLLERS_UNAVAILABLE')
    for name, value in {'memory.max': str(memory * 1024 ** 2), 'memory.swap.max': '0',
                        'pids.max': str(pids), 'cpu.max': str(cpu * 1000) + ' 100000',
                        'cgroup.max.depth': '8', 'cgroup.max.descendants': '512',
                        'cgroup.subtree_control': '+cpu +memory +pids'}.items():
        (host.CG / name).write_text(value)
    for name in ('jobs', 'containers'):
        branch = host.CG / name
        branch.mkdir(mode=0o700)
        (branch / 'cgroup.subtree_control').write_text('+cpu +memory +pids')
    host.run(host.service_command('containerd', [host.executable('containerd'), '--config',
        host.ROOT / 'containerd.toml', '--address', host.RUN / 'containerd.sock', '--root',
        host.DATA / 'containerd', '--state', host.RUN / 'containerd'], memory, pids, cpu))
    need(host.incarnation() == plan['incarnation'], 'HOST_INCARNATION_CHANGED')
    for _ in range(100):
        if (host.RUN / 'containerd.sock').is_socket():
            break
        time.sleep(.1)
    need((host.RUN / 'containerd.sock').is_socket(), 'CONTAINERD_START_UNOBSERVED')
    host.run(host.service_command('docker', host.docker_command(), memory, pids, cpu))
    need(host.incarnation() == plan['incarnation'], 'HOST_INCARNATION_CHANGED')
    for _ in range(100):
        if (host.RUN / 'docker.sock').is_socket():
            break
        time.sleep(.1)
    need((host.RUN / 'docker.sock').is_socket(), 'DOCKER_START_UNOBSERVED')
    docker = ['/usr/bin/docker', '--host', host.SOCKET]
    info = json.loads(client(docker + ['info', '--format', '{{json .}}']))
    need(info['DockerRootDir'] == str(host.DATA / 'docker') and str(info['CgroupVersion']) == '2',
         'RESTORED_DAEMON_IDENTITY_MISMATCH')
    need(info['ID'] == plan['daemon_id'], 'ORIGINAL_DAEMON_ID_CHANGED')
    actual = json.loads(client(docker + ['inspect', *plan['container_ids']]))
    need(sorted(row['Id'] for row in actual) == plan['container_ids'], 'CONTAINER_SET_CHANGED')
    for row in actual:
        stopped_configuration(row, row['HostConfig'])
    need(not client(docker + ['ps', '-q']).strip(), 'UNEXPECTED_RUNNING_CONTAINER')
    for name in ('docker', 'containerd'):
        pid = host.run(['/usr/bin/systemctl', 'show', 'ai4r-rsi-' + name + '.service',
                        '-p', 'MainPID', '--value']).strip()
        need(pid.isdigit() and int(pid) > 0 and Path('/proc', pid, 'exe').resolve() ==
             Path(host.executable('dockerd' if name == 'docker' else name)), 'DAEMON_PROCESS_MISMATCH')
    result = {'schema': 'ai4r-rsi-host-boot-restoration-complete:1', 'plan_sha256': approval,
              'incarnation': plan['incarnation'], 'incarnation_key': plan['incarnation_key'],
              'boot_id': plan['current_boot_id'], 'daemon_id': info['ID'],
              'cgroup_inode': host.CG.stat().st_ino, 'bounds': plan['bounds'],
              'containers_stopped': plan['container_ids'], 'original_receipts_preserved': True,
              'model_started': False}
    complete = encoded(result)
    new(host.ROOT / ('started.instance.' + plan['incarnation_key'] + '.json'), encoded({
        'schema': 'ai4r-rsi-host-restored-bounds:1', 'boot_id': plan['current_boot_id'],
        'incarnation': plan['incarnation'], 'incarnation_key': plan['incarnation_key'],
        'original_started_sha256': plan['proof_sha256'][str(host.ROOT / 'started.json')],
        'plan_sha256': approval, 'cgroup_inode': result['cgroup_inode'],
        'plan_path': str(path), 'completion_sha256': sha(complete),
        'memory_max': str(memory * 1024 ** 2), 'pids_max': str(pids),
        'cpu_max': str(cpu * 1000) + ' 100000'}))
    new(path.with_suffix('.complete.json'), complete)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation', required=True)
    plan = commands.add_parser('plan')
    plan.add_argument('--previous-boot-id', required=True)
    change = commands.add_parser('apply')
    change.add_argument('--plan', type=Path, required=True)
    change.add_argument('--approval-sha256', required=True)
    wrapper = commands.add_parser('client')
    wrapper.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.operation == 'client':
        print(client(args.command).decode(), end='')
    elif args.operation == 'plan':
        raw = encoded(observe(args.previous_boot_id))
        path = plan_path(json.loads(raw)['incarnation_key'], sha(raw))
        host.secure(ROOT / 'config')
        path.parent.parent.mkdir(mode=0o700, exist_ok=True)
        host.secure(path.parent.parent)
        path.parent.mkdir(mode=0o700, exist_ok=True)
        host.secure(path.parent)
        new(path, raw)
        print(json.dumps({'status': 'PLAN_REVIEW_REQUIRED', 'plan_sha256': sha(raw), 'plan_path': str(path)}))
    else:
        print(json.dumps(apply(args.plan, args.approval_sha256), sort_keys=True))


if __name__ == '__main__':
    main()
