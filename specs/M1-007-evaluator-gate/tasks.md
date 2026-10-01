---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M1-007 - Evaluator Gate and independent Verifier
**TASK**: [M1-007](../../docs/tasks/M1/M1-007/TASK.md) | **Spec / Plan revisions**: r1 / r1  
**Feature directory**: specs/M1-007-evaluator-gate/

This is the only implementation work list. Current scope is documentation preparation; unchecked items describe future implementation/verification and are not application execution authorization in this pass.

## Work Items
### Foundation / shared definitions
- [ ] T001 [US1] Read allocated PRD and incoming architecture, inspect existing code/callers/tests and subtree instructions, bind actual paths, effective IFs, fixtures and executable commands; all blocks/ACs; docs/tasks/M1/M1-007/TASK.md and specs/M1-007-evaluator-gate/plan.md.
### Block B01 - Evidence envelope and tier ordering
- [ ] T002 [US1] Implement bounded B01 behavior after its definition/runtime dependencies; AC-001, AC-019, M1-IF-007@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T003 [US1] Execute V01, V19 including all variants; retain actual candidate/source/IF identity and raw results under specs/M1-007-evaluator-gate/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.
### Block B02 - Contract and engineering conformance
- [ ] T004 [US1] Implement bounded B02 behavior after its definition/runtime dependencies; AC-002, AC-003, M1-IF-007@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T005 [US1] Execute V02, V03 including all variants; retain actual candidate/source/IF identity and raw results under specs/M1-007-evaluator-gate/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.
### Block B03 - Budget/protocol/security conformance
- [ ] T006 [US1] Implement bounded B03 behavior after its definition/runtime dependencies; AC-004, AC-005, M1-IF-007@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T007 [US1] Execute V04, V05 including all variants; retain actual candidate/source/IF identity and raw results under specs/M1-007-evaluator-gate/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.
### Block B04 - Independent semantic verification
- [ ] T008 [US1] Implement bounded B04 behavior after its definition/runtime dependencies; AC-006, M1-IF-007@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T009 [US1] Execute V06 including all variants; retain actual candidate/source/IF identity and raw results under specs/M1-007-evaluator-gate/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.
### Block B05 - Lifecycle and durable aggregation
- [ ] T010 [US1] Implement bounded B05 behavior after its definition/runtime dependencies; AC-007, AC-008, M1-IF-007@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T011 [US1] Execute V07, V08 including all variants; retain actual candidate/source/IF identity and raw results under specs/M1-007-evaluator-gate/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.
### Block B06 - Gate failure-injection boundaries
- [ ] T012 [US1] Implement bounded B06 behavior after its definition/runtime dependencies; AC-009, AC-010, AC-011, AC-012, AC-013, AC-014, AC-015, AC-016, AC-017, AC-018, M1-IF-007@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T013 [US1] Execute V09, V10, V11, V12, V13, V14, V15, V16, V17, V18 including all variants; retain actual candidate/source/IF identity and raw results under specs/M1-007-evaluator-gate/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.
### Connected boundaries
- [ ] T014 [US1] Connect real peers and execute V90 for all applicable ACs; real provider calls where required; integration check paths PENDING_DESIGN; preserve traces and run records in specs/M1-007-evaluator-gate/evidence/.
### System contribution
- [ ] T015 [US1] Supply component/configuration/IF identity and current block/boundary evidence to docs/tasks/M1/M1-SYSTEM/TASK.md and its native matrix; participate in its actual candidate journeys.

