"""Controller checks only. Controlled SDK responses are never live MR evidence."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from benchmarks.local_routing.protocol import PROTOCOL
from benchmarks.local_routing.runtime import observe
from benchmarks.local_routing.score import validate_observation
from jiuwenswarm.research.automatic_routing import POLICY, prepare_local_choice
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.local_pool_registry import LocalModelRegistry
from jiuwenswarm.research.model_settings import ModelSettingsOwner


def plan():
    return {'scope':'unit fixture, not real endpoint evidence', 'commit':'unit',
        'limits':{'worker_time_s':30,'verifier_time_s':30,'output_tokens':1024},
        'models':[{'id':name,'base_url':'http://127.0.0.1:'+str(port)+'/v1',
            'served_model':'ai4r-'+name,'context_tokens':65536,'output_tokens':8192,'enabled':True}
            for name,port in [('e4b',8011),('qwen',8012),('bolt',8013)]]}


def job():
    return {'case_id':'mr01-quality','variant_id':'unit','task':'Calculate from the private public fixture.',
        'fault':None,'inputs':[{'sha256':'1'*64,'value':{'secret_input_marker':'DO_NOT_SHOW_TO_REVIEWER'}}],
        'declaration':{'identity':{'name':'benchmark.bounded-json','version_label':'local-1','summary':'Return JSON'},
            'needs':{'model':{'modalities':['text']}},'guarantees':{'acceptance':['JSON object']}}}


def controlled_factory(messages):
    def factory(config, model):
        assert config['auth_mode']=='none' and config['max_retries']==0
        class Client:
            async def _parse_response(self,response):
                return SimpleNamespace(content=response['text'],tool_calls=None)
            async def invoke(self,**kwargs):
                prompt=kwargs['messages'][0]['content']; messages.append((model['model_name'],prompt))
                text=json.dumps({'candidate_id':'local:e4b','reason':'Sufficient'}) if model['max_tokens']==256 else (
                    '{"verdict":"PASS"}' if prompt.startswith('Review only') else '{"answer":4}')
                return await self._parse_response({'text':text,'model':model['model_name'],
                    'usage':{'prompt_tokens':10,'completion_tokens':5},'choices':[{'finish_reason':'stop'}]})
        return Client()
    return factory


@pytest.mark.asyncio
async def test_real_bridge_claims_and_records_join_and_verifier_isolation(tmp_path,monkeypatch):
    messages=[]
    async def ready(self,entry): return True
    monkeypatch.setattr(LocalModelRegistry,'_probe',ready)
    original=ModelSettingsOwner.__init__
    def owner(self,*args,**kwargs):
        original(self,*args,**kwargs); self.native_factory=controlled_factory(messages)
    monkeypatch.setattr(ModelSettingsOwner,'__init__',owner)
    result=await observe(tmp_path/'observation',plan(),job(),'routed',None,0)
    assert result['status']=='completed', result
    assert len(validate_observation(tmp_path/'observation',result))==3
    assert [model for model,_ in messages]==['ai4r-e4b','ai4r-e4b','ai4r-qwen']
    assert 'DO_NOT_SHOW_TO_REVIEWER' in messages[1][1]
    assert 'DO_NOT_SHOW_TO_REVIEWER' not in messages[0][1]+messages[2][1]
    assert result['gate']=='advance' and result['cost'] is None
    corrupted=copy.deepcopy(result); corrupted['worker']['text']='{"answer":5}'
    with pytest.raises(ValueError,match='actual original'):
        validate_observation(tmp_path/'observation',corrupted)


def test_native_schema_requirement_blocks_unqualified_text_adapters():
    snapshot={'candidates':[{'id':'local:qwen','family':'qwen','model_id':'qwen',
        'capabilities':{'modalities':['text'],'tool_calling':False,'context_tokens':65536,'output_tokens':1024}}],
        'verifier_id':'local:qwen','selector_id':'local:e4b',
        'routing_policy':POLICY}
    declaration=job()['declaration']; declaration['needs']['model']['native_structured_output']=True
    with pytest.raises(ResearchError,match='compatible'):
        prepare_local_choice(snapshot,{'call_function':'worker'},'prompt',declaration,
            objective='Task',task_context=None,preflight=lambda _:None)


@pytest.mark.asyncio
async def test_selector_timeout_allows_qwen_worker_and_following_independent_review(tmp_path,monkeypatch):
    messages=[]
    async def ready(self,entry): return True
    monkeypatch.setattr(LocalModelRegistry,'_probe',ready)
    original=ModelSettingsOwner.__init__
    factory=controlled_factory(messages)
    def timed_factory(config,model):
        if model['max_tokens']!=256:return factory(config,model)
        class Client:
            async def _parse_response(self,response): return response
            async def invoke(self,**kwargs):
                messages.append((model['model_name'],'controlled selector timeout'))
                raise TimeoutError('controlled read-only inference timeout')
        return Client()
    def owner(self,*args,**kwargs):
        original(self,*args,**kwargs);self.native_factory=timed_factory
    monkeypatch.setattr(ModelSettingsOwner,'__init__',owner)
    result=await observe(tmp_path/'observation',plan(),job(),'routed',None,0)
    assert result['gate']=='advance', result
    assert [m for m,_ in messages]==['ai4r-e4b','ai4r-qwen','ai4r-qwen']
    calls=[r['record'] for r in result['model_calls']]
    assert calls[0]['outcome']=='outcome_unknown' and calls[0]['purpose']=='routing_selection'
    assert calls[1]['outcome']==calls[2]['outcome']=='completed'
    assert len(validate_observation(tmp_path/'observation',result))==3
