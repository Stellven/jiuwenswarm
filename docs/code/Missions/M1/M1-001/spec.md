# Feature Specification: M1-001 - Connect JiuwenSwarm to Codex

**Current baseline (2026-10-06):** [Latest verbatim PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) and [architecture decisions D1–D15](../../../../architecture/build-package/principles.md#decisions-and-source-amendments) apply to this task. Preserve existing AC/IF/work IDs; coding agents choose detailed schemas, APIs, code paths and checks in the native records. Delivery Phase 1 is the research baseline, Phase 2 is required offline RSI, and Phase 3 is expected dynamic integration: attempt available capabilities and record BLOCKED/INCOMPLETE dependencies; core-demo success does not complete all M1 work. Account identity/profile lifetime is distinct from local execution/workspace lifetime. Runtime evidence remains NOT_RUN.

**TASK**: [M1-001](TASK.md)
**Parent TASKS**: [M1](../TASKS.md)
**Revision / date**: r3 / 2026-10-06
**Language update**: 2026-10-05. Easier English; the requirements and IDs stay the same.
**Feature Branch**: ai4r_xiaoyang. This is the existing branch. No new task branch has been made.
**Input**: [current PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt), §3.0, §3.0.1, §3.0.2; use the model-call rules from §4.3.3; follow the work order in §6.3. The whole-project rules in §1.3–§1.6 and §2.1–§2.12 also apply. Architecture: [current design](../../../../architecture/build-package/README.md); detailed realization belongs to the coding agent, which means the design source has not been supplied yet.
**Status**: Preparing. The required behavior is written below. Detailed realization belongs to the coding agent. The software has not been tested in this document update.

## What this file is for

This file says **what the Codex connection must do and what counts as success**. The PRD calls the existing connection code an **adapter**. Here, that means the code that takes a request from JiuwenSwarm, sends it to Codex, and returns the answer in the format JiuwenSwarm expects.

Codex CLI is the Codex tool used from a terminal. CLI means "command-line interface." This task uses the active Codex account without requiring an enterprise API key.

Other parts of the system also need one common Python entry point to call Codex. The PRD calls this a **provider abstraction**. In plain words, other code uses that entry point and does not have to repeat the details of talking to Codex. It must follow the standard Python class or interface required by the PRD: a shared piece of code that other parts can call in the same way they call a normal model service. The architecture will define its exact inputs and outputs.

The short IDs help people and agents find the same item across files:

- **FR**: a requirement, or something the code must do.
- **AC**: a success condition, or what a check must show.
- **US1**: the user story below.
- **IF**: an agreement about how two parts of the system work together. `@r0` means version r0 of that agreement.

## User Scenarios & Testing
### User Story 1 - Ask Codex and handle its answer or failure (Priority: P1)

A local part of JiuwenSwarm needs to ask Codex for an answer. It sends an allowed request through the existing connection code. It receives either an answer or a clear failure result. The system can tell which run made the request.

The work is to inspect and improve the existing connection code, keep the current request and reply formats, limit access to allowed local code, and provide the common Python entry point. Keep the Phase 1 scope set by the PRD.

**Independent Test**: Check the cases below for each part of this task. Then connect the real parts that use the Codex connection and check them together. Compare the actual results with the ACs. An agent saying "done" does not show that the code passed. A fake service used in a test cannot show that the real Codex account works, that access is properly limited, or that all of M1 is ready.

**Acceptance Scenarios**:
1. Given valid inputs and working services, when JiuwenSwarm asks Codex for an answer within the allowed limits, then the answer and saved results meet the normal success conditions below.
2. Given a relevant bad input, old input, missing service, or input that exceeds an allowed limit, when the code handles it, then it reports the failure required by the PRD. It must not allow later steps to do something the rules forbid.
3. Given a feature that is outside Phase 1 or belongs only to a separate Phase 3 test, when checking the Phase 1 setup, then that feature has not been turned on as part of the normal Phase 1 run.

### Edge Cases

These are the normal and problem cases the checks must cover:

- **AC-001**: Find the existing connection code and the code that calls it. Make one real request to Codex within the allowed limits. Check the returned answer.
- **AC-002**: Try an allowed local caller, a missing or wrong session secret, and a local caller that is not allowed. Check who can access the local connection. Also check that it has not opened a TCP port, which would accept network connections.
- **AC-003**: Call Codex through the common Python entry point. Test a timeout, meaning the call takes too long. Test a missing or expired Codex login.
- **AC-004**: Read the code and settings. Check that requests for chat across several turns, streamed chat, or automatic model switching do not add those excluded features to Phase 1.
- **AC-005**: Check that each supported model call has a local record linked to the run that caused it. Internal labels used only to record or compare runs must stay local. Try to make a supported call skip the required recording step; it must not succeed without being recorded.

The architecture is the design document that says which code parts do each job and how they connect. It still needs to define how to cancel a call, handle an interrupted save, and keep old callers working where the PRD does not give those details. These designs must stop promptly on failure and keep the failure records. They must not add automatic recovery.

Recovery for several computers, a cloud service, or several users sharing the service is N/A, meaning it is outside this local, single-user task. The existing code has not yet been inspected in this work. Its current quality is still unknown.

## Requirements
### Functional Requirements

These are the things the code must do:

- **FR-001** (§3.0.1; §6.3): Inspect and reuse the existing connection code. A real JiuwenSwarm request, with one request and one reply and within the allowed limits, must reach the active Codex CLI. Read the reply and return it in the format JiuwenSwarm already expects. Do not require an enterprise API key.
- **FR-002** (§3.0.1; §2.9): Use only the protected local connection required by the PRD. This local way for two programs to talk is called IPC. Limit its permissions so only allowed local code can use it. Each session needs a short-lived secret, and its requests must be tied to the active JiuwenSwarm run. Do not open a TCP port for this connection. A local caller outside the allowed run context must not be able to use it.
- **FR-003** (§3.0.2): Let the system's model-routing code use the common Python entry point to call Codex. When a call times out or its Codex login stops working, record that failure in the local record of the run and its steps, called the run-tree. The record must show which run caused it. Do not report the failed call as a success.
- **FR-004** (§3.0.1 blacklist; §3.0.2 blacklist): Reuse the existing connection code. Do not build a new replacement server from scratch. Phase 1 handles one request and waits for its reply before the call finishes. Do not add automatic model switching or automatic recovery to Phase 1. Do not add complex chat across several turns with streamed replies.
- **FR-005** (§4.3.3, rules owned by M1-004): Supported model calls must go through the model-call path that M1-004 defines for recording calls. Keep enough local information to link a call to its run for checking and comparing results. Keep labels used only for that purpose out of the request sent to the model service. These labels include the workflow stage, agent role, and capsule ID. A capsule is the PRD's package of task instructions, inputs, and allowed actions. Use M1-004's shared rules and record format; do not create a second format here.

### Key Entities

The main things here are the request, the Codex reply, and the local call record. Their required behavior is described above.

[M1-IF-001@r0](TASK.md#4-embedded-cross-module-agreements) is the place reserved for the rules about using the Codex connection. Its exact input and output fields are PENDING_DESIGN, meaning the architecture still needs to define them.

[M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements) owns the shared rules for linking model calls to local run records. Use that agreement. Do not define another record format in this task.

## Success Criteria
### Measurable Outcomes

The table below lists what each check must show. The codes in the last column mean:

- **BLOCK**: check one part of this task's code.
- **BOUNDARY**: connect it to the real code or service that uses it, and check the call and result across that connection.
- **M1-SYSTEM**: the separate task that checks the whole M1 system from start to finish.

| AC ID | PRD section / requirement / story | What the check must show, including any required limits | Where the check is required |
| --- | --- | --- | --- |
| AC-001 | §3.0.1; §6.3 / FR-001 / US1 | The existing connection code has been inspected and reused. One real JiuwenSwarm request, with one request and one reply and within the allowed limits, reaches the active Codex CLI. The returned answer is read and put in the expected format. No enterprise API key is required. | BOUNDARY; M1-SYSTEM checks the full run. |
| AC-002 | §3.0.1; §2.9 / FR-002 / US1 | The connection uses only the protected local IPC required by the PRD. Its permissions limit access. Each session has a short-lived secret tied to the run. There is no TCP port for this connection. Local code outside the allowed run context cannot call it. | BLOCK, BOUNDARY; M1-SYSTEM checks the full run. |
| AC-003 | §3.0.2 / FR-003 / US1 | The model-routing code can use the common Python entry point. A timeout or loss of Codex login is recorded in the local run-tree, with the run that caused it. The failed call is not reported as a success. | BLOCK, BOUNDARY; M1-SYSTEM checks the full run. |
| AC-004 | §3.0.1 blacklist; §3.0.2 blacklist / FR-004 / US1 | The code reuses the existing connection code. It does not replace it with a new server from scratch. Phase 1 handles one request and waits for one reply. It does not add complex streamed chat across several turns, automatic model switching, or automatic recovery. | BLOCK, BOUNDARY; M1-SYSTEM checks the full run. |
| AC-005 | §4.3.3 / FR-005 / US1; M1-004 owns the shared recording rules. | Calls follow the recording path defined by M1-004. Each call can be linked locally to its run. A supported call cannot skip this recording. Internal stage, role, capsule, and similar labels used only to track or compare calls stay out of the prompt and model-service request. Keep the real task content. Missing reliable token-use or cost numbers does not make the call fail. Use the shared record format from M1-004. | BLOCK, BOUNDARY; M1-SYSTEM checks the full run. |

Read time and resource limits from the active capsule or task settings registered for the run. If a required number has not been supplied, mark it PENDING_SOURCE. Do not guess a time, token, cost, or quality limit. A token is a unit used to count model input and output. All software checks are still NOT_RUN, meaning they have not been run.

## Scope and Assumptions

**Included work**:

- Inspect and improve the existing code that connects JiuwenSwarm to Codex.
- Keep the current request and reply formats working.
- Protect the local connection and provide one common Python entry point for other parts of the system.

**Excluded work**:

- Building a replacement server from scratch.
- Complex streamed chat across several turns.
- Making an enterprise API key a requirement.
- Adding automatic model switching to Phase 1.

Keep the Python entry point usable as a possible future backup route when other model access is added. Setting up live switching between different model services is not part of this task's Phase 1 work.

**Whole-project rules**:

Apply PRD §1.3–§1.6 and §2.1–§2.12 to this task. Other TASKs own the code that carries out their parts of these rules.

- Use the scientific-workflow mode defined in the PRD. M1 is for one local user. Phase 1 follows the fixed step order in the PRD.
- Use only allowed evidence sources. Tools and actions must stay within the task's agreed rules. Set the research method and scoring rules before the run, and do not change them to suit a result.
- Independent checks must not change the work they inspect. Save the required gate decision before releasing work or letting later steps use it. The gate is the system step that decides whether work may move forward.
- Keep failure records. Follow the PRD's required human action when handling failures. Keep the agent's working memory separate from the saved system run records.
- Test RSI changes offline and turn them on only by manual action. RSI means experiments that try to improve the system itself.

**Agreements used from other tasks**:

- [M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements): local settings and security rules.
- [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements): the shared model-call recording rules.
- [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements): local run and failure records.

**Allowed model access**:

Phase 1 uses only the active Codex CLI connection, including for the Reviewer agent that checks work. This spec does not choose a model ID. Record the actual model name and version when testing. Do not add locally hosted model weights or the model pool from earlier design documents to this PRD task.

**Details still needed**:

Find the existing connection code, the code that calls it, and its tests before deciding what to change. The architecture must define the request and reply conversion, the local connection method, how session secrets are created and removed, how timeout and cancellation work, and where failure records are written. The Codex account has not been tested yet.

Architecture is supplied in [the current design](../../../../architecture/build-package/README.md). This holds up work that needs its design details. It does not stop work that can be prepared from the PRD alone. The full PRD sections and their exclusions still apply.

**Whole-system task**:

[M1-SYSTEM](../M1-SYSTEM/TASK.md) checks the full research run and the exact system version used in that run. M1-001 supplies the results for its own code and real connections. A small run that goes from A through the gate to B does not show that all of M1 is complete.

This file owns the success conditions. TASK.md owns agreements between parts. plan.md owns the design and check methods. tasks.md owns the work list, progress, and links to actual run results.
