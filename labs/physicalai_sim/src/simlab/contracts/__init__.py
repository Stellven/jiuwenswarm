"""SIMLAB-IF-001@r1 contracts: records, enums, typed errors, canonical hashing."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import ValidationError

from .errors import CATALOGUE, SimlabError, finding
from .records import RECORDS, SCHEMA_VERSION, Experiment, Manifest, Result, TypedError

__all__ = ["CATALOGUE", "SimlabError", "finding", "RECORDS", "SCHEMA_VERSION", "Experiment", "Manifest",
           "Result", "TypedError", "parse_record", "canonical", "sha256_hex", "pydantic_findings"]

_ENUM_TYPES = {"enum", "literal_error"}


def canonical(value: Any) -> bytes:
    """Canonical JSON bytes: sorted keys, compact, UTF-8, no NaN."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def sha256_hex(data: bytes | str | dict | list) -> str:
    if isinstance(data, (dict, list)):
        data = canonical(data)
    elif isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def _pointer(loc: tuple) -> str:
    parts = []
    for p in loc:
        if isinstance(p, str) and p in {"function-after", "function-before"}:
            continue
        parts.append(str(p).replace("~", "~0").replace("/", "~1"))
    return "/" + "/".join(parts) if parts else ""


def pydantic_findings(exc: ValidationError) -> list[dict]:
    out = []
    for e in exc.errors(include_url=False):
        t = e.get("type", "")
        loc = tuple(x for x in e.get("loc", ()) if not (isinstance(x, str) and x.startswith(("tagged-union", "union["))))
        if t == "missing":
            code = "E_SCHEMA_REQUIRED"
        elif t == "extra_forbidden":
            code = "E_SCHEMA_UNKNOWN_FIELD"
        elif t in _ENUM_TYPES:
            code = "E_SCHEMA_ENUM"
        else:
            code = "E_SCHEMA_TYPE"
        out.append(finding(code, e.get("msg", t), _pointer(loc)))
    # A union failure reports one error per branch at the same path; keep one.
    seen, uniq = set(), []
    for f in out:
        key = (f["code"], f["path"])
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    return uniq


def parse_record(record: str, data: Any):
    """Return (model or None, findings). Every schema finding is returned at once."""
    cls = RECORDS[record]
    if not isinstance(data, dict):
        return None, [finding("E_SCHEMA_TYPE", f"{record} must be a JSON object", "")]
    try:
        return cls.model_validate(data), []
    except ValidationError as exc:
        return None, pydantic_findings(exc)
