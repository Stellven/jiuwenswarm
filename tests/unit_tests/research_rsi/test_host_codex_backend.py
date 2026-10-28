"""Offline exact host native evidence/identity/unknown guards; no native launch."""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research import local_model_relay as relay_module
from jiuwenswarm.research.local_models import LocalModelClient, canonical
from jiuwenswarm.research.providers import ProviderError
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.fixed_subscription import deployment_model, deployment_backend, require_profile_model
from jiuwenswarm.research_rsi import host_codex_backend as host
from jiuwenswarm.research_rsi.spark_backend import subscription_for_deployment


def document():
    return {'schema': 'ai4r-local-model-catalog:1', 'gateway_id': 'rsi-host-fixture',
        'backend': {'kind': 'host-codex-app-server', 'host_python': '/mnt/c/fixture/python.exe',
            'codex_executable': 'C:/fixture/codex.exe', 'codex_sha256': host.NATIVE_SHA256,
            'account_fingerprint': 'c' * 64, 'working_directory': 'D:/fixture/empty-work'},
        'transport': {'socket_path': host.SOCKET.as_posix(), 'session_file': host.SESSION.as_posix(), 'peer_uid': 0, 'socket_mode': 0o660},
        'models': [{'id': host.ENDPOINT, 'name': 'Fixture only', 'model_name': host.MODEL,
            'revision': 'codex-cli-0.163.0-operator-qualified', 'enabled': True, 'context_window': 32768,
            'max_prompt_bytes': 262144, 'timeout_s': 120, 'reasoning_effort': 'medium'}]}


class Catalog(host.HostCatalog):
    def snapshot(self): return host.validate_host_catalog(document())
    def resolve(self, endpoint_id, binding_sha256=None):
        from jiuwenswarm.research.local_models import LocalModelCatalog
        return LocalModelCatalog.resolve(self, endpoint_id, binding_sha256)


def deployment():
    return {'schema': 'ai4r-fixed-subscription:2', 'id': 'host-fixture', 'route_id': 'codex-cli-default',
        'requested_model': host.MODEL, 'endpoint': 'local-protected-IPC', 'backend': 'host-codex-app-server',
        'reasoning_effort': 'medium'}


def native(prompt, *, outcome='completed'):
    bundle = {'schema': 'ai4r-host-codex-response:1', 'requested_model': host.MODEL,
        'account_fingerprint': 'c' * 64, 'binary_sha256': host.NATIVE_SHA256, 'reasoning_effort': 'medium',
        'thread_start': {'thread': {'id': 'thread-fixture'}, 'model': host.MODEL, 'reasoningEffort': 'medium'},
        'turn_start': {'turn': {'id': 'turn-fixture'}}, 'turn_completed': None, 'wire_frames': [],
        'outcome': outcome, 'error_code': None if outcome == 'completed' else 'CONTAINMENT_UNCERTAIN'}
    def frame(direction, packet): bundle['wire_frames'].append({'direction': direction, 'raw': json.dumps(packet) + '\n'})
    frame('out', {'id': 1, 'method': 'thread/start', 'params': {'model': host.MODEL, 'config': {'model_reasoning_effort': 'medium'}}})
    frame('in', {'id': 1, 'result': bundle['thread_start']})
    frame('out', {'id': 2, 'method': 'turn/start', 'params': {'threadId': 'thread-fixture', 'model': host.MODEL,
        'input': [{'type': 'text', 'text': prompt}]}})
    frame('in', {'id': 2, 'result': bundle['turn_start']})
    frame('in', {'method': 'thread/tokenUsage/updated', 'params': {'threadId': 'thread-fixture', 'turnId': 'turn-fixture',
        'tokenUsage': {'last': {'inputTokens': 9, 'outputTokens': 4}}}})
    if outcome == 'completed':
        bundle['turn_completed'] = {'threadId': 'thread-fixture', 'turn': {'id': 'turn-fixture', 'status': 'completed',
            'items': [{'id': 'msg-fixture', 'type': 'agentMessage', 'text': '  {"value":4}\n'}]}}
        frame('in', {'method': 'turn/completed', 'params': bundle['turn_completed']})
    return bundle


