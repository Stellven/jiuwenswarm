"""Whole-package startup and private database snapshot mechanics, no inference."""
import hashlib
import json
from pathlib import Path
import sqlite3
import pytest
from deploy.m1 import rsi_capsule_run as runner
from jiuwenswarm.research_rsi.capsule_doctor import database_fact, snapshot, tree_fact


def test_research_rsi_only_overlay_is_rejected_before_import(tmp_path,monkeypatch):
    monkeypatch.setattr(runner,'protected',lambda path,**kwargs:Path(path))
    pins={'jiuwenswarm/research_rsi/'+name:'a'*64 for name in (
        '__init__.py','capsule_session.py','records.py','diagnosis.py','proposer.py','profiles.py',
        'process_policy.py','session_policy.py','fixed_resources.py','native_lease.py','capsule_doctor.py',
        'targets/capsules.py','targets/capsule_runtime.py','targets/capsule_executor.py')}
    with pytest.raises(ValueError,match='COMPLETE_CAPSULE_PACKAGE_CLOSURE_REQUIRED'):
        runner.load_sources({'source_root':str(tmp_path),'source_pins':pins})


def test_doctor_receipt_is_bound_to_whole_composition_without_hash_cycle(tmp_path,monkeypatch):
    monkeypatch.setattr(runner,'protected',lambda path,**kwargs:Path(path))
    value={'schema':runner.SCHEMA,'session':{'id':'future-distinct-run'},
        'composition':{'core_root':'/original/core'},'evaluator':{'manifest':{'python':{'version':[3,12,15],'executable_sha256':'f'*64}}},'source_pins':{'jiuwenswarm/research/local_model_codex.py':'a'*64},
        'compatibility':{'path':str(tmp_path/'doctor.json'),'sha256':None}}
    scope=runner.compose_doctor_scope(value)
    proof={'schema':'ai4r-rsi-capsule-compose-doctor:1','scope_sha256':scope,'status':'COMPATIBLE',
        'actual_frozen_compose_completed':True,'originals_unchanged':True,
        'model_calls':0,'tool_calls':0,'execution_jobs':0,'work_claims':0,'native_starts':0,
        'python':{'version':[3,12,15],'executable_sha256':'f'*64}}
    raw=json.dumps(proof).encode();(tmp_path/'doctor.json').write_bytes(raw)
    value['compatibility']['sha256']=hashlib.sha256(raw).hexdigest()
    assert runner.compose_doctor_scope(value)==scope
    assert runner.require_compose_doctor(value)==proof
    value['source_pins']['jiuwenswarm/research/local_model_codex.py']='b'*64
    with pytest.raises(ValueError,match='ACTUAL_SCOPED_MODEL_FREE_COMPOSE_DOCTOR_REQUIRED'):
        runner.require_compose_doctor(value)


def test_snapshot_preserves_original_rows_and_blobs_while_copy_is_writable(tmp_path):
    original=tmp_path/'original';(original/'state').mkdir(parents=True)
    (original/'artifacts').mkdir();(original/'artifacts/blob').write_bytes(b'exact retained source')
    db=sqlite3.connect(original/'state/research.sqlite3')
    db.execute('CREATE TABLE attempts(id TEXT PRIMARY KEY,state TEXT)')
    db.execute("INSERT INTO attempts VALUES('historical','completed')");db.commit();db.close()
    before={'tree':tree_fact(original),'db':database_fact(original/'state/research.sqlite3')}
    copied=snapshot(original,tmp_path/'scratch','state/research.sqlite3')
    assert database_fact(copied/'state/research.sqlite3')==before['db']
    db=sqlite3.connect(copied/'state/research.sqlite3')
    db.execute("INSERT INTO attempts VALUES('scratch-only','prepared')");db.commit();db.close()
    (copied/'artifacts/blob').write_bytes(b'scratch-only alteration')
    assert {'tree':tree_fact(original),'db':database_fact(original/'state/research.sqlite3')}==before


