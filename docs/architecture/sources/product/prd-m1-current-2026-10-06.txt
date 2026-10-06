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
*   4.7 Intention Compilers
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

AI4Research is a personalized scientific research system built on **JiuwenSwarm**.

M1 uses JiuwenSwarm in two complementary ways:

*   **SwarmFlow** provides the deterministic, script-defined orchestration used by the governed Phase 1 research baseline.
*   **Agent Team / Cluster Mode** provides the dynamic multi-agent planning and collaboration capabilities evaluated and integrated during Phase 3. Cluster Mode may also invoke SwarmFlow workflows when deterministic orchestration is appropriate.

The target product is **user-scoped rather than local-only**. Durable account/profile state and product-level persistence may be cloud-backed, while execution that depends on user-owned project assets, secure POC execution, the Codex CLI bridge, or user-specific RSI may run inside an authorized local execution environment.

This hybrid boundary is intentional. Cloud-backed deployment can provide durable user access, account persistence, and product availability, while local execution preserves access to user-specific research assets, reproducibility, customization, and appropriate isolation for executable research and capsule-improvement workflows. Local execution is therefore an execution boundary where required, not the definition of the product itself.

The Phase 1 research workflow follows the fixed lifecycle:

**Ingestion → Requirement Compilation → Search & Ideation → Idea Screening → Hypothesis Generation → POC Implementation → Scientific Benchmarking → Scientific Evaluation → Delivery**

Each governed workflow node is a runtime instance of an objective or task within the active execution graph.

When a governed node is instantiated, the system creates a **Node Execution Contract** that binds the node's run-specific objective, required inputs and outputs, acceptance obligations, resource and effect limits, and the exact admitted Capability Capsule versions available to the node.

A workflow node may use one or more Capability Capsules. A Capability Capsule is a reusable, pre-defined capability definition and implementation package; it is not the workflow node itself and is not the run-specific Node Execution Contract.

Workflow outputs are not trusted solely because the producing agent reports success. Before a governed downstream node may begin, the preceding node must submit execution evidence to the Section 4.2 Evaluator Gate and receive an advancing infrastructure verdict.


### 1.2 M1 Product Goal

The objective of M1 is to first establish a **reliable, reproducible, evidence-backed and gate-controlled scientific research baseline**, then extend that baseline through the bounded dynamic planning, capability binding, and routing work defined for M1 Delivery Phase 3. Autonomous self-repair, distributed execution, and unrestricted self-improvement remain outside the M1 baseline unless explicitly promoted through a revised product and architecture decision.

The core product loop is:

> **Given a user-supplied baseline and research objective, identify an evidence-grounded opportunity, formulate a falsifiable technical hypothesis, build the minimum bounded proof of concept required to test it, execute the baseline and treatment under the pre-registered protocol, evaluate the resulting evidence, and return the scientific result with its supporting artifacts and execution trace.**

M1 prioritizes:

*   End-to-end execution of a complete research lifecycle.
*   Explicit contracts between workflow stages.
*   Evidence-grounded research claims.
*   Pre-registered and reproducible experimental evaluation.
*   Independent node-level verification.
*   Gate-controlled workflow advancement.
*   Clear separation between infrastructure correctness and scientific conclusions.
*   Traceability of artifacts, evidence, decisions, and gate verdicts.

### 1.3 M1 Delivery Phase Model

AI4Research uses **M1 Delivery Phase** as the single top-level project-delivery term. The term `Track` is not used as a synonym for Delivery Phase.

An M1 Delivery Phase represents a major product-delivery boundary with a defined purpose, entry condition, implementation scope, validation requirements, and exit condition.

> **Terminology Note:** An M1 Delivery Phase is a project-level delivery concept and is distinct from a JiuwenSwarm SwarmFlow runtime `phase`, which represents a stage inside an executing workflow script.

Implementation Stages in Section 6 are dependency-ordered engineering/integration milestones belonging to an M1 Delivery Phase. They are not separate product phases.

#### M1 Delivery Phase 1 — Governed Research Baseline

**Why this Phase exists:**  
Establish a stable, reproducible, gate-controlled end-to-end scientific research workflow before introducing self-improvement or broader dynamic orchestration behavior.

**Required scope:**

*   The fixed sequential SwarmFlow research workflow.
*   The static Codex CLI model route.
*   The bounded Requirement / Intention Compilation fallback.
*   Capability Capsule registry, admission, and runtime contract binding.
*   CC Runner and Harness execution.
*   Evaluator Gate and Stage Evidence Bundles.
*   Search & Ideation through Delivery.
*   Builder and bounded POC execution.
*   Data Foundations and reproducible run evidence.
*   Required M1 operational interfaces.

**Section 6 mapping:**  
M1 Delivery Phase 1 contains Implementation Stages 0 through 7.

**Phase 1 Exit Requirements:**

*   Implementation Stages 0 through 7 satisfy their Stage Exit Conditions.
*   The complete Stage 3.1 through Stage 3.9 research workflow executes end-to-end.
*   Every governed workflow transition is gate-controlled.
*   Required Evaluator acceptance and failure-injection tests pass.
*   Required run evidence is reproducibly persisted.
*   A `Phase_1_Completion_Report.md` is produced with requirement coverage, tests executed, failures/blockers, known limitations, and evidence references.

Phase 1 establishes the deterministic baseline against which RSI and dynamic-system behavior can be evaluated.

#### M1 Delivery Phase 2 — Local-Isolated RSI Validation

**Why this Phase exists:**  
Demonstrate that reusable Capability Capsule implementations can be improved for an individual user's environment while preserving reproducibility, capability declarations, hidden-evaluation isolation, independent judgment, and human-controlled activation.

RSI execution remains isolated from the live Phase 1 research workflow. The RSI engine may use local user-specific execution context and may consume explicitly approved, reproducibly pinned public benchmark/reference material where required, but it must not receive protected hidden evaluation material or uncontrolled network authority.

**Section 6 mapping:**  
M1 Delivery Phase 2 contains Implementation Stage 8.

**Phase 2 Entry Requirements:**

*   The Phase 1 Capability Capsule registry and provenance model are operational.
*   The Evaluator and required evidence-persistence pathways are operational.
*   The target capability and permitted mutation surface are explicitly declared.
*   The independent evaluation and hidden-fixture boundary is established.

Implementation preparation may occur earlier, but Phase 2 must not be accepted as complete until these dependencies are satisfied.

**Phase 2 Exit Requirements:**

*   Required RSI Target 1 executes successfully under the bounded mutation model.
*   Parent and child capability provenance is preserved.
*   Required hidden-evaluation isolation tests pass.
*   Required adversarial/security tests pass.
*   No candidate autonomously changes its declaration, permissions, referee, hidden evaluation material, or active production standing.
*   Human-controlled admission and activation are demonstrated.
*   A `Phase_2_Completion_Report.md` records implementation status, tests, candidate lineage, security results, blockers, known limitations, and supporting evidence.

#### M1 Delivery Phase 3 — Dynamic System Integration

**Why this Phase exists:**  
Extend the stable Phase 1 baseline with the dynamic planning, capability selection, routing, and orchestration behavior expected of the broader M1 system without allowing unfinished advanced functionality to destabilize the release-critical baseline.

Phase 3 is part of the **expected M1 implementation scope**. It is not automatically equivalent to Future State or M2 work.

Phase 3 includes, where technically available during M1:

*   Dynamic Intention Compiler integration.
*   Agent Team / Cluster Mode dynamic task planning.
*   Leader Agent task decomposition and team formation.
*   Dynamic TaskGraph generation and dependency management.
*   Dynamic Capability Capsule discovery and node binding.
*   Heterogeneous model-routing integration.
*   Alternate Verifier-model integration.
*   OpenJiuwen Code Mode evaluation/integration.
*   Other explicitly approved M1 dynamic orchestration behaviors.

**Phase 3 Entry Requirements:**

*   The relevant Phase 1 deterministic fallback capability is already operational.
*   The dynamic behavior has an isolated configuration or feature boundary so it cannot silently replace or destabilize the accepted baseline.
*   Applicable baseline tests and comparison criteria are available before the dynamic behavior is promoted into normal execution.

Development preparation may occur earlier where it does not block or destabilize Phase 1.

**Phase 3 M1 Expectation:**

Phase 3 functionality should be implemented and validated during M1 wherever the required dependencies, upstream components, credentials, and platform capabilities are available.

An implementation agent must not skip Phase 3 solely because the Phase 1 baseline already satisfies the core M1 demonstration.

If a Phase 3 capability cannot be completed because a required external dependency, unfinished team-owned component, unavailable API/model access, or unresolved platform limitation prevents valid implementation, the capability must be recorded explicitly as `BLOCKED` or `INCOMPLETE` together with the reason and available implementation evidence.

**Phase 3 Exit Requirements:**

For each Phase 3 capability attempted during M1:

*   The dynamic path is tested against its deterministic Phase 1 fallback or baseline where applicable.
*   Disabling the dynamic path restores the accepted deterministic baseline.
*   Dynamic behavior does not weaken Evaluator Gate, security, evidence, reproducibility, or scientific-integrity requirements.
*   The implementation and test outcome are recorded in `Phase_3_Completion_Report.md`.
*   Any unresolved dependency or limitation is explicitly documented rather than silently omitted.

**Core M1 Demo / Release Boundary:**

The core M1 demonstration remains centered on the deterministic governed research baseline and required RSI validation.

A Phase 3 feature that remains explicitly documented as `BLOCKED` or `INCOMPLETE` does not by itself invalidate the core M1 demonstration unless that feature has been separately designated as a mandatory M1 acceptance requirement.

However, Phase 3 remains part of the expected M1 implementation effort and must not be automatically deferred to M2 or Future State merely because it is non-blocking for the core demonstration.

### 1.4 Core Product Invariants

The following invariants apply across M1.

#### Gate-Locked Advancement

No governed downstream workflow node may begin solely because the producing agent claims success.

An advancing Evaluator Gate decision must be durably recorded before downstream execution is released.

#### Runtime Contract-Bound Execution

Every governed workflow node must execute under an explicit Node Execution Contract instantiated for the current run.

The contract must preserve:

*   The node's run-specific objective.
*   Required inputs and required outputs.
*   The exact admitted Capability Capsule versions available to the node.
*   Permitted tools and side effects.
*   Acceptance criteria and proof obligations.
*   Resource and execution constraints.
*   Required evidence obligations.

A runtime contract may restrict a bound Capability Capsule further for the current execution, but it may not grant permissions or behavior outside the capsule's admitted declaration.

#### Evidence Before Trust

Claims of successful execution must be supported by observable evidence such as artifacts, execution traces, benchmark results, test outputs, citations, route information, and gate records where applicable.

#### Pre-Registered Scientific Evaluation

Experimental acceptance conditions must be defined before the POC is executed.

The baseline, validation data, measurement definitions, and acceptance/falsifiability thresholds established by the Hypothesis Generation stage may not be modified downstream in response to observed results.

#### Scientific Failure Is a Valid Research Outcome

A hypothesis being rejected does not mean the system failed.

Stage 3.8 owns the scientific verdict. If the research process executes correctly and produces admissible evidence, a scientific `FAIL` must still proceed to Delivery.

The Evaluator Gate verifies the integrity of the process and artifact; it does not replace the scientific conclusion.

#### Fail Fast and Preserve Evidence

Blocking infrastructure failures must halt autonomous advancement and preserve the available evidence.

M1 must not silently hide failures through autonomous repair, repeated retries, or post-hoc changes to the research contract.


### 1.5 M1 Definition of Done

The **core M1 release/demo gate** is satisfied when the required M1 Delivery Phase 1 Governed Research Baseline and required M1 Delivery Phase 2 Local-Isolated RSI Validation satisfy the acceptance conditions below.

M1 Delivery Phase 3 Dynamic System Integration remains part of the expected M1 implementation effort, but individual Phase 3 capabilities may remain explicitly `BLOCKED` or `INCOMPLETE` without invalidating the core M1 demonstration unless they have been separately promoted into the mandatory acceptance criteria.

For the Phase 1 research baseline:

1. A user submits a research objective and permitted local supporting resources.
2. The request is compiled into a validated `Research_Brief.json`.
3. Search & Ideation produces evidence-linked candidate ideas.
4. Idea Screening selects one bounded opportunity.
5. Hypothesis Generation produces an immutable `Hypothesis_Blueprint.json`.
6. POC Implementation produces a bounded, mechanically valid `POC_Artifact_Bundle.zip`.
7. Scientific Benchmarking executes baseline and treatment using the declared experimental protocol and produces `Benchmark_Payload.json`.
8. Scientific Evaluation produces `Evaluation_Verdict.json`.
9. Delivery produces the final research report and associated research artifacts.
10. Every governed stage transition is controlled by the Evaluator Gate.
11. Required execution and gate evidence is preserved through Data Foundations.
12. Failure-injection testing demonstrates that invalid, stale, unsupported, prohibited, or otherwise inadmissible artifacts cannot incorrectly advance the workflow.

For M1 Delivery Phase 2 — Local-Isolated RSI Validation:
13. The Local-Isolated RSI path satisfies the bounded-mutation, independent-referee, hidden-evaluation isolation, human-activation, and adversarial-security acceptance requirements defined in Sections 4.4 and 6.11.


### 1.6 PRD and Architecture Ownership Boundary

This PRD defines **what the M1 product must do and what must be true for it to be considered correct**.

Accordingly, this PRD owns:

*   Product behavior and user-visible outcomes.
*   M1 scope and non-scope.
*   Workflow responsibilities and ownership.
*   Required capabilities.
*   Required artifacts and their semantic purpose.
*   Required handoffs and dependencies.
*   Product invariants.
*   Acceptance and failure conditions.
*   Product-level implementation sequencing.

The Architecture Design specification owns **how those requirements are technically realized**, including exact payload schemas, internal APIs and IPC transports, class and module boundaries, process topology, storage layout, runtime object models, detailed security mechanisms, and other implementation-specific interfaces.

For example, this PRD may require Stage 3.5 to produce an immutable `Hypothesis_Blueprint.json` containing the agreed experimental methodology, constraints, and verification contract. The Architecture Design specification owns the exact field-level schema and technical representation used to satisfy that requirement.

Architecture may refine implementation details without changing the observable behavior, scope, invariants, ownership, or acceptance requirements defined by this PRD.

Any architectural constraint that requires changing those product requirements must be raised as an explicit PRD decision rather than silently resolved in implementation.


### 1.7 Requirement Authority & Conflict Resolution

This PRD contains product requirements at multiple levels of abstraction. When implementing or interpreting M1, requirements must be read according to the following authority rules.

#### M1 Requirement Authority

1. **M1 Definition of Done and Core Product Invariants**
   define the non-negotiable product outcomes and behaviors that the completed M1 system must satisfy.

2. **Domain Policy & Restrictions**
   define the global operating boundaries that apply across all workflow, foundation, vertical, and implementation-plan sections. A feature-specific requirement may narrow these boundaries but may not silently weaken them.

3. **M1-specific requirements in Sections 3–5**
   define the required behavior, responsibilities, artifacts, dependencies, acceptance conditions, and exclusions of individual product capabilities.

4. **Section 6 — M1 Implementation Order & Integration Plan**
   governs implementation sequence and integration checkpoints. It does not override the required product behavior defined elsewhere in the PRD.

5. **M1 Delivery Phase 2 — Local-Isolated RSI requirements**
   define the required RSI validation scope. Mandatory Phase 2 requirements contribute to the core M1 release/demo gate where specified by Section 1.5.

6. **M1 Delivery Phase 3 — Dynamic System Integration requirements**
   define the expected M1 dynamic planning, capability binding, routing, and related integration work. Phase 3 requirements must preserve the deterministic Phase 1 fallback and do not independently block the core M1 release/demo gate unless explicitly promoted into mandatory acceptance criteria.

7. **Future State requirements**
   are design context only for M1. They must not be implemented as part of the declared M1 scope unless explicitly promoted through a revised product and architecture decision.

#### Interpretation Rule

When two requirements appear inconsistent, they must be interpreted in the manner that preserves the M1 Definition of Done, Core Product Invariants, and global Domain Policy while satisfying the more specific M1 feature requirement where possible.

A narrower feature requirement may specialize a broader requirement, but it may not weaken a global invariant, security boundary, gate requirement, or other explicit M1 product constraint.

#### PRD and Architecture Conflict Rule

The Architecture Design specification owns technical realization where this PRD intentionally leaves implementation details unspecified.

If the Architecture Design specification and this PRD conflict on observable product behavior, M1 scope, product invariants, required artifacts, ownership, acceptance conditions, or required workflow behavior, this PRD governs.

The discrepancy must be recorded and raised as an explicit product/architecture decision rather than being silently resolved by changing product behavior.

Where neither document specifies a low-level implementation choice, the implementation should use the smallest design consistent with the declared M1 behavior, constraints, and architecture.


### 1.8 M1 Scope Label Convention

The following scope labels are used consistently throughout this PRD.

#### Whitelist — M1 Implementation Scope

An item listed under **Whitelist**, **M1 State (Whitelist)**, or **M1 Scope** is part of the declared implementation scope of its applicable M1 Delivery Phase unless explicitly marked conditional.

For M1 Delivery Phases 1 and 2, mandatory Whitelist items contribute to the core M1 release/demo acceptance requirements.

For M1 Delivery Phase 3, Whitelist items are part of the expected M1 implementation effort but may be recorded as `BLOCKED` or `INCOMPLETE` without invalidating the core demo unless explicitly promoted into mandatory acceptance criteria.

#### Conditional M1 Scope

A conditional item is required only when the explicitly named enabling condition is satisfied.

If the enabling dependency is unavailable, the implementation must record the condition and resulting deferral rather than silently representing the item as implemented.

#### Blacklist — Excluded from M1 Implementation

An item listed under **Blacklist**, **Future State (Blacklist for M1)**, or an equivalent exclusion heading must not be implemented as part of the declared M1 scope.

Blacklisted items may remain documented because they clarify:

*   The intended longer-term product target.
*   Boundaries between current and future behavior.
*   Features intentionally deferred beyond M1.
*   Functionality an implementation agent must not accidentally build while implementing M1.

A Blacklist item is not necessarily prohibited permanently unless it is explicitly labelled a **Permanent Blacklist**.

#### Future State

Future State requirements provide product-direction context only. They do not contribute to M1 acceptance unless explicitly promoted through a revised PRD and Architecture decision.


### 1.9 M1 Feature Freeze & Delivery Target

> **Decision Record:** On **October 1, 2026**, the team agreed that **October 5, 2026** is the final day for feature-level changes to M1 scope.

After October 5, changes to this PRD should be limited to:

*   Resolving contradictions or ambiguities.
*   Correcting inaccurate product definitions.
*   Clarifying acceptance criteria.
*   Strengthening required tests or evidence obligations.
*   Reconciling PRD and Architecture boundaries.
*   Correcting implementation-significant omissions that are already part of the agreed M1 target.

A genuinely new M1 feature introduced after the feature freeze requires an explicit product decision and corresponding PRD/Architecture revision rather than being added implicitly during implementation.

The required M1 delivery target is **on or before October 31, 2026**.

No arbitrary calendar deadline is assigned to each internal Delivery Phase or Implementation Stage. Progression is governed by the applicable entry requirements, Stage Exit Conditions, Phase Exit Requirements, and M1 Definition of Done defined in this PRD.


---

## 2. Domain Policy & Restrictions

### 2.1 Purpose

This section defines the global M1 operating boundaries that apply across Workflow Features, Foundation Features, Vertical Features, and the implementation plan.

Individual feature sections may impose narrower restrictions, but they must not silently weaken the product boundaries established here.


### 2.2 M1 Domain Boundary

The M1 Phase 1 system is restricted to the **Scientific Research** workflow lane.

Within this lane, the product may:

*   Interpret a scientific or technical research objective.
*   Retrieve and organize permitted supporting evidence.
*   Generate evidence-grounded candidate ideas.
*   Select one opportunity for investigation.
*   Form a falsifiable technical hypothesis.
*   Construct a bounded proof of concept.
*   Compare a baseline against a treatment.
*   Evaluate the empirical result.
*   Produce a traceable scientific research report.

General-purpose autonomous software engineering, arbitrary workflow generation, and unrelated task domains are not part of the Phase 1 production path.


### 2.3 User and Deployment Boundary

AI4Research provides a **user-scoped research experience with a hybrid target deployment model**.

The product separates durable user/account state from the execution environments used to perform research work.

For M1:

*   Every research run must be attributable to one user, workspace, and run identity.
*   Account/profile persistence must remain logically separate from research execution so durable user state can be cloud-backed without changing workflow semantics.
*   Execution that requires user-owned project assets, local model bridges, untrusted POC code, protected research data, or user-specific RSI may occur inside an authorized local execution environment.
*   User-specific configuration, Capability Capsule selections/versions, research artifacts, and execution evidence must remain reproducibly attributable to the user and run that produced them.
*   Local-only operating-system identity must not be treated as a permanent product invariant.

M1 does not require:

*   Enterprise organization tenancy or shared collaborative workspaces.
*   Distributed remote worker fleets.
*   Cloud execution of untrusted POC or RSI-generated code.
*   Organization-wide quota, chargeback, or billing infrastructure.
*   Distributed cluster scheduling.

The Architecture Design specification owns the exact split between cloud-backed persistence and local execution while preserving these product-level boundaries.


### 2.4 Input and External Evidence Policy

M1 may consume:

*   Natural-language user research requests.
*   Permitted local reference documents.
*   Explicitly supplied project/code assets.
*   Explicitly supplied validation resources.
*   Bounded external academic evidence retrieved through approved Search & Ideation capabilities.

The Phase 1 workflow must not autonomously:

*   Perform unconstrained open-web crawling.
*   Clone arbitrary external repositories during intake.
*   Download undeclared validation datasets.
*   Manufacture missing evidence and represent it as observed or supplied.
*   Expand the search domain beyond explicitly permitted connectors and bounds.


### 2.5 Scientific Integrity Policy

Scientific evaluation must remain separated from hypothesis generation and implementation.

Before empirical execution begins, the workflow must establish and freeze the relevant:

*   Technical claim.
*   Experimental baseline.
*   Independent and dependent variables.
*   Validation resource.
*   Measurement definitions.
*   Experimental procedure.
*   Acceptance or falsifiability conditions.

Downstream components must not:

*   Change thresholds after observing results.
*   Substitute more favorable evaluation data.
*   Change measurement definitions to improve the result.
*   Omit the required baseline comparison.
*   Manufacture empirical measurements.
*   Treat unsupported evidence as validated evidence.

Stage 3.7 owns empirical execution and evidence collection.

Stage 3.8 owns scientific interpretation.

Section 4.2 owns infrastructure admissibility and workflow release control.


### 2.6 Capability and Agent Boundary

Every governed agent action must remain within the active Node Execution Contract and the admitted declarations of the Capability Capsules invoked by that node.

A Node Execution Contract may narrow the permissions of a Capability Capsule for a specific execution, but it may not grant tools, effects, resources, interfaces, or behaviour that the admitted capsule declaration does not permit.

Agents must not:

*   Invoke unauthorized tools.
*   Produce undeclared side effects.
*   Modify artifacts outside their assigned responsibility.
*   Alter upstream scientific acceptance criteria.
*   Expand their own permissions.
*   Bypass the Evaluator Gate.
*   Represent an unexecuted action as completed.
*   Silently rewrite another stage's authoritative artifact.


### 2.7 Workflow Autonomy Boundary

The Phase 1 production workflow is fixed and sequential.

It does not permit:

*   Live DAG restructuring.
*   Autonomous insertion or removal of workflow stages.
*   Parallel hypothesis swarms.
*   Unbounded autonomous retries.
*   Autonomous self-healing execution loops.
*   Silent replanning after a failure.
*   Automatic conversion of a failed gate into a pass.

Dynamic planning and routing behaviors may occur only within the governed M1 Delivery Phase 3 Dynamic System Integration pathway and must preserve the deterministic Phase 1 fallback together with all applicable gate, evidence, security, capability-admission, and Node Execution Contract requirements.


### 2.8 Evaluation and Evidence Policy

The Evaluator Gate is the authoritative infrastructure release boundary for governed nodes.

M1 evaluation uses:

1. **Tier 1 deterministic checks** for mechanically decidable contract, schema, execution, budget, tool, security, and evidence conditions.
2. **Tier 2 independent semantic verification** for relevant correctness, evidence support, logical consistency, citation integrity, and node-specific semantic obligations.

A mandatory Tier-1 failure prevents Tier 2 execution.

The Verifier is read-only with respect to the artifact under review.

Material claims and important execution outcomes must remain traceable to submitted evidence.


### 2.9 Execution and Security Boundary

AI-generated executable code is treated as untrusted.

M1 requires an execution boundary that:

*   Restricts generated code to authorized local resources.
*   Prevents unauthorized host filesystem access.
*   Prevents undeclared network or system-level effects.
*   Restricts tool execution to declared permissions.
*   Preserves evidence of relevant execution behavior.
*   Produces an infrastructure failure when mandatory security boundaries are violated.

