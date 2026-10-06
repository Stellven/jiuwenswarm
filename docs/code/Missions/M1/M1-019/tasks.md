# Tasks: M1-019 - Isolated Phase 2 experiment registration and integration

**TASK**: [TASK](TASK.md) | **Spec / Plan revisions**: r2 / r2
**Feature directory**: `docs/code/Missions/M1/M1-019/`

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Register Architecture and bind owned/consumed IF revisions, actual implementation/test paths and runtime prerequisites in TASK.md and plan.md; affected blocks B01, B02, B03, B04. Path: PENDING_DESIGN for product code.
- [ ] T002 [US1] Resolve applicable source questions; prepare independently justified fixture expectations, versions and actual check commands in plan.md. Do not choose unsourced product thresholds to complete fields.

### Block B01 - Isolation

- [ ] T010 [US1] Implement the source-defined behavior for B01 / AC-001, AC-005 at Architecture-bound paths (PENDING_DESIGN).
- [ ] T101 [US1] Execute V01 for B01/AC-001, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T105 [US1] Execute V05 for B01/AC-005, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.

### Block B02 - Compiler track

- [ ] T011 [US1] Implement the source-defined behavior for B02 / AC-002 at Architecture-bound paths (PENDING_DESIGN).
- [ ] T102 [US1] Execute V02 for B02/AC-002, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.

### Block B03 - Routing track

- [ ] T012 [US1] Implement the source-defined behavior for B03 / AC-003 at Architecture-bound paths (PENDING_DESIGN).
- [ ] T103 [US1] Execute V03 for B03/AC-003, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.

### Block B04 - Other tracks

- [ ] T013 [US1] Implement the source-defined behavior for B04 / AC-004 at Architecture-bound paths (PENDING_DESIGN).
- [ ] T104 [US1] Execute V04 for B04/AC-004, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.

### Block B05 - Approved isolated alternate verifier

- [ ] T201 [US1] Implement the source-defined behavior for B05 / AC-006, after Architecture binds actual implementation paths (PENDING_DESIGN). Requirements stay in spec.md.
- [ ] T202 [US1] Execute V06 for B05/AC-006, retain candidate/source/profile/IF identities and raw evidence under docs/code/Missions/M1/M1-019/evidence/; actual check path PENDING_DESIGN. Update its matrix row.

### Connected boundaries

- [ ] T190 [US1] Connect the actual providers/consumers and execute V90 for the resolved agreement and listed ACs; retain real boundary evidence. Code/test paths PENDING_DESIGN.

### System contribution

- [ ] T200 [US1] Supply this task's exact component/configuration/IF revisions and valid check evidence to M1-SYSTEM; optional Phase 2 work remains non-blocking.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-019@r0 | T010 | V01 / T101 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-019@r0 with actual participants | T010 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-002](spec.md#measurable-outcomes) | B02; M1-IF-019@r0 | T011 | V02 / T102 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-002](spec.md#measurable-outcomes) | B02; M1-IF-019@r0 with actual participants | T011 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-003](spec.md#measurable-outcomes) | B03; M1-IF-019@r0 | T012 | V03 / T103 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-003](spec.md#measurable-outcomes) | B03; M1-IF-019@r0 with actual participants | T012 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-004](spec.md#measurable-outcomes) | B04; M1-IF-019@r0 | T013 | V04 / T104 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-004](spec.md#measurable-outcomes) | B04; M1-IF-019@r0 with actual participants | T013 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-005](spec.md#measurable-outcomes) | B01; M1-IF-019@r0 | T010 | V05 / T105 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-005](spec.md#measurable-outcomes) | B01; M1-IF-019@r0 with actual participants | T010 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-006](spec.md#measurable-outcomes) | B05; M1-IF-019@r0 | T201 | V06 / T202 | NOT_RUN | None / NOT_BUILT | PRD r2 preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-006](spec.md#measurable-outcomes) | B05; M1-IF-019@r0 with actual participants | T201 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |

## Dependency Order and Execution Notes

Foundation work binds the seven Architecture categories and independent fixtures only before affected realization/checks. Each implementation work item precedes its mapped check. T190 requires actual connected participants and effective IFs; T200 supplies/assesses candidate-matched system evidence. Document references do not require full peer-TASK completion.

Existing work IDs are preserved; new IDs are appended and ordered by behavior/dependency, not renumbered. No shared application paths or parallel code edits are assigned. Source requirements/thresholds remain in spec.md, detailed technical mechanisms in future Architecture, progress/evidence here. This documentation update executes no runtime checks, inference, installations or commits.

## Current Verification Conclusion

- Candidate identity: NOT_BUILT; existing implementation has not been assessed.
- Required work complete: No; all work remains unchecked.
- Required AC/check coverage: 6 ACs, 7 V IDs and 12 explicit AC/check rows, all NOT_RUN.
- Conclusion: NOT_READY for runtime acceptance; latest-PRD document preparation is available.
- Next work: foundation definitions/Architecture binding before dependent implementation and real checks; account/runtime/fixture availability is untested.

## Evidence Invalidation

No prior runtime evidence exists for this new task. Changes to relevant PRD/architecture/IF behavior, prompts, code, tests, configuration or fixtures require impact assessment and rerun of affected feature/boundary/system checks. Keep old records and mark affected rows STALE; reuse requires recorded equivalence.
