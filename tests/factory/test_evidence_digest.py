"""Exact JSON selection, task isolation and an actual native Host call."""
import hashlib
import json
from pathlib import Path
import sys
import pytest
from jiuwenswarm.factory import evidence_digest as digest
from jiuwenswarm.factory.api import dispatch
from jiuwenswarm.factory.store import NotFound, ScopeDenied


def put(store, identity, value, task='t', raw=None):
    return store.put_artifact(task,identity,raw if raw is not None else json.dumps(value).encode(),'application/json',None)

def project(store, pointers, identity='source', **options):
    return digest.dispatch(store.scoped('t'),'t','project',{'sources':[{'artifact_id':identity,'pointers':pointers}],**options})['result']

def test_exact_projection_index_and_provenance(store):
    original={'a/b':{'~key':[1,False,None,{'text':'é'}]},'limitations':['CPU only'],'large':'x'*1000}
    record=put(store,'source',original)
    result=project(store,['/a~1b/~0key/3','/limitations'])
    source=result['sources'][0]
    assert source['selections'][0]['value']==original['a/b']['~key'][3]
    assert source['selections'][1]['value']==original['limitations']
    assert source['source_sha256']==record['sha256']
    assert source['omitted_top_level_keys']==['large']
    assert source['parsed_values_exact'] and not source['original_json_lexemes_preserved']
    indexed=dispatch(store.scoped('t'),'t','evidence_digest.index',{'inputs':{'artifact_ids':['source']}})['result']
    assert indexed['sources'][0]['top_level_fields']['large']=={'type':'string','utf8_bytes':1000}
    assert 'x'*100 not in json.dumps(indexed)

@pytest.mark.parametrize('pointer',['/missing','/a~2b','/array/01','/array/-','/array/9','/scalar/next'])
def test_missing_and_malformed_pointers(store,pointer):
    put(store,'source',{'array':[1],'scalar':0})
    with pytest.raises(ValueError):project(store,[pointer])

@pytest.mark.parametrize('raw',[b'{',b'{"a":NaN}',b'{"a":Infinity}',b'{"a":1e309}',b'{"a":1,"a":2}',b'\xff'])
def test_strict_json(store,raw):
    put(store,'source',None,raw=raw)
    with pytest.raises(ValueError):project(store,[''])

def test_bounds_unknown_and_cross_task(store):
    put(store,'source',{'large':'x'*65536})
    with pytest.raises(ValueError,match='output byte bound'):project(store,['/large'])
    with pytest.raises(ValueError):project(store,['/large'],max_output_bytes=1)
    with pytest.raises(ValueError):project(store,['/large']*33)
    with pytest.raises(NotFound):project(store,[''],'unknown')
    store.create_task({'task_id':'other','objective':'isolation'})
    put(store,'foreign',{'secret':True},task='other')
    with pytest.raises(NotFound):project(store,[''],'foreign')
    with pytest.raises(ScopeDenied):
        digest.dispatch(store.scoped('t',{'other'}),'other','index',{'artifact_ids':['foreign']})
    with pytest.raises(ValueError):
        digest.dispatch(store.scoped('t'),'t','index',{'artifact_ids':['source'],'task_id':'other'})
    put(store,'huge',None,raw=b' '* (digest.MAX_SOURCE_BYTES+1))
    with pytest.raises(ValueError,match='source byte bound'):project(store,[''],'huge')

def test_actual_host(store,tmp_path,monkeypatch):
    from jiuwenswarm.ccv2.ccv2 import Host
    put(store,'source',{'exact':{'value':3},'limitations':['fixture only']})
    monkeypatch.setenv('FACTORY_HOME',str(store.home))
    monkeypatch.setenv('FACTORY_TASK_ID','t')
    monkeypatch.setenv('FACTORY_PYTHON',sys.executable)
    bundle=Path(__file__).resolve().parents[2]/'jiuwenswarm/factory/ccs/evidence_digest_lab'
    host=Host(tmp_path/'ccstore',python=sys.executable)
    release=host.prepare(bundle)
    receipt=host.call(release,'project',{'sources':[{'artifact_id':'source','pointers':['/exact','/limitations']}]},grants=['process.exec'])
    assert receipt['state']=='succeeded',receipt
    assert receipt['outputs']['result']['sources'][0]['selections'][0]['value']=={'value':3}

def test_cardinality_depth_and_serialized_bounds(store):
    put(store,'keys',{str(i):None for i in range(129)})
    with pytest.raises(ValueError,match='key cardinality'):project(store,[''],'keys')
    with pytest.raises(ValueError,match='1..8'):
        digest.dispatch(store.scoped('t'),'t','index',{'artifact_ids':['x']*9})
    with pytest.raises(ValueError,match='serialized input'):
        digest.dispatch(store.scoped('t'),'t','index',{'artifact_ids':['x'*65536]})
    with pytest.raises(ValueError,match='depth'):
        digest.project_document(b'['*65+b'0'+b']'*65,'deep',[''])
    with pytest.raises(ValueError,match='node'):
        digest.project_document(b'['+b','.join([b'0']*100001)+b']','nodes',[''])

def test_project_rejects_null_pointers_and_undeclared_fields(store):
    put(store,'source',{'a':1})
    for invalid in [None,[],True,'/a']:
        with pytest.raises(ValueError):project(store,invalid)
    with pytest.raises(ValueError):
        digest.dispatch(store.scoped('t'),'t','project',{'sources':[{'artifact_id':'source','pointers':['/a'],'path':'/tmp'}]})
