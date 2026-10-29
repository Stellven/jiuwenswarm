"""Real policy boundaries with deliberately unavailable kernel delegation.

This retains five genuine policy denials, eight unavailable kernel cases and
no complete qualification. No kernel validation programs execute in this test.
"""
import asyncio
import copy
import json
import os
from pathlib import Path
import sys

from jiuwenswarm.research.contracts.rsi_security import CASES
from jiuwenswarm.research.contracts.rsi_security_cases import FiniteCaseObserver,KERNEL_CASES,KERNEL_PROGRAMS,POLICY_PROGRAMS
from jiuwenswarm.research_records.original_bytes import OriginalBytes
from jiuwenswarm.research_rsi.process_policy import program_prefix,security_program
from jiuwenswarm.research_rsi.records import RecordStore,encoded
from jiuwenswarm.research_rsi.security_campaign import CampaignLedger,SecurityCampaign,prepare_security_campaign_plan
from jiuwenswarm.research_rsi.security_driver import SecurityBoundaryDriver
from jiuwenswarm.research_rsi.worker import PublicBytes,WorkerBroker
from tests.unit_tests.research_rsi.fixture_package import make_unit_package


def test_real_policy_denials_are_retained_while_missing_kernel_never_qualifies(tmp_path):
    if sys.platform!='linux' or os.geteuid()!=0:return
    f=make_unit_package(tmp_path/'core');store=f['store'];store.root.chmod(0o700)
    capture=RecordStore(tmp_path/'capture');ledger=None
    try:
        unit=f['session']['configuration_ref'];bindings={};profiles=[]
        public=OriginalBytes(tmp_path/'public',writable=True)
        for case in CASES:
            session=copy.deepcopy(f['session']);session['session_id']='validation:'+case.lower();session['pass_count_repeats']=1
            genesis=store.read_record(session['chain_root_ref']);genesis['session_id']=session['session_id']
            session['chain_root_ref']=store.put_blob(encoded(genesis));session_ref=store.put_record('rsi-session',session)
            profile=dict(schema='ai4r-rsi-worker-profile:3',process_policy='single_process_seccomp_v1',target_kind='ranking-v1',
                session_ref=session_ref,target_ref=session['target_profile_ref'],parent_ref=f['attempt']['parent_ref'],
                contract_ref=unit,environment_ref=unit,hardware_ref=unit,memory_mb=64,pids_max=16,timeout_s=1)
            profile_ref=store.put_blob(encoded(profile));public.put_ref(profile_ref,store.read_blob(profile_ref));profiles.append(profile_ref)
            bindings[case]=dict(session_ref=session_ref,worker_profile_ref=profile_ref)
        scope=dict(schema='ai4r-rsi-security-scope:1',id='controlled:unavailable-kernel',runtime_build_ref=unit,environment_ref=unit,
            worker_driver_ref=unit,executor_ref=unit,probe_ref=unit,kernel_release='not-an-operational-runtime',
            platform='linux/amd64',worker_profile_refs=profiles)
        scope_ref=store.put_blob(encoded(scope))
        prefix=store.put_blob(program_prefix())
        pins=dict(schema='ai4r-rsi-security-attack-pins:1',program_prefix_ref=prefix,
            attacks={case:store.put_blob(security_program(KERNEL_PROGRAMS[case]) if case in KERNEL_CASES else POLICY_PROGRAMS[case]) for case in CASES})
        observer=FiniteCaseObserver(store.read_blob,store.record_kind,attack_pins=pins,
            public_key=f['signer'].public_bytes(),key_id=f['signer'].key_id)
        broker=WorkerBroker(root=tmp_path/'worker',cgroup_root=None,profiles=profiles,public_reader=PublicBytes([public.root]),
            input_reader=PublicBytes([public.root]),capture_store=capture,hidden=True)
        driver=SecurityBoundaryDriver(store,worker_owner=broker,scope_ref=scope_ref,case_bindings=bindings,
            attack_pins=pins,public_key=f['signer'].public_bytes(),key_id=f['signer'].key_id)
        owner_source=store.put_blob(Path(__file__).read_bytes())
        plan=prepare_security_campaign_plan(store,scope_ref=scope_ref,case_bindings=bindings,observer_ref=owner_source,driver_ref=driver.descriptor_ref)
        driver.bind_plan(plan);ledger=CampaignLedger(store)
        runner=SecurityCampaign(store,ledger=ledger,signer=f['signer'],observer=observer,driver=driver,approved_plan_refs=[plan])
        result_ref=asyncio.run(runner.run(plan));result=store.read_record(result_ref)
        assert result['status']=='BLOCKED' and result['verification'] is None
        observed={case for case,row in result['cases'].items() if row['status']=='OBSERVED'}
        assert observed==set(CASES)-KERNEL_CASES,result['cases']
        assert not list(store.iter_records(kinds={'execution-receipt','rsi-security-effect-start'}))
        assert all(row['outcome']=='SECURITY_HALTED' for row in (entry['record'] for entry in store.iter_records(kinds={'rsi-session-result'})))
        assert result['actual_counts']['RSIV-12']['queries_used']==1
        assert asyncio.run(runner.run(plan))==result_ref
        assert not broker.issued and not broker.executor.active
    finally:
        if ledger is not None:ledger.close()
        capture.close();store.close()
