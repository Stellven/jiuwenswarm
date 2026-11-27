from pathlib import Path
import hashlib
import json

"""The integrated Factory demo uses one native web application."""
from fastapi.testclient import TestClient

from jiuwenswarm.factory.store import Store
from scripts.spark.factory_demo_web import make_app


def test_native_factory_and_fallback_routes_share_the_shell(tmp_path, monkeypatch):
    monkeypatch.setenv('JIUWENSWARM_CONFIG_URL', 'off')
    monkeypatch.setenv('JIUWENSWARM_DATA_DIR', str(tmp_path / 'runtime'))
    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'index.html').write_text('<title>Demo shell</title>')
    (dist / 'app.js').write_text('/* Demo bundle */')
    live, history = tmp_path / 'live', tmp_path / 'history'
    for home, tid in ((live, 'live-run'), (history, 'old-run')):
        with Store(home) as store:
            store.create_task(dict(task_id=tid, objective='Local fixture', budget={}, source={}, allowed_effects=[]))
    monkeypatch.setenv('FACTORY_LAUNCH_ROOT', str(tmp_path / 'unexpected-templates'))
    monkeypatch.setenv('FACTORY_LAUNCH_HOME_ROOT', str(live / 'unexpected-launches'))
    with TestClient(make_app(dist, live, history), base_url='http://localhost', client=('127.0.0.1', 50000)) as api:
        entry = api.get('/factory', follow_redirects=False)
        assert entry.headers['location'] == '/#factory-run'
        assert 'Demo shell' in api.get('/').text
        assert 'Demo bundle' in api.get('/app.js').text
        assert 'Task graph' in api.get('/fallback').text
        assert api.get('/api/board').json()['operator_enabled'] is False
        assert [r['task_id'] for r in api.get('/api/tasks').json()] == ['live-run']
        assert api.get('/api/board?task=old-run').status_code == 404
        assert api.get('/api/plan').status_code == 200
        assert api.get('/api/story').status_code == 200
        assert api.get('/api/telemetry').status_code == 200
        assert api.post('/api/operator').status_code == 403
        listing = api.get('/api/factory/runs').json()
        assert listing['launch_enabled'] is False
        runs = {run['task_id']: run for run in listing['runs']}
        assert runs['old-run']['read_only'] is True
        old_url = '/api/factory/runs/' + runs['old-run']['id']
        assert api.get(old_url + '/state').json()['controls'] is None
        assert api.post(old_url + '/pause', json=dict(reason='read only', confirm=True)).status_code == 403
        assert api.get('/api/nonexistent').status_code == 404
        assert api.get('/api/factory/runs', headers={'Host': 'external.example'}).status_code == 400
        with api.websocket_connect('ws://localhost/ws') as ws:
            ws.send_text('invalid JSON')
            assert ws.receive_json()['code'] == 'BAD_REQUEST'


def test_native_websocket_adapter_accepts_a_unix_listener():
    from starlette.websockets import WebSocket

    from jiuwenswarm.gateway.channel_manager.web.ws_connection_adapter import StarletteWsAdapter

    async def unused(*_args):
        raise AssertionError('unexpected IO')

    scope = dict(type='websocket', scheme='ws', path='/ws', query_string=b'', headers=[(b'host', b'localhost')],
                 client=None, server=('/tmp/demo.sock', None))
    adapter = StarletteWsAdapter(WebSocket(scope, unused, unused))
    assert adapter.path == '/ws'
    assert adapter.local_address is None and adapter.remote_address is None


