"""Offline branch records and real native Host; no agent, GPU or job execution."""
import os
from pathlib import Path
import sys

import pytest

from jiuwenswarm.factory import branch_workbench as bw
from jiuwenswarm.factory.store import NotFound, ScopeDenied, StaleRevision, Store
from jiuwenswarm.factory.taskgraph import plan_get, plan_patch


@pytest.fixture
def branches(store):
    store.advance_decision('t', 0, {'hypothesis':'Explore alternatives using bounded evidence'})
    return store


def call(store, operation, rev=0, key=None, **inputs):
    return bw.dispatch(store.scoped('t'), 't', operation, dict(
        expected_graph_rev=rev, decision_rev=1, idem_key=key or operation+str(rev), **inputs))['analysis']


def make(store, node_id='a', rev=0, **inputs):
    return call(store, 'create', rev, node_id=node_id, hypothesis='Compare '+node_id,
                allocation={'cpu_seconds':10,'gpu_seconds':0}, **inputs)


def measured(store, evidence='measured', **metrics):
    return store.append_observation('t', dict(obs_id=evidence,kind='branch_fixture',values={
        'branch_measurement':{'comparison_key':'same-frozen-workload','scope':'offline_replay',
            'metrics':metrics, 'cost':{'cpu_seconds':1,'gpu_seconds':0}}}))


def test_fork_refine_ready_persist_cas_and_idempotency(branches):
    first = make(branches, capabilities=['factory.inference_lab.test_scope','factory.methodology_followup.followup'])
    assert first['ready'] == ['a']
    assert make(branches, capabilities=['factory.inference_lab.test_scope','factory.methodology_followup.followup']) == first
    with pytest.raises(ValueError, match='idempotency'):
        make(branches, 'changed')
    with pytest.raises(StaleRevision):
        call(branches,'fork',parent_id='a',node_id='b',hypothesis='Alternative',allocation={'cpu_seconds':5,'gpu_seconds':0})
    second = call(branches,'fork',1,parent_id='a',node_id='b',hypothesis='Alternative',allocation={'cpu_seconds':5,'gpu_seconds':0})
    assert second['ready'] == ['a','b']
    third = call(branches,'refine',2,parent_id='a',node_id='c',hypothesis='Continuation',allocation={'cpu_seconds':5,'gpu_seconds':0})
    assert third['ready'] == ['a','b']
    measured(branches,throughput_tps=2)
    recorded = call(branches,'record',3,node_id='a',evidence_id='measured')
    assert recorded['ready'] == ['b','c']
    assert bw.compare(branches,'t')['unknown'] == ['a','b','c']
    with Store(branches.home) as reopened:
        assert bw.status(reopened,'t') == recorded
        assert make(reopened, capabilities=['factory.inference_lab.test_scope','factory.methodology_followup.followup']) == first
        assert plan_get(reopened,'t')['rev'] == 4
    pruned = call(branches,'prune',4,node_id='b',reason='No justified benefit')
    assert pruned['branches'][1]['stage'] == 'pruned'
    assert pruned['allocated']['cpu_seconds'] == 20


def test_budget_shared_across_pruned_branches_and_raw_patches(branches):
    make(branches)
    call(branches,'prune',1,node_id='a',reason='Retain failed idea')
    with pytest.raises(ValueError,match='allocation budget'):
        call(branches,'create',2,node_id='b',hypothesis='Too expensive',allocation={'cpu_seconds':51,'gpu_seconds':0})
    with pytest.raises(ValueError,match='allocation budget'):
        plan_patch(branches,'t',{'add':[dict(node_id='raw',kind='investigate',title='Raw branch',branch={
            'parent_id':None,'hypothesis':'Bypass attempt','stage':'hypothesis',
            'allocation':{'cpu_seconds':0,'gpu_seconds':1}})]},2,1)
    assert bw.status(branches,'t')['graph_rev'] == 2
    make(branches,'active',2)
    with pytest.raises(ValueError,match='immutable'):
        plan_patch(branches,'t',{'update':[dict(node_id='active',branch={
            'parent_id':None,'hypothesis':'Changed','stage':'hypothesis',
            'allocation':{'cpu_seconds':0,'gpu_seconds':0}})]},3,1)


