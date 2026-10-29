"""Stopped repair cannot erase effects, self-certify images or reuse an old phase."""
from contextlib import contextmanager
import copy
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import stat
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[3] / 'deploy/m1/rsi_stopped_repair.py'
spec = importlib.util.spec_from_file_location('stopped_repair_test', SOURCE)
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)
ROOT_LINUX = pytest.mark.skipif(os.name != 'posix' or os.geteuid() != 0, reason='real Linux Root custody')


def write(path, value, uid=0, gid=0, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = value if isinstance(value, bytes) else repair.encoded(value)
    path.write_bytes(raw)
    os.chown(path, uid, gid); os.chmod(path, mode)
    return raw


def db_file(path, sql, uid=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    try:
        db.executescript(sql); db.commit()
    finally:
        db.close()
    os.chown(path, uid, uid); os.chmod(path, 0o600)


@pytest.fixture
def deployed(tmp_path, monkeypatch):
    if os.name != 'posix' or os.geteuid() != 0:
        pytest.skip('Linux Root fixture')
    root = tmp_path / 'deployment'; root.mkdir(mode=0o700)
    (root / 'config').mkdir(mode=0o700)
    local = repair.sibling('rsi_local')
    security = repair.sibling('rsi_security_setup')
    for name, (uid, gid, mode) in local.DIRECTORIES.items():
        path = root / name
        path.mkdir(exist_ok=True)
        os.chown(path, uid, gid); os.chmod(path, mode)
    old = {'app': 'sha256:' + 'a' * 64, 'rsi': 'sha256:' + 'b' * 64, 'worker': 'sha256:' + 'c' * 64}
    new = {'app': 'sha256:' + 'd' * 64, 'rsi': 'sha256:' + 'e' * 64, 'worker': 'sha256:' + 'f' * 64}
    cg = root / 'cgroups'; cg.mkdir(); (cg / 'cgroup.procs').write_text('')
    manifest = {'schema': 'ai4r-rsi-local:3', 'root': str(root), 'project': 'ai4r-rsi-original',
        'images': old, 'key_id': 'test-key', 'cgroup_host': str(cg), 'docker_host': local.NATIVE_DOCKER_HOST,
        'model_backend': 'host-codex', 'model_account_root': '/var/lib/ai4r-rsi-host-codex-client'}
    manifest_raw = write(root / 'local.json', manifest)
    # Only the native status observation is replaced; actual Root metadata and
    # immutable SQLite readers remain in use in the test.
    local.validate_backend = lambda value: None
    local.load_manifest = lambda path: repair.closed_json(repair.read(path))
    paths = security.phase_paths(manifest, 'draft')
    for name, (_, uid, gid, mode) in security.PHASE_ROOTS.items():
        paths[name].mkdir(parents=True); os.chown(paths[name], uid, gid); os.chmod(paths[name], mode)
    write(paths['broker-config'], {'old': 'protected capability remains private'})
    write(paths['validation-control'] / 'runtime.json', {'schema': 'test-original'})
    (paths['validation-control'] / 'public').mkdir(mode=0o755)
    db_file(paths['validation-campaign'] / 'state/research.sqlite3', 'CREATE TABLE records(id TEXT,kind TEXT);CREATE TABLE artifacts(id TEXT);')
    for name, prior in (('operational-bootstrap', None), ('operational-bootstrap.current', ['legacy'])):
        namespace = root / 'controller' / name
        namespace.mkdir(mode=0o700); os.chown(namespace, 12001, 12001)
        write(namespace / 'bootstrap.json', {'prior_namespaces': prior or []}, 12001, 12001)
        db_file(namespace / 'native-leases/index.sqlite', 'CREATE TABLE native_effect_leases(state TEXT);INSERT INTO native_effect_leases VALUES (\'complete\');', 12001)
        db_file(namespace / 'core/state/research.sqlite3', 'CREATE TABLE records(id TEXT,kind TEXT);CREATE TABLE artifacts(id TEXT,sha256 TEXT);', 12001)
    private = root / 'custodian/fixture-review'
    private.mkdir(mode=0o700); os.chown(private, 12002, 12002)
    db_file(private / 'index.sqlite', ';'.join('CREATE TABLE ' + name + '(x TEXT)' for name in repair.NO_SESSION_TABLES) + ';', 12002)
    host = tmp_path / 'native'; host.mkdir(mode=0o700); (host / 'relay').mkdir(mode=0o700)
    db_file(host / 'relay/requests.sqlite3', 'CREATE TABLE requests(id TEXT,digest TEXT,result TEXT);')
    qualification = {'helper_sha256': '1' * 64}
    qualified = tmp_path / 'qualification.json'; write(qualified, qualification, mode=0o400)
    monkeypatch.setattr(repair, 'HOST_ROOT', host)
    monkeypatch.setattr(repair, 'HOST_SOCKET', tmp_path / 'absent.sock')
    monkeypatch.setattr(repair, 'QUALIFICATION', qualified)
    native = SimpleNamespace(load=lambda: {'policy_sha256': '2' * 64, 'qualification': qualification})
    original_sibling = repair.sibling
    monkeypatch.setattr(repair, 'sibling', lambda name: {'rsi_local': local, 'rsi_security_setup': security, 'rsi_host_codex': native}.get(name) or original_sibling(name))
    snapshot_raw = repair.encoded({'schema': 'rsi-public-build-snapshot:2', 'files': []})
    images = {'schema': 'rsi-native-model-images:1', 'runtime': new['app'], 'controller': new['rsi'], 'worker': new['worker'],
        'base_controller': 'sha256:' + '3' * 64, 'base_worker': 'sha256:' + '4' * 64,
        'source_snapshot': repair.digest(snapshot_raw), 'qualification': False}
    installed = [{'role': role, 'image': images[role], 'build_id': '5' * 64, 'frozen_corpus_files': 87,
        'installed_files': 3200, 'qualification': False, 'status': 'INSTALLED_BYTES_VERIFIED'} for role in ('runtime', 'controller', 'worker')]
    policy = {'sha256': '2' * 64, 'model': 'gpt-6.1-sol', 'reasoning_effort': 'medium', 'source_sha256': {'research/local_model_codex.py': '1' * 64}}
    policies = [{'role': role, 'image': images[role], 'status': 'EXACT_INSTALLED_HOST_POLICY_VERIFIED', 'policy': policy, 'inference_performed': False} for role in ('runtime', 'controller', 'worker')]
    state = {'Status': 'exited', 'Running': False, 'Pid': 0, 'ExitCode': 2, 'OOMKilled': False,
        'Restarting': False, 'StartedAt': '2026-10-26T04:00:00Z', 'FinishedAt': '2026-10-26T04:00:01Z'}
    failure = {'schema': 'ai4r-rsi-safe-security-startup-stop:1', 'container_id': '6' * 64,
        'image': old['worker'], 'state': copy.deepcopy(state), 'event_counts': {'create': 1, 'start': 1, 'die': 1},
        'event_bytes_sha256': '7' * 64, 'campaign_record_counts': {}, 'worker_directory_empty': True,
        'visible_socket_directory_empty': True, 'hidden_socket_directory_empty': True,
        'public_metadata_directory_empty': True, 'approval_present': False, 'security_cases_executed': 0,
        'timing_captures_executed': 0, 'model_dispatch_by_observer': False}
    dependency = {'schema': 'ai4r-rsi-observed-build-dependency:1', 'image': repair.DEPENDENCY_IMAGE,
                  'build_id': '8' * 64, 'uv_lock_sha256': '9' * 64, 'files': []}
    proofs = {'images': images, 'installed': installed, 'policy': policies, 'snapshot': json.loads(snapshot_raw), 'failure': failure, 'dependency': dependency}
    monkeypatch.setattr(repair, 'observe_dependency', lambda: copy.deepcopy(dependency))
    request = {'schema': 'ai4r-rsi-stopped-repair-input:1', 'generation': 'repair-one', 'authorization': 'User explicitly authorizes fixing the failed setup and a new bounded run.',
        'bootstrap_generation': 'current', 'failed_container_id': '6' * 64,
        'old_manifest_sha256': repair.digest(manifest_raw), 'new_project': 'ai4r-rsi-repaired',
        'proof_sha256': {k: repair.digest(repair.encoded(v)) for k, v in proofs.items()}}
    folder = root / 'config/stopped-repair-inputs/repair-one'
    input_path = folder / 'input.json'; write(input_path, request)
    for key, filename in repair.PROOF_FILES.items(): write(folder / filename, proofs[key])
    launch = {'command': ['docker', '--project-name', manifest['project']],
        'environment': {'AI4R_JOB_ID': manifest['project'], 'AI4R_RSI_WORKER_IMAGE': old['worker']}}
    prior = root / 'config/security-execution.current'
    write(prior / 'worker-plan.json', launch)
    write(prior / 'worker-launch-claim.json', {'review_sha256': repair.digest(repair.encoded(launch))})
    write(prior / 'producer.json', {'container_id': request['failed_container_id'],
        'process': {'container_id': request['failed_container_id'], 'image': old['worker'], 'started_at': state['StartedAt']}})
    labels = {'com.docker.compose.project': manifest['project'], 'com.docker.compose.service': 'rsi-worker-broker'}
    mounts = [{'Destination': target, 'Source': str(source), 'RW': rw, 'Type': 'bind'} for target, source, rw in (
        ('/var/lib/ai4r-rsi-worker', paths['worker'], True), ('/run/ai4r-rsi-validation', paths['validation-control'], False),
        ('/run/ai4r-rsi-validation/public', paths['validation-public'], True),
        ('/var/lib/ai4r-rsi-validation-campaign', paths['validation-campaign'], True),
        ('/run/ai4r-rsi-worker/broker-service.json', paths['broker-config'], False))]
    checked = []
    def docker(*args):
        if args[:2] == ('image', 'inspect'):
            return repair.encoded({'id': args[2], 'os': 'linux', 'architecture': 'amd64'})
        if args[0] == 'ps': return (request['failed_container_id'] + '\n').encode()
        if args[0] == 'events': return b'{"Action":"create"}\n{"Action":"start"}\n{"Action":"die"}\n'
        if args[:2] == ('inspect', '--format'):
            return b'|'.join((repair.encoded(state), old['worker'].encode(), repair.encoded(labels), b'2026-10-26T03:59:59Z', repair.encoded(mounts)))
        if args[0] == 'inspect': return repair.encoded(mounts)
        pytest.fail('Unexpected effect-bearing Docker command: ' + args[0])
    monkeypatch.setattr(repair, '_docker', docker)
    def observed_image(image, role, snapshot_path, policy_sha):
        checked.append(role)
        return {'installed': {k: v for k, v in next(row for row in installed if row['role'] == role).items() if k not in {'role', 'image'}},
            'policy': copy.deepcopy(policy), 'source_snapshot_sha256': repair.digest(snapshot_path.read_bytes()), 'inference_performed': False}
    monkeypatch.setattr(repair, 'observe_image', observed_image)
    return SimpleNamespace(root=root, request=request, proofs=proofs, input=input_path, paths=paths, state=state,
        manifest=manifest, checked=checked, mounts=mounts, host=host, local=local, security=security)


@ROOT_LINUX
def test_real_stopped_metadata_plan_apply_preserves_sql_originals_and_old_phase(deployed):
    env = deployed
    old_files = {p: repair.digest(p.read_bytes()) for p in (env.root / 'controller').rglob('*') if p.is_file()}
    old_files.update({p: repair.digest(p.read_bytes()) for p in (env.paths['broker-config'], env.paths['validation-control'] / 'runtime.json', env.host / 'relay/requests.sqlite3')})
    reviewed = repair.plan(env.root, env.input)
    assert set(env.checked) == {'runtime', 'controller', 'worker'}
    assert reviewed['new_manifest']['project'] != env.manifest['project']
    assert not (env.root / 'config/stopped-repair-claims').exists()
    result = repair.apply(env.root, env.input, repair.digest(repair.encoded(reviewed)))
    assert result['model_calls'] == 0 and result['candidate_admitted'] is False
    assert all(repair.digest(p.read_bytes()) == sha for p, sha in old_files.items())
    repair.verify_repair_complete(env.root)
    new_paths = env.security.phase_paths(reviewed['new_manifest'], 'draft')
    assert new_paths['worker'] == env.root / 'security-phases/draft.repair-one/worker'
    assert new_paths['broker-config'].name == 'broker-service-draft.repair-one.json'
    assert env.security.phase_paths(reviewed['new_manifest'], 'final')['worker'] == env.root / 'worker'
    assert env.paths['worker'].is_dir() and not new_paths['worker'].exists()


@ROOT_LINUX
@pytest.mark.parametrize('mutation', ['lease', 'candidate', 'security-record', 'security-raw-capture', 'approval', 'active-pid', 'cgroup', 'mount', 'relay-socket', 'unknown', 'final-root'])
def test_actual_stopped_guards_refuse_effects_without_manifest_mutation(deployed, mutation):
    env = deployed; before = (env.root / 'local.json').read_bytes()
    if mutation == 'lease':
        p = env.root / 'controller/operational-bootstrap/native-leases/index.sqlite'
        db = sqlite3.connect(p); db.execute("UPDATE native_effect_leases SET state='uncertain'"); db.commit(); db.close()
    elif mutation == 'candidate':
        db = sqlite3.connect(env.root / 'custodian/fixture-review/index.sqlite'); db.execute("INSERT INTO proposer_starts VALUES('claimed')"); db.commit(); db.close()
    elif mutation == 'security-record':
        db = sqlite3.connect(env.paths['validation-campaign'] / 'state/research.sqlite3'); db.execute("INSERT INTO records VALUES('case','security-case')"); db.commit(); db.close()
    elif mutation == 'security-raw-capture':
        db = sqlite3.connect(env.paths['validation-campaign'] / 'state/research.sqlite3'); db.execute("INSERT INTO artifacts VALUES('raw')"); db.commit(); db.close()
    elif mutation == 'approval': write(env.paths['validation-control'] / 'approval.json', {})
    elif mutation == 'active-pid': env.state.update(Status='running', Running=True, Pid=42)
    elif mutation == 'cgroup': (Path(env.manifest['cgroup_host']) / 'cgroup.procs').write_text('42\n')
    elif mutation == 'mount': env.mounts[0]['Source'] = '/another-phase'
    elif mutation == 'relay-socket': repair.HOST_SOCKET.write_bytes(b'not-a-real-socket-still-blocks')
    elif mutation == 'unknown':
        db = sqlite3.connect(env.host / 'relay/requests.sqlite3'); db.execute("INSERT INTO requests VALUES('new-unknown',?,NULL)", ('a' * 64,)); db.commit(); db.close()
    elif mutation == 'final-root': write(env.root / 'security/installation.json', {})
    with pytest.raises((ValueError, OSError)):
        repair.plan(env.root, env.input)
    assert (env.root / 'local.json').read_bytes() == before
    assert not (env.root / 'config/stopped-repair-claims').exists()


@ROOT_LINUX
@pytest.mark.parametrize('mutation', ['missing-selector', 'bad-selector', 'missing-completion', 'bad-completion', 'phase-tamper', 'manifest-tamper'])
def test_completed_or_partial_journal_never_falls_back_to_old_phase(deployed, mutation):
    env = deployed; reviewed = repair.plan(env.root, env.input)
    repair.apply(env.root, env.input, repair.digest(repair.encoded(reviewed)))
    config = env.root / 'config'
    if mutation == 'missing-selector': (config / 'security-phase-current.json').unlink()
    elif mutation == 'bad-selector': write(config / 'security-phase-current.json', {'schema': 'ai4r-rsi-security-phase-selector:1', 'generation': 'other', 'receipt_sha256': '0' * 64})
    elif mutation == 'missing-completion': (config / 'stopped-repair-applied/repair-one.json').unlink()
    elif mutation == 'bad-completion': write(config / 'stopped-repair-applied/repair-one.json', {})
    elif mutation == 'phase-tamper': write(config / 'security-phase-generations/repair-one.json', {})
    else: write(env.root / 'local.json', env.manifest)
    with pytest.raises((ValueError, OSError, KeyError)):
        repair.verify_repair_complete(env.root)
    with pytest.raises((ValueError, OSError, KeyError)):
        env.security.phase_paths(reviewed['new_manifest'], 'draft')


@ROOT_LINUX
def test_changed_actual_image_result_cannot_be_replaced_by_root_json_status(deployed, monkeypatch):
    env = deployed
    def forged(*args):
        return {'installed': {}, 'policy': {}, 'source_snapshot_sha256': '0' * 64, 'inference_performed': False}
    monkeypatch.setattr(repair, 'observe_image', forged)
    with pytest.raises(ValueError, match='ACTUAL_INSTALLED_IMAGE_PROOF_DIFFERS'):
        repair.plan(env.root, env.input)


@ROOT_LINUX
def test_dependency_claim_must_equal_independent_actual_inventory(deployed, monkeypatch):
    monkeypatch.setattr(repair, 'observe_dependency', lambda: {'image': 'sha256:' + '0' * 64})
    with pytest.raises(ValueError, match='ACTUAL_BUILD_DEPENDENCY_PROOF_DIFFERS'):
        repair.plan(deployed.root, deployed.input)


def test_snapshot_and_inherited_joins_are_exclusive_and_validate_actual_bytes(monkeypatch):
    captured = []
    monkeypatch.setattr(repair, '_docker', lambda *args: captured.append(args) or b'{}')
    repair.observe_image('sha256:' + 'a' * 64, 'worker', Path('/safe/snapshot.json'), 'b' * 64)
    code = captured[0][-1]
    assert "if origin=='snapshot':assert files['jiuwenswarm/'+row['path']]==row['sha256']" in code
    assert "elif origin=='dependency':assert inherited[row['path']]==row" in code
    assert "reuse['dependency_image_id']==EXPECTED_DEPENDENCY" in code
    assert "len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']" in code


def test_exact_frozen_builder_origin_overrides_tui_source_and_requires_web_absence():
    tui = 'channels/tui/frontend/package.json'
    web = 'channels/web/frontend/dist/index.html'
    files = {'jiuwenswarm/' + tui: 'a' * 64, 'jiuwenswarm/research/example.py': 'b' * 64}
    assert repair.expected_origin(tui, files) == 'dependency'
    assert repair.expected_origin(web, files) == 'dependency'
    files['jiuwenswarm/' + web] = 'c' * 64
    assert repair.expected_origin(web, files) == 'snapshot'
    assert repair.expected_origin('research/example.py', files) == 'snapshot'
    assert repair.expected_origin('unproven/generated.py', files) is None


@ROOT_LINUX
@pytest.mark.parametrize('mutation', [None, 'extra-runtime-job', 'broken-ref', 'unlinked-review', 'unsigned-review', 'wrong-owner'])
def test_only_complete_linked_fixture_admin_jobs_are_preserved(deployed, mutation):
    path = deployed.root / 'custodian/fixture-review/index.sqlite'
    db_file(path, 'CREATE TABLE jobs(id TEXT,ref TEXT,state TEXT,result TEXT);', 12002)
    root = path.parent
    def put(value):
        raw = repair.encoded(value); sha = repair.digest(raw)
        write(root / (sha + '.json'), raw, 12002, 12002)
        return {'id': sha + '.json', 'sha256': sha}
    def pin(number): return {'id': 'public-metadata:' + str(number), 'sha256': f'{number:064x}'}
    packet = {'status': 'PRIVATE_REVIEW_PACKET_PREPARED', 'request_ref': pin(1), 'preparation_ref': pin(2),
        'packet_ref': pin(3), 'review_completed': False, 'publication_performed': False}
    authority = {'schema': 'ai4r-rsi-fixture-review-authority:1', **{k: packet[k] for k in ('request_ref', 'preparation_ref', 'packet_ref')}, 'reviewer': 'independent-reviewer'}
    if mutation == 'wrong-owner': authority['reviewer'] = 'another-owner'
    decisions = {k: True for k in ('independent', 'overlap_inventory_complete', 'provenance_approved', 'development_disclosure_approved')}
    evidence = {'schema': 'ai4r-rsi-fixture-review-human-evidence:1', **{k: packet[k] for k in ('request_ref', 'preparation_ref', 'packet_ref')},
        'reviewer': 'independent-reviewer', 'recorded_at': '2026-10-26T00:00:00Z', 'inspected_sections': ['summary', 'parent', 'generator', 'fixtures', 'lineage', 'controls'],
        'decisions': decisions, 'independence_reason': 'Independently reviewed', 'owner_findings': 'Actual owner findings', 'authority_record_ref': put(authority)}
    review = {'schema': 'ai4r-rsi-ranking-review:1', 'preparation_ref': packet['preparation_ref'], 'reviewer': 'independent-reviewer', **decisions,
        'independence_reason': evidence['independence_reason'], 'evidence_refs': [put(evidence)]}
    if mutation == 'unlinked-review': review['preparation_ref'] = pin(4)
    if mutation == 'unsigned-review': review['evidence_refs'] = []
    prepared_pin = put(packet); review_pin = put(review)
    db = sqlite3.connect(path)
    db.execute('INSERT INTO jobs VALUES(?,?,?,NULL)', ('fixture-review-generation', json.dumps(prepared_pin), 'prepared'))
    db.execute('INSERT INTO jobs VALUES(?,?,?,NULL)', ('fixture-review:' + packet['packet_ref']['sha256'], json.dumps(review_pin), 'reviewed'))
    if mutation == 'extra-runtime-job': db.execute("INSERT INTO jobs VALUES('candidate-runtime','{}','running',NULL)")
    db.commit(); db.close()
    if mutation == 'broken-ref': write(root / review_pin['id'], {}, 12002, 12002)
    if mutation is None:
        assert repair.fixture_admin_jobs(path) == [prepared_pin, review_pin]
    else:
        with pytest.raises((ValueError, OSError)):
            repair.fixture_admin_jobs(path)


@ROOT_LINUX
def test_expired_docker_event_buffer_uses_original_proof_and_fresh_unchanged_state(deployed, monkeypatch):
    original = repair._docker
    monkeypatch.setattr(repair, '_docker', lambda *args: b'' if args[0] == 'events' else original(*args))
    reviewed = repair.plan(deployed.root, deployed.input)
    assert reviewed['facts']['failed_producer']['current_events_available'] is False
    assert reviewed['facts']['failed_producer']['retained_failure_sha256'] == deployed.request['proof_sha256']['failure']


@ROOT_LINUX
@pytest.mark.parametrize('mutation', ['cid', 'timestamp', 'count', 'proof-sha', 'fresh-restart'])
def test_retained_failure_cannot_rename_or_hide_a_new_lifecycle(deployed, mutation):
    env = deployed
    if mutation == 'fresh-restart': env.state['StartedAt'] = '2026-10-26T05:00:00Z'
    else:
        failure = copy.deepcopy(env.proofs['failure'])
        if mutation == 'cid': failure['container_id'] = '0' * 64
        elif mutation == 'timestamp': failure['state']['FinishedAt'] = '2026-10-26T05:00:00Z'
        elif mutation == 'count': failure['event_counts']['start'] = 2
        else: failure['event_bytes_sha256'] = 'not-a-hash'
        # Even a separately Root-pinned replacement body must satisfy joins.
        raw = write(env.input.parent / 'failure.json', failure)
        env.request['proof_sha256']['failure'] = repair.digest(raw)
        write(env.input, env.request)
    with pytest.raises(ValueError, match='RETAINED_ORIGINAL_FAILURE_PROOF_DIFFERS'):
        repair.plan(env.root, env.input)


@ROOT_LINUX
def test_review_change_refused_before_any_claim(deployed):
    with pytest.raises(ValueError, match='REVIEW_PLAN_CHANGED'):
        repair.apply(deployed.root, deployed.input, '0' * 64)
    assert not (deployed.root / 'config/stopped-repair-claims').exists()


@ROOT_LINUX
def test_partial_apply_claim_blocks_local_load_before_json_use(deployed, monkeypatch):
    env = deployed; reviewed = repair.plan(env.root, env.input)
    original_new = repair.new
    def crash(path, raw):
        if path.parent.name == 'security-phase-generations': raise OSError('simulated crash after durable claim')
        original_new(path, raw)
    monkeypatch.setattr(repair, 'new', crash)
    with pytest.raises(OSError): repair.apply(env.root, env.input, repair.digest(repair.encoded(reviewed)))
    with pytest.raises(ValueError, match='PARTIAL_STOPPED_REPAIR'):
        repair.verify_repair_complete(env.root)
    actual_local = repair.sibling('rsi_security_setup').local
    monkeypatch.setattr(actual_local, 'linux_storage', lambda *_: None)
    with pytest.raises(ValueError): actual_local.load_manifest(env.root / 'local.json')


def test_verifier_is_fixed_and_has_no_model_effect_or_arbitrary_program_seam(monkeypatch):
    captured = []
    monkeypatch.setattr(repair, '_docker', lambda *args: captured.append(args) or b'{}')
    repair.observe_image('sha256:' + 'a' * 64, 'worker', Path('/safe/snapshot.json'), 'b' * 64)
    command = captured[0]
    assert command[:7] == ('run', '--rm', '--pull', 'never', '--read-only', '--network', 'none')
    assert 'verify_installed_build()' in command[-1]
    assert "hashlib.sha256(raw).hexdigest()==row['sha256']" in command[-1]
    assert '/var/lib/ai4r-accounts' in command[-1]
    assert not any('codex-home' in arg or 'signing-key' in arg for arg in command)


def test_non_root_repair_and_duplicate_json_are_refused(monkeypatch):
    monkeypatch.setattr(repair.os, 'geteuid', lambda: 12001)
    with pytest.raises(ValueError, match='LINUX_ROOT_REQUIRED'): repair.root_identity()
    with pytest.raises(ValueError, match='DUPLICATE_JSON_FIELD'): repair.closed_json(b'{"x":1,"x":2}')


@ROOT_LINUX
@pytest.mark.parametrize('mutation', ['broken-claim-link', 'broken-applied-link', 'orphan-selector', 'orphan-phase'])
def test_missing_deployment_is_allowed_but_symlinks_and_orphans_are_not(tmp_path, mutation):
    root = tmp_path / 'not-yet-created'
    repair.verify_repair_complete(root)
    (root / 'config').mkdir(parents=True)
    config = root / 'config'
    if mutation == 'broken-claim-link': (config / 'stopped-repair-claims').symlink_to(tmp_path / 'missing')
    elif mutation == 'broken-applied-link': (config / 'stopped-repair-applied').symlink_to(tmp_path / 'missing')
    elif mutation == 'orphan-selector': write(config / 'security-phase-current.json', {})
    else:
        folder = config / 'security-phase-generations'; folder.mkdir(mode=0o700)
        write(folder / 'orphan.json', {})
    with pytest.raises((ValueError, OSError)):
        repair.verify_repair_complete(root)
