"""Finite T045 operations proof on a fresh disposable native instance.

An original root-produced I014 build stage is joined by exact frozen identity.
Only newly named test containers are removed; the unrelated sentinel volume
and retained evidence survive. No provider, main-account or fixture grant is
mounted, and no image build or broad cleanup is dispatched here.
"""
from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

try:
    from scripts.research_foundation import FoundationBlocked, digest, validate_profile
    from scripts.research_foundation_host import _absent, _cleanup, _new_name, native_probe, NATIVE_FIELDS
    from scripts.research_image_closure import inspect_closure
except ModuleNotFoundError:
    from research_foundation import FoundationBlocked, digest, validate_profile
    from research_foundation_host import _absent, _cleanup, _new_name, native_probe, NATIVE_FIELDS
    from research_image_closure import inspect_closure


SENTINEL_PROGRAM = r'''
import hashlib,json,os,pathlib,sys
path=pathlib.Path('/sentinel/canary.bin')
if sys.argv[1]=='write':
 with path.open('xb') as output:output.write(os.urandom(48));output.flush();os.fsync(output.fileno())
 path.chmod(0o600)
elif sys.argv[1]!='read':raise SystemExit('Fixed mode required')
raw=path.read_bytes()
print(json.dumps({'schema':'ai4r-operations-sentinel:1','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},sort_keys=True))
'''


def volume(host, name, *, required=True):
    call = host.run(['volume', 'inspect', name], check=False)
    if call.returncode:
        if not required and b'no such volume' in call.stderr.lower(): return None
        raise FoundationBlocked('EXACT_SENTINEL_VOLUME_UNAVAILABLE')
    rows = json.loads(call.stdout)
    if len(rows) != 1 or rows[0].get('Name') != name:
        raise FoundationBlocked('AMBIGUOUS_SENTINEL_VOLUME')
    return {key: rows[0].get(key) for key in ('Name', 'Driver', 'Scope', 'Labels', 'CreatedAt')}


def sentinel_control(host, profile, name, mode, ordinal):
    if mode not in {'write', 'read'}: raise FoundationBlocked('FIXED_SENTINEL_OPERATION_REQUIRED')
    container = 'ai4r-operations-sentinel-' + digest((name + mode + str(ordinal)).encode())[:24]
    if not _absent(host.run(['container', 'inspect', container], check=False)):
        raise FoundationBlocked('FRESH_SENTINEL_CONTROL_REQUIRED')
    record = {'name': container, 'kind': 'container', 'disposable': True, 'mode': mode, 'qualified': False}
    args = ['run', '--rm', '--name', container, '--label', 'ai4r.foundation-probe=' + profile['job_id'],
        '--label', 'ai4r.owner=' + profile['job_id'], '--label', 'com.docker.compose.project=' + profile['project'],
        '--network', 'none', '--read-only', '--user', '0:0', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
        '--memory', '64m', '--pids-limit', '16', '--mount', 'type=volume,src=' + name + ',dst=/sentinel' + (',readonly' if mode == 'read' else ''),
        '--entrypoint', '/usr/local/bin/python3', profile['image_id'], '-I', '-S', '-c', SENTINEL_PROGRAM, mode]
    try:
        call = host.run(args, timeout=30, check=False)
        value = json.loads(call.stdout)
        valid = (call.returncode == 0 and value.get('schema') == 'ai4r-operations-sentinel:1'
                 and value.get('bytes') == 48 and re.fullmatch('[a-f0-9]{64}', value.get('sha256', '')))
        record.update(qualified=bool(valid), observation=value, stdout_sha256=digest(call.stdout), stderr_sha256=digest(call.stderr))
    except Exception as error:
        record['error'] = type(error).__name__
    finally:
        record['cleanup'] = _cleanup(host, container, profile['job_id'])
        record['qualified'] = record['qualified'] and record['cleanup']['confirmed']
    return record


def write_new(path, value):
    with Path(path).open('xb') as stream:
        stream.write(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())
        stream.flush(); os.fsync(stream.fileno())


def verify_export(value):
    raw = base64.b64decode(value['data_b64'], validate=True)
    if len(raw) != value['bytes'] or digest(raw) != value['sha256'] or value.get('private_values_absent') is not True:
        raise FoundationBlocked('OPERATIONS_EXPORT_IDENTITY')
    expected = {row['path']: row for row in value['files']}
    if len(expected) != 4 or len(expected) != len(value['files']) or 'native-observation.json' not in expected:
        raise FoundationBlocked('OPERATIONS_EXPORT_POPULATION')
    for name in expected:
        if (PurePosixPath(name).as_posix() != name or '\\' in name or '..' in PurePosixPath(name).parts
                or (name != 'native-observation.json' and not re.fullmatch(r'service-logs/[a-f0-9]{32}-(agentserver|gateway|frontend)\.log', name))):
            raise FoundationBlocked('OPERATIONS_EXPORT_PATH')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if (len(members) != len(expected) or {member.filename for member in members} != set(expected)
                or archive.comment or min(member.header_offset for member in members) != 0 or raw[-22:-18] != b'PK\x05\x06'):
            raise FoundationBlocked('OPERATIONS_EXPORT_INVENTORY')
        for member in members:
            payload = archive.read(member)
            row = expected[member.filename]
            if (not stat.S_ISREG(member.external_attr >> 16) or member.is_dir() or member.flag_bits & 1
                    or len(payload) != row['bytes'] or digest(payload) != row['sha256']):
                raise FoundationBlocked('OPERATIONS_EXPORT_MEMBER_IDENTITY')
    return raw


