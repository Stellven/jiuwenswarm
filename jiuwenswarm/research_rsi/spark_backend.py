"""Fixed Spark engine behind the existing audited native Codex turn owner.

The root operator publishes a protected Unix relay descriptor. This module has
no selectable destination, headers, API keys, direct generation SDK, or model
router. A private network namespace exposes only its own loopback gateway.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
import stat
import struct
import threading
import time

from jiuwenswarm.research.fixed_subscription import SPARK_REQUESTED_MODEL, deployment_model
from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService, governed_tool_config
from jiuwenswarm.server.runtime.codex_subscription.transport import AppServerTransport, CodexError

MODEL = SPARK_REQUESTED_MODEL
RUN = Path('/run/ai4r-rsi-spark')
SOCKET = RUN / 'model.sock'
PUBLIC_PROFILE = RUN / 'profile.json'
ATTESTATION = RUN / 'listener.json'
BASE_URL = 'http://127.0.0.1:5175/v1'
MAX_BYTES = 16 * 1024 * 1024
MAX_SECONDS = 120
MAX_CONNECTIONS = 2
PROFILE_FIELDS = frozenset(('schema', 'model', 'remote', 'socket', 'protocol', 'profile', 'source_epoch', 'boot_id'))
CONFIGURED_CONTEXT_WINDOW = 16384
ENABLE_THINKING = True
BASE_INSTRUCTIONS = ('You are a bounded text inference worker for a governed research call. Tools, commands, file access, '
                     'network access, delegated agents, and external actions are unavailable. Follow the supplied developer '
                     'instructions and user input. Complete the requested task in this turn and return only the final '
                     'requested answer. Do not send progress updates, preambles, plans to act later, or claims of actions '
                     'you have not performed.')


def request_policy():
    """Source-pinned client policy, separate from the unchanged host relay."""
    return {'schema': 'ai4r-spark-request-policy:3', 'model': MODEL,
            'chat_template_kwargs': {'enable_thinking': ENABLE_THINKING}, 'custom_chat_template': False,
            'base_instructions_sha256': hashlib.sha256(BASE_INSTRUCTIONS.encode()).hexdigest(),
            'configured_context_window': CONFIGURED_CONTEXT_WINDOW}


def effective_descriptor(profile, listener):
    value = {'profile': profile, 'listener': listener, 'request_policy': request_policy()}
    return {**value, 'descriptor_sha256': hashlib.sha256(_encoded(value)).hexdigest()}


def _need(value):
    if not value:
        raise ValueError('Protected fixed Spark runtime is unavailable')


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _protected(path, kind, mode):
    path = Path(path)
    _need(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)))
    for ancestor in path.parents:
        meta = ancestor.stat()
        _need(stat.S_ISDIR(meta.st_mode) and meta.st_uid == 0 and not meta.st_mode & 0o022)
    meta = path.lstat()
    _need(kind(meta.st_mode) and (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) == (0, 13000, mode))
    return meta


def _json_file(path):
    _protected(path, stat.S_ISREG, 0o640)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        meta = os.fstat(fd)
        _need(meta.st_uid == 0 and meta.st_gid == 13000 and stat.S_IMODE(meta.st_mode) == 0o640
              and stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1 and 0 < meta.st_size <= 65536)
        raw = os.read(fd, 65537)
        _need(len(raw) <= 65536)
    finally:
        os.close(fd)
    def pairs(items):
        result = {}
        for key, value in items:
            _need(key not in result)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def public_descriptor():
    _need(os.geteuid() in (0, 12001) and (os.geteuid() == 0 or 13000 in {os.getegid(), *os.getgroups()}))
    _protected(RUN, stat.S_ISDIR, 0o710)
    profile = _json_file(PUBLIC_PROFILE)
    _need(isinstance(profile, dict) and set(profile) == PROFILE_FIELDS)
    _need(profile['schema'] == 'ai4r-rsi-spark:1' and profile['model'] == MODEL
          and profile['remote'] == '127.0.0.1:8000' and profile['socket'] == str(SOCKET)
          and profile['protocol'] == 'openai' and profile['profile'] == '/var/lib/ai4r-rsi-spark/profile.json'
          and isinstance(profile['source_epoch'], str) and re.fullmatch('[0-9a-f]{32}', profile['source_epoch'])
          and profile['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    listener = _json_file(ATTESTATION)
    _need(isinstance(listener, dict) and set(listener) == PROFILE_FIELDS | {'pid', 'start_ticks', 'socket_inode'}
          and all(listener[key] == profile[key] for key in PROFILE_FIELDS)
          and type(listener['pid']) is int and listener['pid'] > 0
          and isinstance(listener['start_ticks'], str) and listener['start_ticks'].isdigit()
          and type(listener['socket_inode']) is int and listener['socket_inode'] > 0)
    meta = _protected(SOCKET, stat.S_ISSOCK, 0o660)
    _need(meta.st_ino == listener['socket_inode'])
    return effective_descriptor(profile, listener)


def unix_connection(descriptor, *, timeout=15):
    # Recheck inode/custody before connecting; cross-PID namespaces may report
    # peer pid 0. The protected root attestation and UID are the authority here.
    _need(public_descriptor() == descriptor)
    connection = http.client.HTTPConnection('localhost', timeout=timeout)
    connection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.sock.settimeout(timeout)
    try:
        connection.sock.connect(str(SOCKET))
        _, uid, _ = struct.unpack('3i', connection.sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        _need(uid == 0 and _protected(SOCKET, stat.S_ISSOCK, 0o660).st_ino == descriptor['listener']['socket_inode'])
        return connection
    except BaseException:
        connection.close()
        raise


def metadata(descriptor):
    for path in ('/health', '/v1/models'):
        connection = unix_connection(descriptor)
        try:
            connection.request('GET', path, headers={'Connection': 'close'})
            response = connection.getresponse()
            raw = response.read(65537)
            _need(response.status == 200 and len(raw) <= 65536)
            if path == '/v1/models':
                value = json.loads(raw)
                _need(isinstance(value, dict) and isinstance(value.get('data'), list) and len(value['data']) == 1
                      and isinstance(value['data'][0], dict) and value['data'][0].get('id') == MODEL)
        finally:
            connection.close()
    _need(descriptor.get('request_policy') == request_policy())
    return {'model': MODEL, 'descriptor_sha256': descriptor['descriptor_sha256'],
            'request_policy_sha256': hashlib.sha256(_encoded(request_policy())).hexdigest(),
            'source_epoch': descriptor['profile']['source_epoch'], 'boot_id': descriptor['profile']['boot_id']}


def provider_configuration():
    return {'model_context_window': CONFIGURED_CONTEXT_WINDOW,
            'model_providers.ai4r_spark.name': 'AI4Research isolated Spark',
            'model_providers.ai4r_spark.base_url': BASE_URL,
            'model_providers.ai4r_spark.wire_api': 'responses',
            'model_providers.ai4r_spark.requires_openai_auth': False,
            'model_providers.ai4r_spark.supports_websockets': False,
            'model_providers.ai4r_spark.request_max_retries': 0,
            'model_providers.ai4r_spark.stream_max_retries': 0,
            # Measured against packaged 0.163.0. Startup's older [tools]
            # view_image setting does not suppress current native builtins.
            # Keep the model-visible declaration empty as well as rejecting
            # all runtime tool requests and nonempty gateway tool payloads.
            **governed_tool_config()}


def _isolated_network():
    _need({name for _, name in socket.if_nameindex()} == {'lo'})


def validated_request(method, path, headers, body):
    """Closed gateway input: no credentials, redirects, endpoints or tools."""
    forbidden = {'authorization', 'proxy-authorization', 'cookie', 'x-api-key', 'api-key', 'x-openai-api-key'}
    names = {key.lower() for key in headers}
    _need(not any(key in forbidden or key.startswith('openai-') for key in names))
    _need('transfer-encoding' not in names and len(body) <= MAX_BYTES)
    if method == 'GET':
        _need(path in {'/health', '/v1/models', '/version'} and not body)
    else:
        _need(method == 'POST' and path in {'/v1/responses', '/v1/chat/completions'} and body)
        def pairs(items):
            result = {}
            for key, item in items:
                _need(key not in result)
                result[key] = item
            return result
        value = json.loads(body, object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite Spark request')))
        _need(isinstance(value, dict) and value.get('model') == MODEL
              and value.get('tools', []) == [] and value.get('functions', []) == [])
        _need(not any(key in value for key in ('previous_response_id', 'conversation', 'web_search_options')))
        _need(not any(key in value for key in ('chat_template', 'enable_thinking')))
        policy = request_policy()['chat_template_kwargs']
        if 'chat_template_kwargs' in value:
            supplied = value['chat_template_kwargs']
            _need(isinstance(supplied, dict) and set(supplied) == {'enable_thinking'}
                  and supplied['enable_thinking'] is policy['enable_thinking'])
        else:
            # Append the one host-owned member without reserializing any existing
            # request byte, prompt string, sampling field, stream or token cap.
            closing = len(body.rstrip()) - 1
            _need(closing >= 0 and body[closing:closing + 1] == b'}')
            member = b',"chat_template_kwargs":' + _encoded(policy)
            body = body[:closing] + member + body[closing:]
        _need(len(body) <= MAX_BYTES)
    return ({'Connection': 'close', **({'Content-Type': 'application/json', 'Accept': 'text/event-stream'} if method == 'POST' else {})}, body)


class _GatewayServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = MAX_CONNECTIONS
    allow_reuse_address = False

    def __init__(self, owner):
        self.owner = owner
        self.slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
        self.connections = set()
        self.connections_lock = threading.Lock()
        super().__init__(('127.0.0.1', 5175), _GatewayHandler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        with self.connections_lock:
            self.connections.add(request)
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self.connections_lock:
                self.connections.discard(request)
            self.slots.release()

    def handle_error(self, request, client_address):
        pass  # Never log prompts, responses, request headers or private errors.

    def close_connections(self):
        with self.connections_lock:
            for connection in tuple(self.connections):
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass


class _GatewayHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def log_message(self, *args):
        pass

    def do_GET(self):
        self._proxy('GET')

    def do_POST(self):
        self._proxy('POST')

    def _proxy(self, method):
        upstream = None
        upstream_socket = None
        sent = False
        deadline = time.monotonic() + MAX_SECONDS
        self.connection.settimeout(MAX_SECONDS)
        try:
            sizes = self.headers.get_all('Content-Length', [])
            _need(len(sizes) <= 1)
            size = int(sizes[0]) if sizes else 0
            _need(0 <= size <= MAX_BYTES and (method == 'GET' or size > 0))
            body = self.rfile.read(size)
            _need(len(body) == size)
            headers, body = validated_request(method, self.path, self.headers, body)
            _need(time.monotonic() < deadline)
            owner = self.server.owner
            _need(public_descriptor() == owner.descriptor)
            upstream = unix_connection(owner.descriptor, timeout=max(.1, deadline - time.monotonic()))
            upstream_socket = upstream.sock
            with self.server.connections_lock:
                self.server.connections.add(upstream_socket)
            upstream.request(method, self.path, body=body or None, headers=headers)
            response = upstream.getresponse()
            _need(100 <= response.status <= 599 and not 300 <= response.status < 400)
            content_type = response.getheader('Content-Type', 'application/json').split(';')[0].lower()
            _need(content_type in {'application/json', 'text/event-stream', 'text/plain'})
            self.send_response(response.status)
            self.send_header('Content-Type', content_type)
            self.send_header('Connection', 'close')
            self.end_headers()
            sent = True
            total = len(body)
            while True:
                _need(time.monotonic() < deadline)
                if upstream.sock is not None:
                    upstream.sock.settimeout(max(.1, deadline - time.monotonic()))
                chunk = response.read1(min(65536, MAX_BYTES - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                _need(total <= MAX_BYTES)
                self.wfile.write(chunk)
                self.wfile.flush()
        except (ValueError, TypeError, KeyError, OSError, http.client.HTTPException):
            if not sent:
                self.send_error(502, 'Fixed local model bridge unavailable')
        finally:
            if upstream is not None:
                upstream.close()
            if upstream_socket is not None:
                with self.server.connections_lock:
                    self.server.connections.discard(upstream_socket)
            self.close_connection = True


class SparkGateway:
    def __init__(self):
        self.descriptor = None
        self.server = None
        self.thread = None
        self._lock = threading.Lock()

    def start(self, descriptor):
        with self._lock:
            _isolated_network()
            if self.server is not None:
                _need(self.descriptor == descriptor and self.thread.is_alive())
                return
            self.descriptor = descriptor
            self.server = _GatewayServer(self)
            self.thread = threading.Thread(target=self.server.serve_forever, name='ai4r-spark-loopback', daemon=True)
            self.thread.start()

    def check(self, descriptor):
        _isolated_network()
        _need(self.descriptor == descriptor and self.server is not None and self.thread is not None
              and self.thread.is_alive() and self.server.socket.getsockname() == ('127.0.0.1', 5175))

    def close(self):
        with self._lock:
            if self.server is not None:
                self.server.shutdown()
                self.server.close_connections()
                self.server.server_close()
                self.thread.join(timeout=3)
            self.server = self.thread = self.descriptor = None


class SparkTransport(AppServerTransport):
    def __init__(self, root, *, gateway):
        super().__init__(root)
        self.gateway = gateway

    def _no_credentials(self):
        _need(not os.path.lexists(self.home / 'auth.json') and not os.path.lexists(self.root / 'auth.json'))

    async def start(self):
        self._no_credentials()
        await super().start()

    async def request(self, method, params=None, *, wire_observer=None):
        if method.startswith(('account/', 'login/', 'auth/')):
            raise CodexError('LOCAL_PROVIDER_HAS_NO_ACCOUNT_LOGIN')
        if method not in {'initialize', 'thread/start', 'turn/start', 'turn/interrupt', 'thread/archive'}:
            raise CodexError('LOCAL_PROVIDER_NATIVE_METHOD_UNAVAILABLE')
        if method == 'thread/start':
            self._no_credentials()
            _need(isinstance(params, dict) and params.get('modelProvider') == 'ai4r_governed'
                  and params.get('model') == MODEL and params.get('sandbox') == 'read-only'
                  and params.get('approvalPolicy') == 'never' and params.get('ephemeral') is True)
            expected = {**governed_tool_config(), 'model_providers.ai4r_governed.name': 'AI4Research governed subscription',
                'model_providers.ai4r_governed.wire_api': 'responses',
                'model_providers.ai4r_governed.requires_openai_auth': True,
                'model_providers.ai4r_governed.request_max_retries': 0,
                'model_providers.ai4r_governed.stream_max_retries': 0}
            _need(params.get('config') == expected)
            _need(not any(key in params for key in ('baseInstructions', 'dynamicTools', 'tools', 'mcpServers', 'env', 'headers')))
            params = dict(params, modelProvider='ai4r_spark', config=provider_configuration(),
                          baseInstructions=BASE_INSTRUCTIONS, allowProviderModelFallback=False)
        elif method == 'turn/start':
            _need(isinstance(params, dict) and params.get('model') == MODEL and params.get('approvalPolicy') == 'never')
        return await super().request(method, params, wire_observer=wire_observer)

    async def close(self):
        try:
            await super().close()
        finally:
            self.gateway.close()


class SparkSubscriptionService(SubscriptionService):
    """Existing governed turn/trace lifecycle with a genuine local source ID."""
    def __init__(self, root):
        gateway = SparkGateway()
        super().__init__(Path(root), transport=SparkTransport(Path(root), gateway=gateway))
        self.gateway = gateway
        self._spark_writer = None
        self._spark_descriptor = None
        self.last_spark_observation = None
        self.account_observation_state = {'status': 'unavailable', 'reason': 'local_provider_has_no_subscription_limits'}

    def set_account_observer(self, writer):
        _need(callable(writer))
        self._spark_writer = writer

    async def _status(self):
        descriptor = await asyncio.to_thread(public_descriptor)
        _need(self._spark_descriptor in (None, descriptor))
        observed = await asyncio.to_thread(metadata, descriptor)
        _isolated_network()
        try:
            await self.transport.start()
            self.gateway.start(descriptor)
        except BaseException:
            await self.transport.close()
            raise
        self._spark_descriptor = descriptor
        # This is explicitly a local public source fingerprint, never ChatGPT
        # account verification, entitlement or subscription telemetry.
        self.account_fingerprint = 'spark-source:' + descriptor['descriptor_sha256']
        self._observation_identity_verified = False
        if self._spark_writer is not None:
            value = {'schema': 'ai4r-rsi-spark-runtime-observation:2', **observed,
                     'epoch': self.epoch, 'source_fingerprint': self.account_fingerprint,
                     'profile_id': hashlib.sha256(str(self.root).encode()).hexdigest(),
                     'observed_at': datetime.now(timezone.utc).isoformat()}
            self._spark_writer('spark-runtime-observation', value)
            self.last_spark_observation = value
        return {'enabled': True, 'state': 'ready', 'provider': 'local-spark', 'model': MODEL,
                'plan': None, 'active_runs': len(self.active), 'error': None}

    async def models(self):
        async with self._account_lock:
            await self._status()
            return {'models': [{'id': MODEL, 'name': MODEL, 'default': True}]}

    async def login(self):
        raise CodexError('LOCAL_PROVIDER_HAS_NO_ACCOUNT_LOGIN')

    async def cancel_login(self, attempt_id):
        raise CodexError('LOCAL_PROVIDER_HAS_NO_ACCOUNT_LOGIN')

    async def logout(self):
        raise CodexError('LOCAL_PROVIDER_HAS_NO_ACCOUNT_LOGIN')

    def readiness_proof(self, *, store, deployment_ref, maximum_age_s=300):
        """Only existing owner + current metadata; never start, dispatch or write."""
        _need(deployment_model(store.read_record(deployment_ref)) == MODEL)
        descriptor = public_descriptor()
        _need(self._spark_descriptor == descriptor and not self.active and self.login_id is None)
        self.gateway.check(descriptor)
        process = self.transport.process
        _need(process is not None and process.returncode is None and type(process.pid) is int and process.pid > 0
              and self.transport._reader is not None and not self.transport._reader.done())
        os.kill(process.pid, 0)
        actual = metadata(descriptor)
        value = self.last_spark_observation
        fields = {'schema', 'model', 'descriptor_sha256', 'request_policy_sha256', 'source_epoch', 'boot_id', 'epoch',
                  'source_fingerprint', 'profile_id', 'observed_at'}
        _need(isinstance(value, dict) and set(value) == fields
              and value.get('schema') == 'ai4r-rsi-spark-runtime-observation:2'
              and all(value.get(key) == item for key, item in actual.items())
              and value.get('epoch') == self.epoch and value.get('source_fingerprint') == self.account_fingerprint
              and self.account_fingerprint == 'spark-source:' + descriptor['descriptor_sha256']
              and value.get('profile_id') == hashlib.sha256(str(self.root).encode()).hexdigest())
        observed = datetime.fromisoformat(value['observed_at'])
        _need(observed.tzinfo is not None and 0 <= (datetime.now(timezone.utc) - observed).total_seconds() <= maximum_age_s)
        matches = [row for row in store.iter_records(kinds=('spark-runtime-observation',)) if row['record'] == value]
        _need(len(matches) == 1 and store.record_kind(matches[0]['ref']) == 'spark-runtime-observation')
        store.read_blob(matches[0]['ref'])
        return [deployment_ref, matches[0]['ref']]


def subscription_for_deployment(root, deployment):
    requested = deployment_model(deployment)
    from jiuwenswarm.research.fixed_subscription import deployment_backend, HOST_CODEX_BACKEND
    if deployment_backend(deployment) == HOST_CODEX_BACKEND:
        from .host_codex_backend import HostCodexSubscriptionService
        return HostCodexSubscriptionService(root)
    return SparkSubscriptionService(root) if requested == MODEL else SubscriptionService(Path(root))
