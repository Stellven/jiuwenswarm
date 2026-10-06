# Verification run: RUN-20261006-RUNTIME-LOCAL-3 ? M0-003

Observed r2 trial controls on the frozen local execution candidate. This record maps retained batch observations to the owning V identifiers; it does not claim that each planned selective command was executed separately.

## Candidate and actual procedures

- Candidate HEAD `2cc0b8695d4000cc72af64eb781356697f7fd861`; 316 execution inputs; snapshot SHA256 `1a2510b1dff775a97d00a8ef9254027ec84c0bd427facb633ec19025fcbe4d85`; dirty diff SHA256 `c7284d208c81417b95c44f90fd350f433f671e00a25a543161692364707d62f4`. Source authority is immediate-plan.md SHA256 `0a7c21c2933c0be3b07e67cedaa91d2bd1706ca4382c364eb474ae616b919ec3`; exactly two CCs and current r2 interfaces.
- Compiler declaration SHA256 `9473f70eff5f4c12d9c609125493b820186303046b3cdf4a1ae9e65298f88dbe`; verifier `9390423fa32d0a00d5a88dbc05bfc8e43408e44463942dd403168a6e3f37f15e`; protected profile `613bfc40ef756b154c8376a8947e8341872168ce185c124edd1b1a3b75e90071`.
- [Shared observed record](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3.md), [exact input manifest](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3/candidate.json) and [unchanged comparison](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3/candidate-comparison.json).
- Actual combined command: [pytest.run.json](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3/pytest.run.json). Working directory: `D:/research/ai_for_research/jiuwenswarm`. Exit code 0; 329 collected, 329 PASS, zero failed/skipped, 62.76 seconds. [Raw per-case results](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3/pytest-cases.json), [JUnit](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3/pytest.xml), [stdout](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3/pytest.stdout.txt), [stderr](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3/pytest.stderr.txt).
- Current native browser command: [browser.run.json](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3/browser.run.json), [JUnit](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3/browser.xml) and [observations/screenshots](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3/browser-observations/accepted-wide.json). Exit code 0; nine collected/PASS, zero failed/skipped, 26.19 seconds; execution inputs unchanged. These are current-candidate scripted journeys; prior LOCAL-1/LOCAL-2 and FRONTEND-MOCK-2 records are not reused as current runtime acceptance.
- Actual dependencies: Windows/Python 3.11.3; real local SQLite/filesystem, process/lease and authenticated ASGI/HTTP/uvicorn/headless/browser boundaries. Provider/native protocol outputs are explicitly fixtures/ScriptedBridge. These assertions establish controls, never model fidelity or scientific truth.

- Renewed native protocol/custody observation: [native-protocol-observation.json](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3/native-protocol-observation.json). Requested identity is checked against native thread-configured model/provider/CLI; observed attributable reroute/error blocks without another turn. Completion.model means confirmed configured model, not independently observed served identity: `served_model=null` and its explicit unavailable reason are retained. One owned turn does not prove provider-internal request counts. Protected correlation identity cannot overwrite observations. Offline installed-schema/fixture checks made zero provider calls.

## Per-check observed outcomes

