# AI4Research - M1 Product Requirements

**Reduced-detail version**

## Contents

1. Overview & M1 Objectives
2. Domain Policy & Restrictions
3. Workflow Features (The Main Pipeline)
4. Foundation Features (The Engine)
5. Vertical Features (The Platform Shell)
6. M1 Implementation Order & Integration Plan

## 1. Overview & M1 Objectives

### 1.1 Product Overview

AI4Research is a personalized scientific research system built on JiuwenSwarm. SwarmFlow provides the deterministic Phase 1 workflow; Agent Team / Cluster Mode supplies the dynamic planning and collaboration integrated in Phase 3 and may invoke SwarmFlow.

**Phase 1 sequence:** Ingestion -> Requirement Compilation -> Search & Ideation -> Idea Screening -> Hypothesis Generation -> POC Implementation -> Scientific Benchmarking -> Scientific Evaluation -> Delivery.

The product is user-scoped, not local-only. Durable account/profile state may be cloud-backed, while research assets, POC execution, the Codex CLI bridge, and user-specific RSI use authorized local execution environments.

A workflow node is a run-specific objective or task. Its **Node Execution Contract** binds the objective, inputs, outputs, acceptance obligations, permissions, resource limits, and exact admitted Capability Capsule versions. A node may use one or more capsules; a capsule is a reusable capability definition and implementation, not the node or its runtime contract.

### 1.2 M1 Product Goal

Given a user-supplied baseline and research objective, identify an evidence-grounded opportunity, form a falsifiable hypothesis, build a bounded POC, compare baseline and treatment under a pre-registered protocol, and deliver the scientific result with its artifacts and evidence.

M1 first establishes a reliable, reproducible, gate-controlled baseline, then extends it through the bounded dynamic work in Phase 3. Infrastructure correctness and scientific conclusions remain distinct.

### 1.3 M1 Delivery Phase Model

An **M1 Delivery Phase** is a project delivery and acceptance boundary, not a SwarmFlow runtime phase. Section 6 Implementation Stages are engineering milestones within delivery phases. Do not use "Track" as a synonym.

#### M1 Delivery Phase 1 - Governed Research Baseline

**Scope:** Implementation Stages 0-7 establish the fixed research workflow, static Codex route, bounded compiler fallback, capsule governance, Harness, Evaluator, Builder, evidence persistence, and operational interfaces.

**Exit:** All assigned Stage Exit Conditions pass; the full research workflow runs end-to-end with gate-controlled transitions; acceptance and failure-injection tests pass; evidence is preserved in `Phase_1_Completion_Report.md` and its referenced records.

#### M1 Delivery Phase 2 - Local-Isolated RSI Validation

**Scope:** Implementation Stage 8 validates user-specific, bounded capsule improvement outside the live research workflow.

**Entry:** Capsule registry/provenance, evaluation, evidence storage, declared mutation scope, and independent hidden-fixture isolation are operational. Preparation may begin earlier, but completion requires these dependencies.

**Exit:** Required RSI Target 1 works; lineage, hidden-data isolation, adversarial security, admission, and human activation are demonstrated and recorded in `Phase_2_Completion_Report.md`.

#### M1 Delivery Phase 3 - Dynamic System Integration

**Expected M1 scope:** Advanced Intention Compiler; Agent Team / Cluster Mode planning, team formation and TaskGraphs; dynamic capsule discovery/binding; heterogeneous model routing; alternate Verifier integration; Code Mode; and other explicitly approved dynamic behavior.

**Entry:** The corresponding deterministic fallback is operational, dynamic behavior is isolated/configurable, and baseline comparison tests exist. Preparation must not destabilize Phase 1.

**Exit evidence:** Validate applicable dynamic paths and restoration of their deterministic fallback, preserving gates, contracts, security, provenance, and scientific integrity. Record results and dependencies in `Phase_3_Completion_Report.md`.

Phase 3 is expected within M1, not automatically M2. Do not skip it merely because the core demonstration works. An explicitly recorded `BLOCKED` or `INCOMPLETE` Phase 3 capability does not independently fail the core demo unless designated mandatory. Core demo acceptance requires Phases 1 and 2.

### 1.4 Core Product Invariants

* **Gate-locked advancement:** Persist an advancing Evaluator decision before releasing any governed downstream node; producer claims alone are insufficient.
* **Runtime contract-bound execution:** Every governed node follows its frozen Node Execution Contract and admitted capsule declarations. A contract may narrow, but not widen, capsule permissions.
* **Evidence before trust:** Artifacts, traces, measurements, citations, route information, and gate records substantiate execution claims.
* **Pre-registered evaluation:** Freeze the hypothesis, baseline, data, measurement definitions, protocol, and decision thresholds before POC execution. Do not revise them after observing results.
* **Scientific failure is valid:** A correctly executed, evidence-supported scientific `FAIL` proceeds to Delivery when infrastructure acceptance passes.
* **Fail fast:** Halt blocking infrastructure failures and preserve evidence; do not conceal failures through autonomous repair, repeated retries, or post-hoc contract changes.

### 1.5 M1 Definition of Done

The core M1 release/demo gate requires a complete governed Phase 1 research run and the required Phase 2 RSI validation:

1. Accept the research objective and permitted supporting resources.
2. Produce validated `Research_Brief.json`.
3. Produce evidence-linked `Candidate_Set.json`.
4. Select one opportunity in `Opportunity_Card.json`.
5. Freeze `Hypothesis_Blueprint.json`.
6. Produce bounded, mechanically valid `POC_Artifact_Bundle.zip`.
7. Execute baseline/treatment under the declared protocol and produce `Benchmark_Payload.json`.
8. Produce `Evaluation_Verdict.json`.
9. Deliver the research report and associated artifacts.
10. Gate every governed transition and persist execution/gate evidence.
11. Demonstrate that failure injection cannot incorrectly release downstream work.
12. Demonstrate required RSI Target 1, bounded mutation, independent evaluation, hidden-data isolation, human activation, and adversarial security.

Phase 3 remains expected M1 work with explicit outcome accounting, even when individual advanced features are not core-demo blockers.

### 1.6 PRD and Architecture Ownership Boundary

The **PRD** owns product behavior, scope, responsibilities, required artifacts and handoffs, invariants, acceptance/failure conditions, and product-level implementation order.

The **Architecture Design Set** owns technical realization: schemas, interfaces, modules, process topology, storage, deployment, and security mechanisms. It may refine implementation without silently changing PRD requirements.

The **Verification / Inspector workstream** owns concrete test design, fixtures, inputs, expected outputs, procedures, assertions, automation, and evidence. Tests must trace to PRD requirements and approved user stories/acceptance scenarios when available; verification must not weaken product acceptance. Raise required product changes explicitly.

### 1.7 Requirement Authority & Conflict Resolution

Apply the source hierarchy: Definition of Done and invariants; global Domain Policy; M1 feature requirements in Sections 3-5; Section 6 implementation checkpoints; mandatory Phase 2 RSI requirements; expected Phase 3 requirements; then Future State context.

Specific feature requirements may specialize but not weaken global restrictions. Section 6 does not override required product behavior. The PRD governs product behavior conflicts with Architecture; record discrepancies for an explicit decision. For unspecified low-level choices, use the smallest design consistent with the approved requirements and Architecture.

### 1.8 M1 Scope Label Convention

**Whitelist / M1 Scope:** Declared implementation scope for the applicable phase. Mandatory Phase 1 and 2 items affect core-demo acceptance. Phase 3 items are expected work with the acceptance distinction in Section 1.3.

