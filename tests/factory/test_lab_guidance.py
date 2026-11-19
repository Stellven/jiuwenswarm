import copy
import pytest
from jiuwenswarm.factory.lab_guidance import recommend,digest


def bundle():
 return dict(schema='factory.lab-guidance-input/1',evidence_ids=['trace:1'],remaining=dict(successors=1,lab_attempts=2),
  identities=dict(source_commit='a'*40,image_id='sha256:'+'b'*64,executable_sha256='c'*64,model_manifest_sha256='d'*64,contract_sha256='e'*64),
  quality=dict(complete=True,correctness='pass',independent_aa=True,aa_relative_spread=.01),
  source_mapping=dict(owner='expert_weight_streaming',path='ggml/src/ggml-cpu/expert-streaming.cpp',source_commit='a'*40),
  trace=dict(schema='expert-reader-timeline/1',critical_path_validated=True,evidence_id='trace:1',decode_ms=100,uncovered_join_wait_ms=30,added_overhead_upper_ms=5))


def test_missing_signal_cannot_infer_queue_wait():
 b=bundle();b['trace']={'miss_bytes':1000000}
 r=recommend(b,'bundle:1');assert r['recommendation']=='collect_more' and r['ontology_delta'] is None


def test_noisy_aa_blocks_proposal():
 b=bundle();b['quality']['aa_relative_spread']=.2
 assert recommend(b,'bundle:1')['recommendation']=='collect_more'


def test_supported_single_change_links_delta_and_contract():
 r=recommend(bundle(),'bundle:1');assert r['recommendation']=='propose'
 assert r['draft_child_contract']['ontology_delta_sha256']==digest(r['ontology_delta'])
 assert r['benefit_range']['client_speedup']==[1,100/75]
 assert r['execution_authorized'] is False and r['draft_child_contract']['draft_only']


@pytest.mark.parametrize('boundary,cc',[('build','factory.builder'),('capture','factory.lab_client'),('material_application','engine.expert_weight_streaming_builder')])
def test_failing_cc_can_be_the_subject(boundary,cc):
 b=bundle();b['failure']=dict(boundary=boundary,evidence_id='trace:1',source_commit='a'*40,reproducer='Repeat the retained bounded CPU fixture.')
 r=recommend(b,'bundle:1');assert r['cc_candidates']==[cc] and r['benefit_range'] is None
 assert r['ontology_delta'] and r['draft_child_contract']


def test_budget_stops_and_foreign_trace_rejected():
 b=bundle();b['remaining']['successors']=0;assert recommend(b,'bundle:1')['recommendation']=='stop'
 b=bundle();b['trace']['evidence_id']='foreign'
 with pytest.raises(ValueError):recommend(b,'bundle:1')


@pytest.mark.parametrize('mode',['missing','noisy','supported'])
def test_real_native_host_bundle_receipt(tmp_path,monkeypatch,mode):
 import sys
 from pathlib import Path
 from jiuwenswarm.ccv2.ccv2 import Host
 from jiuwenswarm.factory.store import Store
 root=Path(__file__).resolve().parents[2];home=tmp_path/'factory'
 b=bundle()
 if mode=='missing':b.pop('trace')
 if mode=='noisy':b['quality']['aa_relative_spread']=.4
 with Store(home) as s:
  s.create_task({'task_id':'t','objective':'CPU fixture only'})
  s.append_observation('t',dict(obs_id='trace:1',kind='fixture',values={'cpu_only':True}))
  s.append_observation('t',dict(obs_id='bundle:1',kind='fixture',values=b))
 monkeypatch.setenv('FACTORY_HOME',str(home));monkeypatch.setenv('FACTORY_TASK_ID','t')
 monkeypatch.setenv('PYTHONPATH',str(root));monkeypatch.setenv('FACTORY_PYTHON',sys.executable)
 host=Host(tmp_path/'ccstore',session_grants=['process.exec'],python=sys.executable)
 r=host.call(host.prepare(root/'jiuwenswarm/factory/ccs/methodology_followup'),'lab_guided',{'evidence_ids':['bundle:1']})
 assert r['state']=='succeeded',r
 assert r['outputs']['analysis']['recommendation']==('propose' if mode=='supported' else 'collect_more')
