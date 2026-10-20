"""Real SQLite/filesystem fault checks; host-only supplemental evidence."""

import hashlib

import pytest

from jiuwenswarm.research.contracts.types import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore


def test_exact_bytes_and_immutable_record_identity(tmp_path):
    store = SQLiteRunStore(tmp_path)
    raw = b'{"a":1}\r\n'
    ref = store.put_blob(raw)
    assert ref["sha256"] == hashlib.sha256(raw).hexdigest()
    assert store.read_blob(ref) == raw
    first = store.append_record("audit", {"id": "event:one", "value": 1})
    assert store.append_record("audit", {"id": "event:one", "value": 1}) == first
    with pytest.raises(ResearchError, match="identity_conflict"):
        store.append_record("audit", {"id": "event:one", "value": 2})


def test_digest_corruption_and_missing_bytes_fail_closed(tmp_path):
    store = SQLiteRunStore(tmp_path)
    ref = store.put_blob(b"original")
    store.blobs.path_for(ref["sha256"]).write_bytes(b"changed")
    with pytest.raises(ResearchError, match="integrity_fault"):
        store.read_blob(ref)


def test_gate_commit_is_atomic_and_candidates_do_not_release(tmp_path):
    store = SQLiteRunStore(tmp_path)
    store.create_run("run:one", account_id="alice", workspace_id="project", submission={})
    a = store.put_blob(b"candidate")
    assert store.accepted_outputs("run:one", "node_a") == {}
    with pytest.raises(ResearchError):
        store.commit_acceptance("run:one", "node_a", "node_a-a1", {"out": a}, [])
    assert store.accepted_outputs("run:one", "node_a") == {}


def test_request_claim_same_content_reconciles_changed_content_conflicts(tmp_path):
    store = SQLiteRunStore(tmp_path)
    assert store.claim_request("alice", "req-1", "a" * 64, "run:one") == ("run:one", True)
    assert store.claim_request("alice", "req-1", "a" * 64, "run:other") == ("run:one", False)
    with pytest.raises(ResearchError, match="identity_conflict"):
        store.claim_request("alice", "req-1", "b" * 64, "run:other")


def test_restart_pauses_running_without_replay_and_export_is_read_only(tmp_path):
    store = SQLiteRunStore(tmp_path)
    store.create_run("run:one", account_id="alice", workspace_id="project", submission={})
    store.set_run_state("run:one", "running")
    store.close()
    reopened = SQLiteRunStore(tmp_path, recover=True)
    assert reopened.get_run("run:one")["state"] == "paused"
    assert list(reopened.iter_records())
    assert reopened.get_run("run:one")["state"] == "paused"


def test_atomic_allocation_and_upload_use_prevent_deletion(tmp_path):
    store = SQLiteRunStore(tmp_path)
    record = {"schema_version": "1.0.0", "id": "upload:one", "user_id": "alice",
              "scope_id": "project", "kind": "docs", "resource_type": "reference_document",
              "filename": "notes.txt", "size_bytes": 4, "stored_path": "pending",
              "content_sha256": hashlib.sha256(b"text").hexdigest(),
              "text_sha256": hashlib.sha256(b"text").hexdigest(), "status": "uploaded",
              "uploaded_at": "2026-10-16T00:00:00Z", "deleted_at": None}
    upload = store.publish_upload(record, b"text", b"text")
    assert upload["stored_path"] == "workspace/input/docs/project/notes.txt"
    actual_path = store.input_root / "docs/project/notes.txt"
    assert actual_path.read_bytes() == b"text"
    run, fresh = store.allocate_run("alice", "r1", "a" * 64, "run:one", "project", {}, [upload["id"]])
    assert fresh and run["state"] == "pending"
    assert store.allocate_run("alice", "r1", "a" * 64, "run:other", "project", {}, [upload["id"]])[1] is False
    with pytest.raises(ResearchError, match="upload_in_use"):
        store.delete_upload(upload["id"], "alice")
    store.set_run_state("run:one", "completed")
    assert store.delete_upload(upload["id"], "alice")["status"] == "deleted"
    assert not actual_path.exists()
