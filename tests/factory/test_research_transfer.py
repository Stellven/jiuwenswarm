"""Real CC packet execution against self-contained methodology transfer tools."""
import json
from pathlib import Path
import subprocess
import sys

from jiuwenswarm.ccv2.ccv2 import Host

CC = Path(__file__).resolve().parents[2] / 'jiuwenswarm/factory/ccs/methodology_transfer_lab'


def test_reference_checks():
    subprocess.run([sys.executable, str(CC / 'verification.py')], check=True)


def test_host_all_capabilities(tmp_path):
    host = Host(tmp_path / 'host', session_grants=['process.exec'], python=sys.executable)
    release = host.prepare(CC)
    examples = json.loads((CC / 'EXAMPLES.json').read_text())
    for capability, inputs in examples.items():
        result = host.call(release, capability, inputs)
        assert result['state'] == 'succeeded', result
        assert result['outputs']['result']


def test_host_rejects_invalid_evidence(tmp_path):
    host = Host(tmp_path / 'host', session_grants=['process.exec'], python=sys.executable)
    release = host.prepare(CC)
    result = host.call(release, 'analyze_abba', {'request': {'cells': []}})
    assert result['state'] != 'succeeded'
