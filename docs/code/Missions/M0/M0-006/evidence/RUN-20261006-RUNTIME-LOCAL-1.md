# Verification run: RUN-20261006-RUNTIME-LOCAL-1 ? M0-006

Observed r2 trial controls on the frozen local execution candidate. This record maps retained batch observations to the owning V identifiers; it does not claim that each planned selective command was executed separately.

## Candidate and actual procedures

- Candidate HEAD `2cc0b8695d4000cc72af64eb781356697f7fd861`; 316 execution inputs; snapshot SHA256 `e60da4c6be859f39c5ec6a03e8cf9c870d69ea7f6b01367066922ebe7b8fdd63`; dirty diff SHA256 `c7284d208c81417b95c44f90fd350f433f671e00a25a543161692364707d62f4`. Source authority is immediate-plan.md SHA256 `0a7c21c2933c0be3b07e67cedaa91d2bd1706ca4382c364eb474ae616b919ec3`; exactly two CCs and current r2 interfaces.
- Compiler declaration SHA256 `e6a6392fa2cd8a6129bc46600be6bedc4f8f1b5a12fe4cad6e05206e060e4149`; verifier `eff8a0761029373fb5077c70c7f370ddd676c0014241a385516ee395fa30cc63`; protected profile `613bfc40ef756b154c8376a8947e8341872168ce185c124edd1b1a3b75e90071`.
- [Shared observed record](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-1.md), [exact input manifest](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-1/candidate.json) and [unchanged comparison](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-1/candidate-comparison.json).
- Actual combined command: [pytest.run.json](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-1/pytest.run.json). Working directory: `D:/research/ai_for_research/jiuwenswarm`. Exit code 0; 279 collected, 279 PASS, zero failed/skipped, 60.56 seconds. [Raw per-case results](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-1/pytest-cases.json), [JUnit](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-1/pytest.xml), [stdout](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-1/pytest.stdout.txt), [stderr](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-1/pytest.stderr.txt).
- Current native browser command: [browser.run.json](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-1/browser.run.json), [JUnit](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-1/browser.xml) and [observations/screenshots](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-1/browser-observations/accepted-wide.json). Exit code 0; nine collected/PASS, zero failed/skipped, 24.79 seconds; execution inputs unchanged. These are current-candidate scripted journeys; prior FRONTEND-MOCK-2 is not reused as current runtime acceptance.
- Actual dependencies: Windows/Python 3.11.3; real local SQLite/filesystem, process/lease and authenticated ASGI/HTTP/uvicorn/headless/browser boundaries. Provider/native protocol outputs are explicitly fixtures/ScriptedBridge. These assertions establish controls, never model fidelity or scientific truth.

## Per-check observed outcomes

