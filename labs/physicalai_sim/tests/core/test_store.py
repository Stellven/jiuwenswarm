"""V-BLK-STORE (AC-008, AC-013, AC-014): write-once records, append-only attempts, data dir outside the repository."""
import sqlite3
from pathlib import Path

import pytest

from simlab.contracts import SimlabError
from simlab.store import Store, resolve_data_dir

LAB = Path(__file__).resolve().parents[2]


def test_data_dir_inside_repository_refused():
    with pytest.raises(SimlabError) as e:
        resolve_data_dir(LAB / "missions" / "not-a-data-dir", create=False) if (LAB / "missions").exists() else resolve_data_dir(LAB)
    assert e.value.code == "E_DATA_DIR"


def test_undeclared_data_dir_refused(monkeypatch):
    monkeypatch.delenv("SIMLAB_DATA_DIR", raising=False)
    with pytest.raises(SimlabError) as e:
        resolve_data_dir(None)
    assert e.value.code == "E_DATA_DIR"


def test_submitted_experiment_and_manifest_are_write_once(store: Store):
    m = {"manifest_id": "man-x", "manifest_sha256": "a" * 64, "experiment_id": "exp-x", "artifacts": []}
    store.put_manifest(m)
    store.put_experiment({"experiment_id": "exp-x", "assets": {"manifest_id": "man-x"}, "objective": "o"})
    for sql in ("UPDATE experiments SET body='{}'", "DELETE FROM experiments", "UPDATE manifests SET body='{}'", "DELETE FROM manifests"):
        with pytest.raises(sqlite3.IntegrityError, match="E_IMMUTABLE"):
            with store.tx() as db:
                db.execute(sql)
    with pytest.raises(SimlabError) as e:
        store.put_experiment({"experiment_id": "exp-x", "assets": {"manifest_id": "man-x"}, "objective": "changed"})
    assert e.value.code == "E_IMMUTABLE"
    assert store.get_experiment("exp-x")["objective"] == "o"
    with pytest.raises(SimlabError):
        store.put_manifest({**m, "artifacts": [{"path": "p"}]})


def test_attempt_changes_once_and_is_never_deleted(store: Store):
    run = store.create_run("exp-x", "original")
    store.add_trial(run, {"trial_id": "t", "ordinal": 0, "arm_id": "a", "condition": "c", "replicate": 0, "episode": 0,
                          "seeds": {}, "params": {}})
    a = store.start_attempt(run, "t", {"trial": 1})
    store.end_attempt(a, "COMPLETED", stop="completed")
    with pytest.raises(sqlite3.IntegrityError, match="E_IMMUTABLE"):
        store.end_attempt(a, "LIMIT_REACHED")
    with pytest.raises(sqlite3.IntegrityError, match="E_IMMUTABLE"):
        with store.tx() as db:
            db.execute("DELETE FROM attempts")
    store.mark_corrupted(a, "planted")  # the one permitted later transition
    row = store.q1("SELECT status, invalid_reason FROM attempts WHERE attempt_id=?", (a,))
    assert (row["status"], row["invalid_reason"]) == ("INVALID", "corrupted_record")
    with pytest.raises(SimlabError):
        store.end_attempt(store.start_attempt(run, "t", {}), "INVALID")  # INVALID needs its reason


def test_blobs_are_content_addressed_and_verified(store: Store):
    sha = store.put_blob(b"hello")
    assert store.get_blob(sha) == b"hello" and store.put_blob(b"hello") == sha
    p = store.blob_path(sha)
    p.chmod(0o644)
    p.write_bytes(b"tampered")
    with pytest.raises(SimlabError) as e:
        store.get_blob(sha)
    assert e.value.code == "E_SEMANTIC_ASSET_HASH"
