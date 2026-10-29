"""Synthetic finite-host-procedure boundaries; not source V acceptance."""
from copy import deepcopy
import ast
import base64
import json
from pathlib import Path
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scripts import research_foundation_host as probes
from scripts.research_foundation import HOST_KINDS, FoundationBlocked


def profile():
    return {'schema': 'ai4r-foundation-target:1', 'job_id': 'ai4r-job-unit', 'project': 'ai4r-target-unit',
        'origin': 'http://127.0.0.1:15176', 'instance_id': 'a' * 32, 'build_id': 'b' * 64,
        'image_ref': 'ai4r-app:unit', 'image_id': 'sha256:' + 'c' * 64, 'candidate_id': 'd' * 64,
        'platform': 'linux/amd64', 'mode': 'blocked_development', 'check_ids': ['M1-001/V09'],
        'fixture_manifest': {'path': 'not-read', 'sha256': 'e' * 64},
        'assertion_manifest': {'path': 'not-read', 'sha256': 'e' * 64},
        'host_receipts': {key: {'path': 'not-read', 'sha256': 'e' * 64} for key in HOST_KINDS},
        'auth': {'token_file': None, 'bootstrap_challenge_file': None}}


class Host:
    def __init__(self, root):
        self.root, self.commands = root, []
        self.present, self.foreign, self.timeout, self.bad_case, self.conflict = False, False, False, False, True
        value = profile()
        self.target = {'Id': 'a' * 64, 'Image': value['image_id'], 'State': {'Running': True},
            'Config': {'Labels': {'com.docker.compose.project': value['project']}},
            'NetworkSettings': {'Ports': {'5173/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '15176'}]}}}

    def run(self, args, **kwargs):
        self.commands.append(args)
        code, stdout, stderr = 0, b'', b''
        if args[:2] == ['container', 'inspect']:
            if self.present:
                owner = 'foreign' if self.foreign else profile()['job_id']
                stdout = json.dumps([{'Config': {'Labels': {'ai4r.foundation-probe': owner}}}]).encode()
            else: code, stderr = 1, b'Error: No such object: ' + args[-1].encode()
        elif args[:3] == ['container', 'rm', '--force']: self.present = False
        elif args[0] == 'run':
            self.present = True
            if self.timeout: raise FoundationBlocked('LOCAL_DOCKER_UNAVAILABLE_OR_TIMEOUT')
            if '--publish' in args:
                code, stderr = 125, b'Bind for 127.0.0.1:15176 failed: port is already allocated' if self.conflict else b'network pool exhausted'
            else:
                mode = args[-1]
                rows = ([{'id': item, 'inspection_only': not self.bad_case, 'sdk': 'codex_subscription'}
                         for item in ('missing', 'invalid_yaml', 'closed_schema')] if mode == 'configuration' else
                        [{'id': 'readable_fixture_mount', 'denied': not self.bad_case, 'code': 'HIDDEN_CUSTODY_MOUNT_PRESENT'}])
                value = {'schema': 'ai4r-foundation-probe-observation:1', 'mode': mode, 'uid': 0, 'cases': rows}
                stdout = b'noisy native log\n' + probes.PREFIX + json.dumps(value).encode() + b'\n'
                self.present = False
        elif args[0] == 'exec': stdout = b'Usage: installed native control\n'
        else: raise AssertionError(args)
        return subprocess.CompletedProcess(args, code, stdout, stderr)

    def json(self, args):
        self.commands.append(args)
        assert args == ['container', 'inspect', self.target['Id']]
        return [deepcopy(self.target)]


@pytest.mark.parametrize('mode', ['configuration', 'custody'])
def test_fixed_probe_uses_same_image_no_credentials_no_host_mount_and_exact_expected_cases(tmp_path, mode):
    host = Host(tmp_path)
    value = probes.configuration_probe(host, profile(), mode)
    assert value['qualified'] and value['cleanup']['confirmed'] and value['target_touched'] is False
    command = next(command for command in host.commands if command[0] == 'run')
    assert command[command.index('--network') + 1] == 'none'
    assert profile()['image_id'] in command and command[-2:] == [probes.CONFIGURATION_PROBE, mode]
    assert '--volume' not in command and '--mount' not in command and '--privileged' not in command
    assert 'SYS_ADMIN' not in command
    assert ('/hidden-fixtures:rw,nosuid,nodev,size=1m,mode=0755' in command) is (mode == 'custody')


@pytest.mark.parametrize('failure', ['bad_case', 'timeout', 'foreign'])
def test_missing_failed_or_unclean_probe_stays_unqualified(tmp_path, failure):
    host = Host(tmp_path); setattr(host, failure, True)
    if failure == 'foreign': host.timeout = True
    value = probes.configuration_probe(host, profile(), 'configuration')
    assert value['qualified'] is False
    if failure == 'foreign':
        assert value['cleanup']['error'] == 'PROBE_CLEANUP_OWNERSHIP_MISMATCH'
        assert not any(command[:2] == ['container', 'rm'] for command in host.commands)


def test_finite_probe_rejects_mode_and_profile_before_docker(tmp_path):
    host = Host(tmp_path)
    with pytest.raises(FoundationBlocked): probes.configuration_probe(host, profile(), 'arbitrary')
    invalid = profile(); invalid['image_id'] = '--privileged'
    with pytest.raises(FoundationBlocked): probes.configuration_probe(host, invalid, 'configuration')
    assert host.commands == []


def test_installed_surface_help_checks_case_insensitively_without_starting_session(tmp_path, monkeypatch):
    monkeypatch.setattr(probes, 'public_ui', lambda _: {'built_ui': True, 'fixture': True})
    host = Host(tmp_path)
    value = probes.installed_surfaces(host, profile(), host.target['Id'])
    assert value['qualified'] and {item['surface'] for item in value['observations']} == {'cli', 'tui'}
    commands = [command for command in host.commands if command[0] == 'exec']
    assert len(commands) == 2 and all(command[-1] == '--help' for command in commands)
    assert all(command[1:3] == ['--user', '10001:10001'] for command in commands)


def test_real_port_conflict_classification_preserves_target_and_only_cleans_own_probe(tmp_path):
    host = Host(tmp_path)
    value = probes.port_conflict_probe(host, profile(), host.target['Id'])
    assert value['qualified'] and value['original_target_unchanged'] and value['cleanup']['confirmed']
    command = next(command for command in host.commands if command[0] == 'run')
    assert command[command.index('--publish') + 1] == '127.0.0.1:15176:5173'
    assert command[-3:] == ['--entrypoint', '/bin/true', profile()['image_id']]
    assert host.target['State']['Running']


def test_unrelated_docker_failure_or_wrong_target_port_is_not_conflict_proof(tmp_path):
    host = Host(tmp_path); host.conflict = False
    assert probes.port_conflict_probe(host, profile(), host.target['Id'])['qualified'] is False
    host = Host(tmp_path); host.target['NetworkSettings']['Ports']['5173/tcp'][0]['HostPort'] = 'other'
    value = probes.port_conflict_probe(host, profile(), host.target['Id'])
    assert value['qualified'] is False and value['error'] == 'EXACT_PRIVATE_TARGET_PORT_REQUIRED'
    assert not any(command[0] == 'run' for command in host.commands)


@pytest.mark.parametrize('incomplete', [False, True])
def test_native_probe_is_fixed_instrumented_and_requires_every_observed_field(tmp_path, incomplete):
    class NativeHost(Host):
        def run(self, args, **kwargs):
            if args[0] == 'run':
                self.commands.append(args)
                assert args[args.index('--env') + 1] == 'AI4R_FOUNDATION_NATIVE_PROBE=1'
                assert args[-3:-1] == ['-I', '-c']
                compile(args[-1], '<frozen native probe>', 'exec')
                fields = {key: True for key in probes.NATIVE_FIELDS}
                if incomplete: fields['zero_external_constructors'] = False
                value = {'schema': 'ai4r-foundation-native-probe:1', 'instrumented': True,
                         'credential_mounted': False, 'observations': fields, 'errors': []}
                return subprocess.CompletedProcess(args, 0, probes.PREFIX + json.dumps(value).encode() + b'\n', b'')
            return super().run(args, **kwargs)
    host = NativeHost(tmp_path)
    value = probes.native_probe(host, profile())
    assert value['qualified'] is (not incomplete) and value['cleanup']['confirmed']
    assert value['program_sha256'] and value['target_touched'] is False
    command = next(item for item in host.commands if item[0] == 'run')
    assert '--mount' not in command and '--volume' not in command and '--privileged' not in command


def test_native_process_absence_proof_refuses_shell_unknown_python_and_installer_forms():
    source = Path(probes.__file__).with_name('research_foundation_native_probe.py').read_text(encoding='utf8')
    tree = ast.parse(source)
    hook = next(node.value.value for node in tree.body if isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == 'TRACE_HOOK' for target in node.targets))
    function = next(node for node in ast.parse(hook).body if isinstance(node, ast.FunctionDef) and node.name == '_approved_process')
    namespace = {'re': re}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<fixed process classifier>', 'exec'), namespace)
    approved = namespace['_approved_process']
    assert approved('python', ['/opt/venv/bin/python', '-m', 'jiuwenswarm.research.executor_rpc'])
    assert not approved('python', ['/opt/venv/bin/python', '-c', "__import__('pip')"])
    assert not approved('python', ['/opt/venv/bin/python', '-m', 'pip', 'install', 'package'])
    assert not approved('sh', ['/bin/sh', '-c', 'npm install'])
    assert not approved('uv', ['uv', 'sync'])
    socket = '/run/ai4r/tmux-' + 'a' * 32 + '.sock'
    command = '/usr/bin/tmux -S ' + socket + ' wait-for ' + 'a' * 32 + '-frontend; exec /opt/venv/bin/python -m jiuwenswarm.research.native_entry frontend'
    assert approved('tmux', ['tmux', '-S', socket, 'new-session', '-d', command])
    assert not approved('tmux', ['tmux', '-S', socket, 'new-session', '-d', 'npm install; ' + command])
    assert not approved('tmux', ['tmux', '-S', socket, 'run-shell', 'npm install'])
    assert not approved('tmux', ['tmux', '-S', '/tmp/foreign.sock', 'list-panes'])


def test_installed_ui_probe_reads_only_approved_origin_and_refuses_redirects():
    class Handler(BaseHTTPRequestHandler):
        redirect = False
        def do_GET(self):
            if self.redirect:
                self.send_response(302); self.send_header('Location', 'http://192.0.2.1:1/'); self.end_headers()
            else:
                self.send_response(200); self.end_headers(); self.wfile.write(b'<html><script src="/assets/native.js"></script></html>')
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    try:
        p = profile(); p['origin'] = 'http://127.0.0.1:' + str(server.server_port)
        assert probes.public_ui(p)['built_ui'] is True
        Handler.redirect = True
        assert probes.public_ui(p)['built_ui'] is False
    finally:
        server.shutdown(); server.server_close(); worker.join(timeout=2)


def test_observed_subsets_are_consumable_without_promoting_a_dead_target_pane(tmp_path, monkeypatch):
    value = {'qualified': True, 'cleanup': {'confirmed': True}, 'returncode': 0,
             'observation': {'errors': [], 'observations': {name: True for name in probes.NATIVE_FIELDS}}}
    monkeypatch.setattr(probes, 'native_probe', lambda *_: value)
    receipts = {kind: {'qualified': False, 'observations': {}} for kind in HOST_KINDS}
    receipts['tmux']['observations']['fixed_owned_panes'] = False
    result = probes.enrich_observations(None, profile(), 'M1-006/V28', receipts, 'a' * 64, tmp_path)
    assert result['tmux']['qualified'] is True and result['tmux']['observations']['attach_detach_preserves'] is True
    assert result['tmux']['observations']['fixed_owned_panes'] is False


def test_raw_native_log_retention_preserves_original_bytes_and_withholds_private_marker(tmp_path):
    source = Path(probes.__file__).with_name('research_foundation_native_probe.py').read_text(encoding='utf8')
    function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == 'retain_service_logs')
    namespace = {'base64': base64, 'digest': probes.digest}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<fixed service-log retention>', 'exec'), namespace)
    safe = tmp_path / 'safe.log'; private = tmp_path / 'private.log'
    safe.write_bytes(b'actual safe fault bytes\n'); private.write_bytes(b'public-prefix private-marker-fixture suffix\n')
    rows = namespace['retain_service_logs']([safe, private], [b'private-marker-fixture', b''])
    assert rows[0]['raw_retained'] is True and base64.b64decode(rows[0]['data_b64']) == safe.read_bytes()
    assert rows[0]['sha256'] == probes.digest(safe.read_bytes())
    assert rows[1]['raw_retained'] is False and 'data_b64' not in rows[1]
    assert rows[1]['reason'] == 'private_value_requires_separate_protected_capture'