**Conditional scope:** Required when its stated dependency is available; otherwise record the dependency and deferral honestly.

**Blacklist / Future State:** Excluded from the declared M1 scope unless explicitly promoted through a product/architecture decision. A phase-specific exclusion applies to that phase; permanent exclusions remain permanent. Future descriptions do not authorize implementation.

### 1.9 M1 Feature Freeze & Delivery Target

The October 1, 2026 decision set **October 5, 2026** as the last day for M1 feature changes. After freeze, changes may resolve contradictions, correct definitions or agreed omissions, clarify acceptance, strengthen evidence, or reconcile PRD and Architecture.

New or expanded M1 features require explicit product approval. Accepted corrections follow Section 1.10. The M1 delivery target is **on or before October 31, 2026**; internal progression depends on entry/exit conditions rather than invented phase dates.

### 1.10 M1 Incremental Change & Canonical Documentation Control

Material defects and post-baseline discoveries require attributable Change Records.

**Classify first:** Implementation defects change code/tests when requirements and design are correct. Design corrections update affected Architecture, code, and verification. Product corrections update the PRD and affected downstream artifacts. New scope requires Section 1.9 approval.

Each record identifies the issue, classification, affected documents/code/tests, approved intended behavior, status, and evidence. Change Records explain history; the current approved PRD and Architecture Design Set remain canonical.

Update only affected canonical documents and reconcile applicable Spec Kit artifacts. Preserve rejected, superseded, and reverted records with explicit status; do not delete history. Agents implement only approved, explicitly selected changes. Completion requires consistent requirements, design, specifications, code, and verification evidence.

## 2. Domain Policy & Restrictions

### 2.1 Purpose

These global boundaries apply to all workflow, foundation, platform, and implementation requirements. Features may narrow but must not silently weaken them.

### 2.2 M1 Domain Boundary

Phase 1 is restricted to scientific research: interpret an objective, retrieve permitted evidence, select an opportunity, form a hypothesis, build/test a bounded POC, and report the result. General-purpose autonomous engineering and arbitrary workflows are not part of the Phase 1 path.

### 2.3 User and Deployment Boundary

Attribute every run to a user, workspace, and run identity. Separate durable account/profile persistence from research execution and preserve reproducible user-specific configuration, capsule versions, artifacts, and evidence.

M1 uses one authorized local execution host; it does not require enterprise tenancy, shared workspaces, remote worker fleets, cloud execution of untrusted POC/RSI code, billing infrastructure, or distributed scheduling. Approved cloud-backed account/profile persistence is not excluded. Architecture owns the precise split.

### 2.4 Input and External Evidence Policy

Accept natural-language requests, permitted local references, explicitly supplied project assets/datasets, and bounded academic evidence from approved search capabilities. Phase 1 must not crawl the open web, clone arbitrary repositories at intake, obtain undeclared datasets, invent evidence, or expand beyond approved sources.

### 2.5 Scientific Integrity Policy

Freeze scientific claims, baseline, variables, validation data, measurements, procedure, and decision criteria before execution. Do not move thresholds, substitute favorable data, omit baseline comparisons, or manufacture measurements.

Stage 3.7 collects empirical evidence; Stage 3.8 interprets it; Section 4.2 determines infrastructure admissibility and release.

### 2.6 Capability and Agent Boundary

Actions must respect the Node Execution Contract and participating capsule declarations. No unauthorized tools/effects, upstream artifact changes, permission expansion, gate bypass, fabricated completion, or silent changes to scientific criteria are permitted.

### 2.7 Workflow Autonomy Boundary

Phase 1 is fixed and sequential: no live restructuring, extra workflow stages, parallel hypothesis swarms, unbounded retries, autonomous self-healing, silent replanning, or conversion of failed gates to passes. Governed Phase 3 planning/routing must preserve the deterministic fallback and all controls.

### 2.8 Evaluation and Evidence Policy

The Evaluator is the release authority. Run deterministic Tier 1 checks before independent, read-only Tier 2 semantic verification. A mandatory Tier 1 failure prevents Tier 2 execution. Decisions and claims require attributable evidence.

### 2.9 Execution and Security Boundary

Treat generated code as untrusted. Restrict filesystem, process, network, tool, and resource access to authorized boundaries; record observed behavior and fail mandatory security violations. Architecture defines the sandbox and isolation mechanisms.

### 2.10 Data and Traceability Boundary

Keep compact reasoning context in agent memory and authoritative raw evidence in Data Foundations. Preserve benchmark logs, traces, artifacts, gate decisions, and records attributable to their run, stage, and capability.

### 2.11 RSI Boundary

RSI is separate from the live Phase 1 workflow and may change only authorized capsule implementation material. It cannot change workflow contracts, gates/referees, model weights, protected interfaces/security, mutation authority, hidden tests, evidence, or promotion policy.

Hidden evaluation is independent; only approved bounded feedback reaches RSI. Scope escape, protected-data access, tampering, or promotion bypass halts the session, preserves evidence, and requires human review. Activation follows human-controlled admission.

### 2.12 M1 Global Non-Goals

Outside the Phase 1 baseline: dynamic production workflow generation, parallel hypothesis execution, unrestricted multi-agent research, and the separately governed Phase 3 behaviors.

Outside M1 unless explicitly approved: multi-host execution, enterprise tenancy/infrastructure, autonomous defect-repair loops, dynamic Evaluators, reviewer voting/debate, live RSI mutation, automatic RSI promotion, model training, cloud deployment of generated artifacts, and automatic external publication. Phase 3 enables only its expressly defined bounded capabilities.

## 3. Workflow Features (The Main Pipeline)

### 3.0 Codex CLI Integration (Priority Unblocker)

Stabilize the existing local Codex CLI adapter as the priority unblocker for JiuwenSwarm model calls using the active subscription, without requiring enterprise API access.

#### 3.0.1 Existing Implementation Verification & Refactor

Inspect and reuse the existing adapter; verify request/response compatibility and synchronous, single-turn calls. Keep IPC local through restricted sockets or named pipes with session-bound authentication; no TCP listener. Do not replace it with an unnecessary new proxy or add complex streaming.

#### 3.0.2 Abstraction for "Endpoint of Last Resort"

Expose the adapter through a provider-compatible interface, record timeouts/authentication failures, and retain it as the fallback route. Dynamic routing belongs to Phase 3 and must not replace the validated Phase 1 route without approval.

### 3.1 Ingestion

Capture the research request and local materials for Requirement Compilation, keeping reference text distinct from executable assets and validation data.

#### 3.1.1 Request Capture & Channel Signal Intake

Accept natural-language input through CLI and native Web UI. External messaging and voice intake are excluded.

#### 3.1.2 User-Supplied Material & Execution Asset Import

Extract text from supplied TXT, Markdown, and PDF references. Bind supplied local repositories and validation datasets to the run without cloning or downloading replacements. Register their identity/type/location and keep them separate from reasoning text. Office formats, complex vectorization, and live scraping are excluded.

#### 3.1.3 Intake Context Binding

Bind active user identity, local execution profile, workspace, and run. No implicit reuse of another run's assets/state. Enterprise SSO is excluded.

#### 3.1.4 Real-Time Deduplication & Provenance Registration

Apply programmatic input-size limits and record source paths, sizes, and ingestion times. Semantic deduplication and intake cryptographic signing/hashing are excluded.

#### 3.1.5 Intake Qualification

