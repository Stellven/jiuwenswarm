# Feature Specification: M0-016 — Faithful Markdown research delivery and verified artifact closure

**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M0](../TASKS.md)
**Revision / date**: r1 / 2026-10-06
**Feature Branch**: ai4r_xiaoyang; directory identity is independent of branch
**Input**: PRD 3.9 (../source/PRD - AI4Research.txt:L1146-L1151); PRD 3.9.1 (../source/PRD - AI4Research.txt:L1152-L1159); PRD 3.9.2 (../source/PRD - AI4Research.txt:L1160-L1167); PRD 3.9.3 (../source/PRD - AI4Research.txt:L1168-L1174); PRD 3.9.4 (../source/PRD - AI4Research.txt:L1175-L1189); PRD 4.2.1 (../source/PRD - AI4Research.txt:L1314-L1354); PRD 4.2.6 (../source/PRD - AI4Research.txt:L1483-L1513); PRD 4.9.3 (../source/PRD - AI4Research.txt:L2223-L2236); PRD 5.2.1 (../source/PRD - AI4Research.txt:L2310-L2327); PRD 6.9 (../source/PRD - AI4Research.txt:L2700-L2717); architecture m1-design.md, workflow.md, contracts-and-native-reuse.md, guard-design.md, placement.md, failure-and-human.md; parent immutable source manifest
**Status**: Specified for preparation; runtime NOT_RUN

## User Scenarios & Testing

### User Story 1 — Complete the bounded declared outcome (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Complete accepted input set, stale verdict, missing benchmark and audience-profile instruction., when the AC-001 operation is exercised, then Report structure and content responsibilities are declared before generation.
2. Given Positive/negative/inconclusive/conditional science, known limitations and unsupported success statement., when the AC-002 operation is exercised, then User receives faithful positive or negative findings and their evidentiary limits.
3. Given Complete package, missing POC/environment/raw data, broken reference, archive traversal and secret/hidden-fixture canary., when the AC-003 operation is exercised, then User can locate the report and reproduce declared local execution inputs from the permitted evidence.
4. Given Accepted report, delayed gate, failed storage commit, browser disconnect and wrong-user destination., when the AC-004 operation is exercised, then Final report/package references and completed lifecycle are durably attributable to the correct user/run.
5. Given Injected request for public upload, automatic chat attachment, custom slides and upstream verdict rewrite., when the AC-005 operation is exercised, then Local evidence-grounded deliverable completes without external effects.
6. Given Labelled faithful negative report, inflated delta, unsupported citation, omitted limitation, prompt injection and missing artifact., when the AC-006 operation is exercised, then Verifier returns grounded findings for exact report/package; protected gate alone authorizes closure.

### User Story 2 — Reject invalid or inadmissible work without advancement (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Complete accepted input set, stale verdict, missing benchmark and audience-profile instruction., when the AC-001 operation is exercised, then Unaccepted/stale inputs, fabricated missing sources or custom audience-derived structure prevent delivery acceptance. Missing, swapped, unadmitted or stale report_capsule.md identity prevents dispatch/release.
2. Given Positive/negative/inconclusive/conditional science, known limitations and unsupported success statement., when the AC-002 operation is exercised, then Scientific FAIL omitted/relabelled, unsupported citation, invented data or missing mandatory methods/limitations cannot pass.
3. Given Complete package, missing POC/environment/raw data, broken reference, archive traversal and secret/hidden-fixture canary., when the AC-003 operation is exercised, then Incomplete/mislabeled package, unauthorized disclosure or automatic external repository/registry publishing is denied.
4. Given Accepted report, delayed gate, failed storage commit, browser disconnect and wrong-user destination., when the AC-004 operation is exercised, then Pending/failed final gate, orphan files, unauthorized destination or persistence fault cannot advertise accepted completion.
5. Given Injected request for public upload, automatic chat attachment, custom slides and upstream verdict rewrite., when the AC-005 operation is exercised, then Forbidden format/distribution/analytical-owner substitution is denied even when report text appears correct.
6. Given Labelled faithful negative report, inflated delta, unsupported citation, omitted limitation, prompt injection and missing artifact., when the AC-006 operation is exercised, then Reviewer substitute text, producer completion claim or missing mandatory evidence cannot count as delivery acceptance.

