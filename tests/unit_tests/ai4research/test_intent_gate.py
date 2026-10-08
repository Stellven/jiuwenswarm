"""Independent frozen examples for M1-INTENT/V01: deficient results never release."""

from __future__ import annotations

import copy
import json
import unittest

from pydantic import ValidationError

from jiuwenswarm.ai4research.intent.gate import semantic_gate, tier1
from jiuwenswarm.ai4research.intent.models import (
    FIXED_DEFAULTS, MANDATORY_OBLIGATIONS, FrozenPolicy, InvocationEvidence, sha256_text,
)
from jiuwenswarm.ai4research.intent.prompts import compiler_prompt, verifier_prompt

ORIGINAL = ("Compare baseline A with treatment B on the supplied dataset. Never use network. "
            "Accuracy is mandatory; speed is optional. Report evidence.")
RUN = "frozen-example-01"


def candidate_fixture() -> dict:
    return {
        "schema_version": "1", "run_id": RUN, "input_sha256": sha256_text(ORIGINAL),
        "lane": "scientific_research",
        "objective": {"text": "Compare baseline A and treatment B on supplied data",
                      "source_quote": "Compare baseline A with treatment B on the supplied dataset."},
        "in_scope": [{"text": "Use supplied dataset", "source_quote": "supplied dataset"}],
        "out_of_scope": [],
        "mandatory_requirements": [{"text": "Accuracy", "source_quote": "Accuracy is mandatory"}],
        "preferences": [{"text": "Speed", "source_quote": "speed is optional"}],
        "constraints": [{"text": "No network", "source_quote": "Never use network."}],
        "targets": [],
        "evidence_obligations": [{"text": "Report evidence", "source_quote": "Report evidence."}],
        "ambiguities": [], "defaults": dict(FIXED_DEFAULTS),
    }


def assessment_fixture(raw_candidate: str) -> dict:
    return {
        "schema_version": "1", "run_id": RUN, "input_sha256": sha256_text(ORIGINAL),
        "candidate_sha256": sha256_text(raw_candidate),
        "checks": [{"obligation_id": obligation, "status": "PASS",
                    "reason": "The supplied meaning and boundaries are preserved in the corresponding fields.",
                    "evidence": [{"source": "input", "quote": "Compare baseline A"},
                                 {"source": "candidate", "quote": "Compare baseline A"}]}
                   for obligation in MANDATORY_OBLIGATIONS],
        "limitations": [],
    }


def invocation_fixture(call_role: str, raw: str, candidate_raw: str = "", **changes) -> InvocationEvidence:
    prompt = compiler_prompt(ORIGINAL, RUN) if call_role == "compiler" else verifier_prompt(ORIGINAL, candidate_raw, RUN)
    fields = dict(invocation_id=call_role + "-call", role=call_role, run_id=RUN,
                  conversation_id=call_role + "-conversation", prompt_sha256=sha256_text(prompt),
                  status="completed", elapsed_seconds=1.0, raw_output=raw,
                  tools=[], effects=[], usage={"total_tokens": 10})
    fields.update(changes)
    return InvocationEvidence(**fields)


