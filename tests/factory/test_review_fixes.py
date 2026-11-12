"""F10 regressions use private stores and mocked host operations."""
import json
import signal
import subprocess
from pathlib import Path

import pytest

from jiuwenswarm.factory import api, build_job, contract, export, manager, story
from jiuwenswarm.factory.controller import Controller, scrub
from jiuwenswarm.factory.inspector import Inspector
from jiuwenswarm.factory.jobs import metadata
from jiuwenswarm.factory.store import ScopeDenied, Store


def attempt(store, **changes):
    return store.create_attempt('t', dict(attempt_id='build-1', kind='build', idem_key='k',
        fingerprint='fp', request={}) | changes)


@pytest.mark.parametrize('terminal', ['succeeded', 'failed', 'cancelled'])
def test_missing_job_preserves_terminal(store, jobs, monkeypatch, terminal):
    a = attempt(store, jobq_id='job-missing')
    store.transition_attempt('t', a['attempt_id'], 'running')
    if terminal == 'cancelled':
        store.transition_attempt('t', a['attempt_id'], 'cancel_requested')
    expected = store.transition_attempt('t', a['attempt_id'], terminal)
    def missing(*args, **kwargs):
        raise subprocess.CalledProcessError(1, 'show')
    monkeypatch.setattr(jobs, '_call', missing)
    assert jobs.status(a['attempt_id']) == expected
    with pytest.raises(ValueError, match='transition_attempt'):
        metadata(store, a, state='unknown')


def test_unknown_to_queued_uses_transition(store, jobs, monkeypatch):
    a = attempt(store, jobq_id='job-existing')
    store.transition_attempt('t', a['attempt_id'], 'unknown')
    monkeypatch.setattr(jobs, '_call', lambda *a, **kw: subprocess.CompletedProcess([], 0, '{"state":"queued"}'))
    result = jobs.status(a['attempt_id'])
    assert result['state'] == 'queued'
    assert result['history'][-1]['previous'] == 'unknown'


@pytest.mark.parametrize('kind,id_key', [('artifact', 'artifact_id'), ('observation', 'obs_id')])
@pytest.mark.parametrize('reserved', ['admission-spoof', 'fake:receipt', 'build-1-spoof'])
def test_agent_cannot_claim_host_ids(store, kind, id_key, reserved):
    attempt(store)
    record = {id_key: reserved}
    if kind == 'artifact':
        record['text'] = 'spoof'
    with pytest.raises(ScopeDenied, match='reserved'):
        api.dispatch(store, 't', 'evidence.publish', {'inputs': {'type': kind, 'record': record}})


@pytest.mark.parametrize('record', [{'host_run': {}}, *({'kind': k} for k in
    ['build_result', 'lab_result', 'evaluation', 'admission', 'operator_intervention'])])
def test_agent_cannot_claim_host_observation(store, record):
    with pytest.raises(ScopeDenied, match='reserved'):
        store.scoped('t').append_observation('t', record)


@pytest.mark.parametrize('action', ['accept', 'reject', 'report_inconclusive', 'inspect'])
def test_decision_refuses_dangling_evidence(store, action):
    with pytest.raises(ValueError, match='Unknown or inaccessible evidence id: missing'):
        store.advance_decision('t', 0, dict(action={'type': action}, evidence_ids=['missing']))
    assert store.get_task('t')['current_decision_rev'] == 0


def test_decision_evidence_read_grant(store):
    store.create_task(dict(task_id='prior', objective='earlier'))
    store.append_observation('prior', dict(obs_id='prior-obs'))
    with pytest.raises(ValueError, match='inaccessible'):
        store.scoped('t').advance_decision('t', 0, {'evidence_ids': ['prior-obs']})
    assert store.scoped('t', {'prior'}).advance_decision('t', 0,
        {'evidence_ids': ['prior-obs']})['rev'] == 1


def test_submit_failure_records_stderr(store, jobs, monkeypatch):
    reason = 'x' * 2500 + 'queue rejected'
    def fail(*a, **kw):
        raise subprocess.CalledProcessError(2, 'submit', stderr=reason)
    monkeypatch.setattr(jobs, '_call', fail)
    monkeypatch.setattr(jobs, '_recover', lambda a: pytest.fail('definite rejection recovered'))
    a = jobs.submit('t', 'build', {}, 'k', 'cpu', ['true'], 10, {})
    assert a['state'] == 'failed'
    assert a['resources']['submit_error'] == reason[-2000:]
    assert a['resources']['error'] == reason[-2000:]


@pytest.mark.parametrize('error', [OSError('offline'), subprocess.TimeoutExpired('submit', 1)])
def test_submit_uncertain_recovers(jobs, monkeypatch, error):
    def fail(*a, **kw):
        raise error
    monkeypatch.setattr(jobs, '_call', fail)
    assert jobs.submit('t', 'build', {}, 'k', 'cpu', ['true'], 10, {})['state'] == 'unknown'


