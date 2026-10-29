"""Fixed disposable native-startup/PTY probe; executed only in its owned image.

The host passes these exact captured bytes to Python. This is verification
instrumentation, never a product entrypoint or a research execution grant.
"""
from __future__ import annotations

import hashlib
import fcntl
import base64
import json
import io
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import threading
import time
import termios
import zipfile
from urllib.error import HTTPError
from urllib.request import urlopen
from urllib.parse import urlsplit, parse_qs


TRACE_HOOK = r'''
import hashlib,ipaddress,json,os,re,sys,threading
_path='/tmp/ai4r-native-probe-traces/'+str(os.getpid())+'.jsonl'
_fd=os.open(_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
def _emit(kind,**fields):
 raw=json.dumps(dict(kind=kind,pid=os.getpid(),uid=os.geteuid(),**fields),sort_keys=True,separators=(',',':')).encode()+b'\n'
 os.write(_fd,raw)
def _profile(frame,event,arg):
 if event!='call' or frame.f_code.co_name!='__init__':return
 obj=frame.f_locals.get('self');cls=type(obj);module=cls.__module__;name=cls.__name__
 if module.startswith('jiuwenswarm.gateway.channel_manager.') and name.endswith('Channel'):
  native=('.web.' in module or '.tui.' in module or module.endswith('.base'))
  _emit('channel_constructor',module=module,name=name,native=native)
def _approved_process(program,words):
 if program in ('python','python3','python3.12'):
  return len(words)>=3 and words[1]=='-m' and words[2] in ('jiuwenswarm.research.bootstrap','jiuwenswarm.research.executor_rpc','jiuwenswarm.research.store_custody')
 if program!='tmux' or len(words)<4 or words[1]!='-S' or not re.fullmatch(r'/run/ai4r/tmux-[a-f0-9]{32}\.sock',str(words[2])):return False
 action=words[3]
 if action in ('new-session','split-window'):
  return bool(re.fullmatch(r'/usr/bin/tmux -S /run/ai4r/tmux-([a-f0-9]{32})\.sock wait-for \1-(agentserver|gateway|frontend); exec /opt/venv/bin/python -m jiuwenswarm\.research\.native_entry \2',str(words[-1])))
 if action=='pipe-pane':return bool(re.fullmatch(r'exec /bin/cat >> /var/lib/ai4r/native/logs/tmux/[a-f0-9]{32}-(agentserver|gateway|frontend)\.log',str(words[-1])))
 if action=='send-keys':return words[-1]=='C-c'
 if action=='set-option':return list(words[-2:])==['remain-on-exit','on']
 return action in ('wait-for','list-panes','list-clients','kill-session','detach-client','select-pane','attach-session') and not any('#(' in str(word) for word in words)
def _audit(event,args):
 if event in ('socket.connect','socket.bind'):
  sock,address=args
  if sock.family not in (2,10):return
  try:loopback=ipaddress.ip_address(address[0]).is_loopback
  except ValueError:loopback=False
  _emit(event,loopback=loopback,port=address[1])
  if event=='socket.connect' and not loopback:raise PermissionError('Owned verification probe denies external network')
 elif event in ('subprocess.Popen','os.exec','os.posix_spawn'):
  program=os.path.basename(str(args[0]));argv=args[1]
  words=argv if isinstance(argv,(list,tuple)) else []
  install=(program in ('pip','pip3','uv','npm','npx','yarn','pnpm') and any(str(x) in ('install','sync','ci','build') for x in words)) or any(str(x)=='pip' for x in words[:3])
  _emit('process_start',program=program,dependency_operation=install,approved_control_process=_approved_process(program,words),module=str(words[2]) if len(words)>=3 and words[1]=='-m' else None)
 elif event=='os.system':_emit('process_start',program='unknown-shell',dependency_operation=True,approved_control_process=False,module=None)
_emit('hook_ready')
sys.addaudithook(_audit);sys.setprofile(_profile);threading.setprofile(_profile)
'''


