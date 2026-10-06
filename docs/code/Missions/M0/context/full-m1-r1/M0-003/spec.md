# Feature Specification: M0-003 — Capability declarations and admitted library

**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M0](../TASKS.md)
**Revision / date**: r1 / 2026-10-06
**Feature Branch**: ai4r_xiaoyang; directory identity is independent of branch
**Input**: PRD 4.1 (../source/PRD - AI4Research.txt:L1190-L1206); PRD 4.1.1 (../source/PRD - AI4Research.txt:L1207-L1224); PRD 4.1.2 (../source/PRD - AI4Research.txt:L1225-L1243); PRD 4.1.5 (../source/PRD - AI4Research.txt:L1284-L1304); PRD 5.2.1 (../source/PRD - AI4Research.txt:L2310-L2327); architecture capsule/declaration.md, capsule/authoring.md, capsules.md, sources/capsule.schema.json, sources/capsule-semantic-v2.10b.md, sources/policy-m1.json, principles.md; parent immutable source manifest
**Status**: Specified for preparation; runtime NOT_RUN

## User Scenarios & Testing

### User Story 1 — Complete the bounded declared outcome (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Leaf/composite/remote-shaped declarations and legacy schema/profile variants., when the AC-001 operation is exercised, then Round-trip supported declarations without losing field meaning; generated make_capsule.md derives from capsule.json.
2. Given Changed prompt/code/transitive dependency and missing carrier/body references., when the AC-002 operation is exercised, then Calculate reproducible identity and verify all required referenced bytes.
3. Given Valid candidate, failed self-test, incomplete evidence and handwritten versus RSI candidates., when the AC-003 operation is exercised, then Admit the exact eligible version with decision/evidence references.
4. Given Admitted inactive, active, suspended and historical versions., when the AC-004 operation is exercised, then Activate an admitted version and explicitly roll back while preserving history.
5. Given Parent/candidate changes inside ranking helper and outside frozen surfaces., when the AC-005 operation is exercised, then Register an inactive child with attributable model/prompt/trajectory provenance.
6. Given Nested composite with duplicate role, invalid wire, cycle and missing member check., when the AC-006 operation is exercised, then Resolve admitted closure into a read-only eligible catalogue.

### User Story 2 — Reject invalid or inadmissible work without advancement (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Leaf/composite/remote-shaped declarations and legacy schema/profile variants., when the AC-001 operation is exercised, then Reject ambiguous migration, incompatible governance fields and legacy inert-budget bypass.
2. Given Changed prompt/code/transitive dependency and missing carrier/body references., when the AC-002 operation is exercised, then Reject hash mismatch, missing dependency or unsupported external pin.
3. Given Valid candidate, failed self-test, incomplete evidence and handwritten versus RSI candidates., when the AC-003 operation is exercised, then No mocked/skipped/missing required check can certify a live capability.
4. Given Admitted inactive, active, suspended and historical versions., when the AC-004 operation is exercised, then Reject self-activation, unknown standing action and deleted historical identity.
5. Given Parent/candidate changes inside ranking helper and outside frozen surfaces., when the AC-005 operation is exercised, then Reject permission widening, overwritten parent or mutable referee dependency.
6. Given Nested composite with duplicate role, invalid wire, cycle and missing member check., when the AC-006 operation is exercised, then Reject missing/recursive/ineligible members and author-granted generalist gate exemption.

### User Story 3 — Recover inspectability without silent replay or overwritten evidence (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Leaf/composite/remote-shaped declarations and legacy schema/profile variants., when the AC-001 operation is exercised, then Migration creates a new version/profile; original sources and admitted versions remain unchanged.
2. Given Changed prompt/code/transitive dependency and missing carrier/body references., when the AC-002 operation is exercised, then A changed closure creates a separately attributable candidate and fresh admission evidence.
3. Given Valid candidate, failed self-test, incomplete evidence and handwritten versus RSI candidates., when the AC-003 operation is exercised, then Failed candidates stay inspectable and inactive; repaired version undergoes fresh checks.
4. Given Admitted inactive, active, suspended and historical versions., when the AC-004 operation is exercised, then Frozen runs keep pins; current suspension halts affected work and preserves in-flight observations.
5. Given Parent/candidate changes inside ranking helper and outside frozen surfaces., when the AC-005 operation is exercised, then Refused mutation keeps forensic evidence; later activation remains a human action.
6. Given Nested composite with duplicate role, invalid wire, cycle and missing member check., when the AC-006 operation is exercised, then Future compatible schema readers require versioned migration and refreshed evidence, not silent reinterpretation.

### Edge Cases

Each AC includes its normal, failure and recovery scenario above. Shared cases include missing/invalid inputs, foreign or stale artifact/contract/implementation identity, unavailable required service, budget exhaustion, permission/disclosure escape, malformed assessment, cancelled or uncertain delivery, persistence failure, duplicate request, restart and incompatible revisions as applicable. Omissions require a source-based explanation in the implementing plan; an all-skipped suite is not acceptance.

## Requirements

### Functional Requirements

