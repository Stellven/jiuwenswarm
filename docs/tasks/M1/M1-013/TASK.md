# TASK: M1-013 - Bounded POC construction and Builder
PRD-derived preparation. This task records the requested initial document breakdown; it does not authorize or claim an implemented runtime. Read the complete registered source, not this extraction alone.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-013 / r1 / 2026-10-01 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | Implementation executor UNASSIGNED; document preparation by Codex |
| Requested outcome and instruction/source | User request: build initial TASK and Spec Kit documents from PRD Full under Code SOP v2, filling source-supported content while reserving architecture decisions. Bounded product outcome: A researcher supplies an admitted immutable blueprint and local assets; Builder returns bounded executable artifacts and mechanical evidence for the Gate before empirical execution. |
| Included scope / exclusions | Phase 1 blueprint-to-POC assembly, local scaffolding, CodeSearch-assisted single-file patch, harness, mechanical checks and bundle. §4.9.1/.2 Phase 2 Code Mode experiment acceptance is owned by M1-019, excluded from this task's required ACs. Excludes autonomous repair, training/fine-tuning/checkpoints, production multi-file refactoring, analytical-output ownership, cloud deliverables and M2+ product integration. |
| PRD clause and architecture node references | [PRD-Full.r1](../sources/PRD-Full.r1.txt): §3.6 (all), §4.9 introduction and Phase 1/Future scope in §§4.9.1–4.9.5; §4.9.1/.2 Phase 2 allocated to M1-019; sequencing §6.7; shared §§1–2. Baseline r1 / 2026-10-01 / 177840 bytes / SHA256 2F689644EF9517378F5CF16B28FA372F011811B9F9095AA0CA6996A6A10B13D9. Architecture source/node IDs: PENDING_SOURCE. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / a8f36245a83358a606bf00f83a64b3353a41c4cd observed for document preparation; dirty-tree status is not an executable candidate identity |
| Affected code/document paths | This TASK and specs/M1-013-poc-builder/{spec.md,plan.md,tasks.md}; actual implementation/test/configuration paths PENDING_DESIGN |

