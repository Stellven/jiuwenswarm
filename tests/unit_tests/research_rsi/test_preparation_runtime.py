"""Controlled custodian facade tests; no operational calibration or keys."""
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

from jiuwenswarm.research_rsi import preparation_runtime as runtime
from jiuwenswarm.research_rsi.records import RecordStore,encoded


def fixture(tmp_path,monkeypatch,operation,parameters,*,objects=()):
    records=tmp_path/'private';records.mkdir()
    inputs=tmp_path/'inputs';inputs.mkdir()
    public=tmp_path/'approved-import';public.mkdir()
    mapping={'/custodian/private':records,'/custodian/inputs':inputs,'/approved/public':public,
             '/protected/signing-key':tmp_path/'key'}
    monkeypatch.setattr(runtime,'_identity',lambda:None)
    monkeypatch.setattr(runtime,'_private_root',lambda value:mapping[value])
    monkeypatch.setattr(runtime,'_path',lambda value:mapping.get(str(value),Path(value)))
    monkeypatch.setattr(runtime,'require_custodian_store',lambda store:store)
    for module in ('targets.ranking_preparation','calibration','calibration_materials'):
        imported=__import__('jiuwenswarm.research_rsi.'+module,fromlist=['require_custodian_store'])
        monkeypatch.setattr(imported,'require_custodian_store',lambda store:store)
    request={'schema':'ai4r-rsi-preparation-request:1','operation':operation,'parameters':parameters}
    raw=encoded(request);pin={'id':'root-approved:opaque-request','sha256':hashlib.sha256(raw).hexdigest()}
    originals={encoded(pin):raw}
    refs=[pin]
    for original,data in objects:
        originals[encoded(original)]=data;refs.append(original)
    reads=[]
    def read(self,reference):reads.append(reference);return originals[encoded(reference)]
    monkeypatch.setattr(runtime.PublicBytes,'read',read)
    config={'schema':'ai4r-rsi-preparation-service:1','record_root':'/custodian/private',
        'approved_request_refs':[pin],'approved_plan_refs':[],'approved_preparation_refs':[],
        'public_roots':['/approved/public'],'public_original_refs':refs,
        'worker':{'socket_path':'/run/ai4r-rsi-worker/hidden/helper.sock','session_id':'controlled:worker',
            'capability':'C'*64,'requests_root':'/custodian/inputs','profile_refs':[]},
        'signing_key_file':'/protected/signing-key','signer_key_id':'unit:custodian'}
    return dict(config=config,request_ref=pin,records=records,inputs=inputs,public=public,reads=reads,
                request=request,originals=originals)


def pin(raw,name):return {'id':name,'sha256':hashlib.sha256(raw).hexdigest()}


def test_unapproved_request_is_refused_before_private_store_opens(tmp_path,monkeypatch):
    dummy={'id':'plan','sha256':'a'*64}
    f=fixture(tmp_path,monkeypatch,'collect-calibration',{'plan_ref':dummy})
    monkeypatch.setattr(runtime,'RecordStore',lambda *a,**k:pytest.fail('Unapproved request opened writable state'))
    with pytest.raises(runtime.PreparationUnavailable):
        asyncio.run(runtime.execute(f['config'],'collect-calibration',dict(f['request_ref'],sha256='b'*64)))
    assert list(f['records'].iterdir())==[]


def test_actual_identity_and_native_private_store_are_required_before_writes(tmp_path):
    root=tmp_path/'native-private'
    if sys.platform!='linux' or not hasattr(os,'geteuid') or os.geteuid()!=12002:
        with pytest.raises(runtime.PreparationUnavailable):runtime._private_root(root)
        assert not root.exists()
        return
    root.mkdir(mode=0o700)
    assert runtime._private_root(root)==root
    store=RecordStore(root)
    try:assert runtime.require_custodian_store(store) is store
    finally:store.close()


def test_new_preparation_is_not_automatically_approved_for_a_plan(tmp_path,monkeypatch):
    dummy={'id':'unapproved-preparation','sha256':'a'*64}
    parameters={key:dummy for key in ('preparation_ref','review_ref','target_ref','fixture_manifest_ref','session_ref','worker_profile_ref')}
    parameters.update(invocation_wall_s=1,evidence_wall_s=1,wall_s=3600)
    f=fixture(tmp_path,monkeypatch,'plan-calibration',parameters)
    monkeypatch.setattr(runtime,'prepare_calibration_plan',lambda *a,**k:pytest.fail('Preparation was silently root-approved'))
    with pytest.raises(runtime.PreparationUnavailable):asyncio.run(runtime.execute(f['config'],'plan-calibration',f['request_ref']))
    assert f['config']['approved_preparation_refs']==[] and f['config']['approved_plan_refs']==[]


