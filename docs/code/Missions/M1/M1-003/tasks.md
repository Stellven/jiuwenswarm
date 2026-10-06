---

**Current baseline (2026-10-06):** [Latest verbatim PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) and [architecture decisions D1–D15](../../../../architecture/build-package/principles.md#decisions-and-source-amendments) apply to this task. Preserve existing AC/IF/work IDs; coding agents choose detailed schemas, APIs, code paths and checks in the native records. Delivery Phase 1 is the research baseline, Phase 2 is required offline RSI, and Phase 3 is expected dynamic integration: attempt available capabilities and record BLOCKED/INCOMPLETE dependencies; core-demo success does not complete all M1 work. Account identity/profile lifetime is distinct from local execution/workspace lifetime. Runtime evidence remains NOT_RUN.

description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M1-003 - Capability capsules and admission
**TASK**: [M1-003](TASK.md) | **Spec / Plan revisions**: r2 / r2
**Feature directory**: docs/code/Missions/M1/M1-003/

This is the only implementation work list. Current scope is documentation preparation; unchecked items describe future implementation/verification and are not application execution authorization in this pass.

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Read allocated PRD and incoming architecture, inspect existing code/callers/tests and subtree instructions, bind actual paths, effective IFs, fixtures and executable commands; all blocks/ACs; docs/code/Missions/M1/M1-003/TASK.md and docs/code/Missions/M1/M1-003/plan.md.

### Block B01 - Contract and readable representation

- [ ] T002 [US1] Implement bounded B01 behavior after its definition/runtime dependencies; AC-001, AC-007, M1-IF-003@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T003 [US1] Execute V01, V07 including all variants; retain actual candidate/source/IF identity and raw results under docs/code/Missions/M1/M1-003/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.

### Block B02 - Admission, lineage and manual standing

- [ ] T004 [US1] Implement bounded B02 behavior after its definition/runtime dependencies; AC-002, AC-003, M1-IF-003@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T005 [US1] Execute V02, V03 including all variants; retain actual candidate/source/IF identity and raw results under docs/code/Missions/M1/M1-003/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.

### Block B03 - Static eligibility and pinned binding

- [ ] T006 [US1] Implement bounded B03 behavior after its definition/runtime dependencies; AC-004, M1-IF-003@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T007 [US1] Execute V04 including all variants; retain actual candidate/source/IF identity and raw results under docs/code/Missions/M1/M1-003/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.

### Block B04 - Bounded runner and Gate handoff

- [ ] T008 [US1] Implement bounded B04 behavior after its definition/runtime dependencies; AC-005, M1-IF-003@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T009 [US1] Execute V05 including all variants; retain actual candidate/source/IF identity and raw results under docs/code/Missions/M1/M1-003/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.

### Block B05 - Implementation-only evolution admission

- [ ] T010 [US1] Implement bounded B05 behavior after its definition/runtime dependencies; AC-006, M1-IF-003@r0; application paths PENDING_DESIGN, bound by T001 without inventing a module.
- [ ] T011 [US1] Execute V06 including all variants; retain actual candidate/source/IF identity and raw results under docs/code/Missions/M1/M1-003/evidence/; check paths PENDING_DESIGN. Update each matrix row honestly.

### Block B06 - Frozen control and permissions safeguards

- [ ] T014 [US1] Implement the source-defined behavior for B06 / AC-008, after Architecture binds actual implementation paths (PENDING_DESIGN). Requirements stay in spec.md.
- [ ] T015 [US1] Execute V08 for B06/AC-008, retain candidate/source/profile/IF identities and raw evidence under docs/code/Missions/M1/M1-003/evidence/; actual check path PENDING_DESIGN. Update its matrix row.

### Connected boundaries

- [ ] T012 [US1] Connect real peers and execute V90 for all applicable ACs; real provider calls where required; integration check paths PENDING_DESIGN; preserve traces and run records in docs/code/Missions/M1/M1-003/evidence/.

### System contribution

- [ ] T013 [US1] Supply component/configuration/IF identity and current block/boundary evidence to docs/code/Missions/M1/M1-SYSTEM/TASK.md and its native matrix; participate in its actual candidate journeys.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-003@r0 | T002 | V01 / T003 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-003@r0 with actual participants | T002 | V90 / T012 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-002](spec.md#measurable-outcomes) | B02; M1-IF-003@r0 | T004 | V02 / T005 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-002](spec.md#measurable-outcomes) | B02; M1-IF-003@r0 with actual participants | T004 | V90 / T012 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-003](spec.md#measurable-outcomes) | B02; M1-IF-003@r0 | T004 | V03 / T005 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-003](spec.md#measurable-outcomes) | B02; M1-IF-003@r0 with actual participants | T004 | V90 / T012 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-004](spec.md#measurable-outcomes) | B03; M1-IF-003@r0 | T006 | V04 / T007 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-004](spec.md#measurable-outcomes) | B03; M1-IF-003@r0 with actual participants | T006 | V90 / T012 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-005](spec.md#measurable-outcomes) | B04; M1-IF-003@r0 | T008 | V05 / T009 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-005](spec.md#measurable-outcomes) | B04; M1-IF-003@r0 with actual participants | T008 | V90 / T012 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-006](spec.md#measurable-outcomes) | B05; M1-IF-003@r0 | T010 | V06 / T011 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-006](spec.md#measurable-outcomes) | B05; M1-IF-003@r0 with actual participants | T010 | V90 / T012 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-007](spec.md#measurable-outcomes) | B01; M1-IF-003@r0 | T002 | V07 / T003 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-007](spec.md#measurable-outcomes) | B01; M1-IF-003@r0 with actual participants | T002 | V90 / T012 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-008](spec.md#measurable-outcomes) | B06; M1-IF-003@r0 | T014 | V08 / T015 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-008](spec.md#measurable-outcomes) | B06; M1-IF-003@r0 with actual participants | T014 | V90 / T012 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |

## Dependency Order and Execution Notes

Foundation work binds the seven Architecture categories and independent fixtures only before affected realization/checks. Each implementation work item precedes its mapped check. T012 requires actual connected participants and effective IFs; T013 supplies/assesses candidate-matched system evidence. Document references do not require full peer-TASK completion.

Existing work IDs are preserved; new IDs are appended and ordered by behavior/dependency, not renumbered. No shared application paths or parallel code edits are assigned. Source requirements/thresholds remain in spec.md, detailed technical mechanisms in future Architecture, progress/evidence here. This documentation update executes no runtime checks, inference, installations or commits.

## Current Verification Conclusion

- Candidate identity: NOT_BUILT; existing implementation has not been assessed.
- Required work complete: No; all work remains unchecked.
- Required AC/check coverage: 8 ACs, 9 V IDs and 16 explicit AC/check rows, all NOT_RUN.
- Conclusion: NOT_READY for runtime acceptance; latest-PRD document preparation is available.
- Next work: foundation definitions/Architecture binding before dependent implementation and real checks; account/runtime/fixture availability is untested.

## Evidence Invalidation
No runtime evidence yet. Changes to PRD, effective IF, implementation/test/configuration, acceptance profiles or frozen fixtures require an impact assessment for this matrix and M1-SYSTEM. Mark affected existing evidence STALE and retain its raw records; reuse only with an explicit unchanged-behavior/input/dependency basis. Generated documents never substitute for runtime evidence.
