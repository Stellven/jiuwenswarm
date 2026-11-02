# TASK: PAS-M1-012 - AI4R journey connection
TASK.md, spec.md, plan.md and tasks.md share this directory. The parent program directory holds TASKS.md.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | PAS-M1-012 / r1 / 2026-10-30 |
| Parent TASKS | [../TASKS.md](../TASKS.md) |
| Executor / collaborators | Claude Code (coding agent) for Suraj (owner) |
| Requested outcome and instruction/source | Phase 4 "Full AI4R journey with follow-ups ... live view" (ARCH "Build order"); exits X4.1, X4.2, X4.5 (Conditional); PRD SL-9.D; TP phase 4 payload compatibility; F7 phase 4 |
| Included scope / exclusions | Included: SIMLAB capsules selected by the typed Planner, checked and gated like every capsule; question to report; overall test inside AI4R; next question with references; payload compatibility; live view if the UI owner provides it. Excluded: any modification of AI4R stages, contracts, PRD or design |
| PRD clause and architecture node references | TASKS §3 rows owned by PAS-M1-012. Nodes N-REQ, N-RCAP, E1 to E7, PL-AI4R |
| Working checkout / branch / base | NOT_STARTED |
| Affected code/document paths | PENDING_DESIGN |

**Reserved ACs (TASKS §2):** AC-001 X4.1 (every number traced to a run); AC-002 X4.2 (overall test inside AI4R, no core change); AC-003 Planner selection, gating and next question with references (SL-9.D); AC-004 X4.5 live view pause and cancel without changing the experiment (Conditional, O-07); AC-005 payload compatibility (TP phase 4 BOUNDARY); AC-006 O-03 acceptance, AI4R consumed unmodified at a pinned baseline, merges recorded and rechecked; AC-007 F7 phase 4 (new sensor, new objects, intervention, model-in-the-loop controller, branch from a checkpoint); AC-008 research-agent evaluation design from NewtonBench and the Gym-Anything creation-and-audit loop.

No separate authorization card or review assignment is required.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-012/` | One directory for this TASK |
| spec.md / plan.md / tasks.md | Created by `$speckit-specify`, `$speckit-plan`, `$speckit-tasks` | ACs / design and procedures / work and evidence |
| evidence/ | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-012/evidence/` (not committed) | Actual runs |
| Supporting artifacts | None yet | Subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| PAS-M1-002, SIMLAB-IF-002@r1 (implementation) | Capsules and thin connection | X2.6 verified | All |
| PAS-M1-003 to PAS-M1-011 (implementation) | Libraries joined to the baseline | Phase 3 exit (phase 4 is never the first connection) | AC-001, AC-002, AC-007 |
| PAS-M1-013 (implementation) | Whole-state checkpoints | X4.4 verified | AC-007 branch case |
| O-03, O-07 (definition) | Owner acceptance of SIMLAB capsules in journeys; live view in the AI4R web app | Stellven and the UI owner | AC-004, AC-006 |

## 4. Embedded cross-module agreements
None owned: this TASK provides no cross-module interface of its own.

Consumed agreements: [SIMLAB-IF-001@r1](../PAS-M1-001/TASK.md#simlab-if-001-at-r1); [SIMLAB-IF-002@r1](../PAS-M1-002/TASK.md#simlab-if-002-at-r1); [SIMLAB-IF-004@r1](../PAS-M1-011/TASK.md#simlab-if-004-at-r1).

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| Q-06 / 2026-10-30 | O-03 and O-07 (TASKS §6 Q-06) | AC-004, AC-006 | None yet | Stellven and the UI owner |
| Q-05 / 2026-10-30 | benchmark payload mapping (TASKS §6 Q-05) | AC-005 | None yet | PAS-M1-002 decides; this TASK verifies |

Progress remains in tasks.md.
