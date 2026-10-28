"""Abandonment retains executed unknowns and never manufactures qualification."""
import copy
import importlib.util
import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager

import pytest

SOURCE = Path(__file__).resolve().parents[3] / 'deploy/m1/rsi_security_abandonment.py'
spec = importlib.util.spec_from_file_location('security_abandonment_test', SOURCE)
abandon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(abandon)
_repair_spec = importlib.util.spec_from_file_location('abandonment_stopped_fixture', SOURCE.with_name('rsi_stopped_repair.py').parents[2] / 'tests/unit_tests/scripts/test_rsi_stopped_repair.py')
_repair_fixture = importlib.util.module_from_spec(_repair_spec)
_repair_spec.loader.exec_module(_repair_fixture)
deployed = _repair_fixture.deployed


class Captures:
    def __init__(self):
        self.values = {}

    def put(self, kind, value):
        raw = value if isinstance(value, bytes) else abandon.encoded(value)
        pin = {'id': kind + ':' + str(len(self.values)), 'sha256': abandon.digest(raw)}
        self.values[pin['id']] = (kind, raw)
        return pin

    def raw(self, pin, kind=None):
        actual, raw = self.values[pin['id']]
        assert kind is None or actual == kind
        assert abandon.digest(raw) == pin['sha256']
        return raw

    def get(self, pin, kind=None):
        return abandon.closed_json(self.raw(pin, kind))

    def records(self, kind):
        return [({'id':k, 'sha256':abandon.digest(v[1])}, abandon.closed_json(v[1])) for k,v in self.values.items() if v[0] == kind]