Reject empty requests and unreadable input directories; otherwise supply the combined request/reference buffer to Section 3.2. Do not add an intake LLM quality-grading step.

### 3.2 Requirement Compilation

Use a self-contained bounded, one-shot Phase 1 compiler to produce `Research_Brief.json`. It must not depend on the externally developed advanced Intention Compiler. Phase 3 integration retains this fallback.

#### 3.2.1 Intent Interpretation

Extract the research objective in one model pass; do not generate candidate ideas here.

#### 3.2.2 Context Scoping

Derive in-scope and out-of-scope boundaries from supplied intake only, without external searches to fill gaps.

#### 3.2.3 Ambiguity Resolution

Use conservative fixed defaults for missing parameters in Phase 1. Interactive clarification belongs to the Phase 3 compiler.

#### 3.2.4 Constraint Resolution

Capture stated runtime, compute, hardware, and token constraints without dynamic host profiling.

#### 3.2.5 Requirement Prioritization

Separate mandatory requirements from optional preferences.

#### 3.2.6 Acceptance Definition

Preserve user-level targets and constraints in the Research Brief. Stage 3.5 owns their conversion into immutable experiment-specific success, falsification, and classification rules.

#### 3.2.7 Requirement Contract Confirmation

Produce the standardized Research Brief and submit it for gate review before Search. Phase 1 hands it to the fixed SwarmFlow workflow; Phase 3 supplies executable task semantics to the Leader. Asynchronous approval waits at this handoff are excluded.

### 3.3 Search & Ideation

Use `search_capsule.md` and explicitly bound supporting capsules for bounded retrieval and evidence-grounded ideation under the node contract.

#### 3.3.1 Search Strategy Formation

Generate a fixed keyword-query list from the Research Brief in a single model pass; no live query-reformulation loops.

#### 3.3.2 Multi-Source Signal Discovery (Hybrid Retrieval)

Use admitted `deepsearch` capabilities for local references and bounded academic-source queries. Apply a strict Top-K bound. No open-web crawling or parallel search swarms.

#### 3.3.3 Source Qualification & Technical Signal Extraction

Extract relevant verbatim source passages, without adding publisher/author-authority grading.

#### 3.3.4 Signal Organization & Trend Analysis

Group retrieved evidence by query. Historical trend analysis and cross-domain transfer modeling are excluded.

#### 3.3.5 Idea Generation

Generate 1-3 evidence-grounded candidate ideas in a single pass and attach source citations. Unsupported speculative ideas are excluded.

#### 3.3.6 Search Coverage Review & Result Compilation

Package `Candidate_Set.json` for gate review before Screening. Validate schema, evidence, and enforceable budgets; record token limits and enforce them only with reliable telemetry. No recursive search-coverage reflection.

### 3.4 Idea Identification / Screening / Opportunity Selection

Use `screening_capsule.md` and bound supporting capabilities to narrow existing candidates to one feasible opportunity. Do not invent new ideas during screening.

#### 3.4.1 Candidate Consolidation

Consolidate near-duplicates in one pass, preserving technically distinct variants. No iterative clustering or re-indexing.

#### 3.4.2 Idea Identification

Associate each candidate with a concrete technical problem and proposed mechanism grounded in the evidence.

#### 3.4.3 Idea Card Formation

Represent each idea in a structured card with identity, summary, evidence links, assumptions, and risks.

#### 3.4.4 Opportunity Definition

State the technical bottleneck and why the proposed mechanism addresses it; commercial business cases are excluded.

#### 3.4.5 Technical Opportunity Screening (Fixed-Rubric LLM Evaluation)

Apply the fixed screening rubric in one model pass: Novelty, Technical Feasibility, and Compute Alignment, each scored 1-5 with a brief evidence-grounded justification. No consensus debate or code execution to assess feasibility.

#### 3.4.6 Strategic Opportunity Screening

Filter explicit dependency conflicts such as unavailable models or closed datasets. Formal patent/legal analysis is excluded.

#### 3.4.7 Opportunity Portfolio Prioritization

Sum the three scores, select Top-1, record lower-ranked rationales, and emit `Opportunity_Card.json` for gate review. No interactive user selection in the Phase 1 path.

### 3.5 Generate Technical Claims & Hypothesis

Use `hypothesis_capsule.md` to turn the selected opportunity into an immutable experimental blueprint. Supporting capabilities require explicit node-contract binding.

#### 3.5.1 Research Question & Technical Claim Formation

Form one concrete, falsifiable technical claim from the selected opportunity; no parallel competing hypotheses.

#### 3.5.2 Claim, Evidence, Data & Method Modeling (Benchmark Definition)

Declare the independent/dependent variables, exact baseline, and supplied validation dataset. Do not generate or scrape new data tailored to the proposed implementation.

#### 3.5.3 Hypothesis Pool & Mechanism Formation

Define the technical intervention to test. Automated counter-evidence probing and iterative parameter evolution are excluded.

#### 3.5.4 Falsifiability Screening & Hypothesis Contracting (Anti-Overfitting Contract)

Freeze success and falsification thresholds and permitted classifications in `Hypothesis_Blueprint.json` before POC generation or empirical results. Intermediate evidence is `INCONCLUSIVE` unless another rule was pre-registered. No downstream threshold changes.

#### 3.5.5 Verification-Ready POC Design

Produce the methodology, constraints, and verification plan in the Hypothesis Blueprint for gate review. Builder/Benchmarking may use, but not change, its dataset, measurements, or thresholds. Execution-code generation belongs to Stage 3.6.

### 3.6 POC Implementation

The POC node uses its Node Execution Contract, `poc_capsule.md`, and the dedicated Builder to construct bounded executable artifacts from the admitted Hypothesis Blueprint. Supporting capabilities must be explicitly bound.

#### 3.6.1 POC Implementation Environment Preparation

Prepare the isolated POC workspace and declare frozen dependencies. Builder does not install or change dependencies during construction; installation occurs in Stage 3.7.

#### 3.6.2 POC Construction (Code Generation)

Use admitted CodeSearch over the local repository and generate the single-file Python patch `poc_patch.py`. No broad production refactoring or prohibited system/network imports (`os`, `sys`, `subprocess`, `requests`, `urllib`, `shutil`).

#### 3.6.3 POC Component Integration & Configuration

Create `run_benchmark.py` linking baseline and treatment under the frozen protocol. Do not change measurement functions or acceptance thresholds.

#### 3.6.4 POC Functional Readiness Validation

Perform mechanical syntax/readiness and output-format checks, not scientific evaluation. Record failures for gate/human handling instead of autonomous repair loops.

#### 3.6.5 Testable POC Artifact Consolidation & Benchmark Handoff

Package the patch, harness, `requirements.txt`, and environment configuration as `POC_Artifact_Bundle.zip`. Submit build evidence to the gate; admitted bundles execute in Stage 3.7, not during packaging. Cloud deployment is excluded.

### 3.7 Scientific Benchmarking (POC Execution)

Use `benchmark_capsule.md` under the node contract to execute the admitted POC against its pre-registered baseline and collect empirical evidence, not scientific verdicts.

#### 3.7.1 Runtime Provisioning & Artifact Unpacking

Unpack the POC in an unprivileged, isolated local Python environment. Install only frozen declared dependencies. Environment failures halt for triage rather than dynamic dependency repair.

#### 3.7.2 Delta Execution (Baseline vs. Treatment)

Run baseline then treatment with the same declared hardware, configuration, data, and random-seed policy. Never report an isolated treatment without baseline comparison.

