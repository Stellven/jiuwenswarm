"""Real local SQLite/filesystem/process boundaries; model calls are fixtures."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from jiuwenswarm.ai4research.common import GovernanceError, canonical_json, hash_json, sha256_bytes
from jiuwenswarm.ai4research.evidence import EvidenceViews
from jiuwenswarm.ai4research.state import RunStore

PROFILE = "c" * 64
CONFIG = {"route": "explicit-boundary-fixture", "profile_sha256": PROFILE}
CONTRACT = {"node_id": "intent", "profile_sha256": PROFILE, "model_calls": 2, "time_seconds": 10}
PINS = {"compiler": "a" * 64, "verifier": "b" * 64}


@pytest.fixture
def boundary(tmp_path):
    authority = object()
    store = RunStore(tmp_path / "state.sqlite", tmp_path / "files", gate_authority=authority,
                     busy_timeout_seconds=0.01)
    run = store.create_run(user_id="owner", workspace_id="workspace", client_request_id="submission",
                           original_text="Only extract this objective; do not propose a method.",
                           configuration=CONFIG, contract=CONTRACT, pins=PINS, mode="mock")
    return store, authority, run["run_id"]


def prepared_pair(store, run_id):
    outputs = []
    for role, status, content in [("compiler", "COMPILING", b'{"objective":"Only extract this objective"}'),
                                  ("verifier", "VERIFYING", b'{"finding":"source-faithful"}')]:
        store.set_status(run_id, status, caller_id="owner")
        attempt = store.begin_attempt(run_id, role, caller_id="owner")
        ref = store.put_artifact(run_id, content, artifact_type="intent_candidate" if role == "compiler" else "raw_assessment",
                                 schema_revision="intent-r2" if role == "compiler" else "assessment-r2", attempt_id=attempt["attempt_id"],
                                 origin="candidate" if role == "compiler" else "assessment", caller_id="owner")
        store.finish_attempt(run_id, attempt["attempt_id"], outcome="SUCCEEDED",
                             evidence={"output_ref": ref, "elapsed_seconds": 0.01, "model_calls": 1}, caller_id="owner")
        outputs.append(ref)
        if role == "compiler":
            store.set_status(run_id, "CHECKING", caller_id="owner")
    store.set_status(run_id, "DECIDING", caller_id="owner")
    decision = {"verdict": "PASS", "subject_ref": outputs[0], "checks": [{"mandatory": True, "status": "PASS"}],
                "reasons": ["Fixed independently expected local fixture"], "mandatory_pass": True,
                "profile_sha256": PROFILE, "contract_sha256": hash_json(CONTRACT), "evidence_refs": outputs}
    return outputs[0], outputs, decision


def test_m0_005_b01_real_process_restart_preserves_and_pauses(boundary):
    store, authority, run_id = boundary
    attempt = store.begin_attempt(run_id, "compiler", caller_id="owner")
    script = """
import sys
from jiuwenswarm.ai4research.state import RunStore
store=RunStore(sys.argv[1],sys.argv[2],gate_authority=object())
assert store.recover_interrupted()==[sys.argv[3]]
run=store.get_run(sys.argv[3],caller_id='owner')
assert run['status']=='PAUSED' and run['attempts'][0]['outcome']=='INTERRUPTED'
assert len(run['attempts'])==1 and run['accepted_ref'] is None
"""
    process = subprocess.run([sys.executable, "-c", script, str(store.db_path), str(store.artifacts_dir), run_id],
                              capture_output=True, text=True, timeout=15)
    assert process.returncode == 0, process.stderr
    run = RunStore(store.db_path, store.artifacts_dir, gate_authority=authority).get_run(run_id, caller_id="owner")
    assert run["status"] == "PAUSED" and run["attempts"][0]["attempt_id"] == attempt["attempt_id"]
    assert len(run["attempts"]) == 1


def test_m0_005_b01_two_connections_reconcile_one_request(boundary):
    store, authority, run_id = boundary
    other = RunStore(store.db_path, store.artifacts_dir, gate_authority=authority)
    result = other.create_run(user_id="owner", workspace_id="workspace", client_request_id="submission",
                              original_text="Only extract this objective; do not propose a method.",
                              configuration=CONFIG, contract=CONTRACT, pins=PINS, mode="mock")
    assert result["run_id"] == run_id
    assert len(store.list_runs(caller_id="owner")) == 1
    with pytest.raises(GovernanceError):
        other.create_run(user_id="owner", workspace_id="workspace", client_request_id="submission",
                         original_text="Different source", configuration=CONFIG, contract=CONTRACT, pins=PINS, mode="mock")


def test_m0_005_b02_actual_sqlite_lock_prevents_release(boundary):
    store, authority, run_id = boundary
    candidate, refs, decision = prepared_pair(store, run_id)
    blocker = sqlite3.connect(store.db_path)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(GovernanceError) as error:
            store.commit_decision(run_id, subject_ref=candidate, decision=decision, evidence_refs=refs,
                                  authority=authority, caller_id="owner", idempotency_key="release")
        assert error.value.code == "persistence_failed"
        inspected = EvidenceViews(store).inspect(run_id, caller_id="owner")
        assert inspected["accepted_ref"] is None and inspected["decision"] is None
    finally:
        blocker.rollback()
        blocker.close()
    assert store.get_artifact(candidate, caller_id="owner")


def test_m0_005_b02_real_process_crash_rolls_back_release(boundary):
    store, authority, run_id = boundary
    candidate, refs, decision = prepared_pair(store, run_id)
    script = """