def test_cancel_bounded_wait(store, jobs, monkeypatch):
    a = attempt(store, jobq_id='job-stuck')
    monkeypatch.setattr(jobs, 'status', lambda id: store.read('t', id))
    monkeypatch.setattr(jobs, '_call', lambda *a, **kw: None)
    assert jobs.cancel(a['attempt_id'], timeout_s=0)['state'] == 'cancel_requested'
    assert store.read('t', a['attempt_id'])['state'] == 'cancel_requested'


def test_redactor_preserves_metrics_and_words(monkeypatch):
    data = b'task-abcdefgh disk-space-low user@localhost'
    assert export.scrub_bytes(data) == data
    metrics = dict(eval_ms_per_token=745, max_tokens='1', min_tokens='0', next_token='42')
    assert scrub(metrics) == metrics == export.sanitize(metrics)
    for key in ('access_token', 'refresh_token', 'id_token', 'api_key', 'authorization', 'password', 'secret'):
        assert scrub({key: 'credential'})[key] == '<redacted>'
    assert scrub({'custom_token': 'a' * 24})['custom_token'] == '<redacted>'
    assert export.scrub_bytes(b'task-' + b'a'*30) == b'task-' + b'a'*30
    assert export.scrub_bytes(b'sk-' + b'a'*20) == b'<redacted>'
    assert export.scrub_bytes(b'user@example.org') == b'<redacted>'
    monkeypatch.setenv('API_KEY', 'private-test-value')
    assert api.input_reason(ValueError('bad private-test-value')) == 'bad <redacted>'


def test_export_extra_file_no_task_name_special_case(store, tmp_path, monkeypatch):
    monkeypatch.setattr(export, 'command', lambda args: {'available': False})
    extra = tmp_path / 'receipt.jsonl'
    extra.write_text('operator evidence')
    out = export.export_task('t', tmp_path / 'bundle', store.home, [extra])
    assert (out / extra.name).read_text() == 'operator evidence'
    assert export.verify(out)


def test_controller_cancel_reaps_lab(store, monkeypatch):
    a = attempt(store, kind='lab')
    calls = []
    monkeypatch.setattr(manager.Manager, 'cancel', lambda self, id: calls.append(id) or {'state': 'cancelled'})
    controller = Controller(store=store)
    assert controller.cancel('t') == [{'state': 'cancelled'}]
    assert calls == [a['attempt_id']]


def test_retry_spool_isolates_bad_manifests(store, tmp_path, monkeypatch):
    m = manager.Manager(store, tmp_path / 'spool')
    for name, data in [('bad', '{'), ('good', '{"task_id":"t","lab_run_id":"good"}')]:
        root = m.spool_root / name
        root.mkdir()
        (root / 'manifest.json').write_text(data)
    monkeypatch.setattr(m, 'ingest_upload', lambda *a: {'ok': True})
    result = m.retry_spool()
    assert result[0]['lab_run_id'] == 'bad'
    assert 'Expecting' in result[0]['error']
    assert result[1] == {'ok': True}
    monkeypatch.setattr(m, 'ingest_upload', lambda *a: (_ for _ in ()).throw(ValueError('z'*400)))
    assert m.retry_spool()[1]['error'] == 'z'*200


def worker_request():
    return dict(engine_sha256='unused', recipe_sha256='unused', tag='factory/llamacpp:test',
                source={'commit': 'c', 'tree': 't'})


@pytest.mark.parametrize('existing', ['empty', 'occupied', 'mkdir_error', 'sigterm'])
def test_build_worker_finally_records_result(store, monkeypatch, existing):
    request = worker_request()
    a = attempt(store, request=request)
    root = store.home / 'builds' / a['attempt_id']
    root.mkdir(parents=True)
    if existing == 'occupied':
        (root / 'keep').write_text('untouched')
    if existing == 'mkdir_error':
        original = Path.mkdir
        def mkdir(path, *args, **kw):
            if path == root:
                raise OSError('directory unavailable')
            return original(path, *args, **kw)
        monkeypatch.setattr(Path, 'mkdir', mkdir)
    elif existing == 'sigterm':
        def interrupted(*a, **kw):
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        monkeypatch.setattr(Path, 'read_bytes', interrupted)
    if existing == 'sigterm':
        with pytest.raises(SystemExit):
            build_job.run(store, 't', a['attempt_id'], request)
    else:
        assert build_job.run(store, 't', a['attempt_id'], request) == 1
    assert store.read('t', a['attempt_id'] + ':build-result')['kind'] == 'build_result'
    if existing == 'occupied':
        assert (root / 'keep').read_text() == 'untouched'
        assert len(list(root.parent.iterdir())) == 2


