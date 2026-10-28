"""Finite, opt-in isolated subscription setup. Run with Linux/WSL root.

prepare creates an empty profile, login requires a human terminal, status only
reads existing authentication through the packaged runtime. No existing home or
credential tree is imported. Docker's selected context is never changed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = '/var/lib/ai4r-rsi-model'
IMAGE = 'sha256:806cb66c0e8fab9fbb6ea6dea87cf4c1c191b28b57b3a9cd2bb0ea3a3824f6d0'
# IMAGE is compatibility-only for already published v1 manifests.
ACCOUNT_ROOT = '/var/lib/ai4r-rsi/controller/accounts'
SCHEMA = 'ai4r-rsi-model:1'
SCHEMA_V2 = 'ai4r-rsi-model:2'
IMAGE_ID = re.compile(r'sha256:[0-9a-f]{64}\Z')
HELPER = '/run/rsi-model-client.py'

# Reuse the existing closed Linux path/custody checks without invoking its
# operator-config-dependent prepare operation.
_spec = importlib.util.spec_from_file_location('_rsi_model_paths', HERE / 'rsi_local.py')
_paths = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_paths)


def model_root(value):
    root = _paths.safe_path(value)
    if ',' in str(root):
        raise ValueError('Docker mount option separators are forbidden in model paths')
    _paths.isolated_root(root)
    forbidden = ('/home', '/root', '/run/user', '/var/lib/ai4r-rsi')
    if any(root == Path(p) or root.is_relative_to(p) for p in forbidden):
        raise ValueError('Model setup requires a separate fresh root outside live account and RSI service roots')
    _paths.linux_storage(root)
    _paths.protected_ancestry(root)
    return root


def manifest_for(root, *, image=None, docker_host=None):
    """No arguments describes legacy bytes; fresh prepare always supplies pins."""
    value = {'schema': SCHEMA, 'root': str(root), 'profile': str(root / 'profile'),
             'image': IMAGE, 'account_root': ACCOUNT_ROOT, 'uid': 12001, 'gid': 12001}
    if image is not None or docker_host is not None:
        if not isinstance(image, str) or not IMAGE_ID.fullmatch(image) or docker_host not in {
                _paths.DEFAULT_DOCKER_HOST, _paths.NATIVE_DOCKER_HOST}:
            raise ValueError('An immutable image ID and fixed reviewed Docker endpoint are required')
        value.update(schema=SCHEMA_V2, image=image, docker_host=docker_host)
    return value


def validate_manifest(value, root):
    if not isinstance(value, dict):
        raise ValueError('Unknown finite model configuration')
    if value.get('schema') == SCHEMA:
        expected = manifest_for(root)
    elif value.get('schema') == SCHEMA_V2:
        expected = manifest_for(root, image=value.get('image'), docker_host=value.get('docker_host'))
    else:
        raise ValueError('Unknown finite model configuration')
    if value != expected:
        raise ValueError('Unknown finite model configuration')
    return value


def require_native_host():
    actual = _paths.native_host_status()
    if actual.get('status') != 'OBSERVED_NOT_QUALIFIED' or actual.get('socket') != _paths.NATIVE_DOCKER_HOST:
        raise ValueError('Verified separate native Docker runtime is unavailable')


def prepare(root=DEFAULT_ROOT, *, image, native_host=False):
    _paths.require_root()
    root = model_root(root)
    if root.exists() or not root.parent.is_dir():
        raise ValueError('Choose a fresh Linux directory with an existing parent; existing state is never replaced')
    docker_host = _paths.NATIVE_DOCKER_HOST if native_host else _paths.DEFAULT_DOCKER_HOST
    value = manifest_for(root, image=image, docker_host=docker_host)
    if native_host:
        require_native_host()
    root.mkdir(mode=0o700)
    os.chown(root, 0, 0)
    os.chmod(root, 0o700)
    profile = root / 'profile'
    profile.mkdir(mode=0o700)
    os.chown(profile, 12001, 12001)
    os.chmod(profile, 0o700)
    _paths.write_new(root / 'model.json', _paths.encoded(value))
    return {'state': 'prepared', 'manifest': str(root / 'model.json'),
            'account_root': str(profile), 'image': value['image'], 'docker_host': value['docker_host']}


def load_manifest(root=DEFAULT_ROOT):
    _paths.require_root()
    root = model_root(root)
    for path, uid, gid in ((root, 0, 0), (root / 'profile', 12001, 12001)):
        meta = path.lstat()
        if not stat.S_ISDIR(meta.st_mode) or (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) != (uid, gid, 0o700):
            raise ValueError('Model directory custody differs')
    path = root / 'model.json'
    _paths.protected_file(path, gid=0)
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError('Model manifest mode differs')
    value = json.loads(path.read_bytes())
    return validate_manifest(value, root)


def environment(source=None):
    # No model/provider credentials or container overrides reach Docker. Docker
    # uses the native WSL socket explicitly; no global Docker context is changed.
    source = os.environ if source is None else source
    allowed = {'PATH', 'HOME', 'LANG', 'LC_ALL', 'TERM'}
    return {key: value for key, value in source.items() if key in allowed}


def docker_command(value, operation):
    if operation not in {'login', 'status'}:
        raise ValueError('Unknown finite model operation')
    validate_manifest(value, Path(value['root']))
    helper = HERE / 'rsi_model_client.py'
    if helper.is_symlink() or not helper.is_file() or ',' in str(helper):
        raise ValueError('Public model helper must be a regular file')
    docker_host = value.get('docker_host', _paths.DEFAULT_DOCKER_HOST)
    command = ['docker', '--host', docker_host, 'run', '--rm', '--pull', 'never', '--init']
    if docker_host == _paths.NATIVE_DOCKER_HOST:
        # The private daemon deliberately creates no bridge or NAT rules.
        # Cloud device authentication uses existing host egress only.
        command += ['--network', 'host']
    if operation == 'login':
        command += ['-it']
    command += ['--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                '--user', '12001:12001', '--pids-limit', '64', '--memory', '512m', '--cpus', '1',
                '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,uid=12001,gid=12001,mode=700',
                '--mount', f"type=bind,src={value['profile']},dst={ACCOUNT_ROOT}",
                '--mount', f'type=bind,src={helper},dst={HELPER},readonly',
                '--workdir', ACCOUNT_ROOT, '--env', f'HOME={ACCOUNT_ROOT}',
                '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'JIUWENSWARM_M1_PROFILE=1',
                '--entrypoint', '/opt/venv/bin/python', value['image'], HELPER, operation]
    return command


def _client_module():
    spec = importlib.util.spec_from_file_location('_rsi_model_public_summary', HERE / 'rsi_model_client.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_summary(root=DEFAULT_ROOT):
    """Read only the bounded sanitized snapshot; never inspect authentication."""
    value = load_manifest(root)
    path = Path(value['profile']) / 'setup-status.json'
    _paths.protected_file(path, uid=12001, gid=12001)
    if path.stat().st_size > 32768 or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError('Invalid model summary custody')
    result = json.loads(path.read_bytes())
    if not _client_module().valid_summary(result):
        raise ValueError('Invalid model summary')
    return result


def operate(operation, root=DEFAULT_ROOT):
    value = load_manifest(root)
    if value.get('docker_host') == _paths.NATIVE_DOCKER_HOST:
        require_native_host()
    if operation == 'login':
        if not all(stream.isatty() for stream in (sys.stdin, sys.stdout, sys.stderr)):
            raise ValueError('Login requires a visible human terminal; device codes must never enter captured logs')
        # Intentionally inherited descriptors, never PIPE, tee, or a log file.
        result = subprocess.run(docker_command(value, operation), env=environment(), timeout=1050)
    else:
        # The helper writes its sanitized result privately. Even an unexpected
        # container traceback or daemon response must not escape to public logs.
        result = subprocess.run(docker_command(value, operation), env=environment(),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    if result.returncode:
        raise ValueError('Isolated model operation failed; no authentication details were collected')
    return safe_summary(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'login', 'status', 'summary'))
    parser.add_argument('--root', default=DEFAULT_ROOT)
    parser.add_argument('--image', help='Fresh prepare requires the exact immutable sha256 controller image ID already loaded in the selected daemon')
    parser.add_argument('--native-host', action='store_true', help='Fresh prepare pins the independently verified native RSI Docker socket')
    args = parser.parse_args(argv)
    if args.operation == 'prepare' and args.image is None:
        parser.error('prepare requires --image sha256:<64 lowercase hex characters>')
    if args.operation != 'prepare' and (args.image is not None or args.native_host):
        parser.error('image and backend are saved at prepare; later operations accept no override')
    try:
        result = (prepare(args.root, image=args.image, native_host=args.native_host) if args.operation == 'prepare' else
                  safe_summary(args.root) if args.operation == 'summary' else operate(args.operation, args.root))
    except (ValueError, OSError, subprocess.SubprocessError):
        print(json.dumps({'state': 'unavailable', 'error': 'MODEL_SETUP_FAILED'}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
