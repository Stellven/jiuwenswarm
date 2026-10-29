import pytest
import asyncio


@pytest.mark.asyncio
async def test_native_diagnostic_uses_authorized_callback_and_records_nonaccepting_trace():
    from jiuwenswarm.research_sidecar.native_diagnostic import run_native_diagnostic

    emissions = iter([
        '{"action":"read_record","arguments":{"record_id":"case-1"}}',
        '{"action":"unsupported","arguments":{"reason":"Insufficient evidence"}}',
    ])
    callback_calls = []
    dispatch_calls = []

    async def model_call(prompt, system):
        callback_calls.append((prompt, system))
        return {"text": next(emissions), "identity": {"effective": "pilot-model"}}

    async def dispatch(name, arguments, ordinal):
        dispatch_calls.append((name, arguments, ordinal))
        return {"case": arguments["record_id"], "label": "candidate"}

    result = await run_native_diagnostic(
        case_id="case-1",
        task={"input": "captured input"},
        model="gpt-6-luna",
        tool_specs=[{
            "name": "read_record",
            "description": "Read one bounded captured record.",
            "input_params": {
                "type": "object",
                "properties": {"record_id": {"type": "string", "enum": ["case-1"]}},
                "required": ["record_id"],
                "additionalProperties": False,
            },
        }],
        model_call=model_call,
        dispatch=dispatch,
        max_model_calls=4,
        max_tool_calls=3,
        timeout_s=20,
    )

    assert len(callback_calls) == 2
    assert len(dispatch_calls) == 1
    assert result["diagnostic_only"] is True
    assert result["product_accepted"] is False
    assert result["comparison_claim"] == "none; not raw upstream JiuwenSwarm"
    assert result["case_id"] == "case-1"
    assert len(result["task_sha256"]) == 64
    assert len(result["tool_spec_sha256"]) == 64
    assert result["model_calls"] == 2
    assert result["tool_calls"] == 1
    assert result["abstention"] == "Insufficient evidence"
    assert [row["raw_emission"] for row in result["model_trace"]] == [
        '{"action":"read_record","arguments":{"record_id":"case-1"}}',
        '{"action":"unsupported","arguments":{"reason":"Insufficient evidence"}}',
    ]
    assert result["tool_trace"][0]["tool"] == "read_record"


@pytest.mark.asyncio
async def test_native_diagnostic_rejects_tool_outside_explicit_allowlist_without_retry():
    from jiuwenswarm.research_sidecar.native_diagnostic import run_native_diagnostic

    calls = []

    async def model_call(prompt, system):
        calls.append(1)
        return '{"action":"shell","arguments":{}}'

    async def dispatch(name, arguments, ordinal):
        raise AssertionError("disallowed tool must not dispatch")

    with pytest.raises(ValueError, match="outside the explicit allowlist"):
        await run_native_diagnostic(
            case_id="case-2", task={"input": "captured"}, model="gpt-6-luna",
            tool_specs=[{"name": "read_record", "description": "read",
                          "input_params": {"type": "object", "properties": {},
                                            "additionalProperties": False}}],
            model_call=model_call, dispatch=dispatch, max_model_calls=4,
            max_tool_calls=3, timeout_s=20)
    assert len(calls) == 1


def test_native_diagnostic_rejects_duplicate_tool_declarations():
    from jiuwenswarm.research_sidecar.native_diagnostic import run_native_diagnostic

    async def unused(*args):
        raise AssertionError("callbacks must not run")

    tools = [{"name": "read_record", "description": "read",
              "input_params": {"type": "object", "properties": {}}}] * 2

    async def invoke():
        await run_native_diagnostic(case_id="case-3", task={}, tool_specs=tools,
            model="gpt-6-luna", model_call=unused, dispatch=unused)

    with pytest.raises(ValueError, match="unique named objects"):
        import asyncio
        asyncio.run(invoke())


@pytest.mark.asyncio
async def test_native_sdk_model_failure_does_not_trigger_hidden_retry():
    from jiuwenswarm.research_sidecar import native_diagnostic as diagnostic

    calls = []

    async def model_call(prompt, system):
        calls.append(1)
        raise RuntimeError("controlled provider failure")

    async def dispatch(name, arguments, ordinal):
        raise AssertionError("tool must not run after model failure")

    with pytest.raises(RuntimeError, match="controlled provider failure"):
        await diagnostic.run_native_diagnostic(
            case_id="failure-case", task={"input": "captured"}, model="gpt-6-luna",
            tool_specs=[{"name": "read_record", "description": "read",
                          "input_params": {"type": "object", "properties": {},
                                            "additionalProperties": False}}],
            model_call=model_call, dispatch=dispatch, max_model_calls=4,
            max_tool_calls=3, timeout_s=20)
    assert calls == [1]
    assert diagnostic._CALLBACKS == {}


@pytest.mark.asyncio
async def test_native_sdk_cancellation_stops_without_hidden_retry():
    from jiuwenswarm.research_sidecar import native_diagnostic as diagnostic

    calls = []
    started = asyncio.Event()

    async def model_call(prompt, system):
        calls.append(1)
        started.set()
        await asyncio.Future()

    async def dispatch(name, arguments, ordinal):
        raise AssertionError("tool must not run after cancellation")

    task = asyncio.create_task(diagnostic.run_native_diagnostic(
        case_id="cancel-case", task={"input": "captured"}, model="gpt-6-luna",
        tool_specs=[{"name": "read_record", "description": "read",
                      "input_params": {"type": "object", "properties": {},
                                        "additionalProperties": False}}],
        model_call=model_call, dispatch=dispatch, max_model_calls=4,
        max_tool_calls=3, timeout_s=20))
    await asyncio.wait_for(started.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == [1]
    assert diagnostic._CALLBACKS == {}
