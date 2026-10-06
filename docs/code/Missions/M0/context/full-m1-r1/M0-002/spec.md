# Feature Specification: M0-002 — Durable identity, profiles and effective configuration

**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M0](../TASKS.md)
**Revision / date**: r1 / 2026-10-06
**Feature Branch**: ai4r_xiaoyang; directory identity is independent of branch
**Input**: PRD 2.3 (../source/PRD - AI4Research.txt:L442-L466); PRD 5.4 (../source/PRD - AI4Research.txt:L2381-L2387); PRD 5.4.1 (../source/PRD - AI4Research.txt:L2388-L2401); PRD 5.4.2 (../source/PRD - AI4Research.txt:L2402-L2409); PRD 5.4.4 (../source/PRD - AI4Research.txt:L2419-L2432); PRD 5.6 (../source/PRD - AI4Research.txt:L2458-L2464); PRD 5.6.1 (../source/PRD - AI4Research.txt:L2465-L2473); PRD 5.6.2 (../source/PRD - AI4Research.txt:L2474-L2481); PRD 5.6.3 (../source/PRD - AI4Research.txt:L2482-L2489); PRD 5.6.4 (../source/PRD - AI4Research.txt:L2490-L2497); PRD 5.6.5 (../source/PRD - AI4Research.txt:L2498-L2518); architecture placement.md, m1-design.md, principles.md, guard-design.md, automation.md; parent immutable source manifest
**Status**: Specified for preparation; runtime NOT_RUN

## User Scenarios & Testing

### User Story 1 — Complete the bounded declared outcome (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Two account identifiers, one local execution context, restart and workspace deletion., when the AC-001 operation is exercised, then Verify profile settings persist while run assets remain explicitly selected.
2. Given Valid/invalid session credentials, cross-origin requests and exposed-interface configuration., when the AC-002 operation is exercised, then Native session remains usable by the intended local client.
3. Given User data, secret canaries, immutable decision records and scoped exports., when the AC-003 operation is exercised, then Export exactly the permitted data and display consequences before applicable product action.
4. Given Conflicting account/machine/project settings, seeded/unseedable model and invalid enum., when the AC-004 operation is exercised, then Use documented precedence account then machine then project; freeze the actual selected values.
5. Given At-limit/over-limit values and unavailable cost telemetry., when the AC-005 operation is exercised, then Resolve finite work and verifier budgets with combined compiler ceiling.
6. Given Baseline and experimental profiles plus attempted remote-worker settings., when the AC-006 operation is exercised, then Resolve one local host/workspace without enterprise scheduler.

### User Story 2 — Reject invalid or inadmissible work without advancement (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Two account identifiers, one local execution context, restart and workspace deletion., when the AC-001 operation is exercised, then Reject missing/foreign identity binding and implicit cross-run artifact import.
2. Given Valid/invalid session credentials, cross-origin requests and exposed-interface configuration., when the AC-002 operation is exercised, then Reject unauthenticated, cross-origin and stale-session operations before effects.
3. Given User data, secret canaries, immutable decision records and scoped exports., when the AC-003 operation is exercised, then Deny unauthorized or hidden-data requests and path escapes.
4. Given Conflicting account/machine/project settings, seeded/unseedable model and invalid enum., when the AC-004 operation is exercised, then Reject unknown governance settings and invalid model routes; unsupported seed control is recorded unavailable with requested/effective values, and blocks only an explicitly strict reproducibility profile requiring that control.
5. Given At-limit/over-limit values and unavailable cost telemetry., when the AC-005 operation is exercised, then Reject unbounded/negative limits and fabricated token measurements.
6. Given Baseline and experimental profiles plus attempted remote-worker settings., when the AC-006 operation is exercised, then Reject prohibited distributed settings and mid-run experimental substitution.

### User Story 3 — Recover inspectability without silent replay or overwritten evidence (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Two account identifiers, one local execution context, restart and workspace deletion., when the AC-001 operation is exercised, then Restart reloads the same stable account without restoring deleted research data.
2. Given Valid/invalid session credentials, cross-origin requests and exposed-interface configuration., when the AC-002 operation is exercised, then Credential rotation invalidates prior credentials without erasing run evidence.
3. Given User data, secret canaries, immutable decision records and scoped exports., when the AC-003 operation is exercised, then Interrupted cleanup preserves a truthful partial outcome and separately durable profile.
4. Given Conflicting account/machine/project settings, seeded/unseedable model and invalid enum., when the AC-004 operation is exercised, then Settings changed after freeze apply only to a new run.
5. Given At-limit/over-limit values and unavailable cost telemetry., when the AC-005 operation is exercised, then Budget correction requires new frozen configuration, not a live ceiling increase.
6. Given Baseline and experimental profiles plus attempted remote-worker settings., when the AC-006 operation is exercised, then Disabling experiment does not erase its failed evidence.

### Edge Cases

