"""Queue integration tests: no evidence, containers, builds, or device access."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

import jiuwenswarm.factory

JOBQ = Path(jiuwenswarm.factory.__file__).with_name('labkit') / 'bin' / 'jobq'


@pytest.fixture
def q(tmp_path):
    fake = tmp_path / 'run_op'
    fake.write_text('#!/usr/bin/env python3\nimport subprocess,sys\na=sys.argv[sys.argv.index("--")+1:]\np=subprocess.Popen(a,start_new_session=True)\nsys.exit(p.wait())\n')
    fake.chmod(0o755)
    env = dict(os.environ, JOBQ_DIR=str(tmp_path / 'state'), JOBQ_RUN_OP=str(fake))
    workers = []

    class Queue:
        def call(self, *args, check=True):
            return subprocess.run([str(JOBQ), *map(str, args)], env=env,
                                  capture_output=True, text=True, check=check, timeout=15)

        def submit(self, cls='cpu', cmd=None, options=()):
            return self.call('submit', '--class', cls, *options, '--',
                             *(cmd or ['true'])).stdout.strip()

        def show(self, jid):
            return json.loads(self.call('show', jid).stdout)

        def worker(self):
            p = subprocess.Popen([str(JOBQ), 'worker', '--once'], env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            workers.append(p)
            return p

        def drain(self):
            self.call('worker', '--once')

        def until(self, jid, predicate):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                j = self.show(jid)
                if predicate(j):
                    return j
                time.sleep(.02)
            pytest.fail('job did not reach expected state: ' + str(j))

    queue = Queue()
    queue.state = tmp_path / "state"
    yield queue
    state = tmp_path / 'state'
    for path in state.glob('job-*.json'):
        j = json.loads(path.read_text())
        for key in ('pgid', 'wrapper_pgid'):
            if j.get(key):
                try:
                    os.killpg(j[key], signal.SIGKILL)
                except ProcessLookupError:
                    pass
    for p in workers:
        if p.poll() is None:
            p.terminate()
        p.communicate(timeout=5)


def test_fifo_and_metadata(q):
    ids = [q.submit('build', ['sleep', '.1'], ['--name', 'ordered']) for _ in range(3)]
    q.drain()
    records = [q.show(i) for i in ids]
    assert all(j['state'] == 'succeeded' and j['rc'] == 0 for j in records)
    assert all(a['end'] <= b['start'] for a, b in zip(records, records[1:]))
    for j in records:
        assert j['argv'] == ['sleep', '.1']
        assert j['pid'] == j['pgid'] and j['pid'] > 0
        assert j['deps'] == [] and j['concurrent_jobs'] == []
        assert j['allow_during_gpu'] is False
    assert ids[0] in q.call('list').stdout
    events = [json.loads(line) for line in (q.state / 'events.jsonl').read_text().splitlines()]
    assert [e['job'] for e in events if e['event'] == 'submitted'] == ids
    assert [e['job'] for e in events if e['event'] == 'succeeded'] == ids


def test_dependencies_success_failure_and_transitive_skip(q):
    good = q.submit()
    bad = q.submit(cmd=['false'])
    child = q.submit(options=['--after', good])
    skipped = q.submit(options=['--after', good, bad])
    grandchild = q.submit(options=['--after', skipped])
    q.drain()
    assert q.show(child)['state'] == 'succeeded'
    assert q.show(child)['start'] >= q.show(good)['end']
    assert q.show(bad)['state'] == 'failed'
    for jid in (skipped, grandchild):
        assert q.show(jid)['state'] == 'skipped_dep_failed'
        assert q.show(jid)['pid'] is None
    assert q.call('submit', '--class', 'cpu', '--after', 'job-abc', '--', 'true', check=False).returncode == 1


def test_gpu_build_exclusion_multiple_workers(q):
    ids = [q.submit(cls, ['sleep', '1']) for cls in ('gpu', 'build')]
    p, other = q.worker(), q.worker()
    assert p.wait(timeout=10) == other.wait(timeout=10) == 0
    a, b = [q.show(i) for i in ids]
    assert a['end'] <= b['start']
    assert a['concurrent_jobs'] == b['concurrent_jobs'] == []


def test_cpu_during_build(q):
    build = q.submit('build', ['sleep', '.6'])
    cpu = q.submit('cpu', ['sleep', '.3'])
    q.drain()
    a, b = q.show(build), q.show(cpu)
    assert a['start'] < b['end'] and b['start'] < a['end']
    assert a['concurrent_jobs'] == [cpu] and b['concurrent_jobs'] == [build]


@pytest.mark.parametrize('cpu_first', [False, True])
def test_cpu_gpu_exclusion_both_directions(q, cpu_first):
    ids = [q.submit(c, ['sleep', '.2']) for c in (('cpu', 'gpu') if cpu_first else ('gpu', 'cpu'))]
    q.drain()
    a, b = [q.show(i) for i in ids]
    assert a['end'] <= b['start']


def test_cpu_opt_in_during_gpu(q):
    gpu = q.submit('gpu', ['sleep', '.5'])
    cpu = q.submit('cpu', ['sleep', '.3'], ['--allow-during-gpu'])
    q.drain()
    assert q.show(cpu)['allow_during_gpu'] is True
    assert q.show(gpu)['concurrent_jobs'] == [cpu]
    assert q.show(cpu)['concurrent_jobs'] == [gpu]


def test_cancel_child_process_group(q, tmp_path):
    child_pid = tmp_path / 'child.pid'
    # Parent reaps its child on TERM, so the assertion checks death, not zombies.
    code = '''import os,signal,subprocess,sys,time
p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"])
def stop(*args):
    p.wait(timeout=3)
    sys.exit(0)
signal.signal(signal.SIGTERM,stop)
open(sys.argv[1],"w").write(str(p.pid))
time.sleep(30)
'''
    jid = q.submit(cmd=[sys.executable, '-c', code, str(child_pid)])
    p = q.worker()
    q.until(jid, lambda j: j['pid'] is not None and child_pid.exists())
    pid = int(child_pid.read_text())
    q.call('cancel', jid)
    assert q.call('wait', jid, '--timeout', '5', check=False).returncode == 1
    assert q.show(jid)['state'] == 'cancelled'
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert p.wait(timeout=5) == 0


def test_queued_cancel_and_wait_codes(q):
    queued = q.submit()
    assert q.call('wait', queued, '--timeout', '.05', check=False).returncode == 2
    q.call('cancel', queued)
    assert q.call('wait', queued, check=False).returncode == 1
    good, bad = q.submit(), q.submit(cmd=['false'])
    q.drain()
    assert q.call('wait', good).returncode == 0
    assert q.call('wait', bad, check=False).returncode == 1
    assert q.show(queued)['state'] == 'cancelled'


def test_job_timeout(q):
    jid = q.submit(cmd=['sleep', '30'], options=['--timeout', '.2'])
    next_job = q.submit('gpu')
    q.drain()
    j = q.show(jid)
    assert j['state'] == 'timeout'
    assert j['end'] - j['start'] < 3
    assert q.show(next_job)['start'] >= j['end']
    assert q.call('wait', jid, check=False).returncode == 1


@pytest.mark.parametrize('reason', ['cancel', 'timeout'])
def test_term_grace_allows_two_second_cleanup(q, tmp_path, reason):
    ready, cleaned = tmp_path / 'ready', tmp_path / 'cleaned'
    code = '''import os,signal,sys,time
from pathlib import Path
def stop(*args):
    time.sleep(2)
    Path(sys.argv[2]).write_text(os.environ['JOBQ_JOB_ID'])
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
Path(sys.argv[1]).write_text('ready')
time.sleep(30)
'''
    options = ['--timeout', '1', '--grace', '3'] if reason == 'timeout' else []
    jid = q.submit(cmd=[sys.executable, '-c', code, str(ready), str(cleaned)], options=options)
    worker = q.worker()
    q.until(jid, lambda j: ready.exists())
    assert q.show(jid)['grace'] == (3 if reason == 'timeout' else 20)
    if reason == 'cancel':
        q.call('cancel', jid)
    assert q.call('wait', jid, '--timeout', '7', check=False).returncode == 1
    job = q.show(jid)
    assert job['state'] == ('cancelled' if reason == 'cancel' else 'timeout')
    assert job['rc'] == 0
    assert cleaned.read_text() == jid
    assert worker.wait(timeout=5) == 0


def test_custom_grace_kills_unresponsive_command(q, tmp_path):
    ready = tmp_path / 'ready'
    code = "import signal,sys,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); open(sys.argv[1], 'w').close(); time.sleep(30)"
    jid = q.submit(cmd=[sys.executable, '-c', code, str(ready)], options=['--grace', '.15'])
    worker = q.worker()
    q.until(jid, lambda j: ready.exists())
    start = time.monotonic()
    q.call('cancel', jid)
    assert q.call('wait', jid, '--timeout', '3', check=False).returncode == 1
    assert .15 <= time.monotonic() - start < 3
    assert q.show(jid)['rc'] != 0
    assert worker.wait(timeout=5) == 0
