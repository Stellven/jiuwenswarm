"""Headless *application* baseline, with JiuwenSwarm owning tools and planning.

No inference on import/preflight. ``run`` starts a fresh process, never a server.
The completion bridge uses the existing LocalModelClient subscription relay;
Codex remains completion-only while the unmodified native application dispatches
its normal tools. Run directories are exclusive and never resumed/replayed.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import uuid

PROVIDER = "native_value_governed"
CORE_PIN = "9e3390195a9ea15235b2b5f7412cb2aa440622cc"
EFFORTS = ("low", "medium", "high")   # file broker only; the subscription binding path stays medium
MODES = ("agent.work.normal", "agent.work.plan", "team.work.normal", "team.work.plan")
WIRE_INSTRUCTION = """You are the completion engine for the native JiuwenSwarm application.
Follow the supplied conversation's instructions. The host owns and executes the
advertised tools. Return exactly one JSON object with keys content (string) and
tool_calls (array). Each tool call has name (an advertised name) and arguments
(an object matching its schema). Use an empty array for a final response.
You may plan, inspect, execute ordinary code, and self-check using these tools.
Do not claim a tool ran until its result appears in the conversation.
"""


def plain(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if is_dataclass(value):
        return plain(asdict(value))
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(plain(value), stream, ensure_ascii=False, allow_nan=False, indent=2)


def load_spec(path):
    spec = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    allowed = {"variant", "task", "binding", "inputs_dir", "skill_dirs", "mode",
               "max_model_calls", "max_tool_calls", "wall_time_s", "config_template",
               "completion_directory", "model", "reasoning_effort"}
    if not isinstance(spec, dict) or set(spec) - allowed:
        raise ValueError("Unknown baseline configuration fields")
    if spec.get("variant") not in {"native", "native-skills"}:
        raise ValueError("variant must be native or native-skills")
    if not isinstance(spec.get("task"), str) or not spec["task"].strip():
        raise ValueError("A public task is required")
    spec.setdefault("mode", "agent.work.normal")
    if spec["mode"] not in MODES:
        raise ValueError("Unsupported native application mode")
    # Per-arm ceilings can match the integrated policy's aggregate 80 calls.
    # This local ceiling grants no dispatch authority: the host's shared
    # campaign reservation/claim remains authoritative for every completion.
    for key, default, maximum in (("max_model_calls", 12, 80), ("max_tool_calls", 30, 80),
                                  ("wall_time_s", 300, 600)):
        spec.setdefault(key, default)
        if type(spec[key]) is not int or not 1 <= spec[key] <= maximum:
            raise ValueError("Invalid " + key)
    spec.setdefault("skill_dirs", [])
    if not isinstance(spec["skill_dirs"], list):
        raise ValueError("skill_dirs must be a list of individual skill directories")
    if (spec["variant"] == "native" and spec["skill_dirs"] or
            spec["variant"] == "native-skills" and not spec["skill_dirs"]):
        raise ValueError("Only native-skills accepts and requires skill_dirs")
    for name in ("binding", "inputs_dir", "config_template", "completion_directory"):
        if name in spec and not Path(spec[name]).is_absolute():
            raise ValueError(name + " must be absolute")
    if ("binding" in spec) == ("completion_directory" in spec):
        raise ValueError("Require exactly one existing binding or completion_directory")
    if "completion_directory" in spec:
        if spec.get("model") not in {"gpt-6.1-sol", "gpt-6-luna"} or spec.get("reasoning_effort") not in EFFORTS:
            raise ValueError("File broker requires explicit approved model and effort (low, medium or high)")
    for skill in spec["skill_dirs"]:
        root = Path(skill)
        if not root.is_absolute() or not (root / "SKILL.md").is_file():
            raise ValueError("Each skill requires an absolute directory containing SKILL.md")
    return spec


def preflight(spec):
    blockers = []
    for module in ("openjiuwen", "yaml", "jsonschema", "jiuwenswarm"):
        if importlib.util.find_spec(module) is None:
            blockers.append("missing dependency: " + module)
    if "openjiuwen" not in " ".join(blockers):
        try:
            direct = json.loads(importlib.metadata.distribution("openjiuwen").read_text("direct_url.json") or "{}")
            if direct.get("vcs_info", {}).get("commit_id") != CORE_PIN:
                blockers.append("installed OpenJiuwen pin differs or is unreported")
        except Exception as exc:
            blockers.append("OpenJiuwen distribution unavailable: " + type(exc).__name__)
    if "binding" in spec and not Path(spec["binding"]).is_file():
        blockers.append("governed binding file unavailable")
    if "completion_directory" in spec and not Path(spec["completion_directory"]).is_dir():
        blockers.append("private completion broker directory unavailable")
    return {"ready": not blockers, "blockers": blockers,
            "inference_performed": False, "native_harness_smoke_passed": False,
            "variant": spec["variant"], "mode": spec["mode"]}


def tool_definitions(tools):
    result = {}
    for tool in plain(tools or []):
        if not isinstance(tool, dict):
            raise ValueError("Native tool schema is not serializable")
        function = tool.get("function", tool)
        name = function.get("name")
        if not isinstance(name, str) or not name or name in result:
            raise ValueError("Missing/duplicate native tool name")
        result[name] = function.get("parameters", function.get("input_schema", {}))
    return result


def parse_completion(raw, tools):
    from jsonschema import validate
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("Duplicate completion key")
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    if (not isinstance(value, dict) or set(value) != {"content", "tool_calls"}
            or not isinstance(value["content"], str) or not isinstance(value["tool_calls"], list)):
        raise ValueError("Expected content and tool_calls completion envelope")
    advertised = tool_definitions(tools)
    for call in value["tool_calls"]:
        if (not isinstance(call, dict) or set(call) != {"name", "arguments"}
                or call["name"] not in advertised or not isinstance(call["arguments"], dict)):
            raise ValueError("Unadvertised or malformed native tool call")
        validate(call["arguments"], advertised[call["name"]])
    return value


class CompletionScope:
    """One run's budget and raw evidence; a failure latches before any retries."""
    def __init__(self, complete, spec, evidence):
        self.complete, self.spec, self.evidence = complete, spec, Path(evidence)
        self.calls = self.selected_tools = 0
        self.failure = None
        self.lock = asyncio.Lock()
        self.deadline = time.monotonic() + spec["wall_time_s"]

    async def invoke(self, messages, tools=None):
        queued = time.monotonic()
        async with asyncio.timeout(max(.001, self.deadline - queued)):
            async with self.lock:
                return await self._invoke(messages, tools, queue_wait_s=time.monotonic() - queued)

    async def _invoke(self, messages, tools=None, *, queue_wait_s):
        if self.failure:
            raise RuntimeError(self.failure)
        try:
            if self.calls >= self.spec["max_model_calls"] or time.monotonic() >= self.deadline:
                raise RuntimeError("native_model_budget_exhausted")
            self.calls += 1
            ordinal = self.calls
            packet = {"messages": plain(messages), "tools": plain(tools or [])}
            prompt = WIRE_INSTRUCTION + "\n" + json.dumps(packet, ensure_ascii=False, allow_nan=False)
            write(self.evidence / f"completion-{ordinal:03d}-request.json", {**packet, "queue_wait_s": queue_wait_s})
            result = await self.complete(prompt, min(self.deadline - time.monotonic(), 120))
            write(self.evidence / f"completion-{ordinal:03d}-response.json", result)
            value = parse_completion(result["text"], tools)
            self.selected_tools += len(value["tool_calls"])
            if self.selected_tools > self.spec["max_tool_calls"]:
                raise RuntimeError("native_tool_budget_exhausted")
            return value
        except BaseException as exc:
            self.failure = type(exc).__name__ + ": " + str(exc)
            raise


