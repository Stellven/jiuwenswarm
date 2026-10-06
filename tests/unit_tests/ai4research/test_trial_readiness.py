"""Actual local storage probes and isolated faults; no live model acceptance."""
from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import time

import pytest

from jiuwenswarm.ai4research.state import RunStore
from tests.fixtures.ai4research.trial_support import OBJECTIVE, make_trial


@pytest.fixture
def store(tmp_path):
    return RunStore(tmp_path / "database/runs.sqlite", tmp_path / "artifacts", gate_authority=object())


def database_snapshot(store):
    with sqlite3.connect(store.db_path.as_uri() + "?mode=ro", uri=True) as connection:
        schema = connection.execute("SELECT name,type,sql FROM sqlite_schema ORDER BY name").fetchall()
        rows = {name: connection.execute(f"SELECT * FROM {name}").fetchall()
                for name in ("runs", "artifacts", "events", "receipts", "decisions")}
        return schema, rows


@pytest.mark.asyncio
async def test_storage_readiness_preserves_real_mock_run_decision_and_artifacts(tmp_path):
    trial = make_trial(tmp_path)
    run = await trial.application.submit(trial.context, original_text=OBJECTIVE, client_request_id="readiness-fixture")
    accepted = await trial.finish(run["run_id"])
    assert accepted["status"] == "ACCEPTED" and accepted["mock"] is True
    before = database_snapshot(trial.application.store)
    existing = {path.relative_to(trial.application.store.artifacts_dir): path.read_bytes()
                for path in trial.application.store.artifacts_dir.rglob("*") if path.is_file()}
    report = trial.application.store.readiness()
    assert report["ready"] is True and report["reason"] == "ready"
    assert report["database"]["ready"] and report["artifacts"]["file_fsync"]
    assert report["artifacts"]["directory_fsync"] is (None if os.name == "nt" else True)
    assert "ACL" in report["security"]
    assert database_snapshot(trial.application.store) == before
    assert {path.relative_to(trial.application.store.artifacts_dir): path.read_bytes()
            for path in trial.application.store.artifacts_dir.rglob("*") if path.is_file()} == existing
    assert trial.application.project(trial.context, run["run_id"])["accepted_ref"] == accepted["accepted_ref"]
    leaked = trial.token in json.dumps(report)
    assert not leaked, "Readiness must never capture a credential"
    assert len(trial.bridge.calls) == 2


def test_storage_readiness_missing_database_is_not_recreated(store):
    store.db_path.unlink()
    report = store.readiness()
    assert report["ready"] is False and report["reason"] == "database_missing"
    assert not store.db_path.exists()
    assert not list(store.db_path.parent.iterdir())
    assert report["artifacts"]["ready"] is True


def test_storage_readiness_corrupt_database_fails_closed_without_repair(store):
    original = b"This is an isolated corrupt SQLite fixture, not a secret."
    store.db_path.write_bytes(original)
    report = store.readiness()
    assert report["ready"] is False and not report["database"]["ready"]
    assert report["reason"] in {"database_unavailable", "database_schema_invalid"}
    assert store.db_path.read_bytes() == original
    assert "SQLite" not in report["reason"]


@pytest.mark.parametrize("fault", ["revision", "missing_table", "extra_column", "missing_trigger", "changed_trigger", "view_instead_of_table"])
def test_storage_readiness_requires_existing_exact_append_only_schema(store, fault):
    with sqlite3.connect(store.db_path) as connection:
        if fault == "revision":
            connection.execute("PRAGMA user_version=3")
        elif fault == "missing_table":
            connection.execute("DROP TABLE decisions")
        elif fault == "extra_column":
            connection.execute("ALTER TABLE receipts ADD COLUMN unsupported TEXT")
        elif fault == "missing_trigger":
            connection.execute("DROP TRIGGER immutable_runs_delete")
        elif fault == "changed_trigger":
            connection.execute("DROP TRIGGER immutable_runs_delete")
            connection.execute("CREATE TRIGGER immutable_runs_delete BEFORE DELETE ON runs BEGIN SELECT 1; END")
        else:
            connection.execute("DROP TABLE decisions")
            connection.execute("CREATE VIEW decisions AS SELECT run_id,contract AS decision,pins AS receipt,NULL AS accepted_ref,created_at FROM runs")
    report = store.readiness()
    assert report["ready"] is False and report["reason"] == "database_schema_invalid"
    assert not list(store.artifacts_dir.glob(".readiness-*"))


def test_storage_readiness_readonly_database_has_no_hidden_creation(store):
    old_mode = store.db_path.stat().st_mode
    try:
        os.chmod(store.db_path, 0o444)
        report = store.readiness()
        assert report["ready"] is False and report["reason"] == "database_write_unavailable"
    finally:
        os.chmod(store.db_path, old_mode)
    assert store.readiness()["ready"] is True


def test_storage_readiness_writer_lock_is_bounded_and_recovers(store):
    before = database_snapshot(store)
    with sqlite3.connect(store.db_path) as blocker:
        blocker.execute("BEGIN IMMEDIATE")
        started = time.monotonic()
        report = store.readiness()
        elapsed = time.monotonic() - started
        assert report["ready"] is False and report["reason"] == "database_write_unavailable"
        assert 0.15 <= elapsed < 1.0
        assert report["artifacts"]["ready"] is True
        blocker.rollback()
    assert store.readiness()["ready"] is True
    assert database_snapshot(store) == before