@pytest.mark.parametrize('stage', ['artifact', 'queued', 'running', 'succeeded'])
def test_freeze_reference_recovers_partial_import(store, tmp_path, monkeypatch, stage):
    image_id = 'sha256:' + 'a'*64
    c = contract.Contract(contract_id='fixture', reference={'stdout_sha256': None, 'image_tag': 'baseline', 'image_id': image_id})
    record = tmp_path / 'build-record.json'
    record.write_text(json.dumps({'image': {'Id': image_id}}))
    monkeypatch.setattr(manager, 'BASELINE_RECORD', record)
    monkeypatch.setattr(contract, 'load', lambda id: c)
    m = manager.Manager(store, tmp_path / 'spool')
    store.create_task(dict(task_id='reference-fixture', objective='reference'))
    key = 'reference-build-receipt'
    if stage != 'artifact':
        store.create_attempt('reference-fixture', dict(attempt_id=key, kind='build', idem_key=key, fingerprint='fp', request={}))
        if stage in {'running', 'succeeded'}:
            store.transition_attempt('reference-fixture', key, 'running')
        if stage == 'succeeded':
            store.transition_attempt('reference-fixture', key, 'succeeded')
    original_create = store.create_attempt
    def create_after_receipt(task, record):
        assert store.artifact_bytes(task, key + ':receipt')
        return original_create(task, record)
    monkeypatch.setattr(store, 'create_attempt', create_after_receipt)
    class Done(Exception):
        pass
    def admitted(task, image, aid):
        assert store.read(task, aid)['state'] == 'succeeded'
        assert json.loads(store.artifact_bytes(task, aid + ':receipt'))['image_id'] == image_id
        raise Done
    monkeypatch.setattr(m, 'admit', admitted)
    with pytest.raises(Done):
        manager.freeze_reference(m, 'fixture', 'baseline')


def test_preflight_cache_uses_store_home(store, tmp_path, monkeypatch):
    monkeypatch.setenv('FACTORY_HOME', str(tmp_path / 'forbidden'))
    monkeypatch.setattr(Inspector, 'image', lambda self, image: {'id': 'sha256:test'})
    monkeypatch.setattr(Inspector, 'container', lambda *a, **kw: subprocess.CompletedProcess([], 0, '--help', ''))
    result = __import__('jiuwenswarm.factory.inspector', fromlist=['dispatch']).dispatch(
        store.scoped('t'), 't', 'inspector.preflight', {'inputs': {'image': {}, 'tool': 'llama-completion', 'argv': ['--help']}})
    assert result['outcome'] == 'ok'
    assert list((store.home / 'preflight').glob('*.txt'))
    assert not (tmp_path / 'forbidden').exists()


def test_contract_identifier_does_not_shadow_cwd(tmp_path, monkeypatch):
    data = dict(contract_id='example', version=1, tolerance='byte-identical stdout',
                reference={'stdout_sha256': None, 'image_id': 'image'})
    directory = tmp_path / 'contracts'
    directory.mkdir()
    path = directory / 'example.json'
    path.write_text(json.dumps(data))
    (tmp_path / 'example').write_text('invalid shadow')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(contract, 'CONTRACTS', directory)
    assert contract.load('example').path == path
    with pytest.raises(ValueError, match='explicit'):
        contract.freeze('example', {})
    run = dict(execution_outcome='ok', evidence_completeness='complete', image_id='image',
               stdout_sha256='a'*64, run_ref='run')
    contract.freeze(path, run)
    assert contract.load(path)['reference']['stdout_sha256'] == 'a'*64


def test_reuse_schema_migrates_on_store_open(store):
    store._db.execute('DROP TABLE builder_reuse_keys')
    with Store(store.home) as reopened:
        assert reopened._db.execute('SELECT * FROM builder_reuse_keys').fetchall() == []


def test_story_terminal_boundary_and_effective_summary():
    event = dict(created=0, rev=1, mark='✓', kind='accept', summary=('long evidence:stdout word ' * 100))
    lines = story.event_lines(event, 0)
    assert len(lines) == 3
    assert lines[-1].endswith('…')
    assert ':stdo…' not in '\n'.join(lines)
    from jiuwenswarm.factory.effective_config import DEFAULTS
    data = dict(tasks=[{}], observations=[dict(obs_id='o', created=0, kind='inspector.verify_effective_config',
        values={'effective': DEFAULTS | {'fill': '1', 'pregate': '1'}, 'requested': {'LLAMA_EXPERT_PREGATE_K': '8'}})])
    event = story.build_events(data)[0]
    assert 'k=8' in event['summary'] and 'fill=1' in event['summary']
    assert 'threads=' not in event['summary']
    assert len(story.event_lines(event, 0)) == 1


def test_config_environment_overrides(tmp_path, monkeypatch):
    import os
    import sys
    monkeypatch.setenv('SIMINFENG_ROOT', str(tmp_path))
    monkeypatch.setenv('FACTORY_MIN_AVAIL_MIB', '700')
    monkeypatch.setenv('DOCKER_PREFIX', 'custom docker -c')
    output = subprocess.check_output([sys.executable, '-c',
        'import json; from jiuwenswarm.factory import config as c; '
        'print(json.dumps([str(c.JOBQ_BIN), str(c.ENGINE), c.MIN_AVAIL_MIB, c.DOCKER_PREFIX]))'],
        text=True, env=os.environ)
    assert json.loads(output) == [str(tmp_path / 'bin/jobq'),
        str(tmp_path / 'cc/build_engine/build_engine.py'), 700, 'custom docker -c']
