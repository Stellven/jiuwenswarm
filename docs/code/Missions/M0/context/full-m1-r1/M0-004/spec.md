# Feature Specification: M0-004 — Governed capsule runner and enforced effects

**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M0](../TASKS.md)
**Revision / date**: r1 / 2026-10-06
**Feature Branch**: ai4r_xiaoyang; directory identity is independent of branch
**Input**: PRD 2.6 (../source/PRD - AI4Research.txt:L516-L533); PRD 2.9 (../source/PRD - AI4Research.txt:L567-L582); PRD 4.1.4 (../source/PRD - AI4Research.txt:L1266-L1283); PRD 4.6.3 (../source/PRD - AI4Research.txt:L2070-L2078); PRD 5.4.3 (../source/PRD - AI4Research.txt:L2410-L2418); architecture capsules.md, placement.md, guard-design.md, workflow.md; parent immutable source manifest
**Status**: Specified for preparation; runtime NOT_RUN

## User Scenarios & Testing

### User Story 1 — Complete the bounded declared outcome (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Single and multi-CC node with mismatched pins/inputs., when the AC-001 operation is exercised, then Observed implementation closure matches the requested admitted identity.
2. Given Two capsules with disjoint read/write/network permissions and escaped path attempts., when the AC-002 operation is exercised, then Approved scoped effect occurs and is recorded.
3. Given Allowed workspace file plus canary denied host path, process/network access and resource exhaustion., when the AC-003 operation is exercised, then Small permitted computation succeeds inside verified isolation.
4. Given Boundary-duration process, nested-call count and hung process., when the AC-004 operation is exercised, then Calls fit frozen limits and are counted once.
5. Given Successful/failed/cancelled invocations and unavailable optional metrics., when the AC-005 operation is exercised, then Aggregate all required invocations without erasing member failures.
6. Given Cached success, swallowed native exception, suspended pin and duplicate request., when the AC-006 operation is exercised, then Exact cached pure computation is labelled reused computation only where policy permits.

### User Story 2 — Reject invalid or inadmissible work without advancement (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Single and multi-CC node with mismatched pins/inputs., when the AC-001 operation is exercised, then Reject changed implementation, denied precondition and unsupported member invocation.
2. Given Two capsules with disjoint read/write/network permissions and escaped path attempts., when the AC-002 operation is exercised, then Deny permission union, undeclared tool, traversal/symlink escape and secret access before effects where enforceable.
3. Given Allowed workspace file plus canary denied host path, process/network access and resource exhaustion., when the AC-003 operation is exercised, then Deny scope escapes and block execution if platform cannot enforce the mandatory mechanism.
4. Given Boundary-duration process, nested-call count and hung process., when the AC-004 operation is exercised, then Reject unbounded recursion, undeclared internal CC and attempts beyond the call/time ceiling.
5. Given Successful/failed/cancelled invocations and unavailable optional metrics., when the AC-005 operation is exercised, then Missing release-essential observations produce non-advancing outcome.
6. Given Cached success, swallowed native exception, suspended pin and duplicate request., when the AC-006 operation is exercised, then Fail closed on unknown native outcome, missing actual observations or ungoverned nested call.

### User Story 3 — Recover inspectability without silent replay or overwritten evidence (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Single and multi-CC node with mismatched pins/inputs., when the AC-001 operation is exercised, then Failed call is preserved; no hidden replay or fallback invocation.
2. Given Two capsules with disjoint read/write/network permissions and escaped path attempts., when the AC-002 operation is exercised, then An observed violation halts dispatch and preserves attributable forensic records.
3. Given Allowed workspace file plus canary denied host path, process/network access and resource exhaustion., when the AC-003 operation is exercised, then Cleanup preserves original evidence and does not imply reversal of effects already performed.
4. Given Boundary-duration process, nested-call count and hung process., when the AC-004 operation is exercised, then Cancellation/uncertain completion remains distinct from failure and never triggers automatic replay.
5. Given Successful/failed/cancelled invocations and unavailable optional metrics., when the AC-005 operation is exercised, then Late in-flight evidence remains attributed to its original halted run.
6. Given Cached success, swallowed native exception, suspended pin and duplicate request., when the AC-006 operation is exercised, then Explicitly corrected rejected work starts a linked fresh run with required checking; no same-run retry, overwritten failure or automatic replay.

### Edge Cases

Each AC includes its normal, failure and recovery scenario above. Shared cases include missing/invalid inputs, foreign or stale artifact/contract/implementation identity, unavailable required service, budget exhaustion, permission/disclosure escape, malformed assessment, cancelled or uncertain delivery, persistence failure, duplicate request, restart and incompatible revisions as applicable. Omissions require a source-based explanation in the implementing plan; an all-skipped suite is not acceptance.

