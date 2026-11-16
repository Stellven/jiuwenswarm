"""Cancellation ownership faults; Docker transport is explicitly substituted."""
from types import SimpleNamespace
import pytest

from jiuwenswarm.factory import benchmark, lab_lifecycle


@pytest.fixture
def cancellation(tmp_path, monkeypatch):
    attempt = dict(task_id='owned', attempt_id='attempt', request={'adapter': benchmark.ADAPTER},
                   state='cancelled', cleanup_state='process_groups_reaped;containers_unverified')
    calls = []
    manager = object.__new__(benchmark.Benchmark)
    manager.store = SimpleNamespace(home=tmp_path)
    manager.jobs = SimpleNamespace(_get=lambda _: attempt, status=lambda _: attempt,
                                  cancel=lambda _: (calls.append('cancel') or attempt))
    monkeypatch.setattr(benchmark, 'metadata', lambda store, value, **changes: dict(value, **changes))
    return manager, attempt, calls


def test_cancel_checks_task_before_effect_and_handles_unstarted_work(cancellation):
    manager, attempt, calls = cancellation
    with pytest.raises(ValueError, match='another task'):
        manager.cancel('other', 'attempt')
    assert calls == []
    assert manager.cancel('owned', 'attempt')['cleanup_state'] == 'no_container_created'
    assert calls == ['cancel']


def test_cancel_recovers_only_exact_attempt_phase_intents(cancellation, monkeypatch):
    manager, attempt, calls = cancellation
    phase = manager.store.home / 'benchmark-spool/attempt/cell-001-A/speed'
    phase.mkdir(parents=True)
    (phase / 'intent.json').write_text('{}')
    unrelated = manager.store.home / 'benchmark-spool/other/cell-001-A/speed'
    unrelated.mkdir(parents=True)
    (unrelated / 'intent.json').write_text('{}')
    monkeypatch.setattr(lab_lifecycle, 'load_intent', lambda path: dict(path=path))
    remaining = {phase}
    monkeypatch.setattr(lab_lifecycle, 'inspect_owned', lambda intent: {'owned': True} if intent['path'] in remaining else None)
    def recover(path, **kwargs):
        assert path == phase
        remaining.remove(path)
    monkeypatch.setattr(lab_lifecycle, 'recover_run', recover)
    assert manager.cancel('owned', 'attempt')['cleanup_state'] == 'reaped'
    assert unrelated.exists()


def test_cancel_cannot_upgrade_unknown_cleanup(cancellation, monkeypatch):
    manager, attempt, calls = cancellation
    phase = manager.store.home / 'benchmark-spool/attempt/cell-001-A/speed'
    phase.mkdir(parents=True)
    (phase / 'intent.json').write_text('{}')
    def unavailable(_):
        raise RuntimeError('Injected Docker outage')
    monkeypatch.setattr(lab_lifecycle, 'load_intent', unavailable)
    assert manager.cancel('owned', 'attempt')['cleanup_state'] == 'containers_unverified'
