"""Synthetic import controls, not model measurements or qualification evidence."""
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

SOURCE=Path(__file__).resolve().parents[3]/'deploy/m1/rsi_development_seed.py'
spec=importlib.util.spec_from_file_location('development_seed_test_owner',SOURCE)
seed=importlib.util.module_from_spec(spec);spec.loader.exec_module(seed)
pytestmark=pytest.mark.skipif(os.name!='posix' or os.geteuid()!=0,reason='Linux disposable Root fixture only')


@pytest.fixture(autouse=True)
def private_tmp_ancestry(tmp_path,monkeypatch):
    """Production rejects /tmp; retain its file checks inside private unit root."""
    import stat
    def protected(path,owner=0,*,directory=False,maximum=seed.MAX_FILE):
        path=Path(path);assert path.is_relative_to(tmp_path)
        for current in (path,*path.parents):
            if current==tmp_path.parent:break
            m=current.lstat()
            seed.need(not stat.S_ISLNK(m.st_mode) and m.st_uid in {0,owner}
                      and not m.st_mode&0o022,'UNPROTECTED_PATH_ANCESTRY')
        m=path.stat();seed.need(m.st_uid==owner and (stat.S_ISDIR(m.st_mode) if directory else
            stat.S_ISREG(m.st_mode) and m.st_nlink==1 and m.st_size<=maximum),'PROTECTED_PATH_CUSTODY_DIFFERS')
        return path
    monkeypatch.setattr(seed,'protected',protected)


def owned(root):
    for path in [root,*root.rglob('*')]:
        os.chown(path,12001,12001)
        path.chmod(0o700 if path.is_dir() else 0o600)


@pytest.fixture
def captured(tmp_path,monkeypatch):
    """Real canonical corpus/registration; explicitly synthetic measured rows."""
    from jiuwenswarm.research.state import SQLiteRunStore,json_bytes
    from jiuwenswarm.research.library import LibraryService
    from jiuwenswarm.research.contracts import Principal
    from jiuwenswarm.research.catalog_calibration import capture_catalog_calibration
    from jiuwenswarm.research.checks.calibration_runtime import prepare_calibration_checks
    from jiuwenswarm.research.checks import CheckRegistry
    root=tmp_path/'root';root.mkdir();(root/'config').mkdir()
    source=root/'source';source.mkdir();core=source/'core'
    store=SQLiteRunStore(core);library=LibraryService(store)
    actor=Principal('synthetic-owner',operations=frozenset({'verifier_assets','library_admit','library_standing'}))
    controls={key:store.put_blob(json_bytes({'synthetic_control':key})) for key in
              ('configuration_ref','model_selection_profile_ref','deployment_ref')}
    generated=asyncio.run(capture_catalog_calibration(store,**controls))
    assets=asyncio.run(prepare_calibration_checks(store,CheckRegistry()))
    selected={**controls,'calibration_runtime_ref':generated['runtime_ref'],'stages':[]}
    profiles={}
    for pin in generated['profile_refs']:
        profile=store.read_record(pin);stage=profile['id'].split(':')[1]
        if stage in ('intent','verifier'):profiles[stage]=(pin,profile)
    library.check_assets.bind_calibration_runtime(generated['runtime_ref'],**controls)
    for stage,(pin,profile) in profiles.items():
        asset=assets[stage]
        library.associate_checks(asset['declaration_ref'],asset['bundle_ref'],asset['profile_ref'],actor)
        registration=library.check_assets.register_profile(pin,actor)
        closure=library.check_assets.closure(asset['bundle_ref'],asset['profile_ref'])
        measured=[]
        for case in profile['cases']:
            receipt=store.append_record('calibration-measurement',{
                'id':'synthetic-measurement:'+case['case_id'],'profile_ref':pin,
                'registration_ref':registration,'case_id':case['case_id'],'asset_kind':case['asset_kind'],
                'result':None,'status':'matched','reason_code':None,'recorded_at':'2020-01-01T00:00:00Z'})
            measured.append(receipt)
            with store.transaction() as db:db.execute('INSERT INTO calibration_attempts VALUES(?,?,?,?)',
                (pin['sha256'],case['case_id'],'matched',json_bytes(receipt).decode()))
        for kind in ('bundle','criteria'):
            receipt=store.append_record('checking-asset-admission',{
                'id':'synthetic-admission:'+stage+':'+kind,'asset_kind':kind,
                'asset_ref':profile['bundle_ref' if kind=='bundle' else 'profile_ref'],
                'admission_policy':'ai4r-check-admission:monotonic-private:1',
                'calibration_profile_ref':pin,'registration_ref':registration,'closure':closure,
                'measurement_refs':measured,'status':'admitted','reasons':[],
                'actor':actor.account_id,'recorded_at':'2020-01-01T00:00:00Z'})
            with store.transaction() as db:db.execute('INSERT INTO checking_asset_admissions VALUES(?,?,?,?)',
                (seed.digest(json_bytes(closure)),kind,pin['sha256'],json_bytes(receipt).decode()))
        admission=asyncio.run(library.admit(asset['declaration_ref'],asset['body_refs'],actor,memory_mb=512))
        assert store.read_record(admission)['status']=='admitted'
        declaration=store.read_record(asset['declaration_ref'])
        library.set_standing(declaration['identity']['name'],declaration['identity']['version_label'],'active',actor,reason='Synthetic fixture only')
        selected['stages'].append({'stage':stage,'declaration_ref':asset['declaration_ref'],'profile_ref':pin})
    selected['binding_ref']=store.put_blob(json_bytes({**controls,'protected_options':{
        'development_builtin_catalog':False,'calibration_runtime_ref':generated['runtime_ref']}}))
    store.close();owned(source)
    monkeypatch.setattr(seed,'ROOT',root);monkeypatch.setattr(seed,'SOURCE',source)
    monkeypatch.setattr(seed,'observe_originals',lambda value:(selected,{'synthetic_original_guard':'unchanged'}))
    work={row['stage']:row['declaration_ref'] for row in selected['stages']}
    return root,source,selected,work