class IntentGateTests(unittest.TestCase):
    def setUp(self):
        self.policy = FrozenPolicy()
        self.candidate = candidate_fixture()
        self.raw = json.dumps(self.candidate, ensure_ascii=False)

    def tier(self, raw=None, **changes):
        raw = self.raw if raw is None else raw
        return tier1(raw, ORIGINAL, RUN, invocation_fixture("compiler", raw, **changes), self.policy)

    def semantic(self, assessment=None, *, raw=None, compiler_changes=None, verifier_changes=None, policy=None):
        raw = self.raw if raw is None else raw
        assessment = assessment_fixture(raw) if assessment is None else assessment
        rendered = assessment if isinstance(assessment, str) else json.dumps(assessment, ensure_ascii=False)
        return semantic_gate(rendered, ORIGINAL, raw, RUN,
                             invocation_fixture("compiler", raw, **(compiler_changes or {})),
                             invocation_fixture("verifier", rendered, raw, **(verifier_changes or {})),
                             policy or self.policy)

    def test_normal_candidate_requires_both_tiers_before_release(self):
        candidate, result = self.tier()
        self.assertEqual(candidate.objective.source_quote, self.candidate["objective"]["source_quote"])
        self.assertTrue(result.tier1)
        self.assertIsNone(result.tier2)
        self.assertFalse(result.accepted)
        accepted = self.semantic()
        self.assertEqual(accepted.verdict, "PASS")
        self.assertTrue(accepted.accepted)

    def test_candidate_json_is_strict_without_repairs(self):
        for bad in ("```json\n" + self.raw + "\n```", self.raw + " trailing", "[]", "{", "NaN",
                    self.raw.replace('"schema_version": "1"', '"schema_version":"1","schema_version":"1"')):
            with self.subTest(raw=bad[:50]):
                candidate, result = self.tier(bad)
                self.assertIsNone(candidate)
                self.assertEqual(result.verdict, "FAIL")
                self.assertIsNone(result.tier2)

    def test_all_candidate_fields_required_and_extra_fields_denied(self):
        for field in self.candidate:
            bad = copy.deepcopy(self.candidate)
            del bad[field]
            with self.subTest(field=field):
                self.assertEqual(self.tier(json.dumps(bad))[1].verdict, "FAIL")
        bad = {**self.candidate, "accepted_reference": "producer-claim"}
        self.assertEqual(self.tier(json.dumps(bad))[1].verdict, "FAIL")

    def test_stale_swapped_wrong_lane_and_fabricated_quotes_block(self):
        variants = [{"run_id": "other-run"}, {"input_sha256": "0" * 64}, {"lane": "engineering"},
                    {"objective": {"text": "Invented objective", "source_quote": "not in original"}},
                    {"objective": {"text": "", "source_quote": "Compare baseline A"}},
                    {"defaults": {**FIXED_DEFAULTS, "permission": "network_allowed"}}]
        for changes in variants:
            with self.subTest(changes=changes):
                self.assertEqual(self.tier(json.dumps({**self.candidate, **changes}))[1].verdict, "FAIL")

    def test_unknown_default_values_block(self):
        bad = {**self.candidate, "defaults": {**FIXED_DEFAULTS, "resources": "GPU available"}}
        self.assertEqual(self.tier(json.dumps(bad))[1].verdict, "FAIL")

    def test_material_ambiguity_cannot_be_overridden_by_all_pass_assessor(self):
        bad = {**self.candidate, "ambiguities": ["Which supplied dataset is intended?"]}
        raw = json.dumps(bad)
        result = self.semantic(raw=raw)
        self.assertEqual(result.verdict, "INCONCLUSIVE")
        self.assertFalse(result.tier1)
        self.assertIsNone(result.tier2)
        self.assertFalse(result.accepted)

    def test_independent_execution_identity_tools_effects_and_prompt_binding(self):
        for changes in ({"role": "verifier"}, {"run_id": "other"}, {"tools": ["network"]},
                        {"effects": ["write_file"]}, {"prompt_sha256": "0" * 64},
                        {"status": "timeout"}, {"status": "cancelled"}, {"elapsed_seconds": 61.0}):
            with self.subTest(changes=changes):
                self.assertEqual(self.tier(**changes)[1].verdict, "FAIL")
        invocation = invocation_fixture("compiler", self.raw + " ")
        result = tier1(self.raw, ORIGINAL, RUN, invocation, self.policy)[1]
        self.assertEqual(result.verdict, "FAIL")

    def test_environment_failure_is_explicit_block(self):
        result = self.tier(status="environment_blocked", error_code="AUTH_REQUIRED")[1]
        self.assertEqual(result.verdict, "ENVIRONMENT_BLOCKED")
        self.assertFalse(result.accepted)

    def test_empty_failed_compiler_reports_execution_cause_before_output_bounds(self):
        for status, error, verdict in (("environment_blocked", "RUNTIME_DISCONNECTED", "ENVIRONMENT_BLOCKED"),
                                       ("timeout", "CALL_TIMEOUT", "FAIL"),
                                       ("cancelled", "CANCELLED", "FAIL"),
                                       ("failed", "TURN_FAILED", "FAIL")):
            with self.subTest(status=status):
                candidate, result = self.tier("", status=status, error_code=error)
                self.assertIsNone(candidate)
                self.assertEqual(result.verdict, verdict)
                self.assertFalse(result.tier1)
                self.assertIsNone(result.tier2)
                self.assertFalse(result.accepted)
                self.assertEqual(result.reasons, [f"INVOCATION_STATUS: {status} ({error})"])
        self.assertEqual(self.tier("")[1].reasons, ["OUTPUT_BOUND: empty or overlarge raw candidate"])

    def test_empty_failed_verifier_reports_execution_cause_before_assessment_bounds(self):
        for status, error, verdict in (("environment_blocked", "RUNTIME_DISCONNECTED", "ENVIRONMENT_BLOCKED"),
                                       ("timeout", "CALL_TIMEOUT", "FAIL"),
                                       ("cancelled", "CANCELLED", "FAIL"),
                                       ("failed", "TURN_FAILED", "FAIL")):
            with self.subTest(status=status):
                result = self.semantic("", verifier_changes={"status": status, "error_code": error})
                self.assertEqual(result.verdict, verdict)
                self.assertTrue(result.tier1)
                self.assertIsNone(result.tier2)
                self.assertFalse(result.accepted)
                self.assertEqual(result.reasons, [f"INVOCATION_STATUS: {status} ({error})"])
        self.assertEqual(self.semantic("").reasons, ["ASSESSMENT_BOUND: empty or overlarge raw assessment"])

    def test_unknown_execution_error_text_is_not_exposed_in_gate_reason(self):
        for error in ("API exception: Bearer example-secret", "RUNTIME_DISCONNECTED\nexample-secret", "UNKNOWN_CODE"):
            with self.subTest(error=error):
                result = self.tier("", status="environment_blocked", error_code=error)[1]
                self.assertEqual(result.verdict, "ENVIRONMENT_BLOCKED")
                self.assertEqual(result.reasons, ["INVOCATION_STATUS: environment_blocked"])
                result = self.semantic("", verifier_changes={"status": "environment_blocked", "error_code": error})
                self.assertEqual(result.reasons, ["INVOCATION_STATUS: environment_blocked"])

    def test_environment_status_does_not_mask_invalid_input_custody_or_prohibited_effects(self):
        invocation = invocation_fixture("compiler", "", status="environment_blocked")
        self.assertEqual(tier1("", " ", RUN, invocation, self.policy)[1].reasons,
                         ["INPUT_BOUND: empty or overlarge original input"])
        for changes, prefix in (({"run_id": "other-run"}, "INVOCATION_IDENTITY"),
                                ({"prompt_sha256": "0" * 64}, "INVOCATION_PROFILE"),
                                ({"tools": ["network"]}, "PROHIBITED_EFFECT"),
                                ({"effects": ["write_file"]}, "PROHIBITED_EFFECT")):
            with self.subTest(changes=changes):
                result = self.tier("", status="environment_blocked", **changes)[1]
                self.assertEqual(result.verdict, "FAIL")
                self.assertTrue(result.reasons[0].startswith(prefix))
                self.assertFalse(result.accepted)

    def test_input_output_bounds_are_utf8_bytes(self):
        self.policy = FrozenPolicy(max_output_bytes=len(self.raw.encode("utf-8")) - 1)
        self.assertEqual(self.tier()[1].verdict, "FAIL")
        policy = FrozenPolicy(max_input_bytes=1)
        result = tier1(self.raw, "é", RUN, invocation_fixture("compiler", self.raw), policy)[1]
        self.assertEqual(result.verdict, "FAIL")
        self.assertEqual(tier1(self.raw, " ", RUN, invocation_fixture("compiler", self.raw), FrozenPolicy())[1].verdict,
                         "FAIL")

    def test_every_obligation_coverage_is_unique_and_required(self):
        for obligation in MANDATORY_OBLIGATIONS:
            assessment = assessment_fixture(self.raw)
            assessment["checks"] = [check for check in assessment["checks"] if check["obligation_id"] != obligation]
            with self.subTest(missing=obligation):
                self.assertEqual(self.semantic(assessment).verdict, "FAIL")
        assessment = assessment_fixture(self.raw)
        assessment["checks"][-1] = assessment["checks"][0]
        self.assertEqual(self.semantic(assessment).verdict, "FAIL")

    def test_material_omission_addition_scope_and_constraints_failure_blocks(self):
        for obligation in ("omissions", "additions", "scope", "constraints"):
            assessment = assessment_fixture(self.raw)
            check = next(check for check in assessment["checks"] if check["obligation_id"] == obligation)
            check.update(status="FAIL", reason="Material supplied condition is omitted or contradicted.")
            assessment["limitations"] = ["Cannot waive missing material meaning."]
            with self.subTest(obligation=obligation):
                result = self.semantic(assessment)
                self.assertEqual(result.verdict, "FAIL")
                self.assertFalse(result.accepted)

    def test_inconclusive_required_judgment_blocks(self):
        assessment = assessment_fixture(self.raw)
        assessment["checks"][-1]["status"] = "INCONCLUSIVE"
        result = self.semantic(assessment)
        self.assertEqual(result.verdict, "INCONCLUSIVE")
        self.assertFalse(result.accepted)

    def test_unsupported_or_missing_assessment_evidence_blocks(self):
        for evidence in ([], [{"source": "input", "quote": "invented quote"}],
                         [{"source": "candidate", "quote": "invented quote"}],
                         [{"source": "input", "quote": "Compare baseline A"}]):
            assessment = assessment_fixture(self.raw)
            assessment["checks"][0]["evidence"] = evidence
            with self.subTest(evidence=evidence):
                self.assertFalse(self.semantic(assessment).accepted)

    def test_binding_is_exact_raw_candidate_not_reserialization(self):
        assessment = assessment_fixture(self.raw)
        assessment["candidate_sha256"] = sha256_text(json.dumps(self.candidate, separators=(",", ":")))
        self.assertEqual(self.semantic(assessment).verdict, "FAIL")
        for field, value in (("run_id", "another"), ("input_sha256", "0" * 64)):
            with self.subTest(field=field):
                bad = {**assessment_fixture(self.raw), field: value}
                self.assertEqual(self.semantic(bad).verdict, "FAIL")

    def test_assessor_cannot_add_host_verdict_or_replacement(self):
        for field in ("verdict", "accepted_reference", "replacement"):
            with self.subTest(field=field):
                self.assertEqual(self.semantic({**assessment_fixture(self.raw), field: "PASS"}).verdict, "FAIL")

    def test_verifier_execution_fresh_state_and_effects_required(self):
        for changes in ({"conversation_id": "compiler-conversation"}, {"invocation_id": "compiler-call"},
                        {"tools": ["read_file"]}, {"effects": ["write_file"]},
                        {"prompt_sha256": "0" * 64}, {"status": "timeout"}):
            with self.subTest(changes=changes):
                self.assertFalse(self.semantic(verifier_changes=changes).accepted)

    def test_combined_budget_and_call_count_block(self):
        policy = FrozenPolicy(total_seconds=15.0)
        result = self.semantic(compiler_changes={"elapsed_seconds": 10.0},
                               verifier_changes={"elapsed_seconds": 10.0}, policy=policy)
        self.assertEqual(result.verdict, "FAIL")
        self.assertEqual(self.semantic(policy=FrozenPolicy(max_calls=1)).verdict, "FAIL")

    def test_token_cap_requires_reliable_meter_and_combined_tokens(self):
        policy = FrozenPolicy(max_tokens=15)
        self.assertEqual(self.semantic(policy=policy).verdict, "FAIL")
        self.assertEqual(self.semantic(policy=policy, compiler_changes={"usage": None}).verdict,
                         "ENVIRONMENT_BLOCKED")
        self.assertEqual(self.semantic(policy=policy, verifier_changes={"usage": {"output_tokens": 3}}).verdict,
                         "ENVIRONMENT_BLOCKED")
        self.assertTrue(self.semantic(policy=FrozenPolicy(max_tokens=20)).accepted)

    def test_nonblocking_limitations_only_follow_all_mandatory_passes(self):
        assessment = assessment_fixture(self.raw)
        assessment["limitations"] = ["No population reliability claim."]
        result = self.semantic(assessment)
        self.assertEqual(result.verdict, "PASS_WITH_KNOWN_LIMITATIONS")
        self.assertTrue(result.accepted)
        self.assertEqual(result.warnings, assessment["limitations"])

    def test_strict_frozen_config_and_evidence_reject_invalid_bounds(self):
        for value in ({"max_calls": 3}, {"max_tokens": 0}, {"per_call_seconds": 0.0},
                      {"total_seconds": float("nan")}, {"max_input_bytes": "65536"}):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                FrozenPolicy(**value)
        with self.assertRaises(ValidationError):
            self.policy.max_calls = 3
        with self.assertRaises(ValidationError):
            invocation_fixture("compiler", self.raw, usage={"total_tokens": -1})

    def test_prompt_profiles_are_bound_and_treat_subjects_as_data(self):
        compile_profile = compiler_prompt(ORIGINAL, RUN)
        verify_profile = verifier_prompt(ORIGINAL, self.raw, RUN)
        self.assertIn("untrusted user data", compile_profile)
        self.assertIn("Do not edit, repair, replace", verify_profile)
        self.assertIn(sha256_text(ORIGINAL), compile_profile)
        self.assertIn(sha256_text(self.raw), verify_profile)
        self.assertNotEqual(compile_profile, verify_profile)


if __name__ == "__main__":
    unittest.main()