| Check / level | Block / AC | Actual local subset counts | Native check result | Scope and remaining requirement |
| --- | --- | --- | --- | --- |
| V01 / BLOCK | B01; AC-001; M0-IF-003@r2 | 15 passed; 0 failed; 0 skipped | PASS | All declared local mechanical assertions covered by the selected current observed cases; no external model is required for this owning check. Real integrated trial acceptance is separate. |
| V02 / BOUNDARY | B01; AC-001; M0-IF-003@r2 | 1 passed; 0 failed; 0 skipped | PASS | All declared local mechanical assertions covered by the selected current observed cases; no external model is required for this owning check. Real integrated trial acceptance is separate. |
| V03 / BLOCK | B02; AC-002; M0-IF-003@r2 | 11 passed; 0 failed; 0 skipped | PASS | All declared local mechanical assertions covered by the selected current observed cases; no external model is required for this owning check. Real integrated trial acceptance is separate. |
| V04 / BOUNDARY | B02; AC-002; M0-IF-003@r2 | 1 passed; 0 failed; 0 skipped | PASS | All declared local mechanical assertions covered by the selected current observed cases; no external model is required for this owning check. Real integrated trial acceptance is separate. |
| V05 / BLOCK | B03; AC-003; M0-IF-003@r2 | 17 passed; 0 failed; 0 skipped | BLOCKED | Selected control assertions PASS; required approved real model/security/container or fidelity observations remain BLOCKED/NOT_RUN, with zero provider calls. The local subset cannot satisfy the whole check. |
| V06 / BOUNDARY | B03; AC-003; M0-IF-003@r2 | 11 passed; 0 failed; 0 skipped | BLOCKED | Selected control assertions PASS; required approved real model/security/container or fidelity observations remain BLOCKED/NOT_RUN, with zero provider calls. The local subset cannot satisfy the whole check. |
| V07 / BLOCK | B04; AC-004; M0-IF-003@r2 | 5 passed; 0 failed; 0 skipped | PASS | All declared local mechanical assertions covered by the selected current observed cases; no external model is required for this owning check. Real integrated trial acceptance is separate. |
| V08 / BOUNDARY | B04; AC-004; M0-IF-003@r2 | 1 passed; 0 failed; 0 skipped | PASS | All declared local mechanical assertions covered by the selected current observed cases; no external model is required for this owning check. Real integrated trial acceptance is separate. |

Counts are distinct observed cases within each check selection. Cases overlap across checks; summing rows is not a new global sample count. Actual expected assertions belong to the exact frozen test inputs; actual outcomes are retained in the linked JUnit/raw records.

## Exact observed case allocation

### G01: V01

```text
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b01_authority_and_future_forms_are_rejected[<lambda>-incompatible_revision0]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b01_authority_and_future_forms_are_rejected[<lambda>-incompatible_revision1]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b01_authority_and_future_forms_are_rejected[<lambda>-incompatible_revision2]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b01_authority_and_future_forms_are_rejected[<lambda>-incompatible_revision3]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b01_authority_and_future_forms_are_rejected[<lambda>-invalid_input0]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b01_authority_and_future_forms_are_rejected[<lambda>-invalid_input1]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b01_authority_and_future_forms_are_rejected[<lambda>-invalid_input2]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b01_authority_and_future_forms_are_rejected[<lambda>-invalid_input3]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b01_authority_and_future_forms_are_rejected[<lambda>-policy_denied0]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b01_authority_and_future_forms_are_rejected[<lambda>-policy_denied1]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b01_authority_and_future_forms_are_rejected[<lambda>-policy_denied2]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b01_authority_and_future_forms_are_rejected[<lambda>-policy_denied3]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b01_authority_and_future_forms_are_rejected[<lambda>-policy_denied4]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b01_canonical_roundtrip_and_derived_markdown
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b01_unseeded_template_is_not_a_valid_declaration
```

### G02: V02

```text
tests.integration_tests.ai4research.test_m0_003_boundary::test_m0_003_b01_packaged_declaration_serialization_boundary
```

### G03: V03

```text
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b02_actual_symlink_or_reparse_is_not_a_source_pin
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b02_changed_closure_never_runs_under_old_identity[bridge.py]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b02_changed_closure_never_runs_under_old_identity[capsules.py]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b02_changed_closure_never_runs_under_old_identity[intent/compiler.prompt.md]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b02_changed_closure_never_runs_under_old_identity[intent/models.py]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b02_missing_dependency_and_swapped_role_are_blocked
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b02_path_escape_is_denied[../secret.txt]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b02_path_escape_is_denied[/etc/passwd]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b02_path_escape_is_denied[C:/secret.txt]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b02_path_escape_is_denied[intent/../secret.txt]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b02_path_escape_is_denied[intent\\compiler.prompt.md]
```

### G04: V04

```text
tests.integration_tests.ai4research.test_m0_003_boundary::test_m0_003_b02_profile_and_upstream_dependency_tamper_boundary
```

### G05: V05

