"""Quality boundaries and matched comparison wiring, not empirical accuracy."""
import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.automatic_routing import POLICY, AutomaticRouting
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.hybrid_benchmark import HybridBenchmark
from jiuwenswarm.research.local_pool_registry import LocalModelRegistry
from jiuwenswarm.research.model_settings import ModelSettingsOwner
from jiuwenswarm.research.routing_assessment import task_evidence
from jiuwenswarm.research.providers import NativeProviders
from tests.unit_tests.research.test_automatic_routing import ControlledSubscription, make_bridge, setup_local


def test_rule_evidence_exposes_hidden_derivation_without_disclosing_values():
    payload = {'inputs':[{'private_rows': [{'secret':'NEVER_DISCLOSE_ME'}],
        'rule':'Choose a threshold that maximizes precision; break ties by the smaller value.'}]}
    evidence = task_evidence('Task\n'+json.dumps(payload), 'Compare short supplied alternatives')
    assert 'derived_metric_controls_decision' in evidence['protected_risk_flags']
    assert 'optimization_or_tie_sensitive_selection' in evidence['protected_risk_flags']
    assert 'NEVER_DISCLOSE_ME' not in json.dumps(evidence)
    assert any(row.get('length') == 1 for row in evidence['input_structure'])


@pytest.mark.asyncio
async def test_protected_derived_decision_cannot_be_sent_to_qwen_by_routine_capsule(tmp_path):
    subscription = ControlledSubscription()
    store, runner, ref, contract, owner, routing = await setup_local(tmp_path, hybrid=True,
        subscription=subscription, hybrid_policy=POLICY)
    try:
        def forbidden(*args):
            raise AssertionError('No local worker or selector should run for protected derived decisions')
        owner.native_factory = forbidden
        bridge = make_bridge(store, runner, owner, routing); bridge.subscription = subscription
        context = runner._start_context(ref, contract, {})
        await runner._await_start(context)
        prompt = 'Assignment\n'+json.dumps({'inputs':[{'rule':'Select a probability threshold that maximizes accuracy.'}]})
        await bridge.call({'execution_id':context.execution_id,'call_ordinal':1},prompt)
        decision = next(store.iter_records(kinds=('automatic-route-decision',)))['record']
        assert decision['selected_candidate_id'] == 'subscription:gpt-6.1-sol'
        assert len(subscription.calls) == 1 and decision['selection_call_ref'] is None
        assert 'Protected task risk' in decision['reason']
    finally:
        store.close()


def test_quality_tier_cannot_be_downgraded_when_frontier_unavailable():
    text = json.dumps({'operations':['optimize'],'difficulty':'routine','candidate_id':'local:qwen','reason':'Tiny input'})
    with pytest.raises(ResearchError) as error:
        AutomaticRouting.decode(text,[{'id':'local:qwen'},{'id':'local:gptoss'}],policy=POLICY)
    assert error.value.code == 'ENVIRONMENT_BLOCKED'
    selected, _ = AutomaticRouting.decode(json.dumps({'operations':['aggregate'],'difficulty':'reasoning',
        'candidate_id':'local:qwen','reason':'Several observations'}),
        [{'id':'local:qwen'},{'id':'local:gptoss'}],policy=POLICY)
    assert selected['id'] == 'local:gptoss'


