# Implementation Plan: M1-001 - Connect JiuwenSwarm to Codex
**TASK**: [M1-001](TASK.md) | **Spec**: [r2](spec.md)
**Revision / date**: r2 / 2026-10-02 | **Branch**: ai4r_xiaoyang, the existing branch.
**Language update**: 2026-10-05. Easier English; the requirements and IDs stay the same.
**Input sources**: PRD r2, §3.0, §3.0.1, §3.0.2; follow the work order in §6.3. Architecture: PENDING_SOURCE. Use the agreement versions listed in TASK.md.

## Summary

This file says **how to divide the work and how to check it**. The goal is to make the existing code that connects JiuwenSwarm to Codex work reliably. Other parts of the system need one common Python entry point to use that connection. Calls must be protected and their failures must be recorded.

The PRD calls the connection code an adapter. It calls the common entry point a provider abstraction. These phrases refer to the two jobs just described. The common entry point follows the standard Python class or interface in the PRD: shared code that other parts call in the same way they call a normal model service. Codex CLI is the Codex tool used from a terminal.

The four blocks below are four groups of work. A block ID does not choose a new code module, class, or separate running program. The architecture, meaning the design of the code parts and their connections, must supply those decisions. First read that design and inspect the existing code and tests. Then fill in the actual code paths and check commands. The requirements and success conditions stay in spec.md.

## How to read the IDs and status

- **B01–B04**: groups of work in this plan.
- **AC-001–AC-005**: success conditions in spec.md.
- **V01–V05 and V90**: checks in this plan.
- **T001 and other T IDs**: work items in tasks.md.
- **IF**: an agreement about how parts of the system work together. `@r0` is its version.
- **PENDING_SOURCE**: the source document or required value has not been supplied.
- **PENDING_DESIGN**: the exact code design is still needed.
- **NOT_RUN**: the software check has not been run.
- **NOT_BUILT**: the system version for the full test has not been put together.

## Technical Context

The architecture must fill in the seven groups of details listed in [Architecture minimum inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt). The numbers below match that file.

1. **Which code part does each job?** Name the modules, separately running programs, owners, and code paths. PENDING_DESIGN (1).
2. **What do the parts pass to each other?** Define input and output fields, their types, and how to check them. Define errors, timeouts, cancellation, and how repeated requests are handled. PENDING_DESIGN (2).
3. **How does a run move forward?** Define step order, how the saved gate decision controls later steps, and how an explicit restart works. PENDING_DESIGN (3).
4. **Where is data saved?** Define who may write it, how records link back to their sources, and how required records are kept fixed. PENDING_DESIGN (4).
5. **How are allowed actions enforced?** Define how code is kept within the permitted files, programs, and access rights. PENDING_DESIGN (5).
6. **What setup does the code need?** Define operating-system and software versions, required packages, and settings. Say which setting wins when several sources give a value, and how it takes effect. PENDING_DESIGN (6).
7. **How do we run and check it?** Define entry points and commands, plus ways to create controlled failures for tests. PENDING_DESIGN (7).

The PRD and spec.md still set required technology, file names, access rights, and behavior. A PENDING_DESIGN label does not remove those rules. Phase 1 sends model calls through the fixed Codex CLI connection. The real account, model, and computer setup have not been tested yet. Read limits and test settings from the supplied sources; do not make up default numbers.

## Constitution Check

This section checks that the documents follow the project's working rules:

- One TASK has one registered feature directory.
- TASK.md owns agreements between parts. spec.md owns success conditions. This plan owns work groups and check methods. tasks.md owns the work list and actual progress.
- Each AC has its own required check and a check across the real connection to other parts.
- Do not add separate approval, review, or implementation-checklist cards.
- The architecture, exact test inputs, and system version to test still need to be linked to the work. Software checks are NOT_RUN. Written documents do not count as results from running the software.

## Project Structure

These document paths already exist:

- `docs/code/Missions/M1/M1-001/TASK.md`: task scope, links, and agreements with other tasks.
- `docs/code/Missions/M1/M1-001/spec.md`: requirements and success conditions.
- `docs/code/Missions/M1/M1-001/plan.md`: this work and check plan.
- `docs/code/Missions/M1/M1-001/tasks.md`: work items, progress, and results.

Use `docs/code/Missions/M1/M1-001/evidence/` for records from actual software checks when those checks run.

The paths for application code, settings, tests, and test inputs are PENDING_DESIGN (minimum inputs 1, 4, 6, and 7). Do not guess a code directory or define a new data format just to fill the table.

## Blocks and Dependencies

