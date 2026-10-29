"""Focused tests for the native bounded Builder agent adapter."""
import json
import asyncio

import pytest

pytest.importorskip("openjiuwen")
from jiuwenswarm.research.builder_agent_runtime import (  # noqa: E402
    MAX_MESSAGE_BYTES,
    TOOL_NAMES,
    _tool_arguments,
    run_builder_agent,
)


@pytest.mark.asyncio
@pytest.mark.parametrize('failure',[RuntimeError('executor unavailable'),asyncio.CancelledError()])
async def test_protected_tool_failure_stops_without_another_model_call(failure):
    calls=[]
    async def model_call(prompt,system):
        calls.append(prompt)
        return json.dumps({'action':'list_files','arguments':{}})
    async def dispatch(*args):raise failure
    with pytest.raises(type(failure)):
        await run_builder_agent(model_call=model_call,dispatch=dispatch,task={'objective':'stop on host failure'},
            session_id='native-tool-failure-'+type(failure).__name__,max_model_calls=2,timeout_s=10)
    assert len(calls)==1


def _history(prompt):
    return json.loads(prompt)


def _tool_result(prompt, predicate):
    for message in _history(prompt):
        if message.get("role") != "tool":
            continue
        content = message.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except ValueError:
                continue
        if isinstance(content, dict) and predicate(content):
            return True
    return False


def test_only_bounded_logical_actions_are_exposed():
    assert TOOL_NAMES == (
        "list_files", "search_files", "read_file", "write_file", "apply_patch",
        "run_checks", "read_log", "submit_candidate", "report_blocked",
    )
    for name in TOOL_NAMES:
        schema = _tool_arguments(name)
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False


def test_action_schema_keeps_host_owned_bounds():
    assert set(_tool_arguments("write_file")["properties"]) == {
        "path", "content", "expected_sha256"
    }
    assert set(_tool_arguments("write_file")["required"]) == {
        "path", "content", "expected_sha256"
    }
    assert set(_tool_arguments("apply_patch")["required"]) == {
        "path", "old", "new", "expected_sha256"
    }
    assert _tool_arguments("run_checks")["properties"]["check"]["enum"] == [
        "compile", "unit", "smoke"
    ]
    assert MAX_MESSAGE_BYTES == 2 * 1024 * 1024


def test_native_tool_schemas_are_available_to_the_provider_callback():
    system, _ = __import__("jiuwenswarm.research.builder_agent_runtime", fromlist=["_messages_to_prompt"])._messages_to_prompt(
        [{"role": "user", "content": "task"}],
        [{"name": "read_file", "input_params": _tool_arguments("read_file")}],
    )
    assert '"action"' in system
    assert '"read_file"' in system
    assert '"path"' in system


@pytest.mark.asyncio
async def test_invalid_envelope_consumes_one_model_call_and_fails_closed():
    calls = []
    dispatched = []

    async def model_call(prompt, system):
        calls.append((prompt, system))
        return '{"action":"run_shell","arguments":{}}'

    async def dispatch(name, args, ordinal):
        dispatched.append((name, args, ordinal))
        return {"blocked": True, "reason": args["reason"]}

    outcome = await run_builder_agent(
        model_call=model_call,
        dispatch=dispatch,
        task={"objective": "test"},
        session_id="test-invalid-envelope",
        max_model_calls=1,
        timeout_s=10,
    )
    assert len(calls) == 1
    assert dispatched == []
    assert outcome["blocked"] is True
    assert outcome["reason"] == "model_call_limit"


@pytest.mark.asyncio
async def test_invalid_envelope_diagnostic_allows_next_native_action():
    calls = []
    dispatched = []
    responses = [
        'not-json',
        json.dumps({"action": "read_file", "arguments": {"path": "main.py"}}),
        json.dumps({"action": "report_blocked", "arguments": {"reason": "read complete"}}),
    ]

    async def model_call(prompt, system):
        calls.append((prompt, system))
        return responses[len(calls) - 1]

    async def dispatch(name, args, ordinal):
        dispatched.append((name, args, ordinal))
        if name == "report_blocked":
            return {"blocked": True, "reason": args["reason"]}
        return {"path": args["path"], "content": "hello"}

    outcome = await run_builder_agent(
        model_call=model_call, dispatch=dispatch, task={"objective": "read"},
        session_id="test-invalid-then-action", max_model_calls=3, timeout_s=10,
    )
    assert len(calls) == 3
    assert "Invalid Builder action envelope" in calls[1][0]
    assert dispatched == [("read_file", {"path": "main.py"}, 2),
                          ("report_blocked", {"reason": "read complete"}, 3)]
    assert outcome == {"blocked": True, "reason": "read complete"}


@pytest.mark.parametrize("malformed", [
    '{"action":"list_files","action":"report_blocked","arguments":{"reason":"ambiguous"}}',
    '{"action":"report_blocked","arguments":{"reason":NaN}}',
])
@pytest.mark.asyncio
async def test_duplicate_keys_and_nonfinite_json_are_rejected(malformed):
    calls = []
    dispatched = []
    responses = [malformed, json.dumps({"action": "report_blocked", "arguments": {"reason": "confirmed"}})]

    async def model_call(prompt, system):
        calls.append(prompt)
        return responses[len(calls) - 1]

    async def dispatch(name, args, ordinal):
        dispatched.append((name, args, ordinal))
        return {"blocked": True, "reason": args["reason"]}

    outcome = await run_builder_agent(
        model_call=model_call, dispatch=dispatch, task={"objective": "strict JSON"},
        session_id="test-strict-json", max_model_calls=2, timeout_s=10,
    )
    assert len(calls) == 2
    assert dispatched == [("report_blocked", {"reason": "confirmed"}, 2)]
    assert outcome == {"blocked": True, "reason": "confirmed"}


