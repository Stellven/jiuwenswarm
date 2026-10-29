"""Finite native-host security bootstrap preparation, never case approval.

probe reads actual host/kernel/image facts only. prepare accepts an explicitly
supplied original metadata closure; absent real thirteen-case bindings it writes
nothing. Worker startup, signing, approval, campaign and publication remain
distinct operations on the same live producer.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys

HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = '/var/lib/ai4r-rsi-codex/local.json'
CASES = tuple('RSIV-' + str(number) for number in range(1, 14))
INPUT_SCHEMA = 'ai4r-rsi-security-setup-input:1'
PUBLIC = '/var/lib/ai4r-rsi-public'
VALIDATION_PUBLIC = '/run/ai4r-rsi-validation/public'
WORKER_ROOT = '/var/lib/ai4r-rsi-worker'
CGROUP_ROOT = '/run/ai4r-rsi-cgroups'
PHASES = frozenset({'draft', 'final'})
PHASE_ROOTS = {
    'worker': ('AI4R_RSI_WORKER_ROOT', 0, 0, 0o711),
    'visible-ipc': ('AI4R_RSI_VISIBLE_WORKER_IPC', 0, 12001, 0o710),
    'hidden-ipc': ('AI4R_RSI_HIDDEN_WORKER_IPC', 0, 12002, 0o710),
    'security': ('AI4R_RSI_SECURITY_ROOT', 0, 13000, 0o750),
    'scope-ipc': ('AI4R_RSI_SECURITY_IPC', 0, 13000, 0o710),
    'validation-control': ('AI4R_RSI_VALIDATION_CONTROL', 0, 0, 0o750),
    'validation-public': ('AI4R_RSI_VALIDATION_PUBLIC', 0, 13000, 0o2750),
    'validation-campaign': ('AI4R_RSI_VALIDATION_CAMPAIGN', 0, 0, 0o700),
    'validation-evidence': ('AI4R_RSI_VALIDATION_EVIDENCE', 0, 13000, 0o2750),
    'validation-custody': ('AI4R_RSI_VALIDATION_CUSTODY', 12002, 12002, 0o700),
    'validation-ipc': ('AI4R_RSI_VALIDATION_IPC', 12002, 13000, 0o710),
}


def sibling(name):
    spec = importlib.util.spec_from_file_location('_security_setup_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


local = sibling('rsi_local')
host = sibling('rsi_host')


class SetupUnavailable(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def need(value, code='SECURITY_SETUP_METADATA_UNAVAILABLE'):
    if not value:
        raise SetupUnavailable(code)


def _json(raw):
    def pairs(rows):
        value = {}
        for key, item in rows:
            need(key not in value); value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_METADATA')))


def protected_json(path, *, maximum=1024 * 1024):
    local.require_root()
    path = local.safe_path(path)
    local.protected_ancestry(path)
    local.protected_file(path, gid=0)
    meta = path.stat()
    need(stat.S_IMODE(meta.st_mode) == 0o600 and meta.st_nlink == 1 and 0 < meta.st_size <= maximum)
    return _json(path.read_bytes())


def load(path=DEFAULT_MANIFEST):
    value = local.load_manifest(path)
    need(value.get('docker_host') == host.SOCKET and value.get('cgroup_host') == str(host.CG / 'jobs'),
         'SEPARATE_NATIVE_HOST_REQUIRED')
    return value


def _read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def probe(manifest=DEFAULT_MANIFEST):
    """No namespace creation, daemon start, cgroup write or executable probe."""
    value = load(manifest)
    actual = host.status()
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(444, 0, 0, 1) if platform.machine().lower() in {'x86_64', 'aarch64'} else -1
    error = ctypes.get_errno() if abi < 0 else None
    image = _json(host.run(['/usr/bin/docker', '--host', host.SOCKET, 'image', 'inspect', value['images']['worker']]))
    need(isinstance(image, list) and len(image) == 1 and isinstance(image[0], dict))
    image = image[0]
    identities = {image.get('Id')}
    identities.update(row.rsplit('@', 1)[-1] for row in image.get('RepoDigests') or [])
    need(value['images']['worker'].rsplit('@', 1)[-1] in identities, 'WORKER_IMAGE_IDENTITY_DIFFERS')
    cg = Path(actual['cgroup_root'])
    return {'schema': 'ai4r-rsi-security-host-probe:1', 'status': 'OBSERVED_NOT_QUALIFIED',
        'kernel_release': platform.release(), 'architecture': platform.machine(),
        'landlock_abi': abi if abi >= 0 else None, 'landlock_query_errno': error,
        'user_namespace_limit': _read('/proc/sys/user/max_user_namespaces'),
        'unprivileged_userns_clone': _read('/proc/sys/kernel/unprivileged_userns_clone'),
        'cgroup_controllers': _read(cg / 'cgroup.controllers'),
        'cgroup_subtree_control': _read(cg / 'cgroup.subtree_control'),
        'bounded_host': {key: actual[key] for key in ('socket', 'cgroup_root', 'memory_max', 'pids_max', 'cpu_max')},
        'worker_image': {'id': image['Id'], 'platform': image['Os'] + '/' + image['Architecture']},
        'not_established': ['worker_namespace_execution', 'case_observations', 'security_qualification', 'host_producer_identity']}


def _ref(value):
    need(isinstance(value, dict) and set(value) == {'id', 'sha256'} and isinstance(value['id'], str) and value['id'])
    need(isinstance(value['sha256'], str) and len(value['sha256']) == 64
         and all(c in '0123456789abcdef' for c in value['sha256']))
    return value


def _original(root, pin):
    """Read only an explicitly nominated indexed public original; no recursion."""
    _ref(pin)
    index_path = root / 'original-byte-index.json'
    local.safe_path(index_path)
    meta = index_path.lstat()
    need(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1 and not meta.st_mode & 0o022
         and 0 < meta.st_size <= 4 * 1024 * 1024)
    index = _json(index_path.read_bytes())
    need(isinstance(index, dict) and index.get('schema') == 'ai4r-original-bytes:1'
         and index.get('refs', {}).get(pin['id']) == pin['sha256'])
    path = local.safe_path(root / (pin['sha256'] + '.bytes'))
    meta = path.lstat()
    need(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1 and not meta.st_mode & 0o022
         and 0 <= meta.st_size <= 4 * 1024 * 1024)
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == pin['sha256'])
    return raw


def runtime_input(value, public_root, key_pin):
    """Validate source identities before generating any capability or config."""
    need(isinstance(value, dict) and set(value) == {'schema', 'runtime', 'additional_profile_refs'}
         and value['schema'] == INPUT_SCHEMA)
    runtime = value['runtime']
    need(isinstance(runtime, dict) and set(runtime) == {'schema', 'campaign_root', 'custodian_public_key',
        'custodian_key_id', 'case_bindings', 'environment_ref', 'originals'})
    need(runtime['schema'] == 'ai4r-rsi-security-runtime-config:1'
         and runtime['campaign_root'] == '/var/lib/ai4r-rsi-validation-campaign'
         and {name: runtime[name] for name in key_pin} == key_pin)
    _ref(runtime['environment_ref'])
    bindings = runtime['case_bindings']
    need(isinstance(bindings, dict) and set(bindings) == set(CASES))
    sessions = set(); profiles = []
    for case in CASES:
        row = bindings[case]
        need(isinstance(row, dict) and set(row) == {'session_ref', 'worker_profile_ref'})
        _ref(row['session_ref']); _ref(row['worker_profile_ref'])
        need(json.dumps(row['session_ref'], sort_keys=True) not in sessions)
        sessions.add(json.dumps(row['session_ref'], sort_keys=True))
        profiles.append(row['worker_profile_ref'])
    need(isinstance(value['additional_profile_refs'], list) and len(value['additional_profile_refs']) <= 87)
    profiles += [_ref(pin) for pin in value['additional_profile_refs']]
    need(len({json.dumps(pin, sort_keys=True) for pin in profiles}) == len(profiles))
    originals = runtime['originals']
    need(isinstance(originals, list) and 0 < len(originals) <= 2048)
    original_rows = {}; total = 0
    for row in originals:
        need(isinstance(row, dict) and set(row) == {'ref', 'kind'})
        pin = _ref(row['ref']); need(pin['id'] not in original_rows)
        need(row['kind'] in {None, 'capsule-declaration', 'rsi-session', 'rsi-target-profile', 'rsi-worker-profile'})
        raw = _original(public_root, pin); total += len(raw); need(total <= 128 * 1024 * 1024)
        original_rows[pin['id']] = (row, raw)
    # The installed source validators are authoritative. This host helper does
    # not maintain a permissive parallel copy of capsule/session policy.
    from jiuwenswarm.research.contracts import validate
    from jiuwenswarm.research_rsi.session_policy import validate_private
    from jiuwenswarm.research_rsi.worker import validate_profile
    validate_private('urn:ai4r:private:rsi-security-runtime-config:1', runtime)
    for row, raw in original_rows.values():
        if row['kind'] == 'rsi-worker-profile':
            validate_profile(_json(raw))
        elif row['kind'] is not None:
            validate(row['kind'], _json(raw))
    def original(pin, kind=None):
        row, raw = original_rows[pin['id']]
        need(row['ref'] == pin and (kind is None or row['kind'] == kind))
        return _json(raw)
    original(runtime['environment_ref'])
    for pin in profiles:
        profile = original(pin, 'rsi-worker-profile')
        need(profile.get('schema') == 'ai4r-rsi-worker-profile:3'
             and profile.get('process_policy') == 'single_process_seccomp_v1'
             and profile.get('environment_ref') == runtime['environment_ref'])
        session = original(profile['session_ref'], 'rsi-session')
        target = original(profile['target_ref'], 'rsi-target-profile')
        need(session['target_profile_ref'] == profile['target_ref'] and target['parent_ref'] == profile['parent_ref'])
    for case in CASES:
        row = bindings[case]
        need(original(row['worker_profile_ref'], 'rsi-worker-profile')['session_ref'] == row['session_ref'])
    return runtime, profiles


def phase_paths(value, phase):
    need(phase in PHASES, 'UNKNOWN_FINITE_SECURITY_PHASE')
    root = Path(value['root'])
    # Draft custody stays entirely outside final standard role roots. This
    # leaves final campaign_root empty without moving/deleting original work.
    repair = sibling('rsi_stopped_repair')
    generation = repair.phase_generation(value)
    draft_name = 'draft.' + generation if generation is not None else 'draft'
    prefix = root / 'security-phases' / draft_name if phase == 'draft' else root
    paths = {name: prefix / name for name in PHASE_ROOTS}
    suffix = ('-draft.' + generation if generation is not None else '-draft') if phase == 'draft' else ''
    paths['broker-config'] = root / 'config' / ('broker-service' + suffix + '.json')
    paths['custodian-config'] = root / 'config' / ('validation-custodian' + suffix + '.json')
    return paths


def prepare_validation_mountpoint(control):
    """Precreate the empty child hidden by the nested public bind mount.

    runc cannot create this target after its parent is mounted read-only. No
    publication, approval, process or campaign state is created here.
    """
    local.require_root()
    control=local.safe_path(control);local.protected_ancestry(control)
    meta=control.lstat()
    need(stat.S_ISDIR(meta.st_mode) and (meta.st_uid,meta.st_gid,stat.S_IMODE(meta.st_mode))==(0,0,0o750),
         'VALIDATION_CONTROL_CUSTODY_DIFFERS')
    target=control/'public'
    if not os.path.lexists(target):
        target.mkdir(mode=0o755)
        os.chown(target,0,0);os.chmod(target,0o755)
    meta=target.lstat()
    need(stat.S_ISDIR(meta.st_mode) and (meta.st_uid,meta.st_gid,stat.S_IMODE(meta.st_mode))==(0,0,0o755)
         and not any(target.iterdir()),'VALIDATION_MOUNTPOINT_MUST_BE_ROOT_OWNED_AND_EMPTY')
    directory=os.open(control,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)
    return target


def prepare(input_path, *, manifest=DEFAULT_MANIFEST, phase='draft'):
    """Write fresh root configs only; never approve or start a producer."""
    value = load(manifest); root = Path(value['root'])
    input_path = local.safe_path(input_path)
    need(input_path.parent == root / 'config', 'ROOT_CONFIG_METADATA_INPUT_REQUIRED')
    paths = phase_paths(value, phase)
    need(not paths['broker-config'].exists() and not paths['custodian-config'].exists()
         and not (paths['validation-control'] / 'runtime.json').exists(), 'EXISTING_PHASE_REQUIRES_INSPECTION')
    if phase == 'draft':
        need(not paths['worker'].parent.exists(), 'EXISTING_PHASE_REQUIRES_INSPECTION')
    else:
        for name, (_, uid, gid, mode) in PHASE_ROOTS.items():
            path = local.safe_path(paths[name]); meta = path.lstat()
            need(stat.S_ISDIR(meta.st_mode) and (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) == (uid, gid, mode)
                 and not any(path.iterdir()), 'FINAL_ROLE_STATE_REQUIRES_INSPECTION')
    raw_key_pin = protected_json(root / 'config/custodian-public.json')
    need(set(raw_key_pin) == {'custodian_key_id', 'custodian_public_key'}
         and raw_key_pin['custodian_key_id'] == value['key_id'])
    runtime, profiles = runtime_input(protected_json(input_path), root / 'public', raw_key_pin)
    environment = _json(_original(root / 'public', runtime['environment_ref']))
    need(environment.get('image_digest') == value['images']['worker'].rsplit('@', 1)[-1]
         and environment.get('platform') in {'linux/amd64', 'linux/arm64'}, 'ORIGINAL_WORKER_IMAGE_BINDING_DIFFERS')
    # Each phase has fresh process/campaign/socket custody. A restart cannot
    # quietly adopt another phase's pending driver or original outcome.
    import secrets
    ports = {}
    for role in ('visible', 'hidden'):
        ports[role + '_port'] = {'schema': 'ai4r-rsi-worker-port:1',
            'socket_path': '/run/ai4r-rsi-worker/' + role + '/worker.sock',
            'session_id': value['project'] + '-' + phase + '-' + role, 'capability': secrets.token_urlsafe(32),
            'input_roots': ['/var/lib/ai4r-rsi-inputs/' + role]}
    broker = {'schema': 'ai4r-rsi-worker-service:1', 'root': WORKER_ROOT,
        'cgroup_root': CGROUP_ROOT, 'public_roots': [PUBLIC, VALIDATION_PUBLIC],
        'profile_refs': profiles, **ports}
    if phase == 'draft':
        phases = root / 'security-phases'
        if phases.exists():
            meta = phases.lstat()
            need(stat.S_ISDIR(meta.st_mode) and (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) == (0, 0, 0o700))
        else:
            phases.mkdir(mode=0o700)
            os.chown(phases, 0, 0)
            os.chmod(phases, 0o700)
        parent = paths['worker'].parent; parent.mkdir(mode=0o700)
        os.chown(parent, 0, 0); os.chmod(parent, 0o700)
        for name, (_, uid, gid, mode) in PHASE_ROOTS.items():
            path = local.safe_path(paths[name])
            path.mkdir(mode=mode)
            os.chown(path, uid, gid)
            os.chmod(path, mode)
    prepare_validation_mountpoint(paths['validation-control'])
    local.write_new(paths['broker-config'], local.encoded(broker))
    local.write_new(paths['validation-control'] / 'runtime.json', local.encoded(runtime))
    return {'schema': 'ai4r-rsi-security-setup-status:1', 'status': 'PREPARED_NOT_STARTED',
        'phase': phase, 'broker_config': str(paths['broker-config']),
        'runtime_config': str(paths['validation-control'] / 'runtime.json'),
        'case_count': len(CASES), 'profile_count': len(profiles),
        'next': 'Review exact launch command with Root; retain producer through capture, separate approval, campaign and publication.'}


def launch_plan(*, manifest=DEFAULT_MANIFEST, phase='draft'):
    """Return finite reviewable command/path overrides, never invoke Docker."""
    value = load(manifest)
    paths = phase_paths(value, phase)
    protected_json(paths['broker-config'])
    protected_json(paths['validation-control'] / 'runtime.json')
    need(not (paths['validation-control'] / 'approval.json').exists()
         and not (paths['validation-control'] / 'publication-approval.json').exists(),
         'EXISTING_APPROVAL_REQUIRES_ORIGINAL_OWNER')
    need(not any(paths['validation-campaign'].iterdir()), 'EXISTING_CAMPAIGN_REQUIRES_ORIGINAL_OWNER')
    overrides = {row[0]: str(paths[name]) for name, row in PHASE_ROOTS.items()}
    overrides.update(AI4R_RSI_WORKER_CONFIG=str(paths['broker-config']),
                     AI4R_RSI_VALIDATION_CUSTODIAN_CONFIG=str(paths['custodian-config']))
    environment = {key: item for key, item in local.environment(value).items() if key.startswith('AI4R_')}
    environment.update(overrides)
    command = local.compose(value)
    command[0] = '/usr/bin/docker'
    return {'schema': 'ai4r-rsi-security-launch-plan:1', 'status': 'REVIEW_REQUIRED', 'phase': phase,
        'command': command + ['up', '--detach', '--no-deps', '--no-build', '--pull', 'never', 'rsi-worker-broker'],
        'environment': environment, 'environment_overrides': overrides,
        'effects': 'Only a metadata-waiting producer; all case/publication approval files must remain absent.',
        'prohibitions': ['No restart after capture', 'No automatic signer start', 'No case or publication approval generated']}


def prepare_signer(plan_ref, *, manifest=DEFAULT_MANIFEST, phase='draft'):
    """Root invokes after reviewing the captured plan; no worker approval."""
    value = load(manifest); paths = phase_paths(value, phase); _ref(plan_ref)
    need(not paths['custodian-config'].exists(), 'EXISTING_SIGNER_REQUIRES_ORIGINAL_OWNER')
    need(not (paths['validation-control'] / 'approval.json').exists(), 'WORKER_APPROVAL_ALREADY_PRESENT')
    from jiuwenswarm.research_rsi.worker import PublicBytes
    from jiuwenswarm.research_rsi.session_policy import validate_private
    public = PublicBytes([paths['validation-public']])
    plan = _json(public.read(plan_ref))
    validate_private('urn:ai4r:private:rsi-security-campaign-plan:1', plan)
    runtime = protected_json(paths['validation-control'] / 'runtime.json')
    need(plan['case_bindings'] == runtime['case_bindings'], 'CAPTURED_PLAN_DIFFERS_FROM_PREPARED_INPUT')
    _ref(plan['verification_profile_ref'])
    pins = _json(public.read(plan['verification_profile_ref']))
    validate_private('urn:ai4r:private:rsi-security-profile-pins:1', pins)
    scope = _json(public.read(plan['scope_ref']))
    validate_private('urn:ai4r:private:rsi-security-scope:1', scope)
    observed = protected_json(paths['validation-control'] / 'runtime-observation.json')
    validate_private('urn:ai4r:private:rsi-runtime-observation:1', observed)
    need(all(observed[name] == scope[name] for name in ('runtime_build_ref', 'environment_ref', 'worker_profile_refs')),
         'CURRENT_HOST_CAPTURE_DIFFERS_FROM_PLAN')
    key_pin = protected_json(Path(value['root']) / 'config/custodian-public.json')
    need(all(runtime[name] == key_pin[name] for name in ('custodian_key_id', 'custodian_public_key')))
    import secrets
    config = {'schema': 'ai4r-rsi-validation-custody:1', 'plan_ref': plan_ref, 'scope_ref': plan['scope_ref'],
        'attack_pins_ref': pins['attack_pins_ref'], **key_pin,
        'rpc_session_id': 'rsi-validation-' + phase + '-' + plan_ref['sha256'][:12],
        'rpc_capability': secrets.token_urlsafe(32)}
    validate_private('urn:ai4r:private:rsi-validation-custody:1', config)
    local.write_new(paths['custodian-config'], local.encoded(config), gid=13000, mode=0o640)
    return {'status': 'SIGNER_CONFIGURED_NOT_STARTED', 'phase': phase, 'plan_ref': plan_ref,
        'config': str(paths['custodian-config']), 'worker_approval_created': False, 'private_key_read': False}


def signer_launch_plan(*, manifest=DEFAULT_MANIFEST, phase='draft'):
    value = load(manifest); paths = phase_paths(value, phase)
    local.protected_file(paths['custodian-config'], private=False, gid=13000)
    need(stat.S_IMODE(paths['custodian-config'].stat().st_mode) == 0o640)
    need(not (paths['validation-control'] / 'approval.json').exists(), 'WORKER_APPROVAL_ALREADY_PRESENT')
    overrides = {row[0]: str(paths[name]) for name, row in PHASE_ROOTS.items()}
    overrides.update(AI4R_RSI_WORKER_CONFIG=str(paths['broker-config']),
                     AI4R_RSI_VALIDATION_CUSTODIAN_CONFIG=str(paths['custodian-config']))
    environment = {key: item for key, item in local.environment(value).items() if key.startswith('AI4R_')}
    environment.update(overrides)
    command = local.compose(value); command[0] = '/usr/bin/docker'
    return {'status': 'REVIEW_REQUIRED', 'phase': phase,
        'command': command + ['--profile', 'rsi-validation', 'up', '--detach', '--no-deps', '--no-build',
                              '--pull', 'never', 'rsi-validation-custodian'],
        'environment': environment, 'producer_restarted': False,
        'effects': 'Only the dedicated UID12002 finite signer; worker case approval remains absent.'}


def observe_current(container_id, scope_ref, *, manifest=DEFAULT_MANIFEST, phase='draft'):
    """Host-only actual observation under rsi_host.observe's private socket bind."""
    value = load(manifest); host.status()
    paths = phase_paths(value, phase)
    need(isinstance(container_id, str) and re.fullmatch('[a-f0-9]{64}', container_id))
    _ref(scope_ref)
    native = Path('/run/ai4r-rsi-docker/docker.sock').stat()
    mapped = Path('/run/docker.sock').stat()
    need(stat.S_ISSOCK(mapped.st_mode) and (mapped.st_ino, mapped.st_dev) == (native.st_ino, native.st_dev),
         'USE_PRIVATE_NATIVE_OBSERVER_NAMESPACE')
    container = _json(host.run(['/usr/bin/docker', '--host', host.SOCKET, 'container', 'inspect', container_id]))
    need(isinstance(container, list) and len(container) == 1)
    labels = container[0].get('Config', {}).get('Labels', {})
    need(labels.get('com.docker.compose.project') == value['project']
         and labels.get('com.docker.compose.service') == 'rsi-worker-broker', 'CURRENT_OWNED_PRODUCER_REQUIRED')
    from jiuwenswarm.research_rsi.worker import PublicBytes
    from jiuwenswarm.research_rsi.security_scope import build_runtime_observation
    public = PublicBytes([paths['validation-public']])
    scope = _json(public.read(scope_ref))
    actual = build_runtime_observation(container_id=container_id, approved_scope=scope, public_reader=public)
    output = paths['validation-control'] / 'runtime-observation.json'
    local.write_new(output, local.encoded(actual))
    return {'schema': 'ai4r-rsi-security-host-observation-status:1', 'status': 'OBSERVED_NOT_QUALIFIED',
        'phase': phase, 'container_id': container_id, 'scope_ref': scope_ref,
        'image_digest': actual['image_digest'], 'observation_file': str(output)}


