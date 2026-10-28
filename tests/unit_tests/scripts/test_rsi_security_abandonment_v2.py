"""Synthetic historical captures only: no syscall attacks, Docker or models."""
import base64
import copy
import importlib.util
import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager

import pytest

ROOT = Path(__file__).parents[3]
spec = importlib.util.spec_from_file_location('abandonment_v2_test',ROOT/'deploy/m1/rsi_security_abandonment.py')
abandon = importlib.util.module_from_spec(spec); spec.loader.exec_module(abandon)


class Captures:
    def __init__(self): self.values = {}; self.serial = 0
    def put(self,kind,value):
        self.serial += 1
        raw = value if isinstance(value,bytes) else abandon.encoded(value)
        pin = {'id':kind+':unit-'+str(self.serial),'sha256':abandon.digest(raw)}
        self.values[pin['id']] = kind,raw
        return pin
    def raw(self,pin,kind=None):
        actual,raw = self.values[pin['id']]
        assert kind is None or actual == kind
        assert abandon.digest(raw) == pin['sha256']
        return raw
    def get(self,pin,kind=None): return abandon.closed_json(self.raw(pin,kind))
    def records(self,kind):
        return [({'id':ident,'sha256':abandon.digest(raw)},abandon.closed_json(raw))
            for ident,(actual,raw) in self.values.items() if actual == kind]