EXTERNAL = ('feishu', 'feishu_enterprise', 'xiaoyi', 'dingtalk', 'telegram', 'discord', 'slack',
            'whatsapp', 'wecom', 'wechat', 'ssh', 'a2a', 'acp')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def wait_for(predicate, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    raise TimeoutError('Owned native probe deadline')


def inspect_json(path):
    try:
        return json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None


def serve_ready():
    try:
        with urlopen('http://127.0.0.1:5173/', timeout=1) as response:
            return response.status == 200 and b'<html' in response.read(1024**2).lower()
    except OSError:
        return False


def api_bound():
    try:
        urlopen('http://127.0.0.1:5173/api/v1/readiness', timeout=1).close()
    except HTTPError as error:
        return error.code == 401 and json.loads(error.read(65536)).get('category') == 'auth'
    except (OSError, ValueError):
        return False
    return False


def retain_service_logs(paths, private_markers):
    entries = []
    for path in paths:
        raw = path.read_bytes()
        entry = {'name': path.name, 'bytes': len(raw), 'sha256': digest(raw), 'raw_retained': False}
        if any(marker and marker in raw for marker in private_markers):
            entry['reason'] = 'private_value_requires_separate_protected_capture'
        else:
            entry.update(raw_retained=True, data_b64=base64.b64encode(raw).decode('ascii'))
        entries.append(entry)
    return entries


def public_export(observation, private_markers):
    metadata = {key: value for key, value in observation.items() if key != 'public_export'}
    metadata['logs'] = [{key: value for key, value in entry.items() if key != 'data_b64'} for entry in observation.get('logs', [])]
    files = {'native-observation.json': json.dumps(metadata, sort_keys=True, separators=(',', ':')).encode()}
    for entry in observation.get('logs', []):
        if not entry.get('raw_retained'): continue
        name = entry['name']
        if Path(name).name != name or '/' in name or '\\' in name:
            raise ValueError('Noncanonical service log name')
        raw = base64.b64decode(entry['data_b64'], validate=True)
        if len(raw) != entry['bytes'] or digest(raw) != entry['sha256']:
            raise ValueError('Original service log identity changed')
        files['service-logs/' + name] = raw
    if any(marker and marker in raw for marker in private_markers for raw in files.values()):
        raise ValueError('Private value in public export')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)); info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED; archive.writestr(info, raw)
    raw = output.getvalue()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if any(marker and marker in archive.read(name) for marker in private_markers for name in archive.namelist()):
            raise ValueError('Private value in serialized export')
    return {'sha256': digest(raw), 'bytes': len(raw), 'data_b64': base64.b64encode(raw).decode('ascii'),
            'files': [{'path': name, 'bytes': len(payload), 'sha256': digest(payload)} for name, payload in sorted(files.items())],
            'private_values_absent': True}


