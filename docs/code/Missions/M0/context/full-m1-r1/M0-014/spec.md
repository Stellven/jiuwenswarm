# Feature Specification: M0-014 — Restricted baseline-treatment benchmarking and empirical evidence

**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M0](../TASKS.md)
**Revision / date**: r1 / 2026-10-06
**Feature Branch**: ai4r_xiaoyang; directory identity is independent of branch
**Input**: PRD 2.5 (../source/PRD - AI4Research.txt:L486-L515); PRD 2.9 (../source/PRD - AI4Research.txt:L567-L582); PRD 3.7 (../source/PRD - AI4Research.txt:L1038-L1043); PRD 3.7.1 (../source/PRD - AI4Research.txt:L1044-L1054); PRD 3.7.2 (../source/PRD - AI4Research.txt:L1055-L1063); PRD 3.7.3 (../source/PRD - AI4Research.txt:L1064-L1072); PRD 3.7.4 (../source/PRD - AI4Research.txt:L1073-L1084); PRD 4.2.1 (../source/PRD - AI4Research.txt:L1314-L1354); PRD 4.2.6 (../source/PRD - AI4Research.txt:L1483-L1513); PRD 5.2.1 (../source/PRD - AI4Research.txt:L2310-L2327); architecture m1-design.md, workflow.md, contracts-and-native-reuse.md, guard-design.md, placement.md, failure-and-human.md; parent immutable source manifest
**Status**: Specified for preparation; runtime NOT_RUN

## User Scenarios & Testing

### User Story 1 — Complete the bounded declared outcome (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Accepted ZIP/requirements, traversal archive, unavailable declared dependency and missing restricted runner boundary., when the AC-001 operation is exercised, then Trusted provisioner records exact effective dependencies/environment and supplies restricted runtime.
2. Given Small known baseline/treatment pair, treatment-only runner, swapped order and changed dataset/config/seed., when the AC-002 operation is exercised, then Measured delta is attributable to the specified intervention under comparable conditions.
3. Given Known logged metrics, non-null missing metric, fabricated LLM metric and failed process partial output., when the AC-003 operation is exercised, then Every required measured value can be reconstructed from captured execution evidence.
4. Given Complete payload, missing arm/log, stale protocol, invalid schema and scientific PASS inserted by benchmark producer., when the AC-004 operation is exercised, then Scientific Evaluation receives exact accepted benchmark evidence after infrastructure checking.
5. Given Timeout, crash, denied filesystem/network access, dependency conflict and instruction to improve result by rerun., when the AC-005 operation is exercised, then Bounded correct run produces collection-only empirical evidence.
6. Given Labelled real matched evidence, synthetic values, absent baseline, protocol drift, impossible measurement and injected result claim., when the AC-006 operation is exercised, then Verifier returns evidence-grounded protocol/admissibility findings, not a second experiment or scientific verdict.

### User Story 2 — Reject invalid or inadmissible work without advancement (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Accepted ZIP/requirements, traversal archive, unavailable declared dependency and missing restricted runner boundary., when the AC-001 operation is exercised, then Unsafe archive, dependency-set mutation or unverified isolation prevents execution; environment unavailable is blocked with evidence. Missing, swapped, unadmitted or stale benchmark_capsule.md identity prevents dispatch/release.
2. Given Small known baseline/treatment pair, treatment-only runner, swapped order and changed dataset/config/seed., when the AC-002 operation is exercised, then Missing baseline, silent source change or mismatched conditions cannot yield admitted benchmark evidence. An inserted optimization/protocol-changing action between baseline and treatment is refused.
3. Given Known logged metrics, non-null missing metric, fabricated LLM metric and failed process partial output., when the AC-003 operation is exercised, then Missing/corrupt/null mandatory measurement, hallucinated result or raw-log-only-in-agent-memory is inadmissible.
4. Given Complete payload, missing arm/log, stale protocol, invalid schema and scientific PASS inserted by benchmark producer., when the AC-004 operation is exercised, then Incomplete/stale/swapped artifact, post-result threshold shift or producer classification cannot pass this boundary.
5. Given Timeout, crash, denied filesystem/network access, dependency conflict and instruction to improve result by rerun., when the AC-005 operation is exercised, then Artifact violation is FAIL; unavailable mandatory environment is ENVIRONMENT_BLOCKED under M0-007; no successor starts.
6. Given Labelled real matched evidence, synthetic values, absent baseline, protocol drift, impossible measurement and injected result claim., when the AC-006 operation is exercised, then Missing mandatory observation, fabricated metric or unavailable required disclosure cannot be excused by semantic plausibility.

