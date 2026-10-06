# Feature Specification: M0-010 — Bounded evidence retrieval and grounded candidate ideation

**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M0](../TASKS.md)
**Revision / date**: r1 / 2026-10-06
**Feature Branch**: ai4r_xiaoyang; directory identity is independent of branch
**Input**: PRD 2.4 (../source/PRD - AI4Research.txt:L467-L485); PRD 3.3 (../source/PRD - AI4Research.txt:L810-L813); PRD 3.3.1 (../source/PRD - AI4Research.txt:L814-L822); PRD 3.3.2 (../source/PRD - AI4Research.txt:L823-L834); PRD 3.3.3 (../source/PRD - AI4Research.txt:L835-L841); PRD 3.3.4 (../source/PRD - AI4Research.txt:L842-L848); PRD 3.3.5 (../source/PRD - AI4Research.txt:L849-L856); PRD 3.3.6 (../source/PRD - AI4Research.txt:L857-L867); PRD 4.2.1 (../source/PRD - AI4Research.txt:L1314-L1354); PRD 4.2.6 (../source/PRD - AI4Research.txt:L1483-L1513); PRD 5.2.1 (../source/PRD - AI4Research.txt:L2310-L2327); architecture m1-design.md, workflow.md, contracts-and-native-reuse.md, guard-design.md, placement.md, failure-and-human.md, capsules.md; parent immutable source manifest
**Status**: Specified for preparation; runtime NOT_RUN

## User Scenarios & Testing

### User Story 1 — Complete the bounded declared outcome (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Brief with explicit exclusions, good/poor initial retrieval and an injected suggestion to expand search., when the AC-001 operation is exercised, then Search executes the declared query strategy within frozen scope.
2. Given Local hits, academic fixture connector, over-Top-K response, unavailable connector and unauthorized network destination., when the AC-002 operation is exercised, then Bounded permitted results are captured with source metadata and declared connector route.
3. Given Known source texts, duplicated chunk, changed source, fabricated quote and ambiguous title collision., when the AC-003 operation is exercised, then Later candidate citations resolve to the original captured excerpt rather than a lossy LLM summary.
4. Given One/two/three candidates and zero/four candidates, unsupported mechanism and fabricated cited filename., when the AC-004 operation is exercised, then Supported distinct ideas can advance with their source evidence.
5. Given Valid candidates, wrong schema, stale run, exceeded time/calls and absent token usage., when the AC-005 operation is exercised, then Screening receives only the exact durably accepted artifact and required source references.
6. Given Labelled faithful retrieval, broken citation, unsupported technical claim, source injection and missing limitations., when the AC-006 operation is exercised, then Separate read-only verifier assesses exact candidate/output evidence and returns reasons/references.
7. Given Adversarial instructions request Google scraping, query retries, trend scoring and additional agents., when the AC-007 operation is exercised, then Single linear bounded search/ideation path remains observable.

### User Story 2 — Reject invalid or inadmissible work without advancement (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Brief with explicit exclusions, good/poor initial retrieval and an injected suggestion to expand search., when the AC-001 operation is exercised, then Poor results cannot trigger rewritten/new queries, recursive prompting or unauthorized source expansion. Missing, swapped, unadmitted or stale search_capsule.md identity prevents dispatch/release.
2. Given Local hits, academic fixture connector, over-Top-K response, unavailable connector and unauthorized network destination., when the AC-002 operation is exercised, then General web/crawling, unadmitted connector, undeclared dataset/repository fetch and search swarm are denied; required unavailable connector is truthfully blocked.
3. Given Known source texts, duplicated chunk, changed source, fabricated quote and ambiguous title collision., when the AC-003 operation is exercised, then Fabricated/transformed excerpt, detached citation and unsupported trend/authority assessment fail evidence integrity.
4. Given One/two/three candidates and zero/four candidates, unsupported mechanism and fabricated cited filename., when the AC-004 operation is exercised, then Wrong count, speculative unsupported idea, invented source or scope violation cannot advance.
5. Given Valid candidates, wrong schema, stale run, exceeded time/calls and absent token usage., when the AC-005 operation is exercised, then Candidate file existence, plausible summary, missing evidence or budget violation does not release Screening.
6. Given Labelled faithful retrieval, broken citation, unsupported technical claim, source injection and missing limitations., when the AC-006 operation is exercised, then Producer narrative, suggested verdict or missing evidence cannot substitute support or waive applicable checks.
7. Given Adversarial instructions request Google scraping, query retries, trend scoring and additional agents., when the AC-007 operation is exercised, then Any forbidden action is detected/contained as required by runner and gate policy; correct-looking candidates do not excuse it.

