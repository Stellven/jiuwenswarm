# Feature Specification: M0-001 — Audited Codex model bridge

**TASK**: [TASK.md](TASK.md) | **Parent**: [M0](../TASKS.md)
**Revision/date**: r3 / 2026-10-06 | **Branch**: ai4r_xiaoyang
**Scope authorities**: [PRD Phase 1](../source/PRD%20-%20AI4Research.txt) and [TRIAL-1 immediate plan](../source/build-package/immediate-plan.md), the product and architecture views of one M0 objective.

## User Scenarios & Testing

### User Story 1 — Complete the bounded trial responsibility (Priority: P1)

**Independent Test**: Source-labelled fixtures and actual required connections; mocks establish only wiring/control behavior.

**Acceptance Scenarios**:

1. Given Native model request/response examples and one real subscription-backed completion., when AC-001 is exercised, then Check standard role/content response mapping and original request ownership.
2. Given Local socket/pipe clients with correct, absent, expired and foreign credentials., when AC-002 is exercised, then Only the owned execution context can request the bounded completion.
3. Given Producer and verifier requests carrying distinct protected role assignments., when AC-003 is exercised, then Observe separate invocation/context identities without model selection by a capsule.
4. Given Responses with exact usage, account-only allowance, missing usage and timeout., when AC-004 is exercised, then Reconcile observed request/completion events with one local call record.
5. Given Canary credentials/private metadata, approved task data, timeout and duplicate-call attempts., when AC-005 is exercised, then Compare the provider payload to an independently approved disclosure manifest.
6. Given Correct/missing dependency, valid/expired subscription and supported/unsupported platform., when AC-006 is exercised, then Record runtime versions and real bounded request/response evidence.

### User Story 2 — Refuse invalid or unavailable work without acceptance (Priority: P1)

**Independent Test**: Source-labelled fixtures and actual required connections; mocks establish only wiring/control behavior.

**Acceptance Scenarios**:

1. Given Native model request/response examples and one real subscription-backed completion., when AC-001 is exercised, then Reject malformed transport messages, unsupported attachments/tools and unavailable authenticated runtime without fabricating a completion.
2. Given Local socket/pipe clients with correct, absent, expired and foreign credentials., when AC-002 is exercised, then Unauthorized session, permissive endpoint, unsupported secure IPC or foreign thread/turn blocks readiness.
3. Given Producer and verifier requests carrying distinct protected role assignments., when AC-003 is exercised, then Reject caller-selected unapproved route or shared producer assessment context.
4. Given Responses with exact usage, account-only allowance, missing usage and timeout., when AC-004 is exercised, then Missing required attribution blocks release; optional spend unavailable does not become zero or inferred usage.
5. Given Canary credentials/private metadata, approved task data, timeout and duplicate-call attempts., when AC-005 is exercised, then Deny credential/control-token leakage or a forbidden second invocation; timeout records DELIVERY_UNKNOWN where completion cannot be proven.
6. Given Correct/missing dependency, valid/expired subscription and supported/unsupported platform., when AC-006 is exercised, then Fail closed if mandatory security or model boundary is unavailable.

### User Story 3 — Retain inspectability and recover only through fresh attributable work (Priority: P1)

**Independent Test**: Source-labelled fixtures and actual required connections; mocks establish only wiring/control behavior.

**Acceptance Scenarios**:

1. Given Native model request/response examples and one real subscription-backed completion., when AC-001 is exercised, then Retain failed attempt; a corrected new invocation uses a fresh identity, with no automatic replay.
2. Given Local socket/pipe clients with correct, absent, expired and foreign credentials., when AC-002 is exercised, then Rotate credentials on owned-session restart; preserve evidence and never kill an unrelated interactive process.
3. Given Producer and verifier requests carrying distinct protected role assignments., when AC-003 is exercised, then A corrected fresh trial run after a failed invocation has a new attributable identity on the same static baseline; no replay, shared producer/verifier conversation or alternate-route retry.
4. Given Responses with exact usage, account-only allowance, missing usage and timeout., when AC-004 is exercised, then Late completion is recorded against its original call; no duplicate successful call record or reassignment.
5. Given Canary credentials/private metadata, approved task data, timeout and duplicate-call attempts., when AC-005 is exercised, then Preserve uncertainty and require explicit new work after inspection; transport recovery does not replay execution.
6. Given Correct/missing dependency, valid/expired subscription and supported/unsupported platform., when AC-006 is exercised, then Rechecking a repaired environment creates a new attributable diagnostic run.

### Edge Cases

The mapped cases cover applicable empty/malformed input, omitted/unsupported semantics, ambiguity/injection, stale/swapped subject, unsupported pin/profile, unavailable model/security, timeout/budget, persistence failure, duplicate request, cancellation, browser disconnect and restart without replay. Scientific/POC/RSI cases are excluded.

## Requirements

### Functional Requirements

- **FR-001**: Reuse the native Codex adapter through a standard model-completion boundary usable by the governed runner. Current authority: immediate-plan.md:L53-L85, immediate-plan.md:L87-L106.
- **FR-002**: Protect local IPC and execution ownership. Current authority: immediate-plan.md:L53-L85, immediate-plan.md:L87-L106.
- **FR-003**: Keep the static Codex work and verifier routes distinct in context but shared in audited transport. Current authority: immediate-plan.md:L53-L85, immediate-plan.md:L87-L106.
- **FR-004**: Capture locally attributable model calls and reliable usage only. Current authority: immediate-plan.md:L53-L85, immediate-plan.md:L87-L106.
- **FR-005**: Minimize provider disclosure and enforce time/call bounds. Current authority: immediate-plan.md:L53-L85, immediate-plan.md:L87-L106.
- **FR-006**: Establish startup diagnostics and baseline completion evidence. Current authority: immediate-plan.md:L53-L85, immediate-plan.md:L87-L106.

