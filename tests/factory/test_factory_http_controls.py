"""Node-check view and operator controls of the factory runs HTTP API.

Synthetic homes only: the muse-q2-ttft plan is seeded without an agent, and node checks
are written as host observations by the test. Nothing runs a model or a controller.
"""
import json
from pathlib import Path
from types import SimpleNamespace

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
    assert outputs['converter']['stage'] == 'fixture' and outputs['converter']['review'] is True
    converter = outputs['converter']['checks'][-1]
    assert converter['passed'] is False and converter['same_settings'] is True and converter['superseded'] is False
    assert [c['name'] for c in converter['verifier']['checks']] == ['source_map', 'split_order']
    pack = outputs['nvfp4_pack']['checks'][-1]
    assert pack['review']['verdict'] == 'pass' and pack['review']['findings'][0]['severity'] == 'minor'
    assert 'entry' not in pack  # compact: the full settings stay in the record
    assert set(detail['node_checks']) >= {'pin_inputs', 'deliver_to_lab'}
    assert detail['controls'] == dict(operator=True, running=False, outcome=None, stop_reason=None, resume=False)


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
    assert api.post(f'/api/factory/runs/{rid}/resume').status_code == 403


def test_resume_starts_detached_cli_only_for_paused_or_partial_runs(home, monkeypatch):
    root, path = home
    service = FactoryHttpService(roots=[root])
    rid = service.listing()['runs'][0]['id']
    api = client(service)
    started = []
    monkeypatch.setattr(factory_http.subprocess, 'Popen',
                        lambda command, **kwargs: started.append((command, kwargs)) or SimpleNamespace(pid=4321))
    state = path / 'sessions' / f'{TID}.state.json'
    state.parent.mkdir(exist_ok=True)
    state.write_text(json.dumps(dict(turns=3, started=1.0, finished=2.0, tick=None, outcome='accept')))
    assert api.post(f'/api/factory/runs/{rid}/resume').status_code == 409
    assert api.post(f'/api/factory/runs/{rid}/resume', json={'command': 'rm'}).status_code == 400
    assert api.post(f'/api/factory/runs/{rid}/resume', headers={'origin': 'http://evil.invalid'}).status_code == 403
    assert started == []
    state.write_text(json.dumps(dict(turns=3, started=1.0, finished=2.0, tick=None, outcome='paused',
                                     stop_reason='paused at requant_q2 (held by operator: x)')))
    controls = service.detail(rid)['controls']
    assert controls['resume'] is True and controls['stop_reason'].startswith('paused at requant_q2')
    monkeypatch.setattr(service, '_running', lambda at: True)
    assert api.post(f'/api/factory/runs/{rid}/resume').status_code == 409
    monkeypatch.setattr(service, '_running', lambda at: False)
    response = api.post(f'/api/factory/runs/{rid}/resume', json={})
    assert response.status_code == 202, response.text
    assert response.json() == dict(id=rid, task_id=TID, pid=4321, resumed_from='paused')
    command, options = started[-1]
    assert command[command.index('--home'):] == ['--home', str(path.resolve()), 'resume', TID, '--plain',
                                                 '--grant', 'process.exec', '--grant', 'workspace.read']
    assert options['start_new_session'] is True and options['stdin'] is factory_http.subprocess.DEVNULL
    assert json.loads((path / 'resume.json').read_text())['pid'] == 4321