### User Story 3 — Recover inspectability without silent replay or overwritten evidence (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Brief with explicit exclusions, good/poor initial retrieval and an injected suggestion to expand search., when the AC-001 operation is exercised, then Insufficient evidence is retained and blocks affected output rather than silently repairing strategy.
2. Given Local hits, academic fixture connector, over-Top-K response, unavailable connector and unauthorized network destination., when the AC-002 operation is exercised, then Connector repair yields fresh attributable work; missing results are not invented and five-paper example is not a default requirement.
3. Given Known source texts, duplicated chunk, changed source, fabricated quote and ambiguous title collision., when the AC-003 operation is exercised, then Replacement evidence receives new identity; stale citations are invalidated and original captured source remains retained.
4. Given One/two/three candidates and zero/four candidates, unsupported mechanism and fabricated cited filename., when the AC-004 operation is exercised, then Scientific evidence scarcity is exposed; no autonomous new search/ideation round repairs the candidate set.
5. Given Valid candidates, wrong schema, stale run, exceeded time/calls and absent token usage., when the AC-005 operation is exercised, then Blocking findings preserve candidate/runtime/source evidence and halt; corrected work starts a fresh linked run.
6. Given Labelled faithful retrieval, broken citation, unsupported technical claim, source injection and missing limitations., when the AC-006 operation is exercised, then Changed connector/query/profile/source snapshot invalidates affected evidence; no semantic failure prompts automatic retry.
7. Given Adversarial instructions request Google scraping, query retries, trend scoring and additional agents., when the AC-007 operation is exercised, then Failure evidence and known capture limits are preserved without silent sanitization or downgraded scope.

### Edge Cases

Each AC includes its normal, failure and recovery scenario above. Shared cases include missing/invalid inputs, foreign or stale artifact/contract/implementation identity, unavailable required service, budget exhaustion, permission/disclosure escape, malformed assessment, cancelled or uncertain delivery, persistence failure, duplicate request, restart and incompatible revisions as applicable. Omissions require a source-based explanation in the implementing plan; an all-skipped suite is not acceptance.

## Requirements

### Functional Requirements

- **FR-001**: Freeze a single-pass query strategy from the accepted Brief. Source: PRD 3.3, PRD 3.3.1, PRD 5.2.1.
- **FR-002**: Retrieve through admitted allowlisted operators with finite external bounds. Source: PRD 3.3.2, PRD 2.4.
- **FR-003**: Retain exact supporting excerpts grouped by their query. Source: PRD 3.3.3, PRD 3.3.4.
- **FR-004**: Generate a bounded directly grounded candidate set. Source: PRD 3.3.5.
- **FR-005**: Capture a typed Candidate_Set handoff with enforceable evidence and budgets. Source: PRD 3.3.6.
- **FR-006**: Calibrate search-specific independent verification using pinned domain logic. Source: PRD 4.2.1, PRD 4.2.6, PRD 3.3.6.
- **FR-007**: Enforce search and ideation exclusions in the connected path. Source: PRD 3.3.1, PRD 3.3.2, PRD 3.3.3, PRD 3.3.4, PRD 3.3.5, PRD 3.3.6.

### Key Entities

