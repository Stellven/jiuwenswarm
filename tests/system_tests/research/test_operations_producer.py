"""Synthetic finite operations boundaries; no actual image/model acceptance."""
import ast
import base64
from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import zipfile

import pytest

from scripts import research_operations as operations
from scripts.research_foundation import HOST_KINDS, FoundationBlocked
from scripts.research_foundation_host import _new_name, NATIVE_FIELDS


def profile():
    return {'schema': 'ai4r-foundation-target:1', 'job_id': 'ai4r-operations-fixture', 'project': 'ai4r-target-fixture',
        'origin': 'http://127.0.0.1:15176', 'instance_id': 'a' * 32, 'build_id': 'b' * 64,
        'image_ref': 'ai4r-app:fixture', 'image_id': 'sha256:' + 'c' * 64, 'candidate_id': 'd' * 64,
        'platform': 'linux/amd64', 'mode': 'blocked_development', 'check_ids': ['M1-001/V15'],
        'fixture_manifest': {'path': 'unused', 'sha256': 'e' * 64}, 'assertion_manifest': {'path': 'unused', 'sha256': 'e' * 64},
        'host_receipts': {key: {'path': 'unused', 'sha256': 'e' * 64} for key in HOST_KINDS},
        'auth': {'token_file': None, 'bootstrap_challenge_file': None}}


def export_function():
    path = Path(operations.__file__).with_name('research_foundation_native_probe.py')
    function = next(node for node in ast.parse(path.read_text(encoding='utf8')).body if isinstance(node, ast.FunctionDef) and node.name == 'public_export')
    namespace = {'base64': base64, 'json': json, 'io': io, 'zipfile': zipfile, 'Path': Path, 'digest': operations.digest}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<fixed public exporter>', 'exec'), namespace)
    return namespace['public_export']


def observation():
    logs = []
    for role in ('agentserver', 'gateway', 'frontend'):
        raw = (role + ' safe raw fixture\n').encode()
        logs.append({'name': 'a' * 32 + '-' + role + '.log', 'bytes': len(raw), 'sha256': operations.digest(raw),
                     'raw_retained': True, 'data_b64': base64.b64encode(raw).decode()})
    return {'schema': 'ai4r-foundation-native-probe:1', 'observations': {key: True for key in NATIVE_FIELDS},
            'errors': [], 'logs': logs, 'redaction_fixture': {'withheld': True}}


def test_real_export_function_retains_exact_safe_raw_logs_and_rejects_private_marker():
    make = export_function(); value = observation()
    exported = make(value, [b'private-marker-fixture'])
    raw = operations.verify_export(exported)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert len(archive.infolist()) == 4
        assert archive.read('service-logs/' + value['logs'][0]['name']) == base64.b64decode(value['logs'][0]['data_b64'])
    value['unsafe_diagnostic'] = 'private-marker-fixture'
    with pytest.raises(ValueError, match='Private value'):
        make(value, [b'private-marker-fixture'])


@pytest.mark.parametrize('change', ['hash', 'inventory', 'private_flag', 'suffix', 'path'])
def test_export_tamper_never_becomes_retained_public_evidence(change):
    value = export_function()(observation(), [])
    if change == 'hash': value['sha256'] = 'a' * 64
    elif change == 'inventory': value['files'].pop()
    elif change == 'private_flag': value['private_values_absent'] = False
    elif change == 'suffix':
        raw = base64.b64decode(value['data_b64']) + b'undeclared suffix'
        value.update(data_b64=base64.b64encode(raw).decode(), bytes=len(raw), sha256=operations.digest(raw))
    else: value['files'][0]['path'] = '../escape'
    with pytest.raises((FoundationBlocked, ValueError)):
        operations.verify_export(value)


class Host:
    def __init__(self, root):
        self.root, self.commands, self.volumes, self.reads = root, [], {}, 0
        self.drift, self.foreign = False, False
    def run(self, args, **kwargs):
        self.commands.append(args)
        code, stdout, stderr = 0, b'', b''
        if args[:2] == ['volume', 'inspect']:
            row = self.volumes.get(args[2]); code = 0 if row else 1
            stdout, stderr = (json.dumps([row]).encode(), b'') if row else (b'', b'Error: no such volume')
        elif args[:2] == ['volume', 'create']:
            labels = dict(args[index + 1].split('=', 1) for index, value in enumerate(args) if value == '--label')
            self.volumes[args[-1]] = {'Name': args[-1], 'Driver': 'local', 'Scope': 'local', 'Labels': labels, 'CreatedAt': 'fixture'}
            stdout = args[-1].encode()
        elif args[:2] == ['container', 'inspect']:
            code, stderr = 1, b'Error: No such object: fixture'
        elif args[0] == 'run':
            mode = args[-1]
            if mode == 'read': self.reads += 1
            changed = self.drift and self.reads > 1
            stdout = json.dumps({'schema': 'ai4r-operations-sentinel:1', 'bytes': 48, 'sha256': ('b' if changed else 'a') * 64}).encode()
        else: raise AssertionError(args)
        return subprocess.CompletedProcess(args, code, stdout, stderr)


def setup_producers(monkeypatch, *, blocked_build=False, bad_native=False):
    def closure(host, scoped, pin, output):
        ledger_path = output.parent / 'resource-ledger.json'
        assert ledger_path.exists(), 'The exact cleanup ledger must precede any probe effect'
        return {'qualified': not blocked_build, 'candidate_id': scoped['candidate_id'], 'image_id': scoped['image_id'],
            'context_sha256': 'e' * 64, 'cleanup': {'confirmed': True}}
    def native(host, scoped):
        # Explicit synthetic fixture. Actual production always invokes Docker.
        value = observation(); value['public_export'] = export_function()(value, [])
        return {'name': _new_name(scoped, 'native'), 'qualified': not bad_native,
                'observation': value, 'cleanup': {'confirmed': True}}
    monkeypatch.setattr(operations, 'inspect_closure', closure)
    monkeypatch.setattr(operations, 'native_probe', native)


def test_operations_declares_resources_before_effect_and_retains_unrelated_volume_and_evidence(tmp_path, monkeypatch):
    setup_producers(monkeypatch)
    host = Host(tmp_path)
    result = operations.operations_probe(host, profile(), {'path': 'receipt.json', 'sha256': 'f' * 64}, tmp_path)
    assert result['qualified'] and all(result['observations'].values())
    assert result['operator_target_touched'] is False
    assert all(item['removed'] for item in result['resources']) and len(result['resources']) == 5
    retained = result['retained_fixture_resources'][0]
    assert retained['name'] in host.volumes
    assert retained['name'] not in {item['id'] for item in result['resources']}
    assert not any(command[:2] == ['volume', 'rm'] for command in host.commands)
    assert (tmp_path / 'operations/public-export.zip').is_file()


@pytest.mark.parametrize('failure', ['build', 'native', 'sentinel'])
def test_failed_actual_stage_or_changed_sentinel_cannot_qualify_operations(tmp_path, monkeypatch, failure):
    setup_producers(monkeypatch, blocked_build=failure == 'build', bad_native=failure == 'native')
    host = Host(tmp_path); host.drift = failure == 'sentinel'
    result = operations.operations_probe(host, profile(), {'path': 'receipt.json', 'sha256': 'f' * 64}, tmp_path)
    assert result['qualified'] is False
    if failure == 'build': assert host.commands == []
    if failure == 'sentinel': assert result['observations']['sentinel'] is False