def main():
    if os.geteuid() != 0 or os.environ.get('AI4R_FOUNDATION_NATIVE_PROBE') != '1':
        raise SystemExit('Owned root probe container required')
    from jiuwenswarm.research.bootstrap import prepare_environment, NativeSessions
    env, ipc = prepare_environment(os.environ)
    if not env.get('JIUWENSWARM_M1_REFUSAL_ONLY'):
        raise SystemExit('A missing operator configuration must disable execution')
    trace = Path('/tmp/ai4r-native-probe-traces'); trace.mkdir(mode=0o700); os.chown(trace, 10001, 10001)
    hook = Path('/tmp/ai4r-native-probe-hook'); hook.mkdir(mode=0o755)
    (hook / 'sitecustomize.py').write_text(TRACE_HOOK, encoding='utf8'); (hook / 'sitecustomize.py').chmod(0o644)
    env.update(PYTHONPATH=str(hook), TERM='xterm-256color')
    import yaml
    config = Path(env['JIUWENSWARM_DATA_DIR']) / 'config/config.yaml'
    value = yaml.safe_load(config.read_bytes()) or {}
    value['channels'] = {name: {'enabled': True, 'token': 'public-test-canary', 'bot_token': '000000:public-test-canary',
                                'app_id': 'public-test-app', 'app_secret': 'public-test-secret'} for name in EXTERNAL}
    config.write_text(yaml.safe_dump(value), encoding='utf8'); os.chown(config, 10001, 10001); config.chmod(0o600)
    native = None
    attached = None
    master = slave = None
    streams = {'stdout': hashlib.sha256(), 'stderr': hashlib.sha256()}
    safe_events = []
    private_markers = []
    result = {'schema': 'ai4r-foundation-native-probe:1', 'instrumented': True,
              'credential_mounted': False, 'stale_channels_enabled': list(EXTERNAL), 'observations': {}, 'errors': []}
    def drain(stream, name):
        for raw in iter(stream.readline, b''):
            streams[name].update(raw)
            if raw.startswith(b'Open JiuwenSwarm: '):
                url = raw[len(b'Open JiuwenSwarm: '):].strip()
                private_markers.append(url)
                try:
                    for values in parse_qs(urlsplit(url.decode()).fragment).values():
                        private_markers.extend(value.encode() for value in values if value)
                except (ValueError, UnicodeError):
                    result['errors'].append('BootstrapMarkerParsingFailed')
            # Bootstrap URLs and all other native output stay out of evidence.
            try:
                value = json.loads(raw)
                if value.get('event') == 'native-service-exit':
                    safe_events.append(value)
            except (ValueError, AttributeError):
                pass
    try:
        native = subprocess.Popen(['/opt/venv/bin/jiuwenswarm-start'], env=env, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        readers = [threading.Thread(target=drain, args=(getattr(native, name), name), daemon=True) for name in streams]
        for reader in readers: reader.start()
        boot = wait_for(lambda: inspect_json(ipc / 'instance.json'))
        if boot.get('schema') != 'ai4r-native-instance:1' or set(boot.get('panes', {})) != {'agentserver', 'gateway', 'frontend'}:
            raise ValueError('Fixed native identity missing')
        result['boot_id'] = boot['boot_id']
        sessions = NativeSessions(ipc, boot['boot_id'], env); sessions.panes = boot['panes']
        wait_for(serve_ready)
        wait_for(api_bound)
        wait_for(lambda: sessions.inspect()['running'])
        # Native readiness can remain unavailable; this probe never submits.
        result['observations']['built_ui'] = True
        before = sessions.inspect()
        result['before'] = before
        token = Path('/var/lib/ai4r-accounts/sessions/session-token')
        grant_value = token.read_bytes() if token.is_file() else None
        if grant_value: private_markers.append(grant_value.strip())
        grant_hash = digest(grant_value) if grant_value else None
        master, slave = pty.openpty()
        os.fchown(slave, 10001, 10001); os.fchmod(slave, 0o600)
        attached = subprocess.Popen(['/opt/venv/bin/jiuwenswarm-start', '--attach', 'frontend'], env=env,
                                    stdin=slave, stdout=slave, stderr=slave, start_new_session=True,
                                    preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0))
        os.close(slave); slave = None
        clients = wait_for(lambda: sessions._tmux('list-clients', '-F', '#{session_name}', check=False).stdout.strip(), 10)
        if any(name != sessions.name for name in clients.splitlines()):
            raise ValueError('Foreign tmux client/session')
        capture = hashlib.sha256()
        if select.select([master], [], [], 1)[0]:
            capture.update(os.read(master, 65536))
        detached = subprocess.run(['/opt/venv/bin/jiuwenswarm-start', '--detach'], env=env,
                                  stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
        attached.wait(timeout=10)
        after = sessions.inspect()
        result['after_detach'] = after
        result['pty_sha256'] = capture.hexdigest()
        result['observations']['attach_detach_preserves'] = (detached.returncode == attached.returncode == 0 and before == after
            and after['running'] and native.poll() is None)
        result['observations']['authority_unchanged'] = bool(grant_hash and token.is_file() and digest(token.read_bytes()) == grant_hash)
        # Only the registered frontend pane receives an actual controlled fault.
        fault = sessions._tmux('send-keys', '-t', boot['panes']['frontend'], 'C-c', check=False)
        native.wait(timeout=30)
        for reader in readers: reader.join(timeout=3)
        result['native_exit_code'] = native.returncode
        result['fault_events'] = safe_events
        logs = sorted((Path(env['JIUWENSWARM_DATA_DIR']) / 'logs/tmux').glob(boot['boot_id'] + '-*.log'))
        result['logs'] = retain_service_logs(logs, private_markers)
        if not all(entry['raw_retained'] for entry in result['logs']):
            result['errors'].append('PrivateValueInServiceLog')
        result['observations']['fault_logs_no_replay'] = (fault.returncode == 0 and native.returncode == 1 and len(logs) == 3
            and all(entry['raw_retained'] for entry in result['logs'])
            and any(any(p.get('role') == 'frontend' and p.get('running') is False for p in event.get('panes', [])) for event in safe_events))
        trace_rows = []
        for path in sorted(trace.glob('*.jsonl')):
            trace_rows.extend(json.loads(line) for line in path.read_bytes().splitlines())
        result['trace'] = trace_rows
        native_constructors = [row for row in trace_rows if row['kind'] == 'channel_constructor' and row.get('native')]
        external_constructors = [row for row in trace_rows if row['kind'] == 'channel_constructor' and not row.get('native')]
        outbound = [row for row in trace_rows if row['kind'] == 'socket.connect' and row.get('loopback') is False]
        unexpected_binds = [row for row in trace_rows if row['kind'] == 'socket.bind' and row.get('port') not in {0, 5173, 18092, 19000, 19001}]
        installs = [row for row in trace_rows if row['kind'] == 'process_start' and row.get('dependency_operation')]
        unknown_processes = [row for row in trace_rows if row['kind'] == 'process_start' and row.get('approved_control_process') is not True]
        observed_native = {row.get('name') for row in native_constructors}
        complete = {'WebChannel', 'TuiChannel'} <= observed_native and len({row['pid'] for row in trace_rows if row['kind'] == 'hook_ready'}) >= 4
        result['observations'].update(zero_external_constructors=bool(complete and not external_constructors),
            zero_external_network=bool(complete and not outbound and not unexpected_binds), no_runtime_install=bool(complete and not installs and not unknown_processes),
            fixed_owned_panes=before['running'] and len(before['panes']) == 3)
        ordinary_env = dict(env); ordinary_env.pop('JIUWENSWARM_M1_PROFILE', None); ordinary_env.pop('PYTHONPATH', None)
        ordinary = subprocess.run(['/opt/venv/bin/python', '-I', '-c',
            "from jiuwenswarm.research.native_profile import M1_PROFILE,native_channel_config;c={'telegram':{'enabled':True}};assert not M1_PROFILE and native_channel_config(c) is c;print('ordinary_configuration_preserved')"],
            env=ordinary_env, capture_output=True, timeout=10)
        result['observations']['ordinary_preserved'] = ordinary.returncode == 0 and ordinary.stdout.strip() == b'ordinary_configuration_preserved'
    except Exception as error:
        result['errors'].append(type(error).__name__)
    finally:
        if attached and attached.poll() is None:
            attached.terminate()
            try: attached.wait(timeout=5)
            except subprocess.TimeoutExpired: attached.kill(); attached.wait(timeout=5)
        if native and native.poll() is None:
            native.terminate()
            try: native.wait(timeout=30)
            except subprocess.TimeoutExpired: native.kill(); native.wait(timeout=5)
        for fd in (master, slave):
            if fd is not None: os.close(fd)
        result['native_output_sha256'] = {name: value.hexdigest() for name, value in streams.items()}
    # A real private marker file exercises the same retention allowlist used by
    # the public export, without introducing any external/provider credential.
    import secrets
    marker = secrets.token_urlsafe(32).encode()
    private_markers.append(marker)
    marker_path = Path('/tmp/ai4r-private-export-marker')
    with marker_path.open('xb') as handle: handle.write(marker)
    marker_path.chmod(0o600)
    canary = retain_service_logs([marker_path], [marker])[0]
    result['redaction_fixture'] = {'withheld': canary['raw_retained'] is False and 'data_b64' not in canary,
                                    'original_sha256': canary['sha256'], 'bytes': canary['bytes']}
    try:
        result['public_export'] = public_export(result, private_markers)
    except Exception as error:
        result['errors'].append(type(error).__name__)
    print('AI4R_FOUNDATION_PROBE:' + json.dumps(result, sort_keys=True, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    main()
