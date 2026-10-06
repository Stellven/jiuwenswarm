"""Connected trial fixture boundaries; mocked findings are not live acceptance."""
from __future__ import annotations

import asyncio
import io
import json
from dataclasses import replace
import zipfile

import pytest

from jiuwenswarm.ai4research.common import GovernanceError, hash_json, sha256_bytes
from jiuwenswarm.ai4research.evidence import EvidenceViews
from jiuwenswarm.ai4research.state import RunStore
from tests.fixtures.ai4research.trial_support import CASE_TEXT, EXPECTED_REFUSAL, OBJECTIVE, make_trial


@pytest.mark.asyncio
async def test_connected_acceptance_is_exact_durable_and_explicit_mock(tmp_path):
    trial = make_trial(tmp_path)
    submitted = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="accepted")
    projected = await trial.finish(submitted["run_id"])
    assert projected["status"] == "ACCEPTED" and projected["mock"] is True
    assert projected["decision"]["verdict"] == "PASS" and len(projected["decision"]["checks"]) == 8
    assert "full stages/M1 incomplete" in projected["scope"]
    run = trial.application.store.get_run(submitted["run_id"], caller_id=trial.context.user_id)
    candidate = trial.application.store.get_artifact(projected["accepted_ref"], caller_id=trial.context.user_id)
    assert json.loads(candidate) == projected["accepted_intent"]
    assert sha256_bytes(candidate) == projected["accepted_ref"]["sha256"]
    assert [call["role"] for call in trial.bridge.calls] == ["compiler", "verifier"]
    assert all(attempt["outcome"] == "SUCCEEDED" for attempt in run["attempts"])
    assert all(attempt["evidence"]["usage"]["tokens"] is None for attempt in run["attempts"])
    for attempt, call in zip(run["attempts"], trial.bridge.calls, strict=True):
        evidence = attempt["evidence"]
        prompt = json.loads(trial.application.store.get_artifact(evidence["prompt_ref"], caller_id=trial.context.user_id))
        observation = json.loads(trial.application.store.get_artifact(evidence["observation_ref"], caller_id=trial.context.user_id))
        assert prompt["input_data"] == call["input"] and prompt["identities"] == call["identities"]
        assert sha256_bytes(prompt["developer_instructions"].encode("utf-8")) == run["pins"][attempt["role"]]["declaration"]["identity"]["carrier"]["sha256"]
        assert observation["runtime_version"] == "ScriptedBridge fixture-v1" and observation["model_calls"] == 1
        assert observation["effects"] == [] and observation["text"]
    assert len({call["identities"]["invocation_id"] for call in trial.bridge.calls}) == 2
    assert [event["event_type"] for event in run["events"]].index("deterministic_pass") < [event["event_type"] for event in run["events"]].index("decision")
    reopened = RunStore(trial.application.store.db_path, trial.application.store.artifacts_dir, gate_authority=trial.authority)
    assert reopened.recover_interrupted() == []
    assert reopened.get_run(run["run_id"], caller_id=trial.context.user_id)["accepted_ref"] == projected["accepted_ref"]


@pytest.mark.asyncio
@pytest.mark.parametrize("variant", list(EXPECTED_REFUSAL))
async def test_scripted_fidelity_challenge_refusal_preserves_candidate(tmp_path, variant):
    trial = make_trial(tmp_path, variant=variant)
    submitted = await trial.application.submit(trial.context, original_text=CASE_TEXT[variant], client_request_id=variant)
    result = await trial.finish(submitted["run_id"])
    assert result["status"] == "FAILED" and result["accepted_ref"] is None
    assert result["decision"]["verdict"] == "FAIL"
    finding = next(check for check in result["decision"]["checks"] if check["check_id"] == EXPECTED_REFUSAL[variant])
    assert finding["status"] == "FAIL" and "Predetermined" in finding["reason"]
    assert [call["role"] for call in trial.bridge.calls] == ["compiler", "verifier"]
    bundle = EvidenceViews(trial.application.store).bundle(result["run_id"], caller_id=trial.context.user_id)
    assert {member["reference"]["type"] for member in bundle["manifest"]["members"]} >= {"original_request", "intent_candidate", "raw_assessment", "deterministic_checks"}
    assert result["attention"] and result["attention"][0]["override_allowed"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["malformed", "extra", "stale", "swapped", "effects"])