#### 3.7.3 Empirical Data Collection

Capture stdout, stderr, traces, and required measurements in Data Foundations, including `empirical_results.json`. Agent memory keeps compact summaries/references rather than raw logs.

#### 3.7.4 Results Consolidation & Handoff

Produce `Benchmark_Payload.json` with raw evidence and measurements. The infrastructure gate checks admissibility; an advancing verdict releases evidence to Stage 3.8 for scientific interpretation.

### 3.8 Scientific Evaluation

Use `scientific_evaluator_capsule.md` to interpret admitted measurements against the frozen hypothesis. This node is distinct from the read-only infrastructure Verifier; it cannot rewrite code or rerun experiments.

#### 3.8.1 Evaluation Scope & Evidence Assembly

Bind Benchmark Payload, Hypothesis Blueprint, and Research Brief. Do not fetch new live leaderboard or web data during evaluation.

#### 3.8.2 Evidence Completeness & Provenance Review

Check every required metric against observed raw evidence and identify missing or fabricated results.

#### 3.8.3 Experimental, Reasoning & External Validity Review

Perform a bounded qualitative plausibility check of experimental results; no secondary perturbation or counterfactual executions.

#### 3.8.4 Claim & Acceptance-Criteria Comparison

Compare measurements deterministically with pre-registered rules. No post-hoc goalpost changes.

#### 3.8.5 Verdict, Blocker & Residual-Risk Classification

Emit `PASS`, `FAIL`, `INCONCLUSIVE`, or `CONDITIONALLY_ACCEPTABLE` in `Evaluation_Verdict.json` using only pre-registered rules. Conditional acceptance requires an explicit pre-execution rule; insufficient or between-boundary evidence is inconclusive. Record blockers and risks. Scientific `FAIL` proceeds unchanged to Delivery when infrastructure acceptance passes.

#### 3.8.6 Refinement & Follow-Up Recording

Record limitations and follow-ups without triggering patches, reruns, or self-healing. Pass the verdict to Delivery through the gate.

### 3.9 Delivery (Report Generation)

Use `report_capsule.md` and explicitly bound supporting capabilities to synthesize admitted results, benchmark evidence, and original objectives without changing the scientific verdict.

#### 3.9.1 Delivery Planning & Evidence Handoff

Use the fixed `sciencediscovery/report-writer` Markdown template with the admitted evidence. No dynamically invented audience-specific report structures.

#### 3.9.2 User-Facing Deliverable Generation

Produce `research_report.md` with methodology, benchmark analysis, citations, and limitations. Publication-ready LaTeX, slide decks, and interactive dashboards are excluded.

#### 3.9.3 Deliverable, Reusable Asset & Knowledge Packaging

Package the report, POC scripts, environment details, and empirical evidence for the user. No automatic external publication.

#### 3.9.4 Authorized Distribution, Knowledge Transfer & Lifecycle Closure

Deliver artifacts to the authorized workspace, expose the report in supported native interfaces, and close/persist the SwarmFlow run. External messaging is disabled.

## 4. Foundation Features (The Engine)

### 4.1 Capability Capsules

Capability Capsules are reusable class-level declarations and implementations with interfaces, permitted behavior, resources, provenance, and governance metadata. They are distinct from runtime nodes and Node Execution Contracts. A capability can have versioned implementation lineage; a node may bind multiple admitted capsules.

#### 4.1.1 Capability Declaration & Assembly

Provide a machine-readable `capsule.json` declaration and corresponding human-readable `make_capsule.md` representation without conflicting sources of truth. Pin implementations and preserve identity, interfaces, permissions, entry points, mutation boundaries, hashes, and lineage. No live capability-class invention, unrestricted remote importing, or arbitrary dependency installation. Model selection belongs to Routing.

#### 4.1.2 Governance, Admission, Versioning & Registry Management

Maintain a capability-class registry with append-only admitted versions, explicit run pinning, reproducible history, admission/self-tests, and provisional trust. Activation, suspension, deprecation, and rollback are human-controlled. No autonomous promotion/deletion or publishing.

#### 4.1.3 Node Capability Binding & Runtime Contract Assembly

Phase 1 node templates declare bounded capability sets without semantic discovery. At node instantiation, resolve admitted versions and freeze the effective Node Execution Contract/bindings for that execution. Phase 3 may discover compatible admitted capabilities through a read-only catalogue, but must still create a contract before execution.

#### 4.1.4 Invocation & Composition

The CC Runner executes bound capsules within the node contract and records invocation identity, inputs/outputs, tool/effect observations, timing, and outcome. Aggregate node evidence for the Evaluator. Builder construction stays governed by the same contract. Enforce measurable time/invocation bounds and unprivileged code execution; no unrestricted composition or runtime installation.

#### 4.1.5 Capability Evolution (RSI Boundaries)

RSI may change only declared mutable implementation material, preserving interfaces, security/effect boundaries, provenance, and admission. No self-expansion, live mutation, automatic activation, referee modification, or recursive mutation of the improver.

### 4.2 Evaluator Gate & Verifier

Every governed output passes a synchronous two-tier infrastructure gate before downstream release. Tier 1 is deterministic and zero-LLM; Tier 2 uses an independent read-only Verifier. The gate checks execution and evidence integrity, not whether the scientific hypothesis succeeded.

#### 4.2.1 Evaluation Evidence Envelope & Two-Tier Gate Execution

Require a Stage Evidence Bundle binding run/node identity, Node Execution Contract, participating capsule versions/hashes, inputs/outputs, acceptance obligations, route, observed tools/effects, budgets, and execution/citation evidence. Tier 1 failure skips Tier 2. Successful Tier 1 proceeds to independent semantic review. Persist the resulting decision; referee policy is frozen against RSI modification.

#### 4.2.2 Contract, Schema & Artifact Conformance Evaluator

Check schema, required artifacts/fields, bounds, proof obligations, and conformance to node/capsule declarations. Reject stale or swapped artifacts by binding them to the correct run, node, contract, and capsule identities. Detect undeclared tools/effects and incomplete evidence. No automatic schema repair or relaxed constraints.

#### 4.2.3 Engineering Correctness & Code Quality Evaluator

Run supplied mandatory engineering tests and bounded static/syntax checks; validate permitted code scope and role separation. Preserve test results and failures as gate evidence. Mandatory failure blocks advancement; the Evaluator does not patch or retry artifacts.

#### 4.2.4 Performance, Cost & Benchmark Evaluator

Enforce measurable runtime budgets and declared operational bounds. Require complete, protocol-conformant baseline/treatment evidence. Time budgets remain authoritative when precise token/cost telemetry is unavailable; record reliable usage only. Scientific interpretation remains with Stage 3.8.

#### 4.2.5 Security, Privacy, Compliance & IP Evaluator

Check prohibited imports, allowlisted tools, filesystem/effect limits, unprivileged execution, local-security evidence, obvious secrets, and required source attribution. Confirmed violations produce `FAIL`; unavailable/misconfigured environments produce `ENVIRONMENT_BLOCKED`. No formal legal/compliance certification.

#### 4.2.6 Evidence, Factuality & Scientific Validity Evaluator

Use the independent semantic Verifier with the designated result/citation-review logic to check evidence support, citation integrity, reasoning, uncertainty, and plausibility. Return structured reasons and evidence references. Do not replace Stage 3.8's scientific conclusion, fetch fresh web evidence at every gate, or use reviewer voting.

#### 4.2.7 Lifecycle, Parity & Human Review Evaluator