## Requirements

### Functional Requirements

- **FR-001**: Invoke only exact admitted implementation pins through the common runner. Source: PRD 4.1.4, PRD 2.6.
- **FR-002**: Intersect authority independently for every participating capsule. Source: PRD 2.6, PRD 4.1.4.
- **FR-003**: Establish actual unprivileged generated-code confinement. Source: PRD 2.9, PRD 5.4.3.
- **FR-004**: Bound time, invocation counts and nested work. Source: PRD 4.1.4, PRD 4.6.3.
- **FR-005**: Capture trustworthy execution evidence before node aggregation. Source: PRD 4.1.4, PRD 4.6.3.
- **FR-006**: Prevent native cache/retry semantics from bypassing governance. Source: PRD 4.1.4, PRD 2.6.

### Key Entities

GovernedInvocation, InvocationObservation, typed artifact reference, immutable input/implementation/profile pins, run/node/attempt/invocation identity and observable result. Exact semantics are owned by [TASK §4](TASK.md#m0-if-004-at-r1).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD 4.1.4, PRD 2.6; FR-001; US1/US2/US3 | Each call binds validated accepted inputs, declaration/interface hashes, role, run/node/attempt/invocation and frozen limits; work and verifier calls use the same execution capture boundary. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-002 | PRD 2.6, PRD 4.1.4; FR-002; US1/US2/US3 | A node can narrow each CC but never combine one CC permission with another; declared tools/files/network/effects are checked before and during execution. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-003 | PRD 2.9, PRD 5.4.3; FR-003; US1/US2/US3 | Generated execution cannot access host/control/profile/library/secret/hidden-fixture stores, undeclared network or Docker socket; mandatory enforced boundary has runtime evidence, not only prompt/import scanning. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-004 | PRD 4.1.4, PRD 4.6.3; FR-004; US1/US2/US3 | Finite invocation arrangement and node-wide plus call limits cover work and verifier calls; timeout terminates owned work and records actual outcome; unavailable token measurement is explicit. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-005 | PRD 4.1.4, PRD 4.6.3; FR-005; US1/US2/US3 | Inputs/outputs, stdout/stderr, route, timing, tool/effect observations, errors and limits are retained with invocation identity; observations disclose their blind spots rather than inferring absence of effects. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-006 | PRD 4.1.4, PRD 2.6; FR-006; US1/US2/US3 | Native helpers and caches may aid execution but cannot create authoritative PASS, re-dispatch uncertain effects, skip mandatory member checks or install capabilities during a run. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |

Mandatory behavior/failure constraints use exact source requirements; finite independent fixture cases must all meet their stated assertions. Source examples do not become arbitrary thresholds. Scientific thresholds are supplied/frozen for the run, not coding-agent inventions. Missing numeric policies are PENDING_SOURCE only for affected checks.

## Scope and Assumptions

- Included: Execute admitted pinned capabilities under the intersection of per-CC, node and run authority, capture per-invocation observations and enforce resource/effect limits.
- Excluded: No capability-created permission union, arbitrary installation, uncontrolled agent loops, automatic retries, host-wide effects or container-as-proof shortcut.
- Consumed agreements: [M0-IF-001@r1](../M0-001/TASK.md#m0-if-001-at-r1); [M0-IF-002@r1](../M0-002/TASK.md#m0-if-002-at-r1); [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1).
- Permitted models: Phase 1 uses the PRD static subscription-authenticated Codex route; do not invent model IDs or providers. Phase 3 uses only explicitly approved pinned profiles/endpoints; before approval, mocks/analysis are labelled. Relevant provider model identifier/version is captured from actual runtime, never assumed.
- Architecture D1–D15 applies by responsibility; D5/D6 are explicit adopted amendments, not silent unchanged compliance. M0 is the coding-program folder, M1 the product.
- Verification checks outputs and evidence; gating applies advancement policy. M1 mandatory integration preserves distinct responsibilities and protected durable verdict/release. All Tier-2 profiles consume M0-007 required upstream adaptation; no profile skips PRD 4.2.6 by using an unrelated generic prompt.
- System contribution: [M0-SYSTEM](../M0-SYSTEM/spec.md); this spec owns block/boundary acceptance and does not duplicate complete-system criteria.

This is the acceptance authority. Technical realization belongs in plan.md; work and current evidence are in tasks.md. No runtime acceptance is claimed by specification generation.