def test_typed_import_preserves_both_real_checking_closures_without_other_profiles(captured):
    _,source,selected,work=captured
    before=seed.digest((source/'core/state/research.sqlite3').read_bytes())
    reader=seed.SourceReader(source/'core')
    try:data=seed.collect(reader,selected,work)
    finally:reader.close()
    assert len(data['tables']['library_versions'])==2
    assert len(data['tables']['calibration_profiles'])==2
    assert len(data['tables']['checking_asset_admissions'])==4
    assert len(data['tables']['calibration_attempts'])==24
    assert len(data['artifacts'])<200
    assert not any(row['kind'].startswith('model-') for row in data['records'])
    assert any(row['kind']=='calibration-material' for row in data['records'])
    assert [row['rowid'] for row in data['records']]==sorted(row['rowid'] for row in data['records'])
    assert seed.digest((source/'core/state/research.sqlite3').read_bytes())==before


def test_cross_stage_declaration_is_not_an_admitted_intent(captured):
    _,source,selected,work=captured
    work={**work,'intent':work['verifier']};reader=seed.SourceReader(source/'core')
    try:
        with pytest.raises(ValueError,match='CROSS_STAGE'):seed.collect(reader,selected,work)
    finally:reader.close()


@pytest.mark.parametrize('fault',['missing_attempt','unmatched_attempt','missing_admission'])
def test_incomplete_original_eligibility_cannot_seed(captured,fault):
    _,source,selected,work=captured
    import sqlite3
    db=sqlite3.connect(source/'core/state/research.sqlite3')
    if fault=='missing_attempt':db.execute('DELETE FROM calibration_attempts WHERE rowid=(SELECT min(rowid) FROM calibration_attempts)')
    elif fault=='unmatched_attempt':db.execute("UPDATE calibration_attempts SET state='blocked' WHERE rowid=(SELECT min(rowid) FROM calibration_attempts)")
    else:db.execute('DELETE FROM checking_asset_admissions WHERE rowid=(SELECT min(rowid) FROM checking_asset_admissions)')
    db.commit();db.close();reader=seed.SourceReader(source/'core')
    try:
        with pytest.raises(ValueError,match='INCOMPLETE|UNMATCHED|BOTH_ADMISSIONS|CHECK_ADMISSION'):
            seed.collect(reader,selected,work)
    finally:reader.close()


def test_artifact_tamper_is_rejected_before_any_destination(captured):
    _,source,selected,work=captured
    pin=work['intent'];path=source/'core/artifacts/sha256'/pin['sha256'][:2]/pin['sha256'];path.write_bytes(b'{}')
    reader=seed.SourceReader(source/'core')
    try:
        with pytest.raises(ValueError,match='ORIGINAL_HASH'):seed.collect(reader,selected,work)
    finally:reader.close()


def receipt(tmp_path,monkeypatch):
    monkeypatch.setattr(seed,'source_pins',lambda:{'rsi_development_seed.py':seed.digest(SOURCE.read_bytes())})
    value={'schema':seed.COMPLETE_SCHEMA,'id':'unit','plan_sha256':'a'*64,'input_sha256':'b'*64,
        'destination':{key:'/unit/'+key for key in seed.DESTINATION_FIELDS-{'native_scope_ref'}},
        'original_guards':{'unit':'closed'},'imported_historical_ref':{'id':'unit','sha256':'c'*64},
        'row_artifact_pins_sha256':'d'*64,'source_pins':seed.source_pins(),'zero_dispatch':True,
        'recorded_at':'2020-01-01T00:00:00Z'}
    value['destination']['native_scope_ref']={'id':'unit-scope','sha256':'e'*64}
    path=tmp_path/'complete.json';path.write_bytes(seed.encoded(value));path.chmod(0o440)
    return value,{'path':str(path),'sha256':seed.digest(path.read_bytes())}