- **FR-001**: Reconcile machine 2.9, semantic 2.10b and the complete declaration field inventory in one versioned current profile. Source: PRD 4.1, PRD 4.1.1.
- **FR-002**: Pin and verify the complete implementation and dependency closure. Source: PRD 4.1.1, PRD 5.2.1.
- **FR-003**: Enforce strict admission and provisional standing for authored and RSI candidates. Source: PRD 4.1.2.
- **FR-004**: Separate admission from human activation, suspension, deprecation and rollback. Source: PRD 4.1.2.
- **FR-005**: Preserve server-enforced mutation and frozen governance boundaries. Source: PRD 4.1.1, PRD 4.1.5.
- **FR-006**: Preserve composite meaning without granting unsupported runtime mechanisms. Source: PRD 4.1.1, PRD 4.1.2.

### Key Entities

CapsuleCandidate, AdmittedCapsuleSnapshot, typed artifact reference, immutable input/implementation/profile pins, run/node/attempt/invocation identity and observable result. Exact semantics are owned by [TASK §4](TASK.md#m0-if-003-at-r1).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD 4.1, PRD 4.1.1; FR-001; US1/US2/US3 | Every inventory field has supported serialization, preserved compatibility or explicit future status; required product limits/checks/RSI lineage are active regardless of historical policy inert flags; unknown authority-bearing fields are rejected. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-002 | PRD 4.1.1, PRD 5.2.1; FR-002; US1/US2/US3 | Code, prompt, checks, resources and external dependency identities have immutable hashes/pins; changed content cannot run under an old identity; credentials are references, never packaged values. The canonical primary capability registry below maps every PRD stage alias to its owning realization; initialization seeds exact version-locked capsule.json, prompt/Markdown alias, implementation and IF hashes, and the binder rejects missing, unadmitted or swapped stage pins. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-003 | PRD 4.1.2; FR-003; US1/US2/US3 | Declaration validity, integrity, required self-tests, provenance and compatibility are observed before eligibility; provisional is the only M1 trust level and not a truth guarantee. Admission uses deterministic checks followed by independently scoped verifier review of required evidence and protected admission decision; authored self-tests alone cannot establish eligibility. Guard-purpose assessments terminate at their mechanically validated boundary without recursive semantic review. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-004 | PRD 4.1.2; FR-004; US1/US2/US3 | Only authenticated human standing actions change active selections; append-only history retains all versions; new runs resolve activated or explicitly pinned versions; suspension blocks start/release without substitution. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-005 | PRD 4.1.1, PRD 4.1.5; FR-005; US1/US2/US3 | Eligible mutation allowlist and protected dependency closure are separate from author metadata; child retains parent lineage and cannot alter ports/effects/checks/security/referee or promote itself. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-006 | PRD 4.1.1, PRD 4.1.2; FR-006; US1/US2/US3 | Pinned members, wiring, effects, lineage and check coverage remain traceable; detect recursive dependency cycles; unsupported composition blocks binding, and metadata never enables deferred fusion/install behavior. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |

Mandatory behavior/failure constraints use exact source requirements; finite independent fixture cases must all meet their stated assertions. Source examples do not become arbitrary thresholds. Scientific thresholds are supplied/frozen for the run, not coding-agent inventions. Missing numeric policies are PENDING_SOURCE only for affected checks.

## Scope and Assumptions

- Included: Define the current versioned capsule serialization/profile, implementation closure, admission, immutable lineage and human standing controls, preserving every architecture declaration field meaning.
- Excluded: No live capability installation, autonomous capability creation/promotion, remote importing, fusion, mid-run replacement, third-party certification or machine-schema-only claims of confinement.
- Consumed agreements: [M0-IF-002@r1](../M0-002/TASK.md#m0-if-002-at-r1).
- Permitted models: Phase 1 uses the PRD static subscription-authenticated Codex route; do not invent model IDs or providers. Phase 3 uses only explicitly approved pinned profiles/endpoints; before approval, mocks/analysis are labelled. Relevant provider model identifier/version is captured from actual runtime, never assumed.
- Architecture D1–D15 applies by responsibility; D5/D6 are explicit adopted amendments, not silent unchanged compliance. M0 is the coding-program folder, M1 the product.
- Verification checks outputs and evidence; gating applies advancement policy. M1 mandatory integration preserves distinct responsibilities and protected durable verdict/release. All Tier-2 profiles consume M0-007 required upstream adaptation; no profile skips PRD 4.2.6 by using an unrelated generic prompt.
- System contribution: [M0-SYSTEM](../M0-SYSTEM/spec.md); this spec owns block/boundary acceptance and does not duplicate complete-system criteria.
- SRC-SCHEMA: Machine schema and semantic inventory disagree on shapes/requiredness; old M1 policy defers product-required fields. Affects AC-001, capsule readers, runtime limits and RSI. Resolution: Create and document a current versioned profile retaining original sources; independently validate migration and activate product-required enforcement.

This is the acceptance authority. Technical realization belongs in plan.md; work and current evidence are in tasks.md. No runtime acceptance is claimed by specification generation.
