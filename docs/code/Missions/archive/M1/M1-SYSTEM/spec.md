# Feature Specification: M1-SYSTEM - Complete integrated M1 verification

> M1-C022 / 2026-10-21: Build the connected local-development workflow first. Do not run audits, tests, experiments, model-based qualification batches or further fixture-quality work for this delivery. Explicit operator authorization of exact shipped built-ins is separate from independent qualification (`qualification_status=NOT_RUN`); runtime deterministic checks, declaration/output-only Capsule verifiers, mechanical assessment checks and committed gates remain mandatory. Earlier results and strict-mode requirements are preserved.
**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M1](../TASKS.md)
**Revision / date**: r5 / 2026-10-21
**Feature Branch**: ai4r_M1
**Input**: [Source baseline](../source-baseline.json); supplied PRD §§1, 2, 6 and their references to mandatory stage exits; supplied architecture 3-build-plan.md, method/phases.md, method/clause-coverage.md and nonblocking criteria; invoked prompt Final Verification; QA implementation prompt. Approved amendments M1-C001/C002 are embedded in TASK/TASKS.
**Status**: Specified; no integrated candidate has passed

**C021 source assignment**: The explicit 2026-10-21 user request selects `../source/Architecture_Design/`, with recorded C001–C020 decisions retained. Existing AC-C019-01..06 now apply to that assignment. Research uses the source's separate Builder and Benchmark nodes, real work/check/verifier/aggregate gates, frozen model routing and one native chat. A CPU-local development run is identified as such and establishes no native GB10 qualification. No checking admission or empirical evidence may be fabricated.

## User Scenarios & Testing

### User Story 1 - Complete an evidence-backed scientific investigation (Priority: P1)
A researcher supplies an authorized objective, baseline and validation resources. The integrated native application qualifies the request, accepts a Research Brief, researches one opportunity, freezes a hypothesis, builds and executes a bounded POC, evaluates it and delivers its report and evidence.
**Independent Test**: Execute the entire static Phase 1 lifecycle through the supported containerized application with real model/runner/checker/gate/executor connections and independently frozen scientific expectations. Reconcile all accepted artifacts and committed transitions on one candidate.
**Acceptance Scenarios**:
1. Given a valid scientific request and ready resources, when the full Phase 1 workflow runs, then the report and retrievable evidence trace every governed transition from Ingestion through Delivery.
2. Given a correctly executed experiment that falsifies its hypothesis, when scientific evaluation returns FAIL, then infrastructure acceptance still permits Delivery of the negative result.
3. Given an unavailable prerequisite, prohibited effect or inadmissible artifact, when the failure occurs, then affected advancement stops, evidence is retained and the actual failure is reported without fabricated completion.

### User Story 2 - Trust the integrated advancement boundary (Priority: P1)
The evaluator and scheduler jointly prevent invalid outputs from releasing dependent work, even during persistence failures, uncertain transport or restart.
**Independent Test**: Execute all ten mandatory PRD §4.2.9 cases against the actual integrated checking/scheduler path, including observed downstream effects and durable decision ordering. Apply the approved citation-tier amendment only to case 4.
**Acceptance Scenarios**:
1. Given a valid artifact, when its mandatory checks, independent verifier and durable gate pass, then and only then may a successor start.
2. Given a mandatory Tier 1 failure, when checking finishes, then there are zero verifier calls for that work subnode and no dependent dispatch.
3. Given a delayed or failed gate persistence, when a producer has reported success, then successors remain locked until the required decision and evidence are committed.
4. Given a failed node with an independent branch, when execution continues, then only its transitive dependents are skipped; independent work follows the frozen order without retry or mid-run human wait.

### User Story 3 - Inspect honest advanced-feature and QA delivery status (Priority: P1)
The operator sees separate implementation, integration and verification outcomes for Planner, Model Routing, RSI and the four-case QA foundation, while the deterministic Phase 1 baseline stays usable.
**Independent Test**: Reconcile code and current raw evidence against every applicable phase commitment; run static/planned comparisons and nonblocking conditions; inspect all four real Docker QA case results, including unavailable dependencies and unexecuted checks.
**Acceptance Scenarios**:
1. Given an experimental path is absent, disabled or broken, when the fixed baseline runs with Codex available, then the same frozen plan and Capsule versions remain usable without side-system dependencies.
2. Given an implemented but unverified advanced feature, when status is reported, then it is described as implemented with the actual integration/verification gap, never as fully validated.
3. Given a QA case has only mock evidence or has not executed, when results are exported, then its required real integration remains incomplete.