@pytest.fixture
def campaign(tmp_path):
    """Construct the real producer's record ABI with test-only generated signatures."""
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research_rsi.signing import Signer
    from jiuwenswarm.research.contracts.rsi_security import CASES
    spec = importlib.util.spec_from_file_location('abandonment_metadata_fixture',ROOT/'tests/unit_tests/research_rsi/test_security_campaign.py')
    fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
    original = SQLiteRunStore(tmp_path/'unit-metadata')
    scope_ref,bindings,observer,driver = fixture.metadata_scope(original)
    store = Captures(); p = store.put
    for ident,sha,kind in original.connection.execute('SELECT a.id,a.sha256,r.kind FROM artifacts a LEFT JOIN records r ON r.id=a.id'):
        store.values[ident] = kind,original.read_blob({'id':ident,'sha256':sha})
    files = []
    for name in ('research_rsi/process_policy.py','research/contracts/rsi_security_cases.py'):
        raw = (ROOT/'jiuwenswarm'/name).read_bytes()
        if name.endswith('process_policy.py'):
            raw = raw.replace(b'def install_process_policy():\n',b'def install_process_policy():\n    # synthetic retained historical source, differs from installed current source\n')
        files.append(dict(path=name,bytes=len(raw),sha256=abandon.digest(raw),content_b64=base64.b64encode(raw).decode()))
    sources = {'schema':'ai4r-rsi-abandonment-original-sources:1','files':files}
    inventory = dict(schema='ai4r-installed-build:2',files=[{k:r[k] for k in ('path','bytes','sha256')} for r in files],
        links=[],dependencies=[],components={},uv_lock_sha256='1'*64,pyproject_sha256='2'*64)
    inventory['build_id'] = abandon.digest(abandon.encoded(inventory))
    inventory_ref = p('blob',inventory)
    wrapper = p('blob',{'candidate_id':'3'*64,'installed_build_ref':inventory_ref})
    scope = store.get(scope_ref); scope['runtime_build_ref'] = wrapper
    scope_ref = p('blob',scope)
    plan = dict(schema='ai4r-rsi-security-campaign-plan:1',scope_ref=scope_ref,case_bindings=bindings,
        observer_ref=observer,driver_ref=driver,verification_profile_ref=None,procedure_ref=None,assertion_manifest_ref=None)
    plan['id'] = 'security-campaign-plan:'+abandon.digest(abandon.encoded(plan)); plan_ref = p('rsi-security-campaign-plan',plan)
    programs,kernels,_ = abandon.retained_programs(store,scope_ref,sources)
    signer = Signer.generate('unit-custodian')
    key_pin = dict(custodian_key_id=signer.key_id,custodian_public_key=base64.urlsafe_b64encode(signer.public_bytes()).decode().rstrip('='))
    def make(prefix=4):
        timestamp = '2026-10-26T00:00:00Z'; rows = {}; counts = {}; prefix_pins = []; pins = None
        db = sqlite3.connect(':memory:')
        db.executescript('CREATE TABLE security_campaigns(lineage,plan_ref,start_ref,result_ref);CREATE TABLE security_cases(lineage,case_id,claim_ref,status,observation_ref,halt_ref,evidence_refs,proof_ref);')
        lineage = abandon.digest(abandon.encoded(bindings))
        campaign_start = p('rsi-security-campaign-start',dict(schema='ai4r-rsi-security-campaign-start:1',plan_ref=plan_ref,scope_ref=scope_ref,started_at=timestamp))
        for index,case in enumerate(CASES):
            if index > prefix:
                counts[case] = dict(canonical_attempts=0,started_attempts=0,pending_started_attempts=0,attempts_used=0,accounting_status='CANONICAL',queries_used=None)
                continue
            binding = bindings[case]; profile = store.get(binding['worker_profile_ref']); session = store.get(binding['session_ref'])
            target = store.get(session['target_profile_ref']); attack = 'security-case-'+abandon.digest(abandon.encoded([plan_ref,case]))[:40]
            claim_ref = p('rsi-security-case-claim',dict(schema='ai4r-rsi-security-case-claim:1',plan_ref=plan_ref,case_id=case,attack_id=attack,started_at=timestamp,**binding))
            source = p('blob',programs[case]); content = p('blob',b'unit historical canary, no actual secrets')
            canary = dict(name=case,path='/var/lib/ai4r-rsi-validation-campaign/boundary-state/'+attack+'/unit',uid=0,gid=0,mode=0o600,sha256=content['sha256'],content_ref=content)
            state = dict(schema='ai4r-rsi-security-state:1',canaries=[canary],peer_accepts=0,peer=None,ledger=None,library=None)
            before,after = p('rsi-security-state',state),p('rsi-security-state',state)
            inputs = p('rsi-security-input',{})
            common = dict(session_ref=binding['session_ref'],worker_profile_ref=binding['worker_profile_ref'],input_ref=inputs,
                attack_id=attack,attack_source_ref=source,before_ref=before,after_ref=after)
            effect = execution = probe = empty = attempt = stdout = stderr = None
            if case in kernels:
                effect = p('rsi-security-effect-start',dict(schema='ai4r-rsi-security-effect-start:1',case_claim_ref=claim_ref,
                    attack_id=attack,attack_source_ref=source,recorded_at=timestamp,**binding))
                probe = p('blob',dict(executor_uid=12003,executor_gid=12003,ready=True,cap_effective='00000000',no_new_privileges='1',
                    network='none',network_namespace='net:[unit]',interfaces=[[1,'lo']],denied_paths={'/hidden-fixtures':True,'/var/lib/ai4r-rsi/custodian':True}))
                stdout = p('blob',abandon.encoded(dict(operation='permission_escalation',uid_before=12003,gid_before=12003,
                    uid_after=12003,gid_after=12003,setuid_errno=22,setgid_errno=22)))
                stderr = p('blob',b'')
                execution = p('execution-receipt',dict(job_id=attack,invocation_id=attack,subject_ref=source,observed_runtime=True,
                    identity=dict(executor_uid=12003,executor_gid=12003),argv=['/usr/local/bin/python3','-I','/resources/attack.py'],
                    stdout_ref=stdout,stderr_ref=stderr,observed_limits=dict(isolation_probe_ref=probe,memory_max=str(profile['memory_mb']*1024*1024),pids_max=str(profile['pids_max'])),
                    termination_reason='completed',exit_code=0,wall_time_s=0.01,**{k:profile[k] for k in ('contract_ref','hardware_ref','timeout_s')}))
                empty = p('kernel-group-empty',dict(job_id=attack,observed_runtime=True,populated=0))
                common.update(execution_ref=execution,probe_ref=probe,stdout_ref=stdout,stderr_ref=stderr,containment_ref=empty)
                denial = p('rsi-kernel-observation',dict(schema='ai4r-rsi-kernel-observation:1',**common))
                diff = p('blob',{})
                attempt = p('rsi-attempt',dict(schema_version='2.0.0',id='security-attempt:'+abandon.digest(attack.encode())[:40],
                    session_id=session['session_id'],sequence=1,previous_ref=None,target_ref=session['target_profile_ref'],parent_ref=target['parent_ref'],child_ref=source,diff_ref=diff,
                    rationale='unit historical capture',visible_evidence_refs=[],queries_used=0,violations=['Prohibited-action validation '+case],stop_reason='unit',
                    configuration_ref=session['configuration_ref'],observation_refs=[effect,execution,denial],time_s=0.01,model_calls=0,unavailable_reasons=[],
                    hash_profile_ref=session['hash_profile_ref'],chain_root_ref=session['chain_root_ref'],attempt_status='rejected',rejection_reason='unit',failure_evidence_refs=[denial]))
            else:
                common.update(execution_ref=None,probe_ref=None,stdout_ref=None,stderr_ref=None,containment_ref=None)
                denial = p('rsi-policy-denial',dict(schema='ai4r-rsi-policy-denial:1',method='checked_changes',input_ref=inputs,before_ref=before,after_ref=after,exception_type='SecurityViolation',exception_code=None))
            obs = dict(schema='ai4r-rsi-security-case-observation:1',case_id=case,attack_source_sha256=source['sha256'],
                mode='kernel' if case in kernels else 'policy',denial_ref=denial,attempt_ref=attempt,**common)
            observation = p('rsi-security-case-observation',obs)
            evidence = [observation]+[obs[name] for name in ('input_ref','before_ref','after_ref','denial_ref','execution_ref','containment_ref','attempt_ref') if obs[name] is not None]
            if effect: evidence.append(effect)
            attempts = [attempt] if attempt else []; halt = proof = None
            if index < prefix:
                halt_value = dict(schema_version='2.0.0',id='security-halt:'+abandon.digest(abandon.encoded([plan_ref,case,observation,attempts,0]))[:40],
                    session_ref=binding['session_ref'],outcome='SECURITY_HALTED',parent=session['parent'],child=None,child_declaration_ref=None,attempt_refs=attempts,
                    final_attempt_ref=None,referee_evidence_ref=None,qualified_by='none',statistics=None,attempts_used=len(attempts),queries_used=0,stop_reason='unit historical halt',limitations=['unit'],recorded_at=timestamp)
                halt = p('rsi-session-result',signer.sign(halt_value)); evidence.append(halt)
                proof = p('rsi-security-case-proof',dict(schema='ai4r-rsi-security-case-proof:1',observation_ref=observation,halt_ref=halt,
                    proof=dict(case_id=case,**binding,attack_id=attack,denial_refs=[denial],attempt_ref=attempt)))
            else:
                failure = p('rsi-security-case-failure',dict(schema='ai4r-rsi-security-case-failure:1',plan_ref=plan_ref,case_claim_ref=claim_ref,case_id=case,
                    phase='independent_observer',observation_ref=observation,exception_module='builtins',exception_type='ValueError',traceback='unit original observer rejected',traceback_truncated=False,recorded_at=timestamp))
                evidence.append(failure)
                pins = dict(claim_ref=claim_ref,effect_start_ref=effect,execution_receipt_ref=execution,isolation_probe_ref=probe,kernel_group_empty_ref=empty,
                    kernel_observation_ref=denial,before_ref=before,after_ref=after,attempt_ref=attempt,observation_ref=observation,failure_ref=failure,observed_prefix=prefix_pins)
            row = dict(claim_ref=claim_ref,status='OBSERVED' if index < prefix else 'OUTCOME_UNKNOWN',observation_ref=observation,halt_ref=halt,evidence_refs=evidence,proof_ref=proof)
            rows[case] = row
            if index < prefix: prefix_pins.append(dict(case_id=case,**row))
            counts[case] = dict(canonical_attempts=len(attempts),started_attempts=int(case in kernels),pending_started_attempts=0,attempts_used=len(attempts),accounting_status='CANONICAL',queries_used=0 if index < prefix else None)
            txt = lambda value: abandon.encoded(value).decode() if value is not None else None
            db.execute('INSERT INTO security_cases VALUES(?,?,?,?,?,?,?,?)',(lineage,case,txt(claim_ref),row['status'],txt(observation),txt(halt),txt(evidence),txt(proof)))
        status = p('rsi-security-campaign-status',dict(plan_ref=plan_ref,scope_ref=scope_ref,status='BLOCKED',verification=None,cases=rows,actual_counts=counts,missing_cases=list(CASES[prefix:])))
        pins['campaign_status_ref'] = status
        text = lambda value: abandon.encoded(value).decode()
        db.execute('INSERT INTO security_campaigns VALUES(?,?,?,?)',(lineage,text(plan_ref),text(campaign_start),text(status)))
        return store,db,pins,sources,key_pin
    yield make
    original.close()


