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
    def bind(item):
        raw=json.dumps(item).encode();(tmp_path/'doctor.json').write_bytes(raw)
        value['compatibility']['sha256']=hashlib.sha256(raw).hexdigest()
    # A receipt without a complete derived source closure is refused.
    for closure in (None,{'complete':False,'module_count':3}):
        bind(dict(proof,**({} if closure is None else {'source_closure':closure})))
        with pytest.raises(ValueError,match='COMPOSE_DOCTOR_COMPLETE_SOURCE_CLOSURE_REQUIRED'):
            runner.require_compose_doctor(value)
    proof['source_closure']={'schema':'ai4r-rsi-source-closure:1','complete':True,'module_count':3,
        'resource_count':1,'modules_sha256':'c'*64,'entry_packages':['jiuwenswarm.research_rsi','jiuwenswarm.research']}
    bind(proof)
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


# --- Derived source closure (no hand-maintained file lists) -----------------

ROOT = Path(__file__).resolve().parents[3]


def package_files(root=ROOT):
    return {p.relative_to(root).as_posix() for p in (root / 'jiuwenswarm').rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and 'node_modules' not in p.parts}


def mini(tmp_path, files):
    for name, text in files.items():
        path = tmp_path / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
    pins = {name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() for name in files}
    return pins


def test_complete_actual_package_closure_and_r1_overlay_missing_native_source():
    from jiuwenswarm.research_rsi.capsule_doctor import source_closure
    files = package_files()
    entries = {'entry:rsi_capsule_run.py': (ROOT / 'deploy/m1/rsi_capsule_run.py').read_bytes(),
               'entry:rsi_development_run.py': (ROOT / 'deploy/m1/rsi_development_run.py').read_bytes()}
    read = lambda name: (ROOT / name).read_bytes()
    complete = source_closure(files, read, entry_files=entries)
    assert complete['complete'] and complete['missing'] == [] and complete['module_count'] > 100
    # R1: the overlay lacked the source-relative native qualification helper.
    partial = source_closure(files - {'jiuwenswarm/research/local_model_codex.py'}, read, entry_files=entries)
    assert not partial['complete']
    missing = {row['path']: row['required_by'] for row in partial['missing']}
    assert 'jiuwenswarm/research/local_model_codex.py' in missing
    # A research_rsi-only overlay is reported with exact paths, not accepted.
    overlay = {name for name in files if name.startswith('jiuwenswarm/research_rsi/')} | {'jiuwenswarm/__init__.py'}
    result = source_closure(overlay, read, entry_files=entries, entry_packages=('jiuwenswarm.research_rsi',))
    assert not result['complete'] and any(row['path'].startswith('jiuwenswarm/research/') for row in result['missing'])


def test_static_walk_covers_imports_and_source_relative_resources(tmp_path):
    from jiuwenswarm.research_rsi.capsule_doctor import require_source_closure, source_closure
    files = {
        'jiuwenswarm/__init__.py': '',
        'jiuwenswarm/research/__init__.py': 'from . import a\n',
        'jiuwenswarm/research/a.py': ('from pathlib import Path\nfrom importlib.resources import files\n'
            'import importlib\nfrom .sub import b\nfrom ..data import table\n'
            'try:\n    import jiuwenswarm.optional_missing\nexcept ImportError:\n    pass\n'
            'def lazy():\n    from jiuwenswarm.research.deferred import thing\n'
            '    from jiuwenswarm.research import ghost_name\n'
            "    root = Path(__file__).parents[1]\n    return (root / 'assets/catalog.json').read_bytes()\n"
            "HELPER = Path(__file__).with_name('helper.py').read_text()\n"
            "SCHEMA = files('jiuwenswarm.contracts').joinpath('schemas', 'x.json').read_text()\n"
            "MOD = importlib.import_module('jiuwenswarm.research.dynamic')\n"
            "def probe():\n    p = Path(__file__).parent / 'maybe'\n    return p.exists() and p.read_text()\n"),
        'jiuwenswarm/research/sub/__init__.py': '', 'jiuwenswarm/research/sub/b.py': '',
        'jiuwenswarm/data/__init__.py': '', 'jiuwenswarm/data/table.py': '',
        'jiuwenswarm/research/deferred.py': 'thing = 1\n', 'jiuwenswarm/research/helper.py': '',
        'jiuwenswarm/research/dynamic.py': '', 'jiuwenswarm/assets/catalog.json': '{}',
        'jiuwenswarm/contracts/__init__.py': '', 'jiuwenswarm/contracts/schemas/x.json': '{}'}
    pins = mini(tmp_path, files)
    read = lambda name: (tmp_path / name).read_bytes()
    full = source_closure(pins, read, entry_packages=('jiuwenswarm.research',))
    assert full['complete'], full['missing']
    assert {row['path'] for row in full['optional_missing']} == {'jiuwenswarm/research/maybe', 'jiuwenswarm/optional_missing.py'}
    # A lazy name the package does not bind is reported, not silently passed.
    assert [row['path'] for row in full['unresolved_lazy_names']] == ['jiuwenswarm/research/ghost_name.py']
    for removed in ('jiuwenswarm/research/helper.py', 'jiuwenswarm/assets/catalog.json',
                    'jiuwenswarm/contracts/schemas/x.json', 'jiuwenswarm/research/dynamic.py',
                    'jiuwenswarm/data/table.py', 'jiuwenswarm/research/sub/b.py', 'jiuwenswarm/research/deferred.py'):
        result = source_closure(set(pins) - {removed}, read, entry_packages=('jiuwenswarm.research',))
        assert [row['path'] for row in result['missing']] == [removed], (removed, result['missing'])
    with pytest.raises(ValueError, match='SOURCE_CLOSURE_INCOMPLETE: missing jiuwenswarm/research/helper.py required by jiuwenswarm/research/a.py:'):
        require_source_closure(tmp_path, {k: v for k, v in pins.items() if k != 'jiuwenswarm/research/helper.py'},
                               entry_packages=('jiuwenswarm.research',))
    # Import-time mode (sandbox runtime): function-level edges are deferred.
    eager = source_closure(set(pins) - {'jiuwenswarm/research/deferred.py', 'jiuwenswarm/assets/catalog.json'},
                           read, entry_packages=('jiuwenswarm.research',), eager_only=True)
    assert eager['complete'] and {row['path'] for row in eager['deferred_missing']} == {
        'jiuwenswarm/research/deferred.py', 'jiuwenswarm/assets/catalog.json',
        'jiuwenswarm/research/ghost_name.py', 'jiuwenswarm/research/maybe'}
    changed = dict(pins, **{'jiuwenswarm/research/a.py': '0' * 64})
    with pytest.raises(ValueError, match='SOURCE_PIN_DIFFERS'):
        require_source_closure(tmp_path, changed, entry_packages=('jiuwenswarm.research',))


