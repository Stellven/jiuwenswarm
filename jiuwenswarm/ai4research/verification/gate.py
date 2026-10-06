"""M0-IF-007@r2: verifier findings are separate from host advancement policy."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, ValidationError

from ..common import GovernanceError, hash_json
from ..intent.models import Digest, StrictModel, strict_json


class Finding(StrictModel):
    check_id: Literal["F1", "F2", "F3", "F4", "F5", "F6"]
    status: Literal["PASS", "FAIL", "INCONCLUSIVE"]
    reason: Annotated[str, Field(min_length=1, max_length=4096)]
    evidence_refs: Annotated[list[Literal["original", "candidate", "execution"]], Field(min_length=1, max_length=3)]


class Assessment(StrictModel):
    schema_revision: Literal["assessment-r2"]
    subject_sha256: Digest
    source_sha256: Digest
    contract_sha256: Digest
    profile_sha256: Digest
    findings: Annotated[list[Finding], Field(min_length=6, max_length=6)]
    limitations: Annotated[list[str], Field(max_length=32)]


def aggregate(raw: bytes, *, subject_ref: dict, original_ref: dict, contract: dict,
              profile_sha256: str, deterministic: list[dict], evidence_refs: list[dict]) -> dict:
    """Validate assessment mechanically, then apply the frozen host policy."""
    try:
        assessment = Assessment.model_validate(strict_json(raw))
    except (ValidationError, GovernanceError) as exc:
        raise GovernanceError("malformed_assessment", "Semantic assessment violates the protected schema.") from exc
    expected = (subject_ref["sha256"], original_ref["sha256"], hash_json(contract), profile_sha256)
    observed = (assessment.subject_sha256, assessment.source_sha256,
                assessment.contract_sha256, assessment.profile_sha256)
    if observed != expected:
        raise GovernanceError("subject_mismatch", "Semantic assessment is stale, swapped or uses different criteria.")
    if {f.check_id for f in assessment.findings} != {f"F{i}" for i in range(1, 7)}:
        raise GovernanceError("missing_findings", "Every frozen semantic obligation needs one finding.")
    if any(not f.reason.strip() for f in assessment.findings):
        raise GovernanceError("malformed_assessment", "Findings need explicit reasons.")
    checks = [*deterministic, *(f.model_dump() for f in assessment.findings)]
    statuses = {c["status"] for c in checks}
    if "FAIL" in statuses:
        verdict = "FAIL"
    elif statuses != {"PASS"}:
        verdict = "INCONCLUSIVE"
    else:
        verdict = "PASS_WITH_KNOWN_LIMITATIONS" if assessment.limitations else "PASS"
    return {"interface_revision": "M0-IF-007@r2", "verdict": verdict,
            "subject_ref": subject_ref, "checks": checks,
            "reasons": [c["reason"] for c in checks], "evidence_refs": evidence_refs,
            "profile_sha256": profile_sha256, "contract_sha256": expected[2],
            "mandatory_pass": statuses == {"PASS"}, "limitations": assessment.limitations,
            "scope": "TRIAL-1 intermediate Intent only; no full-stage or M1 acceptance"}