def test_engine_viewer_uses_only_public_reads(tmp_path, monkeypatch):
    import pytest
    from starlette.websockets import WebSocketDisconnect
    from scripts.spark.r8_engine_site import HISTORY_TASK, LIVE_TASK, TAILSCALE_DNS, TAILSCALE_HOST, make_app as make_engine

    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'index.html').write_text('<title>Engine Factory</title>')
    live, history, replay = (tmp_path / name for name in ('live', 'history', 'replay'))
    for home, tasks in ((live, (LIVE_TASK, 'another-task')), (history, (HISTORY_TASK,))):
        with Store(home) as store:
            for task in tasks:
                store.create_task(dict(task_id=task, objective='Fixture', budget={}, source={}, allowed_effects=[]))

    monkeypatch.setattr(Path, 'home', staticmethod(lambda: tmp_path))
    evidence = tmp_path / 'muse-demo' / 'r8-final'
    evidence.mkdir(parents=True)
    (evidence / 'README.md').write_text('Final index', encoding='utf-8')
    (evidence / 'strict-history.md').write_text('Strict history', encoding='utf-8')
    fixture = tmp_path / 'muse-demo' / 'r9' / 'factory-fixture-c'
    pins, configurations = {}, {}
    for arm, task in (('stock', 4), ('configured', 9)):
        relative = f'{arm}/server.log'
        log = fixture / relative
        log.parent.mkdir(parents=True)
        first = f'0.01.000.001 I slot operator(): id  0 | task {task} | cached n_tokens = 769, memory_seq_rm [769, end)'
        payload = f'/home/private/account\n{first}\n'.encode()
        log.write_bytes(payload)
        pins[relative] = hashlib.sha256(payload).hexdigest()
        configurations[arm] = dict(
            cached_tokens=769, prompt_tokens=788, server_log=relative, server_log_sha256=pins[relative],
            cpu_only={'cuda_visible_devices': '-1', 'requested_gpu_layers': 0},
            cache_prompt=True, server_closed=True,
            rows=[{}, dict(server_log_start=0, server_log_end=len(payload),
                           cache_evidence=dict(cache_line=first, prompt_tokens=788, task_id=task))],
        )
    summary = json.dumps(dict(
        format='muse-cpu-swa-fixture/1', status='complete',
        model=dict(id='small-swa-fixture', source='https://example.test', sha256='1' * 64, bytes=123, window_tokens=512),
        engine=dict(image_id='sha256:' + '2' * 64, sha256='3' * 64, executable='/home/private/llama-server'),
        configurations=configurations,
    )).encode()
    (fixture / 'summary.json').write_bytes(summary)
    pins['summary.json'] = hashlib.sha256(summary).hexdigest()
    (fixture / 'manifest.json').write_text(json.dumps(dict(files=pins, model_sha256='1' * 64)))
    site = make_engine(dist, live, history, replay)
    forwarded = {'X-Forwarded-For': '127.0.0.1', 'Forwarded': 'for=127.0.0.1'}
    with TestClient(site, base_url=f'http://{TAILSCALE_HOST}', client=('100.64.0.9', 50000)) as api:
        assert 'Engine Factory' in api.get('/').text
        for slug, expected in [('readme', 'Final index'), ('method-history', 'Strict history')]:
            url = '/api/factory/engine-bench/' + slug
            assert api.get(url).text == expected
            assert api.post(url, headers=forwarded).status_code == 403
        assert api.get('/api/factory/engine-bench/report.json').status_code == 403
        listing = api.get('/api/factory/runs').json()
        assert set(row['task_id'] for row in listing['runs']) == {LIVE_TASK, HISTORY_TASK, 'another-task'}
        assert listing['launch_enabled'] is False
        run = next(row['id'] for row in listing['runs'] if row['task_id'] == LIVE_TASK)
        for path in ('/api/factory/launch', f'/api/factory/runs/{run}/pause', f'/api/factory/runs/{run}/resume',
                     f'/api/factory/runs/{run}/revise', f'/api/factory/runs/{run}/nodes/n/release',
                     f'/api/factory/runs/{run}/nodes/n/note', '/file-api/file-content', '/api/operator'):
            assert api.post(path, headers=forwarded).status_code == 403
        assert api.get('/', headers={'Host': TAILSCALE_DNS}).status_code == 200
        assert api.get('/', headers={'Host': 'elsewhere.ts.net'}).status_code == 400
        assert api.get('/api/factory/capsules?usage=false').status_code == 200
        assert api.post('/api/factory/capsules', headers=forwarded).status_code == 403
        for path in ('/file-api/raw-file', '/openapi.json', '/api/tasks'):
            assert api.get(path, headers=forwarded).status_code == 403
        route = '/api/factory/capsules/kv_reuse_lab/fixture'
        data = api.get(route).json()
        assert data['configurations']['stock']['cached_tokens'] == 769
        assert data['configurations']['configured']['prompt_tokens'] == 788
        assert api.get(route + '/summary').json() == data
        assert '/home/private' not in api.get(route + '/summary').text
        assert 'cached n_tokens = 769' in api.get(route + '/stock').text
        assert '/home/private' not in api.get(route + '/stock').text
        assert api.get(route + '/manifest.json').status_code == 403
        assert api.post(route).status_code == 403
        (fixture / 'stock/server.log').write_text('tampered log')
        assert api.get(route).json() is None
        assert api.get(route + '/stock').status_code == 404
        with pytest.raises(WebSocketDisconnect), api.websocket_connect('/ws', headers=forwarded):
            pass


def test_operator_peer_must_be_actual_loopback(tmp_path):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'index.html').write_text('<title>Demo</title>')
    live, history = tmp_path / 'live', tmp_path / 'history'
    for home, task in ((live, 'live'), (history, 'history')):
        with Store(home) as store:
            store.create_task(dict(task_id=task, objective='Fixture', budget={}, source={}, allowed_effects=[]))

    app = make_app(dist, live, history)
    for peer in [('100.64.0.9', 50000), None]:
        with TestClient(app, base_url='http://localhost', client=peer) as api:
            headers = {'X-Forwarded-For': '127.0.0.1', 'Forwarded': 'for=127.0.0.1'}
            assert api.post('/api/factory/launch', headers=headers).status_code == 403
            with pytest.raises(WebSocketDisconnect), api.websocket_connect('/ws', headers=headers):
                pass
