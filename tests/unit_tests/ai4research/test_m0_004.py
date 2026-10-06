"""Runner substitution, replay and post-persistence budget probes."""
import asyncio
import time

import pytest

from jiuwenswarm.ai4research.common import GovernanceError
from tests.fixtures.ai4research.trial_support import MODEL, OBJECTIVE, make_trial


@pytest.mark.asyncio
async def test_m0_004_b06_second_compiler_attempt_cannot_dispatch(tmp_path):
    trial = make_trial(tmp_path, wait_role="compiler")
    posted = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="once")
    await asyncio.wait_for(trial.bridge.entered.wait(), 2)
    run = trial.application.store.get_run(posted["run_id"], caller_id=trial.context.user_id)
    with pytest.raises(GovernanceError, match="replay or retry"):
        await trial.application.runner.invoke(run, "compiler", {}, pin=trial.application.pins["compiler"],
            model=MODEL, deadline=time.monotonic() + 1, caller_id=trial.context.user_id)
    assert len(trial.bridge.calls) == 1
    await trial.application.cancel(trial.context, run["run_id"])


@pytest.mark.asyncio
async def test_m0_004_b02_caller_cannot_select_model_or_insert_third_cc(tmp_path):
    trial = make_trial(tmp_path, wait_role="compiler")
    posted = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="roles")
    await asyncio.wait_for(trial.bridge.entered.wait(), 2)
    run = trial.application.store.get_run(posted["run_id"], caller_id=trial.context.user_id)
    for role, model in (("compiler", "foreign-model"), ("delivery", MODEL)):
        with pytest.raises(GovernanceError, match="frozen role|two authored"):
            await trial.application.runner.invoke(run, role, {}, pin=trial.application.pins["compiler"],
                model=model, deadline=time.monotonic() + 1, caller_id=trial.context.user_id)
    assert len(trial.bridge.calls) == 1
    await trial.application.cancel(trial.context, run["run_id"])


@pytest.mark.asyncio
async def test_m0_004_b04_persisting_context_cannot_expand_total_budget(tmp_path, monkeypatch):
    trial = make_trial(tmp_path)
    original_write = trial.application.store.put_artifact
    def slow_context(*args, **kwargs):
        if kwargs.get("artifact_type") == "invocation_context":
            time.sleep(0.15)
        return original_write(*args, **kwargs)
    monkeypatch.setattr(trial.application.store, "put_artifact", slow_context)
    run = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="deadline",
                                         options={"timeout_seconds": 0.1})
    result = await trial.finish(run["run_id"])
    assert result["status"] == "FAILED" and result["accepted_ref"] is None
    assert not trial.bridge.calls
    assert "deterministic_validation" in {check["check_id"] for check in result["not_run"]}
