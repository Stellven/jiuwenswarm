"""Benign campaign bookkeeping controls; no boundary programs or probes run."""
import asyncio
import copy
import json
import os

import pytest

from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.capsules.assets import build_research_assets
from jiuwenswarm.research.contracts import validate
from jiuwenswarm.research.contracts.rsi_security import CASES
from jiuwenswarm.research.contracts.rsi_security_cases import FiniteCaseObserver
from jiuwenswarm.research_rsi.security_campaign import (
    PLAN_SCHEMA, CampaignLedger, CampaignOutcomeUnknown, SecurityCampaign, prepare_security_campaign_plan,
)
from jiuwenswarm.research_rsi.records import encoded
from jiuwenswarm.research_rsi.signing import Signer, verify
from jiuwenswarm.research_records.contracts import ContractData


def test_campaign_plan_has_only_finite_references_and_exact_thirteen_cases():
    pin={'id':'unit:original','sha256':'a'*64}
    plan=dict(schema='ai4r-rsi-security-campaign-plan:1',id='unit:metadata-plan',scope_ref=pin,
        case_bindings={case:dict(session_ref=pin,worker_profile_ref=pin) for case in CASES},observer_ref=pin,
        driver_ref=None,verification_profile_ref=None,procedure_ref=None,assertion_manifest_ref=None)
    contract=ContractData();contract.validate(PLAN_SCHEMA,plan)
    missing=copy.deepcopy(plan);missing['case_bindings'].pop('RSIV-13')
    extra=copy.deepcopy(plan);extra['case_bindings']['arbitrary']=extra['case_bindings']['RSIV-1']
    for changed in (missing,extra,dict(plan,callback='untrusted'),dict(plan,skip_observer=True)):
        with pytest.raises(ValueError):contract.validate(PLAN_SCHEMA,changed)


def metadata_scope(store):
    """Schema-valid public context only; no observations or qualification."""
    asset=build_research_assets(store,verify_catalog=False)['screening']
    parent=store.read_record(asset['declaration_ref']);body=asset['body_refs']['ranking_parent.txt']
    meta=store.put_blob(encoded({'unit':'Benign metadata bookkeeping; no boundary evidence or current image'}))
    target=dict(schema_version='1.0.0',id='security_metadata_target',parent_ref=body,parent_declaration_ref=asset['declaration_ref'],
        frozen_contract_ref=meta,required_test_refs=[meta],mutable_paths=['ranking_parent.txt'],protected_refs=[meta],
        splits=dict(development='metadata:d',hidden_loop='metadata:l',hidden_final='metadata:f',platform='metadata:p'),
        scoring=dict(primary='passed_test_count',secondary='paired_time_at_equal_counts',warmup_batches=5,paired_rounds=7,
            min_relative_gain=.1,noise_multiplier=3,batch_iterations=1000,calibrated_relative_noise=.01),
        calibration_ref=meta,session_query_limit=30,lifetime_query_limit=90,limits=dict(time_s=1,model_calls=1,memory_mb=128),
        scoring_adapter_ref=meta,improver_ref=meta,configuration_ref=meta)
    target_ref=store.put_record('rsi-target-profile',target)
    bindings={}
    for case in CASES:
        sid='security-metadata-'+case.lower()
        genesis=store.put_blob(encoded(dict(session_id=sid,target_ref=target_ref,hash_profile_ref=meta,interface_revision='M1-IF-009@r2')))
        session=dict(schema_version='1.0.0',id='session_'+case.lower().replace('-','_'),session_id=sid,target_profile_ref=target_ref,
            parent=dict(cc_name=parent['identity']['name'],cc_version=parent['identity']['version_label'],declaration_sha256=asset['declaration_ref']['sha256']),
            parent_declaration_ref=asset['declaration_ref'],improver_ref=meta,scoring_adapter_ref=meta,configuration_ref=meta,
            hash_profile_ref=meta,chain_root_ref=genesis,limits=dict(max_attempts=20,max_no_progress=5,wall_s=3600,per_call_s=300,
                session_query_limit=30,lifetime_query_limit=90),pass_count_repeats=1,
            qualification=dict(min_pass_rate_gain=.05,alpha=.05,min_timing_gain=.1,noise_multiplier=3,warmup_batches=5,paired_rounds=7),
            started_by='unit:metadata-owner',frozen_at='2026-10-25T00:00:00Z')
        session_ref=store.put_record('rsi-session',session)
        profile=dict(schema='ai4r-rsi-worker-profile:3',target_kind='ranking-v1',process_policy='single_process_seccomp_v1',
            session_ref=session_ref,target_ref=target_ref,parent_ref=body,contract_ref=meta,environment_ref=meta,hardware_ref=meta,
            memory_mb=128,pids_max=8,timeout_s=1)
        bindings[case]=dict(session_ref=session_ref,worker_profile_ref=store.put_blob(encoded(profile)))
    scope=dict(schema='ai4r-rsi-security-scope:1',id='metadata-only-scope',runtime_build_ref=meta,environment_ref=meta,
        worker_driver_ref=meta,executor_ref=meta,probe_ref=meta,kernel_release='metadata-not-observed',platform='metadata-not-qualified',
        worker_profile_refs=[bindings[case]['worker_profile_ref'] for case in CASES])
    scope_ref=store.put_blob(encoded(scope));observer_ref=store.put_blob(b'unit:unavailable-independent-observer-descriptor')
    driver_ref=store.put_blob(b'unit:metadata-only-driver-descriptor')
    return scope_ref,bindings,observer_ref,driver_ref


