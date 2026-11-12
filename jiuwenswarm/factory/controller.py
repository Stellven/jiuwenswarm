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
import subprocess
import time
import uuid

from .jobs import Jobs
from .store import Store, TASK_INPUTS

# Controller-owned optional inputs use Store's existing additive schema boundary.
TASK_INPUTS.update(resources="JSON NOT NULL DEFAULT '{}'", capability_cc="TEXT NOT NULL DEFAULT ''")

try:
    from .taskgraph import seed_plan
except ImportError:
    seed_plan = None

ROOT = Path(__file__).resolve().parents[2]
ACTIVE = {'queued', 'running', 'cancel_requested'}
TERMINAL = {'reject', 'accept', 'report_inconclusive', 'stop_missing_prerequisite'}


EVOLVE_ACTIONS = {'investigate', 'tune', 'integrate', 'build', 'measure', 'keep_component', 'keep_dormant', 'revert_component'}
COMPONENT_ACTIONS = {'keep_component', 'keep_dormant', 'revert_component'}


def validate_action(action):
    if not isinstance(action, dict) or not isinstance(action.get('type'), str):
        raise ValueError('Decision action requires type')
    kind = action['type']
    if kind not in EVOLVE_ACTIONS | TERMINAL:
        raise ValueError('Unsupported evolve action type')
    if kind in COMPONENT_ACTIONS:
        from .components import load, dependents
        load(action.get('component'))
        if kind == 'keep_dormant':
            # A rejected component may keep its default-off source only as a prerequisite
            # of components still to be measured; its switch stays off in every arm.
            needed = set(action.get('needed_by') or [])
            if (not needed or not needed <= dependents(action['component'])
                    or not isinstance(action.get('reason'), str) or not action['reason'].strip()):
                raise ValueError('keep_dormant requires reason and needed_by naming dependent components')
        if kind == 'keep_component':
            ratio = action.get('ratio')
            if (not isinstance(action.get('image'), (str, dict)) or not action['image']
                    or type(ratio) not in (int, float) or not math.isfinite(ratio) or ratio <= 0):
                raise ValueError('keep_component requires image and finite ratio > 0')
        elif not isinstance(action.get('reason'), str) or not action['reason'].strip():
            raise ValueError('revert_component requires reason')


def validate_keep_evidence(store, task_id, record):
    action = record['action']
    for ref in record.get('evidence_ids', []):
        evidence = store.read(task_id, ref)
        if (evidence.get('kind') == 'ab_result'
                and evidence.get('values', {}).get('component', '').removeprefix('factory.components.')
                    == action['component'].removeprefix('factory.components.')
                and evidence['values'].get('acceptance', {}).get('verdict') == 'accept'):
            return
        if (evidence.get('inputs', {}).get('ab_result', {}).get('component', '').removeprefix('factory.components.')
                == action['component'].removeprefix('factory.components.')
                and evidence.get('inputs', {}).get('acceptance', {}).get('verdict') == 'accept'):
            return
    raise ValueError('keep_component requires a cited ab_result with acceptance.verdict == accept')


def read_tasks(task):
    constraints = task.get('constraints')
    reads = constraints.get('read_tasks', []) if isinstance(constraints, dict) else []
    if not isinstance(reads, list) or not all(isinstance(t, str) and t for t in reads):
        raise ValueError('constraints.read_tasks must be a list of task ids')
    return reads
from .redact import sanitize as scrub
from .config import DOCKER_PREFIX


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
           'FACTORY_WORKSPACE': str(workspace), 'DOCKER_CMD_PREFIX': DOCKER_PREFIX,
           'PYTHONPATH': str(ROOT),
           # Bind native {python} to the controller's admitted environment.
           'CCV2_PYTHON': sys.executable, 'FACTORY_PYTHON': sys.executable,
           'PATH': '/usr/local/cuda/bin:' + os.environ.get('PATH', '')}
    # Cross-task reads only when the operator lists prior tasks in constraints.read_tasks.
    reads = read_tasks(task)
    if reads:
        env['FACTORY_READ_TASKS'] = ','.join(reads)
    quote = json.dumps
    mcp = home / 'agent-mcp.toml'
    mcp.write_text('[mcp_servers.cc]\n' + f'command = {quote(sys.executable)}\n'
                   + 'args = ' + json.dumps(args) + '\n'
                   + 'env_vars = ["FACTORY_TURN", "HOME", "DOCKER_HOST", "DOCKER_CONTEXT", "TMP", "TEMP"]\n'
                   + 'startup_timeout_sec = 60\ntool_timeout_sec = 300\n'
                   + 'default_tools_approval_mode = "approve"\n[mcp_servers.cc.env]\n'
                   + ''.join(f'{k} = {quote(v)}\n' for k, v in env.items()), encoding='utf-8')
    os.environ.update(env | {'JIUWENSWARM_DATA_DIR': str(data),
        'JIUWENSWARM_AGENT_SDK': 'codex_subscription', 'JIUWENSWARM_CODEX_AGENT': '1',
        'JIUWENSWARM_CODEX_AGENT_MCP': str(mcp), 'JIUWENSWARM_CODEX_AGENT_CWD': str(workspace),
        'JIUWENSWARM_SKIP_DOTENV': '1'})
    return mcp