### Edge Cases
- Retain malformed, stale, swapped, unsupported, timed-out, cancelled, interrupted, environment-blocked and scientifically negative attempts with distinct outcomes.
- A missing mandatory service, fixture, model, isolation facility, threshold or evidence record cannot become PASS through a skip, empty test collection or a generated checklist.
- An unknown resource/model fact is not an observed value. Requested and effective model/hardware profiles remain distinct.
- Restart does not replay prior side effects or create acceptance from an existing output file. Disconnection does not resubmit or cancel implicitly.
- A plan cannot add permissions, weaken checks, change the hypothesis after measurement or choose an unadmitted Capsule. Invalid static/planned proposals retain their different source-defined outcomes.
- A correctly captured missing metric retains its receipt-linked empirical row and reason under M1-C002; no measurement is fabricated or replaced with zero.
- Evidence is invalidated when the candidate, source, contract, fixtures, profile or relevant dependency changes. Historical failures remain intact.

## Requirements

### Functional Requirements
- **FR-001**: Verify one fully identified integrated candidate, including relevant uncommitted code/tests/configuration, pinned dependencies/images, supplied source identity and approved clarifications. Child evidence must be current for that candidate. [PRD 6.2.1/6.14; constitution IV/V]
- **FR-002**: Demonstrate all mandatory Phase 1 Stage 0–7 exit conditions and the complete Stage 3.1–3.9 research lifecycle through the existing application. Partial compiler, isolated module or mock-only demonstrations cannot substitute. [PRD 1.3/1.5/6.3–6.10]
- **FR-003**: Preserve the scientific-research lane, authorized inputs/resources, user/workspace/run attribution, evidence policy and explicit non-goals across the whole system. Deployment follows the supplied architecture while preserving user-scoped product identity and separate account/profile persistence. [PRD 1.1/2.1–2.12; D35]
- **FR-004**: Establish integrated frozen-contract, admission, authority, experimental pre-registration, baseline/treatment parity and evidence-before-release invariants. Scientific conclusions remain separate from infrastructure verdicts. [PRD 1.4/2.5/2.6/2.8; child TASK agreements]
- **FR-005**: Execute all ten PRD §4.2.9 acceptance/failure injections with actual advancement/block observations: valid artifact; schema violation without Tier 2; stale/swapped evidence; unsupported claim/citation; runtime budget violation (Tier 1 timeout evidence, no required semantic reviewer); prohibited tool/import; environment failure; allowed known limitation; valid scientific FAIL; durable gate locking. For case 4 only, M1-C001 authorizes Tier 1 rejection with Tier 2 NOT_RUN and unchanged fail/locking obligations. [PRD 4.2.9; QA 12.1; approved M1-C001]
- **FR-006**: Verify enforceable isolation and evidence/credential separation on the actual runtime, including confined POC/Builder identity, protected gate/referee assets, scoped client tokens and absence of authority bypass through sidecar/RSI/router. [PRD 2.9/4.4.9/4.4.10/5.4.3; D35/D44–D46]
- **FR-007**: Verify lifecycle and failure semantics across connected modules: durable history, immutable accepted artifacts, cancellation containment, no hidden retry/replay, no mid-run human wait, retained interrupted attempts and source-defined branch failure propagation. [PRD 2.7/2.10/4.6; D48–D50]
- **FR-008**: Assess all applicable Phase 2 and Phase 3 implementation commitments, including required Target 1 RSI, Model Routing, Planner/dynamic binding and conditional advanced compiler/alternate verifier/Code Mode seams. Report each implementation, integration and verification status separately with actual gaps. Non-blocking release status never authorizes silently omitting implementation. [PRD 1.3/1.5/6.11/6.12/6.14]
- **FR-009**: Target full bounded dynamic planning implementation/integration/verification: decomposition, graph generation/validation, admitted binding, governed execution, invalid-plan blocking and deterministic fallback availability. Static and planned requests retain explicit plan_source and the shared protected execution path. [PRD 4.8/6.12; architecture build-plan and run-plan]
- **FR-010**: Verify fixed baseline independence from router disabled/missing/error/timeout/invalid-choice/killed/hung states, absent RSI, empty/corrupt admission inbox and stopped sidecar. With Codex available, these cases preserve the frozen plan and CC pins. Verify the hot-path import boundary. [Architecture 3-build-plan.md Non-blocking test; reference/import-boundary.md]
- **FR-011**: Verify the supported operational research journey across all twenty PRD user stories using the native application surfaces; do not treat UI progress events as acceptance authority. The owning child specs define individual surface requirements. [PRD 1.11/5; M1-003/004/006]
- **FR-012**: Verify the four requested Docker QA cases against their frozen inputs and independent expectations, reporting implementation/execution status, actual assertions, evidence and gaps per case. These prove integration readiness only and do not replace Phase 1 acceptance or claim routing savings/RSI improvement. [QA implementation prompt; M1-QA]
- **FR-013**: Deliver reproducible Docker build/start/test/export/cleanup and automated QA entry points, with actual image/configuration/hardware/resource identity and explicit x86-64, ARM64 and native-DGX qualification distinctions. [Invoked prompt Final Verification; QA environment]
- **FR-014**: Produce the named phase completion, M1 implementation and final test reports from authoritative native records and raw evidence. Keep Phase 1 release/demo result separate from advanced implementation coverage, targeted verification, four-case QA status and remaining mandatory/non-blocking gaps. Reports are derived deliverables, never parallel work or acceptance authorities. [PRD 1.3/6.2.1/6.14; SOP v2]
- **FR-015**: Complete source-to-AC allocation, record source-backed exclusions/conditional scope, preserve stable Change Record/IF identities in TASK authorities and retain failed/stale/unrun evidence. Only current required PASS evidence permits completion. [PRD 1.6–1.11/6.2.2/6.13; constitution; SOP v2]