Verify lifecycle order, prior gates, actual execution, observed effects, and that downstream work has not started prematurely. Preserve reviewer attribution and reasons. Route blocked/ambiguous/failed runs to human review under the declared interaction mode; human review cannot silently turn failure into pass.

#### 4.2.8 Verdict Aggregation & Orchestration Gate Policy

**Advancing verdicts:** `PASS` means mandatory checks passed; `PASS_WITH_KNOWN_LIMITATIONS` adds recorded non-blocking warnings.

**Blocking verdicts:** `FAIL` means a mandatory condition failed; `ENVIRONMENT_BLOCKED` means an external/runtime dependency prevents evaluation; `INCONCLUSIVE` means evidence cannot support a defensible decision.

Persist verdict, tier outcomes, reasons, warnings, and evidence before release/halt. `ESCALATE_TO_HUMAN` is an orchestration action, not a quality verdict. Normalized runtime results map warning-passes to `PASS`, environment blocks to `BLOCKED`, and retain `INCONCLUSIVE`.

A valid Stage 3.8 scientific `FAIL` receives infrastructure `PASS` when its process/contract/evidence checks pass; retain the scientific result and deliver it.

#### 4.2.9 M1 Evaluator Acceptance & Failure-Injection Tests

Demonstrate all required acceptance cases:

| Case | Required behavior |
|---|---|
| Valid artifact | Both tiers pass; gate advances. |
| Invalid schema | Tier 1 fails; Tier 2 is not run; no downstream start. |
| Stale/swapped artifact | Identity mismatch blocks advancement. |
| Broken citation/unsupported claim | Semantic `FAIL` or `INCONCLUSIVE` blocks advancement. |
| Budget violation | Halt with timeout evidence, without unnecessary semantic review. |
| Prohibited code/tool | Infrastructure failure and triage. |
| Environment failure | `ENVIRONMENT_BLOCKED`, preserved evidence, appropriate human handling. |
| Non-blocking limitation | Advance only when all mandatory checks pass; carry warnings. |
| Scientific negative result | Valid scientific `FAIL` reaches Delivery with infrastructure `PASS`. |
| Delayed/missing gate decision | No downstream start before a durably recorded advancing verdict. |

#### 4.2.10 Future State — Autonomous Multi-Faceted Evaluation via Auto Harness

**Future State only:** Auto Harness, dynamic or parallel evaluators, reviewer ensembles, automatic evaluator calibration, governed runtime repair loops, and autonomous harness evolution are not M1 work.

### 4.3 Foundational Models & Routing

Use the static Codex CLI route for Phase 1. Develop non-Codex, heterogeneous, or alternate-model behavior in Phase 3; use mocks until access is approved and do not claim real integration from mocks. Preserve the validated baseline.

#### 4.3.1 Model Capability Registry

Register Codex as the sole active Phase 1 endpoint. Phase 3 may represent a bounded mixed-model pool and exercise approved endpoints with capability/version metadata. Broad model catalogues, locally hosted weights, and fine-tuned variants are excluded.

#### 4.3.2 Model Routing & Selection

The DAG/Planner selects capsules; Routing selects the model for the given capability/task role. Phase 1 is static; Phase 3 tests bounded two-stage routing with separately reversible configuration. No learned routers, ensembles, mid-call switching, or global cost optimization.

#### 4.3.3 Model Usage Auditing

Attribute calls to run, node, role, capsule, route, timing, and outcome. Preserve available runtime-budget and provider telemetry. Account-level subscription allowance is not per-call token usage; missing token/cost data stays unavailable. Approved calls cannot bypass attribution; do not add internal telemetry-only metadata to provider prompts.

#### 4.3.4 AI Reviewer Agent (Routing Integration)

Provision the independent Tier 2 Reviewer through Codex in Phase 1. Phase 3 may integrate one approved unmodified alternative with reversible activation and the same interface/policy. It must not edit outputs, advance work independently, or silently replace the baseline.

### 4.4 RSI (Recursive Self-Improvement) Integration

Use a fixed, target-independent RSI engine with target-specific profiles to propose and evaluate bounded capsule improvements outside the live workflow. Preserve the independent referee and fixed interfaces.

**Required Target 1:** Improve the pure `rank_opportunities` helper in a sandbox copy of `screening_capsule`; produce an evaluated child and provenance, not automatic production adoption.

**Conditional Target 2:** Improve explicitly mutable screening prompt/rubric material only when the bounded headless model path is available. Otherwise defer Target 2 without blocking Target 1.

#### 4.4.1 Text-Based Artifacts (GEPA / MIProV2 / TextGrad)

For Target 2, mutate only authorized prompt/rubric material while preserving scoring dimensions, interfaces, parent tests, and compatibility. Compare parent/child on the same permitted fixtures. Referee rubrics remain immutable. Population search, live A/B tests, cross-node optimization, and LLM-judge loss are excluded.

#### 4.4.2 Runtime and Resource Routing (Bayesian Optimization / Bandits / Cost-Aware RL)

Measure traces, calls, and execution time only. Time is a tie-breaker when test-pass counts match; RSI does not optimize routing, budgets, retries, or concurrency.

#### 4.4.3 Capability Capsules and Physical Operators (Trajectory Mining / Code Evolution / CEGIS)

Target 1 changes only the authorized helper in a sandbox copy. Preserve Top-1 behavior, input scoring dimensions, `Opportunity_Card.json`, required checks, interfaces, and effects. Parent tests pass before hidden evaluation. No multi-file/operator/dependency mutation or automatic production adoption.

#### 4.4.4 DAG and Agent Organization (AFlow / MCTS / ADAS)

Workflow structure and roles are read-only to RSI. Validate recorded-input replay and interface compatibility without changing graph structure, roles, or gates.

#### 4.4.5 Evaluator, Reward, Contract, and Governance

Freeze checks, hidden sets, scoring/promotion policy, and referee configuration before the session. Preserve parent behavior before improvement evaluation. Hidden-loop feedback is bounded; hidden-final evaluation is terminal only. Test good/bad candidates and adversarial cases. RSI cannot author its own acceptance criteria or alter referee state.

#### 4.4.6 Memory, Retrieval, and Evidence (Memory Learning / Self-RAG / Reranker Training)

Keep hash-chained RSI attempt logs, parent lineage, and candidate evidence; verify provenance and score/log consistency. Product memory learning, reranker training, and writing RSI lessons into live product memory are excluded.

#### 4.4.7 Model Policies and Weights (SFT / LoRA / DPO / GRPO / Agent RL)

RSI never trains or changes model weights. Compare parent/child under the same declared model route and runtime configuration, recording their identity. Any future human-led training is separate; RSI-controlled training, reviewer-weight changes, and router-policy changes are excluded.

#### 4.4.8 Data, Benchmarks, Curriculum, and Observability (Active Learning / Hard-Case Mining / Credit Assignment)

Separate visible development, hidden-loop, hidden-final, and milestone/tracking data. Prevent known overlap with proposer-visible inputs; seed minimum independent fixtures when needed. Preserve the headroom rule and attributable attempts, lineage, scores, timing, and replay references. No RSI-generated hidden suites or milestone data as optimization feedback.

#### 4.4.9 Local-Isolated RSI Sandbox & Hidden-Evaluation Isolation

Isolate proposer/candidate execution from live production and authoritative referee assets. Approved public benchmark/repository retrieval is bounded, read-only, and pinned/snapshotted, not general network authority.

