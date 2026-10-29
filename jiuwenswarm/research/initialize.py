"""Explicit native M1 catalog installation from protected operator bindings.

This command never creates policy, scientific fixtures, credentials, defaults
or RSI candidates. Ordinary Gateway startup continues to resolve only.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import hashlib
import os
import pwd
import uuid
from pathlib import Path

from .contracts import Principal,ResearchError,validate
from .state import SQLiteRunStore,utc_now,json_bytes


def _completed_calibration_reuse(store, owner, profile_ref, actor):
    """Reuse only a complete original request with still-published exact guards."""
    actor.require('verifier_assets')
    profile,closure=owner._profile(profile_ref)
    closure_sha=hashlib.sha256(json_bytes(closure)).hexdigest()
    with store._lock:
        published=store.connection.execute('SELECT * FROM checking_asset_admissions WHERE closure_sha=?',(closure_sha,)).fetchall()
    if not published:return None
    admissions=owner.admissions.require(profile['bundle_ref'],profile['profile_ref'])
    registered,actual_closure,registration=owner.admissions._registered(profile_ref)
    def require(condition):
        if not condition:raise ResearchError('calibration_reuse_invalid','Original completed checking eligibility cannot be safely reused')
    require(registered==profile and actual_closure==closure and store.read_record(registration)['actor']==actor.account_id)
    admitted={}
    for ref in admissions:
        value=store.read_record(ref)
        require(value['calibration_profile_ref']==profile_ref and value['registration_ref']==registration
            and value['closure']==closure and value['actor']==actor.account_id and value['status']=='admitted')
        admitted[value['asset_kind']]=ref
    require(set(admitted)=={'bundle','criteria'})
    with store._lock:
        rows=store.connection.execute("SELECT * FROM private_calibration_requests WHERE state='completed' AND receipt_ref IS NOT NULL AND cancel_id IS NULL").fetchall()
    candidates=[]
    for row in rows:
        request_ref=json.loads(row['request_ref']);request=store.read_record(request_ref)
        if request.get('calibration_profile_ref')!=profile_ref or request.get('actor_id')!=actor.account_id:continue
        validate('urn:ai4r:private:check-calibration-request:1',request)
        require(store.record_kind(request_ref)=='check-calibration-request' and request['id']==row['id'])
        runtime=store.read_record(request['runtime_ref'])
        validate('urn:ai4r:private:calibration-runtime:1',runtime)
        require(store.record_kind(request['runtime_ref'])=='calibration-runtime'
            and all(runtime[key]==owner.runtime[key] for key in ('configuration_ref','model_selection_profile_ref','deployment_ref','verifier_declaration_ref','limits'))
            and profile_ref in runtime['approved_profile_refs']
            and runtime['case_context_refs'][profile_ref['sha256']]==owner.runtime['case_context_refs'][profile_ref['sha256']])
        receipt_ref=json.loads(row['receipt_ref']);receipt=store.read_record(receipt_ref)
        require(store.record_kind(receipt_ref)=='calibration-request-result' and receipt['request_ref']==request_ref
            and receipt['status']=='completed' and receipt.get('reason_code') is None
            and receipt['bundle_admission_ref']==admitted['bundle'] and receipt['criteria_admission_ref']==admitted['criteria'])
        required={case['case_id'] for case in profile['cases']};observed={}
        for ref in receipt['measurement_refs']:
            value=store.read_record(ref)
            require(store.record_kind(ref)=='calibration-measurement' and value['profile_ref']==profile_ref
                and value['registration_ref']==registration and value['status']=='matched' and value['case_id'] not in observed)
            with store._lock:
                attempt=store.connection.execute('SELECT state,receipt_ref FROM calibration_attempts WHERE profile_sha=? AND case_id=?',
                    (profile_ref['sha256'],value['case_id'])).fetchone()
            require(attempt is not None and attempt['state']=='matched' and json.loads(attempt['receipt_ref'])==ref)
            observed[value['case_id']]=ref
        require(set(observed)==required)
        released={json_bytes(ref) for admission in admissions for ref in store.read_record(admission)['measurement_refs']}
        require(released=={json_bytes(ref) for ref in observed.values()})
        candidates.append({**receipt,'reused':True,'original_receipt_ref':receipt_ref,'reuse_runtime_ref':owner.runtime_ref})
    require(len(candidates)==1)
    return candidates[0]


async def initialize_profile(*, calibrate=False, concurrency=2):
    if os.environ.get('JIUWENSWARM_M1_PROFILE')!='1' or os.name!='posix' or os.geteuid()!=10001:
        raise ResearchError('initialization_blocked','Use the explicit native M1 initializer as its configured OS operator identity')
    locator=os.environ.get('JIUWENSWARM_M1_BOOTSTRAP_BINDINGS')
    configuration_path=os.environ.get('JIUWENSWARM_M1_CONFIG','/etc/ai4r/config.yaml')
    if not locator and os.environ.get('JIUWENSWARM_M1_LOCAL_RESEARCH')=='1':
        # docker exec inherits container configuration, not the supervisor's
        # child environment. Resolve only this explicitly opted-in installed
        # generation; do not capture or replace any operator file here.
        from .local_profile import PROFILE_NAME
        captured=Path(os.environ.get('JIUWENSWARM_M1_STATE','/var/lib/ai4r'))/'operator'/PROFILE_NAME
        locator=str(captured/'bootstrap.json');configuration_path=str(captured/'config.json')
    if not locator:raise ResearchError('initialization_blocked','Protected bootstrap locator is required; policy and defaults are never invented')
    from .bootstrap_gateway import _protected_file
    envelope=json.loads(_protected_file(locator).decode('utf-8'))
    if not isinstance(envelope,dict) or set(envelope)!={'binding_ref'}:raise ResearchError('initialization_blocked','Closed protected binding locator is invalid')
    validate('Ref',envelope['binding_ref'])
    _protected_file(configuration_path)
    root=Path(os.environ.get('JIUWENSWARM_M1_STATE','/var/lib/ai4r'))
    accounts_root=Path(os.environ.get('JIUWENSWARM_M1_ACCOUNTS','/var/lib/ai4r-accounts'))
    if not root.is_absolute() or not accounts_root.is_absolute():raise ResearchError('initialization_blocked','Protected state roots must be absolute')
    store=SQLiteRunStore(root,recover=False,input_root='/workspace/input');accounts=None
    try:
        from .accounts import AccountStore
        from .bootstrap_core import compose_core
        from .operator_config import OperatorConfiguration
        bindings=store.read_record(envelope['binding_ref'])
        required={'workspace_id','host_id','configuration_ref','model_selection_profile_ref','deployment_ref','protected_options'}
        if (not required<=set(bindings) or not isinstance(bindings['protected_options'],dict)
            or any(not isinstance(bindings[k],str) or not bindings[k] for k in ('workspace_id','host_id'))):
            raise ResearchError('initialization_blocked','Captured bootstrap bindings are incomplete')
        for key in ('configuration_ref','model_selection_profile_ref','deployment_ref'):
            validate('Ref',bindings[key]);store.read_blob(bindings[key])
        operator=OperatorConfiguration.load(configuration_path,resolve_profile=store.read_record)
        if store.read_record(bindings['configuration_ref']).get('operator')!=operator.snapshot():
            # The common bare snapshot form remains compatible.
            if store.read_record(bindings['configuration_ref'])!=operator.snapshot():
                raise ResearchError('initialization_blocked','Captured configuration differs from the single approved operator file')
        accounts=AccountStore(accounts_root);account=accounts.primary()['account_id'];workspace=bindings['workspace_id']
        principal=Principal(account,frozenset({workspace}),frozenset({'status','readiness','submit','reconcile','cancel','export','upload','list_uploads','delete_upload','settings'}),frozenset({'researcher','reviewer'}))
        uid,gid=os.geteuid(),os.getegid()
        actor=Principal('os:'+str(uid)+':'+pwd.getpwuid(uid).pw_name,operations=frozenset({'library_admit','library_standing','verifier_assets'}))
        # Explicit initialization uses the live owned ports. Their existence
        # grants no calibration, confinement qualification or admission PASS.
        from .native_ports import _session, APP_UID
        from .bridge import ModelBridgeClient
        from .private_rpc import PrivateRPCClient
        from .executor_rpc import ExecutorClient, PROTOCOL
        session=_session('/run/ai4r',APP_UID)
        model=ModelBridgeClient('/run/ai4r/model.sock',peer_uid=APP_UID,**session)
        executor=ExecutorClient(PrivateRPCClient('/run/ai4r-executor/executor.sock',protocol=PROTOCOL,
            peer_uid=0,socket_mode=0o660,**session))
        options=bindings['protected_options'];calibration_results=[]
        development=options.get('development_builtin_catalog') is True
        if development and calibrate:
            raise ResearchError('initialization_blocked','Local development builtins are explicitly unqualified; use separate strict bindings for calibration')
        if calibrate:
            # The explicit operator action uses the same immutable profiles and
            # live owned model port that AgentServer registered at startup.
            # Durable per-case claims prevent a resumed command replaying calls.
            from .calibration_authority import CalibrationAuthority
            runtime_ref=options.get('calibration_runtime_ref')
            if runtime_ref is None:raise ResearchError('initialization_blocked','No authored protected calibration runtime is captured')
            authority=CalibrationAuthority(store,runtime_ref,configuration_ref=bindings['configuration_ref'],
                model_selection_profile_ref=bindings['model_selection_profile_ref'],deployment_ref=bindings['deployment_ref'],
                policy_ref=operator.snapshot()['cc']['plan_policy_ref'],model=model)
            profiles=options.get('calibration_profile_refs')
            if profiles!=authority.runtime['approved_profile_refs']:
                raise ResearchError('initialization_blocked','Explicit catalog calibration profiles differ from the protected runtime')
            limiter=asyncio.Semaphore(concurrency);stop=asyncio.Event();active={}
            async def measure(profile):
                async with limiter:
                    if stop.is_set():
                        return {'status':'not_run','calibration_profile_ref':profile,'reason_code':'earlier_profile_blocked'}
                    # Adapter bindings are profile-local capabilities. Share
                    # durable claims, never a mutable adapter registry between
                    # independent concurrent profile executions.
                    owner=CalibrationAuthority(store,runtime_ref,configuration_ref=bindings['configuration_ref'],
                        model_selection_profile_ref=bindings['model_selection_profile_ref'],deployment_ref=bindings['deployment_ref'],
                        policy_ref=operator.snapshot()['cc']['plan_policy_ref'],model=model)
                    reused=_completed_calibration_reuse(store,owner,profile,actor)
                    if reused is not None:return reused
                    action='local-catalog:'+runtime_ref['sha256']+':'+profile['sha256']
                    request_ref=owner.start(profile,actor,action)
                    active[profile['sha256']]=(owner,request_ref)
                    try:
                        result=await owner.execute(profile,actor,action)
                        if result['status']!='completed' and not stop.is_set():
                            stop.set()
                            # Do not start another profile after a known fault.
                            # Contain already-issued sibling calls through their
                            # actual owner; never erase or replay their claims.
                            containment=[]
                            for key,(other,other_request) in list(active.items()):
                                if key==profile['sha256']:continue
                                try:
                                    if other.inspect_calibration({'request_ref':other_request})['state']=='running':
                                        containment.append(await other.cancel_calibration({'request_ref':other_request}))
                                except ResearchError as error:
                                    containment.append({'request_ref':other_request,'contained':False,'reason_code':error.code})
                            if containment:result['sibling_containment']=containment
                        return result
                    finally:active.pop(profile['sha256'],None)
            calibration_results=await asyncio.gather(*(measure(profile) for profile in profiles))
            blocked=[row for row in calibration_results if row['status']!='completed']
            if blocked:
                receipt=store.append_record('catalog-initialization',{'id':'catalog-init:'+uuid.uuid4().hex,
                    'recorded_at':utc_now(),'status':'blocked','runtime_ready':False,'binding_ref':envelope['binding_ref'],
                    'calibration_results':calibration_results,'diagnostics':[{'code':'catalog_calibration_blocked',
                        'detail':'At least one real independently measured authored guard case did not qualify'}],
                    'limitations':options.get('calibration_limitations',[])})
                return {**store.read_record(receipt),'receipt_ref':receipt}
        composition=await compose_core(store=store,operator=operator,model=model,executor=executor,readiness=None,upload_manager=None,
            principal=principal,operator_actor=actor,configuration_ref=bindings['configuration_ref'],
            model_selection_profile_ref=bindings['model_selection_profile_ref'],deployment_ref=bindings['deployment_ref'],
            workspace_id=workspace,initialize=True,protected_options=options)
        science_ref=None
        if not composition.diagnostics and options.get('local_science_resources_ref') is not None:
            from .local_science import capture_local_science_runtime
            from .local_profile import _write_once
            resources=store.read_record(options['local_science_resources_ref'])
            entries=[composition.library.get(row['pin']['cc_name'],row['pin']['cc_version']) for row in composition.installed.values()]
            science_ref=capture_local_science_runtime(store,configuration_ref=bindings['configuration_ref'],
                policy_ref=operator.snapshot()['cc']['plan_policy_ref'],resource_inventory_ref=options['resource_inventory_ref'],
                entries=entries,approved_environments=resources['approved_environments'],
                scoring_profile=resources.get('scoring_profile'))
            _write_once(Path(configuration_path).parent/'science.json',{'binding_ref':science_ref})
        try:library_ref=composition.library.snapshot()
        except ResearchError:library_ref=None
        record={'id':'catalog-init:'+uuid.uuid4().hex,'recorded_at':utc_now(),'binding_ref':envelope['binding_ref'],
            'configuration_ref':bindings['configuration_ref'],'actor':{'account_id':account,'os_uid':uid,'os_gid':gid,'operator_id':actor.account_id},
            'status':'blocked' if composition.diagnostics else 'initialized','runtime_ready':False,
            'qualification_status':'not_run' if development else 'strict_checking_eligibility_required',
            'library_snapshot_ref':library_ref,'static_template_ref':composition.static_template_ref,
            'admission_refs':[row['admission_ref'] for row in composition.installed.values() if 'admission_ref' in row]+[
                ref for diagnostic in composition.diagnostics for ref in diagnostic.get('evidence_refs',[])],
            'diagnostics':composition.diagnostics,
            'calibration_results':calibration_results,'science_runtime_ref':science_ref,
            'limitations':(['Local development builtins selected; model-based qualification is NOT_RUN and no qualification PASS is claimed; per-request verifiers and gates remain active']
                if development else ['Explicit fixed-catalog installation only; runtime credentials, confinement, scientific resources and required verification remain separately qualified'])}
        receipt=store.append_record('catalog-initialization',record)
        return {**record,'receipt_ref':receipt}
    finally:
        if accounts is not None:accounts.close()
        store.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Explicitly initialize the frozen M1 catalog from protected operator and bootstrap bindings')
    parser.add_argument('--json',action='store_true',help='Emit the structured initialization receipt (default)')
    parser.add_argument('--calibrate',action='store_true',help='Explicitly run captured independent guard cases with real subscription calls before admission')
    parser.add_argument('--concurrency',type=int,choices=(1,2,3),default=2,help='Bound independent profile calls; never replay an issued case')
    args=parser.parse_args(argv)
    try:
        result=asyncio.run(initialize_profile(calibrate=args.calibrate,concurrency=args.concurrency))
    except (ResearchError,ValueError,OSError,UnicodeError) as exc:
        # Never echo protected records, credentials, URLs or raw exceptions.
        result={'status':'blocked','runtime_ready':False,'diagnostics':[{'code':getattr(exc,'code','initialization_blocked'),
            'detail':'Protected initialization prerequisites are unavailable or invalid'}]}
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0 if result['status']=='initialized' else 2


if __name__=='__main__':raise SystemExit(main())
