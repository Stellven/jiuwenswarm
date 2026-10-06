---

**Current baseline (2026-10-06):** [Latest verbatim PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) and [architecture decisions D1–D15](../../../../architecture/build-package/principles.md#decisions-and-source-amendments) apply to this task. Preserve existing AC/IF/work IDs; coding agents choose detailed schemas, APIs, code paths and checks in the native records. Delivery Phase 1 is the research baseline, Phase 2 is required offline RSI, and Phase 3 is expected dynamic integration: attempt available capabilities and record BLOCKED/INCOMPLETE dependencies; core-demo success does not complete all M1 work. Account identity/profile lifetime is distinct from local execution/workspace lifetime. Runtime evidence remains NOT_RUN.

description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M1-009 - Fixed-flow requirement and intention compilation
**TASK**: [M1-009](TASK.md) | **Spec / Plan revisions**: r2 / r2
**Feature directory**: docs/code/Missions/M1/M1-009/

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

- [ ] T091 [US1] Supply actual component/IF/configuration/fixture identities and valid check evidence to [M1-SYSTEM](../M1-SYSTEM/TASK.md); participate in that TASK's full journey checks without duplicating system acceptance.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-009@r0 | T010 | V01 / T101 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-009@r0 with actual participants | T010 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-002](spec.md#measurable-outcomes) | B01; M1-IF-009@r0 | T010 | V02 / T102 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-002](spec.md#measurable-outcomes) | B01; M1-IF-009@r0 with actual participants | T010 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-003](spec.md#measurable-outcomes) | B02; M1-IF-009@r0 | T020 | V03 / T103 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-003](spec.md#measurable-outcomes) | B02; M1-IF-009@r0 with actual participants | T020 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-004](spec.md#measurable-outcomes) | B02; M1-IF-009@r0 | T020 | V04 / T104 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-004](spec.md#measurable-outcomes) | B02; M1-IF-009@r0 with actual participants | T020 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-005](spec.md#measurable-outcomes) | B02; M1-IF-009@r0 | T020 | V05 / T105 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-005](spec.md#measurable-outcomes) | B02; M1-IF-009@r0 with actual participants | T020 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-006](spec.md#measurable-outcomes) | B02; M1-IF-009@r0 | T020 | V06 / T106 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-006](spec.md#measurable-outcomes) | B02; M1-IF-009@r0 with actual participants | T020 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-007](spec.md#measurable-outcomes) | B03; M1-IF-009@r0 | T030 | V07 / T107 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-007](spec.md#measurable-outcomes) | B03; M1-IF-009@r0 with actual participants | T030 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |
| [AC-008](spec.md#measurable-outcomes) | B03; M1-IF-009@r0 | T030 | V08 / T108 | NOT_RUN | None / NOT_BUILT | current PRD preparation; Architecture, executable fixtures and candidate not bound. |
| [AC-008](spec.md#measurable-outcomes) | B03; M1-IF-009@r0 with actual participants | T030 | V90 / T090 | NOT_RUN | None / NOT_BUILT | Real boundary not executed; no prior runtime evidence. |

## Dependency Order and Execution Notes

Foundation work binds the seven Architecture categories and independent fixtures only before affected realization/checks. Each implementation work item precedes its mapped check. T090 requires actual connected participants and effective IFs; T091 supplies/assesses candidate-matched system evidence. Document references do not require full peer-TASK completion.

Existing work IDs are preserved; new IDs are appended and ordered by behavior/dependency, not renumbered. No shared application paths or parallel code edits are assigned. Source requirements/thresholds remain in spec.md, detailed technical mechanisms in future Architecture, progress/evidence here. This documentation update executes no runtime checks, inference, installations or commits.

## Current Verification Conclusion

- Candidate identity: NOT_BUILT; existing implementation has not been assessed.
- Required work complete: No; all work remains unchecked.
- Required AC/check coverage: 8 ACs, 9 V IDs and 16 explicit AC/check rows, all NOT_RUN.
- Conclusion: NOT_READY for runtime acceptance; latest-PRD document preparation is available.
- Next work: foundation definitions/Architecture binding before dependent implementation and real checks; account/runtime/fixture availability is untested.

## Evidence Invalidation
No runtime evidence exists yet. A changed PRD clause, implemented IF revision, default/rubric/threshold, producer/consumer code, model/prompt/configuration, dependency or fixture version requires an impact assessment against the affected AC/V rows and downstream consumers/system journeys. Mark prior affected evidence STALE while retaining raw records; reuse requires a recorded equivalence basis. Documentation preparation alone does not prove application readiness.
