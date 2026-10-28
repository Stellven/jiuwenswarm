"""Root-only, append-only repair of a stopped deployment before any candidate.

This is distinct from the unused-deployment transition. A failed producer and
every old store/configuration stay in place. Only immutable image pins and the
Compose project change. No inference, admission, SQL write, restart or cleanup
is provided. Plan and apply independently observe the real stopped state.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import sys

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = Path('/var/lib/ai4r-rsi-codex')
HOST_ROOT = Path('/var/lib/ai4r-rsi-host-codex')
HOST_SOCKET = Path('/run/ai4r-rsi-host-codex/model.sock')
QUALIFICATION = Path('/var/lib/ai4r-rsi-host-codex-qualification.json')
DOCKER = ['/usr/bin/docker', '--host', 'unix:///run/ai4r-rsi-docker/docker.sock']
GENERATION = re.compile(r'[a-z][a-z0-9-]{0,47}\Z')
HASH = re.compile(r'[a-f0-9]{64}\Z')
IMAGE = re.compile(r'sha256:[a-f0-9]{64}\Z')
PROOF_FILES = {'images': 'images.json', 'installed': 'installed.json', 'policy': 'policy.json',
               'snapshot': 'snapshot.json', 'failure': 'failure.json', 'dependency': 'dependency.json'}
FROZEN_CORPUS_MANIFEST_SHA256 = '74d7fbc9f75efb062bea18b0e9df0c7b0ca443968e345989cae8fddb504bb470'
DEPENDENCY_IMAGE = 'sha256:6423080d962b697479f69653c53f7f0f951835f6d6d962df3a7e3f52833a3a27'
BUILD_GENERATOR_SHA256 = '392688de246c4ba193079f2785e65b26982bfcfa2452837b6a9593bcc253da08'
BUILD_ASSETS = ('channels/web/frontend/dist', 'channels/tui/frontend/dist',
                'channels/tui/frontend/node_modules', 'channels/tui/frontend/package.json')
NO_SESSION_TABLES = ('attempts', 'proposer_starts', 'history_jobs', 'session_history',
                     'session_phases', 'security_halts', 'session_opportunities')


class RepairUnavailable(ValueError):
    pass


def need(value, code='STOPPED_REPAIR_PREREQUISITE_UNAVAILABLE'):
    if not value:
        raise RepairUnavailable(code)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def closed_json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'DUPLICATE_JSON_FIELD')
            result[key] = value
        return result
    return json.loads(raw.decode('utf8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'NONFINITE_JSON'))


def root_identity():
    need(sys.platform == 'linux' and os.geteuid() == os.getegid() == 0, 'LINUX_ROOT_REQUIRED')


def custody(path, *, uid=0, gid=0, mode=0o600, directory=False):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts
         and not any(p.is_symlink() for p in (path, *path.parents)), 'UNSAFE_PATH')
    info = path.lstat()
    need((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
         and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (uid, gid, mode)
         and (directory or info.st_nlink == 1), 'CUSTODY_DIFFERS')
    return info


def read(path, *, uid=0, gid=0, mode=0o600, limit=4 * 1024 * 1024):
    custody(path, uid=uid, gid=gid, mode=mode)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        need(info.st_size <= limit and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))
             == (uid, gid, mode) and info.st_nlink == 1, 'UNSAFE_ORIGINAL')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(limit + 1)
        need(len(raw) <= limit)
        return raw
    finally:
        os.close(fd)


def sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def file_digest(path, uid=0):
    custody(path, uid=uid, gid=uid)
    need(path.stat().st_size <= 256 * 1024 * 1024, 'BOUNDED_INDEX_SIZE_EXCEEDED')
    result = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def new(path, raw):
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'UNSAFE_PATH')
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        os.fchown(stream.fileno(), 0, 0)
        os.fchmod(stream.fileno(), 0o600)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    sync(path.parent)


def mkdir(path):
    path.mkdir(mode=0o700, exist_ok=True)
    custody(path, directory=True, mode=0o700)
    sync(path.parent)


def sibling(name):
    spec = importlib.util.spec_from_file_location('_stopped_repair_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def repair_locks(root):
    import fcntl
    # The same native host lock is held throughout every supported relay serve.
    with sibling('rsi_host_codex_recovery').runtime_lock(HOST_ROOT):
        custody(root, directory=True, mode=0o700)
        custody(root / 'config', directory=True, mode=0o700)
        path = root / 'config/stopped-repair.lock'
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            custody(path)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)


def _database(path, uid):
    custody(path, uid=uid, gid=uid)
    for suffix in ('-wal', '-journal'):
        side = Path(str(path) + suffix)
        need(not side.exists() or side.stat().st_size == 0, 'LIVE_DATABASE_REQUIRES_ORIGINAL_OWNER')
    return sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)


def _count_tables(path, uid, names):
    db = _database(path, uid)
    try:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {name: db.execute('SELECT count(*) FROM ' + name).fetchone()[0]
                for name in names if name in tables}
    finally:
        db.close()


def fixture_admin_jobs(path):
    """Separate immutable human fixture administration from runtime job effects.

    The existing fixture-review owner uses the generic jobs index for its two
    fixed bookkeeping slots. Validate their closed records and exact joins;
    no candidate/runtime job, arbitrary job name or incomplete review is allowed.
    No preparation partition, fixture input or label body is read.
    """
    db = _database(path, 12002)
    try:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'jobs' not in tables:
            return []
        rows = list(db.execute('SELECT id,ref,state,result FROM jobs'))
    finally:
        db.close()
    if not rows:
        return []
    need(path.parent.name == 'fixture-review' and len(rows) == 2, 'CANDIDATE_RUNTIME_JOB_PRESENT')
    def original(text):
        pin = closed_json(text.encode())
        need(set(pin) == {'id', 'sha256'} and HASH.fullmatch(pin['sha256'])
             and pin['id'] == pin['sha256'] + '.json', 'FIXTURE_ADMIN_ORIGINAL_REF_DIFFERS')
        raw = read(path.parent / pin['id'], uid=12002, gid=12002)
        need(digest(raw) == pin['sha256'])
        return pin, closed_json(raw)
    prepared = next((row for row in rows if row[0] == 'fixture-review-generation'), None)
    need(prepared is not None and prepared[2] == 'prepared' and prepared[3] is None, 'FIXTURE_REVIEW_GENERATION_NOT_COMPLETE')
    prepared_pin, packet = original(prepared[1])
    need(set(packet) == {'status', 'request_ref', 'preparation_ref', 'packet_ref', 'review_completed', 'publication_performed'}
         and packet['status'] == 'PRIVATE_REVIEW_PACKET_PREPARED' and packet['review_completed'] is False
         and packet['publication_performed'] is False, 'FIXTURE_ADMIN_RECORD_DIFFERS')
    from jiuwenswarm.research_rsi.worker import ref
    for key in ('request_ref', 'preparation_ref', 'packet_ref'):
        ref(packet[key])
    reviewed = next((row for row in rows if row[0] == 'fixture-review:' + packet['packet_ref']['sha256']), None)
    need(reviewed is not None and reviewed[2] == 'reviewed' and reviewed[3] is None, 'INDEPENDENT_HUMAN_REVIEW_REQUIRED')
    review_pin, review = original(reviewed[1])
    from jiuwenswarm.research_rsi.session_policy import validate_private
    validate_private('urn:ai4r:private:rsi-ranking-review:1', review)
    need(review['preparation_ref'] == packet['preparation_ref']
         and all(review[key] is True for key in ('independent', 'overlap_inventory_complete',
             'provenance_approved', 'development_disclosure_approved')), 'FIXTURE_ADMIN_REVIEW_JOIN_DIFFERS')
    need(len(review['evidence_refs']) == 1, 'EXACT_HUMAN_REVIEW_EVIDENCE_REQUIRED')
    _, evidence = original(encoded(review['evidence_refs'][0]).decode())
    common = {'schema', 'packet_ref', 'preparation_ref', 'request_ref', 'reviewer', 'recorded_at',
              'inspected_sections', 'decisions', 'independence_reason', 'owner_findings', 'authority_record_ref'}
    need(set(evidence) in (common, common | {'channel', 'owner_reply_ref'})
         and evidence['schema'] == 'ai4r-rsi-fixture-review-human-evidence:1'
         and all(evidence[k] == packet[k] for k in ('packet_ref', 'preparation_ref', 'request_ref'))
         and evidence['reviewer'] == review['reviewer'] and evidence['independence_reason'] == review['independence_reason']
         and evidence['decisions'] == {k: review[k] for k in ('independent', 'overlap_inventory_complete',
              'provenance_approved', 'development_disclosure_approved')}, 'HUMAN_REVIEW_EVIDENCE_JOIN_DIFFERS')
    _, authority = original(encoded(evidence['authority_record_ref']).decode())
    need(set(authority) == {'schema', 'packet_ref', 'preparation_ref', 'request_ref', 'reviewer'}
         and authority['schema'] == 'ai4r-rsi-fixture-review-authority:1'
         and all(authority[k] == evidence[k] for k in ('packet_ref', 'preparation_ref', 'request_ref', 'reviewer')),
         'HUMAN_REVIEW_OWNER_AUTHORITY_DIFFERS')
    if 'owner_reply_ref' in evidence:
        _, reply = original(encoded(evidence['owner_reply_ref']).decode())
        sibling('rsi_fixture_review').validate_owner_reply(reply)
        need(evidence['channel'] == 'authenticated_chat'
             and all(reply[k] == evidence[k] for k in ('packet_ref', 'preparation_ref', 'request_ref', 'reviewer',
                    'decisions', 'independence_reason', 'owner_findings')), 'AUTHENTICATED_OWNER_REPLY_DIFFERS')
    else:
        need(set(evidence['inspected_sections']) >= {'summary', 'parent', 'generator', 'fixtures', 'lineage', 'controls'},
             'HUMAN_TTY_INSPECTIONS_INCOMPLETE')
    return [prepared_pin, review_pin]


def _docker(*args):
    result = subprocess.run(DOCKER + list(args), capture_output=True, timeout=60,
                            env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'})
    need(result.returncode == 0 and len(result.stdout) <= 4 * 1024 * 1024,
         'DOCKER_OBSERVATION_UNAVAILABLE')
    return result.stdout


def load_input(root, path):
    raw = read(path)
    value = closed_json(raw)
    fields = {'schema', 'generation', 'authorization', 'bootstrap_generation', 'failed_container_id',
              'old_manifest_sha256', 'new_project', 'proof_sha256'}
    need(isinstance(value, dict) and set(value) == fields
         and value['schema'] == 'ai4r-rsi-stopped-repair-input:1', 'UNKNOWN_REPAIR_INPUT')
    need(isinstance(value['generation'], str) and GENERATION.fullmatch(value['generation'])
         and isinstance(value['bootstrap_generation'], str) and GENERATION.fullmatch(value['bootstrap_generation'])
         and isinstance(value['authorization'], str) and 0 < len(value['authorization']) <= 4096
         and isinstance(value['new_project'], str) and sibling('rsi_local').NAME.fullmatch(value['new_project'])
         and HASH.fullmatch(value['failed_container_id']) and HASH.fullmatch(value['old_manifest_sha256'])
         and set(value['proof_sha256']) == set(PROOF_FILES)
         and all(isinstance(v, str) and HASH.fullmatch(v) for v in value['proof_sha256'].values()),
         'INVALID_REPAIR_SCOPE')
    need(path.parent == root / 'config/stopped-repair-inputs' / value['generation']
         and re.fullmatch(r'input(?:\.[a-z0-9-]{1,32})?\.json', path.name),
         'FIXED_REPAIR_INPUT_REQUIRED')
    proofs = {}
    for kind, filename in PROOF_FILES.items():
        body = read(path.parent / filename)
        need(digest(body) == value['proof_sha256'][kind], 'PROOF_BYTES_DIFFER')
        proofs[kind] = closed_json(body)
    return value, proofs, raw


def validate_image_proofs(proofs, old_images, policy_sha, qualification):
    images = proofs['images']
    need(isinstance(images, dict) and set(images) == {'schema', 'runtime', 'controller', 'worker',
         'base_controller', 'base_worker', 'source_snapshot', 'qualification'}
         and images['schema'] == 'rsi-native-model-images:1' and images['qualification'] is False
         and HASH.fullmatch(images['source_snapshot']), 'UNKNOWN_IMAGE_RECEIPT')
    selected = {'app': images['runtime'], 'rsi': images['controller'], 'worker': images['worker']}
    need(all(isinstance(v, str) and IMAGE.fullmatch(v) for v in selected.values())
         and selected['worker'] != old_images['worker'] and all(selected[k] != old_images[k] for k in selected),
         'NEW_THREE_ROLE_IMAGES_REQUIRED')
    installed = proofs['installed']; policies = proofs['policy']
    need(isinstance(installed, list) and len(installed) == 3 and isinstance(policies, list)
         and len(policies) == 3, 'THREE_ROLE_PROOFS_REQUIRED')
    roles = {'runtime', 'controller', 'worker'}
    need({v.get('role') for v in installed} == {v.get('role') for v in policies} == roles)
    builds = set()
    for row in installed:
        need(set(row) == {'role', 'image', 'build_id', 'frozen_corpus_files', 'installed_files', 'qualification', 'status'}
             and row['image'] == images[row['role']] and row['status'] == 'INSTALLED_BYTES_VERIFIED'
             and row['qualification'] is False and type(row['frozen_corpus_files']) is int
             and row['frozen_corpus_files'] == 87 and type(row['installed_files']) is int and row['installed_files'] > 0
             and HASH.fullmatch(row['build_id']), 'INSTALLED_SOURCE_PROOF_DIFFERS')
        builds.add(row['build_id'])
    need(len(builds) == 1, 'THREE_ROLE_SOURCE_BUILD_DIFFERS')
    for row in policies:
        need(set(row) == {'role', 'image', 'status', 'policy', 'inference_performed'}
             and row['status'] == 'EXACT_INSTALLED_HOST_POLICY_VERIFIED'
             and row['image'] == images[row['role']] and row['inference_performed'] is False,
             'INSTALLED_MODEL_POLICY_PROOF_DIFFERS')
        p = row['policy']
        need(p.get('sha256') == policy_sha and p.get('model') == 'gpt-6.1-sol'
             and p.get('reasoning_effort') == 'medium'
             and p.get('source_sha256', {}).get('research/local_model_codex.py') == qualification['helper_sha256'],
             'NATIVE_NO_TOOLS_SOURCE_POLICY_DIFFERS')
    return selected, next(iter(builds))


def observe_dependency():
    """Actual immutable normal-build dependency bytes, never a claimed fallback."""
    program = r'''
import hashlib,importlib.metadata,json
from pathlib import Path
from jiuwenswarm.research.native_ports import verify_installed_build
build=verify_installed_build()
package=Path(importlib.metadata.distribution('workswarm').locate_file('jiuwenswarm')).resolve()
identity=json.loads(Path('/usr/local/share/ai4r-build-identity.json').read_bytes())
for row in identity['files']:
 assert isinstance(row['path'],str) and not Path(row['path']).is_absolute() and '..' not in Path(row['path']).parts
 path=package/row['path']
 assert not any(p.is_symlink() for p in (path,*path.parents)) and path.is_file()
 raw=path.read_bytes()
 assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
print(json.dumps({'schema':'ai4r-rsi-observed-build-dependency:1','build_id':build,'uv_lock_sha256':identity['uv_lock_sha256'],'files':identity['files']}))
'''
    value = closed_json(_docker('run', '--rm', '--pull', 'never', '--read-only', '--network', 'none',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--user', '0:0', '--pids-limit', '32',
        '--memory', '512m', '--cpus', '1', '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=8m',
        '--entrypoint', '/opt/venv/bin/python', DEPENDENCY_IMAGE, '-I', '-B', '-c', program))
    return {**value, 'image': DEPENDENCY_IMAGE}


def expected_origin(path, files):
    """Reproduce only the independently frozen normal builder's copy rule."""
    for asset in BUILD_ASSETS:
        if path == asset or path.startswith(asset + '/'):
            if asset == BUILD_ASSETS[0] and 'jiuwenswarm/' + asset + '/index.html' in files:
                return 'snapshot'
            return 'dependency'
    return 'snapshot' if 'jiuwenswarm/' + path in files else None


