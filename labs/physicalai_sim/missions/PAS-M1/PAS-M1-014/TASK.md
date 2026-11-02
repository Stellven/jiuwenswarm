# TASK: PAS-M1-014 - First research runs
TASK.md, spec.md, plan.md and tasks.md share this directory. The parent program directory holds TASKS.md.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | PAS-M1-014 / r1 / 2026-10-30 |
| Parent TASKS | [../TASKS.md](../TASKS.md) |
| Executor / collaborators | Claude Code (coding agent) for Suraj (owner) |
| Requested outcome and instruction/source | Phase 5 "Hypothesis-register candidates end to end" (ARCH "Build order"); exit X5.1; F4 held-out set |
| Included scope / exclusions | Included: five register candidates frozen with their selection rule before the campaign; held-out F4 cases on a private volume; capability gaps for bespoke core changes. Excluded: training, M2 subjects |
| PRD clause and architecture node references | TASKS §3 rows owned by PAS-M1-014. Nodes E1 to E7 |
| Working checkout / branch / base | NOT_STARTED |
| Affected code/document paths | PENDING_DESIGN |

**Reserved ACs (TASKS §2):** AC-001 X5.1 (five candidates attempted; at least [confirm: 3] complete end to end with valid checks; negative or null findings count; blocked and invalid reported separately; a held-out case that guides a fix is recorded and retired); AC-002 F4 held-out set never used during development (B03, B12); AC-003 a request needing a bespoke core change is recorded as a capability gap; AC-004 ContactNets/Acosta and PhyWorld-style candidates with licenses recorded; AC-005 phase 5 snapshot and completion report.

No separate authorization card or review assignment is required.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-014/` | One directory for this TASK |
| spec.md / plan.md / tasks.md | Created by `$speckit-specify`, `$speckit-plan`, `$speckit-tasks` | ACs / design and procedures / work and evidence |
| evidence/ | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-014/evidence/` (not committed) | Actual runs |
| Supporting artifacts | None yet | Subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| PAS-M1-012, PAS-M1-013 (implementation) | Full journey, checkpoints, operations | Phase 4 exit | All |
| Hypothesis register (definition) | Candidate pool | Registered (TASKS §1) | AC-001, AC-002 |

## 4. Embedded cross-module agreements
None owned: this TASK provides no cross-module interface of its own.

Consumed agreements: [SIMLAB-IF-001@r1](../PAS-M1-001/TASK.md#simlab-if-001-at-r1); [SIMLAB-IF-002@r1](../PAS-M1-002/TASK.md#simlab-if-002-at-r1); [SIMLAB-IF-004@r1](../PAS-M1-011/TASK.md#simlab-if-004-at-r1).

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| Q-01 / 2026-10-30 | Research value [confirm: 3 of 5] (TASKS §6 Q-01) | AC-001 | None yet | Owner confirms |

Progress remains in tasks.md.
