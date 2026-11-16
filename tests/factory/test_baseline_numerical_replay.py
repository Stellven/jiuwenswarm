"""CPU-only arithmetic and retained-artifact adversarial tests; no native build."""
import hashlib
import json
import struct
from pathlib import Path

import pytest
from jiuwenswarm.factory.ccs.performance_baseline import numerical_replay as replay
from jiuwenswarm.factory.baseline_replay import verify_attempt
from jiuwenswarm.factory.store import Store
from jiuwenswarm.factory.jobs import Jobs, metadata


def pack(values, kind='f'):
    return b''.join(struct.pack('<'+kind,v) for v in values)


@pytest.fixture
def fixture():
    weights=pack([1,2,3,4,-1,-2,-3,-4]); x=pack([1,-2,3,.5])
    expected=dict(run_id='run-1',tensor_id='tensor.weight',offset=12,shape=[2,4],repeats=10,
        samples=2,synchronization='batch',input_kind='pinned_fp32',
        slice_sha256=hashlib.sha256(weights).hexdigest(),input_sha256=hashlib.sha256(x).hexdigest())
    meta={k:v for k,v in expected.items() if not k.endswith('sha256')}
    meta.update(format=replay.FORMAT,criterion=replay.CRITERION,reference_passed=True)
    artifacts={'replay.json':json.dumps(meta).encode(),'input.f32':x,
               'reference.f64':pack([8,-8],'d'),'output.f32':pack([8,-8]*3)}
    return expected,artifacts,weights


def verify(fixture):
    expected,artifacts,weights=fixture
    return replay.verify(expected,artifacts.__getitem__,lambda offset,size:weights)


def test_recomputes_reference_not_producer_flag(fixture):
    assert verify(fixture)['status']=='verified'
    expected,artifacts,_=fixture
    meta=json.loads(artifacts['replay.json']);meta['reference_passed']=False
    artifacts['replay.json']=json.dumps(meta).encode()
    report=verify(fixture)
    assert report['status']=='verified' and report['reference_recomputed']
    assert report['vectors_checked']==3 and not report['tensor_metadata_verified']
    assert not report['execution_provenance_verified'] and not report['promotion_authorized']
    # Two mutually agreeing forged producer vectors cannot replace actual W*x.
    artifacts['reference.f64']=pack([99,99],'d');artifacts['output.f32']=pack([99]*6)
    report=verify(fixture)
    assert report['status']=='failed' and not report['output_passed']


@pytest.mark.parametrize('key,value',[('run_id','other'),('tensor_id','other'),('offset',16),
    ('shape',[4,2]),('samples',3),('repeats',11),('synchronization','each'),
    ('input_kind','calibration_mod17'),('criterion','anything passes')])
def test_changed_declared_identity(fixture,key,value):
    meta=json.loads(fixture[1]['replay.json']);meta[key]=value
    fixture[1]['replay.json']=json.dumps(meta).encode()
    with pytest.raises(ValueError,match='differs'):verify(fixture)


@pytest.mark.parametrize('name',['input.f32','output.f32','reference.f64'])
def test_missing_vectors_cannot_verify(fixture,name):
    del fixture[1][name]
    with pytest.raises(KeyError):verify(fixture)


def test_historical_self_success_without_replay_is_unverified(fixture):
    del fixture[1]['replay.json']
    fixture[1]['stdout']=b'{"reference_passed":true}'
    assert verify(fixture)['status']=='unverified'


@pytest.mark.parametrize('name,kind,count',[('input.f32','f',4),('output.f32','f',6),('reference.f64','d',2)])
@pytest.mark.parametrize('bad',[float('nan'),float('inf')])
def test_nonfinite_vectors(fixture,name,kind,count,bad):
    fixture[1][name]=pack([bad]*count,kind)
    if name=='input.f32':fixture[0]['input_sha256']=hashlib.sha256(fixture[1][name]).hexdigest()
    with pytest.raises(ValueError,match='Nonfinite'):verify(fixture)


@pytest.mark.parametrize('name',['input.f32','output.f32','reference.f64'])
def test_vector_dimensions(fixture,name):
    fixture[1][name]=fixture[1][name][:-4]
    if name=='input.f32':fixture[0]['input_sha256']=hashlib.sha256(fixture[1][name]).hexdigest()
    with pytest.raises(ValueError,match='dimensions'):verify(fixture)


def test_changed_pinned_bytes_and_nonfinite_tensor(fixture):
    expected,artifacts,weights=fixture
    with pytest.raises(ValueError,match='tensor slice digest'):
        verify((expected,artifacts,weights[:-1]+b'\0'))
    weights=pack([float('nan')]+[1]*7)
    expected['slice_sha256']=hashlib.sha256(weights).hexdigest()
    with pytest.raises(ValueError,match='Nonfinite'):verify((expected,artifacts,weights))
    expected['input_sha256']='0'*64
    with pytest.raises(ValueError):verify(fixture)


def test_fixed_tolerance_checks_every_retained_region(fixture):
    fixture[1]['output.f32']=pack([8,-8,8,-8,8.00005,-8])
    assert verify(fixture)['status']=='verified'
    fixture[1]['output.f32']=pack([8,-8,8,-8,8.001,-8])
    assert verify(fixture)['status']=='failed'


def test_python_single_region_and_native_calibration(fixture):
    expected,artifacts,weights=fixture
    expected['samples']=0
    meta=json.loads(artifacts['replay.json']);meta['samples']=0
    artifacts['replay.json']=json.dumps(meta).encode();artifacts['output.f32']=pack([8,-8])
    assert verify(fixture)['vectors_checked']==1
    expected['input_kind']='calibration_mod17';meta['input_kind']='calibration_mod17'
    artifacts['replay.json']=json.dumps(meta).encode()
    with pytest.raises(ValueError,match='calibration input'):verify(fixture)


