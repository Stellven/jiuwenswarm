# Feature Specification: M0-003 — Trial capsule declarations and admitted two-definition library

**TASK**: [TASK.md](TASK.md) | **Parent**: [M0](../TASKS.md)
**Revision/date**: r3 / 2026-10-06 | **Branch**: ai4r_xiaoyang
**Scope authorities**: [PRD Phase 1](../source/PRD%20-%20AI4Research.txt) and [TRIAL-1 immediate plan](../source/build-package/immediate-plan.md), the product and architecture views of one M0 objective.

## User Scenarios & Testing

### User Story 1 — Complete the bounded trial responsibility (Priority: P1)

**Independent Test**: Source-labelled fixtures and actual required connections; mocks establish only wiring/control behavior.

**Acceptance Scenarios**:

1. Given Independently labelled compiler/verifier leaf declarations, unknown authority key, conflicting legacy/canonical shape, task-bound declaration and unsupported composite input., when AC-001 is exercised, then Round-trip the supported trial declarations and compare generated human-readable representations to the canonical declaration.
2. Given Two independently identified trial packages plus altered prompt/code/profile/dependency, missing resource, swapped compiler/verifier role and accidental research-stage seed., when AC-002 is exercised, then Startup resolves the two exact eligible packages and records the pins that actually execute.
3. Given Valid authored compiler/verifier candidates, failed integrity/self-test, incomplete independent review or characterization evidence and a mock-only evaluation., when AC-003 is exercised, then Retain a protected decision and actual check/review references for the exact eligible versions.
4. Given Admitted inactive and active compiler/verifier versions, unauthorized producer standing request, pointer change after freeze, suspended pinned version and explicit historical rollback., when AC-004 is exercised, then Resolve an authorized eligible selection for a fresh run and retain the standing action and selected identity.

### User Story 2 — Refuse invalid or unavailable work without acceptance (Priority: P1)

**Independent Test**: Source-labelled fixtures and actual required connections; mocks establish only wiring/control behavior.

**Acceptance Scenarios**:

1. Given Independently labelled compiler/verifier leaf declarations, unknown authority key, conflicting legacy/canonical shape, task-bound declaration and unsupported composite input., when AC-001 is exercised, then Reject unknown governance fields, conflicting representations and an attempt to make preserved composite/remote/RSI metadata executable.
2. Given Two independently identified trial packages plus altered prompt/code/profile/dependency, missing resource, swapped compiler/verifier role and accidental research-stage seed., when AC-002 is exercised, then Reject missing, stale, swapped, unadmitted or hash-mismatched resources; do not substitute another implementation or silently seed a future stage.
3. Given Valid authored compiler/verifier candidates, failed integrity/self-test, incomplete independent review or characterization evidence and a mock-only evaluation., when AC-003 is exercised, then Keep an incomplete or failed candidate inactive; refuse promotion from a producer boolean, missing evidence or mock-only live-acceptance claim.
4. Given Admitted inactive and active compiler/verifier versions, unauthorized producer standing request, pointer change after freeze, suspended pinned version and explicit historical rollback., when AC-004 is exercised, then Reject self-activation, unknown action, missing admission, removed historical version and execution/release of a suspended pin.

### User Story 3 — Retain inspectability and recover only through fresh attributable work (Priority: P1)

**Independent Test**: Source-labelled fixtures and actual required connections; mocks establish only wiring/control behavior.

**Acceptance Scenarios**:

1. Given Independently labelled compiler/verifier leaf declarations, unknown authority key, conflicting legacy/canonical shape, task-bound declaration and unsupported composite input., when AC-001 is exercised, then A corrected profile/declaration has a new identity and refreshed validation evidence; preserve original source bytes and failed candidate evidence.
2. Given Two independently identified trial packages plus altered prompt/code/profile/dependency, missing resource, swapped compiler/verifier role and accidental research-stage seed., when AC-002 is exercised, then A changed package requires a separately attributable candidate and fresh admission; historical run pins and closure evidence remain inspectable.
3. Given Valid authored compiler/verifier candidates, failed integrity/self-test, incomplete independent review or characterization evidence and a mock-only evaluation., when AC-003 is exercised, then Repair creates or rechecks the attributable candidate using fresh evidence; prior failures remain inspectable and runtime trial evidence remains separately scoped.
4. Given Admitted inactive and active compiler/verifier versions, unauthorized producer standing request, pointer change after freeze, suspended pinned version and explicit historical rollback., when AC-004 is exercised, then An explicit human rollback selects a retained admitted version for fresh work; affected halted runs retain their exact pins and evidence.

