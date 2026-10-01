---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M1-009 - Fixed-flow requirement and intention compilation
**TASK**: [M1-009](../../docs/tasks/M1/M1-009/TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: specs/M1-009-requirement-compilation/

Current request covers documentation preparation only. All implementation and runtime verification below are future work, unchecked and NOT_RUN. This is the only implementation work list; no separate checklist, review, authorization or handoff card is introduced.

## Work Items
### Foundation / shared definitions
- [ ] T001 [US1] Incorporate Architecture when supplied; reconcile source-backed behavior, resolve TASK section 5 questions and advance M1-IF-009@r0 to a technically defined revision; paths: TASK.md section 4, spec.md, plan.md; affects all ACs/checks.
- [ ] T002 [US1] Bind actual producer/consumer/check paths, environment, model/configuration where applicable and versioned fixtures; define executable entries for V01–V08/V90 without changing AC thresholds; paths currently PENDING_DESIGN, recorded in plan.md.

### Block B01 - Normalize intake into the research lane
- [ ] T010 [US1] Implement normalize intake into the research lane against AC-001, AC-002 and canonical IFs; production paths PENDING_DESIGN until T001–T002 bind actual repository locations.
- [ ] T101 [US1] Execute V01 for B01/AC-001; retain expected/observed outcomes and raw artifacts in evidence/; executable check path PENDING_DESIGN in plan.md.
- [ ] T102 [US1] Execute V02 for B01/AC-002; retain expected/observed outcomes and raw artifacts in evidence/; executable check path PENDING_DESIGN in plan.md.

### Block B02 - Compile defaults, constraints and acceptance
- [ ] T020 [US1] Implement compile defaults, constraints and acceptance against AC-003, AC-004, AC-005, AC-006 and canonical IFs; production paths PENDING_DESIGN until T001–T002 bind actual repository locations.
- [ ] T103 [US1] Execute V03 for B02/AC-003; retain expected/observed outcomes and raw artifacts in evidence/; executable check path PENDING_DESIGN in plan.md.
- [ ] T104 [US1] Execute V04 for B02/AC-004; retain expected/observed outcomes and raw artifacts in evidence/; executable check path PENDING_DESIGN in plan.md.
- [ ] T105 [US1] Execute V05 for B02/AC-005; retain expected/observed outcomes and raw artifacts in evidence/; executable check path PENDING_DESIGN in plan.md.
- [ ] T106 [US1] Execute V06 for B02/AC-006; retain expected/observed outcomes and raw artifacts in evidence/; executable check path PENDING_DESIGN in plan.md.

### Block B03 - Qualify Research Brief and hand off
- [ ] T030 [US1] Implement qualify research brief and hand off against AC-007, AC-008 and canonical IFs; production paths PENDING_DESIGN until T001–T002 bind actual repository locations.
- [ ] T107 [US1] Execute V07 for B03/AC-007; retain expected/observed outcomes and raw artifacts in evidence/; executable check path PENDING_DESIGN in plan.md.
- [ ] T108 [US1] Execute V08 for B03/AC-008; retain expected/observed outcomes and raw artifacts in evidence/; executable check path PENDING_DESIGN in plan.md.

### Connected boundaries
- [ ] T090 [US1] Wire actual upstream/shared/downstream services and execute V90 for all ACs using the agreed IF revisions; real model/connector evidence where required; implementation/check paths PENDING_DESIGN, raw results in evidence/.
### System contribution
- [ ] T091 [US1] Supply actual component/IF/configuration/fixture identities and valid check evidence to [M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md); participate in that TASK's full journey checks without duplicating system acceptance.

## Acceptance and Evidence Matrix
| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md#measurable-outcomes) | B01 / M1-IF-009@r0 | T010 | V01 / T101 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-001](spec.md#measurable-outcomes) | B01 / M1-IF-009@r0 and consumed IFs | T010, T090 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Requires actual connected candidate and implementation-ready agreements |
| [AC-002](spec.md#measurable-outcomes) | B01 / M1-IF-009@r0 | T010 | V02 / T102 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-002](spec.md#measurable-outcomes) | B01 / M1-IF-009@r0 and consumed IFs | T010, T090 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Requires actual connected candidate and implementation-ready agreements |
| [AC-003](spec.md#measurable-outcomes) | B02 / M1-IF-009@r0 | T020 | V03 / T103 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-003](spec.md#measurable-outcomes) | B02 / M1-IF-009@r0 and consumed IFs | T020, T090 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Requires actual connected candidate and implementation-ready agreements |
| [AC-004](spec.md#measurable-outcomes) | B02 / M1-IF-009@r0 | T020 | V04 / T104 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-004](spec.md#measurable-outcomes) | B02 / M1-IF-009@r0 and consumed IFs | T020, T090 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Requires actual connected candidate and implementation-ready agreements |
| [AC-005](spec.md#measurable-outcomes) | B02 / M1-IF-009@r0 | T020 | V05 / T105 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-005](spec.md#measurable-outcomes) | B02 / M1-IF-009@r0 and consumed IFs | T020, T090 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Requires actual connected candidate and implementation-ready agreements |
| [AC-006](spec.md#measurable-outcomes) | B02 / M1-IF-009@r0 | T020 | V06 / T106 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-006](spec.md#measurable-outcomes) | B02 / M1-IF-009@r0 and consumed IFs | T020, T090 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Requires actual connected candidate and implementation-ready agreements |
| [AC-007](spec.md#measurable-outcomes) | B03 / M1-IF-009@r0 | T030 | V07 / T107 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-007](spec.md#measurable-outcomes) | B03 / M1-IF-009@r0 and consumed IFs | T030, T090 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Requires actual connected candidate and implementation-ready agreements |
| [AC-008](spec.md#measurable-outcomes) | B03 / M1-IF-009@r0 | T030 | V08 / T108 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-008](spec.md#measurable-outcomes) | B03 / M1-IF-009@r0 and consumed IFs | T030, T090 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Requires actual connected candidate and implementation-ready agreements |

## Dependency Order and Execution Notes
Next action for a future implementation turn: T001, limited to genuinely missing Architecture/product decisions, followed by T002. Source-backed fixture/spec elaboration may proceed independently while unrelated definitions wait. Block order follows plan.md B01 -> B02 -> B03, with each block's checks before V90. T090 depends on actual consumer wiring, not complete consumer/system TASK acceptance; T091 connects results to the system candidate. There is no invented parallel permission or shared-file lock.

## Current Verification Conclusion
- Candidate identity: NOT_BUILT.
- Required work complete: No; no implementation or runtime check work has executed.
- Required AC/check coverage: 8 ACs, 9 planned V IDs; every AC maps to its block V and V90; all matrix results NOT_RUN.
- Conclusion: NOT_READY.
- Remaining limitations and next work IDs: Architecture PENDING_SOURCE; interface/code/command bindings PENDING_DESIGN; local questions in TASK section 5; T001 then T002. No evidence files are fabricated to fill the register.

## Evidence Invalidation
No runtime evidence exists yet. A changed PRD clause, implemented IF revision, default/rubric/threshold, producer/consumer code, model/prompt/configuration, dependency or fixture version requires an impact assessment against the affected AC/V rows and downstream consumers/system journeys. Mark prior affected evidence STALE while retaining raw records; reuse requires a recorded equivalence basis. Documentation preparation alone does not prove application readiness.