# --- Worker-identity traversal -----------------------------------------------

def test_static_traversal_reports_first_blocking_component():
    import shutil, tempfile
    from jiuwenswarm.research_rsi.capsule_doctor import static_traversal, static_tree_readable
    base = Path(tempfile.mkdtemp(prefix='static-traversal-'))
    try:
        (base / 'evidence/work/job').mkdir(parents=True)
        for path in (base, base / 'evidence', base / 'evidence/work/job'):
            path.chmod(0o711)
        (base / 'evidence/work').chmod(0o700)
        assert static_traversal([base / 'evidence/work/job'], uid=54321, gid=54321) == {
            'path': str(base / 'evidence/work'), 'target': str(base / 'evidence/work/job'), 'reason': 'not_searchable',
            'mode': '0o700', 'uid': (base / 'evidence/work').stat().st_uid, 'gid': (base / 'evidence/work').stat().st_gid}
        (base / 'evidence/work').chmod(0o711)
        assert static_traversal([base / 'evidence/work/job'], uid=54321, gid=54321) is None
        assert static_traversal([base / 'evidence/absent'], uid=54321, gid=54321)['reason'] == 'missing'
        tree = base / 'tree'; (tree / 'hidden').mkdir(parents=True); (tree / 'hidden/f.py').write_text('x')
        tree.chmod(0o755); (tree / 'hidden').chmod(0o711)
        assert static_tree_readable(tree, uid=54321, gid=54321) == {
            'path': str(tree / 'hidden'), 'target': str(tree), 'reason': 'not_listable'}
    finally:
        shutil.rmtree(base)


@pytest.mark.skipif(not hasattr(__import__('os'), 'geteuid') or __import__('os').geteuid() != 0,
                    reason='simulated traversal needs root to switch to the UID/GID 12003 worker identity')
def test_simulated_worker_traversal_and_tree_listing_as_uid_12003():
    import os, shutil, tempfile
    from jiuwenswarm.research_rsi.capsule_doctor import worker_traversal
    base = Path(tempfile.mkdtemp(prefix='traversal-'))
    try:
        base.chmod(0o711)
        work = base / 'evidence/work'; work.mkdir(parents=True, mode=0o700)
        (base / 'evidence').chmod(0o711)
        report = worker_traversal([work])
        assert report['mode'] == 'simulated' and report['blocking'] == {
            'path': str(work), 'target': str(work), 'reason': 'not_searchable'}
        work.chmod(0o711)
        assert worker_traversal([work])['blocking'] is None
        runtime = base / 'runtime'; (runtime / 'source').mkdir(parents=True)
        (runtime / 'source/m.py').write_text('x'); runtime.chmod(0o755); (runtime / 'source').chmod(0o711)
        assert worker_traversal([], trees=[runtime])['blocking'] == {
            'path': str(runtime / 'source'), 'target': str(runtime), 'reason': 'not_listable'}
        (runtime / 'source').chmod(0o755); (runtime / 'source/m.py').chmod(0o600)
        assert worker_traversal([], trees=[runtime])['blocking']['reason'] == 'not_readable'
    finally:
        shutil.rmtree(base)
