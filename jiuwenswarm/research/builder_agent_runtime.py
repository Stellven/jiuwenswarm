"""Bounded OpenJiuwen ReAct runtime for the research Builder.

The provider callback and the dispatcher are invocation scoped. All filesystem
and process capabilities remain in the host dispatcher.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Awaitable, Callable, AsyncIterator

from openjiuwen.core.single_agent.schema.agent_card import AgentCard
from openjiuwen.core.foundation.llm.model_clients.base_model_client import BaseModelClient
from openjiuwen.core.foundation.llm.schema.config import ModelClientConfig, ModelRequestConfig
from openjiuwen.core.foundation.llm.schema.message import AssistantMessage
from openjiuwen.core.foundation.llm.schema.tool_call import ToolCall
from openjiuwen.core.foundation.llm.schema.message_chunk import AssistantMessageChunk
from openjiuwen.core.foundation.tool import Tool, ToolCard
from openjiuwen.core.single_agent.agents.react_agent import ReActAgent

MODEL_CLIENT = "ai4r_builder_governed"
TOOL_NAMES = (
    "list_files", "search_files", "read_file", "write_file", "apply_patch",
    "run_checks", "read_log", "submit_candidate", "report_blocked",
)
MAX_MESSAGE_BYTES = 2 * 1024 * 1024
MAX_TOOL_OUTPUT_BYTES = 64 * 1024
_CALLBACKS: dict[str, dict[str, Any]] = {}


class _BuilderClient(BaseModelClient):
    """Native Model client whose opaque ID resolves to this invocation's callback."""
    __client_name__ = MODEL_CLIENT

    def _validate_config(self) -> None:
        # No provider credentials or network client are used by this client.
        if self.model_client_config.client_id not in _CALLBACKS:
            raise ValueError("unknown scoped Builder model callback")

    async def invoke(self, messages, **kwargs):
        scope = _CALLBACKS.get(self.model_client_config.client_id)
        if scope is None:
            raise RuntimeError("Builder model callback scope has ended")
        if scope.get('failure') is not None:
            raise scope['failure']
        if scope["terminal"] is not None:
            value = scope["terminal"]
            display = {key: item for key, item in value.items() if key != "bundle_bytes"} if isinstance(value, dict) else value
            return AssistantMessage(content=json.dumps(display, ensure_ascii=False, default=str), finish_reason="stop",
                                    metadata={"runtime_source": "localfinalization"})
        if scope["model_calls"] >= scope["max_model_calls"]:
            scope["terminal"] = {"blocked": True, "reason": "model_call_limit"}
            return AssistantMessage(content=json.dumps(scope["terminal"]), finish_reason="stop",
                                    metadata={"runtime_source": "localfinalization"})
        if scope['tool_calls'] >= scope['max_tools']:
            scope['terminal']={'blocked':True,'reason':'tool_call_limit'}
            return AssistantMessage(content=json.dumps(scope['terminal']),finish_reason='stop',
                                    metadata={'runtime_source':'localfinalization'})
        scope["model_calls"] += 1
        system, prompt = _messages_to_prompt(messages, kwargs.get("tools"))
        try:
            raw = await scope["model_call"](prompt, system)
        except Exception as error:
            # The governed context marks one definitely failed transient call
            # retryable; ask again once so this counter and the context's call
            # ordinal advance together.
            if not getattr(error, "retryable", False) or scope.get("retried"):
                raise
            scope["retried"] = True
            scope["model_calls"] += 1
            raw = await scope["model_call"](prompt, system)
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise ValueError("Builder model response exceeds the message limit")
        try:
            value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys,
                               parse_constant=_reject_nonfinite_constant)
        except (ValueError, TypeError):
            value = None
        if isinstance(value, dict) and set(value) == {"action", "arguments"}:
            action, arguments = value["action"], value["arguments"]
            if action in TOOL_NAMES and type(arguments) is dict:
                return AssistantMessage(
                    tool_calls=[ToolCall(id=uuid.uuid4().hex, type="function", name=action,
                                         arguments=json.dumps(arguments, ensure_ascii=False))],
                    finish_reason="tool_calls",
                )
        # Let the native ReAct conversation continue with a local diagnostic.
        # _DispatchTool consumes this marker without crossing the host boundary.
        reason = "Invalid Builder action envelope: expected strict JSON with a known action and object arguments."
        scope["invalid_diagnostic"] = reason
        return AssistantMessage(
            tool_calls=[ToolCall(id=uuid.uuid4().hex, type="function", name="report_blocked",
                                 arguments=json.dumps({"reason": reason}))],
            finish_reason="tool_calls",
        )

    async def stream(self, messages, **kwargs):
        result = await self.invoke(messages, **kwargs)
        yield AssistantMessageChunk(content=result.content, finish_reason=result.finish_reason,
                                    tool_calls=result.tool_calls)

    async def generate_image(self, *args, **kwargs):
        raise NotImplementedError("Builder runtime does not support media generation")

    async def generate_speech(self, *args, **kwargs):
        raise NotImplementedError("Builder runtime does not support media generation")

    async def generate_video(self, *args, **kwargs):
        raise NotImplementedError("Builder runtime does not support media generation")


