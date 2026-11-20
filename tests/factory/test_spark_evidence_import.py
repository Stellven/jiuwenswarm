"""Import evidence honestly; no engine or decision agent is run by these tests."""
import importlib.util
import json
from pathlib import Path

import pytest

from jiuwenswarm.factory.store import Store

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('spark_import', ROOT / 'ops/spark/import_evidence.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def fixture(tmp_path):
    base, repo = tmp_path / 'base', tmp_path / 'repo'
    server = base / 'OPS/runs/A'
    write(server / 'start.json', {'arm': 'A', 'command': ['llama-server', '-lm', 'mmap'], 'binary_sha256': 'binary-sha'})
    write(server / 'result.json', {'arm': 'A', 'returncode': 0, 'peak_memory_bytes': 123})
    write(repo / 'ops/spark/prompts/MANIFEST.json', {'prompts': [{'target_tokens_including_template': 512, 'prompt_sha256': 'fixed-sha'}]})
    for name, actual, discard in [('cold', 510, True), ('warm', 512, False)]:
        write(server / name / 'request.json', {'temperature': 0, 'max_tokens': 32})
        write(server / name / 'result.json', {'arm': 'A', 'prompt_tokens': 512, 'usage': {'prompt_tokens': actual},
              'prompt_sha256': 'fixed-sha', 'ok': True, 'discard': discard, 'ttft_s': 3.2})
    return base, repo


def test_cold_mismatched_tokens_excluded_and_import_is_idempotent(tmp_path):
    base, repo = fixture(tmp_path)
    home = base / 'factory-runs/evidence'
    first = module.import_evidence(base, repo, home, 'synthetic-import')
    second = module.import_evidence(base, repo, home, 'synthetic-import')
    assert first['new_observations'] == 4
    assert second['new_observations'] == 0
    with Store(home) as store:
        data = store.dump('synthetic-import')
        measurements = [row for row in data['observations'] if row['kind'] == 'measurement']
        excluded = next(row for row in data['observations'] if row['kind'] == 'request_excluded')
        assert len(measurements) == 1
        assert measurements[0]['values']['prompt_tokens'] == 512
        assert measurements[0]['values']['binary_sha256'] == 'binary-sha'
        assert measurements[0]['source_artifacts']
        assert excluded['values']['prompt_tokens'] == 510
        assert excluded['values']['discarded'] and not excluded['values']['measurement_eligible']
        assert 'no factory decision agent' in data['tasks'][0]['objective']
    before = len(data['artifacts'])
    write(base / 'OPS/runs/A/result.json', {'arm': 'A', 'returncode': -9, 'peak_memory_bytes': 124})
    module.import_evidence(base, repo, home, 'synthetic-import')
    with Store(home) as store:
        data = store.dump('synthetic-import')
        assert len(data['artifacts']) == before + 1
        assert len([row for row in data['observations'] if row['kind'] == 'measurement']) == 1
        assert len([row for row in data['observations'] if row['kind'] == 'server_scope']) == 2


def test_credentials_and_symlink_inputs_rejected(tmp_path):
    secret = tmp_path / 'auth.json'
    secret.write_text('{"access_token":"synthetic"}')
    with pytest.raises(ValueError, match='Credential'):
        module.safe_bytes(secret)
    innocent = tmp_path / 'evidence.json'
    innocent.write_text('{"password":"synthetic"}')
    with pytest.raises(ValueError, match='Credential'):
        module.safe_bytes(innocent)
    link = tmp_path / 'link'
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        module.safe_bytes(link / 'evidence.json')


def test_failed_and_wrong_manifest_results_remain_ineligible():
    result = {'arm': 'A', 'ok': False, 'prompt_tokens': 512, 'usage': {'prompt_tokens': 512}, 'prompt_sha256': 'other'}
    row = module.measurement(result, {'temperature': 0, 'max_tokens': 32}, {}, {}, {}, {'prompts': []})
    assert not row['measurement_eligible']
    assert len(row['exclusion_reasons']) == 2