The precise technical sandbox, IPC, privilege, filesystem, and process-isolation implementation is owned by the Architecture Design specification, subject to these product-level requirements.


### 2.10 Data and Traceability Boundary

M1 separates agent working context from authoritative system evidence.

Agent memory may contain the compact information needed for reasoning.

Raw runtime evidence—including benchmark logs, execution traces, gate evidence, produced artifacts, and run records—must be preserved through the Data Foundations system rather than relying solely on agent memory.

Artifacts and evidence must remain attributable to the relevant run, stage, and producing capability.


### 2.11 RSI Boundary

RSI remains separate from the live Phase 1 research workflow.

Within M1, RSI may only modify explicitly permitted implementation-level aspects of eligible Capability Capsules.

RSI must not autonomously:

* Change workflow contracts or required artifact semantics.
* Change Evaluator, Verifier, gate, check, or acceptance policy.
* Change the live DAG or workflow-stage ownership.
* Modify model weights.
* Expand or rewrite its own mutation permissions.
* Modify security, resource, interface, or effect boundaries designated as non-evolvable.
* Access hidden fixture contents, expected outputs, per-case hidden results, or other referee-only evaluation material.
* Modify, select, or author the hidden tests used to evaluate its own candidate versions.
* Tamper with evaluation evidence, audit records, scoring rules, or promotion records.
* Promote or activate its own generated capability versions into production use.

Hidden evaluation must remain independent of the RSI proposer and the candidate under evaluation. The RSI loop may receive only the bounded evaluation information required by the approved M1 scoring process and must not receive hidden fixture contents.

Any detected attempt to escape the permitted mutation scope, access protected evaluation material, tamper with the referee or its evidence, or bypass promotion controls must halt the affected RSI session, preserve attributable evidence, and require human review before another session proceeds.

Activation of an RSI-generated version requires the admission and human-activation process defined in Section 4.4.


### 2.12 M1 Global Non-Goals

The following behaviors are outside the M1 Delivery Phase 1 deterministic baseline. Items explicitly assigned to M1 Delivery Phase 3 Dynamic System Integration remain within M1 only to the extent defined by the applicable Phase 3 requirements; all other items below remain excluded unless explicitly promoted through a revised product and architecture decision:

*   Dynamic production workflow generation.
*   Unbounded parallel multi-agent research swarms outside the governed Agent Team / Cluster Mode behavior explicitly defined for M1 Delivery Phase 3.
*   Parallel hypothesis execution.
*   Distributed multi-host execution.
*   Multi-user enterprise tenancy.
*   Autonomous defect-repair loops.
*   Dynamic Evaluator generation.
*   Multi-reviewer voting or debate.
*   Live RSI modification of the workflow.
*   Automatic RSI promotion.
*   Model training or fine-tuning.
*   Cloud deployment of generated artifacts.
*   Automatic external publication.
*   Enterprise-scale graph, message-bus, billing, identity, or observability infrastructure.



### 3.0 Codex CLI Integration (Priority Unblocker)

**Description:** A temporary, high-priority adapter that bridges local JiuwenSwarm execution to our active Codex subscription. This bypasses the need for enterprise API keys and unblocks all downstream pipeline testing. 

#### 3.0.1 Existing Implementation Verification & Refactor
*   **Definition & Expectation:** The agent must inspect the repository for the developer's existing Codex CLI adapter code, verify it correctly intercepts OpenJiuwen's native API calls, and refactor it for stability if necessary.
*   **Whitelist (M1 Scope):**
    *   Intercept native OpenJiuwen model invocation requests (e.g., standard OpenAI-compatible `/v1/chat/completions` calls).
    *   Route intercepted requests through the local active Codex CLI process.
    *   Return parsed responses back to the OpenJiuwen runtime in the standard expected format.
    *   **Secure Local IPC Bootstrapping:** Expose the Codex CLI adapter only through a local Unix Domain Socket on POSIX systems, or the equivalent local named-pipe mechanism where required. The IPC endpoint must use restrictive local permissions (e.g., `0600`) and must not expose a TCP listener. Each adapter session must also use an ephemeral session credential so requests can be bound to the active JiuwenSwarm execution context.
*   **Blacklist (Excluded from M1):**
    *   Building a custom local proxy server from scratch (leverage the existing CLI adapter code).
    *   Handling complex multi-turn conversational streaming (stick to synchronous, single-turn completion requests for the DAG).
*   **Dependencies:**
    *   *Requires Input from:* Any SwarmFlow node requesting LLM generation.
    *   *Provides Output to:* The active DAG execution context.

#### 3.0.2 Abstraction for "Endpoint of Last Resort"
*   **Definition & Expectation:** Structures the CLI adapter cleanly so that, rather than being deleted when API keys arrive, it can be handed off to the Model Routing intern to be registered as a permanent fallback pathway.
*   **Whitelist (M1 Scope):**
    *   Wrap the adapter in a standardized Python class/interface that mimics a standard model provider endpoint.
    *   Log adapter timeouts or authentication drops to the local telemetry run-tree.
*   **Blacklist (Excluded from the Phase 1 Baseline):**
    *   Wiring dynamic or heterogeneous model routing directly into the Phase 1 production path before validation. Model-routing development belongs to M1 Delivery Phase 3 Dynamic System Integration and may use mocked endpoints until approved real-model access becomes available. The static Codex CLI route remains the deterministic fallback until an alternate route satisfies the required Phase 3 validation and approval conditions.
*   **Dependencies:**
    *   *Provides Output to:* 4.3 Foundational Models & Routing (for future integration).



### 3.1 Ingestion

**Description:** The deterministic front-door of the AI4Research workstation. It captures natural-language research requests and extracts text from local reference documents, packaging them into a structured raw input buffer for downstream compilation.

#### 3.1.1 Request Capture & Channel Signal Intake
*   **Definition & Expectation:** Receives the user's initial research question and desired outcome without prematurely treating it as a formal requirement.
*   **Whitelist (M1 Scope):**
    *   Capture raw natural language string via CLI argument (e.g., `--topic`).
    *   Capture raw natural language string via native OpenJiuwen Web UI prompt box (`localhost:5173`).
*   **Blacklist (Excluded from M1):**
    *   Integration with external chat channels (Slack, WeChat, Feishu, Discord) is strictly excluded for M1.
    *   Voice-to-text intake.
*   **Dependencies:**
    *   *Requires Input from:* Human User.
    *   *Provides Output to:* 3.1.5 Intake Qualification.

#### 3.1.2 User-Supplied Material & Execution Asset Import

*   **Definition & Expectation:** Imports the local reference materials, project assets, and validation resources explicitly supplied by the user for the current research run. Research documents are extracted into the reasoning context, while executable project assets and datasets remain separately bound workspace resources for downstream Builder and Benchmarking stages.

*   **Whitelist (M1 Scope):**
    *   Read research/reference documents placed in a designated local input directory such as `./workspace/input/docs/`.
    *   Extract raw text from `.txt`, `.md`, and `.pdf` reference documents.
    *   Bind a user-supplied local project/code directory such as `./workspace/input/repo/` to the active run without automatically cloning or modifying external repositories.
    *   Bind user-supplied validation data under a designated path such as `./workspace/input/datasets/` for later use by Stage 3.5 experimental design and Stage 3.7 benchmarking.
    *   Register each resource with its local path, resource type (`reference_document`, `project_asset`, or `validation_data`), and active `run_id`.
    *   Keep executable project assets and validation datasets separate from the raw text buffer unless a downstream capsule explicitly requires their content.

*   **Blacklist (Excluded from M1):**
    *   Live internet scraping during ingestion.
    *   Direct GitHub repository cloning.
    *   Autonomous downloading of external datasets.
    *   Complex document chunking/vectorization.
    *   Text extraction from proprietary Office formats (`.docx`, `.pptx`).

*   **Dependencies:**
    *   *Requires Input from:* Local filesystem and user-supplied workspace resources.
    *   *Provides Output to:* 3.1.5 Intake Qualification, with project assets and validation resources additionally bound to the active SwarmFlow run for downstream use.

#### 3.1.3 Intake Context Binding
*   **Definition & Expectation:** Binds the intake materials to the authorized user, session, and workspace.
*   **Whitelist (M1 Scope):**
    *   Bind the active user/account identity to the authorized local execution profile, workspace, and current `run_id`.
    *   Map run-specific file ingestion strictly to the active SwarmFlow run and workspace.
*   **Blacklist (Excluded from M1):**
    *   Multi-tenant enterprise SSO (Single Sign-On) authentication.
    *   Implicit reuse of run-bound intake materials, execution state, or workspace artifacts across separate research runs without explicit user/account and workspace binding.
*   **Dependencies:**
    *   *Requires Input from:* `jiuwenswarm` runtime environment.

#### 3.1.4 Real-Time Deduplication & Provenance Registration
*   **Definition & Expectation:** Filters malformed content, canonicalizes inputs, and records origin metadata (timestamp, access path) for the run tree.
*   **Whitelist (M1 Scope):**
    *   Programmatic file size limits (e.g., reject files $>50\text{MB}$).
    *   Record local file paths, file sizes, and ingest timestamps into the SwarmFlow telemetry log.
*   **Blacklist (Excluded from M1):**
    *   LLM-based semantic deduplication of overlapping documents.
    *   Cryptographic hashing/signing of intake documents.
*   **Dependencies:**
    *   *Provides Output to:* `jiuwenswarm` Task Memory.

#### 3.1.5 Intake Qualification
*   **Definition & Expectation:** Checks readability and minimum completeness, emitting a qualified intake package or an explicit rejection.
*   **Whitelist (M1 Scope):**
    *   Deterministic Python assertions: Fail and halt if the user prompt string is empty.
    *   Deterministic Python assertions: Fail and halt if the specified input directory is unreadable.
    *   Output the combined prompt and extracted document text as a single in-memory dictionary.
*   **Blacklist (Excluded from M1):**
    *   LLM-based evaluations of whether the prompt makes logical sense (this is deferred to the Section 4.2 Evaluator Gate).
*   **Dependencies:**
    *   *Requires Input from:* 3.1.1 Request Capture and 3.1.2 Material Import.
    *   *Provides Output to:* 3.2 Requirement Compilation.



### 3.2 Requirement Compilation

> **External Dependency Boundary (Intention Compiler):** The M1 Delivery Phase 1 behavior defined in this section is the authoritative deterministic fallback for implementation. It must not depend on completion of the externally developed advanced Intention Compiler. The Phase 1 path uses a bounded, one-shot compiler that produces the standard `Research_Brief.json` contract required by the fixed SwarmFlow workflow. Dynamic, interactive, or externally developed Intention Compiler behavior belongs to M1 Delivery Phase 3 Dynamic System Integration. The Phase 1 compiler remains the required fallback pathway regardless of Phase 3 integration status.

**Description:** An agentic prompt parser that transforms the raw natural-language intake buffer into a standardized, schema-bound Research Brief. This stage acts as the semantic compiler, defining the strict boundaries and metrics used by all downstream agents.

#### 3.2.1 Intent Interpretation
*   **Definition & Expectation:** Determines the user's actual problem, desired change, and deliverable without prematurely selecting a solution.
*   **Whitelist (M1 Scope):**
    *   Execute a single-turn, one-shot LLM generation to extract the core research objective from the raw intake buffer.
*   **Blacklist (Excluded from M1):**
    *   Autonomous ideation or solution generation (deferred to Stage 3.3).
*   **Dependencies:**
    *   *Requires Input from:* 3.1 Ingestion (Qualified Intake Package).

#### 3.2.2 Context Scoping
*   **Definition & Expectation:** Resolves applicable context, affected entities, inclusions, exclusions, and the boundary of the decision to support.
*   **Whitelist (M1 Scope):**
    *   Extract explicit `in_scope` and `out_of_scope` parameters into the JSON schema based *only* on the provided intake text.
*   **Blacklist (Excluded from M1):**
    *   Automated web searching to fill in missing context.
*   **Dependencies:**
    *   *Provides Output to:* Stage 3.3 (Search & Ideation) to constrain the search space.

#### 3.2.3 Ambiguity Resolution
*   **Definition & Expectation:** Finds missing information, conflicting instructions, and undefined terms, and resolves them through focused questions or explicit defaults.
*   **Whitelist (M1 Scope):**
    *   Apply hardcoded, conservative defaults for missing parameters (e.g., if no hardware is specified, default to `single_gpu`).
*   **Blacklist (Excluded from the Phase 1 Baseline):**
    *   Interactive, multi-turn clarification dialogues with the human user. This behavior belongs to M1 Delivery Phase 3 Dynamic Intention Compiler Integration and is not required for the deterministic Phase 1 fallback.

#### 3.2.4 Constraint Resolution
*   **Definition & Expectation:** Identifies and reconciles scope, time, cost, data, safety, policy, tool, and environment constraints.
*   **Whitelist (M1 Scope):**
    *   Extract stated compute limits (token budgets, runtime limits, hardware targets).
*   **Blacklist (Excluded from M1):**
    *   Dynamic profiling or scanning of the user's local system resources to auto-determine constraints.

#### 3.2.5 Requirement Prioritization
*   **Definition & Expectation:** Separates mandatory outcomes, preferences, tradeable qualities, dependencies, and exclusions.
*   **Whitelist (M1 Scope):**
    *   Categorize metrics into a simple binary JSON array of `mandatory_requirements` vs `optional_preferences`.

#### 3.2.6 Acceptance Definition
*   **Definition & Expectation:** Captures the user's observable target outcomes, required metrics, constraints, and product-level success expectations without prematurely defining the final experimental verdict.
*   **Whitelist (M1 Scope):**
    *   Record concrete user-level target metrics and constraints (e.g., desired latency reduction, maximum permitted memory overhead, required hardware bounds).
    *   Preserve these targets in the `Research_Brief.json` so downstream experimental design remains traceable to the original user objective.
*   **Dependencies:**
    *   *Provides Output to:* Stage 3.5 Hypothesis Generation, which converts the relevant user-level targets and scientific design into immutable, experiment-specific success, falsification, and permitted classification rules inside `Hypothesis_Blueprint.json`.

#### 3.2.7 Requirement Contract Confirmation
*   **Definition & Expectation:** Assembles a versioned contract with executable task semantics and records user confirmation or authorized assumptions.
*   **Whitelist (M1 Phase 1 Scope - Static Baseline):**
    *   Package all extracted fields (Intent, Scope, Constraints, Metrics) into a final standard `Research Brief` JSON payload.
    *   Pass this static JSON file explicitly to the deterministic SwarmFlow script to trigger the next DAG node.
*   **Whitelist (M1 Delivery Phase 3 Scope - Dynamic System Integration):**
    *   Pass the compiled `Research Brief` contract directly to the JiuwenSwarm Leader Agent to test dynamic intent resolution and autonomous task routing.
*   **Blacklist (Excluded from M1 Entirely):**
    *   Halting the execution to wait for asynchronous human approval before proceeding.
*   **Dependencies:**
    *   *Provides Output to:* 4.2 Evaluator Gate (for verification before passing to Stage 3.3).


### 3.3 Search & Ideation

**Description:** The primary literature retrieval and synthesis node. This stage consumes the structured Research Brief and executes both local and bounded external search queries to generate an initial set of evidence-grounded candidate ideas.`search_capsule.md` provides the primary Search & Ideation capability used by this node. The runtime Node Execution Contract may additionally bind other admitted supporting Capability Capsules required for retrieval, evidence handling, citation, or related bounded work.

#### 3.3.1 Search Strategy Formation
*   **Definition & Expectation:** Turns the requirement contract into technical themes, source families, queries, time horizons, and coverage targets.
*   **Whitelist (M1 Scope):**
    *   Execute a single LLM prompt (guided by `search_capsule.md`) to generate a static list of keyword queries based on the `Research Brief` JSON payload.
*   **Blacklist (Excluded from M1):**
    *   Dynamic query reformulation (re-writing queries on the fly if initial results are poor).
*   **Dependencies:**
    *   *Requires Input from:* 3.2 Requirement Compilation (Research Brief JSON payload).

#### 3.3.2 Multi-Source Signal Discovery (Hybrid Retrieval)
*   **Definition & Expectation:** Uses the search strategy to retrieve grounding evidence from both local context and external academic literature.
*   **Whitelist (M1 Scope):**
    *   Invoke the whitelisted `deepsearch` operator to execute keyword queries against the local document buffer populated during 3.1 Ingestion.
    *   Execute bounded, structured external queries against designated academic APIs (e.g., arXiv, Semantic Scholar) using `deepsearch`'s built-in connectors.
    *   Enforce a strict programmatic Top-K limit (e.g., maximum 5 external papers per query) to prevent rate limits and context bloat.
*   **Blacklist (Excluded from M1):**
    *   Unconstrained open-web scraping, headless browser crawling, or navigating unstructured sites (e.g., live Google Search scraping).
    *   Parallel multi-agent search swarms (execution must remain a single, linear process).
*   **Dependencies:**
    *   *Requires Service from:* The admitted `search_capsule.md` Capability Capsule and its explicitly allowlisted `deepsearch` operator/connectors, governed through Section 4.1 Capability Capsule.

#### 3.3.3 Source Qualification & Technical Signal Extraction
*   **Definition & Expectation:** Screens discovered material for intent relevance and extracts claims, data, methods, benchmarks, and limitations.
*   **Whitelist (M1 Scope):**
    *   Extract exact verbatim text chunks from the retrieved local and external documents that match the keyword queries.
*   **Blacklist (Excluded from M1):**
    *   LLM-based evaluations of author authority, publisher bias, or geographic source checking.

#### 3.3.4 Signal Organization & Trend Analysis
*   **Definition & Expectation:** Clusters related findings, maps convergence/divergence, and detects momentum, missing capabilities, and technical white spaces.
*   **Whitelist (M1 Scope):**
    *   Group the extracted raw text chunks by the keyword query that triggered them into a standardized JSON array.
*   **Blacklist (Excluded from M1):**
    *   Automated historical trend analysis (e.g., mapping research momentum over time) or complex cross-domain transfer mapping.

#### 3.3.5 Idea Generation
*   **Definition & Expectation:** Expands a diverse candidate set from signal clusters, gaps, adjacencies, cross-domain transfers, and contrarian combinations.
*   **Whitelist (M1 Scope):**
    *   Execute a single-turn LLM generation to synthesize the clustered text chunks (from 3.3.4) into 1 to 3 concrete "Candidate Ideas."
    *   Bind explicit citations (document title, author, or local filename) from the source material to each generated idea.
*   **Blacklist (Excluded from M1):**
    *   Generating contrarian or highly speculative ideas not directly supported by the retrieved text chunks.

#### 3.3.6 Search Coverage Review & Result Compilation
*   **Definition & Expectation:** Tests coverage and combines parallel search outputs, resolving semantic duplicates before narrowing the candidate space.
*   **Whitelist (M1 Scope):**
    *   Package the synthesized "Candidate Ideas" and their mapped citations into a standard `Candidate_Set.json` payload.
*   **Blacklist (Excluded from M1):**
    *   LLM-based self-reflection loops to check if the search was "broad enough" before moving on (intra-node recursive loops are deferred).
*   **Dependencies:**
    *   *Provides Output to:* 4.2 Evaluator Gate for verification of schema validity, evidence obligations, and enforceable runtime-budget constraints before passing to Stage 3.4 Idea Screening. Token-budget fields remain recorded constraints and become mechanically blocking only when the active model endpoint exposes sufficiently reliable usage telemetry.



### 3.4 Idea Identification / Screening / Opportunity Selection

> **Architectural Distinction (3.3 vs. 3.4):** While Stage 3.3 is **divergent** (broadly exploring the literature to synthesize all scientifically valid possibilities), Stage 3.4 is **convergent and pragmatic**. Its objective is not to generate new concepts or re-verify literature claims, but to ruthlessly evaluate incoming candidates against the user's explicit project constraints (compute budget, technical feasibility, and implementation scope). It prunes non-viable proposals down to a single winning opportunity.

**Description:** The fixed-rubric opportunity-screening node of the workstation. This stage ingests the evidence-grounded candidate ideas from Search & Ideation and evaluates each candidate using a bounded, single-pass LLM assessment against fixed scoring dimensions adapted from `sciencediscovery/assessment-screening`: scientific novelty, technical feasibility, and compute alignment. The semantic scores are then passed through deterministic arithmetic and ranking logic to select the single highest-scoring opportunity for the M1 pipeline. `screening_capsule.md` provides the primary opportunity-screening capability for this node. The node may use additional admitted supporting Capability Capsules only when they are explicitly bound by its Node Execution Contract.

#### 3.4.1 Candidate Consolidation
*   **Definition & Expectation:** Combines candidate search outputs, resolves semantic duplicates, and preserves variants whose assumptions, evidence, or opportunity boundaries materially differ.
*   **Whitelist (M1 Scope):**
    *   Perform a single-pass consolidation over the incoming `Candidate_Set.json` to merge near-identical proposals.
    *   Preserve distinct idea variants that rely on different underlying mechanisms or baseline papers.
*   **Blacklist (Excluded from M1):**
    *   Iterative multi-round clustering or cross-database re-indexing.
*   **Dependencies:**
    *   *Requires Input from:* 3.3 Search & Ideation (`Candidate_Set.json`).

#### 3.4.2 Idea Identification
*   **Definition & Expectation:** Converts meaningful signal combinations and gaps into discrete candidate ideas with a recognizable technical value proposition.
*   **Whitelist (M1 Scope):**
    *   Map each consolidated candidate to an explicit technical problem statement and proposed mechanism of action.
*   **Blacklist (Excluded from M1):**
    *   Unconstrained brainstorming or generating brand-new ideas not grounded in the ingested evidence bundle.

#### 3.4.3 Idea Card Formation
*   **Definition & Expectation:** Forms the governing Idea Card containing the candidate's opportunity, relevance, linked evidence, assumptions, novelty, uncertainty, risks, and open questions.
*   **Whitelist (M1 Scope):**
    *   Format each idea into a standardized JSON schema containing: `idea_id`, `title`, `summary`, `linked_citations` (file/title references), `core_assumptions`, and `identified_risks`.
*   **Blacklist (Excluded from M1):**
    *   Unstructured free-form text descriptions lacking schema validation.

#### 3.4.4 Opportunity Definition
*   **Definition & Expectation:** States the unmet need, technical bottleneck, missing capability, or unexploited combination that makes the idea actionable.
*   **Whitelist (M1 Scope):**
    *   Extract a dedicated `opportunity_statement` field articulating the precise bottleneck in the literature and why the proposed method addresses it.
*   **Blacklist (Excluded from M1):**
    *   Commercial business case generation, ROI projections, or addressable market sizing.

#### 3.4.5 Technical Opportunity Screening (Fixed-Rubric LLM Evaluation)
*   **Definition & Expectation:** Screens novelty, evidence maturity, technical feasibility, compute alignment, and the existence of a credible verification path using ported rubrics from `sciencediscovery/assessment-screening`.
*   **Whitelist (M1 Scope):**
    *   Execute a single-turn LLM evaluation scoring each Idea Card on three 1–5 scales:
        1.  *Novelty:* Difference from baseline approaches cited in the brief.
        2.  *Technical Feasibility:* Plausibility of implementation within standard PyTorch/Python frameworks.
        3.  *Compute Alignment:* Strict compliance with the hardware bounds defined in `Research Brief` (e.g., single GPU).
    *   Require a concise, evidence-grounded 1-sentence justification for each numerical score.
*   **Blacklist (Excluded from M1):**
    *   Multi-agent consensus voting or dynamic peer-review debate simulations.
    *   Autonomous live code execution to test feasibility prior to POC stage.

#### 3.4.6 Strategic Opportunity Screening
*   **Definition & Expectation:** Screens user value, timing, safety, legal/licensing exposure, dependencies, and resource implications.
*   **Whitelist (M1 Scope):**
    *   Deterministic filter checking for dependency conflicts (e.g., blacklisting ideas that require unreleased proprietary models or closed datasets).
*   **Blacklist (Excluded from M1):**
    *   Complex IP/patent search or formal legal compliance auditing.

#### 3.4.7 Opportunity Portfolio Prioritization
*   **Definition & Expectation:** Ranks and selects a bounded, diverse opportunity portfolio using transparent criteria, recording reasons for deferred or rejected directions.
*   **Whitelist (M1 Scope):**
    *   Calculate a composite score: $Score = Novelty + Feasibility + ComputeAlignment$.
    *   Rank all cards and select the Top-1 highest-scoring opportunity card to advance down the deterministic SwarmFlow pipeline.
    *   Append rejection/deferral rationales for all lower-ranked candidates into the output metadata.
    *   Package the winning card into `Opportunity_Card.json`.
*   **Blacklist (Excluded from M1):**
    *   Interactive human-in-the-loop idea selection (M1 execution proceeds automatically with the top rubric winner).
*   **Dependencies:**
    *   *Provides Output to:* 4.2 Evaluator Gate (for schema and scoring validation prior to handoff to 3.5 Generate Technical Claims & Hypothesis).



### 3.5 Generate Technical Claims & Hypothesis