def test_host_uses_task_admission_and_retained_artifacts(tmp_path,monkeypatch,fixture):
    expected,artifacts,weights=fixture
    model=tmp_path/'model';model.write_bytes(b'padding12345'+weights)
    contract=tmp_path/'contract.json';contract.write_text(json.dumps({'model':{'path':str(model)}}))
    with Store(tmp_path/'store') as store:
        store.create_task(dict(task_id='t',objective='CPU replay fixture',contract_id=str(contract),constraints={
            'baseline_numerical_replay':expected,'benchmark_contract_sha256':hashlib.sha256(contract.read_bytes()).hexdigest()}))
        attempt=store.create_attempt('t',dict(kind='lab',idem_key='fixture',fingerprint='fixture',request={'adapter':'factory-experiment-v1'}))
        aid=attempt['attempt_id'];refs=[]
        for name,raw in dict(artifacts,**{'result.json':json.dumps(dict(status='succeeded',execution_outcome='ok',evidence_completeness='complete',artifact_copy_returncode=0,cleanup={'container_removed':True})).encode()}).items():
            ref=aid+(':' if name=='result.json' else ':artifacts/')+name
            store.put_artifact('t',ref,raw,'application/octet-stream',aid);refs.append(ref)
        metadata(store,attempt,result_refs=refs)
        store.transition_attempt('t',aid,'running');store.transition_attempt('t',aid,'succeeded')
        monkeypatch.setattr(Jobs,'status',lambda self,ident:self._get(ident))
        report=verify_attempt(store,'t',aid)
        assert report['status']=='verified' and report['admission_verified']
        assert report['task_id']=='t' and report['attempt_id']==aid
        # Mutable producer spool is irrelevant; retained bytes are authoritative.
        spool=store.home/'experiment-spool'/aid;spool.mkdir(parents=True)
        (spool/'replay.json').write_text('{}')
        assert verify_attempt(store,'t',aid)['status']=='verified'
        model.write_bytes(b'padding12345'+pack([99]*8))
        assert verify_attempt(store,'t',aid)['status']=='unverified'
        model.write_bytes(b'padding12345'+weights)
        artifact=store.read('t',aid+':artifacts/output.f32')
        (store.home/artifact['location']).write_bytes(pack([99]*6))
        assert verify_attempt(store,'t',aid)['status']=='unverified'
        store.create_task(dict(task_id='old',objective='Historical flags are not proof'))
        assert verify_attempt(store,'old','unused')['status']=='unverified'


def test_portable_capability_pins_and_scope(tmp_path,fixture):
    expected,artifacts,weights=fixture
    model=tmp_path/'model';model.write_bytes(b'padding12345'+weights)
    for name,raw in artifacts.items():(tmp_path/name).write_bytes(raw)
    pins={name:hashlib.sha256(raw).hexdigest() for name,raw in artifacts.items()}
    report=replay.verify_vectors(str(model),str(tmp_path),expected,pins)
    assert report['status']=='verified' and report['admission_verified'] is False
    (tmp_path/'output.f32').write_bytes(pack([99]*6))
    with pytest.raises(ValueError,match='digest'):replay.verify_vectors(str(model),str(tmp_path),expected,pins)


def test_native_calibration_reference_recomputed_from_pinned_input(fixture):
    expected,artifacts,weights=fixture
    x=pack([(k-8)/17 for k in range(4)])
    values=struct.unpack('<4f',x)
    reference=sum((k+1)*v for k,v in enumerate(values))
    expected.update(input_kind='calibration_mod17',input_sha256=hashlib.sha256(x).hexdigest())
    meta=json.loads(artifacts['replay.json']);meta['input_kind']='calibration_mod17'
    artifacts.update({'replay.json':json.dumps(meta).encode(),'input.f32':x,
        'reference.f64':pack([reference,-reference],'d'),'output.f32':pack([reference,-reference]*3)})
    assert verify(fixture)['status']=='verified'


def test_sealed_cc_invokes_portable_verifier(tmp_path,fixture):
    from jiuwenswarm.ccv2.ccv2 import Host
    expected,artifacts,weights=fixture
    model=tmp_path/'model';model.write_bytes(b'padding12345'+weights)
    for name,raw in artifacts.items():(tmp_path/name).write_bytes(raw)
    host=Host(tmp_path/'ccstore',session_grants=['process.exec'])
    release=host.prepare(Path(__file__).resolve().parents[2]/'jiuwenswarm/factory/ccs/performance_baseline')
    receipt=host.call(release,'verify_vectors',dict(weights_path=str(model),replay_root=str(tmp_path),expected=expected,
        artifact_sha256={n:hashlib.sha256(raw).hexdigest() for n,raw in artifacts.items()}),key='replay')
    assert receipt['state']=='succeeded', receipt
    assert receipt['outputs']['result']['status']=='verified'
    assert receipt['outputs']['result']['admission_verified'] is False


@pytest.mark.parametrize('key,value',[('shape',[4097,4]),('shape',[2,262145]),('samples',32),('repeats',True)])
def test_bounds_fail_before_reading_tensor(fixture,key,value):
    expected,artifacts,_=fixture
    expected[key]=value
    meta=json.loads(artifacts['replay.json']);meta[key]=value
    artifacts['replay.json']=json.dumps(meta).encode()
    with pytest.raises(ValueError,match='bound'):
        replay.verify(expected,artifacts.__getitem__,lambda *args:pytest.fail('Must not read oversized tensor'))