### Edge Cases

The mapped cases cover applicable empty/malformed input, omitted/unsupported semantics, ambiguity/injection, stale/swapped subject, unsupported pin/profile, unavailable model/security, timeout/budget, persistence failure, duplicate request, cancellation, browser disconnect and restart without replay. Scientific/POC/RSI cases are excluded.

## Requirements

### Functional Requirements

- **FR-001**: Define a versioned trial leaf-declaration profile preserving the complete field inventory without executing deferred mechanisms. Current authority: immediate-plan.md:L57-L57, immediate-plan.md:L79-L79, immediate-plan.md:L106-L106.
- **FR-002**: Pin the complete implementation/dependency closure and seed a registry for exactly the two trial CCs. Current authority: immediate-plan.md:L49-L49, immediate-plan.md:L57-L57, immediate-plan.md:L79-L79, immediate-plan.md:L91-L91.
- **FR-003**: Establish protected provisional admission evidence for the two trial definitions, distinct from runtime release. Current authority: immediate-plan.md:L57-L57, immediate-plan.md:L49-L49, immediate-plan.md:L91-L91, immediate-plan.md:L112-L114.
- **FR-004**: Separate admission from authenticated human-controlled standing and immutable trial run pins. Current authority: immediate-plan.md:L57-L57, immediate-plan.md:L74-L74, immediate-plan.md:L79-L79, immediate-plan.md:L91-L91.

### Key Entities

