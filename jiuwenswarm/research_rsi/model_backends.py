"""Explicitly pinned model backends for the capsule improvement loop.

A backend only manufactures *handles*: once-only async callables
``prompt -> text`` exposing the same evidence attributes as the frozen
``DevelopmentModel`` (``used``, ``last_evidence``, ``last_model_calls``,
``last_generating_model``, ``last_unavailable_reasons``). Every handle is
wrapped by ``BoundedDiagnosis`` / ``GuardedProposer`` in the loop, so capture,
size bounds, timeouts and no-retry semantics are identical for every backend.

The backend is always named by configuration. Nothing here inspects the
environment, the network or installed credentials to pick one, and a missing
or unknown backend is a validation error, never a silent default/substitute.
"""
from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

BACKEND_KINDS = ('host-codex', 'fake', 'openai-compatible', 'anthropic')
CALL_START_SCHEMA = 'ai4r-rsi-model-backend-call-start:1'
CALL_SCHEMA = 'ai4r-rsi-model-backend-call:1'
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
ANTHROPIC_VERSION = '2023-06-01'
_ENV = re.compile('[A-Z_][A-Z0-9_]{0,127}')
_MODEL = re.compile('[A-Za-z0-9][A-Za-z0-9_.:/@+-]{0,199}')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def _source_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _module_constant(path, name):
    """Read a literal module constant without importing (and initializing) it."""
    tree = ast.parse(Path(path).read_bytes())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('PINNED_BACKEND_CONSTANT_UNAVAILABLE')


def validate_backend_configuration(value):
    """Closed per-kind configuration. A run that names no backend is refused."""
    need(isinstance(value, dict) and value.get('kind') in BACKEND_KINDS, 'EXPLICIT_MODEL_BACKEND_REQUIRED')
    kind = value['kind']
    allowed = {'host-codex': ({'kind'}, set()),
               'fake': ({'kind'}, {'model'}),
               'openai-compatible': ({'kind', 'base_url', 'model', 'api_key_env'}, {'max_tokens'}),
               'anthropic': ({'kind', 'model', 'api_key_env'}, {'base_url', 'max_tokens'})}[kind]
    need(allowed[0] <= set(value) <= allowed[0] | allowed[1], 'CLOSED_MODEL_BACKEND_CONFIGURATION_REQUIRED')
    if 'model' in value:
        need(isinstance(value['model'], str) and _MODEL.fullmatch(value['model']), 'EXACT_BACKEND_MODEL_REQUIRED')
    if 'api_key_env' in value:
        need(isinstance(value['api_key_env'], str) and _ENV.fullmatch(value['api_key_env']), 'BACKEND_KEY_ENV_NAME_REQUIRED')
    if 'base_url' in value:
        url = value['base_url']
        need(isinstance(url, str) and len(url) <= 512 and re.fullmatch(r'https?://[^\s/?#]+(/[^\s?#]*)?', url)
             and not url.endswith('/'), 'EXACT_BACKEND_BASE_URL_REQUIRED')
    if 'max_tokens' in value:
        need(type(value['max_tokens']) is int and 0 < value['max_tokens'] <= 128000, 'FINITE_BACKEND_MAX_TOKENS_REQUIRED')
    return value


class BackendExhausted(Exception):
    """No further governed handle may be issued (budget, not an error)."""


class ModelBackend:
    kind = None
    model = None

    def bind(self, *, runtime, session):
        self.runtime, self.session = runtime, session
        return self

    @property
    def store(self):
        return self.runtime.store

    def pinned_sha256(self):
        return _source_sha256(__file__)

    def describe(self):
        return {'kind': self.kind, 'model': self.model, 'pinned_sha256': self.pinned_sha256()}

    def capacity(self):
        """Maximum number of iterations this backend can serve, or None."""
        return None

    def handles(self, iteration):
        raise NotImplementedError


class HostCodexBackend(ModelBackend):
    """Production default: the frozen ``DevelopmentModel`` over the host relay.

    Each iteration uses its own Root-prepared, unissued diagnosis/proposal work
    contracts (a contract attempt is consumed by its single call). Iteration 1
    uses exactly the session's historical pair, so a v1 session behaves as
    before. Running out of prepared contracts is a budget stop.
    """
    kind = 'host-codex'

    def __init__(self, factory=None):
        self.factory = factory
        path = Path(__file__).with_name('host_codex_backend.py')
        self.model = _module_constant(path, 'MODEL')
        self._sha256 = _source_sha256(path)

    def pinned_sha256(self):
        return self._sha256

    def contracts(self):
        from .capsule_loop import iteration_contracts
        return iteration_contracts(self.session)

    def capacity(self):
        return len(self.contracts())

    def handles(self, iteration):
        pairs = self.contracts()
        if iteration > len(pairs):
            raise BackendExhausted('NO_PREPARED_WORK_CONTRACTS_FOR_ITERATION')
        factory = self.factory or getattr(self.runtime, 'development_model_factory', None)
        if factory is None:
            # Imported here to leave the ordinary library controller provider-free.
            from deploy.m1.rsi_development_run import DevelopmentModel
            factory = DevelopmentModel
        pair = pairs[iteration - 1]
        return tuple(factory(self.runtime.resources, self.runtime.lease, pair[key], self.session['id'])
                     for key in ('diagnosis_contract_ref', 'proposal_contract_ref'))


