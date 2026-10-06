"""Contract separation, standing recheck and client authority probes."""
import asyncio

import pytest

from jiuwenswarm.ai4research.common import GovernanceError
from tests.fixtures.ai4research.trial_support import OBJECTIVE, make_trial


@pytest.mark.asyncio
async def test_m0_006_b02_client_cannot_replace_contract_or_profile(tmp_path):
    trial = make_trial(tmp_path)
    for option in ({"contract": {"verdict": "PASS"}}, {"model_roles": {"verifier": "producer"}},
                   {"profile_id": "producer-authored"}):
        with pytest.raises(GovernanceError):
            await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="bad", options=option)
    assert not trial.bridge.calls
    assert trial.application.store.list_runs(caller_id=trial.context.user_id) == []


@pytest.mark.asyncio
async def test_m0_006_b03_b04_suspension_after_assessment_blocks_release(tmp_path):
    trial = make_trial(tmp_path, wait_role="verifier")
    run = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="suspend")
    await asyncio.wait_for(trial.bridge.entered.wait(), 3)
    pin = trial.application.pins["compiler"]
    trial.application.library.suspend("intent_compiler", pin.decl_hash,
        human_authorized=True, actor_id=trial.context.user_id, required_scope="fixture-only")
    trial.bridge.release.set()
    result = await trial.finish(run["run_id"])
    assert result["status"] == "ENVIRONMENT_BLOCKED" and result["accepted_ref"] is None
    assert len(trial.bridge.calls) == 2


@pytest.mark.asyncio
async def test_m0_006_b02_one_active_trial_reconciles_but_denies_second_request(tmp_path):
    trial = make_trial(tmp_path, wait_role="compiler")
    first = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="first")
    await asyncio.wait_for(trial.bridge.entered.wait(), 3)
    repeated = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="first")
    assert repeated["run_id"] == first["run_id"]
    with pytest.raises(GovernanceError, match="already active") as failure:
        await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="second")
    assert failure.value.code == "model_busy"
    assert len(trial.bridge.calls) == 1
    assert len(trial.application.store.list_runs(caller_id=trial.context.user_id)) == 1
    trial.bridge.release.set()
    assert (await trial.finish(first["run_id"]))["status"] == "ACCEPTED"
    next_run = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="second")
    assert next_run["run_id"] != first["run_id"]
    assert (await trial.finish(next_run["run_id"]))["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_m0_006_b03_ready_route_never_silently_uses_mock_for_real(tmp_path):
    trial = make_trial(tmp_path)
    trial.application.baseline["provider"] = "codex_subscription"
    assert (await trial.application.readiness())["ready"] is False
    run = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="route")
    result = await trial.finish(run["run_id"])
    assert result["status"] == "ENVIRONMENT_BLOCKED" and not trial.bridge.calls


@pytest.mark.asyncio
async def test_m0_006_b04_account_generation_change_after_verifier_blocks_release(tmp_path, monkeypatch):
    trial = make_trial(tmp_path)
    frozen = {"account_fingerprint": "a" * 64, "account_epoch": "initial-generation", "runtime_version": "0.144.4"}
    trial.application.baseline["runtime_identity"] = frozen
    readiness = trial.bridge.readiness
    async def changing_readiness():
        current = await readiness()
        return {**current, **frozen, "account_epoch": "changed-generation" if len(trial.bridge.calls) == 2 else frozen["account_epoch"]}
    monkeypatch.setattr(trial.bridge, "readiness", changing_readiness)
    run = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="generation")
    result = await trial.finish(run["run_id"])
    assert result["status"] == "FAILED" and result["accepted_ref"] is None
    assert result["decision"]["reasons"] == ["account_changed"]
    assert len(trial.bridge.calls) == 2