Each AC includes its normal, failure and recovery scenario above. Shared cases include missing/invalid inputs, foreign or stale artifact/contract/implementation identity, unavailable required service, budget exhaustion, permission/disclosure escape, malformed assessment, cancelled or uncertain delivery, persistence failure, duplicate request, restart and incompatible revisions as applicable. Omissions require a source-based explanation in the implementing plan; an all-skipped suite is not acceptance.

## Requirements

### Functional Requirements

- **FR-001**: Maintain a durable attributable product account and profile separately from runs/workspaces. Source: PRD 2.3, PRD 5.4.1.
- **FR-002**: Authenticate the loopback control plane and protect session bootstrap. Source: PRD 5.4.2.
- **FR-003**: Respect export/delete and privacy boundaries without erasing protected acceptance history silently. Source: PRD 5.4.4.
- **FR-004**: Resolve account defaults, machine-local and project overrides into an immutable effective run profile. Source: PRD 5.6.1, PRD 5.6.2, PRD 5.6.5.
- **FR-005**: Expose and enforce budgets according to measurable dimensions. Source: PRD 5.6.3, PRD 5.6.1.
- **FR-006**: Preserve one active authorized local execution context and Phase 3 configuration isolation. Source: PRD 5.6.4, PRD 2.3.

### Key Entities

ExecutionProfileRequest, EffectiveExecutionProfile, typed artifact reference, immutable input/implementation/profile pins, run/node/attempt/invocation identity and observable result. Exact semantics are owned by [TASK §4](TASK.md#m0-if-002-at-r1).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD 2.3, PRD 5.4.1; FR-001; US1/US2/US3 | Account/profile survives run/workspace deletion and binds every submission to user/workspace/run; local OS account never substitutes for stable product identity. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-002 | PRD 5.4.2; FR-002; US1/US2/US3 | Authenticated local requests have scoped capability; untrusted origin/session or non-loopback exposure cannot submit, retrieve protected evidence, or mutate control state. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-003 | PRD 5.4.4; FR-003; US1/US2/US3 | The user can inspect, export and explicitly remove local project inputs, artifacts and execution records; workspace deletion is distinct from account deletion. Authorized deletion records its effect and invalidates evidence-availability claims; automatic cleanup cannot silently erase release-essential evidence. Credentials and hidden fixtures never enter ordinary exports/provider contexts. No enterprise retention or legal hold is introduced. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-004 | PRD 5.6.1, PRD 5.6.2, PRD 5.6.5; FR-004; US1/US2/US3 | Requested/effective settings, source precedence, seed support, profile/version and limits are recorded before work; unsupported settings are rejected or explicitly unavailable, never silently effective. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-005 | PRD 5.6.3, PRD 5.6.1; FR-005; US1/US2/US3 | Time and invocation ceilings are positive bounded configuration; unreliable token/cost enforcement remains unavailable while declared constraints are preserved; allowance is not per-call usage. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-006 | PRD 5.6.4, PRD 2.3; FR-006; US1/US2/US3 | Phase 1 does not enable distributed cluster settings or remote workers; alternate compiler/planner/routes are explicit separate profiles whose disable action restores baseline for a new run. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |

Mandatory behavior/failure constraints use exact source requirements; finite independent fixture cases must all meet their stated assertions. Source examples do not become arbitrary thresholds. Scientific thresholds are supplied/frozen for the run, not coding-agent inventions. Missing numeric policies are PENDING_SOURCE only for affected checks.

## Scope and Assumptions

- Included: Separate stable product identity/profile storage from local research workspace lifetime; resolve reproducible configuration and enforce local session/disclosure/privacy controls.
- Excluded: No enterprise tenants, cloud vendor requirement, remote execution control, distributed quota/billing, or silent reuse of unrelated research.
- Consumed agreements: No definition-time external agreement.
- Permitted models: Phase 1 uses the PRD static subscription-authenticated Codex route; do not invent model IDs or providers. Phase 3 uses only explicitly approved pinned profiles/endpoints; before approval, mocks/analysis are labelled. Relevant provider model identifier/version is captured from actual runtime, never assumed.
- Architecture D1–D15 applies by responsibility; D5/D6 are explicit adopted amendments, not silent unchanged compliance. M0 is the coding-program folder, M1 the product.
- Verification checks outputs and evidence; gating applies advancement policy. M1 mandatory integration preserves distinct responsibilities and protected durable verdict/release. All Tier-2 profiles consume M0-007 required upstream adaptation; no profile skips PRD 4.2.6 by using an unrelated generic prompt.
- System contribution: [M0-SYSTEM](../M0-SYSTEM/spec.md); this spec owns block/boundary acceptance and does not duplicate complete-system criteria.
- SRC-IDENTITY: PRD 3.1.3 local single-user wording conflicts with durable product account requirements. Affects Account binding and intake compatibility. Resolution: Apply PRD 1.7 and architecture D12: durable product identity, local execution configuration; preserve source bytes and prohibit implicit prior-run intake reuse.

This is the acceptance authority. Technical realization belongs in plan.md; work and current evidence are in tasks.md. No runtime acceptance is claimed by specification generation.