def observe_image(image, role, snapshot_path, policy_sha, dependency_path=None):
    """Re-execute the fixed read-only verifier; supplied JSON cannot certify itself."""
    program = r'''
import hashlib,importlib.metadata,json,os
from pathlib import Path
from jiuwenswarm.research.native_ports import verify_installed_build
from jiuwenswarm.research_rsi.host_codex_backend import descriptor,HostCatalog,CATALOG,ENDPOINT
build=verify_installed_build()
snapshot_raw=Path('/run/stopped-repair-snapshot.json').read_bytes()
snapshot=json.loads(snapshot_raw)
assert snapshot['schema']=='rsi-public-build-snapshot:2'
files={row['path']:row['sha256'] for row in snapshot['files']}
assert len(files)==len(snapshot['files'])
assert files['deploy/m1/rebuild_cached.py']==EXPECTED_GENERATOR
dependency=json.loads(Path('/run/stopped-repair-dependency.json').read_bytes())
assert dependency['schema']=='ai4r-rsi-observed-build-dependency:1' and dependency['image']==EXPECTED_DEPENDENCY
inherited={row['path']:row for row in dependency['files']}
assert len(inherited)==len(dependency['files'])
package=Path(importlib.metadata.distribution('workswarm').locate_file('jiuwenswarm')).resolve()
identity=json.loads(Path('/usr/local/share/ai4r-build-identity.json').read_bytes())
reuse=json.loads(Path('/usr/local/share/ai4r-dependency-reuse.json').read_bytes())
assert reuse['schema']=='ai4r-cached-runtime-input:1' and reuse['dependency_image_id']==EXPECTED_DEPENDENCY
assert reuse['uv_lock_sha256']==dependency['uv_lock_sha256']==identity['uv_lock_sha256']
assert reuse['assets']==list(BUILD_ASSETS)
for row in identity['files']:
 assert isinstance(row['path'],str) and not Path(row['path']).is_absolute() and '..' not in Path(row['path']).parts
 path=package/row['path']
 assert not any(p.is_symlink() for p in (path,*path.parents)) and path.is_file()
 raw=path.read_bytes()
 assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
 origin=expected_origin(row['path'],files)
 if origin=='snapshot':assert files['jiuwenswarm/'+row['path']]==row['sha256']
 elif origin=='dependency':assert inherited[row['path']]==row
 else:raise ValueError('UNPROVEN_GENERATED_FILE_ORIGIN:'+row['path'])
corpus=package/'research/resources/calibration'
manifest_raw=(corpus/'manifest.json').read_bytes()
assert hashlib.sha256(manifest_raw).hexdigest()==FROZEN_MANIFEST
manifest=json.loads(manifest_raw)
assert len(manifest['files'])==87
assert all(hashlib.sha256((corpus/name).read_bytes()).hexdigest()==sha for name,sha in manifest['files'].items())
for root in (package,Path('/opt/ai4r/jiuwenswarm')):
 for prefix in ('research_rsi','research_records','research_contracts','research/contracts'):
  for path in (root/prefix).rglob('*'):
   meta=path.lstat()
   assert meta.st_uid==0 and not meta.st_mode&0o022 and not path.is_symlink()
   if path.is_file():assert hashlib.sha256(path.read_bytes()).hexdigest()==files['jiuwenswarm/'+path.relative_to(root).as_posix()]
if WORKER:
 assert not any(os.path.lexists(p) for p in ('/hidden-fixtures','/var/lib/ai4r-rsi/custodian','/var/lib/ai4r-rsi/accounts','/var/lib/ai4r','/var/lib/ai4r-accounts','/var/run/docker.sock'))
policy=descriptor(HostCatalog(CATALOG).resolve(ENDPOINT))
assert policy['sha256']==EXPECTED_POLICY and policy['model']=='gpt-6.1-sol' and policy['reasoning_effort']=='medium'
print(json.dumps({'installed':{'status':'INSTALLED_BYTES_VERIFIED','build_id':build,'installed_files':len(identity['files']),'frozen_corpus_files':87,'qualification':False},'policy':policy,'source_snapshot_sha256':hashlib.sha256(snapshot_raw).hexdigest(),'inference_performed':False}))
'''
    import inspect
    program = ('FROZEN_MANIFEST=' + repr(FROZEN_CORPUS_MANIFEST_SHA256) + '\nWORKER=' + repr(role == 'worker')
               + '\nEXPECTED_POLICY=' + repr(policy_sha) + '\nEXPECTED_DEPENDENCY=' + repr(DEPENDENCY_IMAGE)
               + '\nEXPECTED_GENERATOR=' + repr(BUILD_GENERATOR_SHA256) + '\nBUILD_ASSETS=' + repr(BUILD_ASSETS)
               + '\n' + inspect.getsource(expected_origin) + '\n' + program)
    command = ['run', '--rm', '--pull', 'never', '--read-only', '--network', 'none', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges:true', '--user', '0:0', '--pids-limit', '32', '--memory', '512m',
        '--cpus', '1', '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=8m']
    for source, target in ((snapshot_path, '/run/stopped-repair-snapshot.json'),
        (dependency_path or snapshot_path.with_name('dependency.json'), '/run/stopped-repair-dependency.json'),
        (Path('/run/ai4r-rsi-host-codex/catalog.json'), '/run/ai4r-rsi-host-codex/catalog.json'),
        (QUALIFICATION, '/run/ai4r-rsi-host-codex/qualification.json')):
        command += ['--mount', 'type=bind,src=' + str(source) + ',dst=' + target + ',readonly']
    command += ['--entrypoint', '/opt/venv/bin/python', image, '-I', '-B', '-c', program]
    return closed_json(_docker(*command))


