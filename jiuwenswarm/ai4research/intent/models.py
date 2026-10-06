"""M0-IF-020@r2: strict, source-attributed intermediate extraction."""
from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..common import GovernanceError, sha256_bytes

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class SourceSpan(StrictModel):
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]


class Statement(StrictModel):
    text: Annotated[str, Field(min_length=1, max_length=8192)]
    source_spans: Annotated[list[SourceSpan], Field(min_length=1, max_length=32)]


class IntermediateIntent(StrictModel):
    schema_revision: Literal["intent-r2"]
    run_id: Annotated[str, Field(min_length=1, max_length=128)]
    source_sha256: Digest
    objective: Statement
    desired_outcome: Statement | None
    scope: Annotated[list[Statement], Field(max_length=64)]
    constraints: Annotated[list[Statement], Field(max_length=64)]
    omissions: Annotated[list[str], Field(max_length=32)]
    conflicts: Annotated[list[str], Field(max_length=32)]


def strict_json(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate field")
            result[key] = value
        return result

    try:
        if len(raw) > 131072:
            raise ValueError("Oversized output")
        value = json.loads(raw, object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite number")))
        if not isinstance(value, dict):
            raise ValueError("Object required")
        return value
    except (ValueError, UnicodeError) as exc:
        raise GovernanceError("malformed_output", "Output must be one strict JSON object.") from exc


def validate_intent(raw: bytes, original: str, run_id: str) -> IntermediateIntent:
    try:
        intent = IntermediateIntent.model_validate(strict_json(raw))
    except ValidationError as exc:
        raise GovernanceError("invalid_intent", "Intermediate Intent violates the active contract.") from exc
    if intent.run_id != run_id or intent.source_sha256 != sha256_bytes(original.encode("utf-8")):
        raise GovernanceError("subject_mismatch", "Intent is stale or belongs to another original request.")
    statements = [intent.objective, *intent.scope, *intent.constraints]
    if intent.desired_outcome:
        statements.append(intent.desired_outcome)
    for statement in statements:
        if not statement.text.strip():
            raise GovernanceError("invalid_intent", "Empty extracted statement.")
        for span in statement.source_spans:
            if span.end <= span.start or span.end > len(original) or not original[span.start:span.end].strip():
                raise GovernanceError("evidence_mismatch", "Source evidence span is invalid.")
    if any(not text.strip() for text in [*intent.omissions, *intent.conflicts]):
        raise GovernanceError("invalid_intent", "Omissions and conflicts must be explicit nonempty observations.")
    return intent
