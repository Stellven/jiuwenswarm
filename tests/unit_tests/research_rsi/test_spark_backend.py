"""Fixed Spark boundary tests; no real endpoints, listeners or inference."""
import asyncio
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
import io
from email.message import Message
import struct
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research_rsi import spark_backend as spark


def governed_params():
    return {'modelProvider': 'ai4r_governed', 'model': spark.MODEL, 'sandbox': 'read-only',
        'approvalPolicy': 'never', 'ephemeral': True,
        'config': {**spark.governed_tool_config(), 'model_providers.ai4r_governed.name': 'AI4Research governed subscription',
                   'model_providers.ai4r_governed.wire_api': 'responses',
                   'model_providers.ai4r_governed.requires_openai_auth': True,
                   'model_providers.ai4r_governed.request_max_retries': 0,
                   'model_providers.ai4r_governed.stream_max_retries': 0}}


def deployment(model=spark.MODEL):
    return {'schema': 'ai4r-fixed-subscription:1', 'id': 'fixed-test', 'route_id': 'codex-cli-default',
            'requested_model': model, 'endpoint': 'local-protected-IPC'}


def test_transport_injects_only_fixed_provider_and_audits_actual_wire(tmp_path, monkeypatch):
    transport = spark.SparkTransport(tmp_path, gateway=SimpleNamespace(close=lambda: None))
    captured = []
    def observer(direction, raw, packet):
        captured.append(json.loads(raw))
    async def request(self, method, params=None, *, wire_observer=None):
        assert wire_observer is observer
        packet = {'method': method, 'params': params}
        wire_observer('out', json.dumps(packet).encode(), packet)
        return {'thread': {'id': 'native-thread'}, 'model': spark.MODEL}
    monkeypatch.setattr(spark.AppServerTransport, 'request', request)
    params = governed_params()
    params['developerInstructions'] = 'Exact public governed instructions.\nReturn the requested typed value only.'
    original = copy.deepcopy(params)
    result = asyncio.run(transport.request('thread/start', params, wire_observer=observer))
    assert result['model'] == spark.MODEL and params == original
    actual = captured[0]['params']
    assert actual['modelProvider'] == 'ai4r_spark'
    assert actual['config'] == spark.provider_configuration()
    assert actual['config']['model_providers.ai4r_spark.base_url'] == 'http://127.0.0.1:5175/v1'
    assert actual['config']['model_providers.ai4r_spark.requires_openai_auth'] is False
    assert actual['config']['model_providers.ai4r_spark.request_max_retries'] == 0
    assert actual['config']['model_providers.ai4r_spark.stream_max_retries'] == 0
    assert actual['config']['model_context_window'] == 16384
    assert actual['baseInstructions'] == spark.BASE_INSTRUCTIONS
    assert len(actual['baseInstructions']) == 421
    assert actual['allowProviderModelFallback'] is False
    assert {key: actual[key] for key in original if key not in ('modelProvider', 'config')} == {
        key: original[key] for key in original if key not in ('modelProvider', 'config')}
    for key in ('features.view_image', 'features.multi_agent', 'features.goals',
                'tools.experimental_request_user_input.enabled'):
        assert actual['config'][key] is False


@pytest.mark.parametrize('change', [{'model': 'gpt-6-luna'}, {'sandbox': 'danger-full-access'},
    {'modelProvider': 'openai'}, {'approvalPolicy': 'on-request'}, {'ephemeral': False},
    {'config': {'model_providers.ai4r_governed.base_url': 'https://foreign'}},
    {'baseInstructions': 'Foreign override'}, {'baseInstructions': None}, {'baseInstructions': spark.BASE_INSTRUCTIONS}])
def test_transport_rejects_model_provider_and_capability_substitution(tmp_path, change):
    transport = spark.SparkTransport(tmp_path, gateway=SimpleNamespace(close=lambda: None))
    params = governed_params()
    params.update(change)
    with pytest.raises(ValueError):
        asyncio.run(transport.request('thread/start', params))


def test_caller_cannot_select_native_context_even_if_matching_protected_value(tmp_path):
    transport = spark.SparkTransport(tmp_path, gateway=SimpleNamespace(close=lambda: None))
    params = governed_params()
    params['config']['model_context_window'] = 16384
    with pytest.raises(ValueError):
        asyncio.run(transport.request('thread/start', params))


