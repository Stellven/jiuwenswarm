"""Finite public component observations of the app's real hybrid model bridge.

The isolated store/authority cannot admit a product Capsule or advance an app
DAG. It uses the same routing, local adapters and signed-in subscription owner.
No reviewer answers are accepted by this interface.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from pathlib import Path
import re
import time

from .automatic_routing import AutomaticRouting, POLICY, prepare_local_choice
from .bridge import GovernedBridge
from .contracts import ResearchError, validate
from .local_pool_registry import LocalModelRegistry
from .model_settings import ModelSettingsOwner
from .routing_component import ComponentAuthority
from .state import SQLiteRunStore, json_bytes
from .subscription_baseline import task_prompt

SCHEMA = 'ai4r-hybrid-routing-component:1'


class HybridBenchmark:
    def __init__(self, root, subscription):
        self.root, self.subscription = Path(root), subscription
        self.lock = asyncio.Lock()

    async def invoke(self, payload):
        if (not isinstance(payload, dict) or set(payload) != {'request_id', 'assignment'}
                or not isinstance(payload['request_id'], str)
                or not re.fullmatch('[a-zA-Z0-9_-]{8,80}', payload['request_id'])):
            raise ResearchError('invalid_request', 'Invalid public component request')
        prompt = task_prompt(payload['assignment'])
        digest = hashlib.sha256(json_bytes(payload)).hexdigest()
        async with self.lock:
            root = self.root/payload['request_id']
            if root.exists():
                if (root/'request.json').read_bytes() != json_bytes(payload):
                    raise ResearchError('invalid_request', 'Component request identity changed')
                if (root/'result.json').exists():
                    return json.loads((root/'result.json').read_bytes())
                raise ResearchError('DELIVERY_UNKNOWN', 'Original component attempt cannot be replayed')
            root.mkdir(parents=True, mode=0o700)
            (root/'request.json').write_bytes(json_bytes(payload))
            store = SQLiteRunStore(root/'capture')
            started = time.monotonic()
            result = {'schema': SCHEMA, 'request_sha256': digest,
                'request_id': payload['request_id'], 'scope': 'isolated routing component, not product acceptance',
                'routing_policy': copy.deepcopy(POLICY), 'worker': None, 'verifier': None, 'gate': 'not_run',
                'status': 'failed', 'cost': None, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()}
            subscription = self.subscription
            class ComponentSubscription:
                @property
                def account_fingerprint(self): return subscription.account_fingerprint
                async def status(self): return await subscription.status()
                async def invoke_governed_traced(self, scope, prompt, **options):
                    from jiuwenswarm.server.runtime.codex_subscription.governed_trace import GovernedTrace
                    trace = GovernedTrace(scope, store.append_record, store.put_blob)
                    try:
                        response = await subscription.invoke_governed(prompt, _trace=trace, **options)
                    except BaseException as error:
                        error.native_trace_ref = trace.finish('failed')
                        raise
                    response['native_trace_ref'] = trace.finish('completed')
                    return response
            try:
                registry = LocalModelRegistry()
                owner = ModelSettingsOwner(store, root/'private/models.json')
                routing = AutomaticRouting(owner, ComponentSubscription(), local_registry=registry)
                run_id = 'hybrid-component:' + payload['request_id']
                store.create_run(run_id, account_id='component-benchmark', workspace_id='component-benchmark', submission={})
                frozen = await routing.freeze({'account_id': 'component-benchmark', 'run_id': run_id, 'parent_run_id': None})
                snapshot = store.read_record(frozen['selection_ref'])
                declaration = {'identity': {'name': 'benchmark.bounded-json', 'version_label': 'hybrid-1',
                    'summary': 'Answer the bounded public technical assignment as exactly one JSON object.'},
                    'needs': {'model': {'modalities': ['text']}},
                    'guarantees': {'acceptance': ['One finite JSON object', 'Use only supplied facts', 'No tools or external sources']}}
                job = {'variant_id': 'component-work', 'task': payload['assignment']['task'], 'declaration': declaration}
                limits = {'worker_time_s': 90, 'verifier_time_s': 60, 'output_tokens': 1024}
                contract_ref = store.append_record('local-routing-component-contract',
                    {'schema': SCHEMA, 'declaration': declaration, 'assignment': payload['assignment'], 'limits': limits})
                class BoundRouting(AutomaticRouting):
                    def prepare(self, context, prompt):
                        if context['contract_ref'] != contract_ref:
                            raise ResearchError('invalid_request', 'Component assignment changed')
                        return self.limit_subscription(prepare_local_choice(snapshot, context, prompt, declaration,
                            objective=job['task'], task_context=None, preflight=self.preflight), context)
                bound = BoundRouting(owner, ComponentSubscription(), local_registry=registry)
                authority = ComponentAuthority(store, owner, snapshot, job, {'limits': limits}, contract_ref)
                bridge = GovernedBridge(persist=store.append_record, authorize=authority.authorize,
                    revalidate=authority.revalidate, subscription_service=ComponentSubscription(), manual_models=owner,
                    automatic_routing=bound, authorize_routing_selection=authority.selection,
                    read_evidence=store.read_blob, validate_record=validate)
                request = authority.open()
                try:
                    worker = await bridge.call(request, prompt)
                    result.update(worker=worker, status='completed')
                finally:
                    authority.contexts.pop(request['execution_id'], None)
                try:
                    output = json.loads(worker['text'])
                    if not isinstance(output, dict): raise ValueError('Object required')
                    review = ('Review only this declaration and produced output for structural and internal semantic soundness. '
                        'Do not infer unavailable source facts. Return exactly {"verdict":"PASS"} or {"verdict":"FAIL"}.\n'+
                        json.dumps({'declaration': declaration, 'output': output}, ensure_ascii=False))
                    request = authority.open('verifier')
                    try:
                        verifier = await bridge.call(request, review)
                        result['verifier'] = verifier
                        result['gate'] = 'advance' if json.loads(verifier['text']) == {'verdict': 'PASS'} else 'halt'
                    finally:
                        authority.contexts.pop(request['execution_id'], None)
                except Exception as error:
                    result.update(gate='halt', reason='review_or_structure:' + (getattr(error, 'code', None) or type(error).__name__))
            except BaseException as error:
                result['reason'] = getattr(error, 'code', None) or type(error).__name__
                if isinstance(error, asyncio.CancelledError): raise
            finally:
                result['elapsed_s'] = time.monotonic() - started
                result['records'] = list(store.iter_records())
                result['model_calls'] = [r for r in result['records'] if r['kind'] == 'model-call']
                result['decisions'] = [r for r in result['records'] if r['kind'] == 'automatic-route-decision']
                resolved = {r['record']['id'] for r in result['model_calls']}
                result['unresolved_claims'] = [r['ref'] for r in result['records']
                    if r['kind'] == 'model-call-claim' and r['record']['call_id'] not in resolved]
                result['capture_root'] = str(root/'capture')
                store.close()
                (root/'result.json').write_bytes(json_bytes(result))
            return result
