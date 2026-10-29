"""Actual native session/signature joins; synthetic finite launch, no models."""
import asyncio
import ast
import copy
import hashlib
import importlib.util
import inspect
import os
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.cc_ui_runtime import module

dev = module('cc_rsi_development')


@pytest.fixture
def installed(tmp_path):
    from jiuwenswarm.research.shell_auth import SessionAuthority
    from jiuwenswarm.research.contracts import Principal
    from jiuwenswarm.research_rsi.signing import Signer
    authority = SessionAuthority(tmp_path/'native', 'http://127.0.0.1:5175')
    bootstrap = authority.initialize(Principal('unit:human', frozenset({'local'}), frozenset({'status'})))
    grant = authority.bootstrap(bootstrap.split('research_bootstrap=')[1], origin=authority.origin, host=authority.host)
    headers = {'origin': authority.origin, 'host': authority.host, 'cookie': grant['set_cookie'].split(';')[0]}
    signer = Signer.generate('unit:development-key')
    policy = {'schema': dev.POLICY, 'workspace_id': 'local', 'origin': authority.origin,
        'actors': ['unit:human'], 'gateway_key_id': 'unit:development-key',
        'target_id': 'unit:ranking', 'revision': 'a'*64, 'run_id': 'unit-development'}
    class Journal:
        value = None
        def lookup(self): return self.value
        def claim(self, identity, assertion):
            assert self.value is None
            self.value = {'identity': copy.deepcopy(identity), 'assertion': copy.deepcopy(assertion)}
        def accept(self, record):
            self.value['launch'] = record
            return {'id': 'unit:launch', 'sha256': hashlib.sha256(dev.encoded(record)).hexdigest()}
        def acknowledge(self, ack): self.value['ack'] = copy.deepcopy(ack)
    journal = Journal(); launches = []; checks = []; assertions = []
    def preflight(): checks.append(True)
    def launch(): launches.append(True); return {'pid': 123, 'unit_only': True}
    engine = dev.RootDevelopmentEngine(policy, signer.public_bytes(), journal, preflight, launch, clock=lambda: 1000)
    class Client:
        def start(self, params, assertion):
            assertions.append(copy.deepcopy(assertion))
            return engine.handle({'protocol': dev.PROTOCOL, 'operation': 'start', 'params': params, 'assertion': assertion})
        def status(self): return engine.status()
    class Projection:
        def snapshot(self, params):
            assert params == {}
            return {'revision': 'a'*64, 'targets': [
                {'id': 'unit:ranking', 'run': {'allowed': True, 'blocker': None}},
                {'id': 'foreign', 'run': {'allowed': True, 'blocker': None}}], 'nodes': []}
    adapter = dev.NativeDevelopmentAdapter(authority, signer, Client(), policy, projection=Projection(), clock=lambda: 1000)
    params = {'target_id': 'unit:ranking', 'revision': 'a'*64, 'client_request_id': 'unit:click-1'}
    yield locals()
    authority.close()


def test_real_native_click_signed_root_exact_once_and_idempotent(installed):
    v = installed
    ack = asyncio.run(v['adapter'].execute(v['headers'], v['params']))
    assert ack['status'] == 'ACCEPTED_UNQUALIFIED' and ack['security_status'] == 'SECURITY_DEFERRED'
    assert ack == asyncio.run(v['adapter'].execute(v['headers'], v['params']))
    assert len(v['launches']) == len(v['checks']) == 1
    assert v['journal'].value['assertion']['actor'] == 'unit:human'
    assert set(ack) == {'target_id', 'revision', 'client_request_id', 'run_id', 'status', 'security_status', 'receipt_ref'}


@pytest.mark.parametrize('field,value', [('actor', 'unit:root'), ('argv', ['/bin/sh']), ('budget', 99), ('proof', 'browser')])
def test_browser_cannot_select_authority_or_commands(installed, field, value):
    v = installed
    with pytest.raises(ValueError): asyncio.run(v['adapter'].execute(v['headers'], v['params'] | {field: value}))
    assert not v['launches'] and v['journal'].value is None


@pytest.mark.parametrize('field,value', [('target_id', 'foreign'), ('revision', 'b'*64)])
def test_different_target_or_published_revision_refused(installed, field, value):
    v = installed
    with pytest.raises(ValueError): asyncio.run(v['adapter'].execute(v['headers'], v['params'] | {field: value}))
    assert not v['launches']


