# AI4Research PRD - Condensed M1 Testing Edition

**Purpose:** A shortened, test-oriented version of the October 8, 2026 AI4Research PRD. It preserves the original section/feature headings, M1 phase model, essential outputs, security/gate constraints, and implementation order, but omits many low-level examples, exhaustive conditions, and detailed implementation notes.

**Authority:** This is an abridged test input, **not a replacement** for the canonical full PRD, Architecture Design Set, M1 Test Specification, or applicable Spec Kit artifacts. Any omitted detail remains governed by those source artifacts.

**Intention Compiler clarification:** The Phase 1 compiler is bounded and non-interactive, not limited to one LLM call. Architecture Design determines its internal call structure; the validated `Research_Brief.json` contract is unchanged.

## Table of Contents & Implementation Order

**1. Overview & M1 Objectives**
**2. Domain Policy & Restrictions**

**3. Workflow Features (The Main Pipeline)**
*   **3.0 Codex CLI Integration (Priority Unblocker):** Check, refactor, and finalize the existing CLI adapter connection to OpenJiuwen to ensure pipeline testing is unblocked via the active subscription (bypassing API key requirements).
*   **3.1 Ingestion**
*   **3.2 Requirement Compilation**
*   **3.3 Search & Ideation**
*   **3.4 Idea Screening**
*   **3.5 Hypothesis Generation**
*   **3.6 POC Implementation (Builder)**
*   **3.7 Scientific Benchmarking**
*   **3.8 Scientific Evaluation**
*   **3.9 Delivery (Report Generation)**

**4. Foundation Features (The Engine)**
*   4.1 Capability Capsule
*   4.2 Evaluator Gate & Verifier
*   4.3 Foundational Models & Routing
*   4.4 RSI Integration
*   4.5 Data Foundations
*   4.6 Harness Core
*   4.8 Planner 
*   4.9 Builder

**5. Vertical Features (The Platform Shell)**
*   5.1 Visibility & Statistics (Telemetry)
*   5.2 Installer & CLI & Webapp
*   5.3 UI
*   5.4 Account Management
*   5.5 Message Channels
*   5.6 System Configurations (`config.yaml`)

**6. M1 Implementation Order & Integration Plan**

## 1. Overview & M1 Objectives

### 1.1 Product Overview

AI4Research is a user-scoped scientific research system on JiuwenSwarm. Phase 1 uses a fixed, gated SwarmFlow research workflow; Phase 3 evaluates dynamic Agent Team / Cluster Mode while preserving that baseline.
- **Runtime contract:** Every governed node has a run-specific Node Execution Contract and one or more admitted, version-pinned Capability Capsules.
- **Evidence gate:** Nodes advance only after an advancing Evaluator Gate verdict is persisted.
- **Deployment:** User/account persistence may be cloud-backed, while authorized user-specific and untrusted execution may run locally.

### 1.2 M1 Product Goal

**M1 goal:** Deliver a reproducible, evidence-backed, gate-controlled scientific research baseline and attempt the governed dynamic integration defined for Phase 3.
- **Research loop:** Given a user baseline and objective, find a grounded idea, define a falsifiable hypothesis, build a bounded POC, compare baseline with treatment, evaluate, and deliver evidence-linked results.
- **Priorities:** Explicit contracts, independent verification, artifact provenance, scientific integrity, and fail-fast behavior.

### 1.3 M1 Delivery Phase Model

**Three delivery phases:** (1) governed research baseline, (2) local-isolated RSI validation, (3) dynamic system integration. Delivery Phases are project milestones, not SwarmFlow runtime phases; Implementation Stages are dependency-ordered milestones within them.

#### M1 Delivery Phase 1 — Governed Research Baseline

Required deterministic SwarmFlow research baseline: fixed stages 3.1-3.9, Codex route, capsules, gate, Builder, evidence persistence, and local interfaces. Exit after implementation Stages 0-7, gate tests, and `Phase_1_Completion_Report.md`.

#### M1 Delivery Phase 2 — Local-Isolated RSI Validation

Required local-isolated RSI validation: Target 1 code mutation, independent hidden evaluation, lineage, adversarial isolation tests, and human promotion/rollback. Exit after Stage 8 and `Phase_2_Completion_Report.md`.

#### M1 Delivery Phase 3 — Dynamic System Integration

Attempt expected dynamic Compiler/Planner, capability discovery, routing, alternate Verifier, and Code Mode in isolation. Preserve fallbacks; record each attempt as validated, blocked, or incomplete with `Phase_3_Completion_Report.md`.

### 1.4 Core Product Invariants

**Non-negotiable M1 properties:** gate-locked advancement, node contract-bound permissions, evidence before trust, pre-registered experiment thresholds, scientific failure as a valid result, and fail-fast preservation of failures.

#### Gate-Locked Advancement

No downstream governed node may start until an advancing Evaluator Gate decision has been durably recorded.

#### Runtime Contract-Bound Execution

Each governed node gets a frozen Node Execution Contract covering objectives, inputs, outputs, admitted capsule versions, limits, proof obligations, and permissions; it cannot expand capsule authority.

#### Evidence Before Trust

Accept execution claims only when supported by artifacts, traces, provenance, citations, tests, or other required evidence.

#### Pre-Registered Scientific Evaluation

Freeze experiment method, data, metrics, and success/falsification criteria before running the POC; do not revise after results.

#### Scientific Failure Is a Valid Research Outcome

A scientifically negative but properly executed result must reach Delivery; the infrastructure gate evaluates process integrity.

#### Fail Fast and Preserve Evidence

Block advancement on mandatory failures, preserve evidence, and prohibit hidden repair/retry loops in M1.

### 1.5 M1 Definition of Done

**Core M1 release/demo:** Required Phase 1 and Phase 2 acceptance conditions must pass; Phase 3 is expected work but individually blocked/incomplete capabilities do not automatically invalidate the core demo.
- **End-to-end outputs:** `Research_Brief.json` -> `Candidate_Set.json` -> `Opportunity_Card.json` -> `Hypothesis_Blueprint.json` -> `POC_Artifact_Bundle.zip` -> `Benchmark_Payload.json` -> `Evaluation_Verdict.json` -> final report and artifacts.
- **Must demonstrate:** Gate-controlled transitions, persisted reproducible evidence, rejection of invalid/stale/unsupported artifacts, and required RSI security/activation tests.

### 1.6 PRD and Architecture Ownership Boundary

**PRD owns what:** observable product behavior, outcomes, M1 scope, artifacts, handoffs, invariants, acceptance/failure criteria, and product-level sequencing.
- **Architecture Design owns how:** schemas, services/APIs, process and module boundaries, persistence and security implementations.
- **Verification owns tests:** fixtures, exact procedures, assertions, automation, and evidence traceable to PRD requirements.

