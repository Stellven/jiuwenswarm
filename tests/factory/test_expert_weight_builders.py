"""CPU/source contracts; no device, model inference, Docker or performance acceptance."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from jiuwenswarm.ccv2.ccv2 import Host

CCS=Path(__file__).resolve().parents[2]/'jiuwenswarm/factory/ccs'
GIB=2**30


def module(name):
    spec=importlib.util.spec_from_file_location(name,CCS/name/'components.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def fixture(name):return json.loads((CCS/name/'fixtures/example.json').read_text())


@pytest.mark.parametrize('name,cap',[('expert_weight_residency','plan'),('expert_weight_streaming','ranges'),('expert_weight_streaming','integration')])
def test_native_host_seals_and_invokes(tmp_path,name,cap):
    host=Host(tmp_path/'host',session_grants=['process.exec'],python=sys.executable)
    release=host.prepare(CCS/name)
    receipt=host.call(release,cap,{'inputs':fixture(name)})
    assert receipt['state']=='succeeded',receipt
    assert receipt['outputs']['result'].get('execution_authorized',False) is False
    for declaration in json.loads((CCS/name/'cc.yaml').read_text())['materials'].values():
        assert (CCS/name/declaration['path']).is_file()


def test_memory_shared_allocation_and_two_contexts():
    p=module('expert_weight_residency');x=fixture('expert_weight_residency')
    x['allocations'].append(copy.deepcopy(x['allocations'][0]))
    r=p.plan(x)
    assert r['context_slot_bytes']==[24*GIB,16*GIB]
    assert r['slot_bytes']==16*GIB and r['io_uses_slot_storage']
    x['allocations'][-1]['bytes']+=1
    with pytest.raises(ValueError,match='Conflicting'):p.plan(x)


@pytest.mark.parametrize('change',[{'physical_bytes':64*GIB},{'fallback_bytes':17*GIB},{'max_inflight_bytes':17*GIB}])
def test_infeasible_budget_cannot_activate(change):
    x=fixture('expert_weight_residency');x.update(change)
    r=module('expert_weight_residency').plan(x)
    assert r['status']=='infeasible' and not r['execution_authorized']
    assert 'effective_environment' not in r


def test_holdout_cannot_change_frozen_policy():
    p=module('expert_weight_residency');x=fixture('expert_weight_residency');before=p.plan(x)
    x['trace'] += [dict(x['trace'][0],request='holdout',expert=999)]*100
    assert p.plan(x)==before
    x['evaluation_requests']=['train']
    with pytest.raises(ValueError,match='Distinct'):p.plan(x)


@pytest.mark.parametrize('field,value',[('checkpoint','b'*64),('layer',1),('layout',None),('expert',True)])
def test_changed_semantic_identity_rejected(field,value):
    x=fixture('expert_weight_residency');x['inventory'][0][field]=value
    with pytest.raises((ValueError,TypeError)):module('expert_weight_residency').plan(x)


@pytest.mark.parametrize('layout,width',[('f32',4),('iq1_m',56),('iq2_xxs',66),('iq2_xs',74)])
def test_original_packed_ranges_preserve_repeats(layout,width):
    x=fixture('expert_weight_streaming');t=x['tensor'];t['layout']=layout
    stride=(256 if layout=='f32' else 1)*width*32
    t.update(expert_stride=stride,bytes=3*stride);t['shard']['size']=64+3*stride
    r=module('expert_weight_streaming').ranges(x)
    assert r['selected_ids']==[2,0,2,1]
    assert [v['offset'] for v in r['ranges']]==[64+2*stride,64,64+stride]
    assert all(v['bytes']==stride and v['key'][3].startswith(t['name']) for v in r['ranges'])
    assert not r['prefetch'] and not r['engram_included']


@pytest.mark.parametrize('mutation',['pin','stride','extent','short','ids','layout','engram','boolean','offset'])
def test_unsafe_original_ranges_rejected(mutation):
    x=fixture('expert_weight_streaming');t=x['tensor']
    if mutation=='pin':x['source_commit']='0'*40
    elif mutation=='stride':t['expert_stride']+=1
    elif mutation=='extent':t['bytes']-=1
    elif mutation=='short':t['shard']['size']-=1
    elif mutation=='ids':x['selected_ids']=[3]
    elif mutation=='layout':t['layout']='q4_invented'
    elif mutation=='engram':t['name']='per_layer_token_embd.weight'
    elif mutation=='boolean':x['selected_ids']=[True]
    else:t['offset']=2**63
    with pytest.raises(ValueError):module('expert_weight_streaming').ranges(x)


def test_integration_uses_existing_admission_boundaries():
    r=module('expert_weight_streaming').integration(fixture('expert_weight_streaming'))
    assert not r['hardware_admitted']
    assert r['rollback']=={'LLAMA_EXPERT_RESIDENCY':'0','LLAMA_EXPERT_STREAMING':'0'}
    assert r['third_cc']=='pending profile evidence'
    assert 'factory.lab_client' in r['existing_path']