def test_existing_oauth_profile_refused_without_reading_or_replacing_it(tmp_path):
    home = tmp_path / 'codex-home'
    home.mkdir()
    auth = home / 'auth.json'
    auth.write_bytes(b'existing-private-profile-must-stay-untouched')
    transport = spark.SparkTransport(tmp_path, gateway=SimpleNamespace(close=lambda: None))
    with pytest.raises(ValueError):
        asyncio.run(transport.start())
    assert auth.read_bytes() == b'existing-private-profile-must-stay-untouched'


@pytest.mark.parametrize('header', ['Authorization', 'authorization', 'Cookie', 'Proxy-Authorization',
                                    'OpenAI-Organization', 'OpenAI-Project', 'X-Api-Key', 'transfer-encoding'])
def test_gateway_rejects_oauth_keys_identity_and_transfer_encoding(header):
    with pytest.raises(ValueError):
        spark.validated_request('POST', '/v1/responses', {header: 'private'}, json.dumps({'model': spark.MODEL}).encode())


def test_gateway_regenerates_headers_and_drops_codex_identity():
    result, body = spark.validated_request('POST', '/v1/responses',
        {'User-Agent': 'native', 'session-id': 'private', 'x-codex-turn-metadata': 'private'},
        json.dumps({'model': spark.MODEL, 'tools': []}).encode())
    assert result == {'Connection': 'close', 'Content-Type': 'application/json', 'Accept': 'text/event-stream'}
    assert json.loads(body)['chat_template_kwargs'] == {'enable_thinking': True}


@pytest.mark.parametrize('path,body', [('/v1/responses?redirect=foreign', {'model': spark.MODEL}),
    ('https://foreign/v1/responses', {'model': spark.MODEL}), ('/v1/responses', {'model': 'gpt-6-luna'}),
    ('/v1/responses', {'model': spark.MODEL, 'tools': [{'type': 'web_search'}]}),
    ('/v1/responses', {'model': spark.MODEL, 'previous_response_id': 'foreign'})])
def test_gateway_rejects_route_model_tools_or_foreign_conversation(path, body):
    with pytest.raises(ValueError):
        spark.validated_request('POST', path, {}, json.dumps(body).encode())


def test_gateway_refuses_host_network_before_binding(monkeypatch):
    monkeypatch.setattr(spark.socket, 'if_nameindex', lambda: [(1, 'lo'), (2, 'eth0')])
    gateway = spark.SparkGateway()
    with pytest.raises(ValueError):
        gateway.start({})
    assert gateway.server is None


def descriptor():
    profile = {'schema': 'ai4r-rsi-spark:1', 'model': spark.MODEL, 'remote': '127.0.0.1:8000',
        'socket': str(spark.SOCKET), 'protocol': 'openai', 'profile': '/var/lib/ai4r-rsi-spark/profile.json',
        'source_epoch': 'a' * 32, 'boot_id': 'controlled-kernel-boot'}
    listener = dict(profile, pid=123, start_ticks='42', socket_inode=789)
    return spark.effective_descriptor(profile, listener)


@pytest.mark.parametrize('change', ['foreign_model', 'foreign_boot', 'extra_field', 'socket_inode'])
def test_root_public_descriptor_rejects_source_or_inode_changes(monkeypatch, change):
    value = descriptor()
    if change == 'foreign_model':
        value['profile']['model'] = 'gpt-6-luna'
    elif change == 'foreign_boot':
        value['profile']['boot_id'] = 'foreign'
    elif change == 'extra_field':
        value['profile']['authorization'] = 'not-allowed'
    else:
        value['listener']['socket_inode'] = 999
    monkeypatch.setattr(spark.os, 'geteuid', lambda: 12001, raising=False)
    monkeypatch.setattr(spark.os, 'getegid', lambda: 12001, raising=False)
    monkeypatch.setattr(spark.os, 'getgroups', lambda: [13000], raising=False)
    monkeypatch.setattr(spark, '_protected', lambda *args: SimpleNamespace(st_ino=789))
    monkeypatch.setattr(spark, '_json_file', lambda path: value['profile'] if path == spark.PUBLIC_PROFILE else value['listener'])
    monkeypatch.setattr(Path, 'read_text', lambda *args, **kwargs: 'controlled-kernel-boot')
    with pytest.raises(ValueError):
        spark.public_descriptor()


