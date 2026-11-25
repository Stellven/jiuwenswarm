"""The scheduler agent: a JiuwenSwarm agent that finalizes one preliminary node contract.

The planner writes rough (preliminary) node contracts. Just before a node runs, the controller
starts this agent for it. The agent reads a brief (``factory.scheduler.brief``: the preliminary
contract, accepted upstream outputs, what failed before, the capsule catalog and the machine state),
writes the final contract and binds capsules, and proposes it (``factory.scheduler.propose``).
Control code (``scheduler.finalize`` / ``node_finalize.check_final``) admits or refuses it: a final
contract may be more concrete or stricter than the preliminary one, never weaker.

It is a separate agent from the one that works the node: its own JiuwenSwarm profile, its own
session and its own capsule root (``scheduler_ccs``), with only the scheduler capsule. The model is
Codex through the JiuwenSwarm ``codex_subscription`` transport; ``FACTORY_SCHEDULER_MODEL`` picks
the model (default ``gpt-6.2-sol``).

Run once for one node (the controller does this in a subprocess, so the two agents never share a
transport or MCP configuration)::

    python -m jiuwenswarm.factory.scheduler_agent --home <factory home> --task <task> --node <node>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = 'gpt-6.2-sol'
TURN_TIMEOUT_S = 900
CAPSULES = Path(__file__).with_name('scheduler_ccs')


def profile(home):
    return Path(home).resolve() / 'scheduler-agent'


def configure(home, task_id):
    """This agent's own JiuwenSwarm profile and MCP configuration; returns the MCP file."""
    home = Path(home).resolve()
    base = profile(home)
    workspace, data = base / 'workspace', base / 'data'
    for directory in (base, workspace, data, base / 'ccstore'):
        directory.mkdir(parents=True, exist_ok=True)
    auth = data / 'subscription' / 'codex-home' / 'auth.json'
    if not auth.is_file():  # the operator's Codex login, shared read-only by copy
        for source in (home / 'agent-data/subscription/codex-home/auth.json', Path.home() / '.codex/auth.json'):
            if source.is_file():
                auth.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, auth)
                os.chmod(auth, 0o600)
                break
    args = ['-m', 'jiuwenswarm.ccv2.agent_mcp', '--ccs', str(CAPSULES), '--store', str(base / 'ccstore'),
            '--workspace', str(workspace), '--grant', 'process.exec']
    env = {'FACTORY_HOME': str(home), 'FACTORY_TASK_ID': task_id, 'FACTORY_WORKSPACE': str(workspace),
           'FACTORY_AGENT_ROLE': 'scheduler',
           'PYTHONPATH': os.pathsep.join(dict.fromkeys([str(ROOT), *filter(None, os.environ.get('PYTHONPATH', '').split(os.pathsep))])),
           'CCV2_PYTHON': sys.executable, 'FACTORY_PYTHON': sys.executable, 'PATH': os.environ.get('PATH', '')}
    for key in ('FACTORY_MACHINE_STATE', 'FACTORY_READ_TASKS'):
        if key in os.environ:
            env[key] = os.environ[key]
    quote = json.dumps
    mcp = base / 'mcp.toml'
    mcp.write_text('[mcp_servers.cc]\n' + f'command = {quote(sys.executable)}\n'
                   + 'args = ' + json.dumps(args) + '\n'
                   + 'env_vars = ["FACTORY_TURN", "HOME", "TMP", "TEMP"]\n'
                   + 'startup_timeout_sec = 60\ntool_timeout_sec = 120\n'
                   + 'default_tools_approval_mode = "approve"\n[mcp_servers.cc.env]\n'
                   + ''.join(f'{k} = {quote(v)}\n' for k, v in env.items()), encoding='utf-8')
    os.environ.update(env | {'JIUWENSWARM_DATA_DIR': str(data), 'JIUWENSWARM_AGENT_SDK': 'codex_subscription',
                             'JIUWENSWARM_CODEX_AGENT': '1', 'JIUWENSWARM_CODEX_AGENT_MCP': str(mcp),
                             'JIUWENSWARM_CODEX_AGENT_CWD': str(workspace), 'JIUWENSWARM_SKIP_DOTENV': '1'})
    return mcp


def query(task_id, node_id, attempt):
    message = dict(role='scheduler', task_id=task_id, node_id=node_id, attempt=attempt,
                   instructions=Path(__file__).with_name('SCHEDULER.md').read_text(encoding='utf-8'))
    if attempt > 1:
        message['host_observation'] = ('Your earlier proposal for this node was refused or not made. '
                                       'Read the refusal reasons in the brief (earlier proposals) and fix them.')
    return json.dumps(message, ensure_ascii=False)


