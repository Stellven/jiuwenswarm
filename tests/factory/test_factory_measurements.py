"""Verify ledger provenance and filesystem boundaries without running a model."""
import hashlib
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService, attach_factory_routes


def _client(root):
    app = FastAPI()
    attach_factory_routes(app, service=FactoryHttpService(roots=[], measurement_root=root))
    return TestClient(app)


def _append(root, row):
    with (root / 'LEDGER.jsonl').open('a') as stream:
        stream.write(json.dumps(row) + '\n')


def _record(root, relative, event, result, **extra):
    target = root / 'runs' / relative / 'result.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result))
    _append(root, dict(event=event, result_path=str(target.parent), **result, **extra))
    return target


def _request(**extra):
    return dict(dict(arm='A', prompt_tokens=512, prompt_sha256='pinned-test-prompt', ok=True, discard=False,
                     ttft_s=2, decode_tps=12, usage={'prompt_tokens': 512}, timings={'cache_n': 0},
                     started='2026-11-20T01:00:01+00:00'), **extra)


def _scope():
    return dict(start='2026-11-20T01:00:00+00:00', stop='2026-11-20T01:00:20+00:00',
                scope_verified=True, returncode=0, binary_sha256='engine', peak_memory_bytes=47)


def test_measurements_link_to_exact_request_ledger_row_and_scope_files(tmp_path):
    root = tmp_path
    result = _record(root, 'stock/warm', 'request-stop', _request(), binary_sha256='engine')
    _record(root, 'stock', 'stop', _scope())
    _record(root, 'stock/warm-final', 'request-stop', _request(ttft_s=1), phase='P4')
    _record(root, 'stock/discarded', 'request-stop', _request(discard=True))
    _record(root, 'stock/cache', 'request-stop', _request(timings={'cache_n': 3}))
    _record(root, 'stock/bad-token-count', 'request-stop', _request(usage={'prompt_tokens': 510}))
    api = _client(root)
    response = api.get('/api/factory/measurements')
    assert response.status_code == 200
    payload = response.json()
    assert not payload['issues']
    assert [sample['phase'] for sample in payload['samples']] == ['reconnaissance', 'final']
    first = payload['samples'][0]
    assert first['source'] == {
        'line': 1, 'path': 'runs/stock/warm/result.json', 'sha256': hashlib.sha256(result.read_bytes()).hexdigest(),
        'integrity': 'ledger-match',
    }
    assert first['peak_memory_bytes'] == 47
    assert first['memory_source']['line'] == 2
    assert 'memory_source' not in payload['samples'][1]
    evidence = '/api/factory/measurements/evidence'
    assert api.get(f'{evidence}/1?kind=ledger').json()['evidence']['event'] == 'request-stop'
    assert api.get(f'{evidence}/1?kind=result').json()['evidence']['ttft_s'] == 2
    assert api.get(f'{evidence}/2?kind=result').json()['evidence']['peak_memory_bytes'] == 47


def test_missing_changed_and_escaping_result_files_cannot_supply_measurements(tmp_path):
    root = tmp_path / 'ops'
    target = _record(root, 'changed', 'request-stop', _request())
    target.write_text(json.dumps(_request(ttft_s=123)))
    missing = _record(root, 'missing', 'request-stop', _request())
    missing.unlink()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'result.json').write_text(json.dumps(_request()))
    _append(root, dict(event='request-stop', result_path=str(outside), **_request()))
    (root / 'runs' / 'symlink').symlink_to(outside, target_is_directory=True)
    _append(root, dict(event='request-stop', result_path='runs/symlink', **_request()))
    api = _client(root)
    payload = api.get('/api/factory/measurements').json()
    assert not payload['samples']
    assert [source['integrity'] for source in payload['issues']] == [
        'mismatch', 'missing', 'unavailable', 'unavailable',
    ]
    evidence = '/api/factory/measurements/evidence'
    assert api.get(f'{evidence}/1?kind=result').json()['source']['integrity'] == 'mismatch'
    assert api.get(f'{evidence}/3?kind=result').status_code == 404
    assert api.get(f'{evidence}/4?kind=result').status_code == 404
    assert api.get(f'{evidence}/9?kind=ledger').status_code == 404


def test_reported_intervals_and_explicit_digest_are_retained(tmp_path):
    request = _request()
    declared_digest = hashlib.sha256(json.dumps(request).encode()).hexdigest()
    _record(tmp_path, 'stock/warm', 'request-stop', request, result_sha256=declared_digest)
    summary = dict(arm='A', prompt_tokens=512, prompt_sha256='pinned-test-prompt', confidence_intervals={
        'ttft_s': {'low': 1.8, 'high': 2.2, 'n': 1, 'level': 0.95, 'source_lines': [1]},
        'decode_tps': {'low': 13, 'high': 12, 'n': 1, 'level': 0.95, 'source_lines': [1]},
    })
    _record(tmp_path, 'stock/summary', 'measurement-summary', summary)
    api = _client(tmp_path)
    payload = api.get('/api/factory/measurements').json()
    assert payload['samples'][0]['source']['integrity'] == 'verified'
    assert payload['samples'][0]['source']['expected_sha256'] == declared_digest
    assert payload['summaries'][0]['intervals'] == {'ttft_s': summary['confidence_intervals']['ttft_s']}
    assert api.get('/api/factory/measurements/evidence/2?kind=result').json()['evidence'] == summary
