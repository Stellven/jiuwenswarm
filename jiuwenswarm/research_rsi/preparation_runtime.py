"""Finite UID12002 preparation administration; no publication or approval.

Root approves exact requests/plans/preparations and explicit import originals.
This facade only writes custodian-private records, never controller exports,
candidate inboxes, review decisions, model credentials or operational keys.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

from .records import RecordStore,encoded
from .session_policy import validate_private,_contracts
from .worker import PublicBytes,WorkerClient,validate_profile,ref
from .targets.ranking_preparation import (
    require_custodian_store,prepare_ranking,verify_calibration2,freeze_prepared_target,
)
from .calibration import prepare_calibration_plan,CalibrationLedger,RankingCalibrationCollector,_scope,PLAN_SCHEMA
from .calibration_materials import prepare_calibration_materials

CONFIG_FILE=Path('/run/ai4r-rsi/preparation-service.json')
CONFIG_SCHEMA='urn:ai4r:private:rsi-preparation-service:1'
REQUEST_SCHEMA='urn:ai4r:private:rsi-preparation-request:1'
REQUEST_SCHEMAS={'ai4r-rsi-preparation-request:1':REQUEST_SCHEMA,
                 'ai4r-rsi-preparation-request:2':'urn:ai4r:private:rsi-preparation-request:2'}
BUNDLE_SCHEMA='urn:ai4r:private:rsi-preparation-materials:1'
OPERATIONS=('prepare-ranking','plan-calibration','prepare-materials','collect-calibration','verify-freeze',
            'compile-helper-session','assemble-job2','prepare-session-materials','prepare-helper')


class PreparationUnavailable(ValueError):pass


def _need(value):
    if not value:raise PreparationUnavailable('Protected custodian preparation facts or explicit root approval are unavailable')


def _json(raw):
    def pairs(values):
        result={}
        for key,value in values:
            _need(key not in result);result[key]=value
        return result
    return json.loads(raw.decode('utf8'),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(PreparationUnavailable('Nonfinite private preparation capture')))


def _path(value):
    path=Path(value)
    _need(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)))
    return path


def _identity():
    _need(sys.platform=='linux' and hasattr(os,'geteuid') and os.geteuid()==12002)


def _private_root(value):
    """Check native custody before SQLite can create a single file."""
    _identity();path=_path(value);meta=path.stat()
    _need(stat.S_ISDIR(meta.st_mode) and meta.st_uid==12002 and stat.S_IMODE(meta.st_mode)==0o700)
    _native_fs(path)
    return path


def _native_fs(path):
    class FS(ctypes.Structure):_fields_=[('kind',ctypes.c_long),('padding',ctypes.c_byte*248)]
    filesystem=FS()
    _need(ctypes.CDLL(None,use_errno=True).statfs(os.fsencode(path),ctypes.byref(filesystem))==0)
    _need(filesystem.kind in (0xEF53,0x58465342,0x9123683E,0x01021994,0x794c7630,0x2FC12FC1))


def _root_config_bytes():
    path=_path(CONFIG_FILE)
    descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        meta=os.fstat(descriptor)
        _need(stat.S_ISREG(meta.st_mode) and meta.st_uid==0 and meta.st_gid==12002
              and stat.S_IMODE(meta.st_mode)==0o440 and meta.st_nlink==1 and 0<meta.st_size<=1024*1024)
        with os.fdopen(descriptor,'rb',closefd=False) as stream:return stream.read(1024*1024+1)
    finally:os.close(descriptor)


def load_config():
    _identity();config=_json(_root_config_bytes());validate_private(CONFIG_SCHEMA,config)
    return config


def _approved(pin,allowed):
    ref(pin);_need(encoded(pin) in {encoded(value) for value in allowed})


def _imports(config,store):
    # No recursive Ref walk: root separately nominates every original byte.
    roots=[_path(value) for value in config['public_roots']]
    private=_path(config['record_root']);inputs=_path(config['worker']['requests_root'])
    for root in roots:
        _need(not any(root==other or root.is_relative_to(other) or other.is_relative_to(root) for other in (private,inputs)))
    public=PublicBytes(roots)
    for pin in config['public_original_refs']:
        try:store.read(pin)
        except FileNotFoundError:
            raw=public.read(pin)
            _need(hashlib.sha256(raw).hexdigest()==pin['sha256'])
            store.put_ref(pin,raw)
    require_custodian_store(store)


def _plan(config,store,plan_ref):
    _approved(plan_ref,config['approved_plan_refs'])
    plan=store.get(plan_ref);validate_private(PLAN_SCHEMA,plan)
    _approved(plan['preparation_ref'],config['approved_preparation_refs'])
    _approved(plan['worker_profile_ref'],config['worker']['profile_refs'])
    values={key:plan[key] for key in ('preparation_ref','review_ref','target_ref','fixture_manifest_ref','session_ref','worker_profile_ref')}
    scope=_scope(store,**values)
    _need(prepare_calibration_plan(store,**values,invocation_wall_s=plan['invocation_wall_s'],
        evidence_wall_s=plan['evidence_wall_s'],wall_s=plan['wall_s'])==plan_ref)
    profile=scope[-1]
    from .process_policy import POLICY
    _need(profile.get('schema')=='ai4r-rsi-worker-profile:3' and profile.get('process_policy')==POLICY)
    return plan,scope


def _qualification(store):
    from .security_installation import installed_consumer_qualification
    from .candidate_bindings import CandidateResolver
    authority=installed_consumer_qualification(store,candidate_resolver=CandidateResolver(read=store.read,locate=store.candidate_binding_ref))
    _need(authority is not None)
    return authority


def _signer(config):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from .signing import Signer
    path=_path(config['signing_key_file']);_native_fs(path)
    descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        meta=os.fstat(descriptor)
        _need(stat.S_ISREG(meta.st_mode) and meta.st_uid==12002 and stat.S_IMODE(meta.st_mode)==0o600
              and meta.st_nlink==1 and meta.st_size==32)
        with os.fdopen(descriptor,'rb',closefd=False) as stream:key=stream.read(33)
    finally:os.close(descriptor)
    return Signer(Ed25519PrivateKey.from_private_bytes(key),config['signer_key_id'])


def _guard(authority,plan,target):
    from .qualification import require_qualification
    return require_qualification(authority,'trial',session_ref=plan['session_ref'],
        worker_profile_ref=plan['worker_profile_ref'],candidate_ref=target['parent_ref'])


def _bundle(store,rows):
    bundle={'schema':'ai4r-rsi-preparation-materials:1','materials':[
        {'ref':row['ref'],'bytes_base64':base64.b64encode(row['bytes']).decode('ascii')} for row in rows]}
    validate_private(BUNDLE_SCHEMA,bundle);_need(len(encoded(bundle))<=16*1024*1024)
    return store.put(bundle)


async def _collect(config,store,plan,scope,plan_ref):
    from .fixed_resources import FixtureEvaluator
    _,target,manifest,session,profile=scope
    requests_root=_private_root(config['worker']['requests_root'])
    private=_path(config['record_root']);key=_path(config['signing_key_file'])
    _need(not (requests_root==private or requests_root.is_relative_to(private) or private.is_relative_to(requests_root))
          and not key.is_relative_to(requests_root))
    authority=_qualification(store);_guard(authority,plan,target)
    requests=RecordStore(requests_root)
    ledger=None
    try:
        require_custodian_store(requests)
        binding=config['worker']
        worker=WorkerClient(socket_path=binding['socket_path'],session_id=binding['session_id'],capability=binding['capability'],
            requests=requests,profile_ref=plan['worker_profile_ref'],session_ref=plan['session_ref'],hidden=True,
            timeout_s=plan['invocation_wall_s'],target_kind=profile['target_kind'],
            batch_iterations=target['scoring']['batch_iterations'],process_policy=profile['process_policy'])
        evaluator=FixtureEvaluator(manifest=manifest,store=store,worker=worker,session_ref=plan['session_ref'],
            target=target,repeats=session['pass_count_repeats'])
        ledger=CalibrationLedger(store)
        collector=RankingCalibrationCollector(store,ledger=ledger,evaluator=evaluator,qualification=authority,
            approved_plan_refs=config['approved_plan_refs'])
        pin=await collector.collect(plan_ref)
        result=store.get(pin)
        status='COLLECTED_REVIEW_REQUIRED' if result.get('status')=='UNSIGNED_REVIEW_REQUIRED' else 'BLOCKED'
        return {'status':status,'collection_ref':pin}
    finally:
        if ledger is not None:ledger.close()
        requests.close()


def _freeze(config,store,parameters):
    plan,scope=_plan(config,store,parameters['plan_ref'])
    _,target,manifest,_,_=scope
    collection=store.get(parameters['collection_ref'])
    _need(set(collection)=={'schema','status','plan_ref','proposal_ref','exposure_ref','capture_refs'}
          and collection['schema']=='ai4r-rsi-calibration-collection-result:1'
          and collection['status']=='UNSIGNED_REVIEW_REQUIRED' and collection['plan_ref']==parameters['plan_ref']
          and collection['proposal_ref'] is not None)
    # Require the actual once-only private ledger terminal; a request cannot
    # nominate a free-standing producer-shaped collection record as authority.
    ledger=CalibrationLedger(store)
    try:
        state=ledger.lookup(plan['fixture_identity'],parameters['plan_ref'])
        _need(state is not None and state['state']=='complete' and state['result_ref']==parameters['collection_ref']
              and state['started']==state['expected']==plan['expected_invocations'])
    finally:ledger.close()
    template=store.get(parameters['template_ref'])
    # The request may not substitute a new template after actual collection.
    from .targets.ranking_preparation import draft_target
    expected,_=draft_target(store,plan['preparation_ref'],template,review_ref=plan['review_ref'],validate=_contracts().validate)
    _need(expected==target)
    authority=_qualification(store);_guard(authority,plan,target)
    signer=_signer(config)
    installation=authority.installation
    _need(signer.key_id==installation.key_id and signer.public_bytes()==installation.public_key)
    proposal=store.get(collection['proposal_ref'])
    _need(proposal.get('preparation_ref')==plan['preparation_ref'] and proposal.get('review_ref')==plan['review_ref'])
    # Ed25519 signing is deterministic and remains only in memory until every
    # original capture/count/noise/headroom check independently succeeds.
    signed=signer.sign(proposal)
    verify_calibration2(signed,target=target,manifest=manifest,store=store,
        public_key=signer.public_bytes(),key_id=signer.key_id)
    _guard(authority,plan,target)
    calibration_ref=store.put(signed)
    frozen=freeze_prepared_target(store,preparation_ref=plan['preparation_ref'],template=template,
        review_ref=plan['review_ref'],calibration_ref=calibration_ref,
        public_key=signer.public_bytes(),key_id=signer.key_id,validate=_contracts().validate)
    return {'status':'FROZEN_PRIVATE', 'calibration_ref':calibration_ref,**frozen}


async def execute(config,operation,request_ref):
    """Execute one exact root-approved private request; return safe refs only."""
    _identity();validate_private(CONFIG_SCHEMA,config)
    _need(operation in OPERATIONS);_approved(request_ref,config['approved_request_refs'])
    root=_private_root(config['record_root']);store=RecordStore(root)
    try:
        require_custodian_store(store);_imports(config,store)
        request=_json(store.read(request_ref))
        _need(isinstance(request,dict) and request.get('schema') in REQUEST_SCHEMAS)
        validate_private(REQUEST_SCHEMAS[request['schema']],request)
        _need(request['operation']==operation);parameters=request['parameters']
        if operation=='prepare-helper':
            from .targets.ranking_preparation import prepare_helper
            for pin in parameters['prior_preparation_refs']:_approved(pin,config['approved_preparation_refs'])
            pin=prepare_helper(store,**parameters,declaration=store.get(parameters['parent_declaration_ref']))
            return {'status':'PREPARED_REVIEW_REQUIRED','preparation_ref':pin}
        if operation=='compile-helper-session':
            from .session_preparation import compile_helper_session
            return compile_helper_session(store,**{key:value for key,value in parameters.items() if key!='schema'})
        if operation=='assemble-job2':
            from .session_preparation import assemble_job2
            _approved(parameters['preparation_ref'],config['approved_preparation_refs'])
            _approved(parameters['worker_profile_ref'],config['worker']['profile_refs'])
            pin=assemble_job2(store,approved_preparation_refs=config['approved_preparation_refs'],
                **{key:value for key,value in parameters.items() if key!='schema'})
            return {'status':'JOB_COMPILED_NOT_STARTED','job_ref':pin}
        if operation=='prepare-session-materials':
            from .session_preparation import session_public_materials
            _approved(parameters['worker_profile_ref'],config['worker']['profile_refs'])
            projection=session_public_materials(store,approved_public_refs=config['public_original_refs'],
                approved_preparation_refs=config['approved_preparation_refs'],**parameters)
            return {'status':'MATERIALS_PREPARED_PRIVATE','materials_ref':_bundle(store,projection['materials']),
                'required_original_refs':list(projection['required_original_refs']),
                'private_runtime_refs':list(projection['private_runtime_refs'])}
        if operation=='prepare-ranking':
            for pin in parameters['prior_preparation_refs']:_approved(pin,config['approved_preparation_refs'])
            pin=prepare_ranking(store,**parameters,declaration=store.get(parameters['parent_declaration_ref']))
            return {'status':'PREPARED_REVIEW_REQUIRED','preparation_ref':pin}
        if operation=='plan-calibration':
            _approved(parameters['preparation_ref'],config['approved_preparation_refs'])
            _approved(parameters['worker_profile_ref'],config['worker']['profile_refs'])
            profile=validate_profile(store.get(parameters['worker_profile_ref']))
            from .process_policy import POLICY
            _need(profile.get('schema')=='ai4r-rsi-worker-profile:3' and profile.get('process_policy')==POLICY)
            return {'status':'PLAN_APPROVAL_REQUIRED','plan_ref':prepare_calibration_plan(store,**parameters)}
        if operation=='prepare-materials':
            _plan(config,store,parameters['plan_ref'])
            rows=prepare_calibration_materials(store,plan_ref=parameters['plan_ref'],
                approved_plan_refs=config['approved_plan_refs'],parent_body_refs=parameters['parent_body_refs'])
            return {'status':'MATERIALS_PREPARED_PRIVATE','materials_ref':_bundle(store,rows)}
        if operation=='collect-calibration':
            plan,scope=_plan(config,store,parameters['plan_ref'])
            return await _collect(config,store,plan,scope,parameters['plan_ref'])
        return _freeze(config,store,parameters)
    finally:store.close()


def main(argv=None):
    parser=argparse.ArgumentParser(prog='ai4r-rsi-preparation')
    parser.add_argument('operation',choices=OPERATIONS);parser.add_argument('--request-ref',required=True)
    args=parser.parse_args(argv)
    try:
        pin=_json(args.request_ref.encode('utf8'));ref(pin)
        value=asyncio.run(execute(load_config(),args.operation,pin))
        print(json.dumps(value,sort_keys=True));return 2 if value['status']=='BLOCKED' else 0
    except (ValueError,KeyError,TypeError,OSError,AttributeError,RecursionError):
        print(json.dumps({'status':'BLOCKED','reason':'Protected custodian preparation request, actual qualification, independent review or raw calibration evidence is unavailable'}))
        return 2


if __name__=='__main__':raise SystemExit(main())
