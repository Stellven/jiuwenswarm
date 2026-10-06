# Feature Specification: M0-007 — Protected guard profiles, Verifier and durable release

**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M0](../TASKS.md)
**Revision / date**: r1 / 2026-10-06
**Feature Branch**: ai4r_xiaoyang; directory identity is independent of branch
**Input**: PRD 2.8 (../source/PRD - AI4Research.txt:L551-L566); PRD 4.2 (../source/PRD - AI4Research.txt:L1305-L1313); PRD 4.2.1 (../source/PRD - AI4Research.txt:L1314-L1354); PRD 4.2.2 (../source/PRD - AI4Research.txt:L1355-L1383); PRD 4.2.3 (../source/PRD - AI4Research.txt:L1384-L1414); PRD 4.2.4 (../source/PRD - AI4Research.txt:L1415-L1447); PRD 4.2.5 (../source/PRD - AI4Research.txt:L1448-L1482); PRD 4.2.6 (../source/PRD - AI4Research.txt:L1483-L1513); PRD 4.2.7 (../source/PRD - AI4Research.txt:L1514-L1541); PRD 4.2.8 (../source/PRD - AI4Research.txt:L1542-L1627); PRD 4.2.9 (../source/PRD - AI4Research.txt:L1628-L1698); PRD 4.2.10 (../source/PRD - AI4Research.txt:L1699-L1722); PRD 4.3.4 (../source/PRD - AI4Research.txt:L1779-L1796); PRD 5.2.1 (../source/PRD - AI4Research.txt:L2310-L2327); architecture guard-design.md, capsules.md, failure-and-human.md, principles.md, capsule/declaration.md; parent immutable source manifest
**Status**: Specified for preparation; runtime NOT_RUN

## User Scenarios & Testing

### User Story 1 — Complete the bounded declared outcome (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Same CC with different input/objective/protocol/scope and absent profile., when the AC-001 operation is exercised, then Derive repeatable binding identity for identical complete context.
2. Given Valid payload and missing field/wrong type/stale/swapped/interface mismatch evidence., when the AC-002 operation is exercised, then Valid current subject reaches Tier 2 exactly once.
3. Given Passing/failing tests, timeout and missing baseline/treatment/protocol metrics., when the AC-003 operation is exercised, then Consume complete declared check results and pre-registered comparison metadata.
4. Given Allowed computation and prohibited imports/effects/secret canaries., when the AC-004 operation is exercised, then Approved scoped artifact preserves citations and required execution-boundary evidence.
5. Given Faithful/omitted/unsupported/citation-broken/ambiguous/injected artifacts with labelled fixtures., when the AC-005 operation is exercised, then Structured findings cite observed support and disclose uncertainty.
6. Given All five verdicts, missing evidence reference and post-review mutation., when the AC-006 operation is exercised, then Propagate non-blocking warnings and normalized vocabulary without losing original verdict.
7. Given Frozen protocol with positive, negative, inconclusive and corrupt evidence results., when the AC-007 operation is exercised, then Deliver a faithful negative result without rewritten thresholds.
8. Given Independent labelled ten-category challenge manifest and real Node A/Gate/Node B boundary., when the AC-008 operation is exercised, then Valid/known-limitation/negative-science cases advance exactly as declared.
9. Given Forbidden mutation attempts and pre-labelled verifier challenge categories., when the AC-009 operation is exercised, then Characterize separate invocation/context, not statistically independent error or universal truth.
10. Given Exact upstream source snapshots plus a fixed labelled adaptation corpus separate from RSI hidden fixtures and live requests., when the AC-010 operation is exercised, then Adopt applicable factuality/result and citation checks into the correct node profile with source mapping and evidence references.