| Check / level | Block / AC | Actual local subset counts | Native check result | Scope and remaining requirement |
| --- | --- | --- | --- | --- |
| V03 / BLOCK | B02; AC-002; M0-IF-006@r2 | 2 passed; 0 failed; 0 skipped | PASS | All declared local mechanical assertions covered by the selected observed cases; no external model is required for this owning check. Real integrated trial acceptance is separate. |
| V04 / BOUNDARY | B02; AC-002; M0-IF-006@r2 | 3 passed; 0 failed; 0 skipped | PASS | All declared local mechanical assertions covered by the selected observed cases; no external model is required for this owning check. Real integrated trial acceptance is separate. |
| V05 / BLOCK | B03; AC-003; M0-IF-006@r2 | 2 passed; 0 failed; 0 skipped | BLOCKED | Selected control assertions PASS; required approved real model/security/container or fidelity observations remain BLOCKED/NOT_RUN, with zero provider calls. The local subset cannot satisfy the whole check. |
| V06 / BOUNDARY | B03; AC-003; M0-IF-006@r2 | 3 passed; 0 failed; 0 skipped | BLOCKED | Selected control assertions PASS; required approved real model/security/container or fidelity observations remain BLOCKED/NOT_RUN, with zero provider calls. The local subset cannot satisfy the whole check. |
| V07 / BLOCK | B04; AC-004; M0-IF-006@r2 | 19 passed; 0 failed; 0 skipped | PASS | All declared local mechanical assertions covered by the selected observed cases; no external model is required for this owning check. Real integrated trial acceptance is separate. |
| V08 / BOUNDARY | B04; AC-004; M0-IF-006@r2 | 14 passed; 0 failed; 0 skipped | PASS | All declared local mechanical assertions covered by the selected observed cases; no external model is required for this owning check. Real integrated trial acceptance is separate. |
| V09 / BLOCK | B05; AC-005; M0-IF-006@r2 | 18 passed; 0 failed; 0 skipped | PASS | All declared local mechanical assertions covered by the selected observed cases; no external model is required for this owning check. Real integrated trial acceptance is separate. |
| V10 / BOUNDARY | B05; AC-005; M0-IF-006@r2 | 18 passed; 0 failed; 0 skipped | PASS | All declared local mechanical assertions covered by the selected observed cases; no external model is required for this owning check. Real integrated trial acceptance is separate. |
| V11 / BLOCK | B06; AC-006; M0-IF-006@r2 | 15 passed; 0 failed; 0 skipped | BLOCKED | Selected control assertions PASS; required approved real model/security/container or fidelity observations remain BLOCKED/NOT_RUN, with zero provider calls. The local subset cannot satisfy the whole check. |
| V12 / BOUNDARY | B06; AC-006; M0-IF-006@r2 | 5 passed; 0 failed; 0 skipped | BLOCKED | Selected control assertions PASS; required approved real model/security/container or fidelity observations remain BLOCKED/NOT_RUN, with zero provider calls. The local subset cannot satisfy the whole check. |
| V13 / BLOCK | B07; AC-007; M0-IF-006@r2 | 6 passed; 0 failed; 0 skipped | BLOCKED | Selected control assertions PASS; required approved real model/security/container or fidelity observations remain BLOCKED/NOT_RUN, with zero provider calls. The local subset cannot satisfy the whole check. |
| V14 / BOUNDARY | B07; AC-007; M0-IF-006@r2 | 7 passed; 0 failed; 0 skipped | BLOCKED | Selected control assertions PASS; required approved real model/security/container or fidelity observations remain BLOCKED/NOT_RUN, with zero provider calls. The local subset cannot satisfy the whole check. |

Counts are distinct observed cases within each check selection. Cases overlap across checks; summing rows is not a new global sample count. Their actual expected assertions are in the exact frozen test inputs, and actual results in the linked JUnit/raw records.

## Exact observed case allocation

### G01: V03

```text
tests.unit_tests.ai4research.test_m0_006::test_m0_006_b02_client_cannot_replace_contract_or_profile
tests.unit_tests.ai4research.test_m0_006::test_m0_006_b02_one_active_trial_reconciles_but_denies_second_request
```

### G02: V04

```text
tests.integration_tests.ai4research.test_intent_trial::test_actual_authentication_foreign_workspace_and_bundle_isolation
tests.integration_tests.ai4research.test_intent_trial::test_connected_acceptance_is_exact_durable_and_explicit_mock
tests.unit_tests.ai4research.test_m0_006::test_m0_006_b02_one_active_trial_reconciles_but_denies_second_request
```

### G03: V05

```text
tests.unit_tests.ai4research.test_m0_006::test_m0_006_b03_b04_suspension_after_assessment_blocks_release
tests.unit_tests.ai4research.test_m0_006::test_m0_006_b03_ready_route_never_silently_uses_mock_for_real
```

### G04: V06

```text
tests.integration_tests.ai4research.test_intent_trial::test_unavailable_provider_and_changed_pin_are_retained_without_dispatch
tests.unit_tests.ai4research.test_m0_006::test_m0_006_b03_b04_suspension_after_assessment_blocks_release
tests.unit_tests.ai4research.test_m0_006::test_m0_006_b03_ready_route_never_silently_uses_mock_for_real
```

