"""Independent CPU invariants and real native CC transport; no GPU claims."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
from concurrent.futures import CancelledError
import pytest
from jiuwenswarm.ccv2.ccv2 import Host

BASE=Path(__file__).resolve().parents[2]/'jiuwenswarm/factory/ccs'

def load(name):
    spec=importlib.util.spec_from_file_location(name,BASE/name/'components.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

cache=load('expert_cache_lab')
ssd=load('ssd_streaming_lab')

def event(i,expert,request='a',layer=0,size=2):
    return dict(seq=i,request=request,token=i,layer=layer,expert=expert,bytes=size)


def test_byte_capacity_eviction_and_layer_identity():
    rows=[event(i,e,size=s) for i,(e,s) in enumerate([(0,2),(1,3),(0,2),(2,4),(1,3)])]
    result=cache.replay(dict(trace=rows,capacity_bytes=5))
    assert [r['hit'] for r in result['events']]==[False,False,True,False,False]
    assert result['loaded_bytes']==12
    assert result['peak_resident_bytes']==5
    assert result['events'][3]['evicted']==[[0,1],[0,0]]
    rows=[event(0,0),event(1,0,layer=1),event(2,0,request='b')]
    assert cache.replay(dict(trace=rows,capacity_bytes=4))['hits']==1
    over=cache.replay(dict(trace=[event(0,0,size=6),event(1,0,size=6)],capacity_bytes=5))
    assert over['hits']==0 and over['peak_resident_bytes']==0 and over['loaded_bytes']==12


def test_lfu_distinct_from_lru_and_causal_prediction():
    rows=[event(i,e) for i,e in enumerate([0,0,0,1,2,0])]
    assert cache.replay(dict(trace=rows,capacity_bytes=4,policy='lfu'))['hits']==3
    assert cache.replay(dict(trace=rows,capacity_bytes=4,policy='lru'))['hits']==2
    rows=[event(i,e) for i,e in enumerate([1,2,1,2,1,2])]
    data=dict(trace=rows,train_events=2)
    first=cache.predict(data)['predictions']
    changed=cache.predict(dict(data,trace=rows[:-1]+[event(5,15)]))['predictions']
    assert first[:-1]==changed[:-1]
    assert first[-1]['predicted']==changed[-1]['predicted']
    model=cache.NextExpertPredictor()
    model.observe(event(0,3,'a'));model.observe(event(1,7,'b'))
    assert not model.transitions  # no inter-request transition
    model.observe(event(2,4,'a',layer=1))
    assert not model.transitions  # no inter-layer transition


@pytest.mark.parametrize('rows',[[event(1,0),event(0,1)],[event(0,0),event(1,0,size=3)],[event(0,384)],[event(0,0,size=True)]])
def test_invalid_expert_trace_rejected(rows):
    with pytest.raises(ValueError):cache.validate(dict(trace=rows))


def test_positional_reads_coalescing_and_duplicate_order():
    assert ssd.coalesce([[3,3],[0,4],[10,2],[0,4]])==[(0,6),(10,2)]
    result=ssd.fixture_read(dict(data='abcdefghijklm',ranges=[[10,2],[0,4],[3,3],[0,4]]))
    assert result['hex_data']==[b'kl'.hex(),b'abcd'.hex(),b'def'.hex(),b'abcd'.hex()]
    assert result['peak_inflight']<=2
    assert ssd.coalesce([[0,2],[3,2]],max_gap=1)==[(0,5)]
    result=ssd.evaluate(dict(ranges=[[0,2],[8,2]],bytes_per_second=2,read_latency_seconds=1,max_inflight=1))
    assert result['modeled_seconds']==4
    with pytest.raises(ValueError):ssd.fixture_read(dict(data='abc',ranges=[[1,3]]))


def test_real_short_read_count_byte_backpressure_and_cancel(monkeypatch):
    with tempfile.TemporaryFile() as f:
        f.write(b'abc');f.flush()
        reader=ssd.BoundedPread(f.fileno(),workers=1,max_inflight=2,max_inflight_bytes=4)
        try:
            with pytest.raises(EOFError):reader.submit(2,2).result()
        finally:reader.close()
        entered,release=threading.Event(),threading.Event()
        original=ssd.os.pread
        def blocked(fd,n,offset):
            entered.set();assert release.wait(5)
            return original(fd,n,offset)
        monkeypatch.setattr(ssd.os,'pread',blocked)
        reader=ssd.BoundedPread(f.fileno(),workers=1,max_inflight=2,max_inflight_bytes=3)
        first=reader.submit(0,2);assert entered.wait(2)
        with pytest.raises(BlockingIOError):reader.submit(0,2) # bytes, below count
        second=reader.submit(2,1)
        with pytest.raises(BlockingIOError):reader.submit(0,1) # count
        reader.cancel();release.set()
        try:
            with pytest.raises(CancelledError):first.result()
            with pytest.raises(CancelledError):second.result()
        finally:reader.close()
        with pytest.raises(CancelledError):reader.submit(0,1)
        assert reader.pending==0 and reader.pending_bytes==0


@pytest.mark.parametrize('name,caps', [('expert_cache_lab',['validate','replay','predict']),('ssd_streaming_lab',['plan','evaluate','read_fixture'])])
def test_all_capabilities_real_host_and_bundled_attachment(tmp_path,name,caps):
    host=Host(tmp_path/'store',session_grants=['process.exec'],python=sys.executable)
    package=BASE/name
    release=host.prepare(package)
    data=json.loads((package/'fixtures/example.json').read_text())
    assert set(host.describe(release)['capabilities'])==set(caps)
    for capability in caps:
        receipt=host.call(release,capability,{'inputs':data})
        assert receipt['state']=='succeeded',receipt
        assert isinstance(receipt['outputs']['result'],dict)
    assert host.call(release,caps[0],{'inputs':{'ranges':[[-1,2]],'trace':[event(0,-1)]}})['state']=='failed'
    units=json.loads((package/'VERIFICATION-UNITS.json').read_text())
    assert units['scope'].startswith('CPU reference certification only')
    assert (package/units['units'][0]['attachment']).is_file()


def test_atomic_group_forecast_ignores_all_current_expert_labels():
    rows=[]
    for token in range(4):
        for expert in (0,1,2,3,4,5):
            rows.append(dict(seq=len(rows),request='a',token=token,layer=0,expert=expert,bytes=2))
    original=cache.predict(dict(trace=rows,train_events=6))
    altered=[dict(row,expert=20+row['expert']) if row['token']==2 else row for row in rows]
    changed=cache.predict(dict(trace=altered,train_events=6))
    assert original['predictions'][1]['predicted']==changed['predictions'][1]['predicted']
    assert original['evaluation_groups']==3 and original['evaluation_events']==18
    with pytest.raises(ValueError,match='boundary'):
        cache.predict(dict(trace=rows,train_events=1))
    heldout=[dict(row,request='b',seq=len(rows)+row['seq']) for row in rows]
    frozen=cache.predict(dict(trace=rows+heldout,evaluation_requests=['b']))
    assert frozen['mode']=='request_separated_frozen_holdout'
    assert all(row['request']=='b' for row in frozen['predictions'])
    assert frozen['train_events']==24