async def file_completion(directory, prompt, timeout, *, model, effort="medium"):
    """Private shared-directory transport; host alone possesses Codex credentials.

    The request stays durable after timeout. Never retry or delete it: the host
    controller must reconcile its actual effect before any further dispatch.
    """
    root = Path(directory)
    request_id = uuid.uuid4().hex
    request = {"schema": "native-value-completion-request:1", "request_id": request_id,
               "prompt": prompt, "timeout_s": timeout, "model": model, "reasoning_effort": effort}
    temporary = root / (request_id + ".request.tmp")
    write(temporary, request)
    temporary.rename(root / (request_id + ".request.json"))
    response_path = root / (request_id + ".response.json")
    async with asyncio.timeout(timeout + 5):
        while not response_path.exists():
            await asyncio.sleep(0.1)
    response = json.loads(response_path.read_text(encoding="utf-8"))
    if (response.get("schema") != "native-value-completion-response:1"
            or response.get("request_id") != request_id):
        raise RuntimeError("Invalid completion broker response")
    if response.get("status") != "completed":
        raise RuntimeError("Completion broker " + str(response.get("status")) + ": " + str(response.get("error")))
    if (response.get("identity", {}).get("effective") != model
            or response.get("reasoning_effort") != effort or not isinstance(response.get("text"), str)):
        raise RuntimeError("Completion broker model/effort identity mismatch")
    return response


