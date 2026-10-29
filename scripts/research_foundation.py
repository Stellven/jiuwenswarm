"""Closed controller bindings for the source-owned foundation procedures.

These observations are verification inputs, never product execution authority.
The host driver refreshes host observations; the controller has no Docker socket.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


HOST_KINDS = ('image', 'ports', 'startup', 'channels', 'tmux', 'operations', 'native_platform', 'child_checks')
JOIN_KEYS = ('job_id', 'project', 'origin', 'instance_id', 'build_id', 'image_ref', 'image_id', 'candidate_id', 'platform')
PROFILE_KEYS = {'schema', *JOIN_KEYS, 'mode', 'check_ids', 'fixture_manifest', 'assertion_manifest', 'host_receipts', 'auth'}
# Each name denotes a required source obligation, not merely one HTTP response.
# Missing observations are failed assertions, even in development mode.
CHECKS = {
    'M1-001/V08': ('tests/integration/research/test_deployment.py::test_multiarchitecture_build', {
        'multiarch.manifests': 'both linux/amd64 and linux/arm64 app manifests',
        'multiarch.locks': 'exact frozen dependency and source closure',
        'multiarch.native_separate': 'build and emulation do not imply native GB10 qualification'}),
    'M1-001/V09': ('tests/integration/research/test_deployment.py::test_startup_private_origin', {
        'startup.built_ui': 'installed native HTML and referenced assets are served',
        'startup.private_ports': 'only approved private 5173 endpoint is published',
        'startup.identity': 'readiness identifies actual installed build and boot',
        'startup.blocked_execution': 'unavailable prerequisites prohibit execution',
        'startup.config_negative': 'missing and invalid operator configuration prevent governed startup',
        'startup.fixture_custody': 'planted readable fixture storage prevents protected startup',
        'startup.optional_absence': 'sidecar, RSI, API router absence preserves fixed route',
        'auth.spoof_denied': 'unauthenticated and spoofed HTTP identity has zero authority',
        'auth.websocket': 'actual native cookie, Origin and Host boundary rejects unauthenticated and foreign clients',
        'auth.revoked': 'revocation closes HTTP and native WebSocket grants'}),
    'M1-001/V15': ('tests/integration/research/test_operations.py::test_owned_operations', {
        'operations.lifecycle': 'identified build/start/probe/test/export/cleanup all execute',
        'operations.ledger': 'only exact ledger-owned resources are removed',
        'operations.sentinel': 'unrelated sentinel resources survive',
        'operations.evidence': 'raw evidence survives cleanup',
        'operations.redaction': 'secret-marker fixture is absent from public exports'}),
    'M1-001/V16': ('tests/system_tests/research/test_foundation.py::test_foundation', {
        'system.identity': 'same candidate, installed build, image and instance across boundaries',
        'system.ready': 'actual UI/API/model/state/executor prerequisites ready',
        'system.child_checks': 'all required current native child SYSTEM receipts pass',
        'system.builder': 'dedicated Builder credential and real sandbox qualification',
        'system.platforms': 'amd64, arm64 emulated and physical GB10 observations remain independent',
        'system.retention': 'raw model/executor/state evidence survives display and restart'}),
    'M1-001/V17': ('tests/integration/research/test_native_startup.py::test_m1_channel_allowlist_or_owned_tmux', {
        'channels.constructed': 'every stale enabled external connector constructs zero clients',
        'channels.network': 'zero external listeners and connector outbound attempts',
        'channels.ordinary': 'ordinary non-M1 configuration behavior remains available',
        'channels.native': 'native web, CLI and installed TUI remain available',
        'tmux.owned': 'only instance-owned session and fixed panes exist',
        'tmux.detach': 'actual attach/detach preserves pane state and execution',
        'tmux.fault': 'owned service fault and logs remain inspectable without replay or grant'}),
    'M1-006/V05': ('tests/integration/research/test_native_startup.py::test_observed_readiness_and_security_prerequisites', {
        'readiness.source_projection': 'missing canonical pins return closed unavailable error; actual RunPins are never fabricated',
        'readiness.identity': 'actual instance and build are distinct from liveness',
        'readiness.prerequisites': 'all unavailable runtime prerequisites have explicit reasons',
        'readiness.no_execution': 'blocked readiness exposes no submission authority',
        'readiness.controlled_variants': 'actual storage/auth/model/isolation/device missing variants each fail closed',
        'readiness.optional_absence': 'sidecar and RSI absence is not a fixed-route startup dependency',
        'readiness.security_sentinel': 'readable harmless fixture-path sentinel blocks protected boot',
        'readiness.identity_mismatch': 'identity, contract and pin mismatch prevents client submission'}),
    'M1-006/V06': ('tests/integration/research/test_native_startup.py::test_native_endpoint_topology', {
        'topology.private': 'one approved private native origin exposes UI and control API',
        'topology.no_internal': 'no model, state, fixture or Docker port is published',
        'topology.auth': 'control API requires explicit bearer grant',
        'topology.built_assets': 'installed built assets and native internal proxy share the original origin',
        'topology.no_broad_home': 'Docker socket and broad host home are absent from all app mounts',
        'topology.no_runtime_install': 'normal native startup performs no dependency install or UI helper build',
        'topology.port_conflict': 'conflicting published port cannot silently move the product target'}),
    'M1-006/V28': ('tests/integration/research/test_terminal_boundary.py::test_owned_terminal_boundary', {
        'terminal.owned': 'terminal only controls the identified owned tmux session',
        'terminal.attach_detach': 'actual PTY attach/detach preserves running work',
        'terminal.fault': 'owned fault and logs remain inspectable',
        'terminal.authority': 'terminal interaction grants no core-store or unrelated OS authority'}),
    'M1-006/V29': ('tests/integration/research/test_native_channel_whitelist.py::test_native_channel_whitelist', {
        'whitelist.construction': 'all stale enabled legacy connectors construct zero clients',
        'whitelist.network': 'no external listener or connector outbound attempt',
        'whitelist.native': 'native web, CLI and TUI remain available',
        'whitelist.ordinary': 'non-M1 channel configuration remains unchanged'}),
}


class FoundationBlocked(ValueError):
    """A required real resource or closed binding is unavailable."""


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def read_regular(path, *, private=False, maximum=4 * 1024 * 1024):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise FoundationBlocked('CONTROLLER_FILE_ALIAS')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or meta.st_size > maximum:
            raise FoundationBlocked('CONTROLLER_FILE_CUSTODY')
        if private and os.name != 'nt' and (stat.S_IMODE(meta.st_mode) != 0o600 or meta.st_uid != os.geteuid()):
            raise FoundationBlocked('CONTROLLER_SECRET_CUSTODY')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            return stream.read(maximum + 1)
    finally:
        os.close(fd)


def read_pin(pin):
    if not isinstance(pin, dict) or set(pin) != {'path', 'sha256'}:
        raise FoundationBlocked('CONTROLLER_PIN_SHAPE')
    raw = read_regular(pin['path'])
    if digest(raw) != pin['sha256']:
        raise FoundationBlocked('CONTROLLER_PIN_CHANGED')
    return json.loads(raw)


def validate_profile(profile):
    if not isinstance(profile, dict) or set(profile) != PROFILE_KEYS or profile['schema'] != 'ai4r-foundation-target:1':
        raise FoundationBlocked('FOUNDATION_PROFILE_SHAPE')
    if profile['mode'] not in {'blocked_development', 'qualified_foundation'}:
        raise FoundationBlocked('FOUNDATION_MODE')
    for key in JOIN_KEYS:
        if not isinstance(profile[key], str) or not profile[key] or len(profile[key]) > 256:
            raise FoundationBlocked('FOUNDATION_IDENTITY')
    for key in ('project', 'job_id'):
        if not re.fullmatch(r'ai4r-[a-z0-9][a-z0-9-]{1,80}', profile[key]):
            raise FoundationBlocked('FOUNDATION_RESOURCE_SCOPE')
    parsed = urlsplit(profile['origin'])
    try:
        host = ipaddress.ip_address(parsed.hostname)
        if (parsed.scheme not in {'http', 'https'} or not host.is_private or host.is_unspecified
                or host.is_multicast or parsed.username or parsed.password or not parsed.port
                or parsed.path or parsed.query or parsed.fragment):
            raise ValueError
    except (ValueError, TypeError):
        raise FoundationBlocked('FOUNDATION_PRIVATE_ORIGIN') from None
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', profile['image_id']) or not re.fullmatch(r'[a-f0-9]{64}', profile['candidate_id']):
        raise FoundationBlocked('FOUNDATION_PIN_IDENTITY')
    if profile['platform'] not in {'linux/amd64', 'linux/arm64'}:
        raise FoundationBlocked('FOUNDATION_PLATFORM')
    checks = profile['check_ids']
    if not isinstance(checks, list) or not checks or len(set(checks)) != len(checks) or any(c not in CHECKS for c in checks):
        raise FoundationBlocked('FOUNDATION_CHECK_ALLOWLIST')
    if set(profile['host_receipts']) != set(HOST_KINDS):
        raise FoundationBlocked('FOUNDATION_HOST_RECEIPTS')
    if not isinstance(profile['auth'], dict) or set(profile['auth']) != {'token_file', 'bootstrap_challenge_file'}:
        raise FoundationBlocked('FOUNDATION_AUTH_SHAPE')
    return profile


def manifests(check_id, procedure_sha256, source_sha256):
    selector, assertions = CHECKS[check_id]
    module, name = selector.split('::')
    case_id = module.removesuffix('.py').replace('/', '.') + '::' + name
    fixture = {'schema': 'ai4r-foundation-fixtures:1', 'id': check_id + '/fixtures', 'check_id': check_id,
               'procedure_sha256': procedure_sha256, 'source_baseline_sha256': source_sha256,
               'cases': [{'id': key, 'source_requirement': value} for key, value in assertions.items()]}
    assertion = {'id': check_id + '/assertions', 'check_id': check_id, 'procedure_sha256': procedure_sha256,
                 'required_dependency_mode': 'real_system' if check_id == 'M1-001/V16' else 'real_boundary',
                 'required_assertion_ids': list(assertions), 'required_case_ids': [case_id]}
    return fixture, assertion


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Target:
    def __init__(self, profile=None):
        supplied = os.environ.get('AI4R_FOUNDATION_TARGET')
        if profile is None:
            if not supplied:
                raise FoundationBlocked('AI4R_FOUNDATION_TARGET_REQUIRED: no real target is bound')
            profile = json.loads(read_regular(supplied))
        self.profile = validate_profile(profile)
        self.host = {}
        for kind, pin in profile['host_receipts'].items():
            value = read_pin(pin)
            expected = {'schema', 'kind', *JOIN_KEYS, 'observed_at', 'qualified', 'observations', 'limitations'}
            if (set(value) != expected or value['schema'] != 'ai4r-foundation-host-receipt:1' or value['kind'] != kind
                    or any(value[key] != profile[key] for key in JOIN_KEYS)
                    or type(value['qualified']) is not bool or not isinstance(value['observations'], dict)
                    or not isinstance(value['limitations'], list)):
                raise FoundationBlocked('FOUNDATION_HOST_JOIN')
            self.host[kind] = value
        self.fixture = read_pin(profile['fixture_manifest'])
        self.assertions = read_pin(profile['assertion_manifest'])
        if self.assertions['check_id'] not in profile['check_ids'] or self.fixture['check_id'] != self.assertions['check_id']:
            raise FoundationBlocked('FOUNDATION_CHECK_JOIN')
        expected = manifests(self.assertions['check_id'], self.assertions['procedure_sha256'], self.fixture['source_baseline_sha256'])
        if (self.fixture, self.assertions) != expected:
            raise FoundationBlocked('FOUNDATION_ASSERTION_POPULATION_CHANGED')
        self.results = []
        self.http = []

    def require(self, assertion_id, condition, observation=None):
        if assertion_id not in self.assertions['required_assertion_ids'] or any(r['id'] == assertion_id for r in self.results):
            raise FoundationBlocked('FOUNDATION_ASSERTION_NOT_FROZEN_OR_DUPLICATE')
        self.results.append({'id': assertion_id, 'passed': condition is True, 'observation': observation})

    def request(self, path, *, authenticated=False, method='GET', value=None, headers=None, maximum_response=4 * 1024 * 1024):
        if not path.startswith('/') or path.startswith('//') or urlsplit(path).netloc:
            raise FoundationBlocked('FOUNDATION_HTTP_SCOPE')
        sent = {'Accept': 'application/json', **(headers or {})}
        if authenticated:
            token_path = self.profile['auth']['token_file']
            if not token_path:
                raise FoundationBlocked('CONTROLLER_AUTH_REQUIRED')
            token = read_regular(token_path, private=True, maximum=4096).decode('ascii').strip()
            if not 20 <= len(token) <= 256 or any(c.isspace() for c in token):
                raise FoundationBlocked('CONTROLLER_AUTH_INVALID')
            sent['Authorization'] = 'Bearer ' + token
        data = None if value is None else json_bytes(value)
        if data is not None:
            sent['Content-Type'] = 'application/json'
        request = Request(self.profile['origin'] + path, data=data, method=method, headers=sent)
        if type(maximum_response) is not int or not 0 < maximum_response <= 16 * 1024 * 1024:
            raise FoundationBlocked('CONTROLLER_RESPONSE_POLICY')
        try:
            response = build_opener(NoRedirect()).open(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read(maximum_response + 1)
            if len(raw) > maximum_response:
                raise FoundationBlocked('CONTROLLER_RESPONSE_LIMIT')
            status = response.status
            content_type = response.headers.get('content-type', '')
            decoded = json.loads(raw) if 'application/json' in content_type else None
            # Do not serialize arbitrary server content, headers, tokens or URLs.
            self.http.append({'method': method, 'path': path.split('?')[0], 'authenticated': authenticated,
                              'status': status, 'bytes': len(raw), 'body_sha256': digest(raw)})
            return status, decoded, raw

    def finish(self):
        required = self.assertions['required_assertion_ids']
        actual = [r['id'] for r in self.results]
        complete = set(actual) == set(required) and len(actual) == len(required)
        output = os.environ.get('AI4R_FOUNDATION_OBSERVATIONS')
        if output:
            path = Path(output)
            with path.open('x', encoding='utf8') as handle:
                json.dump({'schema': 'ai4r-foundation-controller-observations:1', 'check_id': self.assertions['check_id'],
                           'joins': {k: self.profile[k] for k in JOIN_KEYS}, 'assertions': self.results,
                           'http': self.http, 'complete': complete}, handle, indent=2)
        failed = [r['id'] for r in self.results if not r['passed']]
        if not complete or failed:
            raise AssertionError('Required real observations unavailable or failed: ' + ', '.join(failed or sorted(set(required) - set(actual))))


def observed(target, kind, key):
    receipt = target.host[kind]
    return receipt['qualified'] is True and receipt['observations'].get(key) is True


def exercise(check_id):
    """Run the finite source procedure against its identified actual target.

    Assertions without their actual operation traces remain false. A fresh
    development instance is useful diagnostic evidence, never full acceptance.
    """
    target = Target()
    if target.assertions['check_id'] != check_id:
        raise FoundationBlocked('FOUNDATION_WRONG_PROCEDURE')
    values = {}
    mappings = {
        'M1-001/V08': {'multiarch.manifests': ('image', 'both_architectures'), 'multiarch.locks': ('image', 'locked_closure'),
                       'multiarch.native_separate': ('native_platform', 'separate_platform_observations')},
        'M1-001/V09': {'startup.private_ports': ('ports', 'approved_private_only'), 'startup.config_negative': ('startup', 'invalid_config_cases'),
                       'startup.fixture_custody': ('startup', 'planted_fixture_denied'), 'startup.optional_absence': ('startup', 'fixed_route_without_optional'),
                       'startup.blocked_execution': ('startup', 'blocked_execution_observed'), 'auth.websocket': ('startup', 'websocket_auth_matrix'),
                       'auth.revoked': ('startup', 'revoked_http_ws')},
        'M1-001/V15': {key: ('operations', key.split('.')[1]) for key in CHECKS['M1-001/V15'][1]},
        'M1-001/V16': {'system.identity': ('image', 'same_candidate_closure'), 'system.child_checks': ('child_checks', 'all_current_pass'),
                       'system.builder': ('child_checks', 'live_builder_qualified'), 'system.platforms': ('native_platform', 'all_required_platforms'),
                       'system.retention': ('child_checks', 'lossless_restart_retention')},
        'M1-001/V17': {'channels.constructed': ('channels', 'zero_external_constructors'), 'channels.network': ('channels', 'zero_external_network'),
                       'channels.ordinary': ('channels', 'ordinary_preserved'), 'channels.native': ('startup', 'native_surfaces'),
                       'tmux.owned': ('tmux', 'fixed_owned_panes'), 'tmux.detach': ('tmux', 'attach_detach_preserves'),
                       'tmux.fault': ('tmux', 'fault_logs_no_replay')},
        'M1-006/V06': {'topology.private': ('ports', 'approved_private_only'), 'topology.no_internal': ('ports', 'no_internal_ports'),
                       'topology.no_broad_home': ('ports', 'no_broad_home'), 'topology.no_runtime_install': ('startup', 'no_runtime_install'),
                       'topology.port_conflict': ('startup', 'port_conflict_denied')},
        'M1-006/V28': {'terminal.owned': ('tmux', 'fixed_owned_panes'), 'terminal.attach_detach': ('tmux', 'attach_detach_preserves'),
                       'terminal.fault': ('tmux', 'fault_logs_no_replay'), 'terminal.authority': ('tmux', 'authority_unchanged')},
        'M1-006/V29': {'whitelist.construction': ('channels', 'zero_external_constructors'), 'whitelist.network': ('channels', 'zero_external_network'),
                       'whitelist.native': ('startup', 'native_surfaces'), 'whitelist.ordinary': ('channels', 'ordinary_preserved')},
    }
    for key, (kind, name) in mappings.get(check_id, {}).items():
        values[key] = observed(target, kind, name)
    if check_id in {'M1-001/V09', 'M1-001/V16', 'M1-006/V05', 'M1-006/V06'}:
        try:
            status, readiness, _ = target.request('/api/v1/readiness', authenticated=True)
            valid = status == 200 and isinstance(readiness, dict)
            if valid:
                from jiuwenswarm.research.contracts import validate
                validate('client-readiness', readiness)
            unavailable = status == 503 and isinstance(readiness, dict) and readiness.get('category') == 'unavailable'
            if unavailable:
                from jiuwenswarm.research.contracts import validate
                validate('client-error', readiness)
                unavailable = bool(readiness.get('message') and readiness.get('correction') and 'pins' not in readiness)
            identity = bool(valid and readiness.get('instance_id') == target.profile['instance_id'] and readiness.get('build_id') == target.profile['build_id'])
            prerequisites = readiness.get('prerequisites', []) if valid else []
            explicit = bool(prerequisites) and all(isinstance(p, dict) and p.get('name') and p.get('status') in {'ready', 'unavailable'}
                                                 and isinstance(p.get('reason'), str) and p['reason'].strip() for p in prerequisites)
            blocked = bool(valid and readiness.get('ready') is False and any(p.get('status') == 'unavailable' for p in prerequisites)
                           and 'submit' not in readiness.get('operations', []))
            if check_id == 'M1-006/V05':
                values.update({'readiness.source_projection': bool(valid or unavailable), 'readiness.identity': identity,
                               'readiness.prerequisites': explicit, 'readiness.no_execution': bool(blocked or unavailable),
                               'readiness.controlled_variants': observed(target, 'startup', 'required_prerequisite_variants'),
                               'readiness.optional_absence': observed(target, 'startup', 'fixed_route_without_optional'),
                               'readiness.security_sentinel': observed(target, 'startup', 'planted_fixture_denied'),
                               'readiness.identity_mismatch': observed(target, 'startup', 'client_identity_mismatch_denied')})
            elif check_id == 'M1-001/V09':
                values['startup.identity'] = identity
            elif check_id == 'M1-001/V16':
                values['system.identity'] = values['system.identity'] and identity
                values['system.ready'] = bool(valid and readiness.get('ready') is True and explicit and all(p['status'] == 'ready' for p in prerequisites))
        except Exception:
            for key in CHECKS[check_id][1]:
                if key.startswith(('readiness.', 'system.ready', 'startup.identity')):
                    values[key] = False
    if check_id in {'M1-001/V09', 'M1-006/V06'}:
        try:
            denial = []
            for headers, suffix in [({}, ''), ({'X-User-Id': 'operator'}, '?user_id=operator'), ({'Authorization': 'Bearer public-invalid-canary'}, '')]:
                status, error, _ = target.request('/api/v1/readiness' + suffix, headers=headers)
                denial.append(status == 401 and isinstance(error, dict) and error.get('category') == 'auth')
            if check_id == 'M1-006/V06':
                values['topology.auth'] = all(denial)
            else:
                values['auth.spoof_denied'] = all(denial)
            if check_id in {'M1-001/V09', 'M1-006/V06'}:
                status, _, raw = target.request('/')
                html = raw.decode('utf8', errors='strict')
                import re
                assets = re.findall(r'(?:src|href)="(/assets/[^"?#]+)"', html)
                built = status == 200 and '<html' in html.lower() and bool(assets)
                if built:
                    asset_status, _, asset = target.request(assets[0], maximum_response=16 * 1024 * 1024)
                    built = asset_status == 200 and bool(asset)
                values['startup.built_ui' if check_id == 'M1-001/V09' else 'topology.built_assets'] = built
        except Exception:
            values.setdefault('topology.auth' if check_id == 'M1-006/V06' else 'auth.spoof_denied', False)
    for key in CHECKS[check_id][1]:
        target.require(key, values.get(key) is True)
    target.finish()
