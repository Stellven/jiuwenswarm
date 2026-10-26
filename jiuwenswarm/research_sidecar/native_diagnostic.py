"""Ungated diagnostic execution with OpenJiuwen's native ReActAgent.

This is not an execution of the pinned upstream JiuwenSwarm harness and makes
no upstream-comparison claim. It imports no JiuwenSwarm agent, adapter, tool,
or policy code. The caller supplies bounded tools and the existing authorized
completion callback; OpenJiuwen owns the ReAct/tool-call loop. Results are
diagnostics and must never be submitted as accepted Benchmark custody.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import uuid
from typing import Any, AsyncIterator, Awaitable, Callable, Mapping

from openjiuwen.core.foundation.llm.model_clients.base_model_client import BaseModelClient
from openjiuwen.core.foundation.llm.schema.config import ModelClientConfig, ModelRequestConfig
from openjiuwen.core.foundation.llm.schema.message import AssistantMessage
from openjiuwen.core.foundation.llm.schema.message_chunk import AssistantMessageChunk
from openjiuwen.core.foundation.llm.schema.tool_call import ToolCall
from openjiuwen.core.foundation.tool import Tool, ToolCard
from openjiuwen.core.single_agent.agents.react_agent import ReActAgent
from openjiuwen.core.single_agent.schema.agent_card import AgentCard


OPENJIUWEN_CORE_COMMIT = "9e3390195a9ea15235b2b5f7412cb2aa440622cc"
MODEL_CLIENT = "ai4r_native_diagnostic_governed"
_CALLBACKS: dict[str, dict[str, Any]] = {}
_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_MAX_MESSAGE_BYTES = 2 * 1024 * 1024
_MAX_TOOL_OUTPUT_BYTES = 64 * 1024


def _reject_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def _messages_to_prompt(messages: Any, tools: Any) -> tuple[str, str]:
    rows = []
    for message in messages if isinstance(messages, (list, tuple)) else [messages]:
        if hasattr(message, "model_dump"):
            row = message.model_dump(mode="json", exclude_none=True)
        elif isinstance(message, Mapping):
            row = dict(message)
        else:
            raise ValueError("Unsupported native OpenJiuwen message")
        if row.get("role") not in {"system", "user", "assistant", "tool"}:
            raise ValueError("Unsupported message role")
        rows.append(row)
    systems = [{"role": row["role"], "content": row.get("content", "")}
               for row in rows if row["role"] == "system"]
    system = json.dumps(systems, ensure_ascii=False, separators=(",", ":"))
    public_tools = [{"name": tool["name"], "description": tool["description"],
                     "input_params": tool["input_params"]} for tool in tools]
    system += "\nReturn exactly one JSON object {\"action\": tool_name, \"arguments\": object}. "
    system += "Choose only from these bounded native tools and schemas: "
    system += json.dumps(public_tools, ensure_ascii=False, separators=(",", ":"))
    prompt = json.dumps([row for row in rows if row["role"] != "system"],
                        ensure_ascii=False, separators=(",", ":"))
    if len(system.encode("utf-8")) + len(prompt.encode("utf-8")) > _MAX_MESSAGE_BYTES:
        raise ValueError("Native agent conversation exceeds the byte limit")
    return system, prompt


class _NativeTool(Tool):
    def __init__(self, card: ToolCard, scope: dict[str, Any]):
        super().__init__(card)
        self.scope = scope

    async def invoke(self, inputs, **kwargs):
        scope = self.scope
        if scope["failure"] is not None:
            raise scope["failure"]
        if scope["tool_calls"] >= scope["max_tool_calls"]:
            raise RuntimeError("diagnostic tool-call ceiling reached")
        scope["tool_calls"] += 1
        ordinal = scope["tool_calls"]
        try:
            result = await scope["dispatch"](self.card.name, inputs or {}, ordinal)
        except BaseException as error:
            scope["failure"] = error
            raise
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False, default=str)
        if len(encoded.encode("utf-8")) > _MAX_TOOL_OUTPUT_BYTES:
            encoded = encoded.encode("utf-8")[:_MAX_TOOL_OUTPUT_BYTES].decode("utf-8", "ignore")
        scope["tool_trace"].append({"ordinal": ordinal, "tool": self.card.name,
                                    "arguments": inputs or {}, "result": encoded})
        return encoded

    async def stream(self, inputs, **kwargs) -> AsyncIterator[Any]:
        yield await self.invoke(inputs, **kwargs)


class _GovernedModelClient(BaseModelClient):
    """Native OpenJiuwen provider adapter; callback owns auth, identity and budget."""
    __client_name__ = MODEL_CLIENT

    def _validate_config(self) -> None:
        if self.model_client_config.max_retries != 0:
            raise ValueError("Native diagnostic transport retries must be disabled")
        if self.model_client_config.client_id not in _CALLBACKS:
            raise ValueError("Unknown authorized completion callback")

    async def invoke(self, messages, *, tools=None, **kwargs):
        scope = _CALLBACKS.get(self.model_client_config.client_id)
        if scope is None:
            raise RuntimeError("Authorized completion callback scope ended")
        if scope["failure"] is not None:
            raise scope["failure"]
        if scope["model_calls"] >= scope["max_model_calls"]:
            raise RuntimeError("diagnostic model-call ceiling reached")
        scope["model_calls"] += 1
        system, prompt = _messages_to_prompt(messages, scope["tool_specs"])
        raw = await scope["model_call"](prompt, system)
        if isinstance(raw, Mapping):
            raw = raw.get("text")
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > _MAX_MESSAGE_BYTES:
            raise ValueError("Authorized completion returned invalid or oversized text")
        scope["model_trace"].append({"ordinal": scope["model_calls"], "raw_emission": raw})
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        if (type(value) is not dict or set(value) != {"action", "arguments"}
                or type(value["action"]) is not str or type(value["arguments"]) is not dict):
            raise ValueError("Completion must select one listed tool or unsupported with object arguments")
        if value["action"] == "unsupported":
            if set(value["arguments"]) != {"reason"} or not isinstance(value["arguments"]["reason"], str):
                raise ValueError("Unsupported abstention requires exactly one reason string")
            scope["abstention"] = value["arguments"]["reason"][:2048]
            return AssistantMessage(content="Unsupported: " + scope["abstention"], finish_reason="stop")
        if value["action"] not in scope["tool_names"]:
            raise ValueError("Completion selected a tool outside the explicit allowlist")
        from jsonschema import Draft202012Validator
        spec = next(row for row in scope["tool_specs"] if row["name"] == value["action"])
        errors = sorted(Draft202012Validator(spec["input_params"]).iter_errors(value["arguments"]),
                        key=lambda error: list(error.absolute_path))
        if errors:
            raise ValueError("Completion tool arguments failed the declared input schema")
        return AssistantMessage(tool_calls=[ToolCall(
            id=uuid.uuid4().hex, type="function", name=value["action"],
            arguments=json.dumps(value["arguments"], ensure_ascii=False))], finish_reason="tool_calls")

    async def stream(self, messages, **kwargs):
        response = await self.invoke(messages, **kwargs)
        yield AssistantMessageChunk(content=response.content, finish_reason=response.finish_reason,
                                    tool_calls=response.tool_calls)

    async def generate_image(self, *args, **kwargs):
        raise ValueError("Media calls are disabled in the diagnostic")

    async def generate_speech(self, *args, **kwargs):
        raise ValueError("Media calls are disabled in the diagnostic")

    async def generate_video(self, *args, **kwargs):
        raise ValueError("Media calls are disabled in the diagnostic")


class _NoRetryReActAgent(ReActAgent):
    async def _recover_from_model_exception(self, *args, **kwargs) -> bool:
        return False


async def run_native_diagnostic(*, case_id: str, task: Any, tool_specs: list[dict[str, Any]],
                                  model_call: Callable[[str, str], Awaitable[Any]],
                                  dispatch: Callable[[str, dict[str, Any], int], Awaitable[Any]],
                                  model: str, max_model_calls: int = 8,
                                  max_tool_calls: int = 12, timeout_s: float = 300) -> dict[str, Any]:
    """Run a native upstream ReAct agent and return explicitly ungated diagnostics.

    This uses the native OpenJiuwen core ReActAgent, not the upstream
    JiuwenSwarm application. `model_call` must be the caller's existing authorized, budgeted completion
    callback. The callback's one plain-text response chooses one JSON action;
    this module converts that into OpenJiuwen's native ToolCall protocol.
    `dispatch` is the complete capability boundary. No product acceptance,
    benchmark custody, or evaluation gate is emitted here.
    """
    if not isinstance(model, str) or not model.strip():
        raise ValueError("An exact selected model name is required")
    if not isinstance(case_id, str) or not case_id.strip() or len(case_id) > 128:
        raise ValueError("A stable case identity is required")
    if (type(max_model_calls) is not int or not 1 <= max_model_calls <= 20
            or type(max_tool_calls) is not int or not 1 <= max_tool_calls <= 40
            or not isinstance(timeout_s, (int, float)) or not 0 < timeout_s <= 600):
        raise ValueError("Requested diagnostic ceilings exceed hard limits")
    if not isinstance(tool_specs, list) or not tool_specs:
        raise ValueError("At least one explicitly bounded tool is required")
    normalized = []
    names = set()
    for spec in tool_specs:
        if (type(spec) is not dict or set(spec) != {"name", "description", "input_params"}
                or not isinstance(spec["name"], str) or not _NAME.fullmatch(spec["name"])
                or spec["name"] in names or not isinstance(spec["description"], str)
                or type(spec["input_params"]) is not dict
                or spec["input_params"].get("type") != "object"):
            raise ValueError("Tool specs must be unique named objects with object input schemas")
        names.add(spec["name"])
        from jsonschema import Draft202012Validator
        Draft202012Validator.check_schema(spec["input_params"])
        normalized.append(json.loads(json.dumps(spec, allow_nan=False)))
    if not callable(model_call) or not callable(dispatch):
        raise ValueError("Authorized completion and bounded dispatcher callbacks are required")
    client_id = "native-diagnostic:" + uuid.uuid4().hex
    scope = {"model_call": model_call, "dispatch": dispatch, "tool_specs": normalized,
             "tool_names": names, "model_calls": 0, "tool_calls": 0,
             "max_model_calls": max_model_calls, "max_tool_calls": max_tool_calls,
             "model_trace": [], "tool_trace": [], "failure": None, "abstention": None}
    _CALLBACKS[client_id] = scope
    agent = None
    started = time.monotonic()
    try:
        agent = _NoRetryReActAgent(AgentCard(id=client_id, name="Ungated Native Diagnostic"))
        config = agent._config.model_copy(deep=True)
        config.model_client_config = ModelClientConfig(client_provider=MODEL_CLIENT,
            client_id=client_id, max_retries=0, timeout=min(float(timeout_s), 600))
        config.model_config_obj = ModelRequestConfig(model_name=model)
        config.model_name = model
        config.model_provider = MODEL_CLIENT
        config.parallel_tool_calls = False
        config.max_iterations = max_model_calls + 1
        config.mem_scope_id = ""
        config.context_processors = []
        config.sys_operation_id = None
        config.workspace = None
        agent.configure(config)
        for spec in normalized:
            card = ToolCard(id="native-diagnostic-tool:" + uuid.uuid4().hex,
                name=spec["name"], description=spec["description"],
                input_params=spec["input_params"], parallel_safe=False)
            agent.ability_manager.add_ability(card, _NativeTool(card, scope))
        query = json.dumps({"task": task}, ensure_ascii=False, allow_nan=False, default=str)
        if len(query.encode("utf-8")) > _MAX_MESSAGE_BYTES:
            raise ValueError("Diagnostic input exceeds the byte limit")
        task_sha256 = hashlib.sha256(query.encode("utf-8")).hexdigest()
        tool_spec_sha256 = hashlib.sha256(json.dumps(normalized, ensure_ascii=False,
            allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        result = await asyncio.wait_for(agent.invoke({"query": query,
            "conversation_id": "native-diagnostic:" + uuid.uuid4().hex}),
            timeout=max(0.001, float(timeout_s) - (time.monotonic() - started)))
        if scope["failure"] is not None:
            raise scope["failure"]
        output = result.get("output") if isinstance(result, dict) else None
        return {"diagnostic_only": True, "product_accepted": False,
            "comparison_claim": "none; not raw upstream JiuwenSwarm",
            "execution": {"agent": "openjiuwen.core.single_agent.ReActAgent",
                          "openjiuwen_core_commit": OPENJIUWEN_CORE_COMMIT},
            "case_id": case_id, "task_sha256": task_sha256,
            "tool_spec_sha256": tool_spec_sha256,
            "requested_model": model, "model_calls": scope["model_calls"],
            "tool_calls": scope["tool_calls"], "abstention": scope["abstention"],
            "model_trace": scope["model_trace"], "tool_trace": scope["tool_trace"],
            "elapsed_s": time.monotonic() - started, "output": output}
    finally:
        _CALLBACKS.pop(client_id, None)
        if agent is not None:
            try:
                agent.ability_manager.teardown_tools()
            except Exception:
                pass
