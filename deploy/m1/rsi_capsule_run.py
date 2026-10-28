"""Pinned Root evaluator and unprivileged normal governed capsule controller.

Preflight is read-only. Only ``run`` consumes the Root claim, forks an evaluator,
and permanently drops controller identity before composing Core/model owners.
"""
from __future__ import annotations
import argparse
import asyncio
import base64
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path, PurePosixPath
import re
import select
import signal
import stat
import subprocess
import sys
import time
import types

SCHEMA = 'ai4r-rsi-capsule-run-configuration:2'
PREFLIGHT_SCHEMA = 'ai4r-rsi-capsule-run-preflight:1'
MAX_CONFIG = 8 * 1024 * 1024
MAX_PIPE_FRAME = 4 * 1024 * 1024
COMPOSITION_SHA256 = '5ba11903f494c06cffaa56f40efae2b5cadee73711a3bc7dd2b9f7e04a6f8016'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_frame_deadline(stream, deadline):
    """Read one bounded frame while retaining coalesced subsequent frames."""
    pending = getattr(stream, '_capsule_pending_frames', None)
    if pending is None:
        pending = bytearray()
        stream._capsule_pending_frames = pending
    while True:
        boundary = pending.find(b'\n')
        if boundary >= 0:
            need(boundary <= MAX_PIPE_FRAME, 'PIPE_FRAME_TOO_LARGE')
            raw = bytes(pending[:boundary+1]); del pending[:boundary+1]
            return closed_json(raw)
        need(len(pending) <= MAX_PIPE_FRAME, 'PIPE_FRAME_TOO_LARGE')
        remaining = deadline-time.monotonic()
        need(remaining > 0, 'FINITE_PIPE_DEADLINE_EXPIRED')
        ready, _, _ = select.select([stream.fileno()], [], [], remaining)
        need(bool(ready), 'FINITE_PIPE_DEADLINE_EXPIRED')
        part = os.read(stream.fileno(), min(65536, MAX_PIPE_FRAME+1-len(pending)))
        if not part:
            need(not pending, 'TRUNCATED_PIPE_FRAME')
            return None
        pending.extend(part)


def closed_json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'DUPLICATE_JSON_FIELD')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: need(False, 'NONFINITE_JSON'))


def protected(path, *, directory=False):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts
         and not any(p.is_symlink() for p in (path, *path.parents)), 'REAL_ROOT_PATH_REQUIRED')
    for item in (path, *path.parents):
        meta = item.stat()
        need(meta.st_uid == 0 and not meta.st_mode & 0o022, 'ROOT_IMMUTABLE_CUSTODY_REQUIRED')
    meta = path.stat()
    need(stat.S_ISDIR(meta.st_mode) if directory else stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1,
         'ROOT_PATH_TYPE_REQUIRED')
    return path


