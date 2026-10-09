"""Protected, owned Codex process adapter implementing M0-IF-003@r1.

No app code is imported. The capability receives only bounded stdin data and
has no tools; process limits and cancellation are owned by this bridge.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def unavailable_usage(reason="Provider exposes no attributable billing telemetry"):
    return {"input_tokens": None, "output_tokens": None, "cost_amount": None,
            "currency": None, "unavailable_reasons": [reason]}


@dataclass
class ModelResult:
    text: str | None
    raw_stdout: str = ""
    raw_stderr: str = ""
    error: str | None = None
    outcome: str = "completed"
    duration_s: float = 0.0
    model_calls: int = 1
    started_at: str = field(default_factory=utc_now)
    ended_at: str = field(default_factory=utc_now)
    identity: dict = field(default_factory=lambda: {
        "requested": "approved native Codex default", "effective": None,
        "basis": "native configuration; served identity unavailable"})
    usage: dict = field(default_factory=unavailable_usage)
    effects: list[str] = field(default_factory=lambda: ["approved_model_disclosure"])
    settings: dict = field(default_factory=dict)
    raw_stdout_bytes: bytes | None = None
    raw_stderr_bytes: bytes | None = None


class ProcessLimits:
    """Hard memory/process-lifetime limit, established before child resumes."""

    def __init__(self, memory_mb: int = 1024):
        self.memory_mb = memory_mb
        self.handle = None

    @staticmethod
    def available() -> bool:
        return os.name == "nt" or os.name == "posix"

    def probe(self) -> bool:
        process = None
        try:
            process = subprocess.Popen([getattr(sys, "_base_executable", sys.executable), "-c", "print('owned-limit-ready')"], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, **self.popen_options())
            self.attach(process)
            stdout, _ = process.communicate(timeout=5)
            return process.returncode == 0 and b"owned-limit-ready" in stdout
        except (OSError, subprocess.TimeoutExpired):
            return False
        finally:
            if process is not None:
                terminate_owned(process)
            self.close()

    def popen_options(self):
        if os.name == "nt":
            return {"creationflags": subprocess.CREATE_NO_WINDOW | 0x00000004}
        import resource
        cap = self.memory_mb * 1024 * 1024

        def restricted():
            resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
        return {"preexec_fn": restricted, "start_new_session": True}

    def attach(self, process):
        if os.name != "nt":
            return
        from ctypes import wintypes

        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IOC(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class EXTENDED(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IOC),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                  ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateJobObjectW(None, None)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObject failed")
        self.handle = handle
        limits = EXTENDED()
        # Kill on close, aggregate memory, process memory, exactly one process.
        limits.BasicLimitInformation.LimitFlags = 0x2000 | 0x100 | 0x200 | 0x8
        limits.BasicLimitInformation.ActiveProcessLimit = 1
        limits.ProcessMemoryLimit = self.memory_mb * 1024 * 1024
        limits.JobMemoryLimit = limits.ProcessMemoryLimit
        if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
        if not kernel.AssignProcessToJobObject(handle, wintypes.HANDLE(int(process._handle))):
            raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")
        native = ctypes.WinDLL("ntdll")
        native.NtResumeProcess.argtypes = [wintypes.HANDLE]
        if native.NtResumeProcess(wintypes.HANDLE(int(process._handle))) != 0:
            raise OSError("Unable to resume protected child")

    def close(self):
        if self.handle is not None:
            ctypes.WinDLL("kernel32").CloseHandle(ctypes.c_void_p(self.handle))
            self.handle = None


def terminate_owned(process):
    if process.poll() is None:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()


def parse_events(stdout: str):
    events, messages, usage = [], [], unavailable_usage()
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError as exc:
            raise ValueError("Malformed native JSONL event") from exc
        events.append(event)
        item = event.get("item", {})
        if item.get("type") == "agent_message":
            messages.append(item.get("text", ""))
        if item.get("type") and item.get("type") not in {"agent_message", "reasoning", "todo_list"}:
            raise ValueError("Denied native tool event: " + item["type"])
        if event.get("type") == "turn.completed":
            native = event.get("usage") or {}
            usage["input_tokens"] = native.get("input_tokens")
            usage["output_tokens"] = native.get("output_tokens")
            usage["unavailable_reasons"] = ["Attributable cost/currency not supplied by native CLI"]
        if event.get("type") in {"error", "turn.failed"}:
            raise ValueError("Native invocation failure: " + str(event.get("message", event.get("error", "unknown"))))
    return (messages[-1] if messages else None), events, usage


class CodexBridge:
    synthetic = False

    def __init__(self, config):
        self.config = config
        self.executable = shutil.which(str(config.codex_path or "codex"))

    def readiness(self):
        result = []
        ok, reason = False, "Approved native Codex executable unavailable"
        if self.executable:
            try:
                probe = subprocess.run([self.executable, "login", "status"], capture_output=True,
                                       text=True, encoding="utf-8", errors="replace", timeout=8)
                ok = probe.returncode == 0
                reason = "Native authenticated access probe passed" if ok else "Native authentication unavailable"
            except (OSError, subprocess.TimeoutExpired):
                reason = "Native access probe failed or timed out"
        result.append({"name": "model", "status": "ready" if ok else "unavailable", "reason": reason})
        enforcement = ProcessLimits.available() and ProcessLimits(getattr(self.config, "memory_mb", 1024)).probe()
        result.append({"name": "required_enforcement", "status": "ready" if enforcement else "unavailable",
                       "reason": "Owned process hard memory/lifetime probe passed; adapter tools are disabled" if enforcement
                       else "Mandatory owned-process enforcement unavailable"})
        return result

    def invoke(self, *, role, prompt, schema, timeout_s, cancelled: Callable[[], bool], invocation_id):
        start, began = utc_now(), time.monotonic()
        identity = {"requested": self.config.model_name or "approved native Codex default",
                    "effective": None, "basis": "operator-selected CLI identity; provider-served identity not independently exposed"}
        if not self.executable:
            return ModelResult(None, error="Configured native executable unavailable", outcome="environment_blocked",
                               model_calls=0, started_at=start, identity=identity)
        limits = ProcessLimits(getattr(self.config, "memory_mb", 1024))
        process = None
        with tempfile.TemporaryDirectory(prefix="intent-owned-") as own:
            cwd = Path(own)
            schema_path = cwd / "output.schema.json"
            schema_path.write_text(json.dumps(schema), encoding="utf-8")
            args = [self.executable, "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
                    "--skip-git-repo-check", "--json", "--color", "never", "-s", "read-only",
                    "--output-schema", str(schema_path), "-C", str(cwd)]
            for feature in ("shell_tool", "apply_patch_freeform", "apps", "plugins", "hooks", "multi_agent", "skill_search",
                            "image_generation", "view_image", "in_app_browser", "js_repl", "exec_permission_approvals",
                            "request_permissions_tool", "workspace_dependencies", "computer_use", "browser_use", "browser_use_external",
                            "sleep_tool", "unbounded_connection_retries"):
                args += ["--disable", feature]
            args += ["--enable", "skip_host_skill_discovery"]
            args += ["-c", 'web_search="disabled"', "-c", 'model_reasoning_effort="low"',
                     "-c", 'approval_policy="never"', "-c", "mcp_servers={}",
                     "-c", "suppress_unstable_features_warning=true",
                     "-c", 'model_provider="intent_openai"', "-c", 'model_providers.intent_openai.name="OpenAI protected compiler transport"',
                     "-c", "model_providers.intent_openai.requires_openai_auth=true",
                     "-c", "model_providers.intent_openai.request_max_retries=0",
                     "-c", "model_providers.intent_openai.stream_max_retries=0", "-"]
            if self.config.model_name:
                args[-1:-1] = ["-m", self.config.model_name]
            settings = {"adapter": "codex-exec-stdin-v1", "tools": [], "web_search": "disabled",
                        "automatic_retries": 0, "role": role, "memory_mb": limits.memory_mb,
                        "transport_request_max_retries": 0, "transport_stream_max_retries": 0,
                        "backend_model_request_count": None,
                        "backend_count_limitation": "Native invocation is observed; provider-internal requests are not exposed",
                        "transport_schema_sha256": __import__("hashlib").sha256(schema_path.read_bytes()).hexdigest(),
                        "transport_schema_limitations": "Optional ext omitted; unsupported conditional rules enforced by authoritative host checks",
                        "memory_enforcement": "Windows Job Object before resume" if os.name == "nt" else "RLIMIT_AS before exec",
                        "native_user_config": "ignored; existing authentication only", "invocation_id": invocation_id}
            try:
                process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           **limits.popen_options())
                limits.attach(process)
                buffers = {"stdout": bytearray(), "stderr": bytearray()}
                seen, overflow = {"stdout": 0, "stderr": 0}, threading.Event()
                guard = threading.Lock()

                def writer():
                    try:
                        process.stdin.write(prompt.encode("utf-8"))
                        process.stdin.close()
                    except (BrokenPipeError, OSError):
                        pass

                def reader(stream, name):
                    while True:
                        chunk = stream.read(4096)
                        if not chunk:
                            break
                        with guard:
                            seen[name] += len(chunk)
                            remaining = self.config.max_output_bytes - sum(len(x) for x in buffers.values())
                            buffers[name].extend(chunk[:max(0, remaining)])
                            if len(chunk) > remaining:
                                overflow.set()
                                break
                    stream.close()

                threads = [threading.Thread(target=writer, daemon=True),
                           threading.Thread(target=reader, args=(process.stdout, "stdout"), daemon=True),
                           threading.Thread(target=reader, args=(process.stderr, "stderr"), daemon=True)]
                for thread in threads:
                    thread.start()
                outcome, error = "completed", None
                while process.poll() is None or any(t.is_alive() for t in threads):
                    if overflow.is_set():
                        outcome, error = "output_limit", "Hard stdout/stderr capture bound exceeded; truncated evidence explicit"
                        terminate_owned(process)
                        break
                    if cancelled():
                        outcome, error = "cancelled", "Explicit cancellation contained owned invocation"
                        terminate_owned(process)
                        break
                    if time.monotonic() - began >= timeout_s:
                        outcome, error = "timeout", "Frozen invocation time limit exceeded"
                        terminate_owned(process)
                        break
                    time.sleep(0.025)
                for thread in threads:
                    thread.join(5)
                stdout_bytes, stderr_bytes = bytes(buffers["stdout"]), bytes(buffers["stderr"])
                stdout, stderr = stdout_bytes.decode("utf-8", errors="replace"), stderr_bytes.decode("utf-8", errors="replace")
                settings.update(raw_capture_bytes={name: len(value) for name, value in buffers.items()},
                                raw_observed_bytes_at_least=seen, raw_evidence_truncated=overflow.is_set())
                text = None
                usage = unavailable_usage()
                if outcome == "completed":
                    if process.returncode != 0:
                        outcome, error = "failed", "Native process returned non-success"
                    elif len(stdout.encode("utf-8")) > self.config.max_output_bytes:
                        outcome, error = "failed", "Captured response exceeds frozen output bound"
                    else:
                        try:
                            text, _events, usage = parse_events(stdout)
                            settings["native_usage"] = next((event.get("usage") for event in reversed(_events) if event.get("type") == "turn.completed"), None)
                            if text is None:
                                outcome, error = "no_output", "Native invocation produced no artifact"
                        except ValueError as exc:
                            outcome, error = "failed", str(exc)
                return ModelResult(text, stdout, stderr, error, outcome, time.monotonic() - began, 1,
                                   start, utc_now(), identity, usage, ["approved_model_disclosure"], settings, stdout_bytes, stderr_bytes)
            except Exception as exc:
                if process is not None:
                    terminate_owned(process)
                return ModelResult(None, error=type(exc).__name__ + ": " + str(exc), outcome="environment_blocked",
                                   duration_s=time.monotonic()-began, model_calls=0 if process is None else 1,
                                   started_at=start, ended_at=utc_now(), identity=identity, settings=settings)
            finally:
                limits.close()


class FixtureBridge:
    """Explicit test injection; normal product clients cannot supply responses."""
    synthetic = True

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def readiness(self):
        return [{"name": "model", "status": "ready", "reason": "Labelled smoke fixture; invalid for product acceptance"},
                {"name": "required_enforcement", "status": "ready", "reason": "In-process fixture has no model/tool authority"}]

    def invoke(self, **kwargs):
        self.calls.append(kwargs["role"])
        item = self.responses.pop(0) if self.responses else None
        if callable(item):
            item = item(kwargs)
        if isinstance(item, ModelResult):
            return item
        text = json.dumps(item) if isinstance(item, dict) else item
        return ModelResult(text, raw_stdout=text or "", outcome="completed" if text is not None else "no_output",
                           error=None if text is not None else "Fixture produced no artifact",
                           identity={"requested": "labelled fixture", "effective": "labelled fixture", "basis": "test injection"},
                           usage=unavailable_usage("Synthetic fixture; tokens/cost are not model measurements"), effects=[],
                           settings={"adapter": "fixture", "invalid_for_product": True})