### Key Entities
Integrated candidate manifest; source/contract/fixture/profile pins; mandatory phase/stage exits; system journey; scientific and infrastructure outcomes; gate ordering evidence; advanced-capability status; four-case QA result; derived completion report. Child TASKs remain the sole owners of their product interfaces and block acceptance.

## Success Criteria

### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| M1-SYSTEM/AC-001 | PRD 1.5/6.14; FR-001, FR-002; US1; Story 1 (including applicable boundary/failure scenarios) | One exact integrated candidate passes every mandatory Phase 1 Stage 0–7 exit and completes Ingestion through Delivery with required child evidence current | SYSTEM |
| M1-SYSTEM/AC-002 | PRD 1.4/2.5; FR-002, FR-004; US1; Story 1 (including applicable boundary/failure scenarios) | A real scientifically positive and a real scientifically negative but admissible experiment both reach Delivery with frozen protocol and traceable measurements | SYSTEM |
| M1-SYSTEM/AC-003 | PRD 4.2.9, QA 12.1; FR-005; US2; Story 2 (including applicable boundary/failure scenarios) | All ten required evaluator cases execute their assertions and actual scheduler effects; case 4 carries approved Tier 1 FAIL/Tier 2 NOT_RUN deviation, without relabeling original Tier 2 coverage | SYSTEM |
| M1-SYSTEM/AC-004 | PRD 1.4/2.6/2.8; FR-004, FR-007; US2; Story 2 (including applicable boundary/failure scenarios) | No successor starts before all required predecessor decisions/evidence persist; invalid/missing/stale/swapped authority or evidence never releases work | SYSTEM |
| M1-SYSTEM/AC-005 | PRD 2.3/2.4/2.9/5.4.3; FR-003, FR-006; Story 1 (including applicable boundary/failure scenarios) | Actual unauthorized access/effect attempts are denied by the integrated boundary; required identity/resource/credential separation and permitted access both demonstrated | SYSTEM |
| M1-SYSTEM/AC-006 | PRD 4.6; D49/D50; FR-007; Story 2 (including applicable boundary/failure scenarios) | Cancellation, disconnect and restart retain evidence without implicit replay; failed-node dependents skip while independent branches continue; no post-intake human wait | SYSTEM |
| M1-SYSTEM/AC-007 | PRD 6.12; FR-008, FR-009; US3; Story 3 (including applicable boundary/failure scenarios) | Static and planned requests exercise the same protected execution mechanism; valid planning reaches its declared end and invalid planning is blocked; actual targeted result is reported, with all gaps explicit | SYSTEM |
| M1-SYSTEM/AC-008 | Architecture build-plan Non-blocking test; FR-010; US3; Story 3 (including applicable boundary/failure scenarios) | Every named side-system absence/failure condition is exercised with Codex available and preserves frozen plan/CC pins; import-boundary positive and planted-negative checks demonstrate enforcement | SYSTEM |
| M1-SYSTEM/AC-009 | PRD 1.11/5; FR-011; Story 1 (including applicable boundary/failure scenarios) | US01–US20 map to owning child ACs and integrated observations; accepted results, failed runs, saved history, limits, future defaults and authorized deletion are inspectable without rerunning research | SYSTEM |
| M1-SYSTEM/AC-010 | QA Scope/Acceptance; FR-012; US3; Story 3 (including applicable boundary/failure scenarios) | Each of CC, verifier, routing and RSI cases reports real Docker execution assertions and evidence; mocks/skips/missing resources remain incomplete and distinct from achieved integration | SYSTEM |
| M1-SYSTEM/AC-011 | Invoked prompt; FR-013; Story 1 (including applicable boundary/failure scenarios) | Actual build identities and executed supported-platform commands are reproducible; ARM64 emulation and native GB10 results are separately stated, with missing native qualification unclaimed | SYSTEM |
| M1-SYSTEM/AC-012 | PRD 6.14; FR-008, FR-014; US3; Story 3 (including applicable boundary/failure scenarios) | phase_1_completion_report.md, phase_2_completion_report.md, phase_3_completion_report.md, m1_implementation_report.md and m1_final_test_report.md (canonical lowercase names from the glossary for the corresponding PRD report labels) derive their statuses from current evidence and separately identify core release, advanced coverage and remaining gaps | SYSTEM |
| M1-SYSTEM/AC-013 | PRD 1.10/1.11/6.2.2; FR-001, FR-015; Story 3 (including applicable boundary/failure scenarios) | Every in-scope clause/story has an owning AC and current evidence link, exclusions have source basis, approved amendments are propagated, and no stale/unrun/blocked check is counted as PASS | SYSTEM |
| M1-SYSTEM/AC-014 | PRD 1.5/6.14; FR-008, FR-012, FR-014; Story 3 (including applicable boundary/failure scenarios) | Core M1 release/demo is declared PASS only from mandatory Phase 1 evidence; a separate full-delivery conclusion retains incomplete advanced or requested QA work instead of declaring all work complete | SYSTEM |
| M1-SYSTEM/AC-015 | PRD 2.1–2.12; FR-003; Story 1 (including applicable boundary/failure scenarios) | Complete journeys retain user/workspace/run identity and permitted resource provenance; out-of-lane requests, undeclared dataset/repository/network access and prohibited autonomous behavior are rejected without expanding Phase 1 scope | SYSTEM |

