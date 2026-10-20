"""Finite human Library commands; OS permission never grants qualification."""
from __future__ import annotations
import argparse
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import pwd
import uuid
from .contracts import Principal,ResearchError,validate
from .state import SQLiteRunStore,json_bytes,utc_now


def require(value,reason):
    if not value:raise ResearchError('operator_request',reason)


def operator_identity():
    if os.name!='posix' or os.environ.get('JIUWENSWARM_M1_PROFILE')!='1' or os.geteuid()!=0:
        raise ResearchError('operator_identity','The finite Library command requires an explicit Linux OS operator')
    return Principal('os:0:'+pwd.getpwuid(0).pw_name,operations=frozenset({'library_admit','library_standing','verifier_assets'}))


class OperatorLibrary:
    """Protected composition object; it is never exposed through client tokens."""
    FIELDS={
        'inspect':{'declaration_ref'},
        'associate-checks':{'declaration_ref','bundle_ref','profile_ref','evidence_refs'},
        'admit':{'declaration_ref','body_refs','memory_mb','evidence_refs'},
        'admit-rsi':{'package_path'},
        'standing':{'name','version','to_standing','effect_scope','reason'},
        'calibrate-checks':{'calibration_profile_ref'},
    }
    def __init__(self,store,library,operator,bindings,actor,*,self_test_runner=None,calibration_authority=None):
        self.store,self.library,self.operator,self.bindings,self.actor=store,library,operator,bindings,actor
        self.self_tests=self_test_runner
        self.calibration=calibration_authority

    async def execute(self,command,request_ref):
        require(command in self.FIELDS,'Unknown finite Library command')
        self.actor.require('verifier_assets' if command in {'associate-checks','calibrate-checks'} else 'library_standing' if command=='standing' else 'library_admit')
        configuration=self.store.read_record(self.bindings['configuration_ref'])
        require(configuration.get('operator',configuration)==self.operator.snapshot(),'Captured operator configuration changed')
        validate('Ref',request_ref);request=self.store.read_record(request_ref)
        optional={'static_template_ref'} if command=='standing' else set()
        require(isinstance(request,dict) and self.FIELDS[command]|{'schema','id'}<=set(request)
            and set(request)<=self.FIELDS[command]|{'schema','id'}|optional
            and request['schema']=='ai4r-library-action:1' and isinstance(request['id'],str) and request['id'],
            'Closed immutable Library action is invalid')
        for key in ('declaration_ref','bundle_ref','profile_ref','calibration_profile_ref'):
            if key in request:validate('Ref',request[key]);self.store.read_blob(request[key])
        if 'evidence_refs' in request:
            require(isinstance(request['evidence_refs'],list),'Evidence must be exact immutable Refs')
            for ref in request['evidence_refs']:validate('Ref',ref);self.store.read_blob(ref)
        if command=='admit':
            policy=self.store.read_record(self.operator.snapshot()['cc']['plan_policy_ref'],contract_id='plan-policy')
            require(type(request['memory_mb']) is int and 0<request['memory_mb']<=policy['aggregate_limits']['memory_mb'],'Admission memory widens the protected policy')
            require(isinstance(request['body_refs'],dict),'Body closure must name exact Refs')
            for ref in request['body_refs'].values():validate('Ref',ref);self.store.read_blob(ref)
        if command=='standing':self._standing_template(request)
        key='library-operator:'+hashlib.sha256(json_bytes([self.actor.account_id,command,request['id']])).hexdigest()
        with self.store.transaction() as db:
            prior=db.execute('SELECT value FROM metadata WHERE key=?',(key,)).fetchone()
            if prior:
                captured=json.loads(prior['value']);require(captured['request_ref']==request_ref,'Human action identity already names different bytes')
                require(captured.get('receipt_ref') is not None,'Issued human action has no terminal receipt; reconcile without replay')
                return self.store.read_record(captured['receipt_ref'])
            db.execute('INSERT INTO metadata VALUES(?,?)',(key,json_bytes({'request_ref':request_ref}).decode()))
        result={'id':key+':result','command':command,'request_ref':request_ref,'actor':self.actor.account_id,'recorded_at':utc_now()}
        try:
            if command=='inspect':result.update(status='completed',declaration_ref=request['declaration_ref'],view_ref=self.library.render_declaration(request['declaration_ref']))
            elif command=='associate-checks':
                self.library.associate_checks(request['declaration_ref'],request['bundle_ref'],request['profile_ref'],self.actor,evidence_refs=request['evidence_refs'])
                result.update(status='prepared',qualified=False,declaration_ref=request['declaration_ref'])
            elif command=='admit':
                ref=await self.library.admit(request['declaration_ref'],request['body_refs'],self.actor,memory_mb=request['memory_mb'],
                    evidence_refs=request['evidence_refs'],self_test_runner=self.self_tests)
                result.update(status=self.store.read_record(ref)['status'],admission_ref=ref)
            elif command=='admit-rsi':
                require(isinstance(request['package_path'],str),'A protected inbox package path is required')
                package=self.library.capture_rsi_inbox(request['package_path'],self.actor)
                ref=await self.library.admit_rsi(package,self.actor,self_test_runner=self.self_tests)
                result.update(status=self.store.read_record(ref)['status'],package_ref=package,admission_ref=ref)
            elif command=='calibrate-checks':
                require(self.calibration is not None,'Explicit protected calibration runtime is unavailable')
                measured=await self.calibration.execute(request['calibration_profile_ref'],self.actor,request['id'])
                result.update(status=measured['status'],calibration_request_ref=measured['request_ref'],
                    bundle_admission_ref=measured['bundle_admission_ref'],criteria_admission_ref=measured['criteria_admission_ref'],
                    measurement_refs=measured['measurement_refs'],reason_code=measured['reason_code'])
            else:
                ref=self.library.set_standing(request['name'],request['version'],request['to_standing'],self.actor,reason=request['reason'],effect_scope=request['effect_scope'])
                result.update(status='completed',standing_ref=ref)
                if 'static_template_ref' in request:result['static_template_ref']=request['static_template_ref']
        except (ResearchError,OSError,ValueError) as error:
            result.update(status='blocked',reason_code=getattr(error,'code','operator_unavailable'))
        receipt=self.store.append_record('library-operator-action',result)
        with self.store.transaction() as db:db.execute('UPDATE metadata SET value=? WHERE key=?',(json_bytes({'request_ref':request_ref,'receipt_ref':receipt}).decode(),key))
        return result

    def _standing_template(self,request):
        row=self.library.get(request['name'],request['version']);admission=self.store.read_record(row['admission_ref'])
        promoting=admission['parent_ref'] is not None and request['to_standing']=='active' and request['effect_scope']=='live_plans'
        if promoting:
            ref=request.get('static_template_ref');validate('Ref',ref)
            require(ref!=self.operator.snapshot()['cc']['static_template_ref'],'Live promotion requires a distinct authored static template')
            template=self.store.read_record(ref,contract_id='static-template')
            require(any(node['cc']==admission['cc'] for node in template['nodes']),'New static template does not name this exact admitted child')
        else:require('static_template_ref' not in request,'A static template is only attached to explicit RSI live promotion')