@pytest.mark.parametrize('prefix',[0,4,6])
def test_unknown_canonical_after_bounded_prefix_stays_unknown_without_predicate_or_new_effect(campaign,prefix,monkeypatch):
    from jiuwenswarm.research.contracts.rsi_security_cases import FiniteCaseObserver
    def forbidden(*args,**kwargs): pytest.fail('Disposition must not execute observer predicates or reinterpret errno')
    monkeypatch.setattr(FiniteCaseObserver,'_kernel_capture',forbidden)
    store,db,pins,sources,key = campaign(prefix)
    old_rows,old_bytes = list(db.iterdump()),copy.deepcopy(store.values)
    result = abandon.join_canonical_unknown(store,db,pins,sources,key)
    assert result['original_case_status']=='OUTCOME_UNKNOWN' and result['canonical_attempts']==1
    assert result['predicate_verified'] is result['qualification'] is result['prefix_adopted'] is False
    assert result['actual_counts']['RSIV-4']['started_attempts']==0
    assert list(db.iterdump())==old_rows and store.values==old_bytes
    db.close()


@pytest.mark.parametrize('fault',['charge','boolean_charge','extra_case','extra_attempt','unknown_halt','failure_phase','old_source','old_source_self_consistent','prefix_pin','signature','containment','identity','changed_state','missing_evidence'])
def test_v2_rejects_incomplete_foreign_or_changed_original_closure(campaign,fault):
    store,db,pins,sources,key = campaign()
    original_get = store.get
    if fault=='extra_case': db.execute("INSERT INTO security_cases SELECT lineage,'RSIV-6',claim_ref,status,observation_ref,halt_ref,evidence_refs,proof_ref FROM security_cases LIMIT 1")
    elif fault=='extra_attempt': store.put('rsi-attempt',original_get(pins['attempt_ref']))
    elif fault=='old_source': sources['files'][0]['content_b64']=base64.b64encode(b'forged').decode()
    elif fault=='old_source_self_consistent':
        sources['files'][0].update(content_b64=base64.b64encode(b'forged').decode(),bytes=6,sha256=abandon.digest(b'forged'))
    elif fault=='prefix_pin': pins['observed_prefix'][0]['case_id']='RSIV-2'
    elif fault=='signature': key['custodian_key_id']='other-signer'
    def changed(pin,kind=None):
        value = original_get(pin,kind)
        if fault=='charge' and pin==pins['campaign_status_ref']: value['actual_counts']['RSIV-10']['attempts_used']=1
        if fault=='boolean_charge' and pin==pins['campaign_status_ref']: value['actual_counts']['RSIV-5']['attempts_used']=True
        if fault=='unknown_halt' and pin==pins['campaign_status_ref']: value['cases']['RSIV-5']['halt_ref']=pins['failure_ref']
        if fault=='failure_phase' and pin==pins['failure_ref']: value['phase']='driver_observation'
        if fault=='containment' and pin==pins['kernel_group_empty_ref']: value['populated']=1
        if fault=='identity' and pin==pins['execution_receipt_ref']: value['identity']['executor_uid']=0
        if fault=='changed_state' and pin==pins['after_ref']: value['peer_accepts']=1
        if fault=='missing_evidence' and pin==pins['campaign_status_ref']: value['cases']['RSIV-5']['evidence_refs'].pop()
        return value
    store.get = changed
    with pytest.raises((ValueError,AssertionError)): abandon.join_canonical_unknown(store,db,pins,sources,key)
    db.close()