@pytest.mark.parametrize('cloud_model', ['gpt-6-luna', 'gpt-5.6-terra'])
def test_factory_preserves_cloud_and_constructs_local_without_effects(tmp_path, monkeypatch, cloud_model):
    monkeypatch.setattr(spark, 'metadata', lambda *args: pytest.fail('No metadata probe at construction'))
    local = spark.subscription_for_deployment(tmp_path / 'local', deployment())
    cloud = spark.subscription_for_deployment(tmp_path / 'cloud', deployment(cloud_model))
    assert type(local) is spark.SparkSubscriptionService
    assert type(cloud) is spark.SubscriptionService
    assert local.transport.process is None and local.gateway.server is None
    assert local.account_observation_state['reason'] == 'local_provider_has_no_subscription_limits'


@pytest.mark.parametrize('uid', [0, 12001])
def test_relay_requires_root_peer_but_accepts_pid_zero_across_namespaces(monkeypatch, uid):
    value = descriptor()
    closed = []
    class Peer:
        def settimeout(self, seconds): pass
        def connect(self, path): assert path == str(spark.SOCKET)
        def getsockopt(self, *args): return struct.pack('3i', 0, uid, 0)
        def close(self): closed.append(True)
    monkeypatch.setattr(spark, 'public_descriptor', lambda: value)
    monkeypatch.setattr(spark, '_protected', lambda *args: SimpleNamespace(st_ino=789))
    monkeypatch.setattr(spark.socket, 'socket', lambda *args: Peer())
    monkeypatch.setattr(spark.socket, 'AF_UNIX', 1, raising=False)
    monkeypatch.setattr(spark.socket, 'SO_PEERCRED', 17, raising=False)
    if uid == 0:
        connection = spark.unix_connection(value)
        connection.close()
    else:
        with pytest.raises(ValueError):
            spark.unix_connection(value)
    assert closed == [True]


def test_local_account_login_operations_are_unavailable(tmp_path):
    service = spark.SparkSubscriptionService(tmp_path)
    for operation in (service.login, service.logout, lambda: service.cancel_login('foreign')):
        with pytest.raises(spark.CodexError, match='LOCAL_PROVIDER_HAS_NO_ACCOUNT_LOGIN'):
            asyncio.run(operation())


def test_readiness_without_existing_native_owner_cannot_start_one(tmp_path, monkeypatch):
    service = spark.SparkSubscriptionService(tmp_path)
    value = descriptor()
    service._spark_descriptor = value
    monkeypatch.setattr(spark, 'public_descriptor', lambda: value)
    monkeypatch.setattr(service.gateway, 'check', lambda descriptor: None)
    monkeypatch.setattr(spark, 'metadata', lambda *args: pytest.fail('No metadata without native owner'))
    store = SimpleNamespace(read_record=lambda pin: deployment())
    with pytest.raises(ValueError):
        service.readiness_proof(store=store, deployment_ref={'id': 'deployment', 'sha256': 'a' * 64})
    assert service.transport.process is None