async def test_deterministic_refusal_does_not_dispatch_verifier(tmp_path, fault):
    trial = make_trial(tmp_path, compiler_fault=fault)
    submitted = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id=fault)
    result = await trial.finish(submitted["run_id"])
    assert result["status"] == "FAILED" and result["accepted_ref"] is None
    assert [call["role"] for call in trial.bridge.calls] == ["compiler"]
    run = trial.application.store.get_run(result["run_id"], caller_id=trial.context.user_id)
    assert len(run["attempts"]) == 1 and not any(event["event_type"] == "deterministic_pass" for event in run["events"])
    assert {check["check_id"] for check in result["not_run"]} >= {"verifier_dispatch", *(f"semantic:F{i}" for i in range(1, 7))}
    assert all(check["status"] == "NOT_RUN" and check["reason"] for check in result["not_run"])
    if fault == "effects":
        evidence = run["attempts"][0]["evidence"]
        assert evidence["effects"] == ["prohibited mock shell"] and evidence["model_calls"] == 1
        assert evidence["delivery"] == "observed" and evidence["observed_model"] == trial.bridge.calls[0]["model"]
        observed = json.loads(trial.application.store.get_artifact(evidence["observation_ref"], caller_id=trial.context.user_id))
        assert observed["effects"] == evidence["effects"] and observed["runtime_version"] == "ScriptedBridge fixture-v1"
        assert observed["text"] and evidence["prompt_ref"] is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,expected", [("malformed", "INCONCLUSIVE"), ("missing_finding", "INCONCLUSIVE"),
                                           ("stale", "FAILED"), ("swapped", "FAILED"), ("delivery_unknown", "INCONCLUSIVE")])
async def test_raw_semantic_protocol_faults_never_release(tmp_path, fault, expected):
    trial = make_trial(tmp_path, verifier_fault=fault)
    submitted = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id=fault)
    result = await trial.finish(submitted["run_id"])
    assert result["status"] == expected and result["accepted_ref"] is None
    assert len(trial.bridge.calls) == 2
    run = trial.application.store.get_run(result["run_id"], caller_id=trial.context.user_id)
    assert len(run["attempts"]) == 2
    if fault != "delivery_unknown":
        assert any(ref["type"] == "raw_assessment" for ref in run["artifacts"])


@pytest.mark.asyncio
async def test_semantic_inconclusive_blocks_and_limitations_remain_visible(tmp_path):
    trial = make_trial(tmp_path / "uncertain", inconclusive_check="F4")
    run = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="uncertain")
    result = await trial.finish(run["run_id"])
    assert result["status"] == "INCONCLUSIVE" and result["accepted_ref"] is None
    limited = make_trial(tmp_path / "limited", limitations=["Same scripted provider; no reliability measurement."])
    run = await limited.application.submit(limited.context, original_text=OBJECTIVE, client_request_id="limited")
    result = await limited.finish(run["run_id"])
    assert result["status"] == "ACCEPTED" and result["decision"]["verdict"] == "PASS_WITH_KNOWN_LIMITATIONS"
    assert result["decision"]["limitations"] == ["Same scripted provider; no reliability measurement."]


@pytest.mark.asyncio
async def test_timeout_and_call_budget_short_circuit_exactly_once(tmp_path):
    trial = make_trial(tmp_path / "timeout", delay_role="compiler")
    run = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="timeout", options={"timeout_seconds": 0.5})
    result = await trial.finish(run["run_id"])
    assert result["status"] == "FAILED" and len(trial.bridge.calls) == 1
    assert trial.application.store.get_run(run["run_id"], caller_id=trial.context.user_id)["attempts"][0]["outcome"] == "TIMED_OUT"
    bounded = make_trial(tmp_path / "bounded")
    run = await bounded.application.submit(bounded.context, original_text=OBJECTIVE, client_request_id="budget", options={"max_calls": 1})
    result = await bounded.finish(run["run_id"])
    assert result["status"] == "FAILED" and result["decision"]["reasons"] == ["call_budget"]
    assert len(bounded.bridge.calls) == 1


