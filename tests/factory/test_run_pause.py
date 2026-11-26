"""Run-wide operator pause, fixes while paused, and an operator hold on a running node.

Offline controller tests with a scripted facade and fake jobs; not live-agent, image or lab results.
"""
import asyncio
import json

import pytest

from jiuwenswarm.factory import run_pause, scheduler
from jiuwenswarm.factory.cli import format_status, readonly_status
from jiuwenswarm.factory.controller import Controller
from jiuwenswarm.factory.store import ScopeDenied
from jiuwenswarm.factory.taskgraph import operator_patch, plan_get, plan_patch, reconcile, seed_plan

from test_controller import make_task, publish, rig  # noqa: F401 - rig is a fixture
from test_node_contracts import tiny_nodes, write_contract


class StuckJobs:
    """Jobs that keep running: a pause must not wait for or kill them."""
    def __init__(self, store):
        self.store, self.cancelled = store, []

    def status(self, attempt_id):
        return self.store._get('attempts', 't', attempt_id)

    def cancel(self, attempt_id):
        self.cancelled.append(attempt_id)
        return self.store.transition_attempt('t', attempt_id, 'cancel_requested')


def test_pause_and_resume_records_and_pause_md(tmp_path, rig):
    make_task(tmp_path, rig)
    record = rig.pause('t', 'rev 8 is coming')
    assert record['action'] == 'pause' and record['by'] == 'operator' and (rig.home / 'PAUSE.md').exists()
    assert 'rev 8 is coming' in (rig.home / 'PAUSE.md').read_text() and 'jiuwenswarm-factory resume t' in (rig.home / 'PAUSE.md').read_text()
    assert rig.pause('t', 'again')['already'] and len(run_pause.records(rig.store, 't')) == 1
    with pytest.raises(ScopeDenied):  # only the host writes pause records
        rig.store.scoped('t').append_observation('t', dict(kind='operator_pause', values={'action': 'resume'}))
    status = rig.status('t')
    assert status['paused']['reason'] == 'rev 8 is coming' and status['paused']['by'] == 'operator'
    assert 'PAUSED by operator' in format_status(status, plain=True)
    lifted = rig.lift_pause('t', 'rev 8 applied')
    assert lifted['action'] == 'resume' and lifted['pause'] == record['obs_id'] and not (rig.home / 'PAUSE.md').exists()
    assert run_pause.current(rig.store, 't') is None and rig.lift_pause('t') is None
    assert rig.status('t')['paused'] is None and rig.status('t')['pending_operator_notes']  # the agent is told


def test_a_paused_run_stops_before_any_turn_and_resumes(tmp_path, rig):
    make_task(tmp_path, rig)
    calls = []

    async def facade(request):
        calls.append(json.loads(request.params['query']))
        publish(rig, 'accept')
        yield {'event_type': 'chat.final'}
    rig.facade = facade
    rig.pause('t', 'operator looks at the graph')
    result = asyncio.run(rig.run('t'))
    assert result['outcome'] == 'paused' and not calls
    state = rig._load('t')
    assert 'paused by operator' in state['stop_reason'] and 'operator looks at the graph' in state['stop_reason']
    rig.lift_pause('t', 'looked')
    result = asyncio.run(rig.run('t'))
    assert result['outcome'] == 'accept' and len(calls) == 1
    assert any('paused this run and resumed it' in n for n in calls[0]['operator_notes'])


def test_a_pause_while_jobs_run_stops_without_killing_them(tmp_path, rig):
    make_task(tmp_path, rig)
    calls, sleeps = [], []

    async def facade(request):
        calls.append(request)
        publish(rig)
        rig.store.create_attempt('t', dict(attempt_id='a', kind='build', idem_key='i', fingerprint='f', request={}))
        rig.store.transition_attempt('t', 'a', 'running')
        yield {'event_type': 'chat.final'}

    async def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            rig.pause('t', 'stop while the build runs')
    rig.facade, rig.sleep, rig.jobs = facade, sleep, StuckJobs(rig.store)
    result = asyncio.run(rig.run('t'))
    assert result['outcome'] == 'paused' and len(calls) == 1 and len(sleeps) == 2
    assert rig.store._get('attempts', 't', 'a')['state'] == 'running' and not rig.jobs.cancelled
    assert result['pending_attempts'] == ['a']
    # --cancel-jobs goes through the ordinary cancel path.
    rig.lift_pause('t')
    rig.pause('t', 'cancel this time', cancel_jobs=True)
    assert rig.jobs.cancelled == ['a'] and rig.store._get('attempts', 't', 'a')['state'] == 'cancel_requested'


@pytest.fixture
def graph(store, tmp_path):
    store.create_task(dict(task_id='g', objective='o', contract_id=write_contract(tmp_path, tiny_nodes()), constraints={}))
    seed_plan(store, store.get_task('g'))
    store.advance_decision('g', 0, {'hypothesis': 'h'})
    return store