def validate_failure_proof(proof, *, container_id, image, state):
    """Join a retained original observation to fresh exact cessation facts.

    Docker's bounded event history may expire during an offline image build.
    Absence of those events creates no new zero/start assertion. The protected,
    explicitly hash-pinned original remains mandatory even when events survive.
    """
    fields = {'schema', 'container_id', 'image', 'state', 'event_counts', 'event_bytes_sha256',
        'campaign_record_counts', 'worker_directory_empty', 'visible_socket_directory_empty',
        'hidden_socket_directory_empty', 'public_metadata_directory_empty', 'approval_present',
        'security_cases_executed', 'timing_captures_executed', 'model_dispatch_by_observer'}
    need(isinstance(proof, dict) and set(proof) == fields
         and proof['schema'] == 'ai4r-rsi-safe-security-startup-stop:1'
         and proof['container_id'] == container_id and proof['image'] == image and proof['state'] == state
         and proof['event_counts'] == {'create': 1, 'start': 1, 'die': 1}
         and all(type(v) is int for v in proof['event_counts'].values())
         and HASH.fullmatch(proof['event_bytes_sha256']) and proof['campaign_record_counts'] == {}
         and all(proof[key] is True for key in ('worker_directory_empty', 'visible_socket_directory_empty',
                 'hidden_socket_directory_empty', 'public_metadata_directory_empty'))
         and proof['approval_present'] is False and proof['model_dispatch_by_observer'] is False
         and all(type(proof[key]) is int and proof[key] == 0 for key in ('security_cases_executed', 'timing_captures_executed')),
         'RETAINED_ORIGINAL_FAILURE_PROOF_DIFFERS')


