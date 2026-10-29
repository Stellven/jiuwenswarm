"""Finite tool-free native model adapter for standalone function RSI.

Each run owns at most ten once-only calls (diagnosis/proposal, five iterations).
Callers supply only public specifications/source, visible gate feedback and
aggregate measurements. This module never loads benchmark fixtures. No product
bootstrap, calibration, admission or prior native lease is changed.
"""
from __future__ import annotations
import asyncio
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import uuid

MODEL = 'gpt-6.1-sol'
EFFORT = 'medium'
MAX_CALLS = 10
TIMEOUT_S = 120
HOST_WORK = Path('/mnt/d/M1plus/analysis-evidence/integration/parse-duration-rsi-20261028-r1/host-work')
WINDOWS_WORK = 'D:/M1plus/analysis-evidence/integration/parse-duration-rsi-20261028-r1/host-work'
BINARY_SHA256 = '2692c8c7bb2cf8b0aefe638741fc90236f4b824c59578ce84994f9de58200993'
GLOBAL_LOCK = Path('/run/ai4r-rsi-host-codex/function-benchmark.lock')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def real_directory(path):
    path = Path(path).absolute()
    require(path.is_dir() and not any(p.is_symlink() for p in (path, *path.parents)),
            'REAL_FUNCTION_RUN_DIRECTORY_REQUIRED')
    return path


def write_once(path, raw):
    path = Path(path)
    if not isinstance(raw, bytes):
        raw = encoded(raw)
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
    return {'path': str(path), 'sha256': sha(raw)}


def source_pins():
    from jiuwenswarm.research import local_model_codex, local_model_relay, local_models
    from jiuwenswarm.research_rsi import host_codex_backend
    return {str(Path(m.__file__).resolve()): sha(Path(m.__file__).read_bytes())
            for m in (local_model_codex, local_model_relay, local_models, host_codex_backend)} | {
                str(Path(__file__).resolve()): sha(Path(__file__).read_bytes())}


async def relay_idle():
    """Read-only RPC under the real caller identity; no metadata/model turn."""
    from jiuwenswarm.research import local_models
    package_root = str(Path(local_models.__file__).resolve().parents[2])
    script = """import asyncio,json,sys
sys.path.insert(0,sys.argv[1])
from jiuwenswarm.research_rsi.host_codex_backend import HostCodexSubscriptionService
async def main():
 owner=HostCodexSubscriptionService(sys.argv[2])
 try:
  binding,status=await owner.relay_status()
  assert status['active'] is False and status['unresolved'] is False
  print(json.dumps(status,sort_keys=True))
 finally:await owner.transport.close()
asyncio.run(main())
"""
    def identity():
        os.setgroups([13000])
        os.setgid(12001)
        os.setuid(12001)
    proc = await asyncio.create_subprocess_exec(
        sys.executable, '-I', '-B', '-c', script, package_root, str(HOST_WORK),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        preexec_fn=identity, env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8'})
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), 20)
    except BaseException:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
        raise
    require(proc.returncode == 0 and len(stdout) <= 16384, 'GLOBAL_RELAY_STATUS_UNAVAILABLE')
    status = json.loads(stdout)
    require(status.get('schema') == 'ai4r-rsi-host-codex-relay-status:1'
            and status.get('active') is False and status.get('unresolved') is False,
            'GLOBAL_RELAY_NOT_IDLE')
    return status