def load_sources(value):
    root = protected(value['source_root'], directory=True)
    pins = value['source_pins']
    need(isinstance(pins, dict) and pins, 'PINNED_SOURCE_CLOSURE_REQUIRED')
    required = {'jiuwenswarm/research_rsi/' + item for item in (
        '__init__.py', 'capsule_session.py', 'records.py', 'diagnosis.py', 'proposer.py',
        'profiles.py', 'process_policy.py', 'session_policy.py', 'fixed_resources.py',
        'native_lease.py', 'capsule_doctor.py', 'targets/capsules.py', 'targets/capsule_runtime.py', 'targets/capsule_executor.py')}
    required |= {'jiuwenswarm/' + item for item in (
        '__init__.py', 'research/__init__.py', 'research/state.py', 'research/executor.py',
        'research/local_model_codex.py', 'research/local_model_relay.py', 'research/local_models.py',
        'research/private_rpc.py', 'research/resources/host_codex/model_catalog.json',
        'research_contracts/schemas/capsule-declaration.schema.json')}
    need(required <= set(pins), 'COMPLETE_CAPSULE_PACKAGE_CLOSURE_REQUIRED')
    for name, expected in pins.items():
        need(isinstance(name, str) and name.startswith('jiuwenswarm/')
             and not any(part in ('', '.', '..') for part in name.split('/'))
             and '\\' not in name and ':' not in name, 'FINITE_SOURCE_PATH_REQUIRED')
        path = protected(root / name)
        need(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected)
             and digest(path.read_bytes()) == expected, 'SOURCE_PIN_DIFFERS')
    actual = {path.relative_to(root).as_posix() for path in (root / 'jiuwenswarm').rglob('*')
              if path.is_file()}
    need(actual == set(pins), 'SOURCE_CLOSURE_INVENTORY_DIFFERS')
    # Load one complete, pinned package. Source-relative qualification and
    # schemas must observe the same bytes as imports; a research_rsi-only
    # overlay creates a split package and can pass an unrelated relay probe.
    for name, module in tuple(sys.modules.items()):
        if (name == 'jiuwenswarm' or name.startswith('jiuwenswarm.')) and getattr(module, '__file__', None):
            source = Path(module.__file__).resolve()
            need(source.is_relative_to(root) and source.relative_to(root).as_posix() in pins,
                 'PRELOADED_PACKAGE_MODULE_OUTSIDE_PINNED_CLOSURE')
    if 'jiuwenswarm' not in sys.modules:
        spec = importlib.util.spec_from_file_location('jiuwenswarm', root / 'jiuwenswarm/__init__.py',
            submodule_search_locations=[str(root / 'jiuwenswarm')])
        package = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = package; spec.loader.exec_module(package)
    path = protected(value['composition_path'])
    need(digest(path.read_bytes()) == value['composition_sha256'] == COMPOSITION_SHA256, 'FROZEN_COMPOSITION_PIN_DIFFERS')
    name = 'deploy.m1.rsi_development_run'
    for package_name in ('deploy', 'deploy.m1'):
        if package_name not in sys.modules:
            module = types.ModuleType(package_name); module.__path__ = []
            sys.modules[package_name] = module
    spec = importlib.util.spec_from_file_location(name, path)
    composition = importlib.util.module_from_spec(spec)
    sys.modules[name] = composition; spec.loader.exec_module(composition)
    return composition


def validate_configuration(value):
    fields = {'schema', 'session', 'composition', 'evaluator', 'claim_path', 'result_path',
        'source_root', 'source_pins', 'composition_path', 'composition_sha256', 'compatibility'}
    need(isinstance(value, dict) and set(value) == fields and value['schema'] == SCHEMA,
         'CLOSED_ROOT_CAPSULE_RUN_CONFIGURATION_REQUIRED')
    compatibility = value['compatibility']
    need(isinstance(compatibility, dict) and set(compatibility) == {'path', 'sha256'}
         and isinstance(compatibility['path'], str), 'CLOSED_COMPOSE_DOCTOR_BINDING_REQUIRED')
    composition = value['composition']
    need(isinstance(composition, dict) and set(composition) == {
        'core_root', 'input_root', 'record_root', 'native_lease_root', 'account_root', 'work_root',
        'principal', 'exact_binding_refs', 'work_capsule_refs', 'run_contexts'}, 'CLOSED_COMPOSITION_REQUIRED')
    evaluator = value['evaluator']
    need(isinstance(evaluator, dict) and set(evaluator) == {
        'root', 'runtime_root', 'manifest', 'metadata', 'grant_path', 'grant_sha256', 'cgroup_root'}, 'CLOSED_EVALUATOR_REQUIRED')
    for key in ('core_root', 'input_root', 'record_root', 'native_lease_root', 'account_root', 'work_root'):
        path = Path(composition[key])
        need(path.is_absolute() and '..' not in path.parts, 'ABSOLUTE_COMPOSITION_PATH_REQUIRED')
    from jiuwenswarm.research_rsi.capsule_session import validate_session
    from jiuwenswarm.research_rsi.targets.capsule_executor import validate_grant
    session = validate_session(value['session'])
    validate_grant(session['grant'], evaluator['manifest'])
    metadata = evaluator['metadata']
    need(isinstance(metadata, dict) and set(metadata) == {'contract', 'environment', 'hardware'},
         'EXACT_PUBLIC_WORKER_METADATA_REQUIRED')
    from jiuwenswarm.research_rsi.records import encoded
    for key, record in metadata.items():
        need(isinstance(record, dict) and digest(encoded(record)) == session['grant']['worker'][key+'_ref']['sha256'],
             'EXACT_PUBLIC_WORKER_METADATA_PIN_REQUIRED')
    need(session['configuration_ref'] == composition['exact_binding_refs']['configuration_ref'],
         'EXACT_COMPOSITION_CONFIGURATION_REQUIRED')
    need(set(composition['run_contexts']) == {
        'rsi-development:' + session['id'] + ':' + role for role in ('diagnosis', 'proposal')},
        'EXACT_OWN_SESSION_WORK_CONTEXTS_REQUIRED')
    return value


