# Feature Specification: M0-011 — Fixed-rubric screening and deterministic Top-1 ranking

**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M0](../TASKS.md)
**Revision / date**: r1 / 2026-10-06
**Feature Branch**: ai4r_xiaoyang; directory identity is independent of branch
**Input**: PRD 3.4 (../source/PRD - AI4Research.txt:L868-L873); PRD 3.4.1 (../source/PRD - AI4Research.txt:L874-L883); PRD 3.4.2 (../source/PRD - AI4Research.txt:L884-L890); PRD 3.4.3 (../source/PRD - AI4Research.txt:L891-L897); PRD 3.4.4 (../source/PRD - AI4Research.txt:L898-L904); PRD 3.4.5 (../source/PRD - AI4Research.txt:L905-L916); PRD 3.4.6 (../source/PRD - AI4Research.txt:L917-L923); PRD 3.4.7 (../source/PRD - AI4Research.txt:L924-L937); PRD 4.2.1 (../source/PRD - AI4Research.txt:L1314-L1354); PRD 4.2.6 (../source/PRD - AI4Research.txt:L1483-L1513); PRD 4.4.3 (../source/PRD - AI4Research.txt:L1837-L1858); PRD 5.2.1 (../source/PRD - AI4Research.txt:L2310-L2327); architecture m1-design.md, workflow.md, contracts-and-native-reuse.md, guard-design.md, placement.md, failure-and-human.md, offline-rsi.md; parent immutable source manifest
**Status**: Specified for preparation; runtime NOT_RUN

## User Scenarios & Testing

### User Story 1 — Complete the bounded declared outcome (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Near-identical proposals, same title/different mechanism and same mechanism/different baseline., when the AC-001 operation is exercised, then All input IDs and merged-source evidence remain recoverable.
2. Given Complete card, missing risks, fabricated citation, unstructured prose and unsupported mechanism., when the AC-002 operation is exercised, then Card meaning remains attributable to accepted incoming evidence.
3. Given Evidence-grounded bottleneck, broad market claim and commercial ROI narrative., when the AC-003 operation is exercised, then Technical value proposition and uncertainty remain explicit.
4. Given Known score cards plus missing/extra dimension, out-of-range/non-numeric score and unsupported reason., when the AC-004 operation is exercised, then Score evidence links baseline novelty, implementation feasibility and permitted hardware.
5. Given Permitted supplied dataset, unavailable closed data/model and mixed feasible/infeasible cards., when the AC-005 operation is exercised, then Only eligible cards enter the ranking helper.
6. Given Distinct scores, ties, missing score, reversed input ordering and no eligible candidate., when the AC-006 operation is exercised, then Repeated identical declared inputs produce the same selected identity and summed scores.
7. Given Three candidates with winner/dependency-reject/lower-score dispositions and omitted rationale., when the AC-007 operation is exercised, then Hypothesis consumes the exact accepted winning card and relevant source assumptions.
8. Given Independently labelled valid ranking, invented novelty, hardware violation, fabricated reason, injection and near-duplicate omission., when the AC-008 operation is exercised, then Separate read-only verifier checks exact cards and reasons; protected M0-007 gate alone releases Hypothesis.
9. Given Injected request to run feasibility code, seek a patent, create new idea or ask user to select winner., when the AC-009 operation is exercised, then Automated bounded winner selection honors all fixed policy and evidence constraints.

### User Story 2 — Reject invalid or inadmissible work without advancement (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Near-identical proposals, same title/different mechanism and same mechanism/different baseline., when the AC-001 operation is exercised, then Unsupported dropped variant, invented replacement idea or iterative re-clustering fails the assigned obligation. Missing, swapped, unadmitted or stale screening_capsule.md identity prevents dispatch/release.
2. Given Complete card, missing risks, fabricated citation, unstructured prose and unsupported mechanism., when the AC-002 operation is exercised, then Missing required fields, non-grounded new idea or unresolvable source cannot advance.
3. Given Evidence-grounded bottleneck, broad market claim and commercial ROI narrative., when the AC-003 operation is exercised, then Fabricated gap, business-case substitution or omitted assumptions are flagged.
4. Given Known score cards plus missing/extra dimension, out-of-range/non-numeric score and unsupported reason., when the AC-004 operation is exercised, then Invalid dimensions/scores/reasons, live code test or debate/voting cannot satisfy screening.
5. Given Permitted supplied dataset, unavailable closed data/model and mixed feasible/infeasible cards., when the AC-005 operation is exercised, then High novelty/feasibility score cannot compensate for a denied mandatory dependency.
6. Given Distinct scores, ties, missing score, reversed input ordering and no eligible candidate., when the AC-006 operation is exercised, then Wrong arithmetic, lower-score winner, multiple winners or undeclared helper effect fails checks; no viable card causes non-advancing outcome.
7. Given Three candidates with winner/dependency-reject/lower-score dispositions and omitted rationale., when the AC-007 operation is exercised, then Detached citation, missing disposition, stale candidate set or interactive human override cannot advance.
8. Given Independently labelled valid ranking, invented novelty, hardware violation, fabricated reason, injection and near-duplicate omission., when the AC-008 operation is exercised, then Screening author/proposer cannot waive rubric dimensions or use a semantic pass to excuse arithmetic/dependency failure.
9. Given Injected request to run feasibility code, seek a patent, create new idea or ask user to select winner., when the AC-009 operation is exercised, then Observed forbidden behavior halts under common policy even if a selected card looks valid.

