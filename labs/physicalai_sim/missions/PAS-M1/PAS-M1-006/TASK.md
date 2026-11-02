# TASK: PAS-M1-006 - Extra forces library
TASK.md, spec.md, plan.md and tasks.md share this directory. The parent program directory holds TASKS.md.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | PAS-M1-006 / r1 / 2026-10-30 |
| Parent TASKS | [../TASKS.md](../TASKS.md) |
| Executor / collaborators | Claude Code (coding agent) for Suraj (owner) |
| Requested outcome and instruction/source | Phase 3 library "extra forces (magnets, thrust, tires)" (PRD SL-5.D); TB-12 |
| Included scope / exclusions | Included: magnetic forces, thrust, tire forces. Excluded: fluids (Future State) |
| PRD clause and architecture node references | TASKS §3 rows owned by PAS-M1-006. Nodes N-LIB, E4 |
| Working checkout / branch / base | NOT_STARTED |
| Affected code/document paths | PENDING_DESIGN |

**Reserved ACs (TASKS §2):** AC-001 TB-12 (coaxial magnets 3μ₀m₁m₂/(2πr⁴) acting on the other body; hover thrust equals weight); tire known answer PENDING_SOURCE (TASKS §6 Q-04); AC-002 X3.1.

No separate authorization card or review assignment is required.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-006/` | One directory for this TASK |
| spec.md / plan.md / tasks.md | Created by `$speckit-specify`, `$speckit-plan`, `$speckit-tasks` | ACs / design and procedures / work and evidence |
| evidence/ | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-006/evidence/` (not committed) | Actual runs |
| Supporting artifacts | None yet | Subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| PAS-M1-003, SIMLAB-IF-003@r1 (implementation) | Runtime contract, conformance harness, integration path | Shared contracts proven (003/AC-001, AC-002) | All |

## 4. Embedded cross-module agreements
None owned: this TASK provides no cross-module interface of its own.

Consumed agreements: [SIMLAB-IF-001@r1](../PAS-M1-001/TASK.md#simlab-if-001-at-r1); [SIMLAB-IF-003@r1](../PAS-M1-003/TASK.md#simlab-if-003-at-r1).

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| Q-04 / 2026-10-30 | No known-answer case for tires (TASKS §6 Q-04) | AC-001, AC-002 (tire part) | None yet | Owner supplies a case, or this TASK proposes one marked [confirm] |

Progress remains in tasks.md.