def test_wrong_task_and_invalid_measurements_are_atomic(branches):
    make(branches)
    branches.create_task(dict(task_id='other',objective='Private evidence'))
    branches.append_observation('other',dict(obs_id='foreign',kind='measurement',values={}))
    with pytest.raises(NotFound):
        call(branches,'record',1,node_id='a',evidence_id='foreign')
    with pytest.raises(ScopeDenied):
        bw.status(branches.scoped('t'),'other')
    with pytest.raises(ScopeDenied):
        bw.mutate(branches.scoped('t',{'other'}),'other','prune',{})
    branches.append_observation('t',dict(obs_id='not-measurement',kind='method_advice',values={}))
    with pytest.raises(ValueError):
        call(branches,'record',1,node_id='a',evidence_id='not-measurement')
    assert plan_get(branches,'t')['rev'] == 1
    with pytest.raises(ScopeDenied):
        branches.scoped('t').append_observation('t',dict(kind=bw.KIND, values={}))


def test_pareto_preserves_quality_and_scope_and_unknowns(branches):
    for i, metrics in enumerate([
        dict(throughput_tps=10,peak_memory_bytes=100,quality_score=1),
        dict(throughput_tps=20,peak_memory_bytes=80,quality_score=.9),
        dict(throughput_tps=5,peak_memory_bytes=120,quality_score=.8)]):
        make(branches,str(i),2*i)
        measured(branches,'m'+str(i),**metrics)
        call(branches,'record',2*i+1,node_id=str(i),evidence_id='m'+str(i))
    result = bw.compare(branches,'t')
    assert result['groups'][0]['pareto_frontier'] == ['0','1']
    assert result['unknown'] == []
    assert not result['acceptance_authorized']


def test_native_host_calls_real_scoped_api(tmp_path,monkeypatch):
    from jiuwenswarm.ccv2.ccv2 import Host
    home = tmp_path/'factory'
    with Store(home) as store:
        store.create_task(dict(task_id='native',objective='Durable alternatives'))
        store.advance_decision('native',0,{'hypothesis':'Inspect two alternative methods'})
    monkeypatch.setenv('FACTORY_HOME',str(home))
    monkeypatch.setenv('FACTORY_TASK_ID','native')
    monkeypatch.setenv('PYTHONPATH',os.environ.get('PYTHONPATH','')+os.pathsep+str(Path.cwd()))
    host=Host(tmp_path/'ccstore',session_grants=['process.exec'],python=sys.executable)
    release=host.prepare(Path('jiuwenswarm/factory/ccs/branch_workbench'))
    receipt=host.call(release,'create',dict(node_id='a',hypothesis='Inspect',allocation={'cpu_seconds':1,'gpu_seconds':0},expected_graph_rev=0,decision_rev=1,idem_key='native-a'),key='native-a')
    assert receipt['state']=='succeeded',receipt
    assert receipt['outputs']['analysis']['branches'][0]['node_id']=='a'
    receipt=host.call(release,'status',{},key='native-status')
    assert receipt['state']=='succeeded',receipt
    assert receipt['outputs']['analysis']['graph_rev']==1
    def native(op, rev, **values):
        return host.call(release, op, dict(expected_graph_rev=rev,decision_rev=1,idem_key=op+str(rev),**values),key=op+str(rev))
    receipt=native('fork',1,node_id='b',parent_id='a',hypothesis='Alternative',allocation={'cpu_seconds':1,'gpu_seconds':0})
    assert receipt['state']=='succeeded',receipt
    with Store(home) as store:
        store.append_observation('native',dict(obs_id='finding',kind='method_findings',values={'missing':'native model observation'}))
    receipt=native('attach',2,node_id='a',evidence_ids=['finding'],outcome='Need native evidence')
    assert receipt['state']=='succeeded',receipt
    receipt=native('refine',3,node_id='continuation',parent_id='a',hypothesis='Inspect next evidence gap',allocation={'cpu_seconds':1,'gpu_seconds':0})
    assert receipt['state']=='succeeded',receipt
    receipt=native('prune',4,node_id='b',reason='No discriminating evidence')
    assert receipt['state']=='succeeded',receipt
    receipt=host.call(release,'compare',{},key='native-compare')
    assert receipt['state']=='succeeded',receipt
    assert receipt['outputs']['analysis']['unknown']==['a','b','continuation']