Hidden fixtures, expected outputs, and per-case identities remain inaccessible; return only approved aggregate feedback. Freeze hidden sets before the session, cap hidden-loop use, and reserve final evaluation for the terminal point. Preserve audit evidence, human admission/activation, and rollback. Architecture owns the isolation implementation.

#### 4.4.10 RSI Security Guardrails & Adversarial Validation

Actively test hidden-data leakage, referee/scoring tampering, out-of-scope mutation, permission escalation, prompt-injection escape, unauthorized effects, resource abuse, evidence tampering, premature/excessive evaluation access, and promotion bypass.

Every mandatory violation must be blocked with attributable evidence; violations halt the session pending human clearance. Reconcile evaluation and audit records, record sandbox vulnerabilities and residual risks, and never let RSI modify or certify its own guardrails.

### 4.5 Data Foundations

Separate native agent reasoning memory from local append-only system evidence. Avoid complex external telemetry databases, vector infrastructure, and distributed graph stores.

#### 4.5.1 Persistent Memory & Context Retrieval (Agent Memory)

Use JiuwenSwarm Task Memory and Coding Memory for compact facts, decisions, and working context, not large raw execution or benchmark logs.

#### 4.5.2 TaskGraph Persistence & Run Bundles (System Memory)

Preserve isolated Run Bundles and append-only capsule records containing prompts, artifacts, traces, gate results, timing, routing, and available usage. Record the effective configuration, capsule snapshot/versions, evaluation profile, RSI state, and supported seed that actually executed. Automated redaction/deduplication and multi-user telemetry separation are excluded.

#### 4.5.3 Contract & Capability Conformance Observability

Compare observed behavior with node contracts and capsule declarations. Flag undeclared tools/effects or inconsistent behavior; generate static Markdown/JSON capsule-version scorecards with failures, pass rates, runtime, and reliable usage. No persistent telemetry UI or continuous host monitoring.

#### 4.5.4 Sample Run Exports (Scaffolding for RSI Handoff)

Export frozen, labeled, content-hashed run evidence for the separate RSI workstream. Data Foundations prepares the handoff; RSI consumes it independently. No synthetic runs or automatic write-back from experiments into the live workflow.

#### 4.5.5 Extended Graph Management (Future State Only)

**Future State only:** Distributed concept, dataset, code, policy, workflow, trace, and memory graphs are excluded from M1.

### 4.6 Harness Core

The Harness uses JiuwenSwarm/SwarmFlow to manage local workflow lifecycle, capsule dispatch, evidence, and gate handoffs, while retaining Phase 3 Agent Team integration. No distributed brokers or worker infrastructure.

#### 4.6.1 Runtime Control Loop & Run Lifecycle Management

Initialize run identity/configuration and persist node lifecycle state: `Pending`, `Running`, `Evaluating`, then `Completed` or `Failed`. Conclude only after required nodes/gates are satisfied; no Auto Harness recursive sub-runs.

#### 4.6.2 DAG Scheduler & Operator Binding

Phase 1 executes the fixed linear workflow, releasing nodes only on `PASS` or `PASS_WITH_KNOWN_LIMITATIONS`. Phase 3 integrates governed Cluster Mode planning, capability resolution, and dependency management while retaining the static fallback. No multi-arm experimental batching on the primary path.

#### 4.6.3 Main Loop Dispatch & Runtime Supervision

Dispatch the local CC Runner, enforce time budgets, monitor execution health, and submit artifacts/logs/metrics as node evidence to the Evaluator. Remote worker dispatch is excluded.

#### 4.6.4 Failure Recovery & Resumability

Halt crashes and blocking gate results, preserve evidence, and invoke `human_session` in interactive mode. Explicit headless development/evaluation mode instead records the same blocking verdict and returns stable non-zero machine-readable completion without waiting for input. No hidden retry, self-repair, or autonomous partial-DAG rewind.

#### 4.6.5 Distributed Infrastructure & Concurrency (Future State Only)

**Future State only:** Distributed leasing, worker scheduling, queues, and cross-host arbitration are excluded. M1 research uses one authorized local execution host; this does not prohibit approved cloud account/profile persistence.

### 4.8 Planner

Phase 1 bypasses autonomous planning using the fixed SwarmFlow workflow. Phase 3 uses Agent Team / Cluster Mode to decompose objectives, construct TaskGraphs, and bind capabilities while preserving the fallback.

#### 4.8.1 Task Contract Decomposition

Use predefined work units in Phase 1. Phase 3 decomposes the Research Brief into bounded tasks with explicit objectives and dependencies. No mid-flight re-decomposition or complex delegation trees.

#### 4.8.2 TaskGraph Construction

Phase 1 uses the fixed graph with user-specific parameters from the Research Brief. Phase 3 constructs task relationships before dispatch. Massive parallel hypothesis graphs and execution loops are excluded.

#### 4.8.3 TaskGraph Validation & Feasibility Analysis

Validate required graph structure, dependencies, coverage, and capability feasibility before execution. Phase 1 uses startup checks; Phase 3 checks generated plans and returns infeasible plans to compilation for replanning. Multi-agent plan peer review is excluded.

### 4.9 Builder

Builder is the specialized Stage 3.6 executable-artifact construction engine, not a replacement for the general CC Runner or analytical workflow stages. It consumes the immutable Hypothesis Blueprint and returns bounded POC artifacts and mechanical evidence.

#### 4.9.1 Build Contract Interpretation & Preparation (Sub-features 1 & 2)

Interpret the build scope and verify supplied baseline/data in the isolated workspace. Phase 3 may evaluate Code Mode workspace/dependency tools separately. Unconstrained filesystem access and dynamic container provisioning are excluded.

#### 4.9.2 Code & Experimental Asset Construction (Sub-features 3, 5, 6, & 7)

Create the single-file patch and baseline/treatment harness under fixed evaluation data and seed policy. Preserve prohibited-import constraints. Phase 3 may test Code Mode diffs/multi-file refactoring in isolation, not autonomous production-wide refactoring.

#### 4.9.3 Analytical Deliverable Boundary

Builder owns build manifests, configuration, code, compile evidence, and packaging only. It must not regenerate or semantically modify Opportunity Cards, Hypothesis Blueprints, scientific verdicts, or final research reports owned by other stages.

#### 4.9.4 Prototype Assembly & Build Evidence Generation (Sub-features 9 & 12)

Mechanically validate and package dependencies, patch, harness, environment details, and build evidence as `POC_Artifact_Bundle.zip` for Stage 3.7. Container images, cloud services, and deployment packages are excluded.

#### 4.9.5 Excluded Capabilities & Advanced Lifecycle Features (Sub-features 4, 10, 11, & 14)

Model training/fine-tuning, direct integration into production repositories, autonomous runtime defect-repair loops, and deployable cloud services are excluded. Construction/execution failures preserve evidence and halt for the declared human/headless handling.

## 5. Vertical Features (The Platform Shell)

Use native JiuwenSwarm operational interfaces and Data Foundations evidence exports rather than new custom telemetry applications or persistent telemetry databases.

### 5.1 Visibility & Statistics (Telemetry)

Expose current workflow status and inspectable historical execution evidence without altering authoritative runtime state.

#### 5.1.1 Workflow & Platform Status Visibility

Use the native run-tree and CLI/Web UI to show progress, transitions, gate verdicts, and halts. Custom persistent or cross-run dashboards are excluded.

#### 5.1.2 Execution Trace Search & Inspection

Inspect append-only records/Run Bundles and static capsule-version scorecards. No dedicated large-scale interactive trace-search engine.

