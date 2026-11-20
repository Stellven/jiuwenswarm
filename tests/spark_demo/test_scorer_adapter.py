"""Adapter checks are metadata-only; no scorer build or model execution."""
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

MODULE = Path(__file__).resolve().parents[2] / 'tools/spark_demo/scorer_adapter.py'
spec = importlib.util.spec_from_file_location('spark_scorer_adapter', MODULE)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def project(tmp_path):
    stock = tmp_path / 'llama.cpp-stock'
    stock.mkdir()
    subprocess.run(['git', 'init', '-q', stock], check=True)
    (stock / 'README').write_text('Synthetic stock for metadata test\n')
    subprocess.run(['git', '-C', stock, 'add', '.'], check=True)
    subprocess.run(['git', '-C', stock, '-c', 'user.name=Test', '-c', 'user.email=test@localhost',
                    'commit', '-qm', 'synthetic'], check=True)
    build = tmp_path / 'build-stock-cuda121'
    (build / 'bin').mkdir(parents=True)
    (build / 'bin/llama-server').write_bytes(b'synthetic binary; never executed')
    (build / 'CMakeCache.txt').write_text('CMAKE_CUDA_ARCHITECTURES:STRING=121\nGGML_CUDA:BOOL=ON\nCMAKE_GENERATOR:INTERNAL=Unix Makefiles\n')
    frozen = tmp_path / 'inputs/ab'
    frozen.mkdir(parents=True)
    for name in adapter.HASHES:
        (frozen / name).write_text('# synthetic frozen module\n')
    pin = subprocess.check_output(['git', '-C', stock, 'rev-parse', 'HEAD'], text=True).strip()
    return stock, frozen, pin


def test_prepare_pins_overrides_and_preserves_frozen_sources(tmp_path, monkeypatch):
    stock, frozen, pin = project(tmp_path)
    monkeypatch.setattr(adapter, 'PIN', pin)
    monkeypatch.setattr(adapter, 'HASHES', {name: adapter.sha(frozen / name) for name in adapter.HASHES})
    before = {name: (frozen / name).read_bytes() for name in adapter.HASHES}
    _, receipt, _, overrides = adapter.prepare(tmp_path, tmp_path / 'stage')
    assert overrides['RECEIPT_SHA256'] == adapter.sha(receipt)
    assert json.loads(receipt.read_text())['source_verified'] is True
    assert json.loads((tmp_path / 'stage/platform-overrides.json').read_text())['stock_commit'] == pin
    assert before == {name: (frozen / name).read_bytes() for name in adapter.HASHES}
    assert ' run "$@"' in (tmp_path / 'stage/run_checks.sh').read_text()


def test_prepare_refuses_frozen_source_drift(tmp_path, monkeypatch):
    _, frozen, _ = project(tmp_path)
    with pytest.raises(SystemExit, match='digest mismatch'):
        adapter.prepare(tmp_path, tmp_path / 'stage')


def test_server_ledger_wrap_preserves_original_context_protocol(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    (tmp_path / 'OPS').mkdir()
    binary = tmp_path / 'binary'
    binary.write_bytes(b'synthetic')
    events = []
    @contextmanager
    def original(*args, **kwargs):
        events.append('enter')
        yield 42
        events.append('clean-exit-check')
    runtime = SimpleNamespace(server=original, MODEL=Path('/synthetic.gguf'), BASE_ARGS=[])
    adapter.install_ledger(runtime, tmp_path)
    with runtime.server(binary, tmp_path / 'run', 42, ['-n', '1']) as port:
        assert port == 42
        events.append('request')
    assert events == ['enter', 'request', 'clean-exit-check']
    rows = [json.loads(line) for line in (tmp_path / 'OPS/LEDGER.jsonl').read_text().splitlines()]
    assert [row['event'] for row in rows] == ['start', 'stop']
    assert rows[-1]['outcome'] == 'completed'