@contextmanager
def registered_bridge(scope):
    """Register native Model client; no replacement agent or dispatcher."""
    from openjiuwen.core.foundation.llm.model_clients.base_model_client import BaseModelClient
    from openjiuwen.core.foundation.llm.schema.message import AssistantMessage
    from openjiuwen.core.foundation.llm.schema.message_chunk import AssistantMessageChunk
    from openjiuwen.core.foundation.llm.schema.tool_call import ToolCall

    class NativeValueModelClient(BaseModelClient):
        __client_name__ = PROVIDER

        def _validate_config(self):
            if self.model_client_config.max_retries != 0:
                raise ValueError("Native baseline model retries must be zero")

        async def invoke(self, messages, *, tools=None, **kwargs):
            value = await scope.invoke(messages, tools)
            calls = [ToolCall(id=uuid.uuid4().hex, type="function", name=call["name"],
                              arguments=json.dumps(call["arguments"], ensure_ascii=False))
                     for call in value["tool_calls"]]
            return AssistantMessage(content=value["content"], tool_calls=calls or None,
                                    finish_reason="tool_calls" if calls else "stop")

        async def stream(self, messages, **kwargs):
            response = await self.invoke(messages, **kwargs)
            yield AssistantMessageChunk(content=response.content, tool_calls=response.tool_calls,
                                        finish_reason=response.finish_reason)

        async def generate_image(self, *args, **kwargs):
            raise NotImplementedError("Native value baseline is text and ordinary code only")
        generate_speech = generate_image
        generate_video = generate_image

    try:
        yield NativeValueModelClient
    finally:
        scope.failure = scope.failure or "completion_scope_closed"


def child_environment(root):
    root = Path(root).resolve()
    env = dict(os.environ)
    for key in tuple(env):
        if key.startswith(("AI4R_", "JIUWENSWARM_")) or key in {
                "API_KEY", "API_BASE", "MODEL_NAME", "MODEL_PROVIDER", "OPENAI_API_KEY",
                "ANTHROPIC_API_KEY", "CODEX_HOME"}:
            env.pop(key, None)
    env.update(JIUWENSWARM_HOME=str(root / "home"), JIUWENSWARM_DATA_DIR=str(root / "state"),
               JIUWENSWARM_AGENT_SDK="harness", JIUWENSWARM_M1_PROFILE="0",
               HOME=str(root / "home"), USERPROFILE=str(root / "home"),
               PYTHONDONTWRITEBYTECODE="1")
    return env


def copy_tree(source, target):
    source = Path(source)
    if source.is_symlink() or any(path.is_symlink() for path in source.rglob("*")):
        raise ValueError("Input and skill snapshots must not contain symlinks")
    shutil.copytree(source, target, dirs_exist_ok=True)


def config_template(spec):
    """Resolve resources beside the actual native package, including overlays."""
    if spec.get("config_template"):
        template = Path(spec["config_template"])
    else:
        package = importlib.util.find_spec("jiuwenswarm")
        if package is None or not package.origin:
            raise RuntimeError("Native JiuwenSwarm package location is unavailable")
        template = Path(package.origin).parent / "resources" / "config.yaml"
    if not template.is_file():
        raise FileNotFoundError("Native config template unavailable: " + str(template))
    return template


