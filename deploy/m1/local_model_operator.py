"""Optional private model deployment plumbing. No model or SSH operations.

This stdlib-only source is bundled with operator_host for remote host RPC.
Host sources stay outside containers; only the selected socket directory is
bound, and only two validated configuration files enter an app-only volume.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
from urllib.parse import urlsplit

CONFIG_ROOT = '/run/ai4r-local-model-config'
SOCKET_ROOT = '/run/ai4r-local-model'
APP_UID = 10001
PROFILE_SCHEMA = 'ai4r-local-model-deployment:1'
ROLE = 'local-model-config'
CODEX_EFFORTS = frozenset({'medium'})


def require(condition):
    if not condition:
        raise ValueError('Invalid private local-model deployment configuration or custody')


def native_absolute_path(value, *, posix_only=False):
    if (not isinstance(value,str) or not value or '\\' in value or any(ord(c)<32 or 127<=ord(c)<=159 for c in value)
            or value.startswith('//') or any(part in {'.','..'} for part in value.split('/'))):return False
    if value.startswith('/'):return str(PurePosixPath(value))==value
    return (not posix_only and re.fullmatch(r'[A-Z]:/[^:]+',value) is not None
            and PureWindowsPath(value).is_absolute() and str(PureWindowsPath(value)).replace('\\','/')==value)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def path(value):
    require(isinstance(value, str) and value.startswith('/') and ',' not in value
            and '\\' not in value and not any(ord(c) < 32 for c in value)
            and str(PurePosixPath(value)) == value and '..' not in PurePosixPath(value).parts)
    result = Path(value)
    require(not any(p.is_symlink() for p in (result, *result.parents)))
    return result


def read_file(value, *, owner, modes, maximum):
    target = path(value)
    fd = os.open(target, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == owner
                and stat.S_IMODE(info.st_mode) in modes and info.st_size <= maximum)
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(maximum + 1)
        require(len(raw) <= maximum)
        return raw
    finally:
        os.close(fd)


def json_value(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
            parse_constant=lambda _: require(False))
    except (ValueError, UnicodeError):
        raise ValueError('Invalid private local-model JSON') from None


def validate_catalog(value):
    require(isinstance(value, dict) and set(value) == {'schema', 'gateway_id', 'backend', 'transport', 'models'}
            and value['schema'] == 'ai4r-local-model-catalog:1')
    require(isinstance(value['gateway_id'], str) and re.fullmatch(r'[a-z][a-z0-9_.-]{0,63}', value['gateway_id']))
    backend = value['backend']
    require(isinstance(backend,dict))
    codex=backend.get('kind')=='host-codex-app-server'
    if codex:
        require(set(backend)=={'kind','host_python','codex_executable','codex_sha256','account_fingerprint','working_directory'})
        require(native_absolute_path(backend['host_python'],posix_only=True))
        for key in ('codex_executable','working_directory'):require(native_absolute_path(backend[key]))
        for key in ('codex_sha256','account_fingerprint'):
            require(isinstance(backend[key],str) and re.fullmatch('[a-f0-9]{64}',backend[key]))
    else:
        require(set(backend)=={'kind','target','base_url'} and backend['kind']=='ssh-loopback-openai')
        require(isinstance(backend['target'], str) and len(backend['target']) <= 255
                and re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*(?:@[A-Za-z0-9][A-Za-z0-9.-]*)?', backend['target']))
        require(isinstance(backend['base_url'], str))
        url = urlsplit(backend['base_url'])
        require(url.scheme == 'http' and url.hostname in {'127.0.0.1', '::1'}
                and url.port is not None and 1 <= url.port <= 65535 and url.path == '/v1'
                and not (url.username or url.password or url.query or url.fragment))
    transport = value['transport']
    require(isinstance(transport, dict) and set(transport) == {'socket_path', 'session_file', 'peer_uid', 'socket_mode'})
    require(transport['socket_path'] == SOCKET_ROOT + '/model.sock'
            and transport['session_file'] == CONFIG_ROOT + '/session.json'
            and type(transport['peer_uid']) is int and transport['peer_uid'] >= 0
            and type(transport['socket_mode']) is int and transport['socket_mode'] == 0o660)
    fields = {'id', 'name', 'model_name', 'revision', 'enabled', 'context_window',
              'max_output_tokens', 'max_prompt_bytes', 'timeout_s', 'temperature', 'enable_thinking'}
    if codex:fields={'id','name','model_name','revision','enabled','context_window','max_prompt_bytes','timeout_s','reasoning_effort'}
    require(isinstance(value['models'], list) and len(value['models']) <= 32)
    ids = set()
    for model in value['models']:
        require(isinstance(model, dict) and set(model) == fields)
        require(isinstance(model['id'], str) and re.fullmatch(r'local-[a-z0-9][a-z0-9_.-]{0,55}', model['id'])
                and model['id'] not in ids)
        ids.add(model['id'])
        for key in ('name', 'model_name', 'revision'):
            require(isinstance(model[key], str) and 0 < len(model[key]) <= 256
                    and not any(ord(c) < 32 for c in model[key]))
        require(type(model['enabled']) is bool)
        if codex:require(isinstance(model['reasoning_effort'],str) and model['reasoning_effort'] in CODEX_EFFORTS)
        else:require(type(model['enable_thinking']) is bool)
        bounds=(('context_window',1048576),('max_prompt_bytes',256*1024))
        if not codex:bounds+=(('max_output_tokens',32768),)
        for key, bound in bounds:
            require(type(model[key]) is int and 0 < model[key] <= bound)
        if not codex:require(model['max_output_tokens'] <= model['context_window'])
        numbers=(('timeout_s',1,600),) if codex else (('timeout_s',1,600),('temperature',0,2))
        for key, low, high in numbers:
            require(type(model[key]) in {int, float} and math.isfinite(model[key]) and low <= model[key] <= high)
    return value


def validate_profile(profile):
    require(isinstance(profile, dict) and set(profile) == {'schema', 'catalog', 'session_file',
            'socket_directory', 'catalog_sha256', 'session_sha256'} and profile['schema'] == PROFILE_SCHEMA)
    for key in ('catalog', 'session_file', 'socket_directory'):
        path(profile[key])
    for key in ('catalog_sha256', 'session_sha256'):
        require(isinstance(profile[key], str) and re.fullmatch('[a-f0-9]{64}', profile[key]))
    return profile


def inspect_sources(catalog, session_file, socket_directory, *, ready=False):
    """Read protected local files, without contacting the socket or model."""
    require(os.name == 'posix')
    raw_catalog = read_file(catalog, owner=0, modes={0o444, 0o644, 0o600, 0o400}, maximum=128 * 1024)
    value = validate_catalog(json_value(raw_catalog))
    peer = value['transport']['peer_uid']
    raw_session = read_file(session_file, owner=peer, modes={0o600, 0o400}, maximum=16384)
    session = json_value(raw_session)
    require(isinstance(session, dict) and set(session) == {'session_id', 'capability'}
            and all(isinstance(v, str) and 32 <= len(v) <= 256
                    and all(33 <= ord(c) < 127 for c in v) for v in session.values()))
    directory = path(socket_directory)
    info = directory.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == peer and info.st_gid == APP_UID
            and stat.S_IMODE(info.st_mode) == 0o2710)
    # This bind must never disclose the relay's private ledger/session/runtime.
    require(all(item.name == 'model.sock' for item in directory.iterdir()))
    require(not path(catalog).is_relative_to(directory) and not path(session_file).is_relative_to(directory))
    socket = directory / 'model.sock'
    if ready or socket.exists() or socket.is_symlink():
        info = socket.lstat()
        require(not socket.is_symlink() and stat.S_ISSOCK(info.st_mode) and info.st_uid == peer
                and info.st_gid == APP_UID and stat.S_IMODE(info.st_mode) == 0o660)
    profile = dict(schema=PROFILE_SCHEMA, catalog=catalog, session_file=session_file,
        socket_directory=socket_directory, catalog_sha256=hashlib.sha256(raw_catalog).hexdigest(),
        session_sha256=hashlib.sha256(raw_session).hexdigest())
    return profile, raw_catalog, raw_session


def read_pinned(profile, *, ready=True):
    validate_profile(profile)
    current, catalog, session = inspect_sources(profile['catalog'], profile['session_file'],
                                               profile['socket_directory'], ready=ready)
    require(current == profile)
    return catalog, session


def labels(deployment):
    return {'ai4r.deployment': deployment['deployment_id'], 'ai4r.owner': 'ai4r-deployment:1', 'ai4r.role': ROLE}


def apply_compose(deployment, compose):
    profile = deployment.get('local_model')
    if profile is None:
        return
    validate_profile(profile)
    app = compose['services']['ai4r']
    require(not any(v['target'] in {CONFIG_ROOT, SOCKET_ROOT} for v in app['volumes']))
    volume = 'local_model_config'
    require(volume not in compose['volumes'])
    compose['volumes'][volume] = {'name': deployment['project'] + '_' + volume, 'labels': labels(deployment)}
    app['environment']['AI4R_LOCAL_MODEL_CATALOG'] = CONFIG_ROOT + '/catalog.json'
    app['volumes'].extend([
        {'type': 'volume', 'source': volume, 'target': CONFIG_ROOT, 'read_only': True, 'volume': {'nocopy': True}},
        {'type': 'bind', 'source': profile['socket_directory'], 'target': SOCKET_ROOT,
         'read_only': True, 'bind': {'create_host_path': False}}])


# Fixed Docker helper. Only stdin contains configuration/session bytes.
VOLUME_WRITER = '''import base64,json,os,stat,sys,uuid
from pathlib import Path
value=json.load(sys.stdin)
assert set(value)=={'catalog','session'}
root=Path('/operator')
assert not root.is_symlink() and root.stat().st_uid==0
assert set(p.name for p in root.iterdir())<={'catalog.json','session.json'}
for p in root.iterdir():
 s=p.lstat();assert stat.S_ISREG(s.st_mode) and not p.is_symlink() and s.st_nlink==1
 expected=(0,0o444) if p.name=='catalog.json' else (10001,0o400)
 assert (s.st_uid,stat.S_IMODE(s.st_mode))==expected
root.chmod(0o711)
for key,name,uid,mode in [('catalog','catalog.json',0,0o444),('session','session.json',10001,0o400)]:
 raw=base64.b64decode(value[key],validate=True);assert len(raw)<=131072
 temporary=root/('.publish-'+uuid.uuid4().hex)
 try:
  fd=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  with os.fdopen(fd,'wb') as f:
   f.write(raw);f.flush();os.fchown(f.fileno(),uid,uid);os.fchmod(f.fileno(),mode);os.fsync(f.fileno())
  os.replace(temporary,root/name)
 finally:temporary.unlink(missing_ok=True)
fd=os.open(root,os.O_RDONLY);os.fsync(fd);os.close(fd)
'''

VOLUME_VERIFY = '''import hashlib,json,stat,sys
from pathlib import Path
value=json.load(sys.stdin);assert set(value)=={'catalog_sha256','session_sha256'}
root=Path('/operator');meta=root.lstat()
assert stat.S_ISDIR(meta.st_mode) and meta.st_uid==0 and stat.S_IMODE(meta.st_mode)==0o711
assert set(p.name for p in root.iterdir())=={'catalog.json','session.json'}
for key,name,uid,mode in [('catalog_sha256','catalog.json',0,0o444),('session_sha256','session.json',10001,0o400)]:
 p=root/name;s=p.lstat()
 assert stat.S_ISREG(s.st_mode) and not p.is_symlink() and s.st_nlink==1
 assert (s.st_uid,stat.S_IMODE(s.st_mode))==(uid,mode) and s.st_size<=131072
 assert hashlib.sha256(p.read_bytes()).hexdigest()==value[key]
'''


def provision(deployment, docker):
    """Called only from explicit start, never from configure or module import."""
    profile = deployment.get('local_model')
    if profile is None:
        return
    # Bind paths and peer credentials refer to this Linux host. Never silently
    # interpret them on a remote TCP/SSH Docker daemon or userns-remapped host.
    endpoint = os.environ.get('DOCKER_HOST')
    if endpoint:
        require(endpoint == 'unix:///var/run/docker.sock')
    environment_context = os.environ.get('DOCKER_CONTEXT')
    selected_context = deployment.get('docker_context')
    require(not (environment_context and selected_context and environment_context != selected_context))
    selected_context = selected_context or environment_context
    context = [selected_context] if selected_context else []
    contexts = json.loads(docker(deployment, 'context', 'inspect', *context))
    require(isinstance(contexts, list) and len(contexts) == 1
            and isinstance(contexts[0].get('Endpoints', {}).get('docker', {}).get('Host'), str)
            and contexts[0]['Endpoints']['docker']['Host'] == 'unix:///var/run/docker.sock')
    security = json.loads(docker(deployment, 'info', '--format', '{{json .SecurityOptions}}'))
    require(isinstance(security, list) and all(isinstance(item, str) for item in security)
            and not any('rootless' in item.lower() or 'userns' in item.lower() for item in security))
    catalog, session = read_pinned(profile)
    volume = deployment['project'] + '_local_model_config'
    expected = labels(deployment)
    existing = docker(deployment, 'volume', 'ls', '--format', '{{.Name}}').decode().splitlines()
    if volume not in existing:
        args = ['volume', 'create']
        for key, value in expected.items():
            args += ['--label', key + '=' + value]
        docker(deployment, *args, volume)
    observed = json.loads(docker(deployment, 'volume', 'inspect', volume))
    require(len(observed) == 1 and observed[0]['Name'] == volume
            and observed[0].get('Driver') == 'local' and not observed[0].get('Options')
            and all(observed[0].get('Labels', {}).get(k) == v for k, v in expected.items()))
    # Repeated starts may read an identical active volume; changes need a stop.
    if docker(deployment, 'ps', '-q', '--filter', 'volume=' + volume).strip():
        docker(deployment, 'run', '--rm', '-i', '--pull', 'never', '--network', 'none', '--read-only', '--user', '0:0',
            '--cap-drop', 'ALL', '--cap-add', 'DAC_READ_SEARCH', '--security-opt', 'no-new-privileges',
            '--mount', 'type=volume,src=' + volume + ',dst=/operator,readonly',
            '--entrypoint', '/opt/venv/bin/python', deployment['app_image'], '-c', VOLUME_VERIFY,
            data=canonical({k: profile[k] for k in ('catalog_sha256', 'session_sha256')}))
        return
    docker(deployment, 'run', '--rm', '-i', '--pull', 'never', '--network', 'none', '--read-only', '--user', '0:0',
        '--cap-drop', 'ALL', '--cap-add', 'CHOWN', '--cap-add', 'DAC_OVERRIDE', '--cap-add', 'FOWNER',
        '--security-opt', 'no-new-privileges', '--mount', 'type=volume,src=' + volume + ',dst=/operator',
        '--entrypoint', '/opt/venv/bin/python', deployment['app_image'], '-c', VOLUME_WRITER,
        data=canonical({'catalog': base64.b64encode(catalog).decode(), 'session': base64.b64encode(session).decode()}))