### G05: V07

```text
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_exact_durable_acceptance_and_reconciliation
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_invalid_release_binding_denied[authority]
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_invalid_release_binding_denied[contract]
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_invalid_release_binding_denied[mandatory]
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_invalid_release_binding_denied[omitted_assessment]
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_invalid_release_binding_denied[profile]
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_invalid_release_binding_denied[subject]
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_lost_acknowledgement_reconciles_without_reexecution
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_no_success_evidence_no_release_and_blocking_decision_retained
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_subject_must_be_actual_intent_type_schema[intent_candidate-r2]
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_subject_must_be_actual_intent_type_schema[raw_assessment-intent-r2]
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_summary_pass_cannot_override_mandatory_findings[ENVIRONMENT_BLOCKED]
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_summary_pass_cannot_override_mandatory_findings[FAIL]
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_summary_pass_cannot_override_mandatory_findings[INCONCLUSIVE]
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_summary_pass_cannot_override_mandatory_findings[None]
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_transaction_failure_has_no_half_acceptance[before_release]
tests.unit_tests.ai4research.test_m0_005::test_m0_005_b02_transaction_failure_has_no_half_acceptance[before_transaction_commit]
tests.unit_tests.ai4research.test_m0_006::test_m0_006_b03_b04_suspension_after_assessment_blocks_release
tests.unit_tests.ai4research.test_m0_006::test_m0_006_b04_account_generation_change_after_verifier_blocks_release
```

### G06: V08

```text
tests.integration_tests.ai4research.test_intent_trial::test_connected_acceptance_is_exact_durable_and_explicit_mock
tests.integration_tests.ai4research.test_intent_trial::test_final_persistence_failure_preserves_exact_unreleased_evidence
tests.integration_tests.ai4research.test_intent_trial::test_raw_semantic_protocol_faults_never_release[delivery_unknown-INCONCLUSIVE]
tests.integration_tests.ai4research.test_intent_trial::test_raw_semantic_protocol_faults_never_release[malformed-INCONCLUSIVE]
tests.integration_tests.ai4research.test_intent_trial::test_raw_semantic_protocol_faults_never_release[missing_finding-INCONCLUSIVE]
tests.integration_tests.ai4research.test_intent_trial::test_raw_semantic_protocol_faults_never_release[stale-FAILED]
tests.integration_tests.ai4research.test_intent_trial::test_raw_semantic_protocol_faults_never_release[swapped-FAILED]
tests.integration_tests.ai4research.test_intent_trial::test_scripted_fidelity_challenge_refusal_preserves_candidate[candidate_injection]
tests.integration_tests.ai4research.test_intent_trial::test_scripted_fidelity_challenge_refusal_preserves_candidate[omission]
tests.integration_tests.ai4research.test_intent_trial::test_scripted_fidelity_challenge_refusal_preserves_candidate[scope_drift]
tests.integration_tests.ai4research.test_intent_trial::test_scripted_fidelity_challenge_refusal_preserves_candidate[unhandled_conflict]
tests.integration_tests.ai4research.test_intent_trial::test_scripted_fidelity_challenge_refusal_preserves_candidate[unsupported_addition]
tests.integration_tests.ai4research.test_intent_trial::test_semantic_inconclusive_blocks_and_limitations_remain_visible
tests.unit_tests.ai4research.test_m0_006::test_m0_006_b04_account_generation_change_after_verifier_blocks_release
```

### G07: V09, V10