def observer_source_digest(root):
    """Pin the fixed public Python/schema closure without reading private data."""
    root = Path(root)
    paths = [root / 'jiuwenswarm/__init__.py']
    for prefix in ('research', 'research_rsi', 'research_records', 'research_contracts'):
        paths += [p for p in (root / 'jiuwenswarm' / prefix).rglob('*')
                  if p.is_file() and p.suffix in {'.py', '.json'}]
    rows = []
    for path in sorted(paths):
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('OBSERVER_SOURCE_SYMLINK')
        meta = path.stat()
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or meta.st_size > 16 * 1024 * 1024:
            raise ValueError('OBSERVER_SOURCE_NOT_REGULAR')
        rows.append([path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()])
    if not rows:
        raise ValueError('OBSERVER_SOURCE_UNAVAILABLE')
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def observer_adapter():
    """Isolated fixed child composition; rsi_host's sanitized ENV stays intact."""
    import inspect
    source_root = HERE.parents[1]
    script = Path(__file__).resolve()
    code = ('import hashlib,json,os,runpy,stat,sys\nfrom pathlib import Path\n'
            + inspect.getsource(observer_source_digest)
            + '\nroot=Path(' + repr(str(source_root)) + ')\nscript=Path(' + repr(str(script)) + ')\n'
            + 'deps=Path("/opt/ai4r-rsi-host-codex/site-packages")\n'
            + 'assert root.is_absolute() and script.is_file() and not script.is_symlink()\n'
            + 'assert script.stat().st_nlink==1 and hashlib.sha256(script.read_bytes()).hexdigest()=='
            + repr(hashlib.sha256(script.read_bytes()).hexdigest()) + '\n'
            + 'assert observer_source_digest(root)==' + repr(observer_source_digest(source_root)) + '\n'
            + 'for path in (deps,*deps.parents):\n'
            + ' assert not path.is_symlink() and path.is_dir() and path.stat().st_uid==0 and not path.stat().st_mode&0o022\n'
            + 'sys.path[:0]=[str(root),str(deps)]\n'
            + 'sys.argv=[str(script),*sys.argv[1:]]\nrunpy.run_path(str(script),run_name="__main__")\n')
    return ['/usr/bin/python3', '-I', '-B', '-c', code]