**Description:** The experimental design node. This stage translates the single winning Opportunity Card from Stage 3.4 into a rigid, testable blueprint. It explicitly defines the dependent/independent variables, expected performance metrics, and success criteria required by the downstream POC Implementation node. `hypothesis_capsule.md` provides the primary hypothesis-design capability for this node. Any additional supporting capabilities must be explicitly admitted and bound through the node's runtime Node Execution Contract.

#### 3.5.1 Research Question & Technical Claim Formation
*   **Definition & Expectation:** Converts the selected opportunity into a specific research question and testable technical claim, clarifying the research object, expected effects, and applicable situations.
*   **Whitelist (M1 Scope):**
    *   Formulate a direct, one-sentence technical claim (e.g., "Applying 4-bit quantization to the attention weights will reduce VRAM usage by 40% without degrading accuracy by more than 2%").
*   **Blacklist (Excluded from M1):**
    *   Generating multiple competing technical claims for parallel testing. (M1 enforces a single deterministic path).
*   **Dependencies:**
    *   *Requires Input from:* 3.4 Idea Screening (`Opportunity_Card.json`).

#### 3.5.2 Claim, Evidence, Data & Method Modeling (Benchmark Definition)
*   **Definition & Expectation:** Sets up the claim, the data required, the means of measuring, the approaches, and the relationship between the baseline and missing evidence.
*   **Whitelist (M1 Scope):**
    *   Explicitly define the independent variable (what the POC will change) and the dependent variable (what the Benchmark will measure).
    *   Identify the exact baseline state/model required for comparison to ensure performance is evaluated strictly on the delta ($\Delta$).
    *   Lock the evaluation to a static, standard, or user-supplied validation dataset ingested in Stage 3.1.
*   **Blacklist (Excluded from M1):**
    *   Complex data modeling that requires generating synthetic datasets or scraping new external data to test the claim (to prevent the LLM from manufacturing test data tailored to its implementation).

#### 3.5.3 Hypothesis Pool & Mechanism Formation
*   **Definition & Expectation:** Forms the hypothesis from the opportunity and defines the exact mechanism to test it.
*   **Whitelist (M1 Scope):**
    *   Define the concrete technical mechanism (e.g., "Implement the quantization logic in `model.py` at line 45").
*   **Blacklist (Excluded from M1):**
    *   Automated counter-evidence probing or iterative parameter evolution (explicitly deferred to the Future State in M1 objectives).

#### 3.5.4 Falsifiability Screening & Hypothesis Contracting (Anti-Overfitting Contract)
*   **Definition & Expectation:** Determines if the hypothesis can be overthrown by obtained data or methods. Forms the formal, immutable contract for testing.
*   **Whitelist (M1 Scope):**
    *   Pre-Registered Outcome Boundaries: Define an explicit success threshold and an explicit falsification threshold for each required experimental metric. Results that fall between the pre-registered success and falsification boundaries are classified as INCONCLUSIVE unless the Hypothesis Blueprint explicitly defines another permitted classification before execution begins.
    *   Immutable Evaluation Contract: Freeze the success thresholds, falsification thresholds, and permitted classification rules in Hypothesis_Blueprint.json before any POC code is generated or empirical results are observed. Downstream stages may apply these rules but may not modify them after observing results.
*   **Blacklist (Excluded from M1):**
    *   Dynamic statistical power analysis or automated p-value threshold generation (keep falsifiability tied to deterministic bounds).

#### 3.5.5 Verification-Ready POC Design
*   **Definition & Expectation:** Designs the minimum viable verification plan, defining inputs, outputs, index requirements for success, needed resources, restraints, and verification steps.
*   **Whitelist (M1 Scope):**
    *   Output the finalized experimental design as a `Hypothesis_Blueprint.json` payload containing the methodology, constraints, and the step-by-step verification plan.
    *   Enforce role separation: Downstream nodes can read this blueprint to build the execution harness, but cannot alter the validation dataset path, the measurement functions, or the acceptance thresholds.
*   **Blacklist (Excluded from M1):**
    *   Writing the actual execution code (this is strictly reserved for Stage 3.6 POC Implementation).
*   **Dependencies:**
    *   *Provides Output to:* 4.2 Evaluator Gate (for schema and falsifiability validation prior to handoff to 3.6 POC Implementation).


### 3.6 POC Implementation

> **Node Contract & Builder Execution Note:** Stage 3.6 is instantiated as one governed workflow node with a run-specific Node Execution Contract. The contract binds the node's objective, upstream `Hypothesis_Blueprint.json`, required POC outputs, execution/evidence obligations, resource and effect constraints, and the admitted capabilities available for construction. `poc_capsule.md` provides the primary POC-construction capability, while the dedicated Builder defined in Section 4.9 provides the specialized executable-artifact construction function. Additional admitted supporting capabilities such as bounded code search may also participate when explicitly bound by the Node Execution Contract. The Capability Capsules provide reusable capabilities; they do not independently define the run-specific node contract.

**Description:** The execution node. This stage consumes the rigid `Hypothesis_Blueprint.json` generated in Stage 3.5 and translates it into a reproducible proof-of-concept Python script. It acts strictly as an assembly phase: it writes the code, wires the components together, and zips them into an artifact that is benchmark-ready. The node's runtime Node Execution Contract governs the execution-specific objective, permissions, evidence obligations, and required outputs. `poc_capsule.md`, the Builder, and any other explicitly bound supporting Capability Capsules provide the reusable capabilities used to satisfy that contract.

#### 3.6.1 POC Implementation Environment Preparation
*   **Definition & Expectation:** Sets up the isolated environment needed for the POC, including dependencies, data paths, runtime constraints, and compute resources.
*   **Whitelist (M1 Scope):**
    *   Map the user-supplied local workspace files (ingested in 3.1) and static validation datasets into a standardized sandboxed directory (`/workspace/poc/`).
    *   Generate a static `requirements.txt` based on the framework requirements detailed in the `Research Brief`.
*   **Blacklist (Excluded from M1):**
    *   Runtime Dependency Mutation: The Builder may declare dependencies through the generated requirements.txt, but it may not install packages, discover new dependencies, or modify the declared dependency set during POC construction. Installation of the frozen dependency declaration occurs only during Stage 3.7 sandbox provisioning.
*   **Dependencies:**
    *   *Requires Input from:* 3.1 Ingestion (Local Workspace Directory).

#### 3.6.2 POC Construction (Code Generation)
*   **Definition & Expectation:** Constructs the code, models, and prompts required to validate the POC.
*   **Whitelist (M1 Scope):**
    *   Invoke the whitelisted `CodeSearch` operator to navigate the local repository, perform syntax-aware chunking, and pinpoint the exact file and line numbers required for the intervention.
    *   Generate a standalone, single-file Python patch script (`poc_patch.py`) that implements the technical mechanism defined in the Hypothesis Blueprint.
*   **Blacklist (Excluded from M1):**
    *   Autonomous multi-file refactoring across a large legacy codebase (M1 restricts generation to bounded, minimal test harnesses).
    *   Importing or utilizing OS-level or network-level Python modules (e.g., os, sys, subprocess, requests, urllib, shutil) to mitigate the M1 unconfined execution gap.

#### 3.6.3 POC Component Integration & Configuration
*   **Definition & Expectation:** Connects each part into a workable end-to-end execution path and prepares it for the smoke test.
*   **Whitelist (M1 Scope):**
    *   Generate a `run_benchmark.py` harness script. This script must sequentially connect and execute both the unmodified baseline and the new `poc_patch.py` implementation, ensuring the data flow aligns with the 3.5 blueprint.
*   **Blacklist (Excluded from M1):**
    *   Modifying the pre-registered measurement functions or acceptance thresholds from Stage 3.5.

#### 3.6.4 POC Functional Readiness Validation
*   **Definition & Expectation:** Performs a mechanical smoke test run to ensure the POC compiles, outputs are in the correct format, and failures are observable.
*   **Whitelist (M1 Scope):**
    *   Execute a dry-run syntax check (e.g., `python -m py_compile run_benchmark.py`) to confirm the generated harness is syntactically valid and the output logging format conforms to the JSON schema.
    *   *Anti-Overfitting Note:* This is strictly a mechanical check to ensure the engine turns on. It does not evaluate scientific data or metric results, preserving the immutable baseline locked in during Stage 3.5.
*   **Blacklist (Excluded from M1):**
    *   Automated, iterative defect-repair loops if the syntax check fails. (In M1, syntax failures are recorded and routed to the HITL/Evaluator gate rather than triggering autonomous debugging loops).

#### 3.6.5 Testable POC Artifact Consolidation & Benchmark Handoff
*   **Definition & Expectation:** Organizes the final POC, configuration, dependencies, known constraints, and necessary explanations into a benchmark-ready artifact.
*   **Whitelist (M1 Scope):**
    *   Package `requirements.txt`, `poc_patch.py`, `run_benchmark.py`, and the environment configuration into a standardized `POC_Artifact_Bundle.zip` payload.
    *   This package is fully prepared for execution, but execution itself is deferred. Once passed through the Evaluator Gate, it is handed off to **Stage 3.7 Benchmarking** where the script will actually run and record empirical data.
*   **Blacklist (Excluded from M1):**
    *   Deploying the containerized runtime prototype to external cloud clusters. (M1 benchmarking occurs strictly within the local SwarmFlow execution context).
*   **Dependencies:**
    *   *Provides Output to:* 4.2 Evaluator Gate (for script bounds checking prior to passing to 3.7 Benchmarking).



### 3.7 Scientific Benchmarking (POC Execution)

> **Architectural Note (The Core User Loop):** This node represents the scientific execution of the user's specific POC script within the SwarmFlow DAG. It executes the core value proposition of the platform: *"I have this baseline (uploaded in 3.1), how can I make it better (hypothesized in 3.5 and coded in 3.6), so let's run them side-by-side and compare the results."* This is distinct from the overarching "Phased System Validation" project goal (which measures the AI4Research platform's overall performance). 

**Description:** The empirical validation node. This stage unpacks the `POC_Artifact_Bundle.zip` created in Stage 3.6 and executes the code in a sandboxed runtime environment. It strictly executes the protocol defined in the `Hypothesis_Blueprint.json` to collect metrics on the independent/dependent variables, comparing the baseline against the generated patch. `benchmark_capsule.md` provides the primary benchmarking capability used by this node. The node executes under its run-specific Node Execution Contract, which binds the benchmark protocol, required evidence, applicable limits, and any additional admitted supporting capabilities.

#### 3.7.1 Runtime Provisioning & Artifact Unpacking
*   **Definition & Expectation:** Initializes the secure sandbox and installs the explicit requirements generated during POC assembly.
*   **Whitelist (M1 Scope):**
    *   Unpack `POC_Artifact_Bundle.zip` into the active workspace.
    *   **Unprivileged Virtual Environment:** Provision a dedicated Python virtual environment (`venv`) scoped strictly to `/workspace/poc/` and owned by the unprivileged runner user (e.g., `nobody` or `jiuwen-runner`).
    *   Install only the frozen dependencies declared in requirements.txt within the unprivileged local virtual environment. Stage 3.7 must not add, remove, upgrade, or otherwise modify the declared dependency set during execution.
*   **Blacklist (Excluded from M1):**
    *   Resolving dependency conflicts dynamically. (If the environment fails to build, the run is terminated and sent to human triage to avoid infinite debugging loops).
*   **Dependencies:**
    *   *Requires Input from:* 3.6.5 Testable POC Artifact Consolidation (`POC_Artifact_Bundle.zip`).

#### 3.7.2 Delta Execution (Baseline vs. Treatment)
*   **Definition & Expectation:** Runs the actual test script to generate comparative data, ensuring a mathematically fair evaluation.
*   **Whitelist (M1 Scope):**
    *   **The Baseline:** Execute the user's original, unmodified codebase or foundation model (as defined in Stage 3.1 and 3.2).
    *   **The Treatment:** Execute the modified codebase utilizing the `poc_patch.py` script written by the Builder agent in Stage 3.6.
    *   Run the baseline first, followed immediately by the treatment, using the same declared hardware environment, benchmark configuration, validation data, and random-seed policy to ensure a controlled and comparable delta ($\Delta$).
*   **Blacklist (Excluded from M1):**
    *   Evaluating the patch in isolation without running a live baseline comparison (to prevent static hardware advantages from skewing results).

#### 3.7.3 Empirical Data Collection
*   **Definition & Expectation:** Captures the telemetry, logs, and metric outputs generated by the execution harness using the platform's native memory modules.
*   **Whitelist (M1 Scope):**
    *   Capture raw standard output (`stdout`), standard error (`stderr`), benchmark telemetry, and execution traces through the Section 4.5 Data Foundations run-bundle infrastructure.
    *   Task Memory and Coding Memory may retain compact summaries or references required for downstream agent reasoning, but raw execution logs and large telemetry payloads must remain in the system-level Run Bundle rather than the agent reasoning context.
    *   Parse the specific dependent variables defined in 3.5 (e.g., peak allocated VRAM, tokens/sec, accuracy loss) and format them into a structured `empirical_results.json` file.
*   **Blacklist (Excluded from M1):**
    *   Agent-driven scientific interpretation of the data. This node strictly collects and structures empirical evidence. Scientific interpretation and hypothesis classification are reserved for Stage 3.8 Scientific Evaluation.

#### 3.7.4 Results Consolidation & Handoff
*   **Definition & Expectation:** Packages the raw empirical data alongside the execution logs for final review, acting purely as a clean data handoff.
*   **Whitelist (M1 Scope):**
    *   Bundle `empirical_results.json`, system standard output (`stdout`), and standard error logs (`stderr`) into a final, highly readable `Benchmark_Payload.json`.
*   **Blacklist (Excluded from M1):**
    *   Applying the falsifiability rules or grading the success of the experiment. (This node strictly acts as a data collector).
*   **Dependencies:**
    *   *Provides Output to:* 4.2 Evaluator Gate for infrastructure verification of `Benchmark_Payload.json`, including schema validity, provenance, required benchmark evidence, and conformance to the pre-registered execution protocol.
    *   If the Evaluator Gate returns an advancing infrastructure verdict (`PASS` or `PASS_WITH_KNOWN_LIMITATIONS`), the verified benchmark evidence is released to Stage 3.8 Scientific Evaluation.
    *   Stage 3.8—not the Evaluator Gate—is responsible for interpreting the verified empirical results against the pre-registered hypothesis and producing the scientific verdict.


### 3.8 Scientific Evaluation

> **Capability Binding & Architectural Role:** `scientific_evaluator_capsule.md` provides the primary scientific-evaluation capability for Stage 3.8. The workflow node itself executes under a run-specific Node Execution Contract and may use additional admitted supporting capabilities only when explicitly bound by that contract. This scientific capability is distinct from the infrastructure `verifier_capsule.md` used by the Section 4.2 Evaluator Gate. Stage 3.8 owns scientific interpretation and produces `Evaluation_Verdict.json`; the Evaluator Gate independently verifies that the node satisfied its runtime contract and produced admissible evidence before Delivery is released.

**Description:** The scientific judgement node. This stage synthesizes the empirical benchmark telemetry from Stage 3.7 with the pre-registered hypothesis and falsifiability contract from Stage 3.5. It evaluates experimental validity, traces evidence completeness, classifies the scientific verdict, and documents residual risks and follow-ups without altering the code or running additional iterations.

#### 3.8.1 Evaluation Scope & Evidence Assembly
*   **Definition & Expectation:** Clarifies the strategy and standard used for this evaluation, collecting benchmark results, claims, and relative evidence.
*   **Whitelist (M1 Scope):**
    *   Ingest and bind the `Benchmark_Payload.json` (from 3.7), the immutable `Hypothesis_Blueprint.json` (from 3.5), and the `Research_Brief.json` (from 3.2) into a unified evaluation context.
*   **Blacklist (Excluded from M1):**
    *   Dynamically pulling external leaderboard data or querying live web sources during evidence assembly.
*   **Dependencies:**
    *   *Requires Input from:* 3.7 Scientific Benchmarking (`Benchmark_Payload.json`) and 3.5 Generate Technical Claims & Hypothesis (`Hypothesis_Blueprint.json`).

#### 3.8.2 Evidence Completeness & Provenance Review
*   **Definition & Expectation:** Checks if evidence is complete, source traceable, verifies completeness on key experiments, and detects false or hallucinated materials.
*   **Whitelist (M1 Scope):**
    *   Audit metric values against raw execution standard logs (`stdout` / `stderr`) to ensure results originate directly from sandbox execution rather than hallucinated LLM text.
    *   Verify that all dependent variables declared in the Stage 3.5 blueprint contain non-null empirical entries.
*   **Blacklist (Excluded from M1):**
    *   Cryptographic provenance hashing or multi-node cross-verification.

#### 3.8.3 Experimental, Reasoning & External Validity Review
*   **Definition & Expectation:** Checks experiment design and determines if the results make sense in the external physical and computational world.
*   **Whitelist (M1 Scope):**
    *   Execute a single-turn qualitative sanity check evaluating whether the observed delta ($\Delta$) is physically plausible (e.g., flagging mathematically impossible 1000x speedups or negative memory usage as execution anomalies).
*   **Blacklist (Excluded from M1):**
    *   Automated perturbation testing or running secondary counterfactual benchmarks.

#### 3.8.4 Claim & Acceptance-Criteria Comparison
*   **Definition & Expectation:** Compares the benchmark results against the technical claims, hypothesis, and original acceptance criteria.
*   **Whitelist (M1 Scope):**
    *   Perform a deterministic comparison between empirical performance deltas and the pre-registered falsifiability thresholds locked in Stage 3.5 (e.g., verifying if the measured VRAM reduction meets or exceeds the contracted percentage).
*   **Blacklist (Excluded from M1):**
    *   Post-hoc goalpost shifting or dynamically adjusting the pass/fail margin based on observed results.

#### 3.8.5 Verdict, Blocker & Residual-Risk Classification
*   **Definition & Expectation:** Applies the pre-registered classification rules in `Hypothesis_Blueprint.json` to the admitted benchmark evidence and records the scientific verdict, blockers, and residual risks.
*   **Whitelist (M1 Scope):**
    *   Assign one standardized scientific classification: `PASS`, `FAIL`, `INCONCLUSIVE`, or `CONDITIONALLY_ACCEPTABLE`.
    *   `PASS` may be emitted only when the pre-registered success conditions are satisfied.
    *   `FAIL` may be emitted when the pre-registered falsification conditions are satisfied.
    *   `INCONCLUSIVE` must be emitted when the evidence falls between the pre-registered success and falsification boundaries, is insufficient for the required classification, or otherwise fails to satisfy a more specific pre-registered classification rule.
    *   `CONDITIONALLY_ACCEPTABLE` may be emitted only when `Hypothesis_Blueprint.json` explicitly defined the corresponding conditional classification rule before empirical execution began. It must not be invented post-hoc in response to observed results.
    *   **Scientific vs. Infrastructure Routing Flag:** A scientific `FAIL` is a valid research outcome. If Stage 3.8 itself executed correctly and its evidence is admissible, the Evaluator Gate may return infrastructure `PASS`, and the scientific `FAIL` proceeds unchanged to Stage 3.9 Delivery.
    *   Catalog residual constraints and operational risks in `Evaluation_Verdict.json`.
*   **Blacklist (Excluded from M1):**
    *   Post-hoc creation of new classification criteria.
    *   Multi-agent debate or dynamic consensus voting for verdict assignment.

#### 3.8.6 Refinement & Follow-Up Recording
*   **Definition & Expectation:** Notes down points that need improvement, ensuring no improvements or code modifications are implemented in this step.
*   **Whitelist (M1 Scope):**
    *   Record identified technical bottlenecks, algorithmic limitations, and future research directions into `Evaluation_Verdict.json`.
    *   Enforce a strict read-only constraint: this stage records recommendations and cannot trigger code patches or rerun pipeline nodes.
*   **Blacklist (Excluded from M1):**
    *   Autonomous self-healing, automated code refactoring, or iterative re-benchmarking loops.
*   **Dependencies:**
    *   *Provides Output to:* 3.9 Delivery (`Evaluation_Verdict.json`) via the Evaluator Gate.

### 3.9 Delivery (Report Generation)

> **Capability Binding Note:** `report_capsule.md` provides the primary report-generation capability used by the Delivery node. The node executes under a run-specific Node Execution Contract defining the required deliverables, source artifacts, permitted behavior, and evidence obligations. Additional supporting capabilities may participate only when they are admitted and explicitly bound by that contract.

**Description:** The final synthesis and handoff node. It consumes the gate-admitted `Evaluation_Verdict.json` produced by Stage 3.8 Scientific Evaluation, together with the verified benchmark evidence and original Research Brief. It synthesizes those findings into a standardized markdown report and packages the complete research lifecycle for the user. The Evaluator Gate verifies that the Stage 3.8 output is admissible; it does not replace or independently rewrite the scientific verdict contained within that output.

#### 3.9.1 Delivery Planning & Evidence Handoff
*   **Definition & Expectation:** Defines the target audience, delivery format, delivery content, evidence index, permission, and a handoff checklist.
*   **Whitelist (M1 Scope):**
    *   Ingest the verified `Evaluation_Verdict.json` (from Stage 3.8), the `Benchmark_Payload.json` (from Stage 3.7), and the `Research_Brief` (from Stage 3.2).
    *   Lock the delivery format to the static `sciencediscovery/report-writer` markdown template.
*   **Blacklist (Excluded from M1):**
    *   Dynamically profiling the user or analyzing the audience to invent custom document structures.

#### 3.9.2 User-Facing Deliverable Generation
*   **Definition & Expectation:** Generates the report the user needs, including proposals, technical roadmaps, investment recommendations, papers, posters, rebuttals, or visualizations.
*   **Whitelist (M1 Scope):**
    *   Synthesize the findings, experimental results, and verified citations into a structured markdown report.
    *   Ensure the report explicitly includes the methodology, benchmark analysis, and documented limitations.
*   **Blacklist (Excluded from M1):**
    *   Generating multi-format publication-ready LaTeX manuscripts, executive slide summaries, or interactive HTML dashboards (these are explicitly deferred to the Future State).

#### 3.9.3 Deliverable, Reusable Asset & Knowledge Packaging
*   **Definition & Expectation:** Organizes all the deliverables into a unified package.
*   **Whitelist (M1 Scope):**
    *   Consolidate the final markdown report alongside the POC scripts, environment configurations, and raw empirical data into a single, clean output directory for the user.
*   **Blacklist (Excluded from M1):**
    *   Automatically publishing the reusable knowledge assets to external Git repositories or community registries.

#### 3.9.4 Authorized Distribution, Knowledge Transfer & Lifecycle Closure
*   **Definition & Expectation:** Sends the deliverable to the user, confirms acceptance, completes artifact transferring, saves the success/failure experience, and closes the current workflow lifecycle.
*   **Whitelist (M1 Scope):**
    *   Transfer the final artifacts strictly to the sandboxed user workspace.
    *   Display the final report within the native Web UI (`localhost:5173`) or TUI interface.
    *   Log the completed execution trace to the native `/swarmflows` run-tree monitoring to formally close the SwarmFlow lifecycle.
*   **Blacklist (Excluded from M1):**
    *   Sending automated notifications or attachments through external message channels (like Slack, WeChat, or Discord) during the M1 baseline.



---

## 4. Foundation Features (The Engine)

### 4.1 Capability Capsules

**Description:** Capability Capsules (CCs) are reusable, pre-defined capability definitions and implementations that describe a class of work the AI4Research system knows how to perform. A Capability Capsule defines the capability's interface, permitted behavior, implementation resources, provenance, and governance metadata at a reusable class level.

A Capability Capsule is **not** a run-specific execution contract and is **not** synonymous with a workflow node.

> **Capability Capsule / Node / Contract Distinction:**
>
> *   **Capability Capsule (CC):** A reusable capability definition and implementation package. It declares what the capability can do, the interfaces it supports, the tools/effects/resources it may use, its implementation entry points, its version/provenance, and its governed mutation boundaries.
> *   **Workflow Node:** A runtime unit of work representing a specific objective or task inside the active execution graph. A node may invoke one or more Capability Capsules to achieve that objective.
> *   **Node Execution Contract:** A run-specific binding created when a workflow node is instantiated. It defines the node's current objective, inputs, required outputs, acceptance obligations, resource/effect limits, and the exact admitted Capability Capsule versions available to the node for that execution.
> *   A Node Execution Contract may narrow the permissions declared by a Capability Capsule for a specific run, but it may not silently widen the capsule's declared tools, effects, resources, or interface boundaries.

> **Architectural Note — Capability Evolution:**
> *   **Horizontal — Capability Taxonomy:** Distinct reusable capability classes may exist for different types of work, such as general citation handling versus scientific citation handling. Creating or dynamically discovering new capability classes during the deterministic Phase 1 baseline is outside that baseline.
> *   **Vertical — Implementation Lineage:** A capability may evolve through admitted implementation versions such as `Citing V1 → Citing V2`. Each admitted version retains provenance and lineage information so historical runs can reproduce the exact capability implementation that executed.