### User Story 3 — Recover inspectability without silent replay or overwritten evidence (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Near-identical proposals, same title/different mechanism and same mechanism/different baseline., when the AC-001 operation is exercised, then Consolidation defect yields halted evidence; no hidden new ideation round.
2. Given Complete card, missing risks, fabricated citation, unstructured prose and unsupported mechanism., when the AC-002 operation is exercised, then New corrected candidate/card identity is independently checked; old failure remains available.
3. Given Evidence-grounded bottleneck, broad market claim and commercial ROI narrative., when the AC-003 operation is exercised, then Incomplete scientific grounding halts selection rather than initiating patent or business research.
4. Given Known score cards plus missing/extra dimension, out-of-range/non-numeric score and unsupported reason., when the AC-004 operation is exercised, then Score defects halt without repeated assessor calls or author-authored rubric relaxation.
5. Given Permitted supplied dataset, unavailable closed data/model and mixed feasible/infeasible cards., when the AC-005 operation is exercised, then Supplying a newly approved resource is new input/run; no automatic downloads or formal legal audit.
6. Given Distinct scores, ties, missing score, reversed input ordering and no eligible candidate., when the AC-006 operation is exercised, then Production helper remains pinned; future RSI mutates only separate authorized sandbox copy and cannot change interface/dimensions/Top-1.
7. Given Three candidates with winner/dependency-reject/lower-score dispositions and omitted rationale., when the AC-007 operation is exercised, then Corrected ranking creates attributable new work with fresh checking; no overwriting the original candidate history.
8. Given Independently labelled valid ranking, invented novelty, hardware violation, fabricated reason, injection and near-duplicate omission., when the AC-008 operation is exercised, then Upstream/profile/helper changes invalidate calibration and affected acceptance; preserve false accepts/refusals and uncertainty.
9. Given Injected request to run feasibility code, seek a patent, create new idea or ask user to select winner., when the AC-009 operation is exercised, then Human correction starts fresh work; no local exception changes frozen score/interface/referee semantics.

### Edge Cases

Each AC includes its normal, failure and recovery scenario above. Shared cases include missing/invalid inputs, foreign or stale artifact/contract/implementation identity, unavailable required service, budget exhaustion, permission/disclosure escape, malformed assessment, cancelled or uncertain delivery, persistence failure, duplicate request, restart and incompatible revisions as applicable. Omissions require a source-based explanation in the implementing plan; an all-skipped suite is not acceptance.

## Requirements

### Functional Requirements

- **FR-001**: Consolidate near-duplicates once without erasing distinct mechanisms. Source: PRD 3.4, PRD 3.4.1, PRD 5.2.1.
- **FR-002**: Form typed grounded Idea Cards. Source: PRD 3.4.2, PRD 3.4.3.
- **FR-003**: State the specific scientific opportunity without commercial expansion. Source: PRD 3.4.4.
- **FR-004**: Score exactly the fixed three dimensions with reasons in one pass. Source: PRD 3.4.5.
- **FR-005**: Reject disallowed or unavailable candidate dependencies before ranking. Source: PRD 3.4.6.
- **FR-006**: Use a pure deterministic ranking helper preserving required Top-1 semantics. Source: PRD 3.4.7, PRD 4.4.3.
- **FR-007**: Preserve full selection and rejection evidence in Opportunity_Card. Source: PRD 3.4.7.
- **FR-008**: Provide fixed screening domain calibration to the common verification/gate composition. Source: PRD 4.2.1, PRD 4.2.6, PRD 3.4.5, PRD 3.4.7.
- **FR-009**: Keep pragmatic screening inside the bounded M1 responsibility. Source: PRD 3.4.1, PRD 3.4.2, PRD 3.4.4, PRD 3.4.5, PRD 3.4.6, PRD 3.4.7.

### Key Entities

