# Feature Specification: M0-004 — Bounded shared trial compiler/verifier runner

**TASK**: [TASK.md](TASK.md) | **Parent**: [M0](../TASKS.md)
**Revision/date**: r3 / 2026-10-06 | **Branch**: ai4r_xiaoyang
**Scope authorities**: [PRD Phase 1](../source/PRD%20-%20AI4Research.txt) and [TRIAL-1 immediate plan](../source/build-package/immediate-plan.md), the product and architecture views of one M0 objective.

## User Scenarios & Testing

### User Story 1 — Complete the bounded trial responsibility (Priority: P1)

**Independent Test**: Source-labelled fixtures and actual required connections; mocks establish only wiring/control behavior.

**Acceptance Scenarios**:

1. Given Two real connected trial invocations plus stale/swapped implementation pin, wrong original/candidate reference and unavailable configured bridge; isolated mocks are separately labelled development fixtures., when AC-001 is exercised, then Observe the requested eligible implementation closure and separate producer/verifier invocation identities.
2. Given Protected original/candidate context, credential and hidden-fixture canaries, attempted tool/shell/browse/control writes, unauthorized context reference and cross-role authority transfer., when AC-002 is exercised, then Only approved task-relevant text reaches each separate model invocation; required boundary evidence is retained.
3. Given Independently specified within-limit, call-ceiling, hung compiler, hung verifier, cancellation and unknown-delivery fixtures with actual ownership/call observations., when AC-004 is exercised, then Finish allowed calls within frozen ceilings and record actual count, duration and available measurements.
4. Given Successful, failed, cancelled, timed-out and response-loss invocations; missing release-essential evidence, unavailable optional telemetry and secret-bearing transport diagnostics., when AC-005 is exercised, then Persist attributable compiler and verifier observations and provide the gate only exact captured references.
5. Given Lost submission response with duplicate client request, same identity/different payload, native cached success, swallowed native failure, interrupted invocation and missing bridge with mock available., when AC-006 is exercised, then Return the durable existing run/observations for an identical reconciled request without another dispatch.

### User Story 2 — Refuse invalid or unavailable work without acceptance (Priority: P1)

**Independent Test**: Source-labelled fixtures and actual required connections; mocks establish only wiring/control behavior.

**Acceptance Scenarios**:

1. Given Two real connected trial invocations plus stale/swapped implementation pin, wrong original/candidate reference and unavailable configured bridge; isolated mocks are separately labelled development fixtures., when AC-001 is exercised, then Reject changed pin, invalid context or unavailable required integration before dispatch where detectable; later calls remain NOT_RUN.
2. Given Protected original/candidate context, credential and hidden-fixture canaries, attempted tool/shell/browse/control writes, unauthorized context reference and cross-role authority transfer., when AC-002 is exercised, then Block prohibited access, tools, disclosure or unavailable required security readiness; a correct-looking output cannot excuse a violation.
3. Given Independently specified within-limit, call-ceiling, hung compiler, hung verifier, cancellation and unknown-delivery fixtures with actual ownership/call observations., when AC-004 is exercised, then Prevent a call beyond the ceiling, halt on timeout, and keep the semantic call NOT_RUN after failed prerequisites.
4. Given Successful, failed, cancelled, timed-out and response-loss invocations; missing release-essential evidence, unavailable optional telemetry and secret-bearing transport diagnostics., when AC-005 is exercised, then Missing required evidence or failed persistence prevents acceptance; refuse secret leakage through evidence capture.
5. Given Lost submission response with duplicate client request, same identity/different payload, native cached success, swallowed native failure, interrupted invocation and missing bridge with mock available., when AC-006 is exercised, then Reject changed duplicate payload and unknown native completion as non-advancing; no cached/producer result creates accepted state.

### User Story 3 — Retain inspectability and recover only through fresh attributable work (Priority: P1)

**Independent Test**: Source-labelled fixtures and actual required connections; mocks establish only wiring/control behavior.

**Acceptance Scenarios**:

1. Given Two real connected trial invocations plus stale/swapped implementation pin, wrong original/candidate reference and unavailable configured bridge; isolated mocks are separately labelled development fixtures., when AC-001 is exercised, then Preserve failed/uncertain invocation evidence; only a corrected fresh run invokes again, with no fallback or hidden replay.
2. Given Protected original/candidate context, credential and hidden-fixture canaries, attempted tool/shell/browse/control writes, unauthorized context reference and cross-role authority transfer., when AC-002 is exercised, then Halt and preserve attributable observations after an attempted/observed violation; corrective work uses fresh protected configuration and a fresh run.
3. Given Independently specified within-limit, call-ceiling, hung compiler, hung verifier, cancellation and unknown-delivery fixtures with actual ownership/call observations., when AC-004 is exercised, then Cancellation, interruption and unknown completion remain distinct recorded outcomes; none schedules an automatic replay.
4. Given Successful, failed, cancelled, timed-out and response-loss invocations; missing release-essential evidence, unavailable optional telemetry and secret-bearing transport diagnostics., when AC-005 is exercised, then Retain late observations under the original halted run without rewriting the prior outcome or replaying work.
5. Given Lost submission response with duplicate client request, same identity/different payload, native cached success, swallowed native failure, interrupted invocation and missing bridge with mock available., when AC-006 is exercised, then A corrected submission receives a new run identity and preserves previous failure/unknown-delivery evidence.

### Edge Cases

The mapped cases cover applicable empty/malformed input, omitted/unsupported semantics, ambiguity/injection, stale/swapped subject, unsupported pin/profile, unavailable model/security, timeout/budget, persistence failure, duplicate request, cancellation, browser disconnect and restart without replay. Scientific/POC/RSI cases are excluded.

## Requirements

### Functional Requirements

- **FR-001**: Invoke the exact two admitted trial implementations through one scoped runner boundary. Current authority: immediate-plan.md:L49-L49, immediate-plan.md:L58-L58, immediate-plan.md:L74-L74, immediate-plan.md:L79-L79.
- **FR-002**: Enforce only the trial's declared model/context authority without permission transfer or forbidden tools. Current authority: immediate-plan.md:L64-L64, immediate-plan.md:L79-L79, immediate-plan.md:L91-L91.
- **FR-004**: Enforce frozen time/call ceilings over the finite trial invocation arrangement. Current authority: immediate-plan.md:L58-L58, immediate-plan.md:L79-L79, immediate-plan.md:L83-L83, immediate-plan.md:L91-L91.
- **FR-005**: Capture actual trial invocation evidence before assessment or accepted-artifact release. Current authority: immediate-plan.md:L61-L62, immediate-plan.md:L74-L76, immediate-plan.md:L79-L79, immediate-plan.md:L83-L83.
- **FR-006**: Prevent native caches, hidden retries and uncertain transport outcomes from bypassing the trial protocol. Current authority: immediate-plan.md:L66-L66, immediate-plan.md:L83-L83, immediate-plan.md:L91-L91.

### Key Entities

