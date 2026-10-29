"""Account access and immutable manual or automatic run model pools.

Only the model bridge opens credentials. Public run records contain opaque IDs.
Historical manual selections retain their original meaning.
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
    def __init__(self, store, path='/var/lib/ai4r-accounts/provider-credentials.json', *, native_factory=None,
                 local_catalog=None, local_client_factory=None, local_access=None):
        self.store, self.path = store, Path(path)
        self.lock = threading.RLock()
        self.native_factory = native_factory
        self.local_access = local_access
        from .local_models import LocalModelCatalog,LocalModelClient
        self.local_catalog = local_catalog or LocalModelCatalog()
        self.local_client_factory = local_client_factory or LocalModelClient

    def _local_binding(self, account_id, selection):
        try:
            binding=self.local_catalog.resolve(selection['preset_id'],selection['local_binding_sha256'])
            entry=self._load()['accounts'].get(account_id,{}).get('entries',{}).get(selection['preset_id'],{})
            if (entry.get('local_binding_id')!=selection['local_binding_id']
                    or entry.get('local_binding_sha256')!=binding['binding_sha256']):
                raise ValueError('revoked local binding')
            deployment=self.store.read_record(selection['deployment_ref'])
            endpoint=self.store.read_record(deployment['endpoint_ref'])
            if (endpoint != self._local_endpoint(binding) or deployment!={
                    'model_id':selection['preset_id']+':'+binding['model']['model_name'],
                    'provider_model_name':binding['model']['model_name'],'provider':'operator-local',
                    'endpoint_ref':deployment['endpoint_ref'],'adapter_id':self._local_adapter(binding),
                    'revision':binding['model']['revision']}):raise ValueError('local endpoint differs')
            return binding
        except (OSError,ValueError,KeyError,ResearchError):
            raise ProviderError('auth_failed') from None

    @staticmethod
    def _local_adapter(binding):
        return ('private-host-codex-v1' if binding['backend']['kind']=='host-codex-app-server'
                else 'private-openai-ssh-v1')

    @staticmethod
    def _local_endpoint(binding):
        # Paths/capabilities stay private; exports pin the complete policy hash
        # and preserve its non-secret target/model/limit provenance.
        backend=binding['backend']
        if backend['kind']=='host-codex-app-server':
            backend={key:backend[key] for key in ('kind','codex_sha256','account_fingerprint')}
        return {'provider_id':'operator-local','transport':'authenticated-unix-rpc',
            'gateway_id':binding['gateway_id'],'binding_sha256':binding['binding_sha256'],
            'backend':backend,'model':binding['model']}

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
            account = data['accounts'].get(account_id, {'selected_id': 'auto', 'entries': {}})
            choices = []
            for preset in PRESETS:
                entry = account['entries'].get(preset['id'], {})
                credential = data['credentials'].get(entry.get('credential_id'), {})
                choices.append(dict(preset, configured=credential.get('account_id') == account_id
                    and credential.get('platform_id') == preset['platform_id']))
            selected = account['selected_id']
            local_ready=False
            local_error=False
            try:local_models=self.local_catalog.models()
            except (OSError,ValueError,ResearchError):local_models=[];local_error=True
            for model in local_models:
                configured=False;available=False
                try:
                    binding=self.local_catalog.resolve(model['id'])
                    entry=account['entries'].get(model['id'],{})
                    configured=bool(entry.get('local_binding_id')) and entry.get('local_binding_sha256')==binding['binding_sha256']
                    if configured:
                        self.local_client_factory(binding).preflight();available=True
                except (OSError,ValueError,ResearchError,ProviderError):
                    pass
                choices.append({'id':model['id'],'name':model['name'],'model_name':model['model_name'],
                    'base_url':'','platform_id':'operator-local','platform_name':'Local endpoint',
                    'requires_api_key':False,'configured':configured,'available':available,
                    'context_window':model['context_window'],'revision':model['revision']})
                if selected==model['id']:local_ready=available
            if selected.startswith('local-') and not any(c['id']==selected for c in choices):
                choices.append({'id':selected,'name':selected+' (unavailable)','model_name':'',
                    'base_url':'','platform_id':'operator-local','platform_name':'Local endpoint',
                    'requires_api_key':False,'configured':False,'available':False})
            return {'selected_id': selected, 'choices': choices, 'applies_to': 'new_runs',
                'routing_mode': 'automatic' if selected == 'auto' else 'fixed_chatgpt_in_ai4r' if selected == 'chatgpt_ai4r' else 'manual',
                'openrouter_ready': any(c['configured'] for c in choices),
                'chatgpt_model': account.get('chatgpt_model'),
                'local_endpoints_unavailable':local_error,
                'api_ready': local_ready if selected.startswith('local-') else any(c['id'] == selected and c['configured'] for c in choices)}

    def settings(self, request, *, chatgpt_models=()):
        _require(isinstance(request, dict) and set(request) == {'account_id', 'action', 'values'}, 'Invalid model settings request')
        account_id, action, values = request['account_id'], request['action'], request['values']
        _require(isinstance(account_id, str) and 0 < len(account_id) <= 256 and isinstance(values, dict), 'Invalid account or model settings')
        if action == 'get':
            _require(not values, 'Model status takes no values')
            return self.status(account_id)
        _require(action in {'save', 'select', 'remove'}, 'Unknown model settings action')
        preset_id = values.get('preset_id')
        _require(isinstance(preset_id,str),'Choose an existing model ID')
        local = preset_id.startswith('local-')
        _require(preset_id in {'auto', 'codex', 'chatgpt_ai4r'} or preset_id in {p['id'] for p in PRESETS} or local, 'Unknown model choice')
        with self.lock:
            data = self._load()
            account = data['accounts'].setdefault(account_id, {'selected_id': 'auto', 'entries': {}})
            if local:
                _require(action in {'select','remove'} and set(values)=={'preset_id'},'Local endpoints are operator configured; select an existing ID without credentials')
                if action=='remove':
                    account['entries'].pop(preset_id,None)
                    if account['selected_id']==preset_id:account['selected_id']='codex'
                else:
                    binding=self.local_catalog.resolve(preset_id)
                    prior=account['entries'].get(preset_id,{})
                    account['entries'][preset_id]={'local_binding_id':prior.get('local_binding_id')
                        if prior.get('local_binding_sha256')==binding['binding_sha256'] else 'local-binding:'+uuid.uuid4().hex,
                        'local_binding_sha256':binding['binding_sha256']}
                    account['selected_id']=preset_id
                self._save(data)
                return self.status(account_id)
            if action == 'save':
                _require(set(values) == {'preset_id', 'api_key'} and preset_id not in {'codex','chatgpt_ai4r'}, 'Only a preset and API key may be saved')
                preset = next(p for p in PRESETS if p['id'] == ('deepseek-flash' if preset_id == 'auto' else preset_id))
                key = values['api_key']
                _require(isinstance(key, str) and len(key) <= 8192 and not any(c in key for c in '\r\n\0'), 'Invalid API key')
                old = account['entries'].get(preset['id'], {})
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
                _require(set(values) == {'preset_id'} or (action == 'select' and preset_id == 'codex'
                    and set(values) == {'preset_id', 'chatgpt_model'}), 'Unexpected model choice fields')
                if action == 'remove':
                    _require(preset_id not in {'codex', 'chatgpt_ai4r'}, 'Built-in choices cannot be removed')
                    platform = next(p['platform_id'] for p in PRESETS if p['id'] == ('deepseek-flash' if preset_id == 'auto' else preset_id))
                    revoked = {k for k, v in data['credentials'].items() if v['account_id'] == account_id
                        and (v.get('platform_id') == platform or v.get('preset_id') == preset_id)}
                    data['credentials'] = {k: v for k, v in data['credentials'].items() if k not in revoked}
                    account['entries'] = {k: v for k, v in account['entries'].items() if v.get('credential_id') not in revoked}
                    if account['selected_id'] not in {'auto', 'codex', 'chatgpt_ai4r'} and account['selected_id'] not in account['entries']:
                        account['selected_id'] = 'codex'
                else:
                    if preset_id == 'codex' and 'chatgpt_model' in values:
                        model = values['chatgpt_model']
                        _require(model is None or isinstance(model, str) and model in chatgpt_models,
                            'Choose a model from the signed-in ChatGPT model catalog')
                        account['chatgpt_model'] = model
                    if preset_id not in {'auto', 'codex', 'chatgpt_ai4r'}:
                        preset = next(p for p in PRESETS if p['id'] == preset_id)
                        credential = data['credentials'].get(account['entries'].get(preset_id, {}).get('credential_id'), {})
                        _require(credential.get('account_id') == account_id and credential.get('platform_id') == preset['platform_id'], 'Save an OpenRouter API key before selecting this model')
                    account['selected_id'] = preset_id
            self._save(data)
        return self.status(account_id)

    def freeze(self, request, *, automatic_pool=None):
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
                account = self._load()['accounts'].get(account_id, {'selected_id': 'auto', 'entries': {}})
                selected = account['selected_id']
                selection = {'mode': 'codex' if selected == 'codex' else 'api', 'preset_id': selected}
                if selected in {'auto', 'chatgpt_ai4r'}:
                    _require(automatic_pool is not None and automatic_pool.get('candidates'),
                        'Start the pinned local assessor and verifier service before starting research')
                    selection = dict(copy.deepcopy(automatic_pool), mode='automatic', preset_id=selected)
                if selected == 'codex' and account.get('chatgpt_model'):
                    model = account['chatgpt_model']
                    endpoint = {'provider_id': 'chatgpt', 'transport': 'packaged-app-server-subscription'}
                    endpoint_ref = self.store.put_blob(json.dumps(endpoint, sort_keys=True).encode(), media_type='application/json')
                    deployment = {'model_id': model, 'provider_model_name': model, 'provider': 'chatgpt',
                        'endpoint_ref': endpoint_ref, 'adapter_id': 'native-chatgpt-subscription-v1', 'revision': 'manual-chatgpt:1'}
                    selection.update(chatgpt_model=model,
                        deployment_ref=self.store.put_blob(json.dumps(deployment, sort_keys=True).encode(), media_type='application/json'))
                if selected not in {'auto', 'codex', 'chatgpt_ai4r'}:
                    entry = copy.deepcopy(account['entries'][selected])
                    if selected.startswith('local-'):
                        binding=self.local_catalog.resolve(selected,entry.get('local_binding_sha256'))
                        _require(bool(entry.get('local_binding_id')),'Select the approved local endpoint before starting a run')
                        endpoint_ref=self.store.put_blob(json.dumps(self._local_endpoint(binding),sort_keys=True).encode(),media_type='application/json')
                        deployment={'model_id':selected+':'+binding['model']['model_name'],
                            'provider_model_name':binding['model']['model_name'],'provider':'operator-local',
                            'endpoint_ref':endpoint_ref,'adapter_id':self._local_adapter(binding),'revision':binding['model']['revision']}
                        selection.update(local_binding_id=entry['local_binding_id'],local_binding_sha256=binding['binding_sha256'],
                            platform_id='operator-local',deployment_ref=self.store.put_blob(json.dumps(deployment,sort_keys=True).encode(),media_type='application/json'))
                    else:
                        self._freeze_api(account_id,selected,entry,selection)
        selection.update(schema_version='2.0.0' if selection['mode'] == 'automatic' else '1.0.0',
            id='model-selection:' + uuid.uuid4().hex, run_id=run_id, account_id=account_id)
        ref = self.store.append_record('run-model-selection', selection)
        return {'selection_ref': ref}

    def _freeze_api(self,account_id,selected,entry,selection):
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

    def for_call(self, context):
        from .evaluation_model_binding import evaluation_model_selection
        frozen = evaluation_model_selection(self.store, context)
        if frozen is not None:
            return frozen if frozen['mode'] == 'api' else None
        rows = list(self.store.iter_records(run_id=context['run_id'], kinds=('run-model-selection',)))
        if not rows:
            return None  # Historical and evaluation-only Codex runs retain their meaning.
        _require(len(rows) == 1, 'Ambiguous frozen model selection')
        selection = rows[0]['record']
        self.store.get_run(context['run_id'], account_id=selection['account_id'])
        if selection['mode'] != 'api':
            return None
        return copy.deepcopy(selection)

    def chatgpt_for_call(self, context):
        from .evaluation_model_binding import evaluation_model_selection
        frozen = evaluation_model_selection(self.store, context)
        if frozen is not None:
            return frozen if frozen['mode'] == 'codex' and frozen.get('chatgpt_model') else None
        rows = list(self.store.iter_records(run_id=context['run_id'], kinds=('run-model-selection',)))
        if not rows:
            return None
        _require(len(rows) == 1, 'Ambiguous frozen model selection')
        selection = rows[0]['record']
        self.store.get_run(context['run_id'], account_id=selection['account_id'])
        return copy.deepcopy(selection) if selection['mode'] == 'codex' and selection.get('chatgpt_model') else None

    def automatic_for_call(self, context):
        rows = list(self.store.iter_records(run_id=context['run_id'], kinds=('run-model-selection',)))
        _require(len(rows) <= 1, 'Ambiguous frozen model selection')
        if not rows or rows[0]['record']['mode'] != 'automatic':
            return None
        selection = rows[0]['record']
        self.store.get_run(context['run_id'], account_id=selection['account_id'])
        return copy.deepcopy(selection)

    def openrouter_access(self, account_id):
        """Private bridge-only access; never returned by the settings RPC."""
        with self.lock:
            data = self._load()
            entries = data['accounts'].get(account_id, {}).get('entries', {})
            for preset in PRESETS:
                credential_id = entries.get(preset['id'], {}).get('credential_id')
                value = data['credentials'].get(credential_id, {})
                if value.get('account_id') == account_id and value.get('platform_id') == 'openrouter':
                    return credential_id, value['key']
        return None

    def preflight(self, selection):
        if selection.get('access_way') == 'local':
            if self.local_access is None:
                raise ProviderError('auth_failed')
            self.local_access(selection)
            return
        with self.lock:
            if selection.get('platform_id')=='operator-local':
                binding=self._local_binding(selection['account_id'],selection)
                self.local_client_factory(binding).preflight()
                return
            credential = self._load()['credentials'].get(selection['credential_id'])
        matches = credential is not None and credential['account_id'] == selection['account_id']
        if matches:
            matches = (credential.get('platform_id') == selection['platform_id'] if selection.get('platform_id')
                else credential.get('preset_id') == selection['preset_id'])
        if not matches:
            raise ProviderError('auth_failed')

    def _capture_local_trace(self,client,context,status):
        if not getattr(client,'trace',None) or context is None:return None
        from .native_ports import capture_governed_trace_record
        scope={key:context[key] for key in ('run_id','node_id','subnode_id','attempt_id','execution_id','invocation_id','call_id','contract_ref','model_call_start_ref')}
        start=self.store.read_record(scope['model_call_start_ref'])
        _require(self.store.record_kind(scope['model_call_start_ref'])=='model-call-start'
            and all(start.get(k)==scope[k] for k in ('run_id','invocation_id','execution_id','call_id','contract_ref')),
            'Local trace differs from original protected call start')
        capture = self.store.append_record
        try:
            private = self.store.record_kind(scope['contract_ref']) == 'evaluation-subnode-context'
        except ResearchError as error:
            if error.code != 'evidence_unavailable':
                raise
            private = False  # Legacy ordinary captures may have opaque context refs.
        if private:
            capture = lambda kind, value: capture_governed_trace_record(self.store, kind, value)
        events=[]
        for sequence,(direction,method,payload) in enumerate(client.trace):
            raw=self.store.append_record('native-governed-packet',{'method':method,'payload':payload})
            events.append(capture('native-governed-trace-event',{
                'schema':'ai4r-native-governed-trace-event:1','scope':scope,'sequence':sequence,
                'direction':direction,'method':method,'raw_ref':raw}))
        return capture('native-governed-trace',{
            'schema':'ai4r-native-governed-trace:1','scope':scope,'status':status,'event_refs':events})

    async def invoke(self, selection, prompt, *, timeout_s, call_function, context=None):
        self.preflight(selection)
        if selection.get('platform_id')=='operator-local':
            with self.lock:binding=self._local_binding(selection['account_id'],selection)
            client=self.local_client_factory(binding)
            try:
                result=await client.invoke(prompt,timeout_s=timeout_s,
                    call_function='planner' if call_function=='planner' else 'worker')
            except BaseException as error:
                try:
                    trace=self._capture_local_trace(client,context,'interrupted' if getattr(error,'outcome_unknown',False) else 'failed')
                    if trace is not None:error.native_trace_ref=trace
                except Exception:
                    # Retain the original delivery uncertainty and observation
                    # when audit storage itself fails after a provider effect.
                    error.audit_capture_failed=True
                raise
            try:trace=self._capture_local_trace(client,context,'completed')
            except Exception:
                raise ProviderError('AUDIT_UNAVAILABLE',observation=result) from None
            if trace is not None:result['native_trace_ref']=trace
            return result
        if selection.get('access_way') == 'local':
            key = self.local_access(selection)
        else:
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
        selection_output = 256
        if call_function == 'routing_selection' and context is not None:
            snapshot = self.automatic_for_call(context)
            if snapshot is None:
                raise ProviderError('invalid_request')
            selection_output = snapshot['routing_policy']['selection_output_tokens']
            if type(selection_output) is not int or not 1 <= selection_output <= deployment['output_tokens']:
                raise ProviderError('invalid_request')
        # Verifier input isolation is enforced by its own Capsule/runner. This
        # adapter's text transport is identical; no user inputs are added here.
        return await provider.invoke(selection['deployment_ref'], prompt, timeout_s=timeout_s,
            call_function=call_function if selection.get('access_way') == 'local' else 'planner' if call_function == 'planner' else 'worker',
            **({'output_tokens': selection_output} if call_function == 'routing_selection' else {}))
