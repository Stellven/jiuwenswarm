# TASK: PAS-M1-SYSTEM - Integrated system on the local workstation
TASK.md, spec.md, plan.md and tasks.md share this directory. The parent program directory holds TASKS.md.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | PAS-M1-SYSTEM / r1 / 2026-10-30 |
| Parent TASKS | [../TASKS.md](../TASKS.md) |
| Executor / collaborators | Claude Code (coding agent) for Suraj (owner) |
| Requested outcome and instruction/source | System TASK (Code SOP §7): ARCH "Completion boundary"; exit X5.2; ARCH Required proof rules; TP "Always" row; final test report `reports/PAS-M1_Final_Test_Report.md` |
| Included scope / exclusions | Included: one integrated candidate on the laptop; the completion-boundary journey; every earlier exit's checks rerun on that candidate; user stories traced to evidence; compute summary. Excluded: DGX Spark and anything M2 |
| PRD clause and architecture node references | TASKS §3 rows owned by PAS-M1-SYSTEM. Nodes All nodes and edges |
| Working checkout / branch / base | NOT_STARTED |
| Affected code/document paths | PENDING_DESIGN |

**Reserved ACs (TASKS §2):** AC-001 X5.2 (the final test report covers every exit with evidence); AC-002 completion-boundary journey and the overall test, with none of the non-completion conditions (mocked model, number without a run record, special core change, missing dependency reported as run, all-blocked campaign); AC-003 Required proof rules on one candidate (earlier exits' checks keep running; each exit stands alone; no mocks at BOUNDARY or SYSTEM; BLOCKED and NOT_RUN are not PASS); AC-004 US-SL01 to US-SL08 traced to evidence; AC-005 no network from executors and no host port besides 5175 on the integrated candidate; AC-006 compute summary across phases (owner coding prompt).

No separate authorization card or review assignment is required.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-SYSTEM/` | One directory for this TASK |
| spec.md / plan.md / tasks.md | Created by `$speckit-specify`, `$speckit-plan`, `$speckit-tasks` | ACs / design and procedures / work and evidence |
| evidence/ | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-SYSTEM/evidence/` (not committed) | Actual runs |
| Supporting artifacts | None yet | Subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| All TASKs PAS-M1-001 to PAS-M1-014 (implementation) | Verified child evidence valid for the candidate | Each TASK VERIFIED or BLOCKED with reason | All |

## 4. Embedded cross-module agreements
None owned: this TASK provides no cross-module interface of its own.

Consumed agreements: [SIMLAB-IF-001@r1](../PAS-M1-001/TASK.md#simlab-if-001-at-r1); [SIMLAB-IF-002@r1](../PAS-M1-002/TASK.md#simlab-if-002-at-r1); [SIMLAB-IF-003@r1](../PAS-M1-003/TASK.md#simlab-if-003-at-r1); [SIMLAB-IF-004@r1](../PAS-M1-011/TASK.md#simlab-if-004-at-r1).

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| None | None | None | None | None |

Progress remains in tasks.md.