### 1.7 Requirement Authority & Conflict Resolution

**Authority:** Product invariants and Definition of Done take precedence; global policy constrains feature requirements; Sections 3-5 define behavior; Section 6 defines sequence; Phase 3 cannot weaken the Phase 1 baseline.
- **Conflict rule:** PRD governs product outcomes; Architecture Design governs otherwise unspecified implementation details. Escalate any true product-vs-design conflict explicitly.

#### M1 Requirement Authority

Priority: Definition of Done/invariants, global policy, feature requirements, delivery/phase scope, then future context.

#### Interpretation Rule

Resolve ambiguity to preserve the higher-priority M1 requirements and more-specific compatible feature constraints.

#### PRD and Architecture Conflict Rule

PRD governs observable behavior; Architecture Design governs technical realization. Escalate real conflicts rather than silently change product behavior.

### 1.8 M1 Scope Label Convention

**Scope labels:** Whitelist = implementation scope for the stated M1 phase; Conditional = required only if its dependency is met; Blacklist = excluded from M1; Future State = non-acceptance context unless formally promoted.
- Phase 3 Whitelist work is expected but may be reported as `BLOCKED` / `INCOMPLETE` when dependencies prevent completion.

#### Whitelist — M1 Implementation Scope

In-scope capabilities for the stated phase; Phase 1/2 mandatory Whitelist items affect the core demo, while Phase 3 items are expected but may be explicitly blocked or incomplete.

#### Conditional M1 Scope

Required only after its named dependency/enabling condition has been satisfied.

#### Blacklist — Excluded from M1 Implementation

Not part of M1 unless explicitly promoted through approved scope change.

#### Future State

Product-direction context, not an automatic M1 implementation obligation.

### 1.9 M1 Feature Freeze & Delivery Target

**Feature freeze:** October 5, 2026. After the freeze, permit only agreed corrections/clarifications, requirement reconciliation, and verification improvements; new scope needs an explicit decision. **M1 target:** on or before October 31, 2026.

### 1.10 M1 Incremental Change & Canonical Documentation Control

Use attributable Change Records for post-baseline defects, design corrections, product corrections, and approved new scope. Update the canonical PRD, Architecture Design, relevant Spec Kit artifacts, implementation, and verification where affected.
- Do not implement unapproved changes, erase rejected changes, or leave contradictory canonical documentation.

#### Change Classification

Classify each issue as implementation defect, architecture correction, product correction, or new/expanded scope; update only the affected sources of truth.

#### Change Records

Each material change tracks trigger, classification, affected artifacts, intended behavior, owner/status, and validation evidence.

#### Canonical Documentation Rule

Update approved source documents after changes so implementation does not depend on replaying historical change logs.

#### Rejection, Supersession & Reversion

Retain rejected, superseded, and reverted changes in history; only explicitly approved records are actionable.

#### Specification Synchronization

Keep PRD, Architecture Design, Spec Kit, implementation, and verification consistent after approved behavior/design changes.

### 1.11 M1 User Story Traceability

Approved user stories describe the user-facing journey and map to the most specific PRD features. Features and verification evidence must remain traceable to the stories; stories do not replace Whitelist requirements.

#### M1 User Story Definitions & Mapping

| ID | User-facing acceptance need | PRD mapping |
| --- | --- | --- |
| US01 | Check that the workspace is ready. | 5.2.1, 5.2.2 |
| US02 | Submit a research question. | 3.1.1, 3.1.5 |
| US03 | Supply references and experimental resources. | 3.1.2, 3.1.5 |
| US04 | State my targets and limits. | 3.2.3–3.2.6 |
| US05 | Inspect the research brief. | 3.2.7, 5.3.1 |
| US06 | Review ideas and their supporting sources. | 3.3.5–3.3.6, 5.3.1 |
| US07 | Understand why an opportunity was selected. | 3.4.3–3.4.7, 5.3.1 |
| US08 | Inspect the hypothesis and test plan. | 3.5.2, 3.5.4–3.5.5, 5.3.1 |
| US09 | Obtain a proof of concept. | 3.6.2–3.6.5 |
| US10 | Compare the baseline and the proposed change. | 3.7.2–3.7.4 |
| US11 | Understand the scientific outcome. | 3.8.4–3.8.6, 3.9.2 |
| US12 | Monitor research progress. | 5.1.1, 5.3.1–5.3.2 |
| US13 | Inspect a halted run. | 5.1.2, 5.3.3 |
| US14 | Track enforceable research limits. | 5.1.3, 5.6.3 |
| US15 | Read the final research report. | 3.9.2, 3.9.4 |
| US16 | Retrieve the experiment and its evidence. | 3.9.3–3.9.4 |
| US17 | Revisit a previous run. | 5.1.2, 5.3.1 |
| US18 | Set defaults for future research runs. | 5.6.2 |
| US19 | Keep execution within my authorized resources. | 5.4.2–5.4.3, 3.9.4 |
| US20 | Inspect and remove local research data. | 5.4.4 |

## 2. Domain Policy & Restrictions

### 2.1 Purpose

Global policies in Section 2 apply to all workflow, foundation, platform, and implementation requirements; feature-level rules may narrow but not weaken them.

### 2.2 M1 Domain Boundary

Phase 1 operates only in the Scientific Research lane: intake, research discovery, idea selection, hypothesis design, bounded POC, baseline/treatment benchmarking, scientific evaluation, and delivery. General-purpose autonomous engineering and unrelated workflows are excluded.

### 2.3 User and Deployment Boundary

Runs must be attributable to a user, workspace, and run identity. Permit hybrid cloud-backed account/profile state and authorized local execution for user assets, untrusted POC code, model bridges, and RSI. Multi-tenant enterprise/distributed execution is outside M1.

### 2.4 Input and External Evidence Policy

Allow supplied research text, local reference documents, approved code/data assets, and bounded academic retrieval. Disallow unconstrained web crawling, arbitrary repo cloning, undeclared downloads, fabricated evidence, or scope-expanding connectors.

### 2.5 Scientific Integrity Policy

Freeze hypothesis, baseline, validation data, metrics, procedures, and success/falsification thresholds before execution. Benchmarking measures; Scientific Evaluation interprets; the infrastructure gate checks admissibility. Do not move thresholds after seeing results.

### 2.6 Capability and Agent Boundary

All agent actions remain within the active Node Execution Contract and admitted Capability Capsule permissions. No undeclared tools/effects, unauthorized writes, contract changes, self-escalated permissions, fabricated execution, or gate bypass.

### 2.7 Workflow Autonomy Boundary

Phase 1 remains a fixed sequential workflow: no live DAG changes, hypothesis swarms, silent replanning, unbounded retries, or autonomous repair. Phase 3 dynamic behavior is isolated and must preserve fallback and governance.