@pytest.mark.asyncio
async def test_ambiguous_submission_reconciles_without_dispatch_or_changed_identity(tmp_path):
    trial = make_trial(tmp_path, wait_role="compiler")
    first = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="reconcile")
    await asyncio.wait_for(trial.bridge.entered.wait(), 2)
    repeated = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="reconcile")
    assert repeated["run_id"] == first["run_id"] and len(trial.bridge.calls) == 1
    with pytest.raises(GovernanceError, match="changed input"):
        await trial.application.submit(trial.context, original_text="Changed objective", client_request_id="reconcile")
    trial.bridge.release.set()
    result = await trial.finish(first["run_id"])
    assert result["status"] == "ACCEPTED" and len(trial.bridge.calls) == 2


@pytest.mark.asyncio
async def test_browser_disconnect_does_not_cancel_but_explicit_cancel_is_distinct(tmp_path):
    trial = make_trial(tmp_path, wait_role="compiler")
    async with trial.client() as browser:
        response = await browser.post("/api/intent-trial/runs", json={"original_text": OBJECTIVE, "client_request_id": "browser"})
        assert response.status_code == 202
        run_id = response.json()["run_id"]
    await asyncio.wait_for(trial.bridge.entered.wait(), 2)
    assert run_id in trial.application.tasks and not trial.application.tasks[run_id].done()
    result = await trial.application.cancel(trial.context, run_id)
    assert result["status"] == "CANCELLED" and result["accepted_ref"] is None and len(trial.bridge.calls) == 1
    trial.bridge.release.set()
    assert trial.application.store.recover_interrupted() == []
    attempt = trial.application.store.get_run(run_id, caller_id=trial.context.user_id)["attempts"][0]
    assert attempt["outcome"] == "CANCELLED" and attempt["evidence"]["effects_undone"] is False
    assert {check["check_id"] for check in result["not_run"]} >= {"verifier_dispatch", "semantic:F1", "semantic:F6"}


@pytest.mark.asyncio
async def test_browser_disconnect_allows_service_owned_completion(tmp_path):
    trial = make_trial(tmp_path, wait_role="compiler")
    async with trial.client() as browser:
        submitted = await browser.post("/api/intent-trial/runs", json={"original_text": OBJECTIVE, "client_request_id": "disconnected"})
        assert submitted.status_code == 202
        run_id = submitted.json()["run_id"]
    await asyncio.wait_for(trial.bridge.entered.wait(), 2)
    trial.bridge.release.set()
    result = await trial.finish(run_id)
    assert result["status"] == "ACCEPTED" and len(trial.bridge.calls) == 2


@pytest.mark.asyncio
async def test_unavailable_provider_and_changed_pin_are_retained_without_dispatch(tmp_path):
    unavailable = make_trial(tmp_path / "unavailable", available=False)
    submitted = await unavailable.application.submit(unavailable.context, original_text=OBJECTIVE, client_request_id="unavailable")
    result = await unavailable.finish(submitted["run_id"])
    assert result["status"] == "ENVIRONMENT_BLOCKED" and unavailable.bridge.calls == []
    assert result["decision"]["reasons"] == ["environment_unavailable"]
    changed = make_trial(tmp_path / "changed")
    submitted = await changed.application.submit(changed.context, original_text=OBJECTIVE, client_request_id="changed")
    (changed.package / "intent/compiler.prompt.md").write_text("Changed source closure after run freeze.", encoding="utf-8")
    result = await changed.finish(submitted["run_id"])
    assert result["status"] == "ENVIRONMENT_BLOCKED" and changed.bridge.calls == []
    assert result["decision"]["reasons"] == ["ineligible_pin"]


@pytest.mark.asyncio
async def test_restart_pauses_unfinished_and_fresh_correction_is_a_new_run(tmp_path):
    trial = make_trial(tmp_path, wait_role="compiler")
    run = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="unfinished")
    await asyncio.wait_for(trial.bridge.entered.wait(), 2)
    await trial.application.shutdown()
    result = trial.application.project(trial.context, run["run_id"])
    assert result["status"] == "PAUSED" and result["accepted_ref"] is None and len(trial.bridge.calls) == 1
    assert trial.application.store.get_run(run["run_id"], caller_id=trial.context.user_id)["attempts"][0]["outcome"] == "INTERRUPTED"
    assert {check["check_id"] for check in result["not_run"]} >= {"deterministic_validation", "verifier_dispatch", "semantic:F1", "semantic:F6", "protected_release"}
    assert all(check["status"] == "NOT_RUN" and "no replay" in check["reason"] for check in result["not_run"])
    repeated = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="unfinished")
    assert repeated["status"] == "PAUSED" and len(trial.bridge.calls) == 1
    trial.bridge.wait_role = None
    correction = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="fresh", predecessor_run_id=run["run_id"])
    fresh = await trial.finish(correction["run_id"])
    assert fresh["status"] == "ACCEPTED" and fresh["predecessor_run_id"] == run["run_id"]
    assert fresh["run_id"] != run["run_id"] and len(trial.bridge.calls) == 3


