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
    with TestClient(make_app(dist, live, history), base_url='http://localhost') as api:
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