### 2.8 Evaluation and Evidence Policy

Every governed node passes a two-tier Evaluator Gate: deterministic contract/security/evidence checks first; independent, read-only semantic verification second, only after mandatory deterministic checks pass.

### 2.9 Execution and Security Boundary

Treat generated code as untrusted. Confine reads/writes, network, tools, and process effects to authorized local boundaries; record violations as infrastructure failures. Architecture Design specifies exact isolation mechanisms.

### 2.10 Data and Traceability Boundary

Separate agent working memory from authoritative raw traces. Persist artifacts, benchmark logs, model routes, gate evidence, and run records under the appropriate run/stage/capability identity.

### 2.11 RSI Boundary

RSI runs outside the live workflow, mutates only explicitly allowed capsule implementation material, cannot access protected hidden fixtures or modify referee/security/promotion controls, and requires human admission/activation. Detected boundary violations halt RSI and preserve evidence.

### 2.12 M1 Global Non-Goals

M1 excludes ungoverned autonomous swarms, distributed execution, enterprise tenancy/billing, live RSI changes, automatic promotion, model training, external publication, dynamic evaluator generation, and autonomous self-repair. Only specifically approved Phase 3 dynamic work is excepted from the Phase 1 exclusions.

### 3.0 Codex CLI Integration (Priority Unblocker)

**Priority unblocker:** Reuse and stabilize the existing JiuwenSwarm <-> Codex CLI adapter to run the fixed pipeline with the active subscription, without depending on enterprise API keys. Keep the model route local and auditable.

#### 3.0.1 Existing Implementation Verification & Refactor

Verify/refactor the existing adapter, forward JiuwenSwarm model requests through authenticated local Codex CLI, return expected responses, and bind sessions to restricted Unix-socket/named-pipe IPC. No exposed TCP listener or new proxy built from scratch.

#### 3.0.2 Abstraction for "Endpoint of Last Resort"

Expose the existing adapter as a standard model-provider-style fallback, with timeout/auth-failure logs. Phase 1 keeps static Codex routing; heterogeneous routing is Phase 3 work.

### 3.1 Ingestion

Qualify raw user prompts and permitted local materials into a run-bound intake package for Requirement Compilation. Intake does not invent the research solution.

#### 3.1.1 Request Capture & Channel Signal Intake

Accept natural-language research requests through the CLI and native Web UI. Exclude external chat/voice channels in M1.

#### 3.1.2 User-Supplied Material & Execution Asset Import

Import `.txt`, `.md`, `.pdf` reference material and bind supplied project and validation assets to the run. Preserve document-vs-code-vs-data distinctions; no automatic external cloning/downloads.

#### 3.1.3 Intake Context Binding

Associate intake with the authorized user, session, workspace, and `run_id`; prevent implicit cross-run reuse.

#### 3.1.4 Real-Time Deduplication & Provenance Registration

Check basic file bounds and record paths, sizes, and timestamps in provenance/telemetry. No semantic document deduplication or document signing in M1.

#### 3.1.5 Intake Qualification

Reject empty requests and invalid/unreadable required resources with explicit errors. Produce a qualified prompt/document input buffer for Stage 3.2.

### 3.2 Requirement Compilation

**Fixed Phase 1 fallback:** A bounded, non-interactive compiler converts qualified intake into a validated `Research_Brief.json`; it does not depend on the external dynamic Intention Compiler. Internal LLM-call count and sequencing belong to Architecture Design. Interactive clarification and dynamic planning are Phase 3 capabilities.

#### 3.2.1 Intent Interpretation

Extract the research objective, desired change, and deliverable from qualified intake. Remain bounded/non-interactive; Architecture Design defines the internal model-call structure.

#### 3.2.2 Context Scoping

Capture user-supported `in_scope` and `out_of_scope` boundaries without external enrichment.

#### 3.2.3 Ambiguity Resolution

Apply conservative defaults to missing parameters and distinguish recorded system assumptions from user-provided values. No interactive Phase 1 clarification loop.

#### 3.2.4 Constraint Resolution

Extract user-declared hardware, time, compute, token, and other constraints. No autonomous host profiling.

#### 3.2.5 Requirement Prioritization

Classify user requirements into mandatory requirements and optional preferences.

#### 3.2.6 Acceptance Definition

Preserve measurable user targets and constraints in `Research_Brief.json`; Stage 3.5 later defines immutable experiment-specific falsifiability thresholds.

#### 3.2.7 Requirement Contract Confirmation

Emit schema-valid `Research_Brief.json` for gate review and fixed SwarmFlow dispatch. Phase 3 may also deliver the same contract to the dynamic Leader Agent; no mandatory asynchronous user approval in M1.

### 3.3 Search & Ideation

Retrieve and organize permitted evidence, then synthesize a small cited `Candidate_Set.json` for idea screening. Use admitted search capabilities and gate the output.

#### 3.3.1 Search Strategy Formation

Derive bounded static technical search queries from the Research Brief. No adaptive query rewriting in Phase 1.

#### 3.3.2 Multi-Source Signal Discovery (Hybrid Retrieval)

Retrieve from permitted local materials and bounded academic API connectors via admitted `deepsearch`; enforce a query result cap. No open-web crawling or search swarms.

#### 3.3.3 Source Qualification & Technical Signal Extraction

Extract evidence text and associated source references relevant to the search queries. No broad authority/bias profiling.

#### 3.3.4 Signal Organization & Trend Analysis

Group retrieved evidence by query into an organized signal set, without advanced trend analytics.

#### 3.3.5 Idea Generation

Synthesize 1-3 grounded candidate ideas; attach genuine citations rather than inventing unsupported novelty.

#### 3.3.6 Search Coverage Review & Result Compilation

Publish cited `Candidate_Set.json`; the Evaluator Gate checks evidence/schema/budget obligations before Stage 3.4.

### 3.4 Idea Identification / Screening / Opportunity Selection

Apply a fixed screening rubric to candidates, pick one feasible opportunity, and publish `Opportunity_Card.json`. This stage selects rather than invents new ideas.

#### 3.4.1 Candidate Consolidation

Merge near-duplicates without erasing meaningfully distinct candidate mechanisms.

#### 3.4.2 Idea Identification

Map each candidate to a technical problem and proposed mechanism, grounded in existing candidate evidence.

#### 3.4.3 Idea Card Formation

Create structured idea cards with identity, summary, citations, assumptions, and risks.

#### 3.4.4 Opportunity Definition

State each opportunity's concrete bottleneck and proposed mechanism, excluding commercial ROI analysis.

#### 3.4.5 Technical Opportunity Screening (Fixed-Rubric LLM Evaluation)

