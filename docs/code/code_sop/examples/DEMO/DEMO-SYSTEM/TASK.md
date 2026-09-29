# TASK: DEMO-SYSTEM - Verify the complete label journey
Fictional example; no system has been executed.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | DEMO-SYSTEM / r1 / 2026-09-29 |
| Parent TASKS | [DEMO](../TASKS.md) |
| Executor / collaborators | Unassigned example |
| Requested outcome and instruction/source | Demonstrate consumer integration and system verification of SOURCE-03 |
| Included scope / exclusions | Request-to-display journey; no model services or persistence |
| PRD clause and architecture references | Inline DEMO SOURCE-03 r1; provider-to-display edge |
| Working checkout / branch / base | NOT_STARTED |
| Affected paths | Hypothetical consumer/entry point/system tests; PENDING_DESIGN |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | ../specs/DEMO-SYSTEM-journey/ relative to this file | This task only |
| spec.md | [spec](../specs/DEMO-SYSTEM-journey/spec.md) | System ACs |
| plan.md | [plan](../specs/DEMO-SYSTEM-journey/plan.md) | Candidate/journeys |
| tasks.md | [tasks](../specs/DEMO-SYSTEM-journey/tasks.md) | Work/evidence |
| evidence/ | ../specs/DEMO-SYSTEM-journey/evidence/ when executed | Actual runs |
| Supporting artifacts | None | N/A |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| DEMO-001/B01,B02 and IF-001@r1 | Provider and interface definition | Definition needed for wiring; working blocks needed for integration | T001,T002 |
| DEMO-001/V03 | Connected boundary evidence | Needed before final system acceptance; does not block initial wiring | T003,T004 |

## 4. Embedded cross-module agreements
Owned: None; this task consumes an existing boundary and adds no new cross-task interface.
Consumed: [DEMO-001 IF-001@r1](../DEMO-001/TASK.md#4-embedded-cross-module-agreements). Do not copy its fields here.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| EXAMPLE-01 / 2026-09-29 | No executable system candidate | All | All results NOT_RUN | Unassigned; bind actual implementation before execution |
