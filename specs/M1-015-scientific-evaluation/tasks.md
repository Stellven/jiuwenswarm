---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M1-015 - Scientific evidence evaluation and verdict
**TASK**: [M1-015](../../docs/tasks/M1/M1-015/TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: specs/M1-015-scientific-evaluation/

This is the only future implementation work list. The current request prepares documentation; implementation and verification below have not been performed. No separate checklist, authorization, review, report or handoff card is required.

## Work Items
### Foundation / shared definitions
- [ ] T001 [US1] Register the forthcoming architecture inputs and bind affected schemas, canonical IF revisions, runtime/source/test paths and local open questions; update this TASK, spec.md and plan.md only within source-authorized scope. Independent known requirements need not wait.
- [ ] T002 [US1] Prepare versioned fixtures, actual permitted environment/model configuration and independent expected outcomes for plan checks; bind reproducible commands and prerequisites in plan.md. Fixture/test paths PENDING_DESIGN.

### Block B01 - Bind and audit evaluation evidence
- [ ] T003 [US1] Implement bind and audit evaluation evidence according to AC-001, AC-002 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T004 [US1] Execute V01, V02 for B01, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location specs/M1-015-scientific-evaluation/evidence/.

### Block B02 - Assess validity and compare frozen criteria
- [ ] T005 [US1] Implement assess validity and compare frozen criteria according to AC-003, AC-004 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T006 [US1] Execute V03, V04 for B02, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location specs/M1-015-scientific-evaluation/evidence/.

### Block B03 - Classify scientific result and record follow-ups
- [ ] T007 [US1] Implement classify scientific result and record follow-ups according to AC-005, AC-006 and the bound IF; actual code/config paths PENDING_DESIGN.
- [ ] T008 [US1] Execute V05, V06 for B03, preserve each failure/skip and raw evidence, then update its matrix rows; actual check paths PENDING_DESIGN, evidence location specs/M1-015-scientific-evaluation/evidence/.

### Connected boundaries
- [ ] T009 [US1] Execute V90 with real M1-IF-015@r0 provider/consumer and required governance/evidence components after runtime readiness; preserve boundary traces and update each covered AC row in this file; exact connected-test paths PENDING_DESIGN.

### System contribution
- [ ] T010 [US1] Supply candidate identity, configuration/source/IF versions and current check evidence to [M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md); participate in its applicable integrated journeys after component readiness. System AC/evidence authority remains in its own native documents.

## Acceptance and Evidence Matrix
| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B01 | T003 | V01 / T004 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-002](spec.md) | B01 | T003 | V02 / T004 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-003](spec.md) | B02 | T005 | V03 / T006 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-004](spec.md) | B02 | T005 | V04 / T006 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-005](spec.md) | B03 | T007 | V05 / T008 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |
| [AC-005](spec.md) | M1-IF-015@r0; B03 | T007 | V90 / T009 | NOT_RUN | None / NOT_BUILT | Requires actual connected provider/consumer and compatible IF; no stub substitution |
| [AC-006](spec.md) | B03 | T007 | V06 / T008 | NOT_RUN | None / NOT_BUILT | Initial PRD preparation; architecture and fixtures unbound |

## Dependency Order and Execution Notes
T001 resolves only affected definitions; independent source/fixture preparation can proceed. T002 precedes checks requiring real fixtures. B01 -> B02 -> B03. Deterministic checks and fixture preparation may proceed independently of live-model availability; classification cases with an unresolved rubric remain unverified.
Run each block's associated check before relying on its behavior, then T009 after actual boundary readiness, then T010 for the system contribution. Do not run native feature generators concurrently against the shared checkout; select this exact feature directory before native commands. No source implementation, process launch, model call or commit is requested by these prepared work items alone.

## Current Verification Conclusion
- Candidate identity: NOT_BUILT.
- Required work complete: No; all implementation/verification work items are unchecked.
- Required AC/check coverage: 6 ACs mapped to 6 BLOCK checks and V90 BOUNDARY; every current result NOT_RUN.
- Conclusion: NOT_READY for runtime acceptance; PRD document preparation is available.
- Remaining limitations and next work IDs: T001/T002 bind architecture, precise interfaces and fixtures/commands; M1-015-Q01, M1-015-Q02 constrain only affected work. No runtime behavior or security property is established by these documents.

## Evidence Invalidation
No runtime evidence exists to reuse or invalidate. On a future source/IF/implementation/configuration/dependency/fixture change, identify affected AC/V rows and consumer/system journeys using TASKS dependencies, retain prior run records, mark affected evidence STALE and rerun the relevant checks. A document-only edit does not require unrelated application tests; runtime acceptance still requires actual candidate-matched evidence.