Score novelty, feasibility, and compute alignment from 1-5 with short grounded rationales; no voting swarms or preliminary code experiments.

#### 3.4.6 Strategic Opportunity Screening

Deterministically reject candidates with disallowed dependencies or other declared hard constraints.

#### 3.4.7 Opportunity Portfolio Prioritization

Rank by novelty + feasibility + compute alignment, select Top-1, preserve rejection reasons, and produce `Opportunity_Card.json`. No interactive M1 selection.

### 3.5 Generate Technical Claims & Hypothesis

Translate the selected opportunity into a falsifiable, immutable `Hypothesis_Blueprint.json` for Builder and Benchmarking.

#### 3.5.1 Research Question & Technical Claim Formation

Express one testable technical claim linked to the selected opportunity; no competing parallel hypotheses.

#### 3.5.2 Claim, Evidence, Data & Method Modeling (Benchmark Definition)

Define independent/dependent variables, an unchanged baseline, measurement method, and supplied/static validation data.

#### 3.5.3 Hypothesis Pool & Mechanism Formation

Specify the bounded intervention or mechanism that will be built; exclude iterative search/evolution here.

#### 3.5.4 Falsifiability Screening & Hypothesis Contracting (Anti-Overfitting Contract)

Pre-register success and falsification boundaries and permitted `INCONCLUSIVE`/conditional rules before code and empirical results. Never alter them post hoc.

#### 3.5.5 Verification-Ready POC Design

Publish `Hypothesis_Blueprint.json` with reproducible method, constraints, evaluation criteria, and build/test obligations. Subsequent stages may read but not rewrite it.

### 3.6 POC Implementation

Stage 3.6 uses `poc_capsule.md` plus the specialized Builder within the Node Execution Contract to create a minimal benchmark-ready `POC_Artifact_Bundle.zip`. The stage constructs code; Stage 3.7 executes the experiment.

#### 3.6.1 POC Implementation Environment Preparation

Prepare authorized isolated POC workspace and declare frozen dependencies; do not dynamically install or change dependencies during construction.

#### 3.6.2 POC Construction (Code Generation)

Use permitted local CodeSearch; produce a bounded standalone `poc_patch.py` for the blueprint mechanism. No uncontrolled repository refactoring or system/network imports.

#### 3.6.3 POC Component Integration & Configuration

Produce `run_benchmark.py` to run the original baseline and treatment under the frozen protocol.

#### 3.6.4 POC Functional Readiness Validation

Perform mechanical syntax/readiness checks only; do not preview scientific outcomes or enter automatic repair loops.

#### 3.6.5 Testable POC Artifact Consolidation & Benchmark Handoff

Package patch, harness, pinned dependencies, and environment information in `POC_Artifact_Bundle.zip`; gate it before benchmarking.

### 3.7 Scientific Benchmarking (POC Execution)

Execute baseline and POC treatment under the pre-registered protocol in an authorized local sandbox. Return measurements and raw evidence, not a scientific conclusion.

#### 3.7.1 Runtime Provisioning & Artifact Unpacking

Unpack the POC bundle and provision unprivileged local execution using only the frozen dependency declaration; fail on unresolved setup problems.

#### 3.7.2 Delta Execution (Baseline vs. Treatment)

Run unmodified baseline followed by treatment on the same declared data, hardware configuration, measurement definitions, and seed policy.

#### 3.7.3 Empirical Data Collection

Capture stdout/stderr, execution traces, and requested metrics into `empirical_results.json` and durable Run Bundles.

#### 3.7.4 Results Consolidation & Handoff

Publish `Benchmark_Payload.json` with baseline/treatment measurements, differences, and evidence references; gate before scientific interpretation.

### 3.8 Scientific Evaluation

Interpret gate-admitted measurements against the immutable Hypothesis Blueprint and produce `Evaluation_Verdict.json`. A negative scientific outcome is not an infrastructure failure.

#### 3.8.1 Evaluation Scope & Evidence Assembly

Read `Benchmark_Payload.json`, frozen `Hypothesis_Blueprint.json`, and `Research_Brief.json`.

#### 3.8.2 Evidence Completeness & Provenance Review

Check measurement completeness and traceability to actual execution evidence; reject fabricated/unsupported values.

#### 3.8.3 Experimental, Reasoning & External Validity Review

Conduct bounded plausibility/reasoning review; no new empirical experiments or counterfactual benchmarks.

#### 3.8.4 Claim & Acceptance-Criteria Comparison

Compare measured deltas deterministically to the pre-registered experimental success and falsification conditions.

#### 3.8.5 Verdict, Blocker & Residual-Risk Classification

Classify scientific result as `PASS`, `FAIL`, `INCONCLUSIVE`, or pre-authorized `CONDITIONALLY_ACCEPTABLE`; give measurement-linked reasons. A valid scientific `FAIL` still proceeds to Delivery after infrastructure gate acceptance.

#### 3.8.6 Refinement & Follow-Up Recording

Record limitations and research follow-ups without patching code or rerunning nodes.

### 3.9 Delivery (Report Generation)

Prepare the final grounded research report and user deliverables from gate-admitted scientific verdicts and evidence.

#### 3.9.1 Delivery Planning & Evidence Handoff

Read verified verdict, benchmark payload, and original brief; use the agreed Markdown report template.

#### 3.9.2 User-Facing Deliverable Generation

Write a structured Markdown report with objective, hypothesis, methods, baseline-vs-treatment results, verdict, sources, and limitations. Do not misstate recommendations as measurements.

#### 3.9.3 Deliverable, Reusable Asset & Knowledge Packaging

Collect final report, POC scripts, environment, and empirical evidence into an authorized output package.

#### 3.9.4 Authorized Distribution, Knowledge Transfer & Lifecycle Closure

Deliver to the user's sandboxed workspace and supported local UI/TUI; persist the completion trace. No external messaging/publication.

## 4. Foundation Features (The Engine)

### 4.1 Capability Capsules

Capability Capsules are reusable admitted implementations, not nodes or contracts. A workflow node represents run-specific work; a Node Execution Contract binds the objective, outputs, limits, and exact capsule versions for that work.

#### 4.1.1 Capability Declaration & Assembly

Each admitted capsule exposes a machine-readable `capsule.json`, inspectable `make_capsule.md`, pinned implementation resources, version/provenance metadata, permissions, and governed mutation surface. Capsule model selection belongs to Routing.

#### 4.1.2 Governance, Admission, Versioning & Registry Management

Maintain an append-only capability/version registry, strict admission and self-tests, provisional M1 standing, reproducible pinned versions, and human activation/suspension/rollback. No automatic capsule promotion or remote imports.

#### 4.1.3 Node Capability Binding & Runtime Contract Assembly