def readonly_relay_fact(value):
    """Observe the actual fixed transport under its private controller identity.

    Host Python needs the immutable base paths explicitly because -I ignores
    PYTHONPATH. The V18 worker already has the installed package. This literal
    child opens only the existing readonly relay status owner, never Core,
    model work, a lease, or a run claim.
    """
    script = r'''import asyncio,hashlib,importlib.util,json,os,sys
from pathlib import Path
for path in reversed(('/opt/ai4r-rsi-frozen-v18-03ed3199','/opt/ai4r-rsi-host-codex/site-packages')):
 if Path(path).is_dir():sys.path.insert(0,path)
assert os.getuid()==os.geteuid()==12001 and os.getgid()==os.getegid()==12001 and os.getgroups()==[13000]
path=Path(sys.argv[2])
assert hashlib.sha256(path.read_bytes()).hexdigest()=='5ba11903f494c06cffaa56f40efae2b5cadee73711a3bc7dd2b9f7e04a6f8016'
spec=importlib.util.spec_from_file_location('_capsule_readonly_composition',path)
helper=importlib.util.module_from_spec(spec);sys.modules[spec.name]=helper;spec.loader.exec_module(helper)
fact=asyncio.run(helper.relay_idle_fact(Path(sys.argv[1])))
assert set(fact)=={'binding_sha256','policy_sha256','active','unresolved','status_sha256'}
assert fact['active'] is False and fact['unresolved'] is False
raw=json.dumps(fact,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
assert len(raw)<=16384
sys.stdout.buffer.write(raw)
'''
    # load_sources already validated this exact immutable composition; check
    # again before handing its path to the child of the private native owner.
    composition = protected(value['composition_path'])
    need(digest(composition.read_bytes()) == value['composition_sha256'] == COMPOSITION_SHA256,
         'READONLY_NATIVE_COMPOSITION_DIFFERS')
    result = subprocess.run([sys.executable, '-I', '-B', '-c', script,
        value['composition']['account_root'], str(composition)], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, check=False,
        user=12001, group=12001, extra_groups=[13000], close_fds=True,
        env={'PATH':'/usr/local/bin:/usr/bin:/bin', 'LANG':'C.UTF-8', 'PYTHONDONTWRITEBYTECODE':'1'})
    need(result.returncode == 0 and len(result.stdout) <= 16384,
         'CONTROLLER_READONLY_RELAY_STATUS_UNAVAILABLE')
    fact = closed_json(result.stdout)
    need(isinstance(fact, dict) and set(fact) == {
        'binding_sha256', 'policy_sha256', 'active', 'unresolved', 'status_sha256'}
        and fact['active'] is False and fact['unresolved'] is False,
         'CLOSED_IDLE_NATIVE_RELAY_REQUIRED')
    for key in ('binding_sha256', 'policy_sha256', 'status_sha256'):
        need(isinstance(fact[key], str) and re.fullmatch('[0-9a-f]{64}', fact[key]) is not None,
             'EXACT_NATIVE_RELAY_STATUS_DIGEST_REQUIRED')
    return fact


