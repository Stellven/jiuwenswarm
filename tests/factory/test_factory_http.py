"""HTTP boundary checks use synthetic evidence; they never start a model."""
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from jiuwenswarm.factory.store import Store
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService, attach_factory_routes


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / 'bundle'
    (root / 'records').mkdir(parents=True)
    task = dict(task_id='synthetic', objective='Boundary test', budget={}, source={}, initial_run_config={})
    (root / 'records/tasks.json').write_text(json.dumps([task]))
    (root / 'report.md').write_text('Synthetic report')
    manifest = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob('*') if p.is_file()}
    (root / 'MANIFEST.json').write_text(json.dumps(manifest))
    return root


def client(service):
    app = FastAPI()
    attach_factory_routes(app, service=service)
    return TestClient(app)


def test_demo_run_date_uses_recorded_task_creation(bundle):
    task_file = bundle / 'records/tasks.json'
    tasks = json.loads(task_file.read_text())
    created = 1795713964.8986309
    tasks[0]['created'] = created
    task_file.write_text(json.dumps(tasks))
    replay = bundle / 'replay.json'
    replay.write_text(json.dumps(dict(
        schema='factory.curated-replay/1', title='Demo contract', steps=[],
        presentation_header=dict(objective='Read evidence', outcome='Done'),
    )))
    manifest = {p.relative_to(bundle).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (task_file, replay, bundle / 'report.md')}
    (bundle / 'MANIFEST.json').write_text(json.dumps(manifest))

    service = FactoryHttpService(roots=[bundle])
    row, = client(service).get('/api/factory/runs').json()['runs']
    assert row['contract_demo']
    assert row['created'] == created
    assert row['updated'] == bundle.stat().st_mtime


def test_manifest_mismatch_is_visible_and_missing_file_preserved(bundle):
    service = FactoryHttpService(roots=[bundle])
    rid = service.listing()['runs'][0]['id']
    assert next(f for f in service.detail(rid)['files'] if f['path'] == 'report.md')['integrity'] == 'verified'
    (bundle / 'report.md').write_text('Changed')
    assert service.file(rid, 'report.md')['integrity'] == 'mismatch'
    (bundle / 'report.md').unlink()
    assert next(f for f in service.detail(rid)['files'] if f['path'] == 'report.md')['integrity'] == 'missing'


def test_file_membership_traversal_and_symlink_boundaries(bundle, tmp_path):
    service = FactoryHttpService(roots=[bundle])
    api = client(service)
    rid = service.listing()['runs'][0]['id']
    outside = tmp_path / 'secret.txt'
    outside.write_text('outside secret')
    assert api.get(f'/api/factory/runs/{rid}/file', params={'path': '../secret.txt'}).status_code == 404
    assert api.get('/api/factory/runs/unknown').status_code == 404
    (bundle / 'escape.txt').symlink_to(outside)
    assert service.listing()['runs'] == []


