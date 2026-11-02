# TASK: PAS-M1-010 - World models library
TASK.md, spec.md, plan.md and tasks.md share this directory. The parent program directory holds TASKS.md.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | PAS-M1-010 / r1 / 2026-10-30 |
| Parent TASKS | [../TASKS.md](../TASKS.md) |
| Executor / collaborators | Claude Code (coding agent) for Suraj (owner) |
| Requested outcome and instruction/source | Phase 3 library "learned world models" (PRD SL-5.D, SL-5.S); TB-16; X3.4; F9; adopted PhyWorld-style law-governed rollouts |
| Included scope / exclusions | Included: world-model scoring, labeled previews, a real world model measured against physics for a declared domain. Excluded: Physics-IQ and models too large for the laptop (M2) |
| PRD clause and architecture node references | TASKS §3 rows owned by PAS-M1-010. Nodes N-LIB, E4, E5 |
| Working checkout / branch / base | NOT_STARTED |
| Affected code/document paths | PENDING_DESIGN |

**Reserved ACs (TASKS §2):** AC-001 TB-16 (physics-as-predictor scores zero error; a biased predictor scores its known bias); AC-002 X3.4 (a real world model's error against physics reported for a declared domain); AC-003 world models run only as a labeled preview (evidence level `preview`) or as a test subject; predictions are not physics results unless validated for that domain (US-SL05); AC-004 F9 cases with SIMLAB-generated law-governed rollouts; AC-005 X3.1.

No separate authorization card or review assignment is required.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-010/` | One directory for this TASK |
| spec.md / plan.md / tasks.md | Created by `$speckit-specify`, `$speckit-plan`, `$speckit-tasks` | ACs / design and procedures / work and evidence |
| evidence/ | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-010/evidence/` (not committed) | Actual runs |
| Supporting artifacts | None yet | Subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| PAS-M1-003, SIMLAB-IF-003@r1 (implementation) | Runtime contract, conformance harness, integration path | Shared contracts proven (003/AC-001, AC-002) | All |
| SIMLAB-IF-004@r1 (definition) | Call records for a world model reached through the model route | Embedded in PAS-M1-011 | AC-002 |
| A-12 (003/AC-005) | An admitted world model that fits the laptop | Admission recorded | AC-002 |

## 4. Embedded cross-module agreements
None owned: this TASK provides no cross-module interface of its own.

Consumed agreements: [SIMLAB-IF-001@r1](../PAS-M1-001/TASK.md#simlab-if-001-at-r1); [SIMLAB-IF-003@r1](../PAS-M1-003/TASK.md#simlab-if-003-at-r1); [SIMLAB-IF-004@r1](../PAS-M1-011/TASK.md#simlab-if-004-at-r1).

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| None | None | None | None | None |

Progress remains in tasks.md.
