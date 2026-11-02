# TASK: PAS-M1-013 - Scale, whole-state checkpoints and operations
TASK.md, spec.md, plan.md and tasks.md share this directory. The parent program directory holds TASKS.md.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | PAS-M1-013 / r1 / 2026-10-30 |
| Parent TASKS | [../TASKS.md](../TASKS.md) |
| Executor / collaborators | Claude Code (coding agent) for Suraj (owner) |
| Requested outcome and instruction/source | Phase 4 "whole-state checkpoints, concurrency, recovery" (ARCH "Build order"); exits X4.3, X4.4; PRD SL-7, SL-10.D; ARCHC flow 5; F6; IF-001 phase 4 operations |
| Included scope / exclusions | Included: declared-workload scale run; killed-worker recovery without duplicates; whole-state checkpoints at quiescent points and branching; concurrency; crash recovery; `pause`, `resume`, `stream`; `operations` check group; MuJoCo Warp speed records; phase 4 report. Excluded: scale beyond the laptop (M2) |
| PRD clause and architecture node references | TASKS §3 rows owned by PAS-M1-013. Nodes N-RUN, N-DATA |
| Working checkout / branch / base | NOT_STARTED |
| Affected code/document paths | PENDING_DESIGN |

**Reserved ACs (TASKS §2):** AC-001 X4.3 ([confirm: 1,000] runs characterized for concurrency, throughput, latency, peak memory and failures; committed records survive a killed worker; interrupted attempts identifiable; no duplicated completed trials); AC-002 X4.4 (whole-state checkpoint at a quiescent point with no unrecorded model request restores, and a follow-up branches from it); AC-003 concurrent runs and crash recovery; AC-004 F6 cases, `operations` check group and negative controls, `pause`/`resume`/`stream`; AC-005 concurrency, resume and checkpoint unit checks; AC-006 MuJoCo Warp speed and cost records; AC-007 phase 4 snapshot and completion report.

No separate authorization card or review assignment is required.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-013/` | One directory for this TASK |
| spec.md / plan.md / tasks.md | Created by `$speckit-specify`, `$speckit-plan`, `$speckit-tasks` | ACs / design and procedures / work and evidence |
| evidence/ | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-013/evidence/` (not committed) | Actual runs |
| Supporting artifacts | None yet | Subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| PAS-M1-001 (implementation) | Experiment core, records, checkpoints | Phase 1 exits verified | All |
| PAS-M1-003 (implementation) | Library state through IF-003 | 003/AC-008 | AC-002 |
| PAS-M1-011 (implementation) | Memory and model-call history in whole state | 011/AC-003 | AC-002 |

## 4. Embedded cross-module agreements
None owned: this TASK provides no cross-module interface of its own.

Consumed agreements: [SIMLAB-IF-001@r1](../PAS-M1-001/TASK.md#simlab-if-001-at-r1); [SIMLAB-IF-003@r1](../PAS-M1-003/TASK.md#simlab-if-003-at-r1); [SIMLAB-IF-004@r1](../PAS-M1-011/TASK.md#simlab-if-004-at-r1).

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| Q-01 / 2026-10-30 | Scale value [confirm: 1,000] (TASKS §6 Q-01) | AC-001 | None yet | Owner confirms |

Progress remains in tasks.md.
