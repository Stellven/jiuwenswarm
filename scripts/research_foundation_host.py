"""Finite host observations for the registered foundation checks.

Only identified local images and fresh owned probe containers are used. Probe
containers have no application account, provider credential, fixture volume or
Docker socket. They do not authorize research work or replace missing runtime
and scientific resources with synthetic passing observations.
"""
from __future__ import annotations

import hashlib
import base64
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

try:
    from scripts.research_foundation import FoundationBlocked, digest, validate_profile, read_regular, NoRedirect
except ModuleNotFoundError:
    from research_foundation import FoundationBlocked, digest, validate_profile, read_regular, NoRedirect


PREFIX = b'AI4R_FOUNDATION_PROBE:'
CONFIGURATION_PROBE = r'''
import json,os,pathlib,sys
from jiuwenswarm.research.bootstrap import prepare_environment,StartupBlocked
mode=sys.argv[1]
root=pathlib.Path('/tmp/ai4r-foundation-probe');root.mkdir(mode=0o700)
base=dict(os.environ);base.update(JIUWENSWARM_M1_ORIGIN='http://127.0.0.1:5173',JIUWENSWARM_M1_BIND_ADDRESS='127.0.0.1',JIUWENSWARM_M1_STATE='/var/lib/ai4r',JIUWENSWARM_M1_ACCOUNTS='/var/lib/ai4r-accounts')
result={'schema':'ai4r-foundation-probe-observation:1','mode':mode,'uid':os.geteuid(),'cases':[]}
if mode=='configuration':
 for case,raw in [('missing',None),('invalid_yaml',b'operator: [invalid'),('closed_schema',b'{"arbitrary_override":true}')]:
  path=root/(case+'.yaml')
  if raw is not None:path.write_bytes(raw);path.chmod(0o644)
  env=dict(base);env['JIUWENSWARM_M1_CONFIG']=str(path)
  try:
   captured,_=prepare_environment(env)
   result['cases'].append({'id':case,'inspection_only':captured.get('JIUWENSWARM_M1_REFUSAL_ONLY')=='operator_configuration_unavailable','sdk':captured.get('JIUWENSWARM_AGENT_SDK')})
  except Exception as error:result['cases'].append({'id':case,'inspection_only':False,'error':type(error).__name__})
elif mode=='custody':
 path=pathlib.Path('/hidden-fixtures/public-test-canary');path.write_bytes(b'public harmless fixture sentinel');path.chmod(0o644)
 try:
  prepare_environment(base)
  result['cases'].append({'id':'readable_fixture_mount','denied':False})
 except StartupBlocked as error:
  result['cases'].append({'id':'readable_fixture_mount','denied':str(error)=='HIDDEN_CUSTODY_MOUNT_PRESENT','code':str(error)})
else:raise SystemExit('Fixed probe mode required')
print('AI4R_FOUNDATION_PROBE:'+json.dumps(result,sort_keys=True,separators=(',',':')),flush=True)
'''


def _absent(call):
    return bool(call.returncode and (b'No such object:' in call.stderr or b'No such container:' in call.stderr))


def _new_name(profile, kind):
    suffix = hashlib.sha256((profile['job_id'] + '\0' + profile['instance_id'] + '\0' + kind).encode()).hexdigest()[:24]
    return 'ai4r-foundation-' + kind + '-' + suffix


def _seccomp(host):
    path = str((host.root / 'deploy/m1/seccomp/executor.json').resolve())
    if os.name == 'nt':
        match = re.fullmatch(r'([A-Za-z]):[\\/](.*)', path)
        if not match:
            raise FoundationBlocked('LOCAL_SECCOMP_PATH_REQUIRED')
        path = '/mnt/' + match[1].lower() + '/' + match[2].replace('\\', '/')
    return path


def _cleanup(host, name, job_id):
    result = {'name': name, 'attempted': False, 'confirmed': False}
    try:
        call = host.run(['container', 'inspect', name], check=False)
        if call.returncode == 0:
            rows = json.loads(call.stdout)
            if len(rows) != 1 or rows[0].get('Config', {}).get('Labels', {}).get('ai4r.foundation-probe') != job_id:
                raise FoundationBlocked('PROBE_CLEANUP_OWNERSHIP_MISMATCH')
            result['attempted'] = True
            result['remove_returncode'] = host.run(['container', 'rm', '--force', name], check=False).returncode
            call = host.run(['container', 'inspect', name], check=False)
        result['confirmed'] = _absent(call)
        if not result['confirmed']:
            result['error'] = 'PROBE_CLEANUP_UNCONFIRMED'
    except Exception as error:
        result['error'] = str(error) if isinstance(error, FoundationBlocked) else type(error).__name__
    return result


