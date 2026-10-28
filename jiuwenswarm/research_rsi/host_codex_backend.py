"""Finite RSI adapter for the operator's separately authorized native host login.

The reused relay owns durable unknown claims and original backend stdout. This
adapter never opens host credentials or invents HTTP/model/native observations.
"""
import asyncio
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

from jiuwenswarm.research.local_models import LocalModelCatalog, LocalModelClient, canonical, require
from jiuwenswarm.research.private_rpc import PrivateRPCClient
from jiuwenswarm.server.runtime.codex_subscription.governed_trace import GovernedTrace
from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError

MODEL = 'gpt-6.1-sol'
EFFORT = 'medium'
RUN = Path('/run/ai4r-rsi-host-codex')
CATALOG = RUN / 'catalog.json'
SOCKET = RUN / 'model.sock'
SESSION = RUN / 'session.json'
QUALIFICATION = RUN / 'qualification.json'
QUALIFICATION_SOURCE = Path('/var/lib/ai4r-rsi-host-codex-qualification.json')
NATIVE_SHA256 = '2692c8c7bb2cf8b0aefe638741fc90236f4b824c59578ce84994f9de58200993'
ENDPOINT = 'local-host-codex61'
PROTOCOL = 'ai4r-local-model:1'


def validate_host_catalog(value):
    from jiuwenswarm.research.local_models import validate_catalog
    value = validate_catalog(value)
    require(value['backend']['kind'] == 'host-codex-app-server')
    require(value['transport'] == {'socket_path': SOCKET.as_posix(), 'session_file': SESSION.as_posix(),
        'peer_uid': 0, 'socket_mode': 0o660})
    require(len(value['models']) == 1)
    model = value['models'][0]
    require(model['id'] == ENDPOINT and model['model_name'] == MODEL and model['reasoning_effort'] == EFFORT
            and model['revision'] == 'codex-cli-0.163.0-operator-qualified'
            and value['backend']['codex_sha256'] == NATIVE_SHA256
            and model['enabled'] is True and model['timeout_s'] == 120)
    return value


class HostCatalog(LocalModelCatalog):
    def snapshot(self):
        value = validate_host_catalog(super().snapshot())
        qualification(value)
        return value

    def resolve(self, endpoint_id, binding_sha256=None):
        binding = super().resolve(endpoint_id, binding_sha256)
        binding['host_qualification_sha256'] = hashlib.sha256(canonical(qualification(self.snapshot()))).hexdigest()
        return binding


def validate_qualification(value, document):
    from jiuwenswarm.research.local_model_codex import MODEL_CATALOG_SHA256
    fields = {'schema', 'native_version', 'binary_sha256', 'helper_sha256', 'model_catalog_sha256', 'model',
              'reasoning_effort', 'proof_sha256', 'tools_count', 'functions_count', 'additional_tools_count', 'tool_names'}
    require(isinstance(value, dict) and set(value) == fields
        and value['schema'] == 'ai4r-rsi-host-codex-no-tools:1' and value['native_version'] == '0.163.0'
        and value['model'] == MODEL and value['reasoning_effort'] == EFFORT
        and value['binary_sha256'] == document['backend']['codex_sha256'] == NATIVE_SHA256
        and value['model_catalog_sha256'] == MODEL_CATALOG_SHA256
        and value['helper_sha256'] == hashlib.sha256(Path(__file__).parents[1].joinpath('research/local_model_codex.py').read_bytes()).hexdigest()
        and isinstance(value['proof_sha256'], str) and len(value['proof_sha256']) == 64
        and all(char in '0123456789abcdef' for char in value['proof_sha256'])
        and all(type(value[key]) is int and value[key] == 0 for key in ('tools_count', 'functions_count', 'additional_tools_count'))
        and value['tool_names'] == [])
    return value


def qualification(document):
    from jiuwenswarm.research.local_models import protected_json
    return validate_qualification(protected_json(QUALIFICATION, owner_uid=0), document)


def descriptor(binding):
    package = Path(__file__).parents[1]
    paths = ('research/local_model_codex.py', 'research/local_model_relay.py', 'research/local_models.py',
             'research_rsi/host_codex_backend.py', 'research/resources/host_codex/model_catalog.json')
    value = {'schema': 'ai4r-rsi-host-codex-policy:1', 'model': MODEL, 'reasoning_effort': EFFORT,
             'binding_sha256': binding['binding_sha256'],
             'qualification_sha256': binding.get('host_qualification_sha256'),
             'source_sha256': {path: hashlib.sha256((package / path).read_bytes()).hexdigest() for path in paths}}
    return {**value, 'sha256': hashlib.sha256(canonical(value)).hexdigest()}


