"""Real native Host prepare/call; stdlib CPU experiments, no model/GPU claims."""
import json
from pathlib import Path
import sys
import pytest
from jiuwenswarm.ccv2.ccv2 import Host

BASE=Path(__file__).resolve().parents[2]/'jiuwenswarm/factory/ccs'

@pytest.mark.parametrize('name',['kv_reuse_lab','serving_scheduler_lab'])
def test_native_host_all_reference_capabilities(name,tmp_path):
    host=Host(tmp_path/'store',session_grants=['process.exec'],python=sys.executable)
    package=BASE/name; release=host.prepare(package)
    examples=json.loads((package/'fixtures/example.json').read_text())
    declaration=host.describe(release)
    assert set(declaration['capabilities'])==set(examples)|{'verify'}
    for cap,spec in examples.items():
        receipt=host.call(release,cap,{'spec':spec})
        assert receipt['state']=='succeeded',receipt
        result=receipt['outputs']['result']
        if cap=='prefix':assert result['matched_tokens']==2
        elif cap=='allocator':assert result['sequences']=={'a':[1,2],'b':[1,2,3]}
        elif cap=='estimate':assert result['logical_bytes']==4*128*(512+64)*2
        elif cap=='schedule':assert result['complete'] and len(result['completed'])==2
        elif cap=='analyze':assert result['prefill_tokens']==2
        elif cap=='compare':assert len(result['arms'])==2 and result['comparable_workload']
    receipt=host.call(release,'verify',{})
    assert receipt['state']=='succeeded',receipt
    assert receipt['outputs']['result']['passed']
    assert receipt['outputs']['result']['factory_qualification'] is False
    denied=host.call(release,next(iter(examples)),{'spec':{'path':'/etc/passwd','code':'print(1)'}})
    assert denied['state']=='failed'


def test_scheduler_comparison_cannot_replace_workload(tmp_path):
    host=Host(tmp_path/'store',session_grants=['process.exec'],python=sys.executable)
    release=host.prepare(BASE/'serving_scheduler_lab')
    spec={'workload':{'requests':[],'token_budget':4,'prefill_chunk':2},'arms':[{'requests':[]}]}
    assert host.call(release,'compare',{'spec':spec})['state']=='failed'
