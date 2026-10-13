# TASKS: DEVTOOLS

## 1. Identity and source baselines
| Field | Value |
| --- | --- |
| Program ID and objective | DEVTOOLS; maintain the repository's development tools and documentation |
| Register revision/date | r3 / 2026-10-05 |
| Program coordinator | Codex, acting on Xiaoyang's request |
| Full PRD path / revision / SHA256 / bytes | N/A: development maintenance, sourced from the current user request |
| Architecture source and rendered views / revision / SHA256 | Existing repository layout and Code SOP v2; no product architecture changes |
| Scope inclusions and exclusions | Spec Kit Codex plugin and development-document organization; other work requires user instruction |
| System-verification TASK | [DEVTOOLS-001](DEVTOOLS-001/TASK.md) |
| Integrated candidate | Working tree on ai4r_xiaoyang; base 697670e5b4b113645e9296e28ddc19e3a609dada |

## 2. Task register and dependency graph
| TASK ID / entry link | Bounded outcome | Executor | Required for program? | Prerequisite TASK/block/IF IDs | Native feature directory | Progress/evidence source |
| --- | --- | --- | --- | --- | --- | --- |
| [DEVTOOLS-001](DEVTOOLS-001/TASK.md) | Reusable Spec Kit Codex plugin and clear development-document locations | Codex | Yes, current requested scope | None | docs/code/Missions/DEVTOOLS/DEVTOOLS-001/ | [Native work and evidence](DEVTOOLS-001/tasks.md) |

This maintenance task is independent of M1 product implementation.

## 3. Source coverage allocation
| Source clause ID / exact locator | Architecture node/edge IDs | Owning TASK / AC references | Allocation decision and completeness |
| --- | --- | --- | --- |
| U01: organize the mixed docs/code directory and repair its references | N/A: document layout | DEVTOOLS-001/AC-001, AC-003 | Allocated |
| U02: package Spec Kit for Codex development, not product users | N/A: Codex plugin packaging | DEVTOOLS-001/AC-002 | Allocated |
| U03: ask before other work; every action should produce a clearer structure | N/A: scope constraint | DEVTOOLS-001/AC-001, AC-003 | Allocated |
| U04: development tasks are subordinate to code documentation | N/A: directory hierarchy | DEVTOOLS-001/AC-001, AC-003 | Allocated; migrate to docs/code/Missions |
| U05: integrate the TASKS/TASK design and templates into the plugin, including existing records | N/A: reusable task workflow | DEVTOOLS-001/AC-004 | Allocated; plugin owns reusable resources; existing project records stay registered in place |
| U06: clearly distinguish templates, real work and examples | N/A: ownership | DEVTOOLS-001/AC-001, AC-004 | Allocated; no real project records in the plugin |
| U07: store TASKS and all task/native records together under code/Missions/PROGRAM-ID | N/A: physical hierarchy | DEVTOOLS-001/AC-001, AC-004 | Allocated; relocate native artifacts into each task directory |
| U08: remove fictional demonstration tasks | N/A: cleanup | DEVTOOLS-001/AC-001 | Allocated; delete the ten-file fictional example and its active navigation |

## 4. Interface index
No cross-module product agreement is changed. The documented Codex plugin manifest and existing Spec Kit template/feature-selection contracts are verified in the owning task.

## 5. System verification entry
- System TASK: [DEVTOOLS-001](DEVTOOLS-001/TASK.md); [spec](DEVTOOLS-001/spec.md), [plan](DEVTOOLS-001/plan.md), [work/evidence](DEVTOOLS-001/tasks.md).
- Complete journey: discover/install the local plugin, resolve project templates and operate on a selected feature in an isolated fixture.
- Candidate and evidence: recorded in the native evidence matrix.
- Program conclusion: derive from that matrix; no M1 acceptance claim.

## 6. Source changes and unresolved inputs
| Change/question ID | Source or IF revision / question | Affected TASK/AC/block/check IDs | Action and evidence invalidation | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| D01 | User clarified Codex development plugin and requested cleaner structure | DEVTOOLS-001, all ACs | Keep product runtime and existing task contents out of scope | Codex / verify changed paths and pre-existing dirty-file hashes |