### User Story 3 — Recover inspectability without silent replay or overwritten evidence (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Accepted ZIP/requirements, traversal archive, unavailable declared dependency and missing restricted runner boundary., when the AC-001 operation is exercised, then Explicit environment repair creates fresh work; no automatic solver, package upgrade or hidden retry.
2. Given Small known baseline/treatment pair, treatment-only runner, swapped order and changed dataset/config/seed., when the AC-002 operation is exercised, then Failure halts without repeat/rerun; preserved partial baseline or treatment outcome is not rewritten as complete comparison.
3. Given Known logged metrics, non-null missing metric, fabricated LLM metric and failed process partial output., when the AC-003 operation is exercised, then Retain raw failure/partial observations and capture limitations; no invented replacement measurements.
4. Given Complete payload, missing arm/log, stale protocol, invalid schema and scientific PASS inserted by benchmark producer., when the AC-004 operation is exercised, then Corrected payload is fresh evidence with rechecks; observed experiment is not silently rerun or reinterpreted.
5. Given Timeout, crash, denied filesystem/network access, dependency conflict and instruction to improve result by rerun., when the AC-005 operation is exercised, then Interactive triage or stable headless non-success preserves evidence and requests only authorized fresh correction.
6. Given Labelled real matched evidence, synthetic values, absent baseline, protocol drift, impossible measurement and injected result claim., when the AC-006 operation is exercised, then Protocol/runner/profile changes invalidate affected acceptance/calibration; independent paired fixtures remain separate from RSI hidden data.

### Edge Cases

Each AC includes its normal, failure and recovery scenario above. Shared cases include missing/invalid inputs, foreign or stale artifact/contract/implementation identity, unavailable required service, budget exhaustion, permission/disclosure escape, malformed assessment, cancelled or uncertain delivery, persistence failure, duplicate request, restart and incompatible revisions as applicable. Omissions require a source-based explanation in the implementing plan; an all-skipped suite is not acceptance.

## Requirements

### Functional Requirements

- **FR-001**: Provision only accepted artifacts and frozen dependencies in the restricted workspace. Source: PRD 2.9, PRD 3.7, PRD 3.7.1, PRD 5.2.1.
- **FR-002**: Execute actual baseline first then actual treatment on matched conditions. Source: PRD 3.7.2, PRD 2.5.
- **FR-003**: Capture raw observed empirical data independently of agent claims. Source: PRD 3.7.3.
- **FR-004**: Publish a readable typed benchmark handoff without scientific judgment. Source: PRD 3.7.4.
- **FR-005**: Preserve fail-fast runtime and empirical role separation. Source: PRD 3.7.1, PRD 3.7.2, PRD 3.7.3, PRD 3.7.4.
- **FR-006**: Provide protocol-conformance and empirical-origin calibration for independent verification. Source: PRD 4.2.1, PRD 4.2.6, PRD 3.7.4.

### Key Entities