def validate_transition_calibration_calls(calls, *, allowed_failed_refs=()):
    """An optional independently derived exact set, never a failed-row waiver."""
    allowed={}
    for pin in allowed_failed_refs:
        need(isinstance(pin,dict) and set(pin)=={'id','sha256'} and isinstance(pin['id'],str) and pin['id']
             and isinstance(pin['sha256'],str) and HASH.fullmatch(pin['sha256']), 'INVALID_ALLOWED_FAILED_REF')
        key=encoded(pin);need(key not in allowed, 'DUPLICATE_ALLOWED_FAILED_REF');allowed[key]=pin
    consumed=set();seen=set()
    for pin,call in calls:
        key=encoded(pin);need(key not in seen, 'DUPLICATE_CURRENT_CALL_REF');seen.add(key)
        need(call['call_function']=='verifier' and call['id'].startswith('calibration-call:'), 'NONCALIBRATION_OR_UNCERTAIN_CURRENT_CALL')
        if call['outcome']=='failed':
            need(key in allowed, 'NONCALIBRATION_OR_UNCERTAIN_CURRENT_CALL');consumed.add(key)
        else:need(call['outcome']=='completed', 'NONCALIBRATION_OR_UNCERTAIN_CURRENT_CALL')
    need(consumed==set(allowed), 'UNCONSUMED_ALLOWED_FAILED_REF')


