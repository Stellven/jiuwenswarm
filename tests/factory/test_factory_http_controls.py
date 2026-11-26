"""Node-check view and operator controls of the factory runs HTTP API.

Synthetic homes only: the muse-q2-ttft plan is seeded without an agent, and node checks
are written as host observations by the test. Nothing runs a model or a controller.
"""
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from jiuwenswarm.factory import taskgraph
from jiuwenswarm.factory.store import Store
from jiuwenswarm.gateway.channel_manager.web import factory_http
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService, attach_factory_routes

PLAN = Path(factory_http.__file__).resolve().parents[3] / 'factory/tasks/muse-q2-ttft.plan.json'
TID = 'muse-synthetic'


def client(service):
    app = FastAPI()
    attach_factory_routes(app, service=service)
    return TestClient(app)


def check_values(node, output, entry, passed, **extra):
    return dict(format='factory.node-check/2', node_id=node, output=output, kind=entry['kind'], entry=entry,
                key=f'{node}-{output}-{passed}', state='finished', passed=passed,
                reason='passed' if passed else 'verifier failed: split_order', seconds={'total': 3.0}, **extra)


@pytest.fixture
def home(tmp_path):
    root = tmp_path / 'runs'
    home = root / 'home'
    with Store(home) as store:
        store.create_task(dict(task_id=TID, objective='Synthetic node-check view', budget={}, source={},
                               contract_id='muse-q2-ttft-v2', allowed_effects=['process.exec', 'workspace.read']))
        taskgraph.seed_plan(store, store.get_task(TID), json.loads(PLAN.read_text()))
        node = next(n for n in taskgraph.plan_get(store, TID)['nodes'] if n['node_id'] == 'ingest_nvfp4')
        entries = {e['name']: e for e in node['check']['outputs']}
        verifier = dict(cc='weights.build_muse_nvfp4_reader', capability='verify', passed=False, stage_reached=None,
                        reason='split_order failed', checks=[dict(name='source_map', status='pass', stage='fixture', detail='ok'),
                                                             dict(name='split_order', status='fail', stage='fixture', detail='up first')])
        store.append_observation(TID, dict(obs_id='node-check:ingest_nvfp4:converter:1:a', kind='node_check',
                                           values=check_values('ingest_nvfp4', 'converter', entries['converter'], False, verifier=verifier)))
        review = dict(verdict='pass', summary='fine', findings=[dict(severity='minor', file='a.py', line=1, problem='name')],
                      passed=True, reason='passed', reviewer='codex', packet_artifact='p', reply_artifact='r')
        store.append_observation(TID, dict(obs_id='node-check:ingest_nvfp4:nvfp4_pack:2:b', kind='node_check',
                                           values=check_values('ingest_nvfp4', 'nvfp4_pack', entries['nvfp4_pack'], True, review=review)))
    return root, home


def test_detail_serves_node_contract_work_and_compact_checks(home):
    root, _ = home
    service = FactoryHttpService(roots=[root])
    rid = service.listing()['runs'][0]['id']
    detail = service.detail(rid)
    view = detail['node_checks']['ingest_nvfp4']
    assert 'weights.build_muse_nvfp4_reader' in view['helpful_ccs']
    assert view['capability'] == 'weights.build_muse_nvfp4_reader.verify'
    outputs = {o['name']: o for o in view['outputs']}
    assert outputs['converter']['stage'] == 'runtime acceptance' and outputs['converter']['review'] is True
    converter = outputs['converter']['checks'][-1]
    assert converter['passed'] is False and converter['same_settings'] is True and converter['superseded'] is False
    assert [c['name'] for c in converter['verifier']['checks']] == ['source_map', 'split_order']
    pack = outputs['nvfp4_pack']['checks'][-1]
    assert pack['review']['verdict'] == 'pass' and pack['review']['findings'][0]['severity'] == 'minor'
    assert 'entry' not in pack  # compact: the full settings stay in the record
    assert set(detail['node_checks']) >= {'pin_inputs', 'deliver_to_lab'}
    assert detail['controls'] == dict(operator=True, running=False, outcome=None, stop_reason=None,
                                      pause=True, resume=False, revise=True, revise_apply=True)