class _DispatchTool(Tool):
    def __init__(self, card, scope):
        super().__init__(card)
        self.scope = scope

    async def invoke(self, inputs, **kwargs):
        if self.scope.get('failure') is not None:
            raise self.scope['failure']
        self.scope["tool_calls"] += 1
        if self.scope["tool_calls"] > self.scope["max_tools"]:
            raise RuntimeError("Builder tool-call limit reached")
        name = self.card.name
        if self.scope.get("invalid_diagnostic") and name == "report_blocked":
            diagnostic = self.scope.pop("invalid_diagnostic")
            return diagnostic
        ordinal = self.scope["model_calls"]
        try:
            output = await self.scope["dispatch"](name, inputs or {}, ordinal)
        except BaseException as exc:
            # The SDK converts tool exceptions into conversation messages.
            # Keep protected stops fatal before it can ask the model again.
            self.scope['failure']=exc
            raise
        rendered = json.dumps(output, ensure_ascii=False, default=str)
        if len(rendered.encode("utf-8")) > MAX_TOOL_OUTPUT_BYTES:
            rendered = rendered.encode("utf-8")[:MAX_TOOL_OUTPUT_BYTES].decode("utf-8", "ignore")
        if name == "submit_candidate" and isinstance(output, dict) and output.get("submitted"):
            self.scope["terminal"] = output
        elif name == "report_blocked" or (isinstance(output,dict) and output.get('blocked') is True):
            self.scope["terminal"] = output if isinstance(output, dict) else {"blocked": True, "result": output}
            self.scope["terminal"].setdefault("blocked", True)
        return rendered

    async def stream(self, inputs, **kwargs) -> AsyncIterator[Any]:
        yield await self.invoke(inputs, **kwargs)


class _BuilderReActAgent(ReActAgent):
    async def _recover_from_model_exception(self, *args, **kwargs) -> bool:
        # Provider errors must not cause a hidden second request.
        return False