```text
tests.integration_tests.ai4research.test_intent_trial::test_deterministic_refusal_does_not_dispatch_verifier[effects]
tests.integration_tests.ai4research.test_intent_trial::test_deterministic_refusal_does_not_dispatch_verifier[extra]
tests.integration_tests.ai4research.test_intent_trial::test_deterministic_refusal_does_not_dispatch_verifier[malformed]
tests.integration_tests.ai4research.test_intent_trial::test_deterministic_refusal_does_not_dispatch_verifier[stale]
tests.integration_tests.ai4research.test_intent_trial::test_deterministic_refusal_does_not_dispatch_verifier[swapped]
tests.integration_tests.ai4research.test_intent_trial::test_raw_semantic_protocol_faults_never_release[delivery_unknown-INCONCLUSIVE]
tests.integration_tests.ai4research.test_intent_trial::test_raw_semantic_protocol_faults_never_release[malformed-INCONCLUSIVE]
tests.integration_tests.ai4research.test_intent_trial::test_raw_semantic_protocol_faults_never_release[missing_finding-INCONCLUSIVE]
tests.integration_tests.ai4research.test_intent_trial::test_raw_semantic_protocol_faults_never_release[stale-FAILED]
tests.integration_tests.ai4research.test_intent_trial::test_raw_semantic_protocol_faults_never_release[swapped-FAILED]
tests.integration_tests.ai4research.test_intent_trial::test_scripted_fidelity_challenge_refusal_preserves_candidate[candidate_injection]
tests.integration_tests.ai4research.test_intent_trial::test_scripted_fidelity_challenge_refusal_preserves_candidate[omission]
tests.integration_tests.ai4research.test_intent_trial::test_scripted_fidelity_challenge_refusal_preserves_candidate[scope_drift]
tests.integration_tests.ai4research.test_intent_trial::test_scripted_fidelity_challenge_refusal_preserves_candidate[unhandled_conflict]
tests.integration_tests.ai4research.test_intent_trial::test_scripted_fidelity_challenge_refusal_preserves_candidate[unsupported_addition]
tests.integration_tests.ai4research.test_intent_trial::test_semantic_inconclusive_blocks_and_limitations_remain_visible
tests.integration_tests.ai4research.test_intent_trial::test_timeout_and_call_budget_short_circuit_exactly_once
tests.integration_tests.ai4research.test_intent_trial::test_unavailable_provider_and_changed_pin_are_retained_without_dispatch
```

### G08: V11

```text
tests.unit_tests.ai4research.test_headless_client::test_m0_trial_1_b09_confirmed_intake_rejection_never_retries_or_reconciles[400]
tests.unit_tests.ai4research.test_headless_client::test_m0_trial_1_b09_confirmed_intake_rejection_never_retries_or_reconciles[401]
tests.unit_tests.ai4research.test_headless_client::test_m0_trial_1_b09_confirmed_intake_rejection_never_retries_or_reconciles[403]
tests.unit_tests.ai4research.test_headless_client::test_m0_trial_1_b09_confirmed_intake_rejection_never_retries_or_reconciles[409]
tests.unit_tests.ai4research.test_headless_client::test_m0_trial_1_b09_confirmed_intake_rejection_never_retries_or_reconciles[422]
tests.unit_tests.ai4research.test_headless_client::test_m0_trial_1_b09_foreign_endpoint_never_receives_token
tests.unit_tests.ai4research.test_headless_client::test_m0_trial_1_b09_headless_halt_returns_nonzero_and_never_prompts
tests.unit_tests.ai4research.test_headless_client::test_m0_trial_1_b09_redirect_cannot_forward_credential_or_replay_post[302]
tests.unit_tests.ai4research.test_headless_client::test_m0_trial_1_b09_redirect_cannot_forward_credential_or_replay_post[307]
tests.unit_tests.ai4research.test_headless_client::test_m0_trial_1_b10_committed_server_error_reconciles_same_identity_without_post_replay[500]
tests.unit_tests.ai4research.test_headless_client::test_m0_trial_1_b10_committed_server_error_reconciles_same_identity_without_post_replay[502]
tests.unit_tests.ai4research.test_headless_client::test_m0_trial_1_b10_committed_server_error_reconciles_same_identity_without_post_replay[503]
tests.unit_tests.ai4research.test_headless_client::test_m0_trial_1_b10_committed_server_error_reconciles_same_identity_without_post_replay[504]
tests.unit_tests.ai4research.test_headless_client::test_m0_trial_1_b10_server_error_without_reconciled_run_stays_unknown_without_resubmission
tests.unit_tests.ai4research.test_headless_client::test_m0_trial_1_b10_uncertain_submit_retrieves_identity_without_resubmission
```