#### 4.1.1 Capability Declaration & Assembly

*   **Definition & Expectation:** Defines the reusable declaration, implementation resources, provenance, dependencies, and executable entry points belonging to a Capability Capsule.

*   **M1 State (Whitelist):**
    *   **Machine-Readable Capability Declaration:** Each Capability Capsule provides a machine-readable `capsule.json` declaration describing its identity, version, supported input/output interface, permitted tools/effects/resources, implementation entry points, and governed mutation boundaries.
    *   **Human-Readable Representation:** A corresponding `make_capsule.md` representation exposes the declared capability in a form that developers and agents can inspect without creating a second independent source of truth.
    *   **Declaration and Provenance:** Every admitted capsule version must preserve sufficient identity, version, implementation-hash, parent-lineage, and provenance information to determine exactly which capability implementation participated in a run.
    *   **Pinned Implementation:** Admitted capsule implementation resources are version-pinned. A changed implementation must not silently execute under the identity of a previously admitted version.
    *   **Supported Types:** M1 capsules may package governed code tools, Markdown skills/prompts, shared prompt material, or other explicitly admitted capability resources.

*   **Future State (Blacklist for M1):**
    *   Autonomous generation of entirely new capability classes during live workflow execution.
    *   Unrestricted remote A2A capability importing.
    *   Unapproved external MCP capability importing.
    *   Arbitrary per-capsule dependency installation during execution.
    *   *Permanent Boundary:* Capability Capsules do not independently select foundational models; model provisioning remains the responsibility of the Routing layer.

#### 4.1.2 Governance, Admission, Versioning & Registry Management

*   **Definition & Expectation:** Validates, admits, versions, stores, and audits reusable Capability Capsules before they may participate in governed execution.

*   **M1 State (Whitelist):**
    *   **Capability-Class Registry:** The registry is organized around reusable capability identities rather than workflow nodes. A workflow node references admitted capabilities; the node itself is not stored as a capsule.
    *   **Append-Only Implementation Lineage:** Each capability maintains an append-only history of admitted implementation versions. Older admitted versions remain available for reproducibility and explicit rollback.
    *   **Default Active / Pinned Execution:** New runs may resolve the latest human-activated admitted version unless the run explicitly pins another admitted version.
    *   **Strict Admission:** Hand-written and RSI-generated capsule versions must pass admission checks covering declaration validity, implementation integrity, required self-tests, provenance, and compatibility before they become eligible for execution.
    *   **Provisional Certification:** M1 uses a single `provisional` trust level indicating that the required admission and self-test conditions have passed.
    *   **Human Standing Management:** A human-controlled action is required to activate, suspend, deprecate, or roll back an admitted capability version.
    *   Historical execution evidence must preserve the exact capability identifiers, versions, and relevant hashes used during the run.

*   **Future State (Blacklist for M1):**
    *   Automatic deletion of historical admitted versions.
    *   Automatic capability librarians that autonomously revoke or promote capability versions.
    *   Automatic publishing to external capability registries or Agentic Hubs.
    *   Third-party certification tiers beyond the M1 provisional admission model.

#### 4.1.3 Node Capability Binding & Runtime Contract Assembly

*   **Definition & Expectation:** Determines which admitted capabilities may participate in a workflow node and creates the run-specific Node Execution Contract that governs the node instance.

*   **Phase 1 Scope — Static Baseline:**
    *   **Static Workflow Definition:** The fixed SwarmFlow script defines the ordered workflow structure used by the Phase 1 research lifecycle.
    *   **Bounded Capability Sets:** Each governed node type declares the bounded set of capability identities required or permitted for that type of work. A node may bind one or more Capability Capsules.
    *   **No Dynamic Capability Search:** Phase 1 does not semantically search, rank, or invent capabilities during live execution.
    *   **Runtime Version Resolution:** When a node is instantiated, the system resolves the admitted version of each required Capability Capsule according to the active run configuration.
    *   **Node Execution Contract Assembly:** The runtime creates a Node Execution Contract binding the `run_id`, node identity, run-specific objective, input artifacts, required outputs, acceptance obligations, resource/effect constraints, and exact admitted Capability Capsule versions available for that node.
    *   **Immutable Runtime Binding:** Once the node begins execution, its effective contract and capability-version bindings are frozen for that node instance and recorded for reproducibility.

*   **Phase 3 Scope — Dynamic System Integration:**
    *   Agent Team / Cluster Mode may inspect a read-only catalogue of admitted Capability Capsule declarations when dynamically planning work.
    *   Dynamically planned nodes may bind compatible admitted Capability Capsules according to the Phase 3 capability-discovery and contract-assembly requirements.
    *   Dynamic planning does not remove the requirement to create an explicit Node Execution Contract before governed execution begins.

*   **Future State (Blacklist for M1):**
    *   Unbounded semantic capability retrieval.
    *   Live creation or installation of previously unadmitted capabilities.
    *   Autonomous widening of declared capability permissions.

#### 4.1.4 Invocation & Composition

*   **Definition & Expectation:** Executes a workflow node under its active Node Execution Contract and coordinates the admitted Capability Capsules bound to that contract.

*   **M1 State (Whitelist):**
    *   **Common Governed Runtime:** The CC Runner consumes the active Node Execution Contract and invokes the one or more Capability Capsules bound to that node within the contract's declared permissions.
    *   **Capability-Level Observation:** Each capability invocation records its capability identity, version, relevant declaration/interface hash, inputs, outputs, tool/effect observations, timing, and execution outcome.
    *   **Node-Level Evidence:** Capability-level observations are aggregated with the node's runtime evidence into the Stage Evidence Bundle used by the Evaluator Gate.
    *   **Specialized Construction:** Stage 3.6 may invoke the dedicated Builder defined in Section 4.9 when the Builder capability/function is included within the active Node Execution Contract.
    *   **Runtime Budget Enforcement:** Locally measurable execution-time limits and invocation constraints remain authoritative controls when reliable provider-level usage telemetry is unavailable.
    *   **The Two-Tier Gate:** Every governed node output is submitted to the Section 4.2 Evaluator Gate before downstream release.
    *   **Unprivileged Process Sandboxing:** M1 maintains the required execution and code-safety boundaries for generated POC execution.

*   **Future State (Blacklist for M1):**
    *   Automatic installation of capabilities during live execution.
    *   Autonomous repair loops.
    *   Unrestricted capability composition outside the governed contract model.

#### 4.1.5 Capability Evolution (RSI Boundaries)

*   **Definition & Expectation:** Allows bounded improvement of eligible Capability Capsule implementations while preserving their declared interfaces, provenance, security boundaries, and independent evaluation requirements.

*   **M1 State (Whitelist):**
    *   **Implementation-Level Evolution:** RSI may optimize explicitly permitted implementation material belonging to an eligible Capability Capsule.
    *   **Declaration / Interface Stability:** RSI may not silently change the capability's required interface, effect class, security boundary, or other compatibility declaration required by workflow nodes.
    *   **Explicit Mutation Permission:** RSI may change only implementation material explicitly designated as mutable for the target capability.
    *   **Versioned Provenance:** Every proposed child capability must retain attributable lineage to its parent and receive a distinct candidate/admitted version identity.
    *   **No Self-Expansion:** An RSI-generated candidate may not grant itself additional mutation, tool, network, resource, evaluation, or promotion permissions.
    *   **Always-Frozen Referee:** Evaluator, Verifier, hidden evaluation material, scoring policy, security boundaries, and promotion controls remain outside RSI's mutation authority.
    *   **Human Activation:** An RSI-generated capability version remains inactive until it satisfies the required admission process and is explicitly activated by a human.

*   **Future State (Blacklist for M1):**
    *   Autonomous creation of entirely new capability classes without the required governance and admission process.
    *   Live-run mutation of active Capability Capsules.
    *   Automatic production promotion.
    *   RSI modification of the independent referee or hidden evaluation material.
    *   Recursive modification of the live RSI improver itself.


### 4.2 Evaluator Gate & Verifier

> **Architectural Note — Infrastructure Gate vs. Scientific Evaluation:**  
> The **Evaluator Gate** is a recurring infrastructure checkpoint executed between governed workflow nodes. It determines whether a node executed correctly, satisfied its active Node Execution Contract, remained within the declarations of the Capability Capsules it invoked, produced admissible evidence, and may safely release the next node.
>
> This is distinct from **Stage 3.8 Scientific Evaluation**, which performs the dedicated scientific judgment of whether the experimental hypothesis is supported, rejected, inconclusive, or conditionally acceptable. A scientifically valid negative result is therefore **not** treated as an infrastructure failure. If Stage 3.8 correctly produces a schema-valid `Evaluation_Verdict.json` containing a scientific `FAIL`, the Evaluator Gate may still return infrastructure `PASS` and allow the result to proceed to Stage 3.9 Delivery.

**Description:** The synchronous node-level verification and execution-control layer of the AI4Research workstation. Every governed SwarmFlow node submits a standardized **Stage Evidence Bundle** to the Evaluator Gate before downstream execution is released. The Evaluator performs a two-tier verification process: **Tier 1 deterministic programmatic checks** provide zero-LLM fast failure for objective contract, schema, budget, security, and runtime violations; **Tier 2 semantic verification** invokes an independent read-only Verifier Agent using `verifier_capsule.md` and evaluation logic adapted from `sciencediscovery/result-evaluator` and `citation-reviewer`. The combined result is emitted as a structured, auditable gate decision consumed directly by the Harness Core and SwarmFlow scheduler.

#### 4.2.1 Evaluation Evidence Envelope & Two-Tier Gate Execution

*   **Definition & Expectation:** Standardizes the evidence supplied to the Evaluator and defines the deterministic order in which objective and semantic checks execute.

*   **M1 State (Whitelist):**
    *   **Standard Stage Evidence Bundle:** Every completed node must submit a structured evaluation payload containing, where applicable:
        *   `run_id`
        *   `stage_id` / `node_id`
        *   Node Execution Contract identifier and relevant contract hash/version metadata
        *   Bound Capability Capsule identifiers, versions, declaration/interface hashes, and relevant invocation records
        *   Input contract and relevant upstream artifacts
        *   Produced output artifact(s)
        *   Node Execution Contract acceptance criteria and proof obligations
        *   Execution route/model metadata
        *   Declared and observed tool usage
        *   Runtime duration and configured time budget
        *   `stdout` / `stderr`
        *   Test, compile, or benchmark results
        *   Citation/evidence references
        *   Declared side effects and observed side effects
    *   **Tier 1 — Deterministic Fast-Fail:** Execute ordinary programmatic assertions before any LLM reviewer is invoked. Tier 1 covers mechanically decidable conditions such as schema validation, required-field presence, artifact existence, time-budget limits, allowed-tool enforcement, forbidden code patterns, test exit codes, and required gate evidence.
    *   **Zero-LLM Failure Path:** If a mandatory Tier-1 assertion fails, the Evaluator immediately records the failed checks and halts the autonomous workflow without spending a Verifier-Agent model call.
    *   **Tier 2 — Independent Semantic Verification:** If Tier 1 passes, invoke the read-only Verifier Agent through `verifier_capsule.md` to evaluate semantic correctness, evidence support, logical consistency, claim integrity, limitations, and node-specific acceptance criteria that cannot be reduced to deterministic assertions.
    *   **Independent Reviewer Context:** Tier 2 receives the artifact, relevant upstream contracts, evidence bundle, and acceptance criteria, but cannot modify the submitted artifact or implementation.
    *   **Immutable M1 Referee:** Evaluator policies, verifier prompts, acceptance thresholds, and verdict aggregation rules are frozen for M1 and may not be modified by RSI.

*   **Future State (Blacklist for M1):**
    *   Parallel multi-reviewer swarms.
    *   Majority voting or judge ensembles.
    *   Dynamic evaluator generation by Auto Harness.
    *   Evaluator self-modification during live workflow execution.
    *   Automatic retry or repair loops triggered directly by a failed gate.

*   **Dependencies:**
    *   *Requires Input from:* The active Node Execution Contract, the declarations/versions of participating Capability Capsules defined through Section 4.1, and the 4.6 Harness Core Stage Evidence Bundle.
    *   *Requires Services from:* 4.3.4 AI Reviewer Agent for Tier-2 model provisioning.
    *   *Writes Evidence to:* 4.5 Data Foundations.
    *   *Provides Output to:* 4.6 Harness Core / SwarmFlow DAG Scheduler.

---

#### 4.2.2 Contract, Schema & Artifact Conformance Evaluator

*   **Definition & Expectation:** Verifies input/output contracts, schemas, scopes, required artifacts, proof obligations, structural completeness, and admissibility of the evidence submitted by the completed node.

*   **M1 State (Whitelist):**
    *   Validate every node output against the JSON or artifact schema declared by its active `capsule.json`.
    *   Verify required fields exist, are non-null where required, use the declared types, and remain inside configured bounds.
    *   Verify the submitted artifact type and filename match the node contract (for example `Candidate_Set.json`, `Opportunity_Card.json`, `Hypothesis_Blueprint.json`, `POC_Artifact_Bundle.zip`, `Benchmark_Payload.json`, or `Evaluation_Verdict.json`).
    *   Verify required proof obligations are present before the artifact is considered admissible.
    *   Bind the submitted artifact to the current `run_id`, node identity, Node Execution Contract identifier/version, and the identifiers, versions, and relevant interface hashes of participating Capability Capsules to prevent stale or swapped artifacts from being accepted.
    *   Compare each participating Capability Capsule's admitted declaration against observed execution evidence, flagging undeclared tool calls, undeclared outputs, effects outside declared permissions, or missing required behavior.
    *   Reject structurally incomplete evidence even when the underlying LLM response appears semantically plausible.
    *   Execute these checks entirely within Tier 1 wherever the rule is mechanically decidable.

*   **M1 Failure Examples:**
    *   Required JSON field missing.
    *   Wrong artifact type supplied by the node.
    *   Artifact belongs to a different run or stage.
    *   Capsule interface hash does not match the admitted version.
    *   Required citation/evidence field is empty.
    *   Undeclared tool invocation appears in the execution trace.

*   **Future State (Blacklist for M1):**
    *   Automatic schema repair.
    *   Dynamic relaxation of contract constraints.
    *   Semantic migration between incompatible capsule interfaces.

---

#### 4.2.3 Engineering Correctness & Code Quality Evaluator

*   **Definition & Expectation:** Evaluates executable artifacts using automated testing and static checks, verifying that generated code is mechanically valid, remains inside permitted architecture boundaries, and satisfies the engineering acceptance requirements declared by the active capsule.

*   **M1 State (Whitelist):**
    *   Execute declared unit, integration, regression, smoke, and end-to-end tests **when those tests are supplied by the target capsule or workflow stage**.
    *   Consume test exit codes and structured test results as Tier-1 evidence.
    *   Execute syntax and compilation validation for generated Python artifacts, including the mechanical checks required by Stage 3.6.
    *   Run bounded static checks against generated source code for:
        *   Syntax validity.
        *   Prohibited imports.
        *   Required entry points.
        *   Declared file/write boundaries.
        *   Type or lint checks when explicitly configured by the capsule.
    *   Verify that code changes stay inside the implementation scope declared by the `Hypothesis_Blueprint.json`, the active Node Execution Contract, and the admitted declarations of the participating Capability Capsules.
    *   Validate required architecture boundaries, including role separation between Builder, Benchmarking, and Evaluator responsibilities.
    *   Record failing test names, exit codes, compile traces, and relevant `stderr` as gate evidence.

*   **M1 Enforcement Rule:**
    *   Failure of a **mandatory** engineering check produces an infrastructure `FAIL`.
    *   The Evaluator records the failure but does not rewrite, patch, or autonomously retry the implementation.

*   **Future State (Blacklist for M1):**
    *   Autonomous defect repair after test failure.
    *   Reviewer-authored code patches.
    *   Iterative Coder–Reviewer loops.
    *   Large-scale repository-wide maintainability optimization.
    *   Dynamic architecture refactoring initiated by the Evaluator.

---

#### 4.2.4 Performance, Cost & Benchmark Evaluator

*   **Definition & Expectation:** Measures execution quality, latency, throughput, resource usage, scalability, and cost-related constraints, and compares observable results against declared budgets, baselines, and regression thresholds.

*   **M1 State (Whitelist):**
    *   **Time-Budget Enforcement:** Compare each capsule's observed execution duration against the configured M1 time budget. Exceeding a mandatory time limit produces an infrastructure fault.
    *   Record available model call counts, execution latency, routing metadata, and other runtime measurements supplied by the Capsule Runner.
    *   Validate the presence and structural integrity of performance metrics required by the active task contract.
    *   For Stage 3.7 benchmark evidence:
        *   Verify both baseline and treatment executions are represented.
        *   Verify required dependent variables are present.
        *   Verify the benchmark used the pre-registered measurement definitions from `Hypothesis_Blueprint.json`.
        *   Verify baseline/treatment comparison metadata is sufficiently complete for Stage 3.8 evaluation.
    *   Compare measurable values against deterministic operational bounds when those thresholds are declared directly in the active Node Execution Contract or applicable Capability Capsule declaration.
    *   Detect explicit regressions against fixed M1 thresholds where a prior baseline has been supplied.

*   **Architectural Boundary:**
    *   The Performance Evaluator verifies that benchmark evidence is complete, mechanically valid, and measured under the declared protocol.
    *   It does **not** independently reinterpret the scientific meaning of the benchmark. Scientific claim acceptance remains the responsibility of Stage 3.8.

*   **M1 Limitations:**
    *   The temporary Codex CLI adapter does not expose sufficiently reliable token accounting for precise token-cost enforcement.
    *   M1 therefore uses execution **time budgets** as the authoritative runtime budget and records token/cost fields only when reliable telemetry is available.

*   **Future State (Blacklist for M1):**
    *   Real-time monetary budget optimization.
    *   Dynamic rerouting to cheaper models.
    *   Distributed throughput/load testing.
    *   Automatic benchmark generation.
    *   Learned regression thresholds.

---

#### 4.2.5 Security, Privacy, Compliance & IP Evaluator

*   **Definition & Expectation:** Checks execution evidence and generated artifacts for prohibited capabilities, unsafe effects, secrets, permission violations, sensitive-data exposure, policy violations, licensing/attribution issues, and other explicitly declared security or compliance constraints.

*   **M1 State (Whitelist):**
    *   Verify generated code against the prohibited module list defined for M1 POC construction, including disallowed system-level or network-level imports such as:
        *   `os`
        *   `sys`
        *   `subprocess`
        *   `requests`
        *   `urllib`
        *   `shutil`
    *   Compare observed tool invocations against the capsule's explicit allowlist.
    *   Flag attempts to access filesystem paths outside the permitted local workspace.
    *   Verify that execution occurred under the expected unprivileged runner boundary when code execution is involved.
    *   Check that required local-only networking constraints and execution-boundary evidence are present when applicable.
    *   Perform lightweight static detection for obvious embedded secrets or credentials in generated artifacts and logs.
    *   Verify that required source attribution or citation metadata is retained for externally derived research evidence.
    *   Record security violations as explicit gate evidence rather than silently sanitizing the result.

*   **M1 Enforcement Rule:**
    *   A confirmed prohibited action, unauthorized tool use, or scope escape produces infrastructure `FAIL`.
    *   A failure caused by an unavailable or misconfigured execution environment rather than the artifact itself is classified as `ENVIRONMENT_BLOCKED`.

*   **Future State (Blacklist for M1):**
    *   Formal legal opinions.
    *   Full regulatory compliance certification.
    *   Automated patent clearance.
    *   Enterprise DLP scanning.
    *   Full software-composition-analysis infrastructure.
    *   Automated license remediation.
    *   Security-agent attack/defense swarms.

---

#### 4.2.6 Evidence, Factuality & Scientific Validity Evaluator

*   **Definition & Expectation:** Evaluates claim-to-evidence support, citation integrity, source traceability, reasoning consistency, uncertainty, reproducibility, experimental validity, and external plausibility where these qualities are relevant to the current node.

*   **M1 State (Whitelist):**
    *   Invoke the Tier-2 Verifier Agent using evaluation prompts adapted from:
        *   `sciencediscovery/result-evaluator`
        *   `sciencediscovery/citation-reviewer`
    *   Verify that material factual claims made by a node are supported by evidence contained within the submitted evaluation context.
    *   Check that cited sources actually appear in the node's supplied evidence bundle.
    *   Check that citation identifiers, filenames, or source metadata have not been fabricated or detached from the referenced evidence.
    *   Identify unsupported reasoning jumps, contradictions between the artifact and its evidence, and conclusions that materially exceed the supplied evidence.
    *   Evaluate whether uncertainty and material limitations are disclosed when the available evidence does not justify an unconditional conclusion.
    *   For scientific outputs, validate evidence-chain integrity and experimental plausibility without changing the pre-registered success criteria.
    *   Treat impossible or clearly corrupted empirical values as potential execution/evidence anomalies and surface them for classification.
    *   Require the Verifier to return structured reasons and evidence references rather than an unsupported natural-language pass/fail judgment.

*   **Architectural Boundary:**
    *   Node-level semantic verification may determine whether a node's output is sufficiently grounded to advance.
    *   Full interpretation of the completed experiment remains concentrated in Stage 3.8 Scientific Evaluation.
    *   The Evaluator may verify that Stage 3.8 applied its contract correctly without replacing Stage 3.8's scientific verdict with a second independent scientific verdict.

*   **Future State (Blacklist for M1):**
    *   Live external web fact-checking during every gate.
    *   Multi-agent scientific peer-review panels.
    *   Automated replication experiments.
    *   Dynamic counterfactual benchmark execution.
    *   Majority-vote factuality judging.

---

#### 4.2.7 Lifecycle, Parity & Human Review Evaluator

*   **Definition & Expectation:** Verifies that execution actually occurred, required workflow stages and gates were respected, expected side effects match observed side effects, declared functionality is behaviorally present, and ambiguous or high-risk cases are routed to attributable human review.

*   **M1 State (Whitelist):**
    *   Verify that the evaluated node reached the expected runtime lifecycle state:
        *   `Pending`
        *   `Running`
        *   `Evaluating`
        *   `Completed` or `Failed`
    *   Verify that required upstream nodes and gates completed before the current node began.
    *   Verify that the next SwarmFlow node has **not** started before the current gate releases it.
    *   Validate real execution evidence rather than accepting self-reported agent claims that an action or test occurred.
    *   Compare declared side effects against observed execution traces.
    *   Compare the capsule's promised behavior against observed runtime behavior to detect feature or semantic parity failures.
    *   Preserve attributable reviewer information, timestamps, gate reasons, and relevant evidence references in the run bundle.
    *   Route blocked, ambiguous, policy-sensitive, or failed execution to OpenJiuwen's native `human_session` for developer inspection.
    *   Human intervention may review, abort, correct the environment, or explicitly restart work, but the automated Evaluator does not silently convert a failed verdict into a pass.

*   **Future State (Blacklist for M1):**
    *   Automated approval of high-risk exceptions.
    *   Multi-party enterprise approval chains.
    *   Remote asynchronous reviewer queues.
    *   Learned human-review routing.
    *   Automatic replay after human correction without an explicit restart action.

---

#### 4.2.8 Verdict Aggregation & Orchestration Gate Policy

*   **Definition & Expectation:** Aggregates Tier-1 and Tier-2 evaluation results into a stable machine-readable decision that determines whether SwarmFlow may release the next node.

*   **M1 Gate Verdicts:**
    *   `PASS`
        *   All mandatory checks passed.
        *   The artifact is admissible.
        *   SwarmFlow may advance to the next node.
    *   `PASS_WITH_KNOWN_LIMITATIONS`
        *   All mandatory checks passed.
        *   Non-blocking limitations or warnings were identified and recorded.
        *   SwarmFlow may advance, carrying the warnings forward in the run evidence.
    *   `FAIL`
        *   A mandatory contract, engineering, security, evidence, or gate-policy condition failed.
        *   Autonomous workflow advancement is halted.
    *   `ENVIRONMENT_BLOCKED`
        *   Evaluation or execution cannot validly complete because of an external/runtime dependency failure rather than a demonstrated defect in the submitted artifact.
        *   Autonomous workflow advancement is halted.
    *   `INCONCLUSIVE`
        *   Available evidence is insufficient to produce a defensible pass/fail decision.
        *   Autonomous workflow advancement is halted pending human review.

*   **Human Escalation Routing:**
    *   `ESCALATE_TO_HUMAN` is treated as an **orchestration action**, not a separate quality judgment.
    *   `FAIL`, `ENVIRONMENT_BLOCKED`, and `INCONCLUSIVE` may set `routing_action = ESCALATE_TO_HUMAN`.
    *   The Harness Core then invokes OpenJiuwen's native `human_session` and records the human-review requirement in the run tree.

*   **Test-Spec Compatibility Mapping:**
    *   The broader test specification uses the normalized verdict vocabulary `PASS / FAIL / BLOCKED / INCONCLUSIVE`.
    *   M1 orchestration maps detailed runtime verdicts as follows:
        *   `PASS` → `PASS`
        *   `PASS_WITH_KNOWN_LIMITATIONS` → `PASS` with warnings
        *   `FAIL` → `FAIL`
        *   `ENVIRONMENT_BLOCKED` → `BLOCKED`
        *   `INCONCLUSIVE` → `INCONCLUSIVE`