## Scope and Assumptions

- Canonical consumed agreements: [M1-IF-001](../M1-001/TASK.md#4-embedded-cross-module-agreements) (r1, source-bound in the owning TASK), [M1-IF-002](../M1-002/TASK.md#4-embedded-cross-module-agreements) (r2, source-bound in the owning TASK), [M1-IF-003](../M1-002/TASK.md#4-embedded-cross-module-agreements) (r1, source-bound in the owning TASK), [M1-IF-004](../M1-003/TASK.md#4-embedded-cross-module-agreements) (r1, source-bound in the owning TASK), [M1-IF-005](../M1-004/TASK.md#4-embedded-cross-module-agreements) (r1, source-bound in the owning TASK), [M1-IF-006](../M1-005/TASK.md#4-embedded-cross-module-agreements) (r1, source-bound in the owning TASK), [M1-IF-007](../M1-006/TASK.md#4-embedded-cross-module-agreements) (r1, source-bound in the owning TASK), [M1-IF-008](../M1-007/TASK.md#4-embedded-cross-module-agreements) (r1, source-bound in the owning TASK), [M1-IF-009](../M1-008/TASK.md#4-embedded-cross-module-agreements) (r2, source-bound in the owning TASK), [M1-IF-010](../M1-QA/TASK.md#4-embedded-cross-module-agreements) (r1, source-bound in the owning TASK). These are explicit definition prerequisites for dependent planning, not assumed published contracts.
- Included: system acceptance of the complete supplied M1 request, source coverage and derived reporting. Child TASKs own implementation and their ACs; this spec owns the connected journeys and candidate-level conclusion.
- Consumed agreements: the canonical product and QA interfaces reserved in TASKS; exact revisions must be established by the owning TASK before dependent planning. No duplicate product contracts are created here.
- Permitted models: qualified configured routes under source policy, fixed Codex for the Phase 1 baseline. Requested gpt-6.1-sol, effective identity and any unavailability remain distinct; no substitute is relabeled.
- Exclusions: Future State requirements stay excluded where the PRD expressly marks them; complete statistical S07–S10 campaigns are not added by four-case QA scope. Phase 2/3 implementation remains included; their deferred release gates do not exclude code delivery.
- Runtime prerequisites: real model access, dedicated Builder credential, ready isolated execution, baseline/validation resources, protected independent oracles and adequate Docker/native hardware. Missing prerequisites constrain affected checks and cannot be waived by this spec.
- Hardware: current AMD64 WSL execution is development evidence. Required ARM64 builds/execution and native GB10/DGX Spark qualification must retain their actual status. No Huawei baseline qualification is inferred.
- Current candidate is NOT_BUILT. System acceptance and final Analyze/Converge outcomes remain NOT_RUN until their ordered workflow stages and actual verification execute.

## Clarifications

### Session 2026-10-16
- Q: May unsupported citations fail at Tier 1 instead of the original PRD/QA Tier 2 expectation? → A: The user approved Tier 1 rejection and an explicit QA deviation; Tier 2 is NOT_RUN and downstream locking remains mandatory. Registered M1-C001.
- Q: How is a benchmark run with no valid metric represented? → A: The user requires a row for every run with explicit missing-metric status and reason. Registered M1-C002; no value may be invented.
- Workflow steering: complete Specify, then Clarify, Checklist, Plan, Tasks, read-only Analyze/corrections, Implement/verify, Converge in that order across the registered M1 scope. Independent source review supports Specify; it is not downstream phase completion.

- Source-resolved M1-I010 (Exact acceptance population and canonical names): PRD4.2.9 case5 is runtime budget violation, with Tier1 timeout evidence and no required semantic reviewer; verifier timeout is additional coverage, not a replacement. Internal report filenames follow the lowercase glossary crosswalk. Retain source-specific artifact/declaration identity checking without introducing an active interface_hash. Source: PRD4.2.9; glossary.md Artifact crosswalk; D23/D34.

- C006/C007 consumer clarification (2026-10-16): consume canonical M1-IF-009@r2 without restating it. New RSI observations/admission/QA/system evidence must preserve fractional mean-score totals, integer independent-fixture paired counts, every started proposed/rejected attempt, required rejected-attempt reason/failure support and proposed-only final selection. Versioned signatures, exact original bytes and all unchanged custody/qualification/activation constraints remain binding. Explicit v1 is historical decoding, never a substitute for current v2 proof.

C008 consumer revision alignment (2026-10-16): consume canonical M1-IF-002@r2 from M1-002/TASK.md. Library entry/snapshot aggregate limits include work plus independently budgeted checking; unchanged worker declaration/body limits do not pool verifier authority. Exact frozen parent/check pins remain binding for isolated RSI and QA/system evidence. IF009r2/C006/C007 and all existing work/AC/V IDs remain unchanged. Preserve prior progress and frozen evidence identities; revalidate affected current evidence against the new dependency revision.


## M1-C019 integrated user journey acceptance

Current authority/allocation: TASKS/TASK C019. Existing AC identities remain; additional scoped ACs:

- AC-C019-01: Native submission invokes actual Intent then Requirements, accepted-only bindings, and exposes accepted research_brief.json.
- AC-C019-02: Accepted Brief, eligible library and resources feed bounded Planner; checked/verified/gated frozen DAG alone releases research work.
- AC-C019-03: Search, Screening, Hypothesis, Builder/Benchmark, Evaluation and Delivery use the shared runner/check/verifier/gate/scheduler; rejection blocks successors; scientific results derive from actual execution.
- AC-C019-04: All model calls, including Planner/verifiers, consume frozen routing with actual GPT-6.1 Sol provenance. Missing resources block explicitly.
- AC-C019-05: Native bilingual chat exposes durable progress, readable rejection reasons, accepted outputs and report/evidence; ordinary conversation remains usable.
- AC-C019-06: Explicit repeatable initialization captures actual resources and source-defined defaults and installs exact eligible assets; ordinary startup never fabricates admissions/policy.


## M1-C020 declaration/output-only verification

AC-C020-01: Semantic assessor payload has exactly subject_declaration and subject_output. Neither fixed instructions nor payload may contain separately supplied user/upstream input contents, producer history, runtime/policy/manifests, or resolved contents of output-carried references. Exact output content remains unchanged. AC-C020-02: Declaration/output criteria assess semantic/structural conformance and coherence; host-only identity/source/runtime checks and protected gates remain enforced. Input-aware comparison is deferred and not a fallback.

### C022 current delivery boundary

The current user requires a functional connected local-development build before any further agent-run audit/test/experiment/qualification campaign. Consume owning M1-IF-014 r3: exact shipped built-ins can be explicitly authorized locally with qualification_status NOT_RUN, while normal strict independent qualification remains separate. All actual user-run deterministic checks, declaration/output-only Capsule verifiers, mechanical assessment checks and protected gates remain required functional behavior.

Existing system ACs and their identities are preserved. A produced image or local operator permission satisfies no unexecuted system/scientific/security/hardware assertion. Current skipped qualification and verification procedures remain NOT_RUN under C022, with historical failed/blocked/cancelled and genuine qualified records retained. Keep the four benchmark cases implemented; no additional case execution is authorized by this amendment.


### M1-SYSTEM/AC-C023 ? usable PDF-only summary
Consume M1-IF-017@r1 and C023 scope allocation. The supplied text-layer PDF and plain-language summary request must follow the real native upload/chat ? Compiler ? paper Planner ? paper_summary ? paper_delivery chain. Every output must pass mandatory deterministic checks, an independent declaration/output-only Capsule verifier, mechanical assessment checks and gate commit. The original chat must receive a nonempty report covering problem/method/results/contributions/limitations with checked PDF-page citations; refresh/history/export must retain accepted refs and original request/files. No scientific measurement or PDF-only capability is fabricated from the POC demo. Reject missing/unreadable sources and invalid source/page/quote references. Existing POC obligations remain. Component ownership is allocated by TASKS/C023; full-chain acceptance belongs to SYSTEM and is NOT_RUN until observed.


### M1-SYSTEM/AC-C024 and AC-C025
C024: The explicitly selected normal POC profile must resolve its exact prepared Python baseline/data/environment and admit a real native request. An accepted result requires actual baseline-first three repeats per role with seed42, frozen accuracy measurement/success/falsification rules, original per-run stdout/stderr/metric receipts, Evaluation and accepted same-chat Delivery. Missing/failed measurements remain explicit and cannot yield fabricated improvement. This is one positive local educational experiment, not general POC/M1 qualification. C025: Diagnose the exact latest failed uploaded-PDF request on5174, preserve its original failure, correct only the observed defect and return accepted original-source summary through mandatory guards on a fresh authorized request. Never substitute an unrelated successful run as its outcome. Existing C023 originals remain intact.


### M1-SYSTEM/AC-C026
An accepted paper report presents its five prose sections and compact PDF-page citations without dumping exact source quotations or internal citation IDs. Complete exact source quotations/spans remain in accepted downloadable structured evidence. Unaccepted summaries still cannot produce accepted reports. Historical accepted reports retain original bytes/refs. Mandatory declaration/output-only semantic checks and deterministic source/render/manifest/gates remain.

### AC-C027 - external blind dataset readiness
Fresh5175 has no old conversation/upload/result or built-in fixed dataset, proposed classifier or expected score. Imported public training data and unlabeled test features are the only dataset content available to model/generated work; independently supplied holdout labels stay root-only. Generated metric claims cannot be accepted: successful measured accuracy comes from pinned trusted post-exit scoring over exact predictions and hidden labels, with original receipts/host checks/gates. Failed or inconclusive improvement remains deliverable under the existing rules. Missing independent data prevents scientific readiness honestly. Historical runs/results remain unchanged and existing5173/5174 stay available. No unseen-data scientific success is asserted before the user independently runs it.