### G09: V12

```text
tests.integration_tests.ai4research.test_intent_trial::test_ambiguous_submission_reconciles_without_dispatch_or_changed_identity
tests.integration_tests.ai4research.test_intent_trial::test_browser_disconnect_allows_service_owned_completion
tests.integration_tests.ai4research.test_intent_trial::test_browser_disconnect_does_not_cancel_but_explicit_cancel_is_distinct
tests.integration_tests.ai4research.test_intent_trial::test_restart_pauses_unfinished_and_fresh_correction_is_a_new_run
tests.journeys.ai4research.test_intent_trial_system::test_actual_headless_cli_process_is_noninteractive_and_does_not_own_gate
```

### G10: V13

```text
tests.integration_tests.ai4research.test_intent_trial::test_connected_acceptance_is_exact_durable_and_explicit_mock
tests.integration_tests.ai4research.test_intent_trial::test_deterministic_refusal_does_not_dispatch_verifier[effects]
tests.integration_tests.ai4research.test_intent_trial::test_deterministic_refusal_does_not_dispatch_verifier[extra]
tests.integration_tests.ai4research.test_intent_trial::test_deterministic_refusal_does_not_dispatch_verifier[malformed]
tests.integration_tests.ai4research.test_intent_trial::test_deterministic_refusal_does_not_dispatch_verifier[stale]
tests.integration_tests.ai4research.test_intent_trial::test_deterministic_refusal_does_not_dispatch_verifier[swapped]
```

### G11: V14

```text
tests.integration_tests.ai4research.test_intent_trial::test_connected_acceptance_is_exact_durable_and_explicit_mock
tests.integration_tests.ai4research.test_intent_trial::test_deterministic_refusal_does_not_dispatch_verifier[effects]
tests.integration_tests.ai4research.test_intent_trial::test_deterministic_refusal_does_not_dispatch_verifier[extra]
tests.integration_tests.ai4research.test_intent_trial::test_deterministic_refusal_does_not_dispatch_verifier[malformed]
tests.integration_tests.ai4research.test_intent_trial::test_deterministic_refusal_does_not_dispatch_verifier[stale]
tests.integration_tests.ai4research.test_intent_trial::test_deterministic_refusal_does_not_dispatch_verifier[swapped]
tests.journeys.ai4research.test_intent_trial_system::test_actual_loopback_headless_accept_and_refuse_are_sequential
```

## Real prerequisites, eligibility and validity

- [Actual readiness/refusal](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-1/actual-readiness.json) records storage ready but required protected IPC/custody unavailable on Windows, no account probe/model calls, no accepted reference and explicit NOT_RUN downstream stages. The 27 locked real characterization records are NOT_RUN; no false acceptance/refusal measurement is inferred from fixtures.
- [Current eligibility validation](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-1/definition-admission-validation.json) binds the exact two pins to 68 required passing structural/contract/profile cases and six independent scoped review obligations. It proves provisional definition eligibility only; no activation occurred in this assessment and it does not prove connected semantics.
- Required live account/native model, supported protected POSIX/container IPC/custody and ordinary two-call accepted/refused journeys remain BLOCKED. No Docker executable or usable WSL Docker/Python environment was available in the observed environment. Missing prerequisites are not waived.
- Usage/cost/effective seed unavailable values remain explicit. Separate model invocations do not guarantee independent errors. Current finite challenge labels/repetitions remain unchanged; no universal numeric reliability or RSI threshold is introduced.
- Normative source/interface/runtime/profile/pin/fixture/dependency changes invalidate affected observations. This record covers the exact retained execution inputs; subsequent documentation progress changes do not change those inputs. Historical r1/full-M1 PASS is not reused; no complete stage, Node B, Brief/research graph, Phase 3 or full-M1 exit follows.
