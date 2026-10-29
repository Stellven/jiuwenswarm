"""Read-only observers for already captured real RSI operations; never start one."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3

import pytest


def actual_directory(variable):
    value = os.environ.get(variable)
    assert value, f"BLOCKED: {variable} must identify the existing role-owned capture"
    root = Path(value)
    assert root.is_absolute() and root.is_dir(), "BLOCKED: existing absolute capture directory required"
    assert not any(path.is_symlink() for path in (root, *root.parents)), "Capture ancestry cannot be symlinked"
    return root


@pytest.fixture
def public_session():
    def read(variable="AI4R_RSI_FROZEN_EXPORT"):
        from jiuwenswarm.research_sidecar.adapters.rsi import read_public_export, validate_public_session, validate_actual_proposer
        root = actual_directory(variable)
        key = os.environ.get("AI4R_RSI_PUBLIC_KEY_HEX")
        key_id = os.environ.get("AI4R_RSI_SIGNER_KEY_ID")
        assert key and key_id, "BLOCKED: independently pinned public custodian key and key ID required"
        records = read_public_export(root)
        validate_public_session(records, public_key=bytes.fromhex(key), key_id=key_id)
        validate_actual_proposer(records)
        result = next(row["record"] for row in records if row["kind"] == "rsi-session-result")
        session = next(row["record"] for row in records if row["ref"] == result["session_ref"])
        return records, session, result
    return read


class ReadOnlyCoreCapture:
    """Read exact indexed artifacts without constructing a writable product store."""
    def __init__(self, root):
        self.root = root
        database = root / "state/research.sqlite3"
        assert database.is_file(), "BLOCKED: actual isolated store database is absent"
        self.db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA query_only=ON")

    def read(self, ref):
        assert isinstance(ref, dict) and set(ref) == {"id", "sha256"}
        row = self.db.execute("SELECT sha256 FROM artifacts WHERE id=?", (ref["id"],)).fetchone()
        assert row and row["sha256"] == ref["sha256"], "Original identity is absent or swapped"
        digest = ref["sha256"]
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
        path = self.root / "artifacts/sha256" / digest[:2] / digest
        assert not any(p.is_symlink() for p in (path, *path.parents))
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest, "Original capture hash differs"
        return raw

    def get(self, ref):
        return json.loads(self.read(ref))

    def records(self, kind):
        rows = self.db.execute("SELECT r.id,a.sha256 FROM records r JOIN artifacts a ON a.id=r.id WHERE r.kind=? ORDER BY r.captured_at,r.id", (kind,)).fetchall()
        return [(dict(row), self.get(dict(row))) for row in rows]

    def close(self):
        self.db.close()


@pytest.fixture
def isolated_capture():
    assert os.geteuid() == 12001, "BLOCKED: use the actual RSI controller observer identity"
    root = actual_directory("AI4R_RSI_ISOLATED_STORE")
    assert not any(root.is_relative_to(Path(path)) for path in
                   ("/var/lib/ai4r/native", "/var/lib/ai4r-accounts", "/var/lib/ai4r-rsi/custodian")), "Foreign main or custodian state is not a trial capture"
    capture = ReadOnlyCoreCapture(root)
    try:
        yield capture
    finally:
        capture.close()