def configure(spec, root, model):
    import yaml
    from jiuwenswarm.common.utils import prepare_workspace, get_agent_workspace_dir, get_agent_skills_dir
    state = root / "state"
    prepare_workspace(overwrite=False, workspace_dir=state)
    template = config_template(spec)
    config = yaml.safe_load(template.read_text(encoding="utf-8"))
    # Report language only; native tools, rails and model are unchanged.
    config["preferred_language"] = "en"
    # Keep native ordinary tools/rails; only inference selection and background
    # lifecycle are changed. Neither variant receives CC code or a CC verifier.
    config["models"] = {"defaults": [{"model_id": "native-value", "is_default": True,
        "model_client_config": {"model_name": model, "client_provider": PROVIDER,
            # The native app's usability check drops auth_mode before checking
            # this custom provider. This non-secret scope marker satisfies that
            # check; the custom client never sends it to any network endpoint.
            "api_base": "native-value-local-bridge", "auth_mode": "none",
            "api_key": "native-value-scoped-callback", "supports_vision": False,
            "max_retries": 0, "timeout": 120}, "model_config_obj": {}}]}
    config.setdefault("react", {})["workspace_dir"] = str(get_agent_workspace_dir())
    config["react"]["max_iterations"] = spec["max_model_calls"]
    # This completion bridge is text-only. The explicit native switch also
    # suppresses its speculative image-support startup probe (which otherwise
    # starts a real completion and cancels it on the SDK's shorter deadline).
    config["react"]["enable_read_image_multimodal"] = False
    config["auto_recap"] = {"enabled": False}
    config["task_memory"] = {"enabled": False}
    # Background evolution/dreaming are outside the bounded foreground job.
    config.setdefault("rsi", {})["enabled"] = False
    config.setdefault("react", {}).setdefault("evolution", {})["skill_evolution"] = False
    (state / "config" / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    for skill in spec["skill_dirs"]:
        copy_tree(skill, get_agent_skills_dir() / Path(skill).name)
    write(root / "skill-inventory.json", {
        "semantics": "Both arms retain ordinary native bundled skills; native-skills adds selected task skills",
        "selected": [Path(p).name for p in spec["skill_dirs"]],
        "installed": [{"path": str(path.relative_to(root)),
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                      for path in sorted(get_agent_skills_dir().rglob("SKILL.md"))]})
    write(root / "effective-config.json", config)


async def execute_worker(spec, root):
    # These imports happen only after a fresh process has bound its environment.
    # Path resolution caches its first result. Ensure the isolated config root
    # exists before *any* JiuwenSwarm import can choose packaged defaults.
    (root / "state" / "config").mkdir(parents=True, exist_ok=True)
    from jiuwenswarm.research.native_logging import configure_native_logging
    configure_native_logging(root / "logs")
    from jiuwenswarm.research.trajectory import start_native_capture, stop_native_capture
    if "completion_directory" in spec:
        model = spec["model"]
        async def complete(prompt, timeout):
            return await file_completion(spec["completion_directory"], prompt, timeout, model=model,
                                         effort=spec["reasoning_effort"])
    else:
        from jiuwenswarm.research.local_models import LocalModelClient
        binding = json.loads(Path(spec["binding"]).read_text(encoding="utf-8"))
        if (binding.get("backend", {}).get("kind") != "host-codex-app-server"
                or binding.get("model", {}).get("reasoning_effort") != "medium"):
            raise ValueError("Requires existing host Codex subscription binding at medium effort")
        model = binding["model"]["model_name"]
        client = LocalModelClient(binding)
        async def complete(prompt, timeout):
            return await client.invoke(prompt, timeout_s=timeout, call_function="worker")
    scope = CompletionScope(complete, spec, root / "evidence")
    project = root / "project"
    project.mkdir()
    if spec.get("inputs_dir"):
        copy_tree(spec["inputs_dir"], project)
    configure(spec, root, model)
    from jiuwenswarm.server.runtime.agent_adapter.interface import JiuWenSwarm
    from jiuwenswarm.common.schema.agent import AgentRequest
    from jiuwenswarm.common.schema.message import ReqMethod
    app = None
    terminal = False
    errors = []
    session_id = "native-value-" + uuid.uuid4().hex
    with registered_bridge(scope):
        start_native_capture(root / "trajectory")
        try:
            app = JiuWenSwarm()
            # The full facade installs SkillManager and all normal app providers.
            await app.create_instance({"project_dir": str(project), "channel_id": "cli"}, mode="agent")
            request = AgentRequest(request_id=uuid.uuid4().hex, session_id=session_id,
                channel_id="cli", req_method=ReqMethod.CHAT_SEND, is_stream=True,
                params={"query": spec["task"], "mode": spec["mode"], "project_dir": str(project),
                        "skills": [Path(p).name for p in spec["skill_dirs"]]})
            with (root / "events.jsonl").open("x", encoding="utf-8") as events:
                async with asyncio.timeout(spec["wall_time_s"]):
                    async for chunk in app.process_message_stream(request):
                        value = plain(chunk)
                        events.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
                        events.flush()
                        payload = value.get("payload") or {}
                        if payload.get("event_type") == "chat.error":
                            errors.append(payload)
                        terminal |= payload.get("event_type") == "chat.final"
            if scope.failure:
                raise RuntimeError(scope.failure)
            status = "completed" if terminal and not errors and scope.calls else "incomplete"
            return {"status": status, "native_application": "JiuWenSwarm", "variant": spec["variant"],
                    "mode": spec["mode"], "model": model,
                    "reasoning_effort": spec.get("reasoning_effort", "medium"),
                    "model_calls": scope.calls, "selected_tool_calls": scope.selected_tools,
                    "terminal_observed": terminal, "errors": errors,
                    "skill_dirs": [Path(p).name for p in spec["skill_dirs"]]}
        finally:
            if app is not None:
                await asyncio.wait_for(app.cleanup(), 15)
            stop_native_capture()


def worker(spec_path, root):
    root = Path(root).resolve()
    spec = load_spec(spec_path)
    try:
        result = asyncio.run(execute_worker(spec, root))
    except BaseException as exc:
        result = {"status": "failed", "error_type": type(exc).__name__, "error": str(exc),
                  "native_application": "JiuWenSwarm", "variant": spec["variant"]}
    artifacts = []
    for path in sorted((root / "project").rglob("*")):
        if path.is_file() and not path.is_symlink():
            raw = path.read_bytes()
            artifacts.append({"path": str(path.relative_to(root)), "bytes": len(raw),
                              "sha256": hashlib.sha256(raw).hexdigest()})
    result["artifact_manifest"] = artifacts
    write(root / "result.json", result)
    return 0 if result["status"] == "completed" else 1


def run(spec_path, output):
    began = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    spec = load_spec(spec_path)
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / "evidence").mkdir()
    (root / "home").mkdir()
    write(root / "assignment.json", spec)
    command = [sys.executable, "-m", "benchmarks.harbor_suite.native_value", "_worker",
               "--spec", str(root / "assignment.json"), "--output", str(root)]
    write(root / "controller-start.json", {"schema": "native-value-controller-start:1",
        "started_at": started_at, "assigned_caps": {key: spec[key] for key in
            ("max_model_calls", "max_tool_calls", "wall_time_s")}})
    def finish(returncode, status):
        write(root / "controller-finished.json", {"schema": "native-value-controller-finished:1",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_s": time.monotonic() - began, "returncode": returncode, "status": status})
    with (root / "stdout.log").open("xb") as stdout, (root / "stderr.log").open("xb") as stderr:
        try:
            child = subprocess.Popen(command, env=child_environment(root), stdout=stdout, stderr=stderr,
                                     start_new_session=os.name == "posix")
        except OSError:
            finish(None, "launch_failed")
            raise
        try:
            code = child.wait(timeout=spec["wall_time_s"] + 45)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(child.pid, signal.SIGKILL)
            else:
                subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True)
            child.wait()
            write(root / "controller-timeout.json", {"status": "containment_required",
                  "reason": "worker deadline exceeded; reconcile model relay before next dispatch"})
            finish(child.returncode, "containment_required")
            return 2
    finish(code, "completed" if code == 0 else "failed")
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "run", "_worker"))
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    if args.action == "preflight":
        result = preflight(load_spec(args.spec))
        print(json.dumps(result))
        return 0 if result["ready"] else 1
    if not args.output:
        parser.error("--output is required")
    return worker(args.spec, args.output) if args.action == "_worker" else run(args.spec, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
