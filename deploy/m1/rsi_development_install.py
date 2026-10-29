"""Root plan/apply for the fixed development UI broker; never starts a model.

A fresh dedicated gateway assertion key is generated in place. Native login,
browser session, account caches and existing Library operator keys are untouched.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('development_install_launcher', HERE/'rsi_development_launcher.py')
launch = importlib.util.module_from_spec(spec); spec.loader.exec_module(launch)
ETC = Path('/etc/ai4r')
MODULE = Path('/opt/ai4r-cc-rsi-development/cc_rsi_development.py')
REGISTRY = Path('/var/lib/ai4r-cc-rsi-development-installations')
SCHEMA = 'ai4r-rsi-development-install-input:1'
FIELDS = {'schema','policy','module_source','interpreter','service','wrapper','authorization',
          'approved_plan_sha256','launch_configuration'}


def pinned_interpreter(value):
    launch.need(isinstance(value, dict) and set(value) == {'path', 'sha256'}, 'CLOSED_INTERPRETER_PIN_REQUIRED')
    path = launch.protected(value['path'], maximum=16*1024*1024)
    launch.need(path.stat().st_mode & 0o111 and launch.sha(path.read_bytes()) == value['sha256'],
                'PINNED_EXECUTABLE_INTERPRETER_REQUIRED')
    return path


def validate_policy(value):
    launch.need(isinstance(value, dict) and set(value) == set('schema workspace_id origin actors gateway_key_id target_id revision run_id'.split())
        and value['schema'] == 'ai4r-cc-rsi-development-policy:1', 'CLOSED_INSTALL_POLICY_REQUIRED')
    import re
    launch.need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', value['run_id']) is not None
        and isinstance(value['actors'], list) and 1 <= len(value['actors']) <= 16
        and len(set(value['actors'])) == len(value['actors'])
        and all(isinstance(x,str) and 0 < len(x) <= 256 for x in value['actors']), 'FINITE_EXPLICIT_NATIVE_ACTORS_REQUIRED')
    for key in ('workspace_id','origin','gateway_key_id','target_id'):
        launch.need(isinstance(value[key],str) and 0 < len(value[key]) <= 512, 'EXPLICIT_INSTALL_IDENTITY_REQUIRED')
    launch.need(re.fullmatch('[a-f0-9]{64}',value['revision']) is not None, 'EXACT_BASELINE_REVISION_REQUIRED')
    return value


def plan(input_path):
    launch.need(os.name == 'posix' and os.geteuid() == 0, 'ROOT_INSTALLER_REQUIRED')
    raw = launch.protected(input_path).read_bytes(); value = json.loads(raw)
    launch.need(isinstance(value,dict) and set(value) == FIELDS and value['schema'] == SCHEMA, 'CLOSED_INSTALL_INPUT_REQUIRED')
    validate_policy(value['policy'])
    pinned_interpreter(value['interpreter'])
    for key in ('module_source','service','wrapper','authorization','launch_configuration'): launch.pinned(value[key])
    launch.need(Path(value['service']['path']).name == 'rsi_development_service.py'
        and Path(value['wrapper']['path']).name == 'rsi_development_launcher.py', 'FIXED_SERVICE_AND_LAUNCHER_REQUIRED')
    config = json.loads(launch.pinned(value['launch_configuration']).read_bytes())
    launch.need(config['id'] == value['policy']['run_id'] and config['authorization'] == value['authorization']
        and config['approved_plan_sha256'] == value['approved_plan_sha256']
        and config['launcher_sha256'] == value['wrapper']['sha256'], 'REVIEWED_LAUNCH_INSTALLATION_DIFFERS')
    launch.need(len(value['approved_plan_sha256']) == 64, 'EXACT_WORKER_PLAN_REQUIRED')
    directory = REGISTRY/value['policy']['run_id']
    early = read_gateway(value['policy'], value['module_source'])
    destinations = [ETC/name for name in ('cc-rsi-development-gateway.key','cc-rsi-development-gateway.json',
        'cc-rsi-development-root.json','cc-rsi-development-launch.json')]+[MODULE,directory]
    blocked = [ETC/'cc-rsi-development-root.json',ETC/'cc-rsi-development-launch.json',directory/'claim.json',directory/'complete.json']
    launch.need(all(not os.path.lexists(path) for path in blocked)
        and (early is not None or all(not os.path.lexists(path) for path in destinations)), 'INSTALLATION_ALREADY_ISSUED_NO_OVERWRITE')
    facts = {'schema':'ai4r-rsi-development-install-plan:1','input_sha256':launch.sha(raw),
        'source_sha256':launch.sha(Path(__file__).read_bytes()),'launcher_sha256':launch.sha((HERE/'rsi_development_launcher.py').read_bytes()),
        'pins':{key:value[key] for key in ('module_source','interpreter','service','wrapper','authorization','launch_configuration')},
        'policy':value['policy'],'approved_plan_sha256':value['approved_plan_sha256'],
        'destinations':[str(path) for path in destinations], 'fresh_assertion_key':True,
        'existing_gateway_completion':early,'broker_started':False,'model_calls':0,'qualification':False,'library_effects':False}
    return value,facts,directory


def directory(path, mode=0o755):
    path.mkdir(mode=mode, exist_ok=True)
    launch.protected(path, directory=True)


def write(path, raw, *, uid=0, gid=0, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd,'wb') as stream:
        os.fchown(stream.fileno(),uid,gid); os.fchmod(stream.fileno(),mode)
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    parent = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(parent)
    finally: os.close(parent)


def gateway_files(value):
    directory(MODULE.parent)
    write(MODULE,launch.pinned(value['module_source']).read_bytes(),mode=0o444)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
    key = Ed25519PrivateKey.generate()
    write(ETC/'cc-rsi-development-gateway.key',key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()),
          uid=10001,gid=10001,mode=0o400)
    public = base64.urlsafe_b64encode(key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode().rstrip('=')
    gateway = {'schema':'ai4r-cc-rsi-development-gateway:1','policy':value['policy'],
        'gateway_public_key':public,'module_sha256':value['module_source']['sha256']}
    write(ETC/'cc-rsi-development-gateway.json',launch.encoded(gateway),gid=10001,mode=0o440)
    return gateway


def read_gateway(policy, module_source):
    root = REGISTRY/policy['run_id']
    if not os.path.lexists(root): return None
    completion = json.loads(launch.protected(root/'gateway-complete.json').read_bytes())
    claim = json.loads(launch.protected(root/'gateway-claim.json').read_bytes())
    launch.need(claim == {'schema':'ai4r-rsi-development-gateway-claim:1','plan_sha256':completion.get('plan_sha256')},
                'EXACT_GATEWAY_CLAIM_COMPLETION_JOIN_REQUIRED')
    launch.need(set(completion) == {'schema','plan_sha256','policy','gateway_config_sha256','module_sha256','public_key','broker_started','model_calls'}
        and completion['schema'] == 'ai4r-rsi-development-gateway-completion:1'
        and completion['policy'] == policy and completion['module_sha256'] == module_source['sha256']
        and completion['broker_started'] is False and completion['model_calls'] == 0, 'COMPLETED_GATEWAY_INSTALLATION_REQUIRED')
    raw = launch.protected(ETC/'cc-rsi-development-gateway.json').read_bytes(); gateway = json.loads(raw)
    launch.need(launch.sha(raw) == completion['gateway_config_sha256'] and gateway['policy'] == policy
        and gateway['gateway_public_key'] == completion['public_key'] and gateway['module_sha256'] == module_source['sha256']
        and launch.sha(launch.protected(MODULE).read_bytes()) == module_source['sha256'], 'EXISTING_GATEWAY_BYTES_DIFFER')
    key_path = launch.protected(ETC/'cc-rsi-development-gateway.key',owner=10001)
    info = key_path.stat(); secret = key_path.read_bytes()
    launch.need(stat.S_IMODE(info.st_mode) == 0o400 and info.st_gid == 10001 and len(secret) == 32, 'DEDICATED_GATEWAY_KEY_CUSTODY_DIFFERS')
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    public = base64.urlsafe_b64encode(Ed25519PrivateKey.from_private_bytes(secret).public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode().rstrip('=')
    launch.need(public == completion['public_key'], 'EXISTING_GATEWAY_KEY_DIFFERS')
    return completion


def gateway_plan(input_path):
    launch.need(os.name == 'posix' and os.geteuid() == 0, 'ROOT_INSTALLER_REQUIRED')
    raw = launch.protected(input_path).read_bytes(); value = json.loads(raw)
    launch.need(set(value) == {'schema','policy','module_source'}
        and value['schema'] == 'ai4r-rsi-development-gateway-input:1', 'CLOSED_GATEWAY_INPUT_REQUIRED')
    validate_policy(value['policy']); launch.pinned(value['module_source'])
    root = REGISTRY/value['policy']['run_id']
    launch.need(not os.path.lexists(root) and all(not os.path.lexists(path) for path in
        (MODULE,ETC/'cc-rsi-development-gateway.json',ETC/'cc-rsi-development-gateway.key')), 'GATEWAY_ALREADY_ISSUED_NO_OVERWRITE')
    facts = {'schema':'ai4r-rsi-development-gateway-plan:1','input_sha256':launch.sha(raw),
        'source_sha256':launch.sha(Path(__file__).read_bytes()),
        'launcher_sha256':launch.sha(Path(launch.__file__).read_bytes()), 'module_source':value['module_source'],
        'policy':value['policy'],'fresh_assertion_key':True,'broker_started':False,'model_calls':0}
    return value,facts,root


def gateway_apply(input_path, reviewed):
    value,facts,root = gateway_plan(input_path)
    launch.need(launch.sha(launch.encoded(facts)) == reviewed and gateway_plan(input_path)[1] == facts, 'EXACT_GATEWAY_PLAN_REVIEW_REQUIRED')
    directory(root.parent,0o700); root.mkdir(mode=0o700); directory(ETC)
    write(root/'gateway-claim.json',launch.encoded({'schema':'ai4r-rsi-development-gateway-claim:1','plan_sha256':reviewed}))
    gateway = gateway_files(value)
    completion = {'schema':'ai4r-rsi-development-gateway-completion:1','plan_sha256':reviewed,'policy':value['policy'],
        'gateway_config_sha256':launch.sha(launch.encoded(gateway)),'module_sha256':value['module_source']['sha256'],
        'public_key':gateway['gateway_public_key'],'broker_started':False,'model_calls':0}
    write(root/'gateway-complete.json',launch.encoded(completion),mode=0o440)
    return completion


def apply(input_path, reviewed):
    value,facts,root = plan(input_path)
    launch.need(launch.sha(launch.encoded(facts)) == reviewed and plan(input_path)[1] == facts, 'EXACT_INSTALL_PLAN_REVIEW_REQUIRED')
    directory(root.parent,0o700); root.mkdir(mode=0o700,exist_ok=facts['existing_gateway_completion'] is not None)
    write(root/'claim.json',launch.encoded({'schema':'ai4r-rsi-development-install-claim:1','plan_sha256':reviewed}))
    directory(ETC)
    if facts['existing_gateway_completion'] is not None:
        read_gateway(value['policy'],value['module_source'])
        gateway = json.loads(launch.protected(ETC/'cc-rsi-development-gateway.json').read_bytes())
    else: gateway = gateway_files(value)
    public = gateway['gateway_public_key']
    launch_configuration = launch.pinned(value['launch_configuration']).read_bytes()
    root_config = {'schema':'ai4r-cc-rsi-development-root:1','policy':value['policy'],'gateway_public_key':public,
        **{key:value[key] for key in ('interpreter','wrapper','authorization','approved_plan_sha256')},
        'runner':json.loads(launch_configuration)['runner'],'module':{'path':str(MODULE),'sha256':value['module_source']['sha256']},
        'service_sha256':value['service']['sha256']}
    write(ETC/'cc-rsi-development-launch.json',launch_configuration)
    write(ETC/'cc-rsi-development-root.json',launch.encoded(root_config))
    completion = {'schema':'ai4r-rsi-development-install-completion:1','plan_sha256':reviewed,
        'gateway_config_sha256':launch.sha(launch.encoded(gateway)), 'root_config_sha256':launch.sha(launch.encoded(root_config)),
        'launch_configuration_sha256':launch.sha(launch_configuration),'module_sha256':value['module_source']['sha256'],
        'public_key':public,'broker_started':False,'model_calls':0,'qualification':False,'library_effects':False}
    write(root/'complete.json',launch.encoded(completion),mode=0o440)
    return completion


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('operation',choices=('plan','apply','gateway-plan','gateway-apply'))
    parser.add_argument('--input',type=Path,required=True); parser.add_argument('--review-sha256')
    args = parser.parse_args()
    planner = gateway_plan if args.operation.startswith('gateway-') else plan
    changer = gateway_apply if args.operation.startswith('gateway-') else apply
    result = planner(args.input)[1] if args.operation.endswith('plan') else changer(args.input,args.review_sha256)
    print(json.dumps(result,sort_keys=True))