def test_v1_does_not_accept_v2_closure_and_proof_files_are_versioned(campaign):
    store,db,pins,sources,key = campaign()
    with pytest.raises(ValueError,match='EXACT_ORIGINAL_EFFECT_CLOSURE_REQUIRED'): abandon.join_originals(store,db,pins)
    assert abandon.proof_files({'schema':'ai4r-rsi-security-abandonment-input:1'})==abandon.PROOF_FILES
    assert abandon.proof_files({'schema':'ai4r-rsi-security-abandonment-input:2'})==abandon.PROOF_FILES|{'original_sources':'original-sources.json'}
    db.close()


def test_old_program_reconstruction_uses_inventory_pinned_historical_source(campaign):
    from jiuwenswarm.research_rsi.process_policy import security_program
    from jiuwenswarm.research.contracts.rsi_security_cases import KERNEL_PROGRAMS
    store,db,pins,sources,key = campaign()
    plan = store.get(store.get(pins['claim_ref'])['plan_ref'])
    programs,_,_ = abandon.retained_programs(store,plan['scope_ref'],sources)
    assert programs['RSIV-5'] != security_program(KERNEL_PROGRAMS['RSIV-5'])
    assert store.raw(store.get(pins['observation_ref'])['attack_source_ref']) == programs['RSIV-5']
    db.close()


