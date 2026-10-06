"""Independent local custody/failure cases; no real-model acceptance claim."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from jiuwenswarm.ai4research.common import GovernanceError, canonical_json, hash_json
from jiuwenswarm.ai4research.evidence import EvidenceViews
from jiuwenswarm.ai4research.state import RunStore

PROFILE = "f" * 64
CONFIG = {"route": "explicit-local-fixture", "requested_seed": 42, "effective_seed": None,
          "seed_unavailable_reason": "Fixture provider has no seed control", "profile_sha256": PROFILE}
CONTRACT = {"node_id": "intent", "profile_sha256": PROFILE, "time_seconds": 10, "model_calls": 2}
PINS = {"compiler": {"sha256": "a" * 64}, "verifier": {"sha256": "b" * 64}}
ORIGINAL = "Preserve this exact scientific objective — no chosen solution."


@pytest.fixture
def custody(tmp_path):
    authority = object()
    store = RunStore(tmp_path / "state.sqlite", tmp_path / "artifacts", gate_authority=authority)
    run = store.create_run(user_id="researcher", workspace_id="workspace", client_request_id="request-1",
                           original_text=ORIGINAL, configuration=CONFIG, contract=CONTRACT,
                           pins=PINS, mode="mock")
    return store, authority, run


def completed_pair(store, run_id):
    store.set_status(run_id, "COMPILING", caller_id="researcher")
    compiler = store.begin_attempt(run_id, "compiler", caller_id="researcher")
    candidate = store.put_artifact(run_id, canonical_json({"objective": ORIGINAL}),
                                   artifact_type="intent_candidate", schema_revision="intent-r2", origin="candidate",
                                   attempt_id=compiler["attempt_id"], caller_id="researcher",
                                   audiences=("local", "verifier"))
    store.finish_attempt(run_id, compiler["attempt_id"], outcome="SUCCEEDED",
                         evidence={"output_ref": candidate, "elapsed_seconds": 0.02, "model_calls": 1},
                         caller_id="researcher")
    store.set_status(run_id, "CHECKING", caller_id="researcher")
    checks = store.put_artifact(run_id, canonical_json({"mandatory_pass": True}),
                                artifact_type="deterministic_findings", origin="checks", caller_id="researcher")
    store.record_event(run_id, "deterministic_checks", {"reference": checks, "mandatory_pass": True},
                       caller_id="researcher")
    store.set_status(run_id, "VERIFYING", caller_id="researcher")
    verifier = store.begin_attempt(run_id, "verifier", caller_id="researcher")
    assessment = store.put_artifact(run_id, b'{"fidelity":"faithful"}', artifact_type="raw_assessment",
                                    origin="assessment", attempt_id=verifier["attempt_id"], caller_id="researcher")
    store.finish_attempt(run_id, verifier["attempt_id"], outcome="SUCCEEDED",
                         evidence={"output_ref": assessment, "elapsed_seconds": 0.03, "model_calls": 1},
                         caller_id="researcher")
    store.set_status(run_id, "DECIDING", caller_id="researcher")
    refs = [candidate, checks, assessment]
    decision = {"verdict": "PASS", "subject_ref": candidate, "checks": [{"mandatory": True, "status": "PASS"}],
                "reasons": ["Independent fixture expects faithful extraction"], "evidence_refs": refs,
                "profile_sha256": PROFILE, "contract_sha256": hash_json(CONTRACT), "mandatory_pass": True}
    return candidate, refs, decision


def accept(store, authority, run_id):
    candidate, refs, decision = completed_pair(store, run_id)
    receipt = store.commit_decision(run_id, subject_ref=candidate, decision=decision, evidence_refs=refs,
                                    authority=authority, caller_id="researcher", idempotency_key="gate-1")
    return candidate, refs, decision, receipt


def test_m0_005_b01_exact_input_frozen_context_and_idempotent_submission(custody):
    store, _, run = custody
    repeated = store.create_run(user_id="researcher", workspace_id="workspace", client_request_id="request-1",
                                original_text=ORIGINAL, configuration=CONFIG, contract=CONTRACT,
                                pins=PINS, mode="mock")
    assert repeated["run_id"] == run["run_id"]
    assert store.get_artifact(run["original_ref"], caller_id="researcher") == ORIGINAL.encode("utf-8")
    assert repeated["configuration"] == CONFIG and repeated["contract"] == CONTRACT and repeated["pins"] == PINS
    assert len(store.list_runs(caller_id="researcher", workspace_id="workspace")) == 1
    assert store.list_runs(caller_id="another-user") == []


@pytest.mark.parametrize("changed", ["original_text", "configuration", "contract", "pins", "mode"])
def test_m0_005_b01_changed_request_payload_is_not_reconciled(custody, changed):
    store, _, run = custody
    args = dict(user_id="researcher", workspace_id="workspace", client_request_id="request-1",
                original_text=ORIGINAL, configuration=dict(CONFIG), contract=dict(CONTRACT), pins=dict(PINS), mode="mock")
    if changed == "original_text":
        args[changed] = "A materially different request"
    elif changed == "mode":
        args[changed] = "headless"
    else:
        args[changed][next(iter(args[changed]))] = "changed"
    with pytest.raises(GovernanceError, match="changed input"):
        store.create_run(**args)
    assert store.get_run(run["run_id"], caller_id="researcher")["original_text"] == ORIGINAL


@pytest.mark.parametrize("text", ["", " ", "\n\t"])
def test_m0_005_b01_empty_input_has_no_run(tmp_path, text):
    store = RunStore(tmp_path / "state.sqlite", tmp_path / "files", gate_authority=object())
    with pytest.raises(GovernanceError):
        store.create_run(user_id="researcher", workspace_id="workspace", client_request_id="r",
                         original_text=text, configuration=CONFIG, contract=CONTRACT, pins=PINS)
    assert store.list_runs(caller_id="researcher") == []


def test_m0_005_b01_restart_pauses_without_replay_and_correction_retains_lineage(custody):
    store, authority, run = custody
    attempt = store.begin_attempt(run["run_id"], "compiler", caller_id="researcher")
    store.put_artifact(run["run_id"], b"partial output", artifact_type="partial", attempt_id=attempt["attempt_id"], caller_id="researcher")
    reopened = RunStore(store.db_path, store.artifacts_dir, gate_authority=authority)
    assert reopened.get_run(run["run_id"], caller_id="researcher")["attempts"][0]["outcome"] == "RUNNING"
    assert reopened.recover_interrupted() == [run["run_id"]]
    paused = reopened.get_run(run["run_id"], caller_id="researcher")
    assert paused["status"] == "PAUSED" and paused["attempts"][0]["outcome"] == "INTERRUPTED"
    not_run = [check for event in paused["events"] if event["event_type"] == "not_run" for check in event["payload"]["checks"]]
    assert {check["check_id"] for check in not_run} >= {"deterministic_validation", "verifier_dispatch", "semantic:F1", "semantic:F6", "protected_release"}
    assert all(check["status"] == "NOT_RUN" and "no replay" in check["reason"] for check in not_run)
    assert reopened.recover_interrupted() == []
    with pytest.raises(GovernanceError):
        reopened.begin_attempt(run["run_id"], "compiler", caller_id="researcher")
    correction = reopened.create_run(user_id="researcher", workspace_id="workspace", client_request_id="corrected",
                                     original_text="Corrected input", configuration=CONFIG, contract=CONTRACT,
                                     pins=PINS, predecessor_run_id=run["run_id"])
    assert correction["run_id"] != run["run_id"] and correction["predecessor_run_id"] == run["run_id"]
    assert reopened.get_run(run["run_id"], caller_id="researcher")["attempts"] == paused["attempts"]


def test_m0_005_b01_cancel_is_distinct_and_cannot_resume(custody):
    store, _, run = custody
    store.begin_attempt(run["run_id"], "compiler", caller_id="researcher")
    with pytest.raises(GovernanceError):
        store.cancel(run["run_id"], caller_id="foreign")
    cancelled = store.cancel(run["run_id"], caller_id="researcher")
    assert cancelled["status"] == "CANCELLED" and cancelled["attempts"][0]["outcome"] == "CANCELLED"
    assert cancelled["attempts"][0]["evidence"]["effects_undone"] is False
    assert store.recover_interrupted() == []
    with pytest.raises(GovernanceError):
        store.set_status(run["run_id"], "COMPILING", caller_id="researcher")


def test_m0_005_b02_exact_durable_acceptance_and_reconciliation(custody):
    store, authority, run = custody
    candidate, refs, decision, receipt = accept(store, authority, run["run_id"])
    repeated = store.commit_decision(run["run_id"], subject_ref=candidate, decision=decision, evidence_refs=refs,
                                     authority=authority, caller_id="researcher", idempotency_key="gate-1")
    assert repeated == receipt
    assert store.get_run(run["run_id"], caller_id="researcher")["accepted_ref"] == candidate
    reopened = RunStore(store.db_path, store.artifacts_dir, gate_authority=authority)
    assert reopened.recover_interrupted() == []
    assert reopened.get_artifact(candidate, caller_id="researcher") == canonical_json({"objective": ORIGINAL})
    changed = dict(decision, reasons=["Changed historical decision"])
    with pytest.raises(GovernanceError):
        reopened.commit_decision(run["run_id"], subject_ref=candidate, decision=changed, evidence_refs=refs,
                                 authority=authority, caller_id="researcher", idempotency_key="gate-1")


@pytest.mark.parametrize("fault", ["before_release", "before_transaction_commit"])
def test_m0_005_b02_transaction_failure_has_no_half_acceptance(custody, fault):
    store, authority, run = custody
    candidate, refs, decision = completed_pair(store, run["run_id"])
    def fail(stage):
        if stage == fault:
            raise OSError("independent injected filesystem/commit failure")
    store._fault_injector = fail
    with pytest.raises(GovernanceError) as error:
        store.commit_decision(run["run_id"], subject_ref=candidate, decision=decision, evidence_refs=refs,
                              authority=authority, caller_id="researcher", idempotency_key="gate-1")
    assert error.value.code == "persistence_failed"
    snapshot = store.get_run(run["run_id"], caller_id="researcher")
    assert snapshot["accepted_ref"] is None and snapshot["decision"] is None and snapshot["status"] == "DECIDING"
    assert store.get_artifact(candidate, caller_id="researcher")


def test_m0_005_b02_lost_acknowledgement_reconciles_without_reexecution(custody):
    store, authority, run = custody
    candidate, refs, decision = completed_pair(store, run["run_id"])
    def lose_reply(stage):
        if stage == "after_decision_commit":
            raise OSError("response transport disappeared after durable commit")
    store._fault_injector = lose_reply
    with pytest.raises(OSError):
        store.commit_decision(run["run_id"], subject_ref=candidate, decision=decision, evidence_refs=refs,
                              authority=authority, caller_id="researcher", idempotency_key="gate-1")
    store._fault_injector = None
    reconciled = store.commit_decision(run["run_id"], subject_ref=candidate, decision=decision, evidence_refs=refs,
                                      authority=authority, caller_id="researcher", idempotency_key="gate-1")
    assert reconciled["accepted_ref"] == candidate
    assert len(store.get_run(run["run_id"], caller_id="researcher")["attempts"]) == 2


@pytest.mark.parametrize("status", ["FAIL", "INCONCLUSIVE", "ENVIRONMENT_BLOCKED", None])
def test_m0_005_b02_summary_pass_cannot_override_mandatory_findings(custody, status):
    store, authority, run = custody
    candidate, refs, decision = completed_pair(store, run["run_id"])
    decision["checks"].append({"check_id": "independent-negative", "status": status})
    assert decision["mandatory_pass"] is True
    with pytest.raises(GovernanceError, match="Every mandatory finding"):
        store.commit_decision(run["run_id"], subject_ref=candidate, decision=decision, evidence_refs=refs,
                              authority=authority, caller_id="researcher", idempotency_key="gate-1")
    snapshot = store.get_run(run["run_id"], caller_id="researcher")
    assert snapshot["decision"] is None and snapshot["accepted_ref"] is None


@pytest.mark.parametrize("artifact_type,schema", [("raw_assessment", "intent-r2"), ("intent_candidate", "r2")])
def test_m0_005_b02_subject_must_be_actual_intent_type_schema(custody, artifact_type, schema):
    store, authority, run = custody
    candidate, refs, decision = completed_pair(store, run["run_id"])
    impostor = store.put_artifact(run["run_id"], store.get_artifact(candidate, caller_id="researcher"),
                                  artifact_type=artifact_type, schema_revision=schema, caller_id="researcher")
    decision["subject_ref"] = impostor
    decision["evidence_refs"] = [impostor, *refs]
    with pytest.raises(GovernanceError, match="candidate type/schema"):
        store.commit_decision(run["run_id"], subject_ref=impostor, decision=decision,
                              evidence_refs=decision["evidence_refs"], authority=authority,
                              caller_id="researcher", idempotency_key="gate-1")
    assert store.get_run(run["run_id"], caller_id="researcher")["accepted_ref"] is None


@pytest.mark.parametrize("changed", ["authority", "subject", "mandatory", "contract", "profile", "omitted_assessment"])
def test_m0_005_b02_invalid_release_binding_denied(custody, changed):
    store, authority, run = custody
    candidate, refs, decision = completed_pair(store, run["run_id"])
    if changed == "authority": authority = object()
    elif changed == "subject": decision["subject_ref"] = dict(candidate, sha256="0" * 64)
    elif changed == "mandatory": decision["mandatory_pass"] = False
    elif changed == "contract": decision["contract_sha256"] = "0" * 64
    elif changed == "profile": decision["profile_sha256"] = "0" * 64
    elif changed == "omitted_assessment":
        refs = refs[:-1]
        decision["evidence_refs"] = refs
    with pytest.raises(GovernanceError):
        store.commit_decision(run["run_id"], subject_ref=candidate, decision=decision, evidence_refs=refs,
                              authority=authority, caller_id="researcher", idempotency_key="gate-1")
    assert store.get_run(run["run_id"], caller_id="researcher")["accepted_ref"] is None


def test_m0_005_b02_no_success_evidence_no_release_and_blocking_decision_retained(custody):
    store, authority, run = custody
    candidate = store.put_artifact(run["run_id"], b"unexecuted", artifact_type="candidate", caller_id="researcher")
    decision = {"verdict": "PASS", "subject_ref": candidate, "evidence_refs": [candidate], "checks": [True],
                "mandatory_pass": True, "contract_sha256": hash_json(CONTRACT), "profile_sha256": PROFILE}
    with pytest.raises(GovernanceError):
        store.commit_decision(run["run_id"], subject_ref=candidate, decision=decision, evidence_refs=[candidate],
                              authority=authority, caller_id="researcher", idempotency_key="gate")
    decision.update(verdict="INCONCLUSIVE", mandatory_pass=False, reasons=["Missing actual observations"])
    receipt = store.commit_decision(run["run_id"], subject_ref=candidate, decision=decision, evidence_refs=[candidate],
                                    authority=authority, caller_id="researcher", idempotency_key="refusal")
    assert receipt["accepted_ref"] is None
    assert store.get_run(run["run_id"], caller_id="researcher")["status"] == "INCONCLUSIVE"
    with pytest.raises(GovernanceError):
        store.set_status(run["run_id"], "ACCEPTED", caller_id="researcher")


def test_m0_005_b03_actual_records_bundle_and_unavailable_usage(custody):
    store, authority, run = custody
    accept(store, authority, run["run_id"])
    views = EvidenceViews(store)
    ref = views.write_bundle(run["run_id"], caller_id="researcher")
    manifest = views.verify_bundle(ref, caller_id="researcher")
    assert manifest["status"] == "ACCEPTED" and manifest["mode"] == "mock"
    assert manifest["configuration"]["effective_seed"] is None
    assert len(manifest["attempts"]) == 2
    for attempt in manifest["attempts"]:
        assert attempt["evidence"]["usage"]["tokens"] is None
        assert attempt["evidence"]["usage"]["cost"] is None
        assert attempt["evidence"]["usage"]["unavailable_reason"]
    records = (store.artifacts_dir / ref["locator"]).parent / "records.jsonl"
    assert [json.loads(line) for line in records.read_text(encoding="utf-8").splitlines()] == manifest["events"]
    assert views.write_bundle(run["run_id"], caller_id="researcher") == ref


@pytest.mark.parametrize("usage", [{"tokens": 0, "cost": 0}, {"tokens": -1, "reliable": True, "source": "endpoint"},
                                    {"cost": float("nan"), "reliable": True, "source": "endpoint"}])
def test_m0_005_b03_unsubstantiated_usage_refused(custody, usage):
    store, _, run = custody
    attempt = store.begin_attempt(run["run_id"], "compiler", caller_id="researcher")
    output = store.put_artifact(run["run_id"], b"candidate", artifact_type="candidate", attempt_id=attempt["attempt_id"], caller_id="researcher")
    with pytest.raises(GovernanceError):
        store.finish_attempt(run["run_id"], attempt["attempt_id"], outcome="SUCCEEDED",
                             evidence={"output_ref": output, "elapsed_seconds": 1, "model_calls": 1, "usage": usage}, caller_id="researcher")


def test_m0_005_b03_failed_capture_retained_and_credentials_excluded(custody):
    store, _, run = custody
    attempt = store.begin_attempt(run["run_id"], "compiler", caller_id="researcher")
    store.finish_attempt(run["run_id"], attempt["attempt_id"], outcome="DELIVERY_UNKNOWN",
                         evidence={"transport_outcome": "uncertain"}, caller_id="researcher")
    snapshot = store.get_run(run["run_id"], caller_id="researcher")
    assert snapshot["attempts"][0]["outcome"] == "DELIVERY_UNKNOWN" and snapshot["accepted_ref"] is None
    with pytest.raises(GovernanceError): store.begin_attempt(run["run_id"], "verifier", caller_id="researcher")
    with pytest.raises(GovernanceError): store.begin_attempt(run["run_id"], "compiler", caller_id="researcher")
    with pytest.raises(GovernanceError):
        store.record_event(run["run_id"], "capture", {"api_key": "never-store-this"}, caller_id="researcher")
    assert "never-store-this" not in canonical_json(store.get_run(run["run_id"], caller_id="researcher")).decode()


def test_m0_005_b07_inspection_cannot_release_and_known_missing_observations_visible(custody):
    store, _, run = custody
    store.record_event(run["run_id"], "conformance", {"observed_tool": "forbidden-browser", "mandatory_observation": "unavailable"}, caller_id="researcher")
    views = EvidenceViews(store)
    snapshot = views.inspect(run["run_id"], caller_id="researcher")
    assert snapshot["accepted_ref"] is None
    assert snapshot["events"][-1]["payload"] == {"observed_tool": "forbidden-browser", "mandatory_observation": "unavailable"}
    snapshot["accepted_ref"] = {"fabricated": True}
    assert views.inspect(run["run_id"], caller_id="researcher")["accepted_ref"] is None
    with pytest.raises(GovernanceError): views.inspect(run["run_id"], caller_id="foreign")
    with pytest.raises(GovernanceError): store.record_event(run["run_id"], "accepted", {}, caller_id="researcher")


def test_m0_005_b07_artifact_tampering_and_audience_isolation(custody):
    store, _, run = custody
    ref = store.put_artifact(run["run_id"], b"candidate", artifact_type="candidate", caller_id="researcher")
    with pytest.raises(GovernanceError): store.get_artifact(ref, caller_id="foreign")
    with pytest.raises(GovernanceError): store.get_artifact(ref, caller_id="researcher", audience="verifier")
    with pytest.raises(GovernanceError): store.get_artifact(dict(ref, locator="../../outside"), caller_id="researcher")
    (store.artifacts_dir / ref["locator"]).write_bytes(b"swapped bytes")
    with pytest.raises(GovernanceError, match="stored identity"):
        store.get_artifact(ref, caller_id="researcher")


def test_m0_005_b03_observation_reference_must_have_exact_attempt_attribution(custody):
    store, _, run = custody
    attempt = store.begin_attempt(run["run_id"], "compiler", caller_id="researcher")
    unrelated = store.put_artifact(run["run_id"], b"unattributed observation", artifact_type="invocation_observation",
                                   origin="observed", caller_id="researcher")
    with pytest.raises(GovernanceError, match="exact producing attribution"):
        store.finish_attempt(run["run_id"], attempt["attempt_id"], outcome="FAILED",
                             evidence={"observation_ref": unrelated, "error": "prohibited_effect"}, caller_id="researcher")
    assert store.get_run(run["run_id"], caller_id="researcher")["attempts"][0]["outcome"] == "RUNNING"


def test_m0_005_b07_append_only_database_enforced(custody):
    store, _, run = custody
    with sqlite3.connect(store.db_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE runs SET original_text='rewritten' WHERE run_id=?", (run["run_id"],))
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM events WHERE run_id=?", (run["run_id"],))


def test_m0_005_b07_bundle_tamper_refused_and_missing_projection_rebuilt(custody):
    store, _, run = custody
    views = EvidenceViews(store)
    ref = views.write_bundle(run["run_id"], caller_id="researcher")
    path = store.artifacts_dir / ref["locator"]
    payload = path.read_bytes()
    path.write_bytes(b"{}")
    with pytest.raises(GovernanceError): views.verify_bundle(ref, caller_id="researcher")
    path.unlink()
    assert views.write_bundle(run["run_id"], caller_id="researcher") == ref
    assert path.read_bytes() == payload and store.get_run(run["run_id"], caller_id="researcher")["accepted_ref"] is None


@pytest.mark.parametrize("change", ["attempt", "member", "decision"])
def test_m0_005_b07_rehashed_projection_cannot_forge_or_omit_observations(custody, change):
    store, authority, run = custody
    accept(store, authority, run["run_id"])
    views = EvidenceViews(store)
    original = views.write_bundle(run["run_id"], caller_id="researcher")
    old_path = store.artifacts_dir / original["locator"]
    manifest = json.loads(old_path.read_bytes())
    if change == "attempt":
        manifest["attempts"][0]["evidence"]["usage"]["tokens"] = 0
    elif change == "member":
        manifest["members"].pop()
    else:
        manifest["decision"] = None
    forged_hash = hash_json(manifest)
    folder = old_path.parent.parent / forged_hash[:24]
    folder.mkdir()
    forged_path = folder / "manifest.json"
    forged_path.write_bytes(canonical_json(manifest))
    forged = dict(original, manifest_sha256=forged_hash,
                  locator=str(forged_path.relative_to(store.artifacts_dir)).replace("\\", "/"))
    with pytest.raises(GovernanceError) as error:
        views.verify_bundle(forged, caller_id="researcher")
    assert error.value.code == "invalid_input"
    assert views.verify_bundle(original, caller_id="researcher")["accepted_ref"] == manifest["accepted_ref"]
