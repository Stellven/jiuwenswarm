# TASK: [TASK-ID] - [Title]
Copy to docs/tasks/[PROGRAM-ID]/[TASK-ID]/TASK.md. TASK is an identity and entry point. Keep acceptance, design, progress and results in the registered Spec Kit artifacts.

The logical TASK includes its Spec Kit artifacts. Physically, spec.md, plan.md and tasks.md are separate linked files, not sections copied into TASK.md.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | [Fill] |
| Parent TASKS | [Exact link] |
| Executor / collaborators | [Fill or UNASSIGNED] |
| Requested outcome and instruction/source | [Bounded purpose and source reference] |
| Included scope / exclusions | [Fill] |
| PRD clause and architecture node references | [IDs/locators and versions] |
| Working checkout / branch / base | [Fill or NOT_STARTED] |
| Affected code/document paths | [Actual paths or PENDING_DESIGN] |

No separate authorization card or review assignment is required. The requested scope applies; material scope changes are recorded below.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | [specs/TASK-ID-slug/] | One directory for this TASK |
| spec.md | [Link] | Requirements, ACs, thresholds |
| plan.md | [Link] | Technical/block design and verification procedures |
| tasks.md | [Link] | Work/progress and evidence correspondence |
| evidence/ | [Path] | Actual verification runs and raw artifacts |
| Supporting artifacts | [Paths or None] | Research, schemas, data models; subordinate to registered authorities |

Do not repeat acceptance tables, work lists or results here.

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [Fill or None] | [Fill] | [Fill] | [Fill] |

Separate definition-time dependencies from runtime/implementation dependencies. Continue independent work when one dependency is unresolved.

## 4. Embedded cross-module agreements
For every owned IF, repeat this subsection. For consumed IFs, only link the canonical definition and revision. Use None with reason when there is no boundary.

### [IF-ID] at [revision]
| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | [Fill] |
| Purpose / source requirement | [Fill] |
| Inputs: fields, types, units, required/optional, validation | [Fill] |
| Outputs: fields, types, units, semantics, guarantees | [Fill] |
| States and invariants | [Fill] |
| Errors, timeout, retry, cancellation | [Fill or justified N/A] |
| Side effects and idempotency | [Fill or justified N/A] |
| Compatibility and migration | [Version relationship and affected consumers] |
| Machine-readable schema / source path | [Link or None; implements this agreement] |
| Provider/consumer verification responsibilities | [Qualified V IDs and where defined] |
| Open agreement questions | [Fill or None] |

Consumed agreements: [Canonical TASK section links with exact IF revisions; no copied definitions].

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| [Fill or None] | [Fill] | [Fill] | [Fill] | [Fill] |

Progress remains in tasks.md. A material source or interface change updates the parent TASKS allocation/index and all affected native references.
