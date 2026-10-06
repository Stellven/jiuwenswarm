# Tasks: M1-002 - Local configuration, identity and execution boundaries

**Current baseline (2026-10-06):** [Latest verbatim PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) and [architecture decisions D1–D15](../../../../architecture/build-package/principles.md#decisions-and-source-amendments) apply to this task. Preserve existing AC/IF/work IDs; coding agents choose detailed schemas, APIs, code paths and checks in the native records. Delivery Phase 1 is the research baseline, Phase 2 is required offline RSI, and Phase 3 is expected dynamic integration: attempt available capabilities and record BLOCKED/INCOMPLETE dependencies; core-demo success does not complete all M1 work. Account identity/profile lifetime is distinct from local execution/workspace lifetime. Runtime evidence remains NOT_RUN.


**TASK**: [TASK](TASK.md) | **Spec / Plan revisions**: r2 / r2
**Feature directory**: `docs/code/Missions/M1/M1-002/`

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Register Architecture and bind owned/consumed IF revisions, actual implementation/test paths and runtime prerequisites in TASK.md and plan.md; affected blocks B01, B02, B03, B04. Path: PENDING_DESIGN for product code.
- [ ] T002 [US1] Resolve applicable source questions; prepare independently justified fixture expectations, versions and actual check commands in plan.md. Do not choose unsourced product thresholds to complete fields.

### Block B01 - Configuration

- [ ] T010 [US1] Implement the source-defined behavior for B01 / AC-001, AC-004, AC-005, AC-006 at Architecture-bound paths (PENDING_DESIGN).
- [ ] T101 [US1] Execute V01 for B01/AC-001, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T104 [US1] Execute V04 for B01/AC-004, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T105 [US1] Execute V05 for B01/AC-005, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T106 [US1] Execute V06 for B01/AC-006, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.

### Block B02 - Security

- [ ] T011 [US1] Implement the source-defined behavior for B02 / AC-002, AC-003 at Architecture-bound paths (PENDING_DESIGN).
- [ ] T102 [US1] Execute V02 for B02/AC-002, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.
- [ ] T103 [US1] Execute V03 for B02/AC-003, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.

### Block B03 - Budgets

- [ ] T012 [US1] Implement the source-defined behavior for B03 / AC-007 at Architecture-bound paths (PENDING_DESIGN).
- [ ] T107 [US1] Execute V07 for B03/AC-007, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.

### Block B04 - Scope

- [ ] T013 [US1] Implement the source-defined behavior for B04 / AC-008 at Architecture-bound paths (PENDING_DESIGN).
- [ ] T108 [US1] Execute V08 for B04/AC-008, retain raw artifacts and evidence/RUN-ID.md, then update its matrix row. Actual check path PENDING_DESIGN.

### Block B05 - Frozen evaluation configuration

- [ ] T201 [US1] Implement the source-defined behavior for B05 / AC-009, after Architecture binds actual implementation paths (PENDING_DESIGN). Requirements stay in spec.md.
- [ ] T202 [US1] Execute V09 for B05/AC-009, retain candidate/source/profile/IF identities and raw evidence under docs/code/Missions/M1/M1-002/evidence/; actual check path PENDING_DESIGN. Update its matrix row.

### Block B06 - Ablation validity

- [ ] T203 [US1] Implement the source-defined behavior for B06 / AC-010, after Architecture binds actual implementation paths (PENDING_DESIGN). Requirements stay in spec.md.
- [ ] T204 [US1] Execute V10 for B06/AC-010, retain candidate/source/profile/IF identities and raw evidence under docs/code/Missions/M1/M1-002/evidence/; actual check path PENDING_DESIGN. Update its matrix row.

### Connected boundaries

- [ ] T190 [US1] Connect the actual providers/consumers and execute V90 for the resolved agreement and listed ACs; retain real boundary evidence. Code/test paths PENDING_DESIGN.

### System contribution

- [ ] T200 [US1] Supply this task's exact component/configuration/IF revisions and valid check evidence to M1-SYSTEM; optional Phase 3 work remains non-blocking.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-002@r0 | T010 | V01 / T101 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-002](spec.md#measurable-outcomes) | B02; M1-IF-002@r0 | T011 | V02 / T102 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-002](spec.md#measurable-outcomes) | B02; M1-IF-002@r0 with actual participants | T011 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-003](spec.md#measurable-outcomes) | B02; M1-IF-002@r0 | T011 | V03 / T103 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-003](spec.md#measurable-outcomes) | B02; M1-IF-002@r0 with actual participants | T011 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-004](spec.md#measurable-outcomes) | B01; M1-IF-002@r0 | T010 | V04 / T104 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-005](spec.md#measurable-outcomes) | B01; M1-IF-002@r0 | T010 | V05 / T105 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-005](spec.md#measurable-outcomes) | B01; M1-IF-002@r0 with actual participants | T010 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-006](spec.md#measurable-outcomes) | B01; M1-IF-002@r0 | T010 | V06 / T106 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-006](spec.md#measurable-outcomes) | B01; M1-IF-002@r0 with actual participants | T010 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-007](spec.md#measurable-outcomes) | B03; M1-IF-002@r0 | T012 | V07 / T107 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-007](spec.md#measurable-outcomes) | B03; M1-IF-002@r0 with actual participants | T012 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-008](spec.md#measurable-outcomes) | B04; M1-IF-002@r0 | T013 | V08 / T108 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-009](spec.md#measurable-outcomes) | B05; M1-IF-002@r0 | T201 | V09 / T202 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-009](spec.md#measurable-outcomes) | B05; M1-IF-002@r0 with actual participants | T201 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-010](spec.md#measurable-outcomes) | B06; M1-IF-002@r0 | T203 | V10 / T204 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-010](spec.md#measurable-outcomes) | B06; M1-IF-002@r0 with actual participants | T203 | V90 / T190 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |

## Dependency Order and Execution Notes

Foundation work binds the seven Architecture categories and independent fixtures only before affected realization/checks. Each implementation work item precedes its mapped check. T190 requires actual connected participants and effective IFs; T200 supplies/assesses candidate-matched system evidence. Document references do not require full peer-TASK completion.

Existing work IDs are preserved; new IDs are appended and ordered by behavior/dependency, not renumbered. No shared application paths or parallel code edits are assigned. Source requirements/thresholds remain in spec.md, detailed technical mechanisms in future Architecture, progress/evidence here. This documentation update executes no runtime checks, inference, installations or commits.

## Current Verification Conclusion

- Candidate identity: NOT_BUILT; existing implementation has not been assessed.
- Required work complete: No; all work remains unchecked.
- Required AC/check coverage: 10 ACs, 11 V IDs and 17 explicit AC/check rows, all NOT_RUN.
- Conclusion: NOT_READY for runtime acceptance; latest-PRD document preparation is available.
- Next work: foundation definitions/Architecture binding before dependent implementation and real checks; account/runtime/fixture availability is untested.

## Evidence Invalidation

No prior runtime evidence exists for this new task. Changes to relevant PRD/architecture/IF behavior, prompts, code, tests, configuration or fixtures require impact assessment and rerun of affected feature/boundary/system checks. Keep old records and mark affected rows STALE; reuse requires recorded equivalence.

Current D6/D12 alignment: one local Docker/Compose application service is supported, with loopback authentication, protected model IPC and persistent state outside the replaceable image. Stable product-user identity and durable profiles are separate from execution identity and workspace deletion. Coding agents choose the actual configuration and confinement mechanisms; packaging alone is not POC isolation.