def _tool_arguments(name: str) -> dict[str, Any]:
    if name in {"list_files", "submit_candidate"}:
        return {"type": "object", "properties": {}, "additionalProperties": False}
    schemas = {
        "search_files": {"pattern": {"type": "string"}},
        "read_file": {"path": {"type": "string"}},
        "write_file": {"path": {"type": "string"}, "content": {"type": "string"}, "expected_sha256": {"type": "string"}},
        "apply_patch": {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}, "expected_sha256": {"type": "string"}},
        "run_checks": {"check": {"type": "string", "enum": ["compile", "unit", "smoke"]}, "test_name": {"type": "string"}},
        "read_log": {"ref": {"type": "object"}},
        "report_blocked": {"reason": {"type": "string"}},
    }
    required = [key for key in schemas[name] if key != "test_name"]
    return {"type": "object", "properties": schemas[name], "required": required, "additionalProperties": False}


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_nonfinite_constant(value):
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _messages_to_prompt(messages: Any, tools: Any = None) -> tuple[str, str]:
    if isinstance(messages, str):
        return "", messages
    if isinstance(messages, dict):
        messages = [messages]
    rows = []
    for message in messages or []:
        if hasattr(message, "model_dump"):
            row = message.model_dump(mode="json", exclude_none=True)
        elif isinstance(message, dict):
            row = message
        else:
            row = {key: getattr(message, key) for key in
                   ("role", "content", "tool_calls", "tool_call_id", "name")
                   if getattr(message, key, None) is not None}
        rows.append(row)
    systems = [row for row in rows if row.get("role") == "system"]
    system = json.dumps(systems, ensure_ascii=False, default=str)
    available = []
    for tool in tools or []:
        if hasattr(tool, "model_dump"):
            available.append(tool.model_dump(mode="json", exclude_none=True))
        elif isinstance(tool, dict):
            available.append(tool)
        else:
            available.append(str(tool))
    system += "\nReturn exactly one strict JSON object {\"action\": tool_name, \"arguments\": object}. "
    system += "Choose only from these native bounded tools and schemas: "
    system += json.dumps(available, ensure_ascii=False, default=str)
    prompt = json.dumps([row for row in rows if row.get("role") != "system"],
                        ensure_ascii=False, default=str)
    if len(system.encode("utf-8")) + len(prompt.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ValueError("Builder conversation exceeds the message limit")
    return system, prompt


async def run_builder_agent(*, model_call, dispatch, task: dict, session_id: str,
                            max_model_calls: int = 20, max_tools: int = 40,
                            timeout_s: float = 600) -> dict:
    """Run Builder actions through a native ReActAgent, one model call per action.

    ``dispatch(name, arguments, model_ordinal)`` is the sole capability boundary.
    ``model_call(prompt, system)`` supplies the approved provider route.
    """
    if not isinstance(task, dict) or not isinstance(session_id, str) or not session_id:
        raise ValueError("task must be a dict and session_id must be nonempty")
    if not (1 <= max_model_calls <= 20 and 1 <= max_tools <= 40 and 0 < timeout_s <= 600):
        raise ValueError("Builder runtime limits exceed policy")
    started = time.monotonic()
    client_id = "builder:" + uuid.uuid4().hex
    scope = {"model_call": model_call, "dispatch": dispatch, "terminal": None,
             "model_calls": 0, "tool_calls": 0, "max_model_calls": max_model_calls,
             "max_tools": max_tools, "invalid_diagnostic": None, 'failure':None}
    _CALLBACKS[client_id] = scope
    try:
        # Native setup and one ReAct iteration per action ensure provider
        # responses are represented by OpenJiuwen AssistantMessage/ToolCall.
        agent = _BuilderReActAgent(AgentCard(id="builder-" + uuid.uuid4().hex, name="Research Builder"))
        config = agent._config.model_copy(deep=True)
        config.model_client_config = ModelClientConfig(client_provider=MODEL_CLIENT, client_id=client_id,
                                                       max_retries=0)
        config.model_config_obj = ModelRequestConfig(model_name="governed-builder")
        config.model_name = "governed-builder"
        config.model_provider = MODEL_CLIENT
        config.parallel_tool_calls = False
        config.max_iterations = max_model_calls + 1
        config.mem_scope_id = ""
        config.context_processors = []
        config.sys_operation_id = None
        config.workspace = None
        agent.configure(config)
        tools = []
        for name in TOOL_NAMES:
            card = ToolCard(id="builder-tool-" + uuid.uuid4().hex, name=name,
                            description=f"Bounded Builder action: {name}",
                            input_params=_tool_arguments(name), parallel_safe=False)
            tool = _DispatchTool(card, scope)
            agent.ability_manager.add_ability(card, tool)
            tools.append(tool)
        # Passing the task as the initial user content keeps the SDK-native
        # conversation and tool-call/result history in its session context.
        query = json.dumps({"task": task, "session_id": session_id}, ensure_ascii=False)
        if len(query.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise ValueError("Builder task exceeds message limit")
        remaining = timeout_s - (time.monotonic() - started)
        if remaining <= 0:
            return {"blocked": True, "reason": "timeout", "session_id": session_id}
        try:
            result = await asyncio.wait_for(
                agent.invoke({"query": query, "conversation_id": session_id}), timeout=remaining)
        except asyncio.TimeoutError:
            return {"blocked": True, "reason": "timeout", "session_id": session_id}
        if scope.get('failure') is not None:
            raise scope['failure']
        if scope["terminal"] is not None:
            return scope["terminal"]
        output = result.get("output") if isinstance(result, dict) else None
        return {"blocked": True, "reason": "agent_finished_without_terminal_action",
                "session_id": session_id, "output": output}
    finally:
        _CALLBACKS.pop(client_id, None)
        # AbilityManager teardown removes its session-owned tool resources.
        try:
            agent.ability_manager.teardown_tools()
        except Exception:
            pass
