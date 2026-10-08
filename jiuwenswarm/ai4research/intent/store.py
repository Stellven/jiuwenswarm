"""Host-owned immutable evidence and SQLite release authority (M1-IF-INTENT@r1)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class StoreError(RuntimeError):
    """Stable errors; never include raw filesystem or credential contents."""


def encode_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


class IntentStore:
    REQUIRED_ACCEPTANCE_FILES = {"original.txt", "configuration.json", "compiler.prompt.txt", "verifier.prompt.txt", "candidate.raw.json", "compiler.json", "assessment.raw.json", "verifier.json", "decision.json"}
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.artifact_root = self.root / "runs"
        self.artifact_root.mkdir(exist_ok=True)
        self.database = self.root / "intent.sqlite3"
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, corrects_run_id TEXT,
                    state TEXT NOT NULL, decision TEXT, accepted_reference TEXT
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    run_id TEXT NOT NULL REFERENCES runs(run_id), name TEXT NOT NULL,
                    sha256 TEXT NOT NULL, bytes INTEGER NOT NULL,
                    PRIMARY KEY (run_id, name)
                );
                CREATE TABLE IF NOT EXISTS host_profile (id INTEGER PRIMARY KEY, profile_id TEXT NOT NULL);
            """)
            db.execute("INSERT OR IGNORE INTO host_profile VALUES (1, ?)", (uuid.uuid4().hex,))

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.database, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @property
    def profile_id(self):
        with self._connect() as db:
            return db.execute("SELECT profile_id FROM host_profile WHERE id=1").fetchone()[0]

    def recover_interrupted(self):
        """Called once by the process owner; no replay of uncertain effects."""
        with self._connect() as db:
            db.execute("UPDATE runs SET state='PAUSED' WHERE state IN ('CAPTURED','COMPILING','VERIFYING')")

    def claim_runtime(self):
        """Nonblocking process ownership: status reads do not claim or mutate."""
        handle = (self.root / "runtime.lock").open("a+b")
        try:
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except OSError:
            handle.close()
            raise StoreError("RUNTIME_BUSY") from None

    @staticmethod
    def _validate_id(run_id):
        if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{32}", run_id):
            raise StoreError("INVALID_RUN_ID")

    def create(self, run_id, text, owner_id, profile_id, workspace_id, policy, pins, corrects_run_id=None):
        self._validate_id(run_id)
        if not all(isinstance(v, str) and v.strip() for v in (owner_id, profile_id, workspace_id)):
            raise StoreError("IDENTITY_REQUIRED")
        if corrects_run_id:
            old = self.read(corrects_run_id, owner_id)
            if old["state"] not in {"HALTED", "PAUSED"}:
                raise StoreError("CORRECTION_REQUIRES_HALTED_RUN")
        directory = self.artifact_root / run_id
        directory.mkdir(exist_ok=False)
        with self._connect() as db:
            db.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, 'CAPTURED', NULL, NULL)",
                       (run_id, owner_id, profile_id, workspace_id, datetime.now(timezone.utc).isoformat(), corrects_run_id))
        self.write(run_id, "original.txt", text)
        self.write(run_id, "configuration.json", encode_json({
            "agreement": "M1-IF-INTENT@r1", "policy": policy, "pins": pins,
            "owner_id": owner_id, "profile_id": profile_id, "workspace_id": workspace_id,
        }))

    def write(self, run_id, name, content):
        self._validate_id(run_id)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,99}", name):
            raise StoreError("INVALID_ARTIFACT_NAME")
        data = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        path = self.artifact_root / run_id / name
        with self._connect() as db:
            row = db.execute("SELECT state FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None or row[0] in {"ACCEPTED", "HALTED", "PAUSED"}:
                raise StoreError("IMMUTABLE_RUN")
        # Never rewrite evidence, including an orphan from a failed transaction.
        with path.open("xb") as artifact:
            artifact.write(data)
            artifact.flush()
            os.fsync(artifact.fileno())
        if os.name != "nt":
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        digest = hashlib.sha256(data).hexdigest()
        with self._connect() as db:
            db.execute("INSERT INTO artifacts VALUES (?, ?, ?, ?)", (run_id, name, digest, len(data)))
        return {"name": name, "sha256": digest, "bytes": len(data)}

    def state(self, run_id, state):
        if state not in {"COMPILING", "VERIFYING"}:
            raise StoreError("INVALID_STATE")
        with self._connect() as db:
            result = db.execute("UPDATE runs SET state=? WHERE run_id=? AND state IN ('CAPTURED','COMPILING','VERIFYING')", (state, run_id))
            if result.rowcount != 1:
                raise StoreError("IMMUTABLE_RUN")

    def _artifacts(self, db, run_id):
        artifacts = [dict(row) for row in db.execute("SELECT name,sha256,bytes FROM artifacts WHERE run_id=? ORDER BY name", (run_id,))]
        for artifact in artifacts:
            try:
                data = (self.artifact_root / run_id / artifact["name"]).read_bytes()
            except OSError:
                raise StoreError("EVIDENCE_INTEGRITY_FAILED") from None
            if len(data) != artifact["bytes"] or hashlib.sha256(data).hexdigest() != artifact["sha256"]:
                raise StoreError("EVIDENCE_INTEGRITY_FAILED")
        return artifacts

    def complete(self, run_id, decision, candidate=None):
        """Commit decision/reference atomically only after essential files exist."""
        accepted = decision.verdict in {"PASS", "PASS_WITH_KNOWN_LIMITATIONS"} and decision.accepted
        self.write(run_id, "decision.json", encode_json(decision.model_dump(mode="json")))
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            artifacts = self._artifacts(db, run_id)
            names = {a["name"] for a in artifacts}
            reference = None
            if accepted:
                if not self.REQUIRED_ACCEPTANCE_FILES <= names or candidate is None:
                    raise StoreError("RELEASE_EVIDENCE_MISSING")
                exact_candidate = json.loads((self.artifact_root / run_id / "candidate.raw.json").read_text(encoding="utf-8"))
                original = (self.artifact_root / run_id / "original.txt").read_bytes()
                if (candidate.model_dump(mode="json") != exact_candidate or candidate.run_id != run_id or
                        candidate.input_sha256 != hashlib.sha256(original).hexdigest()):
                    raise StoreError("RELEASE_SUBJECT_MISMATCH")
                reference = {"agreement": "M1-IF-INTENT@r1", "run_id": run_id,
                             "candidate": next(a for a in artifacts if a["name"] == "candidate.raw.json"),
                             "input": next(a for a in artifacts if a["name"] == "original.txt"),
                             "intent": candidate.model_dump(mode="json")}
            result = db.execute("UPDATE runs SET state=?, decision=?, accepted_reference=? WHERE run_id=? AND state IN ('CAPTURED','COMPILING','VERIFYING')",
                                ("ACCEPTED" if accepted else "HALTED", encode_json(decision.model_dump(mode="json")), encode_json(reference) if reference else None, run_id))
            if result.rowcount != 1:
                raise StoreError("IMMUTABLE_RUN")
        # Return only after SQLite's context manager has committed.
        return reference

    def read(self, run_id, owner_id):
        self._validate_id(run_id)
        with self._connect() as db:
            row = db.execute("SELECT * FROM runs WHERE run_id=? AND owner_id=?", (run_id, owner_id)).fetchone()
            if row is None:
                raise StoreError("RUN_NOT_FOUND")
            result = dict(row)
            artifacts = self._artifacts(db, run_id)
            if result["state"] == "ACCEPTED" and not self.REQUIRED_ACCEPTANCE_FILES <= {a["name"] for a in artifacts}:
                raise StoreError("EVIDENCE_INTEGRITY_FAILED")
        result["decision"] = json.loads(result["decision"]) if result["decision"] else None
        result["accepted_reference"] = json.loads(result["accepted_reference"]) if result["accepted_reference"] else None
        result["artifacts"] = artifacts
        return result
