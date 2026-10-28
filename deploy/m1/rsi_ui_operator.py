"""Prepare a reviewed installation bundle or serve the separate Root CC broker.

Preparing never deploys/restarts an app, installs files under /etc, starts a
broker, admits a child or activates anything. A fresh key is generated in place
inside the new private bundle; key bytes and configuration contents are never
printed. An explicit deployment must mount the completed bundle later.
"""
from __future__ import annotations
import argparse
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import stat

from jiuwenswarm.research.cc_ui_runtime import module
from jiuwenswarm.research.contracts import ResearchError

installation = module('cc_rsi_installation')
operator = module('cc_rsi_operator')
PREFIX = Path('/var/lib/ai4r-cc-rsi-installations')


def need(value):
    if not value: raise ValueError('Exact protected CC installation prerequisite unavailable')


def encoded(value): return json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()
def sha(raw): return hashlib.sha256(raw).hexdigest()


def policy_for(value):
    installation._fields(value,'schema revision origin workspace_id operators candidates gateway_uid gateway_gid socket_gid library')
    need(value['schema']=='ai4r-cc-rsi-installation-input:1'
        and isinstance(value['revision'],str) and __import__('re').fullmatch('[a-z][a-z0-9-]{0,47}',value['revision'])
        and value['origin']=='http://127.0.0.1:5175')
    need(all(type(value[key]) is int and value[key]==10001 for key in ('gateway_uid','gateway_gid','socket_gid')))
    installation._fields(value['library'],'python bindings_path config_path state_root timeout')
    need(all(value['library'][key]==path for key,path in {
        'python':'/opt/venv/bin/python-cc-operator','bindings_path':'/etc/ai4r/bootstrap-bindings.json',
        'config_path':'/etc/ai4r/config.yaml','state_root':'/var/lib/ai4r'}.items()))
    return operator.validate_operator_policy({'schema':'ai4r-cc-rsi-root-operator-policy:2','workspace_id':value['workspace_id'],
        'revision':value['revision'],'origin':value['origin'],'gateway_key_id':'cc-ui-gateway:'+value['revision'],
        'operators':value['operators'],'candidates':value['candidates']})


def plan(input_path):
    need(os.name=='posix' and os.geteuid()==0)
    raw=installation.protected_bytes(input_path,uid=0,mode=0o600)
    value=json.loads(raw);policy=policy_for(value)
    from jiuwenswarm.research.native_ports import verify_installed_build
    build=verify_installed_build()
    library=module('cc_rsi_library').ProtectedLibraryComposition(policy,**value['library'])
    for digest,candidate in policy['candidates'].items():
        for action in ('admit','activate'):
            ref=candidate[action+'_request_ref']
            if ref is not None: need(library.preflight(action,digest,ref) is True)
    target=PREFIX/value['revision'];need(not os.path.lexists(target))
    return {'schema':'ai4r-cc-rsi-installation-plan:1','input_sha256':sha(raw),
        'policy_sha256':sha(encoded(policy)),'source_build_id':build,'bundle':str(target),
        'entrypoint_sha256':sha(Path(__file__).read_bytes()),'interpreter_sha256':sha(Path(library.python).read_bytes()),
        'gateway_uid':value['gateway_uid'],'gateway_gid':value['gateway_gid'],'socket_gid':value['socket_gid'],
        'operators':len(policy['operators']),'candidates':len(policy['candidates']),
        'app_deployed':False,'broker_started':False,'admission_performed':False,'activation_performed':False},value,policy


def configurations(value,policy,public,interpreter_sha256):
    # Both sides pin the same policy and newly delegated public key. The native
    # account remains a status principal; no browser field grants a Library role.
    public_text=base64.urlsafe_b64encode(public).decode().rstrip('=')
    return ({'schema':'ai4r-cc-rsi-native-gateway-installation:1','policy':policy,
        'gateway_uid':value['gateway_uid'],'gateway_public_key':public_text},
        {'schema':'ai4r-cc-rsi-root-operator-installation:2','policy':policy,
        'gateway_uid':value['gateway_uid'],'socket_gid':value['socket_gid'],
        'gateway_public_key':public_text,'library':dict(value['library'],python_sha256=interpreter_sha256)})


def write_new(path,raw,uid=0,gid=0,mode=0o600):
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    with os.fdopen(descriptor,'wb') as output:
        os.fchown(output.fileno(),uid,gid);os.fchmod(output.fileno(),mode)
        output.write(raw);output.flush();os.fsync(output.fileno())
    descriptor=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def prepare(input_path,review):
    reviewed,value,policy=plan(input_path);need(sha(encoded(reviewed))==review)
    PREFIX.mkdir(mode=0o700,exist_ok=True)
    for path in (PREFIX,*PREFIX.parents):
        info=path.lstat();need(stat.S_ISDIR(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022)
    target=Path(reviewed['bundle']);target.mkdir(mode=0o700)
    write_new(target/'plan.json',encoded(reviewed))
    write_new(target/'claim.json',encoded({'schema':'ai4r-cc-rsi-installation-claim:1','plan_sha256':review}))
    write_new(target/'operator-entrypoint.py',Path(__file__).read_bytes(),mode=0o440)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
    key=Ed25519PrivateKey.generate()
    write_new(target/'gateway.key',key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()),
        uid=value['gateway_uid'],gid=value['gateway_gid'],mode=0o400)
    gateway,root=configurations(value,policy,key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw),reviewed['interpreter_sha256'])
    write_new(target/'gateway.json',encoded(gateway),gid=value['gateway_gid'],mode=0o440)
    write_new(target/'operator.json',encoded(root))
    done={'schema':'ai4r-cc-rsi-installation-complete:1','plan_sha256':review,
        'source_build_id':reviewed['source_build_id'],'entrypoint_sha256':reviewed['entrypoint_sha256'],
        'gateway_config_sha256':sha(encoded(gateway)),'operator_config_sha256':sha(encoded(root)),
        'app_deployed':False,'broker_started':False,'admission_performed':False,'activation_performed':False}
    write_new(target/'complete.json',encoded(done),gid=value['gateway_gid'],mode=0o440)
    return {'status':'CC_INSTALLATION_BUNDLE_PREPARED_NOT_DEPLOYED','bundle':str(target),
        'completion_sha256':sha(encoded(done)),'candidates':len(policy['candidates'])}


async def serve():
    value,key=operator.load_root_operator_config()
    done=installation.completed_installation('operator_config_sha256',installation.protected_bytes('/etc/ai4r/cc-rsi-operator.json',uid=0,mode=0o600))
    need(sha(Path(__file__).read_bytes())==done['entrypoint_sha256'])
    journal=operator.RootOperatorJournal()
    try:
        engine=installation.root_engine(value,key,journal)
        server=await operator.serve_root_operator(engine,value)
        async with server: await server.serve_forever()
    finally: journal.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('operation',choices=('plan','prepare','serve'))
    parser.add_argument('--input',type=Path);parser.add_argument('--review-sha256');args=parser.parse_args(argv)
    try:
        if args.operation=='serve': asyncio.run(serve());return 0
        result=plan(args.input)[0] if args.operation=='plan' else prepare(args.input,args.review_sha256)
        if args.operation=='plan':result={'review_sha256':sha(encoded(result)),'plan':result}
        print(json.dumps(result,sort_keys=True));return 0
    except (ResearchError,OSError,ValueError,KeyError,TypeError):
        print(json.dumps({'status':'BLOCKED','reason':'PROTECTED_CC_INSTALLATION_UNAVAILABLE'}));return 2


if __name__=='__main__':raise SystemExit(main())
