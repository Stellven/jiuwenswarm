"""CPU checks for invalid capacity and unsupported ceiling comparisons."""
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def baseline(monkeypatch):
    root=Path(__file__).resolve().parents[2]/'jiuwenswarm/factory/ccs/performance_baseline'
    monkeypatch.syspath_prepend(str(root))
    spec=importlib.util.spec_from_file_location('validated_baseline',root/'components.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs():
    model=dict(identity='model',demanded_experts=6,layers=2,kv_heads=2,head_dimension=4,kv_element_bytes=2,
               tensors=[dict(shape=[4,8],block_elements=8,block_bytes=4,bytes=16,numerical_path='iq2')])
    return model,dict(usable_memory_bytes=1024,supported_paths=['iq2']),dict(demanded_experts=6,context=8,batch=1)


@pytest.mark.parametrize('field,value',[('kv_heads',-1),('head_dimension',0),('kv_element_bytes',True)])
def test_invalid_kv_dimensions(baseline,field,value):
    model,hardware,workload=inputs()
    model[field]=value
    with pytest.raises(ValueError,match='dimension'):
        baseline.inspect(model,hardware,workload)


@pytest.mark.parametrize('field,value',[('workspace_bytes',-2048),('workspace_bytes',True),('reserved_memory_bytes',-1),('reserved_memory_bytes',1.5)])
def test_invalid_capacity_reservations(baseline,field,value):
    model,hardware,workload=inputs()
    (hardware if field=='reserved_memory_bytes' else workload)[field]=value
    with pytest.raises(ValueError,match='reserved capacity'):
        baseline.inspect(model,hardware,workload)


def test_capacity_reservations_and_infeasible_kv(baseline):
    model,hardware,workload=inputs()
    hardware['reserved_memory_bytes']=128
    workload['workspace_bytes']=128
    assert baseline.inspect(model,hardware,workload)['weight_capacity_bytes']==256
    workload['context']=32
    with pytest.raises(ValueError,match='exceed capacity'):
        baseline.inspect(model,hardware,workload)


def comparison():
    scope=dict(precision='iq2',sparsity='dense',phase='decode',shape=[1,32],model_identity='model',workload_identity='workload')
    return dict(scope,flops=100,memory_bytes=200,dependency_s=1),dict(scope,flops_per_s=50,memory_bytes_per_s=50)


@pytest.mark.parametrize('side,key',[(0,'precision'),(0,'sparsity'),(1,'precision'),(1,'sparsity')])
def test_explicit_numerical_paths_required(baseline,side,key):
    values=comparison()
    del values[side][key]
    with pytest.raises(ValueError):
        baseline.ceilings(*values)


@pytest.mark.parametrize('key,value',[('shape',[2,32]),('phase','prefill'),('model_identity','other-model'),('workload_identity','other-workload')])
def test_mismatched_scope_suppresses_numeric_reference(baseline,key,value):
    work,calibration=comparison()
    calibration[key]=value
    result=baseline.ceilings(work,calibration)
    assert result['ideal_expert_availability_reference']['minimum_seconds'] is None
    assert 'Calibration '+key+' differs' in result['gaps']


def test_unknown_scope_and_self_asserted_evidence_remain_unverified(baseline):
    work,calibration=comparison()
    del calibration['shape']
    result=baseline.ceilings(work,calibration,measured_engine={'verified':True},simulation={'verified':True})
    reference=result['ideal_expert_availability_reference']
    assert reference['minimum_seconds']==4
    assert reference['scope_comparable'] is False
    assert reference['provenance_verified'] is False
    assert result['supplied_evidence_verified'] is False
    assert any('engine measurement provenance' in gap for gap in result['gaps'])
    assert any('replay provenance' in gap for gap in result['gaps'])


def test_matched_declarations_still_have_unknown_provenance(baseline):
    work,calibration=comparison()
    calibration['kind']='hardware_bound'
    result=baseline.ceilings(work,calibration)
    assert result['ideal_expert_availability_reference']['scope_comparable'] is True
    assert result['ideal_expert_availability_reference']['kind']=='declared_hardware_bound'
    assert 'Calibration provenance is unverified' in result['gaps']


def test_native_spec_discloses_declaration_only_format(baseline):
    result=baseline.native_experiment('probe',[],{},0,[1,4],1)
    assert 'does not verify tensor format' in result['interpretation']
