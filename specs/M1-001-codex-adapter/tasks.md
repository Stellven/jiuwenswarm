---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M1-001 - Codex CLI adapter
**TASK**: [M1-001](../../docs/tasks/M1/M1-001/TASK.md) | **Spec / Plan revisions**: r1 / r1  
**Feature directory**: specs/M1-001-codex-adapter/

This is the only implementation work list. Current scope is documentation preparation; unchecked items describe future implementation/verification and are not application execution authorization in this pass.

## Work Items
### Foundation / shared definitions
- [ ] T001 [US1] Read allocated PRD and incoming architecture, inspect existing code/callers/tests and subtree instructions, bind actual paths, effective IFs, fixtures and executable commands; all blocks/ACs; docs/tasks/M1/M1-001/TASK.md and specs/M1-001-codex-adapter/plan.md.
### Block B01 - Existing adapter and native completion compatibility
- [ ] T002 [US1] Implement bounded B01 behavior after its definition/runtime dependencies; AC-001, AC-004, M1-IF-001@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T003 [US1] Execute V01, V04 including all variants; retain actual candidate/source/IF identity and raw results under specs/M1-001-codex-adapter/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.
### Block B02 - Secured local invocation context
- [ ] T004 [US1] Implement bounded B02 behavior after its definition/runtime dependencies; AC-002, M1-IF-001@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T005 [US1] Execute V02 including all variants; retain actual candidate/source/IF identity and raw results under specs/M1-001-codex-adapter/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.
### Block B03 - Provider abstraction and failure telemetry
- [ ] T006 [US1] Implement bounded B03 behavior after its definition/runtime dependencies; AC-003, M1-IF-001@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T007 [US1] Execute V03 including all variants; retain actual candidate/source/IF identity and raw results under specs/M1-001-codex-adapter/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.
### Connected boundaries
- [ ] T008 [US1] Connect real peers and execute V90 for all applicable ACs; real provider calls where required; integration check paths PENDING_DESIGN; preserve traces and run records in specs/M1-001-codex-adapter/evidence/.
### System contribution
- [ ] T009 [US1] Supply component/configuration/IF identity and current block/boundary evidence to docs/tasks/M1/M1-SYSTEM/TASK.md and its native matrix; participate in its actual candidate journeys.

## Acceptance and Evidence Matrix
| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-001@r0 | T002 | V01 / T003 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-001@r0 with actual peers | T002 | V90 / T008 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-002](spec.md#measurable-outcomes) | B02; M1-IF-001@r0 | T004 | V02 / T005 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-002](spec.md#measurable-outcomes) | B02; M1-IF-001@r0 with actual peers | T004 | V90 / T008 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-003](spec.md#measurable-outcomes) | B03; M1-IF-001@r0 | T006 | V03 / T007 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-003](spec.md#measurable-outcomes) | B03; M1-IF-001@r0 with actual peers | T006 | V90 / T008 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |
| [AC-004](spec.md#measurable-outcomes) | B01; M1-IF-001@r0 | T002 | V04 / T003 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; design, fixture and candidate not bound |
| [AC-004](spec.md#measurable-outcomes) | B01; M1-IF-001@r0 with actual peers | T002 | V90 / T008 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; stubs cannot establish this row |

## Dependency Order and Execution Notes
T001 resolves affected pending inputs; independent source/fixture descriptions continue. Each implementation item precedes its verification item. T008 follows actual connected blocks and IF definitions, not full completion of all peer TASKs. T009 links current evidence into system verification. Capsule/provider/evidence definitions avoid a runner/Gate/reviewer full-task dependency cycle.

No shared implementation paths are assigned yet; inspect before parallel code changes. Select this exact feature directory before native generation; a shared feature pointer is not a task lock. No runtime checks, application edits or commits occurred in document preparation.

## Current Verification Conclusion
- Candidate identity: NOT_BUILT for this task candidate; existing implementation was not assessed.
- Required work complete: No; future work remains unchecked.
- Required AC/check coverage: 4 ACs, 5 V IDs and 8 explicit AC/check rows, all NOT_RUN.
- Conclusion: NOT_READY for runtime acceptance; PRD document preparation populated.
- Remaining limitations and next work IDs: T001 binds architecture and actual entries; then dependency-specific work proceeds. Account/runtime availability untested; no fake evidence or PASS claims.

## Evidence Invalidation
No runtime evidence yet. Changes to PRD, effective IF, implementation/test/configuration, acceptance profiles or frozen fixtures require an impact assessment for this matrix and M1-SYSTEM. Mark affected existing evidence STALE and retain its raw records; reuse only with an explicit unchanged-behavior/input/dependency basis. Generated documents never substitute for runtime evidence.