def test_original_source_literal_parser_never_executes_calls(campaign,tmp_path):
    store,db,pins,sources,key = campaign()
    marker = tmp_path/'must-not-exist'
    source = sources['files'][1]
    raw = base64.b64decode(source['content_b64'])
    raw = raw.replace(b"_HEADER=b'''",("_HEADER=__import__('pathlib').Path("+repr(str(marker))+").write_text('executed') or b'''").encode())
    source.update(content_b64=base64.b64encode(raw).decode(),bytes=len(raw),sha256=abandon.digest(raw))
    plan = store.get(store.get(pins['claim_ref'])['plan_ref']); scope = store.get(plan['scope_ref'])
    oldbuild = abandon.original_source_build(store,plan['scope_ref'])
    inventory = store.get(oldbuild['installed_build_ref'])
    inventory['files'] = [{k:row[k] for k in ('path','bytes','sha256')} for row in sources['files']]
    inventory.pop('build_id'); inventory['build_id']=abandon.digest(abandon.encoded(inventory))
    scope['runtime_build_ref']=store.put('blob',{'candidate_id':oldbuild['package_build_id'],'installed_build_ref':store.put('blob',inventory)})
    with pytest.raises(ValueError): abandon.retained_programs(store,store.put('blob',scope),sources)
    assert not marker.exists()
    db.close()