@pytest.fixture
def originals(tmp_path):
    from jiuwenswarm.research.contracts.rsi_security_cases import KERNEL_PROGRAMS, KERNEL_ARGV
    from jiuwenswarm.research_rsi.process_policy import security_program
    store = Captures(); p = store.put
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research_rsi.security_campaign import prepare_security_campaign_plan
    scope_spec = importlib.util.spec_from_file_location('campaign_metadata_fixture', SOURCE.parents[2] / 'tests/unit_tests/research_rsi/test_security_campaign.py')
    scope_module = importlib.util.module_from_spec(scope_spec); scope_spec.loader.exec_module(scope_module)
    original_store = SQLiteRunStore(tmp_path / 'original-metadata')
    scope,bindings,observer,driver = scope_module.metadata_scope(original_store)
    plan = prepare_security_campaign_plan(original_store,scope_ref=scope,case_bindings=bindings,observer_ref=observer,driver_ref=driver)
    for ident,sha,kind in original_store.connection.execute('SELECT a.id,a.sha256,r.kind FROM artifacts a LEFT JOIN records r ON r.id=a.id'):
        store.values[ident] = (kind,original_store.read_blob({'id':ident,'sha256':sha}))
    binding = bindings['RSIV-1']; profile = store.get(binding['worker_profile_ref'])
    meta = scope
    source = p('blob', security_program(KERNEL_PROGRAMS['RSIV-1']))
    attack = 'security-case-' + abandon.digest(abandon.encoded([plan,'RSIV-1']))[:40]
    claim = p('rsi-security-case-claim', dict(schema='ai4r-rsi-security-case-claim:1',plan_ref=plan,case_id='RSIV-1',attack_id=attack,started_at='2026-10-26T00:00:00Z',**binding))
    start = p('rsi-security-effect-start', dict(schema='ai4r-rsi-security-effect-start:1',case_claim_ref=claim,attack_id=attack,attack_source_ref=source,recorded_at='2026-10-26T00:00:00Z',**binding))
    probe = p('blob', dict(executor_uid=12003,executor_gid=12003,ready=True,cap_effective='00000000',no_new_privileges='1',
        network='none',network_namespace='net:[original]',interfaces=[[1,'lo']],
        denied_paths={'/hidden-fixtures':True,'/var/lib/ai4r-rsi/custodian':True}))
    stdout = p('blob',b'{"operation":"hidden_read","errno":2}\n'); stderr = p('blob',b'')
    receipt = p('execution-receipt', dict(job_id=attack,invocation_id=attack,subject_ref=source,observed_runtime=True,
        identity={'executor_uid':12003,'executor_gid':12003},argv=KERNEL_ARGV,stdout_ref=stdout,stderr_ref=stderr,
        observed_limits={'isolation_probe_ref':probe,'memory_max':str(128*1024*1024),'pids_max':'8'},
        termination_reason='completed',exit_code=0,**{k:profile[k] for k in ('contract_ref','hardware_ref','timeout_s')}))
    empty = p('kernel-group-empty', {'job_id':attack,'observed_runtime':True,'populated':0})
    content = p('blob',b'protected original canary')
    canary = {'name':'owned-control','path':'/var/lib/ai4r-rsi-validation-campaign/boundary-state/'+attack+'/canary',
              'uid':0,'gid':0,'mode':0o600,'sha256':content['sha256'],'content_ref':content}
    state = {'schema':'ai4r-rsi-security-state:1','canaries':[canary],'peer_accepts':0,'peer':None,'ledger':None,'library':None}
    before = p('rsi-security-state',state); after = p('rsi-security-state',state)
    inputs = p('rsi-security-input',{'target_path':canary['path']})
    kernel = p('rsi-kernel-observation',dict(schema='ai4r-rsi-kernel-observation:1',attack_id=attack,input_ref=inputs,
        execution_ref=receipt,attack_source_ref=source,probe_ref=probe,stdout_ref=stdout,stderr_ref=stderr,
        containment_ref=empty,before_ref=before,after_ref=after,**binding))
    row = dict(claim_ref=claim,status='OUTCOME_UNKNOWN',observation_ref=None,halt_ref=None,evidence_refs=[],proof_ref=None)
    counts = dict(canonical_attempts=0,started_attempts=1,pending_started_attempts=1,attempts_used=1)
    status = p('rsi-security-campaign-status',dict(plan_ref=plan,scope_ref=meta,status='BLOCKED',cases={'RSIV-1':row},
        actual_counts={'RSIV-1':counts},verification=None))
    campaign_start = p('rsi-security-campaign-start',{'schema':'ai4r-rsi-security-campaign-start:1','plan_ref':plan,'scope_ref':meta,'started_at':'2026-10-26T00:00:00Z'})
    db = sqlite3.connect(':memory:')
    db.executescript('CREATE TABLE security_campaigns(lineage,plan_ref,start_ref,result_ref);CREATE TABLE security_cases(lineage,case_id,claim_ref,status,observation_ref,halt_ref,evidence_refs,proof_ref);')
    lineage = abandon.digest(abandon.encoded(bindings))
    text = lambda value: abandon.encoded(value).decode()
    db.execute('INSERT INTO security_campaigns VALUES(?,?,?,?)',(lineage,text(plan),text(campaign_start),text(status)))
    db.execute('INSERT INTO security_cases VALUES(?,?,?,?,?,?,?,?)',(lineage,'RSIV-1',text(claim),'OUTCOME_UNKNOWN',None,None,'[]',None))
    pins = dict(campaign_status_ref=status,claim_ref=claim,effect_start_ref=start,execution_receipt_ref=receipt,
        isolation_probe_ref=probe,kernel_group_empty_ref=empty,kernel_observation_ref=kernel,before_ref=before,after_ref=after)
    yield store,db,pins
    db.close(); original_store.close()


def test_original_effect_review_preserves_every_row_blob_and_started_charge(originals):
    store,db,pins = originals
    old_rows = list(db.iterdump()); old_blobs = copy.deepcopy(store.values)
    result = abandon.join_originals(store,db,pins)
    assert result['original_case_status'] == 'OUTCOME_UNKNOWN'
    assert result['canonical_attempts'] == 0 and result['charged_started_attempts'] == 1
    assert result['qualification'] is False
    assert list(db.iterdump()) == old_rows and store.values == old_blobs


@pytest.mark.parametrize('kind,field,value',[
    ('rsi-security-effect-start','attack_id','another-case'),
    ('execution-receipt','invocation_id','another-case'),
    ('kernel-group-empty','populated',1),
    ('rsi-security-state','peer_accepts',1),
    ('rsi-kernel-observation','attack_id','another-case'),
])
def test_mismatched_retained_effect_cannot_be_disposed(originals,kind,field,value):
    store,db,pins = originals
    original_get = store.get
    def changed(pin, expected=None):
        result = original_get(pin,expected)
        if store.values[pin['id']][0] == kind:
            result[field] = value
        return result
    store.get = changed
    with pytest.raises(ValueError):
        abandon.join_originals(store,db,pins)


