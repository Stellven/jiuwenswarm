# TASK: DEVTOOLS-001 - Spec Kit Codex plugin and document organization

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | DEVTOOLS-001 / r3 / 2026-10-05 |
| Parent TASKS | [DEVTOOLS](../TASKS.md) |
| Executor / collaborators | Codex / None |
| Requested outcome and instruction/source | Current user request U01-U08 in the parent register; reusable Codex development plugin, clear file ownership and task hierarchy beneath docs/code |
| Included scope / exclusions | Include plugin packaging, necessary Spec Kit path adaptation, document moves and reference repair. Exclude product code, product requirements, unrelated cleanup, commits, pushes and publication. |
| PRD clause and architecture node references | N/A: maintenance request, not M1 product scope |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / 697670e5b4b113645e9296e28ddc19e3a609dada |
| Affected code/document paths | plugins/spec-kit/, .agents/plugins/marketplace.json, .codex/config.toml, .specify/, docs/code/, necessary incoming links, these task records |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/DEVTOOLS/DEVTOOLS-001/ | One feature for this TASK |
| spec.md | [spec](spec.md) | ACs |
| plan.md | [plan](plan.md) | Blocks and verification |
| tasks.md | [work/evidence](tasks.md) | Work and acceptance/evidence mapping |
| evidence/ | docs/code/Missions/DEVTOOLS/DEVTOOLS-001/evidence/ | Actual verification observations |
| Supporting artifacts | None | No parallel reports |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| Existing Spec Kit 1.0.12 and Codex CLI | Installed upstream resources and native plugin management | Preserve version, license and project overrides; confirm available CLI | B01, B02 / T001-T003 |

## 4. Embedded cross-module agreements
None: this task changes development packaging and document paths, not a product module interface. Existing project override precedence and explicit feature-directory selection remain compatibility requirements in spec.md. No consumer TASK definitions are changed.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| D01 / 2026-10-05 | User confirms Codex plugin, with every action contributing to clearer structure | All ACs / no product IF | Baseline links and unrelated dirty files recorded before migration | Codex / verify final paths, links and hashes |
| D02 / 2026-10-05 | User corrects the hierarchy: development tasks belong under docs/code, not beside it | AC-001/003; B02; V02; T007/T008 | Relocate real task records beneath docs/code and revalidate affected links; preserve prior run observations | Codex / directory, reference and content-preservation checks |

| D03 / 2026-10-05 | User requests TASKS/TASK integration and a clear template/real-record boundary | AC-004; B01-B03; V01-V03; T009/T010 | Promote reusable templates, integrate registration/native commands, refresh installation and rerun affected checks; preserve project records | Codex / relocated resolution, links, record preservation and installation |

| D04 / 2026-10-05 | User specifies Missions/PROGRAM-ID, colocated TASK/native files and no fictional demos | AC-001/003/004; T009/T010 | Migrate all 22 registered features into their task folders, remove the ten-file fictional example and revalidate navigation; preserve previous observations | Codex / four files per task, protected bytes and native selected-directory check |

Progress remains in tasks.md.