| Block ID | Job and related success conditions | What goes in and comes out; rules that must always hold | Required tasks, blocks, or agreements | Code paths to change |
| --- | --- | --- | --- | --- |
| B01 | Reuse the existing Codex connection and keep the expected request and reply formats; AC-001, AC-004. | PENDING_DESIGN (1–5). The required behavior is in the linked ACs. | Use TASK section 3 for document needs. Actual connections while the code runs are PENDING_DESIGN (1–3). | PENDING_DESIGN (1 and 7). |
| B02 | Allow only permitted local code to call Codex; AC-002. | PENDING_DESIGN (1–5). The required behavior is in the linked AC. | Use TASK section 3 for document needs. Actual connections while the code runs are PENDING_DESIGN (1–3). | PENDING_DESIGN (1 and 7). |
| B03 | Give other parts a common Python entry point to call Codex, and record call failures; AC-003. | PENDING_DESIGN (1–5). The required behavior is in the linked AC. | Use TASK section 3 for document needs. Actual connections while the code runs are PENDING_DESIGN (1–3). | PENDING_DESIGN (1 and 7). |
| B04 | Make calls through the shared recording path and keep internal tracking labels local; AC-005. | PENDING_DESIGN (1–5). The required behavior is in the linked AC. | Use TASK section 3 for document needs. Actual connections while the code runs are PENDING_DESIGN (1–3). | PENDING_DESIGN (1 and 7). |

Keep these B IDs when the code design arrives. Define the needed agreements before writing code that depends on them. Connect the real parts before checking that connection. A link to another TASK does not mean all of that task must be finished first. The architecture still owns the detailed run order and the way saved decisions control it.

## Interfaces and Technical Decisions