*   **Deterministic Tier Precedence:**
    1.  Execute Tier 1.
    2.  If a mandatory Tier-1 check fails, emit the corresponding blocking verdict and **do not invoke Tier 2**.
    3.  If Tier 1 passes, invoke Tier 2.
    4.  Aggregate mandatory Tier-2 findings using the node's fixed acceptance profile.
    5.  Persist the final gate artifact before releasing or halting the SwarmFlow node transition.

*   **Mandatory Scientific-Failure Routing Rule:**
    *   A `FAIL` contained **inside** `Evaluation_Verdict.json` from Stage 3.8 represents a scientific conclusion that the tested hypothesis was rejected.
    *   If Stage 3.8 itself executed correctly, satisfied its active Node Execution Contract and the admitted declarations of its participating Capability Capsules, and produced valid supporting evidence, the **infrastructure Evaluator Gate returns `PASS`** for the Stage 3.8 node.
    *   The scientific `FAIL` remains unchanged inside the artifact and proceeds to Stage 3.9 Delivery so the user receives the negative result and its supporting explanation.
    *   Only a failure of the evaluation **process itself**—for example missing benchmark evidence, invalid schema, corrupted provenance, or violated gate rules—produces infrastructure `FAIL`.

*   **Minimum Gate Result Schema:**

```json
{
  "run_id": "string",
  "stage_id": "string",
  "gate_verdict": "PASS | PASS_WITH_KNOWN_LIMITATIONS | FAIL | ENVIRONMENT_BLOCKED | INCONCLUSIVE",
  "normalized_verdict": "PASS | FAIL | BLOCKED | INCONCLUSIVE",
  "routing_action": "ADVANCE | HALT | ESCALATE_TO_HUMAN",
  "tier_1": {
    "status": "PASS | FAIL | BLOCKED",
    "checks": []
  },
  "tier_2": {
    "status": "PASS | FAIL | INCONCLUSIVE | NOT_RUN",
    "reasons": [],
    "evidence_refs": []
  },
  "failed_checks": [],
  "warnings": [],
  "known_limitations": [],
  "evidence_refs": [],
  "timestamp": "ISO-8601"
}
```

*   **Orchestration Behavior:**
    *   `PASS` → release the downstream node.
    *   `PASS_WITH_KNOWN_LIMITATIONS` → release the downstream node and propagate warnings.
    *   `FAIL` → halt and preserve failure evidence.
    *   `ENVIRONMENT_BLOCKED` → halt and preserve environment evidence.
    *   `INCONCLUSIVE` → halt pending attributable human review.
    *   Any blocking state may invoke `human_session` according to gate policy.

---

#### 4.2.9 M1 Evaluator Acceptance & Failure-Injection Tests

*   **Definition & Expectation:** The Evaluator is considered complete for M1 only if the gate itself can be demonstrated to prevent invalid workflow advancement using intentionally malformed or ambiguous evidence.

*   **Required M1 Acceptance Cases:**
    1.  **Valid Artifact — Deterministic Pass**
        *   Supply a schema-valid artifact with complete runtime evidence.
        *   Tier 1 passes.
        *   Tier 2 passes.
        *   Gate emits `PASS`.
        *   The next SwarmFlow node starts.

    2.  **Schema Failure — Tier-1 Fast Failure**
        *   Remove a mandatory field or submit an invalid field type.
        *   Tier 1 emits `FAIL`.
        *   Tier 2 is recorded as `NOT_RUN`.
        *   The next SwarmFlow node does not start.

    3.  **Swapped/Stale Artifact Failure**
        *   Submit an otherwise valid artifact belonging to a different node, run, capsule version, or interface hash.
        *   Contract/Artifact Conformance detects the mismatch.
        *   Gate emits `FAIL`.
        *   The next node remains locked.

    4.  **Broken Citation / Unsupported Claim**
        *   Supply a structurally valid artifact containing a citation or factual claim that is not supported by the submitted evidence bundle.
        *   Tier 1 passes.
        *   Tier 2 detects the claim-to-evidence failure.
        *   Gate emits `FAIL` or `INCONCLUSIVE` according to the fixed verifier rubric.
        *   The next node remains locked.

    5.  **Runtime Budget Violation**
        *   Force a capsule to exceed its configured time budget.
        *   Tier 1 detects the runtime violation.
        *   The run halts and records the timeout evidence.
        *   No semantic reviewer call is required.

    6.  **Prohibited Code/Tool Usage**
        *   Inject a forbidden import or execute an undeclared tool.
        *   Tier 1 detects the violation.
        *   Gate emits infrastructure `FAIL`.
        *   The workflow halts for developer triage.

    7.  **Environment Block**
        *   Remove a required dependency or make the required runtime unavailable.
        *   Gate distinguishes environment failure from artifact correctness.
        *   Gate emits `ENVIRONMENT_BLOCKED`.
        *   The workflow halts and invokes human review.

    8.  **Known Non-Blocking Limitation**
        *   Provide an artifact that satisfies every mandatory requirement but contains a documented, non-blocking limitation.
        *   Gate emits `PASS_WITH_KNOWN_LIMITATIONS`.
        *   Warning metadata is persisted.
        *   Downstream execution proceeds.

    9.  **Scientific Negative Result**
        *   Stage 3.8 validly determines that the tested hypothesis is scientifically `FAIL`.
        *   The Stage 3.8 artifact satisfies its contract and evidence requirements.
        *   Evaluator infrastructure verdict is `PASS`.
        *   Scientific `FAIL` remains inside `Evaluation_Verdict.json`.
        *   Stage 3.9 Delivery executes normally.

    10. **Gate-Locking Invariant**
        *   Intentionally delay or block an Evaluator decision.
        *   Assert that no downstream node begins execution until an advancing gate verdict has been durably recorded.

*   **M1 Demonstration Invariant:**
    > **No governed SwarmFlow node may advance solely because its producing agent claims success. Advancement requires an independently recorded Evaluator Gate decision backed by admissible execution evidence.**

---

#### 4.2.10 Future State — Autonomous Multi-Faceted Evaluation via Auto Harness

*   **Definition & Expectation:** Evolves the fixed M1 synchronous gate into a broader evaluation harness capable of selecting and composing specialized verification strategies according to artifact type, risk, domain, and available evidence.

*   **Future State:**
    *   Specialized parallel evaluator agents for:
        *   Contract and schema correctness.
        *   Engineering correctness and maintainability.
        *   Performance and cost.
        *   Security and privacy.
        *   Factuality and citation integrity.
        *   Scientific validity and reproducibility.
        *   Lifecycle and semantic parity.
    *   Auto Harness selection of appropriate evaluation suites based on node contracts and risk profiles.
    *   Independent multi-model reviewer strategies where additional assurance is required.
    *   Automated adversarial and regression test generation.
    *   Governed defect-repair loops that may return failures to Builder nodes for bounded correction.
    *   Continuous evaluator calibration against golden sets and hidden benchmark suites.
    *   Evaluation-policy versioning with reproducible historical gate decisions.
    *   Controlled harness evolution subject to independent validation and human promotion rather than unrestricted self-modification.




### 4.3 Foundational Models & Routing

**Description:** The centralized model registry, selection engine, and usage-auditing layer that manages how execution roles are provisioned with foundation models. The M1 Phase 1 production workflow is strictly locked to the Codex CLI adapter baseline so end-to-end development does not depend on pending external API/model access.

Non-Codex, heterogeneous, or alternate-model routing belongs to M1 Delivery Phase 3 Dynamic System Integration. Until the required endpoint and credential access is approved, Phase 3 may develop interfaces, registry behavior, configuration, mocks, candidate analysis, and routing logic without claiming real-model integration. Once access is approved, explicitly approved real endpoints may be exercised within the Phase 3 configuration for functional evaluation. No experimental route replaces the deterministic Phase 1 Codex CLI fallback without satisfying the required validation and approval conditions.

#### 4.3.1 Model Capability Registry
*   **Definition & Expectation:** Record declared and verified model capabilities such as modality, context size, tool use, structured output, cost class, and suitable tasks.
*   **M1 Phase 1 Scope (Static Baseline):**
    *   Register the Codex CLI adapter as the sole active model endpoint to guarantee end-to-end DAG execution without live API keys.
*   **M1 Delivery Phase 3 Scope (Heterogeneous Model Integration):**
    *   **Heterogeneous Registry Development:** On an isolated development/evaluation branch or configuration, develop the registry to represent a bounded mixed model pool using mocked endpoints while external model/API access remains unavailable.
    *   **Access-Gated Real Registration:** After endpoint and credential access is explicitly approved, selected real models may be registered and exercised within the Phase 3 configuration for functional integration testing.
    *   Each registered model maintains lightweight capability and version metadata required by the routing and audit layers.
    *   Registration of an experimental real model does not make that model eligible for Phase 1 production execution.
*   **Future State (Blacklist for M1):**
    *   Large collections of narrowly specialized models, numerous fine-tuned variants of the same base model, task-specific checkpoints with limited general applicability, experimental or poorly documented models without stable API access, locally hosted model weights, and exhaustive coverage of every available model family or version.
*   **Dependencies:** API key and endpoint provisioning; a minimal and consistent model capability schema.

#### 4.3.2 Model Routing & Selection
*   **Definition & Expectation:** Match and select a model route using task needs, capability, quality, cost, policy, quota, and current health. 
*   **M1 Phase 1 Scope (Static Baseline):**
    *   **Delegated Capsule Selection:** The Router does *not* select the capability capsule. It receives the designated capsule and task execution role directly from the SwarmFlow DAG or Planner.
    *   **Single-Model Fallback Path:** Model selection is statically routed to the Codex CLI adapter (the endpoint of last resort) to guarantee pipeline execution. 
*   **M1 Delivery Phase 3 Scope (Dynamic Model Routing):**
    *   Develop the dynamic two-stage routing logic in an isolated development/evaluation environment where the Router receives the DAG-provided capsule and evaluates compatible model candidates.
    *   Before approved model/API access is available, routing behavior is exercised only against mocked or simulated endpoints.
    *   After access is approved, explicitly approved real endpoints may be exercised within the Phase 3 configuration for functional integration and routing validation.
    *   Experimental routes must remain separately configurable and reversible and must not replace the static Codex Phase 1 route without explicit product and architecture approval.
*   **Future State (Blacklist for M1):**
    *   Learned or fine-tuned routers; model embeddings or vector retrieval; GraphSAGE, HNSW, or other large-scale retrieval infrastructure; bandit, reinforcement-learning, or online-learning-based routing; multi-model voting or ensembles; mid-execution model switching; complex global cost/latency optimization.
*   **Dependencies:** Model Capability Registry; Capsule Registry; API access to candidate models.

#### 4.3.3 Model Usage Auditing

*   **Definition & Expectation:** Ensure every model invocation can be locally attributed to the workflow execution that caused it while preserving a clean provider-facing model request boundary.

*   **M1 State (Whitelist):**
    *   **Locally Correlated Model Calls:** Every model invocation must be attributable in local execution evidence to its originating run, node, execution role, and participating Capability Capsule/version where applicable.
    *   **Common Runtime Telemetry:** Record the selected model endpoint, local route decision, invocation timestamp, completion timestamp, locally measured execution latency, invocation outcome, fallback state, and stable local correlation identifier.
    *   **JiuwenSwarm Budget Telemetry:** Where the active model integration supplies reliable usage information to JiuwenSwarm, preserve the available SwarmFlow/team budget totals and spend observations exposed by the runtime.
    *   **Subscription-Authenticated Codex Telemetry:** When execution uses the ChatGPT-subscription-authenticated Codex pathway, record any usage-allowance, limit, credit, or reset information that the Codex client reliably exposes. Account-level allowance information must not be represented as exact per-node or per-call token usage.
    *   **Per-Invocation Token Accounting Boundary:** Record exact input/output/total token usage only when the active endpoint or bridge exposes reliable usage data for the individual invocation. Missing per-call token telemetry must be represented as unavailable rather than inferred.
    *   **API-Backed Usage Telemetry:** When an approved API-backed endpoint returns provider usage fields, persist the available provider-reported usage with the corresponding model-call observation.
    *   **Audited Invocation Boundary:** Supported M1 model calls must pass through the approved model-routing/bridge boundary so workflow components cannot silently bypass model-use attribution.
    *   **Provider Data Minimization:** Internal workflow metadata used only for local attribution or benchmarking must not be inserted into provider prompts solely to enable telemetry.

*   **Future State (Blacklist for M1):**
    *   Full billing integration.
    *   Organization-wide quota enforcement.
    *   Advanced policy-compliance analytics.
    *   Cross-user chargeback.
    *   Real-time anomaly detection.

*   **Dependencies:** Local Observation/run identity, routing output metadata, model-bridge telemetry, and available provider usage statistics.

#### 4.3.4 AI Reviewer Agent (Routing Integration)
*   **Definition & Expectation:** The routing integration that provisions the model for the independent Reviewer Agent to assess implementation correctness.
*   **M1 Phase 1 Scope (Static Baseline):**
    *   **Static Provisioning for 4.2 Evaluator Gate:** Route Tier-2 Verifier requests to the Codex CLI baseline using the designated `verifier_capsule.md`.
    *   Return structured review results directly to the Evaluator Gate without modifying the submitted artifact or independently advancing the workflow.

*   **M1 Delivery Phase 3 Scope (Alternate Verifier Model Integration):**
    *   Candidate analysis, integration design, and interface preparation may proceed before alternate-model access is available.
    *   Until endpoint and credential access is approved, alternate Verifier-model execution must use mocks or remain analysis-only.
    *   After access is approved, one explicitly approved unmodified candidate model may be integrated through the agreed Verifier interface in an isolated development/evaluation configuration.
    *   Experimental activation must be explicit and reversible, and disabling the experimental route must restore the Codex baseline.
    *   Successful experimental integration does not authorize replacement of the Phase 1 Codex Verifier route.
*   **Future State (Blacklist for M1):**
    *   Reviewer-driven rerouting or dynamic model switching based on failure rates; automatic code modification by the Reviewer; multi-reviewer voting or ensemble review; autonomous iterative Coder–Reviewer loops.
*   **Dependencies:** Model Routing & Selection; Reviewer Capsule (`verifier_capsule.md`); access to implementation outputs and relevant task context.



### 4.4 RSI (Recursive Self-Improvement) Integration

**Description:** The local-isolated capsule self-improvement subsystem that proposes bounded implementation changes to eligible Capability Capsules and evaluates those candidates against fixed, independent evidence before human-controlled admission or activation. In M1, the improver itself remains fixed: M1 demonstrates governed capsule-level self-improvement and establishes the records, observability, isolation, and interface seams required for later recursive improvement of the improver. RSI remains strictly decoupled from the live SwarmFlow DAG.

The M1 engine is expected to generalize across eligible capsule targets through a shared loop core and target-specific profiles rather than through target-specific logic embedded in the optimization engine. The initial M1 targets exercise bounded code and text mutation while preserving fixed capsule interfaces and an independent referee.

**M1 RSI Targets:**

* **Target 1 — Required M1 Commitment:** Code-level improvement of the `rank_opportunities` helper inside a sandbox copy of `screening_capsule`. M1 must demonstrate that the fixed RSI engine can propose, evaluate, and produce evidence for a bounded child implementation without modifying the live production capsule.
* **Target 2 — Conditional Secondary Target:** Text-level improvement of `screening_capsule` implementation material, including `SKILL.md` and the explicitly mutable `references/rubric.md`. This target runs only if the required bounded headless model-execution path is available; otherwise it is deferred to M2 without blocking M1 completion.

#### 4.4.1 Text-Based Artifacts (GEPA / MIProV2 / TextGrad)

* **Definition & Expectation:** Evaluates bounded improvement of implementation-level prompt and rubric material while preserving the target capsule's required dimensions, interface, checks, and independent evaluation contract.

* **M1 State (Whitelist):**
    * **Target 2:** Evaluate text mutation of the `screening_capsule` implementation, including its implementation prompt and explicitly authorized work-capsule rubric content.
    * Mutation may change wording, instructions, examples, scales, thresholds, or weights only where those fields are explicitly listed as mutable by the target capsule.
    * The required scoring dimensions and downstream interface remain fixed.
    * Validate candidate text changes using offline paired parent-versus-child evaluation on the same permitted fixtures.
    * A candidate must preserve the parent Capability Capsule's required tests, admitted declaration, interface, and compatibility requirements before it can be considered an improvement.
    * **Rubric Boundary:** This permission applies only to implementation-level rubric material belonging to the target work capsule. Evaluator, Verifier, gate, check, policy, and other referee-owned rubrics remain immutable to RSI.
    * Target 2 depends on an available bounded headless model-execution path. If that dependency is unavailable for M1, Target 2 is deferred without blocking the Target 1 code-mutation commitment.

* **Future State (Blacklist for M1):**
    * Changing the required scoring-dimension set or capsule interface.
    * RSI modification of Tier-1 checks, Verifier/Tier-2 rubrics, or evaluation policy.
    * Multi-child population search or Pareto optimization.
    * Live or shadow production A/B testing.
    * Cross-node TextGrad-style optimization.
    * LLM-judge loss as the RSI optimization objective.

#### 4.4.2 Runtime and Resource Routing (Bayesian Optimization / Bandits / Cost-Aware RL)
*   **Definition & Expectation:** Optimizes model, tool, budget, retry, and concurrency decisions. Validate with traces, load tests, and cost-latency metrics.
*   **M1 State (Whitelist):**
    *   **Measure Only:** Record execution traces, call counts, and execution time (`cost.time_s`) per proposal in the attempt log.
    *   Time is strictly used as a tie-breaker in the scoring rule if two versions pass the exact same number of tests.
*   **Future State (Blacklist for M1):**
    *   Bayesian optimization of runtime settings, bandit routing, modifying timeouts/budgets, mid-execution model switching, or concurrency load testing.

#### 4.4.3 Capability Capsules and Physical Operators (Trajectory Mining / Code Evolution / CEGIS)

* **Definition & Expectation:** Demonstrates bounded implementation-level code evolution while preserving the target Capability Capsule's admitted declaration, interface, required checks, and effect boundaries.

* **M1 State (Whitelist):**
    * **Target 1 — M1 Commitment:** Apply code mutation to the pure `rank_opportunities` helper associated with Stage 3.4.7 Opportunity Prioritization inside `screening_capsule`.
    * The production helper remains fixed during the M1 optimization experiment.
    * RSI operates on a separate sandbox copy whose permitted mutation surface is explicitly declared.
    * A child may change only the authorized helper implementation. The `Opportunity_Card.json` interface, required Top-1 output behavior, incoming scoring dimensions, checks, and effect boundaries remain fixed.
    * Candidate children must pass the parent's required tests and compatibility requirements before hidden evaluation is considered.
    * M1 output for Target 1 is a sandbox-validated child candidate together with its supporting evaluation and provenance evidence.
    * A sandbox candidate does not automatically become the production implementation. Adoption requires the existing human-gated admission and activation process.
    * The shared RSI loop core must remain target-independent; target-specific fixtures, scoring adapters, mutation permissions, and proposer settings belong to the target profile rather than the core engine.

* **Future State (Blacklist for M1):**
    * Contract or schema changes that alter the capsule interface.
    * Multi-file code mutation.
    * Physical-operator mutation such as DeepSearch, CodeSearch, or workspace I/O.
    * Dependency re-pinning by RSI.
    * Automatic production adoption of a sandbox child.
    * Whole-workflow or multi-capsule code evolution.

#### 4.4.4 DAG and Agent Organization (AFlow / MCTS / ADAS)
*   **Definition & Expectation:** Optimizes workflow structure, agent roles, and coordination. Validate with replay tests, simulations, and success-cost comparisons.
*   **M1 State (Whitelist):**
    *   **Read-Only Context:** Workflow structure and agent roles are read-only variables.
    *   Validate via node-level offline replay tests (scoring the child on recorded inputs) and a wiring dry-run (simulating the child in the DAG without execution to ensure zero port-type mismatches).
*   **Future State (Blacklist for M1):**
    *   AFlow, MCTS, ADAS, dynamically reassigning agent roles, whole-workflow evolution, or adding/removing gates.

#### 4.4.5 Evaluator, Reward, Contract, and Governance

* **Definition & Expectation:** Preserves an independent and immutable referee for RSI so candidate improvements cannot improve their score by weakening, rewriting, bypassing, or learning protected evaluation mechanisms.

* **M1 State (Whitelist):**
    * **The Referee Is Frozen:** RSI does not modify the Evaluator, Verifier, checks, check runners, hidden evaluation sets, scoring policy, promotion policy, or other referee-owned state.
    * The M1 candidate-scoring policy is fixed before an RSI session begins and may not change in response to observed candidate results.
    * Candidate evaluation must first preserve all mandatory parent behavior and tests before improvement evidence is considered.
    * Hidden-loop evaluation may be used only through the bounded information channel defined for M1.
    * Final hidden evaluation is reserved for terminal candidate assessment and must not be repeatedly exposed to the optimization loop.
    * Evaluator/referee configuration relevant to a session must remain pinned sufficiently to detect mid-session drift.
    * A work capsule's explicitly mutable implementation rubric is not itself the referee. Evaluator, Verifier, gate, and check rubrics remain outside RSI's mutation authority.
    * Validate the RSI engine using intentionally good and bad candidate cases together with the security/violation suite defined in Section 4.4.10.

* **Future State (Blacklist for M1):**
    * RSI editing gates, Verifiers, checks, check runners, hidden evaluation suites, scoring rules, or promotion policies.
    * Learned reward models controlled by RSI.
    * RSI-generated acceptance criteria used to certify the same RSI candidate that generated them.
    * Judge-only candidate targets without an independently calibrated referee.

#### 4.4.6 Memory, Retrieval, and Evidence (Memory Learning / Self-RAG / Reranker Training)
*   **Definition & Expectation:** Improves storage, retrieval, citation, and evidence binding. Validate with recall, precision, citation accuracy, and provenance checks.
*   **M1 State (Whitelist):**
    *   **RSI Memory Only:** RSI strictly records its own attempt logs (hash-chained), stores its lineage (`parent_hash`), and binds evidence to its generated candidates.
    *   Validate via pre-submission provenance checks (verifying lineage resolves and claimed scores match the log).
*   **Future State (Blacklist for M1):**
    *   Product memory learning, prompted Self-RAG, reranker training, or writing RSI lessons into the main product memory stores.

#### 4.4.7 Model Policies and Weights (SFT / LoRA / DPO / GRPO / Agent RL)

* **Definition & Expectation:** Preserves model identity and comparability during RSI evaluation while keeping model training and weight modification outside the authority of the RSI subsystem.

* **M1 State (Whitelist):**
    * **No-Training Guarantee:** RSI mutates capsule code or text only; it does not train, fine-tune, or alter model weights.
    * Parent and child evaluations must use the same declared model route and relevant runtime configuration for a comparison to be treated as valid.
    * Model identity and available execution metadata are recorded with RSI evaluation evidence.
    * Training-oriented exports may be produced for separate future human-led work, but RSI itself does not consume those exports to modify weights.

* **Permanent RSI Blacklist:**
    * SFT, LoRA, DPO, GRPO, Agent RL, or any other model-weight modification performed by RSI.
    * RSI modification of Verifier or reviewer model weights.
    * RSI-controlled fine-tuning endpoints.
    * RSI tuning of the model router or changing model-selection policy without a separate product decision.

Separate future model-training or Verifier-calibration work, if approved, remains outside the RSI subsystem and requires its own governed admission and evaluation process.

#### 4.4.8 Data, Benchmarks, Curriculum, and Observability (Active Learning / Hard-Case Mining / Credit Assignment)

* **Definition & Expectation:** Provides the separated evaluation data and attributable observations required to determine whether an RSI candidate represents a genuine improvement rather than overfitting, contamination, or evaluation leakage.

* **M1 State (Whitelist):**
    * Maintain distinct target-specific data splits for visible development data, hidden loop evaluation, and hidden final evaluation.
    * Keep milestone/tracking evaluation data outside the RSI optimization loop.
    * Enforce zero known overlap between protected evaluation splits and proposer-visible development inputs.
    * Before live platform telemetry provides sufficient cases, manually seed the minimum hidden evaluation fixtures required for the approved M1 targets.
    * Preserve the M1 headroom rule so RSI does not claim improvement on a target whose baseline already leaves insufficient measurable room for improvement.
    * Record RSI attempts, candidate lineage, evaluation outcomes, runtime measurements, and session outcomes so candidate decisions can be reconstructed.
    * Where platform observations are available, preserve joinable references between RSI records and the corresponding capsule/run observations without exposing hidden evaluation contents to the proposer.
    * Validate data separation using coverage, contamination, provenance, and replay/attribution checks.