class _Handle:
    """Common once-only handle bookkeeping."""
    def __init__(self):
        self.used = False
        self.last_evidence = []
        self.last_model_calls = None
        self.last_generating_model = None
        self.last_unavailable_reasons = []

    def _claim(self):
        need(not self.used, 'MODEL_HANDLE_ALREADY_USED_NO_REPLAY')
        self.used = True


class _ScriptedHandle(_Handle):
    def __init__(self, backend, iteration, role):
        super().__init__()
        self.backend, self.iteration, self.role = backend, iteration, role

    async def __call__(self, prompt):
        self._claim()
        self.backend.prompts.append((self.iteration, self.role, prompt))
        item = self.backend._next()
        self.last_model_calls = 1
        self.last_generating_model = 'fake:' + self.backend.model
        self.last_evidence = [self.backend.store.put({'schema': 'ai4r-rsi-fake-model-call:1',
            'iteration': self.iteration, 'role': self.role,
            'prompt_sha256': hashlib.sha256(prompt.encode('utf8')).hexdigest()})]
        if isinstance(item, BaseException):
            raise item
        if callable(item):
            item = item(prompt)
            if asyncio.iscoroutine(item):
                item = await item
        return item


class FakeBackend(ModelBackend):
    """Deterministic scripted responses for tests; drives the real loop code.

    ``scripted_responses`` is consumed in call order (diagnosis, proposal,
    diagnosis, ...). Each item is response text, a callable ``prompt -> text``
    or an exception instance to raise after the (counted) call. Exhausting the
    script is an error: no response is ever invented.
    """
    kind = 'fake'

    def __init__(self, scripted_responses, *, model='scripted'):
        self.script = list(scripted_responses)
        self.model = model
        self.prompts = []
        self.cursor = 0

    def _next(self):
        need(self.cursor < len(self.script), 'FAKE_BACKEND_SCRIPT_EXHAUSTED')
        item = self.script[self.cursor]
        self.cursor += 1
        return item

    def handles(self, iteration):
        return _ScriptedHandle(self, iteration, 'diagnosis'), _ScriptedHandle(self, iteration, 'proposal')


class ExplicitHandles(ModelBackend):
    """Legacy unit-test seam: an explicit flat list of once-only handles."""

    def __init__(self, handles, kind):
        handles = list(handles)
        need(len(handles) >= 2 and len(handles) % 2 == 0 and len({id(h) for h in handles}) == len(handles),
             'TWO_SEPARATE_ONCE_ONLY_HANDLES_REQUIRED')
        self.items, self.kind, self.model = handles, kind, 'explicit-test-handles'

    def capacity(self):
        return len(self.items) // 2

    def handles(self, iteration):
        if iteration > self.capacity():
            raise BackendExhausted('NO_EXPLICIT_HANDLES_FOR_ITERATION')
        return tuple(self.items[2 * (iteration - 1):2 * iteration])


def urllib_transport(url, headers, body, timeout):
    request = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        return error.code, error.read(MAX_RESPONSE_BYTES + 1)


class _HTTPHandle(_Handle):
    def __init__(self, backend, iteration, role):
        super().__init__()
        self.backend, self.iteration, self.role = backend, iteration, role

    async def __call__(self, prompt):
        self._claim()
        backend, store = self.backend, self.backend.store
        key = os.environ.get(backend.api_key_env)
        if not key:
            # Refused before any effect: zero calls is an observed fact here.
            self.last_model_calls = 0
            raise ValueError('MODEL_BACKEND_KEY_UNAVAILABLE_NO_CALL')
        url, headers, body = backend.request(prompt, key)
        start = {'schema': CALL_START_SCHEMA, 'kind': backend.kind, 'model': backend.model,
                 'url': url, 'iteration': self.iteration, 'role': self.role,
                 'prompt_sha256': hashlib.sha256(prompt.encode('utf8')).hexdigest(),
                 'request_sha256': hashlib.sha256(body).hexdigest()}
        self.last_evidence = [store.put(start)]
        # From here on the effect may have happened: it is counted and never retried.
        self.last_model_calls = 1
        call = {'schema': CALL_SCHEMA, 'start_ref': self.last_evidence[0], 'outcome': 'unknown',
                'http_status': None, 'response_ref': None, 'effective_model': None, 'usage': None}
        try:
            status, raw = await asyncio.to_thread(backend.transport, url, headers, body, backend.timeout_s)
            call['http_status'] = status
            call['response_ref'] = store.put_bytes(raw[:MAX_RESPONSE_BYTES])
            need(len(raw) <= MAX_RESPONSE_BYTES, 'MODEL_BACKEND_RESPONSE_EXCEEDS_BOUND')
            need(status == 200, 'MODEL_BACKEND_HTTP_STATUS_' + str(status))
            text, effective, usage = backend.parse(json.loads(raw))
            call.update(outcome='completed', effective_model=effective, usage=usage)
            self.last_generating_model = effective
            if not isinstance(usage, dict):
                self.last_unavailable_reasons.append('Model usage is unavailable; inspect backend call evidence.')
            return text
        except BaseException:
            if call['outcome'] == 'unknown' and call['http_status'] is not None:
                call['outcome'] = 'failed'
            raise
        finally:
            self.last_evidence.append(store.put(call))


