# Feature Specification: M0-015 — Read-only scientific evidence evaluation and pre-registered classification

**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M0](../TASKS.md)
**Revision / date**: r1 / 2026-10-06
**Feature Branch**: ai4r_xiaoyang; directory identity is independent of branch
**Input**: PRD 2.5 (../source/PRD - AI4Research.txt:L486-L515); PRD 3.8 (../source/PRD - AI4Research.txt:L1085-L1090); PRD 3.8.1 (../source/PRD - AI4Research.txt:L1091-L1099); PRD 3.8.2 (../source/PRD - AI4Research.txt:L1100-L1107); PRD 3.8.3 (../source/PRD - AI4Research.txt:L1108-L1114); PRD 3.8.4 (../source/PRD - AI4Research.txt:L1115-L1121); PRD 3.8.5 (../source/PRD - AI4Research.txt:L1122-L1135); PRD 3.8.6 (../source/PRD - AI4Research.txt:L1136-L1145); PRD 4.2.1 (../source/PRD - AI4Research.txt:L1314-L1354); PRD 4.2.6 (../source/PRD - AI4Research.txt:L1483-L1513); PRD 4.2.8 (../source/PRD - AI4Research.txt:L1542-L1627); PRD 5.2.1 (../source/PRD - AI4Research.txt:L2310-L2327); architecture m1-design.md, workflow.md, contracts-and-native-reuse.md, guard-design.md, placement.md, failure-and-human.md; parent immutable source manifest
**Status**: Specified for preparation; runtime NOT_RUN

## User Scenarios & Testing

### User Story 1 — Complete the bounded declared outcome (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Matching three-artifact set, stale/swapped blueprint and injected request to query a favorable leaderboard., when the AC-001 operation is exercised, then Evaluation scope preserves original targets and exact registered protocol.
2. Given Known logged metrics, omitted dependent variable, fabricated value and wrong-log identity., when the AC-002 operation is exercised, then Evidence-completeness assessment cites exact admitted measurements and logs.
3. Given Plausible delta, negative memory, inconsistent units, impossible speedup and injected suggestion to rerun., when the AC-003 operation is exercised, then Reasoned validity concerns cite data and remain separate from measured values.
4. Given Below/at/above declared boundaries, multi-metric cases, zero denominator policy and after-result threshold edit., when the AC-004 operation is exercised, then Boundary comparisons reproduce from admitted empirical values and frozen rule identity.
5. Given Positive, falsified, middle/insufficient, predeclared conditional and undeclared post-hoc conditional cases., when the AC-005 operation is exercised, then Scientific verdict and residual risks reflect exact protocol application and remain unchanged at infrastructure gate.
6. Given Measured bottleneck, justified follow-up, unsupported recommendation and code-write/rerun canaries., when the AC-006 operation is exercised, then Recommendations are inspectable narrative outputs, not executed side effects.
7. Given Independent labelled correct negative result, wrong-threshold verdict, unsupported source, missing raw metric and injected positive claim., when the AC-007 operation is exercised, then Separate assessor findings expose process errors/uncertainty while exact admissible negative conclusion proceeds.

### User Story 2 — Reject invalid or inadmissible work without advancement (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Matching three-artifact set, stale/swapped blueprint and injected request to query a favorable leaderboard., when the AC-001 operation is exercised, then Missing required input, changed protocol, unrelated evidence or undeclared query cannot enter accepted interpretation. Missing, swapped, unadmitted or stale scientific_evaluator_capsule.md identity prevents dispatch/release.
2. Given Known logged metrics, omitted dependent variable, fabricated value and wrong-log identity., when the AC-002 operation is exercised, then LLM-generated replacement value, unsupported metric or broken provenance prevents valid scientific process acceptance.
3. Given Plausible delta, negative memory, inconsistent units, impossible speedup and injected suggestion to rerun., when the AC-003 operation is exercised, then Impossible/corrupt values surface as process/evidence anomalies; no perturbation/counterfactual run or silent correction occurs.
4. Given Below/at/above declared boundaries, multi-metric cases, zero denominator policy and after-result threshold edit., when the AC-004 operation is exercised, then Goalpost shift, favorable data substitution, rewritten measurement or invented margin fails process verification.
5. Given Positive, falsified, middle/insufficient, predeclared conditional and undeclared post-hoc conditional cases., when the AC-005 operation is exercised, then Unregistered classification rule, voting/debate or scientific FAIL treated as automatic infrastructure failure violates the boundary.
6. Given Measured bottleneck, justified follow-up, unsupported recommendation and code-write/rerun canaries., when the AC-006 operation is exercised, then Patch, upstream artifact rewrite or rebenchmark attempt is denied and recorded.
7. Given Independent labelled correct negative result, wrong-threshold verdict, unsupported source, missing raw metric and injected positive claim., when the AC-007 operation is exercised, then Producer claim, verifier alternative solution or semantic PASS cannot bypass missing mandatory empirical evidence or change the registered conclusion.