def observe_transition_prerequisites(root, request, proofs, input_path=None, *, allowed_failed_refs=()):
    """Read actual ownership/terminal facts only. Never instantiate a SQL writer."""
    verify_repair_complete(root)
    local = sibling('rsi_local')
    value = local.load_manifest(root / 'local.json')
    need(value['model_backend'] == 'host-codex' and value['root'] == str(root))
    local.validate_backend(value)
    native = sibling('rsi_host_codex').load()
    qualification = closed_json(read(QUALIFICATION, mode=0o400))
    need(native['qualification'] == qualification and not os.path.lexists(HOST_SOCKET), 'OWNED_RELAY_MUST_BE_STOPPED')
    policy_sha = native['policy_sha256']
    images, build = validate_image_proofs(proofs, value['images'], policy_sha, qualification)
    snapshot_path = (input_path.parent if input_path is not None else root / 'config/stopped-repair-inputs' / request['generation']) / PROOF_FILES['snapshot']
    need(digest(read(snapshot_path)) == proofs['images']['source_snapshot'], 'SOURCE_SNAPSHOT_IMAGE_JOIN_DIFFERS')
    dependency = observe_dependency()
    need(dependency == proofs['dependency'], 'ACTUAL_BUILD_DEPENDENCY_PROOF_DIFFERS')
    actual_images = []
    for role, image in (('runtime', images['app']), ('controller', images['rsi']), ('worker', images['worker'])):
        actual = closed_json(_docker('image', 'inspect', image, '--format',
            '{"id":{{json .Id}},"os":{{json .Os}},"architecture":{{json .Architecture}}}'))
        need(actual == {'id': image, 'os': 'linux', 'architecture': 'amd64'})
        checked = observe_image(image, role, snapshot_path, policy_sha)
        expected = next(row for row in proofs['installed'] if row['role'] == role)
        need(checked['installed'] == {k: v for k, v in expected.items() if k not in {'role', 'image'}}
             and checked['policy'] == next(row['policy'] for row in proofs['policy'] if row['role'] == role)
             and checked['source_snapshot_sha256'] == proofs['images']['source_snapshot']
             and checked['inference_performed'] is False, 'ACTUAL_INSTALLED_IMAGE_PROOF_DIFFERS')
        actual_images.append({'role': role, 'image': image, 'verification_sha256': digest(encoded(checked))})
    # Reuse the strict existing receipt validator without its SQLite-writing constructor.
    from jiuwenswarm.research.local_model_relay import LocalModelRelay
    relay = LocalModelRelay.__new__(LocalModelRelay)
    relay.runtime = HOST_ROOT / 'relay'; relay.recovery_policy_sha256 = policy_sha
    db = _database(relay.runtime / 'requests.sqlite3', 0)
    unknowns = []
    try:
        for ident, payload_sha, result in db.execute("SELECT id,digest,result FROM requests WHERE result IS NULL OR json_extract(result,'$.outcome')='outcome_unknown'"):
            need(result is not None, 'UNRESOLVED_NATIVE_REQUEST')
            relay._validate_disposition(ident, payload_sha, result)
            path = relay.runtime / 'reconciliations' / (digest(ident.encode()) + '.json')
            unknowns.append({'request_id': ident, 'payload_sha256': payload_sha,
                             'result_sha256': digest(result.encode()), 'disposition_sha256': digest(read(path))})
    finally:
        db.close()
    # The repair cannot reconcile another unknown or enlarge the reviewed recovery scope.
    need(len(unknowns) <= 1, 'ADDITIONAL_UNKNOWN_REQUIRES_SEPARATE_RECOVERY')
    namespaces = []
    for directory in sorted((root / 'controller').iterdir()):
        need(re.fullmatch(r'operational-bootstrap(?:\.[a-z][a-z0-9-]{0,63})?', directory.name), 'CONTROLLER_SESSION_EFFECT_PRESENT')
        custody(directory, uid=12001, gid=12001, mode=0o700, directory=True)
        bootstrap = closed_json(read(directory / 'bootstrap.json', uid=12001, gid=12001))
        index = directory / 'native-leases/index.sqlite'
        db = _database(index, 12001)
        try:
            counts = dict(db.execute('SELECT state,count(*) FROM native_effect_leases GROUP BY state'))
            need(set(counts) <= {'complete'}, 'PRIOR_NATIVE_LEASE_NOT_COMPLETE')
        finally:
            db.close()
        namespaces.append({'name': directory.name, 'bootstrap_sha256': digest(read(directory / 'bootstrap.json', uid=12001, gid=12001)),
                           'lease_index_sha256': file_digest(index, 12001), 'states': counts,
                           'core_index_sha256': file_digest(directory / 'core/state/research.sqlite3', 12001)})
    current = root / 'controller' / ('operational-bootstrap.' + request['bootstrap_generation'])
    boot = closed_json(read(current / 'bootstrap.json', uid=12001, gid=12001))
    expected = {'operational-bootstrap.' + name if name != 'legacy' else 'operational-bootstrap'
                for name in boot['prior_namespaces']} | {current.name}
    need({row['name'] for row in namespaces} == expected and len(expected) >= 2, 'PRIOR_NAMESPACE_CLOSURE_DIFFERS')
    db = _database(current / 'core/state/research.sqlite3', 12001)
    try:
        def original(sha):
            raw = read(current / 'core/artifacts/sha256' / sha[:2] / sha, uid=12001, gid=12001)
            need(digest(raw) == sha)
            return closed_json(raw)
        calls = db.execute("SELECT a.id,a.sha256 FROM records r JOIN artifacts a ON a.id=r.id WHERE r.kind='model-call'").fetchall()
        validate_transition_calibration_calls([({'id':ident,'sha256':sha},original(sha)) for ident,sha in calls],allowed_failed_refs=allowed_failed_refs)
        for (sha,) in db.execute("SELECT a.sha256 FROM records r JOIN artifacts a ON a.id=r.id WHERE r.kind='library-admission'"):
            admission = original(sha)
            need(admission.get('parent_ref') is None and admission.get('parent_admission_ref') is None,
                 'CHILD_ADMISSION_PRESENT')
            declaration = original(admission['candidate_ref']['sha256'])
            need(not declaration.get('identity', {}).get('lineage'), 'CHILD_DECLARATION_PRESENT')
    finally:
        db.close()
    private_counts = {}; fixture_metadata = {}
    for path in (root / 'custodian/fixture-review/index.sqlite', root / 'custodian/index.sqlite'):
        if path.exists():
            counts = _count_tables(path, 12002, NO_SESSION_TABLES)
            need(not any(counts.values()), 'CANDIDATE_SESSION_EFFECT_PRESENT')
            private_counts[str(path.relative_to(root))] = counts
            fixture_metadata[str(path.relative_to(root))] = fixture_admin_jobs(path)
    # Final standard role roots must still be unused. Public source/control metadata is allowed separately.
    final_names = ('worker', 'security', 'scope-ipc', 'validation-control', 'validation-public',
        'validation-evidence', 'validation-campaign', 'validation-custody', 'validation-ipc',
        'jobs-ipc', 'custodian-ipc', 'visible-ipc', 'hidden-ipc', 'visible-inputs', 'hidden-inputs',
        'requests', 'inbox')
    for name in final_names:
        custody(root / name, uid=local.DIRECTORIES[name][0], gid=local.DIRECTORIES[name][1],
                mode=local.DIRECTORIES[name][2], directory=True)
        need(not any((root / name).iterdir()), 'FINAL_STANDARD_ROLE_STATE_PRESENT')
    return {'value': value, 'policy_sha': policy_sha, 'qualification': qualification, 'images': images, 'build': build, 'dependency': dependency, 'actual_images': actual_images, 'relay': relay, 'unknowns': unknowns, 'namespaces': namespaces, 'calls': calls, 'private_counts': private_counts, 'fixture_metadata': fixture_metadata}