@pytest.mark.parametrize('newline',[b'\r\n',b'\r'])
def test_historical_physical_newlines_match_original_inspect_getsource_semantics(campaign,newline):
    store,db,pins,sources,key = campaign()
    plan = store.get(store.get(pins['claim_ref'])['plan_ref']); scope = store.get(plan['scope_ref'])
    expected,_,_ = abandon.retained_programs(store,plan['scope_ref'],sources)
    source = sources['files'][0]
    raw = base64.b64decode(source['content_b64']).replace(b'\r\n',b'\n').replace(b'\r',b'\n').replace(b'\n',newline)
    source.update(content_b64=base64.b64encode(raw).decode(),bytes=len(raw),sha256=abandon.digest(raw))
    oldbuild = abandon.original_source_build(store,plan['scope_ref'])
    inventory = store.get(oldbuild['installed_build_ref'])
    inventory['files'] = [{k:row[k] for k in ('path','bytes','sha256')} for row in sources['files']]
    inventory.pop('build_id'); inventory['build_id']=abandon.digest(abandon.encoded(inventory))
    scope['runtime_build_ref']=store.put('blob',{'candidate_id':oldbuild['package_build_id'],'installed_build_ref':store.put('blob',inventory)})
    actual,_,_ = abandon.retained_programs(store,store.put('blob',scope),sources)
    assert actual == expected
    db.close()


@pytest.mark.skipif(os.name != 'posix' or os.geteuid() != 0,reason='Linux Root custody')
@pytest.mark.parametrize('tamper',[False,True])
def test_v2_completion_archives_source_proof_and_history_refuses_tampering(tmp_path,monkeypatch,tamper):
    """Real append-only file custody in an isolated tmpdir, no runtime operations."""
    config = tmp_path/'config'; config.mkdir(mode=0o700)
    old = dict(root=str(tmp_path),project='unit-old',images={'worker':'sha256:'+'1'*64})
    abandon.repair.new(tmp_path/'local.json',abandon.encoded(old))
    request = dict(schema='ai4r-rsi-security-abandonment-input:2',generation='unit-v2',authorization='unit explicit disposition',
        old_manifest_sha256=abandon.digest(abandon.encoded(old)),new_project='unit-new')
    folder = config/'security-abandonment-inputs/unit-v2'; folder.mkdir(parents=True,mode=0o700)
    request['proof_sha256'] = {kind:abandon.digest(b'{}') for kind in abandon.proof_files(request)}
    for name in abandon.proof_files(request).values(): abandon.repair.new(folder/name,b'{}')
    path = folder/'input.json'; abandon.repair.new(path,abandon.encoded(request))
    facts = dict(old_manifest=old,new_images={'worker':'sha256:'+'2'*64},prior_selector=None,
        retained_phase={},original_join={'charged_started_attempts':4})
    @contextmanager
    def locked(_): yield
    monkeypatch.setattr(abandon.repair,'repair_locks',locked)
    monkeypatch.setattr(abandon,'load_input',lambda *args:(request,{},path.read_bytes()))
    monkeypatch.setattr(abandon,'_observe',lambda *args:copy.deepcopy(facts))
    monkeypatch.setattr(abandon.repair,'verify_repair_complete',lambda root:abandon.verify_history(root))
    reviewed = abandon.plan(tmp_path,path)
    assert reviewed['schema']=='ai4r-rsi-security-abandonment-plan:2' and reviewed['qualification'] is False
    result = abandon.apply(tmp_path,path,abandon.digest(abandon.encoded(reviewed)))
    assert result['charged_started_attempts']==4 and result['qualification'] is False
    assert abandon.verify_history(tmp_path)['selector']['generation']=='unit-v2'
    archived = config/'security-abandonment-archive/unit-v2/original-sources.json'
    assert archived.read_bytes()==b'{}'
    if tamper:
        archived.write_bytes(b'{"modified":true}')
        with pytest.raises(ValueError,match='PROOF_ARCHIVE_DIFFERS'): abandon.verify_history(tmp_path)
