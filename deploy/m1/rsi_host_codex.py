"""Explicit finite host-Codex RSI transport preparation and one public smoke.

prepare/serve/check never infer. smoke is a separate, once-only operator action.
No benchmark profile, ledger, credentials or existing host login file is opened.
"""
import argparse
import asyncio
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import stat
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
ROOT = Path('/var/lib/ai4r-rsi-host-codex')
CLIENT = Path('/var/lib/ai4r-rsi-host-codex-client')
RUN = Path('/run/ai4r-rsi-host-codex')


def need(value):
    if not value: raise ValueError('Protected dedicated host Codex transport prerequisite unavailable')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def custody(path, uid, gid, mode, *, directory=False):
    path = Path(path)
    need(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)))
    for parent in path.parents:
        info = parent.stat()
        need(info.st_uid == 0 and not info.st_mode & 0o022)
    info = path.lstat()
    need((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
         and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (uid, gid, mode)
         and (directory or info.st_nlink == 1))


def write_new(path, value, uid, gid, mode):
    raw = encoded(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        os.fchown(stream.fileno(), uid, gid); os.fchmod(stream.fileno(), mode)
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


@contextmanager
def runtime_lock():
    """Serialize the complete host relay lifetime against operator recovery."""
    import fcntl
    need(os.name=='posix' and os.geteuid()==0)
    custody(ROOT,0,0,0o700,directory=True)
    path=ROOT/'runtime.lock'
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        custody(path,0,0,0o600)
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:os.close(fd)


def prepare(args):
    need(os.geteuid() == 0)
    from jiuwenswarm.research_rsi.host_codex_backend import (validate_host_catalog, descriptor,
        validate_qualification, QUALIFICATION_SOURCE)
    document = {'schema': 'ai4r-local-model-catalog:1', 'gateway_id': 'rsi-host-codex-sol',
        'backend': {'kind': 'host-codex-app-server', 'host_python': args.host_python,
            'codex_executable': args.codex_executable, 'codex_sha256': args.codex_sha256,
            'account_fingerprint': args.account_fingerprint, 'working_directory': args.working_directory},
        'transport': {'socket_path': str(RUN / 'model.sock'), 'session_file': str(RUN / 'session.json'),
            'peer_uid': 0, 'socket_mode': 0o660},
        'models': [{'id': 'local-host-codex61', 'name': 'RSI host GPT-6.1-Sol medium', 'model_name': 'gpt-6.1-sol',
            'revision': 'codex-cli-0.163.0-operator-qualified', 'enabled': True, 'context_window': args.context_window,
            'max_prompt_bytes': 262144, 'timeout_s': 120, 'reasoning_effort': 'medium'}]}
    validate_host_catalog(document)
    from jiuwenswarm.research.local_models import protected_json
    custody(QUALIFICATION_SOURCE, 0, 0, 0o400)
    qualified = validate_qualification(protected_json(QUALIFICATION_SOURCE, owner_uid=0, private=True), document)
    binding = {key: document[key] for key in ('gateway_id', 'backend', 'transport')}
    binding['model'] = document['models'][0]
    binding['binding_sha256'] = hashlib.sha256(encoded(binding)).hexdigest()
    binding['host_qualification_sha256'] = hashlib.sha256(encoded(qualified)).hexdigest()
    policy_sha = descriptor(binding)['sha256']
    need(not any(os.path.lexists(path) for path in (ROOT, RUN, CLIENT)))
    for path, uid, gid, mode in ((ROOT, 0, 0, 0o700), (RUN, 0, 13000, 0o710), (CLIENT, 12001, 12001, 0o700)):
        path.mkdir(mode=mode); os.chown(path, uid, gid); path.chmod(mode)
    session = {'session_id': secrets.token_urlsafe(32), 'capability': secrets.token_urlsafe(48)}
    write_new(ROOT / 'profile.json', {'schema': 'ai4r-rsi-host-codex:1', 'catalog': document, 'session': session,
        'policy_sha256': policy_sha, 'qualification': qualified}, 0, 0, 0o600)
    write_new(RUN / 'catalog.json', document, 0, 13000, 0o640)
    write_new(RUN / 'qualification.json', qualified, 0, 13000, 0o640)
    write_new(RUN / 'session.json', session, 12001, 12001, 0o400)
    (ROOT / 'relay').mkdir(mode=0o700)
    print(json.dumps({'status': 'PREPARED_NOT_STARTED', 'model': 'gpt-6.1-sol', 'reasoning_effort': 'medium',
        'context_window_declared': args.context_window, 'generation_sent': False}))


def load_profile():
    # Fixed sibling Source, never an operator/browser-selected import path.
    import importlib.util
    spec=importlib.util.spec_from_file_location('_rsi_host_codex_recovery_guard',
        Path(__file__).with_name('rsi_host_codex_recovery.py'))
    recovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(recovery)
    recovery.verify_recovery_complete(ROOT)
    from deploy.m1.rsi_host_codex_upgrade import verify_upgrade_complete
    verify_upgrade_complete(ROOT)
    spec=importlib.util.spec_from_file_location('_rsi_stopped_deployment_guard',
        Path(__file__).with_name('rsi_stopped_repair.py'))
    deployment=importlib.util.module_from_spec(spec);spec.loader.exec_module(deployment)
    deployment.verify_repair_complete(Path('/var/lib/ai4r-rsi-codex'))
    from jiuwenswarm.research.local_models import protected_json
    from jiuwenswarm.research_rsi.host_codex_backend import validate_host_catalog, validate_qualification
    custody(ROOT, 0, 0, 0o700, directory=True)
    custody(ROOT / 'profile.json', 0, 0, 0o600)
    value = protected_json(ROOT / 'profile.json', owner_uid=0, private=True)
    need(set(value) == {'schema', 'catalog', 'session', 'policy_sha256', 'qualification'} and value['schema'] == 'ai4r-rsi-host-codex:1')
    validate_host_catalog(value['catalog'])
    validate_qualification(value['qualification'], value['catalog'])
    session = value['session']
    need(set(session) == {'session_id', 'capability'} and all(isinstance(v, str) and 32 <= len(v) <= 256 for v in session.values()))
    return value


def runtime_incarnation():
    import importlib.util
    spec = importlib.util.spec_from_file_location('_runtime_host_identity', Path(__file__).with_name('rsi_host.py'))
    owner = importlib.util.module_from_spec(spec); spec.loader.exec_module(owner)
    value = owner.incarnation()
    return value, owner.incarnation_key(value)


def verify_runtime_history():
    # A partial restore stays nonreplayable and cannot be served accidentally.
    for claim in ROOT.glob('runtime-restore.*.claim.json'):
        custody(claim, 0, 0, 0o600)
        completion = claim.with_name(claim.name.replace('.claim.json', '.complete.json'))
        custody(completion, 0, 0, 0o600)
        complete = json.loads(completion.read_bytes())
        need(complete.get('schema') == 'ai4r-rsi-host-runtime-restore-complete:1'
             and complete.get('claim_sha256') == hashlib.sha256(claim.read_bytes()).hexdigest())
    return list(ROOT.glob('runtime-restore.*.claim.json'))


def load():
    value = load_profile()
    history = verify_runtime_history()
    identity, key = runtime_incarnation()
    current = ROOT / ('runtime-restore.' + key + '.complete.json')
    if history:
        custody(current, 0, 0, 0o600)
        need(json.loads(current.read_bytes()).get('incarnation') == identity)
    return _load_runtime(value)


def _load_runtime(value):
    from jiuwenswarm.research.local_models import protected_json
    custody(RUN, 0, 13000, 0o710, directory=True)
    custody(RUN / 'catalog.json', 0, 13000, 0o640)
    need(protected_json(RUN / 'catalog.json', owner_uid=0) == value['catalog'])
    custody(RUN / 'qualification.json', 0, 13000, 0o640)
    need(protected_json(RUN / 'qualification.json', owner_uid=0) == value['qualification'])
    custody(RUN / 'session.json', 12001, 12001, 0o400)
    need(protected_json(RUN / 'session.json', owner_uid=12001, private=True) == value['session'])
    session = value['session']
    need(set(session) == {'session_id', 'capability'} and all(isinstance(v, str) and 32 <= len(v) <= 256 for v in session.values()))
    return value


def restore_runtime():
    """Restore only the retained local RPC profile after a boot, never authenticate."""
    with runtime_lock():
        value = load_profile()
        verify_runtime_history()
        need(not os.path.lexists(RUN))
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        need(len(boot) == 36 and all(c in '0123456789abcdef-' for c in boot))
        identity, key = runtime_incarnation()
        claim = ROOT / ('runtime-restore.' + key + '.claim.json')
        completion = ROOT / ('runtime-restore.' + key + '.complete.json')
        need(not os.path.lexists(claim) and not os.path.lexists(completion))
        profile_sha = hashlib.sha256((ROOT / 'profile.json').read_bytes()).hexdigest()
        write_new(claim, {'schema': 'ai4r-rsi-host-runtime-restore-claim:1', 'boot_id': boot,
            'incarnation': identity, 'incarnation_key': key,
            'profile_sha256': profile_sha, 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'inference': False}, 0, 0, 0o600)
        RUN.mkdir(mode=0o710); os.chown(RUN, 0, 13000); os.chmod(RUN, 0o710)
        for name, field, uid, gid, mode in (
                ('catalog.json', 'catalog', 0, 13000, 0o640),
                ('qualification.json', 'qualification', 0, 13000, 0o640),
                ('session.json', 'session', 12001, 12001, 0o400)):
            write_new(RUN / name, value[field], uid, gid, mode)
        need(_load_runtime(value) == value and hashlib.sha256((ROOT / 'profile.json').read_bytes()).hexdigest() == profile_sha)
        need(runtime_incarnation() == (identity, key))
        result = {'schema': 'ai4r-rsi-host-runtime-restore-complete:1', 'boot_id': boot,
            'incarnation': identity, 'incarnation_key': key,
            'profile_sha256': profile_sha, 'claim_sha256': hashlib.sha256(claim.read_bytes()).hexdigest(),
            'runtime_files': {name: hashlib.sha256((RUN / name).read_bytes()).hexdigest()
                              for name in ('catalog.json', 'qualification.json', 'session.json')},
            'inference': False, 'relay_started': False, 'native_login_changed': False}
        write_new(completion, result, 0, 0, 0o600)
        print(json.dumps(result, sort_keys=True))
        return result


async def serve():
    with runtime_lock():
        await _serve_locked()


async def _serve_locked():
    need(os.geteuid() == 0)
    value = load()
    from jiuwenswarm.research.local_model_relay import LocalModelRelay, HostCodexBackend
    from jiuwenswarm.research.private_rpc import PrivateRPCServer
    from jiuwenswarm.research_rsi.host_codex_backend import HostCatalog, CATALOG, ENDPOINT, descriptor
    class SealedHostCatalog(HostCatalog):
        def resolve(self, endpoint_id, binding_sha256=None):
            binding = super().resolve(endpoint_id, binding_sha256=binding_sha256)
            need(descriptor(binding)['sha256'] == value['policy_sha256'])
            return binding
    catalog = SealedHostCatalog(CATALOG, owner_uid=0)
    need(descriptor(catalog.resolve(ENDPOINT))['sha256'] == value['policy_sha256'])
    relay = LocalModelRelay(catalog, ROOT / 'relay', backend=HostCodexBackend(),
        recovery_policy_sha256=value['policy_sha256'])
    def status(payload):
        need(payload == {})
        unresolved = relay.unresolved()
        binding = catalog.resolve(ENDPOINT)
        need(descriptor(binding)['sha256'] == value['policy_sha256'])
        return {'schema': 'ai4r-rsi-host-codex-relay-status:1', 'binding_sha256': catalog.resolve(ENDPOINT)['binding_sha256'],
            'policy_sha256': value['policy_sha256'],
            'session_id': value['session']['session_id'], 'active': relay.lock.locked(), 'unresolved': unresolved}
    server = PrivateRPCServer(RUN / 'model.sock', protocol='ai4r-local-model:1', **value['session'],
        handlers={'invoke': relay.invoke, 'status': status}, allowed_uids={0, 12001},
        socket_mode=0o660, directory_mode=0o710, group_id=13000)
    stop = asyncio.Event(); loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM): loop.add_signal_handler(sig, stop.set)
    try:
        await server.start(); await stop.wait()
    finally:
        await server.close(); relay.close()


async def check():
    need(os.geteuid() == 0)
    value = load()
    from jiuwenswarm.research.private_rpc import PrivateRPCClient
    client = PrivateRPCClient(RUN / 'model.sock', protocol='ai4r-local-model:1', **value['session'], peer_uid=0, socket_mode=0o660)
    status = await client.call('status', {}, timeout_s=10)
    print(json.dumps({'status': 'BLOCKED' if status['active'] or status['unresolved'] else 'TRANSPORT_AVAILABLE',
        'active': status['active'], 'unresolved': status['unresolved'], 'generation_sent': False,
        'account_and_model_access': 'rechecked_in_native_helper_before_each_inference'}))


async def smoke():
    deadline = time.monotonic() + 120
    need(os.geteuid() == 12001 and os.getegid() == 12001)
    custody(CLIENT, 12001, 12001, 0o700, directory=True)
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research_rsi.host_codex_backend import HostCodexSubscriptionService, MODEL
    directory = CLIENT / 'public-smoke'
    directory.mkdir(mode=0o700)  # Refuse replay, including after unknown outcomes.
    write_new(directory / 'started.json', {'schema': 'ai4r-host-public-smoke-start:1',
        'purpose': 'separately_authorized_public_transport_smoke', 'model': MODEL, 'reasoning_effort': 'medium',
        'timeout_s': 120, 'tools': [], 'benchmark_replay': False, 'operational_qualification': False}, 12001, 12001, 0o600)
    store = SQLiteRunStore(directory / 'core')
    owner = HostCodexSubscriptionService(CLIENT)
    owner.set_governed_trace_writer(store.append_record, store.put_blob)
    owner.set_account_observer(store.append_record)
    identifier = 'host-public-smoke:' + uuid.uuid4().hex
    contract = store.append_record('host-public-smoke-contract', {'purpose': 'public_transport_only',
        'requested_model': MODEL, 'reasoning_effort': 'medium', 'tools': [], 'timeout_s': 120})
    start = store.append_record('host-public-smoke-call-start', {'call_id': identifier, 'contract_ref': contract})
    scope = {key: identifier for key in ('run_id', 'node_id', 'subnode_id', 'attempt_id', 'execution_id', 'invocation_id', 'call_id')}
    scope.update(contract_ref=contract, model_call_start_ref=start)
    summary = {'schema': 'ai4r-host-public-smoke-result:1', 'purpose': 'public_transport_only', 'operational_qualification': False,
        'workspace_routing_observed_by_helper': False, 'workspace_routing_evidence': 'separate operator preflight'}
    try:
        remaining = deadline - time.monotonic()
        need(remaining > 0)
        result = await owner.invoke_governed_traced(scope,
            'Return only JSON {"value":4}, the integer sum of two and two. Do not use tools.', model=MODEL, timeout_s=remaining)
        from jiuwenswarm.research.local_model_codex import unpack_bundle
        bundle = unpack_bundle(store.read_record(store.read_record(result['host_native_original_ref'])['raw_ref']))
        try:
            answer = json.loads(result['text']); json_valid = True
        except ValueError:
            answer = None; json_valid = False
        summary.update(outcome='completed', effective_model=result['identity']['effective'],
            reasoning_effort=bundle['thread_start']['reasoningEffort'],
            native_terminal_status=bundle['turn_completed']['turn']['status'], native_outcome=bundle['outcome'],
            provider_turn_id=result['provider_request_id'], usage=result['usage'],
            json_valid=json_valid, json_answer_correct=answer == {'value': 4},
            native_trace_ref=result['native_trace_ref'], host_native_original_ref=result['host_native_original_ref'])
    except BaseException as error:
        summary.update(outcome='outcome_unknown' if getattr(error, 'outcome_unknown', False) else 'failed',
            error_code=getattr(error, 'code', 'invalid_output'), native_trace_ref=getattr(error, 'native_trace_ref', None),
            host_native_original_ref=getattr(error, 'host_native_original_ref', None))
        if summary['host_native_original_ref'] is not None:
            from jiuwenswarm.research.local_model_codex import unpack_bundle
            bundle = unpack_bundle(store.read_record(store.read_record(summary['host_native_original_ref'])['raw_ref']))
            thread = bundle.get('thread_start') or {}; terminal = bundle.get('turn_completed') or {}
            summary.update(effective_model=thread.get('model'), reasoning_effort=thread.get('reasoningEffort'),
                native_terminal_status=terminal.get('turn', {}).get('status'), native_outcome=bundle['outcome'],
                provider_turn_id=(bundle.get('turn_start') or {}).get('turn', {}).get('id'))
    finally:
        write_new(directory / 'summary.json', summary, 12001, 12001, 0o600)
        store.close()
    print(json.dumps(summary))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare_parser = commands.add_parser('prepare', allow_abbrev=False)
    for field in ('host-python', 'codex-executable', 'codex-sha256', 'account-fingerprint', 'working-directory'):
        prepare_parser.add_argument('--' + field, required=True)
    prepare_parser.add_argument('--context-window', type=int, required=True)
    for name in ('serve', 'check', 'smoke', 'restore-runtime'): commands.add_parser(name, allow_abbrev=False)
    args = parser.parse_args(argv)
    if args.command == 'prepare': prepare(args)
    elif args.command == 'restore-runtime': restore_runtime()
    else: asyncio.run({'serve': serve, 'check': check, 'smoke': smoke}[args.command]())


if __name__ == '__main__': main()