Phase 1 binds a bounded static capability set and resolves version-pinned Node Execution Contracts before execution. Phase 3 may dynamically discover only admitted compatible capabilities; no live unadmitted installs.

#### 4.1.4 Invocation & Composition

The CC Runner executes bound capsules under contract constraints; record invocation provenance and behavior and assemble a node Stage Evidence Bundle for the two-tier gate. Enforce measured runtime limits and local sandbox boundaries.

#### 4.1.5 Capability Evolution (RSI Boundaries)

RSI may propose only explicitly authorized capsule implementation changes. Preserve interface, permissions, lineage, and frozen referee; admission and activation remain human-controlled.

### 4.2 Evaluator Gate & Verifier

The Evaluator Gate independently decides whether a governed node's evidence meets its run-specific contract and can release its successor. It is distinct from Stage 3.8 scientific judgment.
- **Tier 1:** Deterministic contract/schema, tool, budget, evidence, and security checks; mandatory failures stop without a verifier call.
- **Tier 2:** Read-only semantic Verifier for claim support, citations, reasoning, and applicable node criteria.

#### 4.2.1 Evaluation Evidence Envelope & Two-Tier Gate Execution

Submit a Stage Evidence Bundle tying run/node identity, contract and capsule versions, outputs, route/model/tool observations, budgets, logs, tests, citations, and side effects to the current execution. Run Tier 1 first, Tier 2 only if eligible, then persist verdict.

#### 4.2.2 Contract, Schema & Artifact Conformance Evaluator

Check schema, mandatory fields, artifact/contract identity, provenance, admitted capsule interfaces, and declared-versus-observed effects. Reject stale, swapped, wrong-type, or incomplete artifacts.

#### 4.2.3 Engineering Correctness & Code Quality Evaluator

Use required compile, smoke, unit/integration, or static checks when applicable. Mandatory engineering failures halt without evaluator-authored patches or retries.

#### 4.2.4 Performance, Cost & Benchmark Evaluator

Enforce measurable execution-time limits and invocation bounds; record available model usage. Verify benchmark structural/protocol evidence, but leave scientific interpretation to Stage 3.8. Do not invent token counts unavailable from Codex CLI.

#### 4.2.5 Security, Privacy, Compliance & IP Evaluator

Reject unauthorized tool/network/filesystem behavior, prohibited generated-code imports, permission escapes, or missing isolation evidence. Distinguish artifact violations (`FAIL`) from unavailable execution environments (`ENVIRONMENT_BLOCKED`).

#### 4.2.6 Evidence, Factuality & Scientific Validity Evaluator

The read-only Verifier checks citation/source binding, claim support, reasoning consistency, uncertainty, and evidence plausibility. It does not rewrite artifacts or replace Stage 3.8's scientific verdict.

#### 4.2.7 Lifecycle, Parity & Human Review Evaluator

Verify required node/gate lifecycle order and actual execution evidence. Preserve reasons and reviewer trace; blocked/ambiguous outcomes may escalate to `human_session`, never silently convert to pass.

#### 4.2.8 Verdict Aggregation & Orchestration Gate Policy

**Gate verdicts:** `PASS` or `PASS_WITH_KNOWN_LIMITATIONS` advance; `FAIL`, `ENVIRONMENT_BLOCKED`, and `INCONCLUSIVE` halt and preserve evidence (and may escalate to human review).
- Tier 1 mandatory failure => Tier 2 `NOT_RUN`; a valid Stage 3.8 scientific `FAIL` can still receive infrastructure `PASS`.
- Persist a machine-readable gate result including run/stage, tier statuses, verdict, action, reasons, warnings, and evidence references before advancing.

#### 4.2.9 M1 Evaluator Acceptance & Failure-Injection Tests

**Required acceptance/failure injection:** Demonstrate valid pass; schema fast-fail; swapped/stale artifact rejection; broken citation rejection; runtime-budget violation; forbidden tool/code rejection; environment block; non-blocking warning; valid negative scientific result reaching Delivery; and delayed gate preventing downstream start.

#### 4.2.10 Future State — Autonomous Multi-Faceted Evaluation via Auto Harness

**Future state only:** Dynamic evaluator selection, specialized reviewer ensembles, self-modifying evaluation, automated adversarial test generation, and gated repair loops are outside M1.

### 4.3 Foundational Models & Routing

Centralize model provisioning and usage auditing. Phase 1 uses the static Codex CLI fallback; Phase 3 may test isolated heterogeneous routing after approved model access without replacing the accepted baseline.

#### 4.3.1 Model Capability Registry

Register Codex CLI as the sole active Phase 1 endpoint; develop Phase 3 capability metadata/registry using mocks until other model endpoints and credentials are explicitly approved.

#### 4.3.2 Model Routing & Selection

Capsule choice comes from the DAG/Planner, not Router. Phase 1 routes to Codex; Phase 3 may test compatible dynamic routes in isolated, reversible configuration, with fallback intact.

#### 4.3.3 Model Usage Auditing

Associate each model call with run/node/role/capsule, route, outcome, and measured latency. Persist real usage data only when available and distinguish subscription allowance from per-call tokens. Do not add private telemetry labels to model prompts.

#### 4.3.4 AI Reviewer Agent (Routing Integration)

Provision Tier-2 `verifier_capsule.md` through the static Codex route. Phase 3 alternate reviewer experiments require approved access, isolation, and reversible fallback; reviewer cannot modify artifacts or advance the gate.

### 4.4 RSI (Recursive Self-Improvement) Integration

**M1 Phase 2 RSI:** A local-isolated, target-independent loop proposes and tests bounded capsule implementation changes under a frozen independent referee, with human-controlled admission/activation.
- **Target 1 (required):** Improve the pure `rank_opportunities` helper inside a sandbox copy of `screening_capsule` without changing production or its interface.
- **Target 2 (conditional):** Improve explicitly mutable `screening_capsule` text/rubric material only when a bounded headless model path is available.

#### 4.4.1 Text-Based Artifacts (GEPA / MIProV2 / TextGrad)

Conditional Target 2 may mutate only explicitly permitted work-capsule prompt/rubric implementation text. Preserve declared dimensions/interfaces; compare parent and child on the same permitted fixtures. Referee rubrics are never mutable.

#### 4.4.2 Runtime and Resource Routing (Bayesian Optimization / Bandits / Cost-Aware RL)

Record RSI elapsed time and invocation counts; time may break ties between candidates with equal tests passed. No optimization of routing, model selection, timeouts, or concurrency in M1.

#### 4.4.3 Capability Capsules and Physical Operators (Trajectory Mining / Code Evolution / CEGIS)