import json,os,sys
from jiuwenswarm.ai4research.state import RunStore
capability=object()
def crash(stage):
    if stage=='before_release': os._exit(37)
store=RunStore(sys.argv[1],sys.argv[2],gate_authority=capability,fault_injector=crash)
payload=json.loads(sys.argv[4])
store.commit_decision(sys.argv[3],subject_ref=payload['subject'],decision=payload['decision'],
 evidence_refs=payload['refs'],authority=capability,caller_id='owner',idempotency_key='release')
"""
    payload = json.dumps({"subject": candidate, "decision": decision, "refs": refs})
    process = subprocess.run([sys.executable, "-c", script, str(store.db_path), str(store.artifacts_dir), run_id, payload],
                              capture_output=True, text=True, timeout=15)
    assert process.returncode == 37, process.stderr
    reopened = RunStore(store.db_path, store.artifacts_dir, gate_authority=authority)
    run = reopened.get_run(run_id, caller_id="owner")
    assert run["accepted_ref"] is None and run["decision"] is None
    assert reopened.recover_interrupted() == [run_id]
    assert reopened.get_run(run_id, caller_id="owner")["status"] == "PAUSED"
    assert reopened.get_artifact(candidate, caller_id="owner")


def test_m0_005_b02_actual_file_directory_failure_is_not_acceptance(boundary):
    store, _, run_id = boundary
    objects = store.artifacts_dir / "objects"
    saved = store.artifacts_dir / "objects-preserved"
    objects.rename(saved)
    objects.write_bytes(b"An actual file blocks directory creation")
    try:
        with pytest.raises(GovernanceError) as error:
            store.put_artifact(run_id, b"candidate", artifact_type="candidate", caller_id="owner")
        assert error.value.code == "persistence_failed"
        assert store.get_run(run_id, caller_id="owner")["accepted_ref"] is None
    finally:
        objects.unlink()
        saved.rename(objects)
    original = store.get_run(run_id, caller_id="owner")["original_ref"]
    assert store.get_artifact(original, caller_id="owner")


def test_m0_005_b03_connected_bundle_contains_every_actual_fixture_call(boundary):
    store, authority, run_id = boundary
    candidate, refs, decision = prepared_pair(store, run_id)
    store.commit_decision(run_id, subject_ref=candidate, decision=decision, evidence_refs=refs,
                          authority=authority, caller_id="owner", idempotency_key="release")
    independent_reader = RunStore(store.db_path, store.artifacts_dir, gate_authority=authority)
    views = EvidenceViews(independent_reader)
    bundle = views.write_bundle(run_id, caller_id="owner")
    manifest = views.verify_bundle(bundle, caller_id="owner")
    assert manifest["accepted_ref"] == candidate
    assert {a["role"] for a in manifest["attempts"]} == {"compiler", "verifier"}
    assert all(a["evidence"]["model_calls"] == 1 for a in manifest["attempts"])
    assert all(a["evidence"]["usage"]["cost"] is None for a in manifest["attempts"])
    assert manifest["mode"] == "mock"
    assert {m["reference"]["artifact_id"] for m in manifest["members"]} == {r["artifact_id"] for r in independent_reader.get_run(run_id, caller_id="owner")["artifacts"]}


def test_m0_005_b07_connected_reader_refuses_tampered_accepted_bytes(boundary):
    store, authority, run_id = boundary
    candidate, refs, decision = prepared_pair(store, run_id)
    store.commit_decision(run_id, subject_ref=candidate, decision=decision, evidence_refs=refs,
                          authority=authority, caller_id="owner", idempotency_key="release")
    (store.artifacts_dir / candidate["locator"]).write_bytes(b"different bytes")
    reader = RunStore(store.db_path, store.artifacts_dir, gate_authority=authority)
    with pytest.raises(GovernanceError): EvidenceViews(reader).inspect(run_id, caller_id="owner")
    with pytest.raises(GovernanceError): EvidenceViews(reader).write_bundle(run_id, caller_id="owner")
    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute("SELECT accepted_ref FROM decisions WHERE run_id=?", (run_id,)).fetchone()[0]


def test_m0_005_b07_fabricated_projection_does_not_change_authority(boundary):
    store, _, run_id = boundary
    views = EvidenceViews(store)
    bundle = views.write_bundle(run_id, caller_id="owner")
    path = store.artifacts_dir / bundle["locator"]
    fabricated = json.loads(path.read_bytes())
    fabricated["status"] = "ACCEPTED"
    payload = canonical_json(fabricated)
    digest = sha256_bytes(payload)
    fake = dict(bundle, manifest_sha256=digest)
    original_parent = path.parent.parent
    target = original_parent / digest[:24]
    target.mkdir()
    (target / "manifest.json").write_bytes(payload)
    fake["locator"] = str((target / "manifest.json").relative_to(store.artifacts_dir)).replace("\\", "/")
    with pytest.raises(GovernanceError): views.verify_bundle(fake, caller_id="owner")
    assert views.inspect(run_id, caller_id="owner")["status"] == "QUALIFIED"
    assert views.inspect(run_id, caller_id="owner")["accepted_ref"] is None
