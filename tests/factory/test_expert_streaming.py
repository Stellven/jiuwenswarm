"""Offline F14 fixtures: neither model inference nor lab/GPU execution."""
import json
from pathlib import Path
import struct

import jsonschema
import pytest
import yaml

from jiuwenswarm.ccv2.ccv2 import load
from jiuwenswarm.factory import ab, components
from jiuwenswarm.factory.controller import Controller, validate_keep_evidence
from jiuwenswarm.factory.expert_streaming import applicability, dispatch, gguf_bytes, parse_engagement

ROOT = Path(__file__).resolve().parents[2] / 'jiuwenswarm/factory'
CAPSULE = ROOT / 'ccs/expert_streaming'
FIXTURE = Path(__file__).parent / 'fixtures/expert_streaming/stderr.txt'


def test_capsule_materials_and_components():
    cc = load(CAPSULE / 'cc.yaml')
    assert cc['id'] == 'engine.expert_streaming' and cc['version'] == '2.0.1'
    assert set(cc['capabilities']) == {'applicability','engagement'}
    for material in cc['materials'].values():
        path = (CAPSULE / material['path']).resolve()
        assert path.is_relative_to(CAPSULE) and path.is_file()
    for path in components.ROOT.glob('*/component.yaml'):
        material = components.load(path.parent.name)
        jsonschema.validate(material,json.loads((ROOT/'schemas/component.schema.json').read_text()))
        assert material['acceptance']['type'] == ('observability' if path.parent.name in ('thread_names','expert_readiness','phase_stats') else 'performance')


def tiny_gguf(path):
    def string(s):
        b=s.encode();return struct.pack('<Q',len(b))+b
    data=b'GGUF'+struct.pack('<IQQ',3,2,1)
    data+=string('general.architecture')+struct.pack('<I',8)+string('qwen3moe')
    for name,size,offset in [('blk.0.ffn_up_exps.weight',1024,0),('token_embd.weight',16,4096)]:
        data+=string(name)+struct.pack('<IQIQ',1,size,0,offset)
    path.write_bytes(data)


def test_applicability_synthetic_gguf(tmp_path):
    model=tmp_path/'tiny.gguf';tiny_gguf(model)
    mem=tmp_path/'meminfo';mem.write_text('MemTotal: 100 kB\nMemAvailable: 1 kB\n')
    assert gguf_bytes(model)==(4096,64)
    result=applicability(model,['-cmoe','-lm','mmap'],mem)
    assert result['verdict']=='applicable' and result['mem_total']==102400
    assert applicability(model,['-ot','ffn_.*exps=CPU','-lm','mmap'],mem)['verdict']=='applicable'
    assert applicability(model,['-cmoe','--no-mmap'],mem)['verdict']=='not_applicable'
    assert applicability(model,[],mem)['verdict']=='unknown'
    assert applicability(tmp_path/'missing',[],mem)['expert_bytes'] is None


def test_engagement_exact_stderr_fixture():
    values=parse_engagement(FIXTURE.read_text())
    assert all(values[k]['status']=='measured' for k in ['config','fill','pregate','readiness'])
    assert values['pregate']['counters'][0]['join_bytes']==4096
    d=values['derived']
    assert d['decode_bytes_read_per_token']==pytest.approx(5208137728/63)
    assert d['demand_wait_ms_per_token']==pytest.approx(16111261271/63/1e6)
    assert d['readiness_ratio_predicted']==0.8 and d['readiness_ratio_unpredicted']==0.25
    assert d['wasted_bytes_per_token']==10 and d['duplicate_bytes_per_token']==2
    assert d['predicted_hits_done_share']==pytest.approx(2534/15908)
    missing=parse_engagement('unrelated stderr')
    assert all(missing[k]=={'status':'not_measured'} for k in ['config','fill','pregate','readiness'])
    assert all(value is None for value in missing['derived'].values())


def test_engagement_stored_attempt_and_evaluation(store):
    attempt=store.create_attempt('t',dict(kind='lab',idem_key='stream',fingerprint='stream',request={}))
    aid=attempt['attempt_id']+':ab/002-candidate/stderr.txt'
    store.put_artifact('t',aid,FIXTURE.read_bytes(),'text/plain',attempt['attempt_id'])
    store._db.execute('UPDATE attempts SET result_refs=? WHERE attempt_id=?',(json.dumps([aid]),attempt['attempt_id']))
    result=dispatch(store.scoped('t'),'t','engagement',{'attempt_id':attempt['attempt_id']})
    assert result['runs'][0]['artifact_id']==aid
    assert store.read('t',result['evidence']['observation_id'])['kind']=='expert_streaming_engagement'
    evaluation=store.add_evaluation('t',dict(eval_id='stream-eval',contract_id='fixture',contract_version='1',contract={},inputs={'source_artifacts':[aid]},execution_outcome='ok',correctness='pass',evidence_completeness='complete'))
    assert dispatch(store.scoped('t'),'t','engagement',{'evaluation_id':evaluation['eval_id']})['runs']==result['runs']
    with pytest.raises(ValueError):dispatch(store,'t','engagement',{})


@pytest.mark.parametrize('kind,ratio,signal,expected',[
    ('observability',1/1.02,'pass','accept'),('observability',1/1.04,'pass','reject'),
    ('observability',1,'not_measured','invalid'),('observability',1,'fail','reject'),
    ('performance',1,'pass','reject'),('performance',1.2,'pass','accept')])