Required Target 1 mutates only sandbox `rank_opportunities` implementation; preserve Top-1 scoring interface/requirements and parent tests. Produce tested child and provenance evidence, not automatic production replacement. Keep loop core target-agnostic.

#### 4.4.4 DAG and Agent Organization (AFlow / MCTS / ADAS)

Treat live DAG/agent organization as read-only; use offline child replay and wiring compatibility checks. Whole-workflow architecture optimization is excluded.

#### 4.4.5 Evaluator, Reward, Contract, and Governance

Freeze evaluator, scoring, hidden suites, checks, and promotion policy throughout RSI. Require parent compatibility first, bound hidden-loop feedback, reserve final hidden evaluation for terminal assessment, and test attempted referee abuse.

#### 4.4.6 Memory, Retrieval, and Evidence (Memory Learning / Self-RAG / Reranker Training)

Preserve RSI attempt logs, candidate hashes/lineage, and provenance. Do not train product memory, RAG, or rerankers as part of M1 RSI.

#### 4.4.7 Model Policies and Weights (SFT / LoRA / DPO / GRPO / Agent RL)

RSI never trains/fine-tunes or changes model weights or Verifier routing. Parent/child comparisons use the same pinned model route and relevant runtime settings.

#### 4.4.8 Data, Benchmarks, Curriculum, and Observability (Active Learning / Hard-Case Mining / Credit Assignment)

Separate proposer-visible development data, protected hidden-loop tests, and protected hidden-final evaluation; freeze fixtures and prevent contamination. Log candidate attempts and scores; do not feed milestone tracking data back to RSI as optimization feedback.

#### 4.4.9 Local-Isolated RSI Sandbox & Hidden-Evaluation Isolation

Isolate RSI and candidates from the live workflow, protected referee, and hidden fixtures. Only approved, pinned, read-only public benchmark retrieval is allowed. Hidden evaluations reveal bounded aggregate results, not cases; cap access; require human activation and rollback.

#### 4.4.10 RSI Security Guardrails & Adversarial Validation

Run intentional adversarial tests for hidden-fixture leakage, referee tampering, out-of-scope mutation, permission/network escape, resource abuse, evidence manipulation, and promotion bypass. Every mandatory attack must be blocked and logged; detected violations halt RSI pending human review.

### 4.5 Data Foundations

Use JiuwenSwarm agent memory for reasoning context, and local append-only Run Bundles and records for authoritative raw evidence. Avoid M1 databases, vector stores, and distributed graphs.

#### 4.5.1 Persistent Memory & Context Retrieval (Agent Memory)

Use native Task/Coding Memory for compact reasoning context, not raw benchmark logs or large telemetry.

#### 4.5.2 TaskGraph Persistence & Run Bundles (System Memory)

Persist isolated `records/bundles/<run_id>/`, append-only `records.jsonl`, and an effective-run manifest for contracts, capsule/model/config versions, traces, outputs, gate results, and available usage metrics.

#### 4.5.3 Contract & Capability Conformance Observability

Compare admitted capsule declaration against observed tools/effects; export static JSON/Markdown scorecards. Represent unavailable token/cost metrics as unavailable.

#### 4.5.4 Sample Run Exports (Scaffolding for RSI Handoff)

Export reproducibly pinned run records to `records/exports/<export_id>/` for isolated RSI evaluation without writing offline results into the live workflow.

#### 4.5.5 Extended Graph Management (Future State Only)

**Future state only:** Distributed concept, dataset, code, policy, workflow, and trace knowledge graphs are excluded from M1.

### 4.6 Harness Core

The JiuwenSwarm Harness controls run identity, node lifecycle, local capsule dispatch, evidence capture, gate execution, and authorized next-node release.

#### 4.6.1 Runtime Control Loop & Run Lifecycle Management

Track `Pending -> Running -> Evaluating -> Completed/Failed` and persist run/node states through the fixed SwarmFlow execution path.

#### 4.6.2 DAG Scheduler & Operator Binding

Phase 1 follows the static sequential DAG and advances only on persisted `PASS`/`PASS_WITH_KNOWN_LIMITATIONS`. Phase 3 may add isolated dynamic planning without removing this path.

#### 4.6.3 Main Loop Dispatch & Runtime Supervision

Dispatch the local CC Runner, enforce timeouts, record stdout/stderr/artifacts/metrics, and send each Stage Evidence Bundle to the gate.

#### 4.6.4 Failure Recovery & Resumability

On failure, stop and record evidence; interactive runs may invoke `human_session`. Headless development/test runs must instead terminate with a stable non-zero machine-readable outcome, without bypassing gate policy. No autonomous repair loops.

#### 4.6.5 Distributed Infrastructure & Concurrency (Future State Only)

**Future state only:** Multi-host worker leasing, distributed message brokers, and execution-cluster scheduling are excluded.

### 4.8 Planner

Phase 1 uses the fixed SwarmFlow Default DAG without autonomous task decomposition. Phase 3 tests Leader Agent TaskGraph planning under existing contracts and fallback constraints.

#### 4.8.1 Task Contract Decomposition

Phase 1 work units are predetermined workflow stages. Phase 3 may decompose objectives into bounded tasks with a dynamic Leader Agent.

#### 4.8.2 TaskGraph Construction

Build the Phase 1 linear SwarmFlow script and inject `Research_Brief.json` parameters. Phase 3 may generate a bounded dynamic TaskGraph, preserving gate and contract semantics.

#### 4.8.3 TaskGraph Validation & Feasibility Analysis

Validate Phase 1 startup/dependencies mechanically. In Phase 3, validate dynamic task dependencies and capsule feasibility before dispatch; prohibit uncontrolled mid-flight replanning.

### 4.9 Builder

Builder is the specialized code/artifact construction function used by Stage 3.6, distinct from the generic CC Runner. It creates patch code, benchmark harness, frozen requirements, and the POC bundle; it does not own scientific/analytical outputs.

#### 4.9.1 Build Contract Interpretation & Preparation (Sub-features 1 & 2)

Consume frozen `Hypothesis_Blueprint.json`, prepare isolated POC workspace, and check required inputs. Phase 3 may evaluate Code Mode tooling in isolation.

#### 4.9.2 Code & Experimental Asset Construction (Sub-features 3, 5, 6, & 7)

Construct single-file `poc_patch.py` and baseline/treatment `run_benchmark.py` with declared safe effects. No uncontrolled multi-file refactoring, model training, or prohibited imports.

#### 4.9.3 Analytical Deliverable Boundary

Do not regenerate or modify analytical products owned by Stages 3.4 (`Opportunity_Card.json`), 3.5 (`Hypothesis_Blueprint.json`), 3.8 (`Evaluation_Verdict.json`), or 3.9 (`research_report.md`).

#### 4.9.4 Prototype Assembly & Build Evidence Generation (Sub-features 9 & 12)

