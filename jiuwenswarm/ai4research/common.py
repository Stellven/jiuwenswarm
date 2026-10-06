"""Credential-free errors and exact artifact identity helpers."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


class GovernanceError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def as_dict(self) -> dict:
        return {"code": self.code, "message": str(self), "details": self.details}


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