BoundTrialInvocation, TrialInvocationObservation, immutable artifact/pin/profile identity; exact agreement in [TASK §4](TASK.md#m0-if-004-at-r2).

## Success Criteria

### Measurable Outcomes

| AC ID | Current scope source / FR | Observable criterion | Required checks |
| --- | --- | --- | --- |
| AC-001 | immediate-plan.md:L49-L49, immediate-plan.md:L58-L58, immediate-plan.md:L74-L74, immediate-plan.md:L79-L79; FR-001 | Compiler and verifier invocations bind validated input references, declaration/interface/implementation/dependency identities, role, run/node/attempt/invocation and frozen limits. The verifier receives the original request and exact captured candidate in a separate protected invocation/context. Both use actual native integration and common outcome capture; unavailable model readiness is not replaced with a mock or alternate route. | B01; V01 BLOCK; V02 BOUNDARY |
| AC-002 | immediate-plan.md:L64-L64, immediate-plan.md:L79-L79, immediate-plan.md:L91-L91; FR-002 | Effective authority is narrowed independently for compiler and verifier. Neither can browse, run shell/project code, profile resources, mutate review subjects, read credentials/hidden challenge material or write control/gate state. Actual protected model integration/IPC and disclosure restrictions are verified; a prompt saying read-only or a container alone is insufficient evidence. Necessary evidence can be passed in a protected bounded context without adding a general-purpose broker service. | B02; V03 BLOCK; V04 BOUNDARY |
| AC-004 | immediate-plan.md:L58-L58, immediate-plan.md:L79-L79, immediate-plan.md:L83-L83, immediate-plan.md:L91-L91; FR-004 | Compile once, then invoke the semantic verifier only after deterministic eligibility; no internal CC calls or recursive verifier. Node-wide and per-invocation time/call controls cover both calls, count actual dispatch once and terminate owned timed-out work. Record requested/effective seed and unsupported seed/usage controls as unavailable; do not infer deterministic model output or fabricate token/cost measurements. | B04; V07 BLOCK; V08 BOUNDARY |
| AC-005 | immediate-plan.md:L61-L62, immediate-plan.md:L74-L76, immediate-plan.md:L79-L79, immediate-plan.md:L83-L83; FR-005 | Retain inputs/candidate/raw assessment references, actual route/model information when available, duration/call counts, stdout/stderr where exposed, error/timeout/cancellation and enforcement observations under exact run/node/attempt/CC/invocation identities. Required observations must persist before their dependent stage; unavailable optional measurements and observation blind spots are explicit, not inferred success. Credentials stay out of evidence. | B05; V09 BLOCK; V10 BOUNDARY |
| AC-006 | immediate-plan.md:L66-L66, immediate-plan.md:L83-L83, immediate-plan.md:L91-L91; FR-006 | Native helpers/cache state never create an authoritative PASS, skip checking, change pins or cause duplicate model dispatch. Reconcile a lost submit response by client request identity without a compiler retry; changed payload under the same identity is rejected. A mock profile remains wiring-only and cannot silently substitute for the real bridge. Browser close and service restart never trigger execution replay. | B06; V11 BLOCK; V12 BOUNDARY |

Fixed finite required fixture assertions must all be met. Real model-backed claims require actual configured bridge, separate verifier and complete durable release/refusal evidence. Freeze challenge labels/repetitions/measurement policy before evaluating; report false acceptance/refusal and provider variability without inventing a universal reliability threshold.

## Scope and Assumptions

- Included: Execute only the two admitted trial CCs through one governed native-model integration/capture boundary under their frozen contract, scoped context and time/call limits. Retain M0-004 and M0-IF-004 identities.
- Excluded: No generated POC execution, POC sandbox implementation, shell/browsing/resource profiling, arbitrary tool execution, internal CC composition, uncontrolled loops, capability installation, dynamic routing, automatic retries, uncertain-call replay or producer-written release.
- Exactly two authored CCs in implemented TRIAL-1; ordinary host checks/gating/control plane are infrastructure. This component does not establish a Phase 1 stage exit. Additional required Phase 1 capabilities have active SYSTEM owners.
- PRD Phase 1 requirements remain active alongside the TRIAL-1 realization. Immediate-plan exclusions bound this Intent component; SYSTEM owns the remaining Phase 1 requirements. Other architecture sources supply interpretation and future panorama, subject to the PRD product invariants and the registered conflict decisions.
- Verification produces structured reasons/evidence; gating applies advancement policy through protected durable host code. Applicable upstream intent-profile adaptation and documented inapplicable portions do not create science/citation features.
- Current static subscription Codex route; actual runtime model/version and reliable telemetry are observed, not guessed. No alternate routing or unsupported seed promise.
- Current work/progress/evidence lives in [tasks.md](tasks.md); required checks initially NOT_RUN.
- Q-TRIAL-MODEL-SECURITY: Existing native adapter source or container presence does not establish authenticated bounded model access or secure IPC. Affected AC-001, AC-002 and real connected acceptance. Resolve: Verify the actual configured bridge, process ownership, denied tools/context access and protected credential/IPC boundary. If unavailable, report ENVIRONMENT_BLOCKED; continue explicitly labelled isolated wiring preparation.

## Joint Phase 1 allocation

USR-05 jointly activates PRD Delivery Phase 1 and the corresponding TRIAL-1 architecture view. This component retains its implemented Intent responsibilities and r2 interfaces. Its local exclusions limit this component realization; Phase 1 obligations beyond it are active owned gaps in [M0-SYSTEM AC-018 through AC-027](../M0-SYSTEM/spec.md), not future context. Exactly two authored CCs describes implemented TRIAL-1 only; it is not a Phase 1 capability ceiling. Phase 2 RSI and Phase 3 dynamic execution remain outside the selected Phase 1 target.

USR-05 changes program allocation, not the retained trial runtime or AC predicates. LOCAL-3 observations may be reused only for the same unchanged trial assertions after exact execution-input comparison; they cannot establish a new Phase 1 stage, full Brief, work Node B or end-to-end exit. The broadened SYSTEM documentary AC-001 is renewed at r3; [fresh alignment observations](../M0-SYSTEM/evidence/RUN-20261006-JOINT-ALIGNMENT-R3.md) establish documentary consistency only. New SYSTEM AC-018 through AC-027 remain unaccepted with NOT_RUN/BLOCKED statuses until their required work and connected checks are observed. Historical r1/r2 source interpretations and evidence are preserved; the former sole-authority interpretation is superseded.
