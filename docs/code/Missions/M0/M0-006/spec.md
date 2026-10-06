# Feature Specification: M0-006 — Fixed trial contracts and gate-locked lifecycle

**TASK**: [TASK.md](TASK.md) | **Parent**: [M0](../TASKS.md)
**Revision/date**: r3 / 2026-10-06 | **Branch**: ai4r_xiaoyang
**Scope authorities**: [PRD Phase 1](../source/PRD%20-%20AI4Research.txt) and [TRIAL-1 immediate plan](../source/build-package/immediate-plan.md), the product and architecture views of one M0 objective.

## User Scenarios & Testing

### User Story 1 — Complete the bounded trial responsibility (Priority: P1)

**Independent Test**: Source-labelled fixtures and actual required connections; mocks establish only wiring/control behavior.

**Acceptance Scenarios**:

1. Given Two requests with different explicit scope/constraints, correct original reference, candidate substituted as input, unknown authority field and producer-selected favorable rubric., when AC-002 is exercised, then Construct attributable immutable work contract and verifier assignment from protected configuration and qualified original input.
2. Given Activation/configuration change after freeze, suspended pin, altered original/profile hash, missing authenticated bridge/storage/security readiness and unsupported seed., when AC-003 is exercised, then Use the original frozen eligible versions and record observed rather than assumed readiness.
3. Given Delayed/failed decision commit, candidate mutation after assessment, forged producer PASS, durable accepted reference and restart inspection., when AC-004 is exercised, then Publish exactly the committed accepted intermediate artifact once the protected gate permits release.
4. Given Compiler fault, Tier-1 failure, verifier uncertainty/timeout, persistence fault, cancellation and late evidence from interrupted owned work., when AC-005 is exercised, then Persist the blocking reason and applicable observations, leave no accepted artifact, and stop later calls.
5. Given Browser disconnect during compilation, restart during each trial phase, restart after accepted commit, web halt and headless unavailable/timeout/uncertain cases with a prompt trap., when AC-006 is exercised, then Continue after browser disconnect; preserve accepted output across restart; show/return the recorded reason for halted work.
6. Given Independent event-order ledger for successful run, deterministic refusal, missing definition/readiness, semantic refusal and attempted extra/dynamic CC insertion., when AC-007 is exercised, then Observe exactly one compiler dispatch and, after mandatory deterministic success only, one separate verifier dispatch, followed by exact committed release.

### User Story 2 — Refuse invalid or unavailable work without acceptance (Priority: P1)

**Independent Test**: Source-labelled fixtures and actual required connections; mocks establish only wiring/control behavior.

**Acceptance Scenarios**:

1. Given Two requests with different explicit scope/constraints, correct original reference, candidate substituted as input, unknown authority field and producer-selected favorable rubric., when AC-002 is exercised, then Reject absent attribution, wrong input identity, widened authority, unknown governance field or producer-authored mandatory policy.
2. Given Activation/configuration change after freeze, suspended pin, altered original/profile hash, missing authenticated bridge/storage/security readiness and unsupported seed., when AC-003 is exercised, then Reject changed snapshot, stale/ineligible pin and unavailable mandatory prerequisite; do not select a newer version or hidden fallback.
3. Given Delayed/failed decision commit, candidate mutation after assessment, forged producer PASS, durable accepted reference and restart inspection., when AC-004 is exercised, then Keep candidate unaccepted during partial persistence, stale/swapped decision or non-advancing verdict; no downstream work or UI event can bypass the lock.
4. Given Compiler fault, Tier-1 failure, verifier uncertainty/timeout, persistence fault, cancellation and late evidence from interrupted owned work., when AC-005 is exercised, then Reject repair/retry instructions from the candidate/verifier or control response; no continuation after halt.
5. Given Browser disconnect during compilation, restart during each trial phase, restart after accepted commit, web halt and headless unavailable/timeout/uncertain cases with a prompt trap., when AC-006 is exercised, then Never resume interrupted model work, replay lost calls or block headless completion on human input.
6. Given Independent event-order ledger for successful run, deterministic refusal, missing definition/readiness, semantic refusal and attempted extra/dynamic CC insertion., when AC-007 is exercised, then Reject reordered/skipped checks, extra runtime CC, duplicate compiler/verifier dispatch and any accepted publication before durable decision.

### User Story 3 — Retain inspectability and recover only through fresh attributable work (Priority: P1)

**Independent Test**: Source-labelled fixtures and actual required connections; mocks establish only wiring/control behavior.

**Acceptance Scenarios**:

1. Given Two requests with different explicit scope/constraints, correct original reference, candidate substituted as input, unknown authority field and producer-selected favorable rubric., when AC-002 is exercised, then A corrected submission creates a fresh contract/run; preserve the old contract and failed candidate without requiring a future Brief.
2. Given Activation/configuration change after freeze, suspended pin, altered original/profile hash, missing authenticated bridge/storage/security readiness and unsupported seed., when AC-003 is exercised, then Fresh corrected work receives a new snapshot; the halted run retains its original identities and readiness observations.
3. Given Delayed/failed decision commit, candidate mutation after assessment, forged producer PASS, durable accepted reference and restart inspection., when AC-004 is exercised, then Reconstruct accepted-reference visibility from durable state after restart without rerunning compiler/verifier or converting interrupted work to PASS.
4. Given Compiler fault, Tier-1 failure, verifier uncertainty/timeout, persistence fault, cancellation and late evidence from interrupted owned work., when AC-005 is exercised, then A corrected user submission creates a fresh linked run and retains every prior failed/uncertain observation.
5. Given Browser disconnect during compilation, restart during each trial phase, restart after accepted commit, web halt and headless unavailable/timeout/uncertain cases with a prompt trap., when AC-006 is exercised, then Inspection retrieves the old run unchanged; user correction starts a new run rather than resuming the paused attempt.
6. Given Independent event-order ledger for successful run, deterministic refusal, missing definition/readiness, semantic refusal and attempted extra/dynamic CC insertion., when AC-007 is exercised, then After a halt/interruption preserve the recorded sequence; a fresh corrected submission starts a new attributable sequence without replay.

### Edge Cases

The mapped cases cover applicable empty/malformed input, omitted/unsupported semantics, ambiguity/injection, stale/swapped subject, unsupported pin/profile, unavailable model/security, timeout/budget, persistence failure, duplicate request, cancellation, browser disconnect and restart without replay. Scientific/POC/RSI cases are excluded.

## Requirements

### Functional Requirements

- **FR-002**: Assemble the protected run-specific intent-node contract and separate verifier assignment before dispatch. Current authority: immediate-plan.md:L72-L79, immediate-plan.md:L81-L81.
- **FR-003**: Freeze trial pins and requested/effective configuration while rechecking actual readiness and eligibility. Current authority: immediate-plan.md:L74-L74, immediate-plan.md:L79-L79, immediate-plan.md:L91-L91.
- **FR-004**: Expose accepted intent only after the exact advancing gate decision and artifact reference are durably committed. Current authority: immediate-plan.md:L59-L59, immediate-plan.md:L75-L76, immediate-plan.md:L83-L83, immediate-plan.md:L119-L119.
- **FR-005**: Halt trial dispatch on blocking faults and preserve original failure and in-flight evidence. Current authority: immediate-plan.md:L66-L66, immediate-plan.md:L83-L85.
- **FR-006**: Preserve browser-independent work and restart-safe inspection with mode-correct failure routing. Current authority: immediate-plan.md:L66-L66, immediate-plan.md:L72-L72, immediate-plan.md:L85-L85, immediate-plan.md:L114-L114.
- **FR-007**: Execute only the fixed connected intent trial sequence with exactly two authored CCs. Current authority: immediate-plan.md:L49-L51, immediate-plan.md:L57-L59, immediate-plan.md:L79-L79, immediate-plan.md:L83-L83, immediate-plan.md:L106-L106.

### Key Entities