def test_prepare_ranking_imports_exact_opaque_parent_refs_and_returns_no_hidden_bytes(tmp_path,monkeypatch):
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    from jiuwenswarm.research_rsi.targets import ranking_preparation
    source=make_unit_package(tmp_path/'source')
    parent=source['session']['parent_declaration_ref'];body=source['attempt']['parent_ref']
    origin_raw=b'{"origin":"seeded development preparation; review pending"}'
    origin=pin(origin_raw,'root:origin')
    generator_raw=Path(ranking_preparation.__file__).read_bytes();generator=pin(generator_raw,'root:generator')
    params={'parent_ref':body,'parent_declaration_ref':parent,'author':'unit:fixture-author',
        'origin_ref':origin,'generator_ref':generator,'prior_preparation_refs':[],
        'populations':{'development':12,'hidden_loop':20,'hidden_final':20,'platform':12},'max_rows':3,'seed':'private-unit-seed-0123456789'}
    objects=[(parent,source['store'].read_blob(parent)),(body,source['store'].read_blob(body)),
             (origin,origin_raw),(generator,generator_raw)]
    source['store'].close()
    f=fixture(tmp_path,monkeypatch,'prepare-ranking',params,objects=objects)
    result=asyncio.run(runtime.execute(f['config'],'prepare-ranking',f['request_ref']))
    assert set(result)=={'status','preparation_ref'} and result['status']=='PREPARED_REVIEW_REQUIRED'
    assert not any(word in json.dumps(result) for word in ('private_seed','partitions','case:','hidden_final'))
    store=RecordStore(f['records'])
    try:
        preparation=store.get(result['preparation_ref'])
        assert preparation['status']=='PENDING_REVIEW_AND_CALIBRATION'
        assert preparation['parent_ref']==body and preparation['parent_declaration_ref']==parent
        assert store.read(parent)==objects[0][1]
        assert len(preparation['partitions']['hidden_final'])==20
    finally:store.close()
    assert f['reads']==f['config']['public_original_refs']
    assert list(f['public'].iterdir())==[] and not (tmp_path/'key').exists()


def test_operation_substitution_and_extra_request_fields_are_rejected(tmp_path,monkeypatch):
    dummy={'id':'plan','sha256':'a'*64}
    f=fixture(tmp_path,monkeypatch,'collect-calibration',{'plan_ref':dummy,'factory':'caller.module'})
    with pytest.raises(ValueError):asyncio.run(runtime.execute(f['config'],'collect-calibration',f['request_ref']))
    # The same approved bytes cannot be dispatched under another finite verb.
    f['request']['parameters'].pop('factory')
    raw=encoded(f['request']);changed=pin(raw,'root-approved:second-opaque-request')
    f['config']['approved_request_refs']=[changed];f['config']['public_original_refs']=[changed]
    f['originals'][encoded(changed)]=raw
    with pytest.raises(ValueError):asyncio.run(runtime.execute(f['config'],'prepare-materials',changed))


def test_materials_bundle_contains_only_the_existing_explicit_public_projection(tmp_path,monkeypatch):
    plan={'id':'plan','sha256':'a'*64};raw=b'controlled public helper';body=pin(raw,'public:body')
    f=fixture(tmp_path,monkeypatch,'prepare-materials',{'plan_ref':plan,'parent_body_refs':{'helper.py':body}})
    monkeypatch.setattr(runtime,'_plan',lambda *a:(None,None))
    monkeypatch.setattr(runtime,'prepare_calibration_materials',lambda *a,**k:({'ref':body,'bytes':raw},))
    result=asyncio.run(runtime.execute(f['config'],'prepare-materials',f['request_ref']))
    assert set(result)=={'status','materials_ref'}
    store=RecordStore(f['records'])
    try:
        bundle=store.get(result['materials_ref'])
        assert set(bundle)=={'schema','materials'} and len(bundle['materials'])==1
        assert bundle['materials'][0]['ref']==body
        assert base64.b64decode(bundle['materials'][0]['bytes_base64'],validate=True)==raw
    finally:store.close()
    assert list(f['public'].iterdir())==[]


