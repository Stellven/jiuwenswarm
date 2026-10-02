---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M1-013 - Bounded POC construction and Builder
**TASK**: [M1-013](../../docs/tasks/M1/M1-013/TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: specs/M1-013-poc-builder/

This is the only future implementation work list. The current request prepares documentation; implementation and verification below have not been performed. No separate checklist, authorization, review, report or handoff card is required.

## Work Items
### Foundation / shared definitions
- [ ] T001 [US1] Register the forthcoming architecture inputs and bind affected schemas, canonical IF revisions, runtime/source/test paths and local open questions; update this TASK, spec.md and plan.md only within source-authorized scope. Independent known requirements need not wait.
- [ ] T002 [US1] Prepare versioned fixtures, actual permitted environment/model configuration and independent expected outcomes for plan checks; bind reproducible commands and prerequisites in plan.md. Fixture/test paths PENDING_DESIGN.

### Block B01 - Interpret blueprint and prepare bounded assets
- [ ] T003 [US1] Implement interpret blueprint and prepare bounded assets according to AC-001 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T004 [US1] Execute V01 for B01, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location specs/M1-013-poc-builder/evidence/.

### Block B02 - Generate patch and wire comparison harness
- [ ] T005 [US1] Implement generate patch and wire comparison harness according to AC-002, AC-003, AC-006 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T006 [US1] Execute V02, V03, V06 for B02, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location specs/M1-013-poc-builder/evidence/.

### Block B03 - Perform mechanical readiness checks
- [ ] T007 [US1] Implement perform mechanical readiness checks according to AC-004 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T008 [US1] Execute V04 for B03, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location specs/M1-013-poc-builder/evidence/.

### Block B04 - Package and submit admitted POC handoff
- [ ] T009 [US1] Implement package and submit admitted poc handoff according to AC-005 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T010 [US1] Execute V05 for B04, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location specs/M1-013-poc-builder/evidence/.

### Connected boundaries
- [ ] T011 [US1] Execute V90 with real M1-IF-013@r0 provider/consumer and required governance/evidence components after runtime readiness; preserve boundary traces and update each covered AC row in this file; exact connected-test paths PENDING_DESIGN.

### System contribution
- [ ] T012 [US1] Supply candidate identity, configuration/source/IF versions and current check evidence to [M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md); participate in its applicable integrated journeys after component readiness. System AC/evidence authority remains in its own native documents.

## Acceptance and Evidence Matrix
| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B01 | T003 | V01 / T004 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-002](spec.md) | B02 | T005 | V02 / T006 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-003](spec.md) | B02 | T005 | V03 / T006 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-004](spec.md) | B03 | T007 | V04 / T008 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-005](spec.md) | B04 | T009 | V05 / T010 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-005](spec.md) | M1-IF-013@r0; B04 | T009 | V90 / T011 | NOT_RUN | None / NOT_BUILT | Requires actual connected provider/consumer and compatible IF; no stub substitution |
| [AC-006](spec.md) | B02 | T005 | V06 / T006 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |

## Dependency Order and Execution Notes
T001 resolves only affected definitions; independent source/fixture preparation can proceed. T002 precedes checks requiring real fixtures. B01 -> B02 -> B03 -> B04. Connected boundary verification needs actual downstream/runtime wiring, not final acceptance of M1-014.
Run each block's associated check before relying on its behavior, then T011 after actual boundary readiness, then T012 for the system contribution. Do not run native feature generators concurrently against the shared checkout; select this exact feature directory before native commands. No source implementation, process launch, model call or commit is requested by these prepared work items alone.

## Current Verification Conclusion
- Candidate identity: NOT_BUILT.
- Required work complete: No; all implementation/verification work items are unchecked.
- Required AC/check coverage: 6 ACs mapped to 6 BLOCK checks and V90 BOUNDARY; every current result NOT_RUN.
- Conclusion: NOT_READY for runtime acceptance; PRD document preparation is available.
- Remaining limitations and next work IDs: T001/T002 bind architecture, precise interfaces and fixtures/commands; M1-013-Q01, M1-013-Q02 constrain only affected work. No runtime behavior or security property is established by these documents.

## Evidence Invalidation
No runtime evidence exists to reuse or invalidate. On a future source/IF/implementation/configuration/dependency/fixture change, identify affected AC/V rows and consumer/system journeys using TASKS dependencies, retain prior run records, mark affected evidence STALE and rerun the relevant checks. A document-only edit does not require unrelated application tests; runtime acceptance still requires actual candidate-matched evidence.

