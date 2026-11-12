"""Offline controller unit tests: scripted facade and fake durable jobs.

These are not live-agent, image, Docker or GPU results.
"""
import asyncio
import json
from pathlib import Path
import tomllib

import pytest

from jiuwenswarm.factory.api import dispatch
from jiuwenswarm.factory.controller import Controller, configure_agent

SENTINEL = 'PRODUCER_SECRET_SENTINEL_DO_NOT_SUMMARIZE'


class FakeJobs:
    def __init__(self, store, calls):
        self.store, self.calls = store, calls
        self.polls = 0

    def status(self, attempt_id):
        self.polls += 1
        # Both status calls happen between facade turns, never as model calls.
        assert len(self.calls) == 1
        state = 'running' if self.polls == 1 else 'succeeded'
        return self.store.transition_attempt('t', attempt_id, state)

    def cancel(self, attempt_id):
        return self.store.transition_attempt('t', attempt_id, 'cancel_requested')


def make_task(tmp_path, controller, max_turns=3, wall_clock_s=100):
    task = dict(task_id='t', objective='Operator objective', constraints={},
                allowed_effects=['process.exec', 'workspace.read'], target='jetson-orin',
                budget={'max_turns': max_turns, 'wall_clock_s': wall_clock_s},
                contract_id='qwen36-greedy-v1', initial_run_config={'env': {'K': '48'}},
                component_cc='factory.engine_component',
                source={'subpath': 'llama.cpp', 'pre_integration_commit': 'e14b87603'},
                operator_labels={'K': 'controlled-invalid: operator value'})
    path = tmp_path / 'task.json'
    path.write_text(json.dumps(task))
    assert controller.init_task(path) == 't'
    return controller.store.get_task('t')


def publish(controller, action='inspect'):
    current = controller.store.get_task('t')
    return dispatch(controller.store.scoped('t'), 't', 'evidence.publish', {'inputs': {
        'type': 'decision', 'expected_rev': current['current_decision_rev'],
        'record': {'evidence_ids': ['t'], 'observations': ['t'], 'hypothesis': 'unit test',
                   'uncertainty': 'pending evidence', 'action': {'type': action},
                   'reason_for_change': 'Considered t', 'stop_condition': 'bounded',
                   'expected_evidence': 'receipt', 'budget': {'turns': 1}}}})


@pytest.fixture
def rig(tmp_path, monkeypatch):
    # configure_agent updates process environment; restore everything it changes.
    for key in ('FACTORY_HOME', 'FACTORY_TASK_ID', 'FACTORY_WORKSPACE', 'DOCKER_CMD_PREFIX',
                'PYTHONPATH', 'PATH', 'CCV2_PYTHON', 'FACTORY_PYTHON', 'JIUWENSWARM_DATA_DIR', 'JIUWENSWARM_AGENT_SDK',
                'JIUWENSWARM_CODEX_AGENT', 'JIUWENSWARM_CODEX_AGENT_MCP',
                'JIUWENSWARM_CODEX_AGENT_CWD', 'JIUWENSWARM_SKIP_DOTENV'):
        monkeypatch.setenv(key, __import__('os').environ.get(key, ''))
    controller = Controller(tmp_path / 'factory', grants=['process.exec', 'gpu.use'])
    yield controller
    controller.store.close()


def test_waits_without_model_calls(tmp_path, rig):
    make_task(tmp_path, rig)
    calls, sleeps = [], []
    async def facade(request):
        calls.append(request)
        publish(rig, 'inspect' if len(calls) == 1 else 'accept')
        if len(calls) == 1:
            rig.store.create_attempt('t', dict(attempt_id='a', kind='build', idem_key='i', fingerprint='f', request={}))
        yield {'event_type': 'chat.tool_call', 'tool_call': {'name': 'fake', 'arguments': {}}}
        yield {'event_type': 'chat.tool_result', 'result': SENTINEL}
    async def sleep(seconds):
        sleeps.append(seconds)
        assert len(calls) == 1
    rig.facade, rig.sleep = facade, sleep
    rig.jobs = FakeJobs(rig.store, calls)
    result = asyncio.run(rig.run('t'))
    assert result['outcome'] == 'accept'
    assert len(calls) == 2 and sleeps == [15, 15]
    assert rig.jobs.polls == 2
    transcript = (rig.home / 'sessions/t.jsonl').read_text()
    assert 'chat.tool_call' in transcript and 'chat.tool_result' in transcript