def test_doctor_drops_identity_before_every_private_path_operation(monkeypatch):
    # Model the worker's Root without DAC_OVERRIDE: even lstat/is_symlink on a
    # private parent must fail before the permanent controller identity drop.
    import stat
    from types import SimpleNamespace
    from jiuwenswarm.research_rsi import capsule_doctor as module
    state={'uid':0,'gid':0,'groups':[],'accesses':0}
    def access():
        assert state['uid']==state['gid']==12001 and state['groups']==[13000]
        state['accesses']+=1
    class PrivatePath:
        def __init__(self,value):self.value=value
        @property
        def parents(self):access();return ()
        def is_absolute(self):access();return True
        def is_symlink(self):access();return False
        def stat(self):access();return SimpleNamespace(st_mode=stat.S_IFDIR|0o700,st_uid=12001)
        def iterdir(self):access();return iter(())
    fake_os=SimpleNamespace(name='posix',ST_RDONLY=1,geteuid=lambda:state['uid'],getuid=lambda:state['uid'],
        getgroups=lambda:state['groups'],setgroups=lambda values:state.update(groups=values),
        setgid=lambda value:state.update(gid=value),setuid=lambda value:state.update(uid=value),
        statvfs=lambda path:(access() or SimpleNamespace(f_flag=1)))
    monkeypatch.setattr(module,'os',fake_os)
    monkeypatch.setattr(module,'Path',PrivatePath)
    def reached_snapshot(path):
        access();raise RuntimeError('REACHED_SNAPSHOT_AFTER_DROP')
    monkeypatch.setattr(module,'tree_fact',reached_snapshot)
    value={'composition':{key:'/private/'+key for key in (
        'core_root','input_root','record_root','native_lease_root','account_root')}}
    with pytest.raises(RuntimeError,match='REACHED_SNAPSHOT_AFTER_DROP'):
        module.doctor(value,None,'/private/scratch',scope_sha256='a'*64)
    assert state['accesses']>10


def test_snapshot_preserves_absent_fresh_index_until_scratch_store_initializes(tmp_path):
    from jiuwenswarm.research_rsi.records import RecordStore
    original=tmp_path/'fresh-native-leases';original.mkdir()
    assert database_fact(original/'index.sqlite')=={'present':False,'tables':{}}
    copied=snapshot(original,tmp_path/'scratch-native-leases','index.sqlite')
    assert not (original/'index.sqlite').exists() and not (copied/'index.sqlite').exists()
    scratch=RecordStore(copied)
    try:
        assert all(row['count']==0 for row in database_fact(copied/'index.sqlite')['tables'].values())
        assert not (original/'index.sqlite').exists()
    finally:scratch.close()


def test_private_snapshot_retains_uncheckpointed_wal_rows(tmp_path):
    original=tmp_path/'live';original.mkdir()
    path=original/'index.sqlite'
    db=sqlite3.connect(path)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA wal_autocheckpoint=0')
    db.execute('CREATE TABLE evidence(value TEXT)')
    db.execute("INSERT INTO evidence VALUES('committed-in-wal')");db.commit()
    before={p.name:p.read_bytes() for p in original.iterdir()}
    try:
        fact=database_fact(path)
        assert fact['tables']['evidence']['count']==1
        copied=snapshot(original,tmp_path/'copy','index.sqlite')
        assert database_fact(copied/'index.sqlite')==fact
        assert {p.name:p.read_bytes() for p in original.iterdir()}==before
    finally:db.close()


def test_capsule_frames_retain_coalesced_records_and_bound_each_frame(monkeypatch):
    import os,time
    if os.name=='nt':
        # Windows select supports sockets only; production uses Linux pipes.
        monkeypatch.setattr(runner.select,'select',lambda readable,*args:(readable,[],[]))
    read_fd,write_fd=os.pipe()
    with os.fdopen(read_fd,'rb') as incoming,os.fdopen(write_fd,'wb') as outgoing:
        outgoing.write(b'{"capture":1}\n{"capture":2}\n{"evaluation":3}\n');outgoing.flush()
        deadline=time.monotonic()+1
        assert runner.read_frame_deadline(incoming,deadline)=={'capture':1}
        assert runner.read_frame_deadline(incoming,deadline)=={'capture':2}
        assert runner.read_frame_deadline(incoming,deadline)=={'evaluation':3}
    monkeypatch.setattr(runner,'MAX_PIPE_FRAME',8)
    read_fd,write_fd=os.pipe()
    with os.fdopen(read_fd,'rb') as incoming,os.fdopen(write_fd,'wb') as outgoing:
        outgoing.write(b'{"too_long":true}\n');outgoing.flush()
        with pytest.raises(ValueError,match='PIPE_FRAME_TOO_LARGE'):
            runner.read_frame_deadline(incoming,time.monotonic()+1)
