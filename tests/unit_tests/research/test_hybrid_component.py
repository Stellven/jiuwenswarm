"""Controlled wiring only; never live benchmark or product acceptance evidence."""
import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.hybrid_benchmark import HybridBenchmark
from jiuwenswarm.research.local_pool_registry import LocalModelRegistry
from jiuwenswarm.research.model_settings import ModelSettingsOwner
from tests.unit_tests.research.test_automatic_routing import ControlledSubscription


@pytest.mark.asyncio
async def test_component_uses_actual_bridge_claims_and_hides_inputs_from_review(tmp_path, monkeypatch):
    config = tmp_path/'models.json'
    config.write_text(json.dumps({'schema': 'ai4r-local-model-endpoints:1', 'models': [
        {'id': name, 'base_url': 'http://127.0.0.1:'+str(port)+'/v1', 'served_model': 'ai4r-'+name,
            'context_tokens': 65536, 'output_tokens': 4096, 'enabled': True}
        for name, port in [('gptoss20', 8012), ('lightning', 8011), ('gptoss', 8013)]]}), encoding='utf-8')
    monkeypatch.setenv('JIUWENSWARM_M1_LOCAL_MODELS', str(config))
    original_registry = LocalModelRegistry.__init__
    async def probe(entry): return True
    def registry(self, *args, **kwargs):
        original_registry(self, *args, probe=probe, **kwargs)
    monkeypatch.setattr(LocalModelRegistry, '__init__', registry)
    observed = []
    def factory(config, model):
        class Client:
            async def _parse_response(self, response):
                return SimpleNamespace(content=response['text'], tool_calls=None)
            async def invoke(self, **kwargs):
                prompt = kwargs['messages'][0]['content']; observed.append(prompt)
                text = ('{"operations":["lookup"],"difficulty":"routine","candidate_id":"local:gptoss20","reason":"Direct transformation"}' if prompt.startswith('Assess the required operations')
                    else '{"verdict":"PASS"}' if prompt.startswith('Review only') else '{"answer":7}')
                return await self._parse_response({'text': text, 'model': model['model_name'],
                    'usage': {'prompt_tokens': 10, 'completion_tokens': 5}, 'choices': [{'finish_reason': 'stop'}]})
        return Client()
    original_owner = ModelSettingsOwner.__init__
    def owner(self, *args, **kwargs):
        original_owner(self, *args, **kwargs); self.native_factory = factory
    monkeypatch.setattr(ModelSettingsOwner, '__init__', owner)
    benchmark = HybridBenchmark(tmp_path/'components', ControlledSubscription())
    payload = {'request_id': 'component-001', 'assignment': {'task': 'Return the supplied number as JSON',
        'inputs': [{'private_source_marker': 'ONLY_WORKER_DOC', 'number': 7}]}}
    result = await benchmark.invoke(payload)
    assert result['status'] == 'completed' and result['gate'] == 'advance', result
    assert len(observed) == 3
    assert 'ONLY_WORKER_DOC' not in observed[0] and 'ONLY_WORKER_DOC' in observed[1]
    assert 'ONLY_WORKER_DOC' not in observed[2] and payload['assignment']['task'] not in observed[2]
    assert len(result['model_calls']) == 3 and not result['unresolved_claims']
    assert await benchmark.invoke(payload) == result and len(observed) == 3
