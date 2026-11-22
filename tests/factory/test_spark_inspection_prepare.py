"""Bounded launch preparation tests never copy real credentials or run an agent."""
import importlib.util
from pathlib import Path

import pytest

from jiuwenswarm.factory.store import Store

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('inspection_prepare', ROOT / 'scripts/spark/prepare_inspection_home.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_inspection_preparation_is_explicit_and_artifact_only(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'
    for name in module.NAMES:
        capsule = repo / 'jiuwenswarm/factory/ccs' / name
        capsule.mkdir(parents=True)
        (capsule / 'GUIDE.md').write_text('Synthetic capsule guide')
    monkeypatch.setattr(module, 'ROOT', repo)
    copied = []
    monkeypatch.setattr(module, 'copy_auth_for_home', lambda home: copied.append(home) or True)
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    task = {'task_id': 'synthetic', 'allowed_effects': ['process.exec', 'workspace.read'],
            'operator_labels': {'inspection_only': True}, 'constraints': {}}
    home = tmp_path / 'home'
    with Store(home) as store:
        store.create_task({'task_id': 'synthetic', 'objective': 'Synthetic inspection'})
    assert module.prepare_inspection_home(home, task)['input_artifacts'] == 5
    assert copied == [home]
    with Store(home) as store:
        data = store.dump('synthetic')
        assert len(data['artifacts']) == 5
        assert data['observations'][0]['kind'] == 'inspection_inputs'
        assert 'does not implement' in data['observations'][0]['limitations']
    assert not (home / 'agent-workspace').exists()
    for changed in ({'allowed_effects': ['workspace.write']}, {'operator_labels': {}}, {'constraints': {'local_commits': True}}):
        with pytest.raises(ValueError):
            module.prepare_inspection_home(home, task | changed)
    assert copied == [home]


def test_missing_login_stops_before_any_inspection_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'copy_auth_for_home', lambda home: False)
    task = {'allowed_effects': ['process.exec', 'workspace.read'], 'operator_labels': {'inspection_only': True}}
    with pytest.raises(ValueError, match='login'):
        module.prepare_inspection_home(tmp_path / 'home', task)
    assert not (tmp_path / 'home').exists()
