"""Demonstration packages exercised through the real CC v2 host."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import urlopen

import pytest

from jiuwenswarm.ccv2.ccv2 import CCError, Host

ROOT = Path(__file__).resolve().parents[2]
CCS = ROOT / 'demo' / 'ccs'
REQUEST = ROOT / 'demo/requests/compute_service_native.request.yaml'
PRODUCT = ROOT / 'tests/ccv2/examples/http_product'


@pytest.fixture
def host(tmp_path):
    return Host(tmp_path / 'store', session_grants=[
        'workspace.read', 'process.exec', 'network.listen', 'network.request'])


def artifact_json(host, ref):
    return json.loads(host.artifact_path(ref).read_text(encoding='utf-8'))


@pytest.mark.parametrize('package', sorted(p.name for p in CCS.iterdir() if (p / 'cc.yaml').is_file()))
def test_prepare(host, package):
    release = host.prepare(CCS / package)
    assert len(release) == 64
    assert host.describe(release)['id'].startswith('demo.')


def test_workspace_inventory(host, tmp_path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    (workspace / 'data.json').write_text('{"name":"a","count":2,"active":true}', encoding='utf-8')
    (workspace / 'data.csv').write_text('x,y\n1,2\n3,4\n', encoding='utf-8')
    (workspace / 'rows.jsonl').write_text('{"x":1}\n{"x":2,"y":3}\n', encoding='utf-8')
    (workspace / 'bad.json').write_text('{', encoding='utf-8')
    for ignored in ('.git', '.venv', 'node_modules', '__pycache__'):
        (workspace / ignored).mkdir()
        (workspace / ignored / 'ignored.json').write_text('{}', encoding='utf-8')
    before = {p.relative_to(workspace): p.read_bytes() for p in workspace.rglob('*') if p.is_file()}
    host.resources['workspace'] = {'kind': 'workspace', 'path': str(workspace)}
    result = host.run(CCS / 'workspace_inspect', 'inspect', {'workspace': 'workspace'})
    assert result['state'] == 'succeeded', result
    report = result['outputs']['report']
    assert report['file_count'] == 4
    assert report['total_bytes'] == sum(len(data) for path, data in before.items() if len(path.parts) == 1)
    assert report['counts_by_extension'] == {'.json': 2, '.csv': 1, '.jsonl': 1}
    assert len(report['largest_files']) == 4
    metadata = {row['path']: row for row in report['structured_files']}
    assert metadata['data.json']['keys'] == {'name': 'string', 'count': 'number', 'active': 'boolean'}
    assert metadata['data.csv']['columns'] == ['x', 'y']
    assert metadata['data.csv']['line_count'] == 3
    assert metadata['rows.jsonl']['columns'] == ['x', 'y']
    assert metadata['rows.jsonl']['line_count'] == 2
    assert metadata['bad.json']['reason']
    assert artifact_json(host, result['outputs']['summary']) == report
    assert before == {p.relative_to(workspace): p.read_bytes() for p in workspace.rglob('*') if p.is_file()}
    limited = host.run(CCS / 'workspace_inspect', 'inspect', {'workspace': 'workspace', 'max_files': 1})
    assert limited['outputs']['report']['file_count'] == 1
    assert limited['outputs']['report']['truncated'] is True


def test_workspace_empty(host, tmp_path):
    workspace = tmp_path / 'empty'
    workspace.mkdir()
    host.resources['empty'] = {'kind': 'workspace', 'path': str(workspace)}
    result = host.run(CCS / 'workspace_inspect', 'inspect', {'workspace': 'empty'})
    assert result['state'] == 'succeeded', result
    report = result['outputs']['report']
    assert report['file_count'] == report['total_bytes'] == 0
    assert report['counts_by_extension'] == {}
    assert report['largest_files'] == report['structured_files'] == []
    assert artifact_json(host, result['outputs']['summary']) == report


def test_workspace_unknown_handle(host):
    result = host.run(CCS / 'workspace_inspect', 'inspect', {'workspace': 'unknown'})
    assert result['state'] in {'failed', 'blocked'}
    assert result['reason'] == 'MISSING_RESOURCE'
    assert result['outputs'] == {}


@pytest.mark.parametrize('resource', [{}, {'missing': True}, {'not_directory': True}])
def test_workspace_process_errors(tmp_path, resource):
    inputs, resources = {}, {}
    if resource:
        path = tmp_path / 'ordinary-file'
        path.write_text('file', encoding='utf-8')
        inputs['workspace'] = 'w'
        if resource.get('not_directory'):
            resources['w'] = {'kind': 'workspace', 'path': str(path)}
    packet = {'call': 'direct', 'attempt': 1, 'capability': 'inspect',
              'inputs': inputs, 'resources': resources, 'output_dir': str(tmp_path / 'out')}
    process = subprocess.run([sys.executable, str(CCS / 'workspace_inspect/inspect.py')],
                             input=json.dumps(packet), capture_output=True, text=True, check=True)
    result = json.loads(process.stdout)
    assert result['outcome'] == 'error'
    assert 'directory' in result['reason'] or 'workspace handle' in result['reason']


def test_service_client(host):
    app = host.start(host.prepare(PRODUCT), 'api')
    try:
        assert (app['state'], app['readiness']) == ('running', 'ready'), app
        host.resources['engine'] = {'kind': 'environment', 'url': app['endpoints']['api'], 'instance': app['id']}
        release = host.prepare(CCS / 'service_client')
        result = host.call(release, 'benchmark', {'engine': 'engine', 'workload': {'points': [1, 2, 3]}})
        assert result['state'] == 'succeeded', result
        assert result['completeness'] == 'complete'
        metrics = result['outputs']['metrics']
        assert metrics['count'] == 3
        assert metrics['values'] == [1, 2, 3]
        assert metrics['runtime'] is None  # Native fixture supplies no runtime metadata.
        assert 'NOT inference-engine TTFT' in metrics['scope']
        assert len(metrics['request_ms']) == 3
        assert 0 <= metrics['p50_client_ms'] <= metrics['p95_client_ms']
        rows = artifact_json(host, result['outputs']['series'])
        assert [row['point'] for row in rows] == [1, 2, 3]
        assert [row['value'] for row in rows] == metrics['values']
        assert [row['client_ms'] for row in rows] == metrics['request_ms']
        empty = host.call(release, 'benchmark', {'engine': 'engine', 'workload': {'points': []}})
        assert empty['state'] == 'succeeded'
        assert empty['outputs']['metrics']['count'] == 0
        assert empty['outputs']['metrics']['p50_client_ms'] is None
        assert artifact_json(host, empty['outputs']['series']) == []
    finally:
        assert host.stop(app['id'])['state'] == 'stopped'


def test_client_partial_and_runtime(tmp_path):
    # Exercise real HTTP with the supplied demo server, using its public class.
    import importlib.util
    from http.server import ThreadingHTTPServer
    import threading

    spec = importlib.util.spec_from_file_location('demo_compute_server', CCS / 'compute_service/payload/server.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = ThreadingHTTPServer(('127.0.0.1', 0), module.API)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = Host(tmp_path / 'store', session_grants=['network.request'])
        host.resources['engine'] = {'kind': 'environment', 'url': f'http://127.0.0.1:{server.server_port}/'}
        result = host.run(CCS / 'service_client', 'benchmark', {'engine': 'engine', 'workload': {'points': [3, 1e308]}})
        assert (result['state'], result['completeness']) == ('succeeded', 'partial'), result
        assert result['outputs']['metrics']['count'] == 1
        assert result['outputs']['metrics']['values'] == [6.0]
        assert result['outputs']['metrics']['runtime']['python']
        assert len(artifact_json(host, result['outputs']['series'])) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_methodology(host):
    release = host.prepare(CCS / 'methodology')
    assert host.describe(release)['bindings'] == {}
    for name in ('method', 'limits'):
        material = host.material(release, name)
        text = host.artifact_path(material['artifact']).read_text(encoding='utf-8')
        assert text and len(text.splitlines()) < 80
    assert host.call(release, 'method', {})['state'] in {'failed', 'blocked'}


def test_request_refused(host, tmp_path):
    # A request path is not a prepared executable release.
    result = host.call(str(REQUEST), 'api', {})
    assert result['state'] in {'failed', 'blocked'}
    assert result['reason'] == 'INVALID_RELEASE'
    with pytest.raises(CCError):
        host.start(str(REQUEST), 'api')
    # Nor can a request be disguised as an implementation declaration.
    folder = tmp_path / 'request'
    folder.mkdir()
    shutil.copyfile(REQUEST, folder / 'cc.yaml')
    with pytest.raises(CCError):
        host.prepare(folder)


@pytest.mark.docker
def test_compute_service_image(host):
    try:
        info = subprocess.run(['docker', 'info'], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        pytest.skip('docker info failed: ' + str(error))
    if info.returncode:
        pytest.skip('docker info failed: ' + (info.stderr.strip() or info.stdout.strip()))
    # A missing application image is a failure, never a skip.
    app = host.start(host.prepare(CCS / 'compute_service'), 'api', timeout=30)
    try:
        assert (app['state'], app['readiness']) == ('running', 'ready'), app
        with urlopen(app['endpoints']['api'] + 'compute?x=3', timeout=3) as response:
            result = json.load(response)
        assert result['value'] == 6.0
        assert 'Debian' in result['runtime']['os_release']
    finally:
        stopped = host.stop(app['id'])
    assert stopped['state'] == 'stopped', stopped
    remaining = subprocess.run(['docker', 'ps', '-a', '--filter', 'name=cc-app', '--format', '{{.Names}}'],
                               capture_output=True, text=True, check=True)
    assert remaining.stdout.strip() == ''