def initialize(runroot, model=MODEL):
    """Create one pinned ledger, or validate the same existing ledger."""
    require(os.name == 'posix' and os.geteuid() == 0, 'ROOT_FUNCTION_MODEL_OWNER_REQUIRED')
    require(model == MODEL, 'QUALIFIED_FUNCTION_MODEL_REQUIRED')
    runroot = real_directory(runroot)
    from jiuwenswarm.research_rsi.host_codex_backend import HostCatalog, CATALOG, ENDPOINT, descriptor
    binding = HostCatalog(CATALOG, owner_uid=0).resolve(ENDPOINT)
    require(binding['model']['model_name'] == MODEL
            and binding['model']['reasoning_effort'] == EFFORT
            and binding['backend']['codex_sha256'] == BINARY_SHA256,
            'QUALIFIED_FUNCTION_MODEL_BINDING_DIFFERS')
    home = runroot / 'model'
    policy = {'schema': 'ai4r-function-rsi-model-policy:1', 'run_root': str(runroot),
              'model': MODEL, 'effort': EFFORT, 'max_calls': MAX_CALLS,
              'timeout_s': TIMEOUT_S, 'host_work_root': str(HOST_WORK),
              'qualified_policy': descriptor(binding), 'source_pins': source_pins(),
              'candidate_execution': False, 'tools': False, 'automatic_retry': False}
    if not home.exists():
        home.mkdir(mode=0o700)
        write_once(home / 'policy.json', policy)
        db = sqlite3.connect(home / 'ledger.sqlite3', isolation_level=None)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('CREATE TABLE calls (ordinal INTEGER PRIMARY KEY, iteration INTEGER NOT NULL, '
                   'phase TEXT NOT NULL, request_id TEXT UNIQUE NOT NULL, state TEXT NOT NULL, '
                   'start_ref TEXT NOT NULL, receipt_ref TEXT, UNIQUE(iteration,phase))')
        db.close()
    else:
        real_directory(home)
        require((home / 'policy.json').read_bytes() == encoded(policy)
                and (home / 'ledger.sqlite3').is_file(), 'FUNCTION_MODEL_POLICY_CHANGED_OR_INCOMPLETE')
    require(not (home / 'HALTED.json').exists(), 'FUNCTION_MODEL_HALTED_NO_REPLAY')
    return home, binding, policy