* **Future State (Blacklist for M1):**
    * RSI writing or assigning its own hidden fixtures.
    * Active learning or adaptive curriculum generation.
    * Using the milestone tracking set as optimization feedback.
    * Cross-capsule credit assignment.
    * Platform-wide live observations autonomously changing the RSI improver.
    * Judged or learned metrics without an independently governed calibration process.

#### 4.4.9 Local-Isolated RSI Sandbox & Hidden-Evaluation Isolation

* **Definition & Expectation:** Provides a local-isolated execution boundary in which RSI may propose and evaluate bounded candidate changes without gaining direct access to production state, referee assets, or protected hidden evaluation material. The isolation boundary may permit explicitly approved, bounded read-only retrieval of public benchmark or repository material without granting general network authority.

* **M1 State (Whitelist):**
    * RSI execution remains physically and logically separate from the live SwarmFlow workflow.
    * **Approved Public Benchmark Retrieval:** Where required by an approved RSI target, the local RSI environment may retrieve explicitly allowlisted public benchmark or public repository material through a bounded read-only retrieval pathway.
    * **Reproducible External Inputs:** Public benchmark or repository material used by RSI must be pinned or snapshotted sufficiently to identify the exact version, revision, commit, or content used during candidate evaluation.
    * **No External Write Authority:** Permission to read an approved public source does not permit RSI to publish changes, push repository modifications, modify upstream benchmarks, or perform arbitrary network activity.
    * **Hidden-Evaluation Separation:** Public benchmark access must remain technically and logically separate from protected hidden-loop and hidden-final evaluation material.
    * Hidden loop and final evaluation material remains outside the readable scope of the RSI proposer and candidate under evaluation.
    * Untrusted candidate execution must not share the same trust boundary as the component holding authoritative hidden evaluation material or scoring logic.
    * Hidden evaluation returns only the bounded aggregate information required by the approved M1 scoring process. Hidden fixture contents, expected outputs, per-case identities, and other referee-only material must not enter proposer context.
    * Hidden evaluation sets are established and frozen before the relevant RSI session begins and must not be rewritten in response to candidate behavior.
    * M1 enforces bounded use of hidden evaluation to reduce adaptive overfitting. Loop-set access is programmatically capped and final-set evaluation occurs only at the approved terminal evaluation point.
    * RSI attempts, lineage, evaluation actions, and resulting decisions must leave attributable evidence sufficient for reconciliation and replay.
    * An RSI-produced child remains inactive until it passes admission and is explicitly activated by a human.
    * Human rollback of an activated RSI-generated version must remain available.

* **Future State (Blacklist for M1):**
    * Live-pipeline RSI mutation.
    * Automatic candidate promotion or activation.
    * Per-case hidden evaluation feedback reaching the proposer.
    * RSI-generated or RSI-selected hidden evaluation suites.
    * RSI modification of referee assets.
    * Broader sealed-suite and operating-system confinement infrastructure beyond the approved M1 isolation boundary.

The Architecture Design and RSI implementation specifications own the exact operating-system accounts, filesystem permissions, encryption and key custody, containerization, process-launcher design, network confinement, and refusal-code implementation used to satisfy these product requirements.


#### 4.4.10 RSI Security Guardrails & Adversarial Validation

* **Definition & Expectation:** Treats the RSI proposer and generated child as potentially adversarial with respect to the evaluation process and validates that optimization pressure cannot bypass the boundaries governing mutation, hidden evaluation, evidence integrity, or promotion.

* **M1 State (Whitelist):**
    * Maintain a fixed security threat model covering, at minimum:
        * Unauthorized hidden-fixture access or leakage.
        * Evaluator, Verifier, check, or scoring-policy tampering.
        * Mutation outside the explicitly permitted target scope.
        * Attempts to widen RSI's own permissions.
        * Prompt-injection-driven scope escape.
        * Unauthorized filesystem, process, tool, or network effects.
        * Resource-exhaustion attempts.
        * Audit or evaluation-evidence tampering.
        * Hidden-evaluation overfitting or premature final-evaluation access.
        * Automatic or unauthorized production promotion.
    * Run an intentional security violation suite before the RSI path is accepted for M1. The suite must actively attempt prohibited behavior rather than relying only on successful normal-path execution.
    * Every mandatory violation case must be blocked and produce attributable security evidence.
    * Security violations halt the affected RSI session and require explicit human clearance before autonomous optimization continues.
    * Hidden evaluation must complete without prohibited fixture disclosure to the proposer or candidate.
    * Authoritative RSI and evaluator records must reconcile sufficiently to demonstrate that reported scores and decisions correspond to actual evaluation activity.
    * Security testing must include deliberate attempts to bypass the sandbox and guardrails, and any discovered vulnerability must be recorded as M1 verification evidence.
    * Known M1 containment limitations and residual risks must be documented explicitly rather than treated as fully solved.

* **Future State (Blacklist for M1):**
    * RSI modification of its own security policy, violation suite, referee, or promotion rules.
    * Automatic acceptance of detected security exceptions.
    * Self-generated hidden security tests used to certify the same RSI process that generated them.





### 4.5 Data Foundations

**Description:** The telemetry and state persistence layer of the platform. M1 strictly avoids complex external databases, vector scaffolding, or distributed graph stores. Instead, it relies on a strict bifurcation of data: utilizing OpenJiuwen's native memory modules for agent reasoning context, and local, append-only file structures for system telemetry and execution records.

#### 4.5.1 Persistent Memory & Context Retrieval (Agent Memory)
*   **Definition & Expectation:** Stores accepted facts, decisions, summaries, and reusable context utilized actively by the LLM during a workflow run.
*   **M1 State (Whitelist):**
    *   Utilize native JiuwenSwarm Task Memory and Coding Memory strictly as the durable working context for the agents.
*   **Future State (Blacklist for M1):**
    *   Storing raw telemetry, benchmark standard outputs (`stdout`/`stderr`), or large execution logs in Task/Coding memory (this prevents context window overflow).

#### 4.5.2 TaskGraph Persistence & Run Bundles (System Memory)
*   **Definition & Expectation:** Stores and versions executable TaskGraph specifications and their runtime state, including nodes, dependencies, results, and raw evidence.
*   **M1 State (Whitelist):**
    *   **Run Evidence Capture:** Workflow hooks capture the prompt, inputs, outputs, full execution traces, and raw gate/verifier evidence. 
    *   **Run Bundles:** Raw evidence is saved into isolated, flat local directories (e.g., `records/bundles/<run_id>/`), providing a complete snapshot of the worker's workspace at execution end.
    *   **Effective Run Manifest:** Each run must preserve the resolved execution configuration required for reproduction and benchmark attribution, including the active capsule-library snapshot/hash, capsule versions used by governed stages, model-routing configuration, evaluation profile, RSI participation state where applicable, effective seed where supported, and other benchmark-relevant configuration identifiers. These recorded values must reflect what actually executed rather than only what was requested.
    *   **Capsule Run Record:** A structured, append-only local file (`records.jsonl`) logs every capsule execution, capturing execution latency, invocation counts, model-routing decisions, failure classes, and token/cost telemetry when the active model endpoint exposes sufficiently reliable usage information.
*   **Future State (Blacklist for M1):**
    *   Multi-user data separation, redaction of sensitive internal text, or automatic trace deduplication.

#### 4.5.3 Contract & Capability Conformance Observability
*   **Definition & Expectation:** Validates observed runtime behavior against the active Node Execution Contract and the admitted declarations of participating Capability Capsules, and generates performance visibility.
*   **M1 State (Whitelist):**
    *   **Declared vs. Observed:** Compare each Capability Capsule's admitted interface, required resources, permitted effects, and implementation declaration against its actual execution trace, explicitly flagging undeclared tool usage, out-of-bound effects, or materially inconsistent behavior.
    *   **Capsule Scorecards:** Generate static Markdown and JSON scorecards detailing pass rates, failure reasons, runtime measurements, and available token/cost telemetry per capsule version. Missing token or cost telemetry must be represented as unavailable rather than inferred.
*   **Future State (Blacklist for M1):**
    *   Persistent telemetry dashboards, web UIs, or host-level CPU/GPU utilization tracking during runs.

#### 4.5.4 Sample Run Exports (Scaffolding for RSI Handoff)
*   **Definition & Expectation:** Packages frozen copies of real runs to serve as the foundational training and testing data for the Local-Isolated RSI engine.
*   **M1 State (Whitelist):**
    *   **Local Data Scaffolding:** Export run bundles and execution records with fixed labels and content hashes to a dedicated local directory (`records/exports/<export_id>/`). This explicitly builds the local data bridge managed by the part-time data observability workstream to support the full-time RSI optimization engine.
    *   **Decoupled Handoff:** The data foundation handles the extraction and formatting of these records into the local workspace, while the actual consumption of this data is dependent on the separate, full-time RSI module.
*   **Future State (Blacklist for M1):**
    *   Generating synthetic runs or building automated pathways that write offline experiment data back into the live workflow.

#### 4.5.5 Extended Graph Management (Future State Only)
*   **Definition & Expectation:** The distributed, highly scalable architecture for modeling relationships across the entire research lifecycle.
*   **M1 State:** 
    *   **Strictly Blacklisted.**
*   **Future State (Deferred to M2+):**
    *   **Concept Graph:** Modeling business concepts, entities, and terminology.
    *   **Dataset Graph:** Registering dataset schemas, dependencies, and quality states
    *   **Code Graph:** Modeling repositories, ASTs, APIs, and module dependencies.
    *   **Policy & Workflow Graphs:** Representing security rules, SOPs, and approval chains.
    *   **Trace & Memory Graphs:** Connecting cross-run operator decisions, evaluations, and learned lessons into an auditable, queryable enterprise knowledge base.



### 4.6 Harness Core

**Description:** The foundational execution layer that drives workflow orchestration, node scheduling, and process lifecycle within AI4Research. The Harness Core is built on JiuwenSwarm and uses SwarmFlow for deterministic Phase 1 workflow execution while preserving the integration boundary required for Agent Team / Cluster Mode behavior in M1 Delivery Phase 3. It dispatches tasks to the local Capability Capsule Runner, captures node-level states, and mediates handoffs to the Evaluator Gate without requiring external message brokers or distributed cluster infrastructure.

#### 4.6.1 Runtime Control Loop & Run Lifecycle Management
*   **Definition & Expectation:** Initializes run identity and session configuration, drives the central state machine loop, maintains durable node execution states, and safely concludes runs when all required nodes and gates are satisfied.
*   **M1 State (Whitelist):**
    *   **JiuwenSwarm SwarmFlow Execution:** Leverage JiuwenSwarm's SwarmFlow execution pathway to initialize, step through, and terminate deterministic Phase 1 research runs.
    *   **Node-Level State Transitions:** Maintain deterministic state progressions (`Pending` $\rightarrow$ `Running` $\rightarrow$ `Evaluating` $\rightarrow$ `Completed` / `Failed`) in memory, writing state snapshots directly to the local run log.
*   **Future State (Blacklist for M1):**
    *   Integration with autonomous evaluation harnesses (Auto Harness) that dynamically spawn recursive sub-runs to self-evaluate pipeline orchestration.

#### 4.6.2 DAG Scheduler & Operator Binding
*   **Definition & Expectation:** Validates TaskGraph dependencies, determines step readiness based on prior outputs and gate verdicts, and binds execution parameters to the target node.
*   **M1 Phase 1 Scope (Static Baseline):**
    *   **Deterministic Sequential Scheduling:** Use JiuwenSwarm's SwarmFlow scheduling pathway to execute the hardcoded Phase 1 Default DAG (Stages 3.1 through 3.9) in an immutable linear sequence.
    *   **Gate-Locked Advancement:** Downstream nodes remain strictly locked until an explicit `PASS` or `PASS_WITH_KNOWN_LIMITATIONS` signal is received from the 4.2 Evaluator Gate.
*   **M1 Delivery Phase 3 Scope (Dynamic System Integration):**
    *   **Agent Team / Cluster Mode Integration:** Evaluate and integrate JiuwenSwarm Agent Team / Cluster Mode for dynamic planning, task decomposition, capability resolution, dependency management, and conditional execution against the deterministic Phase 1 baseline. The deterministic SwarmFlow pathway remains available as the release-critical fallback.
*   **Future State (Blacklist for M1):**
    *   Dynamic parallel batching (concurrent multi-arm experimental execution) or live runtime DAG restructuring on the primary production branch.

#### 4.6.3 Main Loop Dispatch & Runtime Supervision
*   **Definition & Expectation:** Consumes resolved capsule bindings, constructs execution envelopes, dispatches tasks to the local runner, monitors progress/health, and packages output bundles for evaluation.
*   **M1 State (Whitelist):**
    *   **Local Process Dispatch:** Directly invoke the local Capability Capsule (CC) Runner as a managed subprocess.
    *   **Timeout & Health Monitoring:** Enforce declared capsule time budgets to catch hung processes; log timeouts as execution faults.
    *   **Evidence Packaging:** Bundle stdout, stderr, returned artifacts, and execution metrics into a standardized Stage Evidence Bundle, handing it directly to the 4.2 Evaluator Gate before releasing the node.
*   **Future State (Blacklist for M1):**
    *   Dispatching tasks across remote worker fleets, external container runtimes, or distributed cloud execution clusters.

#### 4.6.4 Failure Recovery & Resumability
*   **Definition & Expectation:** Detects failed or stale node executions, determines recovery pathways, safely handles faults, and recovers state without unneeded reruns.
*   **M1 State (Whitelist):**
    *   **Fail-Fast HITL Routing:** Disable autonomous multi-turn retry loops upon execution crash, syntax error, or gate rejection (`FAIL` / `ENVIRONMENT_BLOCKED`). The harness immediately halts autonomous execution, records forensic evidence, and invokes OpenJiuwen's native `human_session` terminal prompt for developer triage.
    *   **Headless Evaluation Halt:** When a run is explicitly launched in non-interactive development/evaluation mode, any condition that would normally invoke `human_session` must instead durably record the blocking verdict, halt reason, and available evidence in the run tree, terminate autonomous execution, and return a stable non-zero completion status without waiting for human input. Headless mode changes only the interaction behavior after a halt; it does not weaken, bypass, or reinterpret Evaluator Gate policy.
    *   **Clean Empirical Baseline:** Preserve failed runs as raw failure records to maintain scientific repeatability rather than masking bugs through automated retries.
*   **Future State (Blacklist for M1):**
    *   Autonomous self-healing code repair loops, multi-round automated requeueing, or complex partial-DAG state rewind/resumption without human review.

#### 4.6.5 Distributed Infrastructure & Concurrency (Future State Only)
*   **Definition & Expectation:** Enterprise-scale infrastructure designed for multi-tenant scheduling, high-throughput message brokering, and cluster resource arbitration.
*   **M1 State:**
    *   **Strictly Blacklisted.** M1 research execution is restricted to a single authorized local execution host and does not require distributed worker leasing, multi-host scheduling, or concurrency arbitration. This execution boundary does not preclude cloud-backed account/profile persistence defined elsewhere in the product model.
*   **Future State (Deferred to M2+):**
    *   **Message Bus & Persistent Queueing:** Brokering tasks via distributed systems (Kafka, RabbitMQ, Celery) with priority ordering and backpressure management.
    *   **Execution Admission & Distributed Leases:** Acquiring, renewing, and reaping task leases across multi-node worker pools to prevent duplicate dispatch.
    *   **Cluster Quota Enforcement:** Multi-user resource allocation, team token throttling, and dynamic GPU capacity balancing.


### 4.7 Intention Compilers

> **Architectural Note & External Dependency Strategy (Ontario Integration Handoff):**
> Advanced intention compilation is an external dependency currently being developed by a cross-office intern in Ontario. To prevent this external dependency from blocking M1 development, the AI4Research platform adopts the same dual-path strategy used for the Codex CLI:
> * **Phase 1 Fixed-Flow Baseline (Immediate Build):** We implement a self-contained, one-shot intention compiler that uses a single bounded LLM pass to transform raw intake text into the rigid `Research Brief` JSON schema required by the SwarmFlow Default DAG. The prompt, schema, defaults, and execution path are fixed: there is no interactive clarification, autonomous replanning, or dynamic workflow selection.
> * **M1 Delivery Phase 3 Modular Integration (Standardized Target Interface):** The sub-features below define the standardized contract and output envelope expected from the Ontario intern's module. When completed, their dynamic/interactive intention compiler will plug directly into the M1 Delivery Phase 3 Agent Team / Cluster Mode integration pathway without requiring downstream workflow nodes to change their input contract.
> * **Permanent Fixed-Flow Fallback:** The Phase 1 one-shot compiler will remain available as a stable fallback pathway after the dynamic compiler is introduced. It preserves the fixed `Research Brief` interface and bounded one-pass behavior, but still requires the configured M1 model endpoint for semantic extraction.

**Description:** The semantic translation layer at the front door of the workstation. It transforms unstructured, natural-language research queries and attached reference materials into standardized, machine-executable task contracts (`Research Brief`).

#### 4.7.1 Intent Classification & Compilation Variant Selection
*   **Definition & Expectation:** Classify the request as implementation, full specification, or research, and select the corresponding lane, output variant, priority, and acceptance profile.
*   **M1 Phase 1 Scope (Static Baseline):**
    *   **Fixed Domain Lane:** Lock classification strictly to the *Scientific Research* lane, bypassing multi-lane branching.
    *   Map incoming prompts directly to the standard research acceptance profile defined in Stage 3.2.
*   **M1 Delivery Phase 3 Scope (Dynamic Intention Compiler Integration):**
    *   Support dynamic request classification, distinguishing between exploratory research synthesis, code implementation tasks, and formal engineering specifications.
*   **Future State (Blacklist for M1):**
    *   Dynamic multi-modal intent classification or real-time priority re-ranking during execution.

#### 4.7.2 Goal, Scope and Context Normalization
*   **Definition & Expectation:** Extract goals, parameters, priorities, success conditions, scope, and non-goals, while collecting only relevant repository, file, attachment, and historical context.
*   **M1 Phase 1 Scope (Static Baseline):**
    *   Execute a single-turn LLM pass to extract the core research objective, explicit parameters, and binary `in_scope` vs. `out_of_scope` lists based strictly on provided intake text.
    *   Bind local document buffers ingested during Stage 3.1 directly to the compiled context.
*   **M1 Delivery Phase 3 Scope (Dynamic Intention Compiler Integration):**
    *   Autonomous semantic filtering across larger local repositories, historical context extraction, and automated non-goal synthesis.
*   **Future State (Blacklist for M1):**
    *   Live internet scraping (e.g., querying arXiv or Google Scholar) to dynamically augment missing context during intake compilation.

#### 4.7.3 Ambiguity Resolution & Readiness
*   **Definition & Expectation:** Detect missing, conflicting, or unclear requirements; generate the minimum necessary clarification questions; determine whether the intent is ready for planning.
*   **M1 Phase 1 Scope (Static Baseline):**
    *   **Hardcoded Defaults:** Incur zero interactive overhead. Apply conservative, hardcoded defaults for missing parameters (e.g., default missing hardware specifications to `single_gpu`).
    *   Programmatic readiness assertions: Verify core objective and input directory paths are non-empty before declaring readiness.
*   **M1 Delivery Phase 3 Scope (Dynamic Intention Compiler Integration):**
    *   Engage OpenJiuwen's native Leader Agent to test multi-turn, interactive clarification dialogues with the human user to resolve ambiguous bounds before dispatch.
*   **Future State (Blacklist for M1):**
    *   Autonomous intent extrapolation (hallucinating user intent without confirmation).

#### 4.7.4 Constraint Compilation
*   **Definition & Expectation:** Convert budget, time, permission, data, security, quality, and side-effect requirements into enforceable constraints, including required approvals.
*   **M1 State (Whitelist):**
    *   Extract declared compute boundaries—including requested token limits, execution-time limits, target hardware, and other explicit resource constraints—from the user input.
    *   Compile these boundaries into structured fields within the `Research Brief` contract.
    *   For the M1 Codex CLI baseline, the CC Runner and Evaluator Gate mechanically enforce execution-time and invocation-count limits. Token limits remain recorded declarative constraints and become mechanically blocking only when the active model endpoint exposes sufficiently reliable usage telemetry.
    *   Compile extracted boundaries into programmatic fields within the `Research Brief` contract to be enforced by the CC Runner and Evaluator Gate.
*   **Future State (Blacklist for M1):**
    *   Dynamic host profiling (scanning local system hardware to infer constraints) or autonomous runtime permission negotiation.

#### 4.7.5 Task Contract & Acceptance Compilation
*   **Definition & Expectation:** Produce a stable, versioned task contract containing normalized inputs and outputs, objectives, constraints, acceptance criteria, and required evidence.
*   **M1 Phase 1 Scope (Static Baseline):**
    *   **The Research Brief Contract:** Package all extracted objectives, scope limits, constraints, user-level target metrics, and acceptance expectations into a standardized, schema-bound `Research Brief` JSON payload.
    *   Pass this static JSON payload explicitly to the deterministic SwarmFlow script to trigger downstream nodes.
*   **M1 Delivery Phase 3 Scope (Dynamic Intention Compiler Integration):**
    *   Compile the task contract into executable task semantics directly consumable by the Cluster Mode Planner / Leader Agent for dynamic routing.
*   **Future State (Blacklist for M1):**
    *   Dynamic post-hoc contract modification after DAG execution begins.




### 4.8 Planner

**Description:** The orchestration layer responsible for translating the compiled intention contract into an executable workflow graph. M1 uses a staged integration strategy: M1 Delivery Phase 1 establishes the deterministic SwarmFlow fallback with autonomous planning disabled, while M1 Delivery Phase 3 integrates JiuwenSwarm Agent Team / Cluster Mode and its Leader Agent for dynamic task decomposition, TaskGraph generation, dependency management, and capability binding. Dynamic planning extends the M1 system but must preserve the validated deterministic fallback.

#### 4.8.1 Task Contract Decomposition
*   **Definition & Expectation:** Interpret the validated task contract, select an appropriate planning pattern, and split the goal into bounded work units with explicit objectives, inputs, outputs, and completion conditions. Generate planning artifacts for RSI optimization.
*   **M1 Phase 1 Scope (Static Baseline):**
    *   **Bypassed by Design:** Autonomous decomposition is disabled. The work units are permanently pre-defined as the sequential stages of the SwarmFlow Default DAG (Ingestion through Delivery).
*   **M1 Delivery Phase 3 Scope (Dynamic Planning):**
    *   **Leader Agent Decomposition:** The native Cluster Mode Leader Agent receives the `Research_Brief.json` from the Intention Compiler and dynamically attempts to break the core objective down into discrete, bounded research sub-tasks.
*   **Future State (Blacklist for M1):**
    *   Dynamic mid-flight re-decomposition (scrapping and rewriting the sub-tasks if a workflow step fails) or complex sub-agent delegation trees.

#### 4.8.2 TaskGraph Construction
*   **Definition & Expectation:** Compile the work units into a logical TaskGraph (DAG), defining dependencies, parent-child relationships, ordering, parallelizable branches, and critical paths.
*   **M1 Phase 1 Scope (Static Baseline):**
    *   **Immutable Python Graph:** The TaskGraph is statically constructed as a hardcoded SwarmFlow Python script. Node dependencies are manually wired, ensuring execution flows in a strict, linear progression.
    *   **User-Specific Parameter Injection:** While the node sequence is fixed, the script programmatically reads the `Research_Brief.json` and injects the user's specific variables (core objective, hardware constraints, metrics) directly into the hardcoded nodes. This guarantees the predetermined sequence still executes a highly personalized, user-specific run.
*   **M1 Delivery Phase 3 Scope (Dynamic Planning):**
    *   **Dynamic Graph Generation:** The Leader Agent dynamically maps the inputs and outputs of its decomposed work units, establishing ad-hoc parent-child relationships and ordering before passing the graph to the Harness Core.
*   **Future State (Blacklist for M1):**
    *   Generating massive parallelizable branches (e.g., designing an execution graph that tests 50 hypotheses simultaneously across a distributed compute cluster) or generating execution loops.

#### 4.8.3 TaskGraph Validation & Feasibility Analysis
*   **Definition & Expectation:** Validate schema completeness, missing dependencies, execution cycles, requirement coverage, and capability feasibility. Block invalid plans or return them for clarification.
*   **M1 Phase 1 Scope (Static Baseline):**
    *   **Programmatic Pre-Checks:** Validation is handled via standard Python syntax checking and pre-run startup assertions. Infinite execution cycles are mathematically impossible due to the linear, unidirectional nature of the Default DAG.
*   **M1 Delivery Phase 3 Scope (Dynamic Planning):**
    *   **Pre-Dispatch Evaluation:** The Leader Agent evaluates its own dynamically generated graph to detect disconnected nodes, missing data dependencies, or capability mismatches. If the graph is infeasible, it routes back to the Intention Compiler for replanning.
*   **Future State (Blacklist for M1):**
    *   Autonomous multi-agent peer review of the proposed execution plan (e.g., a "Red Team" agent actively trying to find flaws in the generated TaskGraph prior to execution).



### 4.9 Builder