def configuration_probe(host, profile, mode):
    validate_profile(profile)
    if mode not in {'configuration', 'custody'}:
        raise FoundationBlocked('FIXED_FOUNDATION_PROBE_REQUIRED')
    name = _new_name(profile, mode)
    initial = host.run(['container', 'inspect', name], check=False)
    if not _absent(initial):
        raise FoundationBlocked('FRESH_PROBE_NAME_REQUIRED')
    args = _base_probe_args(host, profile, name)
    if mode == 'custody':
        args += ['--tmpfs', '/hidden-fixtures:rw,nosuid,nodev,size=1m,mode=0755']
    args += ['--entrypoint', '/opt/venv/bin/python', profile['image_id'], '-I', '-c', CONFIGURATION_PROBE, mode]
    record = {'schema': 'ai4r-foundation-host-probe:1', 'kind': mode, 'name': name,
              'image_id': profile['image_id'], 'program_sha256': digest(CONFIGURATION_PROBE.encode()),
              'target_touched': False, 'qualified': False, 'model_credential_mounted': False}
    try:
        call = host.run(args, timeout=120, check=False)
        record.update(returncode=call.returncode, stdout_sha256=digest(call.stdout), stderr_sha256=digest(call.stderr))
        frames = [line[len(PREFIX):] for line in call.stdout.splitlines() if line.startswith(PREFIX)]
        if call.returncode or len(frames) != 1 or len(frames[0]) > 16384:
            raise FoundationBlocked('FIXED_PROBE_DID_NOT_COMPLETE')
        value = json.loads(frames[0])
        if value.get('schema') != 'ai4r-foundation-probe-observation:1' or value.get('mode') != mode or value.get('uid') != 0:
            raise FoundationBlocked('FIXED_PROBE_IDENTITY_MISMATCH')
        cases = value.get('cases', [])
        if mode == 'configuration':
            expected = {'missing', 'invalid_yaml', 'closed_schema'}
            passed = len(cases) == 3 and {row.get('id') for row in cases} == expected and all(
                row.get('inspection_only') is True and row.get('sdk') == 'codex_subscription' for row in cases)
        else:
            passed = (len(cases) == 1 and cases[0].get('id') == 'readable_fixture_mount' and cases[0].get('denied') is True
                      and cases[0].get('code') == 'HIDDEN_CUSTODY_MOUNT_PRESENT')
        record.update(observation=value, qualified=bool(passed))
    except Exception as error:
        record['error'] = str(error) if isinstance(error, FoundationBlocked) else type(error).__name__
    finally:
        record['cleanup'] = _cleanup(host, name, profile['job_id'])
        record['qualified'] = record['qualified'] and record['cleanup']['confirmed']
    return record


def _base_probe_args(host, profile, name):
    args = ['run', '--rm', '--name', name, '--label', 'ai4r.foundation-probe=' + profile['job_id'],
            '--label', 'ai4r.owner=' + profile['job_id'], '--label', 'com.docker.compose.project=' + profile['project'],
            '--network', 'none', '--read-only', '--init', '--user', '0:0', '--workdir', '/tmp',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--security-opt', 'seccomp=' + _seccomp(host),
            '--memory', '2g', '--pids-limit', '256']
    for capability in ('SETUID', 'SETGID', 'CHOWN', 'FOWNER', 'DAC_OVERRIDE', 'KILL'):
        args += ['--cap-add', capability]
    for path in ('/tmp', '/var/lib/ai4r', '/var/lib/ai4r-accounts', '/var/lib/ai4r-executor', '/workspace/input',
                 '/workspace/poc', '/run/ai4r', '/run/ai4r-supervisor', '/run/ai4r-executor', '/run/ai4r-store'):
        args += ['--tmpfs', path + ':rw,nosuid,nodev,size=128m,mode=0711']
    return args


NATIVE_FIELDS = frozenset({'built_ui', 'attach_detach_preserves', 'authority_unchanged', 'fault_logs_no_replay',
    'zero_external_constructors', 'zero_external_network', 'no_runtime_install', 'fixed_owned_panes', 'ordinary_preserved'})


