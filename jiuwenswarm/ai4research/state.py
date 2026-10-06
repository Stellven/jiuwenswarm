"""Durable, append-only custody for the text-only two-CC trial.

The authenticated host owns this object. Wire clients never receive it or the
gate capability. SQLite is authoritative; files and views cannot grant release.
"""
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import stat
import time
import uuid
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from .common import GovernanceError, canonical_json, hash_json, sha256_bytes, utc_now

INTERFACE_REVISION = "M0-IF-005@r2"
_REF_FIELDS = {"interface_revision", "artifact_id", "run_id", "type", "schema_revision", "sha256", "locator"}
_TERMINAL = {"ACCEPTED", "FAILED", "ENVIRONMENT_BLOCKED", "INCONCLUSIVE", "CANCELLED", "PAUSED"}
_TRANSITIONS = {
    "QUALIFIED": {"COMPILING", "FAILED", "ENVIRONMENT_BLOCKED", "CANCELLED", "PAUSED"},
    "COMPILING": {"CHECKING", "FAILED", "ENVIRONMENT_BLOCKED", "CANCELLED", "PAUSED"},
    "CHECKING": {"VERIFYING", "FAILED", "ENVIRONMENT_BLOCKED", "INCONCLUSIVE", "CANCELLED", "PAUSED"},
    "VERIFYING": {"DECIDING", "FAILED", "ENVIRONMENT_BLOCKED", "INCONCLUSIVE", "CANCELLED", "PAUSED"},
    "DECIDING": {"FAILED", "ENVIRONMENT_BLOCKED", "INCONCLUSIVE", "CANCELLED", "PAUSED"},
}
_VERDICTS = {"PASS", "PASS_WITH_KNOWN_LIMITATIONS", "FAIL", "INCONCLUSIVE", "ENVIRONMENT_BLOCKED"}
_OUTCOMES = {"SUCCEEDED", "FAILED", "ENVIRONMENT_BLOCKED", "TIMED_OUT", "CANCELLED", "INTERRUPTED", "DELIVERY_UNKNOWN", "INCONCLUSIVE"}
_SECRET_KEYS = {"api_key", "access_token", "password", "private_key", "control_token", "session_token"}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GovernanceError("invalid_input", f"{field} must be a nonempty string")
    return value


def _json(value: Any) -> str:
    """Validate finite JSON and reject known credential-bearing fields."""
    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, val in item.items():
                if str(key).lower() in _SECRET_KEYS and val not in (None, ""):
                    raise GovernanceError("policy_denied", "Credentials cannot enter trial evidence")
                visit(val)
        elif isinstance(item, (list, tuple)):
            for val in item:
                visit(val)
    visit(value)
    try:
        return canonical_json(value).decode("utf-8")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise GovernanceError("invalid_input", "Evidence must be finite UTF-8 JSON") from exc