## Acceptance and Evidence Matrix
| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-007@r0 | T002 | V01 / T003 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-007@r0 with actual peers | T002 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-002](spec.md#measurable-outcomes) | B02; M1-IF-007@r0 | T004 | V02 / T005 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-002](spec.md#measurable-outcomes) | B02; M1-IF-007@r0 with actual peers | T004 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-003](spec.md#measurable-outcomes) | B02; M1-IF-007@r0 | T004 | V03 / T005 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-003](spec.md#measurable-outcomes) | B02; M1-IF-007@r0 with actual peers | T004 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-004](spec.md#measurable-outcomes) | B03; M1-IF-007@r0 | T006 | V04 / T007 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-004](spec.md#measurable-outcomes) | B03; M1-IF-007@r0 with actual peers | T006 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-005](spec.md#measurable-outcomes) | B03; M1-IF-007@r0 | T006 | V05 / T007 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-005](spec.md#measurable-outcomes) | B03; M1-IF-007@r0 with actual peers | T006 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-006](spec.md#measurable-outcomes) | B04; M1-IF-007@r0 | T008 | V06 / T009 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-006](spec.md#measurable-outcomes) | B04; M1-IF-007@r0 with actual peers | T008 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-007](spec.md#measurable-outcomes) | B05; M1-IF-007@r0 | T010 | V07 / T011 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-007](spec.md#measurable-outcomes) | B05; M1-IF-007@r0 with actual peers | T010 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-008](spec.md#measurable-outcomes) | B05; M1-IF-007@r0 | T010 | V08 / T011 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-008](spec.md#measurable-outcomes) | B05; M1-IF-007@r0 with actual peers | T010 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-009](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 | T012 | V09 / T013 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-009](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 with actual peers | T012 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-010](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 | T012 | V10 / T013 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-010](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 with actual peers | T012 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-011](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 | T012 | V11 / T013 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-011](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 with actual peers | T012 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-012](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 | T012 | V12 / T013 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-012](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 with actual peers | T012 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-013](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 | T012 | V13 / T013 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-013](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 with actual peers | T012 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-014](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 | T012 | V14 / T013 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-014](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 with actual peers | T012 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-015](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 | T012 | V15 / T013 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-015](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 with actual peers | T012 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-016](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 | T012 | V16 / T013 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-016](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 with actual peers | T012 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-017](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 | T012 | V17 / T013 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-017](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 with actual peers | T012 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-018](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 | T012 | V18 / T013 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-018](spec.md#measurable-outcomes) | B06; M1-IF-007@r0 with actual peers | T012 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-019](spec.md#measurable-outcomes) | B01; M1-IF-007@r0 | T002 | V19 / T003 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-019](spec.md#measurable-outcomes) | B01; M1-IF-007@r0 with actual peers | T002 | V90 / T014 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |

## Dependency Order and Execution Notes
T001 resolves affected pending inputs; independent source/fixture descriptions continue. Each implementation item precedes its verification item. T014 follows actual connected blocks and IF definitions, not full completion of all peer TASKs. T015 links current evidence into system verification. Capsule/provider/evidence definitions avoid a runner/Gate/reviewer full-task dependency cycle.

No shared implementation paths are assigned yet; inspect before parallel code changes. Select this exact feature directory before native generation; a shared feature pointer is not a task lock. No runtime checks, application edits or commits occurred in document preparation.

## Current Verification Conclusion
- Candidate identity: NOT_BUILT for this task candidate; existing implementation was not assessed.
- Required work complete: No; future work remains unchecked.
- Required AC/check coverage: 19 ACs, 20 V IDs and 38 explicit AC/check rows, all NOT_RUN.
- Conclusion: NOT_READY for runtime acceptance; PRD document preparation populated.
- Remaining limitations and next work IDs: T001 binds architecture and actual entries; then dependency-specific work proceeds. Account/runtime availability untested; no fake evidence or PASS claims.

## Evidence Invalidation
No runtime evidence yet. Changes to PRD, effective IF, implementation/test/configuration, acceptance profiles or frozen fixtures require an impact assessment for this matrix and M1-SYSTEM. Mark affected existing evidence STALE and retain its raw records; reuse only with an explicit unchanged-behavior/input/dependency basis. Generated documents never substitute for runtime evidence.