@pytest.fixture
def context(tmp_path):
    if os.name!='posix' or os.geteuid() not in (0,12002):
        # Only metadata contract controls execute on other platforms.
        yield None
        return
    os.chmod(tmp_path,0o700)
    store=SQLiteRunStore(tmp_path/'private');scope,bindings,observer,driver=metadata_scope(store)
    ledger=CampaignLedger(store);signer=Signer.generate('unit:bookkeeping-not-operational')
    try:yield store,ledger,signer,scope,bindings,observer,driver
    finally:ledger.close();store.close()


def mechanics_observer(store,signer):
    # Constructor-only mechanics fixture. No predicate is accepted by it in
    # these tests and it cannot emit a complete verification receipt.
    value=object.__new__(FiniteCaseObserver)
    value.read=store.read_blob;value.kind_reader=store.record_kind
    value.public_key=signer.public_bytes();value.key_id=signer.key_id;value.pins={}
    return value


def make_plan(context,driver=True):
    store,_,_,scope,bindings,observer,descriptor=context
    return prepare_security_campaign_plan(store,scope_ref=scope,case_bindings=bindings,
        observer_ref=observer,driver_ref=descriptor if driver else None)


def test_missing_driver_and_observer_record_only_blocked_status_and_never_pass(context):
    if context is None:return
    store,ledger,signer,scope,bindings,_,_=context;plan=make_plan(context,driver=False)
    campaign=SecurityCampaign(store,ledger=ledger,signer=signer,approved_plan_refs=[plan])
    result_ref=asyncio.run(campaign.run(plan));result=store.read_record(result_ref)
    assert result['status']=='BLOCKED' and result['verification'] is None
    assert result['missing_cases']==list(CASES) and result['cases']=={}
    assert all(row['attempts_used']==0 and row['queries_used'] is None and row['pending_started_attempts']==0
               for row in result['actual_counts'].values())
    assert not list(store.iter_records(kinds={'m1-verification-result','rsi-session-result'}))
    assert asyncio.run(campaign.run(plan))==result_ref
    ledger.close();replacement=CampaignLedger(store)
    try:
        reopened=SecurityCampaign(store,ledger=replacement,signer=signer,approved_plan_refs=[plan])
        assert asyncio.run(reopened.run(plan))==result_ref
    finally:replacement.close()


