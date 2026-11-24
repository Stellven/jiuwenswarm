import json
import sys

import pytest

from jiuwenswarm.factory import spark_engine


def test_non_native_build_refuses_before_commands(tmp_path, monkeypatch):
    out = tmp_path / 'out'
    monkeypatch.setattr(sys, 'argv', ['builder', '--target', 'spark-gb10', '--source', str(tmp_path),
        '--commit', 'a'*40, '--tag', 'factory/strata:test', '--out', str(out),
        '--dependency', str(tmp_path), '--dependency-commit', 'b'*40])
    monkeypatch.setattr(spark_engine.platform, 'machine', lambda: 'x86_64')
    def forbidden(*args, **kwargs):
        pytest.fail('Rejected architecture must not run a command')
    monkeypatch.setattr(spark_engine.subprocess, 'run', forbidden)
    with pytest.raises(ValueError, match='native ARM64'):
        spark_engine.main()
    record = json.loads((out/'build-record.json').read_text())
    assert record['status'] == 'failed'
    assert record['host_architecture'] == 'x86_64'
    assert record['phase_seconds'] == {}
    assert record['build_wall_seconds'] >= 0


def test_native_compile_script_has_valid_python():
    compile(spark_engine.NATIVE_COMPILE, '<native-compile>', 'exec')


def test_llama_target_uses_embedded_ggml_and_server_binary(tmp_path):
    flags=spark_engine.build_flags('llama-server',tmp_path)
    assert '-DGGML_CUDA=ON' in flags
    assert '-DLLAMA_BUILD_SERVER=ON' in flags
    assert not any('STRATA' in value for value in flags)
    assert any('STRATA_GGML_DIR' in value for value in spark_engine.build_flags('strata-dsv41',tmp_path))
    assert "'bin/'+target if target=='llama-server'" in spark_engine.NATIVE_COMPILE
