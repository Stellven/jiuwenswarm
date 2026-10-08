### 4.7 Intention Compilers

> **Architectural Note & External Dependency Strategy (Ontario Integration Handoff):**
> Advanced intention compilation is an external dependency currently being developed by a cross-office intern in Ontario. To prevent this external dependency from blocking M1 development, the AI4Research platform adopts the same dual-path strategy used for the Codex CLI:
> * **Phase 1 Fixed-Flow Baseline (Immediate Build):** Implement a self-contained, bounded, non-interactive intention compiler that transforms raw intake text into the standardized `Research_Brief.json` contract required by the SwarmFlow Default DAG. The required output contract, conservative defaults, and downstream handoff remain fixed. Internal processing steps and LLM call sequencing are defined by the Architecture Design. Interactive clarification, autonomous replanning, and dynamic workflow selection are excluded from this fallback.
> * **M1 Delivery Phase 3 Modular Integration (Standardized Target Interface):** The sub-features below define the standardized contract and output envelope expected from the Ontario intern's module. When completed, their dynamic/interactive intention compiler will plug directly into the M1 Delivery Phase 3 Agent Team / Cluster Mode integration pathway without requiring downstream workflow nodes to change their input contract.
> * **Permanent Fixed-Flow Fallback:** The Phase 1 bounded, non-interactive compiler remains available as a stable fallback pathway after the dynamic compiler is introduced. It preserves the fixed `Research_Brief.json` interface and bounded compilation behavior, while continuing to require the configured M1 model endpoint for semantic extraction.

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
    * Extract the core research objective, explicit parameters, and binary `in_scope` versus `out_of_scope` lists from the qualified intake, without introducing unsupported assumptions or information from undeclared external sources.
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