TrialPreparationBinding, FrozenIntentExecution, immutable artifact/pin/profile identity; exact agreement in [TASK §4](TASK.md#m0-if-006-at-r2).

## Success Criteria

### Measurable Outcomes

| AC ID | Current scope source / FR | Observable criterion | Required checks |
| --- | --- | --- | --- |
| AC-002 | immediate-plan.md:L72-L79, immediate-plan.md:L81-L81; FR-002 | Bind stable product-user/workspace/run/node/attempt attribution, exact original text reference, input/output responsibilities, typed intermediate-intent obligations, the two admitted implementation/dependency pins, separately protected fidelity/check profile, role configuration, mode and time/call limits. Reusable declarations are not nodes/contracts. The original request plus protected trial template establishes obligations before any Research Brief; no chosen method, scientific metrics or user-confirmation gate is forced into the payload. | B02; V03 BLOCK; V04 BOUNDARY |
| AC-003 | immediate-plan.md:L74-L74, immediate-plan.md:L79-L79, immediate-plan.md:L91-L91; FR-003 | Before execution freeze two declaration/implementation/dependency identities, protected profile/policy, original reference, product-user/workspace/run attribution, model roles, mode, time/call limits and requested/effective seed with explicit unsupported control. Pointer/configuration changes cannot alter a running snapshot; current suspension and missing actual model/storage/security readiness block start/release without substitution. Only the trial's actual prerequisites are implemented, not a general planning predicate engine. | B03; V05 BLOCK; V06 BOUNDARY |
| AC-004 | immediate-plan.md:L59-L59, immediate-plan.md:L75-L76, immediate-plan.md:L83-L83, immediate-plan.md:L119-L119; FR-004 | Authoritative run state drives visible pending/running/evaluating/completed/blocked projections. Producer completion, native cache or assessor boolean cannot expose accepted intent. Only PASS/PASS_WITH_KNOWN_LIMITATIONS with all mandatory obligations and exact subject binding permits publication after required persistence. The trial has no required research successor/work Node B; the semantic verifier is not a demonstration work consumer. | B04; V07 BLOCK; V08 BOUNDARY |
| AC-005 | immediate-plan.md:L66-L66, immediate-plan.md:L83-L85; FR-005 | Execution/security/budget/evidence/verification faults stop new dispatch; failed prerequisites leave later calls NOT_RUN. No autonomous fix, requeue, replan or correction. Retain candidate/raw assessment/check/decision/attempt identities and reason; record cancellation, interruption and unknown delivery distinctly rather than pretending prior effects were undone. | B05; V09 BLOCK; V10 BOUNDARY |
| AC-006 | immediate-plan.md:L66-L66, immediate-plan.md:L72-L72, immediate-plan.md:L85-L85, immediate-plan.md:L114-L114; FR-006 | Closing the browser does not cancel submitted work. Restart preserves accepted artifacts and marks interrupted work paused without automatic replay or in-place resumption. Web failures expose a durable correlated reason/action request in the existing surface; headless failures return stable nonzero status and machine-readable run/bundle references without any prompt. Shared routing remains extensible for later native TUI triage but no TUI is required now. | B06; V11 BLOCK; V12 BOUNDARY |
| AC-007 | immediate-plan.md:L49-L51, immediate-plan.md:L57-L59, immediate-plan.md:L79-L79, immediate-plan.md:L83-L83, immediate-plan.md:L106-L106; FR-007 | The protected sequence is qualify/persist run and configuration, compile once, capture candidate/evidence, deterministic checks, separate semantic verifier only if eligible, validate and durably commit decision, then ordinary control-plane accepted output or halt. No planner/research graph/internal composition/Delivery CC is created. Both calls share the governed runner; required checks and gate application remain host infrastructure, not extra authored CCs. | B07; V13 BLOCK; V14 BOUNDARY |

Fixed finite required fixture assertions must all be met. Real model-backed claims require actual configured bridge, separate verifier and complete durable release/refusal evidence. Freeze challenge labels/repetitions/measurement policy before evaluating; report false acceptance/refusal and provider variability without inventing a universal reliability threshold.

## Scope and Assumptions

- Included: Assemble the protected intent-node contract and separately recorded intent-verifier assignment, freeze the two exact pins and effective trial context, and run the fixed once-only sequence to durable accepted intent or halt. Retain M0-006 and M0-IF-006 identities.
- Excluded: No full 3.1-3.9 research graph, planner, Requirement compiler/Research Brief, downstream research nodes, dynamic retrieval/binding/routing, internal composition, parallel hypotheses, distributed dispatch, active-version substitution, automatic repair/requeue/replay, in-place resumption or TUI implementation. Trial release does not claim Stage 1 work-Node-B or complete Stage 2 acceptance.
- Exactly two authored CCs in implemented TRIAL-1; ordinary host checks/gating/control plane are infrastructure. This component does not establish a Phase 1 stage exit. Additional required Phase 1 capabilities have active SYSTEM owners.
- PRD Phase 1 requirements remain active alongside the TRIAL-1 realization. Immediate-plan exclusions bound this Intent component; SYSTEM owns the remaining Phase 1 requirements. Other architecture sources supply interpretation and future panorama, subject to the PRD product invariants and the registered conflict decisions.
- Verification produces structured reasons/evidence; gating applies advancement policy through protected durable host code. Applicable upstream intent-profile adaptation and documented inapplicable portions do not create science/citation features.
- Current static subscription Codex route; actual runtime model/version and reliable telemetry are observed, not guessed. No alternate routing or unsupported seed promise.
- Current work/progress/evidence lives in [tasks.md](tasks.md); required checks initially NOT_RUN.
- SCOPE-STAGE-EXIT: A compiler followed by a semantic verifier is not the Stage 1 governed work Node A -> Gate -> work Node B demonstration. Affected AC-004, AC-007 and acceptance reporting. Resolve: Claim only trial accepted/blocked publication. Complete Stage 1 and Stage 2 criteria are active under SYSTEM AC-019/AC-020. Implement and verify actual work Node B and the full Brief/static native SwarmFlow rather than relabeling the existing verifier or retrieval as downstream work.

## Joint Phase 1 allocation

USR-05 jointly activates PRD Delivery Phase 1 and the corresponding TRIAL-1 architecture view. This component retains its implemented Intent responsibilities and r2 interfaces. Its local exclusions limit this component realization; Phase 1 obligations beyond it are active owned gaps in [M0-SYSTEM AC-018 through AC-027](../M0-SYSTEM/spec.md), not future context. Exactly two authored CCs describes implemented TRIAL-1 only; it is not a Phase 1 capability ceiling. Phase 2 RSI and Phase 3 dynamic execution remain outside the selected Phase 1 target.

USR-05 changes program allocation, not the retained trial runtime or AC predicates. LOCAL-3 observations may be reused only for the same unchanged trial assertions after exact execution-input comparison; they cannot establish a new Phase 1 stage, full Brief, work Node B or end-to-end exit. The broadened SYSTEM documentary AC-001 is renewed at r3; [fresh alignment observations](../M0-SYSTEM/evidence/RUN-20261006-JOINT-ALIGNMENT-R3.md) establish documentary consistency only. New SYSTEM AC-018 through AC-027 remain unaccepted with NOT_RUN/BLOCKED statuses until their required work and connected checks are observed. Historical r1/r2 source interpretations and evidence are preserved; the former sole-authority interpretation is superseded.
