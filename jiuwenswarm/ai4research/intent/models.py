"""Strict runtime schemas implementing M1-IF-INTENT@r1."""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

INTERFACE_ID = "M1-IF-INTENT@r1"
SCHEMA_VERSION = "1"
MANDATORY_OBLIGATIONS = ("fidelity", "omissions", "additions", "constraints", "scope", "ambiguity")
FIXED_DEFAULTS = {"lane": "scientific_research", "scope": "unspecified", "resources": "unspecified"}
Nonempty = Annotated[str, StringConstraints(min_length=1)]
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Obligation = Literal["fidelity", "omissions", "additions", "constraints", "scope", "ambiguity"]
Verdict = Literal["PASS", "PASS_WITH_KNOWN_LIMITATIONS", "FAIL", "ENVIRONMENT_BLOCKED", "INCONCLUSIVE"]


def sha256_text(value: str) -> str:
    """Bind exact UTF-8 text, including whitespace and serialization."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)


class Claim(StrictModel):
    text: Nonempty
    source_quote: Nonempty

    @field_validator("text", "source_quote")
    @classmethod
    def meaningful_string(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("claim text and source quote must contain non-whitespace")
        return value


class IntentCandidate(StrictModel):
    schema_version: Literal["1"]
    run_id: Nonempty
    input_sha256: Digest
    lane: Literal["scientific_research"]
    objective: Claim
    in_scope: list[Claim]
    out_of_scope: list[Claim]
    mandatory_requirements: list[Claim]
    preferences: list[Claim]
    constraints: list[Claim]
    targets: list[Claim]
    evidence_obligations: list[Claim]
    ambiguities: list[Nonempty]
    defaults: dict[str, str]

    @model_validator(mode="after")
    def fixed_defaults(self) -> "IntentCandidate":
        if self.defaults != FIXED_DEFAULTS:
            raise ValueError("only the fixed, explicitly unspecified defaults are permitted")
        if any(not value.strip() for value in self.ambiguities):
            raise ValueError("ambiguities must contain meaningful text")
        return self

    @property
    def quoted_claims(self) -> list[Claim]:
        return [self.objective, *self.in_scope, *self.out_of_scope, *self.mandatory_requirements,
                *self.preferences, *self.constraints, *self.targets, *self.evidence_obligations]


class FrozenPolicy(StrictModel):
    max_input_bytes: int = Field(default=65536, gt=0, le=65536)
    max_output_bytes: int = Field(default=65536, gt=0, le=65536)
    per_call_seconds: float = Field(default=60.0, gt=0, le=60.0)
    total_seconds: float = Field(default=120.0, gt=0, le=120.0)
    max_calls: int = Field(default=2, ge=1, le=2)
    max_tokens: int | None = Field(default=None, gt=0)


class InvocationEvidence(StrictModel):
    invocation_id: Nonempty
    role: Literal["compiler", "verifier"]
    run_id: Nonempty
    conversation_id: Nonempty
    route: Literal["codex"] = "codex"
    model: Nonempty | None = None
    prompt_sha256: Digest
    status: Literal["completed", "failed", "timeout", "cancelled", "environment_blocked"]
    elapsed_seconds: float = Field(ge=0)
    raw_output: str
    tools: list[Nonempty] = Field(default_factory=list)
    effects: list[Nonempty] = Field(default_factory=list)
    usage: dict[str, int] | None = None
    error_code: Nonempty | None = None

    @field_validator("usage")
    @classmethod
    def nonnegative_usage(cls, value: dict[str, int] | None) -> dict[str, int] | None:
        if value is not None and any(count < 0 for count in value.values()):
            raise ValueError("usage counters cannot be negative")
        return value


class EvidenceReference(StrictModel):
    source: Literal["input", "candidate"]
    quote: Nonempty

    @field_validator("quote")
    @classmethod
    def meaningful_quote(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("evidence quote must contain non-whitespace")
        return value


class SemanticCheck(StrictModel):
    obligation_id: Obligation
    status: Literal["PASS", "FAIL", "INCONCLUSIVE"]
    reason: Nonempty
    evidence: list[EvidenceReference] = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a substantive reason is required")
        return value


class SemanticAssessment(StrictModel):
    schema_version: Literal["1"]
    run_id: Nonempty
    input_sha256: Digest
    candidate_sha256: Digest
    checks: list[SemanticCheck] = Field(min_length=6, max_length=6)
    limitations: list[Nonempty]

    @model_validator(mode="after")
    def complete_unique_coverage(self) -> "SemanticAssessment":
        ids = [check.obligation_id for check in self.checks]
        if len(set(ids)) != len(ids) or set(ids) != set(MANDATORY_OBLIGATIONS):
            raise ValueError("each mandatory obligation must appear exactly once")
        if any(not value.strip() for value in self.limitations):
            raise ValueError("limitations must contain meaningful text")
        return self


class GateDecision(StrictModel):
    schema_version: Literal["1"] = "1"
    verdict: Verdict
    tier1: bool
    tier2: bool | None
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.verdict in ("PASS", "PASS_WITH_KNOWN_LIMITATIONS") and self.tier1 and self.tier2 is True
