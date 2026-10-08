"""Independent deterministic checks and protected gate policy, M1-IF-INTENT@r1."""

from __future__ import annotations

import json

from pydantic import ValidationError

from .models import FrozenPolicy, GateDecision, IntentCandidate, InvocationEvidence, SemanticAssessment, sha256_text
from .prompts import compiler_prompt, verifier_prompt

_SAFE_INVOCATION_ERROR_CODES = frozenset({
    "SIGN_IN_REQUIRED", "SUBSCRIPTION_REQUIRED", "ACCOUNT_IDENTITY_UNAVAILABLE", "BUSY",
    "PROFILE_STATE_INVALID", "PROFILE_IN_USE", "PROFILE_CONFIG_CONFLICT", "RUNTIME_VERSION_MISMATCH",
    "RUNTIME_UNAVAILABLE", "RUNTIME_DISCONNECTED", "RUNTIME_ERROR", "RUNTIME_TIMEOUT", "DELIVERY_UNKNOWN",
    "PROHIBITED_TOOL", "INVALID_INPUT", "INVALID_OUTPUT", "OUTPUT_LIMIT", "INVALID_RUNTIME_RESPONSE",
    "CALL_TIMEOUT", "CANCELLED", "TURN_FAILED",
})


def _decision(verdict: str, reason: str, *, tier1: bool = False, tier2: bool | None = None) -> GateDecision:
    return GateDecision(verdict=verdict, tier1=tier1, tier2=tier2, reasons=[reason])


def _strict_json(raw: str) -> object:
    def unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def finite_numbers(value: str) -> None:
        raise ValueError("non-finite JSON number")

    return json.loads(raw, object_pairs_hook=unique_keys, parse_constant=finite_numbers)


def _schema_reason(error: Exception) -> str:
    if isinstance(error, ValidationError):
        # Do not echo a potentially sensitive untrusted output value into the decision.
        return "; ".join(".".join(map(str, item["loc"])) + ":" + item["type"]
                         for item in error.errors()[:8])
    return type(error).__name__


def _invocation_failure(invocation: InvocationEvidence, role: str, run_id: str,
                        raw_output: str, expected_prompt: str, policy: FrozenPolicy) -> tuple[str, str] | None:
    if invocation.run_id != run_id or invocation.role != role:
        return "FAIL", "INVOCATION_IDENTITY: role or run binding differs"
    if invocation.route != "codex" or invocation.prompt_sha256 != sha256_text(expected_prompt):
        return "FAIL", "INVOCATION_PROFILE: route or pinned prompt binding differs"
    if invocation.tools or invocation.effects:
        return "FAIL", "PROHIBITED_EFFECT: tool/effect observations are not empty"
    if invocation.status != "completed":
        verdict = "ENVIRONMENT_BLOCKED" if invocation.status == "environment_blocked" else "FAIL"
        reason = "INVOCATION_STATUS: " + invocation.status
        if invocation.error_code in _SAFE_INVOCATION_ERROR_CODES:
            reason += " (" + invocation.error_code + ")"
        return verdict, reason
    if invocation.raw_output != raw_output:
        return "FAIL", "OUTPUT_BINDING: assessed output differs from observed exact output"
    if invocation.elapsed_seconds > policy.per_call_seconds:
        return "FAIL", "CALL_BUDGET: per-call elapsed time exceeded"
    if invocation.elapsed_seconds > policy.total_seconds:
        return "FAIL", "TOTAL_BUDGET: total elapsed time exceeded"
    if policy.max_tokens is not None:
        usage = invocation.usage
        if usage is None or "total_tokens" not in usage:
            return "ENVIRONMENT_BLOCKED", "TOKEN_METER_UNAVAILABLE: configured cap needs reliable total_tokens"
        if usage["total_tokens"] > policy.max_tokens:
            return "FAIL", "TOKEN_BUDGET: invocation token cap exceeded"
    return None


