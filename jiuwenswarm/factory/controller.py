"""Evidence-driven factory host. Only the agent chooses the next action.

The injectable stream callable and clock are for offline unit tests, not a
simulation mode exposed to operators. Host progress is separate from evidence.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import uuid

from .jobs import Jobs
from .store import Store

ROOT = Path(__file__).resolve().parents[2]
ACTIVE = {'queued', 'running', 'cancel_requested'}
TERMINAL = {'accept', 'report_inconclusive', 'stop_missing_prerequisite'}
SCRUB = [
    (re.compile(r'eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}'), '<jwt>'),
    (re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._\-]{16,}'), r'\1<token>'),
    (re.compile(r'sk-[A-Za-z0-9_\-]{16,}'), '<key>'),
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+'), '<email>'),
    (re.compile(r'(?i)(state|code|code_challenge)=[A-Za-z0-9_\-%.~]{12,}'), r'\1=<redacted>'),
]


def scrub(value):
    if isinstance(value, str):
        for pattern, replacement in SCRUB:
            value = pattern.sub(replacement, value)
    elif isinstance(value, dict):
        value = {k: ('<redacted>' if re.search(r'(?i)(token|secret|password|authorization|api_key)', k)
                     else scrub(v)) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        value = [scrub(v) for v in value]
    return value


def factory_home():
    return Path(os.environ.get('FACTORY_HOME', '~/.jiuwenswarm-factory')).expanduser().resolve()


def configure_agent(task, grants=(), home=None):
    """Configure one operator-owned profile; grants are always an intersection."""
    home = Path(home or factory_home()).resolve()
    workspace, data = home / 'agent-workspace', home / 'agent-data'
    for directory in (home, workspace, data, home / 'sessions', home / 'ccstore'):
        directory.mkdir(parents=True, exist_ok=True)
    effective = sorted(set(task.get('allowed_effects', [])) & set(grants))
    args = ['-m', 'jiuwenswarm.ccv2.agent_mcp', '--ccs', str(ROOT / 'jiuwenswarm/factory/ccs'),
            '--store', str(home / 'ccstore'), '--workspace', str(workspace)]
    for grant in effective:
        args += ['--grant', grant]
    env = {'FACTORY_HOME': str(home), 'FACTORY_TASK_ID': task['task_id'],
           'FACTORY_WORKSPACE': str(workspace), 'DOCKER_CMD_PREFIX': 'sg docker -c',
           'PYTHONPATH': str(ROOT), 'PATH': '/usr/local/cuda/bin:' + os.environ.get('PATH', '')}
    quote = json.dumps
    mcp = home / 'agent-mcp.toml'
    mcp.write_text('[mcp_servers.cc]\n' + f'command = {quote(sys.executable)}\n'
                   + 'args = ' + json.dumps(args) + '\n'
                   + 'env_vars = ["HOME", "DOCKER_HOST", "DOCKER_CONTEXT", "TMP", "TEMP"]\n'
                   + 'startup_timeout_sec = 60\ntool_timeout_sec = 300\n'
                   + 'default_tools_approval_mode = "approve"\n[mcp_servers.cc.env]\n'
                   + ''.join(f'{k} = {quote(v)}\n' for k, v in env.items()), encoding='utf-8')
    os.environ.update(env | {'JIUWENSWARM_DATA_DIR': str(data),
        'JIUWENSWARM_AGENT_SDK': 'codex_subscription', 'JIUWENSWARM_CODEX_AGENT': '1',
        'JIUWENSWARM_CODEX_AGENT_MCP': str(mcp), 'JIUWENSWARM_CODEX_AGENT_CWD': str(workspace),
        'JIUWENSWARM_SKIP_DOTENV': '1'})
    return mcp


class Controller:
    def __init__(self, home=None, *, store=None, jobs=None, grants=(), facade=None,
                 sleep=asyncio.sleep, clock=time.time):
        self.home = Path(home or (store.home if store else factory_home())).resolve()
        self.store = store or Store(self.home)
        self.jobs = jobs or Jobs(self.store)
        self.grants = list(grants)
        self.facade = facade
        self._live_facade = None
        self.sleep, self.clock = sleep, clock
        (self.home / 'sessions').mkdir(parents=True, exist_ok=True)

    def init_task(self, task_file):
        task = json.loads(Path(task_file).read_text(encoding='utf-8'))
        required = {'objective', 'constraints', 'allowed_effects', 'target', 'budget',
                    'contract_id', 'initial_run_config', 'component_cc', 'source'}
        if not isinstance(task, dict) or required - task.keys() or task.keys() - required - {'operator_labels', 'task_id'}:
            raise ValueError('Invalid task fields')
        if not isinstance(task['objective'], str) or not task['objective'].strip():
            raise ValueError('objective must be nonempty text')
        for key in ('contract_id', 'component_cc'):
            if not isinstance(task[key], str) or not task[key].strip():
                raise ValueError(f'{key} must be nonempty text')
        if not isinstance(task['constraints'], (dict, list)) or not isinstance(task['target'], (str, dict)):
            raise ValueError('constraints must be object/list and target must be text/object')
        if not isinstance(task['allowed_effects'], list) or not all(isinstance(g, str) for g in task['allowed_effects']):
            raise ValueError('allowed_effects must be a list of grants')
        for key in ('budget', 'source', 'initial_run_config', 'operator_labels'):
            if not isinstance(task.get(key, {}), dict):
                raise ValueError(f'{key} must be an object')
        budget = task['budget']
        if (type(budget.get('max_turns')) is not int or budget['max_turns'] < 1
                or type(budget.get('wall_clock_s')) not in (int, float)
                or not math.isfinite(budget['wall_clock_s']) or budget['wall_clock_s'] <= 0):
            raise ValueError('budget requires positive max_turns and wall_clock_s')
        source = task['source']
        if not isinstance(source.get('subpath'), str) or not isinstance(source.get('pre_integration_commit'), str):
            raise ValueError('source requires a workspace subpath and pre_integration_commit')
        subpath = Path(source['subpath'])
        if (not source.get('subpath') or subpath.is_absolute() or '..' in subpath.parts
                or not source.get('pre_integration_commit')):
            raise ValueError('source requires a workspace subpath and pre_integration_commit')
        task.setdefault('task_id', 'factory-' + uuid.uuid4().hex)
        # Paths use task IDs; prohibit traversal even for operator-supplied IDs.
        self._state_path(task['task_id'])
        return self.store.create_task(task)['task_id']

    def _state_path(self, task_id):
        if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', task_id):
            raise ValueError('task_id must contain only letters, digits, underscore or hyphen')
        return self.home / 'sessions' / (task_id + '.state.json')

    def _load(self, task_id):
        path = self._state_path(task_id)
        if path.exists():
            return json.loads(path.read_text())
        return dict(turns=0, started=None, outcome=None, seen_attempts={}, missing_decision=False)

    def _save(self, task_id, state):
        path = self._state_path(task_id)
        temp = path.with_suffix('.tmp')
        with temp.open('w') as out:
            json.dump(state, out)
            out.flush()
            os.fsync(out.fileno())
        temp.replace(path)

    @contextmanager
    def _lock(self):
        # A profile has one MCP configuration and one Codex transport: serialize
        # controllers across tasks. Cancellation remains independently available.
        with (self.home / 'controller.lock').open('a') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('A controller is already running in FACTORY_HOME') from None
            yield

    def _snapshot(self, task_id):
        return self.store.dump(task_id)

    def _reconcile(self, task_id):
        for attempt in self._snapshot(task_id)['attempts']:
            if attempt['state'] in ACTIVE | {'unknown'}:
                self.jobs.status(attempt['attempt_id'])

    def _remaining(self, task, state):
        return {'turns': max(0, task['budget']['max_turns'] - state['turns']),
                'wall_clock_s': max(0, task['budget']['wall_clock_s'] - (self.clock() - state['started']))}

    def _message(self, task, state):
        current = self.store.get_task(task['task_id'])
        attempts = self._snapshot(task['task_id'])['attempts']
        changed = [{'attempt_id': a['attempt_id'], 'state': a['state']} for a in attempts
                   if state['seen_attempts'].get(a['attempt_id']) != a['state']]
        state['seen_attempts'] = {a['attempt_id']: a['state'] for a in attempts}
        message = dict(task_id=task['task_id'], decision_rev=current['current_decision_rev'],
                       evidence_cursor=current['evidence_cursor'], changed_attempts=changed,
                       remaining_budget=self._remaining(task, state))
        if state['missing_decision']:
            message['host_observation'] = 'Previous turn ended without publishing a new decision revision.'
        if state['turns'] == 0:
            # Only operator inputs and standing instructions; never producer prose.
            message['objective'] = task['objective']
            message['operator_labels'] = task.get('operator_labels', {})
            message['instructions'] = Path(__file__).with_name('AGENT.md').read_text()
        return json.dumps(message, ensure_ascii=False)

    async def _turn(self, task_id, query, turn):
        from jiuwenswarm.common.schema.agent import AgentRequest
        from jiuwenswarm.common.schema.message import ReqMethod
        stream = self.facade
        if stream is None:
            if self._live_facade is None:
                from jiuwenswarm.server.runtime.agent_adapter.interface import JiuWenSwarm
                self._live_facade = JiuWenSwarm()
                self._live_facade._sdk_name = 'codex_subscription'
            stream = self._live_facade.process_message_stream
        request = AgentRequest(request_id=f'{task_id}-{turn}-{uuid.uuid4().hex}', channel_id='web',
            session_id=task_id, req_method=ReqMethod.CHAT_SEND,
            params={'query': query, 'mode': 'agent.work.normal'})
        log = self.home / 'sessions' / f'{task_id}.jsonl'
        with log.open('a', encoding='utf-8') as out:
            def emit(payload):
                out.write(json.dumps(scrub({'t': self.clock(), **payload}), ensure_ascii=False, default=str) + '\n')
                out.flush()
            emit({'event': 'turn.start', 'turn': turn, 'session_id': task_id, 'query': query})
            async for chunk in stream(request):
                payload = getattr(chunk, 'payload', chunk)
                emit(payload if isinstance(payload, dict) else {'raw': str(payload)})
            emit({'event': 'turn.end', 'turn': turn})

    def _finish(self, task_id, state, outcome):
        data = self._snapshot(task_id)
        state['outcome'] = outcome
        state['pending_attempts'] = [a['attempt_id'] for a in data['attempts'] if a['state'] in ACTIVE | {'unknown'}]
        latest = max(data['decisions'], key=lambda d: d['rev'], default={})
        state['pending_questions'] = [latest.get('uncertainty') or 'No terminal decision with supporting evidence.'] if outcome == 'partial' else []
        state['finished'] = self.clock()
        self._save(task_id, state)
        return self.status(task_id)

    async def run(self, task_id):
        with self._lock():
            task = self.store.get_task(task_id)
            state = self._load(task_id)
            if 'pending_turn_rev' in state:
                state['missing_decision'] = task['current_decision_rev'] == state['pending_turn_rev']
            if state['outcome'] in TERMINAL:
                return self.status(task_id)
            configure_agent(task, self.grants, self.home)
            state['started'] = state['started'] if state['started'] is not None else self.clock()
            state['outcome'] = None
            state.pop('finished', None)
            self._save(task_id, state)
            try:
                # Also reconciles on ordinary run, making restart safe by default.
                self._reconcile(task_id)
                while True:
                    remaining = self._remaining(task, state)
                    if remaining['wall_clock_s'] <= 0:
                        return self._finish(task_id, state, 'partial')
                    decisions = self._snapshot(task_id)['decisions']
                    latest = max(decisions, key=lambda d: d['rev'], default={})
                    action = latest.get('action', {}).get('type')
                    if action in TERMINAL and latest.get('evidence_ids'):
                        return self._finish(task_id, state, action)
                    if remaining['turns'] <= 0:
                        return self._finish(task_id, state, 'partial')
                    active = [a for a in self._snapshot(task_id)['attempts'] if a['state'] in ACTIVE]
                    if active:
                        await self.sleep(min(15, remaining['wall_clock_s']))
                        self._reconcile(task_id)
                        self._save(task_id, state)
                        continue
                    query = self._message(task, state)
                    before = self.store.get_task(task_id)['current_decision_rev']
                    state['turns'] += 1
                    # Reserve the turn durably before invoking the model. On
                    # interruption the next message reports the unconfirmed turn.
                    state['missing_decision'] = True
                    state['pending_turn_rev'] = before
                    self._save(task_id, state)
                    try:
                        await asyncio.wait_for(self._turn(task_id, query, state['turns']),
                                               timeout=remaining['wall_clock_s'])
                    except asyncio.TimeoutError:
                        return self._finish(task_id, state, 'partial')
                    state['missing_decision'] = self.store.get_task(task_id)['current_decision_rev'] == before
                    state.pop('pending_turn_rev', None)
                    self._save(task_id, state)
            finally:
                if self.facade is None:
                    from jiuwenswarm.server.runtime.codex_subscription.service import get_service
                    await get_service().transport.close()

    async def resume(self, task_id):
        return await self.run(task_id)

    def cancel(self, task_id):
        return [self.jobs.cancel(a['attempt_id']) for a in self._snapshot(task_id)['attempts']
                if a['state'] in ACTIVE | {'unknown'}]

    def status(self, task_id):
        data = self._snapshot(task_id)
        task = data['tasks'][0]
        state = self._load(task_id)
        latest = max(data['decisions'], key=lambda d: d['rev'], default=None)
        return dict(task_id=task_id, objective=task['objective'], outcome=state['outcome'],
                    latest_decision=latest, active_jobs=[a for a in data['attempts'] if a['state'] in ACTIVE | {'unknown'}],
                    artifacts=[{k: a[k] for k in ('artifact_id', 'media_type', 'size')} for a in data['artifacts']],
                    evaluations=data['evaluations'], readiness={'decision_published': latest is not None,
                        'jobs_idle': not any(a['state'] in ACTIVE | {'unknown'} for a in data['attempts']),
                        'evaluations_present': bool(data['evaluations'])},
                    budget_used={'turns': state['turns'], 'wall_clock_s': max(0, (state.get('finished') or self.clock()) - state['started']) if state['started'] is not None else 0},
                    pending_attempts=state.get('pending_attempts', []), pending_questions=state.get('pending_questions', []))


def init_task(task_file):
    controller = Controller()
    try:
        return controller.init_task(task_file)
    finally:
        controller.store.close()


async def run(task_id):
    controller = Controller()
    try:
        return await controller.run(task_id)
    finally:
        controller.store.close()


async def resume(task_id):
    return await run(task_id)


def status(task_id):
    controller = Controller()
    try:
        return controller.status(task_id)
    finally:
        controller.store.close()