### User Story 2 — Reject invalid or inadmissible work without advancement (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Same CC with different input/objective/protocol/scope and absent profile., when the AC-001 operation is exercised, then Reject unsupported obligation, producer-selected favorable rubric and missing mandatory check. Missing, swapped, unadmitted or stale verifier_capsule.md identity prevents dispatch/release.
2. Given Valid payload and missing field/wrong type/stale/swapped/interface mismatch evidence., when the AC-002 operation is exercised, then Every invalid variant blocks with no semantic spend or next work start.
3. Given Passing/failing tests, timeout and missing baseline/treatment/protocol metrics., when the AC-003 operation is exercised, then Mandatory test/budget failure blocks; unavailable tokens remain unavailable, not fabricated measured PASS.
4. Given Allowed computation and prohibited imports/effects/secret canaries., when the AC-004 operation is exercised, then No correct-looking output compensates for prohibited effect or missing confinement evidence.
5. Given Faithful/omitted/unsupported/citation-broken/ambiguous/injected artifacts with labelled fixtures., when the AC-005 operation is exercised, then Malformed/unsupported/out-of-scope/uncertain assessment, unavailable permitted model disclosure or timeout cannot advance.
6. Given All five verdicts, missing evidence reference and post-review mutation., when the AC-006 operation is exercised, then Reject forged CC boolean, changed subject, premature downstream start or persistence failure.
7. Given Frozen protocol with positive, negative, inconclusive and corrupt evidence results., when the AC-007 operation is exercised, then Reject outcome-driven acceptance change and infrastructure/science vocabulary conflation.
8. Given Independent labelled ten-category challenge manifest and real Node A/Gate/Node B boundary., when the AC-008 operation is exercised, then All blocking cases keep B locked with expected evidence and no skipped mandatory case.
9. Given Forbidden mutation attempts and pre-labelled verifier challenge categories., when the AC-009 operation is exercised, then Reject self-approved profile change and quality-only permissive gate rule when a mandatory obligation fails.
10. Given Exact upstream source snapshots plus a fixed labelled adaptation corpus separate from RSI hidden fixtures and live requests., when the AC-010 operation is exercised, then Reject unpinned/unavailable source, unreviewed partial adaptation, producer-led verdict, unsupported citation, acceptance-criterion rewrite or Stage 3.8 scientific-authority substitution.

### User Story 3 — Recover inspectability without silent replay or overwritten evidence (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Same CC with different input/objective/protocol/scope and absent profile., when the AC-001 operation is exercised, then Profile changes apply to new assignments and invalidate affected evidence, never live acceptance.
2. Given Valid payload and missing field/wrong type/stale/swapped/interface mismatch evidence., when the AC-002 operation is exercised, then Corrected subject uses fresh checks; earlier failure remains in evidence.
3. Given Passing/failing tests, timeout and missing baseline/treatment/protocol metrics., when the AC-003 operation is exercised, then New implementation candidate reruns affected checks without overwriting failed evidence.
4. Given Allowed computation and prohibited imports/effects/secret canaries., when the AC-004 operation is exercised, then Violation halts and preserves evidence; inspection cannot silently sanitize a pass.
5. Given Faithful/omitted/unsupported/citation-broken/ambiguous/injected artifacts with labelled fixtures., when the AC-005 operation is exercised, then Separate calibrated development set remains outside RSI; correlated provider limitations are recorded.
6. Given All five verdicts, missing evidence reference and post-review mutation., when the AC-006 operation is exercised, then Durable re-read yields same decision; changed inputs cannot reuse cached PASS.
7. Given Frozen protocol with positive, negative, inconclusive and corrupt evidence results., when the AC-007 operation is exercised, then Retained scientific conclusion survives restarts/exports.
8. Given Independent labelled ten-category challenge manifest and real Node A/Gate/Node B boundary., when the AC-008 operation is exercised, then Rerun entire affected suite on changed gate/profile/configuration; preserve per-case outcomes.
9. Given Forbidden mutation attempts and pre-labelled verifier challenge categories., when the AC-009 operation is exercised, then Independent human-admitted profile revision creates new identity and invalidates downstream evidence.
10. Given Exact upstream source snapshots plus a fixed labelled adaptation corpus separate from RSI hidden fixtures and live requests., when the AC-010 operation is exercised, then An upstream/profile change creates a revised mapping and new pinned profile; invalidate affected calibration and boundary evidence.

### Edge Cases

Each AC includes its normal, failure and recovery scenario above. Shared cases include missing/invalid inputs, foreign or stale artifact/contract/implementation identity, unavailable required service, budget exhaustion, permission/disclosure escape, malformed assessment, cancelled or uncertain delivery, persistence failure, duplicate request, restart and incompatible revisions as applicable. Omissions require a source-based explanation in the implementing plan; an all-skipped suite is not acceptance.

