---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M1-018 - Offline implementation-only capsule improvement
**TASK**: [M1-018](../../docs/tasks/M1/M1-018/TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: specs/M1-018-offline-rsi/

This is the only future implementation work list. The current request prepares documentation; implementation and verification below have not been performed. No separate checklist, authorization, review, report or handoff card is required.

## Work Items
### Foundation / shared definitions
- [ ] T001 [US1] Register the forthcoming architecture inputs and bind affected schemas, canonical IF revisions, runtime/source/test paths and local open questions; update this TASK, spec.md and plan.md only within source-authorized scope. Independent known requirements need not wait.
- [ ] T002 [US1] Prepare versioned fixtures, actual permitted environment/model configuration and independent expected outcomes for plan checks; bind reproducible commands and prerequisites in plan.md. Fixture/test paths PENDING_DESIGN.

### Block B01 - Enforce mutation eligibility and immutable boundaries
- [ ] T003 [US1] Implement enforce mutation eligibility and immutable boundaries according to AC-007 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T004 [US1] Execute V07 for B01, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location specs/M1-018-offline-rsi/evidence/.

### Block B02 - Prepare splits and enforce baseline headroom
- [ ] T005 [US1] Implement prepare splits and enforce baseline headroom according to AC-008 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T006 [US1] Execute V08 for B02, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location specs/M1-018-offline-rsi/evidence/.

### Block B03 - Run blind bounded oracle evaluations
- [ ] T007 [US1] Implement run blind bounded oracle evaluations according to AC-009 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T008 [US1] Execute V09 for B03, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location specs/M1-018-offline-rsi/evidence/.

### Block B04 - Generate and replay compatible implementation children
- [ ] T009 [US1] Implement generate and replay compatible implementation children according to AC-001, AC-003, AC-004 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T010 [US1] Execute V01, V03, V04 for B04, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location specs/M1-018-offline-rsi/evidence/.

### Block B05 - Apply frozen scoring and resource observations
- [ ] T011 [US1] Implement apply frozen scoring and resource observations according to AC-002, AC-005 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T012 [US1] Execute V02, V05 for B05, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location specs/M1-018-offline-rsi/evidence/.

### Block B06 - Preserve lineage and export inactive candidates
- [ ] T013 [US1] Implement preserve lineage and export inactive candidates according to AC-006 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T014 [US1] Execute V06 for B06, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location specs/M1-018-offline-rsi/evidence/.

### Connected boundaries
- [ ] T015 [US1] Execute V90 with real M1-IF-018@r0 provider/consumer and required governance/evidence components after runtime readiness; preserve boundary traces and update each covered AC row in this file; exact connected-test paths PENDING_DESIGN.

### System contribution
- [ ] T016 [US1] Supply candidate identity, configuration/source/IF versions and current check evidence to [M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md); participate in its applicable integrated journeys after component readiness. System AC/evidence authority remains in its own native documents.

## Acceptance and Evidence Matrix
| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B04 | T009 | V01 / T010 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-002](spec.md) | B05 | T011 | V02 / T012 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-003](spec.md) | B04 | T009 | V03 / T010 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-004](spec.md) | B04 | T009 | V04 / T010 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-005](spec.md) | B05 | T011 | V05 / T012 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-006](spec.md) | B06 | T013 | V06 / T014 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-007](spec.md) | B01 | T003 | V07 / T004 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-008](spec.md) | B02 | T005 | V08 / T006 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-009](spec.md) | B03 | T007 | V09 / T008 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-009](spec.md) | M1-IF-018@r0; B03 | T007 | V90 / T015 | NOT_RUN | None / NOT_BUILT | Requires actual connected provider/consumer and compatible IF; no stub substitution |

## Dependency Order and Execution Notes
T001 resolves only affected definitions; independent source/fixture preparation can proceed. T002 precedes checks requiring real fixtures. B01 permission/frozen-boundary definition and B02 seeded-manifest preparation may proceed independently; B03 real oracle/isolation and B04 compatible proposal generation depend on those definitions. B05 scores B03/B04 outcomes; B06 retains attempts/lineage and submits inactive candidates. No final M1 acceptance dependency is introduced.
Run each block's associated check before relying on its behavior, then T015 after actual boundary readiness, then T016 for the system contribution. Do not run native feature generators concurrently against the shared checkout; select this exact feature directory before native commands. No source implementation, process launch, model call or commit is requested by these prepared work items alone.

## Current Verification Conclusion
- Candidate identity: NOT_BUILT.
- Required work complete: No; all implementation/verification work items are unchecked.
- Required AC/check coverage: 9 ACs mapped to 9 BLOCK checks and V90 BOUNDARY; every current result NOT_RUN.
- Conclusion: NOT_READY for runtime acceptance; PRD document preparation is available.
- Remaining limitations and next work IDs: T001/T002 bind architecture, precise interfaces and fixtures/commands; M1-018-Q01, M1-018-Q02, M1-018-Q03 constrain only affected work. No runtime behavior or security property is established by these documents.

## Evidence Invalidation
No runtime evidence exists to reuse or invalidate. On a future source/IF/implementation/configuration/dependency/fixture change, identify affected AC/V rows and consumer/system journeys using TASKS dependencies, retain prior run records, mark affected evidence STALE and rerun the relevant checks. A document-only edit does not require unrelated application tests; runtime acceptance still requires actual candidate-matched evidence.