#### 5.1.3 Resource Usage, Cost & Capacity Management

Monitor and persist execution duration, invocation counts, configured limits, and reliable token/cost telemetry. Unavailable usage remains unavailable, not authoritative billing. Cross-user chargeback and dynamic cluster allocation are excluded.

#### 5.1.4 Runtime Status Visibility

Capture static host facts once at run start. Continuous CPU/GPU/RAM sampling and distributed hardware dashboards are excluded.

### 5.2 Installer & CLI & Webapp

Provide Python-based installation and a single local initialization entry point. Reuse native engine/services; compiled desktop packages and self-updating channels are excluded.

#### 5.2.1 CLI Installation & Workstation Initialization (MacOS & Linux - Sub-features 3 & 4)

Support macOS/Linux setup, workspace/evidence scaffolding, capsule registry seeding, isolated RSI workspace and independent hidden fixtures, and configuration. Verify provider authentication, paths, workflow readiness, telemetry capture, and fixture isolation through doctor/pre-flight checks. Provide a direct CLI research entry point.

#### 5.2.2 Web Application & Status Service (Sub-feature 5)

Start the native local Web UI/status service with ephemeral session authentication. Bind it to loopback only and expose prompt intake, run/gate progress, and Markdown results. Cloud-hosted research Web UI, public listeners, and remote multi-tenant status APIs are excluded.

#### 5.2.3 Native Desktop Applications (Windows & MacOS - Sub-features 1 & 2)

**Future State only:** Native Windows/macOS desktop binaries, desktop shells, GUI setup wizards, and background update channels are excluded.

### 5.3 UI

Use the native CLI, Web UI, and TUI, with lightweight AI4Research branding rather than new proprietary interface components.

#### 5.3.1 Command-Line Interface (CLI)

Support research submission, status/output inspection, and stable completion information. Headless tests accept explicit task/configuration and supported seeds, return run identity/evidence references, and never wait for interactive input. Record requested/effective seeds without claiming deterministic model output when unsupported.

#### 5.3.2 Web Graphical User Interface (GUI)

Provide native prompt intake, run-tree monitoring, report viewing, and basic branding. Do not add custom widgets, workflow editors, mid-run gate/threshold controls, or cloud user portals.

#### 5.3.3 Terminal User Interface (TUI)

Expose the native TUI for monitoring and interactive human triage of halted runs. Custom RSI/telemetry widgets and distributed hardware views are excluded.

### 5.4 Account Management & Local Security Controls

Separate durable product identity from local OS/session security. Bind research execution to the active user, workspace, and run; Architecture owns the approved cloud/local identity implementation.

#### 5.4.1 Account Registration & User Profile Management (Sub-features 1 & 3)

Maintain stable account identity and profile persistence independent of a single run/workspace. Bind local runs to that identity; permit machine-specific settings to override account defaults. Do not infer project objectives from unrelated history. Enterprise directories, role hierarchies, and shared workspaces are excluded.

#### 5.4.2 Authentication & Local Web Security (Sub-feature 2)

Keep the local Web UI/backend loopback-only and require protected random session credentials on requests. No public/LAN exposure or enterprise SSO, MFA, OAuth, or multi-tenant session flows.

#### 5.4.3 Runtime Sandboxing & Process Isolation (Security Boundary)

Execute untrusted POC code under restricted local privileges with bounded workspace access. Protect the Codex IPC bridge without a TCP listener. Pre-flight checks must verify the runner cannot read hidden RSI fixtures and halt on isolation failure. Heavy container/hypervisor/kernel enforcement infrastructure is outside M1.

#### 5.4.4 Privacy & Personal Data Controls (Sub-feature 4)

Allow inspection/removal of local project data, artifacts, traces, and settings. Distinguish external account/profile state from local execution data: deleting a workspace is not account deletion. External durable state must remain user-attributable. Enterprise privacy/retention administration is excluded.

### 5.5 Message Channels

M1 uses local CLI/Web UI/TUI and terminal sessions, not external communication connectors. This does not exclude approved account/profile persistence.

#### 5.5.1 TMUX Session & Terminal Surface Management (Sub-feature 3)

Use local tmux sessions/panes for background services and attach/detach log/fault inspection. No distributed terminal synchronization.

#### 5.5.2 External Messaging Integrations: WeChat & Discord (Sub-features 1 & 2)

Disable external chat adapters, webhooks, and bot listeners, including WeChat, Discord, Slack, and Feishu. Intake remains supplied local assets and direct CLI/Web UI requests.

### 5.6 System Configurations (`config.yaml`)

Use local declarative `config.yaml` settings. Resolve/freeze effective configuration at run start; later file changes cannot alter active runs. Architecture owns representation and precedence implementation; remote syncing and distributed topology are excluded.

#### 5.6.1 LLM Configuration (Sub-feature 1)

Configure Codex as the Phase 1 endpoint and static role aliases. Approved alternative endpoints/credential references belong only to explicit evaluation profiles; use mocks before access approval. Do not expose secrets or change Phase 1 aliases implicitly.

#### 5.6.2 User Settings (Sub-feature 2)

Configure local workspace paths, hardware constraints, supported input types, and user preferences. Project configuration overrides global defaults. No organization-wide preference policy or shared local multi-user switching.

#### 5.6.3 Cost & Budget Settings (Sub-feature 3)

Configure/enforce execution-time and invocation limits, using exact usage only when reliably available. Halt exceeded operational bounds. Real-time billing, cloud quota integration, and financially driven rerouting are excluded.

#### 5.6.4 Cluster Settings (Sub-feature 4)

**Outside M1:** Multi-host execution topology, remote worker addresses, distributed heartbeats, leases, and cluster limits. Research executes on one authorized local host; account/profile services are distinct.

#### 5.6.5 Development & Evaluation Run Configuration

Provide explicit development/evaluation profiles pinning relevant capsule, model, Evaluator, RSI, and seed configuration. Record what actually executed and freeze it per run.

Pre-declared ablations may disable/replace approved components, but runs missing mandatory product controls are not valid Phase 1 acceptance evidence and cannot automatically change capsule standing. End-user control disabling, arbitrary component loading, and live production reconfiguration are excluded.

## 6. M1 Implementation Order & Integration Plan

### 6.1 Purpose

Implement dependency-first rather than simply following feature section numbers. Work within a stage may be parallelized, but dependent stages cannot be accepted before prerequisite exit conditions are met. Build governing infrastructure before dependent workflow features; Architecture owns low-level integration design.

### 6.2 Implementation Principle

Build incrementally through runnable, testable integration boundaries. Completion requires upstream contracts, admitted/executable capsules, evidence capture, valid gate decisions, correct Harness release/halt behavior, persistence, and the Stage Exit Condition.

Failed mandatory validation is not completion. Independent work may continue, but blocked stages and dependent integration remain incomplete until resolved or explicitly re-scoped.

### 6.2.1 M1 Validation & Verification Governance

PRD requirements define what must be proven. The M1 Test Specification / Verification Plan defines concrete cases, fixtures, inputs, expected outputs, procedures, assertions, automation, and evidence. Approved user stories and Spec Kit acceptance scenarios supply traceability when available, not substitutes for execution.

Each Implementation Stage records requirements/exit conditions, cases run, results, evidence, and gaps. Detailed expected/actual outputs remain in test artifacts. A stage is complete only with supporting validation.

Each `Phase_<N>_Completion_Report.md` aggregates stage/test results, failures, dependencies, and limitations without replacing underlying evidence. Phase completion requires its applicable exit conditions.

