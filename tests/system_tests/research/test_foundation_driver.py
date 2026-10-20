"""Synthetic controller-boundary tests; never actual product V evidence."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from scripts.research_foundation import (CHECKS, HOST_KINDS, JOIN_KEYS, FoundationBlocked, Target,
    digest, json_bytes, manifests, read_regular, validate_profile)
from scripts.research_system import fresh_observations, junit_result, native_context, validate_candidate
from scripts.research_candidate import capture_candidate


def profile():
    return {'schema': 'ai4r-foundation-target:1', 'job_id': 'ai4r-job-test', 'project': 'ai4r-target-test',
        'origin': 'http://127.0.0.1:15176', 'instance_id': 'fixture-boot', 'build_id': 'fixture-build',
        'image_ref': 'ai4r-m1-app:fixture', 'image_id': 'sha256:' + 'a' * 64, 'candidate_id': 'b' * 64,
        'platform': 'linux/amd64', 'mode': 'blocked_development', 'check_ids': ['M1-006/V05'],
        'fixture_manifest': {'path': 'not-read.json', 'sha256': 'c' * 64},
        'assertion_manifest': {'path': 'not-read.json', 'sha256': 'c' * 64},
        'host_receipts': {kind: {'path': 'not-read.json', 'sha256': 'c' * 64} for kind in HOST_KINDS},
        'auth': {'token_file': None, 'bootstrap_challenge_file': None}}


def publish(tmp_path, value, name):
    path = tmp_path / name
    raw = json_bytes(value)
    path.write_bytes(raw)
    return {'path': str(path), 'sha256': digest(raw)}


def bound(tmp_path):
    value = profile()
    fixture, assertion = manifests('M1-006/V05', 'd' * 64, 'e' * 64)
    value['fixture_manifest'] = publish(tmp_path, fixture, 'fixture.json')
    value['assertion_manifest'] = publish(tmp_path, assertion, 'assertion.json')
    for kind in HOST_KINDS:
        record = {'schema': 'ai4r-foundation-host-receipt:1', 'kind': kind, **{k: value[k] for k in JOIN_KEYS},
                  'observed_at': '2026-10-16T00:00:00Z', 'qualified': False, 'observations': {}, 'limitations': ['Synthetic input.']}
        value['host_receipts'][kind] = publish(tmp_path, record, kind + '.json')
    return value


def test_profile_has_closed_execution_scope():
    value = profile()
    assert validate_profile(value) is value
    mutations = [('origin', 'http://0.0.0.0:5173'), ('origin', 'https://example.com:443'), ('origin', 'http://127.0.0.1:5173/?token=x'),
                 ('project', '--all'), ('mode', 'trust_me'), ('image_id', 'tag:latest'), ('check_ids', ['arbitrary::test'])]
    for key, replacement in mutations:
        changed = deepcopy(value); changed[key] = replacement
        with pytest.raises(FoundationBlocked):
            validate_profile(changed)
    changed = deepcopy(value); changed['commands'] = ['sh', '-c', 'ignored']
    with pytest.raises(FoundationBlocked):
        validate_profile(changed)


def test_source_population_cannot_shrink_or_swap(tmp_path):
    value = bound(tmp_path)
    target = Target(value)
    assert len(target.assertions['required_assertion_ids']) == 8
    assertion = deepcopy(target.assertions)
    assertion['required_assertion_ids'] = assertion['required_assertion_ids'][:1]
    value['assertion_manifest'] = publish(tmp_path, assertion, 'changed-assertion.json')
    with pytest.raises(FoundationBlocked, match='POPULATION'):
        Target(value)


def test_host_join_and_bytes_are_required(tmp_path):
    value = bound(tmp_path)
    path = Path(value['host_receipts']['image']['path'])
    raw = path.read_bytes()
    path.write_bytes(raw + b' ')
    with pytest.raises(FoundationBlocked, match='PIN_CHANGED'):
        Target(value)
    record = json.loads(raw); record['candidate_id'] = 'f' * 64
    value['host_receipts']['image'] = publish(tmp_path, record, 'image-other.json')
    with pytest.raises(FoundationBlocked, match='HOST_JOIN'):
        Target(value)


def test_missing_failed_duplicate_or_unknown_assertion_cannot_pass(tmp_path):
    value = bound(tmp_path)
    target = Target(value)
    first = target.assertions['required_assertion_ids'][0]
    target.require(first, True)
    with pytest.raises(FoundationBlocked, match='DUPLICATE'):
        target.require(first, True)
    with pytest.raises(FoundationBlocked):
        target.require('foreign', True)
    with pytest.raises(AssertionError):
        target.finish()
    target = Target(value)
    for key in target.assertions['required_assertion_ids']:
        target.require(key, key != first)
    with pytest.raises(AssertionError, match=first):
        target.finish()


def test_secret_and_symlink_custody(tmp_path):
    secret = tmp_path / 'token'; secret.write_text('public-test-fixture-not-an-operational-token')
    if os.name != 'nt':
        secret.chmod(0o644)
        with pytest.raises(FoundationBlocked, match='SECRET_CUSTODY'):
            read_regular(secret, private=True)
        secret.chmod(0o600)
        assert read_regular(secret, private=True).startswith(b'public-test')
        link = tmp_path / 'link'; link.symlink_to(secret)
        with pytest.raises(FoundationBlocked, match='ALIAS'):
            read_regular(link)


def test_asset_observation_has_separate_bounded_response_policy(tmp_path):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    payload = b'x' * (5 * 1024 * 1024)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.send_header('content-type', 'application/javascript'); self.end_headers()
            self.wfile.write(payload)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        value = bound(tmp_path)
        value['origin'] = 'http://127.0.0.1:' + str(server.server_port)
        for kind, pin in value['host_receipts'].items():
            record = json.loads(Path(pin['path']).read_bytes()); record['origin'] = value['origin']
            value['host_receipts'][kind] = publish(tmp_path, record, kind + '-origin.json')
        target = Target(value)
        with pytest.raises(FoundationBlocked, match='RESPONSE_LIMIT'):
            target.request('/assets/index.js')
        status, value, raw = target.request('/assets/index.js', maximum_response=16 * 1024 * 1024)
        assert status == 200 and value is None and raw == payload
        assert 'x' * 100 not in json.dumps(target.http)
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_junit_requires_actual_nonempty_unique_nonskipped_cases():
    valid = b'<testsuite tests="1"><testcase classname="m" name="t"/></testsuite>'
    assert junit_result(valid, ['m::t'])
    for raw in [b'<testsuite tests="0"/>', b'<testsuite><testcase classname="m" name="t"><skipped/></testcase></testsuite>',
                b'<testsuite><testcase classname="m" name="t"/><testcase classname="m" name="t"/></testsuite>', b'bad xml']:
        assert not junit_result(raw, ['m::t'])
    assert not junit_result(valid, ['m::other'])


def test_narrow_diagnostic_candidate_cannot_qualify_product(tmp_path):
    (tmp_path / 'p.py').write_text('print("public fixture")\n')
    candidate = capture_candidate(tmp_path, paths=['p.py'])
    value = profile(); value['candidate_id'] = candidate['candidate_id']
    validate_candidate(tmp_path, candidate, value)
    value['mode'] = 'qualified_foundation'
    with pytest.raises(FoundationBlocked, match='FULL_PRODUCT'):
        validate_candidate(tmp_path, candidate, value)
    value['mode'] = 'blocked_development'
    candidate['candidate_id'] = value['candidate_id'] = 'e' * 64
    with pytest.raises(FoundationBlocked, match='CURRENT_TARGET'):
        validate_candidate(tmp_path, candidate, value)


class FakeDocker:
    """Tests only the finite observation adapter, not real Docker acceptance."""
    def __init__(self):
        self.profile = profile()
        self.inspect = {'Image': self.profile['image_id'], 'State': {'Running': True}, 'Mounts': [],
            'Config': {'Image': self.profile['image_ref'], 'Labels': {'com.docker.compose.project': self.profile['project'], 'com.docker.compose.service': 'app'}},
            'NetworkSettings': {'Ports': {'5173/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '15176'}]}}}
    def json(self, args):
        if args[:2] == ['context', 'inspect']:
            return [{'Endpoints': {'docker': {'Host': 'unix:///var/run/docker.sock'}}}]
        if args[:2] == ['image', 'inspect']:
            return [{'Os': 'linux', 'Architecture': 'amd64'}]
        return [self.inspect]
    def run(self, args, **kwargs):
        from types import SimpleNamespace
        if args[0] == 'ps':
            return SimpleNamespace(stdout=b'abcdef123456\n', returncode=0)
        if '/bin/cat' in args:
            return SimpleNamespace(stdout=json_bytes({'boot_id': self.profile['instance_id']}), returncode=0)
        if '/opt/venv/bin/python' in args:
            return SimpleNamespace(stdout=self.profile['build_id'].encode() + b'\n', returncode=0)
        return SimpleNamespace(stdout=json_bytes({'running': True, 'panes': [
            {'role': role, 'pane': '%' + str(i), 'running': True} for i, role in enumerate(('agentserver', 'gateway', 'frontend'))]}), returncode=0)


def test_fresh_observations_do_not_certify_unperformed_effects():
    host = FakeDocker()
    records, _ = fresh_observations(host, host.profile)
    assert records['ports']['observations']['approved_private_only'] is True
    assert records['tmux']['observations']['fixed_owned_panes'] is True
    for kind in ('operations', 'native_platform', 'child_checks', 'channels'):
        assert records[kind]['qualified'] is False
    assert records['image']['observations']['same_candidate_closure'] is False
    assert records['tmux']['observations']['attach_detach_preserves'] is False
    host.inspect['NetworkSettings']['Ports']['18092/tcp'] = [{'HostIp': '0.0.0.0', 'HostPort': '18092'}]
    records, _ = fresh_observations(host, host.profile)
    assert records['ports']['observations']['approved_private_only'] is False
    host.inspect['Config']['Labels']['com.docker.compose.project'] = 'foreign'
    with pytest.raises(FoundationBlocked, match='OWNERSHIP'):
        fresh_observations(host, host.profile)


def test_every_fixed_selector_exists_and_current_native_source_is_bound():
    root = Path(__file__).parents[3]
    for check_id, (selector, _) in CHECKS.items():
        file, function = selector.split('::')
        assert 'def ' + function + '(' in (root / file).read_text(encoding='utf8')
        check, source_sha, interfaces, pins = native_context(root, check_id)
        assert check['id'] == check_id and len(source_sha) == 64
        assert interfaces['M1-IF-002'] == 'r2' and pins