### User Story 3 — Recover inspectability without silent replay or overwritten evidence (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Complete accepted input set, stale verdict, missing benchmark and audience-profile instruction., when the AC-001 operation is exercised, then Missing template/source detail is resolved and versioned before acceptance; no dynamic layout invention to obscure absent evidence.
2. Given Positive/negative/inconclusive/conditional science, known limitations and unsupported success statement., when the AC-002 operation is exercised, then Report correction is new attributable work with fresh checking; upstream scientific evidence/verdict stay immutable.
3. Given Complete package, missing POC/environment/raw data, broken reference, archive traversal and secret/hidden-fixture canary., when the AC-003 operation is exercised, then Packaging failure preserves original artifacts and blocked state; rebuilding package cannot change historical decisions.
4. Given Accepted report, delayed gate, failed storage commit, browser disconnect and wrong-user destination., when the AC-004 operation is exercised, then Browser reconnection retrieves the same accepted result; transfer correction retains evidence without rerunning research or fabricating prior completion.
5. Given Injected request for public upload, automatic chat attachment, custom slides and upstream verdict rewrite., when the AC-005 operation is exercised, then Any later publication or extra format requires separately authorized scope; current run retains exact local outputs.
6. Given Labelled faithful negative report, inflated delta, unsupported citation, omitted limitation, prompt injection and missing artifact., when the AC-006 operation is exercised, then Template/source/profile/model change invalidates affected calibration; preserve measured errors and no scientific-truth guarantee.

### Edge Cases

Each AC includes its normal, failure and recovery scenario above. Shared cases include missing/invalid inputs, foreign or stale artifact/contract/implementation identity, unavailable required service, budget exhaustion, permission/disclosure escape, malformed assessment, cancelled or uncertain delivery, persistence failure, duplicate request, restart and incompatible revisions as applicable. Omissions require a source-based explanation in the implementing plan; an all-skipped suite is not acceptance.

## Requirements

### Functional Requirements

- **FR-001**: Assemble accepted delivery inputs and pin the standard report structure. Source: PRD 3.9, PRD 3.9.1, PRD 5.2.1.
- **FR-002**: Generate a faithful evidence-grounded Markdown report. Source: PRD 3.9.2.
- **FR-003**: Package the complete bounded research lifecycle for the user. Source: PRD 3.9.3.
- **FR-004**: Release accepted artifacts through local control-plane delivery and close lifecycle. Source: PRD 3.9.4, PRD 6.9.
- **FR-005**: Keep delivery responsibility and distribution inside declared M1 bounds. Source: PRD 3.9.1, PRD 3.9.2, PRD 3.9.3, PRD 3.9.4, PRD 4.9.3.
- **FR-006**: Provide report fidelity/citation calibration to mandatory independent checks. Source: PRD 4.2.1, PRD 4.2.6, PRD 3.9.2, PRD 3.9.4.

### Key Entities