def test_root_receipt_has_no_old_source_mount_dependency(tmp_path,monkeypatch):
    value,pin=receipt(tmp_path,monkeypatch)
    assert seed.read_completed_seed(pin)==value
    assert not Path('/unit/core_root').exists()


@pytest.mark.parametrize('fault',['bytes','writable','wrong_source','nonzero_dispatch'])
def test_receipt_tamper_does_not_grant_a_seed(tmp_path,monkeypatch,fault):
    value,pin=receipt(tmp_path,monkeypatch);path=Path(pin['path'])
    if fault=='bytes':path.write_bytes(b'{}')
    elif fault=='writable':path.chmod(0o666)
    else:
        if fault=='wrong_source':value['source_pins']['rsi_development_seed.py']='0'*64
        else:value['zero_dispatch']=False
        path.write_bytes(seed.encoded(value));pin['sha256']=seed.digest(path.read_bytes())
    with pytest.raises(ValueError):seed.read_completed_seed(pin)


def test_launch_guard_cannot_substitute_seed_or_unfreeze_bootstrap(tmp_path,monkeypatch):
    value,pin=receipt(tmp_path,monkeypatch)
    guard={'schema':seed.GUARD_SCHEMA,'id':'unit','seed_receipt_sha256':pin['sha256'],
        'source_guards_sha256':seed.digest(seed.encoded(value['original_guards'])),
        'bootstrap_operations_frozen':True,'relay_idle':True,'original_guards':value['original_guards'],
        'source_pins':value['source_pins'],'recorded_at':'2020-01-01T00:00:00Z'}
    path=tmp_path/'guard.json';path.write_bytes(seed.encoded(guard));path.chmod(0o440)
    guard_ref={'path':str(path),'sha256':seed.digest(path.read_bytes())}
    assert seed.read_launch_guard(guard_ref,pin)==guard
    guard['bootstrap_operations_frozen']=False;path.write_bytes(seed.encoded(guard));guard_ref['sha256']=seed.digest(path.read_bytes())
    with pytest.raises(ValueError,match='EXACT_LAUNCH_GUARD'):seed.read_launch_guard(guard_ref,pin)


def test_existing_destination_refuses_seed_replay_before_packet_or_writes(tmp_path,monkeypatch):
    root=tmp_path/'root';root.mkdir();dest=root/'development/unit';dest.mkdir(parents=True)
    monkeypatch.setattr(seed,'ROOT',root)
    value={'schema':seed.INPUT_SCHEMA,'id':'unit','source_namespace':str(seed.SOURCE),
        'selection_directory':str(seed.SELECTION),'selection_completion_sha256':'a'*64,
        'work_capsule_refs':{k:{'id':k,'sha256':'b'*64} for k in ('intent','verifier')},
        'material_packet':{'path':'/unit/packet.json','sha256':'c'*64},'destination_root':str(dest)}
    monkeypatch.setattr(seed,'observe_originals',lambda _:({},{}))
    # A partial or completed existing namespace must fail before collection.
    with pytest.raises(ValueError,match='FRESH_DESTINATION_ALREADY_EXISTS'):seed.snapshot(value)


@pytest.mark.parametrize('fault', [None, 'private_body', 'extra_hidden_ref', 'parent', 'target',
                                  'visible', 'tests', 'qualification', 'campaigns', 'export'])
def test_only_closed_bound_public_preparation_enters_development(fault):
    pin=lambda name: {'id':name,'sha256':hashlib.sha256(name.encode()).hexdigest()}
    packet={key:pin(key) for key in ('parent_declaration_ref','target_profile_ref','visible_context_ref')}
    visible={'required_test_refs':[pin('test')], 'context':{'schema':'public-development-export','cases':[]}}
    value={'schema':'ai4r-rsi-development-public-preparation:1', **packet,
           'required_test_refs':visible['required_test_refs'],'development_export_ref':pin('export'),
           'security_campaigns':'DEFERRED','qualification':False}
    export=copy.deepcopy(visible['context'])
    if fault=='private_body':value={'schema':'ai4r-rsi-private-preparation:1','partitions':{'hidden':pin('hidden')}}
    elif fault=='extra_hidden_ref':value['hidden_fixture_ref']=pin('hidden')
    elif fault in ('parent','target','visible'):value[fault+('_declaration_ref' if fault=='parent' else '_profile_ref' if fault=='target' else '_context_ref')]=pin('foreign')
    elif fault=='tests':value['required_test_refs']=[pin('foreign-test')]
    elif fault=='qualification':value['qualification']=True
    elif fault=='campaigns':value['security_campaigns']='PASS'
    elif fault=='export':export['cases']=[{'hidden':'not disclosed'}]
    if fault is None:
        assert seed.validate_public_preparation(value,packet,visible,export)==value
    else:
        with pytest.raises(ValueError,match='PUBLIC_'):seed.validate_public_preparation(value,packet,visible,export)