@pytest.mark.parametrize('mutation', ['model', 'effort', 'socket', 'backend', 'extra_generation_control'])
def test_host_catalog_is_exact_finite_policy(mutation):
    value = document()
    if mutation == 'model': value['models'][0]['model_name'] = 'gpt-6-luna'
    elif mutation == 'effort': value['models'][0]['reasoning_effort'] = 'high'
    elif mutation == 'socket': value['transport']['socket_path'] = '/tmp/foreign.sock'
    elif mutation == 'backend': value['backend'] = {'kind': 'ssh-loopback-openai', 'target': 'fixture', 'base_url': 'http://127.0.0.1:8000/v1'}
    else: value['models'][0]['enable_thinking'] = True
    with pytest.raises(ResearchError): host.validate_host_catalog(value)


@pytest.mark.parametrize('change', [{'tools_count': 1}, {'additional_tools_count': 9}, {'functions_count': False},
    {'tool_names': ['exec']}, {'helper_sha256': '0' * 64}, {'binary_sha256': '0' * 64},
    {'model_catalog_sha256': '0' * 64}, {'native_version': '0.161.0'}, {'extra': True}])
def test_qualification_requires_actual_current_empty_tools_proof(change):
    from jiuwenswarm.research.local_model_codex import MODEL_CATALOG_SHA256
    value = {'schema': 'ai4r-rsi-host-codex-no-tools:1', 'native_version': '0.163.0', 'binary_sha256': host.NATIVE_SHA256,
        'helper_sha256': hashlib.sha256(Path(host.__file__).parents[1].joinpath('research/local_model_codex.py').read_bytes()).hexdigest(),
        'model_catalog_sha256': MODEL_CATALOG_SHA256, 'model': host.MODEL, 'reasoning_effort': 'medium',
        'proof_sha256': 'a' * 64, 'tools_count': 0, 'functions_count': 0, 'additional_tools_count': 0, 'tool_names': []}
    assert host.validate_qualification(value, document()) == value
    with pytest.raises(ResearchError): host.validate_qualification(dict(value, **change), document())


def test_production_catalog_fails_closed_without_root_qualification(tmp_path, monkeypatch):
    from jiuwenswarm.research.local_models import LocalModelCatalog
    monkeypatch.setattr(LocalModelCatalog, 'snapshot', lambda _: document())
    monkeypatch.setattr(host, 'QUALIFICATION', tmp_path / 'missing.json')
    with pytest.raises(FileNotFoundError): host.HostCatalog().snapshot()


def test_prepared_binding_and_client_resolver_use_identical_qualified_policy_hash(tmp_path, monkeypatch):
    from jiuwenswarm.research.local_model_codex import MODEL_CATALOG_SHA256
    value = document()
    qualified = {'schema': 'ai4r-rsi-host-codex-no-tools:1', 'native_version': '0.163.0', 'binary_sha256': host.NATIVE_SHA256,
        'helper_sha256': hashlib.sha256(Path(host.__file__).parents[1].joinpath('research/local_model_codex.py').read_bytes()).hexdigest(),
        'model_catalog_sha256': MODEL_CATALOG_SHA256, 'model': host.MODEL, 'reasoning_effort': 'medium',
        'proof_sha256': 'a' * 64, 'tools_count': 0, 'functions_count': 0, 'additional_tools_count': 0, 'tool_names': []}
    catalog_path, proof_path = tmp_path / 'catalog.json', tmp_path / 'qualification.json'
    catalog_path.write_bytes(canonical(value)); catalog_path.chmod(0o640)
    proof_path.write_bytes(canonical(qualified)); proof_path.chmod(0o640)
    monkeypatch.setattr(host, 'QUALIFICATION', proof_path)
    actual = host.HostCatalog(catalog_path, owner_uid=os.geteuid() if os.name == 'posix' else 0).resolve(host.ENDPOINT)
    expected = {key: value[key] for key in ('gateway_id', 'backend', 'transport')}
    expected['model'] = value['models'][0]
    expected['binding_sha256'] = hashlib.sha256(canonical(expected)).hexdigest()
    expected['host_qualification_sha256'] = hashlib.sha256(canonical(qualified)).hexdigest()
    assert actual == expected and host.descriptor(actual) == host.descriptor(expected)