def test_qualitative_evidence_continuation_retains_unknowns(branches):
    make(branches)
    branches.append_observation('t',dict(obs_id='method',kind='method_advice',values={'missing':['residency evidence']}))
    attached=call(branches,'attach',1,node_id='a',evidence_ids=['method'],outcome='Need a residency observation')
    assert attached['branches'][0]['stage']=='inconclusive'
    assert attached['branches'][0]['outcome']=='Need a residency observation'
    assert bw.compare(branches,'t')['unknown']==['a']
    child=call(branches,'refine',2,node_id='followup',parent_id='a',hypothesis='Inspect residency first',allocation={'cpu_seconds':1,'gpu_seconds':0})
    assert child['ready']==['followup']
    assert child['branches'][1]['depends_on']==['a']


def test_measurement_cost_scope_and_partial_vectors(branches):
    make(branches)
    branches.append_observation('t',dict(obs_id='too-costly',kind='fixture',values={'branch_measurement':dict(comparison_key='same',scope='offline_replay',metrics={},cost={'cpu_seconds':11,'gpu_seconds':0})}))
    with pytest.raises(ValueError,match='cost exceeds'):
        call(branches,'record',1,node_id='a',evidence_id='too-costly')
    assert plan_get(branches,'t')['rev']==1
    for node_id,scope in [('b','subsystem'),('c','end_to_end')]:
        rev=plan_get(branches,'t')['rev']
        make(branches,node_id,rev)
        branches.append_observation('t',dict(obs_id='m'+node_id,kind='fixture',values={'branch_measurement':dict(comparison_key='same',scope=scope,metrics=dict(throughput_tps=5,peak_memory_bytes=10,quality_score=1),cost={'cpu_seconds':1,'gpu_seconds':0})}))
        call(branches,'record',rev+1,node_id=node_id,evidence_id='m'+node_id)
    compared=bw.compare(branches,'t')
    assert len(compared['groups'])==2
    assert compared['unknown']==['a']
    assert {g['scope'] for g in compared['groups']}=={'subsystem','end_to_end'}


def test_branch_structural_fields_and_malformed_capabilities(branches):
    make(branches,capabilities=['factory.inference_lab.test_scope'])
    original=plan_get(branches,'t')['nodes'][0]['branch']
    for field,value in [('parent_id','a'),('hypothesis','Rewrite'),('allocation',{'cpu_seconds':0,'gpu_seconds':0}),('capabilities',[])]:
        with pytest.raises(ValueError,match='immutable'):
            plan_patch(branches,'t',{'update':[{'node_id':'a','branch':dict(original,**{field:value})}]},1,1)
    with pytest.raises(ValueError,match='Invalid or missing'):
        plan_patch(branches,'t',{'update':[{'node_id':'a','branch':None}]},1,1)
    with pytest.raises(ValueError,match='capabilities'):
        call(branches,'fork',1,node_id='bad',parent_id='a',hypothesis='Bad cap reference',allocation={'cpu_seconds':1,'gpu_seconds':0},capabilities=[{}])
    assert plan_get(branches,'t')['rev']==1
