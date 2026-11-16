"""Portable CPU/Host checks only: no compiler, CUDA invocation or GPU grant.

Historical native measurements are checked against their retained source hash,
not rerun or promoted to runtime qualification by this test file.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from jiuwenswarm.ccv2.ccv2 import Host

ROOT = Path(__file__).resolve().parents[2]
CCS = ROOT / 'jiuwenswarm/factory/ccs'


def implementation(package):
    spec = importlib.util.spec_from_file_location(
        'runtime_method_' + package, CCS / package / 'components/implementation.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def memory_request():
    return dict(alignment=64, tensors=[
        dict(name='attention', bytes=1024, start=0, end=2),
        dict(name='expert', bytes=2048, start=2, end=4),
        dict(name='residual', bytes=512, start=0, end=4)])


def gpu_request():
    return dict(experts=2, rows=2, cols=3, tokens=2, top_k=2,
                weights=[1, 2, 3, 4, 5, 6, -1, 2, -3, 4, -5, 6],
                inputs=[1, 2, 3, -1, -2, -3], routes=[0, 1, 1, 1],
                gates=[0.75, 0.25, 0.25, 0.75])


@pytest.mark.parametrize('package', ['memory_residency_lab', 'gpu_kernel_lab'])
def test_package_standalone_verification_is_cpu_only(package):
    proc = subprocess.run([sys.executable, 'verification.py'], cwd=CCS / package,
                          capture_output=True, text=True, timeout=30, check=True)
    assert json.loads(proc.stdout)['passed'] is True


@pytest.mark.parametrize('capability', ['plan', 'verify'])
def test_memory_tools_work_through_actual_host(tmp_path, capability):
    host = Host(tmp_path / 'store', session_grants=['process.exec'], python=sys.executable)
    release = host.prepare(CCS / 'memory_residency_lab')
    receipt = host.call(release, capability, {'request': memory_request()})
    assert receipt['state'] == 'succeeded', receipt
    result = receipt['outputs']['result']
    assert result['arena_bytes'] == 2560
    assert result['saved_bytes'] == 1024
    assert receipt['effects']['granted'] == ['process.exec']
    if capability == 'verify':
        assert result['correct'] is True and result['allocated_bytes'] == 2560


def test_gpu_cpu_oracle_works_through_actual_host(tmp_path):
    host = Host(tmp_path / 'store', session_grants=['process.exec'], python=sys.executable)
    release = host.prepare(CCS / 'gpu_kernel_lab')
    receipt = host.call(release, 'evaluate', {'request': gpu_request()})
    assert receipt['state'] == 'succeeded', receipt
    assert receipt['outputs']['result']['output'] == [9.0, 27.0, 6.0, -12.0]
    assert receipt['effects']['granted'] == ['process.exec']


def test_cpu_session_cannot_launch_benchmark_even_with_fake_handle(tmp_path):
    host = Host(tmp_path / 'store', session_grants=['process.exec'], python=sys.executable)
    release = host.prepare(CCS / 'gpu_kernel_lab')
    inputs = {'request': gpu_request(), 'gpu': 'fabricated-gpu'}
    denied = host.call(release, 'benchmark', inputs)
    assert denied['reason'] == 'DENIED', denied
    assert denied['state'] != 'succeeded' and denied['outputs'] == {}
    # A caller cannot upgrade session authority by naming the effect itself.
    elevated = host.call(release, 'benchmark', inputs, grants=['process.exec', 'gpu.use'])
    assert elevated['reason'] == 'DENIED', elevated
    # Handle absence cannot make the missing grant disappear either.
    absent = host.call(release, 'benchmark', {'request': gpu_request()})
    assert absent['reason'] == 'DENIED', absent


def test_gpu_effect_and_handle_are_declared_together():
    import yaml
    declaration = yaml.safe_load((CCS / 'gpu_kernel_lab/cc.yaml').read_text())
    cap = declaration['capabilities']['benchmark']
    assert set(cap['changes']) == {'process.exec', 'gpu.use'}
    assert set(cap['needs']) == {'python', 'gpu'}
    assert cap['takes']['gpu']['kind'] == 'handle'
    assert declaration['capabilities']['evaluate']['needs'] == ['python']


def test_raw_benchmark_packet_without_host_resource_cannot_launch():
    packet = dict(capability='benchmark', inputs={'request': gpu_request(), 'gpu': 'fabricated'})
    proc = subprocess.run([sys.executable, str(CCS / 'gpu_kernel_lab/run.py')],
                          input=json.dumps(packet), text=True, capture_output=True,
                          timeout=30, check=True)
    reply = json.loads(proc.stdout)
    assert reply['outcome'] == 'error'
    assert 'host-bound GPU handle' in reply['error']['message']


def test_missing_binaries_fail_before_any_native_subprocess(monkeypatch):
    memory = implementation('memory_residency_lab')
    gpu = implementation('gpu_kernel_lab')

    def forbidden(*args, **kwargs):
        raise AssertionError('native subprocess must not launch')

    monkeypatch.setattr(memory.subprocess, 'run', forbidden)
    monkeypatch.setattr(gpu.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(gpu.platform, 'machine', lambda: 'aarch64')
    with pytest.raises(ValueError, match='native binary is not bundled'):
        memory.native_experiment(memory_request())
    with pytest.raises(ValueError, match='native binary is not bundled'):
        gpu.benchmark(gpu_request())


def test_x86_native_cuda_request_fails_with_clear_scope(monkeypatch):
    gpu = implementation('gpu_kernel_lab')
    monkeypatch.setattr(gpu.platform, 'machine', lambda: 'x86_64')
    with pytest.raises(ValueError, match='qualified only on Linux ARM64 GB10 SM121'):
        gpu.benchmark(gpu_request())


@pytest.mark.parametrize('patch', [
    {'output': [9.0]},
    {'output': [9.0, 27.0, 6.0, -12.0, 0.0]},
    {'output': [9.0, float('nan'), 6.0, -12.0]},
    {'output': [9.0, 27.0, float('inf'), -12.0]},
    {'output': [9.0, True, 6.0, -12.0]},
    {'all_variants_correct': False},
    {'all_variants_correct': 'true'},
    {'serial_route_ms': float('nan')},
    {'best_batched_ms': 0.0},
    {'speedup': float('inf')},
    {'candidate_ms': [0.5, 0.6, 0.7]},
    {'candidate_ms': [0.5, 0.6, 0.7, -1.0]},
    {'native_max_abs_error': float('nan')},
])
def test_malformed_native_return_rejected_without_gpu(monkeypatch, patch):
    gpu = implementation('gpu_kernel_lab')
    monkeypatch.setattr(gpu.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(gpu.platform, 'machine', lambda: 'aarch64')
    monkeypatch.setattr(gpu.Path, 'is_file', lambda self: True)
    header = bytearray(20)
    header[:4] = b'\x7fELF'
    header[5] = 1
    header[18:20] = (183).to_bytes(2, 'little')
    monkeypatch.setattr(gpu.Path, 'read_bytes', lambda self: bytes(header))
    result = dict(output=[9.0, 27.0, 6.0, -12.0], all_variants_correct=True,
                  serial_route_ms=1.0, best_batched_ms=0.5, speedup=2.0,
                  candidate_ms=[0.5, 0.6, 0.7, 0.8], native_max_abs_error=0.0)
    result.update(patch)
    monkeypatch.setattr(gpu.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(stdout=json.dumps(result)))
    with pytest.raises(ValueError):
        gpu.benchmark(gpu_request())


@pytest.mark.parametrize('package,source,binary', [
    ('memory_residency_lab', 'native_arena.cpp', 'native_arena'),
    ('gpu_kernel_lab', 'native_experts.cu', 'native_experts')])
def test_historical_native_result_matches_source_without_shipping_binary(package, source, binary):
    folder = CCS / package
    result = json.loads((folder / 'ROUND1.json').read_text())
    assert hashlib.sha256((folder / source).read_bytes()).hexdigest() == result['source_sha256']
    assert not (folder / binary).exists()
    assert 'not model throughput' in result['scope'] or 'not whole engine memory' in result['scope']
    units = json.loads((folder / 'VERIFICATION-UNITS.json').read_text())
    assert units['runtime_qualified'] is False
