# Feature Specification: M0-005 — Durable run state, evidence and derived observability

**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M0](../TASKS.md)
**Revision / date**: r1 / 2026-10-06
**Feature Branch**: ai4r_xiaoyang; directory identity is independent of branch
**Input**: PRD 2.10 (../source/PRD - AI4Research.txt:L583-L593); PRD 4.5 (../source/PRD - AI4Research.txt:L1998-L2001); PRD 4.5.1 (../source/PRD - AI4Research.txt:L2002-L2008); PRD 4.5.2 (../source/PRD - AI4Research.txt:L2009-L2018); PRD 4.5.3 (../source/PRD - AI4Research.txt:L2019-L2026); PRD 4.5.4 (../source/PRD - AI4Research.txt:L2027-L2034); PRD 4.5.5 (../source/PRD - AI4Research.txt:L2035-L2047); PRD 5.1 (../source/PRD - AI4Research.txt:L2266-L2269); PRD 5.1.1 (../source/PRD - AI4Research.txt:L2270-L2277); PRD 5.1.2 (../source/PRD - AI4Research.txt:L2278-L2285); PRD 5.1.3 (../source/PRD - AI4Research.txt:L2286-L2294); PRD 5.1.4 (../source/PRD - AI4Research.txt:L2295-L2305); architecture placement.md, m1-design.md, automation.md, guard-design.md, principles.md; parent immutable source manifest
**Status**: Specified for preparation; runtime NOT_RUN

## User Scenarios & Testing

### User Story 1 — Complete the bounded declared outcome (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Concurrent projections, restart, corrupted artifact and partial file/database write., when the AC-001 operation is exercised, then Reload exact records and files against stored identities.
2. Given Failpoints before file persist, during database transaction and before readiness projection., when the AC-002 operation is exercised, then Successor observes the exact committed accepted subject only.
3. Given Requested profile differs from effective route; seed unsupported; failed and successful attempts., when the AC-003 operation is exercised, then Hash manifest and correlate every member call/assessment/decision.
4. Given Accepted summary plus oversized logs and unrelated prior run facts., when the AC-004 operation is exercised, then Resolve compact accepted context with source references.
5. Given Known tool mismatch, sparse observation, failed verifier and available/unavailable usage., when the AC-005 operation is exercised, then Rebuild the same attributable derived views from raw records.
6. Given Approved failed/successful exports and protected-data canaries., when the AC-006 operation is exercised, then RSI receives only explicitly approved visible data subset.

### User Story 2 — Reject invalid or inadmissible work without advancement (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Concurrent projections, restart, corrupted artifact and partial file/database write., when the AC-001 operation is exercised, then Reject missing/corrupt release artifacts and foreign run identity.
2. Given Failpoints before file persist, during database transaction and before readiness projection., when the AC-002 operation is exercised, then Disk full/locked DB/failed commit yields non-advancing outcome, never optional diagnostic treatment.
3. Given Requested profile differs from effective route; seed unsupported; failed and successful attempts., when the AC-003 operation is exercised, then Reject fabricated observed usage or missing required call evidence.
4. Given Accepted summary plus oversized logs and unrelated prior run facts., when the AC-004 operation is exercised, then Deny implicit unrelated research reuse and raw telemetry persistence into agent memory.
5. Given Known tool mismatch, sparse observation, failed verifier and available/unavailable usage., when the AC-005 operation is exercised, then Do not claim unseen effect absence, continuous host GPU utilization tracking or unsupported exact costs; static host/GPU identity remains required.
6. Given Approved failed/successful exports and protected-data canaries., when the AC-006 operation is exercised, then Deny hidden data, secret values, escaping export path and writeback into active workflow.

### User Story 3 — Recover inspectability without silent replay or overwritten evidence (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Concurrent projections, restart, corrupted artifact and partial file/database write., when the AC-001 operation is exercised, then Interrupted work is paused for inspection without automatic replay; committed accepted results remain retrievable.
2. Given Failpoints before file persist, during database transaction and before readiness projection., when the AC-002 operation is exercised, then Recover committed state; incomplete writes remain unaccepted and inspectable.
3. Given Requested profile differs from effective route; seed unsupported; failed and successful attempts., when the AC-003 operation is exercised, then Preserve failed attempts and historical manifests through cleanup/restart.
4. Given Accepted summary plus oversized logs and unrelated prior run facts., when the AC-004 operation is exercised, then Missing memory projection can be rebuilt from accepted state without becoming evidence authority.
5. Given Known tool mismatch, sparse observation, failed verifier and available/unavailable usage., when the AC-005 operation is exercised, then Rebuild broken required projections and keep their AC non-passing until proven; only explicitly optional diagnostics may remain unavailable without changing execution.
6. Given Approved failed/successful exports and protected-data canaries., when the AC-006 operation is exercised, then Failed export preserves source evidence and reports partial output as unusable until validation.

### Edge Cases