def test_explicit_host_deployment_and_profile_cannot_mix_with_same_named_cloud(tmp_path):
    value = deployment()
    assert deployment_model(value) == host.MODEL and deployment_backend(value) == 'host-codex-app-server'
    assert type(subscription_for_deployment(tmp_path, value)) is host.HostCodexSubscriptionService
    cloud = {key: item for key, item in value.items() if key not in {'backend', 'reasoning_effort'}}
    cloud['schema'] = 'ai4r-fixed-subscription:1'
    assert deployment_backend(cloud) == 'codex'
    assert type(subscription_for_deployment(tmp_path, cloud)) is not host.HostCodexSubscriptionService
    profile = {'schema': 'ai4r-local-profile:1', 'model': host.MODEL}
    with pytest.raises(ResearchError): require_profile_model(profile, host.MODEL, backend='host-codex-app-server')
    with pytest.raises(ResearchError): require_profile_model(dict(profile, backend='host-codex-app-server'), host.MODEL, backend='host-codex-app-server')
    for change in ({'reasoning_effort': 'high'}, {'requested_model': 'gpt-6-luna'}, {'backend': 'codex'}, {'extra': True}):
        with pytest.raises(ResearchError): deployment_model(dict(value, **change))


@pytest.mark.parametrize('packet', [
    {'method': 'account/updated', 'params': {'threadId': 'thread-fixture', 'email': 'private@example.invalid'}},
    {'method': 'login/completed', 'params': {'threadId': 'thread-fixture'}},
    {'method': 'auth/changed', 'params': {'threadId': 'thread-fixture'}},
    {'id': 999, 'result': {'account': {'email': 'private@example.invalid'}}},
])
def test_private_account_or_unowned_reply_is_never_a_valid_core_bundle(packet):
    from jiuwenswarm.research.local_models import native_codex_response
    bundle = native('public fixture')
    bundle['wire_frames'].append({'direction': 'in', 'raw': json.dumps(packet)})
    with pytest.raises(ResearchError): native_codex_response(json.dumps(bundle), Catalog().resolve(host.ENDPOINT), prompt='public fixture')


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['completed', 'unknown', 'malformed', 'observer_failure', 'refusal'])
async def test_adapter_preserves_original_native_bytes_and_primary_unknown(tmp_path, monkeypatch, mode):
    prompt = 'Exact public fixture text.\n$(not a shell command)'
    captured = []
    original = native(prompt, outcome='outcome_unknown' if mode == 'unknown' else 'completed')
    if mode == 'refusal':
        original['outcome']='failed';original['error_code']='provider_error'
        original['turn_completed']['turn']['status']='interrupted'
        original['wire_frames'][-1]['raw']=json.dumps({'method':'turn/completed','params':original['turn_completed']})+'\n'
        request={'id':999,'method':'item/commandExecution/requestApproval',
                 'params':{'threadId':'thread-fixture','turnId':'turn-fixture'}}
        refusal={'id':999,'error':{'code':-32601,'message':'Tools and approvals are unavailable.'}}
        original['wire_frames'][-1:-1]=[{'direction':'in','raw':json.dumps(request)+'\n'},
                                       {'direction':'out','raw':json.dumps(refusal)+'\n'}]
    original_text = json.dumps(original) if mode != 'malformed' else '{malformed native bytes'
    class RPC:
        def __init__(self, *args, **kwargs): pass
        async def call(self, operation, payload, **kwargs):
            captured.append(copy.deepcopy(payload))
            return {'request_id': payload['request_id'], 'binding_sha256': payload['binding_sha256'],
                'outcome': original['outcome'], 'http_status': None,
                'response_text': original_text, 'provider_request_id': 'turn-fixture'}
    monkeypatch.setattr(LocalModelClient, 'preflight', lambda self: {'session_id': 's' * 32, 'capability': 'c' * 48})
    service = host.HostCodexSubscriptionService(tmp_path / 'client', catalog=Catalog(),
        client_factory=lambda binding: LocalModelClient(binding, rpc_factory=RPC))
    store = SQLiteRunStore(tmp_path / 'core')
    try:
        service.set_governed_trace_writer(store.append_record, store.put_blob)
        service.set_account_observer(store.append_record)
        if mode == 'observer_failure':
            def unavailable(*args): raise RuntimeError('Controlled observer failure')
            service.set_account_observer(unavailable)
        pin = store.put_blob(b'fixture-scope-reference')
        scope = {key: 'fixture-' + key for key in ('run_id', 'node_id', 'subnode_id', 'attempt_id', 'execution_id', 'invocation_id', 'call_id')}
        scope.update(contract_ref=pin, model_call_start_ref=pin)
        if mode == 'completed':
            result = await service.invoke_governed_traced(scope, prompt, model=host.MODEL, timeout_s=30)
            assert result['text'] == '  {"value":4}\n' and result['identity']['effective'] == host.MODEL
            assert result['usage']['input_tokens'] == 9 and result['usage']['output_tokens'] == 4
            assert result['provider_request_id'] == 'turn-fixture'
        else:
            with pytest.raises(ProviderError) as failure:
                await service.invoke_governed_traced(scope, prompt, model=host.MODEL, timeout_s=30)
            assert failure.value.outcome_unknown is (mode != 'refusal')
            assert failure.value.code == {'unknown': 'CONTAINMENT_UNCERTAIN', 'malformed': 'invalid_output',
                                          'observer_failure': 'AUDIT_UNAVAILABLE','refusal':'provider_error'}[mode]
            result = {'native_trace_ref': failure.value.native_trace_ref,
                      'host_native_original_ref': failure.value.host_native_original_ref}
        assert captured[0]['prompt'] == prompt
        trace = store.read_record(result['native_trace_ref'])
        assert trace['scope'] == scope
        if mode == 'malformed':
            assert result['host_native_original_ref'] is None and trace['event_refs'] == []
            assert not list(store.iter_records(kinds=('host-codex-native-original', 'host-codex-runtime-observation')))
        else:
            record = store.read_record(result['host_native_original_ref'])
            assert record['scope'] == scope and store.read_blob(record['raw_ref']) == original_text.encode()
            native_raw = [store.read_blob(store.read_record(ref)['raw_ref']) for ref in trace['event_refs']]
            assert native_raw == [frame['raw'].encode() for frame in original['wire_frames']]
        assert not service.active and not hasattr(service.transport, 'process')
    finally: store.close()