> **Architectural Distinction & Runtime Role (Builder vs. CC Runner):** 
> The platform strictly separates general reasoning execution from executable artifact synthesis. All upstream and downstream analytical stages (Stages 3.1–3.5 and 3.8–3.9) are executed by the universal **Capability Capsule Runner (CC Runner)** acting as a generic runtime worker dynamically parameterized by markdown capsules. In contrast, the **Builder** is the dedicated generative construction engine responsible for filesystem scaffolding, syntax-checked code synthesis (`poc_patch.py`), harness wiring (`run_benchmark.py`), and testable bundle packaging (`POC_Artifact_Bundle.zip`).

**Description:** The executable artifact construction engine of the workstation. In the M1 Phase 1 baseline, the Builder is invoked specifically by Stage 3.6 POC Implementation to translate the immutable `Hypothesis_Blueprint.json` into bounded executable artifacts: workspace scaffolding, `requirements.txt`, `poc_patch.py`, `run_benchmark.py`, mechanical build evidence, and the final `POC_Artifact_Bundle.zip`. Analytical workflow outputs—including Opportunity Cards, Hypothesis Blueprints, scientific Evaluation Verdicts, and final research reports—remain the responsibility of their dedicated workflow stages executed through the Capability Capsule Runner.

#### 4.9.1 Build Contract Interpretation & Preparation (Sub-features 1 & 2)
*   **Definition & Expectation:** Translate the task or build contract into implementation goals, interfaces, write scopes, acceptance conditions, and prohibited changes. Prepare source materials, dependencies, templates, data paths, workspaces, and pre-build readiness checks.
*   **M1 Phase 1 Scope (Static Baseline):**
    *   Ingest the immutable `Hypothesis_Blueprint.json` generated in Stage 3.5.
    *   Initialize the isolated local workspace directory (`/workspace/poc/`) and verify that target baseline code files and validation datasets are present.
*   **M1 Delivery Phase 3 Scope (Code Mode Integration):**
    *   Evaluate OpenJiuwen Code Mode's automated workspace provisioning and dependency discovery tools on an isolated feature branch.
*   **Future State (Blacklist for M1):**
    *   Dynamic container provisioning (Docker/Kubernetes pods) or unconstrained filesystem access.

#### 4.9.2 Code & Experimental Asset Construction (Sub-features 3, 5, 6, & 7)
*   **Definition & Expectation:** Create or modify deterministic source code, scripts, tests, and configuration to implement the required technical function. Build experiment code, data processing, instrumentation, environment descriptions, benchmark harnesses, baseline comparison runners, and verification scripts.
*   **M1 Phase 1 Scope (Static Baseline):**
    *   **Single-File Patch Generation:** Generate a standalone Python patch script (`poc_patch.py`) via `poc_capsule.md` implementing the technical mechanism specified in the blueprint.
    *   **Benchmark Harness Assembly:** Generate `run_benchmark.py` to execute the baseline and the modified patch side-by-side using fixed random seeds and identical evaluation datasets.
    *   **Safety Constraints:** Enforce strict prompt-level blacklists blocking system-level and network modules (`os`, `sys`, `subprocess`, `requests`, `urllib`, `shutil`) to mitigate host execution risks.
*   **M1 Delivery Phase 3 Scope (Code Mode Integration):**
    *   Test OpenJiuwen Code Mode's AST-aware line-level diff generation and multi-file refactoring.
*   **Future State (Blacklist for M1):**
    *   Autonomous multi-file repository refactoring on the production release path.

#### 4.9.3 Analytical Deliverable Boundary
*   **Definition & Expectation:** Defines the boundary between executable artifact construction performed by the Builder and analytical/narrative artifact generation performed by workflow-specific Capability Capsules.
*   **M1 State (Whitelist):**
    *   The Builder may read upstream analytical contracts required to construct the POC, including `Research_Brief.json` and the immutable `Hypothesis_Blueprint.json`.
    *   The Builder may generate build-specific manifests, execution configuration, code artifacts, compile evidence, and packaging metadata required by Stage 3.6.
    *   `Opportunity_Card.json` remains the output of Stage 3.4.
    *   `Hypothesis_Blueprint.json` remains the output of Stage 3.5.
    *   `Evaluation_Verdict.json` remains the output of Stage 3.8.
    *   `research_report.md` remains the output of Stage 3.9.
    *   These analytical artifacts are generated by their dedicated capsules through the CC Runner and must not be independently regenerated or semantically modified by the Builder.

*   **Future State (Blacklist for M1):**
    *   A generalized Builder that synthesizes arbitrary analytical documents, publication manuscripts, slide decks, posters, or interactive dashboards.

#### 4.9.4 Prototype Assembly & Build Evidence Generation (Sub-features 9 & 12)
*   **Definition & Expectation:** Combine code, models, data, and interfaces into a bounded, runnable, and demonstrable proof of concept. Generate diffs, manifests, hashes, compile and test results, provenance, and acceptance evidence for the build.
*   **M1 State (Whitelist):**
    *   **Artifact Bundle:** Package `requirements.txt`, `poc_patch.py`, and `run_benchmark.py` into a standardized `POC_Artifact_Bundle.zip` ready for handoff to Stage 3.7 Benchmarking.
    *   **Smoke Validation:** Execute a mechanical syntax compilation check (`python -m py_compile run_benchmark.py`) to confirm executable readiness before packaging.
*   **Future State (Blacklist for M1):**
    *   Generating container images, deployment wheels, or runtime services for cloud clusters.

#### 4.9.5 Excluded Capabilities & Advanced Lifecycle Features (Sub-features 4, 10, 11, & 14)
*   **Definition & Expectation:** Training/fine-tuning models, product integration, autonomous defect repair loops, and building executable deployable services or containers.
*   **M1 State:**
    *   **Strictly Blacklisted.** 
    *   **Model Construction (Sub-feature 4):** Building, training, or fine-tuning neural network weights, LoRA adapters, or statistical ML model checkpoints is strictly prohibited (workstation execution is restricted to inference and scripting).
    *   **Defect Repair (Sub-feature 11):** If code fails compilation or execution, autonomous iterative defect-repair loops are disabled. The failure trace is recorded immediately, halting execution to OpenJiuwen's native `human_session` prompt.
*   **Future State (Deferred to M2+):**
    *   **Product Integration (Sub-feature 10):** Integrating verified components directly into target product interfaces, data flows, and production repositories.
    *   **Automated Defect Repair (Sub-feature 11):** Agent-driven error reflection, trace parsing, and iterative multi-turn patch generation.
    *   **Runtime Deliverable Construction (Sub-feature 14):** Building executable or deployable services, containers, workflow bundles, and cloud deployment configurations.




---

## 5. Vertical Features (The Platform Shell)

> **Architectural Note (Data Foundations Integration):** 
> This section works hand-in-hand with the part-time intern's Data Foundation architecture (Section 4.5). While Data Foundations dictates *how* execution evidence is captured and stored to disk, this Visibility section dictates *how* the user and developers actually monitor that telemetry. For M1, we strictly avoid building custom web UIs or persistent databases, relying entirely on OpenJiuwen's native real-time monitors and the Data Foundation's static file exports.

### 5.1 Visibility & Statistics (Telemetry)

**Description:** The telemetry and observability layer of the platform. It provides researchers and developers with insights into workflow progress, agent decisions, token costs, and system health. M1 relies heavily on native platform monitors and offline static files, deferring complex distributed tracking to future enterprise milestones.

#### 5.1.1 Workflow & Platform Status Visibility
*   **Definition & Expectation:** Show workflow progress, blockers, gates, budgets, and the health of hosts, providers, queues, data sources, and other platform components without changing authoritative runtime state.
*   **M1 State (Whitelist):**
    *   **Native Run-Tree:** Utilize OpenJiuwen's native `/swarmflows` run-tree monitoring to provide live, real-time observability of the executing DAG.
    *   **Terminal Output:** Expose live node transitions, Evaluator Gate verdicts (`PASS`, `FAIL`, `BLOCKED`), and execution halts directly in the local CLI or native Web UI.
*   **Future State (Blacklist for M1):**
    *   Custom persistent telemetry dashboards, interactive web-based workflow visualizers, or multi-run aggregate reporting UIs.

#### 5.1.2 Execution Trace Search & Inspection
*   **Definition & Expectation:** Search and inspect time-ordered requests, transitions, tool calls, approvals, failures, artifacts, decisions, and outcomes using filters for project, run, actor, and time range.
*   **M1 State (Whitelist):**
    *   **Static File Observability:** Delegate trace inspection to the offline artifacts generated by the Data Foundation. Developers inspect historical traces by reading the append-only `records.jsonl` and opening isolated Run Bundles (`records/bundles/<run_id>/`).
    *   **Capsule Scorecards:** Generate static Markdown (`scorecard.md`) and JSON files summarizing pass rates, undeclared tool behavior, and failure traces per capsule version, enabling offline review without a database.
*   **Future State (Blacklist for M1):**
    *   Building an interactive search engine (e.g., Elasticsearch/Kibana integration) to dynamically filter and inspect traces across thousands of runs.

#### 5.1.3 Resource Usage, Cost & Capacity Management
*   **Definition & Expectation:** Report model, compute, token, tool, storage, data, quota, human-review, budget, cost, and capacity consumption by project, experiment, capability, and time.
*   **M1 State (Whitelist):**
    *   **Authoritative Runtime Budgets:** Monitor capsule execution duration and model/tool invocation counts using native JiuwenSwarm runtime and security telemetry. These mechanically observable values form the enforceable M1 runtime-budget controls.
    *   **Best-Effort Token & Cost Visibility:** Record token usage and estimated monetary cost only when reliable usage telemetry is supplied by the active model endpoint. Under the temporary Codex CLI adapter, these fields may be null or unavailable and are informational rather than authoritative.
    *   **Offline Budget Accounting:** Persist observed execution duration, invocation counts, available token/cost telemetry, and configured budget limits within the structured Capsule Run Record after each node completes.
*   **Future State (Blacklist for M1):**
    *   Organization-wide cross-user chargebacks, dynamic cluster capacity allocation, or integration with external cloud billing APIs.

#### 5.1.4 Runtime Status Visibility
*   **Definition & Expectation:** Statistics like CPU usage, GPU usage, etc.
*   **M1 State:**
    *   **Strictly Blacklisted.** 
    *   *Static Hardware Profiling Only:* M1 is restricted to capturing static host facts (Operating System, CPU core count, GPU model) exactly *once* at run start via Data Foundation hooks. 
    *   Continuous, real-time sampling of host-level CPU, GPU, or RAM utilization during an active run is strictly excluded to prevent instrumentation overhead.
*   **Future State (Deferred to M2+):**
    *   Live container resource monitoring, distributed hardware dashboards, and dynamic load-balancing based on real-time hardware telemetry.



### 5.2 Installer & CLI & Webapp

**Description:** The deployment, system bootstrapping, and runtime initialization layer for the workstation. In M1, the platform standardizes entirely on Python packaging and a single initialization command to launch local background processes and browser-based status views. Standalone compiled OS binaries, desktop shells, and automated self-updating channels are strictly deferred to future enterprise releases.

#### 5.2.1 CLI Installation & Workstation Initialization (MacOS & Linux - Sub-features 3 & 4)
*   **Definition & Expectation:** Install and operate the CLI on macOS and supported Linux distributions, executing dependency checks, PATH and configuration initialization, provider-authentication readiness, and status and doctor checks.
*   **M1 State (Whitelist):**
    *   **Upstream Engine Bootstrap:** Package delivery is standardized strictly via `pip install jiuwenswarm`, with local process and environment orchestration triggered through the single command `jiuwenswarm-start`.
    *   **Workstation Workspace Scaffolding:** Automated creation of the core filesystem hierarchy required across the workflow pipeline:
        *   `./workspace/input/` for raw user reference materials and document ingestion (Stage 3.1).
        *   `./workspace/poc/` for sandboxed proof-of-concept script generation and harness execution (Stages 3.6 and 3.7).
        *   `records/runs/`, `records/bundles/`, and `records/exports/` for durable append-only run logging, stage evidence capture, and offline export bundles (Section 4.5 Data Foundations).
    *   **RSI & Benchmark Fixture Scaffolding:** Automated provisioning of the lightweight Local-Isolated RSI workspace (`.jiuwenswarm/rsi/tasks/`) and the local Secure Fixture Oracle directory outside the public Git repository. Configure the directory ownership and POSIX permissions required by the Fixture Oracle design in Section 4.4.9, while ensuring that the restricted SwarmFlow execution identity used for untrusted capsule/POC execution cannot directly read the hidden fixture contents. Seed the initial manually authored benchmark sets defined in Sections 4.4.8 and 4.4.9.
    *   **Capsule Registry Seeding:** Automated deployment of the version-locked Capability Capsule implementation resources and prompts (`search_capsule.md` through `report_capsule.md`), alongside their corresponding `capsule.json` declarations and interface hashes, into the local registry (Section 4.1).
    *   **Workstation System Configuration & Doctor Pre-Checks:** 
        *   Bind local system variables, single-user profile parameters, and hardware defaults via `config.yaml` (Section 5.6).
        *   Configure platform telemetry flags required by the Data Foundation (enabling the lossless trajectory store, raising the trace truncation limit, and enabling the sandbox activity log).
        *   Perform pre-flight doctor checks verifying that the Section 3.0 Codex CLI adapter process is active and authenticated, required local paths are readable, and the Default DAG python script is structurally sound.
    *   **Research Execution Entry Point:** Provide a direct terminal CLI invocation command accepting natural-language research questions via arguments (e.g., `--topic`) and passing user inputs into Stage 3.1 Ingestion.
*   **Future State (Blacklist for M1):**
    *   Automated multi-platform background update channels, self-updating binaries, automated backup and restore commands, or dynamic environment-configuration setup wizards.

#### 5.2.2 Web Application & Status Service (Sub-feature 5)
*   **Definition & Expectation:** Build, serve, configure, and health-check the browser-based application and status API; connect it to authentication, configuration, workflow state, runtime visibility, and artifact views across development and packaged deployments.
*   **M1 State (Whitelist):**
    *   **Local Web Server Initialization:** Bootstrapped automatically alongside the background engine via `jiuwenswarm-start`, binding OpenJiuwen's native Web UI strictly to `127.0.0.1:5173`. To authenticate the local session without a login portal, the CLI generates a one-time loopback URL containing the ephemeral authorization token (e.g., `http://127.0.0.1:5173/?auth_token=...`), which the browser caches for local API requests.
    *   **Runtime Context & State Binding:** Connect the web client directly to the active single-user session, displaying live `/swarmflows` workflow progress, Evaluator Gate transition states, and node completion events (Section 5.1).
    *   **Artifact Views & Interactive Prompting:** Support natural-language prompt intake via the web prompt box (Stage 3.1.1) and render the final synthesized markdown deliverable upon reaching Stage 3.9 Delivery.
*   **Future State (Blacklist for M1):**
    *   Cloud-hosted web application deployments, public network bindings, or remote multi-tenant status APIs serving distributed clusters.

#### 5.2.3 Native Desktop Applications (Windows & MacOS - Sub-features 1 & 2)
*   **Definition & Expectation:** Package, install, launch, update, repair, and uninstall native desktop applications on Windows and macOS; guide first-run permissions, runtime, and provider setup, preserve user data, and produce installation evidence.
*   **M1 State:**
    *   **Strictly Blacklisted.** Standalone compiled desktop binaries (such as `.exe` or `.dmg` bundles) are entirely excluded for M1. Workstation interaction is restricted to the terminal CLI and the locally served web interface.
*   **Future State (Deferred to M2+):**
    *   Packaged cross-platform desktop shells (e.g., built with Electron or Tauri), guided first-run GUI setup wizards, OS-level permission managers, and background auto-update daemons.



### 5.3 UI

**Description:** The user-facing operational interfaces for the workstation. M1 intentionally avoids building custom, proprietary interactive components from scratch. Instead, it relies on OpenJiuwen's default out-of-the-box UI tooling (CLI, native Webapp, and terminal GUI) with lightweight cosmetic branding to monitor the deterministic DAG pipeline and retrieve standard outputs.

#### 5.3.1 Command-Line Interface (CLI)
*   **Definition & Expectation:** Provide a scriptable command-response interface for submitting work, inspecting status, managing lifecycle and configuration, and retrieving logs, artifacts, and evidence, with stable exit codes and human-readable or structured JSON output.
*   **M1 State (Whitelist):**
    *   **Pipeline Entry:** Expose standard `jiuwenswarm` CLI arguments to pass the user's research string directly to the Phase 1 static SwarmFlow DAG (e.g., `jiuwenswarm run default_dag.py --topic "..."`).
    *   **Headless Development/Evaluation Entry:** Support an explicit non-interactive execution mode for automated testing and platform benchmarking. A headless run must accept the task input, an explicit run configuration, and a reproducibility seed where supported; execute without interactive prompts; and return machine-readable completion information including the `run_id` and a reference to the resulting Run Bundle. The requested and effective seed must be recorded in run evidence. M1 does not claim deterministic model output where the active model endpoint does not provide deterministic seed control.
    *   **Synchronous Monitoring:** Return human-readable standard output (`stdout`) to the terminal, detailing DAG node transitions, tool invocations, and Tier-1 Evaluator Gate fault flags.
    *   **Stable Completion Status:** Emit stable process exit codes and structured terminal status for successful completion, infrastructure/gate failure, environment blocking, and other required terminal conditions. In headless mode, these statuses must be sufficient for an automated benchmark harness to determine whether the run completed or halted without requiring interactive inspection.
*   **Future State (Blacklist for M1):**
    *   Complex interactive CLI shell environments replacing the native terminal, or deep custom ASCII visualizations.

#### 5.3.2 Web Graphical User Interface (GUI)
*   **Definition & Expectation:** Provide a graphical desktop or web interface for task intake, setup and configuration, workflow and gate monitoring, approval, artifact and evidence inspection, and deliverable access, including loading, empty, error, and accessibility states.
*   **M1 State (Whitelist):**
    *   **Native Web Workbench:** Deploy OpenJiuwen's default web UI (bound locally on `127.0.0.1:5173`) serving as an intake prompt box, run-tree observation pane, and artifact delivery viewer.
    *   **Static Brand Skinning:** Override native OpenJiuwen environment variables and static asset folders to inject the AI4Research logo, update browser page titles, and apply basic CSS color-variable tweaks to visually distinguish the fork's identity.
    *   **DAG State Visualization:** Surface the active nodes, queue status, and `/swarmflows` run-tree progress through the native default widgets.
    *   **Deliverable Retrieval:** Provide a view allowing the user to read the final markdown research report generated in Stage 3.9 Delivery directly within the browser UI.
    *   *Anti-Interactive Bound:* In M1, the GUI is *not* used for complex setup wizards, mid-flight workflow modification, or adjusting gate falsifiability bounds. It is an intake and output monitor.
*   **Future State (Blacklist for M1):**
    *   Custom-built interactive React widgets tailored exclusively for the AI4Research product (e.g., bespoke "Hypothesis Visualizers"), interactive drag-and-drop workflow builders, or cloud-hosted user portal deployments.

#### 5.3.3 Terminal User Interface (TUI)
*   **Definition & Expectation:** Provide an interactive terminal interface for monitoring runs, TaskGraph nodes, agents or panes, queues, gates, logs, and resource state, and for issuing explicit authorized control actions through keyboard-driven views.
*   **M1 State (Whitelist):**
    *   **Native TUI Deployment:** Package and expose the default `jiuwenswarm-tui` interface.
    *   **Human-In-The-Loop (HITL) Fallback:** The TUI primarily serves as the interactive fallback layer. If a node fails (e.g., POC execution crashes in Stage 3.7), the workflow halts and routes directly to the native `human_session` prompt, allowing developers to inspect logs and trace data within the TUI before manually aborting or correcting the run.
*   **Future State (Blacklist for M1):**
    *   Custom TUI widgets displaying dynamic capability capability rubrics, complex RSI loop visualizations, or real-time distributed hardware heatmaps.



### 5.4 Account Management & Local Security Controls

> **Architectural Note (User Identity vs. Local Execution Isolation):**
> AI4Research separates durable user/account identity from the local execution environment used for research work. Account/profile state may be persisted through an approved cloud-backed product service, while project assets, generated POC execution, Codex CLI bridging, and Local-Isolated RSI may remain within an authorized local execution boundary. Local operating-system identity and local session tokens protect the execution environment but are not the sole or permanent definition of the user's AI4Research account.

**Description:** The identity, authorization, account-persistence, and local execution-security layer. M1 must preserve attributable user/account identity across product interactions while securely binding local research execution to the active user, workspace, and run. The Architecture Design specification owns the exact cloud/local identity and persistence implementation while preserving the product boundaries defined in Sections 1.1 and 2.3.

#### 5.4.1 Account Registration & User Profile Management (Sub-features 1 & 3)
*   **Definition & Expectation:** Create an individual product account with verified identity and manage user expertise, roles, research preferences, and default product behavior.
*   **M1 State (Whitelist):**
    *   **User-Scoped Product Identity:** Maintain a stable user/account identifier that is logically distinct from the local operating-system account used to execute research workloads.
    *   **Durable Account/Profile Persistence:** User/account profile state must be capable of persisting independently of an individual local research run or local workspace. The Architecture Design specification owns the exact approved persistence mechanism, including any cloud-backed account store.
    *   **Local Execution Binding:** Every local research run must bind the active user/account identity to the applicable workspace and `run_id`.
    *   **Local Runtime Preferences:** Machine-specific execution settings—such as local workspace paths, available hardware, and local model/runtime configuration—remain represented through local configuration and may override applicable account-level defaults for the active execution environment.
    *   **Domain & Project Context:** Run-specific expertise, project constraints, and scientific objectives remain bound to the applicable research request rather than being silently inferred from unrelated historical account state.
*   **Future State (Blacklist for M1):**
    *   Enterprise directory synchronization.
    *   Organization-wide role hierarchies.
    *   Shared multi-user project workspaces.
    *   Complex UI-driven profile-administration workflows.

#### 5.4.2 Authentication & Local Web Security (Sub-feature 2)
*   **Definition & Expectation:** Support secure sign-in, session establishment, session revocation, and suspicious-access visibility.
*   **M1 State (Whitelist):**
    *   **Strict Loopback Binding:** The local OpenJiuwen web application and backend API must be strictly bound to `127.0.0.1` (localhost). It must explicitly reject incoming connections from `0.0.0.0` or external LAN IPs to prevent unauthorized network access.
    *   **Local Session Token Authentication:** Upon `jiuwenswarm-start`, the engine must generate a random session token stored locally with strict `600` file permissions. The local Web UI and CLI must pass this token in the header of all local API requests, preventing local Cross-Site Request Forgery (CSRF) attacks.
*   **Future State (Blacklist for M1):**
    *   Enterprise Single Sign-On (SSO), Multi-Factor Authentication (MFA) prompts, OAuth token flows, or multi-tenant network session cookies.

#### 5.4.3 Runtime Sandboxing & Process Isolation (Security Boundary)
*   **Definition & Expectation:** Isolate untrusted AI-generated code execution, protect local user data, and secure internal API bridges from local machine hijacking.
*   **M1 State (Whitelist):**
    *   **Unprivileged Privilege Dropping:** When the Builder executes AI-generated POC code in Stage 3.7 Benchmarking, the runner must dynamically drop its OS privileges to a restricted `jiuwen-runner` temporary user or `nobody` group. This ensures the AI script strictly only has read/write access to `./workspace/poc/` and cannot access the user's host files or `~/.ssh` keys.
    *   **Secure IPC Codex Bridge:** The Codex CLI adapter (Section 3.0) must communicate with the OpenJiuwen runner via secure Unix Domain Sockets (or named pipes) secured with strict `chmod 600` permissions. Open TCP ports for the adapter are blacklisted to prevent local malware from hijacking the active LLM session.
    *   **POSIX Fixture Isolation:** The installer configures strict POSIX permissions for the RSI Secure Fixture Oracle folder. The Harness Core runs an automated pre-check on boot asserting that the active SwarmFlow runner cannot read the hidden folder, halting execution immediately if the security boundaries have degraded.
*   **Future State (Blacklist for M1):**
    *   Heavy Docker/Kubernetes container orchestration layers, hypervisor-level Virtual Machine (VM) sandboxing, or eBPF kernel-level syscall filtering.

#### 5.4.4 Privacy & Personal Data Controls (Sub-feature 4)
*   **Definition & Expectation:** Let users inspect, export, retain, or delete personal settings and supplied data, and manage consent for message-derived information.
*   **M1 State (Whitelist):**
    *   **Local Execution-Data Transparency:** User-supplied project assets, locally generated research artifacts, execution traces, and local runtime configuration must remain inspectable within the authorized local workspace.
    *   **Account vs. Execution Data Separation:** Cloud-backed account/profile state, when present, must remain logically distinguishable from local research execution data so deletion or movement of a local workspace is not incorrectly represented as deletion of the user's product account.
    *   **Local Data Control:** Users must be able to inspect and remove locally stored project materials, generated artifacts, and execution records through the local filesystem or supported product controls.
    *   **Attributable Persistence:** Any durable account/profile state retained outside the local execution environment must remain attributable to the corresponding user/account identity and governed independently from local run artifacts.