Run mechanical compile checks and package patch, benchmark harness, requirements, and necessary manifests as `POC_Artifact_Bundle.zip`.

#### 4.9.5 Excluded Capabilities & Advanced Lifecycle Features (Sub-features 4, 10, 11, & 14)

**Excluded:** Model training/fine-tuning, autonomous defect-repair loops, arbitrary service deployment, and unbounded production product integration.

## 5. Vertical Features (The Platform Shell)

### 5.1 Visibility & Statistics (Telemetry)

Expose current execution and historical evidence through native JiuwenSwarm tools and static files, not a custom M1 telemetry platform.

#### 5.1.1 Workflow & Platform Status Visibility

Use `/swarmflows` and CLI/native Web UI to display run ID, node/gate status, current stage, halts, and completed-run evidence references.

#### 5.1.2 Execution Trace Search & Inspection

Inspect saved read-only `records.jsonl` and Run Bundles; provide static per-capsule pass/failure scorecards. No interactive large-scale trace-search engine.

#### 5.1.3 Resource Usage, Cost & Capacity Management

Enforce observable duration/invocation budgets, record available model usage, and retain limits and measurements in run evidence. Token/cost data may be unavailable on Codex CLI and is not inferred.

#### 5.1.4 Runtime Status Visibility

**Excluded for M1:** Continuous host CPU/GPU/RAM monitoring. Record static host/OS/hardware facts once at run start.

### 5.2 Installer & CLI & Webapp

Bootstrap the workstation through Python packaging and local services. Use native CLI/Web/TUI rather than building standalone desktop distributions.

#### 5.2.1 CLI Installation & Workstation Initialization (MacOS & Linux - Sub-features 3 & 4)

Use `pip install jiuwenswarm` and `jiuwenswarm-start`. Initialize input/POC/evidence/RSI workspaces, pinned capsule registry, secure hidden fixtures, `config.yaml`, and authenticated adapter. Doctor checks must block runs if mandatory dependencies are unavailable.

#### 5.2.2 Web Application & Status Service (Sub-feature 5)

Start native Web UI locally on `127.0.0.1:5173` with ephemeral local authentication. Support prompt intake, run/gate monitoring, and final report rendering. No public/multi-tenant web service in M1.

#### 5.2.3 Native Desktop Applications (Windows & MacOS - Sub-features 1 & 2)

**Excluded for M1:** Native `.exe`/`.dmg` desktop apps, installers, update channels, and custom setup wizards.

### 5.3 UI

Rely on supported JiuwenSwarm CLI, native Web UI, and TUI with minimal branding. The interfaces expose intake, status, artifacts, and human triage without redefining gate policy.

#### 5.3.1 Command-Line Interface (CLI)

Support command-line research intake and run-artifact inspection. Headless test runs must accept explicit configuration/seed where available and return run ID, bundle reference, and stable success/failure/block status without interactive prompts.

#### 5.3.2 Web Graphical User Interface (GUI)

Use locally bound native Web UI for prompt intake, run-tree monitoring, final Markdown report reading, and light branding. No custom workflow editor or mid-run contract changes.

#### 5.3.3 Terminal User Interface (TUI)

Expose native `jiuwenswarm-tui` to inspect failures and invoke authorized human review/abort actions. Preserve the failed attempt; no autonomous correction.

### 5.4 Account Management & Local Security Controls

Maintain stable user-scoped account identity distinct from the local execution OS account, with authorized workspace/run binding and local execution security. Account/profile persistence may be cloud-backed; architecture owns the technical implementation.

#### 5.4.1 Account Registration & User Profile Management (Sub-features 1 & 3)

Preserve stable user identity/profile state across runs; bind each local execution to user, workspace, and `run_id`. Store machine-specific execution preferences separately from durable account data.

#### 5.4.2 Authentication & Local Web Security (Sub-feature 2)

Bind local web API to loopback and require ephemeral restricted session-token authentication; reject external/LAN web bindings. No enterprise SSO in M1.

#### 5.4.3 Runtime Sandboxing & Process Isolation (Security Boundary)

Run untrusted POC code as a restricted user within authorized POC paths; secure Codex bridge through local permission-protected IPC; ensure SwarmFlow runner cannot read RSI hidden fixture storage.

#### 5.4.4 Privacy & Personal Data Controls (Sub-feature 4)

Allow local project assets, outputs, and traces to be inspected/removed. Keep local research data distinct from any separately persisted product account/profile state.

### 5.5 Message Channels

Keep all M1 workflow communication and monitoring on authorized local surfaces; external messaging connectors remain disabled.

#### 5.5.1 TMUX Session & Terminal Surface Management (Sub-feature 3)

Use local `tmux` panes/sessions for managed background processes and developer inspection of runtime logs; no remote terminal synchronization.

#### 5.5.2 External Messaging Integrations: WeChat & Discord (Sub-features 1 & 2)

**Excluded for M1:** WeChat, Discord, Slack, Feishu bots, webhooks, notifications, or external content intake.

### 5.6 System Configurations (`config.yaml`)

Use declarative `config.yaml` to govern local defaults, model endpoints, budgets, and approved test profiles. Freeze and record the effective configuration at run start.

#### 5.6.1 LLM Configuration (Sub-feature 1)

Set Codex CLI as the static Phase 1 model route and role aliases. Phase 3 experimental model profiles require approved access and must remain isolated from baseline routing.

#### 5.6.2 User Settings (Sub-feature 2)

Configure workspace paths, supported file extensions, hardware defaults, and precedence (local project settings override global defaults).

#### 5.6.3 Cost & Budget Settings (Sub-feature 3)

Enforce configured time and invocation limits; treat token/cost ceilings as enforceable only with reliable per-call usage telemetry. No automatic monetary rerouting.

#### 5.6.4 Cluster Settings (Sub-feature 4)

**Excluded for M1:** Multi-host execution clusters, remote worker leasing, and cluster heartbeats. Research execution uses one authorized local host.

#### 5.6.5 Development & Evaluation Run Configuration

Support explicit, reproducible development/evaluation profiles and controlled ablation. Freeze actual capsule/model/gate/seed settings per run. A gate-disabled ablation cannot count as a valid Phase 1 product run.

## 6. M1 Implementation Order & Integration Plan

### 6.1 Purpose

This section defines the dependency-ordered integration plan, not runtime DAG ordering. Detailed interfaces, schemas, and service topology remain Architecture Design work.

### 6.2 Implementation Principle

Implement incremental runnable and testable integration boundaries. A stage is complete only when its upstream contracts, admitted capsules, run evidence, gate verdict, Harness behavior, and Stage Exit Condition are demonstrated.

### 6.2.1 M1 Validation & Verification Governance