def test_canonical_adoption_or_extra_effect_is_rejected(originals):
    store,db,pins = originals
    store.put('rsi-attempt',{'session_id':'fabricated'})
    with pytest.raises(ValueError,match='ADDITIONAL_OR_CANONICAL'):
        abandon.join_originals(store,db,pins)


def test_no_disposition_can_turn_changed_canary_or_successful_attack_into_clearance(originals):
    store,db,pins = originals
    kernel = store.get(pins['kernel_observation_ref'])
    bad = b'{"operation":"hidden_read","errno":0}\n'
    # Build an internally hash-consistent malicious stdout and rejoin receipt
    # and kernel to it; raw independent denial check still rejects the effect.
    stdout = store.put('blob',bad)
    execution = store.get(pins['execution_receipt_ref']); execution['stdout_ref'] = stdout
    pins['execution_receipt_ref'] = store.put('execution-receipt',execution)
    kernel['stdout_ref'] = stdout; kernel['execution_ref'] = pins['execution_receipt_ref']
    pins['kernel_observation_ref'] = store.put('rsi-kernel-observation',kernel)
    with pytest.raises(ValueError,match='denied'):
        abandon.join_originals(store,db,pins)


@pytest.mark.parametrize('candidate_field',['candidate_id','candidate_sha256'])
def test_original_runtime_build_abi_keeps_package_and_installed_inventory_digests_distinct(candidate_field):
    store=Captures()
    inventory={'schema':'ai4r-installed-build:2','files':[],'links':[],'dependencies':[],
        'components':{'jiuwenswarm_tui':{'files':[],'links':[]}},'uv_lock_sha256':'1'*64,'pyproject_sha256':'2'*64}
    inventory['build_id']=abandon.digest(abandon.encoded(inventory))
    inventory_ref=store.put('blob',inventory)
    candidate='3'*64
    wrapper_ref=store.put('blob',{candidate_field:candidate,'installed_build_ref':inventory_ref})
    scope=store.put('blob',{'runtime_build_ref':wrapper_ref})
    result=abandon.original_source_build(store,scope)
    assert result['package_build_id']==candidate
    assert result['installed_inventory_build_id']==inventory['build_id']!=candidate


def test_original_installed_inventory_cannot_hide_changed_payload_behind_package_candidate():
    store=Captures()
    manifest={'schema':'ai4r-installed-build:2','files':[],'links':[],'dependencies':[],
        'components':{},'uv_lock_sha256':'1'*64,'pyproject_sha256':'2'*64,'build_id':'4'*64}
    inventory_ref=store.put('blob',manifest)
    wrapper_ref=store.put('blob',{'candidate_id':'3'*64,'installed_build_ref':inventory_ref})
    scope=store.put('blob',{'runtime_build_ref':wrapper_ref})
    with pytest.raises(ValueError,match='INVENTORY_HASH_DIFFERS'):
        abandon.original_source_build(store,scope)


def test_complete_docker_inspection_is_stable_only_for_mount_enumeration_order():
    original={'Id':'1'*64,'State':{'Pid':0},'Config':{'Env':['X=first','X=last'],'Cmd':['one','two']},
        'HostConfig':{'Binds':['first','second']},'Mounts':[
            {'Destination':'/a','Type':'bind','Source':'/original/a','RW':False,'Mode':'ro','Propagation':'rprivate','Other':{'retained':True}},
            {'Destination':'/b','Type':'bind','Source':'/original/b','RW':True,'Mode':'rw','Propagation':'rprivate'}]}
    normalized=abandon.canonical_inspection(original)
    baseline=abandon.digest(abandon.encoded(normalized))
    permutation=copy.deepcopy(original);permutation['Mounts'].reverse()
    assert abandon.digest(abandon.encoded(abandon.canonical_inspection(permutation)))==baseline
    assert original['Mounts'][0]['Destination']=='/a'
    for key,value in [('Source','/different'),('RW',True),('Mode','rw'),('Propagation','shared'),('Other',{'retained':False})]:
        changed=copy.deepcopy(original);changed['Mounts'][0][key]=value
        assert abandon.digest(abandon.encoded(abandon.canonical_inspection(changed)))!=baseline
    for scope,key in [('Config','Env'),('Config','Cmd'),('HostConfig','Binds')]:
        changed=copy.deepcopy(original);changed[scope][key].reverse()
        assert abandon.digest(abandon.encoded(abandon.canonical_inspection(changed)))!=baseline
    duplicate=copy.deepcopy(original);duplicate['Mounts'][1]['Destination']='/a'
    with pytest.raises(ValueError,match='DUPLICATE_OR_INVALID'):
        abandon.canonical_inspection(duplicate)