async def turn(home, task_id, node_id, attempt=1, *, stream=None, model=None, clock=time.time):
    """One scheduler agent turn for one node. ``stream`` is injectable for offline tests."""
    from jiuwenswarm.common.schema.agent import AgentRequest
    from jiuwenswarm.common.schema.message import ReqMethod
    from .telemetry import emit as telemetry_emit
    live = None
    if stream is None:
        from jiuwenswarm.server.runtime.agent_adapter.interface import JiuWenSwarm
        live = JiuWenSwarm()
        live._sdk_name = 'codex_subscription'
        stream = live.process_message_stream
    params = {'query': query(task_id, node_id, attempt), 'mode': 'agent.work.normal',
              'codex_model': model or os.environ.get('FACTORY_SCHEDULER_MODEL', DEFAULT_MODEL)}
    request = AgentRequest(request_id=f'{task_id}-scheduler-{node_id}-{attempt}-{uuid.uuid4().hex}', channel_id='web',
                           session_id=f'{task_id}-scheduler-{node_id}-{attempt}', req_method=ReqMethod.CHAT_SEND,
                           params=params)
    log = Path(home).resolve() / 'sessions' / f'{task_id}.scheduler.jsonl'
    log.parent.mkdir(parents=True, exist_ok=True)
    started, outcome, calls = clock(), 'error', {}
    try:
        with log.open('a', encoding='utf-8') as out:
            def emit(payload):
                out.write(json.dumps({'t': clock(), **payload}, ensure_ascii=False, default=str) + '\n')
                out.flush()
            emit({'event': 'turn.start', 'node_id': node_id, 'attempt': attempt, 'model': params['codex_model']})
            async for chunk in stream(request):
                payload = getattr(chunk, 'payload', chunk)
                payload = payload if isinstance(payload, dict) else {'raw': str(payload)}
                emit(payload)
                kind = payload.get('event_type', payload.get('event'))
                if kind == 'chat.tool_call':
                    name = payload.get('tool_call', {}).get('name', 'unknown')
                    calls[name] = calls.get(name, 0) + 1
                if kind in {'chat.error', 'error'}:
                    outcome = 'stream_error'
            emit({'event': 'turn.end', 'node_id': node_id})
            outcome = 'ok' if outcome != 'stream_error' else 'error'
    finally:
        telemetry_emit(Path(home).resolve(), 'scheduler.turn', task_id, node_id=node_id, attempt=attempt,
                       duration_ms=(clock() - started) * 1000, tool_calls=calls, outcome=outcome,
                       model=params['codex_model'])
        if live is not None:
            from jiuwenswarm.server.runtime.codex_subscription.service import get_service
            await get_service().transport.close()
    return outcome


def run_subprocess(home, task_id, node_id, attempt=1):
    """Run one scheduler turn in its own process (own profile, transport and MCP server)."""
    argv = [sys.executable, '-m', 'jiuwenswarm.factory.scheduler_agent', '--home', str(home), '--task', task_id,
            '--node', node_id, '--attempt', str(attempt)]
    env = {k: v for k, v in os.environ.items() if not k.startswith('JIUWENSWARM_')}
    env['PYTHONPATH'] = os.pathsep.join(dict.fromkeys([str(ROOT), *filter(None, os.environ.get('PYTHONPATH', '').split(os.pathsep))]))
    try:
        return subprocess.run(argv, env=env, timeout=TURN_TIMEOUT_S + 60).returncode
    except subprocess.TimeoutExpired:
        return 124


def main(argv=None):
    parser = argparse.ArgumentParser(description='Finalize one preliminary node contract with the scheduler agent.')
    parser.add_argument('--home', required=True)
    parser.add_argument('--task', required=True)
    parser.add_argument('--node', required=True)
    parser.add_argument('--attempt', type=int, default=1)
    parser.add_argument('--model', help=f'Codex model (default FACTORY_SCHEDULER_MODEL or {DEFAULT_MODEL})')
    args = parser.parse_args(argv)
    configure(args.home, args.task)

    async def bounded():
        return await asyncio.wait_for(turn(args.home, args.task, args.node, args.attempt, model=args.model),
                                      TURN_TIMEOUT_S)
    try:
        outcome = asyncio.run(bounded())
    except asyncio.TimeoutError:
        outcome = 'timeout'
    print(json.dumps({'node_id': args.node, 'outcome': outcome}))
    return 0 if outcome == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