def native_probe(host, profile):
    validate_profile(profile)
    name = _new_name(profile, 'native')
    if not _absent(host.run(['container', 'inspect', name], check=False)):
        raise FoundationBlocked('FRESH_PROBE_NAME_REQUIRED')
    program = read_regular(Path(__file__).with_name('research_foundation_native_probe.py')).decode('utf8')
    args = _base_probe_args(host, profile, name) + ['--env', 'AI4R_FOUNDATION_NATIVE_PROBE=1',
        '--entrypoint', '/opt/venv/bin/python', profile['image_id'], '-I', '-c', program]
    record = {'schema': 'ai4r-foundation-host-probe:1', 'kind': 'native', 'name': name,
              'image_id': profile['image_id'], 'program_sha256': digest(program.encode()),
              'target_touched': False, 'qualified': False, 'model_credential_mounted': False}
    try:
        call = host.run(args, timeout=240, check=False)
        record.update(returncode=call.returncode, stdout_sha256=digest(call.stdout), stderr_sha256=digest(call.stderr))
        frames = [line[len(PREFIX):] for line in call.stdout.splitlines() if line.startswith(PREFIX)]
        if call.returncode or len(frames) != 1 or len(frames[0]) > 4 * 1024**2:
            raise FoundationBlocked('FIXED_PROBE_DID_NOT_COMPLETE')
        value = json.loads(frames[0])
        if value.get('schema') != 'ai4r-foundation-native-probe:1' or value.get('instrumented') is not True or value.get('credential_mounted') is not False:
            raise FoundationBlocked('FIXED_PROBE_IDENTITY_MISMATCH')
        fields = value.get('observations', {})
        record.update(observation=value, qualified=not value.get('errors') and NATIVE_FIELDS <= fields.keys()
                      and all(fields[key] is True for key in NATIVE_FIELDS))
    except Exception as error:
        record['error'] = str(error) if isinstance(error, FoundationBlocked) else type(error).__name__
    finally:
        record['cleanup'] = _cleanup(host, name, profile['job_id'])
        record['qualified'] = record['qualified'] and record['cleanup']['confirmed']
    return record


def installed_surfaces(host, profile, container_id):
    validate_profile(profile)
    _target(host, profile, container_id)
    observations = []
    for surface, argv in [('cli', ['/opt/venv/bin/jiuwenswarm', 'research', '--help']),
                          ('tui', ['/opt/venv/bin/jiuwenswarm-tui', '--help'])]:
        result = host.run(['exec', '--user', '10001:10001', container_id, *argv], timeout=30, check=False)
        observations.append({'surface': surface, 'returncode': result.returncode, 'bytes': len(result.stdout),
                             'sha256': digest(result.stdout), 'stderr_sha256': digest(result.stderr),
                             'help_present': result.returncode == 0 and b'usage:' in result.stdout.lower()})
    ui = public_ui(profile)
    return {'schema': 'ai4r-foundation-installed-surfaces:1', 'image_id': profile['image_id'],
            'instance_id': profile['instance_id'], 'qualified': all(row['help_present'] for row in observations) and ui['built_ui'],
            'public_ui': ui,
            'observations': observations,
            'limitations': ['Help execution does not qualify an authenticated or interactive client journey.']}


def public_ui(profile):
    validate_profile(profile)
    result = {'built_ui': False}
    try:
        with build_opener(NoRedirect()).open(Request(profile['origin'] + '/'), timeout=10) as response:
            raw = response.read(1024**2 + 1)
            result.update(status=response.status, bytes=len(raw), sha256=digest(raw))
            result['built_ui'] = response.status == 200 and len(raw) <= 1024**2 and b'<html' in raw.lower() and b'/assets/' in raw
    except Exception as error:
        result['error'] = type(error).__name__
    return result


def port_conflict_probe(host, profile, container_id):
    validate_profile(profile)
    origin = urlsplit(profile['origin'])
    name = _new_name(profile, 'port')
    if not _absent(host.run(['container', 'inspect', name], check=False)):
        raise FoundationBlocked('FRESH_PROBE_NAME_REQUIRED')
    address = '[' + origin.hostname + ']' if ':' in origin.hostname else origin.hostname
    record = {'schema': 'ai4r-foundation-port-conflict:1', 'name': name, 'qualified': False, 'target_touched': False}
    try:
        before = [_target(host, profile, container_id)]
        expected = {'5173/tcp': [{'HostIp': origin.hostname, 'HostPort': str(origin.port)}]}
        if before[0].get('NetworkSettings', {}).get('Ports') != expected:
            raise FoundationBlocked('EXACT_PRIVATE_TARGET_PORT_REQUIRED')
        call = host.run(['run', '--rm', '--name', name, '--label', 'ai4r.foundation-probe=' + profile['job_id'],
            '--network', 'bridge', '--read-only', '--user', '65534:65534', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--publish', address + ':' + str(origin.port) + ':5173',
            '--entrypoint', '/bin/true', profile['image_id']], timeout=30, check=False)
        record.update(returncode=call.returncode, stdout_sha256=digest(call.stdout), stderr_sha256=digest(call.stderr))
        error = call.stderr.lower()
        conflict = call.returncode != 0 and (b'port is already allocated' in error or b'address already in use' in error)
        after = host.json(['container', 'inspect', container_id])
        same = (len(after) == 1 and after[0].get('Id') == before[0].get('Id') and after[0].get('Image') == profile['image_id']
                and after[0].get('State', {}).get('Running') is True
                and before[0].get('NetworkSettings', {}).get('Ports') == after[0].get('NetworkSettings', {}).get('Ports'))
        record.update(conflict_reported=bool(conflict), original_target_unchanged=bool(same), qualified=bool(conflict and same))
    except Exception as error:
        record['error'] = str(error) if isinstance(error, FoundationBlocked) else type(error).__name__
    finally:
        record['cleanup'] = _cleanup(host, name, profile['job_id'])
        record['qualified'] = record['qualified'] and record['cleanup']['confirmed']
    return record


