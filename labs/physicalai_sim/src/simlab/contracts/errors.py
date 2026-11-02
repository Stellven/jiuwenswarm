"""Typed errors and the stable error-code catalogue (IF-001@r1, contracts/).

A typed error is {code, message, path, severity}. `validate` returns every
finding at once; operations raise SimlabError for operation errors.
"""
from __future__ import annotations

from typing import Any

# Code -> meaning. Stable within r1; additions are recorded in TASK §5.
CATALOGUE: dict[str, str] = {
    "E_SCHEMA_REQUIRED": "A required field is missing",
    "E_SCHEMA_TYPE": "A field has the wrong type or value",
    "E_SCHEMA_ENUM": "A value is not one of the allowed enum strings",
    "E_SCHEMA_UNKNOWN_FIELD": "A field is not part of the IF-001@r1 schema",
    "E_SEMANTIC_NO_ORIGIN": "A protocol item lacks an origin",
    "E_SEMANTIC_PARENT_MISSING": "Parent run or checkpoint does not exist",
    "E_SEMANTIC_COMPARISON_INCOMPLETE": "A comparison lacks unit of inference, pairing, aggregation or required precision",
    "E_SEMANTIC_ZERO_TRIALS": "The design yields no trial",
    "E_SEMANTIC_UNDECLARED_CHECKPOINT": "A save is requested at a point the procedure does not declare",
    "E_SEMANTIC_MJCF_COMPILE": "A model file does not compile (engine message included)",
    "E_SEMANTIC_ASSET_HASH": "An asset is missing from the manifest or its hash differs",
    "E_SEMANTIC_ENGINE_FLAG": "A setting that breaks exact replay is enabled",
    "E_SEMANTIC_DUPLICATE_ID": "An identifier is declared more than once",
    "E_SEMANTIC_UNKNOWN_REF": "A reference names an arm, factor, level, measurement, step or artifact that is not declared",
    "E_SEMANTIC_UNKNOWN_SIGNAL": "A signal name is malformed or names no model element",
    "E_SEMANTIC_UNKNOWN_TARGET": "An intervention or initial-state target names no model element",
    "E_SEMANTIC_TEMPLATE": "A model-file parameter is not resolved by arm, factor or random-variable values",
    "E_SEMANTIC_CONFIG": "The resolved configuration is missing or invalid",
    "E_SEMANTIC_ENGINE": "The declared engine or version is not the admitted executor",
    "E_SEMANTIC_MANIFEST_BINDING": "The manifest does not bind this experiment",
    "E_SEMANTIC_LIMITS": "A declared limit is missing or invalid",
    "E_SEMANTIC_CHECKPOINT_INCOMPATIBLE": "A branch's model state does not fit its parent checkpoint",
    "E_IMMUTABLE": "Attempt to modify a submitted experiment or a bound manifest",
    "E_NOT_BOUND": "The experiment is not bound to a stored manifest",
    "E_BOUND": "The draft is bound and can no longer change",
    "E_UNKNOWN_DRAFT": "No such draft",
    "E_UNKNOWN_RUN": "No such run",
    "E_UNKNOWN_CHECKPOINT": "No such checkpoint",
    "E_UNKNOWN_SIGNAL": "No such signal in this run",
    "E_UNKNOWN_REF": "No such data reference",
    "E_UNKNOWN_OPERATION": "No such operation",
    "E_ALREADY_TERMINAL": "The run already ended",
    "E_NOT_REPLAYABLE": "Exact replay is claimed only on the same machine and build",
    "E_EXTENSION_POINT": "Unknown extension point, or component code does not provide its entry function",
    "E_INVALID_INPUT": "Operation input is malformed",
    "E_RESERVED_OPERATION": "Operation is reserved for a later phase and not provided by this build",
    "E_DATA_DIR": "The declared data directory is missing, unwritable or inside the repository",
    "E_INTERNAL": "Infrastructure failure inside SIMLAB",
}


def finding(code: str, message: str, path: str = "", severity: str = "error") -> dict[str, Any]:
    if code not in CATALOGUE:
        raise KeyError(f"unregistered error code {code}")
    return {"code": code, "message": message, "path": path, "severity": severity}


class SimlabError(Exception):
    """Operation error carrying a typed error object (and optional findings)."""

    def __init__(self, code: str, message: str, path: str = "", findings: list[dict] | None = None):
        if code not in CATALOGUE:
            raise KeyError(f"unregistered error code {code}")
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.path = code, message, path
        self.findings = findings or []

    def to_error(self) -> dict[str, Any]:
        err = finding(self.code, self.message, self.path)
        if self.findings:
            err["findings"] = self.findings
        return err
