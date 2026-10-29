"""Finite custody schema/projection controls; no security programs or probes run."""
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research_records.contracts import ContractData
from jiuwenswarm.research_rsi import security_custody as custody
from jiuwenswarm.research_rsi.records import encoded
from jiuwenswarm.research_rsi.security_campaign import prepare_security_campaign_plan
from tests.unit_tests.research_rsi.test_security_campaign import metadata_scope


def test_validation_custody_config_never_selects_paths_or_ordinary_operations():
    pin={'id':'unit:pin','sha256':'a'*64}
    config=dict(schema='ai4r-rsi-validation-custody:1',plan_ref=pin,scope_ref=pin,attack_pins_ref=pin,
        custodian_key_id='unit:validation',custodian_public_key='A'*43,rpc_session_id='unit:validation',rpc_capability='A'*43)
    validate=ContractData().validate;validate(custody.CONFIG_SCHEMA,config)
    for changed in (dict(config,key_file='/other/key'),dict(config,operations=['sign_terminal']),
                    dict(config,factory='untrusted'),dict(config,approved=True)):
        with pytest.raises(ValueError):validate(custody.CONFIG_SCHEMA,changed)


def test_root_broker_cannot_construct_service_or_read_private_key(monkeypatch):
    if hasattr(os,'geteuid') and os.geteuid()==12002:return
    called=[]
    def forbidden(*args,**kwargs):called.append(True);raise AssertionError('Private-key read attempted outside custodian role')
    monkeypatch.setattr(custody,'_raw',forbidden)
    with pytest.raises(ValueError):custody.ValidationCustody({})
    assert called==[]


@pytest.fixture
def original_projection(tmp_path,monkeypatch):
    if os.name!='posix' or os.geteuid()!=0:
        yield None;return
    store=SQLiteRunStore(tmp_path/'private-core')
    scope_ref,bindings,observer_ref,_=metadata_scope(store)
    empty=store.put_blob(b'');prefix=store.put_blob(b'unit: inert source descriptor; not an executable qualification prefix')
    scope=json.loads(store.read_blob(scope_ref));scope['probe_ref']=empty;scope_ref=store.put_blob(encoded(scope))
    # This intentionally inert metadata projection cannot satisfy the actual
    # FiniteCaseObserver. It only exercises original artifact/index handling.
    attacks=store.put_blob(encoded({'schema':'ai4r-rsi-security-attack-pins:1','program_prefix_ref':prefix,
        'attacks':{case:prefix for case in bindings}}))
    plan=prepare_security_campaign_plan(store,scope_ref=scope_ref,case_bindings=bindings,observer_ref=observer_ref)
    public=tmp_path/'public';public.mkdir();os.chown(public,0,13000);os.chmod(public,0o2750)
    monkeypatch.setattr(custody,'PUBLIC_ROOT',public)
    monkeypatch.setattr(custody,'SOCKET',tmp_path/'absent-validation.sock')
    client=custody.ValidationHaltSigner(store,plan_ref=plan,scope_ref=scope_ref,attack_pins_ref=attacks,
        public_key=b'x'*32,key_id='unit:validation',rpc_session_id='unit:validation',capability='A'*43)
    try:yield store,public,client,empty
    finally:store.close()


def test_actual_core_store_untyped_and_empty_originals_project_without_invented_metadata_fields(original_projection):
    if original_projection is None:return
    store,public,client,empty=original_projection
    assert store.artifact_metadata(empty)=={'media_type':'application/octet-stream'}
    assert custody._kind(store,empty)=='original-bytes'
    typed=store.append_record('unit-protected-kind',{'unit':'Typed original'})
    assert custody._kind(store,typed)=='unit-protected-kind'
    closure_ref,record,observation,claim=client._projection()
    assert record is observation is claim is None
    publication=custody.OriginalBytes(public);closure=publication.get(closure_ref)
    assert closure['case_id'] is None and closure['record_ref'] is None
    rows={encoded(row['ref']):row for row in closure['originals']}
    assert rows[encoded(empty)]['kind']=='original-bytes' and publication.read(empty)==b''
    assert all('key' not in row['kind'] for row in rows.values())
    assert not list(store.iter_records(kinds={'rsi-session-result','execution-receipt','model-call-start'}))


def test_missing_real_validation_custodian_blocks_authority_preflight_without_any_case(original_projection):
    if original_projection is None:return
    store,_,client,_=original_projection
    with pytest.raises(Exception):asyncio.run(client.authorized())
    assert not list(store.iter_records(kinds={'rsi-security-case-claim','rsi-security-effect-start','rsi-session-result'}))


def test_preflight_rejects_authenticated_reply_with_foreign_scope_or_key(original_projection):
    if original_projection is None:return
    _,_,client,_=original_projection
    async def reply(operation,payload,**kwargs):
        assert operation=='validation_readiness' and set(payload)=={'closure_ref'}
        return dict(plan_ref=client.plan_ref,scope_ref=client.scope_ref,attack_pins_ref=client.attack_pins_ref,
            custodian_key_id=client.key_id,public_key_sha256='f'*64,allowed_purpose='security_validation_halt_only')
    client.rpc=SimpleNamespace(call=reply)
    with pytest.raises(ValueError):asyncio.run(client.authorized())


