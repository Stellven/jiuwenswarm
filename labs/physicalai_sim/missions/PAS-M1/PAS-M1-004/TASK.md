# TASK: PAS-M1-004 - Numerical engine and engine cross-checks
TASK.md, spec.md, plan.md and tasks.md share this directory. The parent program directory holds TASKS.md.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | PAS-M1-004 / r1 / 2026-10-30 |
| Parent TASKS | [../TASKS.md](../TASKS.md) |
| Executor / collaborators | Claude Code (coding agent) for Suraj (owner) |
| Requested outcome and instruction/source | Phase 3 library "numerical engine" (ARCH "Build order"; ARCH Responsibilities, Executors); TB-10; F5 MuJoCo vs numerical; adopted Drake second engine and ContactNets/Acosta real-data comparison (TP "Official external benchmarks") |
| Included scope / exclusions | Included: numerical engine executor at a pinned version; ODE closed-form cases per engine; MuJoCo vs numerical agreement; Drake as a second engine with a different contact model; ContactNets cube toss and Acosta impacts as measured evidence. Excluded: x86 vs arm64 agreement (M2) |
| PRD clause and architecture node references | TASKS §3 rows owned by PAS-M1-004. Nodes N-EXE, E3 |
| Working checkout / branch / base | NOT_STARTED |
| Affected code/document paths | PENDING_DESIGN |

**Reserved ACs (TASKS §2):** AC-001 TB-10 (closed form for each engine; agreement between engines is corroboration only); AC-002 F5 MuJoCo vs numerical with a declared tolerance; AC-003 X3.1 for engines (known-answer and registry admission); AC-004 Drake cross-check engine; AC-005 ContactNets and Acosta real data, reported at evidence level `measured` or `validated_range`.

No separate authorization card or review assignment is required.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-004/` | One directory for this TASK |
| spec.md / plan.md / tasks.md | Created by `$speckit-specify`, `$speckit-plan`, `$speckit-tasks` | ACs / design and procedures / work and evidence |
| evidence/ | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-004/evidence/` (not committed) | Actual runs |
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
| None | None | None | None | None |

Progress remains in tasks.md.
