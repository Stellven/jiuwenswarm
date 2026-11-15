"""Offline accounting and actual native evidence calls; no build/GPU execution."""
import io
import json
from pathlib import Path
import subprocess
import sys

import pytest

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory import cc_job_metrics as metrics, job_packages, telemetry

ROOT = Path(__file__).resolve().parents[2]


def package_call(package='factory.integration_skill', **extra):
    return dict(event='cc.job_call', task_id='t', invoked_capsule=package,
                invoked_capsule_version='1.1.0', invoked_release_sha256='a' * 64,
                invoked_capability='build_submit', backend_capability='builder.submit',
                attempt_id='a', outcome='ok', duration_ms=5, **extra)


def test_package_and_backend_spans_stay_separate():
    events = [package_call(), dict(event='cc.call', capsule='factory.builder', capability='builder.submit',
                                  invoked_capsule='factory.integration_skill', outcome='ok', duration_ms=3)]
    report = metrics.analyze(events)
    assert report['packages'][0]['calls'] == report['backends'][0]['calls'] == 1
    assert report['packages'][0]['duration_ms']['total'] == 5
    assert report['backends'][0]['duration_ms']['total'] == 3
    assert metrics.analyze(events[1:])['packages'] == []  # no reconstructed alias identity


def test_job_join_retry_cache_and_polling():
    call = package_call()
    events = [call, call, dict(call, invoked_capability='build_status', backend_capability='builder.status'),
        dict(event='job.transition', task_id='t', attempt_id='a', kind='build', to='running', queue_wait_s=2),
        dict(event='job.transition', task_id='t', attempt_id='a', kind='build', to='failed', queue_wait_s=2, run_s=9),
        dict(event='build.result', task_id='t', attempt_id='a', record_id='a:build-result', wall_s=8, cache_hit=False)]
    report = metrics.analyze(events, [dict(task_id='t', attempt_id='a', kind='build', state='failed',
                                         history=[{'retry_of': 'prior'}])])
    jobs = report['packages'][0]['jobs']
    assert jobs['attempts'] == jobs['failed'] == 1
    assert jobs['queue_wait_s']['total'] == 2 and jobs['run_s']['total'] == 9
    assert jobs['build_wall_s']['total'] == 8
    assert jobs['base_image_cache'] == dict(hit=0, miss=1, unknown=0)
    assert jobs['retries'] == dict(observed=1, unknown=0)
    assert report['unattributed_jobs']['attempts'] == 0


def test_unknowns_conflicts_and_task_scoping():
    events = [package_call(), package_call('engine.expert_streaming'),
              dict(event='job.transition', task_id='t', attempt_id='a', kind='build', to='failed'),
              dict(event='job.transition', task_id='other', attempt_id='a', kind='build', to='succeeded'),
              dict(event='build.result', task_id='t', record_id='legacy', wall_s=0, cache_hit=True)]
    report = metrics.analyze(events)
    assert report['unattributed_jobs']['attempts'] == 2
    assert report['job_attribution'][1]['ownership'] == 'conflicting'
    assert all(p['jobs']['attempts'] == 0 for p in report['packages'])
    assert report['jobs']['retries'] == dict(observed=0, unknown=2)
    assert report['jobs']['run_s']['total'] is None
    assert report['jobs']['run_s']['unknown'] == 2
    assert report['unlinked_build_results'] == 1


def test_replay_failures_and_invalid_measurements():
    events = [dict(package_call(), outcome='error', error_code='TIMEOUT', duration_ms=None),
              dict(package_call(), outcome='other', duration_ms=float('nan')),
              dict(package_call(), replay=True)]
    report = metrics.analyze(events)
    row = report['packages'][0]
    assert row['calls'] == 2 and row['failed'] == 1 and row['unknown_outcome'] == 1
    assert row['error_codes'] == {'TIMEOUT': 1}
    assert row['duration_ms']['unknown'] == 2 and row['duration_ms']['total'] is None
    assert report['excluded_replay_events'] == 1
    assert metrics.analyze(events, include_replay=True)['packages'][0]['calls'] == 3
    json.dumps(report, allow_nan=False)


def test_snapshot_time_fields_and_retry_denominators():
    report = metrics.analyze([], [dict(task_id='t', attempt_id='a', kind='build', state='succeeded',
        history=[dict(state='queued', created=10)], started=12, ended=19)])
    jobs = report['jobs']
    assert jobs['queue_wait_s']['total'] == 2 and jobs['run_s']['total'] == 7
    assert jobs['retries'] == dict(observed=0, unknown=0)
    assert report['unattributed_jobs']['attempts'] == 1
    assert jobs['build_wall_s']['total'] is None


