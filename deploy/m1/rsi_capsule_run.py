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
MAX_TRIALS = 20
DISPATCHERS = ('v18-bwrap', 'local')
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


DOCTOR_SOURCE = 'jiuwenswarm/research_rsi/capsule_doctor.py'
# The whole-package roots (see capsule_doctor.CONTROLLER_ENTRY_PACKAGES); the
# exact module/resource closure under them is derived, never hand-listed.
PACKAGE_ROOTS = ('jiuwenswarm/__init__.py', 'jiuwenswarm/research/__init__.py',
                 'jiuwenswarm/research_rsi/__init__.py', DOCTOR_SOURCE)


def pinned_doctor(root, pins):
    """The configuration's own pinned, stdlib-only diagnostics module, loaded
    stand-alone so nothing from the package is imported before its closure
    is proven complete."""
    raw = protected(root / DOCTOR_SOURCE).read_bytes()
    need(digest(raw) == pins[DOCTOR_SOURCE], 'SOURCE_PIN_DIFFERS: ' + DOCTOR_SOURCE)
    spec = importlib.util.spec_from_loader('capsule_run_pinned_doctor', loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(root / DOCTOR_SOURCE)
    exec(compile(raw, str(root / DOCTOR_SOURCE), 'exec'), module.__dict__)
    return module


def load_sources(value):
    root = protected(value['source_root'], directory=True)
    pins = value['source_pins']
    need(isinstance(pins, dict) and pins, 'PINNED_SOURCE_CLOSURE_REQUIRED')
    # A research_rsi-only overlay is refused before any byte is read.
    need(set(PACKAGE_ROOTS) <= set(pins), 'COMPLETE_CAPSULE_PACKAGE_CLOSURE_REQUIRED')
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
    # Derived import/resource closure of every controller/evaluator module and
    # the frozen composition: an incomplete package names its first missing path.
    # The walk runs once per installed package; its Root proof is reused here
    # after re-verifying the same pins (inventory and bytes, just checked).
    composition_path = protected(value['composition_path'])
    try:
        pinned_doctor(root, pins).proven_source_closure(root, pins, entry_files=[composition_path])
    except ValueError as error:
        raise ValueError('COMPLETE_CAPSULE_PACKAGE_CLOSURE_REQUIRED: ' + str(error)[:2048]) from None
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
    fields = {'root', 'runtime_root', 'manifest', 'metadata', 'grant_path', 'grant_sha256', 'cgroup_root'}
    # ``dispatcher`` is optional: absent means the protected V18 path.
    need(isinstance(evaluator, dict) and fields <= set(evaluator) <= fields | {'dispatcher'}
         and evaluator.get('dispatcher', 'v18-bwrap') in DISPATCHERS, 'CLOSED_EVALUATOR_REQUIRED')
    for key in ('core_root', 'input_root', 'record_root', 'native_lease_root', 'account_root', 'work_root'):
        path = Path(composition[key])
        need(path.is_absolute() and '..' not in path.parts, 'ABSOLUTE_COMPOSITION_PATH_REQUIRED')
    from jiuwenswarm.research_rsi.capsule_session import validate_session, loop_run_context_ids
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
    # One diagnosis and one proposal work context per prepared loop iteration.
    need(set(composition['run_contexts']) == loop_run_context_ids(session),
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
    closure = proof.get('source_closure')
    need(isinstance(closure, dict) and closure.get('complete') is True
         and type(closure.get('module_count')) is int and closure['module_count'] > 0,
         'COMPOSE_DOCTOR_COMPLETE_SOURCE_CLOSURE_REQUIRED')
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
    if evaluator.get('dispatcher', 'v18-bwrap') == 'v18-bwrap':
        protected(evaluator['cgroup_root'], directory=True)  # The local dispatcher owns no cgroup.
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
    from jiuwenswarm.research_rsi.targets.capsule_local_dispatcher import dispatcher_for
    config = value['evaluator']; root = Path(config['root'])
    captures = RecordStore(root / 'captures')
    for key, record in config['metadata'].items():
        need(captures.put(record) == value['session']['grant']['worker'][key+'_ref'],
             'EXACT_PUBLIC_WORKER_METADATA_IDENTITY_REQUIRED')
    # Explicit configuration selects the dispatcher; a missing key is the
    # protected V18 path (never inferred from the host).
    dispatcher = dispatcher_for(config, root=root, runtime_root=config['runtime_root'],
        manifest=config['manifest'], grant_path=config['grant_path'], grant_sha256=config['grant_sha256'],
        cgroup_root=config['cgroup_root'], captures=captures)
    plan = dispatcher.plan()
    # Interface E is served only by a dispatcher that implements it; the ready
    # frame tells the controller so (never inferred on the controller side).
    bench = getattr(dispatcher, 'benchmark', None)
    bench = bench if callable(bench) else None
    jobs = None
    if bench is not None and callable(getattr(dispatcher, 'benchmark_plan', None)):
        jobs = dispatcher.benchmark_plan().get('jobs_per_benchmark')  # W-M1: jobs one call executes
    helper.write_frame(outgoing, {'ready': True, 'plan': plan, 'benchmark': {
        'available': bench is not None, 'jobs': jobs if type(jobs) is int and jobs >= 0 else None}})
    # Iteration/trial arguments are passed when the dispatcher ABI declares them;
    # a historical single-trial dispatcher is refused any multi-trial request.
    accepts = set(inspect.signature(dispatcher.evaluate).parameters)
    bench_accepts = set(inspect.signature(bench).parameters) if bench is not None else set()
    served = []; last_iteration = -1; stop = 'CONTROLLER_CLOSED'
    benchmarks = []; outcomes = {}  # subject sha256 -> {fixture_id: task_success}
    try:
        while True:
            request = await asyncio.to_thread(read_frame_deadline, incoming, dispatcher.deadline)
            if request is None:
                break
            if isinstance(request, dict) and set(request) == {'benchmark'}:
                await serve_benchmark(request['benchmark'], dispatcher, bench, bench_accepts, plan,
                                             outcomes, benchmarks, last_iteration, captures, outgoing, helper)
                if getattr(dispatcher, 'halted', False):
                    stop = 'DISPATCHER_HALTED'
                    break
                continue
            need(isinstance(request, dict) and set(request) == {
                'role', 'body_base64', 'candidate_ref', 'binding', 'iteration', 'trials'},
                'CLOSED_CAPSULE_EVALUATION_REQUEST_REQUIRED')
            role, iteration, trials = request['role'], request['iteration'], request['trials']
            need(role == ('candidate' if served else 'parent'), 'PARENT_FIRST_THEN_CANDIDATES_REQUIRED')
            need(type(iteration) is int and iteration > last_iteration and (iteration == 0) == (role == 'parent'),
                 'MONOTONIC_EVALUATION_ITERATION_REQUIRED')
            need(type(trials) is int and 1 <= trials <= MAX_TRIALS and (trials == 1 or 'trials' in accepts),
                 'FINITE_SUPPORTED_EVALUATION_TRIALS_REQUIRED')
            need(dispatcher.executions < plan['maximum_executions'], 'ROOT_EXECUTION_BUDGET_EXHAUSTED')
            body = base64.b64decode(request['body_base64'], validate=True)
            extra = {key: item for key, item in (('iteration', iteration), ('trials', trials)) if key in accepts}
            try:
                result = await dispatcher.evaluate(role, body=body, candidate_ref=request['candidate_ref'],
                                                   binding=request['binding'], **extra)
            except Exception as error:
                # The controller learns the exact refusal; the Root failure record
                # and nonzero exit below are unchanged. No request is replayed.
                helper.write_frame(outgoing, {'failure': {'exception_type': type(error).__name__,
                                                          'message': str(error)[:4096]}})
                raise
            for capture in capture_closure(captures, result):
                helper.write_frame(outgoing, {'capture': capture})
            helper.write_frame(outgoing, {'evaluation': result})
            served.append({'role': role, 'iteration': iteration, 'trials': trials,
                           'result_ref': result.get('result_ref'), 'executions': result.get('executions')})
            outcomes[digest(body)] = {'role': role, 'iteration': iteration, 'cases': {row.get('fixture_id'): row.get('task_success')
                                                              for row in result.get('rows') or [] if isinstance(row, dict)}}
            last_iteration = iteration
            # A candidate's captured case failures are scored outcomes; only an
            # unknown/in-flight effect (halted dispatcher) or a failed parent
            # control ends service.
            if getattr(dispatcher, 'halted', False):
                stop = 'DISPATCHER_HALTED'
                break
            if role == 'parent' and not evaluation_passed(result, value['session']['capsule_name']):
                stop = 'PARENT_CONTROL_FAILED'
                break
        helper.exclusive(root / 'complete.json', {
            'schema': 'ai4r-rsi-capsule-evaluator-completion:1', 'id': value['session']['id'],
            'configuration_sha256': configuration_sha256, 'grant_ref': dispatcher.grant_ref,
            'plan': plan, 'status': 'STOPPED', 'stop': stop, 'executions': dispatcher.executions,
            'halted': dispatcher.halted, 'completed_roles': list(dispatcher.completed), 'evaluations': served,
            'benchmarks': benchmarks})
    finally:
        captures.close()


def run_wall_s(value):
    """Effect wall of one run: the grant's loop wall plus the paired-benchmark
    wall (``session.loop.benchmark.wall_s`` = grant ``limits.benchmark_wall_s``;
    0 without a benchmark) -- the same sum the Root dispatcher's deadline uses."""
    from jiuwenswarm.research_rsi.capsule_loop import benchmark_wall_s, loop_configuration
    session = value['session']
    return session['grant']['limits']['wall_s'] + benchmark_wall_s(loop_configuration(session))


async def serve_benchmark(request, dispatcher, bench, accepts, plan, outcomes, benchmarks, last_iteration,
                          captures, outgoing, helper):
    """Interface E over the pipes: one ``{'benchmark': {...}}`` request, then
    captures and exactly one ``{'benchmark': report}`` (or failure) frame.

    Root authorizes only subjects it has itself evaluated in this session: the
    benchmark parent is always the evaluated original parent; the benchmark
    candidate is either the parent itself (the A/A baseline, ``iteration`` 0,
    once per run) or the candidate of the iteration just evaluated
    (``iteration`` >= 1, once per iteration) that passed every case the
    parent passed. The dispatcher (W-M1) runs the paired batched protocol,
    refuses an unevaluated candidate or a repeated claim, and enforces the
    exact grant budget; this loop only pre-checks. At most ``max_iterations +
    1`` benchmarks are served, which is what the slot sizes the grant and the
    benchmark wall for.
    """
    need(bench is not None, 'ROOT_BENCHMARK_NOT_SERVED')
    need(isinstance(request, dict) and set(request) == {'parent_body_base64', 'candidate_body_base64', 'iteration'},
         'CLOSED_CAPSULE_BENCHMARK_REQUEST_REQUIRED')
    iteration = request['iteration']
    need(type(iteration) is int and last_iteration >= 0 and iteration in (0, last_iteration),
         'BENCHMARK_FOR_LAST_EVALUATED_ITERATION_OR_BASELINE_REQUIRED')
    need(not any(row['iteration'] == iteration for row in benchmarks), 'ONE_BENCHMARK_PER_ITERATION_AND_ONE_BASELINE')
    parent = base64.b64decode(request['parent_body_base64'], validate=True)
    candidate = base64.b64decode(request['candidate_body_base64'], validate=True)
    parent_sha256, candidate_sha256 = digest(parent), digest(candidate)
    need(parent_sha256 in outcomes and outcomes[parent_sha256]['role'] == 'parent', 'BENCHMARK_PARENT_MUST_BE_EVALUATED_PARENT')
    if iteration == 0:
        need(candidate_sha256 == parent_sha256, 'BASELINE_IS_PARENT_A_A')
    else:
        need(candidate_sha256 in outcomes and outcomes[candidate_sha256]['role'] == 'candidate'
             and outcomes[candidate_sha256]['iteration'] == iteration, 'BENCHMARK_CANDIDATE_OF_THIS_ITERATION_REQUIRED')
    before, after = outcomes[parent_sha256]['cases'], outcomes[candidate_sha256]['cases']
    need(all(after.get(ident) is True for ident, passed in before.items() if passed is True),
         'BENCHMARK_CANDIDATE_MUST_KEEP_PARENT_CORRECTNESS')
    need(dispatcher.executions < plan['maximum_executions'], 'ROOT_EXECUTION_BUDGET_EXHAUSTED')
    extra = {name: item for name, item in (
        ('parent_ref', {'id': parent_sha256, 'sha256': parent_sha256}),
        ('candidate_ref', {'id': candidate_sha256, 'sha256': candidate_sha256})) if name in accepts}
    try:
        report = await bench(parent, candidate, iteration=iteration, **extra)
        need(isinstance(report, dict), 'ROOT_BENCHMARK_REPORT_REQUIRED')
    except Exception as error:
        helper.write_frame(outgoing, {'failure': {'exception_type': type(error).__name__, 'message': str(error)[:4096]}})
        raise
    for capture in capture_closure(captures, report):
        helper.write_frame(outgoing, {'capture': capture})
    helper.write_frame(outgoing, {'benchmark': report})
    benchmarks.append({'iteration': iteration, 'parent_sha256': parent_sha256, 'candidate_sha256': candidate_sha256,
                       'protected_jobs': report.get('protected_jobs'), 'objective_met': report.get('objective_met'),
                       'report_ref': report.get('report_ref')})
    return report


def evaluation_passed(result, name):
    """Parent control, exactly as the loop applies it (capsule_loop): complete
    evaluation and the historical public baseline passed (v1: every case)."""
    from jiuwenswarm.research_rsi.capsule_loop import parent_control_passed
    return parent_control_passed(result, name)


async def controller(value, incoming, outgoing, helper, *, evaluator_pid=None, effect_deadline=None, progress=None,
                     benchmark_plan=None):
    runtime = None

    async def answer(kind):
        """Captures, then exactly one ``kind`` (or failure) frame from Root."""
        deadline = time.monotonic() + run_wall_s(value)
        while True:
            frame = await asyncio.to_thread(read_frame_deadline, incoming, deadline)
            need(isinstance(frame, dict), 'ROOT_EVALUATOR_CLOSED_WITHOUT_RESULT')
            if set(frame) == {'capture'}:
                capture = frame['capture']
                need(isinstance(capture, dict) and set(capture) == {'ref', 'bytes_base64'}, 'EXACT_ROOT_CAPTURE_REQUIRED')
                raw = base64.b64decode(capture['bytes_base64'], validate=True)
                runtime.records.put_ref(capture['ref'], raw)
                continue
            if set(frame) == {'failure'}:
                failure = frame['failure']
                need(isinstance(failure, dict) and set(failure) == {'exception_type', 'message'}, 'EXACT_ROOT_FAILURE_REQUIRED')
                raise ValueError('ROOT_' + kind.upper() + '_FAILED_NO_REPLAY: ' + str(failure['exception_type'])[:128]
                                 + ': ' + str(failure['message'])[:2048])
            need(set(frame) == {kind}, 'UNKNOWN_ROOT_EVALUATOR_FRAME')
            return frame[kind]

    async def benchmark(parent_body, candidate_body, *, iteration):
        # Interface E over the same pipes and grant: one request frame, then
        # captures and exactly one report (or failure) frame.
        helper.write_frame(outgoing, {'benchmark': {
            'parent_body_base64': base64.b64encode(parent_body).decode('ascii'),
            'candidate_body_base64': base64.b64encode(candidate_body).decode('ascii'), 'iteration': iteration}})
        report = await answer('benchmark')
        from jiuwenswarm.research_rsi.targets.capsule_objective import validate_benchmark_report
        from jiuwenswarm.research_rsi.targets.capsule_executor import LOCAL_SCOPE, PROTECTED_SCOPE
        validate_benchmark_report(report, parent_sha256=digest(parent_body), candidate_sha256=digest(candidate_body))
        local = (value.get('evaluator') or {}).get('dispatcher') == 'local'
        # Like evaluation rows: a local report is never presented as protected.
        need(report.get('scope') == (LOCAL_SCOPE if local else PROTECTED_SCOPE), 'CONFIGURED_BENCHMARK_SCOPE_REQUIRED')
        for ref in report['evidence_refs']:
            runtime.store.read(ref)  # every evidence ref arrived as an exact Root capture
        if 'report_ref' in report:
            need(runtime.store.get(report['report_ref']) == {k: v for k, v in report.items() if k != 'report_ref'},
                 'EXACT_ROOT_BENCHMARK_REPORT_CAPTURE_REQUIRED')
        return report

    async def evaluate(role, *, body, candidate_ref, binding, iteration=0, trials=1):
        # Interface A over the bounded pipes: one request frame, then captures
        # and exactly one evaluation (or failure) frame. Served N times.
        helper.write_frame(outgoing, {'role': role, 'body_base64': base64.b64encode(body).decode('ascii'),
            'candidate_ref': candidate_ref, 'binding': binding, 'iteration': iteration, 'trials': trials})
        result = await answer('evaluation')
        from jiuwenswarm.research_rsi.capsule_loop import validate_visible
        from jiuwenswarm.research_rsi.targets.capsule_runtime import capsule_worker_program, BOOTSTRAP_SCHEMA
        from jiuwenswarm.research_rsi.targets.capsule_executor import LOCAL_SCOPE
        validate_visible(result, value['session'], role, candidate_ref, iteration=iteration, trials=trials,
                         objective=getattr(runtime, 'objective', None))
        local = (value.get('evaluator') or {}).get('dispatcher') == 'local'
        # Local rows are accepted only from an explicitly local evaluator and
        # are never presented as protected (publication refuses the scope).
        need(all((row.get('receipt', {}).get('scope') == LOCAL_SCOPE) is local for row in result['rows'])
             and (result.get('scope') == LOCAL_SCOPE) is local, 'CONFIGURED_EVALUATION_SCOPE_REQUIRED')
        need(isinstance(result.get('result_ref'), dict)
             and all(isinstance(row.get(key), dict) for row in result['rows']
                     for key in ('evidence_ref', 'input_ref', 'program_ref')), 'PROTECTED_ROOT_EVIDENCE_REFS_REQUIRED')
        need(runtime.store.get(result['result_ref']) == {key: item for key, item in result.items() if key != 'result_ref'},
             'EXACT_ROOT_RESULT_CAPTURE_REQUIRED')
        for row in result['rows']:
            need(runtime.store.get(row['evidence_ref']) == {key: item for key, item in row.items() if key != 'evidence_ref'},
                 'EXACT_ROOT_ROW_CAPTURE_REQUIRED')
            need(row['bootstrap_schema'] == BOOTSTRAP_SCHEMA, 'EXACT_GUARDED_BOOTSTRAP_PROGRAM_REQUIRED')
            if local:
                # The local program names the job's own host paths, so its
                # hash is pinned by program_ref but not recomputable here.
                continue
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
                          time.monotonic() + run_wall_s(value))
        async def before_model():
            need(time.time() < value['session']['grant']['expires_unix_s']
                 and time.monotonic() < model_deadline, 'MODEL_START_AFTER_ROOT_GRANT_DEADLINE')
            if evaluator_pid is not None:
                need(os.waitid(os.P_PID, evaluator_pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None,
                     'ROOT_EVALUATOR_EXITED_BEFORE_MODEL_START')
            await governed_before_model()
        runtime.before_model = before_model
        # Interface E: exposed only when the Root evaluator's ready frame said
        # its dispatcher serves benchmarks; otherwise the loop falls back to the
        # flagged single-job floor.
        if isinstance(benchmark_plan, dict) and benchmark_plan.get('available') is True:
            runtime.benchmark = benchmark
            jobs = benchmark_plan.get('jobs')
            runtime.benchmark_jobs = jobs if type(jobs) is int and jobs >= 0 else None
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
        'deadline_unix_ns': time.time_ns() + int((run_wall_s(value) + 30) * 1e9),
        'initial_uid': os.geteuid(), 'initial_gid': os.getegid(),
        'uid': os.geteuid(), 'gid': os.getegid(), 'groups': os.getgroups(),
        'controller_uid': 12001, 'controller_gid': 12001, 'controller_groups': [13000]}


def run(value, ack):
    helper = sys.modules['deploy.m1.rsi_development_run']
    helper.exclusive(value['claim_path'], {**ack, 'schema': 'ai4r-rsi-capsule-run-claim:1'})
    root = Path(value['evaluator']['root'])
    helper.exclusive(root / 'controller-owner.json', owner_record(value, ack, 'controller'))
    request_read, request_write = os.pipe(); response_read, response_write = os.pipe()
    # The paired benchmark runs inside the same evaluator and grant: every
    # effect deadline covers its materialized wall too.
    effect_deadline = time.monotonic() + run_wall_s(value)
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
            signal.alarm(run_wall_s(value) + 30)
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
            need(isinstance(ready, dict) and set(ready) == {'ready', 'plan', 'benchmark'} and ready['ready'] is True
                 and isinstance(ready['benchmark'], dict) and set(ready['benchmark']) == {'available', 'jobs'}
                 and type(ready['benchmark']['available']) is bool
                 and ready['plan']['grant_sha256'] == ack['grant_sha256']
                 and ready['plan']['maximum_executions'] == ack['maximum_executions']
                 and ready['plan']['bootstrap_schema'] == ack['bootstrap_schema'], 'EXACT_ROOT_EVALUATOR_READY_REQUIRED')
            result = asyncio.run(controller(value, incoming, outgoing, helper,
                evaluator_pid=pid, effect_deadline=effect_deadline, progress=progress,
                benchmark_plan=ready['benchmark']))
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
    exit_code = os.waitstatus_to_exitcode(status)
    # A loop that already recorded the evaluator's refusal as its error stop keeps
    # every earlier, individually validated evaluation; otherwise no result.
    need(exit_code == 0 or (result.get('loop') or {}).get('stop_reason') == 'error', 'ROOT_EVALUATOR_FAILED_NO_REPLAY')
    helper.exclusive(value['result_path'], result)
    loop = result.get('loop') or {}
    return {'schema': 'ai4r-rsi-capsule-run-terminal:1', 'id': value['session']['id'],
        'status': result['status'], 'result_sha256': digest(helper.encoded(result)),
        'result_ref': result['result_ref'], 'security': 'UNQUALIFIED', 'evaluator_exit_code': exit_code,
        'stop_reason': loop.get('stop_reason'), 'completed_iterations': loop.get('completed_iterations')}


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
