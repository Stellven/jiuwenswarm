"""Broker owner survives clients and cleans up timed-out metadata readers."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

from deploy.m1 import rsi_capsule_broker as broker


def test_disconnected_reply_does_not_escape_owner():
    class Closed:
        def sendall(self, raw):
            raise BrokenPipeError('gateway cancelled')
    assert broker.send_reply(Closed(), b'reply\n') is False
    class Connected:
        def sendall(self, raw):
            self.raw = raw
    client = Connected()
    assert broker.send_reply(client, b'reply\n') is True
    assert client.raw == b'reply\n'


@pytest.mark.skipif(os.name != 'posix', reason='Root broker requires POSIX process groups')
def test_preflight_timeout_kills_descendants(tmp_path):
    marker = tmp_path / 'child-pid'
    program = '''import os, pathlib, time
pid = os.fork()
if pid == 0:
    pathlib.Path(__import__('sys').argv[1]).write_text(str(os.getpid()))
    while True: time.sleep(1)
while not pathlib.Path(__import__('sys').argv[1]).exists(): time.sleep(.01)
while True: time.sleep(1)
'''
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        broker.preflight_process([sys.executable, '-c', program, str(marker)], timeout=1, env=os.environ.copy())
    assert time.monotonic() - started < 5
    pid = int(marker.read_text())
    stat = Path('/proc') / str(pid) / 'stat'
    for _ in range(100):
        if not stat.exists() or stat.read_text().split(') ', 1)[1].startswith('Z'):
            break
        time.sleep(.01)
    else:
        pytest.fail('metadata descendant survived preflight timeout')


@pytest.mark.skipif(os.name != 'posix', reason='Root broker requires POSIX process groups')
def test_preflight_failure_preserves_refusal_and_success_output():
    result = broker.preflight_process([sys.executable, '-c', "print('ready')"], timeout=5, env=os.environ.copy())
    assert result.stdout == b'ready\n'
    with pytest.raises(subprocess.CalledProcessError) as error:
        broker.preflight_process([sys.executable, '-c', "import sys; print('PIN_DIFFERS', file=sys.stderr); sys.exit(7)"], timeout=5, env=os.environ.copy())
    assert str(broker.refusal(error.value)) == 'PIN_DIFFERS'