def test_budget_exhaustion_partial(tmp_path, rig):
    make_task(tmp_path, rig, max_turns=1)
    async def facade(request):
        publish(rig)
        rig.store.create_attempt('t', dict(attempt_id='a', kind='build', idem_key='i', fingerprint='f', request={}))
        yield {'event_type': 'chat.final', 'content': 'waiting on a'}
    rig.facade = facade
    result = asyncio.run(rig.run('t'))
    assert result['outcome'] == 'partial'
    assert result['pending_attempts'] == ['a'] and result['pending_questions']
    assert result['budget_used']['turns'] == 1


def test_wall_clock_exhaustion_partial(tmp_path, rig):
    make_task(tmp_path, rig, wall_clock_s=1)
    async def facade(request):
        await asyncio.sleep(5)
        yield {}
    rig.facade = facade
    result = asyncio.run(rig.run('t'))
    assert result['outcome'] == 'partial' and result['budget_used']['turns'] == 1


def test_missing_decision_reported(tmp_path, rig):
    make_task(tmp_path, rig, max_turns=2)
    messages = []
    async def facade(request):
        messages.append(json.loads(request.params['query']))
        if len(messages) == 2:
            publish(rig, 'report_inconclusive')
        yield {'event_type': 'chat.final'}
    rig.facade = facade
    result = asyncio.run(rig.run('t'))
    assert 'without publishing a new decision revision' in messages[1]['host_observation']
    assert result['budget_used']['turns'] == 2


def test_grants_never_widen(tmp_path, rig):
    task = make_task(tmp_path, rig)
    config = tomllib.loads(configure_agent(task, ['process.exec', 'gpu.use'], rig.home).read_text())
    args = config['mcp_servers']['cc']['args']
    grants = [args[i+1] for i, arg in enumerate(args) if arg == '--grant']
    assert grants == ['process.exec']
    config = tomllib.loads(configure_agent(task, [], rig.home).read_text())
    assert '--grant' not in config['mcp_servers']['cc']['args']
    assert rig.store.get_task('t')['allowed_effects'] == task['allowed_effects']


def test_turn_messages_id_only(tmp_path, rig):
    task = make_task(tmp_path, rig)
    rig.store.put_artifact('t', 'artifact-sentinel', SENTINEL.encode(), 'text/plain', None)
    rig.store.append_observation('t', {'values': {'text': SENTINEL}})
    messages = []
    async def facade(request):
        messages.append(request.params['query'])
        publish(rig, 'inspect' if len(messages) == 1 else 'stop_missing_prerequisite')
        yield {'event_type': 'chat.tool_result', 'result': SENTINEL}
    rig.facade = facade
    asyncio.run(rig.run('t'))
    assert len(messages) == 2 and all(SENTINEL not in message for message in messages)
    assert json.loads(messages[0])['operator_labels'] == task['operator_labels']
    assert 'objective' not in json.loads(messages[1]) and 'instructions' not in json.loads(messages[1])


