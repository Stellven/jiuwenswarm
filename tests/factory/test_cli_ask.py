import json
from types import SimpleNamespace

from jiuwenswarm.factory.cli import ask_task


def args(**kw):
    base = dict(instruction='integrate expert_fill and build once', template=None, branch=None,
                max_turns=None, wall_clock=None, dry_run=False)
    base.update(kw)
    return SimpleNamespace(**base)


def test_ask_builds_task_from_default_template(tmp_path):
    path, task = ask_task(args(), tmp_path)
    assert task['objective'] == 'integrate expert_fill and build once'
    assert task['constraints']['engine_slice'] == 'expert_weight_readiness'
    assert task['contract_id'] == 'qwen36-quick-v1'
    branch = task['source']['branch']
    assert branch.startswith('direct-') and branch == branch.lower()
    assert json.loads(path.read_text()) == task and path.parent == tmp_path / 'tasks'


def test_ask_overrides_and_dry_run_writes_nothing(tmp_path):
    path, task = ask_task(args(branch='proof-1', max_turns=4, wall_clock=600, dry_run=True), tmp_path)
    assert task['source']['branch'] == 'proof-1'
    assert task['budget'] == {'max_turns': 4, 'wall_clock_s': 600}
    assert not path.exists()


def test_ask_rejects_empty_instruction(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        ask_task(args(instruction='   '), tmp_path)
