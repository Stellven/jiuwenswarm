# File Map and Human Understanding Record

> Suggested location: `docs/code-map/FILE_MAP.md`  
> Maintainers: authors maintain entries for their submitted files; module owners keep the map complete; Code Lead maintains function understanding and review records.  
> After copying: build the map from actual files and code, fill in placeholders, and remove instructions. Do not infer responsibilities from names or mark another person as having understood, reviewed, or approved something without evidence.

## When to use this template

- Establish the project map, then update it incrementally when files are added, deleted, renamed, or change responsibility or dependencies. Ordinary implementation changes update only affected records.
- Each submitted change must map to the author's understanding of every changed file. Code Lead must be able to explain relevant function inputs, outputs, side effects, branches, and call relationships, while progressively maintaining an understanding of the whole project.
- Cover added, modified, and deleted functions, plus unchanged callers/callees that the change makes necessary to recheck. Configuration, data, or documentation files may say N/A: no executable functions, but still need file-level verification.
- Locate code by real paths and symbol names; line numbers are supporting references. Mark generated files, third-party code, and binary assets with their source, version, and ownership boundary. Their non-editable contents do not require function-by-function interpretation.
- Preserve Pending understanding, Pending verification, and Pending review honestly. Code Lead assigns follow-up or explicitly limits coverage. A checked table does not establish that all code is understood.

## 1. Map baseline (required)

| Field | Value |
| --- | --- |
| Map maintainer | [Name] |
| Most recent verification | [Date and time zone] |
| Reference version | `huawei_waterloo_main_branch` at [Full SHA] |
| Covered scope | [Verified directories/modules] |
| Uncovered scope and plan | [Paths, reasons, owners, and completion conditions, or None] |
| Ownership source | `docs/governance/OWNERSHIP.md` |
| Architecture source | `docs/architecture/OVERVIEW.md` |

## 2. Project file map (required)

Use one entry per file that humans need to understand and maintain. A large existing codebase may start with module indexes and add file details as changes occur. Directory summaries do not replace file-level records for the current submission.

| Path | Type / status | Primary responsibility | Owner | Entry points / key symbols | Dependencies and callers | Design / contract | Tests |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [Actual file path] | [Source/config/test/generated/documentation; existing/proposed] | [Why the file exists] | [Name] | [Symbols or N/A] | [Paths/modules] | [Repository-relative paths] | [Test paths or explanation] |

Retain related task records after renames or deletions, and update the active map. Do not continue listing a deleted file as a current entry point.

## 3. Author's file-level understanding (required for each task)

- Task: [TASK-ID].
- Branch: [Actual branch: `huawei_waterloo_xiaoyang`, `huawei_waterloo_saurav`, `huawei_waterloo_ramika`, or `huawei_waterloo_muk`].
- Comparison baseline: [Team main branch SHA].
- Code under review: [Full SHA of this submission or candidate commit].
- Author: [Name].

| File | Change and design basis | Why it belongs here | Inputs / outputs or configuration effect | Dependencies and potentially affected locations | Verification | Author understanding status and time |
| --- | --- | --- | --- | --- | --- | --- |
| [Path] | [Change and related AC/design section] | [Responsibility boundary] | [File-level explanation] | [Callers and risks] | [Tests/reports] | Pending understanding: [To be completed] |

After completion, the author must be able to explain each file's purpose, reason for change, dependencies, verification, and risks directly. AI-generated explanations are unverified drafts; mark Understood only after the author personally verifies them.

## 4. Code Lead function-level review (required for executable functions)

Use fully qualified names, such as `module.Class.method`, to distinguish functions with the same name. Complex functions may reference separate explanations, but retain a per-function entry and the actual review status.

| File / function | Change type | Responsibility, inputs, and outputs | Side effects / state / exceptions | Key branches and invariants | Callers / callees and impact | Related tests | Code Lead status / evidence / time | Verified code SHA |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [Path and qualified function name] | [Added/modified/deleted/affected but unchanged] | [Explicit semantics] | [Behavior or None] | [Conditions and constraints] | [Relationships and impact] | [Test names] | Pending review: [To be completed] | [Full SHA] |

For deleted functions, explain replacements and checks for remaining callers. For affected unchanged functions, explain why the change preserves their assumptions. If there are no executable functions, identify the files and explain N/A.

Code Lead confirmation must come from that person's traceable review record. Function-level understanding is input to merge review, not final approval. Keep final approval in the PR or task review record, tied to the candidate commit SHA.

## 5. Whole-project understanding and coverage gaps (required)

| Module / call chain | Scope understood by Code Lead and evidence | Not yet understood or verified | Impact on current task | Follow-up owner / conditions |
| --- | --- | --- | --- | --- |
| [Actual module or call chain] | [Function list, review records, or walkthrough records] | [Paths/symbols or None] | [Blocking/acceptable and reason] | [Name/conditions] |

When a task touches a module not yet understood, establish the understanding required by the current change before approval. Track gaps in legacy code continuously; do not present them as completed function reviews.

## 6. Verification and documentation consistency (required for each task)

| Check | Result / evidence |
| --- | --- |
| Every file in the actual diff has an author record | [Pending / Verified with evidence] |
| Added, modified, deleted, and affected functions are covered | [Pending / Verified with evidence / N/A with reason] |
| Paths, symbols, contracts, and owners match actual code | [Result and version] |
| Module AGENTS entry points and dependencies need updates | [Yes/No and reason] |
| Previous understanding remains applicable after code changes | [Records rechecked or invalidated, with reasons] |

When code changes after review, update understanding and review for the affected scope and record the new verified SHA. Retain earlier records as historical evidence; do not apply them automatically as approval of a new commit.

## 7. Historical task index (update for new tasks)

Keep the active file map manageable. After a task, its detailed records may live in that task's `HANDOFF.md`. Retain paths and verified SHAs here so current files can be traced to historical understanding records.

| TASK-ID | Related files / modules | Author record / Code Lead review location | Verified code SHA | Merge SHA, if merged |
| --- | --- | --- | --- | --- |
| [TASK-ID] | [Scope] | `docs/tasks/<TASK-ID>/HANDOFF.md` or [Actual PR/record location] | [Full SHA] | [SHA or Not merged] |

Related templates: [DESIGN_TEMPLATE.md](DESIGN_TEMPLATE.md), [ARCHITECTURE_TEMPLATE.md](ARCHITECTURE_TEMPLATE.md), [CONTRACT_TEMPLATE.md](CONTRACT_TEMPLATE.md).
