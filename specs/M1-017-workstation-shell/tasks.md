# Tasks: M1-017 - Installable local workstation and operational surfaces

**TASK**: [TASK](../../docs/tasks/M1/M1-017/TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: `specs/M1-017-workstation-shell/`

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Register Architecture and bind owned/consumed IF revisions, actual implementation/test paths and runtime prerequisites in TASK.md and plan.md; affected blocks B01, B02, B03, B04. Path: PENDING_DESIGN for product code.
- [ ] T002 [US1] Resolve applicable source questions; prepare independently justified fixture expectations, versions and actual check commands in plan.md. Do not choose unsourced product thresholds to complete fields.

### Block B01 - Visibility

- [ ] T010 [US1] Implement the source-defined behavior for B01 / AC-001, AC-002, AC-003, AC-004 at Architecture-bound paths (PENDING_DESIGN).

### Block B02 - Bootstrap

- [ ] T011 [US1] Implement the source-defined behavior for B02 / AC-005, AC-006 at Architecture-bound paths (PENDING_DESIGN).

### Block B03 - Surfaces

- [ ] T012 [US1] Implement the source-defined behavior for B03 / AC-007, AC-008, AC-009, AC-010, AC-011 at Architecture-bound paths (PENDING_DESIGN).

### Block B04 - Scope

- [ ] T013 [US1] Implement the source-defined behavior for B04 / AC-012 at Architecture-bound paths (PENDING_DESIGN).

### Verification

- [ ] T101 [US1] Execute V01 for B01/AC-001, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T102 [US1] Execute V02 for B01/AC-002, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T103 [US1] Execute V03 for B01/AC-003, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T104 [US1] Execute V04 for B01/AC-004, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T105 [US1] Execute V05 for B02/AC-005, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T106 [US1] Execute V06 for B02/AC-006, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T107 [US1] Execute V07 for B03/AC-007, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T108 [US1] Execute V08 for B03/AC-008, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T109 [US1] Execute V09 for B03/AC-009, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T110 [US1] Execute V10 for B03/AC-010, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T111 [US1] Execute V11 for B03/AC-011, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T112 [US1] Execute V12 for B04/AC-012, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.

### Connected boundaries

- [ ] T190 [US1] Connect the actual providers/consumers and execute V90 for the resolved agreement and listed ACs; retain real boundary evidence. Code/test paths PENDING_DESIGN.

### System contribution

- [ ] T200 [US1] Supply this task's exact component/configuration/IF revisions and valid check evidence to M1-SYSTEM; optional Phase 2 work remains non-blocking.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B01 / M1-IF-017@r0 | T010 | V01 / T101 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-002](spec.md) | B01 / M1-IF-017@r0 | T010 | V02 / T102 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-003](spec.md) | B01 / M1-IF-017@r0 | T010 | V03 / T103 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-004](spec.md) | B01 / M1-IF-017@r0 | T010 | V04 / T104 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-005](spec.md) | B02 / M1-IF-017@r0 | T011 | V05 / T105 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-006](spec.md) | B02 / M1-IF-017@r0 | T011 | V06 / T106 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-007](spec.md) | B03 / M1-IF-017@r0 | T012 | V07 / T107 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-008](spec.md) | B03 / M1-IF-017@r0 | T012 | V08 / T108 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-009](spec.md) | B03 / M1-IF-017@r0 | T012 | V09 / T109 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-010](spec.md) | B03 / M1-IF-017@r0 | T012 | V10 / T110 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-011](spec.md) | B03 / M1-IF-017@r0 | T012 | V11 / T111 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-012](spec.md) | B04 / M1-IF-017@r0 | T013 | V12 / T112 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-001](spec.md) | M1-IF-017@r0 | T190 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Actual consumer wiring and completed agreement required |
| [AC-002](spec.md) | M1-IF-017@r0 | T190 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Actual consumer wiring and completed agreement required |
| [AC-003](spec.md) | M1-IF-017@r0 | T190 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Actual consumer wiring and completed agreement required |
| [AC-004](spec.md) | M1-IF-017@r0 | T190 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Actual consumer wiring and completed agreement required |
| [AC-005](spec.md) | M1-IF-017@r0 | T190 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Actual consumer wiring and completed agreement required |
| [AC-006](spec.md) | M1-IF-017@r0 | T190 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Actual consumer wiring and completed agreement required |
| [AC-007](spec.md) | M1-IF-017@r0 | T190 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Actual consumer wiring and completed agreement required |
| [AC-008](spec.md) | M1-IF-017@r0 | T190 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Actual consumer wiring and completed agreement required |
| [AC-009](spec.md) | M1-IF-017@r0 | T190 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Actual consumer wiring and completed agreement required |
| [AC-010](spec.md) | M1-IF-017@r0 | T190 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Actual consumer wiring and completed agreement required |
| [AC-011](spec.md) | M1-IF-017@r0 | T190 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Actual consumer wiring and completed agreement required |

## Dependency Order and Execution Notes

T001/T002 constrain only affected work; independent source extraction and fixture design may continue. Implement/check available blocks before connected verification, then contribute to the integrated candidate. Do not equate architecture registration, generated documents or checked work items with runtime acceptance. Definition-time and runtime dependencies remain separate as stated in TASK.md.

## Current Verification Conclusion

- Candidate identity: NOT_BUILT.
- Required work complete: No; this is a populated preparation baseline, not a product implementation.
- Required AC/check coverage: 12 ACs and 13 planned checks; all runtime results NOT_RUN.
- Conclusion: NOT_READY for runtime acceptance.
- Remaining limitations and next work IDs: Architecture/source resolution and executable binding in T001/T002; no product commands executed.

## Evidence Invalidation

No prior runtime evidence exists for this new task. Changes to relevant PRD/architecture/IF behavior, prompts, code, tests, configuration or fixtures require impact assessment and rerun of affected feature/boundary/system checks. Keep old records and mark affected rows STALE; reuse requires recorded equivalence.