class _HTTPBackend(ModelBackend):
    timeout_s = 300

    def __init__(self, *, model, api_key_env, base_url, max_tokens=16000, transport=None):
        validate_backend_configuration({'kind': self.kind, 'model': model, 'api_key_env': api_key_env,
                                        'base_url': base_url, 'max_tokens': max_tokens})
        self.model, self.api_key_env, self.base_url = model, api_key_env, base_url
        self.max_tokens = max_tokens
        self.transport = transport or urllib_transport

    def handles(self, iteration):
        return _HTTPHandle(self, iteration, 'diagnosis'), _HTTPHandle(self, iteration, 'proposal')


class OpenAICompatibleBackend(_HTTPBackend):
    """``POST {base_url}/chat/completions`` with a bearer key from ``api_key_env``."""
    kind = 'openai-compatible'

    def __init__(self, base_url, model, api_key_env, *, max_tokens=16000, transport=None):
        super().__init__(model=model, api_key_env=api_key_env, base_url=base_url,
                         max_tokens=max_tokens, transport=transport)

    def request(self, prompt, key):
        body = json.dumps({'model': self.model, 'max_tokens': self.max_tokens,
                           'messages': [{'role': 'user', 'content': prompt}]}).encode('utf8')
        return (self.base_url + '/chat/completions',
                {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key}, body)

    @staticmethod
    def parse(value):
        need(isinstance(value, dict) and isinstance(value.get('choices'), list) and len(value['choices']) == 1,
             'MODEL_BACKEND_SINGLE_CHOICE_REQUIRED')
        text = value['choices'][0].get('message', {}).get('content')
        need(isinstance(text, str), 'MODEL_BACKEND_TEXT_UNAVAILABLE')
        usage = value.get('usage')
        effective = value.get('model') if isinstance(value.get('model'), str) else None
        return text, effective, ({'input_tokens': usage.get('prompt_tokens'), 'output_tokens': usage.get('completion_tokens')}
                                 if isinstance(usage, dict) else None)


class AnthropicBackend(_HTTPBackend):
    """``POST {base_url}/v1/messages`` with ``x-api-key`` from ``api_key_env``."""
    kind = 'anthropic'

    def __init__(self, model, api_key_env, *, base_url='https://api.anthropic.com', max_tokens=16000, transport=None):
        super().__init__(model=model, api_key_env=api_key_env, base_url=base_url,
                         max_tokens=max_tokens, transport=transport)

    def request(self, prompt, key):
        body = json.dumps({'model': self.model, 'max_tokens': self.max_tokens,
                           'messages': [{'role': 'user', 'content': prompt}]}).encode('utf8')
        return (self.base_url + '/v1/messages',
                {'Content-Type': 'application/json', 'x-api-key': key, 'anthropic-version': ANTHROPIC_VERSION}, body)

    @staticmethod
    def parse(value):
        need(isinstance(value, dict) and isinstance(value.get('content'), list), 'MODEL_BACKEND_CONTENT_REQUIRED')
        texts = [row.get('text') for row in value['content'] if isinstance(row, dict) and row.get('type') == 'text']
        need(len(texts) == 1 and isinstance(texts[0], str), 'MODEL_BACKEND_SINGLE_TEXT_BLOCK_REQUIRED')
        usage = value.get('usage')
        effective = value.get('model') if isinstance(value.get('model'), str) else None
        return texts[0], effective, ({'input_tokens': usage.get('input_tokens'), 'output_tokens': usage.get('output_tokens')}
                                     if isinstance(usage, dict) else None)


def backend_from_configuration(configuration, *, transport=None):
    """Construct exactly the configured backend; never autodetected."""
    value = validate_backend_configuration(configuration)
    kind = value['kind']
    if kind == 'host-codex':
        return HostCodexBackend()
    if kind == 'openai-compatible':
        return OpenAICompatibleBackend(value['base_url'], value['model'], value['api_key_env'],
                                       max_tokens=value.get('max_tokens', 16000), transport=transport)
    if kind == 'anthropic':
        return AnthropicBackend(value['model'], value['api_key_env'],
                                base_url=value.get('base_url', 'https://api.anthropic.com'),
                                max_tokens=value.get('max_tokens', 16000), transport=transport)
    raise ValueError('FAKE_BACKEND_REQUIRES_EXPLICIT_SCRIPT')