@pytest.mark.parametrize('tamper', ['model', 'policy_hash', 'legacy_observation', 'legacy_policy'])
def test_readiness_uses_current_metadata_and_persisted_local_observation_only(tmp_path, monkeypatch, tamper):
    service = spark.SparkSubscriptionService(tmp_path)
    value = descriptor()
    actual = {'model': spark.MODEL, 'descriptor_sha256': value['descriptor_sha256'],
              'request_policy_sha256': hashlib.sha256(spark._encoded(spark.request_policy())).hexdigest(),
              'source_epoch': value['profile']['source_epoch'], 'boot_id': value['profile']['boot_id']}
    service._spark_descriptor = value
    service.account_fingerprint = 'spark-source:' + value['descriptor_sha256']
    service.transport.process = SimpleNamespace(pid=99, returncode=None)
    service.transport._reader = SimpleNamespace(done=lambda: False)
    observation = {'schema': 'ai4r-rsi-spark-runtime-observation:2', **actual, 'epoch': service.epoch,
        'source_fingerprint': service.account_fingerprint, 'profile_id': hashlib.sha256(str(service.root).encode()).hexdigest(),
        'observed_at': datetime.now(timezone.utc).isoformat()}
    service.last_spark_observation = observation
    pin = {'id': 'observation', 'sha256': 'b' * 64}
    deployment_ref = {'id': 'deployment', 'sha256': 'a' * 64}
    store = SimpleNamespace(read_record=lambda ref: deployment(),
        iter_records=lambda **kwargs: [{'record': observation, 'ref': pin}],
        record_kind=lambda ref: 'spark-runtime-observation', read_blob=lambda ref: b'original-observation')
    monkeypatch.setattr(spark, 'public_descriptor', lambda: value)
    monkeypatch.setattr(service.gateway, 'check', lambda descriptor: None)
    monkeypatch.setattr(spark, 'metadata', lambda descriptor: actual)
    monkeypatch.setattr(spark.os, 'kill', lambda *args: None)
    assert service.readiness_proof(store=store, deployment_ref=deployment_ref) == [deployment_ref, pin]
    if tamper == 'model':
        actual['model'] = 'foreign-model'
    elif tamper == 'policy_hash':
        observation['request_policy_sha256'] = 'f' * 64
    elif tamper == 'legacy_observation':
        observation['schema'] = 'ai4r-rsi-spark-runtime-observation:1'
        del observation['request_policy_sha256']
    else:
        previous = spark.request_policy()
        previous['schema'] = 'ai4r-spark-request-policy:2'
        previous['chat_template_kwargs']['enable_thinking'] = False
        observation['request_policy_sha256'] = hashlib.sha256(spark._encoded(previous)).hexdigest()
    with pytest.raises(ValueError):
        service.readiness_proof(store=store, deployment_ref=deployment_ref)


@pytest.mark.parametrize('kwargs', [None, {}, {'enable_thinking': False}, {'enable_thinking': 0}, {'enable_thinking': 1},
    {'enable_thinking': True, 'thinking_budget': 1}, {'enable_thinking': True, 'foreign_template_flag': True}])
def test_fixed_policy_rejects_conflicting_or_ambiguous_template_kwargs(kwargs):
    raw = json.dumps({'model': spark.MODEL, 'input': 'unchanged public test', 'chat_template_kwargs': kwargs}).encode()
    with pytest.raises(ValueError):
        spark.validated_request('POST', '/v1/responses', {}, raw)


@pytest.mark.parametrize('extra', [{'chat_template': 'foreign'}, {'chat_template': None}, {'enable_thinking': True}])
def test_custom_template_cannot_bypass_fixed_installed_template(extra):
    with pytest.raises(ValueError):
        spark.validated_request('POST', '/v1/responses', {}, json.dumps({'model': spark.MODEL, **extra}).encode())


@pytest.mark.parametrize('body', [
    b'{"model":"Qwen3.8-27B-NVFP4","model":"foreign"}',
    b'{"model":"Qwen3.8-27B-NVFP4","chat_template_kwargs":{"enable_thinking":true,"enable_thinking":false}}',
    b'{"model":"Qwen3.8-27B-NVFP4","max_output_tokens":NaN}',
])
def test_gateway_rejects_duplicate_json_members_and_nonfinite_values(body):
    with pytest.raises(ValueError):
        spark.validated_request('POST', '/v1/responses', {}, body)


def test_matching_explicit_false_and_metadata_get_bytes_remain_exact():
    raw = (' {"model":"' + spark.MODEL + '", "chat_template_kwargs": { "enable_thinking" : true }, "stream":true} \n').encode()
    _, outgoing = spark.validated_request('POST', '/v1/responses', {}, raw)
    assert outgoing == raw
    headers, outgoing = spark.validated_request('GET', '/v1/models', {}, b'')
    assert outgoing == b'' and headers == {'Connection': 'close'}