## Requirements

### Functional Requirements

- **FR-001**: Bind complete mandatory check plans from independently admitted profiles. Source: PRD 4.2, PRD 4.2.1, PRD 4.2.2, PRD 5.2.1.
- **FR-002**: Execute Tier 1 first and prohibit semantic calls after mandatory deterministic failure. Source: PRD 4.2.1, PRD 4.2.2.
- **FR-003**: Check engineering and operational evidence against declared obligations. Source: PRD 4.2.3, PRD 4.2.4.
- **FR-004**: Enforce and evaluate prohibited behavior and disclosure before trust. Source: PRD 4.2.5.
- **FR-005**: Provision a separate read-only semantic assessor with scoped output-led evidence. Source: PRD 4.2.1, PRD 4.2.6.
- **FR-006**: Apply stable verdicts and exact protected durable release. Source: PRD 4.2.7, PRD 4.2.8.
- **FR-007**: Preserve scientific negative findings as accepted research outcomes. Source: PRD 4.2.8.
- **FR-008**: Demonstrate all ten evaluator acceptance/failure-injection categories on actual connected boundaries. Source: PRD 4.2.9.
- **FR-009**: Protect referee closure and calibrate semantic limits without expanding future evaluator scope. Source: PRD 4.2.10, PRD 4.2.1.
- **FR-010**: Adapt the required upstream verifier evaluation logic into admitted node-specific Tier-2 profiles with traceable source disposition. Source: PRD 4.2.6.

### Key Entities