def test_storage_readiness_database_rollback_exception_still_closes_and_recovers(store, monkeypatch):
    before = database_snapshot(store)
    native_connect = sqlite3.connect
    observed = []
    class RollbackFault:
        def __init__(self, connection):
            self.connection, self.closed = connection, False
        def __getattr__(self, name):
            return getattr(self.connection, name)
        def rollback(self):
            raise sqlite3.OperationalError("Isolated rollback failure")
        def close(self):
            self.connection.close()
            self.closed = True
    def connect_with_rollback_fault(*args, **kwargs):
        wrapped = RollbackFault(native_connect(*args, **kwargs))
        observed.append(wrapped)
        return wrapped
    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", connect_with_rollback_fault)
        report = store.readiness()
        assert report["ready"] is False and report["reason"] == "database_cleanup_failed"
    assert observed and all(connection.closed for connection in observed)
    assert database_snapshot(store) == before
    assert store.readiness()["ready"] is True


def test_storage_readiness_missing_artifact_directory_is_not_recreated(store):
    store.artifacts_dir.rmdir()
    report = store.readiness()
    assert report["ready"] is False and report["reason"] == "artifact_directory_missing"
    assert report["database"]["ready"] is True
    assert not store.artifacts_dir.exists()


def test_storage_readiness_actual_unwritable_artifact_directory_and_recovery(store):
    if os.name == "nt":
        who = subprocess.run(["whoami.exe", "/user", "/fo", "csv", "/nh"], capture_output=True, check=True)
        sid = next(csv.reader(io.StringIO(who.stdout.decode())))[1]
        deny = subprocess.run(["icacls.exe", str(store.artifacts_dir), "/deny", "*" + sid + ":(W)"], capture_output=True)
        assert deny.returncode == 0, "Required actual isolated ACL fault could not be established"
        try:
            report = store.readiness()
            assert report["ready"] is False and not report["artifacts"]["ready"]
        finally:
            restored = subprocess.run(["icacls.exe", str(store.artifacts_dir), "/remove:d", "*" + sid], capture_output=True)
            assert restored.returncode == 0, "Isolated directory ACL fault could not be removed"
    else:
        old_mode = store.artifacts_dir.stat().st_mode
        try:
            store.artifacts_dir.chmod(0o555)
            report = store.readiness()
            assert report["ready"] is False and report["reason"] == "artifact_directory_unwritable"
        finally:
            store.artifacts_dir.chmod(old_mode)
    assert not list(store.artifacts_dir.glob(".readiness-*"))
    assert store.readiness()["ready"] is True


def redirect_directory(link, target):
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        assert os.name == "nt", "Required actual directory redirection could not be established"
        result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
        assert result.returncode == 0, "Required actual reparse fixture could not be established"


def remove_redirect(link, owner):
    assert link.absolute().is_relative_to(owner.absolute())
    info = link.lstat()
    if stat.S_ISLNK(info.st_mode):
        link.unlink()
    else:
        assert getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        link.rmdir()


@pytest.mark.parametrize("custody", ["database_parent", "artifact_root"])
def test_storage_readiness_actual_custody_redirect_is_refused(store, tmp_path, custody):
    source = store.db_path.parent if custody == "database_parent" else store.artifacts_dir
    saved = source.with_name(source.name + "-saved")
    target = tmp_path / "foreign"
    target.mkdir()
    sentinel = target / "untouched.txt"
    sentinel.write_bytes(b"Readiness must not modify this foreign fixture.")
    source.rename(saved)
    redirect_directory(source, target)
    try:
        report = store.readiness()
        assert report["ready"] is False
        assert report["reason"] == ("database_path_redirected" if custody == "database_parent" else "artifact_path_redirected")
        assert list(target.iterdir()) == [sentinel]
        assert sentinel.read_bytes() == b"Readiness must not modify this foreign fixture."
    finally:
        remove_redirect(source, tmp_path)
        saved.rename(source)
    assert store.readiness()["ready"] is True


@pytest.mark.parametrize("failure", ["write", "fsync", "read"])
def test_storage_readiness_probe_exception_cleanup_and_recovery(store, monkeypatch, failure):
    with monkeypatch.context() as patch:
        if failure == "read":
            patch.setattr(os, "read", lambda descriptor, count: b"Different isolated probe bytes")
        else:
            def refused(*args, **kwargs):
                raise OSError("Injected isolated storage operation failure")
            patch.setattr(os, "write" if failure == "write" else "fsync", refused)
        report = store.readiness()
        assert report["ready"] is False and not report["artifacts"]["ready"]
        assert "Injected" not in json.dumps(report)
    assert not list(store.artifacts_dir.glob(".readiness-*"))
    assert store.readiness()["ready"] is True


def test_storage_readiness_never_deletes_a_substituted_probe(store, monkeypatch):
    native_fsync = os.fsync
    changed = {"attempted": False, "replaced": False, "blocked": False, "probe": None}
    moved = store.artifacts_dir / "moved-open-probe.tmp"
    def substitute(descriptor):
        if not changed["attempted"] and stat.S_ISREG(os.fstat(descriptor).st_mode):
            changed["attempted"] = True
            probe = next(store.artifacts_dir.glob(".readiness-*"))
            changed["probe"] = probe
            try:
                probe.rename(moved)
            except PermissionError:
                changed["blocked"] = True
            else:
                probe.write_bytes(b"Substituted file must survive cleanup.")
                changed["replaced"] = True
        native_fsync(descriptor)
    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", substitute)
        report = store.readiness()
    assert changed["attempted"]
    if changed["replaced"]:
        assert report["ready"] is False and report["reason"] == "artifact_identity_changed"
        assert changed["probe"].read_bytes() == b"Substituted file must survive cleanup."
        if os.name == "nt":
            assert not moved.exists(), "Windows close must delete only the original opened object"
        else:
            assert moved.read_bytes() == b"AI4Research readiness r2\n"
    else:
        assert os.name == "nt" and changed["blocked"]
        assert report["ready"] is True, "OS sharing prevented namespace substitution"
        assert not changed["probe"].exists()