def _target(host, profile, container_id):
    if not isinstance(container_id, str) or not re.fullmatch(r'[a-f0-9]{12,64}', container_id):
        raise FoundationBlocked('EXACT_TARGET_CONTAINER_REQUIRED')
    rows = host.json(['container', 'inspect', container_id])
    if (len(rows) != 1 or not rows[0].get('Id', '').startswith(container_id)
            or rows[0].get('Image') != profile['image_id'] or rows[0].get('State', {}).get('Running') is not True
            or rows[0].get('Config', {}).get('Labels', {}).get('com.docker.compose.project') != profile['project']):
        raise FoundationBlocked('EXACT_LIVE_OWNED_TARGET_REQUIRED')
    return rows[0]


def enrich_observations(host, profile, check_id, receipts, container_id, output, *, source_build_pin=None):
    """Populate only the assertions actually exercised by this fixed procedure."""
    output = Path(output)
    if check_id == 'M1-001/V15':
        if source_build_pin:
            try:
                from scripts.research_operations import operations_probe
            except ModuleNotFoundError:
                from research_operations import operations_probe
            value = operations_probe(host, profile, source_build_pin, output)
            receipts['operations']['observations'] = value['observations']
            receipts['operations']['qualified'] = bool(value['observations'])
            receipts['operations']['limitations'] = [] if value['qualified'] else ['An actual operations stage failed or remained unavailable; retain its exact partial evidence.']
        else:
            receipts['operations']['limitations'] = ['An exact independently verified I014 build-stage pin is required; no lifecycle fixture is dispatched.']
    if check_id in {'M1-001/V09', 'M1-001/V17', 'M1-006/V29'}:
        value = installed_surfaces(host, profile, container_id)
        with (output / 'installed-surfaces.json').open('xb') as stream:
            stream.write(json.dumps(value, sort_keys=True).encode())
        receipts['startup']['observations']['native_surfaces'] = value['qualified']
        receipts['startup']['qualified'] = True
    if check_id in {'M1-001/V09', 'M1-006/V05'}:
        for mode, field in [('configuration', 'invalid_config_cases'), ('custody', 'planted_fixture_denied')]:
            value = configuration_probe(host, profile, mode)
            with (output / (mode + '-probe.json')).open('xb') as stream:
                stream.write(json.dumps(value, sort_keys=True).encode())
            receipts['startup']['observations'][field] = value['qualified']
            receipts['startup']['qualified'] = True
    if check_id == 'M1-006/V06':
        value = port_conflict_probe(host, profile, container_id)
        with (output / 'port-conflict-probe.json').open('xb') as stream:
            stream.write(json.dumps(value, sort_keys=True).encode())
        receipts['startup']['observations']['port_conflict_denied'] = value['qualified']
        receipts['startup']['qualified'] = True
    if check_id in {'M1-001/V17', 'M1-006/V28', 'M1-006/V29', 'M1-006/V06'}:
        value = native_probe(host, profile)
        with (output / 'native-probe.json').open('xb') as stream:
            stream.write(json.dumps(value, sort_keys=True).encode())
        export = value.get('observation', {}).get('public_export')
        if export:
            raw = base64.b64decode(export['data_b64'], validate=True)
            if digest(raw) != export['sha256'] or len(raw) != export['bytes']:
                raise FoundationBlocked('NATIVE_PUBLIC_EXPORT_IDENTITY_CHANGED')
            with (output / 'native-public-export.zip').open('xb') as stream: stream.write(raw)
        fields = value.get('observation', {}).get('observations', {}) if value['cleanup']['confirmed'] else {}
        actual = (value['cleanup']['confirmed'] and value.get('returncode') == 0
                  and value.get('observation', {}).get('errors') == [])
        for kind, names in [('tmux', ('fixed_owned_panes', 'attach_detach_preserves', 'authority_unchanged', 'fault_logs_no_replay')),
                            ('channels', ('zero_external_constructors', 'zero_external_network', 'ordinary_preserved')),
                            ('startup', ('no_runtime_install',))]:
            for name in names:
                target_compatible = receipts[kind]['observations'].get(name) is True if name == 'fixed_owned_panes' else True
                receipts[kind]['observations'][name] = fields.get(name) is True and target_compatible
            receipts[kind]['qualified'] = actual
    # These subsets do not turn the remaining readiness/auth/trace obligations
    # into passes. The controller still checks its complete frozen population.
    return receipts
