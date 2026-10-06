# Feature Specification: M0-008 — Qualified intake and attributable local resource binding

**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M0](../TASKS.md)
**Revision / date**: r1 / 2026-10-06
**Feature Branch**: ai4r_xiaoyang; directory identity is independent of branch
**Input**: PRD 2.3 (../source/PRD - AI4Research.txt:L442-L466); PRD 2.4 (../source/PRD - AI4Research.txt:L467-L485); PRD 3.1 (../source/PRD - AI4Research.txt:L671-L674); PRD 3.1.1 (../source/PRD - AI4Research.txt:L675-L686); PRD 3.1.2 (../source/PRD - AI4Research.txt:L687-L709); PRD 3.1.3 (../source/PRD - AI4Research.txt:L710-L720); PRD 3.1.4 (../source/PRD - AI4Research.txt:L721-L731); PRD 3.1.5 (../source/PRD - AI4Research.txt:L732-L745); PRD 4.2.1 (../source/PRD - AI4Research.txt:L1314-L1354); PRD 4.2.6 (../source/PRD - AI4Research.txt:L1483-L1513); architecture m1-design.md, workflow.md, contracts-and-native-reuse.md, guard-design.md, placement.md, failure-and-human.md; parent immutable source manifest
**Status**: Specified for preparation; runtime NOT_RUN

## User Scenarios & Testing

### User Story 1 — Complete the bounded declared outcome (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Equivalent CLI/Web requests, whitespace-only prompt and external-channel event., when the AC-001 operation is exercised, then Original request is attributable to the submitting local authenticated session.
2. Given Readable text/Markdown/PDF, code tree and validation directory with a canary unchanged baseline file., when the AC-002 operation is exercised, then Qualified document buffer and separate baseline/data references reach authorized consumers.
3. Given Two user/workspace/run identities and repeated filename with different content., when the AC-003 operation is exercised, then Correct identity follows each resource into accepted Intent and later declared consumers.
4. Given Files below/at/above the frozen limit, malformed text/PDF and changing resource identity., when the AC-004 operation is exercised, then Accepted origins and extracted text remain traceable; required mutable resources are snapshotted or identity-validated before consumption.
5. Given Valid package, empty prompt, nonexistent/unreadable required directory and extraction fault., when the AC-005 operation is exercised, then Qualified intake is captured and handed to fixed Intent preparation.
6. Given Faithful extraction, omitted document section, invented source text and instruction injection embedded in a document., when the AC-006 operation is exercised, then Independent read-only verification checks the exact payload; only durable protected gate acceptance exposes successor references.

### User Story 2 — Reject invalid or inadmissible work without advancement (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Equivalent CLI/Web requests, whitespace-only prompt and external-channel event., when the AC-001 operation is exercised, then Empty request is rejected before compiler dispatch; external chat/voice input cannot enter the M1 path.
2. Given Readable text/Markdown/PDF, code tree and validation directory with a canary unchanged baseline file., when the AC-002 operation is exercised, then Unsupported Office file, traversal/symlink escape, unauthorized resource or undeclared download is rejected; no automatic clone or dataset fetch occurs.
3. Given Two user/workspace/run identities and repeated filename with different content., when the AC-003 operation is exercised, then Wrong-user, stale-run and detached workspace references fail binding; unrelated prior account context is not inferred.
4. Given Files below/at/above the frozen limit, malformed text/PDF and changing resource identity., when the AC-004 operation is exercised, then Oversize/unreadable/malformed required material produces explicit rejection rather than silent truncation or fabricated content.
5. Given Valid package, empty prompt, nonexistent/unreadable required directory and extraction fault., when the AC-005 operation is exercised, then Any required missing/unreadable input prevents downstream compiler dispatch and records actionable input correction.
6. Given Faithful extraction, omitted document section, invented source text and instruction injection embedded in a document., when the AC-006 operation is exercised, then Producer success, missing required extraction evidence, unsupported source or injected instructions cannot waive checks or unlock Intent.

### User Story 3 — Recover inspectability without silent replay or overwritten evidence (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Equivalent CLI/Web requests, whitespace-only prompt and external-channel event., when the AC-001 operation is exercised, then A corrected submission creates new attributable input without overwriting the rejected request.
2. Given Readable text/Markdown/PDF, code tree and validation directory with a canary unchanged baseline file., when the AC-002 operation is exercised, then Missing/unsupported resources are corrected through a fresh supplied-input submission; imported evidence is retained.
3. Given Two user/workspace/run identities and repeated filename with different content., when the AC-003 operation is exercised, then A new session may retain durable product profile but establishes new execution binding and preserves old run attribution.
4. Given Files below/at/above the frozen limit, malformed text/PDF and changing resource identity., when the AC-004 operation is exercised, then Replacement material requires new input identity; metadata and prior rejection remain inspectable.
5. Given Valid package, empty prompt, nonexistent/unreadable required directory and extraction fault., when the AC-005 operation is exercised, then Interactive surface shows rejection; headless submission returns non-success without waiting for a clarification dialogue.
6. Given Faithful extraction, omitted document section, invented source text and instruction injection embedded in a document., when the AC-006 operation is exercised, then A changed parser/source/profile invalidates affected calibration/evidence and requires fresh checking; no autonomous repair or prior PASS reuse.

### Edge Cases

