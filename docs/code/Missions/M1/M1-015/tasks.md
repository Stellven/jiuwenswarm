---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M1-015 - Scientific evidence evaluation and verdict
**TASK**: [M1-015](TASK.md) | **Spec / Plan revisions**: r2 / r2
**Feature directory**: docs/code/Missions/M1/M1-015/

This is the only future implementation work list. The current request prepares documentation; implementation and verification below have not been performed. No separate checklist, authorization, review, report or handoff card is required.

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Register the forthcoming architecture inputs and bind affected schemas, canonical IF revisions, runtime/source/test paths and local open questions; update this TASK, spec.md and plan.md only within source-authorized scope. Independent known requirements need not wait.
- [ ] T002 [US1] Prepare versioned fixtures, actual permitted environment/model configuration and independent expected outcomes for plan checks; bind reproducible commands and prerequisites in plan.md. Fixture/test paths PENDING_DESIGN.

### Block B01 - Bind and audit evaluation evidence

- [ ] T003 [US1] Implement bind and audit evaluation evidence according to AC-001, AC-002 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T004 [US1] Execute V01, V02 for B01, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location docs/code/Missions/M1/M1-015/evidence/.

### Block B02 - Assess validity and compare frozen criteria

- [ ] T005 [US1] Implement assess validity and compare frozen criteria according to AC-003, AC-004 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T006 [US1] Execute V03, V04 for B02, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location docs/code/Missions/M1/M1-015/evidence/.

### Block B03 - Classify scientific result and record follow-ups

- [ ] T007 [US1] Implement classify scientific result and record follow-ups according to AC-005, AC-006 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T008 [US1] Execute V05, V06 for B03, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location docs/code/Missions/M1/M1-015/evidence/.

### Connected boundaries

- [ ] T009 [US1] Execute V90 with real M1-IF-015@r0 provider/consumer and required governance/evidence components after runtime readiness; preserve boundary traces and update each covered AC row in this file; exact connected-test paths PENDING_DESIGN.

### System contribution

- [ ] T010 [US1] Supply candidate identity, configuration/source/IF versions and current check evidence to [M1-SYSTEM](../M1-SYSTEM/TASK.md); participate in its applicable integrated journeys after component readiness. System AC/evidence authority remains in its own native documents.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-015@r0 | T003 | V01 / T004 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-002](spec.md#measurable-outcomes) | B01; M1-IF-015@r0 | T003 | V02 / T004 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-003](spec.md#measurable-outcomes) | B02; M1-IF-015@r0 | T005 | V03 / T006 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-004](spec.md#measurable-outcomes) | B02; M1-IF-015@r0 | T005 | V04 / T006 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-004](spec.md#measurable-outcomes) | B02; M1-IF-015@r0 with actual participants | T005 | V90 / T009 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-005](spec.md#measurable-outcomes) | B03; M1-IF-015@r0 | T007 | V05 / T008 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-005](spec.md#measurable-outcomes) | B03; M1-IF-015@r0 with actual participants | T007 | V90 / T009 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-006](spec.md#measurable-outcomes) | B03; M1-IF-015@r0 | T007 | V06 / T008 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |

## Dependency Order and Execution Notes

Foundation work binds the seven Architecture categories and independent fixtures only before affected realization/checks. Each implementation work item precedes its mapped check. T009 requires actual connected participants and effective IFs; T010 supplies/assesses candidate-matched system evidence. Document references do not require full peer-TASK completion.

Existing work IDs are preserved; new IDs are appended and ordered by behavior/dependency, not renumbered. No shared application paths or parallel code edits are assigned. Source requirements/thresholds remain in spec.md, detailed technical mechanisms in future Architecture, progress/evidence here. This documentation update executes no runtime checks, inference, installations or commits.

## Current Verification Conclusion

- Candidate identity: NOT_BUILT; existing implementation has not been assessed.
- Required work complete: No; all work remains unchecked.
- Required AC/check coverage: 6 ACs, 7 V IDs and 8 explicit AC/check rows, all NOT_RUN.
- Conclusion: NOT_READY for runtime acceptance; latest-PRD document preparation is available.
- Next work: foundation definitions/Architecture binding before dependent implementation and real checks; account/runtime/fixture availability is untested.

## Evidence Invalidation
No runtime evidence exists to reuse or invalidate. On a future source/IF/implementation/configuration/dependency/fixture change, identify affected AC/V rows and consumer/system journeys using TASKS dependencies, retain prior run records, mark affected evidence STALE and rerun the relevant checks. A document-only edit does not require unrelated application tests; runtime acceptance still requires actual candidate-matched evidence.