def test_fresh_native_authentication_required_on_every_click(installed):
    v = installed
    headers = dict(v['headers']); headers.pop('cookie')
    with pytest.raises(Exception): asyncio.run(v['adapter'].execute(headers, v['params']))
    assert v['journal'].value is None
    v['adapter'].policy['workspace_id'] = 'foreign'
    with pytest.raises(Exception): asyncio.run(v['adapter'].execute(v['headers'], v['params']))
    assert not v['launches']


def test_root_rejects_valid_signature_for_foreign_workspace_and_expired_click(installed):
    v = installed
    asyncio.run(v['adapter'].execute(v['headers'], v['params']))
    assertion = v['assertions'][0]
    for update in ({'workspace_id': 'foreign'}, {'issued_at': 900, 'expires_at': 930}, {'actor': 'foreign'}):
        changed = {key: value for key, value in (assertion | update).items() if key not in ('signature', 'signer_key_id')}
        with pytest.raises(ValueError): v['engine'].start(v['params'], v['signer'].sign(changed))
    assert len(v['launches']) == 1


def test_claim_survives_launch_failure_and_never_replays(installed):
    v = installed
    def fail(): raise OSError('unit injected launch failure')
    v['engine'].launch = fail
    with pytest.raises(OSError): asyncio.run(v['adapter'].execute(v['headers'], v['params']))
    assert v['journal'].value is not None and v['journal'].value.get('ack') is None
    v['engine'].launch = v['launch']
    for params in (v['params'], v['params'] | {'client_request_id': 'unit:second-click'}):
        with pytest.raises(ValueError): asyncio.run(v['adapter'].execute(v['headers'], params))
    assert not v['launches'] and v['engine'].status()['phase'] == 'CLAIMED'


def test_changed_preflight_blocks_before_claim_or_launch(installed):
    v = installed
    def fail(): raise ValueError('reviewed Source/plan changed')
    v['engine'].preflight = fail
    assert v['engine'].status()['ready'] is False
    with pytest.raises(ValueError): asyncio.run(v['adapter'].execute(v['headers'], v['params']))
    assert v['journal'].value is None and not v['launches']


def test_only_root_ready_target_overlays_run_gate_never_foreign_public_grant(installed):
    v = installed
    view = asyncio.run(v['adapter'].snapshot(v['headers'], {}))
    assert view['targets'][0]['run']['allowed'] is True
    assert view['targets'][1]['run']['allowed'] is False
    asyncio.run(v['adapter'].execute(v['headers'], v['params']))
    view = asyncio.run(v['adapter'].snapshot(v['headers'], {}))
    assert all(row['run']['allowed'] is False for row in view['targets'])


def test_simultaneous_distinct_clicks_launch_only_one(installed):
    v = installed; results = []
    def click(index):
        try: results.append(asyncio.run(v['adapter'].execute(v['headers'], v['params'] | {'client_request_id': f'unit:click-{index}'})))
        except ValueError: results.append(None)
    threads = [threading.Thread(target=click, args=(i,)) for i in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert len(v['launches']) == 1 and len([r for r in results if r is not None]) == 1


def test_root_protocol_closed_and_no_library_operation(installed):
    for payload in ({'protocol': dev.PROTOCOL, 'operation': 'admit'},
                    {'protocol': dev.PROTOCOL, 'operation': 'status', 'path': '/private'}):
        with pytest.raises(ValueError): installed['engine'].handle(payload)
    assert installed['journal'].value is None


def test_actual_native_dispatch_preserves_library_and_scopes_development(installed):
    from jiuwenswarm.research.contracts import ResearchError
    v = installed
    source = Path(__file__).parents[3]/'jiuwenswarm/gateway/channel_manager/web/research_http.py'
    tree = ast.parse(source.read_text(encoding='utf8'))
    functions = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                 and node.name in ('_result', 'native_research_message')]
    namespace = {'ResearchError': ResearchError, 'inspect': inspect, 'os': os}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), namespace)
    actions = []
    class Operator:
        def execute(self, headers, params): actions.append(params); return {'ordinary_library': True}
    channel = SimpleNamespace(research_authority=v['authority'], research_service=None,
        research_cc_workspace='local', research_cc_operator=Operator(), research_cc_development=v['adapter'])
    ws = SimpleNamespace(request_headers=v['headers'])
    dispatch = namespace['native_research_message']
    handled, ack = asyncio.run(dispatch(channel, ws, 'rsi.cc.run.start', v['params']))
    assert handled and ack['status'] == 'ACCEPTED_UNQUALIFIED'
    assert asyncio.run(dispatch(channel, ws, 'rsi.cc.operator.action', {'action': 'admit'})) == (True, {'ordinary_library': True})
    assert actions == [{'action': 'admit'}]
    channel.research_cc_workspace = 'foreign'
    for method in ('rsi.cc.snapshot', 'rsi.cc.candidate.get', 'rsi.cc.run.start', 'rsi.cc.operator.action'):
        with pytest.raises(ResearchError): asyncio.run(dispatch(channel, ws, method, v['params']))
    assert len(v['launches']) == 1 and len(actions) == 1