async def run_operator(command,request_ref):
    actor=operator_identity()
    # An app process cannot regain root to enter this command. All writes after
    # the human entry check use the existing app identity and finite inbox group.
    os.setgroups([13000]);os.setresgid(10001,10001,10001);os.setresuid(10001,10001,10001)
    require(os.geteuid()==10001 and os.getuid()==10001,'Permanent operator identity transition failed')
    from .bootstrap_gateway import _protected_file
    from .operator_config import OperatorConfiguration
    from .library import LibraryService
    locator=os.environ.get('JIUWENSWARM_M1_BOOTSTRAP_BINDINGS')
    require(bool(locator),'Protected bootstrap locator is required')
    envelope=json.loads(_protected_file(locator).decode('utf-8'))
    require(isinstance(envelope,dict) and set(envelope)=={'binding_ref'},'Closed protected bootstrap locator is invalid')
    validate('Ref',envelope['binding_ref'])
    root=Path(os.environ.get('JIUWENSWARM_M1_STATE','/var/lib/ai4r'));require(root.is_absolute(),'State root must be absolute')
    store=SQLiteRunStore(root,recover=False,input_root='/workspace/input')
    try:
        bindings=store.read_record(envelope['binding_ref']);validate('Ref',bindings['configuration_ref'])
        path=os.environ.get('JIUWENSWARM_M1_CONFIG','/etc/ai4r/config.yaml');_protected_file(path)
        operator=OperatorConfiguration.load(path,resolve_profile=store.read_record)
        public=operator.snapshot()['rsi']['custodian_public_key'];options=bindings.get('protected_options',{})
        inbox=options.get('rsi_inbox') or os.environ.get('JIUWENSWARM_M1_RSI_INBOX')
        require(inbox is None or inbox=='/var/lib/ai4r-rsi-inbox','Only the fixed protected public admission inbox is supported')
        library=LibraryService(store,rsi_public_key=base64.urlsafe_b64decode(public+'='*(-len(public)%4)) if public else None,
            rsi_key_id=operator.snapshot()['rsi']['custodian_key_id'],rsi_inbox=inbox,rsi_custodian_uid=12002 if inbox else None)
        if options.get('rsi_security_qualification_ref') is not None:
            try:
                from .contracts.rsi_security import RSIQualification
                # No finite current RSI producer-scope provider is installed in
                # this OS composition yet. Root permission is no substitute.
                library.rsi_security_guard=RSIQualification.from_store(store,options['rsi_security_qualification_ref'],scope_observer=None)
            except (ResearchError,OSError,ValueError,KeyError,TypeError):pass
        if options.get('admission_execution_profile_ref') is not None:
            from .admission_executor import AdmissionTestProvider
            from .executor_rpc import ExecutorClient,PROTOCOL
            from .native_ports import _session,APP_UID
            from .private_rpc import PrivateRPCClient
            rpc=ExecutorClient(PrivateRPCClient('/run/ai4r-executor/executor.sock',protocol=PROTOCOL,
                peer_uid=0,socket_mode=0o660,**_session('/run/ai4r',APP_UID)))
            library.self_test_provider=AdmissionTestProvider(store,configuration_ref=bindings['configuration_ref'],
                execution_profile_ref=options['admission_execution_profile_ref'],rpc=rpc)
        calibration=None
        if command=='calibrate-checks' and options.get('calibration_runtime_ref') is not None:
            from .calibration_authority import CalibrationAuthority
            from .bridge import ModelBridgeClient
            from .native_ports import _session,APP_UID
            calibration=CalibrationAuthority(store,options['calibration_runtime_ref'],configuration_ref=bindings['configuration_ref'],
                model_selection_profile_ref=bindings['model_selection_profile_ref'],deployment_ref=bindings['deployment_ref'],
                policy_ref=operator.snapshot()['cc']['plan_policy_ref'],
                model=ModelBridgeClient('/run/ai4r/model.sock',peer_uid=APP_UID,**_session('/run/ai4r',APP_UID)))
        return await OperatorLibrary(store,library,operator,bindings,actor,calibration_authority=calibration).execute(command,request_ref)
    finally:store.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Finite human-only M1 Library operations over exact captured actions')
    parser.add_argument('command',choices=sorted(OperatorLibrary.FIELDS));parser.add_argument('--request-ref',required=True,help='Exact JSON Ref of the immutable action')
    args=parser.parse_args(argv)
    try:result=asyncio.run(run_operator(args.command,json.loads(args.request_ref)))
    except (ResearchError,OSError,ValueError,KeyError,TypeError):result={'status':'blocked','reason_code':'operator_prerequisites_unavailable'}
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0 if result['status'] in {'completed','prepared','admitted'} else 2


if __name__=='__main__':raise SystemExit(main())