def test_explicit_loop_child_receipt_owns_child_attempt_only():
    cycle = dict(cycle_id='cycle-1', child_task_id='child', attempt_id='a', state='submitted')
    context = telemetry.attempt_context('factory_loop.execute', {'result': cycle})
    call = dict(package_call(), backend_capability='factory_loop.execute', invoked_capability='execute', **context)
    rows = [call, dict(event='job.transition', task_id='child', attempt_id='a', kind='lab', to='succeeded', run_s=10)]
    report = metrics.analyze(rows)
    assert call['task_id'] == 't' and call['attempt_task_id'] == 'child'
    assert report['packages'][0]['jobs']['succeeded'] == 1
    assert report['job_attribution'][0]['ownership'] == 'loop_child_receipt'
    assert report['packages'][0]['jobs']['run_s']['total'] == 10
    legacy = dict(call)
    legacy.pop('attempt_task_id')
    legacy.pop('attempt_attribution')
    assert metrics.analyze([legacy, rows[1]])['unattributed_jobs']['attempts'] == 1
    assert telemetry.attempt_context('factory_loop.status', {'result': cycle})['attempt_task_id'] is None
    assert telemetry.attempt_context('factory_loop.execute', {'result': {'attempt_id': 'a', 'child_task_id': 'child'}})['attempt_task_id'] is None


def test_bad_informational_context_never_loses_backend_call(store, monkeypatch):
    import time
    monkeypatch.setenv('FACTORY_JOB_TELEMETRY', 'not JSON')
    row = telemetry.call(store.home, 't', 'evidence.query', {}, {'outcome': 'ok'}, time.perf_counter())
    assert row['event'] == 'cc.call' and row['invoked_capsule'] is None


@pytest.mark.parametrize('package,identity', [('integration_skill', 'factory.integration_skill'),
                                              ('expert_streaming', 'engine.expert_streaming')])
def test_real_native_package_attribution(store, tmp_path, monkeypatch, package, identity):
    monkeypatch.setenv('FACTORY_HOME', str(store.home))
    monkeypatch.setenv('FACTORY_TASK_ID', 't')
    monkeypatch.setenv('PYTHONPATH', str(ROOT))
    monkeypatch.delenv('FACTORY_PYTHON', raising=False)
    host = Host(tmp_path / 'ccstore', session_grants=('process.exec',), python=sys.executable)
    release = host.prepare(ROOT / 'jiuwenswarm/factory/ccs' / package)
    result = host.call(release, 'evidence_query', {})
    assert result['state'] == 'succeeded', result
    events = telemetry.read_events(store.home)
    native = next(e for e in events if e['event'] == 'cc.job_call')
    backend = next(e for e in events if e['event'] == 'cc.call')
    assert native['invoked_capsule'] == backend['invoked_capsule'] == identity
    assert native['invoked_release_sha256'] == backend['invoked_release_sha256'] == release
    assert native['invoked_capability'] == backend['invoked_capability'] == 'evidence_query'
    assert backend['capsule'] == 'factory.evidence' and backend['capability'] == 'evidence.query'
    assert backend['call_id'] == native['call_id'] == result['call']
    assert native['duration_ms'] >= backend['duration_ms']
    assert metrics.analyze(events)['packages'][0]['capsule'] == identity


def test_wrapper_timeout_is_recorded_without_backend_event(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('FACTORY_HOME', str(tmp_path))
    monkeypatch.setenv('FACTORY_TASK_ID', 't')
    monkeypatch.delenv('CC_BUNDLE_DIR', raising=False)
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(dict(capability='evidence_query', inputs={}))))
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('fixture', 49)
    monkeypatch.setattr(job_packages.subprocess, 'run', timeout)
    job_packages.main('factory.integration_skill')
    assert json.loads(capsys.readouterr().out)['error']['code'] == 'TIMEOUT'
    event, = telemetry.read_events(tmp_path)
    assert event['event'] == 'cc.job_call' and event['outcome'] == 'error'
    assert event['invoked_release_sha256'] is None and event['invoked_capsule_version'] is None


def test_unsealed_source_does_not_claim_current_package_hash(tmp_path, monkeypatch):
    monkeypatch.setenv('CC_BUNDLE_DIR', str(ROOT / 'jiuwenswarm/factory/ccs/integration_skill'))
    assert job_packages.telemetry_identity('factory.integration_skill', 'inspect')['invoked_release_sha256'] is None