STALL_TURNS = 3

class Controller:
    def __init__(self, home=None, *, store=None, jobs=None, grants=(), facade=None,
                 sleep=asyncio.sleep, clock=time.time):
        self.home = Path(home or (store.home if store else factory_home())).resolve()
        self.store = store or Store(self.home)
        if store is not None:
            # An injected Store may have been opened before importing Controller.
            columns = {row['name'] for row in store._db.execute('PRAGMA table_info(tasks)')}
            with store._transaction(inject=False):
                for name in ('resources', 'capability_cc'):
                    if name not in columns:
                        store._db.execute(f'ALTER TABLE tasks ADD COLUMN {name} {TASK_INPUTS[name]}')
                        if name == 'resources':
                            store._json_columns['tasks'].add(name)
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
        if not isinstance(task, dict) or required - task.keys() or task.keys() - required - {'operator_labels', 'task_id', 'resources', 'capability_cc'}:
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
        for key in ('budget', 'source', 'initial_run_config', 'operator_labels', 'resources'):
            if not isinstance(task.get(key, {}), dict):
                raise ValueError(f'{key} must be an object')
        for prior in read_tasks(task):
            self.store.get_task(prior)  # must exist; raises NotFound otherwise
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
        if task['contract_id'] == 'qwen36-bare-greedy-v1':
            self._init_evolve(source)
        task = self.store.create_task(task)
        if seed_plan is not None:
            seed_plan(self.store, task)
        return task['task_id']

    def _init_evolve(self, source):
        workspace = (self.home / 'agent-workspace').resolve()
        checkout = (workspace / source['subpath']).resolve()
        if not checkout.is_relative_to(workspace):
            raise ValueError('Owned checkout escapes workspace')
        if not isinstance(source.get('branch'), str) or not re.fullmatch(r'[a-z][a-z0-9_-]*', source['branch']) or source['pre_integration_commit'] != 'cf34d3113':
            raise ValueError('Engine capability task requires a valid source.branch at cf34d3113')
        def git(*args, check=True):
            return subprocess.run(['git', '-C', str(checkout), *args], check=check,
                                  capture_output=True, text=True)
        if not checkout.is_dir() or git('rev-parse', '--show-toplevel').stdout.strip() != str(checkout):
            raise ValueError('Evolution requires an existing owned git checkout')
        if git('show-ref', '--verify', '--quiet', 'refs/heads/' + source['branch'], check=False).returncode:
            # Create only the named ref: never switch/reset the current branch or worktree.
            git('branch', source['branch'], 'cf34d3113')

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
            message['resources'] = task.get('resources', {})
            if read_tasks(task):
                message['readable_prior_tasks'] = read_tasks(task)  # ids only; query their evidence
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
        from .telemetry import emit as telemetry_emit
        started = self.clock()
        calls, tokens, pending_tools = {}, None, {}
        outcome = 'error'
        os.environ['FACTORY_TURN'] = str(turn)
        # MCP may outlive a turn; native entrypoints also read the durable reservation.
        try:
            with log.open('a', encoding='utf-8') as out:
                def emit(payload):
                    out.write(json.dumps(scrub({'t': self.clock(), **payload}), ensure_ascii=False, default=str) + '\n')
                    out.flush()
                emit({'event': 'turn.start', 'turn': turn, 'session_id': task_id, 'query': query})
                async for chunk in stream(request):
                    payload = getattr(chunk, 'payload', chunk)
                    payload = payload if isinstance(payload, dict) else {'raw': str(payload)}
                    emit(payload)
                    kind = payload.get('event_type', payload.get('event'))
                    if kind == 'chat.tool_call':
                        tool = payload.get('tool_call', {})
                        name = tool.get('name', 'unknown')
                        calls[name] = calls.get(name, 0) + 1
                        pending_tools[tool.get('tool_call_id')] = tool.get('arguments', {})
                    if kind == 'chat.tool_result' and payload.get('tool_name', '').split('.')[-1] in {'cc_material', 'cc_list'}:
                        result = payload.get('result')
                        def unpack(value):
                            if isinstance(value, str):
                                try:
                                    return unpack(json.loads(value))
                                except ValueError:
                                    return None
                            if isinstance(value, dict):
                                if any(k in value for k in ('cc', 'ccs', 'material')):
                                    return value
                                for child in value.values():
                                    found = unpack(child)
                                    if found is not None:
                                        return found
                            if isinstance(value, list):
                                for child in value:
                                    found = unpack(child)
                                    if found is not None:
                                        return found
                            return None
                        material = unpack(result) or {}
                        args = pending_tools.get(payload.get('tool_call_id'), {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except ValueError:
                                args = {}
                        args = args if isinstance(args, dict) else {}
                        telemetry_emit(self.home, 'cc.material', task_id, turn=turn,
                            tool_name=payload['tool_name'], capsule=material.get('cc', args.get('cc')),
                            material=material.get('material', args.get('material')),
                            path=material.get('path'), bytes=len(material['text'].encode()) if isinstance(material.get('text'), str) else None,
                            truncated=material.get('truncated'),
                            observed=bool(material), bytes_scope='returned UTF-8 text; null for listings')
                    def usage(value):
                        if isinstance(value, dict):
                            if isinstance(value.get('usage'), dict):
                                return value['usage']
                            for child in value.values():
                                found = usage(child)
                                if found is not None:
                                    return found
                        return None
                    observed = usage(payload)
                    if observed is not None:
                        tokens = {key: observed.get(key) for key in ('input_tokens', 'output_tokens')}
                    if kind in {'chat.error', 'error'}:
                        outcome = 'stream_error'
                emit({'event': 'turn.end', 'turn': turn})
                outcome = 'ok' if outcome != 'stream_error' else 'error'
        finally:
            telemetry_emit(self.home, 'agent.turn', task_id, turn=turn, start=started,
                           duration_ms=(self.clock() - started) * 1000, tool_calls=calls,
                           tokens=tokens, outcome=outcome)

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
            missing = sorted(set(task.get('allowed_effects', [])) - set(self.grants))
            if missing and not self.grants:
                # No grants at all: every native capsule call would be denied. Fail before a model turn.
                # (A deliberate subset of grants is the operator's choice and stays allowed.)
                raise ValueError('Task allows effects with no operator grant: ' + ', '.join(missing)
                                 + '. Re-run with ' + ' '.join('--grant ' + m for m in missing))
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
                        self.store.validate_evidence(task_id, latest['evidence_ids'], read_tasks(task))
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
                    # A turn that neither advanced the decision nor started a job made no progress.
                    started = any(a['state'] in ACTIVE for a in self._snapshot(task_id)['attempts'])
                    state['idle_turns'] = state.get('idle_turns', 0) + 1 if state['missing_decision'] and not started else 0
                    if state['idle_turns'] >= STALL_TURNS:
                        state['stop_reason'] = f'stalled: {STALL_TURNS} consecutive turns without a decision or job'
                        return self._finish(task_id, state, 'partial')
                    self._save(task_id, state)
            finally:
                if self.facade is None:
                    from jiuwenswarm.server.runtime.codex_subscription.service import get_service
                    await get_service().transport.close()

    async def resume(self, task_id):
        return await self.run(task_id)

    def cancel(self, task_id):
        from .manager import Manager
        results = []
        for attempt in self._snapshot(task_id)['attempts']:
            if attempt['state'] in ACTIVE | {'unknown'}:
                owner = Manager(self.store, self.home / 'lab-spool') if attempt['kind'] == 'lab' else self.jobs
                results.append(owner.cancel(attempt['attempt_id']))
        return results

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


def status(task_id):
    controller = Controller()
    try:
        return controller.status(task_id)
    finally:
        controller.store.close()