def test_resume_same_session(tmp_path, rig):
    make_task(tmp_path, rig)
    calls = []
    async def interrupted(request):
        calls.append(request)
        publish(rig)
        rig.store.create_attempt('t', dict(attempt_id='a', kind='build', idem_key='i', fingerprint='f', request={}))
        yield {'event_type': 'chat.final'}
        raise RuntimeError('unit-test controller restart')
    rig.facade = interrupted
    with pytest.raises(RuntimeError):
        asyncio.run(rig.run('t'))
    restarted = Controller(rig.home, grants=['process.exec'])
    jobs = FakeJobs(restarted.store, calls)
    restarted.jobs = jobs
    # Reconciliation must finish before any resumed model call.
    async def facade(request):
        assert jobs.polls == 2
        calls.append(request)
        publish(restarted, 'accept')
        yield {'event_type': 'chat.final'}
    async def sleep(seconds):
        assert len(calls) == 1
    restarted.facade, restarted.sleep = facade, sleep
    result = asyncio.run(restarted.resume('t'))
    assert result['outcome'] == 'accept'
    assert [call.session_id for call in calls] == ['t', 't']
    assert result['budget_used']['turns'] == 2
    assert 'objective' not in json.loads(calls[1].params['query'])
    assert (rig.home / 'sessions/t.jsonl').read_text().count('turn.start') == 2
    restarted.store.close()


def test_mcp_env_has_factory_vars(tmp_path, rig):
    task = make_task(tmp_path, rig)
    config = tomllib.loads(configure_agent(task, rig.grants, rig.home).read_text())
    server = config['mcp_servers']['cc']
    env = server['env']
    assert env['FACTORY_HOME'] == str(rig.home)
    assert env['FACTORY_TASK_ID'] == 't'
    assert env['FACTORY_WORKSPACE'] == str(rig.home / 'agent-workspace')
    assert env['DOCKER_CMD_PREFIX'] == 'sg docker -c'
    assert '/usr/local/cuda/bin' in env['PATH'].split(':')
    assert env['PYTHONPATH'] == str(Path(__file__).resolve().parents[2])
    assert str(rig.home / 'ccstore') in server['args']
    assert '--allow-built' not in server['args']


def test_operator_values_survive_reopen(tmp_path, rig):
    task = make_task(tmp_path, rig)
    reopened = Controller(rig.home)
    assert reopened.store.get_task('t') == task
    assert reopened.store.read('t', 't')['initial_run_config'] == {'env': {'K': '48'}}
    reopened.store.close()


def test_terminal_without_evidence_is_not_accept(tmp_path, rig):
    make_task(tmp_path, rig, max_turns=1)
    async def facade(request):
        rig.store.advance_decision('t', 0, {'action': {'type': 'accept'}})
        yield {}
    rig.facade = facade
    assert asyncio.run(rig.run('t'))['outcome'] == 'partial'


def test_codex_completed_thread_resumes_after_service_restart(tmp_path, monkeypatch):
    from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
    from tests.unit_tests.runtime.test_codex_subscription import FakeTransport
    monkeypatch.setenv('JIUWENSWARM_CODEX_AGENT', '1')
    monkeypatch.setenv('JIUWENSWARM_CODEX_AGENT_CWD', str(tmp_path / 'work'))
    async def exercise():
        first_transport = FakeTransport()
        first = SubscriptionService(tmp_path / 'sub', transport=first_transport)
        _ = [e async for e in first.stream('factory-task', 'r1', 'first')]
        thread = first.bindings['factory-task']['thread']
        await first_transport.close()
        transport = FakeTransport()
        restarted = SubscriptionService(tmp_path / 'sub', transport=transport)
        _ = [e async for e in restarted.stream('factory-task', 'r2', 'continue')]
        resumes = [p for method, p in transport.calls if method == 'thread/resume']
        assert len(resumes) == 1 and resumes[0]['threadId'] == thread
        assert resumes[0]['sandbox'] == 'workspace-write'
        assert not any(method == 'thread/start' for method, _ in transport.calls)
        assert next(p for method, p in transport.calls if method == 'turn/start')['threadId'] == thread
    asyncio.run(exercise())