An interface is the agreed way one part of the code calls another. Read the agreements in [TASK section 4](TASK.md#4-embedded-cross-module-agreements): M1-IF-001@r0, M1-IF-002@r0, M1-IF-004@r0, and M1-IF-005@r0. At present, they identify where each agreement belongs. The exact calling rules are still waiting for the architecture.

The architecture needs to define data fields, storage, calls between programs, error handling, recovery rules, security methods, how settings take effect, and the actual check entry points. These details are PENDING_DESIGN, as listed above.

Keep all source rules in spec.md. These include required files, local connection limits, required packages and install restrictions, keeping internal labels out of model requests, and any required user action. The architecture must explain how to carry out those rules without changing what counts as success.

This plan has not chosen a new data format, a layout of running programs, or a new code method. When the architecture arrives, update the agreements in their owning TASKs and record the new versions there.

## Verification Design

This section says **what to try and what result to look for**. BLOCK means checking one part of the code. BOUNDARY means checking it while connected to the real code or service that uses it.

The exact commands, code entry points, folders to run in, test-input paths, and ways to create test failures are PENDING_DESIGN (7). T001 will fill them in after reading the architecture and existing code. The table is a plan for checks; it is not a list of checks that have already passed.

| V ID | Check level | Related block / agreement / success condition | Test inputs and real or fake services | Required result and its source | Command, folder, or manual check steps | What must be ready and what to save |
| --- | --- | --- | --- | --- | --- | --- |
| V01 | BOUNDARY | M1-001/B01; M1-001/AC-001; M1-IF-001@r0 | Find the existing connection code and its callers. Use one real local caller and the real Codex CLI account for one request within the allowed limits. | Meet all of [AC-001](spec.md#measurable-outcomes), its PRD r2 sections, and its scope limits. | Inspect the existing code. Send the real request and read the reply. Compare normal and required failure results with AC-001. Exact commands, code paths, and run folder: PENDING_DESIGN (7). | Use the ready items and saved records listed below. A fake Codex service cannot show that the real connection works. |
| V02 | BLOCK | M1-001/B02; M1-001/AC-002; M1-IF-001@r0 | Use the actual local code. Try an allowed caller, a missing or wrong session secret, and a caller outside the allowed run context. Fake services may replace other parts only to test this code separately. | Meet all of [AC-002](spec.md#measurable-outcomes), its PRD r2 sections, and its scope limits. | Check allowed and denied calls, local access rights, and whether a network port (TCP) is open. Compare all normal and failure results with AC-002. Exact commands, code paths, and run folder: PENDING_DESIGN (7). | Use the ready items and saved records listed below. A result claimed for a real connection requires the real parts. |
| V03 | BLOCK | M1-001/B03; M1-001/AC-003; M1-IF-001@r0 | Use the actual local code. Call the common Python entry point. Create a controlled timeout and a missing or expired Codex login. Fake services may replace other parts only to test this code separately. | Meet all of [AC-003](spec.md#measurable-outcomes), its PRD r2 sections, and its scope limits. | Check a normal call and the required failure cases. Read the saved failure records and confirm which run caused them. Exact commands, code paths, and run folder: PENDING_DESIGN (7). | Use the ready items and saved records listed below. A result claimed for a real connection requires the real parts. |
| V04 | BLOCK | M1-001/B01; M1-001/AC-004; M1-IF-001@r0 | Use the actual local code and settings. Include requests for excluded streamed chat and automatic model switching. Fake services may replace other parts only to test this code separately. | Meet all of [AC-004](spec.md#measurable-outcomes), its PRD r2 sections, and its scope limits. | Inspect the code and settings. Check the normal and excluded cases. Confirm that Phase 1 stays within AC-004. Exact commands, code paths, and run folder: PENDING_DESIGN (7). | Use the ready items and saved records listed below. A result claimed for a real connection requires the real parts. |
| V05 | BLOCK | M1-001/B04; M1-001/AC-005; M1-IF-001@r0 | Prepare and version normal cases, cases at the allowed limits, and attempts at forbidden actions before the check. Their expected results must be set independently. | Meet all of [AC-005](spec.md#measurable-outcomes), its PRD r2 sections, and its scope limits. | Compare local call records with the actual request sent to the model service. Try to skip the recording step through a supported call path. Keep internal stage, role, and capsule labels local when used only to track or compare calls. Keep the required task content in the request. Exact commands, code paths, and run folder: PENDING_DESIGN (7). | Use the ready items and saved records listed below. A result claimed for a real connection requires the real parts. |
| V90 | BOUNDARY | M1-IF-001@r0; AC-001, AC-002, AC-003, AC-004, AC-005 | Connect the real parts that send and receive requests. Use the normal and failure cases needed for each AC. Fix the test-input versions before running them. | Meet every listed AC across the real connection. Do not reuse an old success as a current result, allow a forbidden action, or let later steps use work without the required permission. | Observe the connected results, saved local records, and what later steps are allowed to do. Exact entry points, ways to create failures, commands, and run folder: PENDING_DESIGN (7). | The required code parts and agreements must be ready. Save real connection logs, the tested code and settings versions, and the results. Fake services alone cannot pass this check. |

### Ready items and saved records for all checks

Before a check, link it to the current PRD, architecture, agreement versions, test settings, and exact code version being tested. The test settings are also called a profile. The code and settings put together for testing are also called a candidate.

Prepare the test inputs and expected results independently. Give them IDs and versions before running the check. Do not change those saved inputs or expected results during the run. Save the original run records, including failures. Use real services whenever the result is meant to show that a real model call or real connection works.

The AC in spec.md sets the required result and any limits. This plan must not replace it with an easier check or a different limit. T001 must fill in the actual test cases and any supplied product limits before the checks that need them. A required case that was skipped or could not run cannot count as a pass.

For model checks, save the following when available or supported:

- The actual model name and version, route used, and software version used to run it.
- The prompt and settings; the dataset ID and version; each test-group ID and which data it uses; and test-input IDs.
- The number of repeats and scoring rules set before the run. Save the random seed if the software uses one; this is the number used to control random choices.
- Where the timing measurement starts and ends, plus reliable token-use and cost records that the service provides.

Internal labels used only to track or compare runs stay local. Do not put them into a request sent to the model service for that purpose.

This document update makes no model calls, installs no packages, and runs no software checks.

## System Candidate and Journeys

[M1-SYSTEM](../M1-SYSTEM/TASK.md) checks the complete system from start to finish, including rules that apply across tasks. Give it current results for AC-001, AC-002, AC-003, AC-004, and AC-005. Also give it the actual code part, test settings, agreement versions, and relevant PRD rules used in those results.

The full test version is NOT_BUILT. All current checks are NOT_RUN. A small A-to-gate-to-B run, one model reply, or a written report does not show that the full M1 system passed.

Use the real Phase 1 setup as the required starting point for comparison. Phase 2 results cannot replace it. Tests that remove a required control to study its effect cannot replace it either.

## Unresolved Decisions and Impact

- **Architecture is PENDING_SOURCE.** All seven design groups are PENDING_DESIGN. This holds up only the code and checks that need those details. Other PRD reading and test-input preparation can continue. TASK section 5 lists the local questions.
- **Test setup still needs to be fixed for each check.** Confirm test-input versions, allowed computer setup, working account access, supplied budgets and limits, and repeat counts set before measurement. An example number does not become a rule for every run.
- **PRD r2 is the current source.** Keep the existing B, V, and T IDs. Add new IDs for new requirements. Old number limits and RSI methods found only in PRD r1 are not current requirements. There are no software run results to reuse or mark out of date yet.
- **Later changes may make a result out of date.** If a change to a source, agreement, code, setting, or test input affects a check, mark that result STALE. This means the old result no longer proves the current version. Keep the original records and rerun the affected checks, including the whole-system checks that depend on them.