def _observe(root, request, proofs, input_path=None):
    need(sibling('rsi_security_abandonment').verify_history(root) is None, 'USE_SECURITY_ABANDONMENT_SUCCESSOR_PROTOCOL')
    common = observe_transition_prerequisites(root, request, proofs, input_path)
    value = common['value']
    policy_sha = common['policy_sha']
    qualification = common['qualification']
    images = common['images']
    build = common['build']
    dependency = common['dependency']
    actual_images = common['actual_images']
    relay = common['relay']
    unknowns = common['unknowns']
    namespaces = common['namespaces']
    calls = common['calls']
    private_counts = common['private_counts']
    fixture_metadata = common['fixture_metadata']
    security = sibling('rsi_security_setup')
    paths = security.phase_paths(value, 'draft')
    raw = _docker('inspect', '--format', '{{json .State}}|{{.Image}}|{{json .Config.Labels}}|{{.Created}}|{{json .Mounts}}', request['failed_container_id'])
    state, old_image, labels, created, mounted = raw.decode().strip().split('|', 4)
    state = closed_json(state.encode()); labels = closed_json(labels.encode())
    mounts = closed_json(mounted.encode())
    need(state['Status'] == 'exited' and state['Running'] is False and state['Pid'] == 0
         and state['ExitCode'] == 2 and state['OOMKilled'] is False and state['Restarting'] is False
         and state['StartedAt'] != '0001-01-01T00:00:00Z' and state['FinishedAt'] != '0001-01-01T00:00:00Z'
         and old_image == value['images']['worker'] and labels.get('com.docker.compose.project') == value['project']
         and labels.get('com.docker.compose.service') == 'rsi-worker-broker', 'EXACT_FAILED_PRODUCER_TERMINAL_REQUIRED')
    validate_failure_proof(proofs['failure'], container_id=request['failed_container_id'], image=old_image, state=state)
    prior_state = root / 'config' / ('security-execution.' + request['bootstrap_generation'])
    launch_plan_raw = read(prior_state / 'worker-plan.json')
    launch_claim_raw = read(prior_state / 'worker-launch-claim.json')
    producer_raw = read(prior_state / 'producer.json')
    launch_plan = closed_json(launch_plan_raw); launch_claim = closed_json(launch_claim_raw)
    producer = closed_json(producer_raw)
    command = launch_plan['command']; position = command.index('--project-name')
    need(command[position + 1] == value['project'] and launch_plan['environment']['AI4R_JOB_ID'] == value['project']
         and launch_plan['environment']['AI4R_RSI_WORKER_IMAGE'] == old_image
         and launch_claim == {'review_sha256': digest(encoded(launch_plan))}
         and producer['container_id'] == request['failed_container_id']
         and producer['process']['container_id'] == request['failed_container_id']
         and producer['process']['image'] == old_image and producer['process']['started_at'] == state['StartedAt'],
         'ORIGINAL_PRODUCER_PROJECT_RECEIPTS_DIFFER')
    by_target = {row['Destination']: row for row in mounts}
    for target, source, writable in (
        ('/var/lib/ai4r-rsi-worker', paths['worker'], True),
        ('/run/ai4r-rsi-validation', paths['validation-control'], False),
        ('/run/ai4r-rsi-validation/public', paths['validation-public'], True),
        ('/var/lib/ai4r-rsi-validation-campaign', paths['validation-campaign'], True),
        ('/run/ai4r-rsi-worker/broker-service.json', paths['broker-config'], False)):
        row = by_target.get(target, {})
        need(row.get('Type') == 'bind' and row.get('Source') == str(source)
             and row.get('RW') is writable, 'FAILED_PRODUCER_PHASE_MOUNTS_DIFFER')
    # No other live/stopped container may hold this deployment's mounts.
    ids = _docker('ps', '-a', '--no-trunc', '--format', '{{.ID}}').decode().split()
    for cid in ids:
        mounts = closed_json(_docker('inspect', cid, '--format', '{{json .Mounts}}'))
        touching = any(Path(m['Source']) == root or Path(m['Source']).is_relative_to(root) for m in mounts)
        need(not touching or cid == request['failed_container_id'], 'ANOTHER_CONTAINER_HOLDS_DEPLOYMENT')
    # Events are finite and pinned to this original CID; timestamps themselves are retained in State.
    # Docker emits die just after setting FinishedAt. This fixed past bound
    # includes that event without making the reviewed plan clock-dependent.
    until = str(int(datetime.fromisoformat(state['FinishedAt'].replace('Z', '+00:00')).timestamp()) + 2)
    events = _docker('events', '--since', created, '--until', until, '--filter',
                     'container=' + request['failed_container_id'], '--format', '{{json .}}')
    actions = [closed_json(line).get('Action') for line in events.splitlines() if line]
    need(not actions or actions.count('start') == actions.count('die') == 1 and 'restart' not in actions,
         'CURRENT_LIFECYCLE_CONTRADICTS_RETAINED_PROOF')
    for name in ('worker', 'validation-public', 'visible-ipc', 'hidden-ipc', 'security', 'scope-ipc', 'validation-custody', 'validation-ipc', 'validation-evidence'):
        need(not any(paths[name].iterdir()), 'SECURITY_PREPARATION_OR_CASE_EFFECT_PRESENT')
    need(not paths['custodian-config'].exists(), 'SIGNER_WAS_PREPARED')
    need({p.name for p in paths['validation-control'].iterdir()} <= {'runtime.json', 'public'}, 'SECURITY_APPROVAL_OR_OBSERVATION_PRESENT')
    nested = paths['validation-control'] / 'public'
    if nested.exists():
        custody(nested, mode=0o755, directory=True)
        need(not any(nested.iterdir()), 'NESTED_MOUNTPOINT_HAS_CONTENTS')
    count = _count_tables(paths['validation-campaign'] / 'state/research.sqlite3', 0, ('records', 'artifacts'))
    need(count == {'records': 0, 'artifacts': 0}, 'SECURITY_PREPARATION_OR_CASE_RECORD_PRESENT')
    groups = [Path(value['cgroup_host']), *Path(value['cgroup_host']).rglob('cgroup.procs')]
    need(len(groups) <= 257, 'BOUNDED_CGROUP_INSPECTION_EXCEEDED')
    for group in groups:
        procs = group / 'cgroup.procs' if group.is_dir() else group
        need(not procs.read_text().strip(), 'CGROUP_WORKER_PRESENT')
    originals = {'local.before.json': read(root / 'local.json'),
                 'broker.before.json': read(paths['broker-config']),
                 'runtime.before.json': read(paths['validation-control'] / 'runtime.json'),
                 'worker-plan.before.json': launch_plan_raw, 'worker-launch-claim.before.json': launch_claim_raw,
                 'producer.before.json': producer_raw}
    selector = root / 'config/security-phase-current.json'
    if selector.exists():
        originals['phase-selector.before.json'] = read(selector)
    return {'manifest': value, 'manifest_sha256': digest(originals['local.before.json']),
        'input_bytes_sha256': digest(read(input_path or root / 'config/stopped-repair-inputs' / request['generation'] / 'input.json')),
        'policy_sha256': policy_sha, 'qualification_sha256': digest(read(QUALIFICATION, mode=0o400)),
        'native_ledger_sha256': file_digest(relay.runtime / 'requests.sqlite3'),
        'retained_unknowns': unknowns, 'namespaces': namespaces, 'current_calibration_calls': len(calls),
        'private_session_counts': private_counts, 'new_images': images, 'new_build_id': build,
        'retained_fixture_admin_refs': fixture_metadata,
        'actual_image_verifications': actual_images,
        'actual_dependency_verification_sha256': digest(encoded(dependency)),
        'build_asset_origin_rule': {'source_sha256': BUILD_GENERATOR_SHA256, 'dependency_image': DEPENDENCY_IMAGE},
        'admin_source_sha256': {name: digest((HERE / name).read_bytes()) for name in
            ('rsi_stopped_repair.py', 'rsi_local.py', 'rsi_security_setup.py', 'rsi_host_codex.py', 'rsi_host_codex_recovery.py')},
        'failed_producer': {'container_id': request['failed_container_id'], 'state': state, 'image': old_image,
                            'events_sha256': digest(events), 'current_events_available': bool(actions),
                            'retained_failure_sha256': request['proof_sha256']['failure'],
                            'preparation_records': 0, 'security_cases': 0},
        'original_sha256': {name: digest(raw) for name, raw in originals.items()},
        'originals': originals}


