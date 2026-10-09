"""Protected adapter parsing and actual owned-process controls (no live model)."""
import json
import os
import subprocess
import sys

import pytest

from intent_compiler.config import Config
from intent_compiler.model import CodexBridge, ProcessLimits, parse_events, terminate_owned


def events(*values):
    return "\n".join(json.dumps(v) for v in values)


def test_actual_native_event_telemetry_unknown_billing_preserved():
    text, records, usage = parse_events(events(
        {"type": "thread.started", "thread_id": "one"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": '{"answer":1}'}},
        {"type": "turn.completed", "usage": {"input_tokens": 15, "output_tokens": 5}}))
    assert text == '{"answer":1}' and len(records) == 3
    assert usage["input_tokens"] == 15 and usage["output_tokens"] == 5
    assert usage["cost_amount"] is None and usage["currency"] is None


@pytest.mark.parametrize("tool", ["command_execution", "mcp_tool_call", "web_search", "file_change", "unknown_future_tool"])
def test_denies_any_noncontent_native_tool_event(tool):
    with pytest.raises(ValueError, match="Denied"):
        parse_events(events({"type": "item.started", "item": {"type": tool}}))


def test_no_artifact_and_bad_events_are_not_passes():
    assert parse_events(events({"type": "turn.completed"}))[0] is None
    with pytest.raises(ValueError, match="Malformed"):
        parse_events("not JSONL")
    with pytest.raises(ValueError, match="failure"):
        parse_events(events({"type": "turn.failed", "error": "provider missing"}))


def test_native_executable_missing_explicit_no_dispatch(tmp_path):
    config = Config(tmp_path / "state", tmp_path / "input", codex_path="missing-model-executable-xyz")
    bridge = CodexBridge(config)
    assert bridge.readiness()[0]["status"] == "unavailable"
    result = bridge.invoke(role="intention", prompt="test", schema={"type": "object"}, timeout_s=1,
                           cancelled=lambda: False, invocation_id="one")
    assert result.text is None and result.model_calls == 0 and result.outcome == "environment_blocked"


def test_actual_owned_process_memory_failure_is_enforced_before_resume():
    limits = ProcessLimits(128)
    process = subprocess.Popen([getattr(sys, "_base_executable", sys.executable), "-c", "a=bytearray(256*1024*1024);print('UNEXPECTED')"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **limits.popen_options())
    try:
        limits.attach(process)
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode != 0 and "UNEXPECTED" not in stdout and "MemoryError" in stderr
    finally:
        terminate_owned(process)
        limits.close()


def test_owned_process_explicit_termination_is_finite():
    limits = ProcessLimits(128)
    process = subprocess.Popen([getattr(sys, "_base_executable", sys.executable), "-c", "import time;time.sleep(60)"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, **limits.popen_options())
    try:
        limits.attach(process)
        terminate_owned(process)
        process.communicate(timeout=5)
        assert process.returncode != 0
    finally:
        limits.close()


def test_actual_bridge_streaming_capture_overrun_terminates_with_bounded_raw_evidence(tmp_path, monkeypatch):
    from intent_compiler import model
    config = Config(tmp_path / "state", tmp_path / "input", max_output_bytes=4096)
    bridge = CodexBridge(config)
    bridge.executable = getattr(sys, "_base_executable", sys.executable)
    native_popen = subprocess.Popen
    captured = []
    def emitter(args, **options):
        captured.extend(args)
        return native_popen([getattr(sys, "_base_executable", sys.executable), "-c",
                             "import sys,time;sys.stdout.buffer.write(b'x'*1000000);sys.stdout.flush();time.sleep(30)"], **options)
    monkeypatch.setattr(model.subprocess, "Popen", emitter)
    result = bridge.invoke(role="intention", prompt="bounded protected fixture", schema={"type": "object"},
                           timeout_s=5, cancelled=lambda: False, invocation_id="capture-test")
    assert result.outcome == "output_limit" and result.text is None and result.duration_s < 5
    assert len(result.raw_stdout_bytes) + len(result.raw_stderr_bytes) <= config.max_output_bytes
    assert result.settings["raw_evidence_truncated"] is True
    assert "model_providers.intent_openai.request_max_retries=0" in captured
    assert "model_providers.intent_openai.stream_max_retries=0" in captured
