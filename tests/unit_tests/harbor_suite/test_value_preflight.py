import json
from pathlib import Path
import subprocess

import pytest

from benchmarks.harbor_suite import value_preflight


def test_timeout_retains_logs_and_blocked_receipt(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 180, output=b'partial stdout', stderr=b'partial stderr')
    monkeypatch.setattr(value_preflight.subprocess, 'run', timeout)
    output = tmp_path / 'attempt'
    assert value_preflight.main(['--layer', 'release', '--output', str(output)]) == 2
    result = json.loads((output / 'result.json').read_text())
    assert result['status'] == 'blocked' and result['exit_code'] == 124
    assert (output / 'stdout.txt').read_text() == 'partial stdout'
    assert 'partial stderr' in (output / 'stderr.txt').read_text()
    assert result['model_calls'] == 0


def test_offline_command_disables_expensive_coverage_and_pins_sources(tmp_path, monkeypatch):
    def run(command, **kwargs):
        assert command[command.index('-o') + 1] == 'addopts='
        assert '--noconftest' in command and 'no:cacheprovider' in command
        junit = next(arg.split('=', 1)[1] for arg in command if arg.startswith('--junitxml='))
        Path(junit).write_text('<testsuites><testsuite><testcase classname="offline" name="control" time="0.01"/></testsuite></testsuites>')
        return subprocess.CompletedProcess(command, 0, 'one controlled test', '')
    monkeypatch.setattr(value_preflight.subprocess, 'run', run)
    output = tmp_path / 'attempt'
    assert value_preflight.main(['--layer', 'release', '--output', str(output)]) == 0
    result = json.loads((output / 'result.json').read_text())
    assert result['passed'] == 1 and result['source_pins'] == result['source_pins_before']
    assert result['source_changed_during_check'] is False


def test_existing_attempt_is_never_overwritten(tmp_path):
    output = tmp_path / 'attempt'
    output.mkdir()
    with pytest.raises(FileExistsError):
        value_preflight.main(['--output', str(output)])