def test_claims_are_durable_before_trusted_driver_and_known_missing_cases_do_not_replay(context):
    if context is None:return
    store,ledger,signer,scope,bindings,_,descriptor=context;plan=make_plan(context)
    class MetadataDriver:
        plan_ref=plan;scope_ref=scope;descriptor_ref=descriptor
        def __init__(self):self.calls=[]
        def observe(self,case,*,case_claim_ref,session_ref,worker_profile_ref):
            claim=store.read_record(case_claim_ref)
            assert claim['case_id']==case and claim['session_ref']==session_ref and claim['worker_profile_ref']==worker_profile_ref
            assert store.record_kind(case_claim_ref)=='rsi-security-case-claim'
            assert any(row['claim_ref']==case_claim_ref for row in ledger.cases(next(iter(ledger.db.execute('SELECT lineage FROM security_campaigns')))[0]).values())
            self.calls.append(case)
            return None
    driver=MetadataDriver()
    campaign=SecurityCampaign(store,ledger=ledger,signer=signer,observer=mechanics_observer(store,signer),
        driver=driver,approved_plan_refs=[plan])
    result_ref=asyncio.run(campaign.run(plan));result=store.read_record(result_ref)
    assert driver.calls==list(CASES) and result['status']=='BLOCKED' and result['verification'] is None
    assert len(result['cases'])==13 and all(row['status']=='BLOCKED' for row in result['cases'].values())
    assert asyncio.run(campaign.run(plan))==result_ref and driver.calls==list(CASES)
    changed=prepare_security_campaign_plan(store,scope_ref=scope,case_bindings=bindings,
        observer_ref=store.put_blob(b'unit:changed-metadata'),driver_ref=descriptor)
    changed_campaign=SecurityCampaign(store,ledger=ledger,signer=signer,approved_plan_refs=[changed])
    with pytest.raises(CampaignOutcomeUnknown):asyncio.run(changed_campaign.run(changed))
    assert not list(store.iter_records(kinds={'m1-verification-result'}))


def test_unknown_campaign_start_and_cancelled_case_are_not_replayed(context):
    if context is None:return
    store,ledger,signer,scope,_,_,descriptor=context;plan=make_plan(context)
    class MetadataDriver:
        plan_ref=plan;scope_ref=scope;descriptor_ref=descriptor
        def __init__(self):self.calls=[]
        def observe(self,case,**kwargs):
            self.calls.append(case)
            raise asyncio.CancelledError()
    driver=MetadataDriver();campaign=SecurityCampaign(store,ledger=ledger,signer=signer,
        observer=mechanics_observer(store,signer),driver=driver,approved_plan_refs=[plan])
    with pytest.raises(asyncio.CancelledError):asyncio.run(campaign.run(plan))
    assert driver.calls==['RSIV-1']
    diagnostics=list(store.iter_records(kinds={'rsi-security-case-failure'}))
    assert len(diagnostics)==1
    assert diagnostics[0]['record']['exception_type']=='CancelledError'
    assert diagnostics[0]['ref'] in next(iter(ledger.cases(
        ledger.db.execute('SELECT lineage FROM security_campaigns').fetchone()[0]).values()))['evidence_refs']
    with pytest.raises(CampaignOutcomeUnknown):asyncio.run(campaign.run(plan))
    assert driver.calls==['RSIV-1'] and not list(store.iter_records(kinds={'m1-verification-result','rsi-session-result'}))


def test_no_plan_authority_or_observer_boolean_can_authorize_bookkeeping(context):
    if context is None:return
    store,ledger,signer,_,_,_,_=context;plan=make_plan(context)
    campaign=SecurityCampaign(store,ledger=ledger,signer=signer,approved_plan_refs=[])
    with pytest.raises(ValueError,match='Root-approved'):asyncio.run(campaign.run(plan))
    assert ledger.db.execute('SELECT COUNT(*) FROM security_campaigns').fetchone()[0]==0
    for fake in (True,object()):
        with pytest.raises(ValueError):SecurityCampaign(store,ledger=ledger,signer=signer,observer=fake,approved_plan_refs=[plan])


def test_unexpected_missing_observation_stops_further_driver_calls_and_never_creates_pass(context):
    if context is None:return
    store,ledger,signer,scope,_,_,descriptor=context;plan=make_plan(context)
    class MissingObservationDriver:
        plan_ref=plan;scope_ref=scope;descriptor_ref=descriptor
        def __init__(self):self.calls=[]
        def observe(self,case,**kwargs):
            self.calls.append(case)
            raise RuntimeError('Externally supplied observation unavailable')
    driver=MissingObservationDriver()
    campaign=SecurityCampaign(store,ledger=ledger,signer=signer,observer=mechanics_observer(store,signer),
        driver=driver,approved_plan_refs=[plan])
    result=store.read_record(asyncio.run(campaign.run(plan)))
    assert driver.calls==['RSIV-1'] and result['status']=='BLOCKED'
    assert result['cases']['RSIV-1']['status']=='OUTCOME_UNKNOWN' and len(result['cases'])==1
    assert result['verification'] is None and not list(store.iter_records(kinds={'m1-verification-result'}))
    diagnostics=list(store.iter_records(kinds={'rsi-security-case-failure'}))
    assert len(diagnostics)==1
    diagnostic=diagnostics[0]
    assert diagnostic['ref'] in result['cases']['RSIV-1']['evidence_refs']
    assert diagnostic['record']['case_claim_ref']==result['cases']['RSIV-1']['claim_ref']
    assert diagnostic['record']['phase']=='driver_observation'
    assert diagnostic['record']['exception_type']=='RuntimeError'
    assert diagnostic['record']['traceback'].endswith('RuntimeError: Externally supplied observation unavailable\n')
    assert diagnostic['record']['traceback_truncated'] is False
    assert asyncio.run(campaign.run(plan))==next(store.iter_records(kinds={'rsi-security-campaign-status'}))['ref']
    assert len(list(store.iter_records(kinds={'rsi-security-case-failure'})))==1