@pytest.mark.asyncio
async def test_final_persistence_failure_preserves_exact_unreleased_evidence(tmp_path):
    trial = make_trial(tmp_path)
    def fail(stage):
        if stage == "before_release":
            raise OSError("Independent final persistence fault")
    trial.application.store._fault_injector = fail
    run = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="persistence")
    task = trial.application.tasks[run["run_id"]]
    await asyncio.wait_for(asyncio.shield(task), 5)
    snapshot = trial.application.store.get_run(run["run_id"], caller_id=trial.context.user_id)
    assert snapshot["status"] == "DECIDING" and snapshot["decision"] is None and snapshot["accepted_ref"] is None
    projected = trial.application.project(trial.context, run["run_id"])
    assert projected["status"] == "ENVIRONMENT_BLOCKED" and projected["durable_status"] == "DECIDING"
    assert projected["reason_durable"] is False and projected["accepted_ref"] is None
    assert len(trial.bridge.calls) == 2
    assert {ref["type"] for ref in snapshot["artifacts"]} >= {"intent_candidate", "raw_assessment", "deterministic_checks"}
    trial.application.store._fault_injector = None
    assert trial.application.store.recover_interrupted() == [run["run_id"]]
    assert trial.application.project(trial.context, run["run_id"])["status"] == "PAUSED"


@pytest.mark.asyncio
async def test_actual_authentication_foreign_workspace_and_bundle_isolation(tmp_path):
    trial = make_trial(tmp_path)
    async with trial.client() as client:
        response = await client.post("/api/intent-trial/runs", json={"original_text": OBJECTIVE, "client_request_id": "auth"})
        run_id = response.json()["run_id"]
        await trial.finish(run_id)
        bundle = await client.get(f"/api/intent-trial/runs/{run_id}/bundle")
        assert bundle.status_code == 200 and bundle.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
            exported = json.loads(archive.read("manifest.json"))
            assert hash_json(exported["manifest"]) == exported["manifest_sha256"]
            for member in exported["manifest"]["members"]:
                ref = member["reference"]
                assert sha256_bytes(archive.read(ref["artifact_id"] + ".bin")) == ref["sha256"]
            assert trial.token.encode() not in bundle.content
        denied = await client.get("/api/intent-trial/readiness", headers={"Authorization": "Bearer invalid"})
        assert denied.status_code == 403
        origin = await client.get("/api/intent-trial/readiness", headers={"Origin": "https://unrelated.example"})
        assert origin.status_code == 403
        host = await client.get("/api/intent-trial/readiness", headers={"Host": "unrelated.example:4311"})
        assert host.status_code == 403
    other = replace(trial.context, workspace_id="foreign-workspace")
    for operation in (lambda: trial.application.project(other, run_id), lambda: trial.application._owned_run(other, run_id)):
        with pytest.raises(GovernanceError) as error:
            operation()
        assert error.value.code == "policy_denied"
    trial.application.identity.revoke_session(trial.token)
    foreign_path = tmp_path / "foreign-workspace"
    foreign_path.mkdir()
    ws = trial.application.identity.register_workspace(foreign_path)
    foreign_token = trial.application.identity.issue_session(ws.workspace_id)
    async with trial.client(token=foreign_token) as client:
        denied = await client.get(f"/api/intent-trial/runs/{run_id}")
        assert denied.status_code == 403 and denied.json()["detail"]["code"] == "policy_denied"
        denied = await client.get(f"/api/intent-trial/runs/{run_id}/bundle")
        assert denied.status_code == 403 and denied.json()["detail"]["code"] == "policy_denied"
