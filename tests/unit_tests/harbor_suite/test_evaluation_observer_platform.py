import asyncio
from types import SimpleNamespace

import pytest

from benchmarks.harbor_suite import evaluation


def test_platform_options_keep_groups_and_hide_windows_console():
    assert evaluation.observer_process_options('posix') == {'start_new_session': True}
    assert evaluation.observer_process_options('nt')['creationflags'] == 0x08000200
    with pytest.raises(ValueError):
        evaluation.observer_process_options('unknown')


def test_windows_cancellation_stops_observer_tree_only(monkeypatch):
    captured = {}
    process = SimpleNamespace(pid=123, returncode=None)
    async def wait():
        process.returncode = 1
        return 1
    process.wait = wait
    async def kill_wait():
        return 0
    async def create(*args, **kwargs):
        captured.update(args=args, kwargs=kwargs)
        return SimpleNamespace(wait=kill_wait)
    monkeypatch.setattr(evaluation.asyncio, 'create_subprocess_exec', create)
    asyncio.run(evaluation.stop_observer(process, 'nt'))
    assert captured['args'][1:] == ('/PID', '123', '/T', '/F')
    assert captured['args'][0].endswith('taskkill.exe')
    assert captured['kwargs']['creationflags'] == 0x08000000
    assert process.returncode == 1


def test_windows_failed_tree_stop_remains_uncertain(monkeypatch):
    async def wait():
        return 5
    async def create(*args, **kwargs):
        return SimpleNamespace(wait=wait)
    monkeypatch.setattr(evaluation.asyncio, 'create_subprocess_exec', create)
    with pytest.raises(ValueError, match='uncertain'):
        asyncio.run(evaluation.stop_observer(SimpleNamespace(pid=123, returncode=None), 'nt'))
