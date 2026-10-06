---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M1-005 - Evidence foundations and run exports
**TASK**: [M1-005](TASK.md) | **Spec / Plan revisions**: r2 / r2
**Feature directory**: docs/code/Missions/M1/M1-005/

This is the only implementation work list. Current scope is documentation preparation; unchecked items describe future implementation/verification and are not application execution authorization in this pass.

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Read allocated PRD and incoming architecture, inspect existing code/callers/tests and subtree instructions, bind actual paths, effective IFs, fixtures and executable commands; all blocks/ACs; docs/code/Missions/M1/M1-005/TASK.md and docs/code/Missions/M1/M1-005/plan.md.

### Block B01 - Agent working context separation

- [ ] T002 [US1] Implement bounded B01 behavior after its definition/runtime dependencies; AC-001, AC-006, M1-IF-005@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T003 [US1] Execute V01, V06 including all variants; retain actual candidate/source/IF identity and raw results under docs/code/Missions/M1/M1-005/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.

### Block B02 - Run and gate evidence persistence

- [ ] T004 [US1] Implement bounded B02 behavior after its definition/runtime dependencies; AC-002, AC-003, M1-IF-005@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T005 [US1] Execute V02, V03 including all variants; retain actual candidate/source/IF identity and raw results under docs/code/Missions/M1/M1-005/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.

### Block B03 - Conformance observations and scorecards

- [ ] T006 [US1] Implement bounded B03 behavior after its definition/runtime dependencies; AC-004, M1-IF-005@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T007 [US1] Execute V04 including all variants; retain actual candidate/source/IF identity and raw results under docs/code/Missions/M1/M1-005/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.

### Block B04 - Frozen actual-run exports

- [ ] T008 [US1] Implement bounded B04 behavior after its definition/runtime dependencies; AC-005, M1-IF-005@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T009 [US1] Execute V05 including all variants; retain actual candidate/source/IF identity and raw results under docs/code/Missions/M1/M1-005/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.

### Block B05 - Frozen effective run evidence

- [ ] T012 [US1] Implement the source-defined behavior for B05 / AC-007, after Architecture binds actual implementation paths (PENDING_DESIGN). Requirements stay in spec.md.
- [ ] T013 [US1] Execute V07 for B05/AC-007, retain candidate/source/profile/IF identities and raw evidence under docs/code/Missions/M1/M1-005/evidence/; actual check path PENDING_DESIGN. Update its matrix row.

### Connected boundaries

- [ ] T010 [US1] Connect real peers and execute V90 for all applicable ACs; real provider calls where required; integration check paths PENDING_DESIGN; preserve traces and run records in docs/code/Missions/M1/M1-005/evidence/.

### System contribution

- [ ] T011 [US1] Supply component/configuration/IF identity and current block/boundary evidence to docs/code/Missions/M1/M1-SYSTEM/TASK.md and its native matrix; participate in its actual candidate journeys.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-005@r0 | T002 | V01 / T003 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-005@r0 with actual participants | T002 | V90 / T010 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-002](spec.md#measurable-outcomes) | B02; M1-IF-005@r0 | T004 | V02 / T005 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-002](spec.md#measurable-outcomes) | B02; M1-IF-005@r0 with actual participants | T004 | V90 / T010 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-003](spec.md#measurable-outcomes) | B02; M1-IF-005@r0 | T004 | V03 / T005 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-003](spec.md#measurable-outcomes) | B02; M1-IF-005@r0 with actual participants | T004 | V90 / T010 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-004](spec.md#measurable-outcomes) | B03; M1-IF-005@r0 | T006 | V04 / T007 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-004](spec.md#measurable-outcomes) | B03; M1-IF-005@r0 with actual participants | T006 | V90 / T010 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-005](spec.md#measurable-outcomes) | B04; M1-IF-005@r0 | T008 | V05 / T009 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-005](spec.md#measurable-outcomes) | B04; M1-IF-005@r0 with actual participants | T008 | V90 / T010 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-006](spec.md#measurable-outcomes) | B01; M1-IF-005@r0 | T002 | V06 / T003 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-006](spec.md#measurable-outcomes) | B01; M1-IF-005@r0 with actual participants | T002 | V90 / T010 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-007](spec.md#measurable-outcomes) | B05; M1-IF-005@r0 | T012 | V07 / T013 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-007](spec.md#measurable-outcomes) | B05; M1-IF-005@r0 with actual participants | T012 | V90 / T010 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |

## Dependency Order and Execution Notes

Foundation work binds the seven Architecture categories and independent fixtures only before affected realization/checks. Each implementation work item precedes its mapped check. T010 requires actual connected participants and effective IFs; T011 supplies/assesses candidate-matched system evidence. Document references do not require full peer-TASK completion.

Existing work IDs are preserved; new IDs are appended and ordered by behavior/dependency, not renumbered. No shared application paths or parallel code edits are assigned. Source requirements/thresholds remain in spec.md, detailed technical mechanisms in future Architecture, progress/evidence here. This documentation update executes no runtime checks, inference, installations or commits.

## Current Verification Conclusion

- Candidate identity: NOT_BUILT; existing implementation has not been assessed.
- Required work complete: No; all work remains unchecked.
- Required AC/check coverage: 7 ACs, 8 V IDs and 14 explicit AC/check rows, all NOT_RUN.
- Conclusion: NOT_READY for runtime acceptance; latest-PRD document preparation is available.
- Next work: foundation definitions/Architecture binding before dependent implementation and real checks; account/runtime/fixture availability is untested.

## Evidence Invalidation
No runtime evidence yet. Changes to PRD, effective IF, implementation/test/configuration, acceptance profiles or frozen fixtures require an impact assessment for this matrix and M1-SYSTEM. Mark affected existing evidence STALE and retain its raw records; reuse only with an explicit unchanged-behavior/input/dependency basis. Generated documents never substitute for runtime evidence.