AcceptedCandidateSet, Opportunity_Card.json, typed artifact reference, immutable input/implementation/profile pins, run/node/attempt/invocation identity and observable result. Exact semantics are owned by [TASK §4](TASK.md#m0-if-011-at-r1).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD 3.4, PRD 3.4.1, PRD 5.2.1; FR-001; US1/US2/US3 | Single-pass consolidation maps every input candidate to a retained/merged disposition; variants with different mechanism or baseline evidence remain distinct and traceable. The contract binds the exact seeded/admitted primary screening_capsule.md declaration, prompt and implementation closure under the canonical M0-003 primary capability registry; supporting capabilities are separately admitted and explicitly bound. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-002 | PRD 3.4.2, PRD 3.4.3; FR-002; US1/US2/US3 | Each consolidated candidate has stable idea_id/title/summary/linked citations/core assumptions/identified risks plus explicit technical problem and mechanism; schema and source bindings are valid. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-003 | PRD 3.4.4; FR-003; US1/US2/US3 | Opportunity_statement identifies the cited technical bottleneck and why the proposed mechanism addresses it; claims are no broader than the source evidence and Brief. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-004 | PRD 3.4.5; FR-004; US1/US2/US3 | Each eligible card receives Novelty, Technical Feasibility and Compute Alignment on the stated 1-5 scales, each with an evidence-grounded one-sentence reason; compute alignment uses Brief bounds; one bounded LLM assessment supplies scores. Technical Feasibility specifically considers bounded implementation in standard PyTorch/Python frameworks, as required by PRD 3.4.5. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-005 | PRD 3.4.6; FR-005; US1/US2/US3 | Deterministic dependency filter excludes ideas requiring undeclared/unavailable proprietary models or closed datasets; disposition records the specific conflicting requirement and evidence. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-006 | PRD 3.4.7, PRD 4.4.3; FR-006; US1/US2/US3 | rank_opportunities computes Novelty + Feasibility + ComputeAlignment, selects exactly one highest-scoring eligible card under a predeclared tie rule and performs no model/tool/filesystem/network effects. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-007 | PRD 3.4.7; FR-007; US1/US2/US3 | Opportunity_Card.json contains the selected card plus score/justification/dependency/consolidation provenance and rejection/deferral rationales for every nonwinning candidate; accepted Brief/source references survive. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-008 | PRD 4.2.1, PRD 4.2.6, PRD 3.4.5, PRD 3.4.7; FR-008; US1/US2/US3 | Pin upstream assessment-screening content for the producer and result-evaluator/citation-reviewer mappings for independent assessment; fixed profiles check evidence-grounded dimensions/card fidelity while deterministic checks recalculate sums/Top-1; unsupported empirical/publication logic is explicitly N/A with tests. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-009 | PRD 3.4.1, PRD 3.4.2, PRD 3.4.4, PRD 3.4.5, PRD 3.4.6, PRD 3.4.7; FR-009; US1/US2/US3 | Connected observation shows no new unconstrained brainstorming, multiround clustering, ROI/market sizing, patent/legal queries, code execution, vote/debate or human winner-selection wait. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |

Mandatory behavior/failure constraints use exact source requirements; finite independent fixture cases must all meet their stated assertions. Source examples do not become arbitrary thresholds. Scientific thresholds are supplied/frozen for the run, not coding-agent inventions. Missing numeric policies are PENDING_SOURCE only for affected checks.

## Scope and Assumptions

- Included: Consolidate admitted candidates once, form evidence-linked opportunity cards, score fixed dimensions, filter unavailable dependencies and select the deterministic highest-scoring opportunity with rejection reasons and a pure rank_opportunities seam for isolated RSI.
- Excluded: No new brainstorming, iterative clustering, commercial ROI/market/legal/patent analysis, live feasibility execution, multi-agent voting, human selection or production RSI mutation.
- Consumed agreements: [M0-IF-010@r1](../M0-010/TASK.md#m0-if-010-at-r1); [M0-IF-009@r1](../M0-009/TASK.md#m0-if-009-at-r1); [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1); [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1).
- Permitted models: Phase 1 uses the PRD static subscription-authenticated Codex route; do not invent model IDs or providers. Phase 3 uses only explicitly approved pinned profiles/endpoints; before approval, mocks/analysis are labelled. Relevant provider model identifier/version is captured from actual runtime, never assumed.
- Architecture D1–D15 applies by responsibility; D5/D6 are explicit adopted amendments, not silent unchanged compliance. M0 is the coding-program folder, M1 the product.
- Verification checks outputs and evidence; gating applies advancement policy. M1 mandatory integration preserves distinct responsibilities and protected durable verdict/release. All Tier-2 profiles consume M0-007 required upstream adaptation; no profile skips PRD 4.2.6 by using an unrelated generic prompt.
- System contribution: [M0-SYSTEM](../M0-SYSTEM/spec.md); this spec owns block/boundary acceptance and does not duplicate complete-system criteria.
- Q-RANK-TIES: PRD specifies summed Top-1 but not tie, missing-score and no-eligible-card serialization. Affects Deterministic helper boundary and RSI target contract. Resolution: Own a fixed transparent tie/error contract before implementation and fixtures. Highest-score Top-1 and fail-fast missing mandatory input remain invariant; no new numeric threshold.
- SRC-RSI-RUBRIC: Optional work-rubric mutation can mention weights/scales while production screening fixes dimensions/sum. Affects RSI target compatibility. Resolution: M0-018 target declaration must preserve incoming required dimensions, sum/Top-1 output/interface and referee; text target permission does not authorize production or gate-policy change.

This is the acceptance authority. Technical realization belongs in plan.md; work and current evidence are in tasks.md. No runtime acceptance is claimed by specification generation.
