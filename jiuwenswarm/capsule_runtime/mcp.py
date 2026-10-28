"""MCP server over stdio: each admitted capability capsule is one tool.

    python -m jiuwenswarm.capsule_runtime.mcp [--extra-dir DIR ...]
        [--worker-cmd CMD | --worker-openai-base-url URL --worker-model NAME]
        [--verifier-cmd CMD | --verifier-openai-base-url URL --verifier-model NAME] [--require-semantic]

Minimal JSON-RPC 2.0 (initialize, ping, tools/list, tools/call), one JSON message
per line, on purpose. The repo pins ``mcp>=1.28.1,<2`` (locked at 1.29.0) while hosts
may carry mcp 2.x, whose server API differs; a hand-written loop behaves the same
under both. Protocol traffic uses stdout only; diagnostics go to stderr.

Model capsules: ctx.model is backed by, in order, the configured worker backend,
else MCP sampling (``sampling/createMessage`` sent to the client, when the client
declared the sampling capability). With neither, the capsule halts with
stage 'worker', code 'no_model'. Model capsules are listed only when one of the two exists.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from jiuwenswarm.research.contracts import contract_schema

from . import verifier_backends
from .engine import Runtime, stage_lines

SUPPORTED = ('2025-06-18', '2025-03-26', '2024-11-05')
SERVER_INFO = {'name': 'capsule-runtime', 'version': '0.2.0'}
SAMPLING_MAX_TOKENS = 4096
OBJECTIVE = 'task_objective'


def _port_schema(port: dict) -> dict:
    try:
        schema = dict(contract_schema(port['schema_ref']))
        schema.pop('$schema', None)
        schema.pop('$id', None)
        if '$ref' in json.dumps(schema):  # references need the host registry; fall back to a plain object
            raise ValueError
    except Exception:
        schema = {'type': 'object'}
    schema['description'] = port['description'] + ' (' + port['schema_ref'] + ')'
    return schema


def needs_model(capsule) -> bool:
    return bool(capsule.declaration['needs']['injects'])


def tool_for(runtime: Runtime, key: str) -> dict:
    capsule = runtime.get(key)
    d = capsule.declaration
    inputs = d['ports']['inputs']
    effects = d['changes']['effects']
    guarantees = [
        'Source files are hash-pinned (release ' + capsule.release_hash[:12] + ') and rechecked on every call.',
        'Inputs are validated against ' + ', '.join(p['schema_ref'] for p in inputs) + ' before the worker runs.',
        'Outputs are returned only after the capsule checks pass: ' + ', '.join(d['guarantees']['acceptance']) + '.',
        'Time limit ' + str(int(capsule.wall_s)) + 's. Effects: ' + d['changes']['effect_class']
        + (' (' + ', '.join(e['op'] for e in effects) + ')' if effects else ' (none)') + '.',
        'Every call returns a receipt with hashes, check verdicts, model calls and timestamps.',
        'Verifier stages: ' + ' | '.join(stage_lines(capsule)) + '.',
    ]
    unanchored = d['guarantees'].get('unanchored') or []
    text = d['identity']['summary'] + '\n\nGuarantees:\n- ' + '\n- '.join(guarantees)
    if unanchored:
        text += '\n\nNot guaranteed:\n- ' + '\n- '.join(unanchored)
    properties = {p['name']: _port_schema(p) for p in inputs}
    required = [p['name'] for p in inputs if p['required']]
    if needs_model(capsule):
        properties[OBJECTIVE] = {'type': 'string', 'description': 'What the model should accomplish with the packet (the frozen task objective).'}
        required.append(OBJECTIVE)
        text += '\n\nUses a model for its work step (a backend configured on the server, else your client\'s sampling).'
    return {'name': key, 'description': text,
            'inputSchema': {'type': 'object', 'additionalProperties': False, 'properties': properties, 'required': required}}


class SamplingModel:
    """ctx.model backed by the calling client's model through sampling/createMessage."""
    kind = 'mcp_sampling'
    identity = 'mcp_sampling'
    model_name = None
    last_model = None
    last_usage = None

    def __init__(self, server: 'Server'):
        self.server = server

    async def __call__(self, prompt, system=None):
        params = {'messages': [{'role': 'user', 'content': {'type': 'text', 'text': prompt}}],
                  'maxTokens': SAMPLING_MAX_TOKENS, 'includeContext': 'none'}
        if system:
            params['systemPrompt'] = system
        result = await self.server.request('sampling/createMessage', params)
        content = result.get('content')
        if isinstance(content, list):
            content = content[0] if content else None
        if not isinstance(content, dict) or content.get('type') != 'text' or not isinstance(content.get('text'), str):
            raise RuntimeError('sampling reply was not text content')
        self.last_model = result.get('model')
        return content['text']