*   **Future State (Blacklist for M1):**
    *   Enterprise retention-policy administration.
    *   Organization-wide legal-hold workflows.
    *   Advanced UI-driven privacy/compliance administration.



### 5.5 Message Channels

> **Architectural Note (Local Execution Interfaces vs. External Integrations):**
> M1 research execution, monitoring, and human-in-the-loop intervention are restricted to the authorized local execution environment through the supported Web UI, CLI, and TUI surfaces. This local execution boundary is distinct from any approved cloud-backed account/profile persistence. External communication connectors such as WeChat, Discord, Slack, and Feishu remain disabled for M1.

**Description:** The communication routing, notification, and remote intake layer. In M1, external messaging integrations are disabled to protect data privacy and maintain a zero-configuration local profile, utilizing local terminal multiplexers for background process isolation instead.

#### 5.5.1 TMUX Session & Terminal Surface Management (Sub-feature 3)
*   **Definition & Expectation:** Register and operate tmux sessions and panes as controlled terminal and runtime surfaces, including ownership, attach and detach, pane-state and log inspection, notifications, recovery, and isolation between runs.
*   **M1 State (Whitelist):**
    *   **Local Process Isolation:** Utilize local `tmux` sessions and panes to manage background execution of the SwarmFlow DAG and local services (`jiuwenswarm-start`).
    *   **State Inspection:** Allow developers to attach/detach from active terminal panes to review live execution logs, check resource states, and inspect fault traces during workflow execution.
*   **Future State (Blacklist for M1):**
    *   Automated multi-node remote terminal synchronization or distributed terminal session forwarding.

#### 5.5.2 External Messaging Integrations: WeChat & Discord (Sub-features 1 & 2)
*   **Definition & Expectation:** Accept external content links (WeChat), connect authorized workspaces via bots (Discord), ingest permitted signals, deliver approval notifications, and manage credential audits.
*   **M1 State:**
    *   **Strictly Blacklisted.** All external chat adapters, webhooks, and bot listeners (WeChat, Discord, Slack, Feishu) are disabled for M1. Ingestion is strictly restricted to local filesystem files (`./workspace/input/`) and direct CLI/WebUI prompt inputs.
*   **Future State (Deferred to M2+):**
    *   Enabling JiuwenSwarm's pre-built channel modules via `config.yaml` to accept external article links, ingest collaborative workspace messages, and dispatch mobile approval notifications.




### 5.6 System Configurations (`config.yaml`)

> **Architectural Note (Declarative Single-Source Configuration):**  
> The platform avoids complex, database-backed administrative panels for system management. Foundational settings, local execution bounds, model endpoints, and approved development/evaluation settings are declared through local configuration. For reproducibility, each run resolves and freezes its effective configuration at run start; later configuration-file changes must not silently alter an already-active run. The Architecture Design owns the exact file structure, precedence mechanism, and runtime configuration implementation.

**Description:** The configuration parsing, validation, and runtime injection layer. In M1, system behavior is governed entirely through static declarative files, explicitly deferring remote configuration syncing and multi-host cluster topology declarations to future milestones.

#### 5.6.1 LLM Configuration (Sub-feature 1)
*   **Definition & Expectation:** Configure provider endpoints and credential references, register available models and aliases, assign role-specific model defaults, and validate the effective model-routing configuration without exposing raw secrets.
*   **M1 State (Whitelist):**
    *   **Codex CLI Endpoint Registration:** Register the Section 3.0 Codex CLI adapter as the primary model provider endpoint within `config.yaml`, bypassing raw enterprise API keys.
    *   **Static Aliases:** Map role-specific agent roles (such as Searcher, Builder, and Verifier) to the static Codex CLI baseline.
    *   **Access-Gated Experimental Endpoint Configuration:** Approved non-Codex model endpoints and credential references may be configured only within an explicit development/evaluation profile after the required access has been granted. Before approval, those profiles may contain only mocked or non-executable endpoint definitions. Experimental endpoint configuration must not alter the normal Phase 1 Codex role aliases.
*   **Future State (Blacklist for M1):**
    *   Dynamic multi-provider credential rotation, cloud secret manager integrations, or runtime API key provisioning.

#### 5.6.2 User Settings (Sub-feature 2)
*   **Definition & Expectation:** Manage persistent user-local preferences such as display identity, timezone, workspace and knowledge paths, runtime choice, search and reasoning options, UI behavior, and ingestion defaults, with validated configuration precedence.
*   **M1 State (Whitelist):**
    *   **Local Workstation Profiles:** Define local paths (`./workspace/input/`, `./workspace/poc/`), hardware constraints (`single_gpu`), and ingestion extensions (`.txt`, `.md`, `.pdf`) directly inside `config.yaml`.
    *   **Configuration Precedence:** Enforce a strict hierarchy where local project configuration files override global user defaults.
*   **Future State (Blacklist for M1):**
    *   Organization-wide shared preference policies, complex UI-driven preference configuration wizards, or multi-user profile switching within a single local execution environment.

#### 5.6.3 Cost & Budget Settings (Sub-feature 3)
*   **Definition & Expectation:** Define and enforce token, call, monetary, compute, and storage budgets and quotas by provider, model, project, or task; track consumption, warn near limits, and block or reroute work when hard limits are reached.
*   **M1 State (Whitelist):**
    *   **Time-Budget Constraints:** Because the subscription-authenticated Codex pathway may not expose reliable per-invocation token usage to the M1 runtime adapter, the configuration enforces strict *Time Budgets* per Capability Capsule execution unless sufficiently reliable call-level usage telemetry is available.
    *   **Invocation Guardrails:** Leverage native JiuwenSwarm telemetry logs and security hooks to monitor call counts and halt execution if operational thresholds are breached.
*   **Future State (Blacklist for M1):**
    *   Real-time monetary cost accounting, cloud billing API quotas, or dynamic work rerouting based on financial thresholds.

#### 5.6.4 Cluster Settings (Sub-feature 4)
*   **Definition & Expectation:** Declare local and remote execution hosts, host types, addresses, lifecycle settings, heartbeat and probe rules, and capacity or concurrency limits, and expose the validated cluster topology to operator binding and scheduling.
*   **M1 State:**
    *   **Strictly Blacklisted.** Distributed execution-cluster configurations, remote worker addresses, heartbeat probes, and concurrency limits across multiple execution hosts are excluded for M1. Research workload execution is confined to one authorized local execution host. This restriction does not apply to approved cloud-backed account/profile persistence or other non-execution product services.
*   **Future State (Deferred to M2+):**
    *   Multi-host distributed cluster topology declarations, remote worker leasing, and cluster scheduling policies.


#### 5.6.5 Development & Evaluation Run Configuration

*   **Definition & Expectation:** Supports reproducible internal evaluation, regression testing, and controlled ablation studies without changing the normal M1 Phase 1 production baseline.

*   **M1 State (Whitelist):**
    *   **Explicit Evaluation Profile:** Development/evaluation runs may use an explicit configuration profile that selects or pins approved benchmark-relevant component states, including capsule versions or capsule-library snapshots, model-routing configuration, Evaluator configuration, RSI participation state, execution seed where supported, and other approved evaluation controls.
    *   **Frozen Effective Configuration:** The effective configuration is resolved and frozen when the run begins. Configuration changes made after run start must not silently change the components participating in that run.
    *   **Controlled Ablation:** Evaluation profiles may intentionally disable or replace approved components when required by a pre-declared ablation study.
    *   **Product-Validity Boundary:** A run that disables or replaces a mandatory M1 product control—such as the Evaluator Gate—must be explicitly marked as a development/evaluation or ablation run. It must not be represented as a valid Phase 1 product run, used to satisfy the M1 Definition of Done, or automatically modify production capsule standing or activation.
    *   **Recorded Effective State:** Benchmark-relevant configuration recorded in the Run Bundle must describe the component state that actually executed, not merely the configuration that was originally requested.

*   **Future State (Blacklist for M1):**
    *   End-user workflow-component customization.
    *   Arbitrary third-party component loading.
    *   Dynamic production reconfiguration during an active run.
    *   User-facing disabling of mandatory safety or verification controls.



## 6. M1 Implementation Order & Integration Plan

### 6.1 Purpose

Sections 3–5 define **what the M1 system must do**. This section defines the required product-level implementation and integration sequence for the M1 baseline.

The implementation sequence is dependency-driven rather than section-number-driven. Implementation work within a stage may be organized or parallelized according to the Architecture Design specification, but a later implementation stage must not be treated as integrated or complete until the required dependencies and Stage Exit Condition of the preceding stage have been satisfied.

The runtime workflow remains the fixed Phase 1 sequence:

**Ingestion → Requirement Compilation → Search & Ideation → Idea Screening → Hypothesis Generation → POC Implementation → Scientific Benchmarking → Scientific Evaluation → Delivery**

However, the supporting infrastructure required to execute and verify that workflow must be implemented before dependent workflow stages are considered complete.

This section defines product-level implementation sequencing only. Detailed system architecture, exact payload schemas, class/interface definitions, service topology, API specifications, and low-level integration design are maintained separately by the Architecture Design workstream.


### 6.2 Implementation Principle

M1 must be built through incremental end-to-end integration rather than by implementing every feature independently and attempting to connect the system at the end.

Each implementation stage must leave behind a runnable and testable system boundary.

A downstream stage must not be considered integrated merely because its isolated business logic exists. It is considered integrated only when:

*   Its required upstream contract is available.
*   Its Capability Capsule is admitted and executable.
*   Its output can be captured in a Stage Evidence Bundle.
*   The Evaluator Gate can issue a valid decision for that output.
*   The Harness can correctly advance or halt based on that decision.
*   Required execution evidence is persisted through Data Foundations.
*   The Stage Exit Condition defined for the implementation stage has been demonstrated.

A failed mandatory validation or unsatisfied Stage Exit Condition must not be silently treated as complete. Independent implementation work may continue where technically possible, but the affected implementation stage and any dependent stage remain incomplete until the blocking condition is resolved or explicitly re-scoped through a product and architecture decision.


### 6.3 Implementation Stage 0 — Runtime Unblocker & Local Configuration

**Primary Sections:** 3.0, 5.4, 5.6

Establish the minimum local runtime required for all later development.

Implementation priorities:

*   Verify and stabilize the Codex CLI adapter.
*   Establish the secured local IPC pathway.
*   Register the Codex CLI adapter as the Phase 1 model endpoint.
*   Establish the minimum `config.yaml` structure required for local execution.
*   Establish local workspace paths and the restricted execution identity/security boundary.
*   Confirm a minimal model request can be sent through JiuwenSwarm and returned successfully.

**Stage Exit Condition:**  
A local JiuwenSwarm process can execute a bounded model call through the configured Codex CLI adapter using the required M1 local-security boundary.


### 6.4 Implementation Stage 1 — Core Governed Execution Backbone

**Primary Sections:** 4.1, 4.3, 4.5, 4.6, 4.2

Build the minimum infrastructure required to execute a governed node before implementing the complete research workflow.

Dependency order for Stage 1:

**Capability Declaration & Admission → Static Model Provisioning → Evidence Persistence → Harness Execution → Evaluator Gate**

Required capabilities:

*   Define and admit a minimal Capability Capsule with its required declaration, implementation resources, provenance, and interface metadata.
*   Establish the Phase 1 static model route and Reviewer provisioning pathway.
*   Establish Run Bundles and append-only execution records.
*   Execute one bounded capsule through the CC Runner.
*   Package its output and runtime evidence into a Stage Evidence Bundle.
*   Submit that bundle to the two-tier Evaluator Gate.
*   Persist the gate result.
*   Allow the Harness to advance only on an advancing gate verdict.
*   Support explicit non-interactive development/evaluation execution in which blocking failures halt and return a stable machine-readable status without invoking `human_session`.
*   Preserve the effective run configuration and benchmark-relevant component identifiers in the resulting Run Bundle.

**Stage Exit Condition:**  
A minimal test workflow can execute:

**Node A → Evaluator Gate → Node B**

and demonstrate:

*   A valid Node A output releases Node B.
*   An intentionally invalid Node A output prevents Node B from starting.
*   The same blocking failure, when executed in explicit headless development/evaluation mode, is durably recorded and terminates with a stable machine-readable status without waiting for `human_session`.


### 6.5 Implementation Stage 2 — Intake, Requirement Contract & Static DAG

**Primary Sections:** 3.1, 3.2, 4.7, 4.8

Establish the front door and fixed Phase 1 workflow contract.

Required capabilities:

*   Accept a natural-language research request.
*   Bind permitted local documents, project assets, and validation resources.
*   Produce a schema-bound `Research_Brief.json`.
*   Apply the fixed Phase 1 intention-compilation behavior and defaults.
*   Load the Research Brief into the hardcoded SwarmFlow Default DAG.
*   Validate the static graph and required capsule bindings.
*   Pass the resulting workflow artifacts through the Evaluator Gate.

**Stage Exit Condition:**  
A user request can enter through the supported local interface, become a validated `Research_Brief.json`, and initialize the fixed M1 SwarmFlow DAG without autonomous planning.


### 6.6 Implementation Stage 3 — Evidence-to-Hypothesis Research Path

**Primary Sections:** 3.3, 3.4, 3.5

Implement the analytical research path sequentially.

Integration order:

**Search & Ideation → Evaluator Gate → Idea Screening → Evaluator Gate → Hypothesis Generation → Evaluator Gate**

Required outputs:

*   `Candidate_Set.json`
*   `Opportunity_Card.json`
*   `Hypothesis_Blueprint.json`

Each stage must operate through its dedicated Capability Capsule and may only advance after the preceding output has passed the infrastructure gate.

**Stage Exit Condition:**  
A validated Research Brief can progress through evidence retrieval, bounded candidate generation, fixed-rubric opportunity selection, and pre-registered hypothesis formation while preserving citations, constraints, and gate evidence.


### 6.7 Implementation Stage 4 — Builder & POC Assembly

**Primary Sections:** 3.6, 4.9

Implement the executable artifact construction boundary.

Required capabilities:

*   Consume the immutable `Hypothesis_Blueprint.json`.
*   Prepare the bounded local POC workspace.
*   Generate the required POC implementation.
*   Generate the benchmark harness.
*   Perform mechanical syntax/readiness validation.
*   Package the result into `POC_Artifact_Bundle.zip`.
*   Submit the bundle and build evidence to the Evaluator Gate.

The Builder must remain limited to executable artifact construction and must not take ownership of analytical outputs produced by Stages 3.3–3.5 or 3.8–3.9.

**Stage Exit Condition:**  
A gate-admitted `Hypothesis_Blueprint.json` can be converted into a bounded, mechanically valid, gate-admitted `POC_Artifact_Bundle.zip` without autonomous repair loops.


### 6.8 Implementation Stage 5 — Benchmarking & Scientific Evaluation

**Primary Sections:** 3.7, 3.8

Implement the empirical research loop.

Integration order:

**POC Artifact → Baseline/Treatment Execution → Benchmark Evidence → Evaluator Gate → Scientific Evaluation → Evaluator Gate**

Required capabilities:

*   Execute baseline and treatment under the declared experimental protocol.
*   Capture raw runtime and benchmark evidence through Data Foundations.
*   Produce `Benchmark_Payload.json`.
*   Verify benchmark admissibility through the infrastructure gate.
*   Evaluate the admitted evidence against the pre-registered hypothesis.
*   Produce `Evaluation_Verdict.json`.
*   Preserve the distinction between scientific verdict and infrastructure verdict.

**Stage Exit Condition:**  
The system can demonstrate both:

*   A scientifically positive result.
*   A scientifically negative but correctly executed result.

Both must reach the appropriate downstream state when their infrastructure execution is valid.


### 6.9 Implementation Stage 6 — Delivery & End-to-End Research Run

**Primary Section:** 3.9

Complete the user-facing research lifecycle.

Required capabilities:

*   Consume the gate-admitted scientific evaluation.
*   Produce the standardized Markdown research report.
*   Package the relevant research artifacts and evidence.
*   Expose the final result through the supported local interface.
*   Close the SwarmFlow lifecycle and persist the completed run record.

**Stage Exit Condition:**  
A single user request can travel from Stage 3.1 through Stage 3.9 with every governed transition represented in the run evidence and controlled by the Evaluator Gate.


### 6.10 Implementation Stage 7 — Operational Shell & Workstation Integration

**Primary Sections:** 5.1–5.6

Once the end-to-end research path is stable, complete the M1 workstation surface around it.

This includes:

*   Runtime visibility and static trace inspection.
*   Installer and workstation initialization.
*   CLI, native Web UI, and TUI integration.
*   Local authentication and security controls.
*   Local terminal/session management.
*   Final configuration and doctor/pre-flight checks.

These features should integrate with the existing runtime rather than redefine workflow behavior or gate policy.

**Stage Exit Condition:**  
A developer can install, initialize, execute, observe, inspect, and retrieve the output of the complete M1 workflow through the supported local workstation interfaces.


### 6.11 Implementation Stage 8 — Local-Isolated RSI Integration

**Primary Section:** 4.4

RSI should be integrated only after the baseline Capability Capsule, evaluation, evidence, and workflow behavior are sufficiently stable to provide meaningful reference fixtures.

Required capabilities:

* Maintain RSI execution outside the live SwarmFlow DAG.
* Establish the approved M1 target profile and bounded mutation surface.
* Seed, separate, and protect the required development, hidden-loop, and hidden-final evaluation sets.
* Permit only explicitly authorized implementation-level mutation.
* Enforce the RSI always-frozen security and referee boundaries.
* Compare candidate versions against the fixed M1 evaluation policy without exposing protected hidden-evaluation material to the proposer or candidate.
* Preserve attributable RSI attempt, evaluation, lineage, and security evidence.
* Require human admission and activation before a candidate version can become active.
* Support explicit rollback of an activated RSI-generated version.
* Execute the M1 RSI security/violation suite, intentionally attempting prohibited hidden-fixture access, referee tampering, permission escalation, out-of-scope mutation, hidden-data leakage, evidence tampering, resource abuse, and promotion bypass.
* Preserve security findings and discovered sandbox vulnerabilities as M1 verification evidence.

**Stage Exit Condition:**  
The Local-Isolated RSI path can propose and evaluate the approved bounded M1 child-capsule target under a fixed and independent referee; protected hidden evaluation material remains inaccessible to the proposer and candidate except through the approved bounded evaluation channel; required adversarial guardrail tests are blocked and recorded; evaluation and audit evidence is reconcilable; and no candidate modifies the live workflow, referee policy, Capability Capsule interface declaration, or active production version without explicit human action.


### 6.12 M1 Delivery Phase 3 — Dynamic System Integration

Phase 3 is part of the expected M1 implementation effort and begins after the corresponding deterministic Phase 1 baseline capabilities are operational and sufficiently stable for comparison.

Phase 3 must not be interpreted as automatically deferred M2 or Future State work.

The implementation must continue into applicable Phase 3 capabilities after completion of Implementation Stage 8 unless a capability is blocked by an explicitly documented dependency, has been removed through a revised product decision, or is technically unavailable within the M1 environment.

#### Dynamic Intention Compilation

*   Integrate the externally developed advanced Intention Compiler when sufficiently available.
*   Preserve the Phase 1 bounded one-shot compiler as the deterministic fallback.
*   Failure or unavailability of the advanced compiler must not block the baseline research workflow.

#### Agent Team / Cluster Mode Dynamic Planning

*   Evaluate and integrate JiuwenSwarm Agent Team / Cluster Mode for dynamic decomposition of user objectives.
*   Permit the Leader Agent to determine runtime tasks, required roles, and task dependencies within the applicable M1 boundaries.
*   Preserve the deterministic Phase 1 SwarmFlow research workflow as the release-critical fallback and comparison baseline.
*   Cluster Mode may invoke deterministic SwarmFlow workflows when useful; dynamic planning and SwarmFlow orchestration are not treated as mutually exclusive execution models.

#### Dynamic Capability Capsule Discovery & Binding

*   Permit the planner to inspect the admitted Capability Capsule registry.
*   Select or bind compatible admitted capabilities to dynamically planned workflow nodes.
*   Dynamic binding must still produce an explicit Node Execution Contract before governed execution begins.
*   No node may invoke an unadmitted capability or silently expand its runtime permissions.

#### Heterogeneous Model Routing

*   Develop and integrate the dynamic routing interfaces and bounded candidate-selection behavior.
*   Before approved external model access is available, exercise routing behavior through mocks or other approved substitutes.
*   After approved access becomes available, exercise approved real endpoints within the Phase 3 configuration.
*   The static Codex route remains the fallback until an alternate route has passed the required validation and has been explicitly approved.

#### Alternate Verifier Model Integration

*   Evaluate approved alternate Reviewer/Verifier provisioning through the existing Evaluator interface.
*   Experimental Verifier models must not change gate policy or acceptance criteria.

#### OpenJiuwen Code Mode

*   Evaluate and integrate applicable Code Mode capabilities where they improve Builder or dynamic execution behavior without weakening the bounded M1 execution model.

Phase 3 implementation must preserve:

*   Evaluator Gate control.
*   Node Execution Contract enforcement.
*   Capability admission requirements.
*   Evidence and provenance requirements.
*   Phase 1 scientific-integrity constraints.
*   Security and execution boundaries.
*   Deterministic fallback paths for release-critical workflow behavior.

For every Phase 3 capability, the implementation must record one of:

*   `PASS` — implemented and validated for the declared M1 scope.
*   `BLOCKED` — implementation cannot validly complete because of an identified external or upstream dependency.
*   `INCOMPLETE` — implementation work exists but the declared M1 acceptance behavior has not yet been demonstrated.

A Phase 3 capability must not be omitted from the M1 implementation simply because it is non-blocking for the core demonstration.

A `BLOCKED` or `INCOMPLETE` Phase 3 capability does not by itself invalidate the core M1 demonstration unless that capability has been explicitly designated as a mandatory M1 acceptance requirement.

All Phase 3 implementation status, validation results, blockers, and known limitations must be recorded in `Phase_3_Completion_Report.md`.


### 6.13 Architecture Handoff Boundary

This PRD defines the product behavior, required capabilities, scope boundaries, integration dependencies, artifacts, acceptance conditions, and implementation sequence for M1.

The Architecture Design specification owns the detailed technical realization of those requirements, including where applicable:

*   Exact JSON and payload schemas.
*   API and IPC interface definitions.
*   Internal module and class boundaries.
*   Process and service topology.
*   Filesystem and persistence layouts.
*   Detailed sequence diagrams.
*   Runtime object models.
*   Dependency injection and adapter design.
*   Low-level security implementation.
*   Error-code and exception structures.
*   Detailed deployment topology.

Where the architecture specification introduces an implementation detail, it must preserve the product behavior, scope boundaries, invariants, and acceptance requirements defined by this PRD.

If an architectural constraint makes a PRD requirement infeasible or requires changing observable product behavior, the discrepancy should be raised as a PRD decision rather than silently resolved within implementation.


### 6.14 M1 Implementation Completion & Core Demo Rule

The **core M1 release/demo gate** is satisfied only when:

*   Implementation Stages 0 through 8 have satisfied their stated Stage Exit Conditions.
*   The M1 Definition of Done in Section 1.5 has been demonstrated.
*   Required Evaluator Gate acceptance and failure-injection cases have passed.
*   The complete M1 Delivery Phase 1 research workflow can execute end-to-end under the required gate, evidence, security, and persistence constraints.
*   The required M1 Delivery Phase 2 Local-Isolated RSI Target 1 path satisfies its M1 acceptance and security requirements.
*   No known mandatory Phase 1 or Phase 2 requirement is being represented as complete solely because its isolated code exists.

An unresolved mandatory requirement, failed Stage Exit Condition, failed required test, or unavailable mandatory dependency in the core M1 release/demo scope must be recorded as an implementation gap or blocking condition rather than silently treated as completed behavior.

M1 Delivery Phase 3 Dynamic System Integration is part of the expected M1 implementation effort but is not automatically part of the core M1 release/demo gate.

Accordingly:

*   Applicable Phase 3 capabilities must be attempted after their required deterministic baselines and dependencies are available.
*   A Phase 3 capability must not be silently skipped or automatically deferred to a later milestone solely because it is non-blocking for the core M1 demonstration.
*   Each applicable Phase 3 capability must receive an explicit recorded status of `PASS`, `BLOCKED`, or `INCOMPLETE`.
*   `PASS`, `BLOCKED`, and `INCOMPLETE` Phase 3 outcomes must be recorded in `Phase_3_Completion_Report.md` and summarized in `M1_Implementation_Report.md`.
*   An explicitly documented Phase 3 blocker or incomplete advanced feature does not by itself invalidate the core M1 demonstration unless that feature has been separately designated as a mandatory M1 acceptance requirement.

The M1 implementation effort is considered fully accounted for only when the core release/demo requirements have been evaluated and every applicable Phase 3 capability has either been validated or explicitly recorded with its blocker or incomplete status.