class RunStore:
    """Protected host store. Every public run read/write checks its owner.

    ``gate_authority`` is an identity capability, never a serialized token.
    ``recover_interrupted`` is an explicit startup operation, not a constructor
    side effect; reopening for inspection must not interrupt a live service.
    """

    def __init__(self, db_path: str | Path, artifacts_dir: str | Path, *, gate_authority: object,
                 busy_timeout_seconds: float = 1.0, fault_injector: Callable[[str], None] | None = None,
                 forbidden_values: Sequence[bytes] = ()):
        if gate_authority is None or isinstance(gate_authority, (str, bytes, int, float, bool)):
            raise GovernanceError("invalid_input", "A protected host capability object is required")
        if not math.isfinite(busy_timeout_seconds) or busy_timeout_seconds < 0:
            raise GovernanceError("invalid_input", "Invalid SQLite timeout")
        self.db_path = Path(db_path).absolute()
        supplied_root = Path(artifacts_dir).absolute()
        if supplied_root.is_symlink() or self.db_path.is_symlink():
            raise GovernanceError("policy_denied", "Store paths cannot be symlinks")
        self.artifacts_dir = supplied_root.resolve()
        self._authority = gate_authority
        self._timeout = busy_timeout_seconds
        self._fault_injector = fault_injector
        self._forbidden_values = tuple(value for value in forbidden_values if value)
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.artifacts_dir.mkdir(parents=True, exist_ok=True)
            with self._connection() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, 2):
                    raise GovernanceError("incompatible_revision", "Unknown trial state schema")
                conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs(
                  run_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                  request_id TEXT NOT NULL, fingerprint TEXT NOT NULL, original_text TEXT NOT NULL,
                  configuration TEXT NOT NULL, contract TEXT NOT NULL, pins TEXT NOT NULL,
                  mode TEXT NOT NULL, predecessor TEXT, original_ref TEXT NOT NULL, created_at TEXT NOT NULL,
                  UNIQUE(user_id, workspace_id, request_id));
                CREATE TABLE IF NOT EXISTS artifacts(
                  artifact_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
                  ref TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(
                  seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(run_id),
                  event_type TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS receipts(
                  run_id TEXT NOT NULL REFERENCES runs(run_id), operation TEXT NOT NULL,
                  identity TEXT NOT NULL, fingerprint TEXT NOT NULL, result TEXT NOT NULL,
                  PRIMARY KEY(run_id, operation, identity));
                CREATE TABLE IF NOT EXISTS decisions(
                  run_id TEXT PRIMARY KEY REFERENCES runs(run_id), decision TEXT NOT NULL,
                  receipt TEXT NOT NULL, accepted_ref TEXT, created_at TEXT NOT NULL);
                PRAGMA user_version=2;
                """)
                for table in ("runs", "artifacts", "events", "receipts", "decisions"):
                    for operation in ("UPDATE", "DELETE"):
                        conn.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation.lower()} "
                                     f"BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'append-only trial custody'); END")
        except (sqlite3.Error, OSError) as exc:
            raise GovernanceError("persistence_failed", "Trial storage initialization failed") from exc

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path, timeout=self._timeout)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=FULL")
            yield conn
        finally:
            conn.close()

    def readiness(self) -> dict[str, Any]:
        """Probe existing storage capabilities without changing application data.

        The bounded SQLite write is rolled back. The private artifact probe is
        removed only when it still names the opened file; Windows delete-on-close
        removes the exact opened object even if its pathname is substituted.
        This reports storage operations, not OS ACL or runtime isolation proof.
        """
        timeout = min(self._timeout, 0.25)
        database = {"ready": False, "reason": "database_unavailable", "timeout_seconds": timeout}
        artifacts = {"ready": False, "reason": "artifact_directory_unavailable",
                     "file_fsync": False, "directory_fsync": None if os.name == "nt" else False}

        def identity(info):
            return info.st_dev, info.st_ino

        def checked_path(path, kind, missing, redirected):
            try:
                for component in reversed((path, *path.parents)):
                    info = component.lstat()
                    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                        raise GovernanceError(redirected, "Storage custody is redirected.")
                    if component != path and not stat.S_ISDIR(info.st_mode):
                        raise GovernanceError(redirected, "Storage ancestor is not a directory.")
                if not (stat.S_ISREG(info.st_mode) if kind == "file" else stat.S_ISDIR(info.st_mode)):
                    raise GovernanceError(redirected, "Storage custody has an unsupported type.")
                return info
            except FileNotFoundError:
                raise GovernanceError(missing, "Required storage custody is missing.") from None

        connection = None
        phase = "database_unavailable"
        try:
            before = checked_path(self.db_path, "file", "database_missing", "database_path_redirected")
            if not before.st_mode & 0o222:
                raise GovernanceError("database_write_unavailable", "Database is read-only.")
            for suffix in ("-wal", "-shm", "-journal"):
                sidecar = Path(str(self.db_path) + suffix)
                if sidecar.exists() or sidecar.is_symlink():
                    checked_path(sidecar, "file", "database_unavailable", "database_path_redirected")
            # mode=rw refuses a missing database instead of recreating it.
            connection = sqlite3.connect(self.db_path.as_uri() + "?mode=rw", uri=True, timeout=timeout)
            deadline = time.monotonic() + 0.5
            connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            if identity(checked_path(self.db_path, "file", "database_missing", "database_path_redirected")) != identity(before):
                raise GovernanceError("database_identity_changed", "Database identity changed.")
            phase = "database_schema_invalid"
            if connection.execute("PRAGMA user_version").fetchone()[0] != 2:
                raise GovernanceError(phase, "Database schema revision is unsupported.")
            columns = {
                "runs": ("run_id", "user_id", "workspace_id", "request_id", "fingerprint", "original_text", "configuration", "contract", "pins", "mode", "predecessor", "original_ref", "created_at"),
                "artifacts": ("artifact_id", "run_id", "ref", "metadata", "created_at"),
                "events": ("seq", "run_id", "event_type", "payload", "created_at"),
                "receipts": ("run_id", "operation", "identity", "fingerprint", "result"),
                "decisions": ("run_id", "decision", "receipt", "accepted_ref", "created_at"),
            }
            schema = {row[0]: (row[1], row[2]) for row in connection.execute("SELECT name,type,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%'")}
            expected_triggers = {f"immutable_{table}_{operation.lower()}" for table in columns for operation in ("UPDATE", "DELETE")}
            if set(schema) != set(columns) | expected_triggers:
                raise GovernanceError(phase, "Required append-only schema is incomplete.")
            for table, expected_columns in columns.items():
                observed = connection.execute(f"PRAGMA table_info({table})").fetchall()
                if schema[table][0] != "table" or tuple(row[1] for row in observed) != expected_columns:
                    raise GovernanceError(phase, "Required table contract is incompatible.")
                expected_pk = ("run_id", "operation", "identity") if table == "receipts" else (("seq",) if table == "events" else (expected_columns[0],))
                if tuple(row[1] for row in sorted(observed, key=lambda row: row[5]) if row[5]) != expected_pk:
                    raise GovernanceError(phase, "Required primary key is incompatible.")
                # Read only a constant; no original text, evidence or secret is captured.
                connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
                for operation in ("UPDATE", "DELETE"):
                    name = f"immutable_{table}_{operation.lower()}"
                    expected_sql = f"CREATE TRIGGER {name} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'append-only trial custody'); END"
                    observed_sql = re.sub(r"\s+", " ", schema[name][1] or "").strip()
                    if schema[name][0] != "trigger" or observed_sql.lower() != expected_sql.lower():
                        raise GovernanceError(phase, "Required append-only protection is incompatible.")
            phase = "database_unavailable"
            if connection.execute("PRAGMA quick_check(1)").fetchone()[0] != "ok":
                raise GovernanceError(phase, "Database integrity probe failed.")
            phase = "database_write_unavailable"
            connection.execute("BEGIN IMMEDIATE")
            name = "readiness_" + uuid.uuid4().hex
            connection.execute(f"CREATE TABLE {name}(probe INTEGER NOT NULL)")
            connection.execute(f"INSERT INTO {name} VALUES(1)")
            if connection.execute(f"SELECT probe FROM {name}").fetchone()[0] != 1:
                raise GovernanceError(phase, "Database write probe could not be read.")
            connection.rollback()
            if connection.execute("SELECT 1 FROM sqlite_schema WHERE name=?", (name,)).fetchone() is not None:
                raise GovernanceError(phase, "Database probe rollback failed.")
            if identity(checked_path(self.db_path, "file", "database_missing", "database_path_redirected")) != identity(before):
                raise GovernanceError("database_identity_changed", "Database identity changed.")
            database.update(ready=True, reason="ready")
        except GovernanceError as error:
            database["reason"] = error.code
        except (sqlite3.Error, OSError, ValueError, IndexError, TypeError):
            database["reason"] = phase
        finally:
            if connection is not None:
                try:
                    connection.rollback()
                except sqlite3.Error:
                    database.update(ready=False, reason="database_cleanup_failed")
                finally:
                    try:
                        connection.close()
                    except sqlite3.Error:
                        database.update(ready=False, reason="database_cleanup_failed")

        probe_fd = directory_fd = None
        opened_identity = None
        name = ".readiness-" + uuid.uuid4().hex + ".tmp"
        probe = self.artifacts_dir / name
        try:
            directory = checked_path(self.artifacts_dir, "directory", "artifact_directory_missing", "artifact_path_redirected")
            if os.name != "nt" and not directory.st_mode & 0o222:
                raise GovernanceError("artifact_directory_unwritable", "Artifact directory is read-only.")
            flags = os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
            if os.name == "nt":
                # O_TEMPORARY uses delete-on-close for the opened object, not a
                # later pathname unlink that could delete a substituted file.
                flags |= os.O_TEMPORARY
                probe_fd = os.open(probe, flags, 0o600)
            else:
                directory_fd = os.open(self.artifacts_dir, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
                if identity(os.fstat(directory_fd)) != identity(directory):
                    raise GovernanceError("artifact_identity_changed", "Artifact directory identity changed.")
                probe_fd = os.open(name, flags, 0o600, dir_fd=directory_fd)
            opened = os.fstat(probe_fd)
            opened_identity = identity(opened)
            if not stat.S_ISREG(opened.st_mode) or not opened.st_ino:
                raise GovernanceError("artifact_identity_unavailable", "Artifact probe identity is unavailable.")
            if identity(checked_path(probe, "file", "artifact_probe_missing", "artifact_path_redirected")) != opened_identity:
                raise GovernanceError("artifact_identity_changed", "Artifact probe identity changed.")
            payload = b"AI4Research readiness r2\n"
            if os.write(probe_fd, payload) != len(payload):
                raise GovernanceError("artifact_probe_failed", "Artifact probe write was incomplete.")
            os.fsync(probe_fd)
            artifacts["file_fsync"] = True
            os.lseek(probe_fd, 0, os.SEEK_SET)
            if os.read(probe_fd, len(payload) + 1) != payload:
                raise GovernanceError("artifact_probe_failed", "Artifact probe read differed.")
            if identity(checked_path(self.artifacts_dir, "directory", "artifact_directory_missing", "artifact_path_redirected")) != identity(directory) or identity(checked_path(probe, "file", "artifact_probe_missing", "artifact_path_redirected")) != opened_identity:
                raise GovernanceError("artifact_identity_changed", "Artifact custody changed during probe.")
            if directory_fd is not None:
                os.fsync(directory_fd)
                artifacts["directory_fsync"] = True
            artifacts.update(ready=True, reason="ready")
        except GovernanceError as error:
            artifacts["reason"] = error.code
        except (OSError, ValueError):
            artifacts["reason"] = "artifact_probe_failed"
        finally:
            try:
                if os.name != "nt" and probe_fd is not None and directory_fd is not None and opened_identity is not None:
                    try:
                        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                    except FileNotFoundError:
                        artifacts.update(ready=False, reason="artifact_identity_changed")
                    else:
                        if identity(current) == opened_identity and stat.S_ISREG(current.st_mode):
                            os.unlink(name, dir_fd=directory_fd)
                            os.fsync(directory_fd)
                        else:
                            artifacts.update(ready=False, reason="artifact_identity_changed")
            except OSError:
                artifacts.update(ready=False, reason="artifact_cleanup_failed")
            finally:
                for descriptor in (probe_fd, directory_fd):
                    if descriptor is not None:
                        try:
                            os.close(descriptor)
                        except OSError:
                            artifacts.update(ready=False, reason="artifact_cleanup_failed")
        ready = database["ready"] and artifacts["ready"]
        return {"ready": ready, "reason": "ready" if ready else database["reason"] if not database["ready"] else artifacts["reason"],
                "database": database, "artifacts": artifacts,
                "security": "Storage capability probe only; ACL and runtime isolation readiness are separate."}

    @contextmanager
    def _transaction(self):
        try:
            with self._connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    yield conn
                    self._fault("before_transaction_commit")
                    conn.commit()
                except BaseException:
                    conn.rollback()
                    raise
        except (sqlite3.Error, OSError) as exc:
            raise GovernanceError("persistence_failed", "Required trial persistence failed") from exc

    def _fault(self, stage: str) -> None:
        if self._fault_injector is not None:
            self._fault_injector(stage)

    def _row(self, conn, run_id: str, caller_id: str | None):
        row = conn.execute("SELECT * FROM runs WHERE run_id=?", (_text(run_id, "run_id"),)).fetchone()
        if row is None or caller_id != row["user_id"]:
            raise GovernanceError("policy_denied", "Run is not available to this caller")
        return row

    def _event(self, conn, run_id: str, event_type: str, payload: Mapping) -> int:
        if not isinstance(payload, Mapping):
            raise GovernanceError("invalid_input", "Event observations must be structured")
        encoded = _json(payload)
        self._check_secrets(encoded.encode("utf-8"))
        return conn.execute("INSERT INTO events(run_id,event_type,payload,created_at) VALUES(?,?,?,?)",
                            (run_id, event_type, encoded, utc_now())).lastrowid

    @staticmethod
    def _events(conn, run_id: str) -> list[dict]:
        return [{"sequence": r["seq"], "run_id": run_id, "event_type": r["event_type"],
                 "payload": json.loads(r["payload"]), "timestamp": r["created_at"]}
                for r in conn.execute("SELECT * FROM events WHERE run_id=? ORDER BY seq", (run_id,))]

    @staticmethod
    def _status(conn, run_id: str) -> str:
        row = conn.execute("SELECT payload FROM events WHERE run_id=? AND event_type='status' ORDER BY seq DESC LIMIT 1",
                           (run_id,)).fetchone()
        return json.loads(row[0])["status"] if row else "QUALIFIED"

    def _receipt(self, conn, run_id: str, operation: str, identity: str, fingerprint: str):
        row = conn.execute("SELECT * FROM receipts WHERE run_id=? AND operation=? AND identity=?",
                           (run_id, operation, identity)).fetchone()
        if row:
            if row["fingerprint"] != fingerprint:
                raise GovernanceError("invalid_input", "Idempotency identity cannot name changed evidence")
            return json.loads(row["result"])
        return None

    @staticmethod
    def _save_receipt(conn, run_id, operation, identity, fingerprint, result):
        conn.execute("INSERT INTO receipts VALUES(?,?,?,?,?)", (run_id, operation, identity, fingerprint, _json(result)))

    def _check_secrets(self, content: bytes) -> None:
        if any(value in content for value in self._forbidden_values):
            raise GovernanceError("policy_denied", "Protected credential content cannot be captured")

    def _artifact_path(self, locator: str) -> Path:
        if not isinstance(locator, str) or not re.fullmatch(r"objects/[0-9a-f]{64}/[0-9a-f]{32}\.bin", locator):
            raise GovernanceError("invalid_input", "Invalid artifact locator")
        path = self.artifacts_dir / locator
        for item in (path, path.parent, path.parent.parent):
            if item.is_symlink():
                raise GovernanceError("policy_denied", "Artifact symlinks are forbidden")
        if not path.resolve().is_relative_to(self.artifacts_dir):
            raise GovernanceError("policy_denied", "Artifact locator escapes custody")
        return path

    def _write_file(self, run_id: str, content: bytes, artifact_type: str, schema_revision: str) -> dict:
        if not isinstance(content, bytes):
            raise GovernanceError("invalid_input", "Artifact content must be exact bytes")
        self._check_secrets(content)
        artifact_id = uuid.uuid4().hex
        locator = f"objects/{sha256_bytes(run_id.encode('utf-8'))}/{artifact_id}.bin"
        path = self._artifact_path(locator)
        self._fault("before_artifact_persist")
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        self._fault("after_artifact_persist")
        return {"interface_revision": INTERFACE_REVISION, "artifact_id": artifact_id, "run_id": run_id,
                "type": _text(artifact_type, "artifact_type"), "schema_revision": _text(schema_revision, "schema_revision"),
                "sha256": sha256_bytes(content), "locator": locator}

    @staticmethod
    def _save_artifact(conn, ref: dict, metadata: dict):
        conn.execute("INSERT INTO artifacts VALUES(?,?,?,?,?)",
                     (ref["artifact_id"], ref["run_id"], _json(ref), _json(metadata), utc_now()))

    def create_run(self, *, user_id: str, workspace_id: str, client_request_id: str, original_text: str,
                   configuration: Mapping, contract: Mapping, pins: Mapping,
                   run_id: str | None = None, mode: str = "web", predecessor_run_id: str | None = None,
                   caller_id: str | None = None) -> dict:
        for name, value in (("user_id", user_id), ("workspace_id", workspace_id),
                            ("client_request_id", client_request_id), ("original_text", original_text)):
            _text(value, name)
        caller_id = user_id if caller_id is None else caller_id
        if caller_id != user_id or mode not in {"web", "headless", "mock"}:
            raise GovernanceError("policy_denied", "Unsupported submission identity or mode")
        if not all(isinstance(v, Mapping) and v for v in (configuration, contract, pins)) or len(pins) != 2:
            raise GovernanceError("invalid_input", "Frozen configuration, contract and two CC pins are required")
        payload = {"original_text": original_text, "configuration": configuration, "contract": contract,
                   "pins": pins, "mode": mode, "predecessor_run_id": predecessor_run_id}
        serialized = _json(payload)
        self._check_secrets(serialized.encode("utf-8"))
        fingerprint = sha256_bytes(serialized.encode("utf-8"))
        with self._transaction() as conn:
            old = conn.execute("SELECT * FROM runs WHERE user_id=? AND workspace_id=? AND request_id=?",
                               (user_id, workspace_id, client_request_id)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise GovernanceError("invalid_input", "Client request identity cannot be reused for changed input")
                result = self._snapshot(conn, old["run_id"], caller_id)
            else:
                if predecessor_run_id:
                    previous = self._row(conn, predecessor_run_id, caller_id)
                    if previous["workspace_id"] != workspace_id:
                        raise GovernanceError("policy_denied", "Correction must retain workspace attribution")
                run_id = uuid.uuid4().hex if run_id is None else _text(run_id, "run_id")
                ref = self._write_file(run_id, original_text.encode("utf-8"), "original_request", "r2")
                conn.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (run_id, user_id, workspace_id, client_request_id, fingerprint, original_text,
                              _json(configuration), _json(contract), _json(pins), mode, predecessor_run_id, _json(ref), utc_now()))
                self._save_artifact(conn, ref, {"origin": "original", "audiences": ["local", "verifier"],
                                               "node_id": "intent", "attempt_id": None, "invocation_id": None})
                self._event(conn, run_id, "status", {"status": "QUALIFIED", "reason": "Original text and frozen context captured"})
                result = self._snapshot(conn, run_id, caller_id)
        return result

    def put_artifact(self, run_id: str, content: bytes, *, artifact_type: str, schema_revision: str = "r2",
                     node_id: str = "intent", attempt_id: str | None = None, invocation_id: str | None = None,
                     origin: str = "candidate", audiences: Sequence[str] = ("local",),
                     caller_id: str | None = None, idempotency_key: str | None = None) -> dict:
        _text(artifact_type, "artifact_type")
        _text(schema_revision, "schema_revision")
        if not isinstance(content, bytes) or origin not in {"original", "candidate", "assessment", "checks", "observed"}:
            raise GovernanceError("invalid_input", "Invalid immutable artifact content/origin")
        if node_id != "intent" or not audiences or not set(audiences) <= {"local", "verifier"}:
            raise GovernanceError("policy_denied", "Artifact exceeds the trial node/audience")
        metadata = {"origin": origin, "node_id": node_id, "attempt_id": attempt_id,
                    "invocation_id": invocation_id, "audiences": sorted(set(audiences))}
        fingerprint = hash_json({"sha256": sha256_bytes(content), "type": artifact_type,
                                 "schema_revision": schema_revision, **metadata})
        with self._transaction() as conn:
            self._row(conn, run_id, caller_id)
            if attempt_id:
                attempt = self._attempt(conn, run_id, attempt_id)
                if invocation_id and invocation_id != attempt["invocation_id"]:
                    raise GovernanceError("invalid_input", "Artifact invocation differs from its attempt")
                metadata["invocation_id"] = attempt["invocation_id"]
            old = self._receipt(conn, run_id, "artifact", idempotency_key, fingerprint) if idempotency_key else None
            if old:
                self._read_ref(conn, old, caller_id, "local")
                return old
            ref = self._write_file(run_id, content, artifact_type, schema_revision)
            self._save_artifact(conn, ref, metadata)
            self._event(conn, run_id, "artifact", {"reference": ref, **metadata})
            if idempotency_key:
                self._save_receipt(conn, run_id, "artifact", idempotency_key, fingerprint, ref)
        return ref

    def _read_ref(self, conn, ref: Mapping, caller_id: str | None, audience: str) -> bytes:
        if not isinstance(ref, Mapping) or set(ref) != _REF_FIELDS or ref.get("interface_revision") != INTERFACE_REVISION:
            raise GovernanceError("incompatible_revision", "Invalid trial artifact reference")
        self._row(conn, ref["run_id"], caller_id)
        row = conn.execute("SELECT * FROM artifacts WHERE artifact_id=? AND run_id=?",
                           (ref["artifact_id"], ref["run_id"])).fetchone()
        if not row or dict(ref) != json.loads(row["ref"]):
            raise GovernanceError("invalid_input", "Artifact reference is not its stored exact identity")
        if audience not in json.loads(row["metadata"])["audiences"]:
            raise GovernanceError("policy_denied", "Artifact is unavailable to this audience")
        try:
            path = self._artifact_path(ref["locator"])
            with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)), "rb") as stream:
                content = stream.read()
        except OSError as exc:
            raise GovernanceError("persistence_failed", "Required artifact bytes are unavailable") from exc
        if sha256_bytes(content) != ref["sha256"]:
            raise GovernanceError("invalid_input", "Artifact bytes do not match the stored identity")
        return content

    def get_artifact(self, ref: Mapping, *, caller_id: str, audience: str = "local") -> bytes:
        try:
            with self._connection() as conn:
                return self._read_ref(conn, ref, caller_id, audience)
        except sqlite3.Error as exc:
            raise GovernanceError("persistence_failed", "Artifact custody query failed") from exc

    def _attempt(self, conn, run_id: str, attempt_id: str) -> dict:
        for event in self._events(conn, run_id):
            if event["event_type"] == "attempt_started" and event["payload"]["attempt_id"] == attempt_id:
                return event["payload"]
        raise GovernanceError("invalid_input", "Attempt is not registered under this run")

    def _attempts(self, conn, run_id: str) -> list[dict]:
        attempts = {}
        for event in self._events(conn, run_id):
            if event["event_type"] == "attempt_started":
                attempts[event["payload"]["attempt_id"]] = dict(event["payload"], outcome="RUNNING")
            elif event["event_type"] == "attempt_finished":
                attempts[event["payload"]["attempt_id"]].update(event["payload"])
        return list(attempts.values())

    def begin_attempt(self, run_id: str, role: str, *, attempt_id: str | None = None,
                      invocation_id: str | None = None, caller_id: str) -> dict:
        if role not in {"compiler", "verifier"}:
            raise GovernanceError("invalid_input", "The trial has only compiler and verifier roles")
        with self._transaction() as conn:
            self._row(conn, run_id, caller_id)
            if self._status(conn, run_id) in _TERMINAL:
                raise GovernanceError("policy_denied", "Terminal or paused trial cannot dispatch")
            attempts = self._attempts(conn, run_id)
            if any(a["role"] == role for a in attempts):
                raise GovernanceError("policy_denied", "Automatic trial replay or retry is forbidden")
            if role == "verifier" and not any(a["role"] == "compiler" and a["outcome"] == "SUCCEEDED" for a in attempts):
                raise GovernanceError("policy_denied", "Verifier cannot precede successful compiler capture")
            attempt = {"attempt_id": attempt_id or uuid.uuid4().hex, "invocation_id": invocation_id or uuid.uuid4().hex,
                       "role": role, "node_id": "intent", "started_at": utc_now()}
            if any(a["attempt_id"] == attempt["attempt_id"] or a["invocation_id"] == attempt["invocation_id"] for a in attempts):
                raise GovernanceError("invalid_input", "Invocation and attempt identities must remain distinct")
            self._event(conn, run_id, "attempt_started", attempt)
        return attempt

    def finish_attempt(self, run_id: str, attempt_id: str, *, outcome: str, evidence: Mapping,
                       caller_id: str) -> dict:
        _text(outcome, "outcome")
        outcome = {"SUCCESS": "SUCCEEDED", "COMPLETED": "SUCCEEDED"}.get(outcome.upper(), outcome.upper())
        if outcome not in _OUTCOMES or not isinstance(evidence, Mapping):
            raise GovernanceError("invalid_input", "Invalid attempt outcome/evidence")
        evidence = json.loads(_json(evidence))
        if outcome == "SUCCEEDED":
            duration = evidence.get("elapsed_seconds")
            if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
                raise GovernanceError("invalid_input", "Successful invocation needs observed duration")
            if type(evidence.get("model_calls")) is not int or evidence["model_calls"] != 1:
                raise GovernanceError("invalid_input", "Successful trial role needs exactly one observed model call")
            if not isinstance(evidence.get("output_ref"), Mapping):
                raise GovernanceError("invalid_input", "Successful invocation needs retained exact output")
        usage = evidence.get("usage")
        if usage is None:
            evidence["usage"] = {"tokens": None, "cost": None, "unavailable_reason": "No reliable per-call usage supplied"}
        elif isinstance(usage, Mapping):
            available = any(usage.get(k) is not None for k in ("tokens", "cost"))
            if available and (usage.get("reliable") is not True or not usage.get("source")):
                raise GovernanceError("invalid_input", "Available usage needs a reliable per-call observation source")
            if available:
                for key in ("tokens", "cost"):
                    value = usage.get(key)
                    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
                        raise GovernanceError("invalid_input", "Usage must be an observed finite nonnegative measurement")
            else:
                evidence["usage"] = dict(usage, tokens=None, cost=None,
                                          unavailable_reason=usage.get("unavailable_reason") or "No reliable per-call usage supplied")
        else:
            raise GovernanceError("invalid_input", "Usage must be structured or unavailable")
        with self._transaction() as conn:
            self._row(conn, run_id, caller_id)
            attempt = self._attempt(conn, run_id, attempt_id)
            current = next(a for a in self._attempts(conn, run_id) if a["attempt_id"] == attempt_id)
            if current["outcome"] != "RUNNING":
                raise GovernanceError("policy_denied", "Completed attempt cannot be rewritten or replayed")
            for key in ("output_ref", "prompt_ref", "observation_ref"):
                ref = evidence.get(key)
                if ref is not None:
                    if not isinstance(ref, Mapping) or ref.get("run_id") != run_id:
                        raise GovernanceError("invalid_input", "Attempt evidence belongs to another run")
                    self._read_ref(conn, ref, caller_id, "local")
                    meta = json.loads(conn.execute("SELECT metadata FROM artifacts WHERE artifact_id=?", (ref["artifact_id"],)).fetchone()[0])
                    if meta["attempt_id"] != attempt_id:
                        raise GovernanceError("invalid_input", "Attempt output/prompt must have exact producing attribution")
            result = {**attempt, "outcome": outcome, "evidence": evidence, "finished_at": utc_now()}
            self._event(conn, run_id, "attempt_finished", result)
        return result

    def record_event(self, run_id: str, event_type: str, payload: Mapping, *, caller_id: str) -> int:
        _text(event_type, "event_type")
        if event_type in {"status", "attempt_started", "attempt_finished", "decision", "accepted"}:
            raise GovernanceError("policy_denied", "Lifecycle/release events require their protected operation")
        with self._transaction() as conn:
            self._row(conn, run_id, caller_id)
            return self._event(conn, run_id, event_type, payload)

    def set_status(self, run_id: str, status: str, *, caller_id: str, reason: str = "") -> dict:
        _text(status, "status")
        status = status.upper()
        with self._transaction() as conn:
            self._row(conn, run_id, caller_id)
            current = self._status(conn, run_id)
            if status == "ACCEPTED" or status not in _TRANSITIONS.get(current, set()):
                raise GovernanceError("policy_denied", "Invalid fixed-trial lifecycle transition")
            self._event(conn, run_id, "status", {"status": status, "reason": reason})
            result = self._snapshot(conn, run_id, caller_id)
        return result

    def _snapshot(self, conn, run_id: str, caller_id: str | None) -> dict:
        row = self._row(conn, run_id, caller_id)
        result = dict(row)
        result["client_request_id"] = result.pop("request_id")
        result["predecessor_run_id"] = result.pop("predecessor")
        for key in ("configuration", "contract", "pins", "original_ref"):
            result[key] = json.loads(result[key])
        result["status"] = self._status(conn, run_id)
        result["events"] = self._events(conn, run_id)
        result["attempts"] = self._attempts(conn, run_id)
        result["artifacts"] = [json.loads(r[0]) for r in conn.execute("SELECT ref FROM artifacts WHERE run_id=? ORDER BY created_at,artifact_id", (run_id,))]
        decision = conn.execute("SELECT * FROM decisions WHERE run_id=?", (run_id,)).fetchone()
        result["decision"] = json.loads(decision["decision"]) if decision else None
        result["accepted_ref"] = json.loads(decision["accepted_ref"]) if decision and decision["accepted_ref"] else None
        if result["accepted_ref"]:
            self._read_ref(conn, result["accepted_ref"], caller_id, "local")
        return result

    def get_run(self, run_id: str, *, caller_id: str) -> dict:
        try:
            with self._connection() as conn:
                return self._snapshot(conn, run_id, caller_id)
        except sqlite3.Error as exc:
            raise GovernanceError("persistence_failed", "Authoritative trial query failed") from exc

    def list_runs(self, *, caller_id: str, workspace_id: str | None = None) -> list[dict]:
        _text(caller_id, "caller_id")
        try:
            with self._connection() as conn:
                rows = conn.execute("SELECT run_id FROM runs WHERE user_id=? AND (? IS NULL OR workspace_id=?) ORDER BY created_at",
                                    (caller_id, workspace_id, workspace_id)).fetchall()
                return [self._snapshot(conn, r[0], caller_id) for r in rows]
        except sqlite3.Error as exc:
            raise GovernanceError("persistence_failed", "Authoritative trial query failed") from exc

    def commit_decision(self, run_id: str, *, subject_ref: Mapping | None, decision: Mapping,
                        evidence_refs: Sequence[Mapping], authority: object, caller_id: str,
                        idempotency_key: str) -> dict:
        if authority is not self._authority:
            raise GovernanceError("policy_denied", "Only the protected host gate can commit release")
        _text(idempotency_key, "idempotency_key")
        if not isinstance(decision, Mapping) or decision.get("verdict") not in _VERDICTS:
            raise GovernanceError("invalid_input", "Unsupported protected gate decision")
        decision = json.loads(_json(decision))
        evidence_refs = list(evidence_refs)
        if decision.get("subject_ref") != subject_ref or decision.get("evidence_refs") != evidence_refs:
            raise GovernanceError("invalid_input", "Decision must bind its exact subject and evidence list")
        advancing = decision["verdict"] in {"PASS", "PASS_WITH_KNOWN_LIMITATIONS"}
        fingerprint = hash_json({"subject_ref": subject_ref, "decision": decision, "evidence_refs": evidence_refs})
        with self._transaction() as conn:
            row = self._row(conn, run_id, caller_id)
            old = self._receipt(conn, run_id, "decision", idempotency_key, fingerprint)
            if old:
                if old["accepted_ref"]:
                    self._read_ref(conn, old["accepted_ref"], caller_id, "local")
                return old
            if conn.execute("SELECT 1 FROM decisions WHERE run_id=?", (run_id,)).fetchone():
                raise GovernanceError("policy_denied", "Trial decision is immutable")
            current_status = self._status(conn, run_id)
            if current_status in {"CANCELLED", "PAUSED", "ACCEPTED"} or (advancing and current_status in _TERMINAL):
                raise GovernanceError("policy_denied", "Cancelled/paused/accepted work cannot release")
            references = ([subject_ref] if subject_ref is not None else []) + evidence_refs
            for ref in references:
                if not isinstance(ref, Mapping) or ref.get("run_id") != run_id:
                    raise GovernanceError("invalid_input", "Gate evidence has foreign run attribution")
                self._read_ref(conn, ref, caller_id, "local")
            if advancing:
                if not subject_ref or decision.get("mandatory_pass") is not True or not decision.get("checks"):
                    raise GovernanceError("invalid_input", "Advancement requires subject and mandatory check evidence")
                if subject_ref["type"] != "intent_candidate" or subject_ref["schema_revision"] != "intent-r2":
                    raise GovernanceError("invalid_input", "Advancement requires the actual intermediate Intent candidate type/schema")
                checks = decision["checks"]
                if not isinstance(checks, list) or any(not isinstance(check, dict) for check in checks):
                    raise GovernanceError("invalid_input", "Mandatory findings must be structured")
                # Findings without an explicit optional marker are mandatory.
                # A summary boolean never overrides contradictory raw findings.
                mandatory = [check for check in checks if check.get("mandatory", True) is not False]
                if (not mandatory or any(type(check.get("mandatory", True)) is not bool for check in checks)
                        or any(check.get("status") != "PASS" for check in mandatory)):
                    raise GovernanceError("invalid_input", "Every mandatory finding must explicitly PASS before release")
                if decision.get("contract_sha256") != hash_json(json.loads(row["contract"])):
                    raise GovernanceError("invalid_input", "Decision contract differs from frozen contract")
                profile = decision.get("profile_sha256")
                expected_profile = json.loads(row["contract"]).get("profile_sha256") or json.loads(row["configuration"]).get("profile_sha256")
                if not isinstance(profile, str) or not re.fullmatch(r"[0-9a-f]{64}", profile) or (expected_profile and expected_profile != profile):
                    raise GovernanceError("invalid_input", "Decision profile differs from frozen protected assignment")
                attempts = self._attempts(conn, run_id)
                successful = {a["role"]: a for a in attempts if a["outcome"] == "SUCCEEDED"}
                if set(successful) != {"compiler", "verifier"}:
                    raise GovernanceError("invalid_input", "Both trial invocations need successful captured evidence")
                if successful["compiler"]["evidence"]["output_ref"] != subject_ref:
                    raise GovernanceError("invalid_input", "Accepted subject is not the compiler's actual output")
                if any(a["evidence"]["output_ref"] not in evidence_refs for a in successful.values()):
                    raise GovernanceError("invalid_input", "Decision omits actual compiler/verifier output evidence")
            receipt = {"interface_revision": INTERFACE_REVISION, "run_id": run_id, "decision_sha256": hash_json(decision),
                       "accepted_ref": dict(subject_ref) if advancing else None, "committed_at": utc_now()}
            conn.execute("INSERT INTO decisions VALUES(?,?,?,?,?)",
                         (run_id, _json(decision), _json(receipt), _json(subject_ref) if advancing else None, receipt["committed_at"]))
            self._event(conn, run_id, "decision", {"decision": decision, "receipt": receipt})
            status = "ACCEPTED" if advancing else {"FAIL": "FAILED", "ENVIRONMENT_BLOCKED": "ENVIRONMENT_BLOCKED", "INCONCLUSIVE": "INCONCLUSIVE"}[decision["verdict"]]
            self._fault("before_release")
            self._event(conn, run_id, "status", {"status": status, "reasons": decision.get("reasons", [])})
            self._save_receipt(conn, run_id, "decision", idempotency_key, fingerprint, receipt)
        self._fault("after_decision_commit")
        return receipt

    def recover_interrupted(self) -> list[str]:
        """Protected startup: pause unfinished work, retaining all observations."""
        paused = []
        with self._transaction() as conn:
            rows = conn.execute("SELECT run_id,user_id FROM runs ORDER BY created_at").fetchall()
            for row in rows:
                run_id = row["run_id"]
                if self._status(conn, run_id) in _TERMINAL:
                    continue
                for attempt in self._attempts(conn, run_id):
                    if attempt["outcome"] == "RUNNING":
                        self._event(conn, run_id, "attempt_finished", {**attempt, "outcome": "INTERRUPTED", "finished_at": utc_now(),
                                    "evidence": {"unavailable_reason": "Service interrupted; effects not replayed"}})
                roles = {attempt["role"] for attempt in self._attempts(conn, run_id)}
                stages = []
                if "compiler" not in roles:
                    stages.append("compiler_dispatch")
                if not any(event["event_type"] == "deterministic_pass" for event in self._events(conn, run_id)):
                    stages.append("deterministic_validation")
                if "verifier" not in roles:
                    stages.append("verifier_dispatch")
                # No authoritative final findings/release were committed in an
                # unfinished run. Existing invocation records remain distinct;
                # NOT_RUN does not invent an invocation or assert no raw effect.
                stages.extend([*(f"semantic:F{i}" for i in range(1, 7)), "protected_release"])
                self._event(conn, run_id, "not_run", {"checks": [
                    {"check_id": stage, "status": "NOT_RUN", "reason": "Service interruption; no committed finding or release, no replay"}
                    for stage in stages]})
                self._event(conn, run_id, "status", {"status": "PAUSED", "reason": "Service restart; inspection only, no replay"})
                paused.append(run_id)
        return paused

    def cancel(self, run_id: str, *, caller_id: str, reason: str = "Explicit user cancellation") -> dict:
        with self._transaction() as conn:
            self._row(conn, run_id, caller_id)
            status = self._status(conn, run_id)
            if status in _TERMINAL:
                if status == "CANCELLED":
                    return self._snapshot(conn, run_id, caller_id)
                raise GovernanceError("policy_denied", "Terminal run cannot be cancelled or resumed")
            for attempt in self._attempts(conn, run_id):
                if attempt["outcome"] == "RUNNING":
                    self._event(conn, run_id, "attempt_finished", {**attempt, "outcome": "CANCELLED", "finished_at": utc_now(),
                                "evidence": {"reason": reason, "effects_undone": False}})
            self._event(conn, run_id, "status", {"status": "CANCELLED", "reason": reason, "effects_undone": False})
            result = self._snapshot(conn, run_id, caller_id)
        return result