def test_the_scheduler_agent_is_not_started_once_paused(store, tmp_path):
    from test_node_finalize import preliminary_nodes
    store.create_task(dict(task_id='pf', objective='o', contract_id=write_contract(tmp_path, preliminary_nodes()),
                           constraints={}))
    seed_plan(store, store.get_task('pf'))
    calls = []

    def runner(home, task_id, node_id, attempt=1):
        calls.append(node_id)
        controller.pause(task_id, 'pause from outside while the scheduler works')
    controller = Controller(store=store, facade=object(), scheduler=runner)
    state = {}
    assert controller._finalize_pending('pf', state) == [] and calls == ['integrate']
    assert controller._paused('pf', state) and 'pause from outside' in state['stop_reason']


def test_operator_fixes_work_while_paused_and_jobs_of_other_nodes_run(graph):
    controller = Controller(store=graph, facade=object())
    controller.pause('g', 'fix the run')
    graph.create_attempt('g', dict(attempt_id='other', kind='build', idem_key='i', fingerprint='f',
                                   request={'node_id': 'build'}))
    graph.transition_attempt('g', 'other', 'running')
    controller.operator('g', 'hold', 'integrate', 'look first')
    controller.operator('g', 'release', 'integrate', 'looked')
    controller.add_note('g', 'use the new recipe')
    graph.create_attempt('g', dict(attempt_id='old', kind='build', idem_key='j', fingerprint='g', request={'node_id': 'build'}))
    graph.transition_attempt('g', 'old', 'running')
    graph.transition_attempt('g', 'old', 'failed')
    assert scheduler.excuse(graph, 'g', 'old', 'machine was busy')['excused']
    assert controller.revise('g', 'nothing changed in the contract')['changes'] == []  # revise works while paused
    assert run_pause.current(graph, 'g')  # still paused until resumed
    assert 'use the new recipe' in [n['text'] for n in controller.status('g')['pending_operator_notes']]


def test_hold_on_a_running_node_stops_it_from_closing(graph):
    rev = plan_get(graph, 'g')['rev']
    graph.create_attempt('g', dict(attempt_id='a1', kind='build', idem_key='i', fingerprint='f', request={'node_id': 'integrate'}))
    graph.transition_attempt('g', 'a1', 'running')
    plan_patch(graph, 'g', {'update': [dict(node_id='integrate', state='running', attempt_ids=['a1'])]}, rev, 1)
    held = operator_patch(graph, 'g', 'hold', 'integrate', 'operator checks the change before it closes')
    node = next(n for n in held['nodes'] if n['node_id'] == 'integrate')
    assert node['state'] == 'running' and node['hold'].startswith('operator checks')
    graph.transition_attempt('g', 'a1', 'succeeded', result_refs=['g'])
    after = reconcile(graph, 'g', held['rev'], 1)  # the finished job does not close a held node
    assert next(n for n in after['nodes'] if n['node_id'] == 'integrate')['state'] == 'running'
    with pytest.raises(ValueError, match='held by the operator'):
        plan_patch(graph, 'g', {'update': [dict(node_id='integrate', state='done', evidence_ids=['g'])]}, after['rev'], 1)
    work = scheduler.next_work(graph, 'g')
    assert work['waiting']['integrate'].startswith('held by operator') and work['held'] == ['integrate']
    controller = Controller(store=graph, facade=object())
    assert controller.status('g')['held_nodes'] == {'integrate': 'operator checks the change before it closes'}
    assert controller._paused_at('g') == {'integrate': 'held by operator: operator checks the change before it closes'}
    released = operator_patch(graph, 'g', 'release', 'integrate', 'looked')
    closed = reconcile(graph, 'g', released['rev'], 1)  # released: the job result is recorded (checks still owed)
    node = next(n for n in closed['nodes'] if n['node_id'] == 'integrate')
    assert node['state'] == 'blocked' and 'needs a passing node check' in node['reason']


def test_graph_status_script_shows_the_pause_and_pending_notes(graph, monkeypatch, capsys):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / 'scripts/factory/graph_status.py'
    spec = importlib.util.spec_from_file_location('graph_status', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    controller = Controller(store=graph, facade=object())
    controller.pause('g', 'apply rev 8')
    controller.add_note('g', 'rev 8 drops the accuracy node')
    monkeypatch.setenv('FACTORY_HOME', str(graph.home))
    module.main('g', brief=True)
    out = capsys.readouterr().out
    first = out.splitlines()[0]
    assert first.startswith('PAUSED') and 'paused by operator' in first and 'apply rev 8' in first
    assert 'rev 8 drops the accuracy node' in out and 'operator_pause pause operator apply rev 8' in out
    assert '--- PAUSE.md' in out


def test_readonly_status_shows_the_pause(tmp_path, rig):
    make_task(tmp_path, rig)
    rig.pause('t', 'read-only view')
    data = rig.store.dump('t')
    data['_meta'] = {'controller_state': rig._load('t')}
    status = readonly_status(data)
    assert status['paused']['reason'] == 'read-only view'
    assert 'PAUSED by operator' in format_status(status, plain=True)