No separate authorization/review/handoff card is created. Implementation and execution have not been performed by this document-preparation task.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | specs/M1-013-poc-builder/ | One registered directory for this TASK |
| spec.md | [spec](../../../../specs/M1-013-poc-builder/spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](../../../../specs/M1-013-poc-builder/plan.md) | Behavior blocks, pending technical decisions and verification design |
| tasks.md | [tasks](../../../../specs/M1-013-poc-builder/tasks.md) | Work, progress and AC-to-evidence correspondence |
| evidence/ | specs/M1-013-poc-builder/evidence/ (create actual run records when checks execute) | Actual run records/raw artifacts; none yet |
| Supporting artifacts | None generated; schemas/research/data models PENDING_DESIGN only if needed | Subordinate to TASK/spec/plan authorities |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M1-012](../M1-012/TASK.md); [M1-IF-012@r0](../M1-012/TASK.md#4-embedded-cross-module-agreements) | Admitted immutable hypothesis, protocol and acceptance criteria | Definition before contract binding; actual admitted output before real construction | B01–B04; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-008](../M1-008/TASK.md); [M1-IF-008@r0](../M1-008/TASK.md#4-embedded-cross-module-agreements) | Explicitly supplied baseline, local workspace and validation resources | Local-real resources before workspace readiness and boundary verification | B01; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-009](../M1-009/TASK.md); [M1-IF-009@r0](../M1-009/TASK.md#4-embedded-cross-module-agreements) | Research Brief framework and runtime constraints | Definition before requirements generation; pinned run brief before execution | B01–B02; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-002](../M1-002/TASK.md); [M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements) | Authorized local workspace/environment and untrusted-code boundary | Architecture definition before path/sandbox binding; real environment before checks | B01–B04; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-003](../M1-003/TASK.md); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements) | Admitted eligible capsule/runner semantics and pinned identity | Contract definition before binding; actual admitted capsule before governed invocation | All blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-004](../M1-004/TASK.md); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements) | Static Phase 1 Codex execution route and independent reviewer provision | Route definition before model binding; real configured endpoint before live model evidence | Model-dependent blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-005](../M1-005/TASK.md); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements) | Stage Evidence Bundle and durable run-bundle recording | Definition before evidence binding; actual store before boundary checks | All blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-006](../M1-006/TASK.md); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements) | Bounded governed execution and halt/advance/human-session path | Definition before runner integration; connected runtime before boundary checks, not whole system completion | All blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-007](../M1-007/TASK.md); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements) | Independent infrastructure admissibility and durable advancing decisions | Definition before handoff; actual Gate before connected release tests | Handoff and failure blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-SYSTEM](../M1-SYSTEM/TASK.md) | Integrated candidate and complete research/required offline journeys | Final system verification follows relevant block and boundary readiness; full system acceptance is not a prerequisite for independent block preparation | T012; system contribution |

Definition-time agreements are needed before dependent design; runtime provider/consumer readiness is needed before real boundary checks. Neither means waiting for every provider task's final acceptance. r0 agreements remain preliminary until architecture binds them.

## 4. Embedded cross-module agreements
### M1-IF-013 at r0
This is a **preliminary PRD semantic agreement**, not a finalized schema, API or architecture contract. Architecture source is PENDING_SOURCE; representation and implementation are PENDING_DESIGN. Advancing the IF revision must update affected consumers.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider M1-013; consumers M1-007, M1-014, M1-005, M1-SYSTEM |
| Purpose / source requirement | §3.6 (all), §4.9 introduction and Phase 1/Future scope in §§4.9.1–4.9.5; §4.9.1/.2 Phase 2 allocated to M1-019; sequencing §6.7; shared §§1–2; bounded bounded poc construction and builder handoff |
| Inputs: fields, types, units, required/optional, validation | Gate-admitted immutable Hypothesis_Blueprint.json; relevant Research_Brief.json constraints; user-supplied local baseline code and validation resources bound at intake. Mandatory semantic validation: assets exist, planned writes/tools are bounded, experiment contract is unchanged. Field names/types/units/requiredness beyond source artifact names: PENDING_DESIGN. |
| Outputs: fields, types, units, semantics, guarantees | POC_Artifact_Bundle.zip containing requirements.txt, poc_patch.py, run_benchmark.py and environment configuration, plus observable mechanical evidence and provenance for the shared Stage Evidence Bundle. Empirical execution is deferred to M1-014 after infrastructure admission. |
| States and invariants | Builder owns executable construction only; no rewriting authoritative Opportunity Card, Blueprint, Evaluation Verdict or report. Preserve baseline/data/measurement/threshold definitions; single-file POC patch, bounded harness and source-defined module restrictions. Phase 2 outputs stay outside the baseline release path. |
| Errors, timeout, retry, cancellation | Preserve observable source-defined failures and available evidence; use shared bounded execution/independent Gate semantics where applicable. No autonomous repair/unbounded retry. Exact error taxonomy, cancellation/timeout cleanup and encoding PENDING_DESIGN; no fabricated default budgets. |
| Side effects and idempotency | Writes only authorized local POC/build artifacts and invokes permitted CodeSearch/mechanical checks. No cloud deployment or baseline semantic mutation. Repeated-call identity, overwrite and crash-cleanup semantics are PENDING_DESIGN; no autonomous retries or repair loops. |
| Compatibility and migration | r0 records source semantics only. Final typed agreement/versioning rules await architecture. Any input/output/behavior change updates owner and consumer documents and invalidates impacted boundary/system evidence; do not silently weaken PRD scope. |
| Machine-readable schema / source path | None created; PENDING_DESIGN. Any generated schema must implement this IF revision rather than establish a parallel authority. |
| Provider/consumer verification responsibilities | M1-013/V01, V02, V03, V04, V05, V06 establish provider blocks; M1-013/V90 checks actual connected handoff; M1-SYSTEM owns complete integrated journeys. Consumers bind their checks to this revision after architecture, without duplicating AC authority. |
| Open agreement questions | M1-013-Q01, M1-013-Q02 in section 5; field-level schema/API/code paths remain explicitly pending. |

Consumed agreements: [M1-IF-012@r0](../M1-012/TASK.md#4-embedded-cross-module-agreements); [M1-IF-008@r0](../M1-008/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements). Registry admission/manual activation and shared infrastructure policies stay with their owning tasks.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| M1-013-Q01 / 2026-10-01 | Architecture is PENDING_SOURCE; exact schemas, operator ports, source paths, sandbox realization and command entry points are PENDING_DESIGN. | All blocks/checks and M1-IF-013 | Only affected bindings/implementation/checks; any changed source/IF invalidates affected rows and downstream evidence | UNASSIGNED; Register architecture and bind affected design; independent PRD/spec preparation continues. |
| M1-013-Q02 / 2026-10-01 | §3.6.1 assumes preinstalled packages and excludes autonomous runtime pip; §3.7.1 requires installation from requirements. Preserve both source clauses; do not choose a policy silently. | AC-001/AC-005, B01/B04, M1-IF-013 and M1-014 provisioning | Only affected bindings/implementation/checks; any changed source/IF invalidates affected rows and downstream evidence | UNASSIGNED; Confirm whether generation-only prohibition versus executor-controlled installation is intended; update affected source/spec/IF if necessary. |

Progress belongs in native tasks.md. Register material source/IF changes in the parent allocation/index and affected native artifacts; there is currently no runtime evidence to invalidate.

