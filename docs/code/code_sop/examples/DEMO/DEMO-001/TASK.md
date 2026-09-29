# TASK: DEMO-001 - Normalize executor labels
Fictional example; implementation is not requested.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | DEMO-001 / r1 / 2026-09-29 |
| Parent TASKS | [DEMO](../TASKS.md) |
| Executor / collaborators | Unassigned example |
| Requested outcome and instruction/source | Demonstrate document structure using SOURCE-01 and SOURCE-02 |
| Included scope / exclusions | Label validation/normalization; no models, roles, storage or external services |
| PRD clause and architecture references | Inline DEMO SOURCE-01/02 r1; Validate and Normalize nodes |
| Working checkout / branch / base | NOT_STARTED |
| Affected paths | Hypothetical provider and test paths; PENDING_DESIGN until instantiated |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | ../specs/DEMO-001-label/ relative to this file | This task only |
| spec.md | [spec](../specs/DEMO-001-label/spec.md) | ACs |
| plan.md | [plan](../specs/DEMO-001-label/plan.md) | Blocks/checks |
| tasks.md | [tasks](../specs/DEMO-001-label/tasks.md) | Work/evidence |
| evidence/ | ../specs/DEMO-001-label/evidence/ when executed | Actual runs |
| Supporting artifacts | None | N/A |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| DEMO-SYSTEM/T001 | Actual consumer wiring | Needed for provider-consumer boundary execution, not block implementation | DEMO-001/V03 and T004 |

## 4. Embedded cross-module agreements
### IF-001 at r1
| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | DEMO-001 -> DEMO-SYSTEM |
| Purpose / source requirement | SOURCE-01/02 result consumed by SOURCE-03 display |
| Inputs | label: unknown value; valid only if string with nonempty trimmed content |
| Outputs | Success: status=ok and normalized_label string; invalid: status=error and code=INVALID_LABEL, with no normalized_label |
| States and invariants | Stateless; no partial success on invalid input |
| Errors, timeout, retry, cancellation | INVALID_LABEL is a normal error result; no retries; timeout/cancellation N/A for this synchronous in-process toy |
| Side effects and idempotency | No side effects; same input gives same result |
| Compatibility and migration | r1 initial agreement; any field/semantic change updates consumers and invalidates V03/system evidence |
| Machine-readable schema / source path | None; hypothetical implementation has not been created |
| Provider/consumer verification responsibilities | DEMO-001/V01,V02 verify provider; V03 connects actual consumer; DEMO-SYSTEM/V01,V02 verify full journeys |
| Open agreement questions | None within the fictional scope |

Consumed agreements: None.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| EXAMPLE-01 / 2026-09-29 | Implementation paths not bound | Plan/work items | All execution NOT_RUN | Unassigned; bind only if example is implemented |