def test_acceptance(kind,ratio,signal,expected):
    material={'acceptance':dict(type=kind,signal='engagement',overhead_bound=.03)}
    values=dict(gate='improved' if ratio>1.03 else 'not_measured' if kind=='observability' else 'null',ratio=ratio,threshold=.03,engagement=[{'status':signal}])
    evaluation=dict(execution_outcome='ok',correctness='pass',evidence_completeness='complete')
    assert ab.acceptance(material,values,evaluation)['verdict']==expected


def test_environment_lists_knobs_and_leaves_values_to_engine():
    with pytest.raises(ValueError) as error:
        ab.environment({'workload':{'env':{}}},{'LLAMA_EXPERT_UNKNOWN':'1'})
    assert all(key in str(error.value) and value in str(error.value) for key,value in components.allowed_knobs().items())
    assert ab.environment({'workload':{'env':{}}},{'LLAMA_EXPERT_PREGATE_K':'999'})['LLAMA_EXPERT_PREGATE_K']=='999'


def test_task_stream_branch_and_resources(tmp_path,monkeypatch):
    task=json.loads((ROOT/'tasks/expert-streaming-qwen36.json').read_text())
    jsonschema.validate(task,json.loads((ROOT/'schemas/task.schema.json').read_text()))
    checkout=tmp_path/'agent-workspace/llama.cpp';checkout.mkdir(parents=True)
    calls=[]
    import subprocess
    def git(argv,**kwargs):
        calls.append(argv[3:])
        return subprocess.CompletedProcess(argv,1 if 'show-ref' in argv else 0,str(checkout)+'\n','')
    monkeypatch.setattr('jiuwenswarm.factory.controller.subprocess.run',git)
    controller=Controller(home=tmp_path)
    task_id=controller.init_task(ROOT/'tasks/expert-streaming-qwen36.json')
    stored=controller.store.get_task(task_id)
    assert calls[-1]==['branch','stream','cf34d3113']
    assert json.loads(controller._message(stored,dict(turns=0,started=controller.clock(),seen_attempts={},missing_decision=False)))['resources']==task['resources']
    controller.store.close()


def test_keep_requires_accepted_ab_result(store):
    record=dict(action=dict(component='thread_names'),evidence_ids=['t'])
    with pytest.raises(ValueError):validate_keep_evidence(store,'t',record)
    obs=store.append_observation('t',dict(kind='ab_result',values=dict(component='thread_names',acceptance=dict(type='observability',verdict='accept',reasons=[]))))
    record['evidence_ids']=[obs['obs_id']]
    validate_keep_evidence(store,'t',record)


@pytest.mark.parametrize('overhead,capture,expected',[(.02,True,'accept'),(.04,True,'reject'),(.02,False,'invalid')])
def test_observability_from_raw_abba(overhead,capture,expected):
    import hashlib
    import re
    from jiuwenswarm.factory import contract
    fixture=Path(__file__).parent/'fixtures/ab'
    content={'ab/'+str(p.relative_to(fixture)):p.read_bytes() for p in fixture.rglob('*') if p.is_file()}
    content['worker.json']=b'{"execution_outcome":"ok"}'
    for index,arm in enumerate(['base','candidate','candidate','base'],1):
        prefix=f'ab/{index:03d}-{arm}/'
        text=content[prefix+'stderr.txt'].decode()
        text=re.sub(r'(?<!prompt )\beval time[^\n]*', 'eval time = 1 ms / 63 runs ( %.6f ms per token )' % (100*(1+overhead) if arm=='candidate' else 100),text)
        content[prefix+'stderr.txt']=text.encode()
        if capture:
            content[prefix+'threads.summary.json']=b'{"threads":{"12":{"comm":"xfill-0","samples":10}}}'
    c=dict(contract.load('qwen36-bare-greedy-v1'))
    c['reference']=dict(c['reference'],stdout_sha256=hashlib.sha256(content['ab/001-base/stdout.txt']).hexdigest())
    request=dict(component='thread_names',component_material=components.load('thread_names'),contract=c,
        spec=dict(rounds=1,arms={'candidate':{'switch_regex':[]},'base':{}}))
    values,evaluation,_=ab.analyse(request,content)
    assert values['acceptance']['verdict']==expected
    assert evaluation['acceptance']==values['acceptance']
    if not capture:
        assert all(c['status']=='not_measured' for c in values['engagement'])


def test_untrusted_acceptance_publication_denied(store):
    from jiuwenswarm.factory.api import dispatch as api_dispatch
    from jiuwenswarm.factory.store import ScopeDenied
    with pytest.raises(ScopeDenied):
        api_dispatch(store.scoped('t'),'t','evidence.publish',{'inputs':{'type':'observation','record':{'kind':'ab_result','values':{'acceptance':{'verdict':'accept'}}}}})


def test_applicability_uses_contract_and_publishes(store,tmp_path,monkeypatch):
    model=tmp_path/'model.gguf';tiny_gguf(model)
    monkeypatch.setattr('jiuwenswarm.factory.contract.load',lambda _:dict(model={'path':str(model)},workload={'argv':['-cmoe','-lm','mmap']}))
    result=dispatch(store.scoped('t'),'t','applicability',{})
    assert result['expert_bytes']==4096 and result['experts_cpu_side'] is True
    obs=store.read('t',result['evidence']['observation_id'])
    assert obs['kind']=='expert_streaming_applicability'


def test_observability_bound_includes_gate_threshold():
    material={'acceptance':{'type':'observability','signal':'engagement','overhead_bound':.03}}
    evaluation=dict(execution_outcome='ok',correctness='pass',evidence_completeness='complete')
    for overhead,threshold in [(.03,.03),(.05,.06)]:
        values=dict(gate='not_measured',ratio=1/(1+overhead),threshold=threshold,engagement=[{'status':'pass'}])
        assert ab.acceptance(material,values,evaluation)['verdict']=='accept'
