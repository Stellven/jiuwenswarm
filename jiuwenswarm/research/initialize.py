"""Explicit native M1 catalog installation from protected operator bindings.

This command never creates policy, scientific fixtures, credentials, defaults
or RSI candidates. Ordinary Gateway startup continues to resolve only.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import pwd
import uuid
from pathlib import Path

from .contracts import Principal,ResearchError,validate
from .state import SQLiteRunStore,utc_now


async def initialize_profile():
    if os.environ.get('JIUWENSWARM_M1_PROFILE')!='1' or os.name!='posix' or os.geteuid()!=10001:
        raise ResearchError('initialization_blocked','Use the explicit native M1 initializer as its configured OS operator identity')
    locator=os.environ.get('JIUWENSWARM_M1_BOOTSTRAP_BINDINGS')
    if not locator:raise ResearchError('initialization_blocked','Protected bootstrap locator is required; policy and defaults are never invented')
    from .bootstrap_gateway import _protected_file
    envelope=json.loads(_protected_file(locator).decode('utf-8'))
    if not isinstance(envelope,dict) or set(envelope)!={'binding_ref'}:raise ResearchError('initialization_blocked','Closed protected binding locator is invalid')
    validate('Ref',envelope['binding_ref'])
    configuration_path=os.environ.get('JIUWENSWARM_M1_CONFIG','/etc/ai4r/config.yaml')
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
        composition=await compose_core(store=store,operator=operator,model=None,executor=None,readiness=None,upload_manager=None,
            principal=principal,operator_actor=actor,configuration_ref=bindings['configuration_ref'],
            model_selection_profile_ref=bindings['model_selection_profile_ref'],deployment_ref=bindings['deployment_ref'],
            workspace_id=workspace,initialize=True,protected_options=bindings['protected_options'])
        try:library_ref=composition.library.snapshot()
        except ResearchError:library_ref=None
        record={'id':'catalog-init:'+uuid.uuid4().hex,'recorded_at':utc_now(),'binding_ref':envelope['binding_ref'],
            'configuration_ref':bindings['configuration_ref'],'actor':{'account_id':account,'os_uid':uid,'os_gid':gid,'operator_id':actor.account_id},
            'status':'blocked' if composition.diagnostics else 'initialized','runtime_ready':False,
            'library_snapshot_ref':library_ref,'static_template_ref':composition.static_template_ref,
            'admission_refs':[row['admission_ref'] for row in composition.installed.values() if 'admission_ref' in row]+[
                ref for diagnostic in composition.diagnostics for ref in diagnostic.get('evidence_refs',[])],
            'diagnostics':composition.diagnostics,
            'limitations':['Explicit fixed-catalog installation only; runtime credentials, confinement, scientific resources and required verification remain separately qualified']}
        receipt=store.append_record('catalog-initialization',record)
        return {**record,'receipt_ref':receipt}
    finally:
        if accounts is not None:accounts.close()
        store.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Explicitly initialize the frozen M1 catalog from protected operator and bootstrap bindings')
    parser.add_argument('--json',action='store_true',help='Emit the structured initialization receipt (default)')
    parser.parse_args(argv)
    try:
        result=asyncio.run(initialize_profile())
    except (ResearchError,ValueError,OSError,UnicodeError) as exc:
        # Never echo protected records, credentials, URLs or raw exceptions.
        result={'status':'blocked','runtime_ready':False,'diagnostics':[{'code':getattr(exc,'code','initialization_blocked'),
            'detail':'Protected initialization prerequisites are unavailable or invalid'}]}
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0 if result['status']=='initialized' else 2


if __name__=='__main__':raise SystemExit(main())
