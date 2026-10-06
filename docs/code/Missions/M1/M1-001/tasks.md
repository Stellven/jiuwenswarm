---

**Current baseline (2026-10-06):** [Latest verbatim PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) and [architecture decisions D1–D15](../../../../architecture/build-package/principles.md#decisions-and-source-amendments) apply to this task. Preserve existing AC/IF/work IDs; coding agents choose detailed schemas, APIs, code paths and checks in the native records. Delivery Phase 1 is the research baseline, Phase 2 is required offline RSI, and Phase 3 is expected dynamic integration: attempt available capabilities and record BLOCKED/INCOMPLETE dependencies; core-demo success does not complete all M1 work. Account identity/profile lifetime is distinct from local execution/workspace lifetime. Runtime evidence remains NOT_RUN.

description: "Work items, success conditions, and saved check results for M1-001"
---
# Tasks: M1-001 - Connect JiuwenSwarm to Codex
**TASK**: [M1-001](TASK.md) | **Spec / Plan revisions**: r2 / r2
**Feature directory**: docs/code/Missions/M1/M1-001/
**Language update**: 2026-10-05. Easier English; the requirements, work IDs, and progress stay the same.

## What this file is for

This file says **what work needs to be done, what needs to be checked, and what has actually been done**. It is the only code work list for this task. The empty boxes below are future work. This update is for documents only; it does not ask anyone to run or change the application now.

The task is to improve the existing code that sends JiuwenSwarm requests to Codex and returns the replies. The PRD calls this code an adapter. Other parts need one common Python entry point to use it. The PRD calls that a provider abstraction. It follows the standard calling rules for a model service. Codex CLI is the Codex tool used from a terminal. The architecture is the design document that says which code parts do each job and how they connect.

Read spec.md for what the code must do. Read plan.md for the work groups and check methods. Use this file to track the work and link each success condition to its actual check result.

## How to read the work list

- **T** is a work item. **B** is a group of work in plan.md.
- **AC** is a success condition in spec.md. **V** is a check in plan.md.
- **US1** refers to the user story in spec.md.
- **IF** is an agreement about how code parts work together. `@r0` means version r0.
- **PENDING_DESIGN** means the architecture still needs to define the exact code design, files, or commands.
- **NOT_RUN** means the check has not been run. **NOT_BUILT** means the system version for the full test has not been put together.

Example: AC-003 says a Codex timeout must be recorded as a failure. B03 is the group of work that handles this. T006 builds it. V03 checks it, and T007 runs that check and saves the result.

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Read the PRD sections assigned to this task and the architecture when it arrives. Find the existing Codex connection code, the code that calls it, and its tests. Read the working rules in those code folders. Fill in the actual file paths, agreement versions, test inputs, and commands. This applies to all blocks and ACs. Record the needed details in `docs/code/Missions/M1/M1-001/TASK.md` and `docs/code/Missions/M1/M1-001/plan.md`.

### Block B01 - Reuse the connection and keep the expected reply format

- [ ] T002 [US1] Build the B01 behavior required by AC-001 and AC-004, using M1-IF-001@r0. First define the rules it needs and have the required running parts available for the work that uses them. Reuse the existing connection code and keep the request and reply formats working. Code paths are PENDING_DESIGN. T001 must find and record them; do not invent a new module name as a file path.
- [ ] T003 [US1] Run every required case in V01 and V04. Save the exact code version tested, the source and agreement versions, and the original results in `docs/code/Missions/M1/M1-001/evidence/`. Check-file paths are PENDING_DESIGN. Update the matching rows in the results table with what actually happened.

### Block B02 - Allow only permitted local code to call Codex

- [ ] T004 [US1] Build the B02 behavior required by AC-002, using M1-IF-001@r0. First define the rules it needs and have the required running parts available for the work that uses them. Protect the local connection and limit who may call it. Code paths are PENDING_DESIGN. T001 must find and record them; do not invent a new module name as a file path.
- [ ] T005 [US1] Run every required case in V02, including allowed callers and callers that must be denied. Save the exact code version tested, the source and agreement versions, and the original results in `docs/code/Missions/M1/M1-001/evidence/`. Check-file paths are PENDING_DESIGN. Update the matching rows in the results table with what actually happened.

### Block B03 - Give other code one way to call Codex and record failures

- [ ] T006 [US1] Build the B03 behavior required by AC-003, using M1-IF-001@r0. First define the rules it needs and have the required running parts available for the work that uses them. Provide the common Python entry point and record timeouts or lost Codex login in the matching run record. Code paths are PENDING_DESIGN. T001 must find and record them; do not invent a new module name as a file path.
- [ ] T007 [US1] Run every required case in V03, including a normal call, a timeout, and a missing or expired Codex login. Save the exact code version tested, the source and agreement versions, and the original results in `docs/code/Missions/M1/M1-001/evidence/`. Check-file paths are PENDING_DESIGN. Update the matching rows in the results table with what actually happened.

### Block B04 - Record calls and keep internal tracking labels local

- [ ] T010 [US1] Build the B04 behavior required by AC-005. Use the shared model-call recording rules owned by M1-004. Keep labels used only to track or compare runs out of the request sent to the model service. The architecture must supply the actual code paths first; they are PENDING_DESIGN. The requirements stay in spec.md.
- [ ] T011 [US1] Run V05 for B04 and AC-005. Save the exact code version tested, source versions, test settings, agreement versions, and original results in `docs/code/Missions/M1/M1-001/evidence/`. The check-file path is PENDING_DESIGN. Update the matching rows in the results table.

### Connected boundaries

This means checking the Codex connection together with the real parts that call it or receive its results.

- [ ] T008 [US1] Connect those real parts and run V90 for every AC that applies. Make real model calls wherever the AC requires them. The paths for these checks are PENDING_DESIGN. Save connection logs and run records in `docs/code/Missions/M1/M1-001/evidence/`.

### System contribution

This means giving M1-SYSTEM what it needs to check the whole system.

- [ ] T009 [US1] Give `docs/code/Missions/M1/M1-SYSTEM/TASK.md` and its own results table the exact code part, settings, and agreement versions used. Supply current results for this task's code and real connections. Take part in its actual full-system runs using the matching system version.

## Acceptance and Evidence Matrix

This table connects each success condition to the work that builds it and the check that tests it. Each AC has a row for its own required check and a row for V90, the check with real connected parts.

The software has not been tested yet. NOT_RUN is not a pass. "None / NOT_BUILT" means there is no run record and no full system test version prepared.

| AC ID / spec link | Work group / agreement | Code work ID | Required check ID / work that runs it | Current result | Saved run result / tested system version | Why a result can or cannot be reused |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-001@r0 | T002 | V01 / T003 | NOT_RUN | None / NOT_BUILT | Based on current PRD. The design, runnable test inputs, and exact test version still need to be set. |
| [AC-001](spec.md#measurable-outcomes) | B01; M1-IF-001@r0 with real connected parts | T002 | V90 / T008 | NOT_RUN | None / NOT_BUILT | The real connection has not been checked. There is no earlier run result. |
| [AC-002](spec.md#measurable-outcomes) | B02; M1-IF-001@r0 | T004 | V02 / T005 | NOT_RUN | None / NOT_BUILT | Based on current PRD. The design, runnable test inputs, and exact test version still need to be set. |
| [AC-002](spec.md#measurable-outcomes) | B02; M1-IF-001@r0 with real connected parts | T004 | V90 / T008 | NOT_RUN | None / NOT_BUILT | The real connection has not been checked. There is no earlier run result. |
| [AC-003](spec.md#measurable-outcomes) | B03; M1-IF-001@r0 | T006 | V03 / T007 | NOT_RUN | None / NOT_BUILT | Based on current PRD. The design, runnable test inputs, and exact test version still need to be set. |
| [AC-003](spec.md#measurable-outcomes) | B03; M1-IF-001@r0 with real connected parts | T006 | V90 / T008 | NOT_RUN | None / NOT_BUILT | The real connection has not been checked. There is no earlier run result. |
| [AC-004](spec.md#measurable-outcomes) | B01; M1-IF-001@r0 | T002 | V04 / T003 | NOT_RUN | None / NOT_BUILT | Based on current PRD. The design, runnable test inputs, and exact test version still need to be set. |
| [AC-004](spec.md#measurable-outcomes) | B01; M1-IF-001@r0 with real connected parts | T002 | V90 / T008 | NOT_RUN | None / NOT_BUILT | The real connection has not been checked. There is no earlier run result. |
| [AC-005](spec.md#measurable-outcomes) | B04; M1-IF-001@r0 | T010 | V05 / T011 | NOT_RUN | None / NOT_BUILT | Based on current PRD. The design, runnable test inputs, and exact test version still need to be set. |
| [AC-005](spec.md#measurable-outcomes) | B04; M1-IF-001@r0 with real connected parts | T010 | V90 / T008 | NOT_RUN | None / NOT_BUILT | The real connection has not been checked. There is no earlier run result. |

## Dependency Order and Execution Notes

Do the part of T001 needed by each code change or check before starting that work. This includes the relevant architecture details and independently prepared test inputs. Work that does not need a missing detail can continue.

Build each part before running its mapped check. T008 needs the actual connected parts and the agreements they use. T009 needs results that match the system version being tested. A document link to another task does not mean that whole task must be finished first.

Keep all existing work IDs. T010 and T011 appear beside B04 because that is the work they belong to. Their higher numbers do not make them the last steps. Add IDs for new work instead of changing existing numbers.

No shared application files or parallel code changes have been assigned. Requirements and limits stay in spec.md. The architecture supplies the detailed code design. Progress and saved results belong here. This document update runs no software checks or model calls, installs no packages, and makes no commits.

A checked box means the work was done. An AC passes only when all of its required checks have valid passing results. A missing, failed, skipped, blocked, or out-of-date required check cannot count as a pass.

## Current Verification Conclusion

- **Version prepared for testing**: NOT_BUILT. The existing code has not yet been inspected in this work.
- **Required work finished?** No. All work boxes are empty.
- **Checks listed**: 5 success conditions, 6 check IDs, and 10 result rows. All result rows are NOT_RUN.
- **Current conclusion**: NOT_READY, meaning the software is not ready to be marked as passed. The documents based on the latest PRD have been prepared.
- **Next work**: T001. Fill in the design details needed by the next code work and real checks. Account access, the software setup, and test inputs have not been tested yet.

## Evidence Invalidation

This means deciding whether an old result still applies after a change. There are no software run results yet.

Later, changes to the PRD, agreement versions, code, tests, settings, test rules, or fixed test inputs may affect this table and M1-SYSTEM. Check which results depend on each change. Mark those results STALE, meaning they no longer show that the current version works. Keep their original records.

Reuse an old result only after recording why the relevant behavior, inputs, and other parts it depends on have not changed. A generated document cannot replace a result from running the software.