ROOT = pytest.mark.skipif(os.name != 'posix' or os.geteuid() != 0, reason='Linux Root custody')


@pytest.mark.parametrize('source,touches',[
    ('/var/lib/owned/security-phases/draft.original/validation-campaign',True),
    ('/var/lib/owned/security-phases/draft.original/validation-campaign/artifacts',True),
    ('/var/lib/owned/security-phases/draft.original',True),
    ('/var/lib/owned',True),
    ('/',True),
    ('/var/lib/owned/security-phases/draft.other',False),
    ('/var/lib/other',False),
])
def test_other_container_cannot_reach_originals_through_ancestor_exact_or_child_mount(source,touches):
    paths = [Path('/var/lib/owned/security-phases/draft.original/validation-campaign')]
    assert abandon._mount_touches_phase(source,paths) is touches


@ROOT
def test_container_bind_source_alias_into_original_phase_is_rejected(tmp_path):
    retained = tmp_path/'original-phase'; retained.mkdir()
    alias = tmp_path/'innocent-alias'; alias.symlink_to(retained,target_is_directory=True)
    assert abandon._mount_touches_phase(alias,[retained])


@ROOT
def test_append_only_claim_blocks_start_after_interrupted_transition(tmp_path):
    root = tmp_path / 'deployment'; config = root / 'config'; config.mkdir(parents=True,mode=0o700)
    for name in ('security-abandonment-claims','security-abandonment-applied'):
        (config / name).mkdir(mode=0o700)
    abandon.repair.new(config / 'security-abandonment-claims/generation-one.json',b'{}')
    with pytest.raises(ValueError,match='PARTIAL_SECURITY_ABANDONMENT_BLOCKS_START'):
        abandon.repair.verify_repair_complete(root)


@ROOT
def test_actual_readonly_original_store_hashes_and_types(tmp_path):
    root = tmp_path / 'capture'; (root / 'state').mkdir(parents=True,mode=0o700)
    dbpath = root / 'state/research.sqlite3'
    db = sqlite3.connect(dbpath)
    db.executescript('CREATE TABLE artifacts(id,sha256);CREATE TABLE records(id,kind);')
    raw = b'{"actual":"original"}'; sha = abandon.digest(raw); pin = {'id':'original','sha256':sha}
    db.execute('INSERT INTO artifacts VALUES(?,?)',('original',sha)); db.execute('INSERT INTO records VALUES(?,?)',('original','retained'))
    db.commit(); db.close(); os.chmod(dbpath,0o600)
    path = root / 'artifacts/sha256' / sha[:2] / sha; path.parent.mkdir(parents=True); path.write_bytes(raw); os.chmod(path,0o600)
    before = dbpath.read_bytes(); store = abandon.OriginalStore(root)
    try:
        assert store.get(pin,'retained') == {'actual':'original'}
        with pytest.raises(ValueError,match='INDEX_JOIN'):
            store.get(pin,'canonical')
        path.write_bytes(b'changed')
        with pytest.raises(ValueError,match='BLOB_DIFFERS'):
            store.get(pin,'retained')
    finally:
        store.close()
    assert dbpath.read_bytes() == before