class _Lifecycle:
    """No persistent native process: the authenticated host relay owns each call."""
    def __init__(self, owner): self.owner, self.root = owner, owner.root
    async def close(self):
        if self.owner.active:
            raise CodexError('CONTAINMENT_UNCERTAIN')


class HostCodexSubscriptionService:
    def __init__(self, root, *, catalog=None, client_factory=None, rpc_factory=None):
        self.root = Path(root).resolve()
        self.catalog = catalog if catalog is not None else HostCatalog(CATALOG, owner_uid=0)
        self.client_factory = client_factory or LocalModelClient
        self.rpc_factory = rpc_factory or PrivateRPCClient
        self.transport = _Lifecycle(self)
        self.epoch = uuid.uuid4().hex
        self.active = {}
        self._writer = self._observer = None
        self.last_host_observation = None
        self.account_fingerprint = None

    def set_governed_trace_writer(self, append_record, put_blob):
        if not callable(append_record) or not callable(put_blob): raise CodexError('AUDIT_UNAVAILABLE')
        self._writer = append_record, put_blob

    def set_account_observer(self, writer):
        if not callable(writer): raise CodexError('AUDIT_UNAVAILABLE')
        self._observer = writer

    async def login(self): raise CodexError('HOST_LOGIN_MANAGED_BY_OPERATOR')
    async def logout(self): raise CodexError('HOST_LOGIN_MANAGED_BY_OPERATOR')
    async def cancel_login(self, *args): raise CodexError('HOST_LOGIN_MANAGED_BY_OPERATOR')

    def binding(self):
        return self.catalog.resolve(ENDPOINT)

    async def relay_status(self):
        binding = self.binding()
        client = self.client_factory(binding)
        session = client.preflight()
        transport = binding['transport']
        rpc = self.rpc_factory(transport['socket_path'], protocol=PROTOCOL,
            peer_uid=transport['peer_uid'], socket_mode=transport['socket_mode'], **session)
        status = await rpc.call('status', {}, timeout_s=10)
        require(isinstance(status, dict) and set(status) == {'schema', 'binding_sha256', 'policy_sha256', 'active', 'unresolved', 'session_id'}
            and status['schema'] == 'ai4r-rsi-host-codex-relay-status:1'
            and status['binding_sha256'] == binding['binding_sha256']
            and status['policy_sha256'] == descriptor(binding)['sha256']
            and status['session_id'] == session['session_id']
            and type(status['active']) is bool and type(status['unresolved']) is bool)
        require(not status['active'] and not status['unresolved'], 'Host native effect remains unavailable or unknown')
        return binding, status

    async def status(self):
        await self.relay_status()
        return {'state': 'ready', 'source': 'host-codex-app-server', 'account_identity': 'rechecked_by_native_helper_per_call'}

    async def invoke_governed_traced(self, scope, prompt, *, model=None, timeout_s=120, system=None):
        if model != MODEL or system is not None:
            raise CodexError('INVALID_INPUT')
        if self._writer is None: raise CodexError('AUDIT_UNAVAILABLE')
        if self.active: raise CodexError('HOST_NATIVE_BUSY')
        binding = self.binding()
        policy = descriptor(binding)
        client = self.client_factory(binding)
        trace = GovernedTrace(scope, *self._writer)
        self.active[scope['call_id']] = True
        failure = None
        result = None
        original_ref = None
        trace_ref = None
        try:
            result = await client.invoke(prompt, timeout_s=timeout_s, call_function='worker')
        except BaseException as error:
            failure = error
        try:
            # RPC envelopes are not native frames. Retain the helper's original
            # bundle separately, then scope only its genuine native stdio bytes.
            responses = [packet for direction, method, packet in client.trace
                         if direction == 'in' and method == 'local-model/result']
            if responses and isinstance(responses[-1].get('response_text'), str):
                original = responses[-1]['response_text']
                # Malformed stdout stays in the private relay receipt store.
                # Only a validated native bundle may enter Core's export closure.
                if result is not None or getattr(failure, 'observation', None) is not None:
                    from jiuwenswarm.research.local_models import native_codex_response
                    try:
                        bundle, observation, _ = native_codex_response(original, binding, prompt=prompt)
                    except Exception:
                        bundle = None
                    if bundle is not None:
                        raw_ref = self._writer[1](original.encode('utf-8'))
                        original_ref = self._writer[0]('host-codex-native-original', {'schema': 'ai4r-host-codex-original:1',
                            'scope': copy.deepcopy(scope), 'policy_sha256': policy['sha256'], 'raw_ref': raw_ref})
                    methods = {};server_methods = {}
                    for frame in bundle['wire_frames'] if bundle is not None else []:
                        raw = frame['raw'].encode('utf-8')
                        envelope = json.loads(raw)
                        if frame['direction'] == 'out':
                            if 'method' in envelope:
                                method = envelope['method']; methods[envelope['id']] = method
                            else:
                                # Already validated closed tool/approval refusal,
                                # never a request or permission to execute a tool.
                                method = server_methods[envelope['id']]
                            trace.request_observer(method)('out', raw, envelope)
                        elif 'id' in envelope and envelope['id'] in methods and 'method' not in envelope:
                            trace.request_observer(methods[envelope['id']])('in', raw, envelope)
                        else:
                            if 'id' in envelope and 'method' in envelope:
                                server_methods[envelope['id']]=envelope['method']
                            trace.notification('in', raw, envelope)
            trace_ref = trace.finish('completed' if result is not None else 'failed')
            if failure is not None:
                failure.native_trace_ref = trace_ref
                failure.host_native_original_ref = original_ref
                raise failure
            result['native_trace_ref'] = trace_ref
            result['host_native_original_ref'] = original_ref
            observed = {'schema': 'ai4r-rsi-host-codex-observation:1',
                'observed_at': datetime.now(timezone.utc).isoformat(), 'policy_sha256': policy['sha256'],
                'model': result['identity']['effective'], 'reasoning_effort': EFFORT,
                'native_trace_ref': trace_ref, 'provider_request_id': result['provider_request_id']}
            if self._observer is not None: self._observer('host-codex-runtime-observation', observed)
            self.last_host_observation = observed
            self.account_fingerprint = 'host-codex-source:' + policy['sha256']
            return result
        except BaseException as error:
            if error is failure:
                raise
            # A post-dispatch observer failure never becomes a known failed
            # inference. Preserve any already committed original receipt link.
            from jiuwenswarm.research.providers import ProviderError
            observation = ({key: result[key] for key in ('identity', 'usage', 'provider_request_id', 'observed_runtime')}
                if result is not None else getattr(failure, 'observation', None))
            audit_error = ProviderError('AUDIT_UNAVAILABLE', outcome_unknown=True,
                observation=observation)
            audit_error.host_native_original_ref = original_ref
            if trace_ref is not None: audit_error.native_trace_ref = trace_ref
            raise audit_error from None
        finally:
            self.active.pop(scope['call_id'], None)

    async def readiness_proof(self, *, store, deployment_ref, maximum_age_s=300):
        from jiuwenswarm.research.fixed_subscription import deployment_backend, deployment_model
        deployment = store.read_record(deployment_ref)
        require(deployment_backend(deployment) == 'host-codex-app-server' and deployment_model(deployment) == MODEL)
        binding, _ = await self.relay_status()
        policy = descriptor(binding)
        matches = [row for row in store.iter_records(kinds=('host-codex-runtime-observation',))
                   if row['record'].get('policy_sha256') == policy['sha256']]
        require(bool(matches), 'No actual host native observation is available')
        row = matches[-1]; value = row['record']
        require(set(value) == {'schema', 'observed_at', 'policy_sha256', 'model', 'reasoning_effort', 'native_trace_ref', 'provider_request_id'}
            and value['schema'] == 'ai4r-rsi-host-codex-observation:1' and value['model'] == MODEL
            and value['reasoning_effort'] == EFFORT)
        when = datetime.fromisoformat(value['observed_at'].replace('Z', '+00:00'))
        require(when.tzinfo is not None and 0 <= (datetime.now(timezone.utc)-when).total_seconds() <= maximum_age_s)
        store.read_blob(row['ref']); store.read_blob(value['native_trace_ref'])
        return [deployment_ref, row['ref'], value['native_trace_ref']]