def build_plan(request, observed):
    """Pure exact plan, separately testable; no observation booleans grant authority."""
    need(request['old_manifest_sha256'] == observed['manifest_sha256'], 'OLD_MANIFEST_BYTES_DIFFER')
    old = observed['manifest']
    need(request['new_project'] != old['project'], 'NEW_COMPOSE_PROJECT_REQUIRED')
    need(observed['new_images']['worker'] != old['images']['worker'], 'NEW_WORKER_IMAGE_REQUIRED')
    updated = {**old, 'project': request['new_project'], 'images': observed['new_images']}
    need(set(updated) == set(old) and all(updated[k] == old[k] for k in old if k not in {'project', 'images'}))
    manifest_raw = encoded(updated)
    facts = {k: v for k, v in observed.items() if k not in {'originals', 'manifest'}}
    phase = {'schema': 'ai4r-rsi-security-phase-generation:1', 'generation': request['generation'],
        'actor': 'os:0:root', 'authorization': request['authorization'], 'project': request['new_project'],
        'old_project': old['project'], 'old_worker_image': old['images']['worker'],
        'new_worker_image': updated['images']['worker'], 'old_container_id': request['failed_container_id'],
        'old_manifest_sha256': observed['manifest_sha256'], 'new_manifest_sha256': digest(manifest_raw),
        'cessation_sha256': digest(encoded(observed['failed_producer']))}
    plan = {'schema': 'ai4r-rsi-stopped-repair-plan:1', 'generation': request['generation'],
        'actor': 'os:0:root', 'authorization': request['authorization'], 'input_sha256': observed['input_bytes_sha256'],
        'facts': facts, 'old_manifest_sha256': observed['manifest_sha256'],
        'new_manifest_sha256': digest(manifest_raw), 'new_manifest': updated,
        'phase_receipt': phase, 'qualification': False,
        'effects': ['retain every old container/store/configuration', 'archive exact prior metadata',
                    'bind three verified images and distinct Compose project', 'select fresh draft security phase'],
        'prohibitions': ['no inference', 'no producer restart', 'no SQL write', 'no child admission or activation']}
    return plan


def plan(root, input_path):
    root_identity()
    with repair_locks(root):
        request, proofs, _ = load_input(root, input_path)
        observed = _observe(root, request, proofs, input_path)
        return build_plan(request, observed)


def verify_repair_complete(root):
    """Every durable claim requires its exact final completion; never auto-repair."""
    root = Path(root)
    abandonment = sibling('rsi_security_abandonment').verify_history(root)
    need(not any(p.is_symlink() for p in (root, root / 'config', *root.parents)), 'UNSAFE_REPAIR_ROOT')
    claims = root / 'config/stopped-repair-claims'
    applied = root / 'config/stopped-repair-applied'
    if not os.path.lexists(claims):
        if os.path.lexists(applied):
            custody(applied, directory=True, mode=0o700)
            need(not any(applied.iterdir()), 'ORPHAN_REPAIR_COMPLETION')
        need(abandonment is not None or not os.path.lexists(root / 'config/security-phase-current.json'), 'ORPHAN_PHASE_SELECTOR')
        phases = root / 'config/security-phase-generations'
        if os.path.lexists(phases):
            custody(phases, directory=True, mode=0o700)
            need(not any(phases.iterdir()), 'ORPHAN_PHASE_RECEIPT')
        return
    custody(claims, directory=True, mode=0o700)
    custody(applied, directory=True, mode=0o700)
    names = {p.name for p in claims.iterdir()}
    need(names == {p.name for p in applied.iterdir()}, 'PARTIAL_STOPPED_REPAIR_BLOCKS_START')
    old_hashes = set(); new_hashes = set(); edges = {}
    for name in sorted(names):
        need(name.endswith('.json') and GENERATION.fullmatch(name[:-5]), 'UNKNOWN_REPAIR_CLAIM')
        raw = read(claims / name); claim = closed_json(raw)
        done = closed_json(read(applied / name))
        need(set(claim) == {'schema', 'generation', 'plan_sha256', 'old_manifest_sha256', 'new_manifest_sha256', 'phase_receipt_sha256'}
             and claim['schema'] == 'ai4r-rsi-stopped-repair-claim:1' and claim['generation'] == name[:-5]
             and all(HASH.fullmatch(claim[k]) for k in ('plan_sha256', 'old_manifest_sha256', 'new_manifest_sha256', 'phase_receipt_sha256'))
             and set(done) == {'schema', 'generation', 'claim_sha256', 'manifest_sha256', 'phase_receipt_sha256'}
             and done['schema'] == 'ai4r-rsi-stopped-repair-applied:1' and done['generation'] == claim['generation']
             and done['claim_sha256'] == digest(raw) and done['manifest_sha256'] == claim['new_manifest_sha256']
             and done['phase_receipt_sha256'] == claim['phase_receipt_sha256'], 'REPAIR_COMPLETION_DIFFERS')
        phase = root / 'config/security-phase-generations' / name
        need(digest(read(phase)) == claim['phase_receipt_sha256'], 'IMMUTABLE_PHASE_RECEIPT_DIFFERS')
        archive = root / 'config/stopped-repair-archive' / name[:-5]
        plan_raw = read(archive / 'plan.json')
        need(digest(plan_raw) == claim['plan_sha256'] and digest(read(archive / 'local.before.json')) == claim['old_manifest_sha256'],
             'REPAIR_ARCHIVE_DIFFERS')
        need(claim['new_manifest_sha256'] not in new_hashes and claim['old_manifest_sha256'] not in old_hashes,
             'BRANCHED_REPAIR_CHAIN')
        need(claim['old_manifest_sha256'] != claim['new_manifest_sha256'], 'CYCLIC_REPAIR_CHAIN')
        edges[claim['old_manifest_sha256']] = claim['new_manifest_sha256']
        old_hashes.add(claim['old_manifest_sha256']); new_hashes.add(claim['new_manifest_sha256'])
    if names:
        leaves = new_hashes - old_hashes
        starts = old_hashes - new_hashes
        need(len(leaves) == len(starts) == 1, 'DISCONNECTED_REPAIR_CHAIN')
        seen = set(); cursor = next(iter(starts))
        while cursor in edges and cursor not in seen:
            seen.add(cursor); cursor = edges[cursor]
        need(len(seen) == len(names) and cursor in leaves, 'DISCONNECTED_REPAIR_CHAIN')
        need((abandonment['base_manifest_sha256'] if abandonment else digest(read(root / 'local.json'))) in leaves, 'CURRENT_REPAIRED_MANIFEST_DIFFERS')
        selector = abandonment['prior_selector'] if abandonment else closed_json(read(root / 'config/security-phase-current.json'))
        need(set(selector) == {'schema', 'generation', 'receipt_sha256'}
             and selector['schema'] == 'ai4r-rsi-security-phase-selector:1'
             and selector['generation'] + '.json' in names, 'CURRENT_PHASE_SELECTOR_REQUIRED')
        selected_claim = closed_json(read(claims / (selector['generation'] + '.json')))
        need(selected_claim['new_manifest_sha256'] in leaves
             and selector['receipt_sha256'] == selected_claim['phase_receipt_sha256'], 'CURRENT_PHASE_SELECTOR_DIFFERS')


