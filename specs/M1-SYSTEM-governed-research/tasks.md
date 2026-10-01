# Tasks: M1-SYSTEM - Integrated M1 governed research and workstation verification

**TASK**: [TASK](../../docs/tasks/M1/M1-SYSTEM/TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: `specs/M1-SYSTEM-governed-research/`

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Register Architecture and bind owned/consumed IF revisions, actual implementation/test paths and runtime prerequisites in TASK.md and plan.md; affected blocks B01, B02, B03, B04, B05, B06, B07. Path: PENDING_DESIGN for product code.
- [ ] T002 [US1] Resolve applicable source questions; prepare independently justified fixture expectations, versions and actual check commands in plan.md. Do not choose unsourced product thresholds to complete fields.

### Block B01 - Research journeys

- [ ] T010 [US1] Assemble candidate and implement the journey verification for B01 / AC-001, AC-002 at Architecture-bound paths (PENDING_DESIGN).

### Block B02 - Governance

- [ ] T011 [US1] Assemble candidate and implement the journey verification for B02 / AC-003, AC-004, AC-005, AC-006 at Architecture-bound paths (PENDING_DESIGN).

### Block B03 - Recovery

- [ ] T012 [US1] Assemble candidate and implement the journey verification for B03 / AC-007 at Architecture-bound paths (PENDING_DESIGN).

### Block B04 - Workstation

- [ ] T013 [US1] Assemble candidate and implement the journey verification for B04 / AC-008 at Architecture-bound paths (PENDING_DESIGN).

### Block B05 - RSI

- [ ] T014 [US1] Assemble candidate and implement the journey verification for B05 / AC-009 at Architecture-bound paths (PENDING_DESIGN).

### Block B06 - Scope

- [ ] T015 [US1] Assemble candidate and implement the journey verification for B06 / AC-010 at Architecture-bound paths (PENDING_DESIGN).

### Block B07 - Traceability

- [ ] T016 [US1] Assemble candidate and implement the journey verification for B07 / AC-011 at Architecture-bound paths (PENDING_DESIGN).

### Verification

- [ ] T101 [US1] Execute V01 for B01/AC-001, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T102 [US1] Execute V02 for B01/AC-002, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T103 [US1] Execute V03 for B02/AC-003, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T104 [US1] Execute V04 for B02/AC-004, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T105 [US1] Execute V05 for B02/AC-005, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T106 [US1] Execute V06 for B02/AC-006, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T107 [US1] Execute V07 for B03/AC-007, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T108 [US1] Execute V08 for B04/AC-008, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T109 [US1] Execute V09 for B05/AC-009, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T110 [US1] Execute V10 for B06/AC-010, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T111 [US1] Execute V11 for B07/AC-011, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.

### System contribution

- [ ] T200 [US1] Assess same-candidate child evidence, run the complete system journeys, update this matrix and parent TASKS source coverage/conclusion; do not claim completion for partial scope.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B01 / participating IFs | T010 | V01 / T101 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-002](spec.md) | B01 / participating IFs | T010 | V02 / T102 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-003](spec.md) | B02 / participating IFs | T011 | V03 / T103 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-004](spec.md) | B02 / participating IFs | T011 | V04 / T104 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-005](spec.md) | B02 / participating IFs | T011 | V05 / T105 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-006](spec.md) | B02 / participating IFs | T011 | V06 / T106 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-007](spec.md) | B03 / participating IFs | T012 | V07 / T107 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-008](spec.md) | B04 / participating IFs | T013 | V08 / T108 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-009](spec.md) | B05 / participating IFs | T014 | V09 / T109 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-010](spec.md) | B06 / participating IFs | T015 | V10 / T110 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |
| [AC-011](spec.md) | B07 / participating IFs | T016 | V11 / T111 | NOT_RUN | None / NOT_BUILT | Initial PRD-derived preparation; no runtime evidence |

## Dependency Order and Execution Notes

T001/T002 constrain only affected work; independent source extraction and fixture design may continue. Implement/check available blocks before connected verification, then contribute to the integrated candidate. Do not equate architecture registration, generated documents or checked work items with runtime acceptance. Definition-time and runtime dependencies remain separate as stated in TASK.md.

## Current Verification Conclusion

- Candidate identity: NOT_BUILT.
- Required work complete: No; this is a populated preparation baseline, not a product implementation.
- Required AC/check coverage: 11 ACs and 11 planned checks; all runtime results NOT_RUN.
- Conclusion: NOT_READY for runtime acceptance.
- Remaining limitations and next work IDs: Architecture/source resolution and executable binding in T001/T002; no product commands executed.

## Evidence Invalidation

No prior runtime evidence exists for this new task. Changes to relevant PRD/architecture/IF behavior, prompts, code, tests, configuration or fixtures require impact assessment and rerun of affected feature/boundary/system checks. Keep old records and mark affected rows STALE; reuse requires recorded equivalence.

