"""Generic, host-governed native ReAct worker; no provider or storage access.

``invoke_model(prompt, system)`` returns the builder's strict JSON action envelope.
Host tools are async keyword-argument callables. A tool result with a ``candidate``
key replaces the JSON candidate; either builtin also accepts ``candidate``.
``run_checks()`` checks the current snapshot. ``check_runner(candidate)`` returns
a list of {check_id, status: 'pass'|'fail', diagnostic?: str} receipts. Missing,
duplicate or malformed required receipts fail closed. One failed batch consumes
one repair round; max_repair_rounds permits that many retries after first failure.

Returned blobs are exact canonical JSON bytes keyed by SHA256. Trace verification
policy must include its identity, builtin tool names, required_pre_submit_checks
(from required_checks), and an explicit claim_coverage_required setting. This
worker makes no scientific claims; it does not infer claims from model output.
"""
from __future__ import annotations

import asyncio
import copy
from functools import cache
import hashlib
import json
import math
import time
import uuid

from .state import json_bytes


class _Halt(Exception):
    pass


@cache
def _client_type():
    from . import builder_agent_runtime as n

    class WorkerClient(n._BuilderClient):
        __client_name__ = 'ai4r_worker_governed'

        async def invoke(self, messages, **kwargs):
            scope = n._CALLBACKS[self.model_client_config.client_id]
            if scope['failure'] is not None:
                raise scope['failure']
            if scope['terminal'] is not None:
                return n.AssistantMessage(content='Worker stopped.', finish_reason='stop')
            system, prompt = n._messages_to_prompt(messages, kwargs.get('tools'))
            scope['model_calls'] += 1
            action, arguments = await scope['model'](prompt, system)
            # Route unknown actions to the host instead of SDK tool lookup.
            scope['requested_action'] = action
            return n.AssistantMessage(tool_calls=[n.ToolCall(
                id=uuid.uuid4().hex, type='function',
                name=action if action in scope['names'] else 'run_checks',
                arguments=json.dumps(arguments, ensure_ascii=False))], finish_reason='tool_calls')

    return WorkerClient


class ReActAdapter:
    """Invocation-scoped native adapter, importing the SDK only when constructed."""

    def __init__(self):
        from . import builder_agent_runtime as native
        self.native = native
        _client_type()

    async def run(self, task, names, model, dispatch, max_calls, max_tools):
        n = self.native
        client_id = 'worker:' + uuid.uuid4().hex
        provider = 'ai4r_worker_governed'
        scope = dict(terminal=None, failure=None, model_calls=0, tool_calls=0,
                     max_model_calls=max_calls, max_tools=max_tools,
                     invalid_diagnostic=None, model=model, names=names)

        async def route(_name, arguments, ordinal):
            return await dispatch(scope.pop('requested_action'), arguments, ordinal)

        scope['dispatch'] = route
        n._CALLBACKS[client_id] = scope
        agent = None
        try:
            agent = n._BuilderReActAgent(n.AgentCard(id=client_id, name='Research Worker'))
            config = agent._config.model_copy(deep=True)
            config.model_client_config = n.ModelClientConfig(
                client_provider=provider, client_id=client_id, max_retries=0)
            config.model_config_obj = n.ModelRequestConfig(model_name='governed-worker')
            config.model_name = 'governed-worker'
            config.model_provider = provider
            config.parallel_tool_calls = False
            config.max_iterations = max_calls + 1
            config.mem_scope_id = ''
            config.context_processors = []
            config.sys_operation_id = None
            config.workspace = None
            agent.configure(config)
            for name in names:
                schema = {'type': 'object', 'additionalProperties': True}
                if name in ('run_checks', 'submit_candidate'):
                    schema = {'type': 'object', 'properties': {'candidate': {}},
                              'additionalProperties': False}
                card = n.ToolCard(id=uuid.uuid4().hex, name=name,
                                 description=f'Host governed action: {name}',
                                 input_params=schema, parallel_safe=False)
                agent.ability_manager.add_ability(card, n._DispatchTool(card, scope))
            await agent.invoke({'query': json_bytes(task).decode(), 'conversation_id': client_id})
            if scope['failure'] is not None:
                raise scope['failure']
        finally:
            n._CALLBACKS.pop(client_id, None)
            if agent is not None:
                agent.ability_manager.teardown_tools()