def tier1(raw_output: str, original_text: str, run_id: str, invocation: InvocationEvidence,
          policy: FrozenPolicy) -> tuple[IntentCandidate | None, GateDecision]:
    """Strict input, execution, schema, exact-subject and quoted-source checks. No repair."""
    try:
        input_size = len(original_text.encode("utf-8"))
    except UnicodeError:
        return None, _decision("FAIL", "UTF8_INVALID: subject is not valid UTF-8")
    if not original_text.strip() or input_size > policy.max_input_bytes:
        return None, _decision("FAIL", "INPUT_BOUND: empty or overlarge original input")
    failure = _invocation_failure(invocation, "compiler", run_id, raw_output,
                                  compiler_prompt(original_text, run_id), policy)
    if failure:
        return None, _decision(*failure)
    try:
        output_size = len(raw_output.encode("utf-8"))
    except UnicodeError:
        return None, _decision("FAIL", "UTF8_INVALID: candidate is not valid UTF-8")
    if not raw_output.strip() or output_size > policy.max_output_bytes:
        return None, _decision("FAIL", "OUTPUT_BOUND: empty or overlarge raw candidate")
    try:
        candidate = IntentCandidate.model_validate(_strict_json(raw_output))
    except (ValidationError, ValueError, TypeError, RecursionError) as error:
        return None, _decision("FAIL", "CANDIDATE_SCHEMA: " + _schema_reason(error))
    if candidate.run_id != run_id or candidate.input_sha256 != sha256_text(original_text):
        return None, _decision("FAIL", "CANDIDATE_BINDING: run or exact original digest differs")
    if any(claim.source_quote not in original_text for claim in candidate.quoted_claims):
        return None, _decision("FAIL", "CLAIM_REFERENCE: source quote is absent from exact original input")
    if candidate.ambiguities:
        return candidate, _decision("INCONCLUSIVE", "MATERIAL_AMBIGUITY: unresolved meaning cannot advance",
                                    tier1=False)
    return candidate, GateDecision(verdict="PASS", tier1=True, tier2=None,
                                   reasons=["TIER1_PASS: execution, schema, identity and source references conform"])


def semantic_gate(raw_assessment: str, original_text: str, raw_candidate: str, run_id: str,
                  compiler_invocation: InvocationEvidence, verifier_invocation: InvocationEvidence,
                  policy: FrozenPolicy) -> GateDecision:
    """Validate independent assessment custody and coverage, then apply host-owned policy."""
    candidate, preliminary = tier1(raw_candidate, original_text, run_id, compiler_invocation, policy)
    if candidate is None or preliminary.verdict != "PASS":
        return preliminary
    if policy.max_calls < 2:
        return _decision("FAIL", "CALL_COUNT: verifier would exceed frozen invocation budget", tier1=True)
    if (compiler_invocation.invocation_id == verifier_invocation.invocation_id or
            compiler_invocation.conversation_id == verifier_invocation.conversation_id):
        return _decision("FAIL", "INDEPENDENCE: verifier must use a fresh invocation and conversation", tier1=True)
    failure = _invocation_failure(verifier_invocation, "verifier", run_id, raw_assessment,
                                  verifier_prompt(original_text, raw_candidate, run_id), policy)
    if failure:
        return _decision(*failure, tier1=True)
    try:
        if not raw_assessment.strip() or len(raw_assessment.encode("utf-8")) > policy.max_output_bytes:
            return _decision("FAIL", "ASSESSMENT_BOUND: empty or overlarge raw assessment", tier1=True)
    except UnicodeError:
        return _decision("FAIL", "UTF8_INVALID: assessment is not valid UTF-8", tier1=True)
    if compiler_invocation.elapsed_seconds + verifier_invocation.elapsed_seconds > policy.total_seconds:
        return _decision("FAIL", "TOTAL_BUDGET: combined invocation time exceeded", tier1=True)
    if policy.max_tokens is not None:
        total = sum(invocation.usage["total_tokens"] for invocation in (compiler_invocation, verifier_invocation))
        if total > policy.max_tokens:
            return _decision("FAIL", "TOKEN_BUDGET: combined invocation tokens exceeded", tier1=True)
    try:
        assessment = SemanticAssessment.model_validate(_strict_json(raw_assessment))
    except (ValidationError, ValueError, TypeError, RecursionError) as error:
        return _decision("FAIL", "ASSESSMENT_SCHEMA: " + _schema_reason(error), tier1=True)
    if (assessment.run_id != run_id or assessment.input_sha256 != sha256_text(original_text) or
            assessment.candidate_sha256 != sha256_text(raw_candidate)):
        return _decision("FAIL", "ASSESSMENT_BINDING: run/input/exact candidate digest differs", tier1=True)
    for check in assessment.checks:
        for ref in check.evidence:
            subject = original_text if ref.source == "input" else raw_candidate
            if ref.quote not in subject:
                return _decision("FAIL", "ASSESSMENT_REFERENCE: " + check.obligation_id, tier1=True)
        if check.status == "PASS" and {ref.source for ref in check.evidence} != {"input", "candidate"}:
            return _decision("INCONCLUSIVE", "UNSUPPORTED_PASS: both input and candidate evidence required for " +
                             check.obligation_id, tier1=True, tier2=False)
    failed = [check for check in assessment.checks if check.status == "FAIL"]
    uncertain = [check for check in assessment.checks if check.status == "INCONCLUSIVE"]
    if failed or uncertain:
        return GateDecision(verdict="FAIL" if failed else "INCONCLUSIVE", tier1=True, tier2=False,
                            reasons=[check.obligation_id + ": " + check.reason for check in failed + uncertain])
    return GateDecision(verdict="PASS_WITH_KNOWN_LIMITATIONS" if assessment.limitations else "PASS",
                        tier1=True, tier2=True,
                        reasons=["MANDATORY_PASS: all six supported independent obligations passed"],
                        warnings=assessment.limitations)
