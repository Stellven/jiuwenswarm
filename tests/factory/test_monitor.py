import json
import threading
import pytest
from urllib.request import urlopen
from jiuwenswarm.factory.monitor import make_server, HTML
from jiuwenswarm.factory.telemetry import emit


def test_monitor_endpoints(store):
    attempt = store.create_attempt('t', dict(kind='build', request={}, idem_key='k', fingerprint='f'))
    emit(store.home, 'cc.call', 't', capability='evidence.query', duration_ms=1)
    before = sorted(str(p.relative_to(store.home)) for p in store.home.rglob('*'))
    try:
        server = make_server(store.home, port=0)
    except PermissionError:
        pytest.skip('Environment prohibits socket creation; HTTP test requires loopback sockets')
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def get(path):
        with urlopen(f'http://127.0.0.1:{server.server_port}' + path, timeout=10) as response:
            return response.read()
    try:
        assert b'<h2>Engine</h2>' in get('/')
        tasks = json.loads(get('/api/tasks'))
        assert tasks[0]['task_id'] == 't'
        story = json.loads(get('/api/story?task=t'))
        assert isinstance(story['events'], list)
        assert story['task']['objective'] == 'offline build'
        assert isinstance(story['engine_stack'], list)
        assert json.loads(get('/api/telemetry?task=t&since=0'))[-1]['capability'] == 'evidence.query'
        job = json.loads(get('/api/job?attempt=' + attempt['attempt_id']))
        assert job['state'] == 'queued' and job['log'] == []
        assert sorted(str(p.relative_to(store.home)) for p in store.home.rglob('*')) == before
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert 'http://' not in HTML and 'https://' not in HTML
    assert 'innerHTML' not in HTML


def test_monitor_models_and_scrubbed_tail(store, tmp_path):
    from jiuwenswarm.factory.monitor import tasks, job, engine_stack
    from jiuwenswarm.factory.story import load_source
    qdir = tmp_path / 'queue'
    qdir.mkdir()
    a = store.create_attempt('t', dict(kind='build', request={}, idem_key='k', fingerprint='f', jobq_id='job-x', resources=dict(jobq_dir=str(qdir))))
    (qdir / 'job-x.log').write_text('\n'.join(str(n) for n in range(25)))
    assert len(job(store.home, a['attempt_id'])['log']) == 14
    assert tasks(store.home)[0]['task_id'] == 't'
    assert engine_stack(load_source('t', store.home))[0]['state'] == 'base'


def wire_get(home, path):
    """Exercise the actual HTTP handler without sockets in restricted sandboxes."""
    import io
    from types import SimpleNamespace
    from jiuwenswarm.factory.monitor import make_handler
    class Connection:
        def __init__(self):
            self.response = bytearray()
        def makefile(self, *args):
            return io.BytesIO(('GET ' + path + ' HTTP/1.0\r\nHost: localhost\r\n\r\n').encode())
        def sendall(self, data):
            self.response.extend(data)
    connection = Connection()
    make_handler(home)(connection, ('127.0.0.1', 1), SimpleNamespace())
    headers, body = bytes(connection.response).split(b'\r\n\r\n', 1)
    assert b'200 OK' in headers, bytes(connection.response)
    return body


def test_http_handler_without_network(store):
    from jiuwenswarm.factory.story import build_events, load_source
    a = store.create_attempt('t', dict(kind='build', request={}, idem_key='k', fingerprint='f'))
    assert b'<h2>Engine</h2>' in wire_get(store.home, '/')
    assert json.loads(wire_get(store.home, '/api/tasks'))[0]['task_id'] == 't'
    story = json.loads(wire_get(store.home, '/api/story?task=t'))
    assert story['events'] == build_events(load_source('t', store.home))
    assert isinstance(json.loads(wire_get(store.home, '/api/telemetry?task=t')), list)
    assert json.loads(wire_get(store.home, '/api/job?attempt=' + a['attempt_id']))['state'] == 'queued'