@pytest.mark.parametrize('startup,environment,path', [
    ('local', 'foreign', dev.PUBLICATION), (None, 'local', dev.PUBLICATION),
    ('local', None, dev.PUBLICATION), ('local', 'local', '/arbitrary/publication.json')])
def test_native_cc_fallback_rejects_publication_startup_scope_mismatch(installed, monkeypatch, startup, environment, path):
    from jiuwenswarm.research.contracts import ResearchError
    v = installed
    source = Path(__file__).parents[3]/'jiuwenswarm/gateway/channel_manager/web/research_http.py'
    tree = ast.parse(source.read_text(encoding='utf8'))
    functions = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                 and node.name in ('_result', 'native_research_message')]
    namespace = {'ResearchError': ResearchError, 'inspect': inspect, 'os': os}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), namespace)
    monkeypatch.setenv('JIUWENSWARM_CC_RSI_PUBLICATION', path)
    if environment is None: monkeypatch.delenv('JIUWENSWARM_CC_RSI_WORKSPACE', raising=False)
    else: monkeypatch.setenv('JIUWENSWARM_CC_RSI_WORKSPACE', environment)
    channel = SimpleNamespace(research_authority=v['authority'], research_service=None,
        research_cc_workspace=startup, research_cc_operator=None, research_cc_development=None)
    for method in ('rsi.cc.snapshot', 'rsi.cc.candidate.get', 'rsi.cc.run.start', 'rsi.cc.operator.action'):
        with pytest.raises(ResearchError):
            asyncio.run(namespace['native_research_message'](channel, SimpleNamespace(request_headers=v['headers']), method, {}))
    assert v['journal'].value is None


def test_fixed_launcher_rechecks_pins_and_exact_reviewed_preflight_before_effect(monkeypatch, tmp_path):
    path = Path(__file__).parents[3]/'deploy/m1/rsi_development_service.py'
    spec = importlib.util.spec_from_file_location('unit_development_service', path)
    service = importlib.util.module_from_spec(spec); spec.loader.exec_module(service)
    monkeypatch.setattr(service, 'dev', dev)
    pins = []
    def check(value, **kwargs): pins.append(value['path']); return value['path']
    monkeypatch.setattr(service, 'pin', check)
    config = {'policy': {'run_id': 'unit-development'}, 'approved_plan_sha256': 'b'*64}
    for name in ('interpreter', 'wrapper', 'authorization', 'runner'):
        config[name] = {'path': '/unit/' + name, 'sha256': 'c'*64}
    reply = {'schema': 'ai4r-cc-rsi-development-preflight:1', 'ready': True,
        'run_id': 'unit-development', 'approved_plan_sha256': 'b'*64, 'authorization_sha256': 'c'*64}
    calls = []
    def capture(argv, **kwargs):
        calls.append((argv, kwargs)); return SimpleNamespace(stdout=dev.encoded(reply))
    monkeypatch.setattr(service.subprocess, 'run', capture)
    launcher = service.FixedLauncher(config, None)
    launcher.preflight()
    assert pins == ['/unit/' + name for name in ('interpreter', 'wrapper', 'authorization', 'runner')]
    assert calls[0][0] == ['/unit/interpreter', '-B', '/unit/wrapper', 'preflight']
    assert calls[0][1]['timeout'] == 20 and calls[0][1]['stdin'] == service.subprocess.DEVNULL
    for change in ({'approved_plan_sha256': 'd'*64}, {'authorization_sha256': 'd'*64}, {'ready': False}, {'run_id': 'foreign'}):
        old = dict(reply); reply.update(change)
        with pytest.raises(ValueError): launcher.preflight()
        reply.clear(); reply.update(old)
    with pytest.raises(ValueError): launcher.argv('arbitrary-command')
