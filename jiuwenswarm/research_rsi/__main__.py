"""Finite workbench operations with custodian-owned input references."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import asyncio
from .custody import ExposureLedger,require_custody
from .records import RecordStore,encoded


def main(argv=None):
    parser=argparse.ArgumentParser(prog='ai4r-rsi');sub=parser.add_subparsers(dest='operation',required=True)
    doctor=sub.add_parser('doctor');doctor.add_argument('--config');doctor.add_argument('--live',action='store_true');doctor.add_argument('--job-ref')
    preparation=sub.add_parser('prepare')
    from .preparation_runtime import OPERATIONS
    preparation.add_argument('action',choices=OPERATIONS);preparation.add_argument('--request-ref',required=True)
    for command in ('serve-jobs','serve-custodian','serve-worker-broker'):
        service=sub.add_parser(command);service.add_argument('--config',required=True)
    validation=sub.add_parser('serve-security-validation');validation.add_argument('--config',required=True)
    sub.add_parser('serve-validation-custodian')
    profiles=sub.add_parser('profiles');profiles.add_argument('--root',required=True)
    session=sub.add_parser('session');ss=session.add_subparsers(dest='action',required=True)
    for name in ('start','inspect','stop','export'):
        p=ss.add_parser(name);p.add_argument('--job-ref',required=True)
        if name in ('inspect','export'):
            p.add_argument('--offline',action='store_true');p.add_argument('--config')
    cust=sub.add_parser('custodian');cs=cust.add_subparsers(dest='action',required=True)
    for name in ('register','evaluate','final'):
        p=cs.add_parser(name);p.add_argument('--request-ref',required=True)
    args=parser.parse_args(argv)
    if args.operation in {'serve-security-validation','serve-validation-custodian'}:
        from jiuwenswarm.research.private_rpc import BridgeError,PlatformIntegrityError
        try:
            if args.operation=='serve-security-validation':
                from .security_runtime import serve_validation
                asyncio.run(serve_validation(args.config))
            else:
                from .security_custody import serve
                asyncio.run(serve())
            return 0
        except (ValueError,OSError,KeyError,TypeError,BridgeError,PlatformIntegrityError):
            print('BLOCKED: protected validation plan, isolated owners or current evidence unavailable.',file=sys.stderr);return 2
    if args.operation=='prepare':
        from .preparation_runtime import main as prepare_main
        return prepare_main([args.action,'--request-ref',args.request_ref])
    if args.operation=='serve-worker-broker':
        from .worker_bootstrap import main as broker_main
        try:broker_main(args.config);return 0
        except (OSError,ValueError,KeyError):
            print('BLOCKED: separately owned worker broker resources or actual confinement prerequisites are unavailable.',file=sys.stderr);return 2
    if args.operation in {'serve-jobs','serve-custodian'}:
        from .bootstrap import service_main,RuntimeUnavailable
        try:service_main(args.operation,args.config);return 0
        except (RuntimeUnavailable,OSError,ValueError,KeyError):
            print('BLOCKED: protected service configuration, isolated UID or qualified fixed runtime resource binding is unavailable.',file=sys.stderr);return 2
    if args.operation=='doctor':
        from .readiness import check_doctor,check_doctor_live
        try:
            from .worker import ref
            selected=json.loads(args.job_ref) if args.job_ref else None
            if selected is not None:ref(selected)
            if selected is not None and not args.live:parser.error('--job-ref requires --live')
            findings=asyncio.run(check_doctor_live(args.config,job_ref=selected)) if args.live else check_doctor(args.config)
        except (ValueError,OSError,KeyError,TypeError):
            print('BLOCKED: protected readiness configuration or immutable job reference unavailable.',file=sys.stderr);return 2
        print(json.dumps(findings,sort_keys=True));return 0 if findings['status']=='READY' else 2
    if args.operation=='profiles':
        # Print only visible profile IDs/digests, never protected split contents.
        root=Path(args.root)
        print(json.dumps([{'id':p.stem,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(root.glob('*.json'))],sort_keys=True));return 0
    if args.operation=='custodian':
        # Custodian commands run as that owned identity, using the same fixed
        # protected assembly as the service. No controller-selected fixture or
        # signing path and no self-connection bypass of Unix peer policy.
        async def perform():
            from .bootstrap import load_config
            from .fixed_resources import assemble_custodian
            config=load_config(os.environ.get('AI4R_RSI_CUSTODIAN_CONFIG','/run/ai4r-rsi/custodian-service.json'),'custodian')
            requested=json.loads(args.request_ref)
            records=RecordStore(config['record_root']);ledger=None
            try:
                service,ledger=await assemble_custodian(config,records)
                if args.action=='register':
                    if requested!=config['fixture_manifest_ref']:raise ValueError('Registration differs from the exact approved private manifest')
                    return {'registered':True,'fixture_manifest_ref':requested,'authorized_sessions':config['authorized_sessions']}
                return await (service.evaluate(requested) if args.action=='evaluate' else service.final(requested))
            finally:
                if ledger is not None:ledger.close()
                records.close()
        try:print(json.dumps(asyncio.run(perform()),sort_keys=True));return 0
        except (ValueError,OSError,KeyError):
            print('BLOCKED: owned custodian configuration, exact registration/calibration or authorized action unavailable.',file=sys.stderr);return 2
    if args.operation=='session' and getattr(args,'offline',False):
        from .history import inspect_history
        from .worker import ref
        try:
            selected=json.loads(args.job_ref);ref(selected)
            result=inspect_history(args.config or os.environ.get('AI4R_RSI_JOBS_CONFIG','/run/ai4r-rsi/jobs-service.json'),
                selected,export=args.action=='export')
            print(json.dumps(result,sort_keys=True));return 0 if result['state']=='terminal' else 2
        except (ValueError,OSError,KeyError,TypeError):
            print('BLOCKED: protected original history grant or captured bytes unavailable.',file=sys.stderr);return 2
    if args.operation=='session' and getattr(args,'config',None):parser.error('--config requires --offline')
    try:
        from .ports import request
        text=args.job_ref if args.operation=='session' else args.request_ref
        ref=json.loads(text)
        if set(ref)!={'id','sha256'}:raise ValueError('immutable reference required')
        path=os.environ.get('AI4R_RSI_JOB_SOCKET') if args.operation=='session' else os.environ.get('AI4R_RSI_CUSTODIAN_SOCKET')
        peer=os.environ.get('AI4R_RSI_JOB_UID') if args.operation=='session' else os.environ.get('AI4R_RSI_CUSTODIAN_UID')
        if not path or not peer:raise ValueError('protected runtime port not provisioned')
        reply=asyncio.run(request(path,int(peer),args.operation+'_'+args.action,ref))
        print(json.dumps(reply,sort_keys=True));return 0 if reply['status']=='ok' else 2
    except (ValueError,OSError,KeyError):
        print('BLOCKED: protected runtime job/custodian port unavailable; no local privilege fallback.',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