async def propose(runroot, prompt, phase, iteration, model=MODEL):
    """One real call; returns text/evidence refs. Any dispatched error halts run."""
    require(phase in ('diagnosis', 'proposal') and type(iteration) is int and 1 <= iteration <= 5,
            'FINITE_FUNCTION_CALL_ID_REQUIRED')
    require(isinstance(prompt, str) and prompt.strip() and len(prompt.encode('utf-8')) <= 262144,
            'BOUNDED_PUBLIC_FUNCTION_PROMPT_REQUIRED')
    home, binding, policy = initialize(runroot, model)
    locks = []
    db = None
    started = False
    receipt = None
    bundle = None
    ordinal = (iteration - 1) * 2 + (1 if phase == 'diagnosis' else 2)
    call = home / ('call-%02d-%s' % (ordinal, phase))
    request_id = uuid.uuid4().hex
    evidence = {}
    try:
        for path in (GLOBAL_LOCK, home / 'owner.lock'):
            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            locks.append(fd)
            require(stat.S_ISREG(os.fstat(fd).st_mode), 'FUNCTION_MODEL_LOCK_INVALID')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (home / 'HALTED.json').exists(), 'FUNCTION_MODEL_HALTED_NO_REPLAY')
        db = sqlite3.connect(home / 'ledger.sqlite3', isolation_level=None)
        db.execute('PRAGMA synchronous=FULL')
        previous = db.execute('SELECT ordinal,state FROM calls ORDER BY ordinal').fetchall()
        require(len(previous) < MAX_CALLS and len(previous) == ordinal - 1
                and all(n == index + 1 and state == 'completed'
                        for index, (n, state) in enumerate(previous)),
                'FUNCTION_CALL_CONSUMED_OR_PRIOR_EFFECT_UNRESOLVED')
        preflight = await relay_idle()
        call.mkdir(mode=0o700)
        evidence['prompt_ref'] = write_once(call / 'prompt.txt', prompt.encode('utf-8'))
        evidence['relay_before_ref'] = write_once(call / 'relay-before.json', preflight)
        HOST_WORK.mkdir(parents=True, exist_ok=True)
        real_directory(HOST_WORK)
        work_name = 'function-' + sha(str(Path(runroot).absolute()).encode())[:20] + '-' + request_id
        (HOST_WORK / work_name).mkdir(mode=0o700)
        binding = copy.deepcopy(binding)
        binding['backend']['working_directory'] = WINDOWS_WORK + '/' + work_name
        start = {'schema': 'ai4r-function-rsi-model-start:1', 'request_id': request_id,
                 'ordinal': ordinal, 'phase': phase, 'iteration': iteration, 'model': MODEL,
                 'effort': EFFORT, 'policy_sha256': sha(encoded(policy)), 'recorded_at': utc(),
                 'host_working_directory': binding['backend']['working_directory'], **evidence}
        evidence['start_ref'] = write_once(call / 'start.json', start)
        db.execute('BEGIN IMMEDIATE')
        try:
            db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?,NULL)',
                       (ordinal, iteration, phase, request_id, 'started', json.dumps(evidence['start_ref'])))
            db.execute('COMMIT')
        except BaseException:
            db.execute('ROLLBACK')
            raise
        started = True
        from jiuwenswarm.research.local_model_relay import HostCodexBackend
        from jiuwenswarm.research.local_models import native_codex_response
        receipt = await asyncio.wait_for(
            HostCodexBackend()(binding, {'prompt': prompt, 'timeout_s': TIMEOUT_S}),
            TIMEOUT_S + 15)
        evidence['raw_receipt_ref'] = write_once(call / 'native-original.receipt',
                                                 receipt.original_bytes)
        evidence['stderr_ref'] = write_once(call / 'native-stderr.bin', receipt.stderr_bytes)
        transport = receipt.transport_observation
        evidence['transport_ref'] = write_once(call / 'transport.json', transport)
        require(isinstance(transport, dict) and transport.get('returncode') == 0
                and transport.get('observer_joined') is True
                and all(transport.get(name + '_complete') is True for name in ('stdin', 'stdout', 'stderr'))
                and not transport.get('stdout_overflow') and not transport.get('stderr_overflow'),
                'FUNCTION_MODEL_TRANSPORT_NOT_CONTAINED')
        bundle, observation, text = native_codex_response(receipt['response_text'], binding, prompt=prompt)
        require(receipt['outcome'] == bundle['outcome'] == 'completed'
                and observation['identity']['effective'] == MODEL
                and bundle['reasoning_effort'] == EFFORT and isinstance(text, str) and text.strip(),
                'FUNCTION_MODEL_NOT_COMPLETED')
        evidence['relay_after_ref'] = write_once(call / 'relay-after.json', await relay_idle())
        evidence['response_ref'] = write_once(call / 'response.txt', text.encode('utf-8'))
        result = {'schema': 'ai4r-function-rsi-model-result:1', 'state': 'completed',
                  'request_id': request_id, 'iteration': iteration, 'phase': phase, 'model': MODEL,
                  'reasoning_effort': EFFORT, 'usage': observation['usage'],
                  'provider_request_id': observation['provider_request_id'],
                  'calls_consumed': ordinal, 'completed_at': utc(), **evidence}
        ref = write_once(call / 'result.json', result)
        db.execute('UPDATE calls SET state=?,receipt_ref=? WHERE request_id=? AND state=?',
                   ('completed', json.dumps(ref), request_id, 'started'))
        return {'text': text, 'receipt_ref': ref, **result}
    except BaseException as error:
        if started:
            captured = receipt
            cause = error
            while captured is None and cause is not None:
                captured = getattr(cause, 'backend_receipt', None)
                cause = cause.__cause__
            if captured is not None and 'raw_receipt_ref' not in evidence:
                evidence['raw_receipt_ref'] = write_once(call / 'native-original.receipt',
                                                         captured.original_bytes)
                evidence['stderr_ref'] = write_once(call / 'native-stderr.bin', captured.stderr_bytes)
                evidence['transport_ref'] = write_once(call / 'transport.json',
                                                        captured.transport_observation)
            failure = {'schema': 'ai4r-function-rsi-model-result:1', 'state': 'halted',
                       'request_id': request_id, 'ordinal': ordinal, 'iteration': iteration,
                       'phase': phase, 'exception_class': type(error).__name__,
                       'native_outcome': bundle.get('outcome') if bundle else None,
                       'native_error_code': bundle.get('error_code') if bundle else None,
                       'replayed': False, 'recorded_at': utc(), **evidence}
            ref = write_once(call / 'failure.json', failure)
            write_once(home / 'HALTED.json', {'failure_ref': ref, 'no_further_effect': True})
            if db is not None:
                db.execute('UPDATE calls SET state=?,receipt_ref=? WHERE request_id=?',
                           ('halted', json.dumps(ref), request_id))
        raise
    finally:
        if db is not None:
            db.close()
        for fd in reversed(locks):
            os.close(fd)
