import pytest
from fastapi.testclient import TestClient

from jiuwenswarm.software_factory.cc_prepare import prepare
from jiuwenswarm.software_factory.cc_server import create_app


def test_console_restart_keeps_run_and_local_access_boundary(tmp_path):
    bundle = tmp_path / 'package'
    bundle.mkdir()
    (bundle / 'cc.yaml').write_text('''cc: '2'
id: test.echo
version: 1.0.0
bindings:
  default:
    kind: native
    command: ['{python}', '{bundle}/run.py']
capabilities:
  echo:
    does: Echo input
    takes: {value: json}
    gives: {value: json}
''')
    (bundle / 'run.py').write_text("import json,sys\np=json.load(sys.stdin)\nprint(json.dumps({'outcome':'ok','outputs':p['inputs']}))\n")
    config = tmp_path / 'config.json'
    prepare(config, 'console-check', [bundle])
    static = tmp_path / 'web'
    static.mkdir()
    with pytest.raises(ValueError, match='Build the factory console'):
        create_app(config, static)
    (static / 'index.html').write_text('<title>Factory</title>')
    request = {'workflow': 'test-echo-echo', 'inputs': {'value': 42}, 'objective': 'Restart check', 'run_id': 'durable'}
    with TestClient(create_app(config, static)) as client:
        assert client.get('/').status_code == 200
        assert client.post('/api/v1/cc-workflows/runs', json=request).status_code == 202
    with TestClient(create_app(config, static)) as client:
        assert client.get('/api/v1/cc-workflows/runs/durable').json()['id'] == 'durable'
        assert client.get('/healthz').json()['acceptance'] == 'not_assessed'
        assert client.post('/api/v1/cc-workflows/runs/durable/tick', headers={'Origin': 'https://untrusted.example'}).status_code == 403
    with TestClient(create_app(config, static), client=('192.0.2.1', 1234)) as remote:
        assert remote.post('/api/v1/cc-workflows/runs/durable/tick', headers={'X-Forwarded-For': '127.0.0.1'}).status_code == 403
