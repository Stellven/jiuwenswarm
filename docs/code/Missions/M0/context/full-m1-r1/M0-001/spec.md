# Feature Specification: M0-001 — Audited Codex model bridge

**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M0](../TASKS.md)
**Revision / date**: r1 / 2026-10-06
**Feature Branch**: ai4r_xiaoyang; directory identity is independent of branch
**Input**: PRD 3.0 (../source/PRD - AI4Research.txt:L641-L644); PRD 3.0.1 (../source/PRD - AI4Research.txt:L645-L658); PRD 3.0.2 (../source/PRD - AI4Research.txt:L659-L670); PRD 4.3.2 (../source/PRD - AI4Research.txt:L1742-L1755); PRD 4.3.3 (../source/PRD - AI4Research.txt:L1756-L1778); PRD 4.3.4 (../source/PRD - AI4Research.txt:L1779-L1796); PRD 6.3 (../source/PRD - AI4Research.txt:L2553-L2571); architecture placement.md, contracts-and-native-reuse.md, immediate-plan.md, principles.md; parent immutable source manifest
**Status**: Specified for preparation; runtime NOT_RUN

## User Scenarios & Testing

### User Story 1 — Complete the bounded declared outcome (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Native model request/response examples and one real subscription-backed completion., when the AC-001 operation is exercised, then Check standard role/content response mapping and original request ownership.
2. Given Local socket/pipe clients with correct, absent, expired and foreign credentials., when the AC-002 operation is exercised, then Only the owned execution context can request the bounded completion.
3. Given Producer and verifier requests carrying distinct protected role assignments., when the AC-003 operation is exercised, then Observe separate invocation/context identities without model selection by a capsule.
4. Given Responses with exact usage, account-only allowance, missing usage and timeout., when the AC-004 operation is exercised, then Reconcile observed request/completion events with one local call record.
5. Given Canary credentials/private metadata, approved task data, timeout and duplicate-call attempts., when the AC-005 operation is exercised, then Compare the provider payload to an independently approved disclosure manifest.
6. Given Correct/missing dependency, valid/expired subscription and supported/unsupported platform., when the AC-006 operation is exercised, then Record runtime versions and real bounded request/response evidence.

### User Story 2 — Reject invalid or inadmissible work without advancement (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Native model request/response examples and one real subscription-backed completion., when the AC-001 operation is exercised, then Reject malformed transport messages, unsupported attachments/tools and unavailable authenticated runtime without fabricating a completion.
2. Given Local socket/pipe clients with correct, absent, expired and foreign credentials., when the AC-002 operation is exercised, then Unauthorized session, permissive endpoint, unsupported secure IPC or foreign thread/turn blocks readiness.
3. Given Producer and verifier requests carrying distinct protected role assignments., when the AC-003 operation is exercised, then Reject caller-selected unapproved route or shared producer assessment context.
4. Given Responses with exact usage, account-only allowance, missing usage and timeout., when the AC-004 operation is exercised, then Missing required attribution blocks release; optional spend unavailable does not become zero or inferred usage.
5. Given Canary credentials/private metadata, approved task data, timeout and duplicate-call attempts., when the AC-005 operation is exercised, then Deny credential/control-token leakage or a forbidden second invocation; timeout records DELIVERY_UNKNOWN where completion cannot be proven.
6. Given Correct/missing dependency, valid/expired subscription and supported/unsupported platform., when the AC-006 operation is exercised, then Fail closed if mandatory security or model boundary is unavailable.

### User Story 3 — Recover inspectability without silent replay or overwritten evidence (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Native model request/response examples and one real subscription-backed completion., when the AC-001 operation is exercised, then Retain failed attempt; a corrected new invocation uses a fresh identity, with no automatic replay.
2. Given Local socket/pipe clients with correct, absent, expired and foreign credentials., when the AC-002 operation is exercised, then Rotate credentials on owned-session restart; preserve evidence and never kill an unrelated interactive process.
3. Given Producer and verifier requests carrying distinct protected role assignments., when the AC-003 operation is exercised, then An explicitly selected new baseline run after a failed experimental run is separately attributable.
4. Given Responses with exact usage, account-only allowance, missing usage and timeout., when the AC-004 operation is exercised, then Late completion is recorded against its original call; no duplicate successful call record or reassignment.
5. Given Canary credentials/private metadata, approved task data, timeout and duplicate-call attempts., when the AC-005 operation is exercised, then Preserve uncertainty and require explicit new work after inspection; transport recovery does not replay execution.
6. Given Correct/missing dependency, valid/expired subscription and supported/unsupported platform., when the AC-006 operation is exercised, then Rechecking a repaired environment creates a new attributable diagnostic run.

### Edge Cases