@pytest.mark.parametrize('problem', ['wrong_account', 'interrupted', 'inflight', 'text_profile'])
def test_codex_resume_keeps_identity_and_delivery_guards(tmp_path, monkeypatch, problem):
    from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
    from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError
    from tests.unit_tests.runtime.test_codex_subscription import FakeTransport
    monkeypatch.setenv('JIUWENSWARM_CODEX_AGENT', '1')
    async def exercise():
        first = SubscriptionService(tmp_path / 'sub', transport=FakeTransport())
        _ = [e async for e in first.stream('t', 'r1', 'first')]
        binding = first.bindings['t']
        if problem == 'wrong_account':
            binding['owner'] = 'another-account'
        elif problem == 'interrupted':
            binding['epoch'] = 'interrupted'
        elif problem == 'inflight':
            binding['inflight'] = True
        else:
            binding['agent'] = False
        first._save()
        transport = FakeTransport()
        restarted = SubscriptionService(tmp_path / 'sub', transport=transport)
        with pytest.raises(CodexError, match='NEW_SESSION_REQUIRED'):
            _ = [e async for e in restarted.stream('t', 'r2', 'continue')]
        assert not any(method in {'thread/start', 'thread/resume', 'turn/start'} for method, _ in transport.calls)
    asyncio.run(exercise())


def test_codex_logout_revokes_agent_resume_after_restart(tmp_path, monkeypatch):
    from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
    from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError
    from tests.unit_tests.runtime.test_codex_subscription import FakeTransport
    monkeypatch.setenv('JIUWENSWARM_CODEX_AGENT', '1')
    async def exercise():
        first = SubscriptionService(tmp_path / 'sub', transport=FakeTransport())
        _ = [e async for e in first.stream('t', 'r1', 'first')]
        await first.logout()
        restarted = SubscriptionService(tmp_path / 'sub', transport=FakeTransport())
        with pytest.raises(CodexError, match='NEW_SESSION_REQUIRED'):
            _ = [e async for e in restarted.stream('t', 'r2', 'continue')]
    asyncio.run(exercise())


def test_run_without_any_grant_fails_before_a_turn(tmp_path):
    import asyncio, json, pytest
    from jiuwenswarm.factory.controller import Controller
    calls = []
    async def facade(*a, **k):
        calls.append(1)
        if False:
            yield None
    home = tmp_path / 'factory'
    controller = Controller(home, facade=facade)
    task_file = tmp_path / 'task.json'
    task_file.write_text(json.dumps(dict(objective='o', constraints={}, allowed_effects=['process.exec'],
        target='jetson-orin', budget=dict(max_turns=3, wall_clock_s=60), contract_id='qwen36-greedy-v1',
        initial_run_config={'env': {}}, component_cc='factory.engine_component',
        source=dict(subpath='llama.cpp', pre_integration_commit='e14b87603'))))
    try:
        task_id = controller.init_task(str(task_file))
    except (ValueError, OSError) as exc:
        pytest.skip(f'task init needs fixture workspace: {exc}')
    with pytest.raises(ValueError, match='--grant process.exec'):
        asyncio.run(controller.run(task_id))
    assert calls == []


def test_capsules_run_the_api_in_the_controller_venv(tmp_path):
    # Native bindings must retain the controller's venv. Old capsule wrappers
    # still receive FACTORY_PYTHON for compatibility.
    import sys
    from pathlib import Path
    from jiuwenswarm.factory.controller import configure_agent
    mcp = configure_agent({'task_id': 't', 'allowed_effects': []}, home=tmp_path)
    assert f'FACTORY_PYTHON = "{sys.executable}"' in mcp.read_text()
    config = tomllib.loads(mcp.read_text())['mcp_servers']['cc']
    assert config['env']['CCV2_PYTHON'] == sys.executable
    assert config['args'].count('--ccs') == 1
    root = Path(__file__).resolve().parents[2] / 'jiuwenswarm/factory/ccs'
    for wrapper in root.glob('*/run.py'):
        assert "os.environ.get('FACTORY_PYTHON', sys.executable)" in wrapper.read_text(), wrapper