def test_failure_diagnostic_is_bounded_private_and_does_not_capture_locals(context):
    if context is None:return
    store,ledger,signer,scope,_,_,descriptor=context;plan=make_plan(context)
    class FailedDriver:
        plan_ref=plan;scope_ref=scope;descriptor_ref=descriptor
        def observe(self,case,**kwargs):
            private_local='LOCAL_MUST_NOT_BE_CAPTURED'
            assert private_local
            raise ValueError('x'*20000)
    campaign=SecurityCampaign(store,ledger=ledger,signer=signer,observer=mechanics_observer(store,signer),
        driver=FailedDriver(),approved_plan_refs=[plan])
    result=store.read_record(asyncio.run(campaign.run(plan)))
    diagnostic=next(store.iter_records(kinds={'rsi-security-case-failure'}))
    assert result['verification'] is None and result['cases']['RSIV-1']['status']=='OUTCOME_UNKNOWN'
    assert diagnostic['record']['traceback_truncated'] is True
    assert len(diagnostic['record']['traceback'].encode('utf8'))<=16384
    assert 'LOCAL_MUST_NOT_BE_CAPTURED' not in diagnostic['record']['traceback']


def test_async_custodian_halt_serialization_preserves_actual_counts_and_verifies_signature(context):
    """Unit serialization only; this creates no case proof or qualification."""
    if context is None:return
    store,ledger,signer,_,bindings,_,_=context;plan=make_plan(context)
    class RemoteSignerFixture:
        key_id=signer.key_id
        def public_bytes(self):return signer.public_bytes()
        async def sign(self,value):return signer.sign(value)
    campaign=SecurityCampaign(store,ledger=ledger,signer=RemoteSignerFixture(),approved_plan_refs=[plan],
        public_key=signer.public_bytes(),key_id=signer.key_id)
    state=store.append_record('rsi-security-state',{'schema':'ai4r-rsi-security-state:1','canaries':[],
        'peer_accepts':0,'peer':None,'ledger':None,'library':None})
    observation=store.append_record('unit-serialization-input',{'unit':'No independently observed case; not qualification evidence'})
    obs={'session_ref':bindings['RSIV-11']['session_ref'],'after_ref':state,'attempt_ref':None}
    halt=asyncio.run(campaign._halt(plan,'RSIV-11',observation,obs,[],{}))
    value=store.read_record(halt,contract_id='rsi-session-result');verify(value,signer.public_bytes(),signer.key_id)
    assert value['outcome']=='SECURITY_HALTED' and value['attempts_used']==0 and value['queries_used']==0
    assert value['attempt_refs']==[] and value['qualified_by']=='none' and value['statistics'] is None
    assert not list(store.iter_records(kinds={'m1-verification-result','rsi-security-case-proof'}))