Each AC includes its normal, failure and recovery scenario above. Shared cases include missing/invalid inputs, foreign or stale artifact/contract/implementation identity, unavailable required service, budget exhaustion, permission/disclosure escape, malformed assessment, cancelled or uncertain delivery, persistence failure, duplicate request, restart and incompatible revisions as applicable. Omissions require a source-based explanation in the implementing plan; an all-skipped suite is not acceptance.

## Requirements

### Functional Requirements

- **FR-001**: Reuse the native Codex adapter through a standard model-completion boundary usable by the governed runner. Source: PRD 3.0.1, PRD 6.3.
- **FR-002**: Protect local IPC and execution ownership. Source: PRD 3.0.1.
- **FR-003**: Keep the static Codex work and verifier routes distinct in context but shared in audited transport. Source: PRD 3.0.2, PRD 4.3.2, PRD 4.3.4.
- **FR-004**: Capture locally attributable model calls and reliable usage only. Source: PRD 3.0.2, PRD 4.3.3.
- **FR-005**: Minimize provider disclosure and enforce time/call bounds. Source: PRD 4.3.3, PRD 3.0.1.
- **FR-006**: Establish startup diagnostics and baseline completion evidence. Source: PRD 3.0, PRD 3.0.1, PRD 3.0.2, PRD 6.3.

### Key Entities

ModelInvocation, CompletionObservation, typed artifact reference, immutable input/implementation/profile pins, run/node/attempt/invocation identity and observable result. Exact semantics are owned by [TASK §4](TASK.md#m0-if-001-at-r1).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD 3.0.1, PRD 6.3; FR-001; US1/US2/US3 | A bounded single-turn native model request returns a parsed completion or a typed failure to the originating invocation; actual CLI/dependency compatibility is established separately from source inspection. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-002 | PRD 3.0.1; FR-002; US1/US2/US3 | POSIX uses a Unix domain socket with restrictive permissions and ephemeral credential; supported Windows uses equivalent protected named pipe; no bridge TCP listener or other-session process is exposed. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-003 | PRD 3.0.2, PRD 4.3.2, PRD 4.3.4; FR-003; US1/US2/US3 | Phase 1 routes all supported work and verifier calls through the configured static bridge; verifier conversation is separate; no failed call silently selects an alternate model or new conversation retry. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-004 | PRD 3.0.2, PRD 4.3.3; FR-004; US1/US2/US3 | Every call records run/node/attempt/invocation/role/CC pins, endpoint, timestamps, measured duration and outcome locally; absent tokens/cost are unavailable, and account allowance is separately labelled. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-005 | PRD 4.3.3, PRD 3.0.1; FR-005; US1/US2/US3 | Local-only correlation identifiers are absent from provider prompts unless semantically required; scoped approved content only is sent, and configured time/invocation ceilings terminate work without retries. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-006 | PRD 3.0, PRD 3.0.1, PRD 3.0.2, PRD 6.3; FR-006; US1/US2/US3 | Readiness distinguishes authenticated model, secure IPC, installed dependency pin and unavailable capabilities; a mock wiring pass is never labelled real model integration. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |

Mandatory behavior/failure constraints use exact source requirements; finite independent fixture cases must all meet their stated assertions. Source examples do not become arbitrary thresholds. Scientific thresholds are supplied/frozen for the run, not coding-agent inventions. Missing numeric policies are PENDING_SOURCE only for affected checks.

## Scope and Assumptions

- Included: Verify and adapt the existing subscription bridge for bounded synchronous governed model invocations, with protected local IPC, owned context and attributable outcomes.
- Excluded: No custom model proxy, broad conversational feature upgrade, provider tools, model training, inferred token billing or automatic model fallback; alternate routes belong to M0-019.
- Consumed agreements: No definition-time external agreement.
- Permitted models: Phase 1 uses the PRD static subscription-authenticated Codex route; do not invent model IDs or providers. Phase 3 uses only explicitly approved pinned profiles/endpoints; before approval, mocks/analysis are labelled. Relevant provider model identifier/version is captured from actual runtime, never assumed.
- Architecture D1–D15 applies by responsibility; D5/D6 are explicit adopted amendments, not silent unchanged compliance. M0 is the coding-program folder, M1 the product.
- Verification checks outputs and evidence; gating applies advancement policy. M1 mandatory integration preserves distinct responsibilities and protected durable verdict/release. All Tier-2 profiles consume M0-007 required upstream adaptation; no profile skips PRD 4.2.6 by using an unrelated generic prompt.
- System contribution: [M0-SYSTEM](../M0-SYSTEM/spec.md); this spec owns block/boundary acceptance and does not duplicate complete-system criteria.

This is the acceptance authority. Technical realization belongs in plan.md; work and current evidence are in tasks.md. No runtime acceptance is claimed by specification generation.