@ROOT
def test_retained_wal_is_read_without_touching_original_database_or_sidecars(tmp_path):
    root = tmp_path / 'private'; root.mkdir(mode=0o700); path = root / 'index.sqlite'
    original = sqlite3.connect(path)
    original.execute('PRAGMA journal_mode=WAL')
    original.execute('CREATE TABLE retained(value)'); original.execute('INSERT INTO retained VALUES(?)',('actual durable start',)); original.commit()
    os.chmod(path,0o600)
    before = {p:p.read_bytes() for p in root.iterdir()}
    frozen = abandon.FrozenDatabase(path)
    try:
        assert frozen.execute('SELECT value FROM retained').fetchall() == [('actual durable start',)]
        with pytest.raises(sqlite3.OperationalError):
            frozen.execute('DELETE FROM retained')
    finally:
        frozen.close()
    assert {p:p.read_bytes() for p in root.iterdir()} == before
    original.close()


@ROOT
@pytest.mark.parametrize('break_history',[None,'old-repair','old-phase','abandon-completion','retained-original','retained-config'])
def test_abandonment_applies_after_prior_repair_and_keeps_both_histories(deployed, monkeypatch, break_history):
    env = deployed; repair = _repair_fixture.repair
    prior = repair.plan(env.root,env.input)
    repair.apply(env.root,env.input,repair.digest(repair.encoded(prior)))
    config = env.root / 'config'
    original = env.paths['validation-campaign'] / 'original-unknown.txt'
    original.write_bytes(b'original unknown and charged'); os.chmod(original,0o600)
    before = {p:p.read_bytes() for p in (config / 'stopped-repair-archive/repair-one').rglob('*') if p.is_file()}
    request = {'generation':'fresh-abandonment','authorization':'Explicit Root disposition; fresh qualification required',
        'old_manifest_sha256':abandon.digest((env.root/'local.json').read_bytes()),'new_project':'ai4r-rsi-fresh-qualification',
        'proof_sha256':{kind:abandon.digest(b'{}') for kind in abandon.PROOF_FILES}}
    input_path = config / 'security-abandonment-inputs/fresh-abandonment/input.json'
    input_path.parent.mkdir(parents=True); input_path.write_bytes(abandon.encoded(request)); os.chmod(input_path,0o600)
    for filename in abandon.PROOF_FILES.values():
        path = input_path.parent / filename; path.write_bytes(b'{}'); os.chmod(path,0o600)
    prior_selector = abandon.closed_json((config/'security-phase-current.json').read_bytes())
    facts = {'old_manifest':abandon.closed_json((env.root/'local.json').read_bytes()),
        'new_images':{'app':'sha256:'+'7'*64,'rsi':'sha256:'+'8'*64,'worker':'sha256:'+'9'*64},
        'prior_selector':prior_selector,'retained_phase':{'campaign':abandon._snapshot(env.paths['validation-campaign'])},
        'retained_files':{'broker-config':abandon._retained_file(env.paths['broker-config'])},
        'retained_phase_paths':{'campaign':str(env.paths['validation-campaign'])}}
    @contextmanager
    def locked(_):
        yield
    monkeypatch.setattr(abandon.repair,'repair_locks',locked)
    monkeypatch.setattr(abandon,'load_input',lambda root,path:(request,{},input_path.read_bytes()))
    monkeypatch.setattr(abandon,'_observe',lambda *args:copy.deepcopy(facts))
    reviewed = abandon.plan(env.root,input_path)
    result = abandon.apply(env.root,input_path,abandon.digest(abandon.encoded(reviewed)))
    assert result['original_case_status'] == 'OUTCOME_UNKNOWN' and result['charged_started_attempts'] == 1
    assert result['qualification'] is False and result['candidate_admitted'] is False
    assert all(p.read_bytes() == raw for p,raw in before.items())
    current = abandon.closed_json((env.root/'local.json').read_bytes())
    repair.verify_repair_complete(env.root)
    assert repair.phase_generation(current) == 'fresh-abandonment'
    assert abandon.verify_history(env.root)['prior_selector'] == prior_selector
    if break_history:
        target = {'old-repair':config/'stopped-repair-applied/repair-one.json',
                  'old-phase':config/'security-phase-generations/repair-one.json',
                  'abandon-completion':config/'security-abandonment-applied/fresh-abandonment.json',
                  'retained-config':env.paths['broker-config'],
                  'retained-original':original}[break_history]
        target.write_bytes(b'{}')
        with pytest.raises((ValueError,KeyError)):
            repair.verify_repair_complete(env.root)