@pytest.mark.asyncio
async def test_native_conversation_retains_action_and_tool_result_history():
    calls = []
    dispatched = []
    responses = [
        json.dumps({"action": "list_files", "arguments": {}}),
        json.dumps({"action": "report_blocked", "arguments": {"reason": "done"}}),
    ]

    async def model_call(prompt, system):
        calls.append(prompt)
        return responses[len(calls) - 1]

    async def dispatch(name, args, ordinal):
        dispatched.append((name, args, ordinal))
        return {"files": ["main.py"]}

    outcome = await run_builder_agent(
        model_call=model_call, dispatch=dispatch, task={"objective": "inspect"},
        session_id="test-native-history", max_model_calls=2, timeout_s=10,
    )
    assert len(calls) == 2
    history = _history(calls[1])
    tool_calls = [call for row in history for call in (row.get("tool_calls") or [])]
    list_call = next(call for call in tool_calls
                     if call.get("function", {}).get("name") == "list_files")
    assert any(row.get("role") == "tool" and row.get("tool_call_id") == list_call["id"] for row in history)
    assert _tool_result(calls[1], lambda result: result.get("files") == ["main.py"])
    assert dispatched == [("list_files", {}, 1), ("report_blocked", {"reason": "done"}, 2)]
    assert outcome == {"files": ["main.py"], "blocked": True}


@pytest.mark.asyncio
async def test_terminal_dispatch_returns_host_result_without_provider_retry():
    calls = []
    dispatched = []

    async def model_call(prompt, system):
        calls.append(prompt)
        return json.dumps({"action": "report_blocked", "arguments": {"reason": "fixture"}})

    async def dispatch(name, args, ordinal):
        dispatched.append((name, args, ordinal))
        return {"blocked": True, "reason": "fixture"}

    outcome = await run_builder_agent(
        model_call=model_call,
        dispatch=dispatch,
        task={"objective": "stop"},
        session_id="test-terminal",
        max_model_calls=3,
        timeout_s=10,
    )
    assert outcome == {"blocked": True, "reason": "fixture"}
    assert len(calls) == 1
    assert dispatched == [("report_blocked", {"reason": "fixture"}, 1)]


@pytest.mark.asyncio
async def test_native_repair_rechecks_current_snapshot_then_submits():
    import hashlib

    from jiuwenswarm.research.builder_agent_service import BuilderAgentService

    initial = {
        "requirements.txt": "# stdlib\n",
        "poc_patch.py": "def predict(train, test):\n    return []\n",
        "run_benchmark.py": "print('candidate')\n",
    }
    fixed = "def predict(train, test):\n    return [row['label'] for row in train[:len(test)]]\n"
    tests = "import unittest\nclass PredictionTests(unittest.TestCase):\n def test_labels(self): self.assertEqual(predict([{'label':'a'}], [{}]), ['a'])\n"
    check_calls = []

    async def execute_check(check, files, test_name):
        check_calls.append((check, files["poc_patch.py"], test_name))
        passed = files["poc_patch.py"] == fixed
        return {"passed": passed, "detail": "candidate behavior matched" if passed else "predict returned no labels"}

    service = BuilderAgentService(initial_files=initial, execute_check=execute_check,
                                  session_id="native-repair-test")
    file_hash = lambda name: hashlib.sha256(initial[name].encode()).hexdigest()
    test_hash = hashlib.sha256(b"").hexdigest()
    actions = [
        {"action": "write_file", "arguments": {"path": "tests.py", "content": tests, "expected_sha256": test_hash}},
        {"action": "run_checks", "arguments": {"check": "compile"}},
        {"action": "run_checks", "arguments": {"check": "unit", "test_name": "PredictionTests"}},
        {"action": "apply_patch", "arguments": {"path": "poc_patch.py", "old": "return []", "new": "return [row['label'] for row in train[:len(test)]]", "expected_sha256": file_hash("poc_patch.py")}},
        {"action": "run_checks", "arguments": {"check": "compile"}},
        {"action": "run_checks", "arguments": {"check": "unit", "test_name": "PredictionTests"}},
        {"action": "run_checks", "arguments": {"check": "smoke"}},
        {"action": "submit_candidate", "arguments": {}},
    ]
    prompts = []

    async def model_call(prompt, system):
        prompts.append((prompt, system))
        if len(prompts) == 4:
            assert _tool_result(prompt, lambda result: result.get("report", {}).get("passed") is False)
            assert _tool_result(prompt, lambda result: "predict returned no labels" in
                                result.get("report", {}).get("executor_result", {}).get("detail", ""))
        return json.dumps(actions[len(prompts) - 1])

    async def dispatch(name, args, ordinal):
        return await service.dispatch(name, args, ordinal)

    outcome = await run_builder_agent(
        model_call=model_call, dispatch=dispatch, task={"objective": "repair and test"},
        session_id=service.session_id, max_model_calls=12, timeout_s=20,
    )
    assert outcome["submitted"] is True
    assert len(prompts) == len(actions)
    assert outcome["snapshot_sha256"] == service.snapshot_sha256
    assert outcome["checks"]["compile"]["passed"] is True
    assert outcome["checks"]["unit"]["passed"] is True
    assert outcome["checks"]["smoke"]["passed"] is True
    assert [call[0] for call in check_calls] == ["unit", "unit", "smoke"]
    assert service.inspect()["jobs"] == 3
    assert set(outcome["files"]) == {"requirements.txt", "poc_patch.py", "run_benchmark.py"}
    assert len(outcome["journal"]) == len(actions)
