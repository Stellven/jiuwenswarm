---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: [TASK-ID - FEATURE]
**TASK**: [Exact link] | **Spec / Plan revisions**: [Fill]
**Feature directory**: [Exact registered path]

Verification work is required as defined in spec.md and plan.md. This is the only implementation work list. Do not generate a separate implementation checklist, authorization, review or handoff card.

## Work Items
Format: `- [ ] T001 [P?] [US1] Description; block/AC/V references; actual path`.
[P] requires disjoint changes and satisfied dependencies; it is not permission to spawn agents or publish.

### Foundation / shared definitions
- [ ] T001 [US1] [Prepare required fixtures/interfaces/environment; references and paths]

### Block B01 - [Name]
- [ ] T002 [US1] [Implement bounded behavior; B01, AC-001; actual code path]
- [ ] T003 [US1] [Execute block verification V01 and retain run evidence; actual check path]

### Connected boundaries
- [ ] T004 [US1] [Execute V02 against actual connected blocks; IF reference and check path]

### System contribution
- [ ] T005 [US1] [Integrate and execute task's required system contribution, or link the system TASK work; actual path]

Replace sample items with the task's real dependency order. For the system TASK, define its candidate preparation and complete journey checks here. A checked work item means that operation was performed, not that its AC passed.

## Acceptance and Evidence Matrix
| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | B01 | T002 | V01 / T003 | NOT_RUN | None | Initial |

Add rows as needed so every required V has an unambiguous result. Every AC must be covered; every V maps back to ACs. Do not mark an AC passed when one required check is FAIL, BLOCKED, NOT_RUN or STALE.

## Dependency Order and Execution Notes
[Order, unresolved prerequisites, shared-file constraints, resumable next action. Do not duplicate the work list.]

## Current Verification Conclusion
- Candidate identity: [Exact identity or NOT_BUILT].
- Required work complete: [Derive from work items].
- Required AC/check coverage: [Derived matrix summary].
- Conclusion: [NOT_READY / IN_PROGRESS / BLOCKED / VERIFIED].
- Remaining limitations and next work IDs: [Fill or None].

VERIFIED requires all required work complete, all required checks PASS with valid evidence for the candidate and no invalidating dependency. System TASK completion does not by itself establish program completeness without TASKS source coverage.

## Evidence Invalidation
[Changed source/IF/code/configuration/test/dependency IDs, affected rows, new required runs or explicit unchanged-evidence reuse basis. Keep prior run records.]