def test_original_claim_metadata_rejects_rebound_attack_and_execution_invocation(original_projection):
    # These are inert metadata records, never boundary execution or acceptance.
    if original_projection is None:return
    store,_,client,_=original_projection
    case='RSIV-1';binding=store.read_record(client.plan_ref)['case_bindings'][case]
    attack='security-case-'+custody._digest([client.plan_ref,case])[:40]
    claim=dict(plan_ref=client.plan_ref,case_id=case,attack_id=attack,**binding)
    claim_ref=store.append_record('rsi-security-case-claim',claim)
    obs=dict(case_id=case,attack_id=attack,execution_ref=None,**binding)
    custody._claim_binding(store,claim_ref,client.plan_ref,case,binding,obs)
    foreign='security-case-'+'f'*40
    changed_claim=store.append_record('rsi-security-case-claim',dict(claim,attack_id=foreign))
    with pytest.raises(ValueError):
        custody._claim_binding(store,changed_claim,client.plan_ref,case,binding,dict(obs,attack_id=foreign))
    execution=store.append_record('unit-inert-execution-metadata',{'job_id':attack,'invocation_id':'foreign'})
    with pytest.raises(ValueError):
        custody._claim_binding(store,claim_ref,client.plan_ref,case,binding,dict(obs,execution_ref=execution))
    assert not list(store.iter_records(kinds={'execution-receipt','rsi-session-result'}))


def test_service_operation_table_is_validation_specific_only():
    # Constructor-free inspection tests only the fixed transport policy. It is
    # not a service role/key/observer authority and cannot sign any record.
    service=object.__new__(custody.ValidationCustody)
    service.config={'rpc_session_id':'unit:validation','rpc_capability':'A'*43}
    server=service.server()
    assert server.allowed_uids==frozenset({0})
    assert set(server.handlers)=={'validation_readiness','sign_validation_halt'}
    assert not set(server.handlers)&{'oracle','evaluate','session_start','sign_terminal','publish','activate'}


