"""Protected local product identity and hashed session authority for TRIAL-1.

Provisioning methods are trusted host operations, never unauthenticated client
routes. Provider login, OS identity and client declarations are not authority.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit
import uuid

from .common import GovernanceError, canonical_json
from .configuration import validate_trial_options


MAX_SESSION_SECONDS = 86400
TOKEN = re.compile(r"[A-Za-z0-9_-]{43,128}\Z")


@dataclass(frozen=True, slots=True)
class UserProfile:
    user_id: str
    defaults: Mapping[str, Any] = field(repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {"user_id": self.user_id, "defaults": dict(self.defaults)}


@dataclass(frozen=True, slots=True)
class WorkspaceIdentity:
    workspace_id: str
    workspace_path: str

    def to_dict(self) -> dict[str, str]:
        return {"workspace_id": self.workspace_id, "workspace_path": self.workspace_path}


@dataclass(frozen=True, slots=True)
class AuthenticatedTrialContext:
    user_id: str
    workspace_id: str
    workspace_path: str
    session_id: str = field(repr=False)

    def to_dict(self) -> dict[str, str]:
        return {"user_id": self.user_id, "workspace_id": self.workspace_id,
                "workspace_path": self.workspace_path, "session_id": self.session_id,
                "interface_revision": "M0-IF-002@r2"}


def _origin(value: str) -> tuple[str, str, int]:
    if not isinstance(value, str) or len(value) > 2048:
        raise GovernanceError("policy_denied", "Browser origin is malformed.")
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError()
        host = parsed.hostname.lower()
        if host != "localhost" and not ipaddress.ip_address(host).is_loopback:
            raise ValueError()
        return parsed.scheme, host, parsed.port or (443 if parsed.scheme == "https" else 80)
    except (TypeError, ValueError):
        raise GovernanceError("policy_denied", "Browser origin is not an approved local origin.") from None


def _validate_client(peer_host: str, origin: str | None, expected_origin: str | None) -> None:
    try:
        address = ipaddress.ip_address(peer_host)
        allowed = address.is_loopback or (isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None and address.ipv4_mapped.is_loopback)
    except (TypeError, ValueError):
        allowed = False
    if not allowed:
        raise GovernanceError("policy_denied", "Only an authorized loopback client is supported.")
    if origin is not None and (expected_origin is None or _origin(origin) != _origin(expected_origin)):
        raise GovernanceError("policy_denied", "Browser origin does not match the local application.")


def _token_hash(token: str) -> str:
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        raise GovernanceError("policy_denied", "A valid local session credential is required.")
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class IdentityStore:
    """One durable local user with one active authorized workspace context."""

    def __init__(self, db_path: str | Path, *, clock: Callable[[], float] = time.time):
        supplied = Path(db_path).absolute()
        if supplied.is_symlink():
            raise GovernanceError("policy_denied", "Identity storage cannot be a symbolic link.")
        self.db_path = supplied.resolve()
        self._clock = clock
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                descriptor = os.open(self.db_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(descriptor)
            if not self.db_path.is_file() or self.db_path.is_symlink():
                raise GovernanceError("policy_denied", "Identity storage is not a regular protected file.")
            if os.name != "nt":
                os.chmod(self.db_path, 0o600)
            with self._connection() as connection:
                connection.executescript("""
                    CREATE TABLE IF NOT EXISTS product_user (
                        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                        user_id TEXT NOT NULL UNIQUE, defaults_json TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS workspaces (
                        workspace_id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE
                    );
                    CREATE TABLE IF NOT EXISTS sessions (
                        token_hash TEXT PRIMARY KEY, session_id TEXT NOT NULL UNIQUE,
                        user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                        expires_at REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id)
                    );
                    CREATE TABLE IF NOT EXISTS active_context (
                        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                        workspace_id TEXT NOT NULL
                    );
                """)
        except (OSError, sqlite3.Error):
            raise GovernanceError("persistence_failed", "Protected identity storage could not be initialized.") from None

    @contextmanager
    def _connection(self, *, write: bool = False):
        connection = None
        try:
            connection = sqlite3.connect(self.db_path, timeout=5)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except sqlite3.Error:
            if connection is not None:
                connection.rollback()
            raise GovernanceError("persistence_failed", "Protected identity storage operation failed.") from None
        except Exception:
            if connection is not None:
                connection.rollback()
            raise
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _profile(row: sqlite3.Row | None) -> UserProfile:
        if row is None:
            raise GovernanceError("environment_unavailable", "Local product identity has not been provisioned.")
        try:
            defaults = validate_trial_options(json.loads(row["defaults_json"]))
            if not isinstance(row["user_id"], str) or not re.fullmatch(r"[0-9a-f]{32}", row["user_id"]):
                raise ValueError()
        except (ValueError, TypeError, GovernanceError):
            raise GovernanceError("persistence_failed", "Stored product defaults are malformed.") from None
        return UserProfile(row["user_id"], MappingProxyType(defaults))

    def initialize(self, defaults: Mapping[str, Any] | None = None) -> UserProfile:
        options = validate_trial_options(defaults)
        with self._connection(write=True) as connection:
            row = connection.execute("SELECT * FROM product_user WHERE singleton=1").fetchone()
            if row is None:
                connection.execute("INSERT INTO product_user VALUES(1,?,?)", (uuid.uuid4().hex, canonical_json(options).decode()))
                row = connection.execute("SELECT * FROM product_user WHERE singleton=1").fetchone()
            profile = self._profile(row)
            if defaults is not None and options != dict(profile.defaults):
                raise GovernanceError("invalid_input", "Existing defaults require an explicit host update.")
            return profile

    def get_profile(self) -> UserProfile:
        with self._connection() as connection:
            return self._profile(connection.execute("SELECT * FROM product_user WHERE singleton=1").fetchone())

    def set_defaults(self, defaults: Mapping[str, Any]) -> UserProfile:
        options = validate_trial_options(defaults)
        with self._connection(write=True) as connection:
            profile = self._profile(connection.execute("SELECT * FROM product_user WHERE singleton=1").fetchone())
            connection.execute("UPDATE product_user SET defaults_json=? WHERE singleton=1", (canonical_json(options).decode(),))
        return UserProfile(profile.user_id, MappingProxyType(options))

    def register_workspace(self, path: str | Path) -> WorkspaceIdentity:
        if not isinstance(path, (str, Path)) or (isinstance(path, str) and not path.strip()):
            raise GovernanceError("invalid_input", "Workspace location is malformed.")
        try:
            resolved = Path(path).resolve()
        except (OSError, ValueError):
            raise GovernanceError("invalid_input", "Workspace location is malformed.") from None
        if self.db_path.is_relative_to(resolved) or (resolved.exists() and not resolved.is_dir()):
            raise GovernanceError("policy_denied", "Profile custody must be outside the trial workspace.")
        with self._connection(write=True) as connection:
            self._profile(connection.execute("SELECT * FROM product_user WHERE singleton=1").fetchone())
            row = connection.execute("SELECT * FROM workspaces WHERE path=?", (str(resolved),)).fetchone()
            if row is None:
                connection.execute("INSERT INTO workspaces VALUES(?,?)", (uuid.uuid4().hex, str(resolved)))
                row = connection.execute("SELECT * FROM workspaces WHERE path=?", (str(resolved),)).fetchone()
            return WorkspaceIdentity(row["workspace_id"], row["path"])

    def issue_session(self, workspace_id: str, ttl_seconds: float = 3600) -> str:
        """Trusted bootstrap returns a token once; only its digest is stored."""
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float)) or not math.isfinite(ttl_seconds) or not 0 < ttl_seconds <= MAX_SESSION_SECONDS:
            raise GovernanceError("invalid_input", "Session lifetime must be positive, finite and bounded.")
        if not isinstance(workspace_id, str) or not workspace_id:
            raise GovernanceError("invalid_input", "Workspace identity is required.")
        with self._connection(write=True) as connection:
            profile = self._profile(connection.execute("SELECT * FROM product_user WHERE singleton=1").fetchone())
            if connection.execute("SELECT 1 FROM workspaces WHERE workspace_id=?", (workspace_id,)).fetchone() is None:
                raise GovernanceError("policy_denied", "Workspace has not been authorized by the host.")
            now = self._clock()
            foreign = connection.execute("SELECT 1 FROM sessions WHERE revoked=0 AND expires_at>? AND workspace_id<>?", (now, workspace_id)).fetchone()
            if foreign is not None:
                raise GovernanceError("policy_denied", "Another authorized execution context is active.")
            connection.execute("INSERT INTO active_context VALUES(1,?) ON CONFLICT(singleton) DO UPDATE SET workspace_id=excluded.workspace_id", (workspace_id,))
            token = secrets.token_urlsafe(32)
            connection.execute("INSERT INTO sessions VALUES(?,?,?,?,?,0)", (_token_hash(token), uuid.uuid4().hex, profile.user_id, workspace_id, now + ttl_seconds))
            return token

    def authenticate(self, token: str, workspace_id: str | None = None, *, peer_host: str = "127.0.0.1", origin: str | None = None, expected_origin: str | None = None) -> AuthenticatedTrialContext:
        _validate_client(peer_host, origin, expected_origin)
        fingerprint = _token_hash(token)
        with self._connection() as connection:
            row = connection.execute("""SELECT s.*,w.path FROM sessions s
                JOIN workspaces w ON w.workspace_id=s.workspace_id
                JOIN product_user u ON u.singleton=1 AND u.user_id=s.user_id
                JOIN active_context a ON a.singleton=1 AND a.workspace_id=s.workspace_id
                WHERE s.token_hash=? AND s.revoked=0 AND s.expires_at>?""", (fingerprint, self._clock())).fetchone()
            if row is None or (workspace_id is not None and row["workspace_id"] != workspace_id):
                raise GovernanceError("policy_denied", "Session is invalid, expired, revoked or outside its workspace.")
            if str(Path(row["path"]).resolve()) != row["path"]:
                raise GovernanceError("policy_denied", "Authorized workspace location changed.")
            return AuthenticatedTrialContext(row["user_id"], row["workspace_id"], row["path"], row["session_id"])

    def revoke_session(self, token: str) -> bool:
        fingerprint = _token_hash(token)
        with self._connection(write=True) as connection:
            result = connection.execute("UPDATE sessions SET revoked=1 WHERE token_hash=? AND revoked=0", (fingerprint,))
            return result.rowcount == 1

    def custody_status(self) -> dict[str, Any]:
        """Report actual file checks; chmod does not establish Windows ACLs."""
        if os.name == "nt":
            return {"ready": False, "reason": "Windows protected-directory/file ACL evidence is not established by this module.", "session_storage": "sha256_only"}
        mode = self.db_path.stat().st_mode & 0o777
        parent_mode = self.db_path.parent.stat().st_mode & 0o777
        return {"ready": mode == 0o600 and not parent_mode & 0o077, "file_mode": oct(mode), "parent_mode": oct(parent_mode), "session_storage": "sha256_only"}
