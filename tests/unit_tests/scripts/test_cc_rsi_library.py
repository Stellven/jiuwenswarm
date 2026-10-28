"""Closed Root subprocess protocol tests; no installed broker or live Library."""
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).parents[3]
spec = importlib.util.spec_from_file_location('unit_cc_library_publisher', ROOT / 'deploy/m1/rsi_ui_publish.py')
publisher = importlib.util.module_from_spec(spec); spec.loader.exec_module(publisher)
from _ai4r_cc_ui_publish.cc_rsi_library import ProtectedLibraryComposition
from _ai4r_cc_ui_publish.cc_rsi_projection import ProjectionError
import _ai4r_cc_ui_publish.cc_rsi_library as composition_module


def vector():
    composition = ProtectedLibraryComposition.__new__(ProtectedLibraryComposition)
    composition.python = '/unit-only-root-owned/python'
    composition.environment = {'JIUWENSWARM_M1_PROFILE': '1'}
    composition.timeout = 1
    composition.workspace_id = None
    ref = {'id': 'unit-immutable-action', 'sha256': 'a' * 64}
    composition.mapping = {('admit-rsi', json.dumps(ref, sort_keys=True, separators=(',', ':'))): ('b' * 64, 'candidate:' + 'd' * 64)}
    return composition, ref


@pytest.mark.parametrize('fault', [None, 'wrong_hash', 'wrong_ref', 'exit', 'timeout', 'oversize', 'unknown_field'])
def test_closed_child_arguments_and_fail_closed_terminal_validation(monkeypatch, fault):
    composition, ref = vector(); calls = []
    result = {'status': 'admitted_inactive', 'request_ref': ref, 'candidate_hash': 'b' * 64,
              'operator_receipt_ref': {'id': 'unit-real-receipt-contract', 'sha256': 'c' * 64}}
    if fault == 'wrong_hash': result['candidate_hash'] = 'd' * 64
    if fault == 'wrong_ref': result['request_ref'] = dict(ref, id='other')
    if fault == 'unknown_field': result['callback'] = 'forbidden'
    class ProtocolChild:
        def __init__(self, arguments, **options):
            calls.append((arguments, options)); self.killed = False
            options['stdout'].write(b'x' * 65537 if fault == 'oversize' else json.dumps(result).encode())
        def wait(self, timeout=None):
            if fault == 'timeout' and not self.killed: raise subprocess.TimeoutExpired('unit-child', timeout)
            return 2 if fault == 'exit' else 0
        def kill(self): self.killed = True
    monkeypatch.setattr(composition_module.subprocess, 'Popen', ProtocolChild)
    if fault:
        with pytest.raises(ProjectionError): composition.execute('admit-rsi', ref)
    else:
        assert composition.execute('admit-rsi', ref) == result
    arguments, options = calls[0]
    assert arguments[:5] == [composition.python, '-I', '-m', 'jiuwenswarm.research.library_operator', 'admit-rsi']
    assert arguments[-4:] == ['--cc-candidate-hash', 'b' * 64, '--cc-node-id', 'candidate:' + 'd' * 64]
    assert json.loads(arguments[6]) == ref
    assert options['env'] == composition.environment and options['cwd'] == '/'
    assert options['stdin'] == subprocess.DEVNULL and options['close_fds'] is True
    assert options['start_new_session'] is True and 'shell' not in options


def test_unknown_request_and_action_never_spawn(monkeypatch):
    composition, ref = vector()
    def forbidden(*args, **kwargs): pytest.fail('Unknown mapping must never dispatch a process')
    monkeypatch.setattr(composition_module.subprocess, 'Popen', forbidden)
    with pytest.raises(ProjectionError): composition.execute('standing', ref)
    with pytest.raises(ProjectionError): composition.execute('admit-rsi', dict(ref, id='browser-path'))
    with pytest.raises(ProjectionError): composition.preflight('admit', 'f' * 64, ref)