BoundVerificationSubject, VerificationVerdictAndGateDecision, typed artifact reference, immutable input/implementation/profile pins, run/node/attempt/invocation identity and observable result. Exact semantics are owned by [TASK §4](TASK.md#m0-if-007-at-r1).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD 4.2, PRD 4.2.1, PRD 4.2.2, PRD 5.2.1; FR-001; US1/US2/US3 | Fixed preparation uses original request+template obligations; research uses accepted Brief/protocol; assignment pins full contract, CC/dependency versions, criteria, policy, limits and evidence; producer/planner cannot waive checks. The contract binds the exact seeded/admitted primary verifier_capsule.md declaration, prompt and implementation closure under the canonical M0-003 primary capability registry; supporting capabilities are separately admitted and explicitly bound. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-002 | PRD 4.2.1, PRD 4.2.2; FR-002; US1/US2/US3 | Schema/types/non-null/bounds/artifact names, exact run/node/contract/CC identities, required evidence and completion are checked; failed or unavailable mandatory check records non-advancing verdict and Tier 2 NOT_RUN. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-003 | PRD 4.2.3, PRD 4.2.4; FR-003; US1/US2/US3 | Supplied mandatory tests/compile/prohibited-import/entry-point/write-scope checks and time/call/benchmark integrity assertions use real outcomes; failing test names and stderr are retained; no autonomous fix. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-004 | PRD 4.2.5; FR-004; US1/US2/US3 | Forbidden POC imports os/sys/subprocess/requests/urllib/shutil, undeclared tools, path escapes, unprivileged-boundary evidence, secrets and attribution are checked; violation is FAIL, unavailable mandatory isolation is ENVIRONMENT_BLOCKED. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-005 | PRD 4.2.1, PRD 4.2.6; FR-005; US1/US2/US3 | Verifier receives trusted obligations plus exact output/approved evidence, not producer conversation/chain-of-thought or suggested verdict; injection is data; bounded broker reads cannot access unrelated credentials/hidden fixtures or edit subject. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-006 | PRD 4.2.7, PRD 4.2.8; FR-006; US1/US2/US3 | Only PASS and PASS_WITH_KNOWN_LIMITATIONS with all mandatory checks advance; FAIL/ENVIRONMENT_BLOCKED/INCONCLUSIVE halt; ESCALATE_TO_HUMAN is action not verdict; raw assessment/decision binds exact subject before release. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-007 | PRD 4.2.8; FR-007; US1/US2/US3 | Schema-valid scientifically FAIL evaluation with valid evidence receives infrastructure PASS and reaches Delivery unchanged; only process/evidence violations halt. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-008 | PRD 4.2.9; FR-008; US1/US2/US3 | Valid, schema-invalid, stale/swapped, unsupported citation, budget, prohibited tool/code, environment block, known limitation, scientific negative and delayed durable gate cases each assert actual successor lock/release and Tier 2 call behavior. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-009 | PRD 4.2.10, PRD 4.2.1; FR-009; US1/US2/US3 | RSI cannot mutate any guard/check/rubric/policy/custody transitive dependency; no recursive/ensemble/dynamic evaluator or reviewer repair; development fixture labels are fixed before candidate measurement and false acceptance/refusal disclosed. Verification findings and gating advancement policy are distinct responsibilities; M1 mandatory composition is not a general equivalence. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-010 | PRD 4.2.6; FR-010; US1/US2/US3 | Pin the exact revision and content hashes of sciencediscovery/result-evaluator and sciencediscovery/citation-reviewer; map every adopted check to profile and node-specific semantic obligations; record inapplicable portions with rationale; execute positive, omission, unsupported citation, injection, uncertainty and scientific-ownership adaptation cases. Profiles remain read-only, structured, frozen and without gate authority. Missing upstream input blocks adaptation acceptance, not unrelated preparation. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |

Mandatory behavior/failure constraints use exact source requirements; finite independent fixture cases must all meet their stated assertions. Source examples do not become arbitrary thresholds. Scientific thresholds are supplied/frozen for the run, not coding-agent inventions. Missing numeric policies are PENDING_SOURCE only for affected checks.

## Scope and Assumptions

- Included: Own mandatory check profiles and immutable full-context assignments, minimize verifier disclosure, enforce deterministic then semantic assessment, validate exact subject and durably decide release.
- Excluded: No recursive verifier chain, reviewer-authored repairs, parallel voting, producer-approved policy, RSI referee mutation, live fact-check crawling or semantic PASS-as-scientific-truth.
- Consumed agreements: [M0-IF-001@r1](../M0-001/TASK.md#m0-if-001-at-r1); [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1).
- Permitted models: Phase 1 uses the PRD static subscription-authenticated Codex route; do not invent model IDs or providers. Phase 3 uses only explicitly approved pinned profiles/endpoints; before approval, mocks/analysis are labelled. Relevant provider model identifier/version is captured from actual runtime, never assumed.
- Architecture D1–D15 applies by responsibility; D5/D6 are explicit adopted amendments, not silent unchanged compliance. M0 is the coding-program folder, M1 the product.
- Verification checks outputs and evidence; gating applies advancement policy. M1 mandatory integration preserves distinct responsibilities and protected durable verdict/release. All Tier-2 profiles consume M0-007 required upstream adaptation; no profile skips PRD 4.2.6 by using an unrelated generic prompt.
- System contribution: [M0-SYSTEM](../M0-SYSTEM/spec.md); this spec owns block/boundary acceptance and does not duplicate complete-system criteria.
- SRC-GATE: Legacy semantic quality refusal rule and fallback/retry defaults conflict with current mandatory gate and D4. Affects All check assignments and release behavior. Resolution: Current PRD 1.4/4.2 and D2/D4/D15 govern; old schema epochs are compatibility context and never runtime permission.
- Q-CALIBRATION: Real semantic calibration corpus and quantitative reliability threshold are not supplied. Affects Semantic characterization, profile admission and real semantic acceptance claims; deterministic lock assertions can proceed independently.. Resolution: Freeze independent labelled dataset/rubric and justified development acceptance criterion before candidate measurement; preserve false acceptance/refusal, counts and provider correlation; deterministic lock assertions remain executable independently.
- Q-UPSTREAM-RUBRICS: Required result-evaluator and citation-reviewer source bodies and exact upstream revision are absent from this checkout. Affects AC-010, adaptation/calibration/admission and all dependent live Tier-2 profile acceptance. Resolution: Obtain the authorized exact upstream snapshots, pin revision/content identity, map applicable checks and justified exclusions in the owning native plan/profile support record, then execute the declared adaptation cases before acceptance.

This is the acceptance authority. Technical realization belongs in plan.md; work and current evidence are in tasks.md. No runtime acceptance is claimed by specification generation.