AcceptedResearchBrief, Candidate_Set.json, typed artifact reference, immutable input/implementation/profile pins, run/node/attempt/invocation identity and observable result. Exact semantics are owned by [TASK §4](TASK.md#m0-if-010-at-r1).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD 3.3, PRD 3.3.1, PRD 5.2.1; FR-001; US1/US2/US3 | One bounded prompt maps explicit brief themes/scope to a captured static keyword-query list before retrieval; actual queries match the frozen list and allowed source families. The contract binds the exact seeded/admitted primary search_capsule.md declaration, prompt and implementation closure under the canonical M0-003 primary capability registry; supporting capabilities are separately admitted and explicitly bound. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-002 | PRD 3.3.2, PRD 2.4; FR-002; US1/US2/US3 | Admitted search capsule/deepsearch operator queries local document buffer and explicitly designated academic connectors; configured finite Top-K is applied per query before context assembly and operator evidence records actual sources/results. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-003 | PRD 3.3.3, PRD 3.3.4; FR-003; US1/US2/US3 | Every extracted chunk is an exact span of a captured permitted source and maps to the triggering query; JSON grouping preserves source identity/title/author or local filename and relevant limitations. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-004 | PRD 3.3.5; FR-004; US1/US2/US3 | One bounded ideation call produces one to three concrete candidates; each proposed mechanism/claim includes explicit citations to supplied source excerpts and preserves Brief constraints. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-005 | PRD 3.3.6; FR-005; US1/US2/US3 | Candidate_Set.json uses the agreed schema and current run/node/contract/capsule pins; includes candidates/citations/query evidence and required observations; reliable time/invocation limits checked while missing per-call token telemetry is unavailable. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-006 | PRD 4.2.1, PRD 4.2.6, PRD 3.3.6; FR-006; US1/US2/US3 | Domain owner supplies exact grounding/citation/scope obligations to M0-007; pinned result-evaluator and citation-reviewer adaptations map material claim support and source identity to this node, mark empirical-verdict/author-bias sections inapplicable and include omission/injection challenges. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-007 | PRD 3.3.1, PRD 3.3.2, PRD 3.3.3, PRD 3.3.4, PRD 3.3.5, PRD 3.3.6; FR-007; US1/US2/US3 | Observed calls demonstrate no dynamic queries, unstructured crawling, parallel search agent, source-authority grading, historical trend analysis, unsupported speculation or recursive coverage-reflection loop. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |

Mandatory behavior/failure constraints use exact source requirements; finite independent fixture cases must all meet their stated assertions. Source examples do not become arbitrary thresholds. Scientific thresholds are supplied/frozen for the run, not coding-agent inventions. Missing numeric policies are PENDING_SOURCE only for affected checks.

## Scope and Assumptions

- Included: Search permitted local context and designated academic connectors under a fixed query plan, retain exact source excerpts and produce one to three evidence-linked candidates for Screening.
- Excluded: No unrestricted web scraping, headless crawling, dynamic query reformulation, search swarms, authority/bias/geography assessment, historical trend mapping, unsupported speculation or recursive coverage repair.
- Consumed agreements: [M0-IF-009@r1](../M0-009/TASK.md#m0-if-009-at-r1); [M0-IF-008@r1](../M0-008/TASK.md#m0-if-008-at-r1); [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1); [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1).
- Permitted models: Phase 1 uses the PRD static subscription-authenticated Codex route; do not invent model IDs or providers. Phase 3 uses only explicitly approved pinned profiles/endpoints; before approval, mocks/analysis are labelled. Relevant provider model identifier/version is captured from actual runtime, never assumed.
- Architecture D1–D15 applies by responsibility; D5/D6 are explicit adopted amendments, not silent unchanged compliance. M0 is the coding-program folder, M1 the product.
- Verification checks outputs and evidence; gating applies advancement policy. M1 mandatory integration preserves distinct responsibilities and protected durable verdict/release. All Tier-2 profiles consume M0-007 required upstream adaptation; no profile skips PRD 4.2.6 by using an unrelated generic prompt.
- System contribution: [M0-SYSTEM](../M0-SYSTEM/spec.md); this spec owns block/boundary acceptance and does not duplicate complete-system criteria.
- Q-SEARCH-OPERATOR: The current repository has generic search helpers but no inspected deepsearch capsule implementation or academic connector contract. Affects Real operator/connector integration. Resolution: Inspect installed dependency and admitted operator source; freeze exact adapter/version/allowlist. Prepare mocked bounded connector tests independently, but do not claim real integration before evidence.
- Q-SEARCH-LIMIT: PRD maximum five papers is illustrative and exact query/Top-K limits are unsupplied. Affects Retrieval/count/time boundary tests. Resolution: Define finite approved profile bounds and freeze them before verification; record actual configured values rather than inventing PRD numbers.

This is the acceptance authority. Technical realization belongs in plan.md; work and current evidence are in tasks.md. No runtime acceptance is claimed by specification generation.