### Key Entities

ModelInvocation, CompletionObservation, immutable artifact/pin/profile identity; exact agreement in [TASK §4](TASK.md#m0-if-001-at-r2).

## Success Criteria

### Measurable Outcomes

| AC ID | Current scope source / FR | Observable criterion | Required checks |
| --- | --- | --- | --- |
| AC-001 | immediate-plan.md:L53-L85, immediate-plan.md:L87-L106; FR-001 | A bounded single-turn native model request returns a parsed completion or a typed failure to the originating invocation; actual CLI/dependency compatibility is established separately from source inspection. | B01; V01 BLOCK; V02 BOUNDARY |
| AC-002 | immediate-plan.md:L53-L85, immediate-plan.md:L87-L106; FR-002 | POSIX uses a Unix domain socket with restrictive permissions and ephemeral credential; supported Windows uses equivalent protected named pipe; no bridge TCP listener or other-session process is exposed. | B02; V03 BLOCK; V04 BOUNDARY |
| AC-003 | immediate-plan.md:L53-L85, immediate-plan.md:L87-L106; FR-003 | Phase 1 routes all supported work and verifier calls through the configured static bridge; verifier conversation is separate; no failed call silently selects an alternate model or new conversation retry. | B03; V05 BLOCK; V06 BOUNDARY |
| AC-004 | immediate-plan.md:L53-L85, immediate-plan.md:L87-L106; FR-004 | Every call records run/node/attempt/invocation/role/CC pins, endpoint, timestamps, measured duration and outcome locally; absent tokens/cost are unavailable, and account allowance is separately labelled. | B04; V07 BLOCK; V08 BOUNDARY |
| AC-005 | immediate-plan.md:L53-L85, immediate-plan.md:L87-L106; FR-005 | Local-only correlation identifiers are absent from provider prompts unless semantically required; scoped approved content only is sent, and configured time/invocation ceilings terminate work without retries. | B05; V09 BLOCK; V10 BOUNDARY |
| AC-006 | immediate-plan.md:L53-L85, immediate-plan.md:L87-L106; FR-006 | Readiness distinguishes authenticated model, secure IPC, installed dependency pin and unavailable capabilities; a mock wiring pass is never labelled real model integration. | B06; V11 BLOCK; V12 BOUNDARY |

Fixed finite required fixture assertions must all be met. Real model-backed claims require actual configured bridge, separate verifier and complete durable release/refusal evidence. Freeze challenge labels/repetitions/measurement policy before evaluating; report false acceptance/refusal and provider variability without inventing a universal reliability threshold.

## Scope and Assumptions

- Included: Provide the existing Codex-backed bounded model boundary required by the two-CC Intent trial: protected local IPC, fresh compiler/verifier contexts, static role routing, attributable measured outcomes, reliable available usage and explicit authentication/security readiness.
- Excluded: No model proxy product, interactive conversation upgrade, provider tools/browsing, alternate routes, fallback switching, inferred token/cost billing, full Stage 0 completion claim or live reliability claim from mocks.
- Exactly two authored CCs in implemented TRIAL-1; ordinary host checks/gating/control plane are infrastructure. This component does not establish a Phase 1 stage exit. Additional required Phase 1 capabilities have active SYSTEM owners.
- PRD Phase 1 requirements remain active alongside the TRIAL-1 realization. Immediate-plan exclusions bound this Intent component; SYSTEM owns the remaining Phase 1 requirements. Other architecture sources supply interpretation and future panorama, subject to the PRD product invariants and the registered conflict decisions.
- Verification produces structured reasons/evidence; gating applies advancement policy through protected durable host code. Applicable upstream intent-profile adaptation and documented inapplicable portions do not create science/citation features.
- Current static subscription Codex route; actual runtime model/version and reliable telemetry are observed, not guessed. No alternate routing or unsupported seed promise.
- Current work/progress/evidence lives in [tasks.md](tasks.md); required checks initially NOT_RUN.

## Joint Phase 1 allocation

USR-05 jointly activates PRD Delivery Phase 1 and the corresponding TRIAL-1 architecture view. This component retains its implemented Intent responsibilities and r2 interfaces. Its local exclusions limit this component realization; Phase 1 obligations beyond it are active owned gaps in [M0-SYSTEM AC-018 through AC-027](../M0-SYSTEM/spec.md), not future context. Exactly two authored CCs describes implemented TRIAL-1 only; it is not a Phase 1 capability ceiling. Phase 2 RSI and Phase 3 dynamic execution remain outside the selected Phase 1 target.

USR-05 changes program allocation, not the retained trial runtime or AC predicates. LOCAL-3 observations may be reused only for the same unchanged trial assertions after exact execution-input comparison; they cannot establish a new Phase 1 stage, full Brief, work Node B or end-to-end exit. The broadened SYSTEM documentary AC-001 is renewed at r3; [fresh alignment observations](../M0-SYSTEM/evidence/RUN-20261006-JOINT-ALIGNMENT-R3.md) establish documentary consistency only. New SYSTEM AC-018 through AC-027 remain unaccepted with NOT_RUN/BLOCKED statuses until their required work and connected checks are observed. Historical r1/r2 source interpretations and evidence are preserved; the former sole-authority interpretation is superseded.