async def run_agent_worker(policy, task, invoke_model, tools, check_runner, trace):
    """Run a bounded native worker; return manifest/blobs and only submitted output.

    All inputs and callback outputs must be finite JSON. Callbacks are trusted
    async host capabilities and must cooperate with asyncio cancellation. External
    cancellation propagates; callback errors halt without accepting a candidate.
    """
    policy = copy.deepcopy(policy)
    allowed = policy['allowed_tools']
    required = policy['required_checks']
    for values in (allowed, required):
        if (type(values) is not list or len(values) > 64 or
                any(type(v) is not str or not v or len(v) > 128 for v in values) or
                len(set(values)) != len(values)):
            raise ValueError('tool/check ids must be distinct bounded strings')
    builtins = ('run_checks', 'submit_candidate')
    if set(allowed) & set(builtins) or any(not callable(tools.get(k)) for k in allowed):
        raise ValueError('allowed host tools must exist and cannot replace builtins')
    for key in ('max_model_calls', 'max_tool_calls', 'max_repair_rounds'):
        value = policy[key]
        if type(value) is not int or value < (0 if key == 'max_repair_rounds' else 1):
            raise ValueError('invalid call/repair budget')
    if policy['max_repair_rounds'] > 3:
        raise ValueError('at most three repair rounds')
    wall = policy['wall_s']
    if type(wall) not in (int, float) or not math.isfinite(wall) or wall <= 0:
        raise ValueError('wall_s must be positive and finite')
    deadline = time.monotonic() + wall
    blobs = {}
    candidate = None
    candidate_ref = None
    passed_digest = None
    diagnostics = []
    model_calls = tool_calls = failures = 0
    submitted = False
    limit = 2 * 1024 * 1024

    def blob(value):
        raw = json_bytes(value)
        if len(raw) > limit:
            raise _Halt('payload_limit')
        digest = hashlib.sha256(raw).hexdigest()
        blobs[digest] = raw
        return {'sha256': digest}

    def clock_check():
        if time.monotonic() >= deadline:
            raise _Halt('wall_time_limit')

    def replace(value):
        nonlocal candidate, candidate_ref, passed_digest
        ref = blob(value)
        if ref != candidate_ref:
            candidate = copy.deepcopy(value)
            candidate_ref = ref
            passed_digest = None
            trace.append_event('artifact_write', 'worker', result_ref=ref,
                               detail={'candidate_sha256': ref['sha256']})

    async def model(prompt, system):
        nonlocal model_calls
        clock_check()
        if model_calls >= policy['max_model_calls']:
            raise _Halt('model_call_limit')
        if tool_calls >= policy['max_tool_calls']:
            raise _Halt('tool_call_limit')
        model_calls += 1
        args_ref = blob({'prompt': prompt, 'system': system})
        try:
            raw = await invoke_model(prompt, system)
            result_ref = blob(raw)
        except BaseException as exc:
            trace.append_event('model_call', 'model', args_ref=args_ref,
                               result_ref=blob({'error': type(exc).__name__}))
            raise
        trace.append_event('model_call', 'model', args_ref=args_ref, result_ref=result_ref)
        clock_check()
        n = adapter.native
        try:
            if not isinstance(raw, str):
                raise ValueError('expected JSON text')
            value = json.loads(raw, object_pairs_hook=n._reject_duplicate_keys,
                               parse_constant=n._reject_nonfinite_constant)
            if (type(value) is not dict or set(value) != {'action', 'arguments'} or
                    type(value['action']) is not str or not value['action'] or
                    len(value['action']) > 128 or type(value['arguments']) is not dict):
                raise ValueError('invalid action envelope')
            return value['action'], value['arguments']
        except (ValueError, TypeError):
            return '<invalid_action>', {}

    async def dispatch(name, args, _ordinal):
        nonlocal tool_calls, passed_digest, diagnostics, failures, submitted
        tool_calls += 1
        args_ref = blob(args)
        trace.append_event('tool_call', name, args_ref=args_ref)
        halt = None
        try:
            clock_check()
            if tool_calls > policy['max_tool_calls']:
                raise _Halt('tool_call_limit')
            if name not in (*allowed, *builtins):
                output = {'ok': False, 'reason': 'tool_not_allowed'}
            elif name in builtins:
                if set(args) - {'candidate'}:
                    output = {'ok': False, 'reason': 'invalid_arguments'}
                else:
                    if 'candidate' in args:
                        replace(args['candidate'])
                    if candidate_ref is None:
                        output = {'ok': False, 'reason': 'candidate_missing'}
                    elif name == 'submit_candidate':
                        if passed_digest != candidate_ref['sha256']:
                            output = {'ok': False, 'reason': 'current_candidate_not_checked'}
                        else:
                            submitted = True
                            output = {'submitted': True, 'candidate_sha256': passed_digest}
                    else:
                        passed_digest = None
                        try:
                            reports = await check_runner(copy.deepcopy(candidate))
                        except BaseException as exc:
                            reports = []
                            halt = exc
                        valid = type(reports) is list and all(type(r) is dict for r in reports)
                        rows = reports if valid else []
                        diagnostics = []
                        passing = valid
                        for cid in required or ['__batch__']:
                            matches = [r for r in rows if r.get('check_id') == cid]
                            row = matches[0] if len(matches) == 1 else {}
                            ok = (row.get('status') == 'pass' if required else valid) and halt is None
                            passing = passing and ok
                            diagnostic = str(row.get('diagnostic', 'missing or invalid receipt'))[:128]
                            receipt = dict(check_id=cid, runner='check_runner',
                                           candidate_sha256=candidate_ref['sha256'],
                                           status='pass' if ok else 'fail', diagnostic=diagnostic)
                            trace.append_event('check_run', 'check_runner', input_refs=[candidate_ref],
                                               result_ref=blob(receipt), detail={
                                                   'check_id': cid, 'candidate_sha256': candidate_ref['sha256']})
                            diagnostics.append({'check_id': cid, 'status': receipt['status'],
                                                'diagnostic': diagnostic})
                        clock_check()
                        if passing and halt is None:
                            passed_digest = candidate_ref['sha256']
                        else:
                            failures += 1
                            if failures > policy['max_repair_rounds'] and halt is None:
                                halt = _Halt('repair_round_limit')
                        output = {'ok': passed_digest is not None, 'diagnostics': diagnostics}
            else:
                output = await tools[name](**copy.deepcopy(args))
                if isinstance(output, dict) and 'candidate' in output:
                    replace(output['candidate'])
            clock_check()
            # Arbitrary host tool output cannot terminate the native dispatcher.
            output = {'result': output} if name in allowed else output
            result_ref = blob(output)
        except BaseException as exc:
            halt = exc
            submitted = False
            result_ref = blob({'error': type(exc).__name__})
        trace.append_event('tool_result', name, args_ref=args_ref, result_ref=result_ref)
        if halt is not None:
            raise halt
        if submitted:
            trace.append_event('submit', 'worker', args_ref=args_ref, result_ref=candidate_ref,
                               detail={'candidate_sha256': candidate_ref['sha256']})
        return output

    reason = None
    try:
        blob(task)
        adapter = ReActAdapter()
        clock_check()
        await asyncio.wait_for(adapter.run(task, (*allowed, *builtins), model, dispatch,
                                          policy['max_model_calls'], policy['max_tool_calls']),
                               timeout=max(0, deadline - time.monotonic()))
        if not submitted:
            reason = 'agent_finished_without_submit'
    except asyncio.TimeoutError:
        reason = 'wall_time_limit'
    except _Halt as exc:
        reason = str(exc)
    except Exception as exc:
        reason = 'runtime_error:' + type(exc).__name__
    status = 'submitted' if submitted and reason is None else 'halted'
    manifest = trace.finalize({'status': 'succeeded' if status == 'submitted' else 'failed',
                               'final_artifact_sha256': candidate_ref['sha256'] if status == 'submitted' else None}, [])
    result = dict(status=status, manifest=manifest, blobs=blobs, last_diagnostics=diagnostics)
    if status == 'submitted':
        result['candidate'] = copy.deepcopy(candidate)
    else:
        result['reason'] = reason
    return result
