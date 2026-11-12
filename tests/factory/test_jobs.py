import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from jiuwenswarm.factory.jobs import Jobs, KeyConflict
from conftest import until


def submit(jobs, key='key', request=None, argv=None, timeout=10):
    return jobs.submit('t', 'test', request or {}, key, 'cpu', argv or ['sleep', '.3'], timeout, {})


def test_same_key_same_request_returns_same_job(jobs, isolated_jobq):
    first = submit(jobs)
    second = submit(jobs)
    assert first == second
    assert len(list(isolated_jobq.glob('job-*.json'))) == 1
    job = json.loads(next(isolated_jobq.glob('job-*.json')).read_text())
    env = json.loads(Path(job['env_file']).read_text())
    assert env['PATH'].startswith('/usr/local/cuda/bin:')
    assert env['DOCKER_CMD_PREFIX'] == 'sg docker -c'


def test_same_key_changed_request_conflicts(jobs):
    submit(jobs, request={'a': 1})
    with pytest.raises(KeyConflict):
        submit(jobs, request={'a': 2})


def test_identity_persisted_before_launch(jobs, monkeypatch):
    call = jobs._call
    def inspect(*args, **kwargs):
        attempts = jobs.store.dump('t')['attempts']
        assert len(attempts) == 1
        assert attempts[0]['state'] == 'queued'
        assert attempts[0]['fingerprint'] and attempts[0]['idem_key'] == 'key'
        assert attempts[0]['jobq_id'] is None
        return call(*args, **kwargs)
    monkeypatch.setattr(jobs, '_call', inspect)
    assert submit(jobs)['jobq_id']


def test_submit_returns_fast(jobs):
    started = time.monotonic()
    assert submit(jobs, argv=['sleep', '300'])['state'] == 'queued'
    assert time.monotonic() - started < 2


def test_reconnect_recovers_same_job(jobs, worker):
    first = submit(jobs, argv=['sleep', '1'])
    worker()
    until(jobs, first['attempt_id'], lambda a: a['state'] == 'running')
    other = Jobs(jobs.store)
    assert other.status(first['attempt_id'])['jobq_id'] == first['jobq_id']
    assert until(other, first['attempt_id'])['state'] == 'succeeded'


def test_cancel_observed_no_orphans(jobs, worker, tmp_path):
    ready = tmp_path / 'child'
    code = '''import signal,subprocess,sys,time
p=subprocess.Popen(['sleep','300'])
def stop(*args):
    p.wait(timeout=3)
    sys.exit(0)
signal.signal(signal.SIGTERM,stop)
open(sys.argv[1],'w').write(str(p.pid))
time.sleep(300)
'''
    first = submit(jobs, argv=[sys.executable, '-c', code, str(ready)], timeout=600)
    worker()
    until(jobs, first['attempt_id'], lambda a: ready.exists() and a['owner'].get('pgid'))
    group = jobs.status(first['attempt_id'])['owner']['pgid']
    result = jobs.cancel(first['attempt_id'])
    assert result['state'] == 'cancelled'
    job = json.loads((jobs.jobq_dir / (first['jobq_id'] + '.json')).read_text())
    assert job['state'] == 'cancelled'
    assert any(h['state'] == 'cancel_requested' for h in result['history'])
    assert result['cleanup_state'].startswith('process_groups_reaped')
    for stat in Path('/proc').glob('[0-9]*/stat'):
        try:
            assert int(stat.read_text().rsplit(')', 1)[1].split()[2]) != group
        except (FileNotFoundError, ProcessLookupError):
            pass
    assert not Path('/proc', ready.read_text()).exists()


def test_retry_terminal_only_and_result_gate(jobs, worker):
    first = submit(jobs, argv=[sys.executable, '-c', 'raise SystemExit(1)'])
    with pytest.raises(ValueError):
        jobs.retry(first['attempt_id'], 'next')
    worker()
    assert until(jobs, first['attempt_id'])['state'] == 'failed'
    assert jobs.result(first['attempt_id'])['result_refs'] == []
    retry = jobs.retry(first['attempt_id'], 'next')
    assert retry['attempt_id'] != first['attempt_id']
    assert any(h.get('retry_of') == first['attempt_id'] for h in retry['history'])


def test_missing_job_is_unknown(jobs):
    first = submit(jobs)
    (jobs.jobq_dir / (first['jobq_id'] + '.json')).unlink()
    assert jobs.status(first['attempt_id'])['state'] == 'unknown'


def test_timeout_is_failure_with_detail(jobs, worker):
    first = submit(jobs, argv=['sleep', '300'], timeout=.2)
    worker()
    result = until(jobs, first['attempt_id'])
    assert result['state'] == 'failed'
    assert any(h.get('detail') == 'timeout' for h in result['history'])


def test_lost_launch_ack_recovered(jobs, monkeypatch, isolated_jobq):
    original = jobs._call
    def lose_ack(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError('lost ack')
    monkeypatch.setattr(jobs, '_call', lose_ack)
    first = submit(jobs)
    assert first['jobq_id']
    assert submit(Jobs(jobs.store))['jobq_id'] == first['jobq_id']
    assert len(list(isolated_jobq.glob('job-*.json'))) == 1


def test_external_cancel_from_running(jobs, worker):
    attempt = submit(jobs, argv=['sleep', '300'], timeout=600)
    worker()
    until(jobs, attempt['attempt_id'], lambda a: a['state'] == 'running' and a['owner'].get('pgid'))
    jobs._call('cancel', attempt['jobq_id'])
    # Force the host to miss jobq's intermediate stop_reason update.
    subprocess.run([sys.executable, str(jobs.jobq_bin), 'wait', attempt['jobq_id'], '--timeout', '5'],
                   env=dict(os.environ, JOBQ_DIR=str(jobs.jobq_dir)), capture_output=True)
    assert jobs.status(attempt['attempt_id'])['state'] == 'cancelled'
