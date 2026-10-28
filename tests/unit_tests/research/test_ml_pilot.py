import hashlib
import json
import os
from pathlib import Path
import stat

import pytest

from jiuwenswarm.research import ml_pilot
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore


def test_frozen_pilot_model_and_review_selection_cannot_drift(tmp_path):
    from jiuwenswarm.research.local_profile import capture_local_profile
    inputs = tmp_path / 'input'; inputs.mkdir()
    store = SQLiteRunStore(tmp_path / 'state', input_root=inputs)
    try:
        options = dict(input_root=inputs, requested_model='gpt-6-luna', evidence_aware_review=True, allow_missing_science=True)
        result = capture_local_profile(store, tmp_path / 'operator' / 'pilot', **options)
        binding = store.read_record(result['binding_ref'])
        assert store.read_record(binding['deployment_ref'])['requested_model'] == 'gpt-6-luna'
        assert binding['protected_options']['evidence_aware_review'] is True
        assert capture_local_profile(store, tmp_path / 'operator' / 'pilot', **options) == result
        with pytest.raises(ResearchError, match='Frozen model or review mode changed'):
            capture_local_profile(store, tmp_path / 'operator' / 'pilot', input_root=inputs, allow_missing_science=True)
    finally:
        store.close()


@pytest.mark.parametrize('kind', ['signal', 'no-signal'])
def test_ml_fixture_is_reproducible_without_test_label_leakage(kind):
    task, public, private = ml_pilot.task_bytes(kind, 12345)
    assert (task, public, private) == ml_pilot.task_bytes(kind, 12345)
    data, holdout = json.loads(public), json.loads(private)
    assert len(data['train']) == 96 and len(data['test']) == 48
    assert all(set(row) == {'id', 'features'} for row in data['test'])
    assert holdout['public_data_sha256'] == hashlib.sha256(public).hexdigest()
    assert {row['id'] for row in holdout['labels']} == {row['id'] for row in data['test']}
    if kind == 'no-signal':
        assert len({tuple(row['features']) for row in [*data['train'], *data['test']]}) == 1
        assert sum(row['label'] == 'class_0' for row in holdout['labels']) / 48 == .75


@pytest.mark.skipif(os.name != 'posix' or os.geteuid() != 0, reason='Actual root-only task authoring')
def test_private_tasks_are_immutable_and_switch_requires_quiescence(tmp_path, monkeypatch):
    public, private = tmp_path / 'public', tmp_path / 'private'
    tasks = ml_pilot.prepare_tasks(public, private)
    assert len(tasks['tasks']) == 2
    task = tasks['tasks'][0]
    assert stat.S_IMODE(private.stat().st_mode) == 0o700
    assert stat.S_IMODE(Path(task['private_holdout_path']).stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        ml_pilot.prepare_tasks(public, private)
    scorer_root = tmp_path / 'scorer'; scorer_root.mkdir(mode=0o700)
    monkeypatch.setattr(ml_pilot, 'PRIVATE_PATH', str(scorer_root / 'holdout.json'))
    state = tmp_path / 'state'
    store = SQLiteRunStore(state)
    try:
        store.create_run('running', account_id='operator', workspace_id='local', submission={})
        with pytest.raises(ResearchError, match='active research'):
            ml_pilot.select_task(private / 'tasks.json', task['task_id'], state)
        assert not (scorer_root / 'holdout.json').exists()
        store.set_run_state('running', 'halted', reason='Controlled test stop')
        selected = ml_pilot.select_task(private / 'tasks.json', task['task_id'], state)
        assert 'private_holdout_path' not in selected
        assert hashlib.sha256((scorer_root / 'holdout.json').read_bytes()).hexdigest() == task['holdout_sha256']
    finally:
        store.close()