@pytest.mark.asyncio
async def test_small_reasoning_model_keeps_assessor_budget_separate_from_worker_thinking():
    deployment={'adapter_id':'native-local-openai-chat-v1','revision':'local-access-pool:1',
        'model_id':'small','provider_model_name':'small','provider':'local','endpoint_ref':'endpoint',
        'output_tokens':8192,'reasoning_enabled':True,'reasoning_effort':'medium',
        'reasoning_role_policy':'worker_medium_assessor_verifier_none:1'}
    endpoint={'provider_id':'local','base_url':'http://127.0.0.1:8012/v1',
        'models':[{'model_id':'small','provider_model_name':'small'}],
        'credential_env_var':'AI4R_SELECTED_API_KEY','timeout_s':120,'enabled':True}
    provider=NativeProviders(resolve_deployment=lambda ref,function:deployment,
        resolve_endpoint=lambda ref:endpoint,credential_environment={'AI4R_SELECTED_API_KEY':''})
    _,_,worker=await provider._configuration('model',timeout_s=60,call_function='worker')
    _,_,selector=await provider._configuration('model',timeout_s=15,call_function='routing_selection')
    _,_,verifier=await provider._configuration('model',timeout_s=60,call_function='verifier')
    assert worker['extra_body']['reasoning_effort']=='medium'
    assert selector['extra_body']['reasoning_effort']==verifier['extra_body']['reasoning_effort']=='none'
    assert selector['extra_body']['chat_template_kwargs']['enable_thinking'] is False


@pytest.mark.asyncio
async def test_ai4r_reference_and_hybrid_share_verifier_prompt_and_gate(tmp_path,monkeypatch):
    config=tmp_path/'models.json'
    config.write_text(json.dumps({'schema':'ai4r-local-model-endpoints:1','models':[
        {'id':'gptoss20','base_url':'http://127.0.0.1:8012/v1','served_model':'small-check',
         'context_tokens':16384,'output_tokens':4096,'enabled':True}]}),encoding='utf-8')
    monkeypatch.setenv('JIUWENSWARM_M1_LOCAL_MODELS',str(config))
    original_registry=LocalModelRegistry.__init__
    async def probe(entry):return True
    def registry(self,*args,**kwargs):original_registry(self,*args,probe=probe,**kwargs)
    monkeypatch.setattr(LocalModelRegistry,'__init__',registry)
    reviews=[]
    def factory(config,model):
        class Client:
            async def _parse_response(self,response):return SimpleNamespace(content=response['text'],tool_calls=None)
            async def invoke(self,**kwargs):
                prompt=kwargs['messages'][0]['content']
                if prompt.startswith('Review only'):
                    reviews.append(prompt); text='{"verdict":"PASS"}'
                elif prompt.startswith('Assess the required operations'):
                    assert model['max_tokens']==POLICY['selection_output_tokens']
                    text=json.dumps({'operations':['lookup'],'difficulty':'routine','candidate_id':'local:gptoss20','reason':'Copy supplied value'})
                else:text='{"answer":7}'
                return await self._parse_response({'text':text,'model':model['model_name'],
                    'usage':{'prompt_tokens':10,'completion_tokens':5},'choices':[{'finish_reason':'stop'}]})
        return Client()
    original_owner=ModelSettingsOwner.__init__
    def owner(self,*args,**kwargs):original_owner(self,*args,**kwargs);self.native_factory=factory
    monkeypatch.setattr(ModelSettingsOwner,'__init__',owner)
    class Subscription(ControlledSubscription):
        async def invoke_governed(self,prompt,**options):
            result=await super().invoke_governed(prompt,**options)
            return dict(result,text='{"answer":7}')
    service=Subscription();benchmark=HybridBenchmark(tmp_path/'capture',service)
    assignment={'task':'Return the supplied number as JSON','inputs':[{'number':7,'private':'NEVER_IN_REVIEW'}]}
    hybrid=await benchmark.invoke({'request_id':'routed-001','arm':'hybrid','assignment':assignment})
    baseline=await benchmark.invoke({'request_id':'fixed-001','arm':'chatgpt_ai4r','assignment':assignment})
    assert hybrid['gate']==baseline['gate']=='advance'
    assert reviews[0]==reviews[1] and 'NEVER_IN_REVIEW' not in reviews[0]
    assert len(baseline['model_calls'])==2
    assert [row['record']['call_function'] for row in baseline['model_calls']]==['worker','verifier']
    assert baseline['routing_policy']['schema']=='ai4r-chatgpt-fixed-reference:3'
    decisions=[row['record'] for row in baseline['decisions']]
    assert decisions[0]['selected_candidate_id']=='subscription:gpt-6.1-sol'
    assert decisions[1]['selected_candidate_id']=='local:gptoss20'