class Server:
    def __init__(self, runtime: Runtime, verifier_model=None, require_semantic: bool = False):
        self.runtime, self.verifier_model, self.require_semantic = runtime, verifier_model, require_semantic
        self.client_sampling = False
        self._pending: dict[str, asyncio.Future] = {}
        self._next = 0
        self._tasks: set = set()

    # --- startup --------------------------------------------------------
    def expose(self) -> list[str]:
        """Admit every loaded capsule (model capsules against a canned reply); the admitted ones are served."""
        names = []
        for key, capsule in self.runtime.capsules.items():
            if capsule.status != 'loaded':
                print('capsule_runtime: not exposed (%s): %s' % (key, capsule.reason), file=sys.stderr)
                continue
            result = self.runtime.admit(key)
            if result['passed']:
                names.append(key)
            else:
                print('capsule_runtime: not admitted (%s): %s' % (key, '; '.join(result['failures'])), file=sys.stderr)
        return names

    def visible(self) -> list[str]:
        has_model = self.runtime.worker_model is not None or self.client_sampling
        return [k for k in self.runtime.admitted if has_model or not needs_model(self.runtime.get(k))]

    # --- server -> client requests ---------------------------------------
    async def request(self, method: str, params: dict):
        self._next += 1
        ident = 'srv-%d' % self._next
        future = asyncio.get_running_loop().create_future()
        self._pending[ident] = future
        _write({'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params})
        try:
            reply = await future
        finally:
            self._pending.pop(ident, None)
        if 'error' in reply:
            raise RuntimeError('client refused %s: %s' % (method, reply['error'].get('message')))
        return reply.get('result') or {}

    def resolve(self, message: dict) -> bool:
        future = self._pending.get(message.get('id'))
        if future is None or future.done():
            return False
        future.set_result(message)
        return True

    # --- client -> server ------------------------------------------------
    async def handle(self, message: dict) -> dict | None:
        method, ident = message.get('method'), message.get('id')
        params = message.get('params') or {}
        if ident is None:  # notification
            return None
        try:
            if method == 'initialize':
                self.client_sampling = 'sampling' in (params.get('capabilities') or {})
                asked = params.get('protocolVersion')
                result = {'protocolVersion': asked if asked in SUPPORTED else SUPPORTED[0],
                          'capabilities': {'tools': {'listChanged': False}}, 'serverInfo': SERVER_INFO,
                          'instructions': 'Each tool is a verified capability capsule. A delivered result carries outputs '
                                          'and a receipt; a halted result carries the halt stage, code and reason and no outputs.'}
            elif method == 'ping':
                result = {}
            elif method == 'tools/list':
                result = {'tools': [tool_for(self.runtime, k) for k in self.visible()]}
            elif method == 'tools/call':
                result = await self._call(params)
            else:
                return {'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': 'Method not found: ' + str(method)}}
        except Exception as error:  # protocol-level fault, not a capsule halt
            return {'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32603, 'message': type(error).__name__ + ': ' + str(error)}}
        return {'jsonrpc': '2.0', 'id': ident, 'result': result}

    async def _call(self, params: dict) -> dict:
        name = params.get('name')
        if name not in self.runtime.admitted:
            return self._wrap({'status': 'halted', 'halt': {'stage': 'input_guard', 'code': 'unknown_capability',
                                                           'reason': 'No admitted capability named ' + repr(name)}})
        arguments = dict(params.get('arguments') or {})
        capsule = self.runtime.get(name)
        contract = None
        if needs_model(capsule):
            objective = arguments.pop(OBJECTIVE, None)
            if isinstance(objective, str) and objective.strip():
                contract = {'objective': objective}
        worker = None
        if self.runtime.worker_model is None and self.client_sampling:
            worker = SamplingModel(self)
        outcome = await self.runtime.ainvoke(name, arguments, worker_model=worker, contract=contract,
                                             verifier_model=self.verifier_model, require_semantic=self.require_semantic)
        return self._wrap(outcome)

    @staticmethod
    def _wrap(outcome: dict) -> dict:
        return {'isError': outcome['status'] != 'delivered',
                'content': [{'type': 'text', 'text': json.dumps(outcome, ensure_ascii=False, sort_keys=True)}]}


def _write(message: dict) -> None:
    sys.stdout.buffer.write((json.dumps(message, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8'))
    sys.stdout.buffer.flush()


async def serve(server: Server) -> None:
    """Read loop. Requests run as tasks so a tool call can wait on a sampling reply read by this same loop."""
    loop = asyncio.get_running_loop()

    async def answer(message):
        reply = await server.handle(message)
        if reply is not None:
            _write(reply)

    while True:
        line = await loop.run_in_executor(None, sys.stdin.buffer.readline)
        if not line:
            break
        text = line.decode('utf-8').strip()
        if not text:
            continue
        try:
            message = json.loads(text)
            if not isinstance(message, dict):
                raise ValueError('not an object')
        except ValueError:
            _write({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Parse error'}})
            continue
        if 'method' not in message and server.resolve(message):
            continue
        task = asyncio.create_task(answer(message))
        server._tasks.add(task)
        task.add_done_callback(server._tasks.discard)
    if server._tasks:
        await asyncio.gather(*server._tasks, return_exceptions=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--extra-dir', action='append', default=[])
    verifier_backends.add_arguments(parser, 'worker')
    verifier_backends.add_arguments(parser, 'verifier')
    args = parser.parse_args(argv)
    runtime = Runtime(args.extra_dir, worker_model=verifier_backends.from_args(args, 'worker'))
    server = Server(runtime, verifier_backends.from_args(args, 'verifier'), args.require_semantic)
    exposed = server.expose()
    print('capsule_runtime mcp: serving %d tool(s): %s' % (len(exposed), ', '.join(exposed)), file=sys.stderr)
    asyncio.run(serve(server))
    return 0


if __name__ == '__main__':
    sys.exit(main())