TrialCapsuleCandidate, PinnedTrialDefinitions, immutable artifact/pin/profile identity; exact agreement in [TASK §4](TASK.md#m0-if-003-at-r2).

## Success Criteria

### Measurable Outcomes

| AC ID | Current scope source / FR | Observable criterion | Required checks |
| --- | --- | --- | --- |
| AC-001 | immediate-plan.md:L57-L57, immediate-plan.md:L79-L79, immediate-plan.md:L106-L106; FR-001 | Each inventory concept has an explicit supported, compatibility-only or future disposition. The two definitions serialize identity/version, pinned implementation, applicable typed ports, dependencies, declared effects/checks and limits without losing authority-bearing meaning; make_capsule.md derives from capsule.json. Unknown or ambiguous authority fields, task/run fields inside a reusable declaration, and unsupported executable forms are rejected. Legacy source schemas remain unchanged; their inert flags cannot disable trial time/call limits or checks. | B01; V01 BLOCK; V02 BOUNDARY |
| AC-002 | immediate-plan.md:L49-L49, immediate-plan.md:L57-L57, immediate-plan.md:L79-L79, immediate-plan.md:L91-L91; FR-002 | The registry maps only intent compiler and intent verifier to exact declaration, prompt/alias, code, fidelity-profile/check resource and dependency identities, owning IF references, admission evidence and standing. Required referenced bytes/pins are checked before invocation; changed content cannot execute under the old identity. Credentials are protected references, never packaged values. No research-stage prompt or absent upstream body is fabricated. | B02; V03 BLOCK; V04 BOUNDARY |
| AC-003 | immediate-plan.md:L57-L57, immediate-plan.md:L49-L49, immediate-plan.md:L91-L91, immediate-plan.md:L112-L114; FR-003 | Declaration validity, integrity, required self-tests/development cases, provenance and compatibility are observed before eligibility. A self-authored success claim is insufficient. Required independently scoped review evidence and the protected admission decision bind exact pins; the guard-purpose verifier is characterized separately and terminates at a mechanically validated boundary, without a recursive semantic verifier or extra authored runtime CC. Mocked, skipped or unavailable checks cannot certify connected model-backed trial acceptance; provisional admission is not a truth guarantee. | B03; V05 BLOCK; V06 BOUNDARY |
| AC-004 | immediate-plan.md:L57-L57, immediate-plan.md:L74-L74, immediate-plan.md:L79-L79, immediate-plan.md:L91-L91; FR-004 | Only an authenticated human-controlled action changes activation, suspension, deprecation or rollback for the two trial definitions. Admission alone does not activate. Append-only version/standing history is retained; a run freezes activated or explicit admitted pins, active-pointer changes cannot replace them, and suspension prevents start/release without substitution. Startup validation does not autonomously promote an unadmitted version. | B04; V07 BLOCK; V08 BOUNDARY |

Fixed finite required fixture assertions must all be met. Real model-backed claims require actual configured bridge, separate verifier and complete durable release/refusal evidence. Freeze challenge labels/repetitions/measurement policy before evaluating; report false acceptance/refusal and provider variability without inventing a universal reliability threshold.

## Scope and Assumptions

- Included: Support only TRIAL-1 by packaging, admitting, human-activating and pinning the intent compiler and intent verifier as exactly two authored CCs. Preserve the declaration inventory through an explicit versioned trial profile and applicability/future disposition. Retain M0-003 and M0-IF-003 identities; broad r1 is historical future context.
- Excluded: No full research-stage registry/seeding, live creation/import/installation, composite execution, dynamic discovery, RSI generation/mutation/evolution execution, fusion, mid-run substitution, external publishing, third-party certification or general library-management UI. Preserved metadata does not enable a deferred mechanism.
- Exactly two authored CCs in implemented TRIAL-1; ordinary host checks/gating/control plane are infrastructure. This component does not establish a Phase 1 stage exit. Additional required Phase 1 capabilities have active SYSTEM owners.
- PRD Phase 1 requirements remain active alongside the TRIAL-1 realization. Immediate-plan exclusions bound this Intent component; SYSTEM owns the remaining Phase 1 requirements. Other architecture sources supply interpretation and future panorama, subject to the PRD product invariants and the registered conflict decisions.
- Verification produces structured reasons/evidence; gating applies advancement policy through protected durable host code. Applicable upstream intent-profile adaptation and documented inapplicable portions do not create science/citation features.
- Current static subscription Codex route; actual runtime model/version and reliable telemetry are observed, not guessed. No alternate routing or unsupported seed promise.
- Current work/progress/evidence lives in [tasks.md](tasks.md); required checks initially NOT_RUN.
- SRC-SCHEMA: The legacy machine schema and semantic inventory disagree on shapes/requiredness and policy epochs. Affected AC-001 and the trial reader/closure. Resolve: Document one supported versioned trial profile plus complete applicability/future disposition; preserve source files and reject ambiguous authority. Implement migration only if an actual trial input requires it.
- SCOPE-TWO-CCS: The broad r1 primary registry covers research-stage aliases not exercised by the trial. Affected AC-002 and startup seeding. Resolve: Seed exactly the intent compiler and intent verifier. Archive the broader registry as future context; retained metadata cannot enable another authored runtime CC.

## Joint Phase 1 allocation

USR-05 jointly activates PRD Delivery Phase 1 and the corresponding TRIAL-1 architecture view. This component retains its implemented Intent responsibilities and r2 interfaces. Its local exclusions limit this component realization; Phase 1 obligations beyond it are active owned gaps in [M0-SYSTEM AC-018 through AC-027](../M0-SYSTEM/spec.md), not future context. Exactly two authored CCs describes implemented TRIAL-1 only; it is not a Phase 1 capability ceiling. Phase 2 RSI and Phase 3 dynamic execution remain outside the selected Phase 1 target.

USR-05 changes program allocation, not the retained trial runtime or AC predicates. LOCAL-3 observations may be reused only for the same unchanged trial assertions after exact execution-input comparison; they cannot establish a new Phase 1 stage, full Brief, work Node B or end-to-end exit. The broadened SYSTEM documentary AC-001 is renewed at r3; [fresh alignment observations](../M0-SYSTEM/evidence/RUN-20261006-JOINT-ALIGNMENT-R3.md) establish documentary consistency only. New SYSTEM AC-018 through AC-027 remain unaccepted with NOT_RUN/BLOCKED statuses until their required work and connected checks are observed. Historical r1/r2 source interpretations and evidence are preserved; the former sole-authority interpretation is superseded.