def test_operator_routes_guard_origin_body_and_live_homes(home, monkeypatch):
    root, path = home
    service = FactoryHttpService(roots=[root])
    rid = service.listing()['runs'][0]['id']
    api = client(service)
    calls = []

    class Fake:
        def __init__(self, at):
            self.at = at

        def operator(self, task_id, op, node_id, reason):
            calls.append((self.at, task_id, op, node_id, reason))
            with Store(self.at) as store:
                return taskgraph.operator_patch(store, task_id, op, node_id, reason)

    monkeypatch.setattr(factory_http, 'operator_controller', Fake)
    url = f'/api/factory/runs/{rid}/nodes/requant_q2/hold'
    assert api.post(url, json={'reason': 'x'}, headers={'origin': 'http://evil.invalid'}).status_code == 403
    assert api.post(url, json={'reason': ' '}).status_code == 400
    assert api.post(url, json={'reason': 'x', 'extra': 1}).status_code == 400
    assert api.post(f'/api/factory/runs/{rid}/nodes/requant_q2/delete', json={'reason': 'x'}).status_code == 404
    assert api.post(f'/api/factory/runs/{rid}/nodes/..%2Fx/hold', json={'reason': 'x'}).status_code in (400, 404)
    assert calls == []
    response = api.post(url, json={'reason': 'check the recipe first'}, headers={'origin': 'http://testserver'})
    assert response.status_code == 200, response.text
    assert response.json()['held'] == ['requant_q2']
    assert calls == [(path.resolve(), TID, 'hold', 'requant_q2', 'check the recipe first')]
    detail = service.detail(rid)
    assert next(n for n in detail['graph']['nodes'] if n['node_id'] == 'requant_q2')['hold'] == 'check the recipe first'
    # The controller refuses what the graph refuses; the HTTP layer reports it.
    assert api.post(f'/api/factory/runs/{rid}/nodes/requant_q2/release', json={'reason': 'ok'}).status_code == 200
    refused = api.post(f'/api/factory/runs/{rid}/nodes/requant_q2/release', json={'reason': 'again'})
    assert refused.status_code == 422 and 'not held' in refused.json()['detail']


def test_operator_controls_refuse_exported_bundles(tmp_path, monkeypatch):
    bundle = tmp_path / 'bundle'
    (bundle / 'records').mkdir(parents=True)
    (bundle / 'records/tasks.json').write_text(json.dumps([dict(task_id='exported', objective='Bundle', budget={}, source={})]))
    (bundle / 'MANIFEST.json').write_text('{}')
    monkeypatch.setattr(factory_http, 'operator_controller', lambda at: pytest.fail('bundle reached the controller'))
    service = FactoryHttpService(roots=[bundle])
    rid = service.listing()['runs'][0]['id']
    api = client(service)
    assert service.detail(rid)['controls'] is None
    assert api.post(f'/api/factory/runs/{rid}/nodes/a/hold', json={'reason': 'x'}).status_code == 403
    assert api.post(f'/api/factory/runs/{rid}/resume', json=dict(confirm=True, reason='resume')).status_code == 403


def test_run_controls_execute_confirmed_native_commands_without_running_controller(home, monkeypatch):
    root, path = home
    service = FactoryHttpService(roots=[root])
    rid = service.listing()['runs'][0]['id']
    api = client(service)
    url = f'/api/factory/runs/{rid}'
    confirmed = dict(confirm=True, reason='inspect evidence')
    assert api.post(url + '/resume', json=confirmed).status_code == 409
    assert api.post(url + '/pause', json=dict(confirmed, confirm=False)).status_code == 400
    assert api.post(url + '/pause', json=confirmed, headers={'origin': 'http://evil.invalid'}).status_code == 403
    paused = api.post(url + '/pause', json=confirmed)
    assert paused.status_code == 200, paused.text
    state = api.get(url + '/state').json()
    assert state['controls']['resume'] is True
    assert state['run_state']['state'] == 'paused'
    assert state['run_state']['reason'] == confirmed['reason']
    assert (path / 'PAUSE.md').is_file()
    assert api.get(url + '/nodes/ingest_nvfp4').status_code == 200
    assert api.get(url + '/nodes/fake').status_code == 404
    assert api.get(url + '/nodes/ingest_nvfp4/diff?output=converter').status_code == 404
    graph_before = service.detail(rid)['graph']['rev']
    before = {p.name: p.read_bytes() for p in path.glob('factory.sqlite*')}
    preview = api.post(url + '/revise', json=dict(confirmed, dry_run=True))
    assert preview.status_code == 200, preview.text
    assert preview.json()['dry_run'] is True and preview.json()['applied'] is False
    assert service.detail(rid)['graph']['rev'] == graph_before
    assert {p.name: p.read_bytes() for p in path.glob('factory.sqlite*')} == before
    monkeypatch.setattr(service, '_running', lambda at: True)
    assert api.post(url + '/revise', json=dict(confirmed, dry_run=False)).status_code == 409
    monkeypatch.setattr(service, '_running', lambda at: False)
    applied = api.post(url + '/revise', json=dict(confirmed, dry_run=False))
    assert applied.status_code == 200, applied.text
    assert applied.json()['dry_run'] is False
    resumed = api.post(url + '/resume', json=dict(confirmed, reason='-checked'))
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()['reason'] == '-checked'
    assert not (path / 'PAUSE.md').exists()
    assert not (path / 'launch.log').exists()
    assert api.get(url + '/state').json()['controls']['resume'] is False
    assert api.post(url + '/resume', json=confirmed).status_code == 409


def test_historical_native_home_is_read_only(home):
    root, path = home
    service = FactoryHttpService(roots=[root], historical_roots=[path])
    api = client(service)
    run = service.listing()['runs'][0]
    assert run['read_only'] and run['status'] == 'replay'
    url = f"/api/factory/runs/{run['id']}"
    assert api.get(url + '/state').json()['controls'] is None
    for action in ('pause', 'resume', 'revise', 'nodes/ingest_nvfp4/hold'):
        payload = dict(reason='test') if action.startswith('nodes/') else dict(confirm=True, reason='test')
        if action == 'revise':
            payload['dry_run'] = True
        assert api.post(url + '/' + action, json=payload).status_code == 403
