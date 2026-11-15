import fcntl
import importlib.util
from pathlib import Path


def launcher():
    path = Path(__file__).resolve().parents[2] / 'deploy/spark/run-mission.py'
    spec = importlib.util.spec_from_file_location('spark_mission_launcher', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_launcher_reuses_held_bridge_without_starting_or_stopping_it(tmp_path, monkeypatch):
    module = launcher()
    inbox = tmp_path / 'ipc'
    inbox.mkdir()
    with (inbox / 'bridge.lock').open('a') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX)
        monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **k: (_ for _ in ()).throw(
            AssertionError('Existing bridge must not be replaced')))
        assert module.ensure_bridge(tmp_path, tmp_path / 'home', inbox, tmp_path / 'queue', tmp_path / 'jobq') is None
        assert module.bridge_running(inbox)


def test_unheld_bridge_detection_releases_probe_lock(tmp_path):
    module = launcher()
    assert module.bridge_running(tmp_path / 'ipc') is False
    with (tmp_path / 'ipc/bridge.lock').open('a') as new_owner:
        fcntl.flock(new_owner, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_missing_task_is_not_implicitly_initialized(tmp_path):
    import pytest
    module = launcher()
    with pytest.raises(ValueError, match='Initialize and approve'):
        module.main(['--root', str(tmp_path)])
    assert not (tmp_path / 'mission-store/factory.sqlite').exists()


def test_owned_bridge_startup_failure_reaps_only_its_child(tmp_path, monkeypatch):
    import pytest
    module = launcher()
    monkeypatch.setattr(module, 'bridge_running', lambda inbox: False)

    class Child:
        terminated = False
        def poll(self): return None
        def terminate(self): self.terminated = True
        def wait(self, timeout): return 0

    child = Child()
    received = {}
    def start(*args, **kwargs):
        received.update(kwargs)
        return child
    monkeypatch.setattr(module.subprocess, 'Popen', start)
    stamps = iter([0, 11])
    monkeypatch.setattr(module.time, 'monotonic', lambda: next(stamps))
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-secret-that-must-not-enter-jobq')
    with pytest.raises(TimeoutError):
        module.ensure_bridge(tmp_path, tmp_path / 'home', tmp_path / 'ipc', tmp_path / 'queue', tmp_path / 'jobq')
    assert child.terminated
    assert 'OPENAI_API_KEY' not in received['env']
