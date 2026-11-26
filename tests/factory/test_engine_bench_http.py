import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService, attach_factory_routes


def test_engine_bench_only_reads_normalized_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', staticmethod(lambda: tmp_path))
    app = FastAPI()
    attach_factory_routes(app, service=FactoryHttpService(roots=[]))
    client = TestClient(app)
    url = '/api/factory/engine-bench'
    assert client.get(url).json() == {'schema': 'engine-bench/1', 'status': 'unavailable', 'rows': []}
    assert client.get(url, params={'path': '/etc/passwd'}).status_code == 400
    assert client.post(url, json={}).status_code == 405

    directory = tmp_path / 'muse-demo' / 'r8-final'
    directory.mkdir(parents=True)
    external = tmp_path / 'private'
    external.write_text('secret contents', encoding='utf-8')
    dataset = directory / 'engine-bench.jsonl'
    dataset.symlink_to(external)
    assert client.get(url).status_code == 422
    dataset.unlink()

    row = {'schema': 'engine-bench/1', 'kind': 'performance', 'id': 'example',
           'source': {'path': str(external), 'line': 7}, 'quiet': {'eligible': False, 'reason': 'Host load'},
           'metrics': {'ttft_ms': 1024},
           'launch_verdict': {'status': 'excluded', 'reasons': ['runner']},
           'corrected_verdict': {'status': 'accepted', 'reasons': []}, 'raw': {'text': 'raw request contents'}}
    dataset.write_text(json.dumps(row) + '\n', encoding='utf-8')
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.json()['rows'] == [{key: value for key, value in row.items() if key != 'raw'}]
    assert 'secret contents' not in response.text
    dataset.write_text(json.dumps(row) + '\ninvalid', encoding='utf-8')
    assert client.get(url).status_code == 422

def test_engine_bench_documents_use_fixed_plain_text_resources(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', staticmethod(lambda: tmp_path))
    app = FastAPI()
    attach_factory_routes(app, service=FactoryHttpService(roots=[]))
    client = TestClient(app)
    directory = tmp_path / 'muse-demo' / 'r8-final'
    directory.mkdir(parents=True)
    for slug, filename in [('readme', 'README.md'), ('method-history', 'strict-history.md')]:
        url = '/api/factory/engine-bench/' + slug
        document = directory / filename
        assert client.get(url).status_code == 404
        assert client.get(url, params={'path': '/etc/passwd'}).status_code == 400
        assert client.post(url, json={}).status_code == 405
        document.symlink_to('/etc/passwd')
        assert client.get(url).status_code == 422
        document.unlink()
        document.write_text(f'<script>{filename}</script>', encoding='utf-8')
        response = client.get(url)
        assert response.text == f'<script>{filename}</script>'
        assert response.headers['Content-Type'].startswith('text/plain')
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
        assert response.headers['Cache-Control'] == 'no-store'
    assert client.get('/api/factory/engine-bench/report.json').status_code == 404