Each AC includes its normal, failure and recovery scenario above. Shared cases include missing/invalid inputs, foreign or stale artifact/contract/implementation identity, unavailable required service, budget exhaustion, permission/disclosure escape, malformed assessment, cancelled or uncertain delivery, persistence failure, duplicate request, restart and incompatible revisions as applicable. Omissions require a source-based explanation in the implementing plan; an all-skipped suite is not acceptance.

## Requirements

### Functional Requirements

- **FR-001**: Persist authoritative run/node/attempt/invocation lifecycle and immutable subject records. Source: PRD 4.5.2, PRD 2.10.
- **FR-002**: Commit release-essential artifacts and gate decision atomically before readiness. Source: PRD 4.5.2.
- **FR-003**: Capture real run bundles and append-only capsule records with effective manifest. Source: PRD 4.5.2.
- **FR-004**: Use native agent memory for compact accepted context only. Source: PRD 4.5.1, PRD 2.10.
- **FR-005**: Derive conformance, trace search/status and static scorecards from authoritative observations. Source: PRD 4.5.3, PRD 5.1.1, PRD 5.1.2, PRD 5.1.3, PRD 5.1.4.
- **FR-006**: Produce frozen permitted sample-run exports and enforce exclusion boundaries. Source: PRD 4.5.4, PRD 4.5.5.

### Key Entities

EvidenceCommit, StoredEvidenceAndRelease, typed artifact reference, immutable input/implementation/profile pins, run/node/attempt/invocation identity and observable result. Exact semantics are owned by [TASK §4](TASK.md#m0-if-005-at-r1).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD 4.5.2, PRD 2.10; FR-001; US1/US2/US3 | SQLite state plus referenced content-hashed files preserve original inputs, graph/contracts, implementation/configuration versions, outcomes and accepted identities independently of UI/cache/memory. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-002 | PRD 4.5.2; FR-002; US1/US2/US3 | No successor-visible accepted reference exists until required evidence/artifacts and authoritative decision durably commit; duplicate commit identity is idempotent but changed subject cannot reuse it. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-003 | PRD 4.5.2; FR-003; US1/US2/US3 | Prompt/input/output, raw assessment, gate decision and available trace evidence are retained; manifest records what executed including requested/effective seed and unavailable telemetry, library/configuration/model/profile pins. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-004 | PRD 4.5.1, PRD 2.10; FR-004; US1/US2/US3 | Accepted facts/decisions/summaries are scoped to the current authorized task; large raw logs/benchmark outputs live in evidence storage and are referenced instead of copied into Task/Coding memory. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-005 | PRD 4.5.3, PRD 5.1.1, PRD 5.1.2, PRD 5.1.3, PRD 5.1.4; FR-005; US1/US2/US3 | Run status, gate reasons and declared-versus-observed violations are inspectable; JSON/Markdown scorecards retain sample counts, failure reasons, durations and unavailable cost/token fields; projections cannot alter decisions. Capture OS, CPU core count and GPU model once at run start; continuous utilization sampling is excluded. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-006 | PRD 4.5.4, PRD 4.5.5; FR-006; US1/US2/US3 | Exports include real records, labels and hashes with immutable manifest and audience authorization; no synthetic success, hidden-final/loop fixtures, live writeback, enterprise graph subsystem or autonomous trace deduplication. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |

Mandatory behavior/failure constraints use exact source requirements; finite independent fixture cases must all meet their stated assertions. Source examples do not become arbitrary thresholds. Scientific thresholds are supplied/frozen for the run, not coding-agent inventions. Missing numeric policies are PENDING_SOURCE only for affected checks.

## Scope and Assumptions

- Included: Provide one transactional run-state/release authority with immutable artifacts, protected raw evidence, run bundles, records, scorecards, context memory and scoped reproducible exports.
- Excluded: No distributed graph database, enterprise observability, raw-log agent memory, synthetic accepted runs, hidden-fixture export or silent best-effort release.
- Consumed agreements: [M0-IF-002@r1](../M0-002/TASK.md#m0-if-002-at-r1).
- Permitted models: Phase 1 uses the PRD static subscription-authenticated Codex route; do not invent model IDs or providers. Phase 3 uses only explicitly approved pinned profiles/endpoints; before approval, mocks/analysis are labelled. Relevant provider model identifier/version is captured from actual runtime, never assumed.
- Architecture D1–D15 applies by responsibility; D5/D6 are explicit adopted amendments, not silent unchanged compliance. M0 is the coding-program folder, M1 the product.
- Verification checks outputs and evidence; gating applies advancement policy. M1 mandatory integration preserves distinct responsibilities and protected durable verdict/release. All Tier-2 profiles consume M0-007 required upstream adaptation; no profile skips PRD 4.2.6 by using an unrelated generic prompt.
- System contribution: [M0-SYSTEM](../M0-SYSTEM/spec.md); this spec owns block/boundary acceptance and does not duplicate complete-system criteria.

This is the acceptance authority. Technical realization belongs in plan.md; work and current evidence are in tasks.md. No runtime acceptance is claimed by specification generation.
