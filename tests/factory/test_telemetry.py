import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
import pytest
from jiuwenswarm.factory import api, telemetry
from jiuwenswarm.factory.export import export_task, verify
from jiuwenswarm.factory.replay import replay


def invoke(monkeypatch, capsys, store, capability, inputs):
    monkeypatch.setenv('FACTORY_HOME', str(store.home))
    monkeypatch.setenv('FACTORY_TASK_ID', 't')
    monkeypatch.setenv('FACTORY_TURN', '3')
    monkeypatch.setattr(sys, 'argv', ['api', capability])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(dict(capability=capability, inputs=inputs))))
    api.main()
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize('capability,inputs,outcome', [
    ('evidence.query', {}, 'ok'), ('evidence.read', {'id': 'missing'}, 'error'),
    ('evidence.query', {'limit': 99}, 'error'), ('unknown', {}, 'error'),
    ('inspector.inspect', {}, 'error'),
])
def test_every_dispatch(monkeypatch, capsys, store, capability, inputs, outcome):
    result = invoke(monkeypatch, capsys, store, capability, inputs)
    calls = [e for e in telemetry.read_events(store.home) if e['event'] == 'cc.call']
    assert len(calls) == 1
    e = calls[0]
    assert e['capability'] == capability
    assert e['outcome'] == result['outcome'] == outcome
    assert e['turn'] == 3
    assert e['duration_ms'] >= 0
    assert e['error_code'] == result.get('error', {}).get('code')
    if capability.startswith('evidence.'):
        assert e['capsule'] == 'factory.evidence'
        assert e['capsule_version'] == '1.0.0'
        assert len(e['release_sha256']) == 64
    assert e['task_evidence_records'] >= 1


def test_failure_isolated(monkeypatch, capsys, store):
    (store.home / 'telemetry').mkdir(exist_ok=True)
    (store.home / 'telemetry/events.jsonl').mkdir()
    assert invoke(monkeypatch, capsys, store, 'evidence.query', {})['outcome'] == 'ok'
    assert len((store.home / 'telemetry/errors.jsonl').read_text().splitlines()) == 1


def test_sequence_and_fsync(tmp_path, monkeypatch):
    syncs = []
    original = telemetry.os.fsync
    monkeypatch.setattr(telemetry.os, 'fsync', lambda fd: (syncs.append(fd), original(fd)))
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda n: telemetry.emit(tmp_path, 'example', 't', value=n), range(30)))
    rows = telemetry.read_events(tmp_path)
    assert [r['seq'] for r in rows] == list(range(1, 31))
    assert len(syncs) == 30


def test_committed_transitions_and_decisions(store):
    attempt = store.create_attempt('t', dict(kind='build', request={}, idem_key='k', fingerprint='f'))
    aid = attempt['attempt_id']
    store.transition_attempt('t', aid, 'running')
    store.transition_attempt('t', aid, 'succeeded')
    store.advance_decision('t', 0, dict(action=dict(type='accept'), reason_for_change='done'))
    events = telemetry.read_events(store.home)
    jobs = [e for e in events if e['event'] == 'job.transition']
    assert [(e['from'], e['to']) for e in jobs] == [(None, 'queued'), ('queued', 'running'), ('running', 'succeeded')]
    assert jobs[-1]['queue_wait_s'] >= 0 and jobs[-1]['run_s'] >= 0
    assert events[-1]['event'] == 'decision'
    assert events[-1]['reason_length'] == 4


def test_export_slice(store, tmp_path):
    telemetry.emit(store.home, 'example', 't')
    telemetry.emit(store.home, 'example', 'other')
    out = export_task('t', tmp_path / 'bundle', store.home)
    rows = [json.loads(line) for line in (out / 'telemetry.jsonl').read_text().splitlines()]
    assert len(rows) == 1 and rows[0]['task_id'] == 't'
    assert 'telemetry.jsonl' in json.loads((out / 'MANIFEST.json').read_text())
    verify(out)


def test_replay_identical_and_refusal(monkeypatch, capsys, store):
    store.append_observation('t', dict(obs_id='o', values=dict(metric=3)))
    originals = [invoke(monkeypatch, capsys, store, 'evidence.query', {}),
                 invoke(monkeypatch, capsys, store, 'evidence.read', {'id': 'o'})]
    original_bytes = (store.home / 'telemetry/events.jsonl').read_bytes()
    result = replay('t', store.home)
    assert [json.dumps(r, ensure_ascii=False).encode() for r in result['results']] == [json.dumps(r, ensure_ascii=False).encode() for r in originals]
    assert all(e['replay'] for e in result['events'])
    assert (store.home / 'telemetry/events.jsonl').read_bytes() == original_bytes
    with pytest.raises(ValueError, match='refuses'):
        replay('t', store.home, calls=[dict(capability='builder.submit')])


def test_rolled_back_evidence_has_no_event(store):
    before = telemetry.read_events(store.home)
    store.fault = lambda stage: (_ for _ in ()).throw(RuntimeError('fail'))
    with pytest.raises(Exception):
        store.advance_decision('t', 0, {})
    assert telemetry.read_events(store.home) == before


@pytest.mark.asyncio
async def test_turn_stream_metrics(store):
    from jiuwenswarm.factory.controller import Controller
    async def stream(request):
        yield dict(event_type='chat.tool_call', tool_call=dict(tool_call_id='c', name='cc.cc_material', arguments=dict(cc='factory.integration_skill', material='integrate')))
        yield dict(event_type='chat.tool_result', tool_call_id='c', tool_name='cc.cc_material', result=json.dumps(dict(result=dict(content=[dict(type='text', text=json.dumps(dict(cc='factory.integration_skill', material='integrate', text='abc', truncated=False)))]))))
        yield dict(event_type='chat.metadata', usage=dict(input_tokens=12, output_tokens=None))
    controller = Controller(store=store, facade=stream)
    await controller._turn('t', '{}', 2)
    rows = telemetry.read_events(store.home)
    turn = next(e for e in rows if e['event'] == 'agent.turn')
    assert turn['tokens'] == dict(input_tokens=12, output_tokens=None)
    assert turn['tool_calls'] == {'cc.cc_material': 1}
    assert turn['outcome'] == 'ok' and turn['turn'] == 2
    material = next(e for e in rows if e['event'] == 'cc.material')
    assert material['capsule'] == 'factory.integration_skill'
    assert material['bytes'] == 3 and material['path'] is None


@pytest.mark.asyncio
async def test_turn_missing_usage_and_failure(store):
    from jiuwenswarm.factory.controller import Controller
    async def stream(request):
        yield dict(event_type='chat.delta', delta='text')
        raise ValueError('interrupted')
    controller = Controller(store=store, facade=stream)
    with pytest.raises(ValueError):
        await controller._turn('t', '{}', 1)
    turn = telemetry.read_events(store.home)[-1]
    assert turn['event'] == 'agent.turn' and turn['outcome'] == 'error'
    assert turn['tokens'] is None
