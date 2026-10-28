"""Opt-in Linux/WSL RSI provisioning; never controls the existing local app.

Run as Linux root for `prepare`. Keys stay in a newly created Linux directory.
`plan` is read-only; `start` checks static custody, starts only RSI daemons,
then reports actual doctor blockers. Neither command starts a session,
admits a child or activates one.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SCHEMA = 'ai4r-rsi-local:1'
NATIVE_SCHEMA = 'ai4r-rsi-local:2'
MODEL_SCHEMA = 'ai4r-rsi-local:3'
NATIVE_DOCKER_HOST = 'unix:///run/ai4r-rsi-docker/docker.sock'
DEFAULT_DOCKER_HOST = 'unix:///var/run/docker.sock'
NAME = re.compile(r'ai4r-rsi-[a-z0-9][a-z0-9-]{0,31}\Z')
IMAGE = re.compile(r'(?:sha256:[a-f0-9]{64}|[^\s@]+@sha256:[a-f0-9]{64})\Z')
KEY_ID = re.compile(r'[a-z][a-z0-9_.:-]{0,63}\Z')
# Host path, UID, GID, exact mode. No host account/credential tree is copied.
DIRECTORIES = {
    'config': (0, 0, 0o700),
    'controller': (12001, 12001, 0o700),
    'custodian': (12002, 12002, 0o700),
    'public': (12001, 13000, 0o2750),
    'requests': (12001, 13000, 0o2750),
    'inbox': (12002, 13000, 0o2750),
    'jobs-ipc': (12001, 12001, 0o700),
    'custodian-ipc': (12002, 12002, 0o710),
    'visible-ipc': (0, 12001, 0o710),
    'hidden-ipc': (0, 12002, 0o710),
    'visible-inputs': (12001, 12001, 0o700),
    'hidden-inputs': (12002, 12002, 0o700),
    'worker': (0, 0, 0o711),
    'security': (0, 13000, 0o750),
    'scope-ipc': (0, 13000, 0o710),
    'validation-control': (0, 0, 0o750),
    'validation-public': (0, 13000, 0o2750),
    'validation-evidence': (0, 13000, 0o2750),
    'validation-campaign': (0, 0, 0o700),
    'validation-custody': (12002, 12002, 0o700),
    'validation-ipc': (12002, 13000, 0o710),
}
ENV_PATHS = {
    'AI4R_RSI_CONTROLLER_CONFIG': 'config/jobs-service.json',
    'AI4R_RSI_CUSTODIAN_CONFIG': 'config/custodian-service.json',
    'AI4R_RSI_WORKER_CONFIG': 'config/broker-service.json',
    'AI4R_RSI_CONTROLLER_ROOT': 'controller',
    'AI4R_RSI_CUSTODIAN_ROOT': 'custodian',
    'AI4R_RSI_SIGNING_KEY': 'custodian/signing-key',
    'AI4R_RSI_INBOX_ROOT': 'inbox',
    'AI4R_RSI_PUBLIC_ROOT': 'public',
    'AI4R_RSI_REQUEST_ROOT': 'requests',
    'AI4R_RSI_JOB_IPC': 'jobs-ipc',
    'AI4R_RSI_CUSTODIAN_IPC': 'custodian-ipc',
    'AI4R_RSI_VISIBLE_WORKER_IPC': 'visible-ipc',
    'AI4R_RSI_HIDDEN_WORKER_IPC': 'hidden-ipc',
    'AI4R_RSI_VISIBLE_INPUT_ROOT': 'visible-inputs',
    'AI4R_RSI_HIDDEN_INPUT_ROOT': 'hidden-inputs',
    'AI4R_RSI_WORKER_ROOT': 'worker',
    'AI4R_RSI_SECURITY_ROOT': 'security',
    'AI4R_RSI_SECURITY_IPC': 'scope-ipc',
    'AI4R_RSI_VALIDATION_CONTROL': 'validation-control',
    'AI4R_RSI_VALIDATION_PUBLIC': 'validation-public',
    'AI4R_RSI_VALIDATION_CAMPAIGN': 'validation-campaign',
    'AI4R_RSI_VALIDATION_EVIDENCE': 'validation-evidence',
    'AI4R_RSI_VALIDATION_CUSTODY': 'validation-custody',
    'AI4R_RSI_VALIDATION_IPC': 'validation-ipc',
    'AI4R_RSI_VALIDATION_CUSTODIAN_CONFIG': 'config/validation-custodian.json',
}
MANIFEST_FIELDS = {'schema', 'root', 'project', 'images', 'key_id', 'cgroup_host'}
MODEL_FIELDS = MANIFEST_FIELDS | {'docker_host', 'model_backend', 'model_account_root'}
MODEL_BACKENDS = {
    'codex': {'account_root': '/var/lib/ai4r-rsi-model/profile',
              'environment': 'AI4R_RSI_MODEL_ACCOUNT_ROOT', 'overlay': 'compose.rsi.model.yaml'},
    'spark': {'account_root': '/var/lib/ai4r-rsi-spark/codex-profile',
              'environment': 'AI4R_RSI_SPARK_ACCOUNT_ROOT', 'overlay': 'compose.rsi.spark.yaml'},
    'host-codex': {'account_root': '/var/lib/ai4r-rsi-host-codex-client',
                   'environment': 'AI4R_RSI_HOST_CODEX_ACCOUNT_ROOT', 'overlay': 'compose.rsi.host-codex.yaml'},
}


def model_binding(value):
    """A saved closed choice selects one fixed private profile, never ambient state."""
    if value['schema'] != MODEL_SCHEMA:
        return None
    backend = value.get('model_backend')
    if (set(value) != MODEL_FIELDS or value.get('docker_host') != NATIVE_DOCKER_HOST or
            not isinstance(backend, str) or backend not in MODEL_BACKENDS):
        raise ValueError('Unknown finite model backend configuration')
    binding = MODEL_BACKENDS[backend]
    if value.get('model_account_root') != binding['account_root']:
        raise ValueError('Model account root differs from the fixed isolated backend')
    return binding


def model_helper(backend):
    import importlib.util
    if backend not in MODEL_BACKENDS:
        raise ValueError('Unknown finite model backend')
    source = HERE / {'codex': 'rsi_model.py', 'spark': 'rsi_spark.py', 'host-codex': 'rsi_host_codex.py'}[backend]
    spec = importlib.util.spec_from_file_location('ai4r_rsi_selected_model', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_model_backend(value):
    binding = model_binding(value)
    if binding is None:
        return
    require_root()
    helper = model_helper(value['model_backend'])
    if value['model_backend'] == 'codex':
        actual = helper.load_manifest('/var/lib/ai4r-rsi-model')
        if actual.get('profile') != binding['account_root']:
            raise ValueError('Protected isolated cloud model profile differs')
    else:
        # Metadata/custody only: never invoke status, SSH, authentication or inference.
        if value['model_backend'] == 'spark':
            actual = helper.load_profile()
            if actual.get('model') != 'Qwen3.8-27B-NVFP4':
                raise ValueError('Protected Spark model differs')
        else:
            actual = helper.load()
            model = actual['catalog']['models'][0]
            if model['model_name'] != 'gpt-6.1-sol' or model['reasoning_effort'] != 'medium':
                raise ValueError('Protected host Codex model differs')
        account = safe_path(binding['account_root'])
        linux_storage(account)
        protected_ancestry(account)
        meta = account.lstat()
        if not stat.S_ISDIR(meta.st_mode) or (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) != (12001, 12001, 0o700):
            raise ValueError('Isolated Spark profile directory custody differs')
        # Runtime-created workspace/config files are permitted on later starts.
        # Auth-bearing filenames (including dangling links) are never read/imported.
        home = safe_path(account / 'codex-home')
        if os.path.lexists(account / 'auth.json') or os.path.lexists(home / 'auth.json'):
            raise ValueError('Spark profile must contain no account authentication')


def native_host_status():
    # Fixed repository helper, never a manifest-selected module or callback.
    import importlib.util
    spec = importlib.util.spec_from_file_location('ai4r_rsi_native_host', HERE / 'rsi_host.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.status()


def validate_backend(value):
    if value['schema'] in {NATIVE_SCHEMA, MODEL_SCHEMA}:
        if value.get('docker_host') != NATIVE_DOCKER_HOST:
            raise ValueError('Unknown native Docker endpoint')
        require_root()
        actual = native_host_status()
        if (actual.get('status') != 'OBSERVED_NOT_QUALIFIED' or actual.get('socket') != NATIVE_DOCKER_HOST or
                actual.get('cgroup_root') != value['cgroup_host']):
            raise ValueError('Current native daemon and protected delegation do not match')


def safe_path(value):
    text = str(value)
    if (not text.startswith('/') or text.startswith('//') or '\\' in text or ':' in text or
            any(ord(c) < 32 for c in text) or '..' in Path(text).parts or
            re.match(r'^/(?:mnt|media)/[a-zA-Z](?:/|$)', text, re.I)):
        raise ValueError('Use an absolute protected Linux path, never a Windows drive or WSL drive mount')
    path = Path(text)
    if str(path) != text.rstrip('/') or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Canonical paths without symlinks are required')
    return path


def linux_storage(path):
    """Reject Windows/network filesystems even mounted under an innocent name."""
    if sys.platform != 'linux' or not hasattr(os, 'geteuid'):
        raise ValueError('Run this command inside Linux or WSL, not Windows Python')
    existing = path
    while not existing.exists():
        existing = existing.parent
    rows = []
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        fields, tail = line.split(' - ', 1)
        mount = fields.split()[4]
        mount = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), mount)
        if existing == Path(mount) or Path(mount) in existing.parents:
            rows.append((len(Path(mount).parts), tail.split()[0]))
    if not rows or max(rows)[1] not in {'ext4', 'xfs', 'btrfs', 'tmpfs', 'overlay', 'zfs'}:
        raise ValueError('Private state requires a native Linux filesystem (not drvfs/9p/network storage)')
    if any((p / '.git').exists() for p in (path, *path.parents)):
        raise ValueError('Private RSI state must be outside every Git checkout')


def require_root():
    if not hasattr(os, 'geteuid') or os.geteuid() != 0:
        raise ValueError('Use Linux root for exact protected directory and role ownership')


def protected_ancestry(path):
    # A writable parent could rename a safe directory and substitute a symlink
    # between provisioning operations. Root-owned sticky /tmp is safe for our
    # exclusively created, root-owned child and disposable tests.
    for parent in path.parents:
        if not parent.exists():
            continue
        meta = parent.stat()
        if meta.st_uid != 0 or meta.st_mode & 0o022 and not meta.st_mode & stat.S_ISVTX:
            raise ValueError('Private configuration ancestors require root custody')


def isolated_root(path):
    if (any(path == Path(base) or path.is_relative_to(base) for base in
            ('/opt/ai4r-local', '/var/lib/ai4r', '/var/lib/ai4r-accounts')) or
            any(part in {'.codex', '.ssh', '.aws'} for part in path.parts)):
        raise ValueError('RSI state must be outside the live app and existing credential/account roots')


def write_new(path, data, *, uid=0, gid=0, mode=0o600):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), mode)
    with os.fdopen(descriptor, 'wb') as stream:
        os.fchown(stream.fileno(), uid, gid)
        os.fchmod(stream.fileno(), mode)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def encoded(value):
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode() + b'\n'


def prepare(args):
    root = safe_path(args.root)
    isolated_root(root)
    linux_storage(root)
    require_root()
    protected_ancestry(root)
    if not NAME.fullmatch(args.project) or not KEY_ID.fullmatch(args.key_id):
        raise ValueError('Use an isolated ai4r-rsi-* project and a valid development key ID')
    images = {'app': args.app_image, 'rsi': args.image, 'worker': args.worker_image}
    if any(not IMAGE.fullmatch(v) for v in images.values()):
        raise ValueError('All three image references must have immutable sha256 digests')
    if root.exists() or not root.parent.is_dir():
        raise ValueError('Choose a fresh Linux directory with an existing parent; existing state is never replaced')
    cgroup = safe_path(args.cgroup_host) if args.cgroup_host else None
    if getattr(args, 'native_host', False):
        actual = native_host_status()
        native_cgroup = safe_path(actual['cgroup_root'])
        if cgroup is not None and cgroup != native_cgroup:
            raise ValueError('Native backend requires its actual separate bounded job delegation')
        cgroup = native_cgroup
        validate_backend({'schema': NATIVE_SCHEMA, 'docker_host': NATIVE_DOCKER_HOST, 'cgroup_host': str(cgroup)})
    if cgroup is not None and (not cgroup.is_relative_to('/sys/fs/cgroup') or cgroup == Path('/sys/fs/cgroup')):
        raise ValueError('Use a separately delegated bounded cgroup branch, never the cgroup root')
    selected_model = getattr(args, 'model_backend', None)
    if selected_model is not None:
        if not getattr(args, 'native_host', False) or selected_model not in MODEL_BACKENDS:
            raise ValueError('Explicit model backend selection requires the native isolated host')
        # Check independently prepared authoritative custody before provisioning.
        validate_model_backend({'schema': MODEL_SCHEMA, 'root': str(root), 'project': args.project,
            'images': images, 'key_id': args.key_id, 'cgroup_host': str(cgroup),
            'docker_host': NATIVE_DOCKER_HOST, 'model_backend': selected_model,
            'model_account_root': MODEL_BACKENDS[selected_model]['account_root']})
    # This contract contains no model credentials. Existing profile/evaluation
    # resolution is deliberately not fabricated here.
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    operator = OperatorConfiguration.load(args.operator_template).snapshot()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    operator['rsi'] = {'custodian_key_id': args.key_id,
                       'custodian_public_key': base64.urlsafe_b64encode(public).decode().rstrip('=')}
    OperatorConfiguration.from_mapping(operator)
    root.mkdir(mode=0o700)
    os.chown(root, 0, 0)
    os.chmod(root, 0o700)
    for relative, (uid, gid, mode) in DIRECTORIES.items():
        folder = root / relative
        folder.mkdir(mode=mode)
        os.chown(folder, uid, gid)
        os.chmod(folder, mode)
    write_new(root / 'custodian/signing-key', key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()), uid=12002, gid=12002)
    write_new(root / 'config/operator.json', encoded(operator))
    write_new(root / 'config/custodian-public.json', encoded(operator['rsi']))
    manifest = {'schema': SCHEMA, 'root': str(root), 'project': args.project, 'images': images,
                'key_id': args.key_id, 'cgroup_host': str(cgroup) if cgroup else None}
    if getattr(args, 'native_host', False):
        manifest.update(schema=NATIVE_SCHEMA, docker_host=NATIVE_DOCKER_HOST)
    if selected_model is not None:
        manifest.update(schema=MODEL_SCHEMA, model_backend=selected_model,
                        model_account_root=MODEL_BACKENDS[selected_model]['account_root'])
    # Publish last. Interrupted provisioning is retained for explicit cleanup;
    # a later prepare never overwrites or silently rotates the development key.
    write_new(root / 'local.json', encoded(manifest))
    return {'status': 'BLOCKED', 'manifest': str(root / 'local.json'),
            'operator_config': str(root / 'config/operator.json'),
            'reason': 'Development custody prepared; authoritative service/resource records, qualification and dedicated model access are not generated',
            'next': 'Independently prepare protected service configs and captures, then run plan'}


def protected_file(path, uid=0, *, private=True, gid=None):
    safe_path(path)
    meta = path.lstat()
    if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != uid or
            meta.st_mode & (0o077 if private else 0o022) or meta.st_size > 4 * 1024 * 1024 or
            gid is not None and meta.st_gid != gid):
        raise ValueError('Protected regular file custody differs')
    return path


def load_manifest(path):
    require_root()
    path = safe_path(path)
    linux_storage(path)
    protected_file(path)
    # A partial stopped-deployment repair is never a usable configuration.
    # Fixed sibling only; no record or browser input selects this code.
    import importlib.util
    repair_spec = importlib.util.spec_from_file_location('ai4r_rsi_stopped_repair', HERE / 'rsi_stopped_repair.py')
    repair = importlib.util.module_from_spec(repair_spec)
    repair_spec.loader.exec_module(repair)
    repair.verify_repair_complete(path.parent)
    successor_spec = importlib.util.spec_from_file_location('ai4r_rsi_bootstrap_supersession', HERE / 'rsi_bootstrap_supersession.py')
    successor = importlib.util.module_from_spec(successor_spec); successor_spec.loader.exec_module(successor)
    successor.verify_deployment_selections(path.parent)
    value = json.loads(path.read_bytes())
    if (not isinstance(value, dict) or
            not (value.get('schema') == SCHEMA and set(value) == MANIFEST_FIELDS or
                 value.get('schema') == NATIVE_SCHEMA and set(value) == MANIFEST_FIELDS | {'docker_host'} and
                 value.get('docker_host') == NATIVE_DOCKER_HOST or
                 value.get('schema') == MODEL_SCHEMA and set(value) == MODEL_FIELDS)):
        raise ValueError('Unknown finite local configuration')
    model_binding(value)
    root = safe_path(value['root'])
    isolated_root(root)
    protected_ancestry(root)
    if path != root / 'local.json' or not NAME.fullmatch(value['project']):
        raise ValueError('Local configuration root or project mismatch')
    if set(value['images']) != {'app', 'rsi', 'worker'} or any(not IMAGE.fullmatch(v) for v in value['images'].values()):
        raise ValueError('Immutable image references are required')
    if not KEY_ID.fullmatch(value['key_id']):
        raise ValueError('Invalid key identity')
    if value['cgroup_host'] is not None:
        cg = safe_path(value['cgroup_host'])
        if not cg.is_relative_to('/sys/fs/cgroup') or cg == Path('/sys/fs/cgroup'):
            raise ValueError('Invalid delegated cgroup path')
    return value


def environment(value):
    # Ignore ambient AI4R variables so an app profile/credential/root cannot
    # silently substitute for an explicitly prepared RSI role.
    env = {k: v for k, v in os.environ.items() if not k.startswith(('AI4R_', 'COMPOSE_', 'DOCKER_'))}
    root = Path(value['root'])
    env.update({name: str(root / relative) for name, relative in ENV_PATHS.items()})
    env.update({'AI4R_JOB_ID': value['project'], 'AI4R_APP_IMAGE': value['images']['app'],
                'AI4R_RSI_IMAGE': value['images']['rsi'], 'AI4R_RSI_WORKER_IMAGE': value['images']['worker'],
                'AI4R_RSI_CGROUP_HOST': value['cgroup_host'] or '/not-provisioned/rsi-cgroup',
                'AI4R_SECCOMP_PROFILE': str(HERE / 'seccomp/executor.json')})
    binding = model_binding(value)
    if binding is not None:
        env[binding['environment']] = binding['account_root']
    return env


def compose(value):
    # Existing finite topology is the single owner of role/mount separation.
    if value['schema'] not in {SCHEMA, NATIVE_SCHEMA, MODEL_SCHEMA}:
        raise ValueError('Unknown finite local configuration')
    binding = model_binding(value)
    native = value['schema'] in {NATIVE_SCHEMA, MODEL_SCHEMA}
    if native and value.get('docker_host') != NATIVE_DOCKER_HOST:
        raise ValueError('Unknown native Docker endpoint')
    command = ['docker', '--host', NATIVE_DOCKER_HOST if native else DEFAULT_DOCKER_HOST,
            'compose', '--project-name', value['project'], '--env-file', '/dev/null',
            '-f', str(HERE / 'compose.rsi.yaml'), '-f', str(HERE / 'compose.rsi.security.yaml'),
            '-f', str(HERE / 'compose.rsi.validation.yaml')]
    if native:
        command += ['-f', str(HERE / 'compose.rsi.native-host.yaml')]
    if binding is not None:
        command += ['-f', str(HERE / binding['overlay'])]
    return command + ['--profile', 'rsi']


def check_service_file(path, role, key_id):
    config = json.loads(path.read_bytes())
    common = {'schema', 'socket_path', 'allowed_peer_uids', 'record_root', 'binding_id', 'resource_binding_ref'}
    fields = common | ({'job_root', 'allowed_job_refs'} if role == 'jobs' else
        {'custody_root', 'request_root', 'signing_key_file', 'signer_key_id', 'fixture_manifest_ref', 'authorized_sessions'})
    if not isinstance(config, dict) or set(config) != fields or config['schema'] != 'ai4r-rsi-' + role + '-service:1' or config['binding_id'] != 'native-isolated-v1':
        raise ValueError('Unknown finite service config')
    pin = config['resource_binding_ref']
    if not isinstance(pin, dict) or set(pin) != {'id', 'sha256'} or not isinstance(pin['id'], str) or not re.fullmatch('[a-f0-9]{64}', pin['sha256']):
        raise ValueError('Missing immutable resource binding')
    prefix = '/var/lib/ai4r-rsi/' + ('controller' if role == 'jobs' else 'custodian')
    if not safe_path(config['record_root']).is_relative_to(prefix):
        raise ValueError('Record root escapes mounted role')
    if role == 'jobs':
        if not config['allowed_job_refs'] or config['socket_path'] != '/run/ai4r-rsi/jobs/jobs.sock' or not safe_path(config['job_root']).is_relative_to(prefix):
            raise ValueError('Exact authorized job binding absent')
        if not config['allowed_peer_uids'] or any(type(uid) is not int or uid in {10001, 10002, 10011, 12002, 12003} or uid < 0 for uid in config['allowed_peer_uids']):
            raise ValueError('Launcher peer UID is outside isolated role')
    elif (not config['authorized_sessions'] or config['allowed_peer_uids'] != [12001] or
            config['signing_key_file'] != '/run/ai4r-rsi/signing-key' or config['signer_key_id'] != key_id or
            not safe_path(config['custody_root']).is_relative_to(prefix) or
            config['request_root'] != '/var/lib/ai4r-rsi-requests' or
            config['socket_path'] != '/run/ai4r-rsi/custodian/custodian.sock'):
        raise ValueError('Independent custody binding differs')


def inspect(value):
    validate_backend(value)
    validate_model_backend(value)
    root = Path(value['root'])
    blockers = []
    if root.stat().st_uid != 0 or stat.S_IMODE(root.stat().st_mode) != 0o700:
        blockers.append('Local root must remain root-owned mode 0700')
    for relative, (uid, gid, mode) in DIRECTORIES.items():
        try:
            path = safe_path(root / relative)
            meta = path.stat()
            if not stat.S_ISDIR(meta.st_mode) or (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) != (uid, gid, mode):
                raise ValueError()
        except (ValueError, OSError):
            blockers.append('Role directory custody differs: ' + relative)
    try:
        key_path = protected_file(root / 'custodian/signing-key', 12002, gid=12002)
        if stat.S_IMODE(key_path.stat().st_mode) != 0o600:
            raise ValueError()
        # The private bytes never enter a result, log, environment or command.
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        public = Ed25519PrivateKey.from_private_bytes(key_path.read_bytes()).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        operator = json.loads(protected_file(root / 'config/operator.json').read_bytes())
        if operator.get('rsi') != {'custodian_key_id': value['key_id'], 'custodian_public_key': base64.urlsafe_b64encode(public).decode().rstrip('=')}:
            raise ValueError()
    except (ValueError, OSError):
        blockers.append('Development key custody or isolated operator public pin differs')
    # These files are captured by their real owners; prepare never manufactures
    # their refs, fixture calibration, admitted parent, budget or qualification.
    for relative, gid, mode in [('jobs-service.json', 12001, 0o440), ('custodian-service.json', 12002, 0o440), ('broker-service.json', 0, 0o600)]:
        try:
            path = protected_file(root / 'config' / relative, private=False, gid=gid)
            if stat.S_IMODE(path.stat().st_mode) != mode:
                raise ValueError()
            if relative != 'broker-service.json':
                check_service_file(path, 'jobs' if relative == 'jobs-service.json' else 'custodian', value['key_id'])
            else:
                config = json.loads(path.read_bytes())
                if (not isinstance(config, dict) or set(config) != {'schema', 'root', 'cgroup_root', 'public_roots', 'profile_refs', 'visible_port', 'hidden_port'} or
                        config['schema'] != 'ai4r-rsi-worker-service:1' or config['root'] != '/var/lib/ai4r-rsi-worker' or
                        config['cgroup_root'] != '/run/ai4r-rsi-cgroups' or not config['profile_refs'] or
                        '/run/ai4r-rsi-validation/public' not in config['public_roots']):
                    raise ValueError()
        except (ValueError, OSError):
            blockers.append('Missing protected authority config: ' + relative)
    try:
        path=protected_file(root/'validation-control/runtime.json',gid=0)
        if stat.S_IMODE(path.stat().st_mode)!=0o600:raise ValueError()
        config=json.loads(path.read_bytes())
        from jiuwenswarm.research_records.contracts import ContractData
        ContractData().validate('urn:ai4r:private:rsi-security-runtime-config:1',config)
    except (ValueError,OSError,KeyError,TypeError):
        blockers.append('Missing protected authority config: validation-control/runtime.json')
    cg = Path(value['cgroup_host']) if value['cgroup_host'] else None
    if cg is None or not cg.is_dir() or not (cg / 'cgroup.controllers').is_file():
        blockers.append('Separate bounded worker cgroup delegation is unavailable')
    return {'status': 'BLOCKED' if blockers else 'CONFIGURED', 'blockers': blockers,
            'readiness': 'Only the actual read-only RSI doctor can establish current readiness; generated configuration is not security evidence',
            'doctor_command': shlex.join(compose(value) + ['exec', '-T', 'rsi-workbench', 'python', '-m', 'jiuwenswarm.research_rsi', 'doctor', '--live']),
            'start_command': shlex.join(['python3', str(HERE / 'rsi_local.py'), '--manifest', str(root / 'local.json'), 'start']),
            'inbox_integration': {'overlay': str(HERE / 'compose.rsi-inbox.yaml'),
                'public_root': str(root / 'inbox'), 'operator_config': str(root / 'config/operator.json'),
                'status': 'Manual opt-in for a separately prepared app deployment; no app command is executed'}}


def start(value):
    result = inspect(value)
    if result['blockers']:
        return result
    command = compose(value)
    env = environment(value)
    check = subprocess.run(command + ['config', '--quiet'], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if check.returncode:
        return {**result, 'status': 'BLOCKED', 'blockers': ['Existing RSI compose configuration refused static preparation']}
    # Config/start performs no session dispatch. In-process qualification and
    # immutable job allowlists remain authoritative after this preflight.
    run = subprocess.run(command + ['up', '-d', '--no-build', '--pull', 'never', 'rsi-worker-broker', 'rsi-custodian', 'rsi-workbench'],
                         env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if run.returncode:
        raise ValueError('Isolated RSI daemon start failed; inspect the separate project privately')
    # Infrastructure must exist for authenticated operational checks; requiring
    # READY before launching its own daemons would deadlock startup. Doctor
    # reads only controller-visible authority. Never mount hidden custody here.
    check = subprocess.run(command + ['exec', '-T', 'rsi-workbench', 'python', '-m', 'jiuwenswarm.research_rsi', 'doctor', '--live'],
                           env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    try:
        report = json.loads(check.stdout)
        ready = check.returncode == 0 and report.get('status') == 'READY'
    except (ValueError, TypeError):
        ready = False
    return {'status': 'READY' if ready else 'BLOCKED', 'project': value['project'],
            'daemons_requested': True, 'session_started': False,
            'blockers': [] if ready else ['Actual RSI doctor has not established operational readiness; inspect protected authority, daemon health and real IF015 qualification'],
            'next': 'Human selects an exact authorized job only after actual readiness; admission and activation remain separate'}


def start_validation_custodian(value):
    """Explicit later step, after the running producer captures its exact plan."""
    validate_backend(value)
    require_root();root=Path(value['root']);linux_storage(root);protected_ancestry(root)
    from jiuwenswarm.research_records.contracts import ContractData
    path=protected_file(root/'config/validation-custodian.json',private=False,gid=13000)
    if stat.S_IMODE(path.stat().st_mode)!=0o640:raise ValueError('Root validation signing configuration custody differs')
    config=json.loads(path.read_bytes());ContractData().validate('urn:ai4r:private:rsi-validation-custody:1',config)
    public=json.loads(protected_file(root/'config/custodian-public.json').read_bytes())
    if (config['custodian_key_id']!=value['key_id'] or config['custodian_key_id']!=public['custodian_key_id']
            or config['custodian_public_key']!=public['custodian_public_key']):raise ValueError('Separate validation signer public pin differs')
    protected_file(root/'custodian/signing-key',uid=12002,gid=12002)
    for relative in ('validation-custody','validation-ipc','validation-evidence'):
        meta=safe_path(root/relative).stat();expected=DIRECTORIES[relative]
        if not stat.S_ISDIR(meta.st_mode) or (meta.st_uid,meta.st_gid,stat.S_IMODE(meta.st_mode))!=expected:raise ValueError('Validation role custody differs')
    command=compose(value)+['--profile','rsi-validation']
    run=subprocess.run(command+['up','-d','--no-build','--pull','never','--no-deps','rsi-validation-custodian'],
        env=environment(value),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if run.returncode:raise ValueError('Separate validation custodian start failed')
    return {'status':'STARTED_NOT_QUALIFIED','project':value['project'],'service':'rsi-validation-custodian',
        'session_started':False,'producer_restarted':False,'operational_ready':False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', default='/var/lib/ai4r-rsi-local/local.json')
    sub = parser.add_subparsers(dest='operation', required=True)
    p = sub.add_parser('prepare', help='Provision a fresh Linux development key and isolated directories; does not grant readiness')
    p.add_argument('--root', default='/var/lib/ai4r-rsi-local')
    p.add_argument('--project', default='ai4r-rsi-local')
    p.add_argument('--key-id', default='rsi-local-dev')
    p.add_argument('--operator-template', required=True, help='Complete separately captured operator-config with no unresolved evaluation profile')
    p.add_argument('--app-image', required=True)
    p.add_argument('--image', required=True)
    p.add_argument('--worker-image', required=True)
    p.add_argument('--cgroup-host')
    p.add_argument('--native-host', action='store_true', help='Pin the separately provisioned native RSI daemon and its verified bounded cgroup; preserve Docker Desktop')
    p.add_argument('--model-backend', choices=tuple(MODEL_BACKENDS),
                   help='Save an explicit isolated native model backend; requires its independently prepared protected profile and --native-host')
    sub.add_parser('plan', help='Read-only custody checks and explicit blockers')
    sub.add_parser('start', help='Check finite static configuration, start only isolated RSI daemons, then report actual doctor blockers')
    sub.add_parser('start-validation-custodian',help='Start only the separately approved finite validation signer; preserve the running producer')
    args = parser.parse_args(argv)
    try:
        handlers={'start':start,'plan':inspect,'start-validation-custodian':start_validation_custodian}
        result = prepare(args) if args.operation == 'prepare' else handlers[args.operation](load_manifest(args.manifest))
        print(json.dumps(result, sort_keys=True, indent=2))
        return 2 if result['status'] == 'BLOCKED' and args.operation != 'prepare' else 0
    except (ValueError, OSError, TypeError, KeyError, subprocess.TimeoutExpired):
        print(json.dumps({'status': 'BLOCKED', 'reason': 'Linux custody, finite configuration or an explicit prerequisite is unavailable; no authority inferred'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