@pytest.mark.asyncio
async def test_reused_durable_relay_unknown_blocks_all_new_ids_after_restart(tmp_path, monkeypatch):
    if os.name != 'posix': monkeypatch.setattr(relay_module, 'private_path', lambda *args, **kwargs: None)
    directory = tmp_path / 'dedicated-rsi-relay'; directory.mkdir(mode=0o700)
    binding = Catalog().resolve(host.ENDPOINT)
    class Backend:
        calls = 0
        async def __call__(self, bound, payload):
            self.calls += 1
            # Lost raw response is uncertain, not a manufactured provider failure.
            return relay_module.CapturedBackendReceipt(relay_module.LocalModelRelay._unknown(), b'original malformed stdout', 'invalid_json')
    backend = Backend(); relay = relay_module.LocalModelRelay(Catalog(), directory, backend=backend)
    request = {'request_id': 'first', 'endpoint_id': host.ENDPOINT, 'binding_sha256': binding['binding_sha256'],
        'model': host.MODEL, 'prompt': 'public tiny marker', 'timeout_s': 30}
    result = await relay.invoke(request)
    assert result['outcome'] == 'outcome_unknown' and backend.calls == 1
    files = list((directory / 'backend-receipts').glob('*.receipt'))
    assert len(files) == 1 and files[0].read_bytes() == b'original malformed stdout'
    relay.close()
    reopened = relay_module.LocalModelRelay(Catalog(), directory, backend=backend)
    try:
        assert await reopened.invoke(request) == result
        with pytest.raises(ResearchError, match='DELIVERY_UNKNOWN'):
            await reopened.invoke(dict(request, request_id='another-id'))
        assert backend.calls == 1
    finally: reopened.close()


