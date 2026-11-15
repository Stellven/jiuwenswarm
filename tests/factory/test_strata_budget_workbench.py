"""Budget CC negative controls and real native transport; no GPU execution."""
import importlib.util
import json
from pathlib import Path
import sys

from jiuwenswarm.ccv2.ccv2 import Host

PACKAGE=Path(__file__).resolve().parents[2]/'jiuwenswarm/factory/ccs/strata_budget_workbench'
spec=importlib.util.spec_from_file_location('budget_component',PACKAGE/'component.py')
component=importlib.util.module_from_spec(spec);spec.loader.exec_module(component)


def test_examples_native_host_and_profile_purity(tmp_path):
    examples=json.loads((PACKAGE/'EXAMPLES.json').read_text())['calls']
    host=Host(tmp_path/'store',session_grants=['process.exec'],python=sys.executable)
    release=host.prepare(PACKAGE)
    for call in examples:
        before=json.dumps(call,sort_keys=True)
        receipt=host.call(release,call['capability'],call['inputs'])
        assert receipt['state']=='succeeded',receipt
        assert json.dumps(call,sort_keys=True)==before
    invalid=dict(examples[0]['inputs']['request'],budget_bytes=True)
    assert host.call(release,'apply',{'request':invalid})['state']=='failed'


def test_missing_memory_is_unknown_and_not_additive():
    out=component.summarize_memory({'samples':[{'cgroup_peak':10,'available_bytes':100},{'cgroup_peak':11,'available_bytes':90}]})
    assert out['cgroup_kernel_peak_bytes']==11
    assert out['host_sampled_min_available_bytes']==90
    assert out['cgroup_sampled_max_bytes'] is None
    assert not out['exact_gpu_peak_measured']


def test_malformed_duplicate_startup_does_not_hide_beside_valid_rows():
    import pytest
    calls=json.loads((PACKAGE/'EXAMPLES.json').read_text())['calls']
    request=dict(calls[1]['inputs']['request'])
    request['stderr']+='ds4: fixed expert budget requested=invalid\n'
    with pytest.raises(ValueError,match='Malformed'):
        component.verify_startup(request)
    with pytest.raises(ValueError,match='objects'):
        component.summarize_memory({'samples':[None]})