@pytest.mark.parametrize('tamper', ['thinking', 'base', 'context'])
def test_effective_source_identity_binds_policy_without_changing_relay_metadata(tamper):
    value = descriptor()
    legacy_hash = hashlib.sha256(spark._encoded({'profile': value['profile'], 'listener': value['listener']})).hexdigest()
    assert value['descriptor_sha256'] != legacy_hash
    assert value['request_policy']['chat_template_kwargs'] == {'enable_thinking': True}
    assert value['request_policy']['schema'] == 'ai4r-spark-request-policy:3'
    assert value['request_policy']['base_instructions_sha256'] == hashlib.sha256(spark.BASE_INSTRUCTIONS.encode()).hexdigest()
    assert value['request_policy']['configured_context_window'] == 16384
    old_policy = {'schema': 'ai4r-spark-request-policy:1', 'model': spark.MODEL,
        'chat_template_kwargs': {'enable_thinking': False}, 'custom_chat_template': False}
    assert value['descriptor_sha256'] != hashlib.sha256(spark._encoded({
        'profile': value['profile'], 'listener': value['listener'], 'request_policy': old_policy})).hexdigest()
    changed = copy.deepcopy(value)
    if tamper == 'thinking': changed['request_policy']['chat_template_kwargs']['enable_thinking'] = False
    elif tamper == 'base': changed['request_policy']['base_instructions_sha256'] = '0' * 64
    else: changed['request_policy']['configured_context_window'] = 258400
    changed_hash = hashlib.sha256(spark._encoded({k: v for k, v in changed.items() if k != 'descriptor_sha256'})).hexdigest()
    assert changed_hash != value['descriptor_sha256']
    assert set(value['profile']) == spark.PROFILE_FIELDS


def test_gateway_roundtrip_forwards_true_and_preserves_every_other_request_byte_and_stream(monkeypatch):
    value = descriptor()
    raw = json.dumps({'model': spark.MODEL, 'stream': True, 'max_output_tokens': 1024,
        'instructions': 'Public unit-test instructions; no tools.',
        'input': [{'role': 'user', 'content': 'Exact whitespace and unicode: α\nβ'}]}, ensure_ascii=False).encode() + b' \n'
    forwarded = []
    chunks = iter([b'data: {"type":"unit-test-stream"}\n\n', b''])
    response = SimpleNamespace(status=200, getheader=lambda *a: 'text/event-stream', read1=lambda _: next(chunks))
    # Hashable socket sentinel for the handler's bounded owner connection set.
    class Sock:
        def settimeout(self, *args): pass
    upstream_socket = Sock()
    upstream = SimpleNamespace(sock=upstream_socket,
        request=lambda method, path, **kwargs: forwarded.append((method, path, kwargs)),
        getresponse=lambda: response, close=lambda: None)
    monkeypatch.setattr(spark, 'public_descriptor', lambda: value)
    monkeypatch.setattr(spark, 'unix_connection', lambda *a, **k: upstream)
    handler = spark._GatewayHandler.__new__(spark._GatewayHandler)
    handler.connection = SimpleNamespace(settimeout=lambda *a: None)
    handler.headers = Message(); handler.headers['Content-Length'] = str(len(raw))
    handler.rfile = io.BytesIO(raw); handler.wfile = io.BytesIO()
    handler.path = '/v1/responses'
    handler.server = SimpleNamespace(owner=SimpleNamespace(descriptor=value), connections=set(), connections_lock=threading.Lock())
    statuses = []
    handler.send_response = statuses.append
    handler.send_header = lambda *a: None
    handler.end_headers = lambda: None
    handler.send_error = lambda *a: pytest.fail('Valid fixed request should reach controlled upstream')
    handler._proxy('POST')
    assert statuses == [200]
    assert len(forwarded) == 1
    outgoing = forwarded[0][2]['body']
    inserted = b',"chat_template_kwargs":{"enable_thinking":true}'
    assert outgoing.replace(inserted, b'', 1) == raw
    parsed = json.loads(outgoing)
    assert parsed.pop('chat_template_kwargs') == {'enable_thinking': True}
    assert parsed == json.loads(raw)
    assert handler.wfile.getvalue() == b'data: {"type":"unit-test-stream"}\n\n'
    assert handler.close_connection is True