def test_collection_without_actual_installed_qualification_never_opens_worker_client(tmp_path,monkeypatch):
    from jiuwenswarm.research_rsi import security_installation
    plan={'id':'plan','sha256':'a'*64}
    f=fixture(tmp_path,monkeypatch,'collect-calibration',{'plan_ref':plan})
    monkeypatch.setattr(runtime,'_plan',lambda *a:({},(None,{},None,None,None)))
    monkeypatch.setattr(security_installation,'installed_consumer_qualification',lambda *a,**k:None)
    monkeypatch.setattr(runtime,'WorkerClient',lambda **k:pytest.fail('Missing IF015 authority dispatched a worker'))
    with pytest.raises(runtime.PreparationUnavailable):
        asyncio.run(runtime.execute(f['config'],'collect-calibration',f['request_ref']))
    assert list(f['inputs'].iterdir())==[]


def test_forged_calibration_counts_are_not_persisted_as_signed_or_frozen(tmp_path,monkeypatch):
    from jiuwenswarm.research_rsi.signing import Signer
    from jiuwenswarm.research_rsi.targets import ranking_preparation
    parameters={'plan_ref':{'id':'plan','sha256':'a'*64},'collection_ref':{'id':'collection','sha256':'b'*64},
                'template_ref':{'id':'template','sha256':'c'*64}}
    f=fixture(tmp_path,monkeypatch,'verify-freeze',parameters)
    store=RecordStore(f['records'])
    base=store.put({'unit':'private context'})
    proposal=store.put({'schema':'ai4r-rsi-calibration:2','preparation_ref':base,'review_ref':base,
        'known_bad_rejected':10,'known_good_qualified':3,'measurable_headroom':True})
    collection={'schema':'ai4r-rsi-calibration-collection-result:1','status':'UNSIGNED_REVIEW_REQUIRED',
        'plan_ref':parameters['plan_ref'],'proposal_ref':proposal,'exposure_ref':base,'capture_refs':[]}
    parameters['collection_ref']=store.put(collection)
    parameters['template_ref']=store.put({'unit':'template'})
    store.close()
    request=dict(f['request'],parameters=parameters);raw=encoded(request);request_ref=pin(raw,'root-approved:freeze')
    f['config']['approved_request_refs']=[request_ref];f['config']['public_original_refs']=[request_ref]
    f['originals'][encoded(request_ref)]=raw
    plan={'fixture_identity':'controlled:fixture','expected_invocations':123,'preparation_ref':base,'review_ref':base}
    target={'parent_ref':base}
    monkeypatch.setattr(runtime,'_plan',lambda *a:(plan,(None,target,{},None,None)))
    class Ledger:
        def __init__(self,*a):pass
        def lookup(self,*a):return {'state':'complete','result_ref':parameters['collection_ref'],'started':123,'expected':123}
        def close(self):pass
    monkeypatch.setattr(runtime,'CalibrationLedger',Ledger)
    monkeypatch.setattr(ranking_preparation,'draft_target',lambda *a,**k:(target,{}))
    signer=Signer.generate('unit:custodian')
    class Installation:
        public_key=signer.public_bytes();key_id=signer.key_id
    class Authority:installation=Installation()
    monkeypatch.setattr(runtime,'_qualification',lambda store:Authority())
    monkeypatch.setattr(runtime,'_guard',lambda *a:None)
    monkeypatch.setattr(runtime,'_signer',lambda cfg:signer)
    signed=[];original_put=RecordStore.put
    def put(self,value):
        if isinstance(value,dict) and 'signature' in value:signed.append(value)
        return original_put(self,value)
    monkeypatch.setattr(RecordStore,'put',put)
    monkeypatch.setattr(runtime,'freeze_prepared_target',lambda **k:pytest.fail('Unverified source-only counts froze a target'))
    with pytest.raises(ValueError):asyncio.run(runtime.execute(f['config'],'verify-freeze',request_ref))
    assert signed==[]


def test_default_cli_refuses_wrong_identity_and_keeps_private_error_details_out(capsys,monkeypatch):
    monkeypatch.setattr(runtime,'load_config',lambda:(_ for _ in ()).throw(ValueError('PRIVATE-SEED-AND-PATH')))
    assert runtime.main(['collect-calibration','--request-ref','{"id":"plan","sha256":"'+'a'*64+'"}'])==2
    output=capsys.readouterr().out
    assert json.loads(output)['status']=='BLOCKED' and 'PRIVATE-SEED-AND-PATH' not in output