def test_root_scope_can_add_exact_operational_profile_but_cannot_widen_tested_settings(context):
    if context is None:return
    store,_,_,scope_ref,bindings,observer,_=context
    source=store.read_record(bindings['RSIV-1']['session_ref'])
    session=copy.deepcopy(source);session['id']='operational_metadata_session';session['session_id']='operational-metadata-session'
    session['chain_root_ref']=store.put_blob(encoded(dict(session_id=session['session_id'],target_ref=session['target_profile_ref'],
        hash_profile_ref=session['hash_profile_ref'],interface_revision='M1-IF-009@r2')))
    session_ref=store.put_record('rsi-session',session)
    profile=json.loads(store.read_blob(bindings['RSIV-1']['worker_profile_ref']));profile['session_ref']=session_ref
    operational_ref=store.put_blob(encoded(profile))
    scope=json.loads(store.read_blob(scope_ref));scope['worker_profile_refs'].append(operational_ref)
    extended=store.put_blob(encoded(scope))
    plan=prepare_security_campaign_plan(store,scope_ref=extended,case_bindings=bindings,observer_ref=observer)
    assert store.read_record(plan)['scope_ref']==extended
    for field,value in (('memory_mb',256),('timeout_s',2),('process_policy','other_policy'),
                        ('environment_ref',store.put_blob(b'unit:different-environment'))):
        changed=dict(profile);changed[field]=value
        changed_ref=store.put_blob(encoded(changed));changed_scope=copy.deepcopy(scope)
        changed_scope['worker_profile_refs'][-1]=changed_ref
        with pytest.raises(ValueError):
            prepare_security_campaign_plan(store,scope_ref=store.put_blob(encoded(changed_scope)),
                case_bindings=bindings,observer_ref=observer)


def test_pending_typed_start_is_counted_without_fabricating_completed_attempt_or_halt(context):
    if context is None:return
    store,ledger,signer,scope,_,_,descriptor=context;plan=make_plan(context)
    source=store.put_blob(b'unit:inert metadata source identity; never executed')
    class PendingMetadataDriver:
        plan_ref=plan;scope_ref=scope;descriptor_ref=descriptor
        def __init__(self):self.calls=[]
        def observe(self,case,*,case_claim_ref,session_ref,worker_profile_ref):
            self.calls.append(case);claim=store.read_record(case_claim_ref)
            store.append_record('rsi-security-effect-start',dict(schema='ai4r-rsi-security-effect-start:1',
                case_claim_ref=case_claim_ref,session_ref=session_ref,worker_profile_ref=worker_profile_ref,
                attack_id=claim['attack_id'],attack_source_ref=source,recorded_at='2026-10-25T00:00:00Z'))
            raise RuntimeError('Controlled metadata loss; no boundary execution performed')
    driver=PendingMetadataDriver();campaign=SecurityCampaign(store,ledger=ledger,signer=signer,
        observer=mechanics_observer(store,signer),driver=driver,approved_plan_refs=[plan])
    result_ref=asyncio.run(campaign.run(plan));result=store.read_record(result_ref)
    counts=result['actual_counts']['RSIV-1']
    assert driver.calls==['RSIV-1'] and result['status']=='BLOCKED' and result['verification'] is None
    assert counts['attempts_used']==1 and counts['canonical_attempts']==0 and counts['started_attempts']==1
    assert counts['pending_started_attempts']==1 and counts['accounting_status']=='PENDING_STARTED_ATTEMPTS'
    assert counts['queries_used'] is None
    assert not list(store.iter_records(kinds={'rsi-attempt','rsi-session-result','m1-verification-result'}))
    assert asyncio.run(campaign.run(plan))==result_ref and driver.calls==['RSIV-1']


def test_malformed_or_repeated_start_joins_report_unknown_counts_instead_of_zero(context):
    if context is None:return
    store,ledger,signer,scope,bindings,_,_=context;plan=make_plan(context)
    campaign=SecurityCampaign(store,ledger=ledger,signer=signer,approved_plan_refs=[plan])
    binding=bindings['RSIV-1'];source=store.put_blob(b'unit:inert metadata only')
    claim=dict(schema='ai4r-rsi-security-case-claim:1',plan_ref=plan,case_id='RSIV-1',**binding,
        attack_id='unit-pending-claim',started_at='2026-10-25T00:00:00Z')
    claim_ref=store.append_record('rsi-security-case-claim',claim)
    start=dict(schema='ai4r-rsi-security-effect-start:1',case_claim_ref=claim_ref,**binding,
        attack_id=claim['attack_id'],attack_source_ref=source,recorded_at='2026-10-25T00:00:00Z')
    first=store.append_record('rsi-security-effect-start',start)
    counts=campaign._started_accounting(binding,claim_ref,[])
    assert counts['attempts_used']==1 and counts['pending_started_attempts']==1
    store.append_record('rsi-security-effect-start',dict(start,attack_id='foreign-claim'))
    counts=campaign._started_accounting(binding,claim_ref,[])
    assert counts['attempts_used'] is None and counts['accounting_status']=='UNAVAILABLE'
    assert not list(store.iter_records(kinds={'rsi-session-result','m1-verification-result'}))