AcceptedPOCAndProtocol, Benchmark_Payload.json, typed artifact reference, immutable input/implementation/profile pins, run/node/attempt/invocation identity and observable result. Exact semantics are owned by [TASK §4](TASK.md#m0-if-014-at-r1).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD 2.9, PRD 3.7, PRD 3.7.1, PRD 5.2.1; FR-001; US1/US2/US3 | Safely unpack exact accepted POC bundle to scoped workspace, create unprivileged dedicated environment and install only declared frozen requirements; mandatory runner confinement/readiness is verified before any generated code execution. The contract binds the exact seeded/admitted primary benchmark_capsule.md declaration, prompt and implementation closure under the canonical M0-003 primary capability registry; supporting capabilities are separately admitted and explicitly bound. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-002 | PRD 3.7.2, PRD 2.5; FR-002; US1/US2/US3 | Real unmodified supplied baseline executes before treatment using same declared hardware, benchmark configuration, validation data and seed policy; both execution identities/outcomes are captured, with unsupported deterministic seed control disclosed. Treatment follows baseline immediately in the declared contiguous harness sequence, with no intervening optimization or protocol-changing work. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-003 | PRD 3.7.3; FR-003; US1/US2/US3 | System Run Bundle contains actual stdout/stderr, execution traces, benchmark telemetry and declared dependent-variable measurements; empirical_results.json entries map to raw observations with units/identities; working memory retains compact references only. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-004 | PRD 3.7.4; FR-004; US1/US2/US3 | Benchmark_Payload.json binds empirical results and raw log references to current run/node/protocol/bundle/effective environment; it includes both arms and required metric/provenance/comparison metadata but emits no scientific verdict. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-005 | PRD 3.7.1, PRD 3.7.2, PRD 3.7.3, PRD 3.7.4; FR-005; US1/US2/US3 | Observed provisioning/execution has finite configured time/invocation limits, denied unauthorized host/network/system effects and no dynamic dependency mutation, autonomous retries or interpretation; raw failures remain attributable. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-006 | PRD 4.2.1, PRD 4.2.6, PRD 3.7.4; FR-006; US1/US2/US3 | Pinned result-evaluator/citation-reviewer mappings inspect completeness/provenance/matched arms/registered measurements and sources; hypothesis support classification is explicitly delegated to M0-015, not benchmark verifier; mandatory deterministic checks precede separate read-only assessment and protected release. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |

Mandatory behavior/failure constraints use exact source requirements; finite independent fixture cases must all meet their stated assertions. Source examples do not become arbitrary thresholds. Scientific thresholds are supplied/frozen for the run, not coding-agent inventions. Missing numeric policies are PENDING_SOURCE only for affected checks.

## Scope and Assumptions

- Included: Provision accepted POC assets/dependencies under verified restricted execution, run unmodified baseline then treatment under the immutable protocol, capture raw evidence and release typed Benchmark_Payload.json for scientific interpretation.
- Excluded: No dynamic dependency solving/addition/removal/upgrade, treatment-only measurements, threshold/data/measurement edits, scientific classification, extra benchmark iterations, fabricated empirical values or cloud execution.
- Consumed agreements: [M0-IF-013@r1](../M0-013/TASK.md#m0-if-013-at-r1); [M0-IF-012@r1](../M0-012/TASK.md#m0-if-012-at-r1); [M0-IF-008@r1](../M0-008/TASK.md#m0-if-008-at-r1); [M0-IF-002@r1](../M0-002/TASK.md#m0-if-002-at-r1); [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1); [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1).
- Permitted models: Phase 1 uses the PRD static subscription-authenticated Codex route; do not invent model IDs or providers. Phase 3 uses only explicitly approved pinned profiles/endpoints; before approval, mocks/analysis are labelled. Relevant provider model identifier/version is captured from actual runtime, never assumed.
- Architecture D1–D15 applies by responsibility; D5/D6 are explicit adopted amendments, not silent unchanged compliance. M0 is the coding-program folder, M1 the product.
- Verification checks outputs and evidence; gating applies advancement policy. M1 mandatory integration preserves distinct responsibilities and protected durable verdict/release. All Tier-2 profiles consume M0-007 required upstream adaptation; no profile skips PRD 4.2.6 by using an unrelated generic prompt.
- System contribution: [M0-SYSTEM](../M0-SYSTEM/spec.md); this spec owns block/boundary acceptance and does not duplicate complete-system criteria.
- Q-BENCHMARK-ENV: Mandatory generated-code confinement is not established by a venv or Docker image alone. Affects Empirical execution acceptance. Resolution: M0-004 owns mechanism and adversarial proof. Benchmarking consumes its verified restricted runner contract; if the host cannot enforce mandatory bounds, mark blocked and retain prepared harness/schema work.

This is the acceptance authority. Technical realization belongs in plan.md; work and current evidence are in tasks.md. No runtime acceptance is claimed by specification generation.