Produce `M1_Final_Test_Report.md` consolidating requirement/story coverage, phase outcomes, required acceptance/failure-injection results, `PASS`/`FAIL`/`BLOCKED`/`INCOMPLETE` status, limitations, and evidence. It is the verification summary, not a substitute for case-level records.

### 6.2.2 Incremental Change Implementation Protocol

After the initial build, implement bounded approved changes:

1. Read current affected PRD, Architecture, specification, and verification artifacts.
2. Confirm the change classification and scope; do not rewrite correct/unaffected documents for code-only defects.
3. Update intended product/design requirements where needed and reconcile applicable Spec Kit artifacts.
4. Implement only the selected approved change, not unrelated or inactive records.
5. Run affected regression, integration, acceptance, and failure/security validation; preserve evidence.
6. Record the outcome and reconcile canonical docs, specifications, code, and tests before closure.

Correct or explicitly revert destabilizing changes; preserve their history.

### 6.3 Implementation Stage 0 — Runtime Unblocker & Local Configuration

**Scope:** Sections 3.0, 5.4, 5.6. Stabilize the adapter, secure IPC, local configuration/workspace, and execution identity.

**Stage Exit Condition:** JiuwenSwarm completes a bounded Codex CLI model call within the required local-security boundary.

### 6.4 Implementation Stage 1 — Core Governed Execution Backbone

**Scope:** Sections 4.1, 4.3, 4.5, 4.6, 4.2. Establish capsule admission, static model/Reviewer provisioning, evidence persistence, Harness execution, and Evaluator integration.

**Stage Exit Condition:** In **Node A -> Evaluator Gate -> Node B**, valid output releases B and invalid output prevents B from starting. The blocking case also terminates headlessly with durable evidence and stable machine-readable status, without `human_session`; preserve effective configuration.

### 6.5 Implementation Stage 2 — Intake, Requirement Contract & Static DAG

**Scope:** Sections 3.1, 3.2, 4.7, 4.8. Integrate request/resource intake, the fixed compiler, Research Brief, and static graph/capsule binding.

**Stage Exit Condition:** A request becomes validated `Research_Brief.json` and initializes the fixed SwarmFlow workflow without autonomous planning.

### 6.6 Implementation Stage 3 — Evidence-to-Hypothesis Research Path

**Scope:** Sections 3.3-3.5. Integrate Search, Screening, and Hypothesis Generation with gates and their primary capsules; produce Candidate Set, Opportunity Card, and Hypothesis Blueprint.

**Stage Exit Condition:** A validated brief reaches a pre-registered hypothesis through bounded evidence retrieval and fixed-rubric selection, retaining citations, constraints, and gate evidence.

### 6.7 Implementation Stage 4 — Builder & POC Assembly

**Scope:** Sections 3.6, 4.9. Integrate POC workspace, patch/harness generation, mechanical checks, packaging, and gate review. Builder does not take over analytical outputs.

**Stage Exit Condition:** An admitted Hypothesis Blueprint becomes bounded, mechanically valid, admitted `POC_Artifact_Bundle.zip` without autonomous repair loops.

### 6.8 Implementation Stage 5 — Benchmarking & Scientific Evaluation

**Scope:** Sections 3.7-3.8. Integrate protocol-bound baseline/treatment execution, benchmark evidence, infrastructure review, and scientific classification.

**Stage Exit Condition:** Demonstrate both a scientifically positive result and a scientifically negative but correctly executed result, each reaching the appropriate downstream state when infrastructure is valid.

### 6.9 Implementation Stage 6 — Delivery & End-to-End Research Run

**Scope:** Section 3.9. Integrate report generation, artifact packaging, native result access, lifecycle closure, and persistence.

**Stage Exit Condition:** One request completes Stages 3.1-3.9 with every governed transition gate-controlled and recorded.

### 6.10 Implementation Stage 7 — Operational Shell & Workstation Integration

**Scope:** Sections 5.1-5.6. Integrate native interfaces, installer, configuration/pre-flight checks, telemetry, authentication, and terminal management without redefining workflow/gate policy.

**Stage Exit Condition:** A developer can install, initialize, execute, observe, inspect, and retrieve complete research results through the supported local interfaces.

### 6.11 Implementation Stage 8 — Local-Isolated RSI Integration

**Scope:** Section 4.4. Integrate RSI after capsule/evaluation/evidence foundations are stable. Establish target profiles, separated fixtures, authorized mutation, independent scoring, provenance, human activation/rollback, and adversarial validation.

**Stage Exit Condition:** Required Target 1 produces an independently evaluated sandbox child; hidden material remains protected; mandatory adversarial attempts are blocked and recorded; scores/audit evidence reconcile; and live workflow, referee policy, interfaces, and active versions are not changed without explicit human action.

### 6.12 M1 Delivery Phase 3 — Dynamic System Integration

Phase 3 is expected M1 integration, not automatically deferred work. It depends on stable corresponding Phase 1 baselines; the implementation continues into applicable capabilities after Stage 8 unless an explicit dependency, scope decision, or platform limitation blocks them.

* **Advanced Intention Compiler:** Integrate when available, retaining the bounded one-shot fallback.
* **Agent Team / Cluster Mode:** Integrate dynamic task decomposition, roles, dependencies, and TaskGraphs; allow deterministic SwarmFlow use where appropriate.
* **Dynamic capsule binding:** Select only compatible admitted capsules and create a Node Execution Contract before execution.
* **Heterogeneous routing:** Develop bounded interfaces/selection with mocks before approved access, then test real endpoints; preserve Codex fallback until validation/approval.
* **Alternate Verifier:** Use the same interface and unchanged gate acceptance policy.
* **Code Mode:** Evaluate/integrate applicable construction or dynamic-execution capabilities without weakening M1 boundaries.

Preserve gates, contracts, admission, security, scientific integrity, provenance, and reversible deterministic fallbacks. Record every applicable capability as `PASS`, `BLOCKED`, or `INCOMPLETE` in `Phase_3_Completion_Report.md`. Do not skip work merely because it is non-blocking for the core demo.

### 6.13 Architecture Handoff Boundary

Architecture owns the detailed schemas, interfaces, modules, processes, storage, adapters, security mechanisms, errors, and deployment topology used to realize this PRD. Technical refinements must preserve product requirements; conflicts that change behavior require a PRD decision.

### 6.14 M1 Implementation Completion & Core Demo Rule

The **core M1 release/demo gate** requires:

* Stages 0-8 satisfy their exit conditions and Section 1.5 is demonstrated.
* Required gate acceptance/failure-injection tests pass.
* The full Phase 1 workflow and required Phase 2 RSI Target 1 meet evidence/security/persistence requirements.
* Mandatory validation is consolidated in `M1_Final_Test_Report.md` with underlying evidence.
* Implemented changes affecting mandatory behavior are reconciled with canonical documents, specifications, and verification.

Code presence or unavailable dependencies cannot stand in for validation. Record mandatory gaps/blockers explicitly.

Phase 3 remains expected M1 work. Every applicable capability must be attempted when dependencies permit and recorded as `PASS`, `BLOCKED`, or `INCOMPLETE`; a documented advanced-feature gap does not independently fail the core demo unless designated mandatory.

`M1_Implementation_Report.md` summarizes all applicable phases and references the Final Test Report, Phase Completion Reports, and material Change Records. Fully accounted-for work is not the same as every feature passing; preserve unresolved outcomes and underlying evidence.
