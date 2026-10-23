"""Account-owned API choices, private credentials, and immutable per-run selection.

This is explicit user selection, not the automatic development-profile router.
Only the model bridge opens credentials. Public run records contain opaque IDs.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import stat
import threading
import uuid

from .contracts import ResearchError
from .providers import NativeProviders, ProviderError

PRESETS = tuple(json.loads((Path(__file__).parents[1] / 'research_contracts/model-presets/catalog.json').read_text(encoding='utf-8')))


def _require(condition, message):
    if not condition:
        raise ResearchError('validation', message)


class ModelSettingsOwner:
    def __init__(self, store, path='/var/lib/ai4r-accounts/provider-credentials.json', *, native_factory=None):
        self.store, self.path = store, Path(path)
        self.lock = threading.RLock()
        self.native_factory = native_factory

    def _load(self):
        if not self.path.exists():
            return {'schema': 'ai4r-private-model-settings:1', 'accounts': {}, 'credentials': {}}
        if self.path.is_symlink():
            raise ResearchError('unavailable', 'Private model settings custody is invalid')
        fd = os.open(self.path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        try:
            meta = os.fstat(fd)
            if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or meta.st_size > 2 * 1024 * 1024
                    or os.name == 'posix' and (meta.st_uid != os.geteuid() or meta.st_mode & 0o077)):
                raise ResearchError('unavailable', 'Private model settings custody is invalid')
            with os.fdopen(fd, 'r', encoding='utf-8', closefd=False) as stream:
                value = json.load(stream)
        finally:
            os.close(fd)
        if (not isinstance(value, dict) or set(value) != {'schema', 'accounts', 'credentials'}
                or value['schema'] != 'ai4r-private-model-settings:1'
                or not isinstance(value['accounts'], dict) or not isinstance(value['credentials'], dict)):
            raise ResearchError('unavailable', 'Private model settings are invalid')
        return value

    def _save(self, value):
        parent = self.path.parent
        if any(p.is_symlink() for p in (parent, *parent.parents)):
            raise ResearchError('unavailable', 'Private model settings custody is invalid')
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name == 'posix' and (parent.stat().st_uid != os.geteuid() or parent.stat().st_mode & 0o077):
            raise ResearchError('unavailable', 'Private model settings directory is not private')
        pending = parent / ('.model-credentials-' + uuid.uuid4().hex)
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(value, stream, ensure_ascii=False, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, self.path)
        finally:
            pending.unlink(missing_ok=True)

    def status(self, account_id):
        with self.lock:
            data = self._load()
            account = data['accounts'].get(account_id, {'selected_id': 'codex', 'entries': {}})
            choices = []
            for preset in PRESETS:
                entry = account['entries'].get(preset['id'], {})
                credential = data['credentials'].get(entry.get('credential_id'), {})
                choices.append(dict(preset, configured=credential.get('account_id') == account_id
                    and credential.get('platform_id') == preset['platform_id']))
            selected = account['selected_id']
            return {'selected_id': selected, 'choices': choices, 'applies_to': 'new_runs',
                'api_ready': any(c['id'] == selected and c['configured'] for c in choices)}

    def settings(self, request):
        _require(isinstance(request, dict) and set(request) == {'account_id', 'action', 'values'}, 'Invalid model settings request')
        account_id, action, values = request['account_id'], request['action'], request['values']
        _require(isinstance(account_id, str) and 0 < len(account_id) <= 256 and isinstance(values, dict), 'Invalid account or model settings')
        if action == 'get':
            _require(not values, 'Model status takes no values')
            return self.status(account_id)
        _require(action in {'save', 'select', 'remove'}, 'Unknown model settings action')
        preset_id = values.get('preset_id')
        _require(preset_id == 'codex' or preset_id in {p['id'] for p in PRESETS}, 'Unknown model choice')
        with self.lock:
            data = self._load()
            account = data['accounts'].setdefault(account_id, {'selected_id': 'codex', 'entries': {}})
            if action == 'save':
                _require(set(values) == {'preset_id', 'api_key'} and preset_id != 'codex', 'Only a preset and API key may be saved')
                preset = next(p for p in PRESETS if p['id'] == preset_id)
                key = values['api_key']
                _require(isinstance(key, str) and len(key) <= 8192 and not any(c in key for c in '\r\n\0'), 'Invalid API key')
                old = account['entries'].get(preset_id, {})
                credential_id = old.get('credential_id')
                if key.strip():
                    _require(len(data['credentials']) < 128, 'Saved credential revision limit reached')
                    credential_id = 'credential:' + uuid.uuid4().hex
                    data['credentials'][credential_id] = {'account_id': account_id, 'preset_id': preset_id,
                        'platform_id': preset['platform_id'], 'key': key.strip()}
                credential = data['credentials'].get(credential_id, {})
                _require(credential.get('account_id') == account_id and credential.get('platform_id') == preset['platform_id'], 'An OpenRouter API key is required')
                for item in PRESETS:
                    if item['platform_id'] == preset['platform_id']:
                        account['entries'][item['id']] = {'credential_id': credential_id}
                account['selected_id'] = preset_id
            else:
                _require(set(values) == {'preset_id'}, 'Unexpected model choice fields')
                if action == 'remove':
                    _require(preset_id != 'codex', 'Codex is the built-in choice')
                    platform = next(p['platform_id'] for p in PRESETS if p['id'] == preset_id)
                    revoked = {k for k, v in data['credentials'].items() if v['account_id'] == account_id
                        and (v.get('platform_id') == platform or v.get('preset_id') == preset_id)}
                    data['credentials'] = {k: v for k, v in data['credentials'].items() if k not in revoked}
                    account['entries'] = {k: v for k, v in account['entries'].items() if v.get('credential_id') not in revoked}
                    if account['selected_id'] != 'codex' and account['selected_id'] not in account['entries']:
                        account['selected_id'] = 'codex'
                else:
                    if preset_id != 'codex':
                        preset = next(p for p in PRESETS if p['id'] == preset_id)
                        credential = data['credentials'].get(account['entries'].get(preset_id, {}).get('credential_id'), {})
                        _require(credential.get('account_id') == account_id and credential.get('platform_id') == preset['platform_id'], 'Save an OpenRouter API key before selecting this model')
                    account['selected_id'] = preset_id
            self._save(data)
        return self.status(account_id)

    def freeze(self, request):
        _require(set(request) == {'account_id', 'run_id', 'parent_run_id'}, 'Invalid model selection binding')
        account_id, run_id = request['account_id'], request['run_id']
        self.store.get_run(run_id, account_id=account_id)
        existing = list(self.store.iter_records(run_id=run_id, kinds=('run-model-selection',)))
        if existing:
            _require(len(existing) == 1, 'Ambiguous model selection')
            return {'selection_ref': existing[0]['ref']}
        parent = request['parent_run_id']
        if parent:
            self.store.get_run(parent, account_id=account_id)
            rows = list(self.store.iter_records(run_id=parent, kinds=('run-model-selection',)))
            _require(len(rows) <= 1, 'Ambiguous parent model selection')
            # Runs created before model settings keep their original bridge
            # policy; a later API preference must not change their continuation.
            selection = copy.deepcopy(rows[0]['record']) if rows else {'mode': 'codex', 'preset_id': 'codex'}
        else:
            with self.lock:
                account = self._load()['accounts'].get(account_id, {'selected_id': 'codex', 'entries': {}})
                selected = account['selected_id']
                selection = {'mode': 'codex' if selected == 'codex' else 'api', 'preset_id': selected}
                if selected != 'codex':
                    entry = copy.deepcopy(account['entries'][selected])
                    preset = next(p for p in PRESETS if p['id'] == selected)
                    credential = self._load()['credentials'].get(entry['credential_id'], {})
                    _require(credential.get('account_id') == account_id and credential.get('platform_id') == preset['platform_id'], 'Save an OpenRouter API key before starting a new run')
                    endpoint = {'provider_id': preset['platform_id'], 'base_url': preset['base_url'],
                        'models': [{'model_id': selected + ':' + preset['model_name'], 'provider_model_name': preset['model_name']}],
                        'credential_env_var': 'AI4R_SELECTED_API_KEY', 'timeout_s': 600, 'enabled': True}
                    endpoint_ref = self.store.put_blob(json.dumps(endpoint, sort_keys=True).encode(), media_type='application/json')
                    deployment = {'model_id': endpoint['models'][0]['model_id'], 'provider_model_name': preset['model_name'],
                        'provider': preset['platform_id'], 'endpoint_ref': endpoint_ref, 'adapter_id': 'native-openai-chat-v1', 'revision': 'manual-openrouter-preset:1'}
                    selection.update(credential_id=entry['credential_id'], platform_id=preset['platform_id'],
                        deployment_ref=self.store.put_blob(json.dumps(deployment, sort_keys=True).encode(), media_type='application/json'))
        selection.update(schema_version='1.0.0', id='model-selection:' + uuid.uuid4().hex, run_id=run_id, account_id=account_id)
        ref = self.store.append_record('run-model-selection', selection)
        return {'selection_ref': ref}

    def for_call(self, context):
        rows = list(self.store.iter_records(run_id=context['run_id'], kinds=('run-model-selection',)))
        if not rows:
            return None  # Historical and evaluation-only Codex runs retain their meaning.
        _require(len(rows) == 1, 'Ambiguous frozen model selection')
        selection = rows[0]['record']
        self.store.get_run(context['run_id'], account_id=selection['account_id'])
        if selection['mode'] == 'codex':
            return None
        return copy.deepcopy(selection)

    def preflight(self, selection):
        with self.lock:
            credential = self._load()['credentials'].get(selection['credential_id'])
        matches = credential is not None and credential['account_id'] == selection['account_id']
        if matches:
            matches = (credential.get('platform_id') == selection['platform_id'] if selection.get('platform_id')
                else credential.get('preset_id') == selection['preset_id'])
        if not matches:
            raise ProviderError('auth_failed')

    async def invoke(self, selection, prompt, *, timeout_s, call_function):
        self.preflight(selection)
        with self.lock:
            key = self._load()['credentials'][selection['credential_id']]['key']
        deployment = self.store.read_record(selection['deployment_ref'])
        def resolve_deployment(ref, function):
            if ref != selection['deployment_ref']:
                raise ProviderError('invalid_request')
            return deployment
        def resolve_endpoint(ref):
            if ref != deployment['endpoint_ref']:
                raise ProviderError('invalid_request')
            return self.store.read_record(ref)
        options = {'native_factory': self.native_factory} if self.native_factory else {}
        provider = NativeProviders(resolve_deployment=resolve_deployment, resolve_endpoint=resolve_endpoint,
            credential_environment={'AI4R_SELECTED_API_KEY': key}, **options)
        # Verifier input isolation is enforced by its own Capsule/runner. This
        # adapter's text transport is identical; no user inputs are added here.
        return await provider.invoke(selection['deployment_ref'], prompt, timeout_s=timeout_s,
            call_function='planner' if call_function == 'planner' else 'worker')