### User Story 3 — Recover inspectability without silent replay or overwritten evidence (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Matching three-artifact set, stale/swapped blueprint and injected request to query a favorable leaderboard., when the AC-001 operation is exercised, then Missing evidence yields non-advancing process outcome; newly supplied evidence requires fresh attributable work.
2. Given Known logged metrics, omitted dependent variable, fabricated value and wrong-log identity., when the AC-002 operation is exercised, then Retain incomplete/corrupt evidence and limitations; no new experiment or measurement fabrication.
3. Given Plausible delta, negative memory, inconsistent units, impossible speedup and injected suggestion to rerun., when the AC-003 operation is exercised, then Unresolved validity is explicitly non-advancing or scientifically inconclusive according to the fixed contract; no autonomous diagnosis loop.
4. Given Below/at/above declared boundaries, multi-metric cases, zero denominator policy and after-result threshold edit., when the AC-004 operation is exercised, then Invalid protocol is not repaired downstream; a changed experimental design requires a new run and prior evidence remains unchanged.
5. Given Positive, falsified, middle/insufficient, predeclared conditional and undeclared post-hoc conditional cases., when the AC-005 operation is exercised, then A rejected hypothesis is delivered faithfully; no retry or code patch attempts to force a positive outcome.
6. Given Measured bottleneck, justified follow-up, unsupported recommendation and code-write/rerun canaries., when the AC-006 operation is exercised, then Future investigation needs explicit fresh research work; current verdict and execution evidence remain immutable.
7. Given Independent labelled correct negative result, wrong-threshold verdict, unsupported source, missing raw metric and injected positive claim., when the AC-007 operation is exercised, then Changed evaluation/profile/model/protocol invalidates affected evidence/calibration; preserve assessor errors and shared-provider limitations.

### Edge Cases

Each AC includes its normal, failure and recovery scenario above. Shared cases include missing/invalid inputs, foreign or stale artifact/contract/implementation identity, unavailable required service, budget exhaustion, permission/disclosure escape, malformed assessment, cancelled or uncertain delivery, persistence failure, duplicate request, restart and incompatible revisions as applicable. Omissions require a source-based explanation in the implementing plan; an all-skipped suite is not acceptance.

## Requirements

### Functional Requirements

- **FR-001**: Assemble only exact admitted benchmark, protocol and user target context. Source: PRD 3.8, PRD 3.8.1, PRD 5.2.1.
- **FR-002**: Audit completeness and origin against real raw execution logs. Source: PRD 3.8.2.
- **FR-003**: Perform bounded plausibility review without secondary execution. Source: PRD 3.8.3.
- **FR-004**: Apply immutable success/falsification predicates deterministically. Source: PRD 3.8.4, PRD 2.5.
- **FR-005**: Emit only permitted scientific classifications and preserve negative results. Source: PRD 3.8.5, PRD 4.2.8.
- **FR-006**: Record limitations and follow-up recommendations under enforced read-only scope. Source: PRD 3.8.6.
- **FR-007**: Distinguish scientific authoring from independent process verification and protected release. Source: PRD 4.2.1, PRD 4.2.6, PRD 4.2.8, PRD 3.8.5.

### Key Entities