def test_live_view_never_initializes_store_or_changes_database(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    with Store(home) as store:
        store.create_task(dict(task_id='synthetic', objective='read-only', budget={}, source={}))
    before = {p.name: p.read_bytes() for p in home.glob('factory.sqlite*')}
    monkeypatch.setattr(Store, '__init__', lambda *a, **k: pytest.fail('read initialized Store'))
    service = FactoryHttpService(roots=[home])
    rid = service.listing()['runs'][0]['id']
    assert service.detail(rid)['records']['tasks'][0]['objective'] == 'read-only'
    assert before == {p.name: p.read_bytes() for p in home.glob('factory.sqlite*')}


def test_live_contract_cannot_escape_allowed_roots(tmp_path):
    home = tmp_path / 'home'
    outside = tmp_path / 'outside.json'
    outside.write_text('{"secret":"do not open"}')
    with Store(home) as store:
        store.create_task(dict(task_id='synthetic', objective='read-only', contract_id=str(outside)))
    service = FactoryHttpService(roots=[home])
    rid = service.listing()['runs'][0]['id']
    with pytest.raises(ValueError, match='outside allowed'):
        service.detail(rid)


def test_sanitized_artifact_keeps_original_digest(bundle):
    target = bundle / 'credentials.json'
    target.write_text(json.dumps({'password': 'a password for synthetic test'}))
    manifest_path = bundle / 'MANIFEST.json'
    manifest = json.loads(manifest_path.read_text())
    manifest[target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    service = FactoryHttpService(roots=[bundle])
    result = service.file(service.listing()['runs'][0]['id'], target.name)
    assert 'a password' not in result['content']
    assert result['integrity'] == 'verified'
    assert result['sha256'] == manifest[target.name]


@pytest.mark.parametrize(('source', 'expected'), [
    (b'{ "version" : 8, "label": "\\u00e9" }\r\n', b'{ "version" : 8, "label": "\\u00e9" }\r\n'),
    (b'{"nested":{"password":"overwritten value","password":"<redacted>"}}\n',
     b'{\n  "nested": {\n    "password": "<redacted>"\n  }\n}'),
])
def test_json_file_keeps_original_format_when_safe(bundle, source, expected):
    target = bundle / 'contract.json'
    target.write_bytes(source)
    manifest_path = bundle / 'MANIFEST.json'
    manifest = json.loads(manifest_path.read_text())
    manifest[target.name] = hashlib.sha256(source).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    service = FactoryHttpService(roots=[bundle])
    rid = service.listing()['runs'][0]['id']
    result = client(service).get(f'/api/factory/runs/{rid}/file', params={'path': target.name})
    assert result.status_code == 200
    assert result.json()['content'].encode() == expected
    assert result.json()['sha256'] == manifest[target.name]


def test_launch_rejects_cross_origin_unconfigured_and_arbitrary_payload(bundle):
    api = client(FactoryHttpService(roots=[bundle]))
    assert api.post('/api/factory/launch', json={'template_id': 'x'}, headers={'origin': 'http://evil.invalid'}).status_code == 403
    assert api.post('/api/factory/launch', json={'template_id': 'x'}).status_code == 403
    assert api.post('/api/factory/launch', json={'command': 'anything'}).status_code == 400


def test_launch_uses_only_operator_template_in_new_detached_home(tmp_path, monkeypatch):
    from jiuwenswarm.gateway.channel_manager.web import factory_http
    templates = tmp_path / 'templates'
    templates.mkdir()
    (templates / 'reviewed.json').write_text(json.dumps({'task_id': 'template', 'allowed_effects': ['read']}))
    service = FactoryHttpService(roots=[tmp_path / 'runs'], launch_root=templates, launch_home_root=tmp_path / 'runs/homes')
    seen = []
    monkeypatch.setattr(factory_http.subprocess, 'run', lambda command, **kwargs: seen.append(command) or SimpleNamespace(returncode=0))
    monkeypatch.setattr(factory_http.subprocess, 'Popen', lambda command, **kwargs: seen.append((command, kwargs)) or SimpleNamespace(pid=1234))
    result = service.launch('reviewed')
    command, options = seen[-1]
    assert command[-2:] == ['--grant', 'read']
    assert options['start_new_session'] is True
    assert result['task_id'].startswith('web-')
    assert (tmp_path / 'runs/homes' / result['task_id'] / 'task.json').is_file()
    with pytest.raises(Exception):
        service.launch('../reviewed')


def test_artifact_display_name_preserves_confined_content_path(bundle):
    blob = bundle / 'artifacts' / 'hash-only-path'
    blob.parent.mkdir()
    blob.write_text('Retained report')
    mapping = [{'artifact_id': 'source:attached/report.md@sha256:abc', 'exported_path': 'artifacts/hash-only-path'}]
    (bundle / 'artifacts.json').write_text(json.dumps(mapping))
    service = FactoryHttpService(roots=[bundle])
    rid = service.listing()['runs'][0]['id']
    file = service.file(rid, 'artifacts/hash-only-path')
    assert file['display_path'] == 'attached/report.md'
    assert file['path'] == 'artifacts/hash-only-path'
    assert file['content'] == 'Retained report'
    assert client(service).get(f'/api/factory/runs/{rid}/file', params={'path': 'attached/report.md'}).status_code == 404


def test_catalog_distinguishes_exports_and_live_home_for_same_task(bundle, tmp_path):
    import os
    import shutil

    second = tmp_path / 'later-export'
    shutil.copytree(bundle, second)
    os.utime(bundle, (1000, 1000))
    os.utime(second, (2000, 2000))
    home = tmp_path / 'source-home'
    with Store(home) as store:
        store.create_task(dict(task_id='synthetic', objective='Live source', budget={}, source={}))

    runs = FactoryHttpService(roots=[tmp_path, second]).listing()['runs']
    assert len(runs) == len({run['id'] for run in runs}) == 3
    assert {run['name'] for run in runs} == {'synthetic'}
    sources = {run['source_name']: (run['kind'], run['updated']) for run in runs}
    assert sources['bundle'] == ('bundle', 1000)
    assert sources['later-export'] == ('bundle', 2000)
    assert sources['source-home'][0] == 'live'


def test_session_status_requires_controller_evidence(tmp_path):
    fcntl = pytest.importorskip('fcntl')
    if not Path('/proc/locks').is_file():
        pytest.skip('Controller lock observation requires Linux')
    home = tmp_path / 'home'
    with Store(home) as store:
        store.create_task(dict(task_id='synthetic', objective='Synthetic session test', budget={}, source={}))
    now = time.time()
    directory = home / 'sessions'
    directory.mkdir(exist_ok=True)
    state = dict(started=now - 20, tick=now - 2, turns=1, active_s=12)
    state_path = directory / 'synthetic.state.json'
    state_path.write_text(json.dumps(state))
    transcript = [
        dict(event='turn.start', turn=1),
        dict(event_type='chat.delta', content='Checking', t=now - 2),
        dict(event_type='chat.delta', content=' retained evidence.', t=now - 1),
        dict(event_type='chat.tool_call', tool_call=dict(name='evidence.read', tool_call_id='read-1')),
        dict(event_type='chat.tool_result', tool_call_id='read-1'),
        dict(event_type='chat.tool_call', tool_call=dict(name='evidence.query', tool_call_id='query-1')),
    ]
    (directory / 'synthetic.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in transcript))
    service = FactoryHttpService(roots=[home])
    run_id = service.listing()['runs'][0]['id']
    api = client(service)
    url = f'/api/factory/runs/{run_id}/session'
    with (home / 'controller.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        active = api.get(url).json()
        assert active['status'] == 'running'
        assert active['elapsed_s'] >= 14
        assert active['step'] == dict(kind='tool', label='evidence.query')
        assert active['latest_message'] == dict(text='Checking retained evidence.', created=now - 1)
    stale = api.get(url).json()
    assert stale['status'] == 'unknown'
    assert stale['elapsed_s'] == 12
    assert stale['step'] is None
    state_path.write_text(json.dumps(dict(state, finished=now, outcome='partial', tick=None)))
    assert api.get(url).json()['status'] == 'finished'


def test_reviewed_template_metadata_lists_contract_and_capsules(tmp_path):
    templates = tmp_path / 'templates'
    templates.mkdir()
    (templates / 'reviewed.json').write_text(json.dumps(dict(
        contract_id='example-contract', component_cc='example.builder', objective='A reviewed objective',
        operator_labels=dict(display_name='Reviewed session'), source=dict(private_key='never expose'),
    )))
    (templates / 'invalid.json').write_text('not valid JSON')
    service = FactoryHttpService(roots=[], launch_root=templates)
    assert service.listing()['launch_templates'] == [
        dict(id='reviewed', name='Reviewed session', contract_id='example-contract',
             objective='A reviewed objective', capsules=['example.builder']),
    ]


def test_completed_r8_live_home_keeps_native_story_on_detail_and_poll(tmp_path):
    home = tmp_path / 'graph-r8'
    task_id = 'muse-2bit-demo-r8'
    with Store(home) as store:
        store.create_task(dict(task_id=task_id, contract_id=task_id, objective='Build an inference engine',
                               budget={}, source={}))
        store.append_observation(task_id, dict(obs_id='verified-output', kind='output_verified', values={}))
        store.append_observation(task_id, dict(obs_id='completed-plan', kind='taskgraph_patch', values={
            'rev': 1, 'parent_rev': 0, 'decision_rev': 0,
            'patch': {'add': [
                {'node_id': 'deliver', 'title': 'Deliver engine', 'kind': 'deliver', 'state': 'done',
                 'evidence_ids': ['verified-output']},
            ]},
        }))

    api = client(FactoryHttpService(roots=[home]))
    runs = api.get('/api/factory/runs').json()['runs']
    url = f"/api/factory/runs/{runs[0]['id']}"
    response = api.get(url)
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail['graph']['nodes'][0]['state'] == 'done'
    assert detail['curated'] is None
    assert any(event['id'] == 'completed-plan' for event in detail['events'])
    response = api.get(url + '/story', params={'since': 1})
    assert response.status_code == 200, response.text
    assert response.json() == dict(events=detail['events'], cursor=len(detail['events']),
                                   total=len(detail['events']), reset=True)