def observation_plan(container_id, scope_ref, *, manifest=DEFAULT_MANIFEST, phase='draft'):
    value = load(manifest)
    phase_paths(value, phase)
    need(isinstance(container_id, str) and re.fullmatch('[a-f0-9]{64}', container_id))
    _ref(scope_ref)
    return {'status': 'REVIEW_REQUIRED', 'effects': 'Current host observation only, never a security case or approval.',
        'command': ['/usr/bin/python3', str(HERE / 'rsi_host.py'), 'observe',
            *observer_adapter(), '--manifest', manifest,
            'observe-current', '--phase', phase, '--container-id', container_id,
            '--scope-ref', json.dumps(scope_ref, sort_keys=True)]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', default=DEFAULT_MANIFEST)
    commands = parser.add_subparsers(dest='operation', required=True)
    commands.add_parser('probe')
    prepare_parser = commands.add_parser('prepare')
    prepare_parser.add_argument('--input', required=True)
    prepare_parser.add_argument('--phase', choices=sorted(PHASES), required=True)
    plan_parser = commands.add_parser('launch-plan')
    plan_parser.add_argument('--phase', choices=sorted(PHASES), required=True)
    signer = commands.add_parser('prepare-signer')
    signer.add_argument('--phase', choices=sorted(PHASES), required=True)
    signer.add_argument('--plan-ref', required=True)
    signer_plan = commands.add_parser('signer-launch-plan')
    signer_plan.add_argument('--phase', choices=sorted(PHASES), required=True)
    for name in ('observation-plan', 'observe-current'):
        observer = commands.add_parser(name)
        observer.add_argument('--phase', choices=sorted(PHASES), required=True)
        observer.add_argument('--container-id', required=True)
        observer.add_argument('--scope-ref', required=True)
    args = parser.parse_args(argv)
    try:
        if args.operation == 'probe':
            result = probe(args.manifest)
        elif args.operation == 'launch-plan':
            result = launch_plan(manifest=args.manifest, phase=args.phase)
        elif args.operation == 'prepare':
            result = prepare(args.input, manifest=args.manifest, phase=args.phase)
        elif args.operation == 'prepare-signer':
            result = prepare_signer(_json(args.plan_ref), manifest=args.manifest, phase=args.phase)
        elif args.operation == 'signer-launch-plan':
            result = signer_launch_plan(manifest=args.manifest, phase=args.phase)
        else:
            method = observe_current if args.operation == 'observe-current' else observation_plan
            result = method(args.container_id, _json(args.scope_ref), manifest=args.manifest, phase=args.phase)
    except SetupUnavailable as error:
        print(json.dumps({'status': 'BLOCKED', 'reason': error.code}))
        return 2
    except Exception:
        print(json.dumps({'status': 'BLOCKED', 'reason': 'ACTUAL_NATIVE_HOST_OR_ORIGINAL_METADATA_UNAVAILABLE'}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
