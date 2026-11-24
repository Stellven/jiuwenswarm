"""Real CCv2 native invocation plus independent CPU reference invariants."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from jiuwenswarm.ccv2.ccv2 import Host

ROOT = Path(__file__).resolve().parents[2]
CCS = ROOT/'jiuwenswarm/factory/ccs'
CAPABILITIES = [('heterogeneous_placement_lab',cap) for cap in ('plan','execute_reference','overlap_schedule')] + [('precision_lab',cap) for cap in ('quantize','evaluate','calibrate','memory_plan')]


def component(package, module):
    path=CCS/package/'components'/f'{module}.py'
    spec=importlib.util.spec_from_file_location(package+'_'+module,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize('package,capability',CAPABILITIES)
def test_real_host_prepares_and_calls_every_capability(tmp_path,package,capability):
    host=Host(tmp_path/'ccstore',session_grants=('process.exec',),python=sys.executable)
    release=host.prepare(CCS/package)
    request=json.loads((CCS/package/'fixtures'/f'{capability}.json').read_text())
    result=host.call(release,capability,{'request':request})
    assert result['state']=='succeeded',result
    output=result['outputs']['result']
    assert output['qualification']=='cpu_reference_qualified'
    if capability=='execute_reference':
        assert output['output']==[27,36]
        assert output['executed_experts']==list(range(6))
    elif capability=='quantize':
        assert output['decoded'][:4]==[0,-7,7,0]
        assert output['engine_format_compatible'] is False
    elif capability=='evaluate':
        assert output['approximation_gate'] and not output['exact_gate']


def test_shared_physical_capacity_and_all_selected_experts():
    p=component('heterogeneous_placement_lab','placement')
    data=json.loads((CCS/'heterogeneous_placement_lab/fixtures/plan.json').read_text())
    data.update(physical_capacity_bytes=6100,unified_memory=True)
    result=p.plan(data)
    assert len(result['decisions'])==6 and all(d['device']=='cpu' for d in result['decisions'])
    data['gpu_resident_bytes']=1
    with pytest.raises(ValueError,match='shared physical'):p.plan(data)
    data['gpu_resident_bytes']=0;data['selected_experts']=[0,1,2,3,4]
    with pytest.raises(ValueError,match='six'):p.plan(data)


def test_transfer_cost_changes_placement_without_changing_selection():
    p=component('heterogeneous_placement_lab','placement')
    data=json.loads((CCS/'heterogeneous_placement_lab/fixtures/plan.json').read_text())
    fast=p.plan(data)
    data['transfer_bytes_per_second']=100
    slow=p.plan(data)
    assert all(x['device']=='gpu' for x in fast['decisions'])
    assert all(x['device']=='cpu' for x in slow['decisions'])
    assert fast['selected_experts']==slow['selected_experts']


def test_overlap_obeys_transfer_readiness_and_serial_compute():
    p=component('heterogeneous_placement_lab','placement')
    result=p.overlap_schedule({'stages':[{'transfer_ms':3,'compute_ms':5},{'transfer_ms':10,'compute_ms':2}],'tokens':2})
    assert result['optimistic_overlap_ms']==15 and result['serial_ms']==20
    assert result['estimated_ms_per_token']==7.5
    assert result['events'][1]['compute_start_ms']==13


@pytest.mark.parametrize('values',[[0]*17,[-7,0,7],[1e300,-1e300,0],[1e-300,-1e-300,0],[0,0,1,-1,3]])
def test_int4_roundtrip_real_payload_and_finite_extremes(values):
    p=component('precision_lab','precision')
    result=p.quantize({'values':values,'block_size':3})
    assert p.unpack(result['codec'])==result['decoded']
    assert len(result['codec']['packed'])==(len(values)+1)//2
    metrics=p.evaluate({'reference':values,'candidate':result['decoded'],'max_abs_budget':1e300})
    assert metrics['within_budget']
    if not any(values):assert metrics['exact_gate']


@pytest.mark.parametrize('bad',[float('nan'),float('inf'),-float('inf'),True])
def test_precision_rejects_nonfinite_or_boolean(bad):
    p=component('precision_lab','precision')
    with pytest.raises(ValueError):p.quantize({'values':[bad]})


def test_codec_malformed_padding_reserved_code_and_length():
    p=component('precision_lab','precision')
    codec=p.quantize({'values':[-7,0,7],'block_size':3})['codec']
    for packed in ([8,7],[9,23],[9]):
        with pytest.raises(ValueError):p.unpack(dict(codec,packed=packed))
    assert p.evaluate({'reference':[1.0],'candidate':[1.1],'max_abs_budget':0.2})['exact_gate'] is False
    assert p.calibrate({'values':[1,1.1,7],'block_sizes':[3],'max_abs_budget':0})['selected'] is None


def test_memory_counts_tail_scales_and_separate_approximate_kv():
    p=component('precision_lab','precision')
    result=p.memory_plan({'weight_elements':33,'block_size':32,'tokens':2,'layers':1,'kv_heads':1,'head_dim':4})
    assert result['weight_reference_int4_bytes']==33
    assert result['kv_fp16_bytes']==32 and result['kv_candidate_payload_bytes']==16
    assert result['kv_candidate_approximate'] and not result['kv_metadata_bytes_included']


def test_mixed_scale_error_does_not_vanish_beside_equal_outlier():
    p=component('precision_lab','precision')
    result=p.evaluate({'reference':[1e300,1e-300],'candidate':[1e300,0],'max_abs_budget':0})
    assert result['max_abs_error']==1e-300
    assert 0 < result['rmse'] < 1e-300
    assert not result['within_budget'] and not result['exact_gate']