def test_real_policy_halt_over_separate_uid_custodian_rpc(tmp_path,monkeypatch):
    """One real mutation refusal; no kernel program, provider or qualification."""
    if os.name!='posix' or os.geteuid()!=0:return
    from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,NoEncryption
    from jiuwenswarm.research.contracts.rsi_security_cases import CASES,FiniteCaseObserver,KERNEL_CASES,KERNEL_PROGRAMS,POLICY_PROGRAMS
    from jiuwenswarm.research_rsi.process_policy import program_prefix
    from jiuwenswarm.research_rsi.records import RecordStore
    from jiuwenswarm.research_rsi.security_campaign import CampaignLedger,SecurityCampaign
    from jiuwenswarm.research_rsi.security_driver import SecurityBoundaryDriver
    from jiuwenswarm.research_rsi.signing import verify
    from jiuwenswarm.research_rsi.worker import PublicBytes,WorkerBroker
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    f=make_unit_package(tmp_path/'core');store=f['store'];store.root.chmod(0o700)
    capture=RecordStore(tmp_path/'capture');ledger=None;pid=None;stop_write=None
    try:
        scope_ref,bindings,observer_ref,_=metadata_scope(store)
        scope=store.read_record(scope_ref)
        public=custody.OriginalBytes(tmp_path/'worker-public',writable=True)
        for pin in scope['worker_profile_refs']:public.put_ref(pin,store.read_blob(pin))
        # Copy installed finite source originals for observer identity checks.
        # They are never submitted for execution in this policy-only test.
        prefix=program_prefix();prefix_ref=store.put_blob(prefix)
        pins=dict(schema='ai4r-rsi-security-attack-pins:1',program_prefix_ref=prefix_ref,
            attacks={case:store.put_blob(prefix+KERNEL_PROGRAMS[case] if case in KERNEL_CASES else POLICY_PROGRAMS[case]) for case in CASES})
        pins_ref=store.put_blob(encoded(pins));unit_signer=f['signer']
        observer=FiniteCaseObserver(store.read_blob,store.record_kind,attack_pins=pins,
            public_key=unit_signer.public_bytes(),key_id=unit_signer.key_id)
        broker=WorkerBroker(root=tmp_path/'worker',cgroup_root=None,profiles=scope['worker_profile_refs'],
            public_reader=PublicBytes([public.root]),input_reader=PublicBytes([public.root]),capture_store=capture,hidden=True)
        driver=SecurityBoundaryDriver(store,worker_owner=broker,scope_ref=scope_ref,case_bindings=bindings,
            attack_pins=pins,public_key=unit_signer.public_bytes(),key_id=unit_signer.key_id)
        plan=prepare_security_campaign_plan(store,scope_ref=scope_ref,case_bindings=bindings,
            observer_ref=observer_ref,driver_ref=driver.descriptor_ref)
        driver.bind_plan(plan)
        evidence=tmp_path/'evidence';evidence.mkdir();os.chown(evidence,0,13000);evidence.chmod(0o2750)
        private=tmp_path/'custodian';private.mkdir();private.chmod(0o700)
        keyfile=private/'signing.key'
        keyfile.write_bytes(unit_signer.key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()))
        keyfile.chmod(0o600);os.chown(keyfile,12002,12002);os.chown(private,12002,12002)
        configfile=tmp_path/'custody.json';socket=tmp_path/'rpc'/'sign.sock'
        socket.parent.mkdir();socket.parent.chmod(0o710);os.chown(socket.parent,12002,13000)
        config=dict(schema='ai4r-rsi-validation-custody:1',plan_ref=plan,scope_ref=scope_ref,attack_pins_ref=pins_ref,
            custodian_key_id=unit_signer.key_id,custodian_public_key=base64.urlsafe_b64encode(unit_signer.public_bytes()).decode().rstrip('='),
            rpc_session_id='unit:validation-real-policy',rpc_capability='A'*43)
        configfile.write_bytes(encoded(config));os.chown(configfile,0,13000);configfile.chmod(0o640)
        for parent in (tmp_path,*tmp_path.parents):
            if parent==Path('/tmp'):break
            parent.chmod(0o751)
        for name,value in {'PUBLIC_ROOT':evidence,'PRIVATE_ROOT':private,'KEY_FILE':keyfile,'CONFIG_FILE':configfile,'SOCKET':socket}.items():
            monkeypatch.setattr(custody,name,value)
        client=custody.ValidationHaltSigner(store,plan_ref=plan,scope_ref=scope_ref,attack_pins_ref=pins_ref,
            public_key=unit_signer.public_bytes(),key_id=unit_signer.key_id,rpc_session_id=config['rpc_session_id'],capability=config['rpc_capability'])
        # Prepublish static originals while root; the service owns only its key
        # and signature journal and reads this root-owned projection.
        client._projection()
        stop_read,stop_write=os.pipe();pid=os.fork()
        if pid==0:
            try:
                os.close(stop_write)
                os.setgroups([13000]);os.setgid(12002);os.setuid(12002)
                async def service_until_parent_done():
                    task=asyncio.create_task(custody.serve())
                    await asyncio.to_thread(os.read,stop_read,1)
                    task.cancel()
                    try:await task
                    except asyncio.CancelledError:pass
                asyncio.run(service_until_parent_done())
            except BaseException:
                import traceback;traceback.print_exc()
                os._exit(1)
            os._exit(0)
        os.close(stop_read)
        for _ in range(100):
            if socket.exists():break
            ended,_=os.waitpid(pid,os.WNOHANG)
            assert ended==0,'Separate validation custodian failed before readiness'
            time.sleep(.05)
        assert socket.exists(),'Separate validation custodian did not start'
        ledger=CampaignLedger(store)
        runner=SecurityCampaign(store,ledger=ledger,signer=client,observer=observer,driver=driver,approved_plan_refs=[plan])
        async def policy_halt():
            assert await client.authorized() is True
            case='RSIV-4';binding=bindings[case]
            claim=dict(schema='ai4r-rsi-security-case-claim:1',plan_ref=plan,case_id=case,**binding,
                attack_id='security-case-'+custody._digest([plan,case])[:40],started_at='2026-10-25T00:00:00Z')
            claim_ref=store.append_record('rsi-security-case-claim',claim)
            obs_ref=await driver.observe(case,case_claim_ref=claim_ref,**binding)
            obs,records=runner._records(obs_ref);proof=observer(case,scope,tuple(records))
            result_ref=await runner._halt(plan,case,obs_ref,obs,records,proof,claim_ref)
            result=store.read_record(result_ref);verify(result,unit_signer.public_bytes(),unit_signer.key_id)
            assert result['outcome']=='SECURITY_HALTED' and result['attempts_used']==result['queries_used']==0
            assert result['child'] is None and result['qualified_by']=='none'
            # Exact completed retry retrieves the original signature, never a
            # second session signature or a new terminal timestamp.
            unsigned={k:v for k,v in result.items() if k not in {'signature','signer_key_id'}}
            assert await client.sign(unsigned)==result
            return result_ref
        result_ref=asyncio.run(policy_halt())
        assert store.record_kind(result_ref)=='rsi-session-result'
        assert not list(store.iter_records(kinds={'execution-receipt','rsi-security-effect-start','model-call-start'}))
        assert not broker.issued and not broker.executor.active
    finally:
        if pid:
            if stop_write is not None:
                try:os.write(stop_write,b'x')
                except BrokenPipeError:pass
                os.close(stop_write)
            try:os.waitpid(pid,0)
            except ChildProcessError:pass
        if ledger is not None:ledger.close()
        capture.close();store.close()
