"""Offline work-graph checks: fake durable states, no live agent/Docker/GPU."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

import pytest

from jiuwenswarm.factory.store import NotFound, PersistenceFailed, ScopeDenied, StaleRevision, Store
from jiuwenswarm.factory.taskgraph import (
    from_records, initial_plan, plan_get, plan_patch, reconcile, reconcile_patch,
    replay, seed_plan, to_json,
)
from jiuwenswarm.factory.telemetry import read_events

ROOT = Path(__file__).resolve().parents[2]
CC = ROOT / 'jiuwenswarm/factory/ccs/evidence'


@pytest.fixture
def graph_store(store):
    store.advance_decision('t', 0, {'hypothesis': 'inspect before building'})
    return store


def node(key, **changes):
    return dict(node_id=key, kind='inspect', title=key) | changes


def patch(store, value, rev=0, decision=1):
    return plan_patch(store, 't', value, rev, decision)


def test_reject_cycle_and_missing_dependency(graph_store):
    for nodes in ([node('a', depends_on=['b']), node('b', depends_on=['a'])],
                  [node('a', depends_on=['absent'])]):
        with pytest.raises(ValueError, match='cycle|dependency'):
            patch(graph_store, {'add': nodes})
        assert plan_get(graph_store, 't')['rev'] == 0


def test_cas_replay_decision_and_immutable_history(graph_store):
    graph = patch(graph_store, {'add': [node('a'), node('b', depends_on=['a'])]})
    with pytest.raises(StaleRevision):
        patch(graph_store, {'cancel': [{'node_id': 'a', 'reason': 'stale'}]})
    first = to_json(graph)
    graph = patch(graph_store, {'update': [{'node_id': 'a', 'state': 'done', 'evidence_ids': ['t']}]}, 1)
    assert graph['ready_frontier'] == ['b']
    assert plan_get(graph_store, 't', 1) == first
    assert replay('t', graph['history']) == graph == plan_get(graph_store, 't')
    assert from_records(graph_store.dump('t')) == graph
    with Store(graph_store.home) as reopened:
        assert plan_get(reopened, 't') == graph
        with pytest.raises(StaleRevision):
            patch(reopened, {'add': [node('stale-writer')]}, 1)
    record = graph_store.read('t', 't:plan:2')
    assert record['values']['decision_rev'] == 1
    assert record['values']['patch']['update'][0]['node_id'] == 'a'
    with pytest.raises(sqlite3.IntegrityError, match='immutable'):
        graph_store._db.execute("UPDATE observations SET kind='other' WHERE obs_id='t:plan:2'")
    events = [e for e in read_events(graph_store.home, 't') if e['event'] == 'plan.patch']
    assert [e['graph_rev'] for e in events] == [1, 2]
    assert all(e['schema'] == 'factory.telemetry/1' and e['decision_rev'] == 1 for e in events)


def test_done_requires_evidence_and_jobs_require_attempts(graph_store):
    with pytest.raises(ValueError, match='evidence_ids'):
        patch(graph_store, {'add': [node('a', state='done')]})
    with pytest.raises(ValueError, match='attempt_ids'):
        patch(graph_store, {'add': [node('a', kind='build', state='running')]})
    with pytest.raises(ValueError, match='Unknown or inaccessible'):
        patch(graph_store, {'add': [node('a', state='done', evidence_ids=['unrecorded'])]})
    with pytest.raises(ValueError, match='decision revision'):
        patch(graph_store, {'add': [node('a')]}, decision=2)
    assert plan_get(graph_store, 't')['rev'] == 0


def test_readiness_terminal_supersede_retry_and_reorder(graph_store):
    graph = patch(graph_store, {'add': [node('a'), node('b', depends_on=['a']), node('c')]})
    assert graph['ready_frontier'] == ['a', 'c']
    assert 'a is proposed' in graph['blocked_reasons']['b'][0]
    with pytest.raises(ValueError, match='dependencies'):
        patch(graph_store, {'update': [{'node_id': 'b', 'state': 'ready'}]}, 1)
    graph = patch(graph_store, {
        'add': [node('replacement')],
        'supersede': [{'node_id': 'a', 'by': 'replacement', 'reason': 'evidence changed the approach'}],
        'update': [{'node_id': 'b', 'depends_on': ['replacement']}],
        'cancel': [{'node_id': 'c', 'reason': 'no longer needed'}]}, 1)
    for key in ('a', 'c'):
        with pytest.raises(ValueError, match='terminal'):
            patch(graph_store, {'update': [{'node_id': key, 'state': 'proposed'}]}, 2)
    graph = patch(graph_store, {'update': [{'node_id': 'replacement', 'state': 'failed'}]}, 2)
    graph = patch(graph_store, {'update': [{'node_id': 'replacement', 'state': 'ready'}]}, 3)
    assert graph['ready_frontier'] == ['replacement']
    assert graph['nodes'][0]['superseded_by'] == 'replacement'


def test_task_scope_and_reserved_records(graph_store):
    graph_store.create_task({'task_id': 'other', 'objective': 'other'})
    scoped = graph_store.scoped('t', {'other'})
    assert plan_get(scoped, 'other')['rev'] == 0
    with pytest.raises(ScopeDenied):
        plan_patch(scoped, 'other', {'add': [node('a')]}, 0, 1)
    with pytest.raises(ScopeDenied):
        plan_get(graph_store.scoped('t'), 'other')
    with pytest.raises(ScopeDenied):
        scoped.append_observation('t', {'kind': 'taskgraph_patch', 'values': {}})
    other = graph_store.create_attempt('other', dict(kind='build', idem_key='x', fingerprint='x', request={}))
    with pytest.raises(NotFound, match='not found'):
        patch(graph_store, {'add': [node('a', attempt_ids=[other['attempt_id']])]})


def test_atomic_decision_patch_and_failure_rollback(graph_store):
    store = graph_store
    decision = store.advance_decision('t', 1, dict(plan_patch={'add': [node('a')]}, expected_graph_rev=0))
    assert decision['rev'] == 2
    assert plan_get(store, 't')['history'][0]['decision_rev'] == 2
    assert store.read('t', decision['decision_id'])['plan_patch'] == decision['plan_patch']
    before = store.dump('t')
    events = read_events(store.home)
    for record, error in [
        (dict(plan_patch={'add': [node('b')]}, expected_graph_rev=0), StaleRevision),
        (dict(plan_patch={'add': [node('b', state='done')]}, expected_graph_rev=1), ValueError),
        (dict(plan_patch={'add': [node('b')]}), ValueError),
    ]:
        with pytest.raises(error):
            store.advance_decision('t', 2, record)
        assert store.dump('t') == before
        assert read_events(store.home) == events
    store.fault = lambda stage: (_ for _ in ()).throw(RuntimeError('interrupted'))
    try:
        with pytest.raises(PersistenceFailed):
            store.advance_decision('t', 2, dict(plan_patch={'add': [node('b')]}, expected_graph_rev=1))
    finally:
        store.fault = None
    assert store.dump('t') == before
    assert read_events(store.home) == events


def test_initial_plan_proposed_only_and_controller_init(store, tmp_path):
    task = store.get_task('t')
    suggestion = initial_plan(task)
    assert suggestion == initial_plan(task)
    assert all(n['state'] == 'proposed' and not n['attempt_ids'] and not n['evidence_ids'] for n in suggestion['add'])
    graph = seed_plan(store, task)
    assert graph['history'][0]['decision_rev'] == 0
    assert graph['ready_frontier'] == ['inspect']
    with pytest.raises(ValueError, match='decision revision'):
        patch(store, {'add': [node('invented')]}, rev=1, decision=0)
    from jiuwenswarm.factory.controller import Controller
    from tests.factory.test_controller import make_task
    controller = Controller(tmp_path / 'controller')
    try:
        make_task(tmp_path, controller)
        assert plan_get(controller.store, 't')['nodes'][0]['state'] == 'proposed'
    finally:
        controller.store.close()


def test_reconcile_fake_job_states_and_retry(graph_store):
    store = graph_store
    attempt = store.create_attempt('t', dict(attempt_id='job', kind='build', idem_key='j', fingerprint='j', request={}))
    graph = patch(store, {'add': [node('build', kind='build', attempt_ids=['job'])]})
    changes = reconcile_patch(graph, {'job': dict(attempt, state='failed')})
    assert changes['update'][0]['state'] == 'failed'
    changes = reconcile_patch(graph, {'job': dict(attempt, state='succeeded')})
    assert changes['update'][0]['state'] == 'blocked'
    assert 'evidence' in changes['update'][0]['reason']
    store.transition_attempt('t', 'job', 'running')
    graph = reconcile(store, 't', 1, 1)
    assert graph['nodes'][0]['state'] == 'running'
    store.append_observation('t', {'obs_id': 'result', 'values': {'build': 'offline fixture'}})
    store.transition_attempt('t', 'job', 'succeeded', result_refs=['result'])
    graph = reconcile(store, 't', 2, 1)
    assert graph['nodes'][0]['state'] == 'done'
    assert graph['nodes'][0]['evidence_ids'] == ['result']
    assert reconcile(store, 't', 3, 1) == graph  # no new patch for identical evidence
    with pytest.raises(StaleRevision):
        reconcile(store, 't', 2, 1)
    # Retried work follows its latest attempt, retaining old attempt links.
    again = store.create_attempt('t', dict(attempt_id='retry', kind='build', idem_key='r', fingerprint='r', request={}))
    graph = patch(store, {'update': [{'node_id': 'build', 'state': 'ready', 'attempt_ids': ['retry']}]}, 3)
    assert graph['nodes'][0]['attempt_ids'] == ['job', 'retry']
    changes = reconcile_patch(graph, {'job': dict(attempt, state='failed'), 'retry': dict(again, state='running')})
    assert changes['update'][0]['state'] == 'running'
    changes = reconcile_patch(graph, {'retry': dict(again, state='succeeded')})
    assert changes['update'][0]['state'] == 'blocked'  # previous attempt evidence is insufficient


def test_reconcile_dependency_chain_in_one_patch(graph_store):
    store = graph_store
    for aid in ('a', 'b'):
        store.create_attempt('t', dict(attempt_id=aid, kind='build', idem_key=aid, fingerprint=aid, request={}))
        store.transition_attempt('t', aid, 'running')
        store.transition_attempt('t', aid, 'succeeded', result_refs=['t'])
    graph = patch(store, {'add': [node('parent', kind='build', attempt_ids=['a']),
        node('child', kind='build', attempt_ids=['b'], depends_on=['parent'])]})
    graph = reconcile(store, 't', graph['rev'], 1)
    assert [n['state'] for n in graph['nodes']] == ['done', 'done']
    assert len(graph['history']) == 2
    changes = reconcile_patch(graph, {'a': {'state': 'failed'},
                                      'b': {'state': 'succeeded', 'result_refs': ['t']}})
    assert [n['state'] for n in changes['update']] == ['failed', 'blocked']


def test_cli_formats_history_and_monitor(graph_store, capsys):
    graph = patch(graph_store, {'add': [node('a'), node('b', depends_on=['a'])]})
    patch(graph_store, {'cancel': [{'node_id': 'b', 'reason': 'bounded scope'}]}, 1)
    from jiuwenswarm.factory.cli import main
    for option in ([], ['--dot'], ['--json']):
        main(['--home', str(graph_store.home), 'plan', 't', '--rev', '1', *option])
        output = capsys.readouterr().out
        if option == ['--json']:
            assert json.loads(output) == graph
        elif option == ['--dot']:
            assert 'digraph factory_plan' in output and '"a" -> "b"' in output
            assert 'decision 1' in output
        else:
            assert '[proposed] a' in output and 'graph 1 ← decision 1' in output
    from tests.factory.test_monitor import wire_get
    response = json.loads(wire_get(graph_store.home, '/api/plan?task=t'))
    assert response == to_json(plan_get(graph_store, 't'))
    from jiuwenswarm.factory.story import render_story, load_source
    assert 'graph rev 2' in render_story(load_source('t', graph_store.home), plain=True)


def test_native_capsule_plan_calls(graph_store, tmp_path, monkeypatch):
    monkeypatch.setenv('FACTORY_HOME', str(graph_store.home))
    monkeypatch.setenv('FACTORY_TASK_ID', 't')
    monkeypatch.setenv('FACTORY_READ_TASKS', '')
    monkeypatch.setenv('FACTORY_PYTHON', sys.executable)
    monkeypatch.setenv('PYTHONPATH', str(ROOT))
    def native(cap, inputs):
        started = time.perf_counter()
        result = subprocess.run([sys.executable, str(CC / 'run.py')], input=json.dumps(dict(capability=cap, inputs=inputs)),
                                capture_output=True, text=True, timeout=5, env=os.environ)
        assert result.returncode == 0 and not result.stderr, result.stderr
        assert time.perf_counter() - started < 1
        return json.loads(result.stdout)
    result = native('plan_patch', dict(patch={'add': [node('a')]}, expected_graph_rev=0, decision_rev=1))
    assert result['outcome'] == 'ok'
    assert native('plan_get', {})['outputs']['plan'] == result['outputs']['plan']
    assert native('plan_get', {'rev': 0})['outputs']['plan']['nodes'] == []
    assert native('plan_patch', dict(patch={'add': [node('b')]}, expected_graph_rev=0, decision_rev=1))['error']['code'] == 'STALE_REVISION'
    # Exercise native declaration/receipts too: no special bypass in run.py.
    from jiuwenswarm.ccv2.ccv2 import Host
    host = Host(tmp_path / 'host', session_grants=['process.exec'])
    receipt = host.call(host.prepare(CC), 'plan_get', {})
    assert receipt['state'] == 'succeeded', receipt
    assert receipt['outputs']['plan']['rev'] == 1
    receipt = host.call(host.prepare(CC), 'plan_patch', dict(
        patch={'add': [node('b', depends_on=['a'])]}, expected_graph_rev=1, decision_rev=1))
    assert receipt['state'] == 'succeeded', receipt
    assert receipt['outputs']['plan']['blocked_reasons']['b']