AcceptedBenchmarkEvidence, Evaluation_Verdict.json, typed artifact reference, immutable input/implementation/profile pins, run/node/attempt/invocation identity and observable result. Exact semantics are owned by [TASK §4](TASK.md#m0-if-015-at-r1).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD 3.8, PRD 3.8.1, PRD 5.2.1; FR-001; US1/US2/US3 | Evaluation binds accepted Benchmark_Payload, immutable Hypothesis_Blueprint and Research_Brief with raw evidence/source references and current artifact identities; no external leaderboard or live web augmentation. The contract binds the exact seeded/admitted primary scientific_evaluator_capsule.md declaration, prompt and implementation closure under the canonical M0-003 primary capability registry; supporting capabilities are separately admitted and explicitly bound. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-002 | PRD 3.8.2; FR-002; US1/US2/US3 | Every dependent variable required by Blueprint has non-null empirical entry with traceable raw stdout/stderr/measurement support; reported baseline/treatment values agree with admitted evidence. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-003 | PRD 3.8.3; FR-003; US1/US2/US3 | One single-turn qualitative sanity assessment checks whether measured changes are physically/computationally plausible under the admitted protocol, recording anomalies and reasons rather than altering evidence. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-004 | PRD 3.8.4, PRD 2.5; FR-004; US1/US2/US3 | Metric deltas are computed with the registered baseline, units, direction and measurement semantics and compared to exact frozen success/falsification rules; in-between values follow registered middle-region semantics. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-005 | PRD 3.8.5, PRD 4.2.8; FR-005; US1/US2/US3 | Evaluation_Verdict uses PASS only when predeclared success holds, FAIL for declared falsification, INCONCLUSIVE for insufficient/middle evidence, and CONDITIONALLY_ACCEPTABLE only for a rule frozen beforehand; valid scientific FAIL/inconclusive can receive infrastructure PASS and reach Delivery. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-006 | PRD 3.8.6; FR-006; US1/US2/US3 | Evaluation_Verdict includes bottlenecks, algorithmic limitations, residual operational risks and proposed future research with evidence references; evaluator has no authority to write code, change upstream assets or dispatch reruns. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-007 | PRD 4.2.1, PRD 4.2.6, PRD 4.2.8, PRD 3.8.5; FR-007; US1/US2/US3 | scientific_evaluator capability owns interpretation; M0-007 separately maps pinned result-evaluator/citation-reviewer to completeness/provenance/registered-rule application, checks node obligations and readonly effects, and gates release without inventing a replacement scientific verdict; inapplicable publication sections are marked/tested. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |

Mandatory behavior/failure constraints use exact source requirements; finite independent fixture cases must all meet their stated assertions. Source examples do not become arbitrary thresholds. Scientific thresholds are supplied/frozen for the run, not coding-agent inventions. Missing numeric policies are PENDING_SOURCE only for affected checks.

## Scope and Assumptions

- Included: Evaluate admitted benchmark observations against immutable Hypothesis Blueprint and original Research Brief, audit empirical provenance and completeness, apply predeclared classification, and record scientific verdict/risks/follow-ups without code changes or experiments.
- Excluded: No live leaderboards/web evidence, cryptographic or multi-node provenance extension, perturbation/counterfactual runs, post-hoc thresholds/conditional criteria, multi-agent voting, defect repair or pipeline rerun.
- Consumed agreements: [M0-IF-014@r1](../M0-014/TASK.md#m0-if-014-at-r1); [M0-IF-012@r1](../M0-012/TASK.md#m0-if-012-at-r1); [M0-IF-009@r1](../M0-009/TASK.md#m0-if-009-at-r1); [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1); [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1).
- Permitted models: Phase 1 uses the PRD static subscription-authenticated Codex route; do not invent model IDs or providers. Phase 3 uses only explicitly approved pinned profiles/endpoints; before approval, mocks/analysis are labelled. Relevant provider model identifier/version is captured from actual runtime, never assumed.
- Architecture D1–D15 applies by responsibility; D5/D6 are explicit adopted amendments, not silent unchanged compliance. M0 is the coding-program folder, M1 the product.
- Verification checks outputs and evidence; gating applies advancement policy. M1 mandatory integration preserves distinct responsibilities and protected durable verdict/release. All Tier-2 profiles consume M0-007 required upstream adaptation; no profile skips PRD 4.2.6 by using an unrelated generic prompt.
- System contribution: [M0-SYSTEM](../M0-SYSTEM/spec.md); this spec owns block/boundary acceptance and does not duplicate complete-system criteria.
- Q-SCIENCE-RULES: Exact metric aggregation and exceptional arithmetic semantics depend on the M0-012 protocol agreement. Affects Deterministic multi-metric classification. Resolution: Consume frozen owner-defined predicates/units/exception policies; do not invent success margins, conditional acceptance rules or numeric plausibility thresholds after observing results.

This is the acceptance authority. Technical realization belongs in plan.md; work and current evidence are in tasks.md. No runtime acceptance is claimed by specification generation.