```text
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_failed_or_skipped_checks_are_never_eligible[error]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_failed_or_skipped_checks_are_never_eligible[failure]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_failed_or_skipped_checks_are_never_eligible[skipped]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_incomplete_or_changed_evidence_refuses[changed_evidence]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_incomplete_or_changed_evidence_refuses[empty_report]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_incomplete_or_changed_evidence_refuses[missing_case]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_incomplete_or_changed_evidence_refuses[missing_review]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_incomplete_or_changed_evidence_refuses[review_failure]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_missing_never_synthesizes_review
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_requires_observed_cases_and_review_exact_pins
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b03_failed_admission_persistence_does_not_create_eligibility
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b03_failed_prerequisite_records_refusal_without_activation[checks_passed]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b03_failed_prerequisite_records_refusal_without_activation[profile_ready]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b03_failed_prerequisite_records_refusal_without_activation[review_passed]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b03_failed_prerequisite_records_refusal_without_activation[runtime_ready]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b03_failed_prerequisite_records_refusal_without_activation[security_ready]
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b03_fixture_admission_cannot_become_real
```

### G06: V06

```text
tests.integration_tests.ai4research.test_m0_003_boundary::test_m0_003_b03_prerequisite_and_scope_boundary
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_failed_or_skipped_checks_are_never_eligible[error]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_failed_or_skipped_checks_are_never_eligible[failure]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_failed_or_skipped_checks_are_never_eligible[skipped]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_incomplete_or_changed_evidence_refuses[changed_evidence]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_incomplete_or_changed_evidence_refuses[empty_report]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_incomplete_or_changed_evidence_refuses[missing_case]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_incomplete_or_changed_evidence_refuses[missing_review]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_incomplete_or_changed_evidence_refuses[review_failure]
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_missing_never_synthesizes_review
tests.unit_tests.ai4research.test_definition_admission::test_definition_receipt_requires_observed_cases_and_review_exact_pins
```

### G07: V07

```text
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b04_default_suspension_targets_activated_not_newest_candidate
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b04_frozen_pin_suspension_and_explicit_rollback
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b04_human_only_activation_and_append_only_history
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b04_missing_or_swapped_pin_identity_cannot_resolve
tests.unit_tests.ai4research.test_m0_003::test_m0_003_b04_standing_failure_cannot_expose_an_active_pointer
```

### G08: V08

```text
tests.integration_tests.ai4research.test_m0_003_boundary::test_m0_003_b04_restart_and_current_suspension_boundary
```

## Real prerequisites, eligibility and validity
- [Actual readiness/refusal](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3/actual-readiness.json) records storage ready but required protected IPC/custody unavailable on Windows, no account probe/model calls, no accepted reference and explicit NOT_RUN downstream stages. The 27 locked real characterization records are NOT_RUN; no false acceptance/refusal measurement is inferred from fixtures.
- [Current eligibility validation](../../M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3/definition-admission-validation.json) binds the exact two pins to 68 required passing structural/contract/profile cases and six independent scoped review obligations. It proves provisional definition eligibility only; no activation occurred in this assessment and it does not prove connected semantics.
- Required live account/native model, supported protected POSIX/container IPC/custody and ordinary two-call accepted/refused journeys remain BLOCKED. No Docker executable or usable WSL Docker/Python environment was available in the observed environment. Missing prerequisites are not waived.
- Usage/cost/effective seed unavailable values remain explicit. Separate model invocations do not guarantee independent errors. Configured native model/provider and independently served identity remain distinct; served identity is unavailable, not inferred from requested model or process environment. Current finite challenge labels/repetitions remain unchanged; no universal numeric reliability or RSI threshold is introduced.
- Normative source/interface/runtime/profile/pin/fixture/dependency changes invalidate affected observations. This record covers the exact retained execution inputs; subsequent documentation progress changes do not change those inputs. Historical r1/full-M1 PASS is not reused; no complete stage, Node B, Brief/research graph, Phase 3 or full-M1 exit follows.

- Prior LOCAL-1 and LOCAL-2 runs remain immutable history for their older closure candidates. LOCAL-3 renews current local conclusions after native configured-model/reroute and protected identity metadata corrections; their prior PASS is not reused for this candidate.