@pytest.mark.skipif(os.name != 'posix', reason='Actual Linux Unix peer/custody boundary')
@pytest.mark.asyncio
async def test_actual_unix_relay_and_adapter_roundtrip_original_native_fixture(tmp_path):
    from jiuwenswarm.research.local_models import LocalModelCatalog
    from jiuwenswarm.research.private_rpc import PrivateRPCServer
    runtime, export = tmp_path / 'private-relay', tmp_path / 'socket-export'
    runtime.mkdir(mode=0o700)
    export.mkdir(mode=0o700)
    session = {'session_id': 'offline-session-' + 's' * 32, 'capability': 'offline-capability-' + 'c' * 48}
    session_path = runtime / 'session.json'
    session_path.write_text(json.dumps(session)); session_path.chmod(0o600)
    value = document()
    value['transport'] = {'socket_path': str(export / 'model.sock'), 'session_file': str(session_path),
                          'peer_uid': os.geteuid(), 'socket_mode': 0o600}
    catalog_path = tmp_path / 'catalog.json'; catalog_path.write_text(json.dumps(value)); catalog_path.chmod(0o600)
    catalog = LocalModelCatalog(catalog_path, owner_uid=os.geteuid())
    observed = []
    class Backend:
        async def __call__(self, binding, payload):
            observed.append(payload)
            bundle = native(payload['prompt'])
            return {'outcome': 'completed', 'http_status': None,
                'response_text': json.dumps(bundle), 'provider_request_id': 'turn-fixture'}
    relay = relay_module.LocalModelRelay(catalog, runtime, backend=Backend())
    server = PrivateRPCServer(export / 'model.sock', protocol=host.PROTOCOL, **session,
        handlers={'invoke': relay.invoke}, allowed_uids={os.geteuid()})
    store = SQLiteRunStore(tmp_path / 'core')
    try:
        await server.start()
        service = host.HostCodexSubscriptionService(tmp_path / 'client', catalog=catalog)
        service.set_governed_trace_writer(store.append_record, store.put_blob)
        pin = store.put_blob(b'offline-unix-scope')
        scope = {key: 'actual-unix-' + key for key in ('run_id', 'node_id', 'subnode_id', 'attempt_id',
            'execution_id', 'invocation_id', 'call_id')}
        scope.update(contract_ref=pin, model_call_start_ref=pin)
        result = await service.invoke_governed_traced(scope, 'Public Unix fixture only', model=host.MODEL, timeout_s=10)
        assert result['text'] == '  {"value":4}\n' and len(observed) == 1
        record = store.read_record(result['host_native_original_ref'])
        assert store.read_blob(record['raw_ref']) == json.dumps(native('Public Unix fixture only')).encode()
        assert relay.db.execute('SELECT count(*) FROM requests').fetchone()[0] == 1
        assert len(list((runtime / 'backend-receipts').glob('*.receipt'))) == 1
    finally:
        await server.close(); relay.close(); store.close()
