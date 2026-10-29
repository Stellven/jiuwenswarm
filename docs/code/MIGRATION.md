# v2 preparation and migration

## Directory organization (2026-10-05)

| Content | Maintained location |
| --- | --- |
| Current process guides | docs/code/; flattened from the former code_sop wrapper |
| TASKS/TASK/evidence/AGENTS and native templates | plugins/spec-kit/templates/ |
| Shared Spec Kit skills/scripts/defaults | plugins/spec-kit/; installed as a Codex development plugin |
| Project constitution/settings/native overrides | .specify/; no duplicate vendor installation |
| Real task records and native artifacts | docs/code/Missions/PROGRAM-ID/; TASKS.md at program level and all four task files together under TASK-ID/ |
| Historical browser demo | docs/code/Missions/AI4R-001/CODEX_DEMO.md |

Start with [current navigation](README.md) and [plugin workflow](SPEC_KIT_WORKFLOW.md). Archived handbooks/ZIP/manifests are historical snapshots; edit active sources rather than regenerating a second authority. Incoming live links are migrated; existing historical references to removed legacy templates remain historical.

The user's hierarchy correction puts real tasks beneath the development-document parent: docs/code/Missions/. M1, AI4R-001 and DEVTOOLS keep their internal organization. Relative paths back to specs and other documentation are rebased; source contents and prior results are preserved.

## Intended state
This work prepares the process before the complete M1 PRD and architecture arrive. Existing teammates' implementation is unfinished; that is not a defect to repair as part of documentation preparation. No pilot or reviewer staffing is required to adopt this document structure.

## Replacement map
| Former artifact/process | v2 home |
| --- | --- |
| TASK card plus separate authorization | TASK identity, requested scope and source |
| Manual DESIGN and PLAN | Native plan.md |
| Separate contract / ADR / architecture task records | Embedded TASK agreements and native plan decisions; master architecture remains a source |
| Implementation checklist | Removed; native tasks.md is the only work list |
| TESTING policy and TEST_REPORT cards | Rebuilt VERIFICATION.md, plan procedures, native evidence matrix and feature evidence/ |
| AI/human review card and closing gate | Removed from the task lifecycle |
| HANDOFF and CURRENT_STATUS task copies | TASK entry point and native resumable work/evidence |
| CHANGE_REQUEST | TASK changes and TASKS source-impact entries |
| Ownership, file-map and environment cards per task | TASK executor/scope and plan technical context |
| Adoption checklist and kickoff pack | Current package catalog and future-M1 skeleton |

The removed templates and protocols are deleted from the active docs/code package. Historical records in docs/code/Missions/AI4R-001 and existing application test code are preserved. Their old process text is not a requirement for new v2 tasks.

## Prepared now
- Reusable program/task/evidence templates in the plugin.
- TASK-native spec/plan/tasks defaults in the plugin.
- Block, boundary and system verification method.
- Updated root instructions and constitution.
- A future-M1 TASKS skeleton with pending source inputs.
- A complete English delivery bundle and manifest.

## When final inputs arrive
Register exact PRD/architecture paths and baselines in M1 TASKS. Allocate real source clauses, create real TASK cards and their feature directories, and designate the system TASK. Extract the model list from the PRD; do not reuse example names as requirements.

Bind commands and thresholds to actual code and requirements. Unknown values remain explicit until needed. Do not create speculative implementation tasks merely to fill an empty register.

## Existing work
Continuing an existing task does not require retroactive duplication. When moving it to v2, preserve its native work IDs and evidence, register it under a TASKS, fold still-relevant boundary definitions into TASK, and record old artifact paths as historical references. Do not relabel incomplete tests as passing or rewrite earlier execution history.

The current legacy status/environment documents may remain as historical context. New M1 progress lives in its native task records through TASKS.

## Tool maintenance
Project overrides are separate from installed vendor templates and skills. Root instructions and invocation context establish the requested v2 behavior. No application implementation, test-suite replacement or remote repository configuration is performed by this documentation package.

The package is usable while product inputs are pending; completeness of future M1 implementation is a separate evidence-based condition.