AcceptedScientificVerdict, ResearchDeliveryBundle, typed artifact reference, immutable input/implementation/profile pins, run/node/attempt/invocation identity and observable result. Exact semantics are owned by [TASK §4](TASK.md#m0-if-016-at-r1).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD 3.9, PRD 3.9.1, PRD 5.2.1; FR-001; US1/US2/US3 | Delivery reads exact accepted Evaluation_Verdict, Benchmark_Payload and Research_Brief plus relevant Blueprint/citations/artifact references; the adapted sciencediscovery/report-writer template has a pinned upstream source revision and fixed M1 Markdown layout. The contract binds the exact seeded/admitted primary report_capsule.md declaration, prompt and implementation closure under the canonical M0-003 primary capability registry; supporting capabilities are separately admitted and explicitly bound. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-002 | PRD 3.9.2; FR-002; US1/US2/US3 | research_report.md includes user objective, hypothesis/methodology, baseline/treatment results and delta, unchanged scientific verdict, verified citations, benchmark analysis, warnings/material limitations and follow-ups; all material assertions link to admitted source/result evidence. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-003 | PRD 3.9.3; FR-003; US1/US2/US3 | Single clean output package/directory includes checked report, POC scripts, frozen environment/dependencies, raw empirical data and permitted evidence index with resolvable identities; archive/path policy excludes credentials, control state and RSI hidden fixtures. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-004 | PRD 3.9.4, PRD 6.9; FR-004; US1/US2/US3 | After final mandatory checks and durable gate acceptance, control plane transfers exact accepted artifacts to authorized user workspace, exposes Markdown in native Web/TUI and records completed run-tree/trace; producer cannot directly mark run completed or release unchecked report. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-005 | PRD 3.9.1, PRD 3.9.2, PRD 3.9.3, PRD 3.9.4, PRD 4.9.3; FR-005; US1/US2/US3 | Observed output format is fixed Markdown plus permitted research assets; no audience profiling, LaTeX/slides/interactive dashboard, external Git/community publication or Slack/WeChat/Discord notification occurs; Builder does not regenerate analytical report. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-006 | PRD 4.2.1, PRD 4.2.6, PRD 3.9.2, PRD 3.9.4; FR-006; US1/US2/US3 | M0-007 uses pinned result-evaluator/citation-reviewer node mappings to compare report against accepted Brief/protocol/measurements/verdict and test citation fidelity/limitations; unrelated peer-review/manuscript portions are explicit N/A, while schema/package/effect checks remain mandatory before separate read-only semantic assessment. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |

Mandatory behavior/failure constraints use exact source requirements; finite independent fixture cases must all meet their stated assertions. Source examples do not become arbitrary thresholds. Scientific thresholds are supplied/frozen for the run, not coding-agent inventions. Missing numeric policies are PENDING_SOURCE only for affected checks.

## Scope and Assumptions

- Included: Synthesize gate-admitted scientific verdict, protocol, original Brief, citations, POC assets and empirical evidence into the fixed Markdown research report and user package; transfer accepted artifacts through the control plane and close the run.
- Excluded: No audience profiling/custom report structures, publication-ready LaTeX/slides/dashboard formats, external Git/registry publication, chat notifications or verdict/measurement reinterpretation.
- Consumed agreements: [M0-IF-015@r1](../M0-015/TASK.md#m0-if-015-at-r1); [M0-IF-014@r1](../M0-014/TASK.md#m0-if-014-at-r1); [M0-IF-013@r1](../M0-013/TASK.md#m0-if-013-at-r1); [M0-IF-012@r1](../M0-012/TASK.md#m0-if-012-at-r1); [M0-IF-009@r1](../M0-009/TASK.md#m0-if-009-at-r1); [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1); [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1).
- Permitted models: Phase 1 uses the PRD static subscription-authenticated Codex route; do not invent model IDs or providers. Phase 3 uses only explicitly approved pinned profiles/endpoints; before approval, mocks/analysis are labelled. Relevant provider model identifier/version is captured from actual runtime, never assumed.
- Architecture D1–D15 applies by responsibility; D5/D6 are explicit adopted amendments, not silent unchanged compliance. M0 is the coding-program folder, M1 the product.
- Verification checks outputs and evidence; gating applies advancement policy. M1 mandatory integration preserves distinct responsibilities and protected durable verdict/release. All Tier-2 profiles consume M0-007 required upstream adaptation; no profile skips PRD 4.2.6 by using an unrelated generic prompt.
- System contribution: [M0-SYSTEM](../M0-SYSTEM/spec.md); this spec owns block/boundary acceptance and does not duplicate complete-system criteria.
- Q-REPORT-UPSTREAM: Required sciencediscovery report-writer/result-evaluator/citation-reviewer source implementations are not present at inspected repository paths. Affects Pinned template and domain verification adaptations. Resolution: Resolve exact authorized upstream/revision, import/adapt via governed library ownership and record node obligation mappings/N/A/tests before live acceptance; retain proposed paths as proposed until implemented.

This is the acceptance authority. Technical realization belongs in plan.md; work and current evidence are in tasks.md. No runtime acceptance is claimed by specification generation.
