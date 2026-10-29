"""Closed host transport operator CLI; never prepares or invokes a real host."""
import importlib.util
from contextlib import nullcontext
import json
import stat
import shutil
from pathlib import Path

import pytest

SOURCE = Path(__file__).parents[3] / 'deploy/m1/rsi_host_codex.py'
spec = importlib.util.spec_from_file_location('rsi_host_codex_test', SOURCE)
host = importlib.util.module_from_spec(spec); spec.loader.exec_module(host)


@pytest.mark.parametrize('args', [['serve', '--model', 'foreign'], ['smoke', '--timeout', '600'],
    ['check', '--runtime', '/tmp/other'], ['prepare', '--account-file', '/tmp/auth']])
def test_no_runtime_destination_model_budget_or_credentials_override(args, monkeypatch):
    monkeypatch.setattr(host, 'prepare', lambda _: pytest.fail('No prepare permitted'))
    monkeypatch.setattr(host.asyncio, 'run', lambda _: pytest.fail('No runtime permitted'))
    with pytest.raises(SystemExit) as error: host.main(args)
    assert error.value.code == 2


def test_fixed_client_and_transport_roots_are_distinct_from_benchmark():
    assert host.ROOT.as_posix() == '/var/lib/ai4r-rsi-host-codex'
    assert host.CLIENT.as_posix() == '/var/lib/ai4r-rsi-host-codex-client'
    assert host.RUN.as_posix() == '/run/ai4r-rsi-host-codex'
    assert len({host.ROOT, host.CLIENT, host.RUN}) == 3


def restored_profile(tmp_path, monkeypatch):
    root = tmp_path / 'root'; root.mkdir()
    run = tmp_path / 'runtime'
    value = {'catalog': {'public': 'fixed'}, 'qualification': {'proof': 'fixed'},
             'session': {'session_id': 'original-session', 'capability': 'original-capability'}}
    (root / 'profile.json').write_bytes(host.encoded(value))
    monkeypatch.setattr(host, 'ROOT', root)
    monkeypatch.setattr(host, 'RUN', run)
    monkeypatch.setattr(host, 'runtime_lock', nullcontext)
    monkeypatch.setattr(host, 'load_profile', lambda: value)
    def read_restored():
        assert json.loads((run / 'catalog.json').read_bytes()) == value['catalog']
        assert json.loads((run / 'session.json').read_bytes()) == value['session']
        assert json.loads((run / 'qualification.json').read_bytes()) == value['qualification']
        return value
    monkeypatch.setattr(host, '_load_runtime', lambda value: read_restored())
    return root, run


def test_runtime_restore_reuses_exact_profile_no_models(tmp_path, monkeypatch, capsys):
    root, run = restored_profile(tmp_path, monkeypatch)
    before = (root / 'profile.json').read_bytes()
    result = host.restore_runtime()
    assert not result['inference'] and not result['relay_started'] and not result['native_login_changed']
    assert (root / 'profile.json').read_bytes() == before
    assert stat.S_IMODE(run.stat().st_mode) == 0o710
    for name, uid, gid, mode in [('catalog.json', 0, 13000, 0o640),
                               ('qualification.json', 0, 13000, 0o640),
                               ('session.json', 12001, 12001, 0o400)]:
        meta = (run / name).stat()
        assert (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) == (uid, gid, mode)
    assert 'original-capability' not in capsys.readouterr().out
    with pytest.raises(ValueError):
        host.restore_runtime()


def test_runtime_restore_partial_claim_is_not_replayed(tmp_path, monkeypatch):
    root, run = restored_profile(tmp_path, monkeypatch)
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    (root / ('runtime-restore.' + boot + '.claim.json')).write_bytes(b'original-interrupted-claim')
    with pytest.raises((ValueError, FileNotFoundError)):
        host.restore_runtime()
    assert not run.exists()


def test_normal_load_blocks_partial_restore_before_runtime_access(tmp_path, monkeypatch):
    root, _ = restored_profile(tmp_path, monkeypatch)
    (root / 'runtime-restore.boot.claim.json').write_bytes(b'claim')
    monkeypatch.setattr(host, 'custody', lambda path, *a, **kw: path.stat())
    monkeypatch.setattr(host, '_load_runtime', lambda _: pytest.fail('Partial restore must block runtime'))
    with pytest.raises(FileNotFoundError):
        host.load()


def test_same_kernel_new_pid1_gets_distinct_restore_retains_original(tmp_path, monkeypatch):
    root, run = restored_profile(tmp_path, monkeypatch)
    # Pytest's /tmp ancestor is deliberately not Root custody.
    monkeypatch.setattr(host, 'custody', lambda path, *a, **kw: path.stat())
    monkeypatch.setattr(host, 'runtime_incarnation', lambda: ({'kernel': 'same', 'pid1_ticks': '1'}, 'a' * 64))
    host.restore_runtime()
    retained = {p.name: p.read_bytes() for p in root.glob('runtime-restore.*')}
    shutil.rmtree(run)
    monkeypatch.setattr(host, 'runtime_incarnation', lambda: ({'kernel': 'same', 'pid1_ticks': '2'}, 'b' * 64))
    host.restore_runtime()
    assert all((root / name).read_bytes() == raw for name, raw in retained.items())
    assert host.load()['session']['capability'] == 'original-capability'
    monkeypatch.setattr(host, 'runtime_incarnation', lambda: ({'kernel': 'same', 'pid1_ticks': '3'}, 'c' * 64))
    with pytest.raises(FileNotFoundError):
        host.load()