def operations_probe(host, profile, source_build_pin, output):
    validate_profile(profile)
    output = Path(output) / 'operations'; output.mkdir(exist_ok=False)
    suffix = digest((profile['job_id'] + profile['image_id']).encode())[:24]
    scoped = {**profile, 'job_id': 'ai4r-operations-' + suffix, 'project': 'ai4r-verify-operations-' + suffix}
    record = {'schema': 'ai4r-foundation-operations:1', 'qualified': False, 'observations': {},
              'job_id': scoped['job_id'], 'project': scoped['project'], 'operator_target_touched': False,
              'resources': [], 'controls': [], 'retained_fixture_resources': []}
    try:
        sentinel = 'ai4r-foundation-sentinel-' + suffix
        native_name = _new_name(scoped, 'native')
        closure_name = 'ai4r-foundation-closure-' + digest((scoped['job_id'] + scoped['image_id']).encode())[:24]
        controls = [(mode, ordinal, 'ai4r-operations-sentinel-' + digest((sentinel + mode + str(ordinal)).encode())[:24])
                    for mode, ordinal in [('write', 0), ('read', 1), ('read', 2)]]
        ledger = {'job_id': scoped['job_id'], 'project': scoped['project'], 'resources': [
            {'kind': 'container', 'id': name, 'disposable': True} for name in [closure_name, native_name, *[row[2] for row in controls]]]}
        write_new(output / 'resource-ledger.json', ledger)
        record['resource_ledger_sha256'] = digest((output / 'resource-ledger.json').read_bytes())
        record['resources'] = [{**item, 'removed': False} for item in ledger['resources']]
        def removed(name, value):
            matches = [item for item in record['resources'] if item['id'] == name]
            if len(matches) != 1: raise FoundationBlocked('UNRECORDED_RESOURCE_EFFECT')
            matches[0]['removed'] = value is True
        closure_output = output / 'build-closure'; closure_output.mkdir()
        build = inspect_closure(host, scoped, source_build_pin, closure_output)
        removed(closure_name, build['cleanup']['confirmed'])
        (output / 'build-stage.json').write_text(json.dumps(build, sort_keys=True), encoding='utf8')
        if not build['qualified']:
            raise FoundationBlocked('ACTUAL_FROZEN_BUILD_STAGE_REQUIRED')
        record['build_stage'] = {'source_build_pin': source_build_pin, 'candidate_id': build['candidate_id'],
                                'image_id': build['image_id'], 'context_sha256': build['context_sha256'],
                                'reuse_basis': 'Exact original frozen build inputs, raw artifacts and independent installed closure were freshly reverified.'}
        if volume(host, sentinel, required=False): raise FoundationBlocked('FRESH_SENTINEL_VOLUME_REQUIRED')
        record['retained_fixture_resources'] = [{'kind': 'volume', 'name': sentinel, 'fixture_owner': scoped['job_id'],
            'creation_issued': True, 'reason': 'Unrelated sentinel is excluded from the disposable cleanup ledger; retained intentionally.'}]
        host.run(['volume', 'create', '--driver', 'local', '--label', 'ai4r.fixture-owner=' + scoped['job_id'],
                  '--label', 'ai4r.fixture-project=' + scoped['project'], sentinel])
        initial_volume = volume(host, sentinel)
        if initial_volume['Driver'] != 'local' or initial_volume['Labels'].get('ai4r.fixture-owner') != scoped['job_id']:
            raise FoundationBlocked('SENTINEL_CUSTODY_CHANGED')
        record['retained_fixture_resources'][0]['observed'] = initial_volume
        for mode, ordinal, name in controls[:2]:
            control = sentinel_control(host, scoped, sentinel, mode, ordinal); record['controls'].append(control)
            removed(name, control['cleanup']['confirmed'])
            if not control['qualified']: raise FoundationBlocked('SENTINEL_POSITIVE_CONTROL_FAILED')
        before = record['controls'][-1]['observation']
        native = native_probe(host, scoped)
        record['native'] = native
        if native['name'] != native_name: raise FoundationBlocked('UNRECORDED_NATIVE_RESOURCE')
        removed(native_name, native['cleanup']['confirmed'])
        export = native.get('observation', {}).get('public_export')
        raw = verify_export(export) if export else None
        if raw is not None:
            with (output / 'public-export.zip').open('xb') as stream: stream.write(raw)
        control = sentinel_control(host, scoped, sentinel, 'read', 2); record['controls'].append(control)
        removed(controls[2][2], control['cleanup']['confirmed'])
        after_volume = volume(host, sentinel)
        field_values = native.get('observation', {}).get('observations', {})
        passed = sorted(key for key in NATIVE_FIELDS if field_values.get(key) is True)
        record['native_test_population'] = {'required_ids': sorted(NATIVE_FIELDS), 'passed_ids': passed, 'expected': len(NATIVE_FIELDS), 'observed': len(field_values)}
        record['observations'] = {
            'lifecycle': bool(native['qualified'] and raw is not None and len(passed) == len(NATIVE_FIELDS)),
            'ledger': all(item['removed'] for item in record['resources']) and all(item['disposable'] for item in record['resources'])
                      and digest((output / 'resource-ledger.json').read_bytes()) == record['resource_ledger_sha256'],
            'sentinel': bool(control['qualified'] and before == control['observation'] and initial_volume == after_volume
                             and sentinel not in {item['id'] for item in record['resources']}),
            'evidence': raw is not None and (output / 'public-export.zip').read_bytes() == raw,
            'redaction': bool(raw is not None and native.get('observation', {}).get('redaction_fixture', {}).get('withheld') is True
                              and export['private_values_absent'] is True),
        }
        record['qualified'] = all(record['observations'].values())
    except Exception as error:
        record['error'] = str(error) if isinstance(error, FoundationBlocked) else type(error).__name__
    with (output / 'result.json').open('x', encoding='utf8') as stream: json.dump(record, stream, sort_keys=True)
    return record