def phase_generation(value):
    """Consume only the finite protected selector tied to an applied manifest."""
    root = Path(value['root']); selector = root / 'config/security-phase-current.json'
    verify_repair_complete(root)
    if not selector.exists():
        return None
    selected = closed_json(read(selector))
    if selected.get('protocol') == 'security-abandonment':
        return sibling('rsi_security_abandonment').phase_generation(value)
    need(set(selected) == {'schema', 'generation', 'receipt_sha256'}
         and selected['schema'] == 'ai4r-rsi-security-phase-selector:1'
         and GENERATION.fullmatch(selected['generation']) and HASH.fullmatch(selected['receipt_sha256']))
    raw = read(root / 'config/security-phase-generations' / (selected['generation'] + '.json'))
    completion = closed_json(read(root / 'config/stopped-repair-applied' / (selected['generation'] + '.json')))
    need(completion['phase_receipt_sha256'] == selected['receipt_sha256'], 'PHASE_REQUIRES_APPLIED_REPAIR')
    phase = closed_json(raw)
    fields = {'schema', 'generation', 'actor', 'authorization', 'project', 'old_project', 'old_worker_image',
              'new_worker_image', 'old_container_id', 'old_manifest_sha256', 'new_manifest_sha256', 'cessation_sha256'}
    need(digest(raw) == selected['receipt_sha256'] and set(phase) == fields
         and phase['schema'] == 'ai4r-rsi-security-phase-generation:1' and phase['actor'] == 'os:0:root'
         and phase['generation'] == selected['generation'] and phase['project'] == value['project']
         and phase['old_project'] != phase['project'] and phase['new_worker_image'] == value['images']['worker']
         and phase['old_worker_image'] != phase['new_worker_image']
         and phase['new_manifest_sha256'] == digest(read(root / 'local.json'))
         and isinstance(phase['authorization'], str) and 0 < len(phase['authorization']) <= 4096
         and all(HASH.fullmatch(phase[k]) for k in ('old_container_id', 'old_manifest_sha256', 'new_manifest_sha256', 'cessation_sha256')),
         'PHASE_GENERATION_BINDING_DIFFERS')
    return selected['generation']


def apply(root, input_path, review_sha256):
    root_identity(); need(HASH.fullmatch(review_sha256), 'EXACT_REVIEW_HASH_REQUIRED')
    with repair_locks(root):
        request, proofs, input_raw = load_input(root, input_path)
        observed = _observe(root, request, proofs, input_path)
        reviewed = build_plan(request, observed); plan_raw = encoded(reviewed)
        need(digest(plan_raw) == review_sha256, 'REVIEW_PLAN_CHANGED')
        # Recheck under both locks before the first durable repair claim.
        again = _observe(root, request, proofs, input_path)
        need(encoded(build_plan(request, again)) == plan_raw, 'STOPPED_STATE_CHANGED')
        generation = request['generation']; config = root / 'config'
        for folder in ('stopped-repair-archive', 'stopped-repair-claims', 'stopped-repair-applied', 'security-phase-generations'):
            mkdir(config / folder)
        archive = config / 'stopped-repair-archive' / generation
        archive.mkdir(mode=0o700); sync(archive.parent)
        new(archive / 'plan.json', plan_raw)
        new(archive / 'input.json', input_raw)
        for name, raw in observed['originals'].items():
            new(archive / name, raw)
        for kind, filename in PROOF_FILES.items():
            new(archive / filename, read(input_path.parent / filename))
        phase_raw = encoded(reviewed['phase_receipt'])
        claim = {'schema': 'ai4r-rsi-stopped-repair-claim:1', 'generation': generation,
            'plan_sha256': review_sha256, 'old_manifest_sha256': reviewed['old_manifest_sha256'],
            'new_manifest_sha256': reviewed['new_manifest_sha256'], 'phase_receipt_sha256': digest(phase_raw)}
        claim_raw = encoded(claim)
        # This immutable claim precedes every active configuration change. Any
        # crash from here blocks all normal local-helper load/start operations.
        new(config / 'stopped-repair-claims' / (generation + '.json'), claim_raw)
        new(config / 'security-phase-generations' / (generation + '.json'), phase_raw)
        selector = encoded({'schema': 'ai4r-rsi-security-phase-selector:1', 'generation': generation,
                            'receipt_sha256': digest(phase_raw)})
        new(archive / 'phase-selector.pending.json', selector)
        os.replace(archive / 'phase-selector.pending.json', config / 'security-phase-current.json'); sync(config)
        new(archive / 'local.pending.json', encoded(reviewed['new_manifest']))
        need(digest(read(root / 'local.json')) == reviewed['old_manifest_sha256'], 'MANIFEST_CHANGED_AFTER_CLAIM')
        os.replace(archive / 'local.pending.json', root / 'local.json'); sync(root); sync(archive)
        completion = {'schema': 'ai4r-rsi-stopped-repair-applied:1', 'generation': generation,
            'claim_sha256': digest(claim_raw), 'manifest_sha256': reviewed['new_manifest_sha256'],
            'phase_receipt_sha256': digest(phase_raw)}
        new(config / 'stopped-repair-applied' / (generation + '.json'), encoded(completion))
        verify_repair_complete(root)
        need(phase_generation(reviewed['new_manifest']) == generation)
        return {'status': 'STOPPED_REPAIR_APPLIED_NOT_QUALIFIED', 'generation': generation,
                'manifest_sha256': completion['manifest_sha256'], 'completion_sha256': digest(encoded(completion)),
                'old_state_preserved': True, 'model_calls': 0, 'candidate_admitted': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('operation', choices=('plan', 'apply'))
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--review-sha256')
    args = parser.parse_args(argv)
    try:
        result = plan(args.root, args.input) if args.operation == 'plan' else apply(args.root, args.input, args.review_sha256)
        print(json.dumps(result, sort_keys=True)); return 0
    except Exception as error:
        print(json.dumps({'status': 'BLOCKED', 'reason': error.args[0] if isinstance(error, RepairUnavailable)
                          else 'PROTECTED_STOPPED_REPAIR_METADATA_UNAVAILABLE'})); return 2


if __name__ == '__main__':
    raise SystemExit(main())