Each AC includes its normal, failure and recovery scenario above. Shared cases include missing/invalid inputs, foreign or stale artifact/contract/implementation identity, unavailable required service, budget exhaustion, permission/disclosure escape, malformed assessment, cancelled or uncertain delivery, persistence failure, duplicate request, restart and incompatible revisions as applicable. Omissions require a source-based explanation in the implementing plan; an all-skipped suite is not acceptance.

## Requirements

### Functional Requirements

- **FR-001**: Preserve raw user intent at both local entry surfaces. Source: PRD 3.1.1.
- **FR-002**: Import supported documents without conflating execution assets with reasoning text. Source: PRD 3.1.2, PRD 2.4.
- **FR-003**: Bind intake to the stable product user and active local run without importing unrelated history. Source: PRD 3.1.3, PRD 2.3.
- **FR-004**: Enforce configured intake bounds and register observable origins. Source: PRD 3.1.4.
- **FR-005**: Deterministically qualify minimum intake before semantic work. Source: PRD 3.1.5.
- **FR-006**: Provide complete intake obligations to mandatory verification without giving intake release authority. Source: PRD 4.2.1, PRD 4.2.6, PRD 3.1.5.

### Key Entities

LocalResearchSubmission, QualifiedIntake, typed artifact reference, immutable input/implementation/profile pins, run/node/attempt/invocation identity and observable result. Exact semantics are owned by [TASK §4](TASK.md#m0-if-008-at-r1).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD 3.1.1; FR-001; US1/US2/US3 | CLI topic and native Web prompt produce the same qualified request semantics and retain the exact original text; capture does not choose a hypothesis or mislabel raw text as an accepted Brief. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-002 | PRD 3.1.2, PRD 2.4; FR-002; US1/US2/US3 | Only permitted local .txt/.md/.pdf documents are text-extracted; supplied code and validation data retain separate resource references with path/type/run identity and remain unmodified. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-003 | PRD 3.1.3, PRD 2.3; FR-003; US1/US2/US3 | Every input/resource is linked to authorized product user, local session, workspace and run; local profile comes from frozen configuration; a different session/run cannot substitute its assets. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-004 | PRD 3.1.4; FR-004; US1/US2/US3 | Configured finite file-size bounds reject over-limit files before extraction; origin path, size and ingest timestamp are recorded; exact boundary values are configuration-owned, not inferred from illustrative 50 MB text. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-005 | PRD 3.1.5; FR-005; US1/US2/US3 | Nonempty prompt and every required directory/readability assertion must pass; a single qualified in-memory payload contains original prompt plus extracted text and resource references; no LLM is spent on deterministic rejection. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-006 | PRD 4.2.1, PRD 4.2.6, PRD 3.1.5; FR-006; US1/US2/US3 | Intake candidate and original-input evidence use M0-007 protected deterministic/semantic assignments; node-specific result-evaluator/citation-reviewer mappings are pinned, document inapplicable scientific/citation portions and validate fidelity/provenance/injection challenges before accepted Intent can consume intake. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |

Mandatory behavior/failure constraints use exact source requirements; finite independent fixture cases must all meet their stated assertions. Source examples do not become arbitrary thresholds. Scientific thresholds are supplied/frozen for the run, not coding-agent inventions. Missing numeric policies are PENDING_SOURCE only for affected checks.

## Scope and Assumptions

- Included: Capture the original scientific request through supported local CLI/Web surfaces, import permitted documents, bind supplied code/data separately and produce a verified qualified intake for fixed Intent preparation.
- Excluded: No external channels, voice, ingestion web crawling, repository cloning, dataset download, Office extraction, vectorization, semantic deduplication or intake document signing. Account persistence is not an ingestion-owned feature.
- Consumed agreements: [M0-IF-002@r1](../M0-002/TASK.md#m0-if-002-at-r1); [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1).
- Permitted models: Phase 1 uses the PRD static subscription-authenticated Codex route; do not invent model IDs or providers. Phase 3 uses only explicitly approved pinned profiles/endpoints; before approval, mocks/analysis are labelled. Relevant provider model identifier/version is captured from actual runtime, never assumed.
- Architecture D1–D15 applies by responsibility; D5/D6 are explicit adopted amendments, not silent unchanged compliance. M0 is the coding-program folder, M1 the product.
- Verification checks outputs and evidence; gating applies advancement policy. M1 mandatory integration preserves distinct responsibilities and protected durable verdict/release. All Tier-2 profiles consume M0-007 required upstream adaptation; no profile skips PRD 4.2.6 by using an unrelated generic prompt.
- System contribution: [M0-SYSTEM](../M0-SYSTEM/spec.md); this spec owns block/boundary acceptance and does not duplicate complete-system criteria.
- Q-INTAKE-LIMIT: The PRD example is not a supplied numeric maximum file size. Affects Oversize acceptance boundary only. Resolution: Select and freeze a finite supported limit in M0-002 configuration before threshold testing; do not copy 50 MB as an authoritative requirement.
- SRC-INTAKE-PERSISTENCE: PRD 3.1.3 excludes cross-session user state while 2.3/5.4 require durable product identity. Affects Intake identity and context carryover. Resolution: Use m1-design.md/placement.md: preserve durable account/profile separately, prohibit implicit prior research/session context carryover, and bind each local run explicitly.

This is the acceptance authority. Technical realization belongs in plan.md; work and current evidence are in tasks.md. No runtime acceptance is claimed by specification generation.