def compose_doctor_scope(value):
    """Bind actual composition and package bytes without a receipt hash cycle."""
    return digest(json.dumps({key: item for key, item in value.items() if key != 'compatibility'},
        sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf8'))


def require_compose_doctor(value):
    compatibility = value['compatibility']
    raw = protected(compatibility['path']).read_bytes()
    need(len(raw) <= 1024 * 1024 and digest(raw) == compatibility['sha256'],
         'ROOT_COMPOSE_DOCTOR_RECEIPT_DIGEST_DIFFERS')
    proof = closed_json(raw)
    need(isinstance(proof, dict) and proof.get('schema') == 'ai4r-rsi-capsule-compose-doctor:1'
         and proof.get('scope_sha256') == compose_doctor_scope(value)
         and proof.get('status') == 'COMPATIBLE' and proof.get('actual_frozen_compose_completed') is True
         and proof.get('originals_unchanged') is True
         and proof.get('model_calls') == proof.get('tool_calls') == proof.get('execution_jobs') == 0
         and proof.get('work_claims') == 0 and proof.get('native_starts') == 0,
         'ACTUAL_SCOPED_MODEL_FREE_COMPOSE_DOCTOR_REQUIRED')
    expected = value['evaluator']['manifest']['python']
    need(proof.get('python') == {'version': expected['version'],
         'executable_sha256': expected['executable_sha256']}, 'EXACT_WORKER_COMPOSE_DOCTOR_RUNTIME_REQUIRED')
    return proof


def preflight(configuration_path, configuration_sha256):
    need(os.name == 'posix' and os.geteuid() == 0, 'ROOT_CAPSULE_RUNNER_REQUIRED')
    path = protected(configuration_path)
    need(path.stat().st_size <= MAX_CONFIG, 'BOUNDED_ROOT_CONFIGURATION_REQUIRED')
    raw = path.read_bytes()
    need(digest(raw) == configuration_sha256, 'ROOT_CONFIGURATION_DIGEST_DIFFERS')
    value = closed_json(raw)
    # Check closed top-level shape before following any source path.
    need(isinstance(value, dict) and set(value) == {'schema', 'session', 'composition', 'evaluator',
        'claim_path', 'result_path', 'source_root', 'source_pins', 'composition_path', 'composition_sha256', 'compatibility'}
        and value['schema'] == SCHEMA, 'CLOSED_ROOT_CAPSULE_RUN_CONFIGURATION_REQUIRED')
    load_sources(value)
    validate_configuration(value)
    from jiuwenswarm.research_rsi.targets.capsule_runtime import verify_runtime, BOOTSTRAP_SCHEMA
    from jiuwenswarm.research_rsi.records import encoded
    evaluator, session = value['evaluator'], value['session']
    grant_raw = protected(evaluator['grant_path']).read_bytes()
    need(digest(grant_raw) == evaluator['grant_sha256']
         and grant_raw == encoded(session['grant']), 'EXACT_PREPARED_ROOT_GRANT_REQUIRED')
    need(time.time() < session['grant']['expires_unix_s'], 'ROOT_GRANT_EXPIRED')
    verify_runtime(protected(evaluator['runtime_root'], directory=True), evaluator['manifest'])
    protected(evaluator['root'], directory=True)
    protected(evaluator['cgroup_root'], directory=True)
    claim = Path(value['claim_path'])
    protected(claim.parent, directory=True)
    need(not claim.exists() and not claim.is_symlink(), 'ROOT_CLAIM_ALREADY_EXISTS_NO_REPLAY')
    for key in ('core_root', 'input_root', 'record_root', 'native_lease_root', 'account_root', 'work_root'):
        directory = Path(value['composition'][key])
        need(not any(p.is_symlink() for p in (directory, *directory.parents)), 'CONTROLLER_DIRECTORY_SYMLINK_REFUSED')
        meta = directory.stat()
        need(stat.S_ISDIR(meta.st_mode) and meta.st_uid == 12001 and not meta.st_mode & 0o027,
             'PRIVATE_CONTROLLER_OWNED_DIRECTORY_REQUIRED')
    result = Path(value['result_path'])
    need(result.is_absolute() and not result.exists() and not result.is_symlink()
         and result.parent.resolve() == Path(value['composition']['record_root']).resolve(),
         'FRESH_CONTROLLER_RESULT_REQUIRED')
    doctor_proof = require_compose_doctor(value)
    relay_fact = readonly_relay_fact(value)
    need(doctor_proof.get('native_policy_sha256') == relay_fact['policy_sha256']
         and doctor_proof.get('native_binding_sha256') == relay_fact['binding_sha256'],
         'COMPOSE_DOCTOR_NATIVE_BINDING_DIFFERS')
    return value, {'schema': PREFLIGHT_SCHEMA, 'id': session['id'],
        'configuration_sha256': configuration_sha256, 'grant_sha256': evaluator['grant_sha256'],
        'bootstrap_schema': BOOTSTRAP_SCHEMA, 'maximum_executions': session['grant']['max_executions'],
        'model_calls': 0, 'ready': True}


def capture_closure(store, value):
    """Transfer exact public Root records, recursively including receipt bytes."""
    pending = [value]; seen = set()
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if set(item) == {'id', 'sha256'}:
                key = (item['id'], item['sha256'])
                if key in seen:
                    continue
                seen.add(key)
                try:
                    raw = store.read(item)
                except FileNotFoundError:
                    # Worker/environment contracts are external immutable pins,
                    # not public bytes created by this evaluator.
                    continue
                yield {'ref': item, 'bytes_base64': base64.b64encode(raw).decode('ascii')}
                try:
                    pending.append(closed_json(raw))
                except (ValueError, UnicodeError):
                    pass
            else:
                pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


async def evaluator(value, incoming, outgoing, configuration_sha256, helper):
    from jiuwenswarm.research_rsi.records import RecordStore
    from jiuwenswarm.research_rsi.targets.capsule_executor import WholeCapsuleDispatcher
    config = value['evaluator']; root = Path(config['root'])
    captures = RecordStore(root / 'captures')
    for key, record in config['metadata'].items():
        need(captures.put(record) == value['session']['grant']['worker'][key+'_ref'],
             'EXACT_PUBLIC_WORKER_METADATA_IDENTITY_REQUIRED')
    dispatcher = WholeCapsuleDispatcher(root=root, runtime_root=config['runtime_root'],
        manifest=config['manifest'], grant_path=config['grant_path'], grant_sha256=config['grant_sha256'],
        cgroup_root=config['cgroup_root'], captures=captures)
    plan = dispatcher.plan()
    helper.write_frame(outgoing, {'ready': True, 'plan': plan})
    try:
        for role in ('parent', 'candidate'):
            request = await asyncio.to_thread(read_frame_deadline, incoming, dispatcher.deadline)
            if request is None:
                break
            need(isinstance(request, dict) and set(request) == {'role', 'body_base64', 'candidate_ref', 'binding'}
                 and request['role'] == role, 'CLOSED_ORDERED_CAPSULE_EVALUATION_REQUIRED')
            body = base64.b64decode(request['body_base64'], validate=True)
            result = await dispatcher.evaluate(role, body=body, candidate_ref=request['candidate_ref'], binding=request['binding'])
            for capture in capture_closure(captures, result):
                helper.write_frame(outgoing, {'capture': capture})
            helper.write_frame(outgoing, {'evaluation': result})
            if not result['passed']:
                break
        helper.exclusive(root / 'complete.json', {
            'schema': 'ai4r-rsi-capsule-evaluator-completion:1', 'id': value['session']['id'],
            'configuration_sha256': configuration_sha256, 'grant_ref': dispatcher.grant_ref,
            'plan': plan, 'status': 'STOPPED', 'executions': dispatcher.executions,
            'halted': dispatcher.halted, 'completed_roles': list(dispatcher.completed)})
    finally:
        captures.close()


async def controller(value, incoming, outgoing, helper, *, evaluator_pid=None, effect_deadline=None, progress=None):
    runtime = None
    async def evaluate(role, *, body, candidate_ref, binding):
        helper.write_frame(outgoing, {'role': role, 'body_base64': base64.b64encode(body).decode('ascii'),
            'candidate_ref': candidate_ref, 'binding': binding})
        deadline = time.monotonic() + value['session']['grant']['limits']['wall_s']
        while True:
            frame = await asyncio.to_thread(read_frame_deadline, incoming, deadline)
            need(isinstance(frame, dict), 'ROOT_EVALUATOR_CLOSED_WITHOUT_RESULT')
            if set(frame) == {'capture'}:
                capture = frame['capture']
                need(isinstance(capture, dict) and set(capture) == {'ref', 'bytes_base64'}, 'EXACT_ROOT_CAPTURE_REQUIRED')
                raw = base64.b64decode(capture['bytes_base64'], validate=True)
                runtime.records.put_ref(capture['ref'], raw)
                continue
            need(set(frame) == {'evaluation'}, 'UNKNOWN_ROOT_EVALUATOR_FRAME')
            result = frame['evaluation']
            from jiuwenswarm.research_rsi.capsule_session import validate_evaluation
            from jiuwenswarm.research_rsi.targets.capsule_runtime import capsule_worker_program, BOOTSTRAP_SCHEMA
            from jiuwenswarm.research_rsi.records import encoded
            validate_evaluation(result, value['session'], role, candidate_ref)
            need(runtime.store.get(result['result_ref']) == {key: item for key, item in result.items() if key != 'result_ref'},
                 'EXACT_ROOT_RESULT_CAPTURE_REQUIRED')
            for row in result['rows']:
                need(runtime.store.get(row['evidence_ref']) == {key: item for key, item in row.items() if key != 'evidence_ref'},
                     'EXACT_ROOT_ROW_CAPTURE_REQUIRED')
                expected = capsule_worker_program(value['session']['capsule_name'],
                    manifest_sha256=value['session']['grant']['runtime_manifest_sha256'],
                    candidate_sha256=candidate_ref['sha256'], input_sha256=row['input_ref']['sha256'],
                    iterations=value['session']['grant']['iterations'])
                need(row['bootstrap_schema'] == BOOTSTRAP_SCHEMA and row['program_ref']['sha256'] == digest(expected),
                     'EXACT_GUARDED_BOOTSTRAP_PROGRAM_REQUIRED')
            return result
    try:
        composition = dict(value['composition'])
        composition.update({key: value['session'][key] for key in (
            'id', 'native_scope_ref', 'diagnosis_contract_ref', 'proposal_contract_ref')})
        if progress is not None: progress['phase'] = 'COMPOSING'
        runtime = await helper.compose(composition, evaluate)
        runtime.development_model_factory = helper.DevelopmentModel
        governed_before_model = runtime.before_model
        model_deadline = (effect_deadline if effect_deadline is not None else
                          time.monotonic() + value['session']['grant']['limits']['wall_s'])
        async def before_model():
            need(time.time() < value['session']['grant']['expires_unix_s']
                 and time.monotonic() < model_deadline, 'MODEL_START_AFTER_ROOT_GRANT_DEADLINE')
            if evaluator_pid is not None:
                need(os.waitid(os.P_PID, evaluator_pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None,
                     'ROOT_EVALUATOR_EXITED_BEFORE_MODEL_START')
            await governed_before_model()
        runtime.before_model = before_model
        from jiuwenswarm.research_rsi.capsule_session import run_session
        if progress is not None: progress['phase'] = 'SESSION'
        return await run_session(value['session'], runtime)
    finally:
        if runtime is not None:
            close = getattr(runtime.subscription.transport, 'close', None)
            if close is not None:
                pending = close()
                if inspect.isawaitable(pending):
                    await pending
            runtime.records.close(); runtime.lease_records.close(); runtime.core.close()


def owner_record(value, ack, role):
    state = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
    argv = Path('/proc/self/cmdline').read_bytes()
    return {'schema': 'ai4r-rsi-capsule-' + role + '-owner:1', 'id': value['session']['id'],
        'configuration_sha256': ack['configuration_sha256'], 'pid': os.getpid(),
        'start_ticks': int(state[19]), 'argv_sha256': digest(argv),
        'argv': argv.decode('utf8').rstrip('\0').split('\0'),
        'pid_namespace': os.readlink('/proc/self/ns/pid'),
        'mount_namespace': os.readlink('/proc/self/ns/mnt'),
        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'deadline_unix_ns': time.time_ns() + int((value['session']['grant']['limits']['wall_s'] + 30) * 1e9),
        'initial_uid': os.geteuid(), 'initial_gid': os.getegid(),
        'uid': os.geteuid(), 'gid': os.getegid(), 'groups': os.getgroups(),
        'controller_uid': 12001, 'controller_gid': 12001, 'controller_groups': [13000]}


def run(value, ack):
    helper = sys.modules['deploy.m1.rsi_development_run']
    helper.exclusive(value['claim_path'], {**ack, 'schema': 'ai4r-rsi-capsule-run-claim:1'})
    root = Path(value['evaluator']['root'])
    helper.exclusive(root / 'controller-owner.json', owner_record(value, ack, 'controller'))
    request_read, request_write = os.pipe(); response_read, response_write = os.pipe()
    effect_deadline = time.monotonic() + value['session']['grant']['limits']['wall_s']
    pid = os.fork()
    if pid == 0:
        try:
            keep = {0, 1, 2, request_read, response_write}
            for name in os.listdir('/proc/self/fd'):
                fd = int(name)
                if fd not in keep:
                    try: os.close(fd)
                    except OSError: pass
            def expired(signum, frame):
                raise TimeoutError('FINITE_CAPSULE_EVALUATOR_LIFETIME_EXPIRED')
            signal.signal(signal.SIGALRM, expired)
            signal.alarm(value['session']['grant']['limits']['wall_s'] + 30)
            os.setgroups([])
            helper.exclusive(root / 'owner.json', owner_record(value, ack, 'evaluator'))
            with os.fdopen(request_read, 'rb') as incoming, os.fdopen(response_write, 'wb') as outgoing:
                asyncio.run(evaluator(value, incoming, outgoing, ack['configuration_sha256'], helper))
            os._exit(0)
        except BaseException as error:
            try:
                helper.exclusive(root / 'failure.json', {'schema': 'ai4r-rsi-capsule-evaluator-failure:1',
                    'id': value['session']['id'], 'configuration_sha256': ack['configuration_sha256'],
                    'exception_type': type(error).__name__, 'message': str(error)[:4096], 'status': 'ERROR_NO_REPLAY'})
            except BaseException:
                pass
            os._exit(2)
    os.close(request_read); os.close(response_write)
    os.setgroups([13000]); os.setgid(12001); os.setuid(12001)
    need(os.getuid() == os.geteuid() == 12001 and os.getgid() == os.getegid() == 12001
         and os.getgroups() == [13000], 'PERMANENT_CONTROLLER_IDENTITY_DROP_REQUIRED')
    result = None; progress = {'phase': 'WAITING_FOR_EVALUATOR'}; failure = None
    try:
        with os.fdopen(response_read, 'rb') as incoming, os.fdopen(request_write, 'wb') as outgoing:
            ready = read_frame_deadline(incoming, time.monotonic() + 30)
            need(isinstance(ready, dict) and set(ready) == {'ready', 'plan'} and ready['ready'] is True
                 and ready['plan']['grant_sha256'] == ack['grant_sha256']
                 and ready['plan']['maximum_executions'] == ack['maximum_executions']
                 and ready['plan']['bootstrap_schema'] == ack['bootstrap_schema'], 'EXACT_ROOT_EVALUATOR_READY_REQUIRED')
            result = asyncio.run(controller(value, incoming, outgoing, helper,
                evaluator_pid=pid, effect_deadline=effect_deadline, progress=progress))
    except BaseException as error:
        failure = {
            'schema': 'ai4r-rsi-capsule-controller-failure:1', 'id': value['session']['id'],
            'configuration_sha256': ack['configuration_sha256'], 'phase': progress['phase'],
            'exception_type': type(error).__name__, 'message': str(error)[:4096], 'status': 'ERROR_NO_REPLAY'}
        helper.exclusive(Path(value['composition']['record_root']) / 'controller-failure.json', failure)
    finally:
        _, status = os.waitpid(pid, 0)
    if failure is not None:
        # This is a distinct terminal carrier, never an invented session result.
        # Preserve the exact controller error and actual evaluator wait outcome;
        # Root publication independently joins the stopped-worker proofs.
        terminal = {'schema':'ai4r-rsi-capsule-controller-terminal:1', 'id':value['session']['id'],
            'configuration_sha256':ack['configuration_sha256'], 'status':'ERROR_NO_REPLAY',
            'phase':progress['phase'], 'controller_failure_sha256':digest(helper.encoded(failure)),
            'evaluator_exit_code':os.waitstatus_to_exitcode(status),
            'model_calls':0 if progress['phase'] in ('WAITING_FOR_EVALUATOR','COMPOSING') else None,
            'security':'UNQUALIFIED', 'security_campaigns':'DEFERRED'}
        helper.exclusive(value['result_path'], terminal)
        return terminal
    need(os.waitstatus_to_exitcode(status) == 0, 'ROOT_EVALUATOR_FAILED_NO_REPLAY')
    helper.exclusive(value['result_path'], result)
    return {'schema': 'ai4r-rsi-capsule-run-terminal:1', 'id': value['session']['id'],
        'status': result['status'], 'result_sha256': digest(helper.encoded(result)),
        'result_ref': result['result_ref'], 'security': 'UNQUALIFIED'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('operation', choices=('preflight', 'doctor', 'run'))
    parser.add_argument('--configuration', required=True)
    parser.add_argument('--configuration-sha256', required=True)
    parser.add_argument('--scratch-root')
    args = parser.parse_args(argv)
    if args.operation == 'doctor':
        need(os.name == 'posix' and os.geteuid() == 0 and args.scratch_root, 'ROOT_DOCTOR_SCRATCH_REQUIRED')
        raw = protected(args.configuration).read_bytes()
        need(len(raw) <= MAX_CONFIG and digest(raw) == args.configuration_sha256, 'ROOT_CONFIGURATION_DIGEST_DIFFERS')
        value = closed_json(raw)
        need(isinstance(value, dict) and value.get('schema') == SCHEMA, 'WHOLE_PACKAGE_CONFIGURATION_REQUIRED')
        helper = load_sources(value)
        validate_configuration(value)
        from jiuwenswarm.research_rsi.capsule_doctor import doctor
        result = doctor(value, helper, args.scratch_root, scope_sha256=compose_doctor_scope(value))
        print(json.dumps({'status': result['status'], 'scope_sha256': result['scope_sha256'],
            'model_calls': 0, 'execution_jobs': 0}, sort_keys=True))
        return
    need(args.scratch_root is None, 'SCRATCH_ONLY_FOR_DOCTOR')
    value, ack = preflight(args.configuration, args.configuration_sha256)
    if args.operation == 'preflight':
        print(json.dumps(ack, sort_keys=True))
    else:
        os.umask(0o077)
        print(json.dumps(run(value, ack), sort_keys=True))


if __name__ == '__main__':
    main()