Verification must demonstrate PRD acceptance and failure requirements with reproducible evidence. The separate M1 Test Specification owns fixtures, cases, assertions, and procedures; approved user stories remain traceable through test evidence.

#### Implementation Stage Validation

For each stage, report requirement/exit-condition coverage, tests and evidence, and `PASS`/`FAIL`/`BLOCKED`/`INCOMPLETE` status; code alone is not completion.

#### Delivery Phase Validation

Each Phase completion report summarizes validated requirements, blockers, limitations, and links to stage/test evidence.

#### Final M1 Validation

Produce `M1_Final_Test_Report.md` consolidating M1 requirement/user-story coverage, gate/failure tests, phase results, open gaps, and evidence links.

### 6.2.2 Incremental Change Implementation Protocol

Treat follow-on corrections as approved, scoped Change Records: load canonical documents, classify the change, update PRD/Architecture/Spec Kit where needed, implement only approved changes, run regression verification, and preserve final consistency and history.

### 6.3 Implementation Stage 0 — Runtime Unblocker & Local Configuration

**Stage 0 | Primary:** 3.0, 5.4, 5.6. Stabilize secure local Codex CLI IPC and minimum configuration/workspace/runtime security.
- **Exit:** JiuwenSwarm successfully issues a bounded model call through the configured authenticated adapter.

### 6.4 Implementation Stage 1 — Core Governed Execution Backbone

**Stage 1 | Primary:** 4.1, 4.3, 4.5, 4.6, 4.2. Build capsule admission -> static model route -> evidence persistence -> CC Runner/Harness -> two-tier gate.
- **Exit:** `Node A -> Gate -> Node B`: valid output advances; invalid output blocks and persists evidence. Headless test failure exits non-interactively with a stable machine-readable result.

### 6.5 Implementation Stage 2 — Intake, Requirement Contract & Static DAG

**Stage 2 | Primary:** 3.1, 3.2, 4.7, 4.8. Accept authorized intake, compile validated `Research_Brief.json`, and load fixed SwarmFlow DAG with gate and capsule bindings.
- **Exit:** A user request initializes the fixed DAG without autonomous planning.

### 6.6 Implementation Stage 3 — Evidence-to-Hypothesis Research Path

**Stage 3 | Primary:** 3.3-3.5. Integrate Search/Ideation -> Gate -> Screening -> Gate -> Hypothesis -> Gate.
- **Exit:** Produce evidence-linked `Candidate_Set.json`, `Opportunity_Card.json`, and immutable `Hypothesis_Blueprint.json` from a valid brief.

### 6.7 Implementation Stage 4 — Builder & POC Assembly

**Stage 4 | Primary:** 3.6, 4.9. Build bounded code and benchmark harness from the frozen blueprint; mechanically validate and gate `POC_Artifact_Bundle.zip`.
- **Exit:** Valid POC bundle is ready for benchmark, without autonomous repair.

### 6.8 Implementation Stage 5 — Benchmarking & Scientific Evaluation

**Stage 5 | Primary:** 3.7, 3.8. Execute baseline/treatment, gate benchmark evidence, produce scientific verdict, and gate scientific output.
- **Exit:** Both valid positive and valid negative scientific results route correctly, producing `Benchmark_Payload.json` and `Evaluation_Verdict.json`.

### 6.9 Implementation Stage 6 — Delivery & End-to-End Research Run

**Stage 6 | Primary:** 3.9. Produce and deliver evidence-grounded Markdown report and artifacts, and close the run with a durable trace.
- **Exit:** A complete user request flows through Stages 3.1-3.9 with gate-controlled transitions.

### 6.10 Implementation Stage 7 — Operational Shell & Workstation Integration

**Stage 7 | Primary:** 5.1-5.6. Integrate installer, runtime visibility, CLI/Web/TUI, security, terminal sessions, and doctor checks.
- **Exit:** A developer can install, run, monitor, inspect, and retrieve the M1 workflow's outputs locally.

### 6.11 Implementation Stage 8 — Local-Isolated RSI Integration

**Stage 8 | Primary:** 4.4. Implement isolated RSI Target 1 and required security/evidence workflow, only after baseline contracts and referee are stable.
- **Exit:** Sandbox candidate can be proposed/evaluated; hidden fixtures remain protected; adversarial tests are blocked/logged; no unauthorized production or referee mutation; human-controlled activation/rollback works.

### 6.12 M1 Delivery Phase 3 — Dynamic System Integration

**Expected Phase 3 M1 work:** Integrate dynamic intention compilation, Agent Team planning, admitted capability binding, heterogeneous routing, alternate Verifier integration, and Code Mode where enabling dependencies are available.
- Preserve the accepted Phase 1 fallback, gate/contract/security/evidence controls, and scientific-integrity rules.
- Record each capability as `PASS`, `BLOCKED`, or `INCOMPLETE` in `Phase_3_Completion_Report.md`; blocked/incomplete features do not automatically invalidate the core M1 demo.

#### Dynamic Intention Compilation

Integrate the advanced compiler when available, retaining bounded, non-interactive Phase 1 `Research_Brief.json` fallback independent of its availability.

#### Agent Team / Cluster Mode Dynamic Planning

Test the Leader Agent in bounded dynamic planning; maintain fixed SwarmFlow fallback, which Cluster Mode may itself invoke.

#### Dynamic Capability Capsule Discovery & Binding

Permit discovery and binding only from admitted capsule registry; each dynamic node still needs a governed Node Execution Contract.

#### Heterogeneous Model Routing

Test mocks until approved endpoints/credentials exist; any real alternate route remains isolated, validated, and reversible to Codex.

#### Alternate Verifier Model Integration

Test approved alternative reviewer provisioning through the existing gate interface without changing referee policy or acceptance criteria.

#### OpenJiuwen Code Mode

Evaluate Code Mode for Builder/dynamic functionality only where consistent with M1 safety, scope, gates, and fallback.

### 6.13 Architecture Handoff Boundary

PRD controls product outcomes, scope, artifacts, and acceptance. Architecture Design specifies exact schemas, API/IPC, modules, storage, security, and deployment. Resolve any change to observable PRD behavior through an explicit decision.

### 6.14 M1 Implementation Completion & Core Demo Rule

**Core M1 demo requires:** Stages 0-8 passed, Section 1.5 DoD met, mandatory gate/failure-injection tests passed, full Phase 1 run reproduced, and required isolated RSI Target 1 security/activation validated.
- Summarize test evidence in `M1_Final_Test_Report.md`, phases in their completion reports, and all applicable Phase 3 statuses in `Phase_3_Completion_Report.md` and `M1_Implementation_Report.md`.
- Never mark mandatory gaps complete or omit Phase 3 work merely because it is non-blocking.
